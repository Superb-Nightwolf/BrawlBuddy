from typing import Optional
from pydantic import BaseModel, Field


class RankingPlayerItem(BaseModel):
    rank: int
    tag: str
    name: str
    name_color: Optional[str] = None
    icon_id: int = 28000000
    trophies: int
    club_name: Optional[str] = None


class RankingClubItem(BaseModel):
    rank: int
    tag: str
    name: str
    badge_id: int = 8000000
    trophies: int
    member_count: int = 30


class RankingBrawlerItem(BaseModel):
    rank: int
    tag: str
    name: str
    icon_id: int = 28000000
    trophies: int
    club_name: Optional[str] = None
