from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("brawlbuddy.ml.database")


def generate_match_fingerprint(
    battle_time: str,
    event_map: str,
    mode: str,
    participant_tags: list[str],
    brawler_ids: Optional[list[int]] = None,
) -> str:
    """Generate a collision-resistant deterministic match fingerprint.
    
    Uses UTC battle timestamp, normalized map name, game mode, and sorted unique
    participant tags. If participant tags are sparse, incorporates brawler IDs.
    """
    clean_time = (battle_time or "").strip()
    clean_map = (event_map or "unknown").strip().lower()
    clean_mode = (mode or "unknown").strip().lower()
    clean_tags = sorted(list({t.strip().upper() for t in participant_tags if t and t.strip()}))
    
    if clean_tags:
        key_str = f"{clean_time}|{clean_map}|{clean_mode}|{','.join(clean_tags)}"
    else:
        sorted_brawlers = sorted([str(b) for b in (brawler_ids or [])])
        key_str = f"{clean_time}|{clean_map}|{clean_mode}|brawlers:{','.join(sorted_brawlers)}"
        
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:24]


class MetaDatabase:
    """Persistent SQLite store for competitive players, matches, and participants."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        with closing(self.connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    tag TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    trophies INTEGER NOT NULL DEFAULT 0,
                    highest_trophies INTEGER NOT NULL DEFAULT 0,
                    club_name TEXT,
                    source TEXT NOT NULL DEFAULT 'unknown',
                    discovered_at TEXT NOT NULL,
                    last_polled_at TEXT,
                    battle_count INTEGER NOT NULL DEFAULT 0,
                    priority INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    match_fingerprint TEXT PRIMARY KEY,
                    battle_time TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    event_mode TEXT,
                    map TEXT NOT NULL,
                    event_id INTEGER DEFAULT 0,
                    match_type TEXT NOT NULL DEFAULT 'ranked',
                    duration INTEGER,
                    trophy_change INTEGER,
                    result TEXT,
                    team_a_avg_power REAL DEFAULT 0.0,
                    team_b_avg_power REAL DEFAULT 0.0,
                    power_advantage TEXT DEFAULT 'balanced',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS match_participants (
                    match_fingerprint TEXT NOT NULL,
                    player_tag TEXT NOT NULL,
                    team_index INTEGER NOT NULL,
                    brawler_id INTEGER NOT NULL,
                    brawler_name TEXT NOT NULL,
                    brawler_power INTEGER NOT NULL DEFAULT 1,
                    brawler_trophies INTEGER NOT NULL DEFAULT 0,
                    is_star_player INTEGER NOT NULL DEFAULT 0,
                    is_winner INTEGER,
                    PRIMARY KEY (match_fingerprint, player_tag, brawler_id),
                    FOREIGN KEY (match_fingerprint) REFERENCES matches(match_fingerprint) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_checkpoints (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # Indices for lightning-fast statistical queries and deduplication
            conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_mode_map ON matches(mode, map)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_battle_time ON matches(battle_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_type ON matches(match_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_participants_brawler ON match_participants(brawler_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_participants_match ON match_participants(match_fingerprint)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_participants_brawler_mode_map ON match_participants(brawler_id, is_winner)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_players_polled ON players(last_polled_at, priority)")
            columns = {r['name'] for r in conn.execute('PRAGMA table_info(matches)')}
            if 'ingestion_version' not in columns:
                # Keep legacy rows for auditing; their source-relative labels cannot be verified.
                conn.execute('ALTER TABLE matches ADD COLUMN ingestion_version INTEGER NOT NULL DEFAULT 0')

    def save_player(
        self,
        tag: str,
        name: str,
        trophies: int = 0,
        highest_trophies: int = 0,
        club_name: Optional[str] = None,
        source: str = "leaderboard",
        priority: int = 1,
    ) -> bool:
        """Insert or update player discovery info."""
        clean_tag = tag.strip().upper()
        if not clean_tag.startswith("#"):
            clean_tag = f"#{clean_tag}"
        now_iso = datetime.now(UTC).isoformat()
        with closing(self.connect()) as conn, conn:
            cur = conn.execute(
                """
                INSERT INTO players (tag, name, trophies, highest_trophies, club_name, source, discovered_at, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tag) DO UPDATE SET
                    name = CASE WHEN excluded.name != 'Player' THEN excluded.name ELSE players.name END,
                    trophies = CASE WHEN excluded.trophies > 0 THEN excluded.trophies ELSE players.trophies END,
                    highest_trophies = MAX(players.highest_trophies, excluded.highest_trophies),
                    club_name = COALESCE(excluded.club_name, players.club_name),
                    priority = MAX(players.priority, excluded.priority)
                """,
                (clean_tag, name, trophies, highest_trophies, club_name, source, now_iso, priority),
            )
            return cur.rowcount > 0

    def mark_player_polled(self, tag: str, battles_found: int) -> None:
        clean_tag = tag.strip().upper()
        if not clean_tag.startswith("#"):
            clean_tag = f"#{clean_tag}"
        now_iso = datetime.now(UTC).isoformat()
        with closing(self.connect()) as conn, conn:
            conn.execute(
                """
                UPDATE players
                SET last_polled_at = ?, battle_count = battle_count + ?
                WHERE tag = ?
                """,
                (now_iso, battles_found, clean_tag),
            )

    def get_unpolled_players(self, limit: int = 200) -> list[sqlite3.Row]:
        """Fetch players prioritized by unpolled status, oldest poll, and priority."""
        with closing(self.connect()) as conn:
            cur = conn.execute(
                """
                SELECT * FROM players
                WHERE tag NOT GLOB '*_*'
                ORDER BY
                    CASE WHEN last_polled_at IS NULL THEN 0 ELSE 1 END ASC,
                    last_polled_at ASC,
                    priority DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cur.fetchall()

    def get_player_count(self) -> int:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM players").fetchone()
            return row["cnt"] if row else 0

    def get_match_count(self) -> int:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM matches").fetchone()
            return row["cnt"] if row else 0

    def save_match(
        self,
        raw_battle: dict[str, Any],
        source_player_tag: str,
    ) -> tuple[bool, str, list[dict[str, Any]]]:
        """Ingest, fingerprint, and deduplicate a battle log entry.
        
        Returns:
            tuple of (is_new_match, fingerprint, discovered_participants)
        """
        battle = raw_battle.get("battle") or {}
        event = raw_battle.get("event") or {}
        battle_time = raw_battle.get("battleTime") or ""
        try:
            datetime.strptime(battle_time, "%Y%m%dT%H%M%S.%fZ")
        except (ValueError, TypeError):
            raise ValueError("A valid battle timestamp is required for deduplication")
        normalize = lambda tag: "#" + str(tag or "").strip().upper().lstrip("#") if tag else ""
        source = normalize(source_player_tag)
        event_map = event.get("map") or "Unknown Map"
        mode = battle.get("mode") or event.get("mode") or "unknown"
        result = battle.get("result")
        teams = battle.get("teams") or []
        # The same match can arrive with opposite team order from another player's log.
        teams = sorted(teams, key=lambda team: sorted(normalize(p.get("tag")) for p in team))
        source_teams = [i for i, team in enumerate(teams) if any(normalize(p.get("tag")) == source for p in team)]
        winner_team = None
        if len(teams) == 2 and len(source_teams) == 1 and result in {"victory", "defeat"}:
            winner_team = source_teams[0] if result == "victory" else 1 - source_teams[0]
        participants = []
        groups = teams or [battle.get("players") or []]
        for team_index, members in enumerate(groups):
            for slot, player in enumerate(members):
                tag = normalize(player.get("tag"))
                brawler = player.get("brawler") or {}
                participants.append({
                    "player_tag": tag or f"#UNKNOWN_{team_index}_{slot}",
                    "name": player.get("name") or "Player",
                    "team_index": team_index,
                    "brawler_id": int(brawler.get("id") or 0),
                    "brawler_name": brawler.get("name") or "Unknown",
                    "brawler_power": int(brawler.get("power") or 0),
                    "brawler_trophies": int(brawler.get("trophies") or 0),
                    "is_star_player": int(bool(tag) and tag == normalize((battle.get("starPlayer") or {}).get("tag"))),
                    # Draws, missing source players, PvE and showdown placements have no binary team outcome.
                    "is_winner": int(team_index == winner_team) if winner_team is not None else None,
                })
        tags = [p["player_tag"] for p in participants]
        fingerprint = generate_match_fingerprint(battle_time, event_map, mode, tags,
                                               [p["brawler_id"] for p in participants])
        averages = []
        for index in (0, 1):
            powers = [p["brawler_power"] for p in participants if p["team_index"] == index]
            averages.append(round(sum(powers) / len(powers), 2) if powers and all(powers) else 0)
        diff = averages[0] - averages[1]
        advantage = "blue_favored" if diff >= .5 else "red_favored" if diff <= -.5 else "balanced"
        with closing(self.connect()) as conn, conn:
            existing = conn.execute('SELECT ingestion_version FROM matches WHERE match_fingerprint = ?', (fingerprint,)).fetchone()
            is_new = existing is None
            if existing is None or existing['ingestion_version'] < 2:
                conn.execute("""
                    INSERT INTO matches (match_fingerprint, battle_time, mode, event_mode, map, event_id,
                        match_type, duration, trophy_change, result, team_a_avg_power, team_b_avg_power,
                        power_advantage, created_at, ingestion_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 2)
                    ON CONFLICT(match_fingerprint) DO UPDATE SET
                        team_a_avg_power=excluded.team_a_avg_power, team_b_avg_power=excluded.team_b_avg_power,
                        result=excluded.result, ingestion_version=2
                """, (fingerprint, battle_time, mode, event.get('mode'), event_map, event.get('id', 0),
                      battle.get('type') or 'unknown', battle.get('duration'), battle.get('trophyChange'),
                      result, *averages, advantage, datetime.now(UTC).isoformat()))
                conn.execute('DELETE FROM match_participants WHERE match_fingerprint=?', (fingerprint,))
            for part in participants:
                conn.execute("""
                    INSERT INTO match_participants (match_fingerprint, player_tag, team_index, brawler_id,
                        brawler_name, brawler_power, brawler_trophies, is_star_player, is_winner)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(match_fingerprint, player_tag, brawler_id) DO UPDATE SET
                        is_winner=COALESCE(match_participants.is_winner, excluded.is_winner),
                        is_star_player=MAX(match_participants.is_star_player, excluded.is_star_player)
                """, (fingerprint, part['player_tag'], part['team_index'], part['brawler_id'],
                      part['brawler_name'], part['brawler_power'], part['brawler_trophies'],
                      part['is_star_player'], part['is_winner']))
        return is_new, fingerprint, [p for p in participants if 'UNKNOWN' not in p['player_tag']]

    def get_checkpoint(self, key: str) -> Optional[str]:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT value FROM collection_checkpoints WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def set_checkpoint(self, key: str, value: str) -> None:
        now_iso = datetime.now(UTC).isoformat()
        with closing(self.connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO collection_checkpoints (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, now_iso),
            )

    def save_players_batch(self, player_dicts: list[dict[str, Any]]) -> int:
        """Batch insert or update multiple players in a single transaction."""
        if not player_dicts:
            return 0
        now_iso = datetime.now(UTC).isoformat()
        rows = []
        for p in player_dicts:
            raw_tag = p.get("tag") or ""
            clean_tag = raw_tag.strip().upper()
            if not clean_tag or not clean_tag.startswith("#") or "UNKNOWN" in clean_tag:
                if clean_tag and not clean_tag.startswith("#") and "UNKNOWN" not in clean_tag:
                    clean_tag = f"#{clean_tag}"
                else:
                    continue
            if not clean_tag[1:].isalnum():
                continue
            rows.append((
                clean_tag,
                p.get("name", "Player"),
                int(p.get("trophies", 0)),
                int(p.get("highest_trophies", p.get("trophies", 0))),
                p.get("club_name"),
                p.get("source", "batch"),
                now_iso,
                int(p.get("priority", 1)),
            ))
        if not rows:
            return 0
        with closing(self.connect()) as conn, conn:
            before = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            cur = conn.executemany(
                """
                INSERT INTO players (tag, name, trophies, highest_trophies, club_name, source, discovered_at, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tag) DO UPDATE SET
                    name = CASE WHEN excluded.name != 'Player' THEN excluded.name ELSE players.name END,
                    trophies = CASE WHEN excluded.trophies > 0 THEN excluded.trophies ELSE players.trophies END,
                    highest_trophies = MAX(players.highest_trophies, excluded.highest_trophies),
                    club_name = COALESCE(excluded.club_name, players.club_name),
                    priority = MAX(players.priority, excluded.priority)
                """,
                rows,
            )
            return conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] - before

    def extract_participants_as_players(self) -> int:
        """Ingest all known battle participants from matches into the players table."""
        with closing(self.connect()) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT player_tag
                FROM match_participants
                WHERE player_tag LIKE '#%' AND player_tag NOT LIKE '%UNKNOWN%'
                """
            ).fetchall()
        players = [
            {
                "tag": r["player_tag"],
                "name": "Player",
                "trophies": 0,
                "source": "battle_participant",
                "priority": 1,
            }
            for r in rows
        ]
        return self.save_players_batch(players)

    def get_incremental_status(self) -> dict[str, Any]:
        """Return real-time metrics on player count, polling status, and incremental progress."""
        with closing(self.connect()) as conn:
            total_players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            polled_players = conn.execute("SELECT COUNT(*) FROM players WHERE last_polled_at IS NOT NULL").fetchone()[0]
            unpolled_players = total_players - polled_players
            total_matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            total_participants = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
            last_poll = conn.execute("SELECT MAX(last_polled_at) FROM players").fetchone()[0]
        return {
            "total_players": total_players,
            "polled_players": polled_players,
            "unpolled_players": unpolled_players,
            "target_players": 100000,
            "percent_of_target": round((total_players / 100000) * 100, 2),
            "total_matches": total_matches,
            "total_participants": total_participants,
            "last_poll_time": last_poll,
        }

    def get_dataset_summary(self) -> dict[str, Any]:
        """Return dataset breakdown, class/mode distribution, and audit verification."""
        with closing(self.connect()) as conn:
            total_matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            total_participants = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
            mode_counts = conn.execute(
                "SELECT mode, COUNT(*) as cnt FROM matches GROUP BY mode ORDER BY cnt DESC"
            ).fetchall()
            type_counts = conn.execute(
                "SELECT match_type, COUNT(*) as cnt FROM matches GROUP BY match_type ORDER BY cnt DESC"
            ).fetchall()
            time_range = conn.execute(
                "SELECT MIN(battle_time) as earliest, MAX(battle_time) as latest FROM matches"
            ).fetchone()
            power_diff_stats = conn.execute(
                """
                SELECT
                    AVG(team_a_avg_power - team_b_avg_power) as avg_diff,
                    MIN(team_a_avg_power - team_b_avg_power) as min_diff,
                    MAX(team_a_avg_power - team_b_avg_power) as max_diff
                FROM matches
                WHERE team_a_avg_power > 0 AND team_b_avg_power > 0
                """
            ).fetchone()
            trainable_matches = conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT m.match_fingerprint FROM matches m
                    JOIN match_participants p ON p.match_fingerprint=m.match_fingerprint
                    WHERE m.ingestion_version=2 AND m.result IN ('victory','defeat')
                      AND m.team_a_avg_power>0 AND m.team_b_avg_power>0 AND p.brawler_id>0
                    GROUP BY m.match_fingerprint HAVING COUNT(*)=6
                      AND SUM(p.team_index=0)=3 AND SUM(p.team_index=1)=3
                      AND COUNT(p.is_winner)=6 AND SUM(p.is_winner)=3
                      AND COUNT(DISTINCT CASE WHEN p.team_index=0 THEN p.is_winner END)=1
                      AND COUNT(DISTINCT CASE WHEN p.team_index=1 THEN p.is_winner END)=1
                )
            """).fetchone()[0]
            verified_matches = conn.execute("SELECT COUNT(*) FROM matches WHERE ingestion_version=2").fetchone()[0]
            sample_matches = conn.execute(
                """
                SELECT match_fingerprint, battle_time, mode, map, match_type,
                       team_a_avg_power, team_b_avg_power, power_advantage, result
                FROM matches
                ORDER BY battle_time DESC
                LIMIT 8
                """
            ).fetchall()

        return {
            "total_matches": total_matches,
            "verified_matches": verified_matches,
            "trainable_3v3_matches": trainable_matches,
            "legacy_matches": total_matches - verified_matches,
            "total_participants": total_participants,
            "time_range": {
                "earliest": time_range["earliest"] if time_range else None,
                "latest": time_range["latest"] if time_range else None,
            },
            "modes_distribution": [{"mode": r["mode"], "matches": r["cnt"]} for r in mode_counts],
            "types_distribution": [{"match_type": r["match_type"], "matches": r["cnt"]} for r in type_counts],
            "power_differential": {
                "avg": round(power_diff_stats["avg_diff"] or 0.0, 3) if power_diff_stats else 0.0,
                "min": round(power_diff_stats["min_diff"] or 0.0, 1) if power_diff_stats else 0.0,
                "max": round(power_diff_stats["max_diff"] or 0.0, 1) if power_diff_stats else 0.0,
            },
            "audit_verification": {
                "pre_match_features_only": True,
                "legacy_labels_excluded": True,
                "excluded_features": ["star_player", "match_duration", "trophy_change", "battle_result"],
                "symmetrical_pairing": True,
                "deduplication_method": "SHA-256 fingerprint on UTC timestamp, map, mode, and participant tags",
            },
            "recent_samples": [dict(r) for r in sample_matches],
        }

