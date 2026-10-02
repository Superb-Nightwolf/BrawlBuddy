from copy import deepcopy
from itertools import combinations
from statistics import mean

import pytest
from fastapi.testclient import TestClient

from app.core.readiness_config import READINESS_CONFIG
from app.main import app, brawler_guides, buffies_db, equipment_db
from app.models.player import PlayerBrawler
from app.models.readiness import ReadinessRequest
from app.services.readiness_service import ReadinessService, claw_costs


def fixture_service(buffies=True, hypercharge=True):
    guide = {
        "name": "TEST", "gadgets": [{"id": 101, "name": "Recommended Gadget"}],
        "star_powers": [{"id": 201, "name": "Recommended Star"}],
        "recommended_build": {"gadget": "Recommended Gadget", "star_power": "Recommended Star",
                              "gears": ["DAMAGE", "SHIELD"]},
        "gears": ["DAMAGE", "SHIELD", "PET POWER", "THICC HEAD"],
        "hypercharge": {"name": "Test Hyper", "released": hypercharge},
    }
    config = deepcopy(READINESS_CONFIG)
    return ReadinessService({"1": guide}, {}, {"released_brawlers": ["TEST"] if buffies else []}, config)


def inventory(power=8, **overrides):
    return PlayerBrawler(id=1, name="TEST", power=power, **overrides)


def calculate(service, player, **kwargs):
    return service.calculate(1, ReadinessRequest(brawlers=[player], **kwargs))


def trio_service():
    service = fixture_service()
    for bid, name in ((2, "PEER"), (3, "THIRD")):
        service.guides[str(bid)] = {**deepcopy(service.guides["1"]), "name": name}
    buffies = {"released_brawlers": ["TEST", "PEER", "THIRD"], "trios": [
        {"trio": "Test trio", "brawlers": [{"name": name} for name in ("TEST", "PEER", "THIRD")]}]}
    return ReadinessService(service.guides, {}, buffies, service.config)


def test_trio_pool_counts_peers_stored_buffies_and_ignores_other_groups():
    service = trio_service()
    player = inventory(buffies={"gadget": True})
    peer = PlayerBrawler(id=2, name="PEER", power=1, buffies={"star_power": True, "hypercharge": True})
    third = PlayerBrawler(id=3, name="THIRD", power=1, buffies={"gadget": True})
    unrelated = PlayerBrawler(id=4, name="OTHER", power=11,
                             buffies={"gadget": True, "star_power": True, "hypercharge": True})
    request = ReadinessRequest(brawlers=[player, peer, third, unrelated])
    result = service.calculate(1, request)
    claw = result["costs"]["buffieClawAlternative"]
    assert claw["poolSource"] == "trio_pool"
    assert claw["isEstimate"] is False
    assert (claw["poolSize"], claw["targetCount"]) == (5, 2)
    assert {key: claw["group"][key] for key in ("total", "owned", "missing", "remaining", "excluded")} == {
        "total": 9, "owned": 4, "missing": 5, "remaining": 5, "excluded": 0}
    assert [member["owned"] for member in claw["group"]["members"]] == [1, 2, 1]
    assert claw["startingTargetProbability"] == pytest.approx(2 / 5)
    assert claw["worstCase"] == {"pulls": 5, "powerPoints": 10000, "coins": 5000}
    assert claw["totalToMaxReady"]["worstCase"] == {"powerPoints": 12880, "coins": 20925, "gems": 0}
    # The other member's page uses the identical remaining machine, with its own target count.
    other = service.calculate(2, request)["costs"]["buffieClawAlternative"]
    assert other["group"] == claw["group"]
    assert (other["poolSize"], other["targetCount"]) == (5, 1)
    assert other["startingTargetProbability"] == pytest.approx(1 / 5)
    peer.buffies.gadget = True
    updated = service.calculate(1, request)["costs"]["buffieClawAlternative"]
    assert (updated["group"]["owned"], updated["poolSize"]) == (5, 4)


