from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "app" / "ui" / "assets" / "brawlers"
OUTPUT_DIR = SOURCE_DIR / "thumbs"
THUMBNAIL_SIZE = (480, 480)

# Most source renders are already square. Cosmo's official render is wide, so
# trim its left and right sides while preserving the complete portrait height.
PORTRAIT_CROPS = {
    "16000109": (542, 0, 1652, 1110),
}
PORTRAIT_INSETS = {
    "16000109": 28,
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    requested_ids = set(sys.argv[1:])
    generated = 0
    for source in sorted(SOURCE_DIR.glob("*.png")):
        if requested_ids and source.stem not in requested_ids:
            continue
        destination = OUTPUT_DIR / f"{source.stem}.webp"
        with Image.open(source) as image:
            crop = PORTRAIT_CROPS.get(source.stem)
            if crop:
                image = image.crop(crop)
            inset = PORTRAIT_INSETS.get(source.stem, 0)
            render_size = tuple(dimension - (inset * 2) for dimension in THUMBNAIL_SIZE)
            image.thumbnail(render_size, Image.Resampling.LANCZOS)
            if inset:
                portrait = Image.new("RGBA", THUMBNAIL_SIZE, (0, 0, 0, 0))
                position = tuple((canvas - rendered) // 2 for canvas, rendered in zip(
                    THUMBNAIL_SIZE, image.size, strict=True
                ))
                portrait.alpha_composite(image.convert("RGBA"), position)
                image = portrait
            image.save(destination, "WEBP", quality=82, method=6)
        generated += 1
    print(f"Generated {generated} brawler thumbnails in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
