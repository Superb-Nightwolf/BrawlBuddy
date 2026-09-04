from __future__ import annotations

import csv
import hashlib
import io
import json
import struct
import time
import urllib.parse
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ASSET_DIR = PROJECT_ROOT / "app" / "ui" / "assets" / "equipment"
HYPERCHARGE_DIR = ASSET_DIR / "hypercharges"
BUFFY_DIR = ASSET_DIR / "buffies"
CLIENT_VERSION = "69.230"
CLIENT_ROOT = (
    "https://raw.githubusercontent.com/tailsjs/brawl-stars-assets/master/"
    f"{CLIENT_VERSION}"
)
WIKI_API = "https://brawlstars.fandom.com/api.php"
HEADERS = {
    "User-Agent": "BrawlBuddy visual asset synchronizer/1.0",
    "Referer": "https://brawlstars.fandom.com/",
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def fetch_json(url: str) -> Any:
    return json.loads(fetch_bytes(url))


def fetch_csv(relative_path: str) -> list[dict[str, str]]:
    payload = fetch_bytes(f"{CLIENT_ROOT}/{relative_path}").decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(payload)))
    return rows[1:] if rows and rows[0].get(next(iter(rows[0]), "")) == "string" else rows


def normalize(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def wiki_display_name(name: str) -> str:
    special = {
        "8 BIT": "8-Bit",
        "JAE-YONG": "Jae-yong",
        "LARRY & LAWRIE": "Larry & Lawrie",
        "MR. P": "Mr. P",
        "R-T": "R-T",
        "STARR NOVA": "Starr Nova",
    }
    return special.get(name, name.title())


def query_wiki_files(titles: list[str]) -> dict[str, dict[str, Any] | None]:
    result: dict[str, dict[str, Any] | None] = {}
    for offset in range(0, len(titles), 40):
        batch = titles[offset : offset + 40]
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "iiprop": "url|mime|size|sha1",
                "titles": "|".join(batch),
            }
        )
        payload = fetch_json(f"{WIKI_API}?{query}")
        for page in payload["query"]["pages"].values():
            result[page["title"]] = (
                None if "missing" in page else page["imageinfo"][0]
            )
    return result


def query_wiki_prefix(prefix: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "list": "allimages",
            "aiprefix": prefix,
            "ailimit": "20",
            "aiprop": "url|mime|size|sha1",
        }
    )
    payload = fetch_json(f"{WIKI_API}?{query}")
    for item in payload["query"]["allimages"]:
        if item["name"] == prefix + ".png":
            return item
    raise RuntimeError(f"Wiki file not found: File:{prefix}.png")


def png_metadata(payload: bytes) -> tuple[int, int, bool]:
    if len(payload) < 33 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("download is not a PNG")
    if payload[12:16] != b"IHDR":
        raise ValueError("PNG has no IHDR chunk")
    width, height = struct.unpack(">II", payload[16:24])
    color_type = payload[25]
    has_alpha = color_type in {4, 6} or b"tRNS" in payload
    if width < 64 or height < 64:
        raise ValueError(f"image is unexpectedly small: {width}x{height}")
    if not has_alpha:
        raise ValueError("image does not preserve transparency")
    return width, height, has_alpha


def original_url(url: str) -> str:
    return url + ("&" if "?" in url else "?") + "format=original"


def download_verified_png(
    wiki_title: str, wiki_info: dict[str, Any], destination: Path
) -> dict[str, Any]:
    payload = fetch_bytes(original_url(wiki_info["url"]))
    width, height, _ = png_metadata(payload)
    local_sha1 = hashlib.sha1(payload).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".png.part")
    temporary.write_bytes(payload)
    temporary.replace(destination)
    return {
        "local_url": "/" + destination.relative_to(PROJECT_ROOT / "app" / "ui").as_posix(),
        "wiki_file": wiki_title,
        "wiki_page": "https://brawlstars.fandom.com/wiki/"
        + urllib.parse.quote(wiki_title.replace(" ", "_"), safe=":-_"),
        "source_url": wiki_info["url"],
        # Wikia can losslessly re-encode the original response, so retain both the
        # MediaWiki revision identity and the exact bytes stored by this project.
        "source_sha1": wiki_info.get("sha1"),
        "local_sha1": local_sha1,
        "local_sha256": hashlib.sha256(payload).hexdigest(),
        "width": width,
        "height": height,
        "mime": "image/png",
    }


