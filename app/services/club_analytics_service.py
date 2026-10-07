"""Club snapshot calculations using only the returned member roster."""
from __future__ import annotations

from collections import Counter
from math import ceil
from statistics import mean, median, pstdev

from app.models.club import ClubProfile


def role_key(value: str) -> str:
    key = value.lower().replace("_", "").replace(" ", "")
    return key if key in {"president", "vicepresident", "senior", "member"} else "unknown"


def percent(value: float, total: float) -> float | None:
    return round(value / total * 100, 2) if total else None


def percentile(values: list[int], fraction: float) -> float | None:
    if not values:
        return None
    position = (len(values) - 1) * fraction
    lower, upper = int(position), ceil(position)
    return round(values[lower] + (values[upper] - values[lower]) * (position - lower), 2)


def summarize_club_roster(club: ClubProfile) -> dict:
    members = sorted(club.members, key=lambda member: (-member.trophies, member.tag))
    values = sorted(member.trophies for member in members)
    count, total = len(members), sum(values)
    average = round(mean(values), 2) if count else None
    midpoint = median(values) if count else None
    roles = Counter(role_key(member.role) for member in members)
    labels = {"president": "President", "vicepresident": "Vice presidents",
              "senior": "Seniors", "member": "Members", "unknown": "Other roles"}
    role_rows = []
    for key, label in labels.items():
        matching = [member.trophies for member in members if role_key(member.role) == key]
        if key == "unknown" and not matching:
            continue
        role_rows.append({"key": key, "label": label, "value": len(matching),
                          "trophies": sum(matching), "share": percent(sum(matching), total),
                          "average": round(mean(matching), 2) if matching else None})
    distribution = []
    for lower in range(0, 100001, 20000):
        upper = lower + 20000 if lower < 100000 else None
        number = sum(value >= lower and (upper is None or value < upper) for value in values)
        label = f"{lower // 1000}k–{upper // 1000}k" if upper else "100k+"
        distribution.append({"label": label, "value": number, "pct": percent(number, count)})
    top_five = sum(member.trophies for member in members[:5])
    top_ten = sum(member.trophies for member in members[:10])
    cumulative = 0
    rows = []
    for member in members:
        cumulative += member.trophies
        rows.append({"tag": member.tag, "name": member.name, "role": member.role,
                     "role_key": role_key(member.role), "icon_id": member.icon_id,
                     "rank": 1 + sum(value > member.trophies for value in values),
                     "trophies": member.trophies, "share": percent(member.trophies, total),
                     "cumulative_share": percent(cumulative, total),
                     "gap_to_average": round(member.trophies - average, 2),
                     "gap_to_median": member.trophies - midpoint,
                     "entry_gap": max(0, club.required_trophies - member.trophies)})
    top = members[0] if count else None
    leaders = roles["president"] + roles["vicepresident"]
    next_target = (total // 100000 + 1) * 100000
    return {
        "member_count": count, "capacity": 30, "open_slots": max(0, 30 - count),
        "capacity_percent": round(min(100, count / 30 * 100), 2),
        "reported_trophies": club.trophies, "roster_trophies": total,
        "total_difference": club.trophies - total, "totals_match": club.trophies == total,
        "average_trophies": average, "median_trophies": midpoint,
        "min_trophies": min(values) if count else None, "max_trophies": max(values) if count else None,
        "trophy_range": max(values) - min(values) if count else None,
        "q1": percentile(values, .25), "q3": percentile(values, .75),
        "standard_deviation": round(pstdev(values), 2) if count else None,
        "top_member_name": top.name if top else None,
        "top_member_trophies": top.trophies if top else None,
        "presidents_count": roles["president"], "vice_presidents_count": roles["vicepresident"],
        "seniors_count": roles["senior"], "regular_members_count": roles["member"],
        "leadership_count": leaders, "leadership_pct": percent(leaders, count),
        "roles": role_rows, "distribution": distribution,
        "top5_trophies": top_five, "top5_count": min(5, count), "top5_share": percent(top_five, total),
        "top10_trophies": top_ten, "top10_count": min(10, count), "top10_share": percent(top_ten, total),
        "above_average": sum(value > average for value in values) if count else 0,
        "at_or_above_entry": sum(value >= club.required_trophies for value in values),
        "below_entry": sum(value < club.required_trophies for value in values),
        "entry_deficit": sum(max(0, club.required_trophies - value) for value in values),
        "next_target": next_target, "to_target": next_target - total,
        "rows": rows,
    }
