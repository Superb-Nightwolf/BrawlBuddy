import json
import logging
from pathlib import Path
from typing import Any, Optional

from app.clients.brawl_stars import BrawlStarsClient
from app.models.events import EventMap, EventSlot

logger = logging.getLogger("brawlbuddy.events_service")

# Curated Map-to-Meta brawler recommendations
META_MAP_PICKS: dict[str, list[str]] = {
    "Center Stage": ["Shelly", "Bibi", "Frank", "Colt", "Max"],
    "Sneaky Fields": ["Bibi", "Frank", "Buster", "Jacky", "Cordelius"],
    "Pinball Dreams": ["Rico", "Colt", "Fang", "Piper", "Spike"],
    "Goldarm Gulch": ["Piper", "Brock", "Nani", "Gene", "Mandy"],
    "Flaring Phoenix": ["Piper", "Nani", "Belle", "Angelo", "Brock"],
    "New Horizons": ["Mandy", "Piper", "Brock", "Nani", "Gene"],
    "Hard Rock Mine": ["Gene", "Tara", "Carl", "Poco", "Pam"],
    "Double Swoosh": ["Rosa", "Bo", "Buster", "Ash", "Tara"],
    "Gem Fort": ["Penny", "Jessie", "Gene", "Poco", "Janet"],
    "Skull Creek": ["Shelly", "Bull", "Edgar", "Cordelius", "Buzz"],
    "Feast or Famine": ["Shelly", "Bull", "Buzz", "Cordelius", "Leon"],
    "Dark Passage": ["Piper", "Brock", "Crow", "Leon", "Spike"],
    "Infinite Doom": ["Colt", "Brock", "Spike", "Leon", "Crow"],
    "Dueling Beetles": ["Jessie", "Penny", "Tick", "Emz", "Amber"],
    "Open Business": ["Barley", "Tick", "Dynamike", "Grom", "Sprout"],
    "Ring of Fire": ["Amber", "Lou", "Otis", "Squeak", "Penny"],
}


class EventsService:
    def __init__(self, client: BrawlStarsClient, demo_path: Optional[Path] = None) -> None:
        self.client = client
        self.demo_path = demo_path or Path(__file__).resolve().parent.parent.parent / "data" / "demo_events.json"
        self._cached_events: Optional[list[EventSlot]] = None

    def parse_event(self, raw: dict[str, Any], slot_idx: int = 1) -> EventSlot:
        event_info = raw.get("event", {})
        map_name = event_info.get("map", "Battle Arena")
        mode_name = event_info.get("mode", raw.get("mode", "brawlBall"))
        map_id = event_info.get("id", 0)

        image_url = event_info.get("image_url") or f"https://cdn.brawlify.com/maps/regular/{map_id}.png" if map_id else None

        modifiers = [str(m).upper() for m in raw.get("modifiers", [])]
        meta_picks = META_MAP_PICKS.get(map_name, ["Shelly", "Colt", "Brock", "Spike", "Piper"])

        start_time = raw.get("startTime", raw.get("start_time", ""))
        end_time = raw.get("endTime", raw.get("end_time", ""))

        return EventSlot(
            slot_id=raw.get("slot_id", slot_idx),
            event=EventMap(
                id=map_id,
                mode=mode_name,
                map=map_name,
                image_url=image_url
            ),
            start_time=start_time,
            end_time=end_time,
            time_remaining_seconds=raw.get("time_remaining_seconds", 3600),
            time_remaining_label=raw.get("time_remaining_label", "Active now"),
            modifiers=modifiers,
            top_meta_picks=meta_picks
        )

    def load_demo(self) -> list[EventSlot]:
        if not self.demo_path.exists():
            return []
        with self.demo_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [self.parse_event(item, idx + 1) for idx, item in enumerate(data)]

    async def get_events(self) -> tuple[list[EventSlot], str]:
        if self._cached_events:
            return self._cached_events, "CACHE"

        if not self.client.api_key:
            demo_events = self.load_demo()
            return demo_events, "DEMO"

        try:
            raw_events = await self.client.get_events()
            events = [self.parse_event(item, idx + 1) for idx, item in enumerate(raw_events)]
            self._cached_events = events
            return events, "LIVE"
        except Exception as e:
            logger.warning(f"Failed to fetch live event rotation: {e}. Falling back to demo.")
            return self.load_demo(), "DEMO"
