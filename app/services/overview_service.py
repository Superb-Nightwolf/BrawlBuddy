"""Account analytics with explicit denominators and field availability."""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from statistics import median
from typing import Any

from app.models.player import PlayerProfile, PlayerResources
from app.models.readiness import ReadinessRequest


def percentage(part: float, total: float) -> float | None:
    return round(part / total * 100, 1) if total else None


EQUIPMENT = {
    "gadgets": ("Gadgets", ("gadgets",)),
    "star_powers": ("Star Powers", ("starPowers", "star_powers")),
    "gears": ("Gears", ("gears",)),
    "hypercharges": ("Hypercharges", ("hyperCharges", "hypercharges", "hypercharge")),
}


def known(brawler, key: str) -> bool:
    return any(field in brawler.available_fields for field in EQUIPMENT[key][1])


class OverviewService:
    def __init__(self, catalog: list[dict], readiness):
        self.catalog = catalog
        self.readiness = readiness

    def summarize(self, player: PlayerProfile, official_catalog: list[dict] | None = None,
                  resources: PlayerResources | None = None) -> dict[str, Any]:
        roster = player.brawlers
        count = len(roster)
        metadata = {b["id"]: b for b in self.catalog}
        catalog = {b["id"]: b for b in (official_catalog if official_catalog is not None else self.catalog)}
        catalog_ids = set(catalog)
        unlocked = len({b.id for b in roster} & catalog_ids)
        powers = Counter(b.power for b in roster)
        classes = Counter(metadata.get(b.id, {}).get("class", "Unknown") for b in roster)
        rarities = Counter(metadata.get(b.id, {}).get("rarity", "Unknown") for b in roster)
        trophies = [b.trophies for b in roster]
        trophy_total = sum(trophies)
        top = sorted(roster, key=lambda b: b.trophies, reverse=True)
        trophy_ranges = [("0–249", 0, 250), ("250–499", 250, 500), ("500–749", 500, 750),
                         ("750–999", 750, 1000), ("1,000–1,999", 1000, 2000), ("2,000+", 2000, float("inf"))]
        prestige = Counter(b.prestige_level for b in roster)
        equipment = []
        for key, (label, aliases) in EQUIPMENT.items():
            observed = [b for b in roster if known(b, key)]
            owned = sum(len({item.id or item.name for item in getattr(b, key)}) for b in observed)
            covered = sum(bool(getattr(b, key)) for b in observed)
            available = matched = 0
            metadata_known = 0
            for b in observed:
                entry = catalog.get(b.id, {})
                items = next((entry[a] for a in aliases if a in entry), None)
                if not isinstance(items, list):
                    continue
                metadata_known += 1
                ids = {item["id"] for item in items if isinstance(item, dict) and item.get("id")}
                available += len(ids)
                matched += len({item.id for item in getattr(b, key)} & ids)
            equipment.append({"key": key, "label": label, "owned": owned, "covered": covered,
                              "known": len(observed), "unknown": count - len(observed),
                              "coverage_pct": percentage(covered, len(observed)),
                              "available": available if metadata_known == len(observed) and observed else None,
                              "completion_pct": percentage(matched, available)
                              if metadata_known == len(observed) and observed else None})

        buffies = []
        for key, label in (("gadget", "Gadget Buffies"), ("star_power", "Star Power Buffies"),
                           ("hypercharge", "Hypercharge Buffies")):
            eligible = [b for b in roster if key in self.readiness._buffie_categories(b.id)]
            observed = [b for b in eligible if "buffies" in b.available_fields]
            owned = sum(getattr(b.buffies, key) for b in observed)
            buffies.append({"key": key, "label": label, "owned": owned, "eligible": len(eligible),
                            "known": len(observed), "unknown": len(eligible) - len(observed),
                            "pct": percentage(owned, len(observed))})

        hc_known = [b for b in roster if known(b, "hypercharges")]
        hc_active = sum(b.is_hypercharge_active for b in hc_known)
        hc_stored = sum(b.is_hypercharge_stored for b in hc_known)
        win_fields = [("3v3", "3vs3Victories", player.victories_3v3),
                      ("Solo", "soloVictories", player.solo_victories),
                      ("Duo", "duoVictories", player.duo_victories)]
        victories = [{"label": label, "value": value if field in player.available_fields else None}
                     for label, field, value in win_fields]
        victories_complete = all(row["value"] is not None for row in victories)
        victories_total = sum(row["value"] or 0 for row in victories)

        request = ReadinessRequest(brawlers=roster, source=player.source)
        builds = []
        power_cost = {"coins": 0, "powerPoints": 0}
        for b in roster:
            for level in range(b.power, 11):
                price = self.readiness.config["powerUpgrades"][str(level)]
                for currency in power_cost:
                    power_cost[currency] += price[currency]
            if str(b.id) not in self.readiness.guides or not all(known(b, k) for k in EQUIPMENT):
                continue
            if self.readiness._buffie_categories(b.id) and "buffies" not in b.available_fields:
                continue
            result = self.readiness.calculate(b.id, request)
            cost = result["costs"]["guaranteed"]
            affordable = None if resources is None or not result["costsComplete"] else (
                resources.coins >= cost["coins"] and resources.power_points >= cost["powerPoints"]
                and resources.gems >= cost["gems"])
            builds.append({"id": b.id, "name": b.name, "power": b.power,
                           "progress": result["overallProgress"], "complete": result["complete"],
                           "costs_complete": result["costsComplete"], "cost": cost,
                           "subtotals": result["costs"]["subtotals"], "affordable": affordable,
                           "missing": [row["name"] for row in result["breakdown"]
                                       if row["category"] != "power" and row["status"] == "missing"]})
        cost_total = {key: sum(b["cost"][key] for b in builds) for key in ("coins", "powerPoints", "gems")}
        build_coin_cost = sum(b["subtotals"]["build"]["coins"] for b in builds)
        cost_total["coins"] = power_cost["coins"] + build_coin_cost
        cost_total["powerPoints"] = power_cost["powerPoints"]
        pending = sorted((b for b in builds if not b["complete"]),
                         key=lambda b: (not b["costs_complete"], b["cost"]["coins"], b["cost"]["gems"], b["id"]))
        milestones = sorted(roster, key=lambda b: (b.trophies_to_next_prestige if b.prestige_level
                                                   else b.trophies_to_next_milestone or 0, b.id))
        streaks = [b for b in roster if b.max_win_streak is not None or b.current_win_streak is not None]
        rows = [{"id": b.id, "name": b.name, "power": b.power, "trophies": b.trophies,
                 "highest_trophies": b.highest_trophies if "highestTrophies" in b.available_fields else None,
                 "prestige": b.prestige_level, "prestige_source": b.prestige_level_source,
                 "current_streak": b.current_win_streak, "best_streak": b.max_win_streak,
                 "skin": b.skin.model_dump() if b.skin else None,
                 "class": metadata.get(b.id, {}).get("class", "Unknown"),
                 "rarity": metadata.get(b.id, {}).get("rarity", "Unknown"),
                 "equipment": {key: len(getattr(b, key)) if known(b, key) else None for key in EQUIPMENT},
                 "buffies": sum((b.buffies.gadget, b.buffies.star_power, b.buffies.hypercharge))
                 if "buffies" in b.available_fields else None} for b in roster]
        next_goal = ((player.trophies // 5000) + 1) * 5000
        return {
            "source": player.source, "fetched_at": player.fetched_at.isoformat(), "tag": player.tag,
            "collection": {"owned": count, "unlocked": unlocked, "total": len(catalog_ids),
                           "locked": len(catalog_ids) - unlocked, "pct": percentage(unlocked, len(catalog_ids)),
                           "catalog_source": "OFFICIAL_API" if official_catalog is not None else "STATIC_GAME_DATA",
                           "unknown_catalog_ids": count - unlocked},
            "power": {"average": round(sum(b.power for b in roster) / count, 2) if count else None,
                      "median": median([b.power for b in roster]) if roster else None,
                      "maxed": powers[11], "maxed_pct": percentage(powers[11], count),
                      "bars": [{"label": str(level), "value": powers[level]} for level in range(1, 12)],
                      "remaining_levels": sum(max(0, 11 - b.power) for b in roster)},
            "trophies": {"current": player.trophies, "best": player.highest_trophies
                         if "highestTrophies" in player.available_fields else None,
                         "gap": max(0, player.highest_trophies - player.trophies)
                         if "highestTrophies" in player.available_fields else None,
                         "next_goal": next_goal, "to_goal": next_goal - player.trophies,
                         "goal_pct": percentage(player.trophies, next_goal),
                         "average": round(trophy_total / count, 1) if count else None,
                         "median": median(trophies) if trophies else None,
                         "top5_pct": percentage(sum(b.trophies for b in top[:5]), trophy_total),
                         "top5": sum(b.trophies for b in top[:5]), "roster_total": trophy_total,
                         "distribution": [{"label": label, "value": sum(lo <= t < hi for t in trophies)}
                                          for label, lo, hi in trophy_ranges]},
            "classes": [{"label": k, "value": v} for k, v in classes.items()],
            "rarities": [{"label": k, "value": v} for k, v in rarities.items()],
            "prestige": {"total": player.brawler_prestige_level, "source": player.total_prestige_source,
                         "brawlers": sum(b.prestige_level > 0 for b in roster),
                         "bars": [{"label": "Path" if level == 0 else f"P{level}", "value": prestige[level]}
                                  for level in sorted(prestige)],
                         "known": sum(b.prestige_level_source != "INFERRED" for b in roster)},
            "equipment": equipment, "buffies": buffies,
            "hypercharges": {"active": hc_active, "stored": hc_stored,
                             "missing": len(hc_known) - hc_active - hc_stored,
                             "unknown": count - len(hc_known)},
            "victories": {"rows": victories, "total": victories_total if victories_complete else None,
                          "complete": victories_complete},
            "ranked": {"season": player.ranked_season_id,
                       "rows": [{"label": label, "value": elo, "rank": rank}
                                for label, elo, rank in (
                                    ("Current", player.ranked_elo, player.ranked_rank_name),
                                    ("Season best", player.highest_season_ranked_elo, player.highest_season_ranked_rank_name),
                                    ("All-time best", player.highest_all_time_ranked_elo, player.highest_all_time_ranked_rank_name))]},
            "fame": {"value": player.fame, "tier": player.fame_tier_name},
            "streaks": {"current_max": max((b.current_win_streak for b in streaks if b.current_win_streak is not None), default=None),
                        "record": max((b.max_win_streak for b in streaks if b.max_win_streak is not None), default=None),
                        "known": len(streaks)},
            "builds": {"known": len(builds), "complete": sum(b["complete"] for b in builds),
                       "build_coin_cost": build_coin_cost,
                       "mean_progress": round(sum(b["progress"] or 0 for b in builds) / len(builds), 1)
                       if builds else None, "cost": cost_total, "power_cost": power_cost,
                       "all_costs_complete": len(builds) == count and all(b["costs_complete"] for b in builds),
                       "goals": pending[:6], "histogram": [
                           {"label": label, "value": sum(lo <= (b["progress"] or 0) < hi for b in builds)}
                           for label, lo, hi in (("0–24%", 0, 25), ("25–49%", 25, 50),
                                                ("50–74%", 50, 75), ("75–99%", 75, 100), ("100%", 100, 101))]},
            "milestones": [{"id": b.id, "name": b.name,
                            "target": b.next_milestone_label or f"Prestige {b.next_prestige_level}",
                            "remaining": b.trophies_to_next_prestige if b.prestige_level
                            else b.trophies_to_next_milestone, "source": b.prestige_level_source}
                           for b in milestones[:5]],
            "records": {"xp": player.exp_points, "level": player.exp_level,
                        "championship": player.is_qualified_from_championship_challenge
                        if "isQualifiedFromChampionshipChallenge" in player.available_fields else None,
                        "robo": player.best_robo_rumble_time, "big_brawler": player.best_time_as_big_brawler,
                        "power_play": player.highest_power_play_points},
            "rows": rows,
        }


def summarize_battles(entries: list, tag: str) -> dict:
    own_tag = tag.upper()
    modes = Counter()
    brawlers = Counter()
    outcomes = Counter()
    samples = []
    star_count = duration = 0
    durations_known = trophy_known = 0
    trophy_change = 0
    power_gaps = []
    for entry in sorted(entries, key=lambda e: e.battle_time):
        participants = entry.players + [p for team in entry.teams for p in team]
        own = next((p for p in participants if p.tag.upper() == own_tag), None)
        if own is None:
            continue
        result = entry.result if entry.result in ("victory", "defeat", "draw") else "placement" if entry.rank else "unknown"
        outcomes[result] += 1
        modes[entry.mode] += 1
        brawlers[own.brawler.name] += 1
        if entry.star_player and entry.star_player.tag.upper() == own_tag:
            star_count += 1
        if entry.duration is not None:
            duration += entry.duration
            durations_known += 1
        if entry.trophy_change is not None:
            trophy_change += entry.trophy_change
            trophy_known += 1
        own_team = next((team for team in entry.teams if any(p.tag.upper() == own_tag for p in team)), None)
        other = next((team for team in entry.teams if team is not own_team), None)
        if own_team and other and len(entry.teams) == 2:
            power_gaps.append(sum(p.brawler.power for p in own_team) / len(own_team)
                              - sum(p.brawler.power for p in other) / len(other))
        samples.append({"time": entry.battle_time, "mode": entry.mode, "map": entry.event.map,
                        "brawler": own.brawler.name, "id": own.brawler.id, "result": result,
                        "rank": entry.rank, "duration": entry.duration, "trophy_change": entry.trophy_change})
    decisive = outcomes["victory"] + outcomes["defeat"]
    return {"count": len(samples), "wins": outcomes["victory"], "losses": outcomes["defeat"],
            "draws": outcomes["draw"], "placements": outcomes["placement"], "unknown": outcomes["unknown"],
            "win_rate": percentage(outcomes["victory"], decisive), "decisive": decisive,
            "star_player": star_count, "play_seconds": duration, "durations_known": durations_known,
            "trophy_change": trophy_change if trophy_known else None, "trophies_known": trophy_known,
            "power_gap": round(sum(power_gaps) / len(power_gaps), 2) if power_gaps else None,
            "power_gap_count": len(power_gaps), "modes": [{"label": k, "value": v} for k, v in modes.most_common()],
            "brawlers": [{"label": k, "value": v} for k, v in brawlers.most_common()],
            "samples": samples, "oldest": samples[0]["time"] if samples else None,
            "newest": samples[-1]["time"] if samples else None}


def summarize_club(club, tag: str) -> dict:
    members = sorted(club.members, key=lambda m: m.trophies, reverse=True)
    position = next((i + 1 for i, member in enumerate(members) if member.tag.upper() == tag.upper()), None)
    own = next((m for m in members if m.tag.upper() == tag.upper()), None)
    return {"name": club.name, "tag": club.tag, "description": club.description,
            "trophies": club.trophies, "members": len(members), "position": position,
            "required_trophies": club.required_trophies, "type": club.type,
            "role": own.role if own else None, "own_trophies": own.trophies if own else None,
            "contribution": percentage(own.trophies, club.trophies) if own else None,
            "average": round(sum(m.trophies for m in members) / len(members)) if members else None,
            "leaders": [{"label": m.name, "value": m.trophies} for m in members[:5]]}


def event_timing(slot) -> dict:
    def parse(value):
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=UTC)
        except ValueError:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
            except ValueError:
                return None
    now = datetime.now(UTC)
    start, end = parse(slot.start_time), parse(slot.end_time)
    return {"id": slot.slot_id, "map": slot.event.map, "mode": slot.event.mode,
            "modifiers": slot.modifiers, "start": slot.start_time, "end": slot.end_time,
            "active": start <= now < end if start and end else None,
            "remaining_seconds": max(0, int((end - now).total_seconds())) if end else None,
            "progress": min(100, max(0, percentage((now - start).total_seconds(), (end - start).total_seconds()) or 0))
            if start and end and end > start else None}
