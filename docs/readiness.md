# Brawler readiness

The detail page uses `ReadinessService` through
`POST /api/brawlers/{id}/readiness`. The browser supplies its already-loaded
inventory; the server resolves the recommended build from the guide. This
endpoint calculates a plan and does not buy items or change inventory.

The overall and category rings, item statuses, individual costs, direct Gem
budget, and Claw estimates consume that result. No economy calculations are
duplicated in the browser. Combat Kit and Readiness keep equal desktop widths;
the full breakdown sits underneath, with a stacked layout on phones.

The server returns Power, recommended-build, and gameplay-Buffie subtotals in
`costs.subtotals`. Both requirements tables share the same item, status, and
resource layout. The compact Readiness totals omit the repeated Claw trio;
the full planning comparison retains its portraits and ownership icons.
On desktop, the full comparison places Direct Gems beside the three Claw
scenarios and presents the trio in a compact row underneath. Scenario amounts
use the same number size as the direct totals. Requirements tables use
proportional columns, centered statuses, and centered Power Point values.
Totals explanations appear in their information buttons. The Claw alternative
stays expanded, including an availability message when no pulls apply.

The five category circles show Power Level, Gears, Gadget + Star Power,
Hypercharge, and Buffies in that order. `categoryProgress` provides separate
owned counts and percentages for Gears, the recommended Gadget/Star Power
pair, and Hypercharge. Unavailable categories show no percentage. The combined
`progress.build` field remains available for clients using the earlier model.

## Central configuration

`config/readiness.json` contains the versioned Power upgrade table, equipment
prices/unlock levels, Gear IDs/rarities/availability, scoring weights, default
Buffie Gem price, and Claw costs/pools. Restart the server after editing it.
The roster upgrade calculator uses the same Power cost table.

The upgrade table supplied in the feature specification totals 3,740 Power
Points and 7,765 Coins from Power 1 to 11. Remaining costs sum only the
transitions after the current level. Gear prices use the configured rarity or
an item-specific `coins` override. Set a Gear's `enabled` to false to remove it,
or set `brawlerIds` to restrict it. `removedWithBuffies` excludes affected Epic
and Mythic Gears when Buffies are released for that Brawler.

Recommended Gadget, Star Power, and Gear ownership are matched by numeric ID.
Names resolve the curated recommendation to its catalog ID; matching an owned
name or an arbitrary item in the category does not satisfy the requirement.
There is one base Hypercharge per Brawler, so its Brawler-scoped ownership array
is used. A Hyper Buffie does not imply base Hypercharge ownership. Stored owned
items incur no purchase cost, and their activation Power is displayed.

Set a maintained direct Gem price as follows:

```json
{
  "directGemPrices": {
    "16000005": {
      "gadget": {"gems": 99, "estimated": false}
    }
  }
}
```

