from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Optional

from app.clients.brawl_stars import BrawlStarsClient
from app.core.errors import ApiRateLimited, PlayerNotFound, UpstreamUnavailable
from app.ml.database import MetaDatabase

logger = logging.getLogger("brawlbuddy.ml.collector")

COMPETITIVE_REGIONS = [
    "global",
    "us",
    "kr",
    "jp",
    "br",
    "de",
    "fr",
    "es",
    "gb",
    "it",
    "ca",
    "mx",
    "pl",
    "tr",
    "fi",
    "se",
    "nl",
    "au",
    "sg",
    "hk",
    "tw",
    "in",
    "id",
    "th",
    "ph",
    "vn",
    "my",
    "sa",
    "ae",
    "ar",
    "cl",
    "co",
    "za",
    "no",
    "dk",
    "ch",
    "pt",
    "cz",
    "hu",
    "ro",
    "gr",
    "at",
    "be",
    "nz",
    "ie",
    "il",
    "pe",
]



@dataclass
class CollectionStats:
    players_discovered: int = 0
    players_polled: int = 0
    battles_fetched: int = 0
    new_matches_saved: int = 0
    duplicate_matches_skipped: int = 0
    failed_polls: int = 0
    start_time: float = field(default_factory=time.monotonic)

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.start_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "players_discovered": self.players_discovered,
            "players_polled": self.players_polled,
            "battles_fetched": self.battles_fetched,
            "new_matches_saved": self.new_matches_saved,
            "duplicate_matches_skipped": self.duplicate_matches_skipped,
            "failed_polls": self.failed_polls,
            "elapsed_seconds": round(self.elapsed_seconds(), 2),
        }


