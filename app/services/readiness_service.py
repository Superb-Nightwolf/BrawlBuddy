"""Deterministic inventory readiness, direct costs, and separate Claw exposure."""
from __future__ import annotations

import re
from math import comb
from typing import Any

from app.core.readiness_config import READINESS_CONFIG
from app.models.player import PlayerBrawler
from app.models.readiness import ReadinessRequest


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def claw_costs(pool_size: int, target_count: int, config: dict[str, Any]) -> dict[str, Any]:
    """The last target's order statistic in a uniformly shuffled unique pool."""
    if pool_size < 0 or target_count < 0 or target_count > pool_size:
        raise ValueError("Remaining reward count must be at least the number of missing Buffies")

    def exposure(pulls: float) -> dict[str, float]:
        return {
            "pulls": pulls,
            "powerPoints": pulls * config["powerPointsPerPull"],
            "coins": pulls * config["coinsPerPull"],
        }

    return {
        "poolSize": pool_size,
        "targetCount": target_count,
        "startingTargetProbability": target_count / pool_size if pool_size and target_count else 0,
        "individualTargetProbability": 1 / pool_size if pool_size and target_count else 0,
        "perPull": exposure(1),
        "bestCase": exposure(target_count),
        "expected": exposure(target_count * (pool_size + 1) / (target_count + 1) if target_count else 0),
        "worstCase": exposure(pool_size if target_count else 0),
        "completionProbabilities": {
            "bestCase": 1 / comb(pool_size, target_count),
            "worstCase": 1,
        },
    }


