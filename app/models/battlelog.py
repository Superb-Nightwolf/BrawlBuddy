from typing import Any, Optional
from pydantic import BaseModel, Field


class BattleBrawler(BaseModel):
    id: int
    name: str
    power: int = 1
    trophies: int = 0
    icon_id: Optional[int] = None


class BattlePlayer(BaseModel):
    tag: str
    name: str
    brawler: BattleBrawler
    is_star_player: bool = False


class BattleTeam(BaseModel):
    players: list[BattlePlayer]
    average_power: float = 0.0
    total_trophies: int = 0


class BattleEvent(BaseModel):
    id: int
    mode: str
    map: str


class BattleLogEntry(BaseModel):
    battle_time: str
    event: BattleEvent
    mode: str
    type: str = "ranked"
    result: Optional[str] = None  # "victory", "defeat", "draw"
    duration: Optional[int] = None
    trophy_change: Optional[int] = None
    star_player: Optional[BattlePlayer] = None
    teams: list[list[BattlePlayer]] = Field(default_factory=list)
    players: list[BattlePlayer] = Field(default_factory=list)  # For solo/duo showdown
    rank: Optional[int] = None  # For showdown (e.g. 1st, 2nd)
    team_a_avg_power: float = 0.0
    team_b_avg_power: float = 0.0
    power_advantage: str = "balanced"  # "blue_favored", "red_favored", "balanced"
