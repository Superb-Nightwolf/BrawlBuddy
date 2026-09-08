from __future__ import annotations

from dataclasses import asdict, dataclass


PRESTIGE_STEP_TROPHIES = 1_000
MAX_PRESTIGE_ASSET_LEVEL = 10
PRESTIGE_ASSET_ID_OFFSET = 3

PATH_MILESTONES = (
    (0, "Wood", 0),
    (250, "Bronze", 1),
    (500, "Silver", 2),
    (750, "Gold", 3),
)

MILESTONE_REWARDS = {
    250: "Player icon and spray",
    500: "Pins",
    750: "Rare skin or 1,000 Bling",
    1_000: "Gold Brawler Title",
    2_000: "Neon Player Icon",
    3_000: "Neon Brawler Title",
}


@dataclass(frozen=True)
class PrestigeState:
    level: int
    level_is_authoritative: bool
    total_trophies: int
    trophies_in_level: int
    floor_trophies: int
    next_level: int
    next_total_trophies: int
    trophies_remaining: int
    progress_percent: float
    label: str
    asset_id: int
    visual_level: int | None
    visual_is_fallback: bool
    next_reward: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def _path_state(total_trophies: int, authoritative: bool) -> PrestigeState:
    threshold, label, asset_id = PATH_MILESTONES[0]
    for candidate in PATH_MILESTONES:
        if total_trophies >= candidate[0]:
            threshold, label, asset_id = candidate

    next_threshold = next(
        (value for value, _, _ in PATH_MILESTONES if value > total_trophies),
        PRESTIGE_STEP_TROPHIES,
    )
    span = max(1, next_threshold - threshold)
    progress = min(span, max(0, total_trophies - threshold))
    return PrestigeState(
        level=0,
        level_is_authoritative=authoritative,
        total_trophies=total_trophies,
        trophies_in_level=total_trophies,
        floor_trophies=0,
        next_level=1,
        next_total_trophies=PRESTIGE_STEP_TROPHIES,
        trophies_remaining=max(0, next_threshold - total_trophies),
        progress_percent=round((progress / span) * 100, 1),
        label=label,
        asset_id=asset_id,
        visual_level=None,
        visual_is_fallback=False,
        next_reward=MILESTONE_REWARDS.get(next_threshold),
    )


def resolve_prestige_state(
    total_trophies: int,
    prestige_level: int | None = None,
    *,
    highest_trophies: int | None = None,
) -> PrestigeState:
    """Resolve current Prestige without confusing API totals and in-level progress.

    ``prestige_level`` is authoritative when supplied by the official API. Older
    demo/fixture payloads fall back to the highest known cumulative trophy count.
    """
    trophies = max(0, int(total_trophies or 0))
    authoritative = prestige_level is not None
    if authoritative:
        level = max(0, int(prestige_level or 0))
    else:
        legacy_peak = max(trophies, int(highest_trophies or 0))
        level = legacy_peak // PRESTIGE_STEP_TROPHIES

    if level == 0:
        return _path_state(trophies, authoritative)

    floor_trophies = level * PRESTIGE_STEP_TROPHIES
    next_total = (level + 1) * PRESTIGE_STEP_TROPHIES
    trophies_in_level = max(0, trophies - floor_trophies)
    trophies_remaining = max(0, PRESTIGE_STEP_TROPHIES - trophies_in_level)
    visual_level = min(level, MAX_PRESTIGE_ASSET_LEVEL)
    return PrestigeState(
        level=level,
        level_is_authoritative=authoritative,
        total_trophies=trophies,
        trophies_in_level=trophies_in_level,
        floor_trophies=floor_trophies,
        next_level=level + 1,
        next_total_trophies=next_total,
        trophies_remaining=trophies_remaining,
        progress_percent=round(min(100, trophies_in_level / PRESTIGE_STEP_TROPHIES * 100), 1),
        label=f"Prestige {level}",
        asset_id=PRESTIGE_ASSET_ID_OFFSET + visual_level,
        visual_level=visual_level,
        visual_is_fallback=level > MAX_PRESTIGE_ASSET_LEVEL,
        next_reward=MILESTONE_REWARDS.get(next_total),
    )
