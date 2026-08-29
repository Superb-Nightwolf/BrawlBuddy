import json
import logging
from pathlib import Path
from typing import Any, Optional

from app.clients.brawl_stars import BrawlStarsClient
from app.models.rankings import RankingBrawlerItem, RankingClubItem, RankingPlayerItem

logger = logging.getLogger("brawlbuddy.rankings_service")


class RankingsService:
    def __init__(self, client: BrawlStarsClient, demo_path: Optional[Path] = None) -> None:
        self.client = client
        self.demo_path = demo_path or Path(__file__).resolve().parent.parent.parent / "data" / "demo_rankings.json"
        self._player_cache: dict[str, list[RankingPlayerItem]] = {}
        self._club_cache: dict[str, list[RankingClubItem]] = {}

    def load_demo_players(self) -> list[RankingPlayerItem]:
        if not self.demo_path.exists():
            return []
        with self.demo_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [RankingPlayerItem(**item) for item in data.get("players", [])]

    def load_demo_clubs(self) -> list[RankingClubItem]:
        if not self.demo_path.exists():
            return []
        with self.demo_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [RankingClubItem(**item) for item in data.get("clubs", [])]

    async def get_player_rankings(self, country_code: str = "global") -> tuple[list[RankingPlayerItem], str]:
        cc = country_code.lower()
        if cc in self._player_cache:
            return self._player_cache[cc], "CACHE"

        if not self.client.api_key:
            demo_items = self.load_demo_players()
            return demo_items, "DEMO"

        try:
            raw_data = await self.client.get_rankings_players(cc)
            items = []
            for item in raw_data.get("items", []):
                items.append(
                    RankingPlayerItem(
                        rank=item.get("rank", 1),
                        tag=item.get("tag", ""),
                        name=item.get("name", "Brawler"),
                        name_color=item.get("nameColor"),
                        icon_id=item.get("icon", {}).get("id", 28000000),
                        trophies=item.get("trophies", 0),
                        club_name=item.get("club", {}).get("name") if item.get("club") else None
                    )
                )
            self._player_cache[cc] = items
            return items, "LIVE"
        except Exception as e:
            logger.warning(f"Failed to fetch live player rankings for {cc}: {e}. Falling back to demo.")
            return self.load_demo_players(), "DEMO"

    async def get_club_rankings(self, country_code: str = "global") -> tuple[list[RankingClubItem], str]:
        cc = country_code.lower()
        if cc in self._club_cache:
            return self._club_cache[cc], "CACHE"

        if not self.client.api_key:
            demo_items = self.load_demo_clubs()
            return demo_items, "DEMO"

        try:
            raw_data = await self.client.get_rankings_clubs(cc)
            items = []
            for item in raw_data.get("items", []):
                items.append(
                    RankingClubItem(
                        rank=item.get("rank", 1),
                        tag=item.get("tag", ""),
                        name=item.get("name", "Alliance"),
                        badge_id=item.get("badgeId", 8000000),
                        trophies=item.get("trophies", 0),
                        member_count=item.get("memberCount", 30)
                    )
                )
            self._club_cache[cc] = items
            return items, "LIVE"
        except Exception as e:
            logger.warning(f"Failed to fetch live club rankings for {cc}: {e}. Falling back to demo.")
            return self.load_demo_clubs(), "DEMO"
