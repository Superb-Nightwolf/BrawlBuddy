import json
from pathlib import Path

import pytest

from app.core.prestige import resolve_prestige_state
from app.models.player import DataSource
from app.services.player_service import parse_player


@pytest.mark.parametrize(
    ("trophies", "level", "label", "asset_id", "remaining"),
    [
        (0, 0, "Wood", 0, 250),
        (249, 0, "Wood", 0, 1),
        (250, 0, "Bronze", 1, 250),
        (500, 0, "Silver", 2, 250),
        (750, 0, "Gold", 3, 250),
        (1_000, 1, "Prestige 1", 4, 1_000),
        (2_000, 2, "Prestige 2", 5, 1_000),
        (3_000, 3, "Prestige 3", 6, 1_000),
        (10_000, 10, "Prestige 10", 13, 1_000),
    ],
)
def test_official_prestige_boundaries(
    trophies: int, level: int, label: str, asset_id: int, remaining: int
) -> None:
    state = resolve_prestige_state(trophies, level)
    assert state.level == level
    assert state.label == label
    assert state.asset_id == asset_id
    assert state.trophies_remaining == remaining
    assert state.level_is_authoritative is True


def test_1000_trophy_boundary_respects_authoritative_api_level() -> None:
    ready = resolve_prestige_state(1_000, 0)
    prestiged = resolve_prestige_state(1_000, 1)
    assert ready.label == "Gold"
    assert ready.trophies_remaining == 0
    assert prestiged.label == "Prestige 1"
    assert prestiged.trophies_in_level == 0


def test_higher_prestige_keeps_real_level_with_p10_visual_fallback() -> None:
    state = resolve_prestige_state(12_345, 12)
    assert state.level == 12
    assert state.label == "Prestige 12"
    assert state.trophies_in_level == 345
    assert state.next_level == 13
    assert state.asset_id == 13
    assert state.visual_level == 10
    assert state.visual_is_fallback is True


def test_legacy_payload_derives_prestige_only_when_api_field_is_missing() -> None:
    state = resolve_prestige_state(900, None, highest_trophies=2_050)
    assert state.level == 2
    assert state.level_is_authoritative is False


def test_player_api_prestige_fields_are_authoritative() -> None:
    player = parse_player(
        {
            "tag": "#2PP",
            "name": "Prestige Player",
            "trophies": 4_050,
            "totalPrestigeLevel": 4,
            "brawlers": [
                {
                    "id": 16000000,
                    "name": "SHELLY",
                    "power": 11,
                    "rank": 5,
                    "trophies": 4_050,
                    "highestTrophies": 4_060,
                    "prestigeLevel": 4,
                }
            ],
        }
    )
    assert player.total_prestige_level == 4
    assert player.total_prestige_source is DataSource.OFFICIAL_API
    assert player.brawlers[0].prestige_level == 4
    assert player.brawlers[0].prestige_trophies == 50
    assert player.brawlers[0].prestige_level_source is DataSource.OFFICIAL_API


def test_prestige_asset_manifest_covers_current_catalog_and_special_names() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "data" / "brawler_catalog.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "data" / "prestige_assets.json").read_text(encoding="utf-8"))
    available = set(manifest["available"]["brawler_ids"])
    assert {item["id"] for item in catalog}.issubset(available)
    by_name = {item["name"]: item["id"] for item in catalog}
    assert by_name["NORI"] in available
    assert by_name["WENDY"] in available
    assert by_name["LARRY & LAWRIE"] in available
    assert {0, 1, 2, 3, 13}.issubset(manifest["available"]["tiered_asset_ids"])
