import pytest
from pathlib import Path
from app.clients.brawl_stars import BrawlStarsClient
from app.core.config import get_settings
from app.services.battlelog_service import BattleLogService


@pytest.mark.asyncio
async def test_battlelog_service_load_demo():
    settings = get_settings()
    client = BrawlStarsClient(settings.brawl_stars, "test_token")
    service = BattleLogService(client=client)
    items, source = await service.get_battlelog("#2PP")
    assert len(items) > 0
    assert items[0].event.map is not None
    assert items[0].team_a_avg_power > 0
    await client.close()
