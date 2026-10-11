# ML integration and review — feature/__0.0.10

Reviewed on 12 October 2026. The local `ml` branch was renamed to `feature/__0.0.10` and merged with `feature/brawlbuddy_v0.0.9`. Design commit `74c6fdb` remains isolated on 0.0.9. The merge preserves the dashboard, club-navigation fix and page designs; the integrated branch adds and repairs the AI Meta section.

## What the ML system actually does

| Stage | Inputs | Work and output |
| --- | --- | --- |
| Player discovery | Global/regional player rankings, club rankings/rosters, brawler rankings and battle participants | Builds a persistent pool of player tags. Discovery is bounded by regional lists and a 5,000-player cascade batch; reaching a requested target is not guaranteed. |
| Collection | Recent battle logs for selected players | Throttles requests, derives source-relative team outcomes, creates stable match fingerprints and discovers additional participants. Logs are recent windows, not a complete historical dataset. |
| Storage | Matches, participant picks, player polling records | SQLite with WAL and indexed queries. Runtime data stays local and is ignored by Git. Repeated perspectives share a match fingerprint. Team order is canonicalized. |
| Outcome quality | Two teams, a tracked source player and victory/defeat | Labels both sides only when the source is located uniquely. Draws, missing sources, PvE and showdown placements have no inferred binary team outcome. Previously ingested labels are retained as legacy records and excluded until re-ingested. |
| Observed meta | Verified labeled participants under mode/map/type filters | Smoothed win rates, observed pick shares and relative tiers. The smoothing prior has weight 20. Coverage labels count observations; they are not calibrated confidence in winning. |
| Pair evidence | Verified same-team and opposing-team observations | A single grouped query loads directional pair evidence per draft, avoiding one database query per candidate/teammate/opponent. Pair and counter evidence respect the map filter. |
| Training | Complete labeled 3v3 matches with known power | Encodes ally picks, enemy picks, mode, map and power difference. Uses two perspectives per match. No post-match fields enter the feature matrix. |
| Validation | Earlier timestamps for folds, latest timestamps for final holdout | Keeps both perspectives and equal timestamps together. Uses expanding temporal folds. Each fold fits its own vocabulary and fresh estimator. Selects by mean validation log loss, never by the final test labels. |
| Model comparison | Logistic regression, random forest, histogram gradient boosting and soft voting; optional LightGBM/XGBoost | Fits installed frameworks with bounded CPU pools. Reports real accuracy, ROC-AUC, log loss and Brier score. The selected model can be the baseline; the UI does not assume an ensemble won. |
| Match prediction | Six known picks, supported map/mode and power difference | Uses the same symmetric probability calculation during evaluation and serving. Swapping teams complements the probability. Partial/unseen matchups receive a low-coverage neutral fallback, which the UI displays as awaiting coverage. |
| Draft ranking | Current draft, observed map performance, pair/counter evidence, optional owned roster | Uses a composite ranking score. Its weights are 45% model term, 35% observed win rate, 10% teammate evidence and 10% opposing-pick evidence. The model term is neutral for partial drafts. Scores are not win probabilities. |
| UI | Shared app catalog/player state and real ML responses | Meta picks, draft room, team combinations, connected roster, model/data audit and pipeline operations. Uses the existing pastel palette, 400px desktop cover, official portraits and shared hover/focus/click/Escape information controls. |

## Loops and gaps found and corrected

