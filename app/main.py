from __future__ import annotations

import logging
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.clients.brawl_stars import BrawlStarsClient
from app.core.config import PROJECT_ROOT, get_settings
from app.core.errors import BrawlAdvisorError
from app.models.player import PlayerResources
from app.services.battlelog_service import BattleLogService
from app.services.club_service import ClubService
from app.services.events_service import EventsService
from app.services.player_service import PlayerService
from app.services.rankings_service import RankingsService
from app.services.resource_service import ResourceService
from app.services.upgrade_service import UpgradeService

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

client = (
    BrawlStarsClient(settings.brawl_stars, settings.api_token)
    if settings.api_token
    else None
)
player_service = PlayerService(
    client=client,
    demo_file=PROJECT_ROOT / "data" / "demo_player.json",
    cache_seconds=settings.cache.player_seconds,
)
club_service = ClubService(
    client=client,
    demo_file=PROJECT_ROOT / "data" / "demo_club.json",
    cache_seconds=settings.cache.player_seconds,
)
battlelog_service = BattleLogService(
    client=client,
    demo_path=PROJECT_ROOT / "data" / "demo_battlelog.json"
)
events_service = EventsService(
    client=client,
    demo_path=PROJECT_ROOT / "data" / "demo_events.json"
)
rankings_service = RankingsService(
    client=client,
    demo_path=PROJECT_ROOT / "data" / "demo_rankings.json"
)
resource_service = ResourceService(PROJECT_ROOT / "data" / "brawl_advisor.db")
with (PROJECT_ROOT / "data" / "brawler_guides.json").open("r", encoding="utf-8") as handle:
    brawler_guides = json.load(handle)
with (PROJECT_ROOT / "data" / "brawler_catalog.json").open("r", encoding="utf-8") as handle:
    brawler_catalog = json.load(handle)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s", settings.app.name)
    yield
    if client:
        await client.close()


app = FastAPI(
    title=settings.app.name,
    version="0.1.0",
    description="Account intelligence API for Brawl Stars progression planning.",
    lifespan=lifespan,
)
assets = PROJECT_ROOT / "app" / "ui" / "assets"
app.mount("/assets", StaticFiles(directory=assets), name="assets")


@app.exception_handler(BrawlAdvisorError)
async def handle_domain_error(_: Request, exc: BrawlAdvisorError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/brawlers", include_in_schema=False)
async def brawlers_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/resources", include_in_schema=False)
async def resources_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/club", include_in_schema=False)
async def club_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/club/{club_tag}", include_in_schema=False)
async def club_tag_page(club_tag: str) -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/battles", include_in_schema=False)
async def battles_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/events", include_in_schema=False)
async def events_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/leaderboards", include_in_schema=False)
async def leaderboards_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/calculator", include_in_schema=False)
async def calculator_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/brawlers/{brawler_id}", include_in_schema=False)
async def brawler_detail_page(brawler_id: int) -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "ui" / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app.name}


@app.get("/api/status")
async def status() -> dict[str, bool | str]:
    return {
        "app_name": settings.app.name,
        "live_api_configured": settings.api_token is not None,
        "demo_available": settings.app.demo_mode,
    }


def _player_analytics(player) -> dict:
    total_victories = player.total_victories or 1
    return {
        "brawlers_unlocked": len(player.brawlers),
        "average_power": player.average_power,
        "power_11_count": player.power_11_count,
        "rank_35_count": player.rank_35_count,
        "rank_30_plus_count": player.rank_30_plus_count,
        "rank_25_plus_count": player.rank_25_plus_count,
        "rank_20_plus_count": player.rank_20_plus_count,
        "rank_15_plus_count": player.rank_15_plus_count,
        "total_gadgets_count": player.total_gadgets_count,
        "total_star_powers_count": player.total_star_powers_count,
        "total_gears_count": player.total_gears_count,
        "total_showdown_victories": player.total_showdown_victories,
        "total_victories": player.total_victories,
        "victories_3v3_pct": round((player.victories_3v3 / total_victories) * 100),
        "victories_solo_pct": round((player.solo_victories / total_victories) * 100),
        "victories_duo_pct": round((player.duo_victories / total_victories) * 100),
        "next_trophy_milestone": player.next_trophy_milestone,
        "prestige_tier": player.prestige_tier,
        "brawler_prestige_level": player.brawler_prestige_level,
        "combat_archetype": player.combat_archetype,
        "completion_score": player.completion_score,
        "top_loadouts": player.top_loadouts,
        "highest_power_play_points": player.highest_power_play_points,
    }