class ReadinessService:
    def __init__(self, guides: dict, equipment: dict, buffies: dict, config: dict | None = None):
        self.guides = guides
        self.equipment = equipment
        self.buffies = buffies
        self.config = config if config is not None else READINESS_CONFIG
        self.released = {normalized(name) for name in buffies.get("released_brawlers", [])}
        guide_ids = {normalized(guide["name"]): int(bid) for bid, guide in guides.items()}
        self.trio_pools = []
        for trio in buffies.get("trios", []):
            members = [guide_ids.get(normalized(member["name"])) for member in trio["brawlers"]]
            if len(members) != 3 or len(set(members)) != 3 or None in members:
                continue
            self.trio_pools.append({"name": trio["trio"], "rewards": [
                {"brawlerId": bid, "category": category}
                for bid in members for category in self._buffie_categories(bid)
            ]})

    def _buffie_categories(self, brawler_id: int) -> list[str]:
        guide = self.guides.get(str(brawler_id), {})
        if normalized(guide.get("name", "")) not in self.released:
            return []
        categories = self.config["buffie"].get("releasedCategories", {}).get(
            str(brawler_id), self.config["buffie"]["categories"]
        )
        return [category for category in dict.fromkeys(categories) if category in ("gadget", "star_power", "hypercharge")
                and (category != "hypercharge" or self._hypercharge_available(guide))]

    @staticmethod
    def _hypercharge_available(guide: dict) -> bool:
        hyper = guide.get("hypercharge") or {}
        return bool(hyper.get("name") and hyper.get("released") is not False
                    and normalized(hyper["name"]) not in ("unreleased", "notyetreleased"))

    def _recommended_item(self, guide: dict, brawler_id: int, kind: str, name: str | None) -> dict | None:
        if not name:
            return None
        collection = "gadgets" if kind == "gadget" else "star_powers"
        item = next((item for item in guide.get(collection, [])
                     if normalized(item["name"]) == normalized(name) and item.get("id")), None)
        if item:
            return item
        return next((dict(item, name=key) for key, item in self.equipment.items()
                     if item.get("type") == kind and str(item.get("brawler_id")) == str(brawler_id)
                     and normalized(key) == normalized(name) and item.get("id")), None)

    def _claw(self, brawler_id: int, roster: dict[int, PlayerBrawler], missing: list[str],
              manual_size: int | None) -> dict[str, Any]:
        config = self.config["buffie"]["claw"]
        pool_source, pool_name = "reference", "Reference pool"
        # A maintained pool is an explicit list of gameplay rewards, not the full
        # released Buffie catalog. Machines can contain different collections.
        pool = next((pool for pool in config.get("pools", []) if any(
            reward["brawlerId"] == brawler_id for reward in pool["rewards"])), None)
        pool_source_kind = "configured_pool"
        if pool is None:
            pool = next((pool for pool in self.trio_pools if any(
                reward["brawlerId"] == brawler_id for reward in pool["rewards"])), None)
            pool_source_kind = "trio_pool"
        group = None
        if pool:
            rewards = {(reward["brawlerId"], reward["category"]) for reward in pool["rewards"]}
            eligible = {(bid, category) for bid, category in rewards
                        if bid in roster and category in self._buffie_categories(bid)}
            collected = {(bid, category) for bid, category in eligible if getattr(roster[bid].buffies, category)}
            remaining = eligible - collected
            members = []
            for bid in dict.fromkeys(reward["brawlerId"] for reward in pool["rewards"]):
                member_rewards = {category for reward_id, category in rewards if reward_id == bid}
                owned_categories = {category for reward_id, category in collected if reward_id == bid}
                members.append({"brawlerId": bid, "name": self.guides.get(str(bid), {}).get("name", str(bid)),
                                "isOwned": bid in roster, "owned": len(owned_categories), "total": len(member_rewards),
                                "categories": {category: category in owned_categories
                                               for category in self.config["buffie"]["categories"]}})
            group = {"name": pool["name"], "total": len(rewards), "owned": len(collected),
                     "missing": len(rewards) - len(collected), "remaining": len(remaining),
                     "excluded": len(rewards) - len(eligible), "members": members}
        unavailable_reason = None
        if manual_size is not None:
            size, pool_source, pool_name = manual_size, "user_input", "Your machine"
        elif pool:
            size, pool_source, pool_name = len(remaining), pool_source_kind, pool["name"]
            if any((brawler_id, category) not in remaining for category in missing):
                unavailable_reason = "The selected machine does not contain every missing Buffie. Check its rewards."
        else:
            brawler = roster.get(brawler_id)
            collected = sum(getattr(brawler.buffies, category) for category in self._buffie_categories(brawler_id)) if brawler else 0
            size = max(0, config["initialPoolSize"] - collected)

        if not missing:
            size = max(0, size)
        if unavailable_reason:
            return {"available": False, "reason": unavailable_reason, "poolSize": size,
                    "targetCount": len(missing), "poolSource": pool_source, "poolName": pool_name, "group": group}
        result = claw_costs(size, len(missing), config)
        result.update({"available": True, "poolSource": pool_source, "poolName": pool_name,
                       "isEstimate": pool_source == "reference", "duplicateProtected": True, "group": group})
        return result

    def calculate(self, brawler_id: int, request: ReadinessRequest) -> dict[str, Any]:
        guide = self.guides.get(str(brawler_id))
        if not guide:
            raise KeyError(brawler_id)
        roster = {item.id: item for item in request.brawlers}
        player = roster.get(brawler_id)
        current = player.power if player else 0
        target = request.targetPower
        build = guide.get("recommended_build") or {}
        equipment_config = self.config["equipment"]
        buffie_categories = self._buffie_categories(brawler_id)
        buffies_released = bool(buffie_categories)
        rows: list[dict[str, Any]] = []
        ownership = {"gadget": False, "starPower": False, "gears": [], "hypercharge": False,
                     "buffies": {"gadget": False, "starPower": False, "hyperCharge": False}}
        missing: dict[str, Any] = {"gadget": False, "starPower": False, "gears": [], "hypercharge": False, "buffies": []}
        totals = {"powerPoints": 0, "coins": 0, "gems": 0}
        subtotals = {category: {**totals, "gemsEstimated": False} for category in ("power", "build", "buffies")}
        costs_complete = True

        def add_row(key: str, category: str, label: str, item_name: str, item_id: int | None,
                    owned: bool, unlock: int, cost: dict, available: bool = True,
                    note: str = "", image_url: str | None = None, estimated: bool = False):
            status = "unavailable" if not available else "stored" if owned and current < unlock else "owned" if owned else "missing"
            actual_cost = {"powerPoints": 0, "coins": 0, "gems": 0}
            if available and not owned:
                actual_cost.update(cost)
                for currency in totals:
                    totals[currency] += actual_cost[currency]
                    subtotals[category][currency] += actual_cost[currency]
                subtotals[category]["gemsEstimated"] |= estimated
            row = {"key": key, "category": category, "label": label, "name": item_name,
                   "id": item_id, "status": status, "owned": owned, "available": available,
                   "unlockPower": unlock, "cost": actual_cost, "gemsEstimated": estimated and not owned,
                   "note": note, "imageUrl": image_url}
            rows.append(row)
            return row

        for level in range(max(1, current), target):
            add_row(f"power-{level}", "power", f"Power {level} → {level + 1}", "Level upgrade", None,
                    False, level, self.config["powerUpgrades"][str(level)], image_url="/assets/currencies/power-points.png")

        group_rows: dict[str, list[dict]] = {"gadget": [], "star_power": [], "gears": [], "hypercharge": [], "buffies": []}
        for kind, label, owned_key in (("gadget", "Recommended Gadget", "gadget"), ("star_power", "Recommended Star Power", "starPower")):
            item = self._recommended_item(guide, brawler_id, kind, build.get(kind))
            unlock = equipment_config[kind]["unlockPower"]
            available = bool(item) and target >= unlock
            owned_items = getattr(player, "gadgets" if kind == "gadget" else "star_powers", [])
            owned = bool(item and any(owned_item.id == item["id"] for owned_item in owned_items))
            row = add_row(kind, "build", label, (item or {}).get("name") or build.get(kind) or "Recommendation unavailable",
                          (item or {}).get("id"), owned, unlock, {"coins": equipment_config[kind]["coins"]},
                          available, "Recommendation unavailable" if not item else "",
                          (item or {}).get("image_url"))
            group_rows[kind].append(row)
            ownership[owned_key] = owned
            missing[owned_key] = available and not owned
            if not item and target >= unlock:
                costs_complete = False

        gear_names = list(dict.fromkeys(name.upper() for name in (build.get("gears") or [])))[:len(equipment_config["gearUnlockPowers"])]
        available_gear_names = {name.upper() for name in guide.get("gears", [])}
        for index, name in enumerate(gear_names):
            gear = equipment_config["gears"].get(name.upper())
            unlock = equipment_config["gearUnlockPowers"][index]
            removed = bool(gear and buffies_released and gear.get("removedWithBuffies"))
            available = bool(gear and gear.get("enabled", True) and not removed and
                             target >= unlock and name in available_gear_names and
                             (not gear.get("brawlerIds") or brawler_id in gear["brawlerIds"]))
            item_id = gear["id"] if gear else None
            owned = bool(gear and player and any(item.id == item_id for item in player.gears))
            price = (gear or {}).get("coins", equipment_config["gearPrices"].get((gear or {}).get("rarity")))
            if available and price is None:
                available = False
            note = "Replaced by Buffies" if removed else "Gear unavailable" if not available else ""
            row = add_row(f"gear-{index}", "build", f"Recommended Gear #{index + 1}", name, item_id,
                          owned, unlock, {"coins": price or 0}, available, note,
                          f"/assets/equipment/gears/{item_id}.png" if item_id else None)
            group_rows["gears"].append(row)
            if available:
                (ownership["gears"] if owned else missing["gears"]).append(item_id)
            if not gear or price is None:
                costs_complete = False
        if not gear_names and target >= equipment_config["gearUnlockPowers"][0]:
            costs_complete = False

        hyper = guide.get("hypercharge") or {}
        hyper_available = self._hypercharge_available(guide) and target >= equipment_config["hypercharge"]["unlockPower"]
        hyper_owned = bool(player and player.has_hypercharge)
        row = add_row("hypercharge", "build", "Hypercharge", hyper.get("name", "Unavailable"), hyper.get("id"),
                      hyper_owned, equipment_config["hypercharge"]["unlockPower"],
                      {"coins": equipment_config["hypercharge"]["coins"]}, hyper_available,
                      "Not released" if not self._hypercharge_available(guide) else "",
                      hyper.get("image_url"))
        group_rows["hypercharge"].append(row)
        ownership["hypercharge"] = hyper_owned
        missing["hypercharge"] = hyper_available and not hyper_owned

        category_names = {"gadget": ("Gadget Buffie", "gadget"), "star_power": ("Star Power Buffie", "starPower"),
                          "hypercharge": ("Hyper Buffie", "hyperCharge")}
        for category in buffie_categories:
            label, owned_key = category_names[category]
            owned = bool(player and getattr(player.buffies, category))
            override = self.config["buffie"]["directGemPrices"].get(str(brawler_id), {}).get(category)
            if override is None:
                override = self.config["buffie"].get("directGemPricesByCategory", {}).get(category)
            price = override.get("gems") if isinstance(override, dict) else override
            estimated = override.get("estimated", False) if isinstance(override, dict) else override is None
            price = self.config["buffie"]["defaultDirectGemPrice"] if price is None else price
            available = target >= equipment_config[category]["unlockPower"]
            row = add_row(f"buffie-{category}", "buffies", label, label, None, owned,
                          equipment_config[category]["unlockPower"], {"gems": price}, available,
                          image_url=f"/assets/equipment/buffies/{brawler_id}-{category.replace('_', '-')}.png", estimated=estimated)
            group_rows["buffies"].append(row)
            row["directGemPrice"] = price
            row["directGemPriceEstimated"] = estimated
            ownership["buffies"][owned_key] = owned
            if available and not owned:
                missing["buffies"].append(category)

        weights = self.config["weights"]
        power_progress = min(1, current / target) if player else 0
        numerator, denominator = weights["power"] * power_progress, weights["power"]
        build_items: list[dict] = []
        for group, items in group_rows.items():
            applicable = [item for item in items if item["available"]]
            if group != "buffies":
                build_items.extend(applicable)
            if applicable:
                fraction = sum(item["owned"] for item in applicable) / len(applicable)
                numerator += weights[group] * fraction
                denominator += weights[group]
        buffie_rows = [row for row in group_rows["buffies"] if row["available"]]
        category_progress = {}
        for category, items in {
            "gears": group_rows["gears"],
            "abilities": group_rows["gadget"] + group_rows["star_power"],
            "hypercharge": group_rows["hypercharge"],
        }.items():
            applicable = [item for item in items if item["available"]]
            owned_count = sum(item["owned"] for item in applicable)
            category_progress[category] = {
                "owned": owned_count, "total": len(applicable),
                "progress": round(owned_count / len(applicable) * 100, 1) if applicable and player else None,
            }
        build_owned = sum(row["owned"] for row in build_items)
        buffies_owned = sum(row["owned"] for row in buffie_rows)
        buffie_gems = sum(row["cost"]["gems"] for row in buffie_rows)
        gems_estimated = any(row["gemsEstimated"] for row in buffie_rows)
        claw = self._claw(brawler_id, roster, missing["buffies"], request.remainingClawPoolSize) if player else {
            "available": False, "reason": "Unlock this Brawler before planning Claw rewards.", "targetCount": len(missing["buffies"])}
        if claw["available"]:
            # A route replaces the Buffie Gem purchase, while keeping all Power
            # and recommended-build requirements. Never charge both routes.
            claw["totalToMaxReady"] = {
                scenario: {"powerPoints": totals["powerPoints"] + claw[scenario]["powerPoints"],
                           "coins": totals["coins"] + claw[scenario]["coins"], "gems": 0}
                for scenario in ("bestCase", "expected", "worstCase")
            }

        # Do not round an almost-complete inventory up to a misleading 100%.
        overall = round(numerator / denominator * 100, 1) if denominator and player else None
        complete = bool(player and current >= target and all(row["owned"] for row in build_items + buffie_rows) and costs_complete)
        if overall == 100 and not complete:
            overall = 99.9
        return {
            "brawlerId": brawler_id, "name": guide["name"], "currentPower": current, "targetPower": target,
            "isOwned": bool(player), "inventorySource": request.source.value, "configVersion": self.config["version"],
            "overallProgress": overall, "complete": complete, "costsComplete": costs_complete,
            "categoryProgress": category_progress,
            "buffiePriceSources": self.config["buffie"].get("directPriceSources", []),
            "progress": {"power": round(power_progress * 100, 1) if player else None,
                         "build": round(build_owned / len(build_items) * 100, 1) if build_items and player else None,
                         "buffies": round(buffies_owned / len(buffie_rows) * 100, 1) if buffie_rows and player else None},
            "counts": {"buildOwned": build_owned, "buildTotal": len(build_items),
                       "buffiesOwned": buffies_owned, "buffiesTotal": len(buffie_rows)},
            "owned": ownership, "missing": missing, "breakdown": rows,
            "costs": {"guaranteed": {**totals, "gemsEstimated": gems_estimated},
                      "subtotals": subtotals,
                      "buffieDirect": {"missing": len(missing["buffies"]), "gems": buffie_gems, "estimated": gems_estimated},
                      "buffieClawAlternative": claw},
            "weights": weights, "normalizationWeight": denominator,
        }
