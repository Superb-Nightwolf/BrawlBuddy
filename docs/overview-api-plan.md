# Overview API inventory and plan

Verified on 7 October 2026 using this project's configured credentials against the official Brawl Stars API

This inventory combines direct live response inspection with the current BrawlBuddy client, parsers, models, and UI

Field availability can differ by account or mode — an absent field must be displayed as unavailable rather than replaced with a fictional record

Official developer reference: <https://developer.brawlstars.com/#/documentation>

## Official endpoints and current integration

All paths below are relative to `https://api.brawlstars.com/v1`

| Endpoint | What it returns | Current BrawlBuddy integration |
|---|---|---|
| `GET /players/{playerTag}` | Public profile, Ranked summary, Fame, owned brawlers and equipment | Connected, with Ranked, Fame, streak and skin fields preserved |
| `GET /players/{playerTag}/battlelog` | Recent battle entries with mode-specific results and participants | Connected |
| `GET /clubs/{clubTag}` | Club profile and member roster | Connected |
| `GET /clubs/{clubTag}/members` | Club member list | Verified live, separate endpoint not connected |
| `GET /brawlers` | Brawler catalogue and available equipment identifiers | Connected |
| `GET /brawlers/{brawlerId}` | A single brawler catalogue entry | Verified live, not connected |
| `GET /events/rotation` | Event slots, maps, modes, modifiers and schedule | Connected, including official slot IDs and nested modifiers |
| `GET /rankings/{countryCode}/players` | Global or country trophy leaderboard | Connected |
| `GET /rankings/{countryCode}/clubs` | Global or country club trophy leaderboard | Connected |
| `GET /rankings/{countryCode}/brawlers/{brawlerId}` | Global or country trophy leaderboard for one brawler | Verified live, not connected |

This is the useful public endpoint set for our dashboard, not a claim that every developer-portal operation is listed here

Tags need their leading `#` encoded as `%23` in requests

## Player profile fields

| Area | Official response fields | Overview use |
|---|---|---|
| Identity | `tag`, `name`, `nameColor`, `icon.id` | Account header, player icon and tag |
| Account trophies | `trophies`, `highestTrophies` | Current total, personal best, gap to best |
| Total Prestige | `totalPrestigeLevel` | Permanent account progression card |
| Experience | `expLevel`, `expPoints` | Secondary profile information |
| Victory counters | `3vs3Victories`, `soloVictories`, `duoVictories` | Lifetime recorded victories and victory composition |
| Championship status | `isQualifiedFromChampionshipChallenge` | Qualification status when applicable |
| Legacy PvE records | `bestRoboRumbleTime`, `bestTimeAsBigBrawler` | Optional records drawer, only if meaningful data exists |
| Club summary | `club.tag`, `club.name` | Club card and link to full roster |
| Fame | `fame`, `fameTierName` | Fame amount and published tier label |
| Current Ranked season | `rankedSeasonId`, `rankedRank`, `rankedRankName`, `rankedElo` | Current official rank and rating |
| Season Ranked best | `highestSeasonRankedRank`, `highestSeasonRankedRankName`, `highestSeasonRankedElo` | Highest rank and rating for the returned season |
| All-time Ranked best | `highestAllTimeRankedRank`, `highestAllTimeRankedRankName`, `highestAllTimeRankedElo` | Personal Ranked record |
| Owned collection | `brawlers[]` | Roster and progression summaries |

**Now preserved by the player parser and displayed in Overview:** Fame fields, all current/season/all-time Ranked fields, per-brawler win streaks, and the returned skin object

The current parser also accepts legacy `highestPowerPlayPoints`, but that field was absent in the inspected live response

Do not substitute old Power Play points for modern Ranked Elo

Fame is a profile progression value, not spendable Credits

Ranked numerical rank codes should use their official accompanying name rather than a guessed tier mapping

## Per-brawler fields

| Area | Official fields | What we can show |
|---|---|---|
| Identity | `id`, `name` | Stable catalogue matching and artwork lookup |
| Power | `power` | Current Power and Power distribution |
| Trophies | `trophies`, `highestTrophies` | Current trophies, personal best and trophy gaps |
| Permanent Prestige | `prestigeLevel` | Official Prestige and collection distribution |
| Legacy progression | `rank` | Retain internally, prefer current Prestige for current-facing progression |
| Gadgets | `gadgets[]` with `id`, `name` | Owned Gadgets and missing ownership when compared with catalogue |
| Star Powers | `starPowers[]` with `id`, `name` | Owned Star Powers and missing ownership |
| Gears | `gears[]` with equipment identifiers and supplied metadata | Owned Gears and build gaps |
| Hypercharges | `hyperCharges[]` with `id`, `name` | Owned base Hypercharge, including ownership below Power 11 |
| Buffies | `buffies.gadget`, `buffies.starPower`, `buffies.hyperCharge` | Three separate ownership flags |
| Win streaks | `currentWinStreak`, `maxWinStreak` | Current and record streak per brawler |
| Skin | `skin.id`, `skin.name` | The skin returned for the brawler |

