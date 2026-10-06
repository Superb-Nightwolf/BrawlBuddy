from pathlib import Path
import importlib
import gzip
import shutil
import subprocess
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from app.core.errors import PlayerNotFound


ROOT = Path(__file__).resolve().parents[1]
main = importlib.import_module("app.main")


@pytest.mark.parametrize("path", ["/", "/assets/app.js", "/assets/styles.css", "/api/visual-assets", "/api/equipment"])
def test_text_payloads_are_compressed_without_changing_content(path):
    with TestClient(main.app) as client:
        plain = client.get(path, headers={"Accept-Encoding": "identity"})
        with client.stream("GET", path, headers={"Accept-Encoding": "gzip"}) as compressed:
            encoded = b"".join(compressed.iter_raw())
    assert plain.status_code == compressed.status_code == 200
    assert compressed.headers["content-encoding"] == "gzip"
    assert gzip.decompress(encoded) == plain.content
    assert len(encoded) < len(plain.content) * 0.4
    assert "Accept-Encoding" in compressed.headers["vary"]


def test_shared_assets_are_reused_but_html_and_configuration_revalidate():
    with TestClient(main.app) as client:
        script = client.get("/assets/app.js?v=151")
        again = client.get("/assets/app.js?v=151", headers={"If-None-Match": script.headers["etag"]})
        image = client.get("/assets/app-logo.webp", headers={"Accept-Encoding": "gzip"})
        metadata = client.get("/api/equipment")
        html = client.get("/brawlers")
        config = client.get("/config.js")
        player = client.get("/api/demo/player")
    assert script.headers["cache-control"] == again.headers["cache-control"] == "public, max-age=3600"
    assert again.status_code == 304
    assert image.headers.get("content-encoding") is None
    assert metadata.headers["cache-control"] == "public, max-age=3600"
    assert html.headers["cache-control"] == "no-cache"
    assert config.headers["cache-control"] == "no-store"
    assert "public" not in player.headers.get("cache-control", "")


def test_status_does_not_scan_artwork_on_each_visit(monkeypatch):
    with TestClient(main.app) as client:
        def unexpected_scan(*args, **kwargs):
            raise AssertionError("Artwork scan must happen before serving traffic")
        monkeypatch.setattr(Path, "rglob", unexpected_scan)
        dates = [client.get("/api/status").json()["content_last_updated"] for _ in range(3)]
    assert len(set(dates)) == 1


def test_failed_lookup_does_not_repeat_the_same_upstream_request(monkeypatch):
    player = AsyncMock(side_effect=PlayerNotFound("Player not found"))
    club = AsyncMock(side_effect=PlayerNotFound("Club not found"))
    monkeypatch.setattr(main.player_service, "get_player", player)
    monkeypatch.setattr(main.club_service, "get_club", club)
    with TestClient(main.app) as client:
        response = client.get("/api/lookup?tag=2PP")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Player not found"
    player.assert_awaited_once_with("#2PP")
    club.assert_awaited_once_with("#2PP")


@pytest.mark.parametrize("name", ["app-logo", "app-logo-text", "total-prestige-emblem-hd"])
def test_optimized_artwork_preserves_every_pixel(name):
    image = pytest.importorskip("PIL.Image")
    original = ROOT / "app/ui/assets" / f"{name}.png"
    optimized = original.with_suffix(".webp")
    with image.open(original) as source, image.open(optimized) as result:
        assert source.size == result.size
        assert source.convert("RGBA").tobytes() == result.convert("RGBA").tobytes()
    assert optimized.stat().st_size < original.stat().st_size * 0.8


def test_startup_fetches_account_with_metadata_and_shares_inflight_requests():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for frontend loading checks")
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/ui/assets/app.js', 'utf8');
const section = (start, end) => source.slice(source.indexOf(start), source.indexOf(end));
const calls = [], pending = new Map(), rendered = [];
const state = {page: 'overview', player: null, ownedBrawlers: [], catalog: []};
const context = {
  state, ACCOUNT_CACHE_KEY: 'account', sessionStorage: {getItem() {return null;}, setItem() {}},
  $(id) {return null;}, request(url) {
    calls.push(url);
    return new Promise(resolve => pending.set(url, resolve));
  },
  renderAccount(payload) {rendered.push(payload); state.player = payload.player;},
  mergeCatalog() {return [];}, loadDemo() {throw Error('Unexpected fallback');},
  configurePage() {}, showView() {}, window: {scrollTo() {}},
  location: {search: ''}, URLSearchParams, Promise, encodeURIComponent,
};
vm.createContext(context);
vm.runInContext(section('let catalogPromise = null;', '\nfunction mergeCatalog('), context);
vm.runInContext(section("const DEFAULT_PLAYER_TAG =", '\nasync function loadInitialClub('), context);
vm.runInContext(section('async function handleRoute(', '\nwindow.addEventListener(\'popstate\''), context);
(async () => {
  const route = vm.runInContext('handleRoute()', context);
  const lookup = calls.find(url => url.startsWith('/api/lookup'));
  assert.ok(lookup, 'Account lookup must start before metadata resolves');
  vm.runInContext('loadCatalog(); loadCatalog();', context);
  assert.equal(calls.filter(url => url === '/api/equipment').length, 1);
  pending.get(lookup)({type: 'player', player: {tag: '#9Q889JCR0'}});
  await Promise.resolve(); await Promise.resolve();
  assert.equal(rendered.length, 0, 'Render with complete equipment and visual metadata');
  for (const [url, resolve] of pending) if (url !== lookup) resolve(url.includes('/catalog') ? {list: [{id: 1}]} : {});
  await route;
  assert.equal(rendered.length, 1);
  assert.equal(state.catalog.length, 1);
  await vm.runInContext('loadCatalog()', context);
  assert.equal(calls.filter(url => url === '/api/equipment').length, 1);
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True, capture_output=True, text=True)


def test_showing_overview_does_not_build_roster_or_start_route_requests():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for frontend rendering checks")
    script = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('app/ui/assets/app.js', 'utf8');
const view = {classList: {contains() {return false;}, add() {}, remove() {}}};
let rosterRenders = 0;
const state = {page: 'overview', brawlers: [{id: 1}], rosterDirty: true};
const context = {state, $() {return view;}, document: {querySelectorAll() {return [];}},
  BrawlBuddyMotion: {enter() {}}, renderBrawlers() {rosterRenders++; state.rosterDirty = false;}};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function showView('), source.indexOf('\nasync function request(')), context);
vm.runInContext('showView()', context);
assert.equal(rosterRenders, 0);
state.page = 'brawlers'; vm.runInContext('showView(); showView()', context);
assert.equal(rosterRenders, 1);
state.rosterDirty = true; vm.runInContext('showView()', context);
assert.equal(rosterRenders, 2);
state.page = 'club'; vm.runInContext('showView()', context);
// There are deliberately no loader stubs: view updates must not issue duplicate requests.
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True, capture_output=True, text=True)
