from __future__ import annotations

import hashlib
import json
import struct
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
UI_DIR = PROJECT_ROOT / "app" / "ui"
ASSET_DIR = UI_DIR / "assets" / "equipment"
HEADERS = {"User-Agent": "BrawlBuddy equipment asset synchronizer/1.0"}
GEARS = {
    "SPEED": 62000000,
    "HEALTH": 62000001,
    "DAMAGE": 62000002,
    "VISION": 62000003,
    "SHIELD": 62000004,
    "RELOAD SPEED": 62000005,
    "SUPER CHARGE": 62000006,
    "THICC HEAD": 62000007,
    "TALK TO THE HAND": 62000008,
    "EXHAUSTING STORM": 62000012,
    "STICKY OIL": 62000013,
    "PET POWER": 62000014,
    "QUADRUPLETS": 62000015,
    "SUPER TURRET": 62000016,
    "GADGET COOLDOWN": 62000017,
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def normalize(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 3:
                raise
        except urllib.error.URLError:
            if attempt == 3:
                raise
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}")


def png_dimensions(payload: bytes) -> tuple[int, int]:
    if len(payload) < 33 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("download is not a PNG")
    if payload[12:16] != b"IHDR":
        raise ValueError("PNG has no IHDR chunk")
    width, height = struct.unpack(">II", payload[16:24])
    if width < 32 or height < 32:
        raise ValueError(f"image is unexpectedly small: {width}x{height}")
    return width, height


def download(source_url: str, destination: Path) -> dict[str, Any]:
    payload = fetch_bytes(source_url)
    width, height = png_dimensions(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".png.part")
    temporary.write_bytes(payload)
    temporary.replace(destination)
    return {
        "local_url": "/" + destination.relative_to(UI_DIR).as_posix(),
        "source_url": source_url,
        "local_sha256": hashlib.sha256(payload).hexdigest(),
        "width": width,
        "height": height,
        "mime": "image/png",
    }


def main() -> None:
    guides_path = DATA_DIR / "brawler_guides.json"
    equipment_path = DATA_DIR / "equipment_ids.json"
    manifest_path = DATA_DIR / "visual_asset_manifest.json"
    guides = load_json(guides_path)
    equipment = load_json(equipment_path)
    manifest = load_json(manifest_path)

    brawlapi = json.loads(fetch_bytes("https://api.brawlapi.com/v1/brawlers"))["list"]
    api_by_id = {str(item["id"]): item for item in brawlapi}
    hashes: dict[str, list[str]] = defaultdict(list)
    files = 0
    name_corrections: list[dict[str, str | int]] = []

    for brawler_id, guide in guides.items():
        remote = api_by_id[brawler_id]
        for collection, remote_collection, folder, local_folder in (
            ("gadgets", "gadgets", "gadgets", "gadgets"),
            ("star_powers", "starPowers", "star-powers", "star-powers"),
        ):
            remote_by_id = {
                item["id"]: item
                for item in remote[remote_collection]
                if item.get("released", True)
            }
            for item in guide[collection]:
                remote_item = remote_by_id.get(item["id"])
                if remote_item is None:
                    raise RuntimeError(
                        f"{guide['name']} / {item['id']} is absent from current BrawlAPI"
                    )
                if normalize(remote_item["name"]) != normalize(item["name"]):
                    old_name = item["name"]
                    new_name = remote_item["name"].upper()
                    name_corrections.append(
                        {
                            "brawler": guide["name"],
                            "id": item["id"],
                            "old": old_name,
                            "new": new_name,
                        }
                    )
                    item["name"] = new_name
                    build_key = "gadget" if collection == "gadgets" else "star_power"
                    if guide["recommended_build"].get(build_key) == old_name:
                        guide["recommended_build"][build_key] = new_name
                    indexed = equipment.pop(old_name)
                    equipment[new_name] = indexed
                source_url = f"https://cdn.brawlify.com/{folder}/regular/{item['id']}.png"
                metadata = download(
                    source_url, ASSET_DIR / local_folder / f"{item['id']}.png"
                )
                digest = metadata["local_sha256"]
                label = f"{guide['name']} / {item['name']}"
                hashes[digest].append(label)
                files += 1
                item["source_url"] = source_url
                item["image_url"] = metadata["local_url"]
                indexed = equipment[item["name"]]
                indexed["source_url"] = source_url
                indexed["image_url"] = metadata["local_url"]

    manifest["gears"] = {}
    for name, gear_id in GEARS.items():
        source_url = f"https://cdn.brawlify.com/gears/regular/{gear_id}.png"
        metadata = download(source_url, ASSET_DIR / "gears" / f"{gear_id}.png")
        digest = metadata["local_sha256"]
        hashes[digest].append(f"Gear / {name}")
        manifest["gears"][name] = {"id": gear_id, **metadata}
        files += 1

    manifest["equipment"] = {
        "source": "https://github.com/Brawlify/CDN",
        "cross_validation": "https://api.brawlapi.com/v1/brawlers",
        "gadgets": sum(len(guide["gadgets"]) for guide in guides.values()),
        "star_powers": sum(len(guide["star_powers"]) for guide in guides.values()),
        "gears": len(GEARS),
        "duplicate_content_groups": [
            labels for labels in hashes.values() if len(labels) > 1
        ],
    }
    save_json(guides_path, guides)
    save_json(equipment_path, equipment)
    save_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "gadgets": manifest["equipment"]["gadgets"],
                "star_powers": manifest["equipment"]["star_powers"],
                "gears": manifest["equipment"]["gears"],
                "local_files": files,
                "unique_hashes": len(hashes),
                "duplicate_content_groups": len(
                    manifest["equipment"]["duplicate_content_groups"]
                ),
                "name_corrections": name_corrections,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