The skin object is not a complete owned-skin inventory

Owned equipment arrays do not establish which Gadget, Star Power or Gear is currently selected for play

A Hypercharge Buffie flag is separate from ownership of the base Hypercharge

The existing app distinguishes an owned Hypercharge usable at Power 11 from an owned Hypercharge stored below Power 11

When an equipment field is missing, retain a known/unknown distinction rather than automatically treating it as confirmed unowned

## Catalogue, battles, clubs and events

The live catalogue returned **108 brawlers at verification time** with `id`, `name`, `gadgets`, `starPowers`, `gears` and `hyperCharges`

Use the actual fresh catalogue length for completion denominators — never hardcode 108 as a lasting game total

The official catalogue does not directly supply our rarity/class artwork system, ability descriptions, attack damage tables, upgrade prices or meta rankings

Battle log entries can contain:

- `battleTime` and `event` information including map and mode
- Battle `mode`, `type`, `result`, `duration` and `starPlayer`
- Teams or players with tags, names and brawler snapshots
- Mode-dependent placement and trophy-change fields when actually supplied

The inspected recent battles contained `duration`, `mode`, `result`, `starPlayer`, `teams` and `type`

Do not promise trophy-change or placement data on every match

The recent battle window is bounded and mode-dependent, not a lifetime archive

It does not provide a complete movement replay or guaranteed damage, healing, kills, deaths, selected builds, or draft history for our Overview

Club responses can supply `tag`, `name`, `description` when present, `type`, `badgeId`, `requiredTrophies`, `trophies`, `isFamilyFriendly` and `members`

Member fields verified live were `tag`, `name`, `nameColor`, `icon`, `role` and `trophies`

The sample club omitted `description` — the UI needs an unavailable state rather than invented club copy

Event rotation fields verified live were `slotId`, `startTime`, `endTime` and `event`

The nested event contained `id`, `map`, `mode`, `modeId` and `modifiers`

Countdowns can be calculated from `endTime`, while map images and map recommendations need other metadata

Leaderboards give ranked lists, not a search endpoint for every player's exact global position or a population distribution for exact percentiles

## Calculations possible from a single profile

| Metric | Calculation | Inputs or conditions |
|---|---|---|
| Unlocked and locked brawlers | Owned IDs intersect catalogue IDs, then catalogue minus owned | Fresh official catalogue |
| Collection completion | Unlocked catalogue brawlers / catalogue total × 100 | Dynamic denominator |
| Average Power | Sum of owned brawler Power / owned count | Empty account handled |
| Power distribution | Count at each Power from 1 through 11 | Owned profile |
| Max-Power percentage | Power 11 count / owned count × 100 | Label denominator clearly |
| Gadget and Star Power coverage | Count brawlers owning at least one of the category | Count brawlers once, separately show item totals |
| Equipment collection completion | Owned valid item IDs / available item IDs | Exact applicable equipment catalogue |
| Base Hypercharges owned | Count brawlers with a returned base Hypercharge | Do not use Buffie flags as proxy |
| Active versus stored Hypercharges | Owned at Power 11 versus owned below Power 11 | Current use rules |
| Buffie ownership | Count true flags per category and distinct Buffied brawlers | Separate availability metadata for denominators |
| Prestige distribution | Count per official Prestige level | Preserve official versus inferred source |
| Highest-trophy brawlers | Sort by current or highest trophies | Label which sort is used |
| Trophy concentration | Top N owned brawler trophies / roster trophy sum × 100 | Measures roster concentration, not skill |
| Gap to personal best | `max(0, highestTrophies - trophies)` | For account or brawler |
| Victory composition | Category victory counter / sum of the three victory counters × 100 | Not a lifetime win rate |
| Current longest streak | Maximum returned `currentWinStreak` | Display associated brawler |
| Best recorded streak | Maximum returned `maxWinStreak` | Display associated brawler |
| Ranked gap to season best | `max(0, highestSeasonRankedElo - rankedElo)` | Same official season |
| Closest next milestone | Target trophies minus current progression under verified rules | Versioned milestone rules |

Profile victory totals do not include lifetime losses or total matches, so lifetime win rate cannot be calculated

Trophy and Prestige milestone targets need maintained game rules or a clearly labeled user target

## Calculations that need additional data

