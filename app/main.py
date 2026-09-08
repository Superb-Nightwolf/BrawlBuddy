from __future__ import annotations

import logging
import json
import mimetypes
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/png', '.png')

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
from app.services.matchup_service import MatchupService
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
    overrides_file=PROJECT_ROOT / "data" / "player_overrides.json",
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
matchup_service = MatchupService(
    data_path=PROJECT_ROOT / "data" / "brawler_matchups.json",
    catalog_path=PROJECT_ROOT / "data" / "brawler_catalog.json",
    battlelog_service=battlelog_service,
)
resource_service = ResourceService(PROJECT_ROOT / "data" / "brawl_advisor.db")
with (PROJECT_ROOT / "data" / "brawler_guides.json").open("r", encoding="utf-8") as handle:
    brawler_guides = json.load(handle)
with (PROJECT_ROOT / "data" / "brawler_catalog.json").open("r", encoding="utf-8") as handle:
    brawler_catalog = json.load(handle)
equipment_db = {}
equipment_path = PROJECT_ROOT / "data" / "equipment_ids.json"
if equipment_path.exists():
    with equipment_path.open("r", encoding="utf-8") as handle:
        equipment_db = json.load(handle)
buffies_db = {}
buffies_path = PROJECT_ROOT / "data" / "buffies_db.json"
if buffies_path.exists():
    with buffies_path.open("r", encoding="utf-8") as handle:
        buffies_db = json.load(handle)
visual_asset_manifest = {}
visual_asset_manifest_path = PROJECT_ROOT / "data" / "visual_asset_manifest.json"
if visual_asset_manifest_path.exists():
    with visual_asset_manifest_path.open("r", encoding="utf-8") as handle:
        visual_asset_manifest = json.load(handle)
data_sources = {}
data_sources_path = PROJECT_ROOT / "data" / "game_data_sources.json"
if data_sources_path.exists():
    with data_sources_path.open("r", encoding="utf-8") as handle:
        data_sources = json.load(handle)
prestige_assets = {}
prestige_assets_path = PROJECT_ROOT / "data" / "prestige_assets.json"
if prestige_assets_path.exists():
    with prestige_assets_path.open("r", encoding="utf-8") as handle:
        prestige_assets = json.load(handle)


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


def _content_last_updated() -> str:
    """Return the newest published data/UI timestamp without a manual date edit."""
    published_files = list((PROJECT_ROOT / "data").glob("*.json"))
    published_files.extend(
        path for path in assets.rglob("*") if path.is_file()
    )
    published_files.append(PROJECT_ROOT / "app" / "ui" / "index.html")
    newest = max(path.stat().st_mtime for path in published_files if path.exists())
    return datetime.fromtimestamp(newest, tz=timezone.utc).replace(microsecond=0).isoformat()


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
        "content_last_updated": _content_last_updated(),
    }


