from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_product_pages_and_surge_guide_are_available() -> None:
    with TestClient(app) as client:
        for path in ("/", "/brawlers", "/battles", "/events", "/leaderboards", "/brawlers/16000038"):
            response = client.get(path)
            assert response.status_code == 200
            assert "BrawlBuddy" in response.text

        guide = client.get("/api/guides/16000038").json()
        assert guide["name"] == "SURGE"
        assert len(guide["gadgets"]) == 2
        assert len(guide["star_powers"]) == 2


def test_penny_and_tara_have_full_curated_guides() -> None:
    with TestClient(app) as client:
        penny = client.get("/api/guides/16000019").json()
        tara = client.get("/api/guides/16000017").json()

    for guide in (penny, tara):
        assert len(guide["max_stats"]) >= 8
        assert len(guide["how_to_use"]) >= 5
        assert len(guide["gadgets"]) == 2
        assert len(guide["star_powers"]) == 2
        assert guide["hypercharge"]["name"]
        assert guide["recommended_build"]["gadget"]
        assert len(guide["strengths"]) >= 4
        assert len(guide["watch_out_for"]) >= 4
        assert guide["sources"][0]["url"].startswith("https://brawlstars.fandom.com/wiki/")

    assert penny["attack"]["name"] == "Plunderbuss"
    assert tara["super"]["name"] == "Gravity"


def test_next_ten_brawlers_have_full_curated_guides() -> None:
    expected = {
        16000020: "FRANK",
        16000021: "GENE",
        16000022: "TICK",
        16000023: "LEON",
        16000024: "ROSA",
        16000025: "CARL",
        16000026: "BIBI",
        16000027: "8-BIT",
        16000028: "SANDY",
        16000029: "BEA",
    }

    with TestClient(app) as client:
        guides = {brawler_id: client.get(f"/api/guides/{brawler_id}").json() for brawler_id in expected}

    for brawler_id, expected_name in expected.items():
        guide = guides[brawler_id]
        assert guide["name"] == expected_name
        assert len(guide["max_stats"]) == 8
        assert len(guide["how_to_use"]) == 5
        assert len(guide["gadgets"]) == 2
        assert len(guide["star_powers"]) == 2
        assert len(guide["strengths"]) == 4
        assert len(guide["watch_out_for"]) == 4
        assert guide["hypercharge"]["name"]
        assert guide["recommended_build"]["gadget"]
        assert guide["sources"][0]["url"].startswith("https://brawlstars.fandom.com/wiki/")


def test_second_batch_of_ten_brawlers_have_full_curated_guides() -> None:
    expected = {
        16000030: "EMZ",
        16000031: "MR. P",
        16000032: "MAX",
        16000034: "JACKY",
        16000035: "GALE",
        16000036: "NANI",
        16000037: "SPROUT",
        16000039: "COLETTE",
        16000040: "AMBER",
        16000041: "LOU",
    }

    with TestClient(app) as client:
        guides = {brawler_id: client.get(f"/api/guides/{brawler_id}").json() for brawler_id in expected}

    for brawler_id, expected_name in expected.items():
        guide = guides[brawler_id]
        assert guide["name"] == expected_name
        assert len(guide["max_stats"]) == 8
        assert len(guide["how_to_use"]) == 5
        assert len(guide["gadgets"]) == 2
        assert len(guide["star_powers"]) == 2
        assert len(guide["strengths"]) == 4
        assert len(guide["watch_out_for"]) == 4
        assert guide["hypercharge"]["name"]
        assert guide["recommended_build"]["gadget"]
        assert guide["sources"][0]["url"].startswith("https://brawlstars.fandom.com/wiki/")


def test_demo_contains_clickable_surge_account_progress() -> None:
    with TestClient(app) as client:
        payload = client.get("/api/demo/player").json()
    surge = next(item for item in payload["player"]["brawlers"] if item["id"] == 16000038)
    assert surge["power"] == 10
    assert surge["gadgets"][0]["name"] == "POWER SURGE"
    assert surge["star_powers"][0]["name"] == "TO THE MAX!"


def test_full_catalog_has_106_unique_brawlers_and_local_artwork() -> None:
    with TestClient(app) as client:
        payload = client.get("/api/brawlers/catalog").json()

    brawlers = payload["list"]
    assert payload["count"] == 106
    assert len(brawlers) == 106
    assert len({brawler["id"] for brawler in brawlers}) == 106
    assert len({brawler["name"] for brawler in brawlers}) == 106

    artwork_dir = Path("app/ui/assets/brawlers")
    missing = [brawler["name"] for brawler in brawlers if not (artwork_dir / f"{brawler['id']}.png").is_file()]
    assert missing == []

    thumbnail_dir = artwork_dir / "thumbs"
    missing_thumbnails = [
        brawler["name"] for brawler in brawlers
        if not (thumbnail_dir / f"{brawler['id']}.webp").is_file()
    ]
    assert missing_thumbnails == []


def test_penny_and_tara_use_distinct_canonical_ids() -> None:
    with TestClient(app) as client:
        player_brawlers = client.get("/api/demo/player").json()["player"]["brawlers"]
        catalog = client.get("/api/brawlers/catalog").json()["list"]

    penny = next(item for item in player_brawlers if item["name"] == "PENNY")
    tara = next(item for item in catalog if item["name"] == "TARA")
    assert penny["id"] == 16000019
    assert tara["id"] == 16000017
    assert penny["id"] != tara["id"]


