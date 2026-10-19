from __future__ import annotations

import logging
import json
from collections import defaultdict
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from starlette.concurrency import run_in_threadpool

from app.core.config import PROJECT_ROOT
from app.ml.database import MetaDatabase
from app.ml.meta_engine import StatisticalMetaEngine
from app.ml.model import BrawlerOutcomePredictor
from app.services.player_service import PlayerService

logger = logging.getLogger("brawlbuddy.router.ml_meta")

router = APIRouter(prefix="/api", tags=["ML & Meta"])
bulk_dataset_directory = PROJECT_ROOT / 'data' / 'bulk-sample-100k'


@router.get('/ml/bulk-dataset/status')
def get_bulk_dataset_status() -> dict[str, Any]:
    """Read the external worker's published checkpoint without touching its database."""
    try:
        progress = json.loads((bulk_dataset_directory / 'progress.json').read_text(encoding='utf-8'))
        timestamp = datetime.fromisoformat(progress['updated_at'])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        age = max(0, (datetime.now(UTC) - timestamp).total_seconds())
        return {**progress, 'available': True, 'is_stale': age > 120,
                'report_age_seconds': round(age), 'publish_interval_seconds': 30}
    except FileNotFoundError:
        return {'available': False, 'state': 'not_started', 'message': 'The bulk CSV worker has not started.'}
    except (OSError, ValueError, KeyError, TypeError):
        return {'available': False, 'state': 'unavailable', 'message': 'The latest collection report could not be read. Retrying…'}

# Initialize ML services
db_path = PROJECT_ROOT / "data" / "brawl_meta.db"
meta_db = MetaDatabase(db_path)
meta_engine = StatisticalMetaEngine(meta_db)
predictor = BrawlerOutcomePredictor(meta_db)
predictor.load_model()


class DraftRequest(BaseModel):
    @model_validator(mode='after')
    def validate_draft(self):
        mode = getattr(self, 'mode', 'brawlBall')
        if mode not in {'brawlBall', 'gemGrab', 'heist', 'hotZone', 'bounty', 'knockout', 'wipeout'}:
            raise ValueError('Draft predictions support competitive team modes only')
        team = getattr(self, 'teamBrawlers', getattr(self, 'draftAllies', []))
        enemies = getattr(self, 'enemyBrawlers', getattr(self, 'draftEnemies', []))
        if len(team) > 3 or len(enemies) > 3 or len(set(team + enemies)) != len(team + enemies):
            raise ValueError('Use at most three unique brawlers per side, with no duplicate picks')
        if any(b < 16000000 or b >= 17000000 for b in team + enemies):
            raise ValueError('Invalid brawler identifier')
        if getattr(self, 'ownedBrawlersOnly', False) and not getattr(self, 'playerTag', None):
            raise ValueError('Connect a player before filtering by owned brawlers')
        return self


class PredictMatchRequest(DraftRequest):
    mode: str = "brawlBall"
    map: str = "Center Stage"
    teamBrawlers: list[int] = Field(default_factory=list)
    enemyBrawlers: list[int] = Field(default_factory=list)
    powerDiff: float = Field(default=0.0, ge=-10, le=10, allow_inf_nan=False)


class RecommendRequest(DraftRequest):
    mode: str = "brawlBall"
    map: Optional[str] = None
    teamBrawlers: list[int] = Field(default_factory=list)
    enemyBrawlers: list[int] = Field(default_factory=list)
    ownedBrawlersOnly: bool = False
    playerTag: Optional[str] = None
    top_k: int = Field(default=15, ge=1, le=50)


@router.get("/meta/filters")
def get_meta_filters() -> dict[str, Any]:
    """Get active game modes, maps, and match types stored in the database."""
    filters = meta_engine.get_available_filters()
    return {
        "status": "success",
        "data": filters,
    }


