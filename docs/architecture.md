# BrawlBuddy architecture

## Scope and milestone

This repository implements the first useful vertical slice: enter a Brawl Stars player tag, retrieve the player's public account from the official API, and present the profile and brawler inventory in a polished responsive dashboard. It also stores manually entered resources locally because the official player response does not provide spendable account balances.

The presentation now has route-specific Overview, Brawlers, Resources, and brawler-detail experiences. Generated local artwork provides reliable visual fallbacks; optional Brawlify CDN URLs map official numeric IDs to fan-kit/game imagery when that asset host is reachable. The UI includes Supercell's required unofficial fan-content notice.

Recommendation scoring, upgrade costs, live meta, and community collection are deliberately not presented as complete. They require independently verified, versioned game metadata and source-compliant collectors. The UI calls this out instead of showing invented scores.

## Technology choices

- **FastAPI** provides the REST boundary, validation integration, async request lifecycle, and OpenAPI documentation. A future web, Android, or iOS client can reuse the same endpoints.
- **Pydantic v2** provides typed configuration and domain validation.
- **httpx.AsyncClient** provides a single async official API client with timeouts, bounded retries, rate-limit handling, and bearer authentication.
- **truststore** keeps TLS verification enabled while using the native Windows certificate store, including organization-managed certificate authorities.
- **SQLite via the Python standard library** stores manual resources without introducing an ORM for one small table. SQL and constraints remain portable enough to replace with PostgreSQL when persistence expands.
- **Static HTML/CSS and a small JavaScript client** keep presentation independent from the Python domain layer and give full control over the responsive visual system. The browser never receives the API token.
- **YAML configuration plus environment secrets** keeps behavioral configuration readable while excluding credentials from source control.

NiceGUI was evaluated. It is productive and is built on FastAPI, but its server-driven UI and real-time connection add coupling that does not improve this initial read-oriented dashboard. FastAPI plus a thin web client gives the cleanest future mobile boundary. Native mobile apps should consume the REST API; they should not embed the web dashboard.

## Runtime architecture

```text
Browser UI
    ↓ JSON over /api
FastAPI routes
    ↓
PlayerService ───────────── ResourceService
    ↓                              ↓
BrawlStarsClient                 SQLite
    ↓
Official Brawl Stars API
```

The domain and service modules do not import UI code. Future recommendation code belongs in `app/scoring` and `app/services` and should receive typed domain objects rather than browser state.

## Official data source

The official developer portal is the authority for API access and credentials: <https://developer.brawlstars.com/>. The application uses the documented player endpoint under `https://api.brawlstars.com/v1` and percent-encodes the leading `#` in a validated player tag. The client can also support the official brawler catalogue endpoint without duplicating HTTP logic.

The parser consumes only fields present in the player response:

- player tag and name;
- name color and icon ID when present;
- trophies and highest trophies;
- experience level/points when present;
- 3v3, solo, and duo victories;
- club summary when present;
- unlocked brawlers, power, rank, trophies, highest trophies, and equipment arrays when returned.

Unknown response fields are ignored. Optional fields default safely; they are not synthesized.

### Official API limitations relevant to this product

The public player response is not a complete private inventory ledger. In particular, this application does not treat coins, Power Points, gems, credits, bling, progression income, purchase history, or exact upgrade affordability as official player fields. These values are user input until an official supported source exists. The official brawler catalogue is not sufficient on its own to establish current upgrade costs, meta strength, map performance, or build quality.

Official API tokens are created through the developer portal and are IP-restricted. A token may work locally and fail after the caller's public IP changes. This is translated into a useful authentication error.

## Data provenance

`DataSource` defines the product-wide classifications:

- `OFFICIAL_API`
- `USER_INPUT`
- `STATIC_GAME_DATA`
- `COMMUNITY_SOURCE`
- `CALCULATED`
- `INFERRED`
- `DEMO`

Player profiles and brawler rows carry their provenance. Resource rows are user input. Derived analytics are returned in a separate `analytics` object. Demo data is explicitly marked `DEMO` in both the model and UI.

## Domain model

The initial typed model includes:

- `PlayerProfile`
- `ClubSummary`
- `PlayerBrawler`
- `EquipmentItem`
- `PlayerResources`
- `DataSource`

Recommendation types are postponed until the verified cost and meta inputs exist. This prevents premature models from quietly becoming a fictional contract.

## Cache and resilience

Player responses use a small in-memory TTL cache (three minutes by default). Static brawler data can use a longer TTL when that flow is added. External requests have a configurable timeout, up to three attempts, exponential backoff for transient failures, and bounded handling of `Retry-After`.

Failures are translated into stable error codes for invalid tags, missing credentials, player-not-found, authentication/IP restriction, rate limiting, and upstream failure. No token or authorization header is logged.

## Planned recommendation design

The deterministic engine will remain independent of API and UI modules:

```text
PlayerProfile + PlayerResources
        + versioned UpgradeMetadata
        + versioned MetaSnapshot
                    ↓
            RecommendationEngine
                    ↓
Recommendation(score, confidence, factors, evidence, resource delta)
```

Each factor will emit a normalized contribution and evidence record. The weighted total will therefore be debuggable rather than a black box. No recommendation should ship until upgrade costs have source, effective date/game version, validation, and tests.

## Project structure

```text
app/
  clients/       official external clients
  core/          typed settings and shared errors
  models/        provenance-aware domain models
  services/      use cases and local persistence
  ui/            presentation assets only
config/          human-readable behavior
data/            demo input and ignored local SQLite database
docs/            architecture and source decisions
tests/           meaningful validation and persistence tests
```

## Development phases

1. **Foundation (implemented):** player-tag validation, official lookup, typed parsing, demo mode, responsive dashboard, brawler search/sort/filter, manual resources, cache, errors, tests.
2. **Verified upgrade metadata:** versioned brawler catalogue and upgrade costs, metadata validation, marginal upgrade steps.
3. **Resource planner:** affordability, paths, budget optimization, remaining resources.
4. **Recommendation engine V1:** deterministic meta, efficiency, current level, roster coverage, and versatility factors with debug breakdowns.
5. **Current meta:** official balance notes, permitted statistics, maps/modes, versioned snapshots, freshness.
6. **Community intelligence:** API/RSS/permitted connectors, normalized source signals, reliability, context, time decay, confidence.
7. **Advanced planning and polish:** scenarios, time estimates only when progression inputs exist, recommendation history, accessibility and richer artwork from an authorized asset source.

At every phase the existing REST boundary stays stable enough for a future native mobile client.
