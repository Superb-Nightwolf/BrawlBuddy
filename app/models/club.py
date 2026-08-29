from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.player import DataSource


class ClubMember(BaseModel):
    tag: str
    name: str
    name_color: str | None = None
    role: str = "member"  # president, vicePresident, senior, member
    trophies: int = Field(default=0, ge=0)
    icon_id: int | None = None


class ClubProfile(BaseModel):
    tag: str
    name: str
    description: str | None = None
    type: str = "open"  # open, inviteOnly, closed
    badge_id: int | None = None
    required_trophies: int = Field(default=0, ge=0)
    trophies: int = Field(default=0, ge=0)
    members: list[ClubMember] = Field(default_factory=list)
    source: DataSource = DataSource.OFFICIAL_API
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def max_members(self) -> int:
        return 30

    @property
    def capacity_percent(self) -> int:
        return round((len(self.members) / 30) * 100)

    @property
    def average_trophies(self) -> int:
        if not self.members:
            return 0
        return round(self.trophies / len(self.members))

    @property
    def top_member(self) -> ClubMember | None:
        if not self.members:
            return None
        return max(self.members, key=lambda m: m.trophies)

    @property
    def president(self) -> ClubMember | None:
        for m in self.members:
            if m.role.lower() == "president":
                return m
        return self.members[0] if self.members else None

    @property
    def vice_presidents_count(self) -> int:
        return sum(1 for m in self.members if m.role.lower() in {"vicepresident", "vice_president"})

    @property
    def seniors_count(self) -> int:
        return sum(1 for m in self.members if m.role.lower() == "senior")

    @property
    def regular_members_count(self) -> int:
        return sum(1 for m in self.members if m.role.lower() == "member")

    @property
    def prestige_tier(self) -> str:
        if self.trophies >= 1_000_000:
            return "Masters Syndicate"
        if self.trophies >= 800_000:
            return "Legendary Alliance"
        if self.trophies >= 600_000:
            return "Mythic Guild"
        if self.trophies >= 400_000:
            return "Diamond League"
        if self.trophies >= 200_000:
            return "Gold Division"
        return "Silver Division"