@app.get("/api/player")
async def get_player(tag: str = Query(min_length=3, max_length=20)) -> dict:
    player, cache_hit = await player_service.get_player(tag)
    return {
        "player": player.model_dump(mode="json"),
        "analytics": _player_analytics(player),
        "freshness": {"fetched_at": player.fetched_at.isoformat(), "cache_hit": cache_hit},
    }


@app.get("/api/demo/player")
async def get_demo_player() -> dict:
    if not settings.app.demo_mode:
        return {"error": {"code": "demo_disabled", "message": "Demo mode is disabled."}}
    player = player_service.get_demo_player()
    return {
        "player": player.model_dump(mode="json"),
        "analytics": _player_analytics(player),
        "freshness": {"fetched_at": player.fetched_at.isoformat(), "cache_hit": False},
    }


@app.get("/api/club")
async def get_club(tag: str = Query(min_length=3, max_length=20)) -> dict:
    club, cache_hit = await club_service.get_club(tag)
    return {
        "club": club.model_dump(mode="json"),
        "analytics": {
            "member_count": club.member_count,
            "capacity_percent": club.capacity_percent,
            "average_trophies": club.average_trophies,
            "top_member_name": club.top_member.name if club.top_member else None,
            "top_member_trophies": club.top_member.trophies if club.top_member else 0,
            "vice_presidents_count": club.vice_presidents_count,
            "seniors_count": club.seniors_count,
            "regular_members_count": club.regular_members_count,
            "prestige_tier": club.prestige_tier,
        },
        "freshness": {"fetched_at": club.fetched_at.isoformat(), "cache_hit": cache_hit},
    }


@app.get("/api/demo/club")
async def get_demo_club() -> dict:
    if not settings.app.demo_mode:
        return {"error": {"code": "demo_disabled", "message": "Demo mode is disabled."}}
    club = club_service.get_demo_club()
    return {
        "club": club.model_dump(mode="json"),
        "analytics": {
            "member_count": club.member_count,
            "capacity_percent": club.capacity_percent,
            "average_trophies": club.average_trophies,
            "top_member_name": club.top_member.name if club.top_member else None,
            "top_member_trophies": club.top_member.trophies if club.top_member else 0,
            "vice_presidents_count": club.vice_presidents_count,
            "seniors_count": club.seniors_count,
            "regular_members_count": club.regular_members_count,
            "prestige_tier": club.prestige_tier,
        },
        "freshness": {"fetched_at": club.fetched_at.isoformat(), "cache_hit": False},
    }


@app.get("/api/lookup")
async def smart_lookup(tag: str = Query(min_length=3, max_length=20)) -> dict:
    """Smart lookup: tries player first; if not found, tries club."""
    # If in demo mode and tag matches demo club or player
    clean_tag = tag.strip().upper().replace(" ", "")
    if not clean_tag.startswith("#"):
        clean_tag = f"#{clean_tag}"

    # Try player
    try:
        player, cache_hit = await player_service.get_player(clean_tag)
        return {
            "type": "player",
            "player": player.model_dump(mode="json"),
            "analytics": _player_analytics(player),
            "freshness": {"fetched_at": player.fetched_at.isoformat(), "cache_hit": cache_hit},
        }
    except Exception:
        # Fallback to club
        try:
            club, cache_hit = await club_service.get_club(clean_tag)
            return {
                "type": "club",
                "club": club.model_dump(mode="json"),
                "analytics": {
                    "member_count": club.member_count,
                    "capacity_percent": club.capacity_percent,
                    "average_trophies": club.average_trophies,
                    "top_member_name": club.top_member.name if club.top_member else None,
                    "top_member_trophies": club.top_member.trophies if club.top_member else 0,
                    "vice_presidents_count": club.vice_presidents_count,
                    "seniors_count": club.seniors_count,
                    "regular_members_count": club.regular_members_count,
                    "prestige_tier": club.prestige_tier,
                },
                "freshness": {"fetched_at": club.fetched_at.isoformat(), "cache_hit": cache_hit},
            }
        except Exception:
            # If both fail, raise the player exception
            player, cache_hit = await player_service.get_player(clean_tag)
            return {}


@app.get("/api/resources/{player_tag}")
async def get_resources(player_tag: str) -> PlayerResources:
    return resource_service.get(player_tag)


