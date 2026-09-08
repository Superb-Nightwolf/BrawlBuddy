# BrawlBuddy Prestige model

Checked against the live Brawl Stars API and published sources on 2026-09-08.

## Current rules

The February 2026 system replaces the old per-Brawler Rank/Trophy Tier presentation.
Before Prestige, a Brawler progresses through Wood (0), Bronze (250), Silver (500),
and Gold (750). The 1,000-Trophy milestone opens permanent Prestige progression.
Each subsequent 1,000 Trophies advances that Brawler by one Prestige level; there is
no supported maximum level in BrawlBuddy.

Published milestone rewards are:

- 250: Player icon and spray
- 500: Pins
- 750: Rare skin, or 1,000 Bling when no eligible skin is available
- 1,000: Gold Brawler Title
- Prestige 2: Neon Player Icon
- Prestige 3: Neon Brawler Title

Rewards shown by BrawlBuddy are milestone information only. The public API does not
confirm cosmetic ownership or claim state.

Prestige is permanent and cannot drop to a lower achieved level. The retired seasonal
Trophy Box/season reset system and the old leaderboard Prestige statistic are not used.
Ranked competitive mode remains separate and unchanged.

## API semantics

The current player response exposes:

- `brawlers[].prestigeLevel`: authoritative permanent level for that Brawler
- `totalPrestigeLevel`: authoritative account-wide sum of Brawler Prestige levels
- `brawlers[].trophies`: cumulative public Trophy total used by the API
- `brawlers[].highestTrophies`: highest cumulative public Trophy total
- `brawlers[].rank`: retained as a legacy compatibility field, not displayed as
  current Brawler progression

BrawlBuddy derives the in-level display counter as
`trophies - (prestigeLevel * 1000)`. This is kept separate from cumulative trophies.
If a legacy fixture lacks `prestigeLevel`, the highest known Trophy value supplies an
explicitly labeled inferred fallback. The official field always wins, including at
the exact 1,000/2,000/3,000 boundaries.

## Asset mapping

The Brawlify CDN repository defines asset IDs 0–3 as Wood, Bronze, Silver, and Gold,
and IDs 4–13 as Prestige 1–10. The resolver attempts:

1. `https://cdn.brawlify.com/prestiges/brawlers/{brawlerId}/{assetId}.png`
2. `https://cdn.brawlify.com/prestiges/tiered/{assetId}.png`
3. for the pre-Prestige path, `https://cdn.brawlify.com/prestiges/regular/{assetId}.png`

Prestige 11 and above retain their real numeric label and progression data while using
the Prestige 10 frame as a clearly identified visual fallback. They are never relabeled
as Prestige 10.

`scripts/sync_prestige_assets.py` refreshes the lightweight availability manifest from
the Brawlify GitHub repository without downloading duplicate image bundles. Browser/CDN
caching handles the images. Missing Brawler-specific art falls back without breaking the
page. The manifest currently covers every published Brawler ID in BrawlBuddy, including
Nori, Wendy, and special-name Brawlers; later Brawler folders are discovered by the same
sync command.

## Sources

- [Supercell February 2026 release notes](https://supercell.com/en/games/brawlstars/blog/release-notes/release-notes-february-2026/)
- [Supercell Prestige support article](https://support.supercell.com/brawl-stars/en/articles/prestige.html)
- [Supercell Trophy Season transition](https://supercell.com/en/games/brawlstars/blog/news/important-trophy-season-changes-4/)
- [Brawlify Prestige asset README](https://github.com/Brawlify/CDN/blob/master/prestiges/README.md)
- [Brawlify CDN repository](https://github.com/Brawlify/CDN/tree/master/prestiges)