@router.get("/meta/brawlers")
def get_brawler_meta_stats(
    mode: Optional[str] = Query(None, description="Game mode (e.g. brawlBall, gemGrab, knockout)"),
    map: Optional[str] = Query(None, description="Map name"),
    match_type: Optional[str] = Query(None, description="Match type: ranked, soloRanked, etc."),
    min_picks: int = Query(1, ge=1, description="Minimum picks threshold"),
) -> dict[str, Any]:
    """Get Bayesian-smoothed win rates, pick rates, confidence, and meta tiers."""
    stats = meta_engine.compute_brawler_stats(
        mode=mode,
        map_name=map,
        match_type=match_type,
        min_picks=min_picks,
    )
    return {
        "status": "success",
        "filters": {
            "mode": mode or "all",
            "map": map or "all",
            "match_type": match_type or "all",
        },
        "total_brawlers": len(stats),
        "brawlers": stats,
    }


@router.get("/meta/teams")
def get_top_teams(
    mode: str = Query("brawlBall", description="Game mode"),
    map: Optional[str] = Query(None, description="Map name"),
    min_matches: int = Query(2, ge=1, description="Minimum team matches"),
) -> dict[str, Any]:
    """Find top performing 3-brawler team combinations for a map and mode."""
    filters = ["m.mode = ?"]
    params: list[Any] = [mode]
    if map:
        filters.append("m.map = ?")
        params.append(map)

    where_clause = f"WHERE {' AND '.join(filters)}"

    query = f"""
        SELECT
            m.match_fingerprint,
            p.team_index,
            p.brawler_id,
            p.brawler_name,
            p.is_winner
        FROM match_participants p
        JOIN matches m ON p.match_fingerprint = m.match_fingerprint
        {where_clause}
        AND m.ingestion_version=2 AND p.is_winner IS NOT NULL AND p.team_index IN (0, 1)
    """

    with closing(meta_db.connect()) as conn:
        rows = conn.execute(query, params).fetchall()

    # Group by (match_fingerprint, team_index)
    teams_dict: dict[tuple[str, int], dict[str, Any]] = defaultdict(lambda: {"brawlers": [], "names": [], "is_winner": 0})
    for r in rows:
        key = (r["match_fingerprint"], r["team_index"])
        teams_dict[key]["brawlers"].append(r["brawler_id"])
        teams_dict[key]["names"].append(r["brawler_name"])
        if r["is_winner"] == 1:
            teams_dict[key]["is_winner"] = 1

    # Aggregate by sorted brawler trio
    trio_stats: dict[tuple[int, ...], dict[str, Any]] = defaultdict(lambda: {"matches": 0, "wins": 0, "names": []})
    for t in teams_dict.values():
        if len(t["brawlers"]) == 3:
            # Sort IDs to normalize team composition
            paired = sorted(zip(t["brawlers"], t["names"]), key=lambda x: x[0])
            sorted_ids = tuple(p[0] for p in paired)
            sorted_names = [p[1] for p in paired]
            
            trio_stats[sorted_ids]["matches"] += 1
            if t["is_winner"] == 1:
                trio_stats[sorted_ids]["wins"] += 1
            trio_stats[sorted_ids]["names"] = sorted_names

    result_trios = []
    for ids, data in trio_stats.items():
        if data["matches"] >= min_matches:
            raw_wr = data["wins"] / data["matches"]
            smoothed_wr = (data["wins"] + 5 * 0.5) / (data["matches"] + 5)
            result_trios.append({
                "brawler_ids": list(ids),
                "brawler_names": data["names"],
                "matches": data["matches"],
                "wins": data["wins"],
                "win_rate": round(raw_wr, 4),
                "smoothed_win_rate": round(smoothed_wr, 4),
                "confidence": "HIGH" if data["matches"] >= 10 else "MEDIUM",
            })

    result_trios.sort(key=lambda t: (t["smoothed_win_rate"], t["matches"]), reverse=True)

    return {
        "status": "success",
        "mode": mode,
        "map": map or "all",
        "teams": result_trios[:20],
    }