@app.get("/api/guides/{brawler_id}")
async def get_brawler_guide(brawler_id: int) -> dict:
    return brawler_guides.get(str(brawler_id), {})


@app.get("/api/battlelog")
async def get_battlelog(tag: str = Query(min_length=3, max_length=20)) -> dict:
    entries, source = await battlelog_service.get_battlelog(tag)
    return {
        "items": [e.model_dump(mode="json") for e in entries],
        "source": source,
    }


@app.get("/api/demo/battlelog")
async def get_demo_battlelog() -> dict:
    entries = battlelog_service.load_demo()
    return {
        "items": [e.model_dump(mode="json") for e in entries],
        "source": "DEMO",
    }


@app.get("/api/events")
async def get_events() -> dict:
    events, source = await events_service.get_events()
    return {
        "items": [e.model_dump(mode="json") for e in events],
        "source": source,
    }


@app.get("/api/demo/events")
async def get_demo_events() -> dict:
    events = events_service.load_demo()
    return {
        "items": [e.model_dump(mode="json") for e in events],
        "source": "DEMO",
    }


@app.get("/api/rankings/players")
async def get_player_rankings(country: str = Query(default="global", min_length=2, max_length=10)) -> dict:
    players, source = await rankings_service.get_player_rankings(country)
    return {
        "items": [p.model_dump(mode="json") for p in players],
        "country": country.upper(),
        "source": source,
    }


@app.get("/api/rankings/clubs")
async def get_club_rankings(country: str = Query(default="global", min_length=2, max_length=10)) -> dict:
    clubs, source = await rankings_service.get_club_rankings(country)
    return {
        "items": [c.model_dump(mode="json") for c in clubs],
        "country": country.upper(),
        "source": source,
    }


@app.get("/api/demo/rankings")
async def get_demo_rankings() -> dict:
    players = rankings_service.load_demo_players()
    clubs = rankings_service.load_demo_clubs()
    return {
        "players": [p.model_dump(mode="json") for p in players],
        "clubs": [c.model_dump(mode="json") for c in clubs],
        "source": "DEMO",
    }


@app.post("/api/calculator/plan")
async def calculate_upgrade_plan(request: Request) -> dict:
    body = await request.json()
    brawlers = body.get("brawlers", [])
    player_tag = body.get("player_tag", "#2PP")
    wallet_data = resource_service.get(player_tag)
    wallet = {"coins": wallet_data.coins, "power_points": wallet_data.power_points}
    return UpgradeService.calculate_roster_plan(brawlers, wallet)


@app.post("/api/calculator/reset")
async def calculate_trophy_reset(request: Request) -> dict:
    body = await request.json()
    brawlers = body.get("brawlers", [])
    return UpgradeService.calculate_trophy_reset(brawlers)


@app.get("/api/meta/tierlist")
async def get_meta_tierlist() -> dict:
    # Curated Meta Tierlist across all brawlers based on competitive usage
    return {
        "S": ["Fang", "Piper", "Bibi", "Frank", "Cordelius", "Angelo", "Clancy", "Moe", "Kenji"],
        "A": ["Shelly", "Colt", "Brock", "Spike", "Gene", "Tara", "Jessie", "Leon", "Crow", "Melodie", "Lily", "Draco"],
        "B": ["Bull", "El Primo", "Poco", "Rosa", "Carl", "Bo", "Emz", "Stu", "Nani", "Edgar", "Gale", "Colette", "Belle", "Maisie", "Pearl", "Mortis", "Max", "Buzz", "Janet", "Otis", "Buster", "Surge", "Kit"],
        "C": ["Dynamike", "Tick", "8-Bit", "Rico", "Darryl", "Penny", "Jacky", "Gus", "Pam", "Bea", "Griff", "Grom", "Bonnie", "Ash", "Lola", "Sam", "Mandy", "Hank", "Larry & Lawrie", "Mr. P", "Sprout", "Byron", "Squeak", "Lou", "Ruffs", "Eve", "Gray", "R-T", "Willow", "Doug", "Chuck", "Charlie", "Mico", "Meg", "Chester", "Shade"],
        "D": ["Juju"]
    }


@app.get("/api/brawlers/catalog")
async def get_brawler_catalog() -> dict:
    return {"count": len(brawler_catalog), "list": brawler_catalog}


@app.put("/api/resources/{player_tag}")
async def save_resources(player_tag: str, resources: PlayerResources) -> PlayerResources:
    resources.player_tag = player_tag
    return resource_service.save(resources)


