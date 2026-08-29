import pytest
from app.clients.brawl_stars import BrawlStarsClient
from app.core.config import get_settings
from app.services.rankings_service import RankingsService


@pytest.mark.asyncio
async def test_rankings_service_load_demo():
    settings = get_settings()
    client = BrawlStarsClient(settings.brawl_stars, "test_token")
    service = RankingsService(client=client)
    players, _ = await service.get_player_rankings("global")
    assert len(players) > 0
    assert players[0].rank == 1
    assert players[0].trophies > 0

    clubs, _ = await service.get_club_rankings("global")
    assert len(clubs) > 0
    assert clubs[0].rank == 1
    assert clubs[0].trophies > 0
    await client.close()
