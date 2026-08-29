from __future__ import annotations

import pytest

from app.core.errors import InvalidPlayerTag
from app.models.player import DataSource
from app.services.player_service import normalize_player_tag, parse_player


def test_normalize_player_tag() -> None:
    assert normalize_player_tag(" 2pp ") == "#2PP"
    assert normalize_player_tag("#pylq") == "#PYLQ"


@pytest.mark.parametrize("tag", ["", "#ABC", "#12-34", "not-a-tag"])
def test_rejects_invalid_player_tag(tag: str) -> None:
    with pytest.raises(InvalidPlayerTag):
        normalize_player_tag(tag)


def test_parse_player_uses_only_available_fields() -> None:
    payload = {
        "tag": "#2PP",
        "name": "Nova",
        "trophies": 500,
        "brawlers": [
            {
                "id": 1,
                "name": "SHELLY",
                "power": 9,
                "rank": 20,
                "trophies": 400,
                "highestTrophies": 450,
            }
        ],
    }
    player = parse_player(payload)
    assert player.name == "Nova"
    assert player.brawlers[0].gadgets == []
    assert player.source is DataSource.OFFICIAL_API
    assert player.average_power == 9.0


def test_parse_player_prestige_and_victories() -> None:
    payload = {
        "tag": "#2PP",
        "name": "Nova",
        "trophies": 28476,
        "highestTrophies": 29120,
        "expLevel": 186,
        "expPoints": 143200,
        "3vs3Victories": 8421,
        "soloVictories": 614,
        "duoVictories": 1058,
        "isQualifiedFromChampionshipChallenge": True,
        "bestRoboRumbleTime": 16,
        "club": {"tag": "#PQL20", "name": "Starrbound"},
        "brawlers": [
            {"id": 1, "name": "SHELLY", "power": 11, "rank": 30, "trophies": 906},
            {"id": 2, "name": "COLT", "power": 10, "rank": 26, "trophies": 812},
        ],
    }
    player = parse_player(payload)
    assert player.total_showdown_victories == 1672
    assert player.total_victories == 10093
    assert player.rank_25_plus_count == 2
    assert player.rank_30_plus_count == 1
    assert player.prestige_tier == "Mythic Champion"
    assert player.is_qualified_from_championship_challenge is True
    assert player.club.name == "Starrbound"


