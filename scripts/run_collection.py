"""BrawlBuddy Battle Collection CLI.

Allows discovering competitive players and collecting historical battle logs
with rate limiting, deduplication, and progress reporting.
"""

from __future__ import annotations

from contextlib import closing
import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.clients.brawl_stars import BrawlStarsClient
from app.core.config import get_settings
from app.ml.collector import BattleLogCollector, CollectionStats
from app.ml.database import MetaDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("brawlbuddy.collection")


async def main_async(args: argparse.Namespace) -> None:
    settings = get_settings()
    database = MetaDatabase(PROJECT_ROOT / "data" / "brawl_meta.db")
    if args.status:
        import json
        print(json.dumps(database.get_dataset_summary(), indent=2))
        return
    if not settings.api_token:
        logger.error("Configure the game token before collection.")
        sys.exit(1)
    client = BrawlStarsClient(settings.brawl_stars, settings.api_token)
    collector = BattleLogCollector(client, database, requests_per_second=args.rps)

    try:
        if args.discover:
            print(f"[*] Discovering competitive players (Target: {args.target_players})...")
            def on_disc_prog(step: str, count: int) -> None:
                print(f"    -> [{step}] Total players discovered: {count}")
            
            total = await collector.discover_top_players(
                target_player_count=args.target_players,
                on_progress=on_disc_prog,
            )
            print(f"[+] Discovery complete. Player count in DB: {total}")

        if args.collect:
            print(f"[*] Collecting battle logs for up to {args.max_players} players (RPS: {args.rps})...")
            def on_coll_prog(stats: CollectionStats) -> None:
                print(
                    f"    -> Polled: {stats.players_polled} players | "
                    f"Battles fetched: {stats.battles_fetched} | "
                    f"New matches saved: {stats.new_matches_saved} | "
                    f"Deduplicated skips: {stats.duplicate_matches_skipped} | "
                    f"Time: {stats.elapsed_seconds():.1f}s"
                )

            stats = await collector.collect_battlelogs(
                max_players=args.max_players,
                cascade_discovery=args.cascade,
                on_progress=on_coll_prog,
            )
            print("\n[+] Collection batch completed successfully!")
            print(f"    - Players polled: {stats.players_polled}")
            print(f"    - Battles fetched from API: {stats.battles_fetched}")
            print(f"    - New unique matches saved: {stats.new_matches_saved}")
            print(f"    - Matches deduplicated (exact duplicates prevented): {stats.duplicate_matches_skipped}")
            print(f"    - Failed/404 polls: {stats.failed_polls}")
            print(f"    - Total players discovered in DB now: {stats.total_players}")

    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="BrawlBuddy Battle Collection CLI")
    parser.add_argument("--discover", action="store_true", help="Run player discovery phase")
    parser.add_argument("--target-players", type=int, default=5000, help="Target competitive player count")
    parser.add_argument("--collect", action="store_true", help="Run battle log collection phase")
    parser.add_argument("--max-players", type=int, default=200, help="Max players to poll in this run")
    parser.add_argument("--rps", type=float, default=6.0, help="Requests per second rate limit")
    parser.add_argument("--no-cascade", dest="cascade", action="store_false", help="Disable cascading player discovery")
    parser.add_argument("--status", action="store_true", help="Print meta database status")

    args = parser.parse_args()
    if not (args.discover or args.collect or args.status):
        parser.print_help()
        sys.exit(0)

    if not 1 <= args.max_players <= 1000 or not 1 <= args.rps <= 10 or not 10 <= args.target_players <= 100000:
        parser.error("Use max-players 1–1000, rps 1–10 and target-players 10–100000")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
