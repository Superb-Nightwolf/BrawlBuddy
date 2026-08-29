from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.models.player import PlayerResources
from app.services.player_service import normalize_player_tag


class ResourceService:
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._database_path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS player_resources (
                    player_tag TEXT PRIMARY KEY,
                    coins INTEGER NOT NULL DEFAULT 0 CHECK (coins >= 0),
                    power_points INTEGER NOT NULL DEFAULT 0 CHECK (power_points >= 0),
                    gems INTEGER NOT NULL DEFAULT 0 CHECK (gems >= 0),
                    credits INTEGER NOT NULL DEFAULT 0 CHECK (credits >= 0),
                    bling INTEGER NOT NULL DEFAULT 0 CHECK (bling >= 0),
                    updated_at TEXT NOT NULL
                )
                """
            )

    def get(self, raw_tag: str) -> PlayerResources:
        tag = normalize_player_tag(raw_tag)
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM player_resources WHERE player_tag = ?", (tag,)
            ).fetchone()
        if not row:
            return PlayerResources(player_tag=tag)
        return PlayerResources(**dict(row))

    def save(self, resources: PlayerResources) -> PlayerResources:
        resources.player_tag = normalize_player_tag(resources.player_tag)
        resources.updated_at = datetime.now(UTC)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO player_resources
                    (player_tag, coins, power_points, gems, credits, bling, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_tag) DO UPDATE SET
                    coins = excluded.coins,
                    power_points = excluded.power_points,
                    gems = excluded.gems,
                    credits = excluded.credits,
                    bling = excluded.bling,
                    updated_at = excluded.updated_at
                """,
                (
                    resources.player_tag,
                    resources.coins,
                    resources.power_points,
                    resources.gems,
                    resources.credits,
                    resources.bling,
                    resources.updated_at.isoformat(),
                ),
            )
        return resources
