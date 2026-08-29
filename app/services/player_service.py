from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from app.clients.brawl_stars import BrawlStarsClient
from app.core.errors import InvalidPlayerTag, MissingApiToken
from app.models.player import (
    ClubSummary,
    DataSource,
    EquipmentItem,
    PlayerBrawler,
    PlayerProfile,
)

logger = logging.getLogger(__name__)
TAG_PATTERN = re.compile(r"^#[0289PYLQGRJCUV]{3,14}$", re.IGNORECASE)


def normalize_player_tag(raw_tag: str) -> str:
    tag = raw_tag.strip().upper().replace(" ", "")
    if not tag.startswith("#"):
        tag = f"#{tag}"
    if not TAG_PATTERN.fullmatch(tag):
        raise InvalidPlayerTag(
            "Enter a valid player tag using 3–14 Brawl Stars tag characters, for example #2PP."
        )
    return tag


def _equipment(items: list[dict[str, Any]] | None) -> list[EquipmentItem]:
    return [EquipmentItem.model_validate(item) for item in (items or [])]


def parse_player(payload: dict[str, Any], source: DataSource = DataSource.OFFICIAL_API) -> PlayerProfile:
    brawlers = [
        PlayerBrawler(
            id=item["id"],
            name=item["name"],
            power=item["power"],
            rank=item.get("rank", 1),
            trophies=item.get("trophies", 0),
            highest_trophies=item.get("highestTrophies", 0),
            gadgets=_equipment(item.get("gadgets")),
            star_powers=_equipment(item.get("starPowers")),
            gears=_equipment(item.get("gears")),
            source=source,
        )
        for item in payload.get("brawlers", [])
    ]
    club_data = payload.get("club") or None
    return PlayerProfile(
        tag=payload["tag"],
        name=payload["name"],
        name_color=payload.get("nameColor"),
        icon_id=(payload.get("icon") or {}).get("id"),
        trophies=payload.get("trophies", 0),
        highest_trophies=payload.get("highestTrophies", 0),
        exp_level=payload.get("expLevel"),
        exp_points=payload.get("expPoints"),
        victories_3v3=payload.get("3vs3Victories", 0),
        solo_victories=payload.get("soloVictories", 0),
        duo_victories=payload.get("duoVictories", 0),
        is_qualified_from_championship_challenge=bool(payload.get("isQualifiedFromChampionshipChallenge", False)),
        best_robo_rumble_time=payload.get("bestRoboRumbleTime"),
        best_time_as_big_brawler=payload.get("bestTimeAsBigBrawler"),
        highest_power_play_points=payload.get("highestPowerPlayPoints"),
        club=ClubSummary.model_validate(club_data) if club_data else None,
        brawlers=brawlers,
        source=source,
    )


class PlayerService:
    def __init__(
        self,
        client: BrawlStarsClient | None,
        demo_file: Path,
        cache_seconds: int,
    ) -> None:
        self._client = client
        self._demo_file = demo_file
        self._cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, PlayerProfile]] = {}

    async def get_player(self, raw_tag: str) -> tuple[PlayerProfile, bool]:
        tag = normalize_player_tag(raw_tag)
        cached = self._cache.get(tag)
        if cached and time.monotonic() - cached[0] <= self._cache_seconds:
            logger.info("Player cache hit for %s", tag)
            return cached[1], True
        if self._client is None:
            raise MissingApiToken(
                "Live lookup needs BRAWL_STARS_API_TOKEN. You can still explore the labeled demo account."
            )
        logger.info("Loading player %s", tag)
        player = parse_player(await self._client.get_player(tag))
        self._cache[tag] = (time.monotonic(), player)
        return player, False

    def get_demo_player(self) -> PlayerProfile:
        with self._demo_file.open("r", encoding="utf-8") as handle:
            return parse_player(json.load(handle), source=DataSource.DEMO)

