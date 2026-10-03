from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_collection_prestige_respects_api_totals_and_permanent_levels() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required to test the collection Prestige summary")
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('./app/ui/assets/app.js', 'utf8');
const level = source.slice(source.indexOf('function getPrestigeLevel('), source.indexOf('function getPrestigeState('));
const summary = source.slice(source.indexOf('const COLLECTION_PRESTIGE_CATEGORIES'), source.indexOf('function renderCollectionPrestige('));
const context = {PRESTIGE_STEP: 1000};
vm.createContext(context);
vm.runInContext(level + summary, context);
const run = player => context.getCollectionPrestigeSummary(player);
const brawlers = [0, 250, 500, 750, 1000, 2000, 3000, 12000].map(trophies => ({trophies, prestige_level: Math.floor(trophies / 1000)}));
// A permanent Prestige survives a current Trophy total below its threshold.
brawlers[6].trophies = 900;
const player = {source: 'OFFICIAL_API', total_prestige_source: 'OFFICIAL_API', total_prestige_level: 42, brawlers};
let result = run(player);
assert.equal(result.total, 42);
assert.equal(result.source, 'OFFICIAL API');
assert.equal(result.unlocked, 8);
assert.equal(result.prestiged, 4);
assert.deepEqual(Object.values(result.counts), [1, 1, 1, 1, 1, 1, 2]);
assert.equal(Object.values(result.counts).reduce((a,b) => a+b, 0), 8);
assert.equal(run({...player, total_prestige_level: 0}).total, 0);
result = run({brawlers: [{trophies: 900, highest_trophies: 2050}]});
assert.equal(result.total, 2);
assert.equal(result.counts.prestige2, 1);
assert.equal(result.source, 'ESTIMATED PRESTIGE');
assert.equal(run({...player, source: 'DEMO'}).source, 'DEMO PLAYER');
assert.equal(run({source: 'OFFICIAL_API', brawlers: []}).total, 0);
assert.equal(run(null).total, null);
assert.equal(run(null).source, 'CONNECT A PLAYER');
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True)
