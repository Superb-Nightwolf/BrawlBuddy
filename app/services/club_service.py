from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from app.clients.brawl_stars import BrawlStarsClient
from app.core.errors import InvalidPlayerTag, MissingApiToken
from app.models.club import ClubMember, ClubProfile
from app.models.player import DataSource

logger = logging.getLogger(__name__)
TAG_PATTERN = re.compile(r"^#[0289PYLQGRJCUV]{3,14}$", re.IGNORECASE)


def normalize_club_tag(raw_tag: str) -> str:
    tag = raw_tag.strip().upper().replace(" ", "")
    if not tag.startswith("#"):
        tag = f"#{tag}"
    if not TAG_PATTERN.fullmatch(tag):
        raise InvalidPlayerTag(
            "Enter a valid club tag using 3–14 Brawl Stars tag characters, for example #PQL20."
        )
    return tag


def parse_club(payload: dict[str, Any], source: DataSource = DataSource.OFFICIAL_API) -> ClubProfile:
    members = [
        ClubMember(
            tag=item["tag"],
            name=item["name"],
            name_color=item.get("nameColor"),
            role=item.get("role", "member"),
            trophies=item.get("trophies", 0),
            icon_id=(item.get("icon") or {}).get("id"),
        )
        for item in payload.get("members", [])
    ]
    # Sort members by trophies descending
    members.sort(key=lambda m: m.trophies, reverse=True)

    return ClubProfile(
        tag=payload["tag"],
        name=payload["name"],
        description=payload.get("description"),
        type=payload.get("type", "open"),
        badge_id=payload.get("badgeId"),
        required_trophies=payload.get("requiredTrophies", 0),
        trophies=payload.get("trophies", 0),
        members=members,
        source=source,
    )


class ClubService:
    def __init__(
        self,
        client: BrawlStarsClient | None,
        demo_file: Path,
        cache_seconds: int,
    ) -> None:
        self._client = client
        self._demo_file = demo_file
        self._cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, ClubProfile]] = {}

    async def get_club(self, raw_tag: str) -> tuple[ClubProfile, bool]:
        tag = normalize_club_tag(raw_tag)
        cached = self._cache.get(tag)
        if cached and time.monotonic() - cached[0] <= self._cache_seconds:
            logger.info("Club cache hit for %s", tag)
            return cached[1], True
        if self._client is None:
            raise MissingApiToken(
                "Live lookup needs BRAWL_STARS_API_TOKEN. You can still explore the labeled demo club."
            )
        logger.info("Loading club %s", tag)
        club = parse_club(await self._client.get_club(tag))
        self._cache[tag] = (time.monotonic(), club)
        return club, False

    def get_demo_club(self) -> ClubProfile:
        with self._demo_file.open("r", encoding="utf-8") as handle:
            return parse_club(json.load(handle), source=DataSource.DEMO)
