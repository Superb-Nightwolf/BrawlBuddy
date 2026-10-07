from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models.club import ClubMember, ClubProfile
from app.services.club_analytics_service import summarize_club_roster
from app.services.club_service import ClubService


def club_with(values, roles=None, reported=None):
    roles = roles or ["member"] * len(values)
    return ClubProfile(tag="#PQL20", name="Test club", trophies=sum(values) if reported is None else reported,
                       required_trophies=25000,
                       members=[ClubMember(tag=f"#Q{i}", name=f"Member {i}", trophies=value, role=role)
                                for i, (value, role) in enumerate(zip(values, roles))])


def test_club_metrics_use_roster_sum_and_correct_denominators():
    club = club_with([10000, 20000, 30000, 40000], ["president", "vicePresident", "senior", "member"], reported=120000)
    result = summarize_club_roster(club)
    assert result["roster_trophies"] == 100000
    assert result["reported_trophies"] == 120000
    assert result["total_difference"] == 20000
    assert result["totals_match"] is False
    assert result["average_trophies"] == 25000
    assert result["median_trophies"] == 25000
    assert result["q1"] == 17500
    assert result["q3"] == 32500
    assert result["standard_deviation"] == 11180.34
    assert result["top5_count"] == 4
    assert result["top5_share"] == 100
    assert result["capacity_percent"] == 13.33
    assert result["open_slots"] == 26
    assert result["leadership_count"] == 2
    assert result["leadership_pct"] == 50
    assert result["below_entry"] == 2
    assert result["entry_deficit"] == 20000
    assert result["above_average"] == 2
    assert result["next_target"] == 200000
    assert result["to_target"] == 100000
    assert sum(row["value"] for row in result["distribution"]) == 4
    assert [row["value"] for row in result["distribution"]] == [1, 2, 1, 0, 0, 0]
    assert result["rows"][0]["share"] == 40
    assert result["rows"][-1]["cumulative_share"] == 100
    assert sum(row["trophies"] for row in result["roles"]) == 100000
    assert "prestige_tier" not in result


def test_empty_roster_has_unknown_averages_and_zero_counts():
    result = summarize_club_roster(club_with([]))
    for key in ("average_trophies", "median_trophies", "min_trophies", "max_trophies", "q1", "q3", "standard_deviation", "top5_share"):
        assert result[key] is None
    assert result["member_count"] == result["roster_trophies"] == 0
    assert result["open_slots"] == 30
    assert result["rows"] == []
    assert result["presidents_count"] == 0
    assert all(row["value"] == 0 for row in result["roles"])


def test_ties_unknown_roles_and_zero_trophies_are_not_fabricated():
    result = summarize_club_roster(club_with([0, 0, 0], ["vice_president", "coLeader", "senior"]))
    assert all(row["rank"] == 1 for row in result["rows"])
    assert all(row["share"] is None for row in result["rows"])
    assert result["standard_deviation"] == 0
    assert result["q1"] == result["q3"] == 0
    assert result["vice_presidents_count"] == 1
    assert result["presidents_count"] == 0
    assert next(row for row in result["roles"] if row["key"] == "unknown")["value"] == 1
    ranked = summarize_club_roster(club_with([100, 200, 200]))
    assert [row["rank"] for row in ranked["rows"]] == [1, 1, 3]


def test_large_roster_cohorts_do_not_overlap():
    result = summarize_club_roster(club_with(list(range(10000, 310000, 10000))))
    assert result["open_slots"] == 0
    assert result["capacity_percent"] == 100
    assert result["top5_trophies"] == sum(range(260000, 310000, 10000))
    assert result["top10_trophies"] == sum(range(210000, 310000, 10000))
    assert sum(row["value"] for row in result["distribution"]) == 30
    assert result["top5_share"] < result["top10_share"] < 100


@pytest.mark.asyncio
async def test_manual_club_refresh_bypasses_the_cache():
    class Client:
        calls = 0

        async def get_club(self, tag):
            self.calls += 1
            return {"tag": tag, "name": f"Snapshot {self.calls}", "members": []}

    client = Client()
    service = ClubService(client, Path("unused"), 300)
    first, cached = await service.get_club("#PQL20")
    assert not cached
    second, cached = await service.get_club("#PQL20")
    assert cached and second.name == first.name
    refreshed, cached = await service.get_club("#PQL20", refresh=True)
    assert not cached and refreshed.name == "Snapshot 2"
    assert client.calls == 2


def test_demo_route_returns_chart_metrics_and_no_invented_league():
    from app.main import app

    with TestClient(app) as client:
        payload = client.get("/api/demo/club").json()
    members, summary = payload["club"]["members"], payload["analytics"]
    assert summary["member_count"] == len(members)
    assert summary["roster_trophies"] == sum(member["trophies"] for member in members)
    assert summary["average_trophies"] == round(summary["roster_trophies"] / len(members), 2)
    assert len(summary["rows"]) == 30
    assert "prestige_tier" not in summary


def test_club_route_forwards_refresh_and_exposes_calculated_fields(monkeypatch):
    from app import main

    calls = []

    async def load(tag, refresh=False):
        calls.append((tag, refresh))
        return club_with([10000, 30000]), False

    monkeypatch.setattr(main.club_service, "get_club", load)
    with TestClient(main.app) as client:
        response = client.get("/api/club?tag=%23PQL20&refresh=true")
    assert response.status_code == 200
    assert calls == [("#PQL20", True)]
    assert response.json()["analytics"]["median_trophies"] == 20000
