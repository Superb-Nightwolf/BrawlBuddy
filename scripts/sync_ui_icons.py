from __future__ import annotations

import hashlib
import json
import struct
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = PROJECT_ROOT / "app" / "ui"
ASSET_DIR = UI_DIR / "assets"
MANIFEST_PATH = PROJECT_ROOT / "data" / "visual_asset_manifest.json"
WIKI_API = "https://brawlstars.fandom.com/api.php"
HEADERS = {
    "User-Agent": "BrawlBuddy UI icon synchronizer/1.0",
    "Referer": "https://brawlstars.fandom.com/",
}

MODES = {
    "gem-grab": ("Gem Grab", "File:Gem Grab.png", ["gemGrab", "gem grab"]),
    "hot-zone": ("Hot Zone", "File:Hot Zone.png", ["hotZone", "hot zone"]),
    "brawl-ball": ("Brawl Ball", "File:Brawl Ball.png", ["brawlBall", "brawl ball"]),
    "showdown": ("Showdown", "File:Showdown.png", ["showdown", "soloShowdown", "solo showdown"]),
    "duo-showdown": ("Duo Showdown", "File:Duo Showdown.png", ["duoShowdown", "duo showdown"]),
    "knockout": ("Knockout", "File:Knockout.png", ["knockout"]),
    "wipeout": ("Wipeout", "File:Wipeout.png", ["wipeout"]),
    "heist": ("Heist", "File:Heist.png", ["heist"]),
    "bounty": ("Bounty", "File:Bounty.png", ["bounty"]),
    "duels": ("Duels", "File:Duels.png", ["duels"]),
    "siege": ("Siege", "File:Siege.png", ["siege"]),
    "takedown": ("Takedown", "File:Takedown.png", ["takedown"]),
    "lone-star": ("Lone Star", "File:Lone Star.png", ["loneStar", "lone star"]),
    "basket-brawl": ("Basket Brawl", "File:Basket Brawl.png", ["basketBrawl", "basket brawl"]),
    "volley-brawl": ("Volley Brawl", "File:Volley Brawl.png", ["volleyBrawl", "volley brawl"]),
    "payload": ("Payload", "File:Payload.png", ["payload"]),
    "boss-fight": ("Boss Fight", "File:Boss Fight.png", ["bossFight", "boss fight"]),
}

CLASSES = {
    "damage-dealer": ("Damage Dealer", "File:Class-Damage Dealer.png", ["damage dealer", "damage_dealer"]),
    "tank": ("Tank", "File:Class-Tank.png", ["tank"]),
    "marksman": ("Marksman", "File:Class-Marksman.png", ["marksman"]),
    "artillery": ("Artillery", "File:Class-Artillery.png", ["artillery"]),
    "assassin": ("Assassin", "File:Class-Assassin.png", ["assassin"]),
    "support": ("Support", "File:Class-Support.png", ["support"]),
    "controller": ("Controller", "File:Class-Controller.png", ["controller"]),
}

BUFFIE = ("Buffie", "File:Icon-Buffie.png", ["buffie", "buffy"])


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def wiki_file_info(titles: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    query = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url|mime|size|sha1",
            "titles": "|".join(titles),
        }
    )
    payload = json.loads(fetch_bytes(f"{WIKI_API}?{query}"))
    for page in payload["query"]["pages"].values():
        if "missing" in page:
            raise RuntimeError(f"Missing Wiki artwork: {page['title']}")
        result[page["title"]] = page["imageinfo"][0]
    return result


def verified_png(payload: bytes) -> tuple[int, int]:
    if len(payload) < 33 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("download is not a PNG")
    if payload[12:16] != b"IHDR":
        raise ValueError("PNG has no IHDR chunk")
    width, height = struct.unpack(">II", payload[16:24])
    if payload[25] not in {4, 6} and b"tRNS" not in payload:
        raise ValueError("PNG does not preserve transparency")
    return width, height


def download_record(
    slug: str,
    label: str,
    title: str,
    aliases: list[str],
    info: dict[str, Any],
    category: str,
) -> dict[str, Any]:
    source_url = info["url"] + ("&" if "?" in info["url"] else "?") + "format=original"
    payload = fetch_bytes(source_url)
    width, height = verified_png(payload)
    destination = ASSET_DIR / category / f"{slug}.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".png.part")
    temporary.write_bytes(payload)
    temporary.replace(destination)
    return {
        "label": label,
        "aliases": aliases,
        "local_url": "/" + destination.relative_to(UI_DIR).as_posix(),
        "wiki_file": title,
        "wiki_page": "https://brawlstars.fandom.com/wiki/"
        + urllib.parse.quote(title.replace(" ", "_"), safe=":-_"),
        "source_url": info["url"],
        "source_sha1": info.get("sha1"),
        "local_sha256": hashlib.sha256(payload).hexdigest(),
        "width": width,
        "height": height,
        "mime": "image/png",
    }


def main() -> None:
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    titles = (
        [item[1] for item in MODES.values()]
        + [item[1] for item in CLASSES.values()]
        + [BUFFIE[1]]
    )
    info = wiki_file_info(titles)
    ui_icons: dict[str, Any] = {
        "checked_at": date.today().isoformat(),
        "official_references": {
            "modes": "https://support.supercell.com/brawl-stars/en/articles/game-modes-12.html",
            "classes": "https://support.supercell.com/brawl-stars/en/articles/brawler-classes.html",
        },
        "modes": {},
        "classes": {},
    }
    for slug, (label, title, aliases) in MODES.items():
        ui_icons["modes"][slug] = download_record(
            slug, label, title, aliases, info[title], "modes"
        )
    for slug, (label, title, aliases) in CLASSES.items():
        ui_icons["classes"][slug] = download_record(
            slug, label, title, aliases, info[title], "classes"
        )
    buffie_label, buffie_title, buffie_aliases = BUFFIE
    ui_icons["buffie"] = download_record(
        "generic", buffie_label, buffie_title, buffie_aliases,
        info[buffie_title], "buffies"
    )
    manifest["ui_icons"] = ui_icons
    manifest.setdefault("fallbacks", {})["buffy_unreleased"] = [
        ui_icons["buffie"]["local_url"],
        "/assets/buffie_icon.webp",
    ]
    manifest["checked_at"] = date.today().isoformat()
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"modes": len(MODES), "classes": len(CLASSES)}, indent=2))


if __name__ == "__main__":
    main()
