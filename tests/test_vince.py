from pathlib import Path
import json

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


ROOT = Path(__file__).resolve().parents[1]


def test_vince_complete_kit_and_source_conflicts_are_explicit() -> None:
    with TestClient(app) as client:
        guide = client.get("/api/guides/16000110").json()
        catalog = client.get("/api/brawlers/catalog").json()
    vince = next(item for item in catalog["list"] if item["id"] == 16000110)
    assert (vince["name"], vince["rarity"], vince["class"]) == ("VINCE", "Mythic", "Damage Dealer")
    assert [(item["id"], item["name"]) for item in guide["gadgets"]] == [
        (23001452, "HOT COFFEE"), (23001453, "METAMOTHOSIS")]
    assert [(item["id"], item["name"]) for item in guide["star_powers"]] == [
        (23001450, "COME TO PAPA"), (23001451, "BUG BANDAGE")]
    assert "1,200" in guide["star_powers"][1]["description"]
    assert "15 seconds" in guide["gadgets"][0]["description"]
    assert "13 seconds" in guide["gadgets"][1]["description"]
    assert guide["max_stats"][0]["value"] == "6,800"
    assert guide["max_stats"][1]["value"].startswith("2,200")
    assert guide["attack"]["name"] == "Espresso Shot"
    assert guide["super"]["name"] == "Barista Barrage"
    assert "20+" in guide["super"]["description"]
    assert "50%" in guide["trait"]["description"]
    assert guide["release_status"]["unlock_date_confirmed"] is False
    assert "provisional" in guide["source_note"]
    assert guide["hypercharge"]["released"] is False
    assert all("<!" not in item["description"] for key in ("gadgets", "star_powers") for item in guide[key])
    updates = json.loads((ROOT / "data/game_data_sources.json").read_text(encoding="utf-8"))
    assert updates["brawler_updates"]["16000110"]["checked_at"] == guide["verified_at"]


def test_vince_does_not_receive_fabricated_matchup_rates() -> None:
    with TestClient(app) as client:
        for endpoint, method in (("/api/brawlers/16000110/matchups", "get"),
                                 ("/api/brawlers/16000110/matchups/refresh", "post")):
            result = getattr(client, method)(endpoint).json()
            assert result["strong_against"] == []
            assert result["struggles_against"] == []
            assert result["best_alongside"] == []
            assert result["methodology"]["status"] == "unavailable"
            assert result["methodology"]["sample_size"] is None


def test_vince_official_and_generated_artwork_are_separate_and_valid() -> None:
    base = ROOT / "app/ui/assets/brawlers"
    hero_manifest = json.loads((base / "hero-artwork.json").read_text(encoding="utf-8"))
    entry = hero_manifest["16000110"]
    assert entry["initial"] == "generated"
    assert entry["official"] != entry["generated"]
    with TestClient(app) as client:
        for local_url in (entry["official"], entry["generated"], "/assets/brawlers/16000110.png"):
            response = client.get(local_url)
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/png"
            path = ROOT / "app/ui" / local_url.lstrip("/")
            with Image.open(path) as image:
                assert image.format == "PNG"
                assert image.mode == "RGBA" or "transparency" in image.info
                assert image.convert("RGBA").getchannel("A").getextrema() == (0, 255)
        assert client.get("/assets/brawlers/thumbs/16000110.webp").status_code == 200
        assert client.get("/brawlers/16000110").status_code == 200
    with Image.open(base / "thumbs/16000110.webp") as image:
        assert image.size == (480, 480)
        assert image.format == "WEBP"