def _player_analytics(player) -> dict:
    total_victories = player.total_victories or 1
    return {
        "brawlers_unlocked": len(player.brawlers),
        "average_power": player.average_power,
        "power_11_count": player.power_11_count,
        "total_prestige_level": player.brawler_prestige_level,
        "total_prestige_source": player.total_prestige_source,
        "prestige_brawler_count": sum(b.prestige_level >= 1 for b in player.brawlers),
        "prestige_1_count": sum(b.prestige_level == 1 for b in player.brawlers),
        "prestige_2_count": sum(b.prestige_level == 2 for b in player.brawlers),
        "prestige_3_plus_count": sum(b.prestige_level >= 3 for b in player.brawlers),
        "wood_count": sum(b.prestige_level == 0 and b.trophies < 250 for b in player.brawlers),
        "bronze_count": sum(b.prestige_level == 0 and 250 <= b.trophies < 500 for b in player.brawlers),
        "silver_count": sum(b.prestige_level == 0 and 500 <= b.trophies < 750 for b in player.brawlers),
        "gold_count": sum(b.prestige_level == 0 and 750 <= b.trophies for b in player.brawlers),
        "total_gadgets_count": player.total_gadgets_count,
        "total_star_powers_count": player.total_star_powers_count,
        "total_gears_count": player.total_gears_count,
        "total_hypercharges_count": player.total_hypercharges_count,
        "active_hypercharges_count": player.active_hypercharges_count,
        "stored_hypercharges_count": player.stored_hypercharges_count,
        "total_buffied_brawlers_count": player.total_buffied_brawlers_count,
        "gadget_buffies_count": player.gadget_buffies_count,
        "star_power_buffies_count": player.star_power_buffies_count,
        "hypercharge_buffies_count": player.hypercharge_buffies_count,
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
    guide = brawler_guides.get(str(brawler_id))
    if not guide:
        return {}

    guide_copy = dict(guide)
    useful_maps = [dict(m) for m in guide_copy.get("useful_maps", [])]

    try:
        events, _ = await events_service.get_events()
        brawler_name = guide.get("name", "").strip().upper()
        active_by_map = {e.event.map.strip().lower(): e for e in events}

        meta_active_maps = []
        for e in events:
            top_picks = [p.strip().upper() for p in e.top_meta_picks]
            map_name_norm = e.event.map.strip().lower()
            if brawler_name in top_picks and map_name_norm not in [m["name"].strip().lower() for m in useful_maps]:
                meta_active_maps.append({
                    "id": e.event.id,
                    "name": e.event.map,
                    "mode": e.event.mode,
                    "image_url": e.event.image_url or f"https://cdn.brawlify.com/maps/regular/{e.event.id}.png",
                    "is_active": True,
                    "slot_id": e.slot_id,
                    "time_remaining_label": e.time_remaining_label,
                    "time_remaining_seconds": e.time_remaining_seconds,
                    "modifiers": e.modifiers,
                })

        for m in useful_maps:
            active_event = active_by_map.get(m["name"].strip().lower())
            if active_event:
                m["is_active"] = True
                m["slot_id"] = active_event.slot_id
                m["time_remaining_label"] = active_event.time_remaining_label
                m["time_remaining_seconds"] = active_event.time_remaining_seconds
                m["modifiers"] = active_event.modifiers
            else:
                m["is_active"] = False

        combined_maps = meta_active_maps + useful_maps
        seen = set()
        deduped = []
        for item in combined_maps:
            norm = item["name"].strip().lower()
            if norm not in seen:
                seen.add(norm)
                deduped.append(item)

        # Dynamic priority: active maps in live rotation first, followed by top all-time picks
        deduped.sort(key=lambda x: (0 if x.get("is_active") else 1))
        guide_copy["useful_maps"] = deduped[:4]
    except Exception as exc:
        logger.warning(f"Could not dynamically enrich useful_maps for brawler {brawler_id}: {exc}")

    guide_copy["matchups"] = matchup_service.get_matchups(brawler_id)
    return guide_copy


@app.get("/api/brawlers/{brawler_id}/matchups")
async def get_brawler_matchups(brawler_id: int) -> dict:
    return matchup_service.get_matchups(brawler_id)


@app.post("/api/brawlers/{brawler_id}/matchups/refresh")
async def refresh_brawler_matchups(brawler_id: int) -> dict:
    return matchup_service.refresh_matchups(brawler_id)


@app.get("/api/equipment")
async def get_equipment_catalog() -> dict:
    return equipment_db


@app.get("/api/buffies")
async def get_buffies_catalog() -> dict:
    return buffies_db


@app.get("/api/visual-assets")
async def get_visual_asset_manifest() -> dict:
    return visual_asset_manifest


@app.get("/api/prestige/assets")
async def get_prestige_assets() -> dict:
    return prestige_assets


@app.get("/api/data-sources")
async def get_data_sources() -> dict:
    return data_sources


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
    player_tag = body.get("player_tag", "#9Q889JCR0")
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