| Finding | Why it mattered | Change |
| --- | --- | --- |
| Shuffled stratified folds separated mirrored match rows | The validation fold could see the opposite view of its own match in training | Grouped chronological folds and holdout boundaries by unique timestamp; match perspectives remain together |
| Model selected using final holdout performance | Reported test quality participated in model selection | Select by temporal validation log loss; reserve latest-time holdout for reporting |
| Draws were stored as losses for both teams | Mirroring then invented a winner | Draw labels stay unknown and are excluded from binary training/meta wins |
| Source missing from teams still produced outcomes | Every opposing team could be labeled as a winner/loser incorrectly | Require a unique source team and exactly two teams |
| Showdown source rank labeled every participant | Other players inherited someone else's placement | No showdown binary team labels are inferred |
| Opposite team order on duplicate logs | Enrichment could attach outcomes to the wrong side | Canonicalize team order before persistence |
| Legacy data/model silently retained questionable labels and validation | Old performance could be presented as trustworthy after fixes | Add ingestion revision, retain legacy rows/files, exclude them from clean training/statistics, and serve only v3 artifacts |
| Missing timestamps merged unrelated entries and could repeat a whole player poll | Fingerprints lacked a reliable time identity; a bad entry could interrupt good entries | Reject malformed/missing timestamps, count skipped entries and continue polling valid entries |
| Synthetic showdown participants entered discovery | Repeated invalid polling could consume work | New missing tags use excluded unknown placeholders; underscore placeholders are excluded from the polling pool and batch discovery |
| High-priority players could starve older polled players | A repeated collection batch returned to the same priority group | Prioritize unpolled players, then oldest polling time, then priority |
| Discovery continued through credential/rate failures | Thousands of doomed requests could follow one systemic failure | Stop on credential errors or rate errors after client retries; preserve collected rows |
| Account trophy counts overwritten with brawler trophies | Discovery corrupted player-level metadata | Participant/brawler-ranking discovery supplies tags without substituting individual brawler trophies for account totals |
| Batch upserts counted existing tags as newly discovered | Progress overstated discovery | Return actual insert-count deltas; collection separates newly discovered and total players |
| Assumed six or ten participant slots | Mixed modes and missing participants distorted pick share | Use actual labeled participant counts |
| Map was mentioned but absent from features | Predictions implied map conditioning they did not implement | Add map vocabulary/features fitted within each training fold |
| Incomplete and unseen drafts received strong confidence | Missing features were treated as a supported composition | Reserve learned estimates for complete supported matchups; report uncalibrated estimates and neutral fallback explicitly |
| Drafts allowed duplicates, oversized teams and non-finite power values | Invalid compositions could produce arbitrary results | Validate team size, duplicates, identifier range, supported mode, power range and candidate limits |
| Owned filtering unpacked the player-service result incorrectly | It could silently recommend unowned brawlers | Correct tuple handling, require a connected tag and fail visibly when the collection cannot load; opponent suggestions are not limited by your collection |
| Empty map filter became a literal “Unknown Map” in draft queries | All-map suggestions had no evidence and fell back to zero-sample candidates | Preserve the absent map filter and offer only candidates observed under the selection |
| Pair/counter query nested inside every candidate loop | A single draft could open hundreds of SQLite connections | Load directional interaction evidence once per request |
| Retraining ran synchronously on the event loop | Page requests/status polling could stall | Background training in a worker thread, bounded CPU pools and one operation at a time |
| Training mutated the serving predictor | Requests could see changing vocabularies during retraining | Train a separate candidate and publish it only after success |
| Background tasks were untracked | Shutdown could abandon clients or writes | Track the operation task; stop collection on shutdown and allow training to finish; expose collection cancellation |
| Model writes were non-atomic | Readers could observe an incomplete artifact | Replace model/metadata files atomically after writing temporary files |
| UI hardcoded metrics, dataset counts and champion name | Missing data looked like successful evaluated ML | Render actual values or explicit empty states; remove the zero-leakage guarantee |
| Frontend used `window.state`, while app state is lexical | Roster/catalog information could appear unavailable | Read the shared app state correctly |
| Duplicate auto-initialization and unbounded polling | Repeated route visits created unnecessary loads and stale responses | One route-owned load, abort stale requests, serial polling, stop on route exit and pause network polling in hidden tabs |
| Tests relied on private local DB/model files | A fresh checkout could not reproduce checks | Temporary deterministic datasets and isolated predictors/endpoints; no live collection or production retraining inside tests |
| Dependency manifest declared only XGBoost | Fresh setup missed FastAPI, dataframe and training packages | Complete base dependencies, optional booster extras and regenerated lockfile |
| CLI training expected obsolete result keys/artifact names | Successful training could still fail when printing results | Match the real result schema and v3 artifact names; status inspection no longer requires a token |

