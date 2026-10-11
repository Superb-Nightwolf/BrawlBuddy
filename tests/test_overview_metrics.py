from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_overview_metrics_count_equipped_brawlers_once_and_handle_empty_account():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required to test the account summary renderer')
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('./app/ui/assets/app.js', 'utf8');
const render = source.slice(source.indexOf('function renderOverviewMetrics() {'), source.indexOf('\nfunction brawlerImage('));
const values = {};
const state = {player: {brawlers: [
  {gadgets: [{id: 1}], star_powers: [{id: 2}, {id: 3}]},
  {gadgets: [], star_powers: [{id: 4}]},
  {gadgets: [], star_powers: []},
  {},
]}, analytics: {average_power: 9.25, power_11_count: 1}};
const context = {state, format: String, setText(id, value) {values[id] = String(value);}};
vm.createContext(context);
vm.runInContext(render, context);
vm.runInContext('renderOverviewMetrics()', context);
assert.equal(values['brawler-count'], '4');
assert.equal(values['average-power'], '9.25');
assert.equal(values['power-eleven'], '1');
assert.equal(values['equipped-count'], '2');
state.player = null;
state.analytics = null;
vm.runInContext('renderOverviewMetrics()', context);
assert.equal(values['brawler-count'], '0');
assert.equal(values['average-power'], '—');
assert.equal(values['power-eleven'], '0');
assert.equal(values['equipped-count'], '0');
"""
    subprocess.run([node, '-e', script], cwd=ROOT, check=True)


def test_rank_icons_render_from_player_data_without_analytics():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required to test the account summary renderer')
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('./app/ui/assets/app.js', 'utf8');
const helpers = source.slice(source.indexOf('function normalizeKey('), source.indexOf('function escapeMarkup('));
const render = source.slice(source.indexOf('function renderHeroRank('), source.indexOf('function renderAccount('));
const values = {};
const icons = [{}, {}].map(attributes => ({attributes, setAttribute(key, value) {attributes[key] = value;}}));
const context = {
  document: {querySelectorAll() {return icons;}},
  setText(id, value) {values[id] = value;},
  format: value => new Intl.NumberFormat('en-US').format(value),
};
vm.createContext(context);
vm.runInContext(helpers + render, context);
for (const league of ['Bronze', 'Silver', 'Gold', 'Diamond', 'Mythic', 'Legendary', 'Masters', 'Pro']) {
  for (const division of ['', ' I', ' II', ' III', ' 1', ' 2', ' 3']) {
    context.player = {ranked_rank_name: league + division, ranked_elo: 4917};
    vm.runInContext('renderHeroRank(player)', context);
    const expected = `/assets/ranked/${league.toLowerCase()}.png`;
    assert.equal(icons[0].attributes.src, expected);
    assert.equal(icons[1].attributes.src, expected);
    assert.ok(fs.existsSync('./app/ui' + expected));
    assert.equal(values['hero-ranked-label'], league + division);
    assert.equal(values['hero-ranked-rating'], '4,917');
  }
}
context.player = {};
vm.runInContext('renderHeroRank(player)', context);
assert.equal(values['hero-ranked-label'], 'Ranked rating');
assert.equal(values['hero-ranked-rating'], '—');
assert.equal(icons[0].attributes.src, '/assets/rarity-skull.svg');
context.player = {ranked_rank_name: 'Unknown league'};
vm.runInContext('renderHeroRank(player)', context);
assert.equal(icons[0].attributes.src, '/assets/rarity-skull.svg');
"""
    subprocess.run([node, '-e', script], cwd=ROOT, check=True)
