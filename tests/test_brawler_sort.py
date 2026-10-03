from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_roster_sort_options_and_ordering() -> None:
    html = (ROOT / "app/ui/index.html").read_text(encoding="utf-8")
    assert '<option value="newest">Newest brawlers</option>' in html
    assert '<option value="oldest">Oldest brawlers</option>' in html
    assert '<option value="trophies_asc">Least trophies</option>' in html
    assert '<option value="name_desc">Name Z–A</option>' in html
    assert 'value="prestige_desc"' not in html
    assert 'value="prestige_asc"' not in html
    assert '<option value="prestige_next">Closest to next Prestige</option>' in html
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required to test roster sorting")
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('./app/ui/assets/app.js', 'utf8');
const render = source.slice(source.indexOf('function renderBrawlers() {'), source.indexOf('\nfunction renderGuideProfile('));
const catalog = JSON.parse(fs.readFileSync('./data/brawler_catalog.json', 'utf8'));
const state = {brawlers: catalog.map((b, i) => ({...b, owned: i % 2 === 0, power: i % 11 + 1})), level: 'all', view: 'grid'};
let sort = 'newest';
let query = '';
let equipment = 'all';
let displayed = [];
const holder = {replaceChildren() { displayed = []; }, classList: {toggle() {}}, append(b) {displayed.push(b.id);}};
const context = {
  state, document: {querySelector() {return null;}},
  $(id) {
    if (id === 'brawler-sort') return {value: sort};
    if (id === 'brawler-search') return {value: query};
    if (id === 'equipment-filter') return {value: equipment};
    if (id === 'brawler-grid') return holder;
    return null;
  },
  matchesEquipment(b, filter) {return filter === 'all' || b.owned;},
  cardFor(b) {return b;}, scheduleBrawlerNameFit() {},
};
vm.createContext(context);
vm.runInContext(render, context);
const run = () => vm.runInContext('renderBrawlers()', context);
run();
assert.deepEqual(displayed, catalog.map(b => b.id).sort((a,b) => b-a));
assert.equal(displayed[0], 16000110);
sort = 'oldest'; run();
assert.deepEqual(displayed, catalog.map(b => b.id).sort((a,b) => a-b));
assert.equal(displayed[0], 16000000);
query = 'co'; sort = 'newest'; run();
assert.deepEqual(displayed, catalog.filter(b => b.name.toLowerCase().includes(query)).map(b => b.id).sort((a,b) => b-a));
query = ''; equipment = 'owned'; state.level = '3'; sort = 'oldest'; run();
assert.deepEqual(displayed, state.brawlers.filter(b => b.owned && b.power === 3).map(b => b.id).sort((a,b) => a-b));
equipment = 'all'; state.level = 'all';
state.brawlers = [
  {id: 1, name: 'ZIGGY', trophies: 20, owned: true},
  {id: 2, name: 'COSMO', trophies: 0, owned: false},
  {id: 3, name: 'WENDY', trophies: 20, owned: true},
  {id: 4, name: 'AMBER', owned: false},
  {id: 5, name: 'SHELLY', trophies: 200, owned: true},
];
sort = 'trophies_asc'; run();
assert.deepEqual(displayed, [4, 2, 3, 1, 5]);
sort = 'trophies'; run();
assert.deepEqual(displayed, [5, 3, 1, 4, 2]);
sort = 'name_desc'; run();
assert.deepEqual(displayed, [1, 3, 5, 2, 4]);
sort = 'name'; run();
assert.deepEqual(displayed, [4, 2, 5, 3, 1]);
query = 'w'; sort = 'name_desc'; run();
assert.deepEqual(displayed, [3]);
query = ''; state.ownership = 'locked'; sort = 'newest'; run();
assert.deepEqual(displayed, [4, 2]);
query = 'cos'; run();
assert.deepEqual(displayed, [2]);
state.ownership = 'unlocked'; run();
assert.deepEqual(displayed, []);
query = ''; sort = 'oldest'; run();
assert.deepEqual(displayed, [1, 3, 5]);
state.ownership = 'all'; run();
assert.deepEqual(displayed, [1, 2, 3, 4, 5]);
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True)


def test_progression_filters_match_one_stage_and_respect_permanent_prestige() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required to test roster progression")
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('./app/ui/assets/app.js', 'utf8');
const prestige = source.slice(source.indexOf('function getPrestigeLevel('), source.indexOf('function getPrestigeState('));
const filters = source.slice(source.indexOf('function matchesEquipment('), source.indexOf('function renderBrawlers('));
const context = {
  PRESTIGE_STEP: 1000, state: {},
  getBrawlerClass() {return '';}, getBrawlerRarity() {return '';},
  hasHypercharge() {return false;}, hasBuffie() {return false;},
};
vm.createContext(context);
vm.runInContext(prestige + filters, context);
const stages = ['progression_wood', 'progression_bronze', 'progression_silver', 'progression_gold', 'prestige_1', 'prestige_2', 'prestige_3_plus'];
const cases = [
  [0, 0, 0], [249, 0, 0], [250, 0, 1], [499, 0, 1],
  [500, 0, 2], [749, 0, 2], [750, 0, 3], [999, 0, 3],
  [1000, 0, 3], [1000, 1, 4], [1999, 1, 4], [2000, 2, 5],
  [3000, 3, 6], [12000, 12, 6], [100, 2, 5],
];
for (const [trophies, prestige_level, stage] of cases) {
  const brawler = {owned: true, trophies, prestige_level};
  assert.deepEqual(stages.filter(filter => context.matchesEquipment(brawler, filter)), [stages[stage]]);
  assert.equal(context.matchesEquipment({...brawler, owned: false}, stages[stage]), false);
}
assert.equal(context.matchesEquipment({owned: true, trophies: 900, highest_trophies: 2050}, 'prestige_2'), true);
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True)
