from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "prestige_assets.json"
GITHUB_CONTENTS = "https://api.github.com/repos/Brawlify/CDN/contents/prestiges"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "BrawlBuddy prestige sync/1.0"}


def fetch_json(url: str) -> list[dict]:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def numeric_names(url: str, expected_type: str) -> list[int]:
    return sorted(
        int(item["name"].removesuffix(".png"))
        for item in fetch_json(url)
        if item["type"] == expected_type
        and item["name"].removesuffix(".png").isdigit()
    )


def main() -> None:
    query = "?ref=master"
    brawler_ids = numeric_names(f"{GITHUB_CONTENTS}/brawlers{query}", "dir")
    tiered_ids = numeric_names(f"{GITHUB_CONTENTS}/tiered{query}", "file")
    regular_ids = numeric_names(f"{GITHUB_CONTENTS}/regular{query}", "file")
    payload = {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).date().isoformat(),
        "cdn_base_url": "https://cdn.brawlify.com/prestiges",
        "repository": "https://github.com/Brawlify/CDN/tree/master/prestiges",
        "official_rules": {
            "release_notes": "https://supercell.com/en/games/brawlstars/blog/release-notes/release-notes-february-2026/",
            "support": "https://support.supercell.com/brawl-stars/en/articles/prestige.html",
        },
        "asset_ids": {
            "wood": 0,
            "bronze": 1,
            "silver": 2,
            "gold": 3,
            "prestige_level_offset": 3,
            "max_visual_prestige": 10,
        },
        "available": {
            "brawler_ids": brawler_ids,
            "tiered_asset_ids": tiered_ids,
            "regular_asset_ids": regular_ids,
        },
        "resolver": {
            "specific": "/brawlers/{brawler_id}/{asset_id}.png",
            "generic": "/tiered/{asset_id}.png",
            "path_generic": "/regular/{asset_id}.png",
        },
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Synced {len(brawler_ids)} brawler folders and {len(tiered_ids)} tier assets")


if __name__ == "__main__":
    main()
