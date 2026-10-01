"""Publish Vince's cross-checked October profile without resyncing older brawlers.

The editorial build/maps are practice suggestions, not measured rankings. Run
the catalog audit after this targeted sync; it never fabricates matchup data.
"""
from __future__ import annotations

from datetime import date
import re

from sync_release_data import DATA_DIR, CLIENT_ROOT, fetch_csv, fetch_json, load_json, save_json
from sync_equipment_assets import ASSET_DIR, FANKIT_EQUIPMENT_SOURCES, local_metadata


BRAWLER_ID = 16000110
WIKI_URL = "https://brawlstars.fandom.com/wiki/Vince"
API_URL = f"https://api.brawlapi.com/v1/brawlers/{BRAWLER_ID}"
RELEASE_URL = "https://supercell.com/en/games/brawlstars/blog/release-notes/release-notes-august-2026/"


def main() -> None:
    remote = fetch_json(API_URL)
    expected = {23001450: "COME TO PAPA", 23001451: "BUG BANDAGE",
                23001452: "HOT COFFEE", 23001453: "METAMOTHOSIS"}
    actual = {item["id"]: item["name"].upper()
              for key in ("gadgets", "starPowers") for item in remote[key]}
    if remote["name"].upper() != "VINCE" or remote["rarity"]["name"] != "Mythic" or actual != expected:
        raise RuntimeError("Vince's remote identity/kit changed; review before publishing.")

    wiki = fetch_json("https://brawlstars.fandom.com/api.php?action=parse&prop=wikitext&format=json&page=Vince")["parse"]["wikitext"]["*"]
    for pattern in (r"Health\s*=\s*3400", r"Attack\s*=\s*1100", r"Reload\s*=\s*1\.45 seconds",
                    r"Gadget1Cooldown\s*=\s*15 seconds", r"Gadget2Cooldown\s*=\s*13 seconds",
                    r"Turning a caterpillar into a moth heals Vince for 1200"):
        if not re.search(pattern, wiki):
            raise RuntimeError(f"Vince's Wiki facts changed: {pattern}; review before publishing.")

    characters = fetch_csv("csv_logic/characters.csv")
    character = next(row for row in characters if row["Name"] == "Stacker")
    skills = {row["Name"]: row for row in fetch_csv("csv_logic/skills.csv")}
    attack, super_skill = skills["StackerWeapon"], skills["StackerUlti"]
    cards = fetch_csv("csv_logic/cards.csv")
    healing = next(row for row in cards if row["Name"] == "Stacker_unique_2")
    if healing["Value"] != "600" or character["ClassArchetype"] != "damage_dealer":
        raise RuntimeError("Vince's healing or class changed; review before publishing.")
    if (character["Hitpoints"], attack["Damage"], attack["CastingRange"],
        attack["RechargeTime"], super_skill["Damage"], super_skill["CastingRange"]) != (
            "3400", "1100", "25", "1450", "400", "27"):
        raise RuntimeError("Vince's snapshot stats changed; review level scaling.")

    checked = date.today().isoformat()
    guide = {
        "id": BRAWLER_ID, "name": "VINCE", "rarity": "Mythic", "class": "Damage Dealer",
        "intro": "Vince is a ranged damage dealer who converts nearby caterpillars into a moth collection. His Super marks enemies for stronger follow-up coffee shots and gains additional effects as his collection grows. Defeat removes half of his stored moths.",
        "trait": {"name": "Caterpillars", "description": "Collect caterpillars by walking over them or hitting them with coffee. They become moths; defeat removes 50% of the collection, with the remainder rounded down."},
        "attack": {"name": "Espresso Shot", "description": "A single coffee projectile damages its target and can convert a caterpillar into a collected moth."},
        "super": {"name": "Barista Barrage", "description": "Applies a Caterpillar debuff so Vince's main attacks deal bonus damage. Below 5 moths it fires one projectile; at 5+ it fires three and reloads one ammo per Brawler hit; at 10+ it fires five and can bounce to nearby enemies; at 20+ it fires seven and also slows enemies."},
        "max_stats": [
            {"label": "Health", "value": "6,800"},
            {"label": "Base attack damage", "value": "2,200"},
            {"label": "Attack range", "value": "8.33 tiles"},
            {"label": "Reload", "value": "1.45 seconds"},
            {"label": "Base Super damage", "value": "800 per projectile"},
            {"label": "Super range", "value": "9.0 tiles"},
            {"label": "Super projectiles", "value": "1 / 3 / 5 / 7"},
            {"label": "Movement", "value": "Normal (750)"},
        ],
        "how_to_use": [
            "Collect caterpillars along safe routes; walking over one preserves ammo for lane pressure.",
            "Land Barista Barrage before your coffee shots to use its marked-target damage bonus.",
            "Protect a large collection: defeat removes half your moths and can reduce your Super stage.",
            "Use Metamothosis when nearby caterpillars are available; it doubles the moths collected rather than creating new caterpillars.",
            "Try Bug Bandage for sustain while collecting, or Come to Papa to bring caterpillars closer.",
            "Practice the 5, 10, and 20 moth thresholds to learn the extra projectiles, ammo reload, bounce, and slow effects.",
        ],
        "strengths": [
            "Long-range coffee shots support sustained lane pressure",
            "Marked enemies take extra damage from follow-up main attacks",
            "A growing collection adds utility and projectiles to the Super",
            "Gadgets offer either aimed area damage or faster collection",
        ],
        "watch_out_for": [
            "Defeat removes half the moth collection",
            "Risky collection detours can surrender positioning and objectives",
            "A Super mark needs accurate follow-up shots to realize its damage bonus",
            "Build and map suggestions are provisional; verified matchup samples are not available",
        ],
        "mode_fit": ["Gem Grab", "Hot Zone", "Brawl Ball", "Knockout"],
        "gadgets": [
            {"id": 23001452, "name": "HOT COFFEE", "description": "Throw an aimed explosive cappuccino for area damage. Cooldown: 15 seconds."},
            {"id": 23001453, "name": "METAMOTHOSIS", "description": "Convert nearby caterpillars into moths, gaining an additional moth per caterpillar collected. Cooldown: 13 seconds."},
        ],
        "star_powers": [
            {"id": 23001450, "name": "COME TO PAPA", "description": "Nearby caterpillars crawl toward Vince."},
            {"id": 23001451, "name": "BUG BANDAGE", "description": "Converting a caterpillar into a moth restores 1,200 health at Power 11."},
        ],
        "hypercharge": {"released": False, "name": "Unreleased", "description": "No released Hypercharge is confirmed for Vince.", "image_url": None},
        "recommended_build": {"gadget": "METAMOTHOSIS", "star_power": "BUG BANDAGE", "gears": ["SHIELD", "DAMAGE"],
                              "note": "Provisional practice build: pair collection with healing. Try Hot Coffee for area pressure or Come to Papa for easier pickups. Modes and maps below are mechanics-based practice suggestions, not measured best picks."},
        "gears": ["SPEED", "HEALTH", "DAMAGE", "VISION", "SHIELD", "GADGET COOLDOWN"],
        "release_status": {"catalog_listed": True, "brawlapi_released": remote["released"], "unlock_date_confirmed": False,
                           "note": "Listed by Brawlify as released; other references still describe an upcoming October launch. An exact in-game unlock date is not independently confirmed."},
        "source_note": f"Vince only checked {checked}: identity and equipment IDs from BrawlAPI; mechanics from Supercell and the Wiki; numeric stats cross-checked with the 69.230 client snapshot. Unlock timing remains unconfirmed. No released Hypercharge or Buffies are confirmed. Build, mode, and map suggestions are provisional, not measured rankings.",
        "sources": [{"label": "Brawl Stars Wiki - Vince", "url": WIKI_URL},
                    {"label": "Supercell - August 2026 release notes", "url": RELEASE_URL},
                    {"label": "BrawlAPI - Vince IDs and release flag", "url": API_URL},
                    {"label": "Client data snapshot 69.230 (community mirror)", "url": CLIENT_ROOT + "/csv_logic/skills.csv"}],
        "verified_at": checked,
    }

    # Keep practice maps in the same local catalog format; do not imply win rates.
    maps = load_json(DATA_DIR / "maps_catalog.json")
    guide["useful_maps"] = [maps[str(ident)] for ident in (15001319, 15000300, 15000132, 15001318)]
    catalog = load_json(DATA_DIR / "brawler_catalog.json")
    guides = load_json(DATA_DIR / "brawler_guides.json")
    equipment = load_json(DATA_DIR / "equipment_ids.json")
    manifest = load_json(DATA_DIR / "visual_asset_manifest.json")
    sources = load_json(DATA_DIR / "game_data_sources.json")
    matchups = load_json(DATA_DIR / "brawler_matchups.json")

    for collection, kind, folder in (("gadgets", "gadget", "gadgets"), ("star_powers", "star_power", "star-powers")):
        for item in guide[collection]:
            # Preserve verified original FanKit assets. CDN previews contain
            # red notification badges and must never overwrite these files.
            source = FANKIT_EQUIPMENT_SOURCES[item['id']]
            metadata = local_metadata(source, ASSET_DIR / folder / f"{item['id']}.png")
            item.update(image_url=metadata["local_url"], source_url=source)
            equipment[item["name"]] = {"id": item["id"], "type": kind, "brawler_id": str(BRAWLER_ID), "brawler_name": "VINCE",
                                      "image_url": item["image_url"], "source_url": source}

    if not any(item["id"] == BRAWLER_ID for item in catalog):
        catalog.append({key: guide[key] for key in ("id", "name", "rarity", "class")})
    guides[str(BRAWLER_ID)] = guide
    manifest["brawlers"][str(BRAWLER_ID)] = {"name": "VINCE", "hypercharge": {"released": False, "local_url": None},
        "buffies": {"released": False, **{category: {"released": False, "local_url": None}
                                          for category in ("gadget", "star_power", "hypercharge")}}}
    for collection in ("gadgets", "star_powers"):
        manifest["equipment"][collection] = sum(len(item[collection]) for item in guides.values())
    overrides = manifest["equipment"]["official_overrides"]
    overrides["equipment_ids"] = sorted(FANKIT_EQUIPMENT_SOURCES)
    overrides.setdefault("assets", {})
    for collection, folder in (("gadgets", "gadgets"), ("star_powers", "star-powers")):
        for index, item in enumerate(guide[collection], start=1):
            overrides["assets"][str(item["id"])] = {
                **local_metadata(item["source_url"], ASSET_DIR / folder / f"{item['id']}.png"),
                "source_file": f"{'gadget' if collection == 'gadgets' else 'starpower'}_vince_{index}.png",
                "checked_at": checked,
            }

    # The generic service fallback invents rates, so explicitly publish no sample.
    matchups[str(BRAWLER_ID)] = {"brawler_id": BRAWLER_ID, "brawler_name": "VINCE", "strong_against": [],
        "struggles_against": [], "best_alongside": [], "methodology": {"source": "NO VERIFIED MATCHUP SAMPLE",
        "checked_at": checked, "sample_size": None, "status": "unavailable"}}
    sources["sync"]["guides"] = len(guides)
    sources.setdefault("brawler_updates", {})[str(BRAWLER_ID)] = {"checked_at": checked, "name": "VINCE",
        "sources": guide["sources"], "scope": "Vince identity, abilities, stats, equipment and artwork only; older brawlers were not reverified.",
        "unlock_date_confirmed": False, "client_asset_version": "69.230"}
    for filename, payload in (("brawler_catalog.json", catalog), ("brawler_guides.json", guides),
                              ("equipment_ids.json", equipment), ("visual_asset_manifest.json", manifest),
                              ("brawler_matchups.json", matchups), ("game_data_sources.json", sources)):
        save_json(DATA_DIR / filename, payload)
    print(f"Published Vince; catalog has {len(catalog)} brawlers. Unlock date and matchup samples remain unconfirmed.")


if __name__ == "__main__":
    main()