@router.post("/ml/predict-match")
async def predict_match(req: PredictMatchRequest) -> dict[str, Any]:
    """Predict victory probability for a specific team vs enemy matchup."""
    result = await run_in_threadpool(predictor.predict_match,
        mode=req.mode,
        map_name=req.map,
        team_brawlers=req.teamBrawlers,
        enemy_brawlers=req.enemyBrawlers,
        power_diff=req.powerDiff,
    )
    return {
        "status": "success",
        "data": result,
    }


@router.post("/ml/recommend")
async def recommend_brawlers(req: RecommendRequest, request: Request) -> dict[str, Any]:
    """AI Draft Assistant recommending best remaining brawlers considering draft and owned collection."""
    owned_ids: Optional[list[int]] = None

    # Handle personalized owned brawlers
    if req.ownedBrawlersOnly and req.playerTag:
        try:
            player_service: PlayerService = request.app.state.player_service
            player_data, _ = await player_service.get_player(req.playerTag)
            brawlers = player_data.brawlers or []
            owned_ids = [b.id for b in brawlers]
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not load the connected player collection") from exc

    recs = await run_in_threadpool(predictor.recommend_brawlers,
        mode=req.mode,
        map_name=req.map,
        team_brawlers=req.teamBrawlers,
        enemy_brawlers=req.enemyBrawlers,
        owned_brawlers=owned_ids,
        top_k=req.top_k,
    )

    return {
        "status": "success",
        "mode": req.mode,
        "map": req.map or "all",
        "teamBrawlers": req.teamBrawlers,
        "enemyBrawlers": req.enemyBrawlers,
        "ownedFiltered": bool(owned_ids is not None),
        "recommendations": recs,
    }


class DraftStepRequest(DraftRequest):
    mode: str = Field(default="brawlBall", description="Game mode")
    map: Optional[str] = Field(default=None, description="Map name")
    draftAllies: list[int] = Field(default_factory=list, description="Currently locked ally brawlers")
    draftEnemies: list[int] = Field(default_factory=list, description="Currently locked enemy brawlers")
    activeSlot: str = Field(default="ally_1", pattern=r"^(ally_[123]|enemy_[123]|complete)$", description="Draft slot to evaluate (ally_1, ally_2, enemy_1, etc.)")
    ownedBrawlersOnly: bool = Field(default=False, description="Filter candidates to owned brawlers only")
    playerTag: Optional[str] = Field(default=None, description="Player tag for collection filtering")
    top_k: int = Field(default=12, ge=1, le=50, description="Max recommendations to return")


@router.post("/ml/draft/step")
async def draft_step(req: DraftStepRequest, request: Request) -> dict[str, Any]:
    """Provide step-by-step drafting suggestions with projected win % deltas and synergy."""
    owned_ids: Optional[list[int]] = None
    if req.ownedBrawlersOnly and req.playerTag:
        try:
            player_service = request.app.state.player_service
            player_data, _ = await player_service.get_player(req.playerTag)
            if player_data and hasattr(player_data, "brawlers"):
                owned_ids = [b.id for b in player_data.brawlers]
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not load the connected player collection") from exc

    step_eval = await run_in_threadpool(predictor.evaluate_draft_step,
        mode=req.mode,
        map_name=req.map,
        draft_allies=req.draftAllies,
        draft_enemies=req.draftEnemies,
        active_slot=req.activeSlot,
        owned_brawlers=owned_ids if req.activeSlot.startswith("ally") else None,
        top_k=req.top_k,
    )
    return {
        "status": "success",
        "data": step_eval,
    }


@router.get("/ml/transparency/summary")
def get_transparency_summary() -> dict[str, Any]:
    """Full transparency summary: dataset audit, multi-framework benchmark, and feature importances."""
    dataset_summary = meta_db.get_dataset_summary()
    return {
        "status": "success",
        "model_version": predictor.version,
        "active_model_name": predictor.metrics.model_name if predictor.metrics else "Not Loaded",
        "dataset": dataset_summary,
        "benchmark_leaderboard": predictor.benchmark_results,
        "metrics": predictor.metrics.to_dict() if predictor.metrics else None,
        "feature_importances": predictor.feature_importances,
        "validation": predictor.validation,
    }


