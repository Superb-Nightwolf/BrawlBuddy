from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from app.core.readiness_config import READINESS_CONFIG

from app.models.player import DataSource, PlayerBrawler


class ReadinessRequest(BaseModel):
    """Calculate from the already-loaded inventory; no purchase or inventory write."""

    brawlers: list[PlayerBrawler] = Field(default_factory=list, max_length=200)
    source: DataSource = DataSource.USER_INPUT
    targetPower: int = Field(default=READINESS_CONFIG["targetPower"], ge=1, le=11)
    remainingClawPoolSize: int | None = Field(default=None, ge=0, le=1000)

    @field_validator("brawlers")
    @classmethod
    def validate_inventory(cls, value: list[PlayerBrawler]) -> list[PlayerBrawler]:
        if len({item.id for item in value}) != len(value):
            raise ValueError("Duplicate brawler IDs in inventory")
        if any(item.power > 11 for item in value):
            raise ValueError("Power level cannot exceed 11")
        return value