def main() -> None:
    catalog = read_json(DATA_DIR / "brawler_catalog.json")
    guides = read_json(DATA_DIR / "brawler_guides.json")
    buffies = read_json(DATA_DIR / "buffies_db.json")
    existing_manifest_path = DATA_DIR / "visual_asset_manifest.json"
    existing_manifest = (
        read_json(existing_manifest_path) if existing_manifest_path.exists() else {}
    )
    cards = fetch_csv("csv_logic/cards.csv")
    characters = fetch_csv("csv_logic/characters.csv")
    texts = fetch_csv("localization/texts.csv")

    text_by_tid = {row["TID"]: row["EN"] for row in texts}
    character_by_name = {row["Name"]: row for row in characters}
    overcharge_by_display: dict[str, dict[str, str]] = {}
    for card in cards:
        if "_overcharge" not in card["Name"].casefold() or "_buddy_" in card["Name"].casefold():
            continue
        character = character_by_name[card["Target"]]
        display_name = text_by_tid[character["TID"]]
        overcharge_by_display[normalize(display_name)] = {
            "client_target": card["Target"],
            "client_card": card["Name"],
            "client_export": card["IconExportName"],
        }

    buddy_categories: dict[str, set[str]] = defaultdict(set)
    for card in cards:
        if card["Type"] != "buddy":
            continue
        character = character_by_name[card["Target"]]
        display_name = text_by_tid[character["TID"]]
        suffix = card["Name"].rsplit("_", 1)[-1]
        category = {
            "Gadgets": "gadget",
            "Starpowers": "star_power",
            "Overcharge": "hypercharge",
        }[suffix]
        buddy_categories[normalize(display_name)].add(category)

    local_names = {normalize(item["name"]): str(item["id"]) for item in catalog}
    client_local_hypercharges = set(overcharge_by_display).intersection(local_names)
    released_local = {
        normalize(guide["name"])
        for guide in guides.values()
        if guide["hypercharge"].get("released")
    }
    if client_local_hypercharges != released_local:
        raise RuntimeError(
            "Local Hypercharge release flags do not match client records: "
            f"client_only={sorted(client_local_hypercharges - released_local)}, "
            f"local_only={sorted(released_local - client_local_hypercharges)}"
        )

    buffy_entries: dict[str, dict[str, str]] = {}
    for trio in buffies["trios"]:
        for entry in trio["brawlers"]:
            buffy_entries[normalize(entry["name"])] = entry
    if set(buffy_entries) != set(buddy_categories):
        raise RuntimeError(
            "Local Buffy brawlers do not match client records: "
            f"client_only={sorted(set(buddy_categories) - set(buffy_entries))}, "
            f"local_only={sorted(set(buffy_entries) - set(buddy_categories))}"
        )
    if any(categories != {"gadget", "star_power", "hypercharge"} for categories in buddy_categories.values()):
        raise RuntimeError("One or more client Buffy brawlers lacks a category")

    hyper_titles = {
        brawler_id: f"File:{wiki_display_name(guide['name'])}-Hypercharge.png"
        for brawler_id, guide in guides.items()
        if guide["hypercharge"].get("released")
    }
    hyper_info = query_wiki_files(list(hyper_titles.values()))
    # MediaWiki title normalization incorrectly capitalizes the second half of Jae-yong.
    jae_title = "File:Jae-yong-Hypercharge.png"
    if hyper_info.get(jae_title) is None:
        hyper_info[jae_title] = query_wiki_prefix("Jae-yong-Hypercharge")

    buffy_titles = list(buffies["image_urls"])
    buffy_info = query_wiki_files(buffy_titles)
    if any(info is None for title, info in hyper_info.items() if title in hyper_titles.values()):
        missing = [title for title in hyper_titles.values() if not hyper_info.get(title)]
        raise RuntimeError(f"Missing Wiki Hypercharge files: {missing}")
    if any(buffy_info.get(title) is None for title in buffy_titles):
        missing = [title for title in buffy_titles if not buffy_info.get(title)]
        raise RuntimeError(f"Missing Wiki Buffy files: {missing}")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "checked_at": date.today().isoformat(),
        "client": {
            "repository": "https://github.com/tailsjs/brawl-stars-assets",
            "version": CLIENT_VERSION,
            "cards_csv": f"{CLIENT_ROOT}/csv_logic/cards.csv",
            "characters_csv": f"{CLIENT_ROOT}/csv_logic/characters.csv",
            "local_catalog_hypercharges": len(client_local_hypercharges),
            "buffy_brawlers": len(buddy_categories),
        },
        "fallbacks": {
            "hypercharge": [
                "/assets/section_hypercharge.png",
                "/assets/hypercharge_icon.webp",
            ],
            "buffy": {
                "gadget": ["/assets/section_gadget.png", "/assets/buffie_icon.webp"],
                "star_power": [
                    "/assets/section_star_power.png",
                    "/assets/buffie_icon.webp",
                ],
                "hypercharge": [
                    "/assets/section_hypercharge.png",
                    "/assets/buffie_icon.webp",
                ],
            },
            "buffy_unreleased": [
                "/assets/buffies/generic.png",
                "/assets/buffie_icon.webp",
            ],
        },
        "brawlers": {},
    }
    for preserved_key in ("equipment", "gears", "ui_icons"):
        if preserved_key in existing_manifest:
            manifest[preserved_key] = existing_manifest[preserved_key]

    content_hashes: dict[str, str] = {}
    for item in catalog:
        brawler_id = str(item["id"])
        name = item["name"]
        name_key = normalize(name)
        guide = guides[brawler_id]
        released = bool(guide["hypercharge"].get("released"))
        entry: dict[str, Any] = {"name": name}
        if released:
            title = hyper_titles[brawler_id]
            artwork = download_verified_png(
                title, hyper_info[title], HYPERCHARGE_DIR / f"{brawler_id}.png"
            )
            artwork.update(overcharge_by_display[name_key])
            artwork["released"] = True
            entry["hypercharge"] = artwork
        else:
            if name_key in overcharge_by_display:
                raise RuntimeError(f"Unreleased local Hypercharge exists in client: {name}")
            entry["hypercharge"] = {"released": False, "local_url": None}

        is_buffy_released = name_key in buddy_categories
        entry["buffies"] = {"released": is_buffy_released}
        if is_buffy_released:
            source_entry = buffy_entries[name_key]
            file_fields = {
                "gadget": "gadget_img_file",
                "star_power": "star_img_file",
                "hypercharge": "hyper_img_file",
            }
            for category, field in file_fields.items():
                underscored = source_entry[field]
                title = underscored.replace("_Buffie-", " Buffie-")
                artwork = download_verified_png(
                    title,
                    buffy_info[title],
                    BUFFY_DIR / f"{brawler_id}-{category.replace('_', '-')}.png",
                )
                artwork["released"] = True
                entry["buffies"][category] = artwork
        else:
            for category in ("gadget", "star_power", "hypercharge"):
                entry["buffies"][category] = {"released": False, "local_url": None}

        for category, artwork in [("hypercharge", entry["hypercharge"]), *entry["buffies"].items()]:
            if not isinstance(artwork, dict) or not artwork.get("local_sha256"):
                continue
            digest = artwork["local_sha256"]
            label = f"{brawler_id}:{category}"
            if digest in content_hashes:
                raise RuntimeError(
                    f"Duplicate individual artwork: {label} == {content_hashes[digest]}"
                )
            content_hashes[digest] = label
        manifest["brawlers"][brawler_id] = entry

    manifest_path = DATA_DIR / "visual_asset_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "brawlers": len(manifest["brawlers"]),
                "hypercharges": sum(
                    entry["hypercharge"]["released"]
                    for entry in manifest["brawlers"].values()
                ),
                "buffy_brawlers": sum(
                    entry["buffies"]["released"]
                    for entry in manifest["brawlers"].values()
                ),
                "individual_files": len(content_hashes),
                "manifest": str(manifest_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
