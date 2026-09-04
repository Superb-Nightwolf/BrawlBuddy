from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ART_DIR = PROJECT_ROOT / "app" / "ui" / "assets" / "brawlers"
THUMB_DIR = ART_DIR / "thumbs"
VISUAL_MANIFEST_PATH = DATA_DIR / "visual_asset_manifest.json"
UI_DIR = PROJECT_ROOT / "app" / "ui"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "BrawlBuddy asset audit"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def png_dimensions(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def is_webp(path: Path) -> bool:
    with path.open("rb") as handle:
        header = handle.read(12)
    return len(header) == 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).casefold()
    return "".join(character for character in folded if character.isalnum())


def audit(online: bool) -> tuple[list[str], list[str], dict[str, int]]:
    catalog: list[dict[str, Any]] = load_json(DATA_DIR / "brawler_catalog.json")
    guides: dict[str, dict[str, Any]] = load_json(DATA_DIR / "brawler_guides.json")
    equipment: dict[str, dict[str, Any]] = load_json(DATA_DIR / "equipment_ids.json")
    buffies: dict[str, Any] = load_json(DATA_DIR / "buffies_db.json")
    visual_assets: dict[str, Any] = load_json(VISUAL_MANIFEST_PATH)

    errors: list[str] = []
    warnings: list[str] = []
    catalog_ids = {str(item["id"]) for item in catalog}
    equipment_ids: list[int] = []
    equipment_names: list[str] = []

    if len(catalog) != len(catalog_ids):
        errors.append("The brawler catalog contains duplicate IDs.")
    if len({item["name"] for item in catalog}) != len(catalog):
        errors.append("The brawler catalog contains duplicate names.")

    for brawler in catalog:
        brawler_id = str(brawler["id"])
        guide = guides.get(brawler_id)
        if guide is None:
            errors.append(f"{brawler['name']}: missing guide for {brawler_id}.")
            continue

        for field in ("id", "name", "rarity"):
            if guide.get(field) != brawler.get(field):
                errors.append(
                    f"{brawler['name']}: catalog/guide {field} mismatch "
                    f"({brawler.get(field)!r} != {guide.get(field)!r})."
                )

        for collection, kind, url_folder in (
            ("gadgets", "gadget", "gadgets"),
            ("star_powers", "star_power", "star-powers"),
        ):
            items = guide.get(collection, [])
            if len(items) != 2:
                errors.append(f"{brawler['name']}: expected 2 {collection}, found {len(items)}.")
            for item in items:
                item_id = item.get("id")
                item_name = item.get("name")
                equipment_ids.append(item_id)
                equipment_names.append(item_name)
                expected_source_url = (
                    f"https://cdn.brawlify.com/{url_folder}/regular/{item_id}.png"
                )
                expected_url = (
                    f"/assets/equipment/{url_folder}/{item_id}.png"
                )
                if item.get("image_url") != expected_url:
                    errors.append(f"{brawler['name']} / {item_name}: incorrect image URL.")
                if item.get("source_url") != expected_source_url:
                    errors.append(f"{brawler['name']} / {item_name}: incorrect source URL.")
                database_item = equipment.get(item_name)
                expected_database_item = {
                    "id": item_id,
                    "type": kind,
                    "brawler_id": brawler_id,
                    "brawler_name": brawler["name"],
                    "image_url": expected_url,
                    "source_url": expected_source_url,
                }
                if database_item != expected_database_item:
                    errors.append(
                        f"{brawler['name']} / {item_name}: equipment index does not match guide."
                    )

        build = guide.get("recommended_build", {})
        gadget_names = {item["name"] for item in guide.get("gadgets", [])}
        star_power_names = {item["name"] for item in guide.get("star_powers", [])}
        if build.get("gadget") not in gadget_names:
            errors.append(
                f"{brawler['name']}: recommended Gadget {build.get('gadget')!r} is not in its kit."
            )
        if build.get("star_power") not in star_power_names:
            errors.append(
                f"{brawler['name']}: recommended Star Power "
                f"{build.get('star_power')!r} is not in its kit."
            )
        for gear in build.get("gears", []):
            if gear not in guide.get("gears", []):
                errors.append(f"{brawler['name']}: recommended Gear {gear!r} is unavailable.")

        artwork = ART_DIR / f"{brawler_id}.png"
        thumbnail = THUMB_DIR / (
            "16000108.png" if brawler_id == "16000108" else f"{brawler_id}.webp"
        )
        if not artwork.is_file():
            errors.append(f"{brawler['name']}: missing local artwork {artwork.name}.")
        elif (dimensions := png_dimensions(artwork)) is None:
            errors.append(f"{brawler['name']}: invalid PNG artwork {artwork.name}.")
        elif min(dimensions) < 200:
            errors.append(f"{brawler['name']}: artwork is unexpectedly small ({dimensions}).")
        if not thumbnail.is_file():
            errors.append(f"{brawler['name']}: missing local thumbnail {thumbnail.name}.")
        elif thumbnail.suffix == ".webp" and not is_webp(thumbnail):
            errors.append(f"{brawler['name']}: invalid WebP thumbnail {thumbnail.name}.")
        elif thumbnail.suffix == ".png" and png_dimensions(thumbnail) is None:
            errors.append(f"{brawler['name']}: invalid PNG thumbnail {thumbnail.name}.")

    for guide_id in sorted(set(guides) - catalog_ids):
        errors.append(f"Guide {guide_id} has no catalog brawler.")
    if len(set(equipment_ids)) != len(equipment_ids):
        errors.append("One or more Gadget/Star Power IDs are duplicated.")
    if len(set(equipment_names)) != len(equipment_names):
        errors.append("One or more Gadget/Star Power names are duplicated.")
    if set(equipment) != set(equipment_names):
        errors.append("The equipment index and guide equipment names differ.")

    manifest_brawlers = visual_assets.get("brawlers", {})
    if set(manifest_brawlers) != catalog_ids:
        errors.append("The visual asset manifest and catalog brawler IDs differ.")
    individual_hashes: dict[str, str] = {}
    expected_individual_paths: set[Path] = set()
    buffy_released_names: set[str] = set()
    released_hypercharges = 0
    individual_buffies = 0

    for brawler in catalog:
        brawler_id = str(brawler["id"])
        entry = manifest_brawlers.get(brawler_id, {})
        if entry.get("name") != brawler["name"]:
            errors.append(f"{brawler['name']}: visual manifest name mismatch.")

        guide_hypercharge = guides[brawler_id]["hypercharge"]
        manifest_hypercharge = entry.get("hypercharge", {})
        guide_released = bool(guide_hypercharge.get("released"))
        if manifest_hypercharge.get("released") is not guide_released:
            errors.append(f"{brawler['name']}: Hypercharge release status mismatch.")
        if guide_released:
            released_hypercharges += 1
            expected_url = f"/assets/equipment/hypercharges/{brawler_id}.png"
            if guide_hypercharge.get("image_url") != expected_url:
                errors.append(f"{brawler['name']}: guide does not use its local Hypercharge.")

        buffy_entry = entry.get("buffies", {})
        if buffy_entry.get("released"):
            buffy_released_names.add(brawler["name"])

        artworks = [("hypercharge", manifest_hypercharge)]
        artworks.extend(
            (f"buffy-{category}", buffy_entry.get(category, {}))
            for category in ("gadget", "star_power", "hypercharge")
        )
        for category, artwork in artworks:
            if artwork.get("released"):
                if category.startswith("buffy-"):
                    individual_buffies += 1
                local_url = artwork.get("local_url", "")
                path = UI_DIR / local_url.lstrip("/")
                expected_individual_paths.add(path)
                if not path.is_file():
                    errors.append(f"{brawler['name']} / {category}: missing {local_url}.")
                    continue
                if png_dimensions(path) != (artwork.get("width"), artwork.get("height")):
                    errors.append(f"{brawler['name']} / {category}: invalid PNG dimensions.")
                digest = file_hash(path)
                if digest != artwork.get("local_sha256"):
                    errors.append(f"{brawler['name']} / {category}: checksum mismatch.")
                if digest in individual_hashes:
                    errors.append(
                        f"{brawler['name']} / {category}: duplicates {individual_hashes[digest]}."
                    )
                individual_hashes[digest] = f"{brawler['name']} / {category}"
                if not artwork.get("wiki_file") or not artwork.get("source_url"):
                    errors.append(f"{brawler['name']} / {category}: missing source identity.")
            elif artwork.get("local_url"):
                errors.append(f"{brawler['name']} / {category}: unreleased item has artwork.")

    manifest_buffy_names = {name.upper() for name in buffy_released_names}
    if set(buffies.get("released_brawlers", [])) != manifest_buffy_names:
        errors.append("Buffy release list does not match the visual manifest.")
    for trio in buffies.get("trios", []):
        for brawler in trio.get("brawlers", []):
            for field in ("gadget_img_file", "star_img_file", "hyper_img_file"):
                if brawler.get(field) not in buffies.get("image_urls", {}):
                    errors.append(f"{brawler['name']}: unresolved Buffy file key {field}.")

    for fallback_group in (
        visual_assets.get("fallbacks", {}).get("hypercharge", []),
        *visual_assets.get("fallbacks", {}).get("buffy", {}).values(),
        visual_assets.get("fallbacks", {}).get("buffy_unreleased", []),
    ):
        for local_url in fallback_group:
            if not (UI_DIR / local_url.lstrip("/")).is_file():
                errors.append(f"Missing visual fallback: {local_url}.")

    local_individual_paths = {
        path
        for folder in (
            PROJECT_ROOT / "app" / "ui" / "assets" / "equipment" / "hypercharges",
            PROJECT_ROOT / "app" / "ui" / "assets" / "equipment" / "buffies",
        )
        for path in folder.glob("*.png")
    }
    unused_paths = local_individual_paths - expected_individual_paths
    missing_paths = expected_individual_paths - local_individual_paths
    if unused_paths:
        errors.append(f"Unused individual assets: {sorted(path.name for path in unused_paths)}.")
    if missing_paths:
        errors.append(f"Manifest assets absent locally: {sorted(path.name for path in missing_paths)}.")

    equipment_asset_paths: set[Path] = set()
    for item in equipment.values():
        local_url = item.get("image_url", "")
        path = UI_DIR / local_url.lstrip("/")
        equipment_asset_paths.add(path)
        if not path.is_file() or png_dimensions(path) is None:
            errors.append(f"Invalid local equipment asset: {local_url}.")
    gear_assets = visual_assets.get("gears", {})
    for name, gear in gear_assets.items():
        path = UI_DIR / gear.get("local_url", "").lstrip("/")
        equipment_asset_paths.add(path)
        if not path.is_file() or png_dimensions(path) != (
            gear.get("width"), gear.get("height")
        ):
            errors.append(f"Invalid local Gear asset: {name}.")

    ui_icons = visual_assets.get("ui_icons", {})
    mode_icons = ui_icons.get("modes", {})
    class_icons = ui_icons.get("classes", {})
    if len(mode_icons) != 17:
        errors.append(f"Expected 17 verified mode icons, found {len(mode_icons)}.")
    if set(class_icons) != {
        "damage-dealer", "tank", "marksman", "artillery",
        "assassin", "support", "controller",
    }:
        errors.append("The official class icon mapping is incomplete.")
    for group_name, records in (("mode", mode_icons), ("class", class_icons)):
        for slug, record in records.items():
            path = UI_DIR / record.get("local_url", "").lstrip("/")
            if not path.is_file() or png_dimensions(path) != (
                record.get("width"), record.get("height")
            ):
                errors.append(f"Invalid local {group_name} icon: {slug}.")
                continue
            if file_hash(path) != record.get("local_sha256"):
                errors.append(f"Checksum mismatch for {group_name} icon: {slug}.")
    generic_buffie = ui_icons.get("buffie", {})
    generic_buffie_path = UI_DIR / generic_buffie.get("local_url", "").lstrip("/")
    if (
        generic_buffie.get("local_url") != "/assets/buffies/generic.png"
        or not generic_buffie_path.is_file()
        or png_dimensions(generic_buffie_path)
        != (generic_buffie.get("width"), generic_buffie.get("height"))
    ):
        errors.append("The generic unreleased-Buffy symbol is invalid or missing.")

    for paths, label in (
        ([ART_DIR / f"{item['id']}.png" for item in catalog], "artwork"),
        (
            [
                THUMB_DIR
                / ("16000108.png" if item["id"] == 16000108 else f"{item['id']}.webp")
                for item in catalog
            ],
            "thumbnail",
        ),
    ):
        hashes = Counter(file_hash(path) for path in paths if path.is_file())
        duplicates = {value for value, count in hashes.items() if count > 1}
        if duplicates:
            errors.append(f"Duplicate {label} image content detected ({len(duplicates)} groups).")

    if online:
        try:
            remote_brawlers = fetch_json("https://api.brawlapi.com/v1/brawlers")["list"]
            remote_by_id = {str(item["id"]): item for item in remote_brawlers}
            if len(remote_by_id) != len(remote_brawlers):
                warnings.append("Current BrawlAPI response contains duplicate brawler IDs.")
            for brawler in catalog:
                brawler_id = str(brawler["id"])
                remote = remote_by_id.get(brawler_id)
                if remote is None:
                    errors.append(f"{brawler['name']}: missing from current BrawlAPI catalog.")
                    continue
                if remote["name"].upper() != brawler["name"]:
                    errors.append(
                        f"{brawler['name']}: current API name is {remote['name']!r}."
                    )
                guide = guides[brawler_id]
                for local_key, remote_key in (
                    ("gadgets", "gadgets"),
                    ("star_powers", "starPowers"),
                ):
                    local_items = {item["id"]: item for item in guide[local_key]}
                    remote_items = {
                        item["id"]: item for item in remote[remote_key] if item.get("released", True)
                    }
                    for item_id, local_item in local_items.items():
                        if item_id not in remote_items:
                            errors.append(
                                f"{brawler['name']} / {item_id}: missing from current BrawlAPI "
                                f"{local_key}."
                            )
                            continue
                        remote_name = remote_items[item_id]["name"].upper()
                        if normalized_name(local_item["name"]) != normalized_name(remote_name):
                            errors.append(
                                f"{brawler['name']} / {item_id}: local name "
                                f"{local_item['name']!r}, current name {remote_name!r}."
                            )
                    extra_ids = set(remote_items) - set(local_items)
                    if extra_ids:
                        warnings.append(
                            f"Current BrawlAPI lists extra {local_key} IDs for "
                            f"{brawler['name']}: {sorted(extra_ids)}."
                        )
            local_missing = [
                item for item in remote_brawlers
                if item.get("released", True) and str(item["id"]) not in catalog_ids
            ]
            for item in local_missing:
                warnings.append(
                    f"Current API has an additional released brawler: {item['name']} ({item['id']})."
                )
        except Exception as exc:  # pragma: no cover - depends on network availability
            warnings.append(f"Could not query BrawlAPI: {exc}")

        try:
            tree = fetch_json(
                "https://api.github.com/repos/Brawlify/CDN/git/trees/master?recursive=1"
            )
            paths = {item["path"] for item in tree["tree"]}
            for brawler in catalog:
                brawler_id = str(brawler["id"])
                guide = guides[brawler_id]
                expected_paths = [f"brawlers/borders/{brawler_id}.png"]
                expected_paths.extend(
                    f"gadgets/regular/{item['id']}.png" for item in guide["gadgets"]
                )
                expected_paths.extend(
                    f"star-powers/regular/{item['id']}.png"
                    for item in guide["star_powers"]
                )
                for expected_path in expected_paths:
                    if expected_path not in paths:
                        errors.append(
                            f"{brawler['name']}: missing from Brawlify CDN: {expected_path}."
                        )
        except Exception as exc:  # pragma: no cover - depends on network availability
            warnings.append(f"Could not query the Brawlify CDN manifest: {exc}")

    counts = {
        "brawlers": len(catalog),
        "guides": len(guides),
        "gadgets": sum(len(guide.get("gadgets", [])) for guide in guides.values()),
        "star_powers": sum(
            len(guide.get("star_powers", [])) for guide in guides.values()
        ),
        "equipment_index": len(equipment),
        "released_hypercharges": released_hypercharges,
        "unreleased_hypercharges": len(catalog) - released_hypercharges,
        "buffy_brawlers": len(buffy_released_names),
        "individual_buffies": individual_buffies,
        "individual_visual_assets": len(individual_hashes),
        "local_equipment_assets": len(equipment_asset_paths),
        "mode_icons": len(mode_icons),
        "class_icons": len(class_icons),
    }
    return errors, warnings, counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit BrawlBuddy catalog and image relationships.")
    parser.add_argument(
        "--online",
        action="store_true",
        help="Also compare IDs/names with BrawlAPI and asset paths with the Brawlify CDN.",
    )
    args = parser.parse_args()
    errors, warnings, counts = audit(args.online)
    print(json.dumps({"counts": counts, "errors": errors, "warnings": warnings}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
