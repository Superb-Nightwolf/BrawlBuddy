import pytest
from app.clients.brawl_stars import BrawlStarsClient
from app.core.config import get_settings
from app.services.events_service import EventsService


@pytest.mark.asyncio
async def test_events_service_load_demo():
    settings = get_settings()
    client = BrawlStarsClient(settings.brawl_stars, "test_token")
    service = EventsService(client=client)
    events, source = await service.get_events()
    assert len(events) >= 5
    assert len(events[0].top_meta_picks) > 0
    assert events[0].event.map is not None
    await client.close()
