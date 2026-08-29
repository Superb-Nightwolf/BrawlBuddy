from pathlib import Path

import pytest

from app.core.errors import InvalidPlayerTag
from app.models.player import DataSource
from app.services.club_service import ClubService, normalize_club_tag, parse_club

DEMO_FILE = Path(__file__).resolve().parent.parent / "data" / "demo_club.json"


def test_normalize_club_tag():
    assert normalize_club_tag("pql20") == "#PQL20"
    assert normalize_club_tag("#pql20") == "#PQL20"
    assert normalize_club_tag(" #2y8l89 ") == "#2Y8L89"
    with pytest.raises(InvalidPlayerTag):
        normalize_club_tag("INVALID_TAG_TOO_LONG_1234567890")
    with pytest.raises(InvalidPlayerTag):
        normalize_club_tag("1")


def test_parse_demo_club():
    service = ClubService(client=None, demo_file=DEMO_FILE, cache_seconds=60)
    club = service.get_demo_club()
    assert club.tag == "#PQL20"
    assert club.name == "Starrbound Alliance"
    assert club.member_count == 30
    assert club.capacity_percent == 100
    assert club.top_member is not None
    assert club.top_member.trophies >= 29000
    assert club.president is not None
    assert club.president.role == "president"
    assert club.vice_presidents_count == 2
    assert club.seniors_count == 4
    assert club.regular_members_count == 23
    assert club.prestige_tier == "Legendary Alliance"
