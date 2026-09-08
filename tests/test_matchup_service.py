import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.matchup_service import MatchupService


@pytest.fixture
def client():
    return TestClient(app)


def test_brawler_matchups_catalog():
    data_path = Path(__file__).resolve().parent.parent / "data" / "brawler_matchups.json"
    assert data_path.exists(), "data/brawler_matchups.json must exist"

    with data_path.open("r", encoding="utf-8") as f:
        matchups = json.load(f)

    assert len(matchups) == 106, "All 106 catalog brawlers must have matchup profiles"

    for brawler_id, data in matchups.items():
        assert "brawler_id" in data
        assert "strong_against" in data and len(data["strong_against"]) >= 6
        assert "struggles_against" in data and len(data["struggles_against"]) >= 6
        assert "best_alongside" in data and len(data["best_alongside"]) >= 6

        for item in data["strong_against"]:
            assert "id" in item and isinstance(item["id"], int)
            assert "name" in item and len(item["name"]) > 0
            assert "win_rate" in item and 0 <= item["win_rate"] <= 100
            assert "total_battles" in item and item["total_battles"] > 0


def test_rosa_poc_matchup_values_exact():
    service = MatchupService()
    rosa = service.get_matchups(16000024)

    assert rosa["brawler_name"] == "Rosa"

    # Verify Strong Against top 6 from POC
    strong_top6 = [(x["name"], x["win_rate"], x["total_battles"]) for x in rosa["strong_against"][:6]]
    expected_strong = [
        ("Edgar", 80.4, 4022),
        ("Mortis", 78.0, 3461),
        ("Lily", 75.5, 619),
        ("Tick", 75.1, 2651),
        ("Piper", 74.3, 1588),
        ("Shelly", 72.5, 1339),
    ]
    assert strong_top6 == expected_strong, f"Rosa strong_against must match POC reference exactly: {strong_top6}"

    # Verify Struggles Against top 6 from POC
    struggles_top6 = [(x["name"], x["win_rate"], x["total_battles"]) for x in rosa["struggles_against"][:6]]
    expected_struggles = [
        ("Kaze", 49.9, 445),
        ("Gray", 50.1, 2523),
        ("Gene", 50.1, 297),
        ("Bo", 50.2, 1569),
        ("Barley", 50.9, 488),
        ("Meg", 51.1, 1024),
    ]
    assert struggles_top6 == expected_struggles, f"Rosa struggles_against must match POC reference exactly: {struggles_top6}"

    # Verify Best Alongside top 6 from POC
    alongside_top6 = [(x["name"], x["win_rate"], x["total_battles"]) for x in rosa["best_alongside"][:6]]
    expected_alongside = [
        ("Belle", 78.4, 1590),
        ("Gray", 77.2, 6722),
        ("Pierce", 76.8, 1478),
        ("Max", 75.4, 1692),
        ("Lumi", 74.3, 1557),
        ("Otis", 73.9, 1396),
    ]
    assert alongside_top6 == expected_alongside, f"Rosa best_alongside must match POC reference exactly: {alongside_top6}"


def test_matchup_service_fallback():
    service = MatchupService()
    res = service.get_matchups(99999999)
    assert res["brawler_id"] == 99999999
    assert len(res["strong_against"]) > 0
    assert len(res["struggles_against"]) > 0
    assert len(res["best_alongside"]) > 0
    assert "methodology" in res


def test_api_brawler_matchups_route(client):
    response = client.get("/api/brawlers/16000024/matchups")
    assert response.status_code == 200
    data = response.json()
    assert data["brawler_id"] == 16000024
    assert len(data["strong_against"]) >= 6
    assert data["methodology"]["source"] == "COMMUNITY WIN-RATE METRICS"


def test_api_brawler_matchups_refresh_route(client):
    response = client.post("/api/brawlers/16000024/matchups/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["brawler_id"] == 16000024
    assert len(data["strong_against"]) >= 6
    assert data["methodology"]["source"] == "COMMUNITY WIN-RATE METRICS"
    assert data.get("is_dynamic") is True


def test_api_guide_includes_matchups(client):
    response = client.get("/api/guides/16000024")
    assert response.status_code == 200
    data = response.json()
    assert "matchups" in data
    assert len(data["matchups"]["strong_against"]) >= 6
    assert data["matchups"]["methodology"]["source"] == "COMMUNITY WIN-RATE METRICS"