def test_trio_counts_keep_locked_rewards_separate_from_missing_and_eligible():
    result = calculate(trio_service(), inventory(buffies={"gadget": True}))
    claw = result["costs"]["buffieClawAlternative"]
    assert claw["poolSize"] == 2
    assert (claw["group"]["total"], claw["group"]["owned"], claw["group"]["missing"], claw["group"]["excluded"]) == (9, 1, 8, 6)
    assert [member["isOwned"] for member in claw["group"]["members"]] == [True, False, False]


def test_released_buffie_catalog_has_nine_distinct_three_brawler_machines():
    service = ReadinessService(brawler_guides, equipment_db, buffies_db)
    assert len(buffies_db["trios"]) == len(service.trio_pools) == 9
    grouped_ids = []
    for pool in service.trio_pools:
        assert len(pool["rewards"]) == 9
        ids = {reward["brawlerId"] for reward in pool["rewards"]}
        assert len(ids) == 3
        grouped_ids.extend(ids)
    assert len(grouped_ids) == len(set(grouped_ids)) == 27
    assert {brawler_guides[str(bid)]["name"] for bid in grouped_ids} == set(buffies_db["released_brawlers"])


def test_power_8_example_uses_actual_recommended_inventory_and_direct_gems():
    player = inventory(gadgets=[{"id": 101, "name": "Recommended Gadget"}],
                       gears=[{"id": 62000002, "name": "DAMAGE"}], buffies={"gadget": True})
    result = calculate(fixture_service(), player, remainingClawPoolSize=9)
    assert result["costs"]["guaranteed"] == {"powerPoints": 2880, "coins": 13925, "gems": 378, "gemsEstimated": False}
    assert result["costs"]["subtotals"] == {
        "power": {"powerPoints": 2880, "coins": 5925, "gems": 0, "gemsEstimated": False},
        "build": {"powerPoints": 0, "coins": 8000, "gems": 0, "gemsEstimated": False},
        "buffies": {"powerPoints": 0, "coins": 0, "gems": 378, "gemsEstimated": False},
    }
    assert result["counts"] == {"buildOwned": 2, "buildTotal": 5, "buffiesOwned": 1, "buffiesTotal": 3}
    assert result["progress"] == {"power": 72.7, "build": 40.0, "buffies": 33.3}
    assert result["categoryProgress"] == {
        "gears": {"owned": 1, "total": 2, "progress": 50.0},
        "abilities": {"owned": 1, "total": 2, "progress": 50.0},
        "hypercharge": {"owned": 0, "total": 1, "progress": 0.0},
    }
    assert result["overallProgress"] == 49.9
    assert [(row["cost"]["powerPoints"], row["cost"]["coins"]) for row in result["breakdown"] if row["category"] == "power"] == [(550, 1250), (890, 1875), (1440, 2800)]
    claw = result["costs"]["buffieClawAlternative"]
    assert claw["bestCase"] == {"pulls": 2, "powerPoints": 4000, "coins": 2000}
    assert claw["worstCase"] == {"pulls": 9, "powerPoints": 18000, "coins": 9000}
    assert claw["startingTargetProbability"] == pytest.approx(2 / 9)
    assert claw["individualTargetProbability"] == pytest.approx(1 / 9)
    assert claw["totalToMaxReady"] == {
        "bestCase": {"powerPoints": 6880, "coins": 15925, "gems": 0},
        "expected": {"powerPoints": pytest.approx(16213.333333), "coins": pytest.approx(20591.666667), "gems": 0},
        "worstCase": {"powerPoints": 20880, "coins": 22925, "gems": 0},
    }


def test_full_power_path_and_already_maxed_costs():
    service = fixture_service()
    result = calculate(service, inventory(power=1))
    power_rows = [row for row in result["breakdown"] if row["category"] == "power"]
    assert sum(row["cost"]["powerPoints"] for row in power_rows) == 3740
    assert sum(row["cost"]["coins"] for row in power_rows) == 7765
    assert not [row for row in calculate(service, inventory(power=11))["breakdown"] if row["category"] == "power"]