class BattleLogCollector:
    """Manages polite, robust, and checkpointed data collection from Brawl Stars API."""

    def __init__(
        self,
        client: BrawlStarsClient,
        database: MetaDatabase,
        requests_per_second: float = 5.0,
    ) -> None:
        self.client = client
        self.db = database
        self.min_interval = 1.0 / max(requests_per_second, 0.5)
        self._last_request_time = 0.0

    async def _throttle(self) -> None:
        """Enforce rate limiting between successive requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self._last_request_time = time.monotonic()

    async def discover_top_players(
        self,
        target_player_count: int = 100000,
        regions: Optional[list[str]] = None,
        include_brawlers: bool = True,
        include_clubs: bool = True,
        on_progress: Optional[Callable[[str, int], None]] = None,
    ) -> int:
        """Populate the players table with competitive player tags up to target_player_count."""
        regions = regions or COMPETITIVE_REGIONS
        current_count = self.db.get_player_count()
        logger.info("Starting player discovery. Current player count: %d, target: %d", current_count, target_player_count)

        # 0. First, harvest all participant tags already sitting in matches DB
        extracted = self.db.extract_participants_as_players()
        current_count = self.db.get_player_count()
        if on_progress:
            on_progress(f"Extracted participants: +{extracted}", current_count)

        # 1. Discover from Regional Leaderboards
        for cc in regions:
            if current_count >= target_player_count:
                break
            try:
                await self._throttle()
                logger.info("Fetching leaderboard for region: %s", cc)
                data = await self.client.get_rankings_players(cc)
                batch_players = []
                for item in data.get("items", []):
                    tag = item.get("tag")
                    if tag:
                        batch_players.append({
                            "tag": tag,
                            "name": item.get("name", "Player"),
                            "trophies": item.get("trophies", 0),
                            "highest_trophies": item.get("trophies", 0),
                            "club_name": item.get("club", {}).get("name") if item.get("club") else None,
                            "source": f"leaderboard_{cc}",
                            "priority": 3 if cc == "global" else 2,
                        })
                if batch_players:
                    self.db.save_players_batch(batch_players)
                    current_count = self.db.get_player_count()
                if on_progress:
                    on_progress(f"Leaderboard {cc}", current_count)
            except Exception as e:
                logger.warning("Error fetching leaderboard for %s: %s", cc, e)

        # 2. Discover from Top Club Rosters (scales massively up to 100k+)
        if include_clubs and current_count < target_player_count:
            club_limit = 100 if target_player_count >= 50000 else (30 if target_player_count > 20000 else 10)
            for cc in regions:
                if current_count >= target_player_count:
                    break
                try:
                    await self._throttle()
                    club_ranks = await self.client.get_rankings_clubs(cc)
                    club_items = club_ranks.get("items", [])[:club_limit]
                    for club in club_items:
                        if current_count >= target_player_count:
                            break
                        c_tag = club.get("tag")
                        if not c_tag:
                            continue
                        try:
                            await self._throttle()
                            club_detail = await self.client.get_club(c_tag)
                            members = club_detail.get("members", [])
                            batch_members = []
                            for m in members:
                                m_tag = m.get("tag")
                                if m_tag:
                                    batch_members.append({
                                        "tag": m_tag,
                                        "name": m.get("name", "Player"),
                                        "trophies": m.get("trophies", 0),
                                        "highest_trophies": m.get("trophies", 0),
                                        "club_name": club.get("name"),
                                        "source": f"club_{c_tag}",
                                        "priority": 2,
                                    })
                            if batch_members:
                                self.db.save_players_batch(batch_members)
                                current_count = self.db.get_player_count()
                        except Exception as c_exc:
                            logger.debug("Failed club %s: %s", c_tag, c_exc)
                    if on_progress:
                        on_progress(f"Clubs {cc}", current_count)
                except Exception as exc:
                    logger.warning("Failed club ranking %s: %s", cc, exc)

        # 3. Discover from Brawler-specific leaderboards if more players needed
        if include_brawlers and current_count < target_player_count:
            try:
                await self._throttle()
                brawlers_resp = await self.client.get_brawlers()
                brawlers_list = brawlers_resp.get("items", [])
                logger.info("Found %d brawlers for leaderboard discovery", len(brawlers_list))
                
                for brawler in brawlers_list:
                    if current_count >= target_player_count:
                        break
                    b_id = brawler.get("id")
                    b_name = brawler.get("name", "Brawler")
                    if not b_id:
                        continue
                    try:
                        await self._throttle()
                        b_rankings = await self.client.get_rankings_brawler(b_id)
                        batch_brawlers = []
                        for item in b_rankings.get("items", []):
                            tag = item.get("tag")
                            if tag:
                                batch_brawlers.append({
                                    "tag": tag,
                                    "name": item.get("name", "Player"),
                                    "trophies": item.get("trophies", 0),
                                    "highest_trophies": item.get("trophies", 0),
                                    "club_name": item.get("club", {}).get("name") if item.get("club") else None,
                                    "source": f"brawler_leaderboard_{b_id}",
                                    "priority": 2,
                                })
                        if batch_brawlers:
                            self.db.save_players_batch(batch_brawlers)
                            current_count = self.db.get_player_count()
                        if on_progress:
                            on_progress(f"Brawler {b_name}", current_count)
                    except Exception as exc:
                        logger.warning("Failed brawler leaderboard %d: %s", b_id, exc)
            except Exception as exc:
                logger.warning("Failed to list brawlers for leaderboard: %s", exc)

        # 4. Step 4: Cascade battle log discovery from unpolled players until 100k target reached
        if current_count < target_player_count:
            logger.info("Scaling discovery via cascading battle logs (current: %d, target: %d)...", current_count, target_player_count)
            unpolled = self.db.get_unpolled_players(limit=5000)
            cascade_batch = []
            for idx, p in enumerate(unpolled):
                if current_count >= target_player_count:
                    break
                p_tag = p["tag"]
                try:
                    await self._throttle()
                    raw_log = await self.client.get_battlelog(p_tag)
                    items = raw_log.get("items", [])
                    for item in items:
                        is_new, _, participants = self.db.save_match(item, source_player_tag=p_tag)
                        for part in participants:
                            t = part.get("player_tag")
                            if t and t != p_tag:
                                cascade_batch.append({
                                    "tag": t,
                                    "name": part.get("name", "Player"),
                                    "trophies": part.get("brawler_trophies", 0),
                                    "highest_trophies": part.get("brawler_trophies", 0),
                                    "source": "battle_participant",
                                    "priority": 1,
                                })
                    self.db.mark_player_polled(p_tag, len(items))
                    if len(cascade_batch) >= 100:
                        self.db.save_players_batch(cascade_batch)
                        cascade_batch.clear()
                        current_count = self.db.get_player_count()
                    if on_progress and (idx + 1) % 15 == 0:
                        current_count = self.db.get_player_count()
                        on_progress(f"Battle Log Cascade #{idx+1}", current_count)
                except Exception as exc:
                    logger.debug("Cascade battle log skipped for %s: %s", p_tag, exc)
            if cascade_batch:
                self.db.save_players_batch(cascade_batch)
                cascade_batch.clear()
                current_count = self.db.get_player_count()

        self.db.extract_participants_as_players()
        final_count = self.db.get_player_count()
        logger.info("Player discovery complete. Total players in DB: %d", final_count)
        return final_count

    async def collect_battlelogs(
        self,
        max_players: int = 200,
        cascade_discovery: bool = True,
        on_progress: Optional[Callable[[CollectionStats], None]] = None,
    ) -> CollectionStats:
        """Fetch battle logs for unpolled or prioritized players with robust deduplication."""
        stats = CollectionStats()
        players_to_poll = self.db.get_unpolled_players(limit=max_players)
        logger.info("Collecting battle logs for %d players", len(players_to_poll))

        batch_cascade: list[dict[str, Any]] = []

        for idx, player in enumerate(players_to_poll):
            tag = player["tag"]
            try:
                await self._throttle()
                raw_log = await self.client.get_battlelog(tag)
                items = raw_log.get("items", [])
                stats.battles_fetched += len(items)

                for item in items:
                    is_new, fingerprint, participants = self.db.save_match(item, source_player_tag=tag)
                    if is_new:
                        stats.new_matches_saved += 1
                    else:
                        stats.duplicate_matches_skipped += 1

                    # Cascading player discovery from match participants
                    if cascade_discovery:
                        for part in participants:
                            p_tag = part.get("player_tag")
                            if p_tag and p_tag != tag:
                                batch_cascade.append({
                                    "tag": p_tag,
                                    "name": part.get("name", "Player"),
                                    "trophies": part.get("brawler_trophies", 0),
                                    "highest_trophies": part.get("brawler_trophies", 0),
                                    "source": "battle_participant",
                                    "priority": 1,
                                })

                self.db.mark_player_polled(tag, len(items))
                stats.players_polled += 1

                # Flush cascade batch periodically
                if len(batch_cascade) >= 100:
                    self.db.save_players_batch(batch_cascade)
                    batch_cascade.clear()

            except PlayerNotFound:
                logger.debug("Player %s not found on API, marking polled with 0 battles", tag)
                self.db.mark_player_polled(tag, 0)
                stats.failed_polls += 1
            except ApiRateLimited:
                logger.warning("API rate limited while polling %s. Waiting 2.0s...", tag)
                stats.failed_polls += 1
                await asyncio.sleep(2.0)
            except UpstreamUnavailable as exc:
                logger.warning("Upstream unavailable for %s: %s", tag, exc)
                stats.failed_polls += 1
                await asyncio.sleep(1.0)
            except Exception as exc:
                logger.error("Unexpected error collecting for %s: %s", tag, exc)
                stats.failed_polls += 1

            if on_progress and (idx + 1) % 10 == 0:
                stats.players_discovered = self.db.get_player_count()
                on_progress(stats)

        if batch_cascade:
            self.db.save_players_batch(batch_cascade)
            batch_cascade.clear()

        stats.players_discovered = self.db.get_player_count()
        if on_progress:
            on_progress(stats)

        logger.info(
            "Collection run finished: Polled %d players, %d new matches saved, %d duplicates deduplicated, total players: %d",
            stats.players_polled,
            stats.new_matches_saved,
            stats.duplicate_matches_skipped,
            stats.players_discovered,
        )
        return stats

