from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class AppConfig(BaseModel):
    name: str = "BrawlBuddy"
    debug: bool = False
    demo_mode: bool = True
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)


class BrawlStarsConfig(BaseModel):
    api_base_url: str = "https://api.brawlstars.com/v1"
    token_env: str = "BRAWL_STARS_API_TOKEN"
    timeout_seconds: float = Field(default=10.0, gt=0)
    retry_attempts: int = Field(default=3, ge=1, le=5)


class CacheConfig(BaseModel):
    player_seconds: int = Field(default=180, ge=0)
    brawlers_seconds: int = Field(default=86400, ge=0)


class Settings(BaseModel):
    app: AppConfig = AppConfig()
    brawl_stars: BrawlStarsConfig = BrawlStarsConfig()
    cache: CacheConfig = CacheConfig()

    @property
    def api_token(self) -> str | None:
        value = os.getenv(self.brawl_stars.token_env, "").strip()
        return value or None


def _env_bool(name: str, fallback: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings(config_path: Path | None = None) -> Settings:
    path = config_path or PROJECT_ROOT / "config" / "config.yaml"
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    settings = Settings.model_validate(raw)
    settings.app.demo_mode = _env_bool("BRAWL_ADVISOR_DEMO_MODE", settings.app.demo_mode)
    settings.app.debug = _env_bool("BRAWL_ADVISOR_DEBUG", settings.app.debug)
    settings.app.host = os.getenv("BRAWL_ADVISOR_HOST", settings.app.host)
    settings.app.port = int(os.getenv("BRAWL_ADVISOR_PORT", settings.app.port))
    return settings
