"""Cache verified hero counterparts without touching existing generated artwork."""
from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

from sync_visual_assets import fetch_bytes, original_url

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app/ui/assets"
MANIFEST = ASSETS / "brawlers/hero-artwork.json"


def cache_artwork(ident: str, entry: dict) -> dict:
    if entry["official"].startswith("/assets/"):
        return entry
    source_url = entry["official"]
    destination = ASSETS / "brawlers/official" / f"{ident}.webp"
    if not destination.exists():
        payload = fetch_bytes(entry.get("download_url") or original_url(source_url))
        with Image.open(io.BytesIO(payload)) as source:
            if source.format not in {"PNG", "WEBP"} or min(source.size) < 64:
                raise ValueError("Unexpected artwork format or dimensions")
            artwork = source.convert("RGBA")
            artwork.thumbnail((680, 660), Image.Resampling.LANCZOS)
            destination.parent.mkdir(parents=True, exist_ok=True)
            artwork.save(destination, "WEBP", quality=88, method=6)
    with Image.open(destination) as image:
        image.verify()
    return {**entry, "official": "/assets/" + destination.relative_to(ASSETS).as_posix(), "source_url": source_url}


def main() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(cache_artwork, ident, entry): ident for ident, entry in entries.items()}
        for index, job in enumerate(as_completed(jobs), 1):
            ident = jobs[job]
            try:
                entries[ident] = job.result()
            except Exception as error:
                errors.append(f"{ident}: {error}")
            if index % 20 == 0:
                print(f"Checked {index}/{len(entries)} hero pairs", flush=True)
    MANIFEST.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("\n".join(errors))
    print(f"Ready: {len(entries)} hero pairs", flush=True)


if __name__ == "__main__":
    main()
