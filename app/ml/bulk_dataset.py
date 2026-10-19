"""Resumable, isolated CSV dataset collection; never writes the production ML store."""
from __future__ import annotations

import asyncio
import csv
import gzip
import json
import os
import shutil
import sqlite3
import time
import zlib
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.errors import ApiAuthenticationError, ApiRateLimited, PlayerNotFound, UpstreamUnavailable
from app.ml.collector import COMPETITIVE_REGIONS
from app.ml.database import generate_match_fingerprint


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def clean_tag(value: Any) -> str:
    value = str(value or '').strip().upper().lstrip('#')
    return '#' + value if value and value.isalnum() and 'UNKNOWN' not in value else ''


@contextmanager
def dataset_lock(directory: Path):
    """An OS lock releases on crashes too; two workers cannot collect the same dataset."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'worker.lock').open('a+b') as handle:
        handle.write(b'1')
        handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class BulkDataset:
    """SQLite is a temporary dedup/checkpoint index. CSVs are the portable deliverable."""

    def __init__(self, directory: Path, target_players=100000, matches_per_player=50):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(directory / 'checkpoint.sqlite', timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA synchronous=NORMAL')
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS players (
                tag TEXT PRIMARY KEY, name TEXT NOT NULL, trophies INTEGER NOT NULL,
                source TEXT NOT NULL, region TEXT, priority INTEGER NOT NULL,
                discovered_at TEXT NOT NULL, cohort INTEGER NOT NULL DEFAULT 0,
                distinct_matches INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
                idle_polls INTEGER NOT NULL DEFAULT 0, next_poll REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending', last_polled_at TEXT);
            CREATE INDEX IF NOT EXISTS idx_bulk_due ON players(cohort, status, next_poll);
            CREATE INDEX IF NOT EXISTS idx_bulk_poll_order ON players(cohort,status,next_poll,priority DESC,trophies DESC);
            CREATE INDEX IF NOT EXISTS idx_bulk_discovery ON players(attempts,priority DESC,trophies DESC);
            CREATE TABLE IF NOT EXISTS matches (
                fingerprint TEXT PRIMARY KEY, battle_time TEXT NOT NULL, mode TEXT NOT NULL,
                map TEXT NOT NULL, match_type TEXT NOT NULL, first_source_tag TEXT NOT NULL,
                trainable_3v3 INTEGER NOT NULL, raw_json BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS observations (
                player_tag TEXT NOT NULL REFERENCES players(tag),
                fingerprint TEXT NOT NULL REFERENCES matches(fingerprint),
                result TEXT, trophy_change INTEGER, showdown_rank INTEGER, observed_at TEXT NOT NULL,
                PRIMARY KEY(player_tag, fingerprint));
            CREATE TABLE IF NOT EXISTS tasks (
                key TEXT PRIMARY KEY, kind TEXT NOT NULL, region TEXT, entity TEXT,
                priority INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0, due REAL NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS idx_bulk_tasks ON tasks(status,priority,key);
        ''')
        prior = self.get('config')
        config = {'target_players': target_players, 'matches_per_player': matches_per_player}
        if prior is not None and json.loads(prior) != config:
            self.conn.close()
            raise ValueError('Existing dataset has different targets. Resume with the original targets or use a new directory.')
        self.target_players = target_players
        self.matches_per_player = matches_per_player
        if prior is None:
            self.set('config', json.dumps(config))
            self.set('started_at', utc_now())
            self.set('requests', '0')
            self.set('malformed_entries', '0')
            self.set('phase', 'discovery')
            self.set('csv_formula_escaping', 'Leading formula characters in text fields are prefixed with an apostrophe.')

    def get(self, key: str) -> str | None:
        row = self.conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str):
        with self.conn:
            self.conn.execute('INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))

    def increment(self, key: str, amount=1):
        self.set(key, str(int(self.get(key) or 0) + amount))

    def add_task(self, kind: str, region='', entity='', priority=0):
        self.conn.execute('INSERT OR IGNORE INTO tasks(key,kind,region,entity,priority) VALUES (?,?,?,?,?)',
                          (f'{kind}:{region}:{entity}', kind, region, str(entity), priority))

    def seed_tasks(self, regions: list[str]):
        if self.get('regions') is not None:
            return
        with self.conn:
            for index, region in enumerate(regions):
                self.add_task('players', region, priority=index)
                self.add_task('clubs', region, priority=1000 + index)
            self.add_task('brawlers', priority=3000)
        self.set('regions', json.dumps(regions))

    def add_players(self, items: list[dict], source: str, region='', priority=1, account_trophies=True):
        rows = []
        for item in items:
            if tag := clean_tag(item.get('tag')):
                rows.append((tag, str(item.get('name') or 'Player'),
                             int(item.get('trophies') or 0) if account_trophies else 0,
                             source, region, priority, utc_now()))
        with self.conn:
            self.conn.executemany('''
                INSERT INTO players(tag,name,trophies,source,region,priority,discovered_at) VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(tag) DO UPDATE SET
                    name=CASE WHEN excluded.name='Player' THEN players.name ELSE excluded.name END,
                    trophies=MAX(players.trophies, excluded.trophies),
                    source=CASE WHEN excluded.priority>players.priority THEN excluded.source ELSE players.source END,
                    region=CASE WHEN excluded.priority>players.priority THEN excluded.region ELSE players.region END,
                    priority=MAX(players.priority, excluded.priority)
            ''', rows)

    def player_count(self) -> int:
        return self.conn.execute('SELECT COUNT(*) FROM players').fetchone()[0]

    def freeze_cohort(self):
        # Known account trophies first. Brawler-trophy figures are deliberately not account trophies.
        with self.conn:
            self.conn.execute('''UPDATE players SET cohort=1 WHERE tag IN (
                SELECT tag FROM players ORDER BY priority DESC, trophies DESC, tag LIMIT ?)
            ''', (self.target_players,))
        self.set('phase', 'collection')

    def save_poll(self, tag: str, items: list[dict], poll_seconds: float, idle_limit: int) -> int:
        """One durable transaction per response; cap observations, never count repeats as new."""
        row = self.conn.execute('SELECT * FROM players WHERE tag=?', (tag,)).fetchone()
        remaining = self.matches_per_player - row['distinct_matches']
        added = malformed = 0
        discovered = []
        with self.conn:
            for item in items:
                if added >= remaining:
                    break
                try:
                    battle_time = item['battleTime']
                    datetime.strptime(battle_time, '%Y%m%dT%H%M%S.%fZ')
                    battle = item.get('battle') or {}
                    event = item.get('event') or {}
                    teams = battle.get('teams') or []
                    groups = teams or [battle.get('players') or []]
                    people = [player for group in groups for player in group]
                    tags = [clean_tag(player.get('tag')) for player in people]
                    if tag not in tags:
                        # The result is relative to the source; don't invent source observations.
                        raise ValueError('Source player missing')
                    mode = battle.get('mode') or event.get('mode') or 'unknown'
                    map_name = event.get('map') or 'Unknown Map'
                    fingerprint = generate_match_fingerprint(battle_time, map_name, mode, tags,
                        [int((player.get('brawler') or {}).get('id') or 0) for player in people])
                    trainable = (len(teams) == 2 and all(len(team) == 3 for team in teams)
                        and len(set(tags)) == 6 and all(tags)
                        and battle.get('result') in {'victory', 'defeat'}
                        and battle.get('type') != 'friendly'
                        and all(int((player.get('brawler') or {}).get('power') or 0) > 0
                                and int((player.get('brawler') or {}).get('id') or 0) > 0 for player in people))
                    raw_json = zlib.compress(json.dumps(item, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), level=3)
                    self.conn.execute('''INSERT OR IGNORE INTO matches VALUES (?,?,?,?,?,?,?,?)''',
                        (fingerprint, battle_time, mode, map_name, battle.get('type') or 'unknown', tag,
                         int(trainable), raw_json))
                    if trainable:
                        # Keep the source tag and raw source-relative outcome together if an earlier
                        # observation lacked an eligible result or complete power information.
                        self.conn.execute('''UPDATE matches SET trainable_3v3=1,first_source_tag=?,raw_json=?
                            WHERE fingerprint=? AND trainable_3v3=0''',
                            (tag, raw_json, fingerprint))
                    cursor = self.conn.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?)',
                        (tag, fingerprint, battle.get('result'), battle.get('trophyChange'), battle.get('rank'), utc_now()))
                    added += cursor.rowcount
                    discovered.extend({'tag': player.get('tag'), 'name': player.get('name')} for player in people)
                except (ValueError, TypeError, KeyError, AttributeError):
                    malformed += 1
            count = row['distinct_matches'] + added
            idle = 0 if added else row['idle_polls'] + 1
            status = 'complete' if count >= self.matches_per_player else 'stalled' if idle >= idle_limit else 'pending'
            self.conn.execute('''UPDATE players SET distinct_matches=?, attempts=attempts+1,
                idle_polls=?, next_poll=?, status=?, last_polled_at=? WHERE tag=?''',
                (count, idle, time.time() + poll_seconds, status, utc_now(), tag))
        if self.get('phase') == 'discovery':
            self.add_players(discovered, 'match_participant', priority=0, account_trophies=False)
        if malformed:
            self.increment('malformed_entries', malformed)
        return added

    def fail_player(self, tag: str, permanent: bool, retry_seconds: float):
        with self.conn:
            self.conn.execute('''UPDATE players SET attempts=attempts+1, next_poll=?,
                status=?,last_polled_at=? WHERE tag=?''',
                (time.time() + retry_seconds, 'unavailable' if permanent else 'pending', utc_now(), tag))

    def summary(self) -> dict:
        totals = dict(self.conn.execute('''SELECT COUNT(*) AS candidate_tags,
            SUM(cohort) AS selected_players, SUM(cohort AND attempts>0) AS players_polled,
            SUM(cohort AND status='complete') AS players_at_target,
            SUM(cohort AND status='stalled') AS stalled_players,
            SUM(cohort AND status='unavailable') AS unavailable_players FROM players''').fetchone())
        totals = {key: value or 0 for key, value in totals.items()}
        matches = self.conn.execute('SELECT COUNT(*),SUM(trainable_3v3) FROM matches').fetchone()
        observations = self.conn.execute('SELECT COUNT(*) FROM observations').fetchone()[0]
        return {**totals, 'target_players': self.target_players, 'matches_per_player': self.matches_per_player,
            'unique_matches': matches[0], 'eligible_3v3_matches': matches[1] or 0,
            'player_match_observations': observations,
            'target_observations': self.target_players * self.matches_per_player,
            'requests': int(self.get('requests') or 0), 'malformed_entries': int(self.get('malformed_entries') or 0),
            'phase': self.get('phase'), 'state': self.get('state') or 'ready', 'message': self.get('message') or '',
            'started_at': self.get('started_at'), 'updated_at': utc_now(), 'worker_pid': os.getpid(),
            'last_full_csv_export': self.get('last_full_csv_export')}

    def publish_status(self, state: str, message=''):
        self.set('state', state)
        self.set('message', message)
        tmp = self.directory / 'progress.json.tmp'
        tmp.write_text(json.dumps(self.summary(), indent=2), encoding='utf-8')
        tmp.replace(self.directory / 'progress.json')

    def export_csv(self, players_only=False):
        """Stream rows from a consistent read snapshot, replacing complete files atomically."""
        queries = {'players.csv': '''SELECT tag,name,trophies,source,region,discovered_at,cohort,
            distinct_matches,attempts,idle_polls,status,last_polled_at FROM players
            ''' + ('WHERE cohort=1 ' if self.get('phase') == 'collection' else '') +
            'ORDER BY cohort DESC,priority DESC,trophies DESC,tag'}
        if not players_only:
            queries.update({'matches.csv.gz': 'SELECT * FROM matches',
                            'player_matches.csv.gz': 'SELECT * FROM observations'})
        reader = sqlite3.connect(self.directory / 'checkpoint.sqlite', timeout=30)
        reader.execute('BEGIN')
        try:
            for filename, query in queries.items():
                cursor = reader.execute(query)
                tmp = self.directory / (filename + '.tmp')
                opener = gzip.open if filename.endswith('.gz') else open
                options = {'compresslevel': 3} if filename.endswith('.gz') else {}
                with opener(tmp, 'wt', encoding='utf-8', newline='', **options) as handle:
                    writer = csv.writer(handle)
                    writer.writerow([column[0] for column in cursor.description])
                    for row in cursor:
                        values = [zlib.decompress(value).decode('utf-8') if isinstance(value, bytes) else value for value in row]
                        writer.writerow(["'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r'))
                                         else value for value in values])
                tmp.replace(self.directory / filename)
        finally:
            reader.close()
        if not players_only:
            self.set('last_full_csv_export', utc_now())
        manifest = self.summary()
        manifest['files'] = [name for name in ('players.csv', 'matches.csv.gz', 'player_matches.csv.gz')
                             if (self.directory / name).exists()]
        manifest['format'] = 'Raw JSON is from first_source_tag; player_matches.csv.gz stores each source-relative result separately. Gzip files contain standard UTF-8 CSV.'
        manifest['csv_formula_escaping'] = self.get('csv_formula_escaping')
        manifest['note'] = 'Only up to 25 recent matches are available per poll. 50 distinct matches need later activity. Discovery sources are not a global top-100000 ranking.'
        tmp = self.directory / 'manifest.json.tmp'
        tmp.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        tmp.replace(self.directory / 'manifest.json')

    def close(self):
        self.conn.close()


class BulkDatasetWorker:
    def __init__(self, client, dataset: BulkDataset, rps=3.0, poll_hours=6.0, idle_limit=12,
                 export_seconds=3600, max_requests=0, regions=None):
        self.client, self.db = client, dataset
        self.interval = 1 / rps
        self.poll_seconds = poll_hours * 3600
        self.idle_limit = idle_limit
        self.export_seconds = export_seconds
        self.max_requests = max_requests
        self.regions = regions or COMPETITIVE_REGIONS
        self.last_request = 0.0
        self.last_export = self.last_status = time.monotonic()
        self.session_requests = 0
        self.backoff = 0

    async def request(self, call, *args):
        await asyncio.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        self.session_requests += 1
        self.db.increment('requests')
        return await call(*args)

    async def discovery_step(self):
        if self.db.player_count() >= self.db.target_players:
            self.db.freeze_cohort()
            self.db.export_csv(players_only=True)
            return
        row = self.db.conn.execute("SELECT * FROM tasks WHERE status='pending' AND due<=? ORDER BY priority,key LIMIT 1", (time.time(),)).fetchone()
        if row:
            kind, region, entity = row['kind'], row['region'], row['entity']
            try:
                if kind == 'players':
                    data = await self.request(self.client.get_rankings_players, region)
                    self.db.add_players(data.get('items', []), 'account_leaderboard', region, priority=3)
                elif kind == 'clubs':
                    data = await self.request(self.client.get_rankings_clubs, region)
                    with self.db.conn:
                        for rank, item in enumerate(data.get('items', [])[:100]):
                            if tag := clean_tag(item.get('tag')):
                                # Globally ranked clubs are requested first; shared clubs are deduplicated.
                                self.db.add_task('members', entity=tag, priority=2000 + rank)
                elif kind == 'members':
                    data = await self.request(self.client.get_club, entity)
                    self.db.add_players(data.get('members', []), f'top_club:{entity}', priority=2)
                elif kind == 'brawlers':
                    data = await self.request(self.client.get_brawlers)
                    with self.db.conn:
                        for item in data.get('items', []):
                            if brawler_id := item.get('id'):
                                self.db.add_task('brawler_ranking', 'global', brawler_id, priority=4000)
                                for index, country in enumerate(self.regions):
                                    if country != 'global':
                                        self.db.add_task('brawler_ranking', country, brawler_id, priority=5000 + index)
                else:
                    data = await self.request(self.client.get_rankings_brawler, int(entity), region)
                    self.db.add_players(data.get('items', []), f'brawler_leaderboard:{entity}', region,
                                        priority=1, account_trophies=False)
                with self.db.conn:
                    self.db.conn.execute("UPDATE tasks SET status='done',attempts=attempts+1 WHERE key=?", (row['key'],))
                self.db.set('message', f'Discovery: {kind} {region} {entity}')
            except PlayerNotFound:
                with self.db.conn:
                    self.db.conn.execute("UPDATE tasks SET status='unavailable',attempts=attempts+1 WHERE key=?", (row['key'],))
            except UpstreamUnavailable:
                attempts = row['attempts'] + 1
                with self.db.conn:
                    self.db.conn.execute("UPDATE tasks SET status=?,attempts=?,due=? WHERE key=?",
                        ('unavailable' if attempts >= 5 else 'pending', attempts, time.time() + 60 * attempts, row['key']))
                raise
            return
        if self.db.conn.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0]:
            await asyncio.sleep(5)
            return
        # Rankings can exhaust before 100k. Expand via participants, labelled explicitly.
        player = self.db.conn.execute("SELECT * FROM players WHERE attempts=0 ORDER BY priority DESC,trophies DESC LIMIT 1").fetchone()
        if player is None:
            self.db.freeze_cohort()  # Collect the available sample; report the shortfall at the end.
            return
        try:
            data = await self.request(self.client.get_battlelog, player['tag'])
            self.db.save_poll(player['tag'], data.get('items', []), self.poll_seconds, self.idle_limit)
        except PlayerNotFound:
            self.db.fail_player(player['tag'], True, self.poll_seconds)
        except UpstreamUnavailable:
            self.db.fail_player(player['tag'], player['attempts'] >= 4, 300)
            raise

    async def collection_step(self) -> bool:
        player = self.db.conn.execute('''SELECT * FROM players WHERE cohort=1 AND status='pending'
            AND next_poll<=? ORDER BY next_poll,priority DESC,trophies DESC LIMIT 1''', (time.time(),)).fetchone()
        if player is None:
            due = self.db.conn.execute("SELECT MIN(next_poll) FROM players WHERE cohort=1 AND status='pending'").fetchone()[0]
            if due is None:
                return False
            self.db.set('message', 'Waiting for new player matches; completed players are skipped.')
            await asyncio.sleep(min(30, max(0.1, due - time.time())))
            return True
        try:
            data = await self.request(self.client.get_battlelog, player['tag'])
            added = self.db.save_poll(player['tag'], data.get('items', []), self.poll_seconds, self.idle_limit)
            self.db.set('message', f"Polled {player['tag']}: {added} new distinct matches")
        except PlayerNotFound:
            self.db.fail_player(player['tag'], True, self.poll_seconds)
        except UpstreamUnavailable:
            self.db.fail_player(player['tag'], False, min(self.poll_seconds, 300))
            raise
        return True

    async def run(self):
        self.db.seed_tasks(self.regions)
        self.db.publish_status('running', 'Resuming durable checkpoints')
        self.db.export_csv(players_only=shutil.disk_usage(self.db.directory).free < 3 * 1024**3)
        try:
            while True:
                if (self.db.directory / 'stop.request').exists():
                    self.db.publish_status('stopped', 'Stop requested; run the command again to resume.')
                    break
                if self.max_requests and self.session_requests >= self.max_requests:
                    self.db.publish_status('stopped', 'Session request budget reached; resume to continue.')
                    break
                if shutil.disk_usage(self.db.directory).free < 3 * 1024**3:
                    self.db.publish_status('disk_low', 'Less than 3 GiB free. Collection is checkpointed; free space and resume.')
                    break
                try:
                    if self.db.get('phase') == 'discovery':
                        await self.discovery_step()
                    elif not await self.collection_step():
                        summary = self.db.summary()
                        complete = summary['players_at_target'] == self.db.target_players
                        self.db.publish_status('complete' if complete else 'incomplete',
                            'Target achieved.' if complete else 'Available rankings/activity exhausted; remaining gaps are recorded, not padded.')
                        break
                    self.backoff = 0
                except ApiAuthenticationError:
                    self.db.publish_status('needs_token', 'Token is invalid or not authorized for the current IP. Update .env and resume.')
                    break
                except (ApiRateLimited, UpstreamUnavailable) as exc:
                    self.backoff = min(900, max(60, self.backoff * 2))
                    self.db.publish_status('backoff', f'{type(exc).__name__}; retrying after {self.backoff}s')
                    deadline = time.monotonic() + self.backoff
                    while time.monotonic() < deadline and not (self.db.directory / 'stop.request').exists():
                        await asyncio.sleep(min(10, max(0, deadline - time.monotonic())))
                now = time.monotonic()
                if now - self.last_status >= 30:
                    self.db.publish_status('running', self.db.get('message') or '')
                    self.db.export_csv(players_only=True)
                    self.last_status = now
                    print(json.dumps(self.db.summary()), flush=True)
                if now - self.last_export >= self.export_seconds:
                    self.db.export_csv()
                    self.last_export = now
        except asyncio.CancelledError:
            self.db.publish_status('stopped', 'Worker interrupted; checkpoints can be resumed.')
            raise
        except Exception as exc:
            self.db.publish_status('error', f'{type(exc).__name__}; inspect worker.stderr.log')
            raise
        finally:
            self.db.export_csv(players_only=self.db.get('state') == 'disk_low')