@router.get("/ml/model-status")
def get_model_status() -> dict[str, Any]:
    """Get metadata, freshness, metrics, and dataset coverage for the current ML model."""
    p_count = meta_db.get_player_count()
    m_count = meta_db.get_match_count()
    
    with closing(meta_db.connect()) as conn:
        latest_match = conn.execute("SELECT MAX(battle_time) as latest FROM matches").fetchone()["latest"]
        polled_count = conn.execute("SELECT COUNT(*) as c FROM players WHERE last_polled_at IS NOT NULL").fetchone()["c"]

    return {
        "status": "operational",
        "model_version": predictor.version,
        "model_loaded": predictor.model is not None,
        "metrics": predictor.metrics.to_dict() if predictor.metrics else None,
        "baseline_metrics": predictor.baseline_metrics.to_dict() if predictor.baseline_metrics else None,
        "benchmark_leaderboard": predictor.benchmark_results,
        "feature_importances": predictor.feature_importances,
        "validation": predictor.validation,
        "dataset": {
            "total_discovered_players": p_count,
            "polled_players": polled_count,
            "total_unique_matches": m_count,
            "verified_matches": meta_db.get_dataset_summary()["verified_matches"],
            "latest_match_time": latest_match,
        },
    }



# --- Engine Operations & Telemetry ---

import asyncio
from app.clients.brawl_stars import BrawlStarsClient
from app.core.config import get_settings
from app.ml.collector import BattleLogCollector, CollectionStats

operation_task: asyncio.Task | None = None

operation_state: dict[str, Any] = {
    "running": False,
    "task": "Idle",
    "message": "Engine is ready for operations.",
    "last_result": None,
    "progress": {},
}


class DiscoverRequest(BaseModel):
    target_players: int = Field(default=5000, ge=10, le=100000)


class ScalePlayersRequest(BaseModel):
    target_players: int = Field(default=100000, ge=100, le=100000)


class CollectRequest(BaseModel):
    max_players: int = Field(default=50, ge=1, le=1000)
    rps: float = Field(default=6.0, ge=1.0, le=10.0)


@router.get("/ml/operations/incremental-status")
def get_incremental_status() -> dict[str, Any]:
    """Get real-time tracking of player pool progress toward 100k and unpolled queue."""
    return meta_db.get_incremental_status()


@router.get("/ml/operations/telemetry")
def get_operations_telemetry() -> dict[str, Any]:
    """Provide comprehensive engine telemetry for the operational control center."""
    p_count = meta_db.get_player_count()
    m_count = meta_db.get_match_count()
    incremental_st = meta_db.get_incremental_status()
    
    with closing(meta_db.connect()) as conn:
        polled_count = conn.execute("SELECT COUNT(*) as c FROM players WHERE last_polled_at IS NOT NULL").fetchone()["c"]
        part_count = conn.execute("SELECT COUNT(*) as c FROM match_participants").fetchone()["c"]
        latest_match = conn.execute("SELECT MAX(battle_time) as latest FROM matches").fetchone()["latest"]
        
        mode_rows = conn.execute("SELECT mode, COUNT(*) as c FROM matches GROUP BY mode ORDER BY c DESC").fetchall()
        modes_breakdown = [{"mode": r["mode"], "count": r["c"]} for r in mode_rows]
        
        map_rows = conn.execute("SELECT map, mode, COUNT(*) as c FROM matches GROUP BY map, mode ORDER BY c DESC LIMIT 8").fetchall()
        top_maps = [{"map": r["map"], "mode": r["mode"], "count": r["c"]} for r in map_rows]

    return {
        "status": "success",
        "telemetry": {
            "total_players": p_count,
            "polled_players": polled_count,
            "unpolled_players": incremental_st.get("unpolled_players", 0),
            "target_players": 100000,
            "percent_of_target": incremental_st.get("percent_of_target", 0),
            "polled_percent": round((polled_count / p_count * 100) if p_count else 0, 1),
            "total_matches": m_count,
            "total_participants": part_count,
            "latest_match_time": latest_match,
            "modes_breakdown": modes_breakdown,
            "top_maps": top_maps,
        },
        "model": {
            "version": predictor.version,
            "metrics": predictor.metrics.to_dict() if predictor.metrics else None,
            "baseline": predictor.baseline_metrics.to_dict() if predictor.baseline_metrics else None,
            "benchmark_leaderboard": predictor.benchmark_results,
        },
        "operation_state": operation_state,
    }


