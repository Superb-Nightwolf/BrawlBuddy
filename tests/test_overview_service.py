from types import SimpleNamespace

from app.services.battlelog_service import BattleLogService
from app.services.overview_service import OverviewService, summarize_battles
from app.services.player_service import parse_player
from app.services.resource_service import ResourceService
from app.services.events_service import EventsService


def service():
    return OverviewService([
        {"id": 1, "class": "Tank", "rarity": "Rare"},
        {"id": 2, "class": "Support", "rarity": "Epic"},
        {"id": 3, "class": "Support", "rarity": "Rare"},
    ], SimpleNamespace(guides={}, _buffie_categories=lambda _: [],
                       config={"powerUpgrades": {str(i): {"coins": 10, "powerPoints": 5}
                                                 for i in range(1, 11)}}))


def test_new_profile_fields_and_missing_fields_remain_distinct():
    player = parse_player({"tag": "#2PP", "name": "Player", "fame": 0,
                           "rankedElo": 5633, "rankedRankName": "MYTHIC III",
                           "highestSeasonRankedElo": 5928, "highestAllTimeRankedElo": 6200,
                           "brawlers": [{"id": 1, "name": "SHELLY", "power": 11,
                                         "currentWinStreak": 0, "maxWinStreak": 6,
                                         "skin": {"id": 29000000, "name": "Example skin"}}]})
    assert player.fame == 0
    assert player.ranked_elo == 5633
    assert player.highest_all_time_ranked_elo == 6200
    assert player.brawlers[0].current_win_streak == 0
    assert player.brawlers[0].skin.name == "Example skin"
    summary = service().summarize(player)
    assert summary["fame"]["value"] == 0
    assert summary["equipment"][0]["unknown"] == 1
    assert summary["equipment"][0]["coverage_pct"] is None
    assert summary["victories"]["total"] is None
    assert summary["records"]["championship"] is None
    assert summary["builds"]["known"] == 0


def test_denominators_unknown_catalog_ids_and_unique_equipment():
    player = parse_player({"tag": "#2PP", "name": "Player", "trophies": 500,
                           "3vs3Victories": 0, "soloVictories": 0, "duoVictories": 0,
                           "brawlers": [
                               {"id": 1, "name": "SHELLY", "power": 11, "trophies": 500,
                                "gadgets": [{"id": 101, "name": "A"}, {"id": 101, "name": "A"}]},
                               {"id": 2, "name": "COLT", "power": 9, "trophies": 0, "gadgets": []},
                               {"id": 99, "name": "NEW", "power": 1, "trophies": 0},
                           ]})
    catalog = [{"id": 1, "gadgets": [{"id": 101}, {"id": 102}]},
               {"id": 2, "gadgets": [{"id": 103}]}, {"id": 3}]
    summary = service().summarize(player, catalog)
    assert summary["collection"]["unlocked"] == 2
    assert summary["collection"]["locked"] == 1
    assert summary["collection"]["unknown_catalog_ids"] == 1
    assert summary["equipment"][0]["owned"] == 1
    assert summary["equipment"][0]["covered"] == 1
    assert summary["equipment"][0]["known"] == 2
    assert summary["equipment"][0]["coverage_pct"] == 50
    assert summary["equipment"][0]["completion_pct"] == 33.3
    assert summary["victories"]["total"] == 0
    assert summary["power"]["remaining_levels"] == 12
    assert summary["builds"]["power_cost"] == {"coins": 120, "powerPoints": 60}


def test_empty_account_has_no_fictional_percentages_or_streaks():
    summary = service().summarize(parse_player({"tag": "#2PP", "name": "Empty"}))
    assert summary["power"]["average"] is None
    assert summary["power"]["maxed_pct"] is None
    assert summary["streaks"]["record"] is None
    assert summary["trophies"]["top5_pct"] is None
    assert summary["builds"]["mean_progress"] is None


def test_recent_results_exclude_placements_draws_and_other_accounts():
    parser = BattleLogService(None)
    def match(result=None, tag="#2PP", rank=None, change=None):
        return parser.parse_entry({"battleTime": "20261007T010000.000Z",
                                   "event": {"id": 1, "mode": "soloShowdown", "map": "Example"},
                                   "battle": {"result": result, "rank": rank, "trophyChange": change,
                                              "players": [{"tag": tag, "name": "Player",
                                                           "brawler": {"id": 1, "name": "SHELLY", "power": 11}}]}})
    result = summarize_battles([match("victory", change=8), match("defeat", change=-3),
                               match("draw"), match(rank=2), match("victory", tag="#PYLQ")], "#2PP")
    assert result["count"] == 4
    assert result["win_rate"] == 50
    assert result["decisive"] == 2
    assert result["placements"] == 1
    assert result["trophy_change"] == 5
    assert result["trophies_known"] == 2
    assert result["power_gap"] is None


def test_power_difference_is_relative_to_the_connected_players_team():
    entry = BattleLogService(None).parse_entry({"event": {"id": 1, "mode": "brawlBall", "map": "Example"},
        "battle": {"teams": [
            [{"tag": "#PYLQ", "name": "Other", "brawler": {"id": 2, "name": "COLT", "power": 11}}],
            [{"tag": "#2PP", "name": "Player", "brawler": {"id": 1, "name": "SHELLY", "power": 9}}]]}})
    assert summarize_battles([entry], "#2PP")["power_gap"] == -2


def test_unsaved_wallet_is_not_a_zero_balance(tmp_path):
    resources = ResourceService(tmp_path / "resources.db")
    assert resources.get_saved("#2PP") is None
    wallet = resources.get("#2PP")
    resources.save(wallet)
    assert resources.get_saved("#2PP").coins == 0


def test_events_preserve_official_slot_and_nested_modifier_fields():
    event = EventsService(None).parse_event({"slotId": 12,
        "startTime": "20261007T010000.000Z", "endTime": "20261007T020000.000Z",
        "event": {"id": 15000001, "mode": "brawlBall", "modeId": 3, "map": "Example",
                  "modifiers": [{"id": 7, "name": "Fast"}, "Healing"]}})
    assert event.slot_id == 12
    assert event.event.mode_id == 3
    assert event.modifiers == ["Fast", "Healing"]


def test_live_overview_never_uses_demo_supplemental_data(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    player = parse_player({"tag": "#2PP", "name": "Live", "brawlers": []})
    async def get_player(_):
        return player, False
    async def battles(_):
        return main.battlelog_service.load_demo(), "DEMO"
    async def events():
        return main.events_service.load_demo(), "DEMO"
    async def catalog():
        return None
    monkeypatch.setattr(main.player_service, "get_player", get_player)
    monkeypatch.setattr(main.battlelog_service, "get_battlelog", battles)
    monkeypatch.setattr(main.events_service, "get_events", events)
    monkeypatch.setattr(main.resource_service, "get_saved", lambda _: None)
    monkeypatch.setattr(main, "_overview_official_catalog", catalog)
    result = TestClient(main.app).get("/api/overview", params={"tag": "#2PP"})
    assert result.status_code == 200
    data = result.json()
    assert data["summary"]["source"] == "OFFICIAL_API"
    assert data["battles"]["source"] == "UNAVAILABLE"
    assert data["battles"]["count"] == 0
    assert data["events"]["source"] == "UNAVAILABLE"
    assert data["events"]["items"] == []
