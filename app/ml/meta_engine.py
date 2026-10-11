from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from typing import Any, Optional

from app.ml.database import MetaDatabase

logger = logging.getLogger("brawlbuddy.ml.meta_engine")


@dataclass
class BrawlerMetaStat:
    brawler_id: int
    brawler_name: str
    total_picks: int
    wins: int
    losses: int
    raw_win_rate: float
    smoothed_win_rate: float
    pick_rate: float
    star_player_count: int
    star_player_rate: float
    avg_power: float
    avg_trophies: float
    confidence: str
    tier: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "brawler_id": self.brawler_id,
            "brawler_name": self.brawler_name,
            "total_picks": self.total_picks,
            "wins": self.wins,
            "losses": self.losses,
            "raw_win_rate": round(self.raw_win_rate, 4),
            "smoothed_win_rate": round(self.smoothed_win_rate, 4),
            "pick_rate": round(self.pick_rate, 4),
            "star_player_count": self.star_player_count,
            "star_player_rate": round(self.star_player_rate, 4),
            "avg_power": round(self.avg_power, 1),
            "avg_trophies": round(self.avg_trophies, 0),
            "confidence": self.confidence,
            "tier": self.tier,
        }


class StatisticalMetaEngine:
    """Computes empirically smoothed win rates, pick rates, synergies, and counters."""

    def __init__(self, database: MetaDatabase, smoothing_weight: float = 20.0) -> None:
        self.db = database
        self.smoothing_weight = smoothing_weight

    def get_available_filters(self) -> dict[str, Any]:
        """Return available game modes, maps, and match types in the database."""
        with closing(self.db.connect()) as conn:
            modes = [row["mode"] for row in conn.execute("SELECT DISTINCT mode FROM matches ORDER BY mode").fetchall()]
            types = [row["match_type"] for row in conn.execute("SELECT DISTINCT match_type FROM matches ORDER BY match_type").fetchall()]
            map_rows = conn.execute("SELECT mode, map, COUNT(*) as match_count FROM matches GROUP BY mode, map ORDER BY match_count DESC").fetchall()
            
            maps_by_mode: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for r in map_rows:
                maps_by_mode[r["mode"]].append({"map": r["map"], "matches": r["match_count"]})

        return {
            "modes": modes,
            "match_types": types,
            "maps_by_mode": dict(maps_by_mode),
        }

    def compute_brawler_stats(
        self,
        mode: Optional[str] = None,
        map_name: Optional[str] = None,
        match_type: Optional[str] = None,
        min_picks: int = 1,
    ) -> list[dict[str, Any]]:
        """Calculate empirically smoothed win rates, pick rates, and meta tiers."""
        filters = []
        params = []
        if mode:
            filters.append("m.mode = ?")
            params.append(mode)
        if map_name:
            filters.append("m.map = ?")
            params.append(map_name)
        if match_type:
            filters.append("m.match_type = ?")
            params.append(match_type)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        with closing(self.db.connect()) as conn:
            # 1. Total matches for pick rate denominator
            total_matches_query = f"SELECT COUNT(*) as total FROM matches m {where_clause}"
            total_matches = conn.execute(total_matches_query, params).fetchone()["total"] or 0

            # 2. Aggregated participant stats per brawler
            query = f"""
                SELECT
                    p.brawler_id,
                    p.brawler_name,
                    COUNT(*) as total_picks,
                    SUM(CASE WHEN p.is_winner = 1 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN p.is_winner = 0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN p.is_star_player = 1 THEN 1 ELSE 0 END) as star_players,
                    AVG(p.brawler_power) as avg_power,
                    AVG(p.brawler_trophies) as avg_trophies
                FROM match_participants p
                JOIN matches m ON p.match_fingerprint = m.match_fingerprint
                {where_clause}
                GROUP BY p.brawler_id, p.brawler_name
                HAVING total_picks >= ?
            """
            rows = conn.execute(query, (*params, min_picks)).fetchall()

        if not rows:
            return []

        # Average win rate across entire pool as empirical Bayesian prior
        total_wins_all = sum(r["wins"] for r in rows)
        total_picks_all = sum(r["total_picks"] for r in rows)
        prior_mean = (total_wins_all / total_picks_all) if total_picks_all > 0 else 0.50

        # Team slots per match: ~6 for 3v3, ~10 for showdown
        slots_multiplier = 6.0 if (not mode or "showdown" not in mode.lower()) else 10.0
        total_slots = max(total_matches * slots_multiplier, 1.0)

        stats_list: list[BrawlerMetaStat] = []
        for r in rows:
            picks = r["total_picks"]
            wins = r["wins"]
            losses = r["losses"]
            raw_wr = (wins / picks) if picks > 0 else 0.50

            # Bayesian smoothing: (wins + C * prior) / (picks + C)
            smoothed_wr = (wins + self.smoothing_weight * prior_mean) / (picks + self.smoothing_weight)
            pick_rate = picks / total_slots
            sp_rate = (r["star_players"] / picks) if picks > 0 else 0.0

            # Confidence based on sample count
            if picks >= 50:
                confidence = "HIGH"
            elif picks >= 15:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            stats_list.append(
                BrawlerMetaStat(
                    brawler_id=r["brawler_id"],
                    brawler_name=r["brawler_name"],
                    total_picks=picks,
                    wins=wins,
                    losses=losses,
                    raw_win_rate=raw_wr,
                    smoothed_win_rate=smoothed_wr,
                    pick_rate=pick_rate,
                    star_player_count=r["star_players"],
                    star_player_rate=sp_rate,
                    avg_power=r["avg_power"] or 1.0,
                    avg_trophies=r["avg_trophies"] or 0.0,
                    confidence=confidence,
                    tier="B",  # Assigned in next pass
                )
            )

        # Assign tiers (S, A, B, C, D) based on smoothed win rate distribution
        stats_list.sort(key=lambda s: s.smoothed_win_rate, reverse=True)
        count = len(stats_list)
        for idx, s in enumerate(stats_list):
            percentile = (idx + 1) / count
            if percentile <= 0.15:
                s.tier = "S"
            elif percentile <= 0.40:
                s.tier = "A"
            elif percentile <= 0.70:
                s.tier = "B"
            elif percentile <= 0.90:
                s.tier = "C"
            else:
                s.tier = "D"

        return [s.to_dict() for s in stats_list]

    def compute_pair_synergy(
        self,
        brawler_a: int,
        brawler_b: int,
        mode: Optional[str] = None,
        map_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Calculate pairwise synergy when Brawler A and B play on the same team."""
        filters = []
        params = [brawler_a, brawler_b]
        if mode:
            filters.append("m.mode = ?")
            params.append(mode)
        if map_name:
            filters.append("m.map = ?")
            params.append(map_name)

        where_extra = f"AND {' AND '.join(filters)}" if filters else ""

        query = f"""
            SELECT
                COUNT(*) as paired_matches,
                SUM(CASE WHEN p1.is_winner = 1 THEN 1 ELSE 0 END) as paired_wins
            FROM match_participants p1
            JOIN match_participants p2
                ON p1.match_fingerprint = p2.match_fingerprint
                AND p1.team_index = p2.team_index
                AND p1.player_tag != p2.player_tag
            JOIN matches m ON p1.match_fingerprint = m.match_fingerprint
            WHERE p1.brawler_id = ? AND p2.brawler_id = ?
            {where_extra}
        """

        with closing(self.db.connect()) as conn:
            row = conn.execute(query, params).fetchone()
            paired_matches = (row["paired_matches"] or 0) if row else 0
            paired_wins = (row["paired_wins"] or 0) if row else 0

        win_rate = (paired_wins / paired_matches) if paired_matches > 0 else 0.50
        smoothed = (paired_wins + 10 * 0.5) / (paired_matches + 10)
        
        return {
            "brawler_a": brawler_a,
            "brawler_b": brawler_b,
            "paired_matches": paired_matches,
            "paired_wins": paired_wins,
            "raw_win_rate": round(win_rate, 4),
            "smoothed_win_rate": round(smoothed, 4),
            "confidence": "HIGH" if paired_matches >= 30 else ("MEDIUM" if paired_matches >= 10 else "LOW"),
        }

    def compute_head_to_head_counter(
        self,
        brawler: int,
        opponent: int,
        mode: Optional[str] = None,
    ) -> dict[str, Any]:
        """Calculate head-to-head performance of brawler facing opponent on opposing team."""
        filters = []
        params = [brawler, opponent]
        if mode:
            filters.append("m.mode = ?")
            params.append(mode)

        where_extra = f"AND {' AND '.join(filters)}" if filters else ""

        query = f"""
            SELECT
                COUNT(*) as matches_faced,
                SUM(CASE WHEN p1.is_winner = 1 THEN 1 ELSE 0 END) as wins_against
            FROM match_participants p1
            JOIN match_participants p2
                ON p1.match_fingerprint = p2.match_fingerprint
                AND p1.team_index != p2.team_index
            JOIN matches m ON p1.match_fingerprint = m.match_fingerprint
            WHERE p1.brawler_id = ? AND p2.brawler_id = ?
            {where_extra}
        """

        with closing(self.db.connect()) as conn:
            row = conn.execute(query, params).fetchone()
            faced = (row["matches_faced"] or 0) if row else 0
            wins = (row["wins_against"] or 0) if row else 0

        win_rate = (wins / faced) if faced > 0 else 0.50
        smoothed = (wins + 10 * 0.5) / (faced + 10)

        return {
            "brawler": brawler,
            "opponent": opponent,
            "matches_faced": faced,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "smoothed_win_rate": round(smoothed, 4),
            "is_favored": smoothed > 0.52,
            "confidence": "HIGH" if faced >= 25 else ("MEDIUM" if faced >= 8 else "LOW"),
        }
