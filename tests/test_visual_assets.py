from __future__ import annotations

import hashlib
import json
import struct
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = PROJECT_ROOT / "app" / "ui"
DATA_DIR = PROJECT_ROOT / "data"


def _load(name: str) -> dict:
    with (DATA_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:33]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", path
    assert header[12:16] == b"IHDR", path
    assert header[25] in {4, 6} or b"tRNS" in path.read_bytes(), path
    return struct.unpack(">II", header[16:24])


def test_visual_asset_manifest_is_available_and_complete() -> None:
    with TestClient(app) as client:
        catalog = client.get("/api/brawlers/catalog").json()["list"]
        response = client.get("/api/visual-assets")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["schema_version"] == 1
    assert manifest["client"]["version"] == "69.230"
    assert set(manifest["brawlers"]) == {str(item["id"]) for item in catalog}


def test_individual_asset_mappings_are_unique_valid_and_match_release_status() -> None:
    manifest = _load("visual_asset_manifest.json")
    guides = _load("brawler_guides.json")
    hashes: set[str] = set()
    hypercharge_count = 0
    buffy_counts = {"gadget": 0, "star_power": 0, "hypercharge": 0}

    for brawler_id, entry in manifest["brawlers"].items():
        hypercharge = entry["hypercharge"]
        assert hypercharge["released"] is bool(
            guides[brawler_id]["hypercharge"]["released"]
        )
        if hypercharge["released"]:
            hypercharge_count += 1
            assert guides[brawler_id]["hypercharge"]["image_url"] == hypercharge["local_url"]
            artworks = [hypercharge]
        else:
            assert hypercharge["local_url"] is None
            artworks = []

        buffies = entry["buffies"]
        for category in buffy_counts:
            artwork = buffies[category]
            assert artwork["released"] is buffies["released"]
            if artwork["released"]:
                buffy_counts[category] += 1
                artworks.append(artwork)
            else:
                assert artwork["local_url"] is None

        for artwork in artworks:
            path = UI_DIR / artwork["local_url"].lstrip("/")
            assert path.is_file(), path
            assert _png_dimensions(path) == (artwork["width"], artwork["height"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == artwork["local_sha256"]
            assert digest not in hashes, path
            hashes.add(digest)
            assert artwork["wiki_file"].startswith("File:")
            assert artwork["source_url"].startswith("https://static.wikia.nocookie.net/")

    assert hypercharge_count == 106
    assert buffy_counts == {"gadget": 27, "star_power": 27, "hypercharge": 27}
    assert len(hashes) == 187


def test_visual_asset_fallbacks_are_local_and_ordered_by_specificity() -> None:
    manifest = _load("visual_asset_manifest.json")
    fallbacks = manifest["fallbacks"]

    assert fallbacks["hypercharge"] == [
        "/assets/section_hypercharge.png",
        "/assets/hypercharge_icon.webp",
    ]
    assert fallbacks["buffy"]["gadget"][0] == "/assets/section_gadget.png"
    assert fallbacks["buffy"]["star_power"][0] == "/assets/section_star_power.png"
    assert fallbacks["buffy"]["hypercharge"][0] == "/assets/section_hypercharge.png"
    assert fallbacks["buffy_unreleased"] == [
        "/assets/buffies/generic.png",
        "/assets/buffie_icon.webp",
    ]
    for sources in [
        fallbacks["hypercharge"],
        *fallbacks["buffy"].values(),
        fallbacks["buffy_unreleased"],
    ]:
        assert sources[-1] in {
            "/assets/hypercharge_icon.webp",
            "/assets/buffie_icon.webp",
        }
        for url in sources:
            assert (UI_DIR / url.lstrip("/")).is_file(), url


def test_all_equipment_and_gear_icons_are_local_valid_pngs() -> None:
    guides = _load("brawler_guides.json")
    equipment = _load("equipment_ids.json")
    manifest = _load("visual_asset_manifest.json")
    paths: set[Path] = set()

    for brawler_id, guide in guides.items():
        for collection, folder in (
            ("gadgets", "gadgets"),
            ("star_powers", "star-powers"),
        ):
            for item in guide[collection]:
                assert item["image_url"] == f"/assets/equipment/{folder}/{item['id']}.png"
                assert item["source_url"] == (
                    f"https://cdn.brawlify.com/{folder}/regular/{item['id']}.png"
                )
                assert equipment[item["name"]]["brawler_id"] == brawler_id
                path = UI_DIR / item["image_url"].lstrip("/")
                assert path.is_file()
                _png_dimensions(path)
                paths.add(path)

    assert len(paths) == 424
    assert len(manifest["gears"]) == 15
    for gear in manifest["gears"].values():
        path = UI_DIR / gear["local_url"].lstrip("/")
        assert path.is_file()
        assert _png_dimensions(path) == (gear["width"], gear["height"])


def test_buffy_file_keys_and_release_list_match_confirmed_manifest() -> None:
    buffies = _load("buffies_db.json")
    manifest = _load("visual_asset_manifest.json")
    released = {
        entry["name"]
        for entry in manifest["brawlers"].values()
        if entry["buffies"]["released"]
    }
    assert set(buffies["released_brawlers"]) == released
    assert "SURGE" in released
    assert {"AMBER", "CHUCK", "EL PRIMO", "GUS", "POCO", "SHADE"}.issubset(released)

    mapped_files = []
    for trio in buffies["trios"]:
        for brawler in trio["brawlers"]:
            mapped_files.extend(
                brawler[field]
                for field in ("gadget_img_file", "star_img_file", "hyper_img_file")
            )
    assert len(mapped_files) == 81
    assert len(set(mapped_files)) == 81
    assert set(mapped_files).issubset(buffies["image_urls"])


def test_released_brawlers_use_their_own_three_buffy_icons() -> None:
    manifest = _load("visual_asset_manifest.json")
    for brawler_id, entry in manifest["brawlers"].items():
        buffies = entry["buffies"]
        if not buffies["released"]:
            continue
        urls = {
            category: buffies[category]["local_url"]
            for category in ("gadget", "star_power", "hypercharge")
        }
        assert urls == {
            "gadget": f"/assets/equipment/buffies/{brawler_id}-gadget.png",
            "star_power": f"/assets/equipment/buffies/{brawler_id}-star-power.png",
            "hypercharge": f"/assets/equipment/buffies/{brawler_id}-hypercharge.png",
        }
        assert len(set(urls.values())) == 3


def test_mode_and_class_icon_manifest_is_complete_and_local() -> None:
    manifest = _load("visual_asset_manifest.json")
    ui_icons = manifest["ui_icons"]
    assert len(ui_icons["modes"]) == 17
    assert set(ui_icons["classes"]) == {
        "damage-dealer", "tank", "marksman", "artillery",
        "assassin", "support", "controller",
    }
    assert {"gem-grab", "hot-zone", "brawl-ball", "showdown"}.issubset(
        ui_icons["modes"]
    )
    for group in ("modes", "classes"):
        for record in ui_icons[group].values():
            path = UI_DIR / record["local_url"].lstrip("/")
            assert path.is_file(), path
            assert _png_dimensions(path) == (record["width"], record["height"])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record["local_sha256"]
            assert record["mime"] == "image/png"
            assert record["aliases"]
    generic_buffie = ui_icons["buffie"]
    assert generic_buffie["local_url"] == "/assets/buffies/generic.png"
    generic_path = UI_DIR / generic_buffie["local_url"].lstrip("/")
    assert _png_dimensions(generic_path) == (
        generic_buffie["width"], generic_buffie["height"]
    )


def test_footer_content_date_is_generated_from_published_files() -> None:
    with TestClient(app) as client:
        status = client.get("/api/status").json()
        html = client.get("/").text
    updated = datetime.fromisoformat(status["content_last_updated"])
    assert updated.tzinfo is not None
    assert updated.timestamp() >= (DATA_DIR / "visual_asset_manifest.json").stat().st_mtime - 1
    assert 'id="content-last-updated"' in html


def test_every_catalog_and_detail_route_can_serve_its_local_images() -> None:
    manifest = _load("visual_asset_manifest.json")
    with TestClient(app) as client:
        catalog = client.get("/api/brawlers/catalog").json()["list"]
        for brawler in catalog:
            brawler_id = str(brawler["id"])
            assert client.get(f"/brawlers/{brawler_id}").status_code == 200
            assert client.get(f"/assets/brawlers/{brawler_id}.png").status_code == 200
            thumbnail_name = "16000108.png" if brawler_id == "16000108" else f"{brawler_id}.webp"
            assert client.get(f"/assets/brawlers/thumbs/{thumbnail_name}").status_code == 200
            hypercharge = manifest["brawlers"][brawler_id]["hypercharge"]
            if hypercharge["released"]:
                response = client.get(hypercharge["local_url"])
                assert response.status_code == 200
                assert response.headers["content-type"] == "image/png"


def test_september_client_changes_are_published_without_future_brawlers() -> None:
    guides = _load("brawler_guides.json")
    equipment = _load("equipment_ids.json")
    catalog = _load("brawler_catalog.json")

    assert guides["16000107"]["hypercharge"]["name"] == "MASTER FISHERMAN"
    assert guides["16000108"]["hypercharge"]["name"] == "GREEN ENERGY"
    assert guides["16000107"]["hypercharge"]["released"] is True
    assert guides["16000108"]["hypercharge"]["released"] is True

    expected_reworks = {
        "16000004": (23000409, "MULTIBALL"),
        "16000052": (23000489, "REPURPOSE"),
        "16000061": (23000514, "KNOCKBACK SPIRIT"),
    }
    for brawler_id, (item_id, name) in expected_reworks.items():
        gadget = next(item for item in guides[brawler_id]["gadgets"] if item["id"] == item_id)
        assert gadget["name"] == name
        assert equipment[name]["id"] == item_id
    assert {"BOUNCY CASTLE", "TOOLBOX", "SOUL SWITCHER"}.isdisjoint(equipment)

    catalog_names = {item["name"] for item in catalog}
    assert "COSMO" not in catalog_names
    assert "VINCE" not in catalog_names