def test_wrong_item_and_same_name_do_not_satisfy_recommended_id():
    result = calculate(fixture_service(), inventory(
        gadgets=[{"id": 999, "name": "Recommended Gadget"}],
        star_powers=[{"id": 888, "name": "Recommended Star"}],
        gears=[{"id": 777, "name": "DAMAGE"}]))
    assert result["owned"]["gadget"] is False
    assert result["owned"]["starPower"] is False
    assert result["owned"]["gears"] == []
    assert result["counts"]["buildOwned"] == 0
    correct = calculate(fixture_service(), inventory(gadgets=[{"id": 101, "name": "Renamed"}]))
    assert correct["owned"]["gadget"] is True
    assert next(row for row in correct["breakdown"] if row["key"] == "gadget")["cost"]["coins"] == 0


def test_owned_stored_items_and_buffies_never_receive_a_second_charge():
    player = inventory(power=6, gadgets=[{"id": 101, "name": "G"}],
                       star_powers=[{"id": 201, "name": "SP"}],
                       gears=[{"id": 62000002, "name": "D"}, {"id": 62000004, "name": "S"}],
                       hypercharges=[{"id": 301, "name": "HC"}],
                       buffies={"gadget": True, "star_power": True, "hypercharge": True})
    result = calculate(fixture_service(), player)
    assert all(row["status"] == "stored" for row in result["breakdown"] if row["category"] != "power")
    assert all(not any(row["cost"].values()) for row in result["breakdown"] if row["category"] != "power")
    assert result["progress"]["build"] == 100
    assert all(category["progress"] == 100 for category in result["categoryProgress"].values())
    assert result["complete"] is False
    maxed = calculate(fixture_service(), player.model_copy(update={"power": 11}))
    assert maxed["overallProgress"] == 100
    assert maxed["complete"] is True
    assert maxed["costs"]["guaranteed"] == {"coins": 0, "powerPoints": 0, "gems": 0, "gemsEstimated": False}
    assert all(not any(subtotal.values()) for subtotal in maxed["costs"]["subtotals"].values())
    assert maxed["costs"]["buffieClawAlternative"]["worstCase"]["pulls"] == 0
    assert maxed["costs"]["buffieClawAlternative"]["totalToMaxReady"]["worstCase"] == {"powerPoints": 0, "coins": 0, "gems": 0}


def test_unreleased_hypercharge_and_buffies_are_removed_from_denominator():
    player = inventory(power=11, gadgets=[{"id": 101, "name": "G"}],
                       star_powers=[{"id": 201, "name": "SP"}],
                       gears=[{"id": 62000002, "name": "D"}, {"id": 62000004, "name": "S"}])
    result = calculate(fixture_service(buffies=False, hypercharge=False), player)
    assert result["normalizationWeight"] == 80
    assert result["overallProgress"] == 100
    assert result["progress"]["buffies"] is None
    assert result["categoryProgress"]["hypercharge"] == {"owned": 0, "total": 0, "progress": None}
    assert result["costs"]["guaranteed"]["gems"] == 0
    assert result["costs"]["subtotals"]["buffies"] == {"powerPoints": 0, "coins": 0, "gems": 0, "gemsEstimated": False}
    assert result["missing"]["hypercharge"] is False
    assert result["counts"]["buildTotal"] == 4


def test_hyper_buffie_flag_is_not_base_hypercharge_ownership():
    result = calculate(fixture_service(), inventory(power=11, buffies={"hypercharge": True}))
    assert result["owned"]["hypercharge"] is False
    assert result["owned"]["buffies"]["hyperCharge"] is True
    assert next(row for row in result["breakdown"] if row["key"] == "hypercharge")["cost"]["coins"] == 5000