@router.get("/ml/operations/status")
def get_operations_status() -> dict[str, Any]:
    """Get real-time status of ongoing background operations."""
    return operation_state


async def _run_discovery_bg(target_players: int) -> None:
    global operation_state
    settings = get_settings()
    if not settings.api_token:
        operation_state["running"] = False
        operation_state["message"] = "Error: Brawl Stars API token missing in .env"
        return

    client = BrawlStarsClient(settings.brawl_stars, settings.api_token)
    collector = BattleLogCollector(client, meta_db, requests_per_second=6.0)
    try:
        def on_prog(step: str, count: int) -> None:
            operation_state["message"] = f"Discovering: {step} (Total in DB: {count:,} / {target_players:,})"
            operation_state["progress"] = {"step": step, "count": count, "target": target_players}

        total = await collector.discover_top_players(
            target_player_count=target_players,
            on_progress=on_prog,
        )
        operation_state["last_result"] = {"action": "discover", "total_players": total}
        operation_state["message"] = f"Player discovery complete! Total database pool: {total:,} player tags."
    except Exception as exc:
        logger.error("Discovery error: %s", exc)
        operation_state["message"] = f"Discovery stopped: {exc}"
        operation_state["last_result"] = {"status": "error"}
    finally:
        await client.close()
        operation_state["running"] = False


@router.post("/ml/operations/discover")
async def trigger_player_discovery(req: DiscoverRequest) -> dict[str, Any]:
    """Trigger background competitive player discovery."""
    global operation_state
    if not get_settings().api_token:
        raise HTTPException(status_code=503, detail="Configure the game token before collection")
    if operation_state["running"]:
        raise HTTPException(status_code=409, detail=f"An operation is already in progress ({operation_state['task']}).")

    operation_state["running"] = True
    operation_state["task"] = "Player Discovery"
    operation_state["message"] = f"Starting player discovery (target: {req.target_players:,})..."
    operation_state["progress"] = {}
    operation_state["last_result"] = None

    start_operation(_run_discovery_bg(req.target_players))
    return {"status": "started", "task": "Player Discovery", "target": req.target_players}


@router.post("/ml/operations/scale-players")
async def trigger_scale_players(req: ScalePlayersRequest) -> dict[str, Any]:
    """Trigger massive player discovery scaling up to 100,000 competitive players."""
    global operation_state
    if not get_settings().api_token:
        raise HTTPException(status_code=503, detail="Configure the game token before collection")
    if operation_state["running"]:
        raise HTTPException(status_code=409, detail=f"An operation is already in progress ({operation_state['task']}).")

    operation_state["running"] = True
    operation_state["task"] = "Scale to 100k Players"
    operation_state["message"] = f"Discovering player pool toward {req.target_players:,} tags across regional rankings, clubs and participants..."
    operation_state["progress"] = {}
    operation_state["last_result"] = None

    start_operation(_run_discovery_bg(req.target_players))
    return {"status": "started", "task": "Scale to 100k Players", "target": req.target_players}


