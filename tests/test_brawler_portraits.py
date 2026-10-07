import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_cached_portraits_match_the_catalog_and_recorded_artwork():
    image = pytest.importorskip('PIL.Image')
    catalog = json.loads((ROOT / 'data/brawler_catalog.json').read_text(encoding='utf-8'))
    portraits = json.loads((ROOT / 'data/brawler_portraits.json').read_text(encoding='utf-8'))['portraits']
    assert set(portraits) == {str(b['id']) for b in catalog if b['id'] not in {16000108, 16000109, 16000110}}
    for brawler_id, record in portraits.items():
        path = ROOT / 'app/ui' / record['local_url'].lstrip('/')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['local_sha256']
        assert record['source_url'] == f'https://cdn.brawlify.com/brawlers/borders/{brawler_id}.png'
        with image.open(path) as portrait:
            assert portrait.format == 'WEBP'
            assert portrait.size == (record['width'], record['height'])
            assert portrait.width == portrait.height


def test_other_pages_use_local_official_portraits_with_a_bounded_symbol_fallback():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for portrait rendering checks')
    script = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('./app/ui/assets/app.js', 'utf8');
const slice = (start, end) => source.slice(source.indexOf(start), source.indexOf(end));
const context = {};
vm.createContext(context);
vm.runInContext(slice('function escapeMarkup(', '\nfunction sourceLabel('), context);
vm.runInContext(slice('function brawlerImage(', '\nfunction remoteBrawlerImage('), context);
vm.runInContext(slice('function officialBrawlerIconSource(', '\nfunction brawlerNameMarkup('), context);
const catalog = JSON.parse(fs.readFileSync('./data/brawler_catalog.json', 'utf8'));
for (const brawler of catalog) {
  const url = context.officialBrawlerIconSource(brawler);
  assert.ok(fs.existsSync('./app/ui' + url.split('?')[0]), brawler.name);
}
assert.equal(context.officialBrawlerIconSource({id: '16000002'}), '/assets/brawlers/portraits/16000002.webp');
assert.equal(context.officialBrawlerIconSource(null), '/assets/rarity-skull.svg');
const markup = context.brawlerIconMarkup({id: 16000002, name: '<BULL>'});
assert.ok(markup.includes('&lt;BULL&gt; official portrait'));
assert.ok(markup.includes('loading="lazy"'));
const fallback = markup.match(/onerror="([^"]+)"/)[1];
const image = {src: '/missing', onerror: () => {}};
new Function(fallback).call(image);
assert.equal(image.src, '/assets/rarity-skull.svg');
assert.equal(image.onerror, null);
assert.ok(!markup.includes('/model/') && !markup.includes('/thumbs/'));
"""
    subprocess.run([node, '-e', script], cwd=ROOT, check=True)