def test_central_gear_prices_and_removed_gears():
    service = fixture_service(buffies=False)
    service.guides["1"]["recommended_build"]["gears"] = ["PET POWER", "THICC HEAD"]
    result = calculate(service, inventory())
    gear_rows = [row for row in result["breakdown"] if row["key"].startswith("gear-")]
    assert [row["cost"]["coins"] for row in gear_rows] == [1500, 2000]
    service.released = {"test"}
    result = calculate(service, inventory())
    gear_rows = [row for row in result["breakdown"] if row["key"].startswith("gear-")]
    assert all(row["status"] == "unavailable" and row["cost"]["coins"] == 0 for row in gear_rows)
    assert result["counts"]["buildTotal"] == 3
    assert result["normalizationWeight"] == 85
    service.released.clear()
    service.config["equipment"]["gears"]["PET POWER"]["enabled"] = False
    assert calculate(service, inventory())["counts"]["buildTotal"] == 4


def test_specific_gem_price_overrides_category_price():
    service = fixture_service()
    service.config["buffie"]["directGemPrices"] = {"1": {"gadget": {"gems": 199, "estimated": False}}}
    player = inventory(buffies={"star_power": True, "hypercharge": True})
    result = calculate(service, player)
    assert result["costs"]["buffieDirect"] == {"missing": 1, "gems": 199, "estimated": False}
    assert result["costs"]["guaranteed"]["gems"] == 199


@pytest.mark.parametrize("flags,total", [
    ({}, 527), ({"gadget": True}, 378), ({"star_power": True}, 348),
    ({"hypercharge": True}, 328),
    ({"gadget": True, "star_power": True, "hypercharge": True}, 0),
])
def test_standard_buffie_prices_charge_only_missing_categories(flags, total):
    result = calculate(fixture_service(), inventory(buffies=flags))
    assert result["costs"]["guaranteed"]["gems"] == total
    assert result["costs"]["buffieDirect"]["estimated"] is False
    prices = {row["key"]: row["directGemPrice"] for row in result["breakdown"] if row["category"] == "buffies"}
    assert prices == {"buffie-gadget": 149, "buffie-star_power": 179, "buffie-hypercharge": 199}


def test_missing_category_price_uses_explicit_estimated_fallback():
    service = fixture_service()
    del service.config["buffie"]["directGemPricesByCategory"]["gadget"]
    result = calculate(service, inventory(buffies={"star_power": True, "hypercharge": True}))
    assert result["costs"]["buffieDirect"] == {"missing": 1, "gems": 300, "estimated": True}
    assert result["costs"]["subtotals"]["buffies"] == {"powerPoints": 0, "coins": 0, "gems": 300, "gemsEstimated": True}


@pytest.mark.parametrize("size,targets", [(9, 1), (9, 2), (9, 3), (5, 2), (3, 3), (1, 1)])
def test_claw_expectation_matches_every_possible_order_of_unique_targets(size, targets):
    outcomes = [max(positions) for positions in combinations(range(1, size + 1), targets)]
    result = claw_costs(size, targets, READINESS_CONFIG["buffie"]["claw"])
    assert result["bestCase"]["pulls"] == min(outcomes)
    assert result["expected"]["pulls"] == pytest.approx(mean(outcomes))
    assert result["worstCase"]["pulls"] == max(outcomes)
    assert result["expected"]["powerPoints"] == pytest.approx(mean(outcomes) * 2000)
    assert result["expected"]["coins"] == pytest.approx(mean(outcomes) * 1000)
    assert result["completionProbabilities"]["bestCase"] == pytest.approx(
        sum(pulls == min(outcomes) for pulls in outcomes) / len(outcomes))
    assert result["completionProbabilities"]["worstCase"] == 1


def test_configured_pool_removes_all_owned_rewards_and_locked_brawlers():
    service = fixture_service()
    service.guides["2"] = {**deepcopy(service.guides["1"]), "name": "PEER"}
    service.guides["3"] = {**deepcopy(service.guides["1"]), "name": "LOCKED"}
    service.released.update({"peer", "locked"})
    service.config["buffie"]["claw"]["pools"] = [{"name": "Known machine", "rewards": [
        {"brawlerId": bid, "category": category}
        for bid in (1, 2, 3) for category in ("gadget", "star_power", "hypercharge")]}]
    player = inventory(buffies={"gadget": True})
    peer = PlayerBrawler(id=2, name="PEER", power=11, buffies={"gadget": True, "star_power": True})
    result = service.calculate(1, ReadinessRequest(brawlers=[player, peer]))
    claw = result["costs"]["buffieClawAlternative"]
    assert claw["poolSize"] == 3  # 9 - 3 locked rewards - 3 owned rewards
    assert claw["targetCount"] == 2
    assert claw["worstCase"]["pulls"] == 3
    assert claw["poolSource"] == "configured_pool"
    player.buffies.star_power = True
    after = service.calculate(1, ReadinessRequest(brawlers=[player, peer]))["costs"]["buffieClawAlternative"]
    assert (after["poolSize"], after["targetCount"]) == (2, 1)


