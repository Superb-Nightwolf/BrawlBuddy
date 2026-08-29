from typing import Any, Optional
from pydantic import BaseModel, Field


class EventMap(BaseModel):
    id: int
    mode: str
    map: str
    image_url: Optional[str] = None


class EventModifier(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None


class EventSlot(BaseModel):
    slot_id: int
    event: EventMap
    start_time: str
    end_time: str
    time_remaining_seconds: int = 0
    time_remaining_label: str = ""
    modifiers: list[str] = Field(default_factory=list)
    top_meta_picks: list[str] = Field(default_factory=list)