async def _run_collection_bg(max_players: int, rps: float) -> None:
    global operation_state
    settings = get_settings()
    if not settings.api_token:
        operation_state["running"] = False
        operation_state["message"] = "Error: Brawl Stars API token missing in .env"
        return

    client = BrawlStarsClient(settings.brawl_stars, settings.api_token)
    collector = BattleLogCollector(client, meta_db, requests_per_second=rps)
    try:
        def on_prog(stats: CollectionStats) -> None:
            operation_state["message"] = (
                f"Polled {stats.players_polled}/{max_players} players • "
                f"{stats.new_matches_saved} new matches saved • {stats.duplicate_matches_skipped} duplicates skipped"
            )
            operation_state["progress"] = stats.to_dict()

        stats = await collector.collect_battlelogs(
            max_players=max_players,
            cascade_discovery=True,
            on_progress=on_prog,
        )
        operation_state["last_result"] = {
            "action": "collect",
            "stats": stats.to_dict(),
        }
        operation_state["message"] = (
            f"Collection finished! Polled {stats.players_polled} players, "
            f"saved {stats.new_matches_saved} unique matches ({stats.duplicate_matches_skipped} duplicates skipped). "
            f"Total players in DB: {stats.total_players:,}."
        )
    except Exception as exc:
        logger.error("Collection error: %s", exc)
        operation_state["message"] = f"Collection stopped: {exc}"
        operation_state["last_result"] = {"status": "error"}
    finally:
        await client.close()
        operation_state["running"] = False


@router.post("/ml/operations/collect")
async def trigger_battle_collection(req: CollectRequest) -> dict[str, Any]:
    """Trigger background battle log collection batch."""
    global operation_state
    if not get_settings().api_token:
        raise HTTPException(status_code=503, detail="Configure the game token before collection")
    if operation_state["running"]:
        raise HTTPException(status_code=409, detail=f"An operation is already in progress ({operation_state['task']}).")

    operation_state["running"] = True
    operation_state["task"] = "Battle Collection"
    operation_state["message"] = f"Initiating battle log collection for {req.max_players} players (RPS: {req.rps})..."
    operation_state["progress"] = {}
    operation_state["last_result"] = None

    start_operation(_run_collection_bg(req.max_players, req.rps))
    return {"status": "started", "task": "Battle Collection", "max_players": req.max_players}


def start_operation(coro) -> None:
    global operation_task
    operation_task = asyncio.create_task(coro)


async def shutdown_operations() -> None:
    if operation_task and not operation_task.done():
        if operation_state['task'] == 'Model Training':
            # A worker thread cannot be safely interrupted while writing a model.
            await operation_task
        else:
            operation_task.cancel()
            await asyncio.gather(operation_task, return_exceptions=True)
    operation_state['running'] = False


async def _run_training_bg() -> None:
    global predictor
    candidate = BrawlerOutcomePredictor(meta_db, model_dir=predictor.model_dir)
    try:
        result = await run_in_threadpool(candidate.train_and_evaluate)
        if result['status'] == 'success':
            # Publish a complete predictor; requests keep using the previous one during training.
            predictor = candidate
        operation_state['last_result'] = result
        operation_state['message'] = ('Training complete: ' + result['best_model'] if result['status'] == 'success'
                                      else result.get('message', result['status']))
    except Exception:
        logger.exception('Model training failed')
        operation_state['last_result'] = {'status': 'error'}
        operation_state['message'] = 'Training failed; the previous model remains active.'
    finally:
        operation_state['running'] = False


@router.post('/ml/operations/retrain', status_code=202)
async def trigger_model_retrain() -> dict[str, Any]:
    if operation_state['running']:
        raise HTTPException(status_code=409, detail='Another engine operation is already running')
    operation_state.update(running=True, task='Model Training', message='Training with temporal validation…',
                           last_result=None, progress={})
    start_operation(_run_training_bg())
    return {'status': 'started', 'task': 'Model Training'}


@router.post('/ml/operations/cancel')
async def cancel_collection() -> dict[str, Any]:
    if operation_state['task'] == 'Model Training' and operation_state['running']:
        raise HTTPException(status_code=409, detail='Training finishes its current run before shutdown')
    if operation_task and not operation_task.done():
        operation_task.cancel()
        await asyncio.gather(operation_task, return_exceptions=True)
    operation_state.update(running=False, message='Collection stopped. Saved data is preserved.')
    return {'status': 'cancelled'}
