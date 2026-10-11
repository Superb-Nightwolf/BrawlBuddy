import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_meta_filters_endpoint():
    response = client.get("/api/meta/filters")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "modes" in data["data"]
    assert "brawlBall" in data["data"]["modes"]


def test_meta_brawlers_endpoint():
    response = client.get("/api/meta/brawlers?mode=brawlBall")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "brawlers" in data
    assert len(data["brawlers"]) > 0
    first = data["brawlers"][0]
    assert "brawler_id" in first
    assert "smoothed_win_rate" in first
    assert "tier" in first


def test_meta_teams_endpoint():
    response = client.get("/api/meta/teams?mode=brawlBall&min_matches=1")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "teams" in data


def test_predict_match_endpoint():
    payload = {
        "mode": "brawlBall",
        "map": "Center Stage",
        "teamBrawlers": [16000000, 16000001, 16000002],
        "enemyBrawlers": [16000003, 16000004, 16000005],
        "powerDiff": 0.0,
    }
    response = client.post("/api/ml/predict-match", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    pred = data["data"]
    assert "win_probability" in pred
    assert 0.0 <= pred["win_probability"] <= 1.0


def test_recommend_endpoint():
    payload = {
        "mode": "brawlBall",
        "map": "Center Stage",
        "teamBrawlers": [16000000],
        "enemyBrawlers": [16000003],
        "top_k": 5,
    }
    response = client.post("/api/ml/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    recs = data["recommendations"]
    assert len(recs) <= 5
    for r in recs:
        assert "brawler_id" in r
        assert "score" in r
        assert "explanation" in r


def test_model_status_endpoint():
    response = client.get("/api/ml/model-status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "metrics" in data
    assert "dataset" in data
    assert data["dataset"]["total_unique_matches"] > 0


def test_meta_page_route():
    response = client.get("/meta")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_operations_telemetry():
    response = client.get("/api/ml/operations/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "telemetry" in data
    assert data["telemetry"]["total_matches"] > 0
    assert "model" in data


def test_operations_status():
    response = client.get("/api/ml/operations/status")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "task" in data


def test_operations_retrain():
    response = client.post("/api/ml/operations/retrain")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "lgbm" in data
    assert data["lgbm"]["roc_auc"] > 0.80


def test_transparency_summary_endpoint():
    response = client.get("/api/ml/transparency/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "dataset" in data
    assert "benchmark_leaderboard" in data
    assert len(data["benchmark_leaderboard"]) >= 5
    assert "feature_importances" in data


def test_draft_step_endpoint():
    payload = {
        "mode": "brawlBall",
        "map": "Center Stage",
        "draftAllies": [16000000],
        "draftEnemies": [16000003],
        "activeSlot": "ally_2",
        "top_k": 5,
    }
    response = client.post("/api/ml/draft/step", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    step_data = data["data"]
    assert "current_win_probability" in step_data
    assert "candidates" in step_data
    assert len(step_data["candidates"]) <= 5
    assert "win_rate_delta" in step_data["candidates"][0]


def test_incremental_status_endpoint():
    response = client.get("/api/ml/operations/incremental-status")
    assert response.status_code == 200
    data = response.json()
    assert "total_players" in data
    assert "unpolled_players" in data
    assert "target_players" in data
    assert data["target_players"] == 100000

