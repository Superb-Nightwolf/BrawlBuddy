from __future__ import annotations

import csv
import html
import io
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CLIENT_VERSION = "69.230"
CLIENT_ROOT = (
    "https://raw.githubusercontent.com/tailsjs/brawl-stars-assets/master/"
    f"{CLIENT_VERSION}"
)
WIKI_API = "https://brawlstars.fandom.com/api.php"
HEADERS = {"User-Agent": "BrawlBuddy release data synchronizer/1.0"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def fetch_json(url: str) -> Any:
    return json.loads(fetch_bytes(url))


def fetch_csv(relative_path: str) -> list[dict[str, str]]:
    text = fetch_bytes(f"{CLIENT_ROOT}/{relative_path}").decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows[1:] if rows and next(iter(rows[0].values())) == "string" else rows


def wiki_name(name: str) -> str:
    result = name.title()
    return {
        "8-Bit": "8-Bit",
        "Jae-Yong": "Jae-yong",
        "Larry & Lawrie": "Larry & Lawrie",
        "Mr. P": "Mr. P",
        "R-T": "R-T",
        "Starr Nova": "Starr Nova",
    }.get(result, result)


def clean_wikitext(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\[\[[^]|]+\|([^]]+)\]\]", r"\1", value)
    value = re.sub(r"\[\[([^]]+)\]\]", r"\1", value)
    value = re.sub(r"\{\{[^{}]+\}\}", "", value)
    value = html.unescape(value).replace(r"\q", '"')
    return re.sub(r"\s+", " ", value).strip()


def fetch_hypercharge_quote(name: str) -> tuple[str, str]:
    page = wiki_name(name)
    query = urllib.parse.urlencode(
        {"action": "parse", "format": "json", "page": page, "prop": "wikitext"}
    )
    wikitext = fetch_json(f"{WIKI_API}?{query}")["parse"]["wikitext"]["*"]
    section_match = re.search(
        r"==\s*Hypercharge:\s*(.*?)\s*==(.*?)(?=\n==[^=]|\Z)",
        wikitext,
        flags=re.I | re.S,
    )
    if not section_match:
        raise RuntimeError(f"No Wiki Hypercharge section for {name}")
    heading = clean_wikitext(section_match.group(1))
    section = section_match.group(2)
    quote_match = re.search(r"\{\{Quote\|(.*?)\}\}", section, flags=re.I | re.S)
    if not quote_match:
        raise RuntimeError(f"No Wiki Hypercharge quote for {name}")
    return heading, clean_wikitext(quote_match.group(1))


def wiki_image_info(titles: list[str]) -> dict[str, dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url|mime|size|sha1",
            "titles": "|".join(titles),
        }
    )
    pages = fetch_json(f"{WIKI_API}?{query}")["query"]["pages"].values()
    missing = [page["title"] for page in pages if "missing" in page]
    if missing:
        raise RuntimeError(f"Missing Wiki Buffy images: {missing}")
    return {page["title"]: page["imageinfo"][0] for page in pages}


