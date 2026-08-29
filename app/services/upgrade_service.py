from typing import Any

# Official Supercell Upgrade Costs (Level -> Next Level)
# Index i is cost to go from level (i+1) to (i+2)
POWER_UPGRADE_COINS = {
    1: 20,
    2: 35,
    3: 75,
    4: 140,
    5: 290,
    6: 480,
    7: 800,
    8: 1250,
    9: 1875,
    10: 2800,
}

POWER_UPGRADE_POWER_POINTS = {
    1: 20,
    2: 30,
    3: 50,
    4: 80,
    5: 130,
    6: 210,
    7: 340,
    8: 550,
    9: 890,
    10: 1440,
}

EQUIPMENT_COSTS = {
    "gadget": 1000,
    "star_power": 2000,
    "gear_super_rare": 1000,
    "gear_epic": 1500,
    "gear_mythic": 2000,
    "hypercharge": 5000,
}


class UpgradeService:
    @staticmethod
    def calculate_brawler_upgrade_cost(current_power: int, target_power: int = 11) -> dict[str, int]:
        if current_power >= target_power or current_power < 1:
            return {"coins": 0, "power_points": 0}

        coins_needed = sum(POWER_UPGRADE_COINS[lvl] for lvl in range(current_power, target_power))
        pp_needed = sum(POWER_UPGRADE_POWER_POINTS[lvl] for lvl in range(current_power, target_power))

        return {
            "coins": coins_needed,
            "power_points": pp_needed
        }

    @staticmethod
    def calculate_roster_plan(brawlers: list[dict[str, Any]], wallet: dict[str, int]) -> dict[str, Any]:
        coins_wallet = wallet.get("coins", 0)
        pp_wallet = wallet.get("power_points", 0)

        total_roster_coins = 0
        total_roster_pp = 0
        brawler_plans = []

        for b in brawlers:
            power = b.get("power", 1)
            cost = UpgradeService.calculate_brawler_upgrade_cost(power, 11)
            total_roster_coins += cost["coins"]
            total_roster_pp += cost["power_points"]

            can_afford = (coins_wallet >= cost["coins"] and pp_wallet >= cost["power_points"]) if cost["coins"] > 0 else True
            can_upgrade_1_level = False
            if power < 11:
                cost_1 = UpgradeService.calculate_brawler_upgrade_cost(power, power + 1)
                can_upgrade_1_level = (coins_wallet >= cost_1["coins"] and pp_wallet >= cost_1["power_points"])

            brawler_plans.append({
                "id": b.get("id"),
                "name": b.get("name"),
                "current_power": power,
                "target_power": 11,
                "coins_to_max": cost["coins"],
                "pp_to_max": cost["power_points"],
                "can_max_now": can_afford and power < 11,
                "can_upgrade_next_level": can_upgrade_1_level
            })

        # Affordable upgrades sorted by highest power first
        affordable_now = [p for p in brawler_plans if p["can_max_now"]]

        return {
            "wallet": {"coins": coins_wallet, "power_points": pp_wallet},
            "total_coins_to_max_all": total_roster_coins,
            "total_pp_to_max_all": total_roster_pp,
            "coins_deficit": max(0, total_roster_coins - coins_wallet),
            "pp_deficit": max(0, total_roster_pp - pp_wallet),
            "brawlers_can_max_immediately": len(affordable_now),
            "brawler_plans": brawler_plans
        }

    @staticmethod
    def calculate_trophy_reset(brawlers: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculates monthly trophy reset decay and bling payoff for brawlers with 1000+ trophies."""
        decaying_brawlers = []
        total_bling_reward = 0
        total_trophies_lost = 0

        for b in brawlers:
            trophies = b.get("trophies", 0)
            if trophies > 1000:
                # Supercell trophy reset resets to 1000 and awards Bling based on excess
                excess = trophies - 1000
                bling = min(500, int(excess * 0.5) + 10)
                total_trophies_lost += excess
                total_bling_reward += bling
                decaying_brawlers.append({
                    "name": b.get("name"),
                    "current_trophies": trophies,
                    "reset_trophies": 1000,
                    "trophies_lost": excess,
                    "projected_bling": bling
                })

        return {
            "eligible_brawlers_count": len(decaying_brawlers),
            "total_trophies_decay": total_trophies_lost,
            "total_projected_bling": total_bling_reward,
            "decaying_brawlers": decaying_brawlers
        }
