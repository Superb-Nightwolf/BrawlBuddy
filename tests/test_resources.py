from __future__ import annotations

from pathlib import Path

from app.models.player import PlayerResources
from app.services.resource_service import ResourceService


def test_resources_round_trip() -> None:
    database_path = Path("data") / "test_resources.db"
    database_path.unlink(missing_ok=True)
    try:
        service = ResourceService(database_path)
        saved = service.save(
            PlayerResources(player_tag="#2PP", coins=4250, power_points=1800)
        )
        loaded = service.get("2pp")
        assert loaded.coins == 4250
        assert loaded.power_points == 1800
        assert loaded.updated_at == saved.updated_at
    finally:
        database_path.unlink(missing_ok=True)
