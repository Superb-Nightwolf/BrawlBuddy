from __future__ import annotations

from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "app" / "ui" / "assets" / "brawlers"
OUTPUT_DIR = SOURCE_DIR / "thumbs"
THUMBNAIL_SIZE = (480, 480)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = 0
    for source in sorted(SOURCE_DIR.glob("*.png")):
        destination = OUTPUT_DIR / f"{source.stem}.webp"
        with Image.open(source) as image:
            image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            image.save(destination, "WEBP", quality=82, method=6)
        generated += 1
    print(f"Generated {generated} brawler thumbnails in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
