from __future__ import annotations


class BrawlAdvisorError(Exception):
    """Base class for errors safe to translate into API responses."""

    status_code = 500
    code = "internal_error"


class InvalidPlayerTag(BrawlAdvisorError):
    status_code = 422
    code = "invalid_player_tag"


class MissingApiToken(BrawlAdvisorError):
    status_code = 503
    code = "missing_api_token"


class PlayerNotFound(BrawlAdvisorError):
    status_code = 404
    code = "player_not_found"


class ApiAuthenticationError(BrawlAdvisorError):
    status_code = 503
    code = "api_authentication_error"


class ApiRateLimited(BrawlAdvisorError):
    status_code = 503
    code = "api_rate_limited"


class UpstreamUnavailable(BrawlAdvisorError):
    status_code = 503
    code = "upstream_unavailable"

