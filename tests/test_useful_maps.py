import json
from pathlib import Path


def test_maps_catalog_structure():
    catalog_path = Path(__file__).resolve().parent.parent / "data" / "maps_catalog.json"
    assert catalog_path.exists(), "data/maps_catalog.json must exist"

    with catalog_path.open("r", encoding="utf-8") as f:
        catalog = json.load(f)

    assert len(catalog) >= 20, "Maps catalog must contain competitive active maps"
    for map_id_str, map_data in catalog.items():
        assert map_data["id"] == int(map_id_str)
        assert map_data["name"]
        assert map_data["mode"]
        assert map_data["image_url"].startswith("https://cdn.brawlify.com/maps/regular/")
        assert map_data["image_url"].endswith(f"{map_data['id']}.png")


def test_brawler_guides_have_useful_maps():
    guides_path = Path(__file__).resolve().parent.parent / "data" / "brawler_guides.json"
    assert guides_path.exists()

    with guides_path.open("r", encoding="utf-8") as f:
        guides = json.load(f)

    assert len(guides) == 106, "All 106 brawlers must be represented"

    for brawler_id, guide in guides.items():
        assert "useful_maps" in guide, f"Brawler {guide.get('name', brawler_id)} must have useful_maps"
        maps = guide["useful_maps"]
        assert len(maps) == 4, f"Brawler {guide.get('name', brawler_id)} must have exactly 4 useful maps"
        for m in maps:
            assert "id" in m and isinstance(m["id"], int)
            assert "name" in m and len(m["name"]) > 0
            assert "mode" in m and len(m["mode"]) > 0
            assert m["image_url"].startswith("https://cdn.brawlify.com/maps/regular/")


def test_buster_useful_maps_match_poc_reference():
    guides_path = Path(__file__).resolve().parent.parent / "data" / "brawler_guides.json"
    with guides_path.open("r", encoding="utf-8") as f:
        guides = json.load(f)

    buster_guide = next(g for g in guides.values() if g.get("name", "").upper() == "BUSTER")
    map_names = [m["name"] for m in buster_guide["useful_maps"]]

    assert map_names == ["Sneaky Fields", "Double Swoosh", "Center Stage", "Hard Rock Mine"], (
        f"Buster's useful maps must match the POC reference exactly: {map_names}"
    )