def main() -> None:
    guides_path = DATA_DIR / "brawler_guides.json"
    equipment_path = DATA_DIR / "equipment_ids.json"
    buffies_path = DATA_DIR / "buffies_db.json"
    sources_path = DATA_DIR / "game_data_sources.json"
    guides = load_json(guides_path)
    equipment = load_json(equipment_path)
    buffies = load_json(buffies_path)
    sources = load_json(sources_path)

    cards = fetch_csv("csv_logic/cards.csv")
    characters = fetch_csv("csv_logic/characters.csv")
    texts = fetch_csv("localization/texts.csv")
    text_by_tid = {row["TID"]: row["EN"] for row in texts}
    character_by_name = {row["Name"]: row for row in characters}
    overcharges: dict[str, dict[str, str]] = {}
    for card in cards:
        if "_overcharge" not in card["Name"].casefold() or "_buddy_" in card["Name"].casefold():
            continue
        display_name = text_by_tid[character_by_name[card["Target"]]["TID"]]
        overcharges[display_name] = card

    guide_names = {guide["name"] for guide in guides.values()}
    if not guide_names.issubset(overcharges):
        raise RuntimeError(
            f"Catalog brawlers without client Hypercharges: {sorted(guide_names - set(overcharges))}"
        )

    wiki_quotes: dict[str, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(fetch_hypercharge_quote, name): name for name in guide_names
        }
        for future in as_completed(futures):
            name = futures[future]
            wiki_quotes[name] = future.result()

    hypercharge_name_changes = 0
    wiki_name_anomalies: list[dict[str, str]] = []
    for brawler_id, guide in guides.items():
        client_card = overcharges[guide["name"]]
        client_name = text_by_tid[client_card["TID"]]
        wiki_heading, wiki_description = wiki_quotes[guide["name"]]
        if clean_wikitext(client_name).casefold() != wiki_heading.casefold():
            wiki_name_anomalies.append(
                {
                    "brawler": guide["name"],
                    "client": client_name,
                    "wiki": wiki_heading,
                }
            )
        if guide["hypercharge"].get("name") != client_name:
            hypercharge_name_changes += 1
        guide["hypercharge"].update(
            {
                "released": True,
                "name": client_name,
                "description": wiki_description,
                "image_url": f"/assets/equipment/hypercharges/{brawler_id}.png",
            }
        )

    gadget_reworks = {
        ("RICO", 23000409): (
            "MULTIBALL",
            "Rico fires a big bullet that splits into 3 smaller bullets when hitting a wall or enemy Brawlers. Cooldown: 17 seconds.",
        ),
        ("MEG", 23000489): (
            "REPURPOSE",
            "Meg ejects from the Mecha, launching it forward and dealing 1600 damage on the way. Her Super charges during the next 6 seconds. Cooldown: 25 seconds.",
        ),
        ("GUS", 23000514): (
            "KNOCKBACK SPIRIT",
            "Gus throws a spirit, knocking back enemies and dealing 1080 damage. Cooldown: 10 seconds.",
        ),
    }
    for guide in guides.values():
        for gadget in guide["gadgets"]:
            replacement = gadget_reworks.get((guide["name"], gadget["id"]))
            if not replacement:
                continue
            old_name = gadget["name"]
            new_name, description = replacement
            gadget["name"] = new_name
            gadget["description"] = description
            if guide["recommended_build"].get("gadget") == old_name:
                guide["recommended_build"]["gadget"] = new_name
            indexed = equipment.pop(old_name)
            indexed["image_url"] = gadget["image_url"]
            equipment[new_name] = indexed

    new_buffy_descriptions = {
        "AMBER": {
            "gadgets": {
                "FIRE STARTERS": "Amber can place up to 2 barrels.",
                "DANCING FLAMES": "Amber gains 20% movement speed and deals 400 damage to enemies she touches.",
            },
            "star_powers": {
                "WILD FLAMES": "Amber gains 10% movement speed when near oil.",
                "SCORCHIN' SIPHON": "Burn duration is increased by 1 second.",
            },
            "hypercharge": "Main attacks also burn like oil.",
        },
        "CHUCK": {
            "gadgets": {
                "REROUTING": "Chuck gains a 20% shield for 5 seconds.",
                "GHOST TRAIN": "The Super leaves a trail of fire that deals 1200 damage and burns for 3 seconds.",
            },
            "star_powers": {
                "PIT STOP": "Posts leave an area that deals 200 damage over 4 seconds.",
                "TICKETS PLEASE!": "Super dash speed is increased by 25%.",
            },
            "hypercharge": "Chuck's main attack shoots 3 clouds of steam in a cone.",
        },
        "EL PRIMO": {
            "gadgets": {
                "SUPLEX SUPPLEMENT": "El Primo slams enemies into the ground, dealing 1000 area damage.",
                "ASTEROID BELT": "Destroyed projectiles also charge El Primo's Super.",
            },
            "star_powers": {
                "EL FUEGO": "Punching a burning enemy extends the burn for 4 seconds.",
                "METEOR RUSH": "The speed boost also grants a 20% shield.",
            },
            "hypercharge": "Main attacks are bigger and light enemies on fire for 2 seconds.",
        },
        "GUS": {
            "gadgets": {
                "KOOKY POPPER": "Nearby enemies lose 1 ammo.",
                "KNOCKBACK SPIRIT": "Creates a spirit for each enemy hit.",
            },
            "star_powers": {
                "HEALTH BONANZA": "Spirits move toward the nearest ally.",
                "SPIRIT ANIMAL": "Spooky also gives a teammate a 15% speed boost for 5 seconds.",
            },
            "hypercharge": "Gus' main attack becomes larger and can go through walls.",
        },
        "POCO": {
            "gadgets": {
                "TUNING FORK": "Teammates inside the healing circle also gain 25% reload speed.",
                "PROTECTIVE TUNES": "The area is larger and lasts longer.",
            },
            "star_powers": {
                "DA CAPO!": "Hitting full-health teammates gives them 10% Super Charge Rate for 3 seconds.",
                "SCREECHING SOLO": "Enemies hit by the Super are silenced for 0.5 seconds.",
            },
            "hypercharge": "Main attacks fire in a 180-degree cone.",
        },
        "SHADE": {
            "gadgets": {
                "LONGARMS": "Damaged enemies are pulled toward the center of the hug.",
                "JUMP SCARE": "Shade gains a 2000-health shield when jumping.",
            },
            "star_powers": {
                "SPOOKY SPEEDSTER": "Hitting opponents also reduces Gadget cooldown by 15%.",
                "HARDENED HOODIE": "Incorporeal Form lasts 1 second longer.",
            },
            "hypercharge": "The center of Shade's hugs has increased damage and size.",
        },
    }
    guide_by_name = {guide["name"]: guide for guide in guides.values()}
    for name, descriptions in new_buffy_descriptions.items():
        guide = guide_by_name[name]
        for collection in ("gadgets", "star_powers"):
            by_name = descriptions[collection]
            for ability in guide[collection]:
                ability["buffie_description"] = by_name[ability["name"]]
        guide["hypercharge"]["buffie_description"] = descriptions["hypercharge"]

    new_buffy_groups = [
        ("Mexican Entertainers", ["El Primo", "Poco", "Amber"]),
        ("Ghost Station", ["Gus", "Chuck", "Shade"]),
    ]
    existing_buffy_names = {
        brawler["name"]
        for trio in buffies["trios"]
        for brawler in trio["brawlers"]
    }
    new_titles: list[str] = []
    for _, names in new_buffy_groups:
        for name in names:
            new_titles.extend(
                f"File:{name} Buffie-{category}.png"
                for category in ("Gadget", "Star", "Hyper")
            )
    image_info = wiki_image_info(new_titles)
    for trio_name, names in new_buffy_groups:
        entries = []
        for name in names:
            if name in existing_buffy_names:
                continue
            entry = {"name": name}
            for category, field in (
                ("Gadget", "gadget_img_file"),
                ("Star", "star_img_file"),
                ("Hyper", "hyper_img_file"),
            ):
                title = f"File:{name} Buffie-{category}.png"
                entry[field] = title
                buffies["image_urls"][title] = image_info[title]["url"]
            entries.append(entry)
        if entries:
            buffies["trios"].append({"trio": trio_name, "brawlers": entries})

    client_buffy_names = set()
    for card in cards:
        if card["Type"] != "buddy":
            continue
        display_name = text_by_tid[character_by_name[card["Target"]]["TID"]]
        if display_name in guide_names:
            client_buffy_names.add(display_name)
    buffies["released_brawlers"] = sorted(client_buffy_names)

    sources["checked_at"] = "2026-09-02"
    sources["client_asset_version"] = CLIENT_VERSION
    sources["sync"]["guides"] = len(guides)
    sources["sync"]["hypercharge_descriptions"] = len(guides)
    sources["sync"]["buffie_descriptions"] = sum(
        sum(bool(item.get("buffie_description")) for item in guide["gadgets"])
        + sum(bool(item.get("buffie_description")) for item in guide["star_powers"])
        + bool(guide["hypercharge"].get("buffie_description"))
        for guide in guides.values()
    )

    save_json(guides_path, guides)
    save_json(equipment_path, equipment)
    save_json(buffies_path, buffies)
    save_json(sources_path, sources)
    print(
        json.dumps(
            {
                "client_version": CLIENT_VERSION,
                "guides_checked": len(guides),
                "hypercharge_names_corrected": hypercharge_name_changes,
                "released_hypercharges": len(guides),
                "buffy_brawlers": len(client_buffy_names),
                "gadget_reworks": len(gadget_reworks),
                "wiki_name_anomalies_rejected": wiki_name_anomalies,
                "future_brawlers_not_published": ["COSMO", "VINCE"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
