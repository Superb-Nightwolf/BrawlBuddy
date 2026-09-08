from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from app.clients.brawl_stars import BrawlStarsClient
from app.core.errors import InvalidPlayerTag, MissingApiToken
from app.core.prestige import resolve_prestige_state
from app.models.player import (
    BuffieFlags,
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


def _equipment(items: list[dict[str, Any]] | list[str] | dict[str, Any] | None) -> list[EquipmentItem]:
    if not items:
        return []
    if isinstance(items, dict):
        items = [items]
    result: list[EquipmentItem] = []
    for item in items:
        if isinstance(item, str):
            result.append(EquipmentItem(id=0, name=item))
        elif isinstance(item, dict):
            item_id = item.get("id", 0)
            item_name = item.get("name", "")
            item_level = item.get("level")
            result.append(EquipmentItem(id=item_id, name=item_name, level=item_level))
        elif isinstance(item, EquipmentItem):
            result.append(item)
    return result


def _buffie_flags(items: dict[str, Any] | list[Any] | None) -> BuffieFlags:
    """Normalize the official flag object and older local list fixtures."""
    gadget = False
    star_power = False
    hypercharge = False

    if isinstance(items, dict):
        gadget = bool(items.get("gadget", False))
        star_power = bool(items.get("starPower", items.get("star_power", False)))
        hypercharge = bool(items.get("hyperCharge", items.get("hypercharge", False)))
    elif isinstance(items, list):
        for item in items:
            raw = item if isinstance(item, str) else item.get("name", "") if isinstance(item, dict) else ""
            key = re.sub(r"[^a-z0-9]", "", raw.lower())
            gadget = gadget or "gadget" in key
            star_power = star_power or key in {"sp", "starpower"} or "starpower" in key
            hypercharge = hypercharge or key in {"hc", "hypercharge"} or "hypercharge" in key

    return BuffieFlags(gadget=gadget, star_power=star_power, hypercharge=hypercharge)


def _merge_equipment(base: list[EquipmentItem], extra: list[EquipmentItem]) -> list[EquipmentItem]:
    existing_ids = {e.id for e in base if e.id}
    existing_names = {e.name.upper() for e in base if e.name}
    merged = list(base)
    for item in extra:
        if (item.id and item.id in existing_ids) or (item.name and item.name.upper() in existing_names):
            continue
        merged.append(item)
    return merged


def parse_player(
    payload: dict[str, Any],
    source: DataSource = DataSource.OFFICIAL_API,
    overrides: dict[str, Any] | None = None,
) -> PlayerProfile:
    brawlers_override = (overrides or {}).get("brawlers", {})
    brawlers: list[PlayerBrawler] = []
    for item in payload.get("brawlers", []):
        brawler_id = item.get("id")
        brawler_name = str(item.get("name", "")).upper()
        b_override = (
            brawlers_override.get(str(brawler_id))
            or brawlers_override.get(brawler_id)
            or brawlers_override.get(brawler_name)
            or {}
        )

        # The official API field is camelCase. Legacy aliases remain supported
        # for demo data without overriding an explicitly empty official array.
        hc_raw = item.get("hyperCharges")
        if hc_raw is None:
            hc_raw = item.get("hypercharges")
        if hc_raw is None:
            hc_raw = item.get("hypercharge")
        if hc_raw is None:
            hc_raw = []
        if isinstance(hc_raw, bool) and hc_raw:
            hc_items = [EquipmentItem(id=0, name="Hypercharge")]
        else:
            hc_items = _equipment(hc_raw)

        if b_override.get("hypercharges"):
            hc_items = _merge_equipment(hc_items, _equipment(b_override["hypercharges"]))

        gadgets = _equipment(item.get("gadgets"))
        if b_override.get("gadgets"):
            gadgets = _merge_equipment(gadgets, _equipment(b_override["gadgets"]))

        star_powers = _equipment(item.get("starPowers") or item.get("star_powers"))
        if b_override.get("star_powers") or b_override.get("starPowers"):
            star_powers = _merge_equipment(
                star_powers,
                _equipment(b_override.get("star_powers") or b_override.get("starPowers")),
            )

        gears = _equipment(item.get("gears"))
        if b_override.get("gears"):
            gears = _merge_equipment(gears, _equipment(b_override["gears"]))

        buffies_raw = item.get("buffies")
        if b_override.get("buffies"):
            override_buffies = b_override.get("buffies")
            if isinstance(buffies_raw, dict) and isinstance(override_buffies, dict):
                buffies_raw = {**buffies_raw, **override_buffies}
            elif not buffies_raw:
                buffies_raw = override_buffies
        buffies = _buffie_flags(buffies_raw)
        official_prestige = item.get("prestigeLevel")
        prestige = resolve_prestige_state(
            item.get("trophies", 0),
            official_prestige,
            highest_trophies=item.get("highestTrophies", 0),
        )

        brawlers.append(
            PlayerBrawler(
                id=item["id"],
                name=item["name"],
                power=item["power"],
                rank=item.get("rank", 1),
                prestige_level=prestige.level,
                prestige_level_source=(
                    source if official_prestige is not None else DataSource.INFERRED
                ),
                prestige_trophies=prestige.trophies_in_level,
                prestige_floor_trophies=prestige.floor_trophies,
                next_prestige_level=prestige.next_level,
                next_prestige_trophy_milestone=prestige.next_total_trophies,
                trophies_to_next_prestige=prestige.trophies_remaining,
                prestige_progress_percent=prestige.progress_percent,
                prestige_label=prestige.label,
                prestige_asset_id=prestige.asset_id,
                prestige_visual_level=prestige.visual_level,
                prestige_visual_is_fallback=prestige.visual_is_fallback,
                next_prestige_reward=prestige.next_reward,
                trophies=item.get("trophies", 0),
                highest_trophies=item.get("highestTrophies", 0),
                gadgets=gadgets,
                star_powers=star_powers,
                gears=gears,
                hypercharges=hc_items,
                buffies=buffies,
                source=source,
            )
        )
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
        total_prestige_level=payload.get("totalPrestigeLevel"),
        total_prestige_source=(
            source if payload.get("totalPrestigeLevel") is not None else DataSource.INFERRED
        ),
        source=source,
    )


class PlayerService:
    def __init__(
        self,
        client: BrawlStarsClient | None,
        demo_file: Path,
        cache_seconds: int,
        overrides_file: Path | None = None,
    ) -> None:
        self._client = client
        self._demo_file = demo_file
        self._cache_seconds = cache_seconds
        self._overrides_file = overrides_file
        self._cache: dict[str, tuple[float, PlayerProfile]] = {}

    def _get_overrides_for_tag(self, tag: str) -> dict[str, Any] | None:
        if not self._overrides_file or not self._overrides_file.exists():
            return None
        try:
            with self._overrides_file.open("r", encoding="utf-8") as handle:
                all_overrides = json.load(handle) or {}
                norm_tag = tag.upper()
                return all_overrides.get(norm_tag) or all_overrides.get(norm_tag.replace("#", ""))
        except Exception as err:
            logger.warning("Failed to load player overrides from %s: %s", self._overrides_file, err)
            return None

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
        overrides = self._get_overrides_for_tag(tag)
        player = parse_player(await self._client.get_player(tag), overrides=overrides)
        self._cache[tag] = (time.monotonic(), player)
        return player, False

    def get_demo_player(self) -> PlayerProfile:
        with self._demo_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
            tag = payload.get("tag", "")
            overrides = self._get_overrides_for_tag(tag) if tag else None
            return parse_player(payload, source=DataSource.DEMO, overrides=overrides)