def test_pool_missing_a_target_does_not_claim_guaranteed_claw_completion():
    service = fixture_service()
    service.config["buffie"]["claw"]["pools"] = [{"name": "Partial machine", "rewards": [{"brawlerId": 1, "category": "gadget"}]}]
    result = calculate(service, inventory())
    assert result["costs"]["buffieClawAlternative"]["available"] is False
    assert "totalToMaxReady" not in result["costs"]["buffieClawAlternative"]
    assert result["costs"]["guaranteed"]["gems"] == 527


def test_reference_pool_is_explicitly_an_estimate_and_manual_size_is_validated():
    service = fixture_service()
    player = inventory(buffies={"gadget": True})
    result = calculate(service, player)
    claw = result["costs"]["buffieClawAlternative"]
    assert claw["poolSize"] == 8
    assert claw["isEstimate"] is True
    manual = calculate(service, player, remainingClawPoolSize=5)["costs"]["buffieClawAlternative"]
    assert manual["poolSize"] == 5
    assert manual["isEstimate"] is False
    assert manual["totalToMaxReady"]["worstCase"] == {"powerPoints": 12880, "coins": 20925, "gems": 0}
    with pytest.raises(ValueError):
        calculate(service, player, remainingClawPoolSize=1)


def test_catalog_preview_has_no_personal_readiness_or_claw_guarantee():
    result = fixture_service().calculate(1, ReadinessRequest())
    assert result["overallProgress"] is None
    assert result["currentPower"] == 0
    assert result["isOwned"] is False
    assert result["costs"]["buffieClawAlternative"]["available"] is False


def test_unknown_build_data_is_excluded_and_totals_are_marked_partial():
    service = fixture_service()
    service.guides["1"]["recommended_build"]["gadget"] = "Unknown gadget"
    result = calculate(service, inventory())
    assert result["costsComplete"] is False
    assert result["normalizationWeight"] == 90
    assert next(row for row in result["breakdown"] if row["key"] == "gadget")["status"] == "unavailable"


def test_readiness_endpoint_and_invalid_inventory():
    with TestClient(app) as client:
        demo = client.get("/api/demo/player").json()["player"]
        result = client.post("/api/brawlers/16000005/readiness", json={"brawlers": demo["brawlers"], "source": "DEMO"})
        assert result.status_code == 200
        assert result.json()["costs"]["guaranteed"]["powerPoints"] == 2880
        assert result.json()["inventorySource"] == "DEMO"
        invalid = client.post("/api/brawlers/16000005/readiness", json={"brawlers": demo["brawlers"], "remainingClawPoolSize": 0})
        assert invalid.status_code == 422
        assert client.post("/api/brawlers/999/readiness", json={}).status_code == 404
        assert client.post("/api/brawlers/16000005/readiness", json={"targetPower": 12}).status_code == 422
        assert client.post("/api/brawlers/16000005/readiness", json={"brawlers": [demo["brawlers"][0]] * 2}).status_code == 422


def test_all_catalog_guides_produce_valid_readiness_results():
    service = ReadinessService(brawler_guides, equipment_db, buffies_db)
    for bid, guide in brawler_guides.items():
        player = PlayerBrawler(id=int(bid), name=guide["name"], power=8)
        result = service.calculate(int(bid), ReadinessRequest(brawlers=[player]))
        assert 0 <= result["overallProgress"] <= 100
        assert all(value >= 0 for value in result["costs"]["guaranteed"].values())
