import shutil
import subprocess
from pathlib import Path

import pytest


def test_character_theme_priority_fallbacks_and_background_only_application() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for client theme validation")
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { getTheme, apply } = require('./app/ui/assets/brawler-hero-themes.js');
const catalog = JSON.parse(fs.readFileSync('data/brawler_catalog.json', 'utf8'));
for (const brawler of catalog) {
  const before = JSON.stringify(brawler);
  const theme = getTheme(brawler);
  for (const key of ['primary', 'secondary', 'accent', 'deep', 'glow', 'surface', 'border']) {
    assert.match(theme[key], /^#[a-f0-9]{6}$/i, `${brawler.name}: ${key}`);
  }
  assert.equal(theme.spotlightPosition.length, 2);
  assert.ok(theme.spotlightPosition.every(x => x > 0 && x < 100));
  assert.ok(theme.spotlightIntensity > 0 && theme.spotlightIntensity <= 1);
  assert.equal(JSON.stringify(brawler), before);
}
// Same rarity must not force unrelated characters into the same background.
const legendary = name => getTheme({ name, rarity: 'Legendary' });
assert.notEqual(legendary('AMBER').primary, legendary('CROW').primary);
assert.notEqual(legendary('AMBER').effectType, legendary('CROW').effectType);
assert.equal(legendary('AMBER').border, legendary('CROW').border);
// A known character wins over misleading generic kit cues.
assert.equal(getTheme({name:'AMBER', rarity:'Legendary'}, {
  attack: {description:'An icy snow attack.'}
}).effectType, 'embers');
// New characters get a family from their kit, then a safe rarity fallback.
const frost = getTheme({name:'NEW CHARACTER', rarity:'Legendary'}, {
  attack: {description:'Freezes enemies with ice.'}
});
assert.equal(frost.effectType, 'frost');
assert.equal(frost.border, legendary('AMBER').border);
assert.equal(getTheme({name:'NEW CHARACTER', rarity:'Epic'}).effectType, 'dust');
assert.equal(getTheme({name:'NEW CHARACTER', rarity:'Unknown'}).border,
  getTheme({name:'NEW CHARACTER', rarity:'Common'}).border);
// Applying a theme writes decorative properties only; it preserves live content.
const properties = new Map();
const element = {innerHTML:'<strong>922 / 1,000</strong>', dataset:{},
  style:{setProperty:(key, value)=>properties.set(key, value)}};
apply(element, {name:'AMBER', rarity:'Legendary'});
assert.equal(element.innerHTML, '<strong>922 / 1,000</strong>');
assert.deepEqual(Object.keys(element.dataset), ['heroEffect']);
assert.ok([...properties.keys()].every(key => /^--(theme-|rarity-accent|spotlight-)/.test(key)));
apply(null, {name:'AMBER'});
"""
    subprocess.run([node, "-e", script], cwd=Path(__file__).resolve().parents[1], check=True)
