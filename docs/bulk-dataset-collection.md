# 100,000-player CSV collection

The worker targets **100,000 distinct selected player tags and 50 distinct source-observed matches per tag**. This is at most **5,000,000 player-match observations**, not five million independent matches. Matches shared by several sampled players are stored once, with separate source-relative observations. The current Meta database and model are not modified or retrained by this job.

## Sources and limits

Discovery visits the global and 46 regional account leaderboards, their top 100 club rosters, then global and regional brawler leaderboards as needed. If those sources are exhausted, it can expand through observed match participants. Sources are preserved in the tag CSV: `account_leaderboard`, `top_club:<tag>`, `brawler_leaderboard:<id>`, and `match_participant`. Brawler trophies are never stored as account trophies. Duplicate club requests and duplicate tags are skipped. This is a competitive sampling strategy, **not an official global top-100,000 ranking**.

A live probe returned 200 leaderboard entries and 25 battle-log entries, with an empty paging cursor. Fetching the same log twice does not provide 50 distinct matches. Players must play additional matches and be polled again. The worker repolls incomplete players after six hours, skips players at 50, and labels players with 12 consecutive unchanged successful polls as `stalled`. Missing accounts become `unavailable`. Neither status pretends the target was reached. Completed collection is reported only when all 100,000 players have 50 records; exhausted source/activity coverage is reported as `incomplete`.

The finite recent-history window means some battles can disappear between polls. This is a sample of captured matches, not guaranteed complete player history. Discovery is checkpointed by endpoint; a crash after storing a response but before its task completes can cause a harmless duplicate request on resume.

At 3 requests/second, 200,000 battle-log calls alone take at least **18.5 hours**. Discovery, latency, service retries, throttling, repeated unchanged logs and additional player activity add time. There is no reliable completion ETA. The rate is shared with any other activity using the same token; keep concurrent manual collection small.

## Files

All generated files are in `data/bulk-sample-100k/`, ignored by Git.

Watch the worker in the local **Meta → Pipeline** page: `http://127.0.0.1:8000/meta?section=pipeline`. The live panel checks the published report automatically, shows the latest polled tag and progress bars, and flags stale running reports. Its counts are separate from the model database shown in the manual pipeline below it. This read-only monitor does not control or interrupt the bulk worker.

| File | Contents |
|---|---|
| `players.csv` | During discovery: deduplicated candidates. After selection: exactly the available selected cohort, up to 100,000 tags. Includes name, known account trophies, discovery source/region, captured count, attempts and status. |
| `matches.csv.gz` | Unique match fingerprint, time, mode, map, type, first source tag, structural 3v3 eligibility and full original battle JSON. Standard UTF-8 CSV compressed with gzip. |
| `player_matches.csv.gz` | Player tag → match fingerprint, that player's result, trophy change, showdown placement and capture time. Standard UTF-8 CSV compressed with gzip. |
| `manifest.json` | Targets, counts, provenance/format notes and last full export time. |
| `progress.json` | Worker state and latest published counts; refreshed about every 30 seconds and on state transitions. |
| `checkpoint.sqlite` | Separate temporary deduplication, discovery tasks and restart checkpoints, with compressed raw responses. This is not `data/brawl_meta.db`. |
| `worker.stdout.log`, `worker.stderr.log` | Background worker progress and diagnostics; no credentials are exported. |

Player CSVs refresh about every 30 seconds; the compressed match snapshots refresh hourly and at orderly shutdown. Files are streamed to temporary files and atomically replaced. The three CSVs in a full export share a read snapshot. A later player-only update can be newer than the match snapshots: check `last_full_csv_export` before importing.

Leading spreadsheet formula characters in textual fields are escaped with an apostrophe. Names may therefore require stripping that escape when used as raw strings in later import code. Tags, fingerprints and the JSON content remain unchanged. Raw JSON's `result` belongs to `first_source_tag`. Use the separate observation CSV for another player's perspective; do not blindly apply that first result to all players.

C: had about 13.5 GB free at launch. Raw checkpoint responses and match CSV exports are compressed to reduce disk pressure. The worker checks free space and stops with `disk_low` below 3 GiB. Free space or move the entire sample directory, then resume. Keep the SQLite file and its `-wal`/`-shm` companions together; stop the worker before moving files.

## Commands

Run from the repository root using the project environment:

```powershell
# Start or resume. A second worker for this directory is rejected by an OS lock.
.\.venv\Scripts\python.exe scripts/collect_bulk_dataset.py --target-players 100000 --matches-per-player 50 --rps 3 --poll-hours 6

# Published status, without network requests or credentials
.\.venv\Scripts\python.exe scripts/collect_bulk_dataset.py --status

# Request a clean stop, preserving progress and exporting the current sample
.\.venv\Scripts\python.exe scripts/collect_bulk_dataset.py --stop

# After stopping, export immediately (the worker lock protects against concurrent export)
.\.venv\Scripts\python.exe scripts/collect_bulk_dataset.py --export
```

Targets cannot change within an existing sample directory. Use a separate `--directory data/bulk-sample-other` for another target. `--max-requests N` sets a bounded per-session request budget for testing; omitted/zero continues toward the target or recorded activity exhaustion. Token/IP failures set `needs_token`; update `.env` and resume. Rate limits and upstream failures use progressively longer backoff, up to 15 minutes, with durable checkpoint preservation. Jobs resume by rerunning the command; they do not automatically start after reboot.

Compressed CSVs can be consumed directly without expanding large files:

```python
import pandas as pd
for chunk in pd.read_csv('data/bulk-sample-100k/matches.csv.gz', chunksize=10000):
    # raw_json is the original item; first_source_tag is required for outcome normalization.
    pass
```

## Whether more data improves prediction

More verified, varied matches can improve map/brawler coverage and reduce noisy win-rate estimates. A larger row count does not guarantee better prediction. The independent sample size is the deduplicated match count, and only a subset is eligible for the current 3v3 outcome model. Top-player sampling favors particular players, regions, teams and strategies. Many repeated players or copied shared games can exaggerate apparent performance.

Before migration/training, inspect mode/map/brawler coverage and missing fields; normalize each match with its recorded first source tag; exclude friendly/unsupported outcomes; split by time and unique match; audit repeated-player and patch overlap; benchmark log loss/Brier score and calibration on untouched later matches. Compare against the current baseline rather than assuming larger data is automatically better. The 3v3 eligibility flag is a structural screen, not a claim of representative or calibrated training data. Do not use trophy changes, winner fields or other post-match values as prediction inputs.

Validation: 12 isolated tests cover repeated polls, the 50-record cap, shared opposite outcomes, malformed entries, activity gaps, source provenance, CSV round trips, target-consistent restarts, duplicate-worker locking and authentication failure. A live two-player trial confirmed fetching, exporting and shared-match deduplication. The full suite passed with 197 tests.
