# BrawlBuddy

BrawlBuddy is a Python-first Brawl Stars progression companion. It connects a player tag to the official Brawl Stars API, displays the real public profile and brawler collection, tracks manually entered resources locally, and provides transparent per-brawler account-readiness guidance. A polished, clearly labeled demo works without credentials.

It uses versioned upgrade prices and transparent readiness calculations. Buffie Gem totals use category-specific prices, and unknown Claw pools are labeled as estimates; readiness does not represent skill, win rate, or measured meta strength.

## What is included

- distinct responsive Overview, Brawlers, Resources, and brawler-detail pages;
- local original profile and Surge guide artwork with remote fan-kit/CDN images where available;
- official player-tag lookup and conservative response parsing;
- brawler cards and compact table mode with search, exact Power 1–11 filters, equipment ownership filters, and sorting;
- official API-backed permanent Brawler Prestige, Total Prestige, progression filters, and Brawler-specific Prestige emblems;
- a Surge guide with official-release-note sources, combat usage, power ladder, equipment ownership, and a rule-based readiness plan;
- calculated Brawler Readiness with overall/category donuts, exact Power and equipment costs, category-specific direct-Gem Buffie prices, and a separate duplicate-protected Claw alternative;
- manual coin, Power Point, gem, credit, and bling inventory stored in SQLite;
- explicit `OFFICIAL_API`, `USER_INPUT`, `CALCULATED`, and `DEMO` provenance;
- short player cache, retry/backoff, timeouts, and useful API errors;
- demo mode with unmistakable sample-data labels;
- generated OpenAPI documentation at `/docs`;
- unit tests for tag validation, missing API fields, parsing, and local persistence.

See [docs/architecture.md](docs/architecture.md) for API capabilities, limitations, design decisions, recommendation boundaries, and the development roadmap.

See [docs/readiness.md](docs/readiness.md) for the readiness model, price configuration, ownership matching, and Claw pool assumptions. Standard Buffie prices are 149/179/199 Gems for Gadget/Star/Hyper Buffies; maintained offers can override them.

Claw routes use the released three-Brawler trios in `data/buffies_db.json`, subtracting owned gameplay Buffies across all three members from the nine-reward machine. The upper comparison shows the collection counts and calculates costs and odds from the eligible remaining rewards.

## Prerequisites

- Python 3.12 or newer
- a Brawl Stars developer API token for live lookup (optional for demo mode)

## Supercell API setup

1. Sign in at <https://developer.brawlstars.com/>.
2. Create an API key for the public IP address of the computer running BrawlBuddy.
3. Copy `.env.example` to `.env`, or set `BRAWL_STARS_API_TOKEN` in the shell that starts the app.

The application reads the token only on the server. It is not placed in YAML, returned by an endpoint, logged, or sent to the browser. Official API keys are IP-restricted; if your public IP changes, create/update the key in the developer portal.

## Install and run

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:BRAWL_STARS_API_TOKEN = "your-token"
python -m app
```

Open <http://127.0.0.1:8000>. Without a token, the demo still loads and live lookup explains what is missing.

## Configuration

Runtime behavior lives in `config/config.yaml`. Secrets use environment variables.

Supported overrides:

```text
BRAWL_STARS_API_TOKEN
BRAWL_ADVISOR_DEMO_MODE
BRAWL_ADVISOR_DEBUG
BRAWL_ADVISOR_HOST
BRAWL_ADVISOR_PORT
```

## Entering a player tag

Select **Connect account** and enter the tag shown beneath the player's in-game name. The leading `#` is optional. Input is normalized and validated before any external request.

## Manual resources

Coins and other balances are not treated as official public player data. Enter them in **Your resources** and select **Save resources**. Values are stored in `data/brawl_advisor.db`, keyed by normalized player tag. This database is ignored by Git.

## Recommendation algorithm

Not implemented in this milestone. The planned deterministic engine will score independent factors (verified meta strength, marginal upgrade value, resource efficiency, roster gap, and versatility), expose each factor contribution, attach evidence and freshness, and calculate confidence from data completeness/quality. See the architecture document for the boundary.

## Updating metadata

Power, equipment, Buffie pricing, readiness weights, and Claw settings live in `config/readiness.json`. Maintain prices against published game information and current offers, update the configuration version, and run the readiness tests when changing economy data. See [docs/readiness.md](docs/readiness.md) for supported overrides and pool definitions.

Refresh the lightweight Brawlify Prestige availability manifest without downloading duplicate artwork:

```powershell
python scripts/sync_prestige_assets.py
```

See [docs/prestige.md](docs/prestige.md) for the official rules, API semantics, fallback behavior, and exact CDN mapping.

## Testing

```powershell
python -m pytest
```

Manual smoke checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/demo/player
```

## Known limitations

- Live lookup requires a valid, IP-authorized official API token.
- The public player API is not a private inventory ledger, so spendable resources are manual.
- Demo brawlers are a small illustrative sample, not a current full-account or meta dataset.
- Brawler artwork is represented by generated lettermarks until an authorized, maintainable asset source is selected.
- SQLite currently stores resources only; profile history and metadata snapshots follow in later phases.

## Future roadmap

Verified upgrade costs → affordability and upgrade paths → deterministic recommendation engine → current meta snapshots → compliant community evidence → advanced what-if planner → native mobile clients consuming the same REST API.

This project is not affiliated with, endorsed, sponsored, or specifically approved by Supercell.