| Metric | Extra input | Interpretation |
|---|---|---|
| Recent win rate | Latest real battle log | Victories / (victories + defeats), with draws shown separately |
| Recent mode or brawler performance | Recent log grouped by mode or own brawler ID | Always show sample size and time window |
| Recent Star Player count | Returned Star Player matching connected player tag | Restrict to applicable modes |
| Recent trophy movement | Sum supplied trophy-change values | Only matches where changes are available |
| Recent playtime | Sum supplied battle durations | Excludes queue, menus and missing durations |
| Recent mode usage | Count sampled battles by mode | Recent sample, not lifetime preference |
| Team Power comparison | Team brawler Power snapshots | Describes Power difference, not predicted winner |
| Club position | Sort club member trophies | Exact within returned club roster |
| Club trophy contribution | Player trophies / returned club trophies × 100 | Same observation window where possible |
| Club capacity | Member count versus current maximum | Maintained capacity rule |
| Class and rarity coverage | Maintained brawler class/rarity catalogue | Not returned by the official brawler list |
| Build readiness | Profile ownership + exact chosen build + unlock rules | Custom progression score, not official skill |
| Remaining upgrade cost | Power + missing equipment + maintained prices | Coins, Power Points and Gems kept separate |
| Affordable next upgrades | Upgrade costs + manually entered balances | Resource input freshness must be visible |
| Best brawlers for today's maps | Event rotation + maintained recommendations + ownership | Curated guidance, not an official API meta ranking |
| Account change over days or weeks | Persisted profile snapshots | Start collecting prospectively |
| Full match trend | Persisted, deduplicated observed battles | API does not backfill full lifetime history |
| Ranked season history | Stored season snapshots or another verified source | Current profile is only a summary |

Showdown placement should remain placement unless we explicitly define and label a success threshold

Recent win rates should not mix demos with live matches or silently turn missing results into defeats

## Information we cannot automatically obtain for this panel

- Spendable Coins, Power Points, Gems, Credits and Bling
- Complete skin/cosmetic inventory, purchase history and transaction prices
- Brawl Pass tier, quest progress, private inbox, friends or chat history from the inspected endpoint set
- Full lifetime losses, match history, account creation date or exact time played
- Guaranteed per-match combat statistics, actual positioning replay, selected equipment and full draft details
- Verified global meta, matchup win rates, best builds or damage tables from player/catalogue responses alone
- Exact account upgrade affordability without balance input and maintained prices
- Exact worldwide percentile or exact global rank for a player absent from the returned leaderboard slice

## Recommended Overview structure

### Row 1 — Player identity and official account stats

Player name, icon, tag and club, with current trophies, highest trophies, Total Prestige and current Ranked tier/rating

Show the account source and fetch timestamp

### Row 2 — Roster progression

Unlocked versus total catalogue, Power 11 count, Power distribution and ownership coverage for Gadgets, Star Powers, Gears, Hypercharges and Buffies

Cards link to the corresponding roster filter

### Row 3 — Next goals

Three practical goals selected with explicit rules, for example a stored Hypercharge brawler approaching Power 11, a chosen build missing one item, or a brawler near its next verified Prestige milestone

Attach exact missing requirements and known costs

Use resource balances only after the user has supplied them

### Row 4 — Recent performance

Recent W/L/D, sampled win rate, most-used brawler and mode, Star Player count and latest matches

Show sample size and window — hide the win-rate card if there are no applicable result-bearing matches

### Row 5 — Personal records and live context

Ranked season/all-time best, Fame, win streak record, highest-trophy brawlers, club summary and event countdowns

Keep these compact or expandable so Overview stays focused on account progression and useful next actions

## Original implementation checklist

1. Extend the player and brawler models/parsers to preserve live Fame, Ranked, streak and skin fields
2. Preserve field availability so a missing API field is not displayed as a confirmed zero or unowned item
3. Replace fixed catalogue/equipment completion assumptions with current applicable metadata
4. Remove invented trophy-derived league labels — `prestige_tier` currently maps trophies to labels such as Masters League, which are not the official Ranked result
5. Remove fallback records such as 1,250 Power Play points, Insane XVI, 3m 15s and Level 186 from live-account displays
6. Label highest-trophy brawlers as such — `top_loadouts` currently picks the first owned Gadget and Star Power, which does not prove the player uses that build
7. Correct the events parser to read `slotId` and nested `event.modifiers`, and retain `modeId`
8. Give Overview event and battle caches suitable expiry and refresh behavior — now refreshed after 60 seconds and cleared by the dashboard Refresh action
9. Keep official rotation data separate from hardcoded map picks and curated meta inputs
10. Persist profile and battle observations only when implementing historical charts, with deduplication and coverage labels

The redesigned Overview now implements items 1–9 for the data it displays — existing legacy analytics aliases remain for compatibility but are no longer used to present fake leagues or records

Historical snapshot storage in item 10 remains a future addition — the dashboard only charts available profile and recent-battle data

## Suggested implementation order

1. Extend and verify the API data contract
2. Replace unsupported Overview fallbacks with real values or unavailable states
3. Build account header and roster progression cards
4. Add Ranked/Fame/streak records
5. Add recent performance with correct sample labeling
6. Add practical next goals using existing readiness calculations
7. Add historical charts after sufficient observations have accumulated