Put this inside the `buffie` object. The 99 value is an illustrative offer
override, not a verified current offer. Brawler-specific prices override
`directGemPricesByCategory`, which supplies standard prices: **149 Gems for
Gadget Buffies, 179 for Star Buffies, and 199 for Hyper Buffies**. These prices
were cross-checked on October 2, 2026 against the [Brawl Stars Wiki cost table](https://brawlstars.fandom.com/wiki/Buffies)
and [BrawlMetrics](https://brawlmetrics.gg/news/brawl-stars-buffies). Supercell's
support page confirms direct Gem purchasing but does not publish this table.
Limited-time offers can differ; prices remain centrally configurable.

The legacy `defaultDirectGemPrice` of 300 is only an estimated fallback if a
category price is removed and no Brawler override exists. Gem totals display
whole amounts calculated from the configured prices. The readiness “i” button
shows the calculation explanation, category prices, and source links in the
same small-button, dark-tooltip style as Matchups & Teammates. It supports
hover, keyboard focus, and click; outside clicks and Escape dismiss it. The
tooltip adapts its position and height to fit the viewport on phones.
Cosmetic/Bling Buffies never affect readiness or costs.

## Scoring

Power progress is `min(currentPower / targetPower, 1)`. Build progress is the
owned fraction of applicable recommended items. Buffie progress is the owned
fraction of applicable gameplay Buffies. Overall readiness combines Power,
Gadget, Star Power, Gears, Hypercharge, and Buffie fractions using their
configured weights (initially 40, 10, 15, 15, 10, 10).

Unavailable components are removed from the denominator. Missing guide or
price information marks resource totals as partial rather than assigning
invented items or prices. Unowned Brawlers show a post-unlock cost preview and
no personal percentage; their unlock cost is not included. Readiness measures
the build inventory, not skill or an empirical competitive rating.

The specification's example percentages are illustrative: the described
Power-8 inventory has two of five recommended build items owned, not three.
With the specified weights and one of three Buffies owned, its calculated
overall readiness is 49.9%, its Power progress is 72.7%, and Build progress is
40%. With the updated category prices, its resource budget is 2,880 PP,
13,925 Coins, and 378 Gems (179 + 199 for its two missing Buffies).
The tests lock down these calculations.

## Claw Machine alternative

The total cards show the direct Gem route, followed by an **OR** comparison
with Claw Machine routes when gameplay Buffies are missing. The Claw best,
average, and worst cards use `buffieClawAlternative.totalToMaxReady`: existing
Power/build requirements plus that scenario's Claw Power Points and Coins,
with zero Gems. These are alternative budgets, never combined with the direct
Gem purchase. Changing the remaining reward count updates both comparisons.

For `K` desired rewards in a uniform remaining pool of `N` unique gameplay
rewards, minimum pulls are `K`, expected pulls are `K × (N + 1) / (K + 1)`, and
maximum pulls are `N` (zero when `K = 0`). The chance of any desired Buffie next
pull is `K / N`; a particular desired Buffie's chance is `1 / N`. Expected
The probability of collecting all desired rewards in the best-case `K` pulls
is `1 / C(N, K)`; collecting them by `N` pulls has probability 1 under this
model. These completion probabilities differ from the next-pull probability.
The average scenario shows expected cost without assigning a completion
probability to fractional expected pulls. Reference pools remain explicitly
labeled as estimates in the total cards.
The Claw route has its own matching “i” tooltip for the next-pull probability,
pool assumptions, and explanation of what the route totals include. These
details update with the pool input and remain outside the price-card layout.

Expected costs retain their decimal values in the service. These are exposure estimates,
not guarantees, and assume each eligible remaining reward is equally likely.

The maintained `data/buffies_db.json` catalog defines the nine released trios,
each containing three Brawlers and nine gameplay rewards. The service resolves
their Brawler IDs, then subtracts the loaded player's owned Buffies across
**all three members**, including stored Buffies at low Power. Buffies owned
outside this trio do not change its pool. Locked-Brawler rewards are excluded
from eligible pulls and tracked separately from unowned rewards.

`buffieClawAlternative.group` contains the full nine-reward total, owned,
missing, eligible remaining, excluded, and per-member category ownership.
The upper route cards display these counts and use that eligible remaining
count for best/average/worst costs and odds. The visible "Claw Machine group"
shows all three members with their real Gadget, Star Power, and Hypercharge
Buffie artwork: colored when owned, grayscale when missing or locked. Both
route headings share the same size, weight, color, and spacing.
For example, Shelly owns one,
Colt owns one, and Spike owns two: four of nine are collected and five remain.
Spike's one missing Buffie then has a 20% next-pull chance and at most five
pulls. All trio pages share the same pool, with their own target counts.
The manual reward-count form is hidden for catalog-derived trios.

For a Brawler with no maintained trio or configured machine, the nine-reward
reference pool remains an explicitly labeled fallback estimate. Only this
fallback subtracts the selected Brawler's recorded gameplay Buffies. The
player can enter the actual remaining reward count under **Claw Machine
Alternative**. Manual overrides expire when Buffie inventory changes, and
do not persist or overwrite inventory.

To override catalog membership with a separately maintained machine, configure
`buffie.claw.pools`:

```json
[
  {
    "name": "Example machine — replace with verified membership",
    "rewards": [
      {"brawlerId": 16000000, "category": "gadget"},
      {"brawlerId": 16000000, "category": "star_power"},
      {"brawlerId": 16000000, "category": "hypercharge"}
    ]
  }
]
```

Supply every gameplay reward in the actual machine. The service removes
rewards for locked Brawlers, unavailable categories, and all already-owned
rewards across the loaded roster. Duplicate entries do not increase the pool.
If a configured machine lacks a desired reward, it does not claim a guarantee
of collecting all target Buffies. A manual remaining-count override takes
precedence over configured/reference pools.

## Sources and verification

Checked on 2026-10-02:

- [Supercell Gear prices and unlock slots](https://support.supercell.com/brawl-stars/en/articles/gears-8.html).
- [Supercell April 2026 release notes: one three-Brawler trio per Buffie machine](https://supercell.com/en/games/brawlstars/blog/release-notes/release-notes-april-2026/).
- [Supercell Buffie eligibility and direct purchase](https://support.supercell.com/brawl-stars/en/articles/buffies.html).
- [Supercell Claw duplicate protection and reference drop chance](https://support.supercell.com/brawl-stars/en/articles/buffie-claw-machine-drop-chances-3.html).
- [Supercell Claw costs and special-Gear removal](https://supercell.com/en/games/brawlstars/blog/news/new-power-brawl-pass-changes-and-a-new-starr-drop-2/).

Supercell's older launch article discussed 18-reward machines, while the
current support drop-chance page lists 11.11% for a non-Bling Buffie. Neither
establishes the precise remaining pool for an individual account, which is
why actual maintained/input pool data takes precedence.

Run `python -m pytest -q` and syntax-check both `app.js` and `readiness.js` with
Node. Readiness tests cover costs, ID matching, stored items, unavailable
components, pricing overrides, removed Gears, complete and preview states,
account-wide reward removal, input validation, and all catalog guides. Claw
expectations are also compared with every possible arrangement of target
positions in small unique pools.