def test_all_106_brawlers_have_complete_curated_guides() -> None:
    with TestClient(app) as client:
        catalog = client.get("/api/brawlers/catalog").json()["list"]
        for brawler in catalog:
            brawler_id = brawler["id"]
            name = brawler["name"]
            guide = client.get(f"/api/guides/{brawler_id}").json()
            
            assert guide["id"] == brawler_id, f"ID mismatch for {name}"
            assert guide["name"] == name, f"Name mismatch for {name}"
            assert guide["rarity"], f"Missing rarity for {name}"
            assert guide["class"], f"Missing class for {name}"
            assert guide["intro"], f"Missing intro for {name}"
            assert guide["attack"]["name"], f"Missing attack for {name}"
            assert guide["super"]["name"], f"Missing super for {name}"
            assert len(guide["max_stats"]) == 8, f"Expected 8 stats for {name}, got {len(guide['max_stats'])}"
            assert len(guide["how_to_use"]) >= 5, f"Expected 5 how_to_use for {name}"
            assert len(guide["strengths"]) >= 4, f"Expected 4 strengths for {name}"
            assert len(guide["watch_out_for"]) >= 4, f"Expected 4 watch_out_for for {name}"
            assert len(guide["mode_fit"]) >= 4, f"Expected 4 mode_fit for {name}"
            assert len(guide["gadgets"]) == 2, f"Expected 2 gadgets for {name}"
            assert len(guide["star_powers"]) == 2, f"Expected 2 star_powers for {name}"
            assert guide["hypercharge"]["name"], f"Missing hypercharge for {name}"
            assert guide["recommended_build"]["gadget"], f"Missing recommended gadget for {name}"
            assert guide["recommended_build"]["star_power"], f"Missing recommended star power for {name}"
            assert len(guide["sources"]) >= 2, f"Missing sources for {name}"
            assert guide["sources"][0]["url"].startswith("https://brawlstars.fandom.com/wiki/"), f"Invalid wiki url for {name}"


def test_spike_uses_current_gear_and_distinct_buffie_data() -> None:
    with TestClient(app) as client:
        spike = client.get("/api/guides/16000005").json()

    assert spike["gears"] == [
        "SPEED", "HEALTH", "DAMAGE", "VISION", "SHIELD", "GADGET COOLDOWN"
    ]
    assert "STICKY SPIKES" not in spike["recommended_build"]["gears"]
    assert next(item for item in spike["star_powers"] if item["name"] == "FERTILIZE")["description"] == (
        "Super heals for 75% of damage dealt."
    )
    assert next(item for item in spike["star_powers"] if item["name"] == "FERTILIZE")["buffie_description"] == (
        "Super projectile speed is 30% faster."
    )
    assert next(item for item in spike["star_powers"] if item["name"] == "CURVEBALL")["buffie_description"] == (
        "Curving spikes have extended range."
    )
    assert spike["hypercharge"]["buffie_description"] == "Main attack needle grenades detonate twice!"


def test_current_gear_roster_is_consistent_for_every_brawler() -> None:
    universal = ["SPEED", "HEALTH", "DAMAGE", "VISION", "SHIELD", "GADGET COOLDOWN"]
    special = {
        "AMBER": ["RELOAD SPEED", "STICKY OIL"],
        "ASH": ["SUPER CHARGE"],
        "BELLE": ["RELOAD SPEED"],
        "BONNIE": ["SUPER CHARGE"],
        "EL PRIMO": ["SUPER CHARGE"],
        "EVE": ["RELOAD SPEED", "QUADRUPLETS"],
        "GENE": ["TALK TO THE HAND"],
        "JACKY": ["SUPER CHARGE"],
        "JESSIE": ["PET POWER"],
        "LOLA": ["RELOAD SPEED"],
        "LOU": ["SUPER CHARGE"],
        "MR. P": ["PET POWER"],
        "NANI": ["SUPER CHARGE"],
        "OTIS": ["SUPER CHARGE"],
        "PAM": ["SUPER TURRET"],
        "PENNY": ["PET POWER"],
        "SANDY": ["EXHAUSTING STORM"],
        "SPROUT": ["SUPER CHARGE"],
        "TARA": ["PET POWER"],
        "TICK": ["THICC HEAD"],
    }

    with TestClient(app) as client:
        catalog = client.get("/api/brawlers/catalog").json()["list"]
        guides = [client.get(f"/api/guides/{item['id']}").json() for item in catalog]

    for guide in guides:
        assert guide["gears"] == universal + special.get(guide["name"], []), guide["name"]
    assert sum(len(guide["gears"]) == 6 for guide in guides) == 86
    assert sum(len(guide["gears"]) == 7 for guide in guides) == 18
    assert sum(len(guide["gears"]) == 8 for guide in guides) == 2


def test_data_source_metadata_is_current_and_cross_validated() -> None:
    with TestClient(app) as client:
        payload = client.get("/api/data-sources").json()

    assert payload["checked_at"] >= "2026-08-31"
    assert payload["sync"]["guides"] == 106
    assert payload["sync"]["wiki_pages_failed"] == 0
    urls = {source["url"] for source in payload["sources"]}
    assert "https://support.supercell.com/brawl-stars/en/articles/gears-8.html" in urls
    assert "https://brawlstars.fandom.com/wiki/Gears" in urls
