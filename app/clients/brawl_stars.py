from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any
from urllib.parse import quote

import httpx
import truststore

from app.core.config import BrawlStarsConfig
from app.core.errors import (
    ApiAuthenticationError,
    ApiRateLimited,
    PlayerNotFound,
    UpstreamUnavailable,
)

logger = logging.getLogger(__name__)


class BrawlStarsClient:
    """Small async client for the documented official Brawl Stars API."""

    def __init__(self, config: BrawlStarsConfig, token: str) -> None:
        self._config = config
        self._token = token
        ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._client = httpx.AsyncClient(
            base_url=config.api_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=httpx.Timeout(config.timeout_seconds),
            verify=ssl_context,
        )

    @property
    def api_key(self) -> str:
        return self._token

    async def close(self) -> None:
        await self._client.aclose()

    async def get_player(self, player_tag: str) -> dict[str, Any]:
        encoded_tag = quote(player_tag, safe="")
        return await self._request(f"/players/{encoded_tag}")

    async def get_battlelog(self, player_tag: str) -> dict[str, Any]:
        encoded_tag = quote(player_tag, safe="")
        return await self._request(f"/players/{encoded_tag}/battlelog")

    async def get_club(self, club_tag: str) -> dict[str, Any]:
        encoded_tag = quote(club_tag, safe="")
        return await self._request(f"/clubs/{encoded_tag}")

    async def get_events(self) -> list[dict[str, Any]]:
        return await self._request("/events/rotation")

    async def get_rankings_players(self, country_code: str = "global") -> dict[str, Any]:
        return await self._request(f"/rankings/{country_code}/players")

    async def get_rankings_clubs(self, country_code: str = "global") -> dict[str, Any]:
        return await self._request(f"/rankings/{country_code}/clubs")

    async def get_brawlers(self) -> dict[str, Any]:
        return await self._request("/brawlers")

    async def _request(self, path: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._config.retry_attempts):
            try:
                response = await self._client.get(path)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt + 1 < self._config.retry_attempts:
                    await asyncio.sleep(0.35 * (2**attempt))
                    continue
                raise UpstreamUnavailable("The Brawl Stars API did not respond in time.") from exc

            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise UpstreamUnavailable("The Brawl Stars API returned malformed data.") from exc
            if response.status_code == 404:
                raise PlayerNotFound("No Brawl Stars player was found for that tag.")
            if response.status_code in {401, 403}:
                raise ApiAuthenticationError(
                    "The Brawl Stars API token is invalid or is not authorized for this IP address."
                )
            if response.status_code == 429:
                last_error = ApiRateLimited("The Brawl Stars API rate limit was reached.")
            elif response.status_code >= 500:
                last_error = UpstreamUnavailable("The Brawl Stars API is temporarily unavailable.")
            else:
                raise UpstreamUnavailable(f"The Brawl Stars API returned HTTP {response.status_code}.")

            if attempt + 1 < self._config.retry_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 0.35 * (2**attempt)
                await asyncio.sleep(min(delay, 4.0))

        logger.warning("Brawl Stars request failed after retries: %s", path)
        if last_error:
            raise last_error
        raise UpstreamUnavailable("The Brawl Stars API request failed.")
