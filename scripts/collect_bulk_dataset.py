"""Collect/export a resumable 100k-player, 50-match CSV sample in a separate directory."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.brawl_stars import BrawlStarsClient
from app.core.config import get_settings
from app.ml.bulk_dataset import BulkDataset, BulkDatasetWorker, dataset_lock


async def collect(args, dataset):
    settings = get_settings()
    if not settings.api_token:
        dataset.publish_status('needs_token', 'Configure BRAWL_STARS_API_TOKEN in .env, then resume.')
        return
    client = BrawlStarsClient(settings.brawl_stars, settings.api_token)
    try:
        await BulkDatasetWorker(client, dataset, rps=args.rps, poll_hours=args.poll_hours,
            idle_limit=args.idle_limit, max_requests=args.max_requests,
            export_seconds=args.export_seconds).run()
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'data' / 'bulk-sample-100k')
    parser.add_argument('--target-players', type=int, default=100000)
    parser.add_argument('--matches-per-player', type=int, default=50)
    parser.add_argument('--rps', type=float, default=3)
    parser.add_argument('--poll-hours', type=float, default=6)
    parser.add_argument('--idle-limit', type=int, default=12, help='Consecutive successful polls without new matches before marking stalled')
    parser.add_argument('--export-seconds', type=int, default=3600)
    parser.add_argument('--max-requests', type=int, default=0, help='Per-session budget; 0 continues to target/activity exhaustion')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    if not (1 <= args.target_players <= 100000 and 1 <= args.matches_per_player <= 50
            and 0.5 <= args.rps <= 5 and args.poll_hours >= 0.1 and args.idle_limit >= 1
            and args.export_seconds >= 60 and args.max_requests >= 0):
        parser.error('Use players 1–100000, matches 1–50, rps 0.5–5, poll-hours >=0.1, idle-limit >=1, export-seconds >=60.')
    if args.stop:
        args.directory.mkdir(parents=True, exist_ok=True)
        (args.directory / 'stop.request').touch()
        print('Stop requested. Check progress.json for the final state.')
        return
    if args.status:
        path = args.directory / 'progress.json'
        print(path.read_text(encoding='utf-8') if path.exists() else 'Dataset has not started.')
        return
    logging.basicConfig(level=logging.WARNING)
    try:
        with dataset_lock(args.directory):
            dataset = BulkDataset(args.directory, args.target_players, args.matches_per_player)
            try:
                if args.export:
                    dataset.export_csv()
                else:
                    (args.directory / 'stop.request').unlink(missing_ok=True)
                    asyncio.run(collect(args, dataset))
                print(json.dumps(dataset.summary(), indent=2))
            finally:
                dataset.close()
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Cannot start collector: {exc}\n')


if __name__ == '__main__':
    main()
