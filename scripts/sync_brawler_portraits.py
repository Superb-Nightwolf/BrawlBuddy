"""Cache the same official portraits used by the roster for other HQ pages."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import urllib.request

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'app/ui/assets/brawlers/portraits'
# These new brawlers already have official local portraits in the roster.
LOCAL_PORTRAITS = {16000108, 16000109, 16000110}


def download_portrait(brawler):
    source = f"https://cdn.brawlify.com/brawlers/borders/{brawler['id']}.png"
    request = urllib.request.Request(source, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=25) as response:
        content = response.read()
    with Image.open(io.BytesIO(content)) as image:
        image.load()
        destination = DESTINATION / f"{brawler['id']}.webp"
        image.save(destination, 'WEBP', lossless=True, method=6)
        with Image.open(destination) as cached:
            if cached.convert('RGBA').tobytes() != image.convert('RGBA').tobytes():
                raise ValueError(f"Portrait pixels changed for {brawler['name']}")
        return str(brawler['id']), {
            'name': brawler['name'], 'source_url': source,
            'local_url': f'/assets/brawlers/portraits/{destination.name}',
            'width': image.width, 'height': image.height,
            'source_sha256': hashlib.sha256(content).hexdigest(),
            'local_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
        }


def main():
    catalog = json.loads((ROOT / 'data/brawler_catalog.json').read_text(encoding='utf-8'))
    DESTINATION.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        portraits = dict(pool.map(download_portrait, [b for b in catalog if b['id'] not in LOCAL_PORTRAITS]))
    manifest = {'checked_at': date.today().isoformat(), 'portraits': portraits}
    (ROOT / 'data/brawler_portraits.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f"Cached {len(portraits)} portraits losslessly ({sum(p.stat().st_size for p in DESTINATION.glob('*.webp')):,} bytes).")


if __name__ == '__main__':
    main()
