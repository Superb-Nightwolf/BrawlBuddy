from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DataSource(StrEnum):
    OFFICIAL_API = "OFFICIAL_API"
    USER_INPUT = "USER_INPUT"
    STATIC_GAME_DATA = "STATIC_GAME_DATA"
    COMMUNITY_SOURCE = "COMMUNITY_SOURCE"
    CALCULATED = "CALCULATED"
    INFERRED = "INFERRED"
    DEMO = "DEMO"


class ClubSummary(BaseModel):
    tag: str | None = None
    name: str | None = None


class EquipmentItem(BaseModel):
    id: int
    name: str
    level: int | None = None


class PlayerBrawler(BaseModel):
    id: int
    name: str
    power: int = Field(ge=1)
    rank: int = Field(default=1, ge=1)
    trophies: int = Field(default=0, ge=0)
    highest_trophies: int = Field(default=0, ge=0)
    gadgets: list[EquipmentItem] = Field(default_factory=list)
    star_powers: list[EquipmentItem] = Field(default_factory=list)
    gears: list[EquipmentItem] = Field(default_factory=list)
    hypercharges: list[EquipmentItem] = Field(default_factory=list)
    buffies: list[str] = Field(default_factory=list)
    source: DataSource = DataSource.OFFICIAL_API

    @property
    def has_hypercharge(self) -> bool:
        return len(self.hypercharges) > 0 or any("hyper" in b.lower() for b in self.buffies)

    @property
    def is_hypercharge_active(self) -> bool:
        return self.has_hypercharge and self.power == 11

    @property
    def is_hypercharge_stored(self) -> bool:
        return self.has_hypercharge and self.power < 11


class PlayerProfile(BaseModel):
    tag: str
    name: str
    name_color: str | None = None
    icon_id: int | None = None
    trophies: int = Field(default=0, ge=0)
    highest_trophies: int = Field(default=0, ge=0)
    exp_level: int | None = Field(default=None, ge=0)
    exp_points: int | None = Field(default=None, ge=0)
    victories_3v3: int = Field(default=0, ge=0)
    solo_victories: int = Field(default=0, ge=0)
    duo_victories: int = Field(default=0, ge=0)
    is_qualified_from_championship_challenge: bool = False
    best_robo_rumble_time: int | None = None
    best_time_as_big_brawler: int | None = None
    highest_power_play_points: int | None = None
    club: ClubSummary | None = None
    brawlers: list[PlayerBrawler] = Field(default_factory=list)
    source: DataSource = DataSource.OFFICIAL_API
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def average_power(self) -> float:
        if not self.brawlers:
            return 0
        return round(sum(item.power for item in self.brawlers) / len(self.brawlers), 1)

    @property
    def power_11_count(self) -> int:
        return sum(item.power == 11 for item in self.brawlers)

    @property
    def rank_35_count(self) -> int:
        return sum(item.rank >= 35 for item in self.brawlers)

    @property
    def rank_30_plus_count(self) -> int:
        return sum(item.rank >= 30 for item in self.brawlers)

    @property
    def rank_25_plus_count(self) -> int:
        return sum(item.rank >= 25 for item in self.brawlers)

    @property
    def rank_20_plus_count(self) -> int:
        return sum(item.rank >= 20 for item in self.brawlers)

    @property
    def rank_15_plus_count(self) -> int:
        return sum(item.rank >= 15 for item in self.brawlers)

    @property
    def total_gadgets_count(self) -> int:
        return sum(len(item.gadgets) for item in self.brawlers)

    @property
    def total_star_powers_count(self) -> int:
        return sum(len(item.star_powers) for item in self.brawlers)

    @property
    def total_gears_count(self) -> int:
        return sum(len(item.gears) for item in self.brawlers)

    @property
    def total_hypercharges_count(self) -> int:
        return sum(1 for item in self.brawlers if item.has_hypercharge)

    @property
    def active_hypercharges_count(self) -> int:
        return sum(1 for item in self.brawlers if item.is_hypercharge_active)

    @property
    def next_trophy_milestone(self) -> int:
        trophies = self.highest_trophies or self.trophies
        milestones = [5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000, 50000, 60000, 70000, 80000, 100000]
        for m in milestones:
            if trophies < m:
                return m
        return trophies + 5000

    @property
    def total_showdown_victories(self) -> int:
        return self.solo_victories + self.duo_victories

    @property
    def total_victories(self) -> int:
        return self.victories_3v3 + self.solo_victories + self.duo_victories

    @property
    def brawler_prestige_level(self) -> int:
        """Calculate player prestige: each 1000 trophies (current or highest peak record) on any brawler equals 1 prestige point."""
        return sum(max(item.trophies, item.highest_trophies) // 1000 for item in self.brawlers)

    @property
    def prestige_tier(self) -> str:
        trophies = self.highest_trophies or self.trophies
        if trophies >= 50_000:
            return "Masters League"
        if trophies >= 35_000:
            return "Legendary Tier"
        if trophies >= 25_000:
            return "Mythic Champion"
        if trophies >= 15_000:
            return "Diamond League"
        if trophies >= 10_000:
            return "Gold Tier"
        if trophies >= 5_000:
            return "Silver League"
        return "Bronze Challenger"

    @property
    def combat_archetype(self) -> str:
        total = self.total_victories or 1
        pct_3v3 = (self.victories_3v3 / total) * 100
        pct_solo = (self.solo_victories / total) * 100
        pct_duo = (self.duo_victories / total) * 100
        if pct_3v3 >= 60:
            return "3v3 Team Tactician"
        if pct_solo >= 40:
            return "Showdown Lone Wolf"
        if pct_duo >= 40:
            return "Duo Syndicate Specialist"
        return "Versatile Arena Master"

    @property
    def completion_score(self) -> int:
        total_possible_brawlers = 106
        roster_pct = (len(self.brawlers) / total_possible_brawlers) * 100
        power11_pct = (self.power_11_count / max(1, len(self.brawlers))) * 100
        max_equip = len(self.brawlers) * 8
        total_equip = self.total_gadgets_count + self.total_star_powers_count + self.total_gears_count + self.total_hypercharges_count
        equip_pct = (total_equip / max(1, max_equip)) * 100
        score = (roster_pct * 0.4) + (power11_pct * 0.35) + (equip_pct * 0.25)
        return min(100, max(1, round(score)))

    @property
    def top_loadouts(self) -> list[dict]:
        sorted_brawlers = sorted(self.brawlers, key=lambda b: b.trophies, reverse=True)[:3]
        return [
            {
                "id": b.id,
                "name": b.name,
                "power": b.power,
                "rank": b.rank,
                "trophies": b.trophies,
                "highest_trophies": b.highest_trophies,
                "gadget": b.gadgets[0].name if b.gadgets else None,
                "star_power": b.star_powers[0].name if b.star_powers else None,
                "gears": [g.name for g in b.gears],
                "hypercharge": b.hypercharges[0].name if b.hypercharges else None,
            }
            for b in sorted_brawlers
        ]


class PlayerResources(BaseModel):
    player_tag: str
    coins: int = Field(default=0, ge=0, le=100_000_000)
    power_points: int = Field(default=0, ge=0, le=100_000_000)
    gems: int = Field(default=0, ge=0, le=100_000_000)
    credits: int = Field(default=0, ge=0, le=100_000_000)
    bling: int = Field(default=0, ge=0, le=100_000_000)
    source: DataSource = DataSource.USER_INPUT
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

