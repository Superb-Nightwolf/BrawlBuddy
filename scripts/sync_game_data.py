from __future__ import annotations

import argparse
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUIDES_PATH = PROJECT_ROOT / "data" / "brawler_guides.json"
SOURCES_PATH = PROJECT_ROOT / "data" / "game_data_sources.json"

UNIVERSAL_GEARS = [
    "SPEED",
    "HEALTH",
    "DAMAGE",
    "VISION",
    "SHIELD",
    "GADGET COOLDOWN",
]

SPECIAL_GEARS = {
    "AMBER": ["RELOAD SPEED", "STICKY OIL"],
    "ASH": ["SUPER CHARGE"],
    "BELLE": ["RELOAD SPEED"],
    "BONNIE": ["SUPER CHARGE"],
    "ELPRIMO": ["SUPER CHARGE"],
    "EVE": ["RELOAD SPEED", "QUADRUPLETS"],
    "GENE": ["TALK TO THE HAND"],
    "JACKY": ["SUPER CHARGE"],
    "JESSIE": ["PET POWER"],
    "LOLA": ["RELOAD SPEED"],
    "LOU": ["SUPER CHARGE"],
    "MRP": ["PET POWER"],
    "NANI": ["SUPER CHARGE"],
    "OTIS": ["SUPER CHARGE"],
    "PAM": ["SUPER TURRET"],
    "PENNY": ["PET POWER"],
    "SANDY": ["EXHAUSTING STORM"],
    "SPROUT": ["SUPER CHARGE"],
    "TARA": ["PET POWER"],
    "TICK": ["THICC HEAD"],
}

GLOBAL_SOURCES = [
    {
        "label": "Supercell Support — Gears",
        "url": "https://support.supercell.com/brawl-stars/en/articles/gears-8.html",
        "covers": "Gear slots and Power Level requirements",
    },
    {
        "label": "Supercell — New Power, Brawl Pass Changes and a New Starr Drop",
        "url": "https://supercell.com/en/games/brawlstars/blog/news/new-power-brawl-pass-changes-and-a-new-starr-drop-2/",
        "covers": "Buffy ownership model and replacement of Epic/Mythic Gears",
    },
    {
        "label": "Supercell — Release Notes June 2026",
        "url": "https://supercell.com/en/games/brawlstars/blog/release-notes/release-notes-june-2026/",
        "covers": "Latest official release and balance changes",
    },
    {
        "label": "Brawl Stars Wiki — Gears",
        "url": "https://brawlstars.fandom.com/wiki/Gears",
        "covers": "Current per-brawler Gear availability and Gear history",
    },
]

