from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

main = importlib.import_module("app.main")


@pytest.mark.parametrize(
    "path",
    [
        "/api/battlelog?tag=2PP",
        "/api/events",
        "/api/rankings/players",
        "/api/rankings/clubs",
    ],
)
def test_missing_token_returns_demo_instead_of_server_error(monkeypatch, path):
    for service in (main.battlelog_service, main.events_service, main.rankings_service):
        monkeypatch.setattr(service, "client", None)
    monkeypatch.setattr(main.events_service, "_cached_events", None)
    with TestClient(main.app) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.json()["source"] == "DEMO"
    assert response.json()["items"]


def test_public_alpha_cannot_overwrite_resource_balances(monkeypatch):
    monkeypatch.setattr(main.settings.app, "allow_resource_writes", False)
    with TestClient(main.app) as client:
        response = client.put("/api/resources/2PP", json={"player_tag": "2PP", "coins": 999})
    assert response.status_code == 403


def test_frontend_configuration_is_served_as_uncached_javascript():
    with TestClient(main.app) as client:
        response = client.get("/config.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert response.headers["cache-control"] == "no-store"


def test_production_environment_allows_only_configured_firebase_origin(tmp_path):
    script = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    for origin in ['https://test-alpha.web.app', 'https://other.web.app']:
        response = client.options('/api/status', headers={
            'Origin': origin, 'Access-Control-Request-Method': 'GET'
        })
        print(response.status_code, response.headers.get('access-control-allow-origin', '-'))
"""
    env = {
        **os.environ,
        "BRAWL_STARS_API_TOKEN": "",
        "BRAWL_ADVISOR_CORS_ORIGINS": "https://test-alpha.web.app",
        "BRAWL_ADVISOR_DATABASE_PATH": str(tmp_path / "resources.db"),
    }
    result = subprocess.run(
        [sys.executable, "-c", script], env=env, text=True, capture_output=True, check=True
    )
    assert result.stdout.splitlines() == ["200 https://test-alpha.web.app", "400 -"]


def test_firebase_upload_directory_contains_only_frontend_files():
    from pathlib import Path

    config = json.loads(Path("firebase.json").read_text(encoding="utf-8"))
    public = Path(config["hosting"]["public"])
    assert public == Path("app/ui")
    assert (public / "index.html").is_file()
    assert not list(public.rglob(".env*"))
    assert not list(public.rglob("*.db"))
