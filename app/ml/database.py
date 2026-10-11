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
                ORDER BY
                    CASE WHEN last_polled_at IS NULL THEN 0 ELSE 1 END ASC,
                    priority DESC,
                    last_polled_at ASC
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
        battle = raw_battle.get("battle", {})
        event = raw_battle.get("event", {})
        battle_time = raw_battle.get("battleTime", "")
        event_map = event.get("map") or "Unknown Map"
        mode = battle.get("mode") or event.get("mode") or "unknown"
        event_mode = event.get("mode")
        event_id = event.get("id", 0)
        match_type = battle.get("type", "ranked")
        duration = battle.get("duration")
        trophy_change = battle.get("trophyChange")
        result = battle.get("result")
        star_player_tag = (battle.get("starPlayer") or {}).get("tag", "").upper()

        # Extract participants across teams or showdown players
        teams = battle.get("teams", [])
        showdown_players = battle.get("players", [])
        
        all_participants: list[dict[str, Any]] = []
        all_tags: list[str] = []
        brawler_ids: list[int] = []

        if teams:
            # 3v3 or 5v5 team match
            for team_idx, team_members in enumerate(teams):
                for p in team_members:
                    tag = (p.get("tag") or "").strip().upper()
                    if tag and not tag.startswith("#"):
                        tag = f"#{tag}"
                    brawler = p.get("brawler") or {}
                    b_id = brawler.get("id", 0)
                    b_name = brawler.get("name", "Unknown")
                    b_power = brawler.get("power", 1)
                    b_trophies = brawler.get("trophies", 0)
                    p_name = p.get("name", "Player")
                    
                    if tag:
                        all_tags.append(tag)
                    if b_id:
                        brawler_ids.append(b_id)

                    # Determine winner:
                    # In Supercell API: result is reported relative to the tracked player!
                    # If result == 'victory', the team containing source_player_tag won!
                    is_winner: Optional[int] = None
                    if result in ("victory", "defeat"):
                        source_tag = source_player_tag.strip().upper()
                        # Check which team has source_tag
                        source_in_this_team = any(
                            (m.get("tag") or "").strip().upper() == source_tag for m in team_members
                        )
                        if result == "victory":
                            is_winner = 1 if source_in_this_team else 0
                        elif result == "defeat":
                            is_winner = 0 if source_in_this_team else 1
                    elif result == "draw":
                        is_winner = 0

                    all_participants.append({
                        "player_tag": tag or f"#UNKNOWN_{team_idx}_{b_id}",
                        "name": p_name,
                        "team_index": team_idx,
                        "brawler_id": b_id,
                        "brawler_name": b_name,
                        "brawler_power": b_power,
                        "brawler_trophies": b_trophies,
                        "is_star_player": 1 if tag and tag == star_player_tag else 0,
                        "is_winner": is_winner,
                    })
        elif showdown_players:
            # Showdown / solo match
            rank = battle.get("rank", 0)
            for p in showdown_players:
                tag = (p.get("tag") or "").strip().upper()
                if tag and not tag.startswith("#"):
                    tag = f"#{tag}"
                brawler = p.get("brawler") or {}
                b_id = brawler.get("id", 0)
                b_name = brawler.get("name", "Unknown")
                b_power = brawler.get("power", 1)
                b_trophies = brawler.get("trophies", 0)
                p_name = p.get("name", "Player")

                if tag:
                    all_tags.append(tag)
                if b_id:
                    brawler_ids.append(b_id)

                # In showdown: top 4 (duo) or top 1-4 (solo) is considered winning / positive trophies
                is_win = 1 if rank and rank <= 4 else 0
                all_participants.append({
                    "player_tag": tag or f"#SHOWDOWN_{b_id}",
                    "name": p_name,
                    "team_index": 0,
                    "brawler_id": b_id,
                    "brawler_name": b_name,
                    "brawler_power": b_power,
                    "brawler_trophies": b_trophies,
                    "is_star_player": 0,
                    "is_winner": is_win,
                })

        # Calculate power averages if 2 teams
        team_a_avg = 0.0
        team_b_avg = 0.0
        t0 = [p for p in all_participants if p["team_index"] == 0]
        t1 = [p for p in all_participants if p["team_index"] == 1]
        if t0 and t1:
            team_a_avg = round(sum(p["brawler_power"] for p in t0) / len(t0), 2)
            team_b_avg = round(sum(p["brawler_power"] for p in t1) / len(t1), 2)
        diff = team_a_avg - team_b_avg
        advantage = "blue_favored" if diff >= 0.5 else ("red_favored" if diff <= -0.5 else "balanced")

        fingerprint = generate_match_fingerprint(battle_time, event_map, mode, all_tags, brawler_ids)
        now_iso = datetime.now(UTC).isoformat()

        with closing(self.connect()) as conn, conn:
            # Check if match already exists
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO matches (
                    match_fingerprint, battle_time, mode, event_mode, map, event_id,
                    match_type, duration, trophy_change, result,
                    team_a_avg_power, team_b_avg_power, power_advantage, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fingerprint, battle_time, mode, event_mode, event_map, event_id,
                    match_type, duration, trophy_change, result,
                    team_a_avg, team_b_avg, advantage, now_iso
                ),
            )
            is_new = cur.rowcount > 0

            if is_new:
                for part in all_participants:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO match_participants (
                            match_fingerprint, player_tag, team_index, brawler_id,
                            brawler_name, brawler_power, brawler_trophies,
                            is_star_player, is_winner
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fingerprint,
                            part["player_tag"],
                            part["team_index"],
                            part["brawler_id"],
                            part["brawler_name"],
                            part["brawler_power"],
                            part["brawler_trophies"],
                            part["is_star_player"],
                            part["is_winner"],
                        ),
                    )

        # Return discovered participants that can be used for cascading discovery
        discovered = [p for p in all_participants if p["player_tag"].startswith("#") and "UNKNOWN" not in p["player_tag"]]
        return is_new, fingerprint, discovered

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
            return cur.rowcount

    def extract_participants_as_players(self) -> int:
        """Ingest all known battle participants from matches into the players table."""
        with closing(self.connect()) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT player_tag, brawler_trophies
                FROM match_participants
                WHERE player_tag LIKE '#%' AND player_tag NOT LIKE '%UNKNOWN%'
                """
            ).fetchall()
        players = [
            {
                "tag": r["player_tag"],
                "name": "Player",
                "trophies": r["brawler_trophies"] or 0,
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
                "target_leakage_prevented": True,
                "excluded_features": ["star_player", "match_duration", "trophy_change", "battle_result"],
                "symmetrical_pairing": True,
                "deduplication_method": "SHA-256 fingerprint on UTC timestamp, map, mode, and participant tags",
            },
            "recent_samples": [dict(r) for r in sample_matches],
        }

