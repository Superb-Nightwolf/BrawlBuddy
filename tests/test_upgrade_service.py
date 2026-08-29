from app.services.upgrade_service import UpgradeService


def test_calculate_brawler_upgrade_cost():
    cost_p1_to_11 = UpgradeService.calculate_brawler_upgrade_cost(1, 11)
    assert cost_p1_to_11["coins"] == 7765
    assert cost_p1_to_11["power_points"] == 3740

    cost_p10_to_11 = UpgradeService.calculate_brawler_upgrade_cost(10, 11)
    assert cost_p10_to_11["coins"] == 2800
    assert cost_p10_to_11["power_points"] == 1440


def test_calculate_roster_plan():
    brawlers = [
        {"id": 1, "name": "Shelly", "power": 10, "trophies": 900},
        {"id": 2, "name": "Colt", "power": 11, "trophies": 800}
    ]
    wallet = {"coins": 5000, "power_points": 2000}
    plan = UpgradeService.calculate_roster_plan(brawlers, wallet)
    assert plan["total_coins_to_max_all"] == 2800
    assert plan["total_pp_to_max_all"] == 1440
    assert plan["brawlers_can_max_immediately"] == 1


def test_calculate_trophy_reset():
    brawlers = [
        {"name": "Shelly", "trophies": 1050},
        {"name": "Colt", "trophies": 800}
    ]
    reset = UpgradeService.calculate_trophy_reset(brawlers)
    assert reset["eligible_brawlers_count"] == 1
    assert reset["total_trophies_decay"] == 50
    assert reset["total_projected_bling"] > 0
