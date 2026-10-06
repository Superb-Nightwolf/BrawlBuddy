"""Build pixel-identical WebP copies of the large UI branding PNGs.

Run with a Python environment containing Pillow; original artwork is retained.
"""
from pathlib import Path

from PIL import Image


ASSETS = Path(__file__).resolve().parents[1] / "app" / "ui" / "assets"


def main() -> None:
    for name in ("app-logo", "app-logo-text", "total-prestige-emblem-hd"):
        original = ASSETS / f"{name}.png"
        optimized = original.with_suffix(".webp")
        with Image.open(original) as source:
            pixels = source.convert("RGBA")
            pixels.save(optimized, lossless=True, quality=100, method=6, exact=True)
            with Image.open(optimized) as result:
                assert result.convert("RGBA").tobytes() == pixels.tobytes(), name
        print(f"{name}: {original.stat().st_size:,} -> {optimized.stat().st_size:,} bytes (identical pixels)")
    with Image.open(ASSETS / "app-logo.png") as source:
        source.thumbnail((128, 128), Image.Resampling.LANCZOS)
        source.save(ASSETS / "favicon.png", optimize=True)


if __name__ == "__main__":
    main()