## Verified local run

| Check | Result |
| --- | --- |
| Collection smoke run | 10 player logs, 247 entries, 244 new matches, 3 duplicates, 0 failed polls; approximately 5.5 seconds at 2 requests/second |
| Preserved dataset | 4,697 unique stored matches: 247 newly verified ingestions and 4,450 legacy records excluded from training/statistical outcomes |
| Eligible training data | 132 complete verified 3v3 matches, 264 mirrored observations |
| Temporal split | 105 earlier training matches and 27 latest-time holdout matches; 5 expanding temporal folds |
| Selection | Baseline logistic regression, validation log loss approximately 0.5379 |
| Selected model holdout | ROC-AUC approximately 0.7586; accuracy 70.4%. This is a small holdout, not a population accuracy claim. |
| Test suite | 185 tests passed; two upstream test-client deprecation warnings. JavaScript syntax and Git whitespace checks passed. |
| Browser | Actual 1280px viewport: cover measured 400px; no horizontal overflow. Shared ⓘ click and Escape, disabled duplicate draft options, observed team combinations, connected roster and real model metrics checked. Training launched from the UI without blocking navigation; the merged Leaderboards podium opened Heaven and loaded its club roster. |
| Server | Integrated branch on `http://127.0.0.1:8000/meta`; separate 0.0.9 design worktree remains on port 8001. |

A local SQLite backup was preserved in the ignored `data/models/pre-v3-data.db` before additional ingestion. Model artifacts, collected records, tokens and server logs are not committed.

## Remaining scientific and operational limits

- The collection favors leaderboard/club players, includes repeat players and covers a recent battle-log window. It is not representative of every skill level, region or patch. Chronological evaluation prevents mirrored-row/time leakage but does not establish performance on unseen players.
- The local verified sample is small. No fixed accuracy promise, independent audit certificate or calibrated confidence guarantee is made. A larger clean multi-day evaluation and explicit probability calibration are required before treating estimates as reliable competitive guidance.
- Compositions, mode, map and average power do not capture player skill, bans, pick order, equipment or positioning. Observed teammate/opponent associations are not causal synergy or counter proof.
- Recommendation weights are a documented heuristic, not a separately learned ranking model. Unsupported maps/drafts remain in an explicit fallback state instead of inventing coverage.
- These operations are designed for one local server worker. A shared durable job queue, operation authorization and cross-process locking are needed for an internet-hosted multi-worker control panel. In-flight jobs do not automatically resume after restart; saved data and polling records do.
- Discovery targets are goals, not guarantees. Re-running bounded discovery/collection grows the persistent pool. No mass 100,000-player collection was launched during this review.
- Desktop browser layout was verified. Phone breakpoint styles are supplied; no phone screenshot was taken in this run.

## Run a fresh checkout

```powershell
uv sync --locked --extra dev --extra boosters
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
uv run python scripts/run_collection.py --status
uv run python scripts/run_collection.py --collect --max-players 50 --rps 2
uv run python scripts/train_model.py
uv run pytest -q
```

The `boosters` extra is optional. Without it, training compares the installed core frameworks. For pip users, install `requirements.txt` (and `requirements-dev.txt` for tests); add LightGBM/XGBoost only if desired. A fresh checkout starts without private collected data or model files and shows useful empty states. Configure the game token locally for live collection.

Preview artifacts: [Meta cover](design-previews/meta-explorer.png) and [model/data panel](design-previews/meta-model-data.png).