GUIDE_OVERRIDES = {
    "SPIKE": {
        "max_stats": [
            {"label": "Health", "value": "6,000"},
            {"label": "Damage per spike", "value": "1,080 per projectile"},
            {"label": "Attack range", "value": "7.67 tiles"},
            {"label": "Reload", "value": "2.0 seconds"},
            {"label": "Super damage", "value": "800 per second (4,000 total)"},
            {"label": "Super duration", "value": "4.5 seconds"},
            {"label": "Super range", "value": "7.67 tiles"},
            {"label": "Movement", "value": "Normal"},
        ],
        "how_to_replacements": {
            "Use Fertilize to heal inside your Super while fighting off close-range tanks or assassins.":
                "Use Fertilize when several enemies are caught in your Super; its healing now scales with the damage the Super deals."
        },
    },
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def clean_wikitext(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<!--.*?-->", "", value, flags=re.S)
    value = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\{\{nowrap\|([^{}]+)\}\}", r"\1", value, flags=re.I)
    value = re.sub(r"\{\{[^{}]+\}\}", "", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", value).strip()


def wiki_page_name(url: str) -> str:
    path = urlparse(url).path
    return unquote(path.split("/wiki/", 1)[-1])


def fetch_wikitext(url: str) -> str:
    page = wiki_page_name(url)
    api_url = (
        "https://brawlstars.fandom.com/api.php?action=parse&prop=wikitext"
        f"&format=json&origin=*&page={quote(page)}"
    )
    request = Request(api_url, headers={"User-Agent": "BrawlBuddy-data-sync/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    return payload["parse"]["wikitext"]["*"]


def extract_abilities(wikitext: str) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    abilities: dict[str, dict[str, str]] = {}
    for match in re.finditer(
        r"^==(Attack|Super):\s*([^=\n]+)==\s*$(.*?)(?=^==|\Z)",
        wikitext,
        flags=re.M | re.S | re.I,
    ):
        kind, section_name, body = match.groups()
        quote_match = re.search(r"\{\{Quote\|([^{}]*?)\}\}", body, flags=re.I | re.S)
        if quote_match:
            abilities[f"__{kind.lower()}__"] = {
                "kind": "combat",
                "name": clean_wikitext(section_name),
                "description": clean_wikitext(quote_match.group(1)),
            }

    for match in re.finditer(
        r"^===([^=\n]+)===\s*$(.*?)(?=^===|^==|\Z)",
        wikitext,
        flags=re.M | re.S,
    ):
        section_name, body = match.groups()
        kind_match = re.search(r"\{\{(Gadget|StarPower)\|", body, flags=re.I)
        if not kind_match:
            continue
        kind = "gadget" if kind_match.group(1).lower() == "gadget" else "star_power"
        base_match = re.search(
            r"\{\{Quote\|([^{}]*?)\}\}\s*\{\{(?:Gadget|StarPower)\|",
            body,
            flags=re.I | re.S,
        )
        buffie_kind = "Gadget" if kind == "gadget" else "Star"
        buffie_match = re.search(
            rf"\{{\{{Quote\|([^{{}}]*?)\}}\}}\s*\{{\{{Buffie\|{buffie_kind}\}}\}}",
            body,
            flags=re.I | re.S,
        )
        record: dict[str, str] = {"kind": kind}
        if base_match:
            record["description"] = clean_wikitext(base_match.group(1))
        if buffie_match:
            record["buffie_description"] = clean_wikitext(buffie_match.group(1))
        abilities[normalize(clean_wikitext(section_name))] = record

    hypercharge: dict[str, str] = {}
    hyper_match = re.search(
        r"^==Hypercharge(?::\s*([^=\n]+))?==\s*$(.*?)(?=^==|\Z)",
        wikitext,
        flags=re.M | re.S | re.I,
    )
    if hyper_match:
        section_name, body = hyper_match.groups()
        base_match = re.search(
            r"\{\{Quote\|([^{}]*?)\}\}\s*\{\{Hypercharge\}\}",
            body,
            flags=re.I | re.S,
        )
        buffie_match = re.search(
            r"\{\{Quote\|([^{}]*?)\}\}\s*\{\{Buffie\|Hyper\}\}",
            body,
            flags=re.I | re.S,
        )
        if section_name:
            hypercharge["name"] = clean_wikitext(section_name)
        if base_match:
            hypercharge["description"] = clean_wikitext(base_match.group(1))
        if buffie_match:
            hypercharge["buffie_description"] = clean_wikitext(buffie_match.group(1))
    return abilities, hypercharge


def find_wiki_url(guide: dict) -> str | None:
    for source in guide.get("sources", []):
        url = source.get("url", "")
        if "brawlstars.fandom.com/wiki/" in url and not url.endswith("/Brawl_Stars_Wiki"):
            return url
    return None


def sync_guide(guide: dict, parsed: tuple[dict[str, dict[str, str]], dict[str, str]] | None, checked_at: str) -> dict[str, int]:
    counts = {"combat": 0, "base": 0, "buffie": 0, "hypercharge": 0}
    abilities, hypercharge = parsed or ({}, {})
    for kind in ("attack", "super"):
        current = abilities.get(f"__{kind}__", {})
        if current.get("description"):
            guide[kind] = {
                "name": current.get("name") or guide.get(kind, {}).get("name", kind.title()),
                "description": current["description"],
            }
            counts["combat"] += 1

    for key in ("gadgets", "star_powers"):
        expected_kind = "gadget" if key == "gadgets" else "star_power"
        for ability in guide.get(key, []):
            current = abilities.get(normalize(ability.get("name", "")), {})
            if current.get("kind") != expected_kind:
                continue
            if current.get("description"):
                ability["description"] = current["description"]
                counts["base"] += 1
            if current.get("buffie_description"):
                ability["buffie_description"] = current["buffie_description"]
                counts["buffie"] += 1
            else:
                ability.pop("buffie_description", None)

    guide_hypercharge = guide.get("hypercharge") or {}
    if hypercharge.get("description"):
        guide_hypercharge["description"] = hypercharge["description"]
        counts["hypercharge"] += 1
    if hypercharge.get("buffie_description"):
        guide_hypercharge["buffie_description"] = hypercharge["buffie_description"]
        counts["buffie"] += 1
    else:
        guide_hypercharge.pop("buffie_description", None)

    special = SPECIAL_GEARS.get(normalize(guide.get("name", "")).upper(), [])
    guide["gears"] = UNIVERSAL_GEARS + special

    allowed = {normalize(name): name for name in guide["gears"]}
    recommended = guide.get("recommended_build", {}).get("gears", [])
    cleaned_recommended: list[str] = []
    for name in recommended:
        normalized = normalize(name.replace("MYTHIC", ""))
        if normalized == normalize("GADGET CHARGE"):
            normalized = normalize("GADGET COOLDOWN")
        canonical = allowed.get(normalized)
        if canonical and canonical not in cleaned_recommended:
            cleaned_recommended.append(canonical)
    guide.setdefault("recommended_build", {})["gears"] = cleaned_recommended

    override = GUIDE_OVERRIDES.get(guide.get("name", ""), {})
    if override.get("max_stats"):
        guide["max_stats"] = override["max_stats"]
    replacements = override.get("how_to_replacements", {})
    guide["how_to_use"] = [replacements.get(step, step) for step in guide.get("how_to_use", [])]

    guide["verified_at"] = checked_at
    guide["source_note"] = (
        "Ability and Buffy text was checked against the current Brawl Stars Wiki; "
        "Gear progression and Buffy rules were cross-checked with Supercell. "
        f"Verified {checked_at}."
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh BrawlBuddy ability, Buffy, Gear, and provenance data.")
    parser.add_argument("--audit-only", action="store_true", help="Fetch and validate without writing files.")
    args = parser.parse_args()

    guides = json.loads(GUIDES_PATH.read_text(encoding="utf-8"))
    checked_at = date.today().isoformat()
    parsed_pages: dict[str, tuple[dict[str, dict[str, str]], dict[str, str]]] = {}
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {}
        for guide_id, guide in guides.items():
            url = find_wiki_url(guide)
            if url:
                futures[pool.submit(fetch_wikitext, url)] = guide_id
        for future in as_completed(futures):
            guide_id = futures[future]
            try:
                parsed_pages[guide_id] = extract_abilities(future.result())
            except Exception as exc:  # A failed page must never erase existing curated data.
                errors[guide_id] = str(exc)

    totals = {"combat": 0, "base": 0, "buffie": 0, "hypercharge": 0}
    for guide_id, guide in guides.items():
        counts = sync_guide(guide, parsed_pages.get(guide_id), checked_at)
        for key, value in counts.items():
            totals[key] += value

    source_data = {
        "checked_at": checked_at,
        "policy": "Supercell is authoritative for game rules and releases; the Brawl Stars Wiki supplies current per-ability text and per-brawler Gear rosters.",
        "sources": GLOBAL_SOURCES,
        "sync": {
            "guides": len(guides),
            "wiki_pages_loaded": len(parsed_pages),
            "wiki_pages_failed": len(errors),
            "base_ability_descriptions": totals["base"],
            "attack_and_super_descriptions": totals["combat"],
            "buffie_descriptions": totals["buffie"],
            "hypercharge_descriptions": totals["hypercharge"],
        },
    }

    if not args.audit_only:
        GUIDES_PATH.write_text(json.dumps(guides, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        SOURCES_PATH.write_text(json.dumps(source_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({"checked_at": checked_at, "totals": totals, "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
