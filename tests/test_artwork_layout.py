import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_visible_bounds_ignore_padding_and_faint_shadows() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the browser helper unit test")
    script = r"""
const assert = require('node:assert/strict');
const {visibleBounds} = require('./app/ui/assets/artwork-layout.js');
const pixels = new Uint8ClampedArray(8 * 10 * 4);
for (let y = 2; y < 8; y++) for (let x = 1; x < 6; x++) pixels[(y * 8 + x) * 4 + 3] = 255;
pixels[3] = 24;
assert.deepEqual(visibleBounds(pixels, 8, 10), {left: 1, top: 2, width: 5, height: 6});
assert.deepEqual(visibleBounds(new Uint8ClampedArray(8 * 10 * 4), 8, 10), {left: 0, top: 0, width: 8, height: 10});
assert.deepEqual(visibleBounds(new Uint8ClampedArray(8 * 10 * 4).fill(255), 8, 10), {left: 0, top: 0, width: 8, height: 10});
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True)


def test_all_hero_art_fits_the_shared_vertical_frame_without_clipping() -> None:
    base = ROOT / "app/ui/assets/brawlers"
    registry = json.loads((base / "hero-artwork.json").read_text(encoding="utf-8"))
    paths = [
        (brawler_id, base.parent / entry["generated"].removeprefix("/assets/"))
        for brawler_id, entry in registry.items()
    ]
    paths.append(("SURGE preview", base.parent / "surge-guide-art.png"))
    for brawler_id, path in paths:
        with Image.open(path) as image:
            bounds = image.convert("RGBA").getchannel("A").point(lambda alpha: 255 if alpha > 24 else 0).getbbox()
            assert bounds is not None
            width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
            # CSS reserves the same 82% stage-width body height for every hero.
            assert .82 * width / height <= 1, f"{brawler_id} would overflow horizontally"
    assert len(registry) == 108
