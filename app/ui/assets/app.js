const state = {
  page: 'overview',
  player: null,
  analytics: null,
  club: null,
  clubAnalytics: null,
  catalog: [],
  ownedBrawlers: [],
  brawlers: [],
  battles: [],
  battleFilter: 'all',
  events: [],
  metaTierlist: {},
  rankingsRegion: 'global',
  rankingsType: 'players',
  rankingsPlayers: [],
  rankingsClubs: [],
  level: 'all',
  equipment: 'all',
  view: 'grid',
  dataSources: {},
  visualAssets: {},
  prestigeAssets: {},
};

const ACCOUNT_CACHE_KEY = 'brawlbuddy_account_v4';
const CLUB_CACHE_KEY = 'brawlbuddy_club_v3';

const $ = (id) => document.getElementById(id);
const format = (value) => new Intl.NumberFormat().format(value ?? 0);

function normalizeKey(str) {
  return String(str || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}

function getUiIconRecord(group, value) {
  const normalized = normalizeKey(value);
  const records = state.visualAssets?.ui_icons?.[group] || {};
  return Object.values(records).find((record) => {
    const aliases = [record.label, ...(record.aliases || [])];
    return aliases.some((alias) => normalizeKey(alias) === normalized);
  }) || null;
}

function uiIconMarkup(group, value, className, fallback = '★') {
  const record = getUiIconRecord(group, value);
  if (!record?.local_url) return `<span class="${className} ui-icon-fallback">${fallback}</span>`;
  return `<img class="${className}" src="${record.local_url}" alt="" aria-hidden="true" onerror="this.onerror=null;this.replaceWith(document.createTextNode('${fallback}'))">`;
}

function modeLabel(value) {
  const record = getUiIconRecord('modes', value);
  if (record?.label) return record.label;
  return String(value || 'Brawl').replace(/([a-z])([A-Z])/g, '$1 $2');
}

const PRESTIGE_STEP = 1000;
const MAX_PRESTIGE_VISUAL_LEVEL = 10;

function getPrestigeLevel(brawler) {
  if (Number.isInteger(brawler?.prestige_level) && brawler.prestige_level >= 0) {
    return brawler.prestige_level;
  }
  const peak = Math.max(brawler?.trophies || 0, brawler?.highest_trophies || brawler?.highestTrophies || 0);
  return Math.floor(peak / PRESTIGE_STEP);
}

function getPrestigeState(brawler) {
  const total = Math.max(0, Number(brawler?.trophies || 0));
  const level = getPrestigeLevel(brawler);
  if (level > 0) {
    const inLevel = Number.isFinite(brawler?.prestige_trophies)
      ? Math.max(0, brawler.prestige_trophies)
      : Math.max(0, total - (level * PRESTIGE_STEP));
    const remaining = Number.isFinite(brawler?.trophies_to_next_prestige)
      ? Math.max(0, brawler.trophies_to_next_prestige)
      : Math.max(0, PRESTIGE_STEP - inLevel);
    const visualLevel = Math.min(level, MAX_PRESTIGE_VISUAL_LEVEL);
    return {
      level,
      label: brawler?.prestige_label || `Prestige ${level}`,
      assetId: Number.isInteger(brawler?.prestige_asset_id) ? brawler.prestige_asset_id : 3 + visualLevel,
      trophiesInLevel: inLevel,
      remaining,
      nextLevel: brawler?.next_prestige_level || level + 1,
      nextTotal: brawler?.next_prestige_trophy_milestone || (level + 1) * PRESTIGE_STEP,
      progress: Number.isFinite(brawler?.prestige_progress_percent) ? brawler.prestige_progress_percent : Math.min(100, inLevel / 10),
      nextReward: brawler?.next_prestige_reward || null,
      visualFallback: brawler?.prestige_visual_is_fallback === true || level > MAX_PRESTIGE_VISUAL_LEVEL,
      authoritative: brawler?.prestige_level_source === 'OFFICIAL_API' || brawler?.prestige_level_source === 'DEMO',
    };
  }

  const milestones = [
    { min: 0, next: 250, label: 'Wood', assetId: 0, reward: 'Player icon and spray' },
    { min: 250, next: 500, label: 'Bronze', assetId: 1, reward: 'Pins' },
    { min: 500, next: 750, label: 'Silver', assetId: 2, reward: 'Rare skin or 1,000 Bling' },
    { min: 750, next: 1000, label: 'Gold', assetId: 3, reward: 'Gold Brawler Title' },
  ];
  const milestone = [...milestones].reverse().find((item) => total >= item.min) || milestones[0];
  const span = milestone.next - milestone.min;
  return {
    level: 0,
    label: brawler?.prestige_label || milestone.label,
    assetId: Number.isInteger(brawler?.prestige_asset_id) ? brawler.prestige_asset_id : milestone.assetId,
    trophiesInLevel: total,
    remaining: Number.isFinite(brawler?.trophies_to_next_prestige) ? brawler.trophies_to_next_prestige : Math.max(0, milestone.next - total),
    nextLevel: 1,
    nextTotal: milestone.next,
    progress: Number.isFinite(brawler?.prestige_progress_percent) ? brawler.prestige_progress_percent : Math.min(100, Math.max(0, total - milestone.min) / span * 100),
    nextReward: brawler?.next_prestige_reward || milestone.reward,
    visualFallback: false,
    authoritative: brawler?.prestige_level_source === 'OFFICIAL_API' || brawler?.prestige_level_source === 'DEMO',
  };
}

function prestigeAssetSources(brawler) {
  const prestige = getPrestigeState(brawler);
  const base = state.prestigeAssets?.cdn_base_url || 'https://cdn.brawlify.com/prestiges';
  const available = state.prestigeAssets?.available?.brawler_ids || [];
  const hasSpecific = available.length === 0 || available.includes(Number(brawler?.id));
  const sources = [];
  if (hasSpecific && Number.isInteger(Number(brawler?.id))) {
    sources.push(`${base}/brawlers/${Number(brawler.id)}/${prestige.assetId}.png`);
  }
  sources.push(`${base}/tiered/${prestige.assetId}.png`);
  if (prestige.level === 0) sources.push(`${base}/regular/${prestige.assetId}.png`);
  return [...new Set(sources)];
}

function applyPrestigeImage(image, brawler) {
  const sources = prestigeAssetSources(brawler);
  let index = 0;
  image.src = sources[index] || '';
  image.onerror = () => {
    index += 1;
    if (sources[index]) image.src = sources[index];
    else image.classList.add('hidden');
  };
}

function prestigeBadgeMarkup(brawler, className = 'prestige-inline-badge') {
  const prestige = getPrestigeState(brawler);
  const sources = prestigeAssetSources(brawler);
  const label = prestige.level > 0 ? `Prestige ${prestige.level}` : prestige.label;
  const fallback = sources[1] || sources[0] || '';
  return `<span class="${className}"><img src="${sources[0] || ''}" data-fallback="${fallback}" onerror="if(this.dataset.fallback&&this.src!==this.dataset.fallback){this.src=this.dataset.fallback}else{this.style.display='none'}" alt=""><b>${label}</b></span>`;
}

function renderContentUpdated(value) {
  const target = $('content-last-updated');
  if (!target || !value) return;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return;
  target.textContent = `Content updated ${new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: 'numeric'
  }).format(parsed)}`;
}

function hasHypercharge(brawler, guide = null) {
  if (!brawler || !brawler.owned) return false;
  if (Array.isArray(brawler.hypercharges) && brawler.hypercharges.length > 0) return true;
  if (brawler.has_hypercharge === true || brawler.hasHypercharge === true) return true;
  if (brawler.hypercharge && typeof brawler.hypercharge === 'object' && brawler.hypercharge.name) return true;
  if (typeof brawler.hypercharge === 'string' && brawler.hypercharge.trim()) return true;
  return false;
}

function getBuffieFlags(brawler) {
  const flags = { gadget: false, star_power: false, hypercharge: false };
  const raw = brawler?.buffies;

  if (Array.isArray(raw)) {
    raw.forEach((entry) => {
      const value = normalizeKey(typeof entry === 'string' ? entry : entry?.name);
      if (value.includes('gadget')) flags.gadget = true;
      if (value === 'sp' || value.includes('starpower')) flags.star_power = true;
      if (value === 'hc' || value.includes('hypercharge')) flags.hypercharge = true;
    });
  } else if (raw && typeof raw === 'object') {
    flags.gadget = raw.gadget === true;
    flags.star_power = raw.star_power === true || raw.starPower === true;
    flags.hypercharge = raw.hypercharge === true || raw.hyperCharge === true;
  }

  return flags;
}

function hasBuffie(brawler, type = 'gadget') {
  if (!brawler || !brawler.owned) return false;
  const flags = getBuffieFlags(brawler);
  const normType = normalizeKey(type);
  if (normType.includes('gadget')) return flags.gadget;
  if (normType === 'sp' || normType.includes('starpower')) return flags.star_power;
  if (normType === 'hc' || normType.includes('hypercharge')) return flags.hypercharge;
  return false;
}

const EQUIPMENT_UNLOCK_LEVEL = {
  gadget: 7,
  gear: 8,
  star_power: 9,
  hypercharge: 11,
};

function baseEquipmentOwned(brawler, type) {
  if (type === 'gadget') return (brawler?.gadgets || []).length > 0;
  if (type === 'star_power') return (brawler?.star_powers || []).length > 0;
  if (type === 'hypercharge') return hasHypercharge(brawler);
  return false;
}

function equipmentUseState(brawler, type, isOwned) {
  const unlockLevel = EQUIPMENT_UNLOCK_LEVEL[type] || 1;
  if (!brawler?.owned) return { key: 'not-account', label: 'NOT IN ACCOUNT', className: 'missing-status', unlockLevel };
  if (!isOwned) return { key: 'not-owned', label: 'NOT OWNED', className: 'missing-status', unlockLevel };
  if ((brawler.power || 0) < unlockLevel) {
    return { key: 'stored', label: 'STORED', className: 'hypercharge-stored-status', unlockLevel };
  }
  return { key: 'active', label: 'ACTIVE', className: 'owned-status', unlockLevel };
}

function buffieUseState(brawler, type, abilityOwned = baseEquipmentOwned(brawler, type)) {
  const unlockLevel = EQUIPMENT_UNLOCK_LEVEL[type] || 1;
  if (!brawler?.owned) return { key: 'not-account', label: 'NOT IN ACCOUNT', className: 'missing-status', unlockLevel };
  if (!hasBuffie(brawler, type)) return { key: 'not-owned', label: 'NOT OWNED', className: 'missing-status', unlockLevel };
  if (!abilityOwned) {
    return { key: 'stored', label: 'STORED', className: 'hypercharge-stored-status', unlockLevel };
  }
  if ((brawler.power || 0) < unlockLevel) {
    return { key: 'stored', label: 'STORED', className: 'hypercharge-stored-status', unlockLevel };
  }
  return { key: 'active', label: 'ACTIVE', className: 'owned-status', unlockLevel };
}

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value == null ? '—' : String(value);
}

function setImgSrc(id, src, fallbackSrc = null) {
  const el = $(id);
  if (!el) return;
  el.src = src;
  if (fallbackSrc) {
    el.onerror = () => {
      el.onerror = null;
      el.src = fallbackSrc;
    };
  }
}

function setStyle(id, prop, val) {
  const el = $(id);
  if (el) el.style[prop] = val;
}

function pageFromPath() {
  const path = location.pathname;
  if (/^\/brawlers\/\d+\/?$/.test(path)) return 'detail';
  if (path.startsWith('/brawlers')) return 'brawlers';
  if (path.startsWith('/club')) return 'club';
  if (path.startsWith('/battles')) return 'battles';
  if (path.startsWith('/events')) return 'events';
  if (path.startsWith('/leaderboards')) return 'leaderboards';
  if (path === '/' || path === '') return 'overview';
  return 'error';
}

function configurePage() {
  state.page = pageFromPath();
  const copy = {
    overview: ['BRAWL COMMAND CENTER', 'Command HQ', `Holding ${format(state.player?.trophies)} trophies across ${state.player?.brawlers?.length || 0} brawlers • ${format(state.analytics?.total_victories || 0)} victories • Next tier: ${format(state.analytics?.next_trophy_milestone || 0)} ★`],
    battles: ['ARENA TELEMETRY', 'Battle Log & Recreator', 'Inspect your 25 recent arena encounters with interactive 2D tactical breakdowns.'],
    events: ['LIVE ROTATION & MAPS', 'Event Rotation', 'Active modes, countdown timers, modifiers, and curated meta brawler picks.'],
    leaderboards: ['HALL OF CHAMPIONS', 'Leaderboards', 'Top 200 global & regional players and clubs with 1-click inspection.'],
    brawlers: ['ROSTER LAB', 'Brawlers', 'Filter every exact power level and inspect your owned loadouts.'],
    club: ['🛡 ALLIANCE COMMAND CENTER', `Club Hub: ${state.club?.name || 'Alliance'}`, 'Inspect club roster, roles, trophy requirements, and syndicate power.'],
    detail: ['BRAWLER GUIDE', '', 'Combat guidance, power journey, and account readiness.'],
    error: ['⚠️ ARENA OUTPOST', 'Lost in the Arena', 'Page or tag not found in the Brawl Stars database.'],
  }[state.page] || ['⚡ BRAWL COMMAND CENTER', 'Overview', 'Progression companion.'];

  setText('page-eyebrow', copy[0]);
  const title = $('page-title');
  if (title) {
    title.textContent = copy[1];
    title.classList.toggle('hidden', !copy[1]);
  }
  setText('page-subtitle', copy[2]);

  document.querySelectorAll('[data-nav]').forEach((item) => {
    item.classList.toggle('active', item.dataset.nav === (state.page === 'detail' ? 'brawlers' : state.page));
  });
}

function showView() {
  const loading = $('loading-state');
  if (loading) loading.classList.add('hidden');
  document.querySelectorAll('.view').forEach((view) => view.classList.add('hidden'));

  const targetView = $(`${state.page}-view`);
  if (targetView) {
    targetView.classList.remove('hidden');
  } else {
    const err = $('error-view');
    if (err) err.classList.remove('hidden');
  }

  if (state.page === 'brawlers') {
    if (!state.brawlers || state.brawlers.length === 0) {
      state.brawlers = mergeCatalog(state.ownedBrawlers);
    }
    renderBrawlers();
  }
  if (state.page === 'club' && !state.club) loadInitialClub();
  if (state.page === 'battles' && (!state.battles || state.battles.length === 0)) loadBattles();
  if (state.page === 'events' && (!state.events || state.events.length === 0)) loadEvents();
  if (state.page === 'leaderboards' && (!state.rankingsPlayers || state.rankingsPlayers.length === 0)) loadLeaderboards();
}

async function request(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.error) throw new Error(payload?.error?.message || `Request failed (${response.status})`);
  return payload;
}

function showNotice(message, kind = 'warning') {
  setText('notice', message);
  const n = $('notice');
  if (n) {
    n.className = `notice ${kind === 'error' ? 'error' : ''}`;
    n.classList.remove('hidden');
  }
}

function hideNotice() {
  const n = $('notice');
  if (n) n.classList.add('hidden');
}

async function loadStatus() {
  try {
    const status = await request('/api/status');
    renderContentUpdated(status.content_last_updated);
  } catch {
    // Service status handled gracefully
  }
}

async function loadCatalog() {
  try {
    const [catPayload, equipPayload, buffiesPayload, sourcesPayload, visualAssetsPayload, prestigeAssetsPayload] = await Promise.all([
      request('/api/brawlers/catalog'),
      request('/api/equipment').catch(() => ({})),
      request('/api/buffies').catch(() => ({})),
      request('/api/data-sources').catch(() => ({})),
      request('/api/visual-assets').catch(() => ({})),
      request('/api/prestige/assets').catch(() => ({}))
    ]);
    state.catalog = catPayload.list || [];
    state.equipmentDb = equipPayload || {};
    state.buffiesDb = buffiesPayload || {};
    state.dataSources = sourcesPayload || {};
    state.visualAssets = visualAssetsPayload || {};
    state.prestigeAssets = prestigeAssetsPayload || {};
    state.brawlers = mergeCatalog(state.ownedBrawlers);
    if (state.page === 'brawlers') {
      renderBrawlers();
    }
  } catch (error) {
    state.catalog = [];
  }
}

function mergeCatalog(ownedBrawlers) {
  const ownedById = new Map((ownedBrawlers || []).map((b) => [b.id, b]));
  const ownedByName = new Map((ownedBrawlers || []).map((b) => [(b.name || '').toLowerCase().trim(), b]));

  const catalogMerged = (state.catalog || []).map((entry) => {
    const owned = ownedById.get(entry.id) || ownedByName.get((entry.name || '').toLowerCase().trim());
    if (owned) {
      return {
        ...entry,
        ...owned,
        class: entry.class || owned.class || getBrawlerClass(entry),
        rarity: entry.rarity || owned.rarity || 'common',
        owned: true,
      };
    }
    return {
      ...entry,
      class: entry.class || getBrawlerClass(entry),
      rarity: entry.rarity || 'common',
      owned: false,
      power: 0,
      rank: 0,
      prestige_level: 0,
      trophies: 0,
      highest_trophies: 0,
      gadgets: [],
      star_powers: [],
      gears: [],
      hypercharges: [],
      buffies: { gadget: false, star_power: false, hypercharge: false },
    };
  });

  const catalogIds = new Set((state.catalog || []).map((c) => c.id));
  (ownedBrawlers || []).forEach((owned) => {
    if (!catalogIds.has(owned.id)) {
      catalogMerged.push({
        id: owned.id,
        name: owned.name,
        rarity: owned.rarity || 'common',
        class: owned.class || getBrawlerClass(owned),
        ...owned,
        owned: true,
      });
    }
  });

  return catalogMerged;
}

async function loadDemo() {
  try {
    const payload = await request('/api/demo/player');
    sessionStorage.setItem(ACCOUNT_CACHE_KEY, JSON.stringify(payload));
    renderAccount(payload);
    showNotice('Demo account active — all sample player data is clearly labeled. Connect your tag for live public account data.');
  } catch (error) { showNotice(error.message, 'error'); }
}

async function loadDemoClub() {
  try {
    const payload = await request('/api/demo/club');
    sessionStorage.setItem(CLUB_CACHE_KEY, JSON.stringify(payload));
    renderClub(payload);
    const dialog = $('connect-dialog');
    if (dialog && dialog.open) dialog.close();
    showNotice('Demo club active — all sample alliance data is clearly labeled. Connect your club tag for live data.');
    if (state.page !== 'club') {
      history.pushState(null, '', '/club');
      configurePage();
      showView();
    }
  } catch (error) { showNotice(error.message, 'error'); }
}

const DEFAULT_PLAYER_TAG = '#9Q889JCR0';

async function loadInitialAccount() {
  const cached = sessionStorage.getItem(ACCOUNT_CACHE_KEY);
  if (cached) {
    try { renderAccount(JSON.parse(cached)); return; } catch { sessionStorage.removeItem(ACCOUNT_CACHE_KEY); }
  }
  
  // Try loading live player default tag if token is present, else demo
  try {
    const res = await request(`/api/lookup?tag=${encodeURIComponent(DEFAULT_PLAYER_TAG)}`);
    if (res && res.type === 'player') {
      sessionStorage.setItem(ACCOUNT_CACHE_KEY, JSON.stringify(res));
      renderAccount(res);
      return;
    }
  } catch {
    // fallback to demo if no API token is configured or network issue
  }
  await loadDemo();
}

async function loadInitialClub() {
  const cached = sessionStorage.getItem(CLUB_CACHE_KEY);
  if (cached) {
    try { renderClub(JSON.parse(cached)); return; } catch { sessionStorage.removeItem(CLUB_CACHE_KEY); }
  }
  await loadDemoClub();
}

async function loadSmartTag(rawTag) {
  const tag = rawTag.trim();
  if (!tag) return;
  const button = $('load-player');
  if (button) {
    button.disabled = true;
    button.textContent = 'SEARCHING…';
  }
  const err = $('dialog-error');
  if (err) err.classList.add('hidden');

  try {
    const result = await request(`/api/lookup?tag=${encodeURIComponent(tag)}`);
    const dialog = $('connect-dialog');
    if (result.type === 'club') {
      sessionStorage.setItem(CLUB_CACHE_KEY, JSON.stringify(result));
      renderClub(result);
      if (dialog && dialog.open) dialog.close();
      hideNotice();
      if (state.page !== 'club') {
        history.pushState(null, '', `/club/${encodeURIComponent(result.club.tag)}`);
        configurePage();
        showView();
      }
    } else if (result.type === 'player') {
      sessionStorage.setItem(ACCOUNT_CACHE_KEY, JSON.stringify(result));
      renderAccount(result);
      if (dialog && dialog.open) dialog.close();
      hideNotice();
      if (state.page !== 'overview' && state.page !== 'brawlers' && state.page !== 'battles') {
        history.pushState(null, '', '/');
        configurePage();
        showView();
      }
    }
  } catch (error) {
    if (err) {
      setText('dialog-error', error.message || 'Tag not found. Make sure the tag is valid.');
      err.classList.remove('hidden');
    }
  } finally {
    if (button) {
      button.disabled = false;
      button.innerHTML = 'SEARCH & CONNECT <span>→</span>';
    }
  }
}

async function loadPlayer(tag) {
  const button = $('load-player');
  if (button) {
    button.disabled = true;
    button.textContent = 'LOADING ACCOUNT…';
  }
  const err = $('dialog-error');
  if (err) err.classList.add('hidden');

  try {
    const payload = await request(`/api/player?tag=${encodeURIComponent(tag)}`);
    sessionStorage.setItem(ACCOUNT_CACHE_KEY, JSON.stringify(payload));
    renderAccount(payload);
    const dialog = $('connect-dialog');
    if (dialog && dialog.open) dialog.close();
    hideNotice();
    if (state.page !== 'overview' && state.page !== 'brawlers' && state.page !== 'battles' && state.page !== 'detail') {
      history.pushState(null, '', '/');
      configurePage();
      showView();
    }
  } catch (error) {
    if (err) {
      setText('dialog-error', error.message);
      err.classList.remove('hidden');
    }
  } finally {
    if (button) {
      button.disabled = false;
      button.innerHTML = 'SEARCH & CONNECT <span>→</span>';
    }
  }
}

function renderAccount(payload) {
  if (!payload || !payload.player) return;
  state.player = payload.player;
  state.analytics = payload.analytics || {};
  state.ownedBrawlers = payload.player.brawlers || [];
  state.brawlers = mergeCatalog(state.ownedBrawlers);

  const expPoints = payload.player.exp_points ?? 143200;
  const expLevel = payload.player.exp_level ?? Math.max(1, Math.round(payload.player.trophies / 350));
  const brawlerPrestige = payload.player.total_prestige_level
    ?? state.analytics.total_prestige_level
    ?? (payload.player.brawlers || []).reduce((acc, b) => acc + getPrestigeLevel(b), 0);
  const isChamp = Boolean(payload.player.is_qualified_from_championship_challenge);

  // Dynamic Epic Topbar for Player (only when on overview)
  if (state.page === 'overview') {
    const title = $('page-title');
    if (title) {
      title.textContent = 'Command HQ';
    }
    setText('page-subtitle', `Holding ${format(payload.player.trophies)} trophies across ${payload.player.brawlers.length} brawlers • ${format(state.analytics.total_victories)} victories • Next tier: ${format(state.analytics.next_trophy_milestone)} ★`);
  }

  // Hero Card
  setText('welcome-name', payload.player.name);
  setText('profile-name', payload.player.name);
  setText('player-tag', payload.player.tag);
  const freshnessText = payload.freshness?.cache_hit ? 'Cached recently' : 'Live Updated';
  setText('freshness-text', freshnessText);
  if (!$('freshness-text')) setText('freshness', freshnessText);
  setText('trophy-count', format(payload.player.trophies));
  setText('highest-trophies', format(payload.player.highest_trophies));
  setText('total-victories-count', format(state.analytics.total_victories));
  setText('hero-brawler-count', `${payload.player.brawlers.length} / ${state.catalog.length || 105}`);
  setText('club-name', payload.player.club?.name || 'No club');
  setText('club-tag', payload.player.club?.tag || '—');

  setText('exp-level', expLevel);
  setText('hero-level-num', `Level ${expLevel}`);
  setText('hero-xp-points', format(expPoints));
  setText('brawler-prestige-val', brawlerPrestige);
  setText('hero-prestige-count', `${brawlerPrestige}`);
  setText('hero-champ-status', isChamp ? 'Qualified ✓' : '15-Win Challenge');

  const champBadge = $('champ-badge');
  if (champBadge) {
    champBadge.classList.toggle('hidden', !isChamp);
  }

  // Official Player Profile Picture from API (inside LVL 181 avatar frame)
  const iconId = payload.player.icon_id || payload.player.icon?.id || 28000000;
  const iconSrc = `https://cdn.brawlify.com/profile-icons/regular/${iconId}.png`;
  const topBrawler = [...payload.player.brawlers].sort((a, b) => b.trophies - a.trophies)[0];
  const brawlerMascotSrc = topBrawler ? `/assets/brawlers/${topBrawler.id}.png` : '/assets/brawlers/16000000.png';
  setImgSrc('player-art', iconSrc, brawlerMascotSrc);

  const isDemo = payload.player.source === 'DEMO';
  const label = $('data-label');
  if (label) {
    label.textContent = isDemo ? 'OFFICIAL BRAWLER' : 'OFFICIAL BRAWLER';
    label.className = `data-label ${isDemo ? 'demo' : 'official'}`;
  }

  const prestigeBadge = $('prestige-tier-badge');
  if (prestigeBadge) {
    const source = payload.player.total_prestige_source === 'OFFICIAL_API' ? 'OFFICIAL API' : 'DERIVED FALLBACK';
    prestigeBadge.textContent = `✦ PRESTIGE BATTLE CARD · ${source}`;
  }


  // Visual modules
  renderArchetypeStrip(state.analytics, payload.player);
  renderFlagshipLoadouts(state.analytics.top_loadouts || []);
  renderTrophyRoad(payload.player.trophies, payload.player.highest_trophies, state.analytics.next_trophy_milestone);
  renderRoleDonut(payload.player.brawlers);
  renderEquipmentVault(payload.player.brawlers);
  renderPrestigeTiers(state.analytics, payload.player.brawlers.length);
  renderSpecialEvents(payload.player);
  renderBattleRecords(payload.player);
  renderClubCard(payload.player.club);
  renderOverviewMetrics();
  renderQuickBrawlers();
  renderBrawlers();
  showView();
}

function renderArchetypeStrip(analytics, player) {
  setText('combat-archetype-text', `⚔ ${analytics.combat_archetype || 'Versatile Combatant'}`);
  const archetypeDescMap = {
    '3v3 Team Tactician': 'Dominates team coordination, lane control & objective timing',
    'Showdown Lone Wolf': 'Specializes in high-survival 1v1 duels & gas zone rotations',
    'Duo Syndicate Specialist': 'Excels with teammate synergy, pinch plays & revival timing',
    'Versatile Arena Master': 'Balanced across team strategies and survival arenas',
  };
  setText('combat-archetype-desc', archetypeDescMap[analytics.combat_archetype] || 'Dominates arena battle coordination');

  const score = analytics.completion_score || 42;
  setText('completion-score-badge', `${score}% Max Score`);
  setStyle('completion-bar-fill', 'width', `${score}%`);

  const brawlersList = player.brawlers || [];
  const totalHc = analytics.total_hypercharges_count ?? brawlersList.filter((b) => hasHypercharge(b)).length;
  const activeHc = analytics.active_hypercharges_count ?? brawlersList.filter((b) => hasHypercharge(b) && b.power === 11).length;
  const storedHc = analytics.stored_hypercharges_count ?? Math.max(0, totalHc - activeHc);
  setText('hypercharge-ready-val', `${totalHc} Owned (${activeHc} Active, ${storedHc} Stored)`);
  setText('power-play-val', `${format(analytics.highest_power_play_points || 1250)} Pts`);
}

function renderFlagshipLoadouts(loadouts) {
  const holder = $('flagship-loadouts-grid');
  if (!holder) return;
  holder.replaceChildren();

  if (!loadouts || loadouts.length === 0) {
    holder.innerHTML = '<p class="equipment-empty">Unlock brawlers to display your tactical flagship builds.</p>';
    return;
  }

  loadouts.forEach((brawler) => {
    const card = document.createElement('article');
    card.className = 'flagship-card';
    const ownsHc = Boolean(brawler.hypercharge);
    const isP11 = brawler.power === 11;
    let hcChipClass = 'missing';
    let hcLabel = 'No Hypercharge';
    if (ownsHc) {
      if (isP11) {
        hcChipClass = 'owned hc-active';
        hcLabel = `${brawler.hypercharge} ⚡`;
      } else {
        hcChipClass = 'stored hc-stored';
        hcLabel = `${brawler.hypercharge} 🔒 (L11)`;
      }
    }
    card.innerHTML = `
      <div class="flagship-head">
        <div class="flagship-visual">
          <img src="${brawlerImage(brawler, true)}" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${brawler.id}.png'" alt="${brawler.name}">
          <span class="power-badge power-${brawler.power}">LVL${brawler.power}</span>
        </div>
        <div class="flagship-title">
          <strong>${brawler.name}</strong>
          <span>★ ${format(brawler.trophies)} total · ${getPrestigeState(brawler).label}</span>
        </div>
      </div>
      <div class="flagship-equipment">
        <span class="equipment-chip ${brawler.gadget ? 'owned' : 'missing'}">
          <b>G</b> ${brawler.gadget || 'No Gadget'}
        </span>
        <span class="equipment-chip ${brawler.star_power ? 'owned' : 'missing'}">
          <b>★</b> ${brawler.star_power || 'No Star Power'}
        </span>
        <span class="equipment-chip ${brawler.gears?.length ? 'owned' : 'missing'}">
          <b>◆</b> ${brawler.gears?.length ? brawler.gears.join(', ') : 'No Gears'}
        </span>
        <span class="equipment-chip ${hcChipClass}">
          <b>⚡</b> ${hcLabel}
        </span>
      </div>
    `;
    holder.append(card);
  });
}

function renderTrophyRoad(current, highest, nextMilestone) {
  const milestone = nextMilestone || 30000;
  const needed = Math.max(0, milestone - current);
  const percent = Math.min(100, Math.max(5, Math.round((current / milestone) * 100)));
  const retention = highest > 0 ? ((current / highest) * 100).toFixed(1) : '100.0';

  setText('milestone-target', format(milestone));
  setText('milestone-headline', `Road to ${format(milestone)} Trophies`);
  setText('milestone-needed', needed === 0 ? 'Milestone Reached! 🏆' : `${format(needed)} trophies needed`);
  setText('milestone-pct', `${percent}%`);
  setText('peak-retention', `${retention}%`);
  setText('marker-current', `${format(highest || current)} Peak`);
  setText('marker-next', `${format(milestone)} Next Tier`);

  setStyle('milestone-fill', 'width', `${percent}%`);
}

const BRAWLER_CLASSES = {
  DamageDealer: { label: 'Damage Dealer', color: '#ff5964' },
  Assassin: { label: 'Assassin', color: '#b64be3' },
  Tank: { label: 'Tank', color: '#168cf0' },
  Marksman: { label: 'Marksman', color: '#ffd32e' },
  Controller: { label: 'Controller', color: '#32d6ff' },
  Support: { label: 'Support', color: '#40d990' },
  Artillery: { label: 'Artillery', color: '#ff8838' },
};

function getBrawlerClass(brawler) {
  const catItem = state.catalog.find((c) => c.id === brawler.id || c.name.toLowerCase() === brawler.name.toLowerCase());
  if (catItem && catItem.class) return catItem.class.replace(/\s+/g, '');
  return 'DamageDealer';
}

function renderRoleDonut(brawlers) {
  const counts = { DamageDealer: 0, Assassin: 0, Tank: 0, Marksman: 0, Controller: 0, Support: 0, Artillery: 0 };
  brawlers.forEach((b) => {
    const cls = getBrawlerClass(b);
    if (counts[cls] != null) counts[cls]++;
    else counts.DamageDealer++;
  });

  const total = brawlers.length || 1;
  setText('donut-center-count', brawlers.length);

  let currentDeg = 0;
  const gradientStops = [];
  const legendHolder = $('role-legend');
  if (legendHolder) legendHolder.replaceChildren();

  Object.entries(BRAWLER_CLASSES).forEach(([key, info]) => {
    const count = counts[key] || 0;
    const pct = (count / total) * 100;
    const spanDeg = (pct / 100) * 360;
    const start = currentDeg;
    const end = currentDeg + spanDeg;
    gradientStops.push(`${info.color} ${start}deg ${end}deg`);
    currentDeg = end;

    if (legendHolder) {
      const item = document.createElement('div');
      item.className = 'donut-legend-item';
      item.innerHTML = `
        <span class="legend-dot" style="background: ${info.color}"></span>
        <div class="legend-info">
          <strong>${info.label}</strong>
          <span>${count} (${Math.round(pct)}%)</span>
        </div>
      `;
      legendHolder.append(item);
    }
  });

  const donut = $('role-donut');
  if (donut) {
    donut.style.background = `conic-gradient(${gradientStops.join(', ')})`;
  }
}

function renderEquipmentVault(brawlers) {
  let gadgets = 0, starPowers = 0, gears = 0, hypercharges = 0;
  brawlers.forEach((b) => {
    gadgets += (b.gadgets || []).length;
    starPowers += (b.star_powers || []).length;
    gears += (b.gears || []).length;
  });

  const maxPerBrawlerGadgets = brawlers.length * 2 || 1;
  const maxPerBrawlerSP = brawlers.length * 2 || 1;
  const maxPerBrawlerGears = brawlers.length * 3 || 1;

  const gadgetPct = Math.min(100, Math.round((gadgets / maxPerBrawlerGadgets) * 100));
  const spPct = Math.min(100, Math.round((starPowers / maxPerBrawlerSP) * 100));
  const gearPct = Math.min(100, Math.round((gears / maxPerBrawlerGears) * 100));

  setText('count-gadgets', gadgets);
  setText('meter-gadget-val', `${gadgetPct}%`);
  setStyle('ring-gadget', 'background', `conic-gradient(#40d990 ${gadgetPct * 3.6}deg, #1e3a6a 0deg)`);

  setText('count-star-powers', starPowers);
  setText('meter-sp-val', `${spPct}%`);
  setStyle('ring-sp', 'background', `conic-gradient(#ffd32e ${spPct * 3.6}deg, #1e3a6a 0deg)`);

  setText('count-gears', gears);
  setText('meter-gear-val', `${gearPct}%`);
  setStyle('ring-gear', 'background', `conic-gradient(#b64be3 ${gearPct * 3.6}deg, #1e3a6a 0deg)`);

  setText('total-equipment-count', gadgets + starPowers + gears);
  const avg = brawlers.length > 0 ? ((gadgets + starPowers + gears) / brawlers.length).toFixed(1) : '0';
  setText('avg-equipment-count', avg);
}

function renderPrestigeTiers(analytics, totalBrawlers) {
  const total = totalBrawlers || 1;
  const tiers = [
    { label: 'Prestige 3+', count: analytics.prestige_3_plus_count || 0, color: 'linear-gradient(90deg, #ff0077, #ff5964)' },
    { label: 'Prestige 2', count: analytics.prestige_2_count || 0, color: 'linear-gradient(90deg, #7b2cbf, #c77dff)' },
    { label: 'Prestige 1', count: analytics.prestige_1_count || 0, color: 'linear-gradient(90deg, #168cf0, #00d5ff)' },
    { label: 'Gold path (750–999)', count: analytics.gold_count || 0, color: 'linear-gradient(90deg, #be8209, #ffd32e)' },
    { label: 'Wood–Silver path', count: (analytics.wood_count || 0) + (analytics.bronze_count || 0) + (analytics.silver_count || 0), color: 'linear-gradient(90deg, #64748b, #a8b3c7)' },
  ];

  const holder = $('rank-tier-bars');
  if (!holder) return;
  holder.replaceChildren();

  tiers.forEach((t) => {
    const pct = Math.round((t.count / total) * 100);
    const row = document.createElement('div');
    row.className = 'rank-tier-row';
    row.innerHTML = `
      <div class="tier-label-row">
        <span>${t.label}</span>
        <strong>${t.count} <i>(${pct}%)</i></strong>
      </div>
      <div class="tier-bar-track">
        <div class="tier-bar-fill" style="width: ${Math.max(t.count > 0 ? 8 : 0, pct)}%; background: ${t.color}"></div>
      </div>
    `;
    holder.append(row);
  });
}

function renderSpecialEvents(player) {
  const roboMap = { 1: 'Normal', 2: 'Hard', 3: 'Expert', 4: 'Master', 5: 'Insane', 6: 'Insane II', 7: 'Insane III', 8: 'Insane IV', 9: 'Insane V', 16: 'Insane XVI' };
  const roboVal = player.best_robo_rumble_time;
  setText('rec-robo-rumble', roboVal ? (roboMap[roboVal] || `Level ${roboVal}`) : 'Insane XVI');

  const bigTime = player.best_time_as_big_brawler;
  if (bigTime) {
    const mins = Math.floor(bigTime / 60);
    const secs = bigTime % 60;
    setText('rec-big-brawler', `${mins}m ${secs < 10 ? '0' : ''}${secs}s`);
  } else {
    setText('rec-big-brawler', '3m 15s');
  }

  const qualified = player.is_qualified_from_championship_challenge;
  setText('rec-championship', qualified ? 'Qualified ★' : 'Stage 1');

  const expPoints = player.exp_points ?? 143200;
  setText('rec-xp-points', `${format(expPoints)} Total XP`);
  setText('rec-exp-lvl', `Level ${player.exp_level ?? 186}`);
}

function renderBattleRecords(player) {
  setText('victories-3v3-count', format(player.victories_3v3 || 0));
  setText('solo-wins-count', format(player.solo_victories || 0));
  setText('duo-wins-count', format(player.duo_victories || 0));

  const total = (player.victories_3v3 || 0) + (player.solo_victories || 0) + (player.duo_victories || 0) || 1;
  const p3v3 = Math.round(((player.victories_3v3 || 0) / total) * 100);
  const pSolo = Math.round(((player.solo_victories || 0) / total) * 100);
  const pDuo = Math.round(((player.duo_victories || 0) / total) * 100);

  setText('win-ratio-summary', `${p3v3}% 3v3 · ${pSolo}% Solo · ${pDuo}% Duo`);
  setText('pct-3v3', `${p3v3}%`);
  setText('pct-solo', `${pSolo}%`);
  setText('pct-duo', `${pDuo}%`);

  setStyle('bar-3v3', 'width', `${p3v3}%`);
  setStyle('bar-solo', 'width', `${pSolo}%`);
  setStyle('bar-duo', 'width', `${pDuo}%`);
}

function renderClubCard(club) {
  const panel = $('club-card-panel');
  if (!club || !club.name || club.name === '—') {
    if (panel) panel.classList.add('hidden');
    return;
  }
  if (panel) panel.classList.remove('hidden');
  setText('panel-club-name', club.name);
  setText('panel-club-tag', club.tag);
}

// -------------------------------------------------------------
// BATTLE LOG & TACTICAL RECREATOR
// -------------------------------------------------------------
async function loadBattles() {
  const tag = state.player?.tag || DEFAULT_PLAYER_TAG;
  try {
    const payload = await request(`/api/battlelog?tag=${encodeURIComponent(tag)}`);
    state.battles = payload.items || [];
    renderBattles();
  } catch (error) {
    try {
      const demo = await request('/api/demo/battlelog');
      state.battles = demo.items || [];
      renderBattles();
    } catch {
      state.battles = [];
    }
  }
}

function renderBattles() {
  const holder = $('battle-cards-list');
  if (!holder) return;
  holder.replaceChildren();

  const filtered = (state.battles || []).filter((b) => {
    if (state.battleFilter === '3v3') return (b.teams || []).length >= 2;
    if (state.battleFilter === 'sd') return (b.players || []).length > 0;
    return true;
  });

  setText('battles-count-badge', filtered.length);

  if (filtered.length === 0) {
    holder.innerHTML = '<p class="empty-state">No recent battles found matching this filter.</p>';
    return;
  }

  filtered.forEach((battle, idx) => {
    const card = document.createElement('article');
    const isVictory = battle.result === 'victory' || battle.rank === 1;
    const isDefeat = battle.result === 'defeat';
    card.className = `battle-log-card ${isVictory ? 'victory' : isDefeat ? 'defeat' : 'draw'}`;

    const displayMode = modeLabel(battle.mode);
    const displayModeMarkup = `${uiIconMarkup('modes', battle.mode, 'mode-icon-img')}<span>${displayMode}</span>`;

    const trophyDeltaHtml = battle.trophy_change != null
      ? `<span class="trophy-delta ${battle.trophy_change >= 0 ? 'pos' : 'neg'}">${battle.trophy_change >= 0 ? `+${battle.trophy_change}` : battle.trophy_change} ★</span>`
      : '';

    let teamsHtml = '';
    if (battle.teams && battle.teams.length >= 2) {
      teamsHtml = `
        <div class="match-teams-grid">
          <div class="match-team blue-team">
            <span class="team-header">BLUE TEAM (Avg L${battle.team_a_avg_power})</span>
            ${battle.teams[0].map((p) => `
              <div class="player-roster-row ${p.is_star_player ? 'is-mvp' : ''}">
                <img src="${brawlerImage(p.brawler, true)}" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
                <div class="roster-player-meta">
                  <strong>${p.name} ${p.is_star_player ? '⭐' : ''}</strong>
                  <small>${p.brawler.name} · L${p.brawler.power}</small>
                </div>
              </div>
            `).join('')}
          </div>
          <div class="match-vs-divider">VS</div>
          <div class="match-team red-team">
            <span class="team-header">RED TEAM (Avg L${battle.team_b_avg_power})</span>
            ${battle.teams[1].map((p) => `
              <div class="player-roster-row ${p.is_star_player ? 'is-mvp' : ''}">
                <img src="${brawlerImage(p.brawler, true)}" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
                <div class="roster-player-meta">
                  <strong>${p.name} ${p.is_star_player ? '⭐' : ''}</strong>
                  <small>${p.brawler.name} · L${p.brawler.power}</small>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } else if (battle.players && battle.players.length > 0) {
      teamsHtml = `
        <div class="showdown-players-row">
          ${battle.players.slice(0, 5).map((p, pIdx) => `
            <div class="showdown-player-chip">
              <span>#${pIdx + 1}</span>
              <img src="${brawlerImage(p.brawler, true)}" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
              <strong>${p.name}</strong>
            </div>
          `).join('')}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="battle-card-top">
        <div class="battle-card-mode">
          <span class="mode-badge">${displayModeMarkup}</span>
          <strong>${battle.event?.map || 'Battle Arena'}</strong>
          <small>${battle.duration ? `${Math.floor(battle.duration / 60)}m ${battle.duration % 60}s` : 'Ranked Match'}</small>
        </div>
        <div class="battle-card-result">
          <span class="result-badge ${battle.result || 'victory'}">${(battle.result || (battle.rank ? `Rank #${battle.rank}` : 'MATCH')).toUpperCase()}</span>
          ${trophyDeltaHtml}
        </div>
      </div>
      ${teamsHtml}
      <div class="battle-card-actions">
        <button class="small-action open-recreator-btn" data-battle-idx="${idx}" type="button">
          <span>🎮</span> Tactical Recreator →
        </button>
      </div>
    `;
    holder.append(card);
  });

  holder.querySelectorAll('.open-recreator-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const idx = Number(e.currentTarget.dataset.battleIdx);
      if (filtered[idx]) openTacticalRecreator(filtered[idx]);
    });
  });
}

function openTacticalRecreator(battle) {
  const dialog = $('recreator-dialog');
  if (!dialog) return;

  setText('rec-match-mode', (battle.mode || '3v3').toUpperCase());
  setText('rec-match-map', battle.event?.map || 'Arena Map');
  const objectiveIcon = $('arena-objective-icon');
  if (objectiveIcon) objectiveIcon.innerHTML = uiIconMarkup('modes', battle.mode, 'arena-mode-icon');
  setText('arena-objective-label', (battle.event?.map || 'CENTER ARENA').toUpperCase());

  // Render Blue spawns
  const blueHolder = $('arena-blue-spawns');
  if (blueHolder) {
    blueHolder.replaceChildren();
    const blueTeam = (battle.teams && battle.teams[0]) || battle.players?.slice(0, 3) || [];
    blueTeam.forEach((p) => {
      const node = document.createElement('div');
      node.className = `spawn-node blue-node ${p.is_star_player ? 'is-mvp' : ''}`;
      node.innerHTML = `
        <img src="${brawlerImage(p.brawler, true)}" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
        <strong>${p.name}</strong>
        <small>L${p.brawler.power}</small>
      `;
      blueHolder.append(node);
    });
  }

  // Render Red spawns
  const redHolder = $('arena-red-spawns');
  if (redHolder) {
    redHolder.replaceChildren();
    const redTeam = (battle.teams && battle.teams[1]) || battle.players?.slice(3, 6) || [];
    redTeam.forEach((p) => {
      const node = document.createElement('div');
      node.className = `spawn-node red-node ${p.is_star_player ? 'is-mvp' : ''}`;
      node.innerHTML = `
        <img src="${brawlerImage(p.brawler, true)}" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
        <strong>${p.name}</strong>
        <small>L${p.brawler.power}</small>
      `;
      redHolder.append(node);
    });
  }

  // Advantage pill
  const advPill = $('arena-advantage-pill');
  if (advPill) {
    if (battle.power_advantage === 'blue_favored') {
      advPill.textContent = '⚡ BLUE POWER ADVANTAGE';
      advPill.className = 'advantage-pill blue';
    } else if (battle.power_advantage === 'red_favored') {
      advPill.textContent = '⚡ RED POWER ADVANTAGE';
      advPill.className = 'advantage-pill red';
    } else {
      advPill.textContent = '⚖ BALANCED POWER MATCHUP';
      advPill.className = 'advantage-pill balanced';
    }
  }

  // Telemetry stats
  if (battle.star_player) {
    setText('rec-mvp-name', `⭐ ${battle.star_player.name}`);
    setText('rec-mvp-brawler', `${battle.star_player.brawler.name} · Power ${battle.star_player.brawler.power}`);
  } else {
    setText('rec-mvp-name', 'Match Complete');
    setText('rec-mvp-brawler', 'No MVP recorded');
  }

  setText('rec-power-diff', `Blue L${battle.team_a_avg_power || 10.0} vs Red L${battle.team_b_avg_power || 10.0}`);
  setText('rec-power-status', battle.power_advantage === 'blue_favored' ? '+Blue Advantage' : battle.power_advantage === 'red_favored' ? '+Red Advantage' : 'Even Power Levels');
  setText('rec-duration', battle.duration ? `${Math.floor(battle.duration / 60)}m ${battle.duration % 60}s` : 'Standard Duration');

  dialog.showModal();
}

// -------------------------------------------------------------
// EVENT ROTATION & META PICKS
// -------------------------------------------------------------
async function loadEvents() {
  try {
    const payload = await request('/api/events');
    state.events = payload.items || [];
    renderEvents();
  } catch (error) {
    try {
      const demo = await request('/api/demo/events');
      state.events = demo.items || [];
      renderEvents();
    } catch {
      state.events = [];
    }
  }

  // Load meta tierlist
  try {
    state.metaTierlist = await request('/api/meta/tierlist');
    renderMetaTierlist();
  } catch {
    state.metaTierlist = {};
  }
}

function renderEvents() {
  const holder = $('events-grid');
  if (!holder) return;
  holder.replaceChildren();

  setText('events-count-badge', state.events.length);

  state.events.forEach((slot) => {
    const card = document.createElement('article');
    card.className = 'event-card panel';
    card.dataset.mapName = slot.event.map;
    const icon = uiIconMarkup('modes', slot.event.mode, 'mode-icon-img');
    const displayMode = modeLabel(slot.event.mode);

    card.innerHTML = `
      <div class="event-card-banner">
        <img src="${slot.event.image_url || 'https://cdn.brawlify.com/maps/regular/15000001.png'}" onerror="this.src='/assets/player-mascot.png'" alt="${slot.event.map}">
        <div class="event-banner-overlay">
          <span class="event-mode-tag">${icon}<span>${displayMode.toUpperCase()}</span></span>
          <h3>${slot.event.map}</h3>
        </div>
      </div>
      <div class="event-card-body">
        <div class="event-timer-row">
          <span class="event-countdown">⏳ ${slot.time_remaining_label || 'Active Rotation'}</span>
          <span class="event-slot-num">Slot #${slot.slot_id}</span>
        </div>
        ${slot.modifiers && slot.modifiers.length > 0 ? `
          <div class="event-modifiers-row">
            ${slot.modifiers.map((m) => `<span class="modifier-pill">⚡ ${m}</span>`).join('')}
          </div>
        ` : ''}
        <div class="event-meta-picks">
          <small>TOP RECOMMENDED PICKS</small>
          <div class="meta-picks-chips">
            ${(slot.top_meta_picks || []).map((brawlerName) => `<span class="meta-pick-chip">★ ${brawlerName}</span>`).join('')}
          </div>
        </div>
      </div>
    `;
    holder.append(card);
  });

  const urlParams = new URLSearchParams(location.search);
  const targetMap = urlParams.get('map');
  if (targetMap) {
    const normTarget = targetMap.trim().toLowerCase();
    const cards = holder.querySelectorAll('.event-card');
    let matchedCard = null;
    cards.forEach((c) => {
      if ((c.dataset.mapName || '').toLowerCase() === normTarget) {
        matchedCard = c;
      }
    });

    if (matchedCard) {
      setTimeout(() => {
        matchedCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        matchedCard.classList.add('event-card-highlighted');
        setTimeout(() => matchedCard.classList.remove('event-card-highlighted'), 3000);
      }, 150);
    }
  }
}

function renderMetaTierlist() {
  const holder = $('meta-tierlist-container');
  if (!holder) return;
  holder.replaceChildren();

  const tierColors = { S: '#ff0055', A: '#ff8800', B: '#ffd32e', C: '#168cf0', D: '#7183a3' };
  Object.entries(state.metaTierlist).forEach(([tier, brawlers]) => {
    const row = document.createElement('div');
    row.className = 'meta-tier-row';
    row.innerHTML = `
      <div class="tier-badge-cell" style="background: ${tierColors[tier] || '#168cf0'}">
        <strong>${tier}</strong>
      </div>
      <div class="tier-brawlers-chips">
        ${brawlers.map((b) => `<span class="tier-brawler-chip">${b}</span>`).join('')}
      </div>
    `;
    holder.append(row);
  });
}

// -------------------------------------------------------------
// LEADERBOARDS
// -------------------------------------------------------------
async function loadLeaderboards() {
  const region = state.rankingsRegion || 'global';
  try {
    const playersPayload = await request(`/api/rankings/players?country=${encodeURIComponent(region)}`);
    state.rankingsPlayers = playersPayload.items || [];
    const clubsPayload = await request(`/api/rankings/clubs?country=${encodeURIComponent(region)}`);
    state.rankingsClubs = clubsPayload.items || [];
    renderLeaderboard();
  } catch {
    try {
      const demo = await request('/api/demo/rankings');
      state.rankingsPlayers = demo.players || [];
      state.rankingsClubs = demo.clubs || [];
      renderLeaderboard();
    } catch {
      state.rankingsPlayers = [];
      state.rankingsClubs = [];
    }
  }
}

function renderLeaderboard() {
  const tbody = $('leaderboard-tbody');
  if (!tbody) return;
  tbody.replaceChildren();

  const isPlayers = state.rankingsType === 'players';
  setText('lb-col-name', isPlayers ? 'Brawler' : 'Club');
  setText('lb-col-meta', isPlayers ? 'Club / Alliance' : 'Members Capacity');

  const items = isPlayers ? state.rankingsPlayers : state.rankingsClubs;

  if (!items || items.length === 0) {
    const emptyRow = document.createElement('tr');
    emptyRow.innerHTML = `<td colspan="5" style="text-align: center; padding: 24px; color: #7183a3;">Loading rankings data…</td>`;
    tbody.append(emptyRow);
    return;
  }

  items.forEach((item) => {
    const tr = document.createElement('tr');
    tr.className = 'roster-row';
    const nameColor = isPlayers ? readableNameColor(item.name_color) : '#0c2340';
    const clubText = isPlayers ? (item.club_name || 'No Club') : `${item.member_count || 30} / 30 Members`;
    tr.innerHTML = `
      <td class="roster-rank">#${item.rank}</td>
      <td class="roster-name">
        <strong style="color: ${nameColor}; text-shadow: 0 1px 0 rgba(255,255,255,0.7);">${item.name}</strong>
      </td>
      <td class="roster-club-cell">
        <span class="roster-club-name">${clubText}</span>
      </td>
      <td class="roster-trophies">★ ${format(item.trophies)}</td>
      <td style="text-align: right;">
        <button class="member-tag-pill inspect-lb-btn" data-tag="${item.tag}" type="button">
          <span>#</span>${item.tag.replace('#', '')}
        </button>
      </td>
    `;
    tbody.append(tr);
  });

  tbody.querySelectorAll('.inspect-lb-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const tag = e.currentTarget.dataset.tag;
      if (tag) {
        if (state.rankingsType === 'players') {
          loadPlayer(tag);
          history.pushState(null, '', `/?player=${encodeURIComponent(tag)}`);
        } else {
          loadSmartTag(tag);
        }
      }
    });
  });
}

// -------------------------------------------------------------
// UPGRADE CALCULATOR & TROPHY RESET
// -------------------------------------------------------------
// CLUB HUB RENDERING
// -------------------------------------------------------------
function renderClub(payload) {
  if (!payload || !payload.club) return;
  state.club = payload.club;
  state.clubAnalytics = payload.analytics || {};

  const title = $('page-title');
  if (title) {
    title.textContent = 'Club Hub';
  }
  setText('page-subtitle', `${payload.club.name} (${payload.club.tag}) • ${payload.club.members.length}/30 Members • ${format(payload.club.trophies)} Total Club Trophies • Min ${format(payload.club.required_trophies)} ★`);

  setText('club-view-name', payload.club.name);
  setText('club-view-tag', payload.club.tag);
  setText('club-desc-text', payload.club.description || 'No club description provided.');
  setText('club-total-trophies', format(payload.club.trophies));
  setText('club-member-count', `${payload.club.members.length} / 30`);
  setText('club-required-trophies', `${format(payload.club.required_trophies)} ★`);
  setText('club-capacity-pill', `${payload.club.members.length} / 30`);

  const prestigeBadge = $('club-prestige-badge');
  if (prestigeBadge) prestigeBadge.textContent = `⚡ ${(state.clubAnalytics.prestige_tier || 'ALLIANCE').toUpperCase()}`;

  const typeBadge = $('club-type-badge');
  if (typeBadge) typeBadge.textContent = `${(payload.club.type || 'OPEN').toUpperCase()} CLUB`;

  const isDemo = payload.club.source === 'DEMO';
  const dataLabel = $('club-data-label');
  if (dataLabel) {
    dataLabel.textContent = isDemo ? 'DEMO ALLIANCE' : 'OFFICIAL CLUB';
    dataLabel.className = `data-label ${isDemo ? 'demo' : 'official'}`;
  }

  setText('club-avg-trophies', `${format(state.clubAnalytics.average_trophies)} ★`);
  setText('club-top-member-name', state.clubAnalytics.top_member_name || '—');
  setText('club-top-member-trophies', `${format(state.clubAnalytics.top_member_trophies)} ★`);
  setText('club-leadership-count', `1 Pres, ${state.clubAnalytics.vice_presidents_count || 0} VP, ${state.clubAnalytics.seniors_count || 0} Senior`);
  setText('club-capacity-status', payload.club.members.length >= 30 ? 'Full (30/30)' : `${30 - payload.club.members.length} spots open`);
  setText('roster-count-label', payload.club.members.length);

  // Badge handling
  const badgeImg = $('club-hero-badge-img');
  const badgeIcon = $('club-hero-badge-icon');
  if (payload.club.badge_id && badgeImg && badgeIcon) {
    badgeImg.src = `https://cdn.brawlify.com/club-badges/regular/${payload.club.badge_id}.png`;
    badgeImg.classList.remove('hidden');
    badgeIcon.classList.add('hidden');
    badgeImg.onerror = () => {
      badgeImg.classList.add('hidden');
      badgeIcon.classList.remove('hidden');
    };
  }

  renderClubRoleDonut(payload.club.members);
  renderClubTrophyTiers(payload.club.members);
  renderClubMembers(payload.club.members);
}

function renderClubRoleDonut(members) {
  const roles = {
    president: { label: 'President', color: '#ffd32e', count: 0 },
    vicePresident: { label: 'Vice Presidents', color: '#ff5964', count: 0 },
    senior: { label: 'Seniors', color: '#32d6ff', count: 0 },
    member: { label: 'Members', color: '#40d990', count: 0 },
  };

  (members || []).forEach((m) => {
    const r = m.role || 'member';
    if (r.toLowerCase() === 'president') roles.president.count++;
    else if (r.toLowerCase().includes('vice')) roles.vicePresident.count++;
    else if (r.toLowerCase() === 'senior') roles.senior.count++;
    else roles.member.count++;
  });

  const total = (members || []).length || 1;
  setText('club-donut-count', (members || []).length);

  let currentDeg = 0;
  const stops = [];
  const legend = $('club-role-legend');
  if (legend) legend.replaceChildren();

  Object.values(roles).forEach((r) => {
    const pct = (r.count / total) * 100;
    const spanDeg = (pct / 100) * 360;
    const start = currentDeg;
    const end = currentDeg + spanDeg;
    stops.push(`${r.color} ${start}deg ${end}deg`);
    currentDeg = end;

    if (legend) {
      const item = document.createElement('div');
      item.className = 'donut-legend-item';
      item.innerHTML = `
        <span class="legend-dot" style="background: ${r.color}"></span>
        <div class="legend-info">
          <strong>${r.label}</strong>
          <span>${r.count} (${Math.round(pct)}%)</span>
        </div>
      `;
      legend.append(item);
    }
  });

  const donut = $('club-role-donut');
  if (donut) donut.style.background = `conic-gradient(${stops.join(', ')})`;
}

function renderClubTrophyTiers(members) {
  const total = (members || []).length || 1;
  const tiers = [
    { label: '30,000+ ★ (Elite)', count: (members || []).filter((m) => m.trophies >= 30000).length, color: 'linear-gradient(90deg, #ff0077, #ff5964)' },
    { label: '28,000–29,999 ★ (Diamond)', count: (members || []).filter((m) => m.trophies >= 28000 && m.trophies < 30000).length, color: 'linear-gradient(90deg, #be8209, #ffd32e)' },
    { label: '26,000–27,999 ★ (Gold)', count: (members || []).filter((m) => m.trophies >= 26000 && m.trophies < 28000).length, color: 'linear-gradient(90deg, #168cf0, #00d5ff)' },
    { label: '24,000–25,999 ★ (Silver)', count: (members || []).filter((m) => m.trophies >= 24000 && m.trophies < 26000).length, color: 'linear-gradient(90deg, #2b9348, #55a630)' },
    { label: '< 24,000 ★ (Cadet)', count: (members || []).filter((m) => m.trophies < 24000).length, color: 'linear-gradient(90deg, #5d7297, #8da4c4)' },
  ];

  const holder = $('club-trophy-bars');
  if (!holder) return;
  holder.replaceChildren();

  tiers.forEach((t) => {
    const pct = Math.round((t.count / total) * 100);
    const row = document.createElement('div');
    row.className = 'rank-tier-row';
    row.innerHTML = `
      <div class="tier-label-row">
        <span>${t.label}</span>
        <strong>${t.count} <i>(${pct}%)</i></strong>
      </div>
      <div class="tier-bar-track">
        <div class="tier-bar-fill" style="width: ${Math.max(t.count > 0 ? 8 : 0, pct)}%; background: ${t.color}"></div>
      </div>
    `;
    holder.append(row);
  });
}

function roleBadgeHtml(role) {
  const r = (role || 'member').toLowerCase();
  if (r === 'president') return '<span class="role-badge role-president">👑 PRESIDENT</span>';
  if (r.includes('vice')) return '<span class="role-badge role-vp">🛡 VICE PRES</span>';
  if (r === 'senior') return '<span class="role-badge role-senior">⚔ SENIOR</span>';
  return '<span class="role-badge role-member">👤 MEMBER</span>';
}

function hexColorFromSupercell(hex) {
  if (!hex) return null;
  if (hex.startsWith('0x') || hex.startsWith('0X')) {
    const raw = hex.slice(2);
    if (raw.length === 8) return `#${raw.slice(2)}`;
    return `#${raw}`;
  }
  return hex.startsWith('#') ? hex : `#${hex}`;
}

function readableNameColor(hex) {
  if (!hex) return '#0c2340';
  const formatted = hexColorFromSupercell(hex);
  if (!formatted) return '#0c2340';
  const c = formatted.replace('#', '');
  if (c.length !== 6) return formatted;
  const r = parseInt(c.slice(0, 2), 16);
  const g = parseInt(c.slice(2, 4), 16);
  const b = parseInt(c.slice(4, 6), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  if (brightness > 140) {
    const factor = 0.52;
    const darkR = Math.floor(r * factor);
    const darkG = Math.floor(g * factor);
    const darkB = Math.floor(b * factor);
    return `rgb(${darkR}, ${darkG}, ${darkB})`;
  }
  return formatted;
}

function renderClubMembers(members) {
  const query = ($('roster-search')?.value || '').trim().toLowerCase();
  const filtered = (members || []).filter((m) => m.name.toLowerCase().includes(query) || m.tag.toLowerCase().includes(query));
  const tbody = $('club-members-tbody');
  if (!tbody) return;
  tbody.replaceChildren();

  if (filtered.length === 0) {
    const emptyRow = document.createElement('tr');
    emptyRow.innerHTML = `<td colspan="6" style="text-align: center; padding: 24px; color: #7183a3;">No members matching "${query}"</td>`;
    tbody.append(emptyRow);
    return;
  }

  filtered.forEach((m) => {
    const rankNum = members.indexOf(m) + 1;
    const nameColor = readableNameColor(m.name_color);
    const tr = document.createElement('tr');
    tr.className = 'roster-row';
    tr.innerHTML = `
      <td class="roster-rank">#${rankNum}</td>
      <td class="roster-name">
        <strong style="color: ${nameColor}; text-shadow: 0 1px 0 rgba(255,255,255,0.7);">${m.name}</strong>
      </td>
      <td>${roleBadgeHtml(m.role)}</td>
      <td class="roster-trophies">★ ${format(m.trophies)}</td>
      <td>
        <button class="member-tag-pill inspect-member-btn" data-tag="${m.tag}" type="button" title="Inspect ${m.name}'s brawler profile">
          <span>#</span>${m.tag.replace('#', '')}
        </button>
      </td>
      <td style="text-align: right;">
        <button class="small-action inspect-member-btn" data-tag="${m.tag}" type="button">Inspect Brawler Profile →</button>
      </td>
    `;
    tbody.append(tr);
  });

  tbody.querySelectorAll('.inspect-member-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const tag = e.currentTarget.dataset.tag;
      if (tag) {
        loadPlayer(tag);
        history.pushState(null, '', `/?player=${encodeURIComponent(tag)}`);
      }
    });
  });
}

function renderOverviewMetrics() {
  const metrics = [
    { label: 'AVERAGE POWER', value: state.analytics?.average_power ?? '—', desc: 'Roster combat level' },
    { label: 'MAX POWER 11', value: state.analytics?.power_11_count ?? 0, desc: 'Peak hypercharge ready' },
    { label: 'PRESTIGED BRAWLERS', value: state.analytics?.prestige_brawler_count ?? 0, desc: 'Permanent Brawler Prestige' },
    { label: 'TOTAL SHOWDOWN', value: format(state.analytics?.total_showdown_victories ?? 0), desc: 'Solo & duo survivor wins' },
  ];
  const holder = $('overview-metrics');
  if (!holder) return;
  holder.replaceChildren();
  metrics.forEach((metric) => {
    const card = document.createElement('article');
    card.className = 'metric-card';
    const label = document.createElement('span'); label.textContent = metric.label;
    const value = document.createElement('strong'); value.textContent = metric.value;
    const desc = document.createElement('small'); desc.textContent = metric.desc;
    card.append(label, value, desc);
    holder.append(card);
  });
}

function brawlerImage(brawler, thumbnail = false) {
  return thumbnail
    ? (brawler.id === 16000108
      ? '/assets/brawlers/thumbs/16000108.png?v=2'
      : `/assets/brawlers/thumbs/${brawler.id}.webp`)
    : `/assets/brawlers/${brawler.id}.png`;
}

function remoteBrawlerImage(brawler) {
  return `https://cdn.brawlify.com/brawlers/borders/${brawler.id}.png`;
}

function initials(name) { return String(name || '?').split(/\s+/).map((word) => word[0]).join('').slice(0, 2); }

function addImageWithFallback(holder, brawler, className) {
  const fallback = document.createElement('span');
  fallback.className = 'brawler-fallback';
  fallback.textContent = initials(brawler.name);
  const image = document.createElement('img');
  image.className = className;
  const primarySrc = (brawler.id === 16000108)
    ? brawlerImage(brawler, true)
    : `https://cdn.brawlify.com/brawlers/borders/${brawler.id}.png`;
  image.src = primarySrc;
  image.alt = `${brawler.name} official portrait`;
  image.loading = 'lazy';
  image.decoding = 'async';
  let step = 0;
  image.onerror = () => {
    step += 1;
    if (step === 1) {
      image.src = brawlerImage(brawler, true);
    } else if (step === 2) {
      image.src = `/assets/brawlers/${brawler.id}.png`;
    } else if (step === 3) {
      image.src = `https://cdn.brawlify.com/brawlers/model/${brawler.id}.png`;
    } else {
      image.remove();
      fallback.classList.add('visible');
    }
  };
  holder.append(fallback, image);
}

function renderQuickBrawlers() {
  const holder = $('quick-brawlers');
  if (!holder) return;
  holder.replaceChildren();
  [...state.ownedBrawlers].sort((a, b) => b.trophies - a.trophies).slice(0, 4).forEach((brawler) => {
    const link = document.createElement('a'); link.href = `/brawlers/${brawler.id}`; link.className = 'quick-brawler';
    const visual = document.createElement('div'); visual.className = 'quick-visual'; addImageWithFallback(visual, brawler, 'quick-image');
    const copy = document.createElement('div'); const name = document.createElement('strong'); name.textContent = brawler.name; const meta = document.createElement('span'); meta.textContent = `Power ${brawler.power} · ${format(brawler.trophies)} trophies`; copy.append(name, meta);
    const arrow = document.createElement('b'); arrow.textContent = '→'; link.append(visual, copy, arrow); holder.append(link);
  });
}

function compactEquipmentSummary(holder, brawler) {
  if (!brawler.owned) {
    const chip = document.createElement('span'); chip.className = 'equipment-chip locked'; chip.textContent = 'NOT IN ACCOUNT'; holder.append(chip); return;
  }
  const gadgetOwned = (brawler.gadgets || []).length > 0;
  const starPowerOwned = (brawler.star_powers || []).length > 0;
  const isHcOwned = hasHypercharge(brawler);
  const gadgetStatus = gadgetOwned ? (brawler.power >= 7 ? '✓' : '📦') : '—';
  const starPowerStatus = starPowerOwned ? (brawler.power >= 9 ? '✓' : '📦') : '—';
  const hcStatus = isHcOwned ? (brawler.power >= 11 ? '✓' : '📦') : '—';
  const buffieFlags = getBuffieFlags(brawler);

  [
    ['SP', starPowerStatus, starPowerOwned],
    ['Gadget', gadgetStatus, gadgetOwned],
    ['Gear', (brawler.gears || []).length ? `${brawler.gears.length}` : '—', (brawler.gears || []).length > 0],
    ['HC', hcStatus, isHcOwned],
  ].forEach(([label, sym, isOwned]) => {
    const chip = document.createElement('span');
    const isStored = isOwned && ((label === 'Gadget' && brawler.power < 7) || (label === 'SP' && brawler.power < 9) || (label === 'HC' && brawler.power < 11));
    chip.className = `equipment-chip ${isOwned ? (isStored ? 'stored' : 'owned') : 'missing'}`;
    chip.textContent = `${label} ${sym}`;
    holder.append(chip);
  });

  [
    ['Buffy G', buffieFlags.gadget],
    ['Buffy SP', buffieFlags.star_power],
    ['Buffy HC', buffieFlags.hypercharge],
  ].filter(([, owned]) => owned).forEach(([label]) => {
    const buffyChip = document.createElement('span');
    buffyChip.className = 'equipment-chip buffy-chip owned';
    buffyChip.textContent = `${label} ✓`;
    buffyChip.title = `${label} ownership flag returned by the player API`;
    holder.append(buffyChip);
  });
}

const ALL_GEARS = {
  'SPEED': { id: 62000000, name: 'SPEED', icon: '/assets/equipment/gears/62000000.png' },
  'HEALTH': { id: 62000001, name: 'HEALTH', icon: '/assets/equipment/gears/62000001.png' },
  'DAMAGE': { id: 62000002, name: 'DAMAGE', icon: '/assets/equipment/gears/62000002.png' },
  'VISION': { id: 62000003, name: 'VISION', icon: '/assets/equipment/gears/62000003.png' },
  'SHIELD': { id: 62000004, name: 'SHIELD', icon: '/assets/equipment/gears/62000004.png' },
  'GADGET COOLDOWN': { id: 62000017, name: 'GADGET COOLDOWN', icon: '/assets/equipment/gears/62000017.png' },
  'RELOAD SPEED': { id: 62000005, name: 'RELOAD SPEED', icon: '/assets/equipment/gears/62000005.png' },
  'SUPER CHARGE': { id: 62000006, name: 'SUPER CHARGE', icon: '/assets/equipment/gears/62000006.png' },
  'THICC HEAD': { id: 62000007, name: 'THICC HEAD', icon: '/assets/equipment/gears/62000007.png' },
  'TALK TO THE HAND': { id: 62000008, name: 'TALK TO THE HAND', icon: '/assets/equipment/gears/62000008.png' },
  'EXHAUSTING STORM': { id: 62000012, name: 'EXHAUSTING STORM', icon: '/assets/equipment/gears/62000012.png' },
  'STICKY OIL': { id: 62000013, name: 'STICKY OIL', icon: '/assets/equipment/gears/62000013.png' },
  'PET POWER': { id: 62000014, name: 'PET POWER', icon: '/assets/equipment/gears/62000014.png' },
  'QUADRUPLETS': { id: 62000015, name: 'QUADRUPLETS', icon: '/assets/equipment/gears/62000015.png' },
  'SUPER TURRET': { id: 62000016, name: 'SUPER TURRET', icon: '/assets/equipment/gears/62000016.png' },
};

const BASE_GEAR_NAMES = ['SPEED', 'HEALTH', 'DAMAGE', 'VISION', 'SHIELD', 'GADGET COOLDOWN'];

const SPECIAL_GEARS_BY_BRAWLER = {
  'AMBER': ['RELOAD SPEED', 'STICKY OIL'],
  'ASH': ['SUPER CHARGE'],
  'BELLE': ['RELOAD SPEED'],
  'BONNIE': ['SUPER CHARGE'],
  'EL PRIMO': ['SUPER CHARGE'],
  'ELPRIMO': ['SUPER CHARGE'],
  'EVE': ['RELOAD SPEED', 'QUADRUPLETS'],
  'GENE': ['TALK TO THE HAND'],
  'JACKY': ['SUPER CHARGE'],
  'JESSIE': ['PET POWER'],
  'LOLA': ['RELOAD SPEED'],
  'LOU': ['SUPER CHARGE'],
  'MR. P': ['PET POWER'],
  'MRP': ['PET POWER'],
  'NANI': ['SUPER CHARGE'],
  'OTIS': ['SUPER CHARGE'],
  'PAM': ['SUPER TURRET'],
  'PENNY': ['PET POWER'],
  'SANDY': ['EXHAUSTING STORM'],
  'SPROUT': ['SUPER CHARGE'],
  'TARA': ['PET POWER'],
  'TICK': ['THICC HEAD'],
};

function getBrawlerGearRoster(brawler) {
  const normName = (brawler.name || '').toUpperCase().trim();
  const special = SPECIAL_GEARS_BY_BRAWLER[normName] || [];
  const gearNames = [...BASE_GEAR_NAMES, ...special];

  const ownedGears = brawler.gears || [];
  ownedGears.forEach((g) => {
    const gNameUpper = (g.name || '').toUpperCase().trim();
    if (gNameUpper && !gearNames.includes(gNameUpper)) {
      gearNames.push(gNameUpper);
    }
  });

  return gearNames.map((name) => {
    if (ALL_GEARS[name]) return ALL_GEARS[name];
    const matched = ownedGears.find((g) => (g.name || '').toUpperCase().trim() === name);
    const id = matched?.id || 0;
    return {
      id,
      name,
      icon: `/assets/equipment/gears/${id}.png`,
    };
  });
}

function getBrawlerCatalogEquipment(brawlerId) {
  const bId = String(brawlerId);
  const allEquip = Object.entries(state.equipmentDb || {}).map(([key, item]) => ({
    name: item.name || key,
    ...item,
  }));
  const brawlerEquip = allEquip.filter((item) => String(item.brawler_id) === bId);
  let gadgets = brawlerEquip.filter((item) => item.type === 'gadget').sort((a, b) => a.id - b.id);
  let starPowers = brawlerEquip.filter((item) => item.type === 'star_power').sort((a, b) => a.id - b.id);

  const guide = state.guides?.[bId];
  if ((!gadgets || gadgets.length === 0) && guide?.gadgets) {
    gadgets = (guide.gadgets || []).map((g) => ({
      id: g.id,
      name: g.name,
      type: 'gadget',
      image_url: g.image_url || `/assets/equipment/gadgets/${g.id}.png`,
    }));
  }
  if ((!starPowers || starPowers.length === 0) && guide?.star_powers) {
    starPowers = (guide.star_powers || []).map((sp) => ({
      id: sp.id,
      name: sp.name,
      type: 'star_power',
      image_url: sp.image_url || `/assets/equipment/star-powers/${sp.id}.png`,
    }));
  }

  return { gadgets, starPowers };
}

function renderRosterEquipmentLab(holder, brawler) {
  holder.replaceChildren();
  const bId = String(brawler.id);
  const catalogEquip = getBrawlerCatalogEquipment(bId);

  // 1. Resolve Gadgets
  let gadgets = catalogEquip.gadgets;
  if (!gadgets || gadgets.length === 0) {
    gadgets = (brawler.gadgets || []).map((g) => ({
      id: g.id,
      name: g.name,
      image_url: `/assets/equipment/gadgets/${g.id}.png`,
    }));
  }
  while (gadgets.length < 2) {
    gadgets.push({ id: 0, name: 'Gadget', image_url: '/assets/section_gadget.png' });
  }

  // 2. Resolve Star Powers
  let starPowers = catalogEquip.starPowers;
  if (!starPowers || starPowers.length === 0) {
    starPowers = (brawler.star_powers || brawler.starPowers || []).map((sp) => ({
      id: sp.id,
      name: sp.name,
      image_url: `/assets/equipment/star-powers/${sp.id}.png`,
    }));
  }
  while (starPowers.length < 2) {
    starPowers.push({ id: 0, name: 'Star Power', image_url: '/assets/section_star_power.png' });
  }

  const ownedGadgetIds = new Set((brawler.gadgets || []).map((g) => Number(g.id)));
  const ownedGadgetNames = new Set((brawler.gadgets || []).map((g) => normalizeKey(g.name)));
  const ownedSpIds = new Set((brawler.star_powers || brawler.starPowers || []).map((sp) => Number(sp.id)));
  const ownedSpNames = new Set((brawler.star_powers || brawler.starPowers || []).map((sp) => normalizeKey(sp.name)));

  const buffiesReleased = isBuffieReleased(brawler);
  const hasGadgetBuffy = Boolean(brawler.owned) && hasBuffie(brawler, 'gadget');
  const hasSpBuffy = Boolean(brawler.owned) && hasBuffie(brawler, 'star_power');
  const hasHcBuffy = Boolean(brawler.owned) && hasBuffie(brawler, 'hypercharge');
  const isHcOwned = Boolean(brawler.owned) && hasHypercharge(brawler);
  const isHcActive = isHcOwned && ((brawler.power || 0) >= 11);

  const gadgetBuffieUrl = state.visualAssets?.brawlers?.[bId]?.buffies?.gadget?.local_url || `/assets/equipment/buffies/${bId}-gadget.png`;
  const spBuffieUrl = state.visualAssets?.brawlers?.[bId]?.buffies?.star_power?.local_url || `/assets/equipment/buffies/${bId}-star-power.png`;
  const hcBuffieUrl = state.visualAssets?.brawlers?.[bId]?.buffies?.hypercharge?.local_url || `/assets/equipment/buffies/${bId}-hypercharge.png`;
  const hcIconUrl = state.visualAssets?.brawlers?.[bId]?.hypercharge?.local_url || `/assets/equipment/hypercharges/${bId}.png`;

  // Row 1: Gadgets (centered, consistent capsule width)
  const rowGadgets = document.createElement('div');
  rowGadgets.className = 'lab-row lab-row-gadgets';
  gadgets.slice(0, 2).forEach((g) => {
    const isOwned = Boolean(brawler.owned) && (
      (g.id > 0 && ownedGadgetIds.has(Number(g.id))) ||
      (Boolean(g.name) && ownedGadgetNames.has(normalizeKey(g.name)))
    );
    // Condition 1 & 2:
    const isCapsuleActive = buffiesReleased
      ? (isOwned && hasGadgetBuffy)
      : isOwned;
    const capsule = document.createElement('div');
    capsule.className = `lab-capsule gadget-capsule ${isCapsuleActive ? 'owned' : 'unowned'}`;
    capsule.title = `${g.name || 'Gadget'} (${isOwned ? 'Owned' : 'Not owned'})`;

    const equipSlot = document.createElement('div');
    equipSlot.className = `equip-slot ${isOwned ? 'owned' : 'unowned'}`;
    const equipImg = document.createElement('img');
    equipImg.className = 'equip-icon';
    equipImg.src = g.image_url || `/assets/equipment/gadgets/${g.id}.png`;
    equipImg.alt = g.name || 'Gadget';
    equipImg.onerror = () => { equipImg.src = '/assets/section_gadget.png'; };
    equipSlot.append(equipImg);

    const buffieSlot = document.createElement('div');
    buffieSlot.className = `buffie-slot buffie-gadget ${hasGadgetBuffy ? 'owned' : 'unowned'}`;
    buffieSlot.title = `Gadget Buffie (${hasGadgetBuffy ? 'Owned' : 'Not owned'})`;
    const buffieImg = document.createElement('img');
    buffieImg.className = 'buffie-icon';
    buffieImg.src = gadgetBuffieUrl;
    buffieImg.alt = 'Gadget Buffie';
    buffieImg.onerror = () => { buffieImg.src = '/assets/buffies/generic.png'; };
    buffieSlot.append(buffieImg);

    capsule.append(equipSlot, buffieSlot);
    rowGadgets.append(capsule);
  });

  // Row 2: Star Powers & Hypercharge (centered, identical capsule width)
  const rowSpHc = document.createElement('div');
  rowSpHc.className = 'lab-row lab-row-sp-hc';
  starPowers.slice(0, 2).forEach((sp) => {
    const isOwned = Boolean(brawler.owned) && (
      (sp.id > 0 && ownedSpIds.has(Number(sp.id))) ||
      (Boolean(sp.name) && ownedSpNames.has(normalizeKey(sp.name)))
    );
    // Condition 1 & 2:
    const isCapsuleActive = buffiesReleased
      ? (isOwned && hasSpBuffy)
      : isOwned;
    const capsule = document.createElement('div');
    capsule.className = `lab-capsule sp-capsule ${isCapsuleActive ? 'owned' : 'unowned'}`;
    capsule.title = `${sp.name || 'Star Power'} (${isOwned ? 'Owned' : 'Not owned'})`;

    const equipSlot = document.createElement('div');
    equipSlot.className = `equip-slot ${isOwned ? 'owned' : 'unowned'}`;
    const equipImg = document.createElement('img');
    equipImg.className = 'equip-icon';
    equipImg.src = sp.image_url || `/assets/equipment/star-powers/${sp.id}.png`;
    equipImg.alt = sp.name || 'Star Power';
    equipImg.onerror = () => { equipImg.src = '/assets/section_star_power.png'; };
    equipSlot.append(equipImg);

    const buffieSlot = document.createElement('div');
    buffieSlot.className = `buffie-slot buffie-sp ${hasSpBuffy ? 'owned' : 'unowned'}`;
    buffieSlot.title = `Star Power Buffie (${hasSpBuffy ? 'Owned' : 'Not owned'})`;
    const buffieImg = document.createElement('img');
    buffieImg.className = 'buffie-icon';
    buffieImg.src = spBuffieUrl;
    buffieImg.alt = 'Star Power Buffie';
    buffieImg.onerror = () => { buffieImg.src = '/assets/buffies/generic.png'; };
    buffieSlot.append(buffieImg);

    capsule.append(equipSlot, buffieSlot);
    rowSpHc.append(capsule);
  });

  // Hypercharge Capsule
  // Condition 1 & 2 (if stored, don't do it!):
  const isCapsuleActive = buffiesReleased
    ? (isHcActive && hasHcBuffy)
    : isHcActive;
  const hcCapsule = document.createElement('div');
  hcCapsule.className = `lab-capsule hc-capsule ${isCapsuleActive ? 'owned' : 'unowned'}`;
  hcCapsule.title = `Hypercharge (${isHcActive ? 'Active' : isHcOwned ? 'Stored (Lvl 11 Required)' : 'Not owned'})`;

  const hcSlot = document.createElement('div');
  hcSlot.className = `equip-slot ${isHcOwned ? 'owned' : 'unowned'}`;
  const hcImg = document.createElement('img');
  hcImg.className = 'equip-icon hc-icon';
  hcImg.src = hcIconUrl;
  hcImg.alt = 'Hypercharge';
  hcImg.onerror = () => { hcImg.src = '/assets/section_hypercharge.png'; };
  hcSlot.append(hcImg);

  const hcBuffieSlot = document.createElement('div');
  hcBuffieSlot.className = `buffie-slot buffie-hc ${hasHcBuffy ? 'owned' : 'unowned'}`;
  hcBuffieSlot.title = `Hypercharge Buffie (${hasHcBuffy ? 'Owned' : 'Not owned'})`;
  const hcBuffieImg = document.createElement('img');
  hcBuffieImg.className = 'buffie-icon';
  hcBuffieImg.src = hcBuffieUrl;
  hcBuffieImg.alt = 'Hypercharge Buffie';
  hcBuffieImg.onerror = () => { hcBuffieImg.src = '/assets/buffies/generic.png'; };
  hcBuffieSlot.append(hcBuffieImg);

  hcCapsule.append(hcSlot, hcBuffieSlot);
  rowSpHc.append(hcCapsule);

  // Row 3: Gears Strip (supporting 6 to 8 gears per brawler)
  const rowGears = document.createElement('div');
  rowGears.className = 'lab-row lab-row-gears';
  const gearsPill = document.createElement('div');
  gearsPill.className = 'gears-strip-pill';

  const brawlerGears = getBrawlerGearRoster(brawler);
  const ownedGearIds = new Set((brawler.gears || []).map((g) => Number(g.id)));
  const ownedGearNames = new Set((brawler.gears || []).map((g) => normalizeKey(g.name)));

  brawlerGears.forEach((gear) => {
    const isOwned = Boolean(brawler.owned) && (ownedGearIds.has(gear.id) || ownedGearNames.has(normalizeKey(gear.name)));
    const gearSlot = document.createElement('div');
    gearSlot.className = `gear-slot ${isOwned ? 'owned' : 'unowned'}`;
    gearSlot.title = `${gear.name} Gear (${isOwned ? 'Owned' : 'Not owned'})`;

    const gearImg = document.createElement('img');
    gearImg.className = 'gear-icon';
    gearImg.src = gear.icon;
    gearImg.alt = gear.name;
    gearImg.onerror = () => { gearImg.src = '/assets/section_gear.png'; };
    gearSlot.append(gearImg);
    gearsPill.append(gearSlot);
  });
  rowGears.append(gearsPill);

  holder.append(rowGadgets, rowSpHc, rowGears);
}

function cardFor(brawler) {
  const rarityLabel = getBrawlerRarity(brawler) || 'Common';
  const rarityClass = rarityLabel.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const link = document.createElement('a'); link.className = `brawler-card rarity-${rarityClass || 'common'}`; link.href = `/brawlers/${brawler.id}`;
  const visual = document.createElement('div'); visual.className = 'brawler-visual';
  const frameBox = document.createElement('div'); frameBox.className = 'brawler-frame-box';
  addImageWithFallback(frameBox, brawler, 'brawler-image');
  visual.append(frameBox);
  const badge = document.createElement('span'); badge.className = `power-badge ${brawler.owned ? `power-${brawler.power}` : 'locked'} rarity-${rarityClass || 'common'}`; badge.textContent = brawler.owned ? `LVL${brawler.power}` : 'LOCKED'; visual.append(badge);
  if (brawler.owned) {
    const prestige = getPrestigeState(brawler);
    const emblem = document.createElement('span'); emblem.className = 'prestige-card-emblem'; emblem.title = `${brawler.name}: ${prestige.label}`;
    const emblemImage = document.createElement('img'); emblemImage.alt = `${brawler.name} ${prestige.label} emblem`; applyPrestigeImage(emblemImage, brawler);
    emblem.append(emblemImage); visual.append(emblem);

    const trophyEmblem = document.createElement('span'); trophyEmblem.className = 'trophy-card-emblem'; trophyEmblem.title = `${brawler.name}: ${format(brawler.trophies)} Trophies`;
    trophyEmblem.innerHTML = `<div class="trophy-emblem-box"><span class="trophy-emblem-bg" aria-hidden="true"><svg class="trophy-emblem-svg" viewBox="0 0 24 24"><path d="M19 5h-2V3H7v2H5c-1.1 0-2 .9-2 2v1c0 2.55 1.92 4.63 4.39 4.94A5.01 5.01 0 0 0 11 15.9V19H7v2h10v-2h-4v-3.1a5.01 5.01 0 0 0 3.61-2.96C19.08 12.63 21 10.55 21 8V7c0-1.1-.9-2-2-2zM5 8V7h2v3.82C5.84 10.4 5 9.3 5 8zm14 0c0 1.3-.84 2.4-2 2.82V7h2v1z"/></svg></span><div class="trophy-emblem-content"><span class="trophy-emblem-val">${format(brawler.trophies)}</span><span class="trophy-emblem-sub">TROPHIES</span></div></div>`;
    visual.append(trophyEmblem);
  }
  const copy = document.createElement('div'); copy.className = 'brawler-card-copy';
  const top = document.createElement('div'); top.className = 'brawler-name-row'; 
  const name = document.createElement('strong'); name.textContent = brawler.name; name.title = brawler.name; 
  const rarityTag = document.createElement('span'); rarityTag.className = `brawler-rarity-tag rarity-${rarityClass || 'common'}`; rarityTag.textContent = rarityLabel;
  top.append(name, rarityTag);
  const equipment = document.createElement('div'); equipment.className = 'equipment-row equipment-lab-wrap'; renderRosterEquipmentLab(equipment, brawler);
  const open = document.createElement('div'); open.className = 'open-guide'; open.innerHTML = '<span>VIEW GUIDE</span><b>→</b>';
  copy.append(top, equipment, open); link.append(visual, copy); return link;
}

let brawlerNameFitFrame = 0;

function fitBrawlerNames(root = document) {
  cancelAnimationFrame(brawlerNameFitFrame);
  brawlerNameFitFrame = requestAnimationFrame(() => {
    root.querySelectorAll('.brawler-name-row strong').forEach((label) => {
      label.style.fontSize = '';
      const baseSize = Number.parseFloat(getComputedStyle(label).fontSize) || 18;
      if (label.scrollWidth <= label.clientWidth) return;

      for (let reduction = 5; reduction <= 65; reduction += 5) {
        const size = baseSize * (1 - (reduction / 100));
        label.style.fontSize = `${size}px`;
        if (label.scrollWidth <= label.clientWidth) break;
      }
    });
  });
}

function scheduleBrawlerNameFit(root = document) {
  fitBrawlerNames(root);
  window.setTimeout(() => fitBrawlerNames(root), 150);
  if (document.fonts?.ready) {
    document.fonts.ready.then(() => fitBrawlerNames(root));
  }
}

const BRAWLER_CLASSES_BY_NAME = {
  "PENNY": "Controller", "TARA": "Damage Dealer", "FRANK": "Tank", "GENE": "Controller", "TICK": "Artillery", "LEON": "Assassin", "ROSA": "Tank", "CARL": "Damage Dealer", "BIBI": "Tank", "8-BIT": "Damage Dealer", "SANDY": "Controller", "BEA": "Marksman", "EMZ": "Controller", "MR. P": "Controller", "MAX": "Support", "JACKY": "Tank", "GALE": "Controller", "NANI": "Marksman", "SPROUT": "Artillery", "COLETTE": "Damage Dealer", "AMBER": "Controller", "LOU": "Controller", "SURGE": "Damage Dealer", "SHELLY": "Damage Dealer", "COLT": "Damage Dealer", "BULL": "Tank", "BROCK": "Marksman", "RICO": "Damage Dealer", "SPIKE": "Damage Dealer", "BARLEY": "Artillery", "JESSIE": "Controller", "NITA": "Damage Dealer", "DYNAMIKE": "Artillery", "EL PRIMO": "Tank", "MORTIS": "Assassin", "CROW": "Assassin", "POCO": "Support", "BO": "Controller", "PIPER": "Marksman", "PAM": "Support", "DARRYL": "Tank", "BYRON": "Support", "EDGAR": "Assassin", "RUFFS": "Support", "STU": "Assassin", "BELLE": "Marksman", "SQUEAK": "Controller", "GROM": "Artillery", "BUZZ": "Assassin", "GRIFF": "Controller", "ASH": "Tank", "MEG": "Tank", "LOLA": "Damage Dealer", "FANG": "Assassin", "EVE": "Damage Dealer", "JANET": "Marksman", "BONNIE": "Marksman", "OTIS": "Controller", "SAM": "Tank", "GUS": "Support", "BUSTER": "Tank", "CHESTER": "Damage Dealer", "GRAY": "Support", "MANDY": "Marksman", "R-T": "Damage Dealer", "WILLOW": "Controller", "MAISIE": "Marksman", "HANK": "Tank", "CORDELIUS": "Assassin", "DOUG": "Support", "PEARL": "Damage Dealer", "CHUCK": "Damage Dealer", "CHARLIE": "Controller", "MICO": "Assassin", "KIT": "Support", "LARRY & LAWRIE": "Artillery", "MELODIE": "Assassin", "ANGELO": "Marksman", "DRACO": "Tank", "LILY": "Assassin", "BERRY": "Support", "CLANCY": "Damage Dealer", "MOE": "Damage Dealer", "KENJI": "Assassin", "SHADE": "Assassin", "JUJU": "Artillery", "MEEPLE": "Controller", "OLLIE": "Assassin", "LUMI": "Support", "FINX": "Controller", "JAE-YONG": "Assassin", "KAZE": "Assassin", "ALLI": "Tank", "TRUNK": "Tank", "MINA": "Marksman", "ZIGGY": "Controller", "PIERCE": "Marksman", "GIGI": "Support", "GLOWY": "Controller", "SIRIUS": "Damage Dealer", "NAJIA": "Assassin", "DAMIAN": "Damage Dealer", "STARR NOVA": "Controller", "BOLT": "Marksman", "NORI": "Assassin", "WENDY": "Damage Dealer"
};

const BRAWLER_RARITIES_BY_NAME = {
  "SHELLY": "Common", "COLT": "Rare", "BULL": "Rare", "BROCK": "Rare", "RICO": "Super Rare", "SPIKE": "Legendary", "BARLEY": "Rare", "JESSIE": "Super Rare", "NITA": "Rare", "DYNAMIKE": "Super Rare", "EL PRIMO": "Rare", "MORTIS": "Mythic", "CROW": "Legendary", "POCO": "Rare", "BO": "Epic", "PIPER": "Epic", "PAM": "Epic", "TARA": "Mythic", "DARRYL": "Super Rare", "PENNY": "Super Rare", "FRANK": "Epic", "GENE": "Mythic", "TICK": "Super Rare", "LEON": "Legendary", "ROSA": "Rare", "CARL": "Super Rare", "BIBI": "Epic", "8-BIT": "Super Rare", "SANDY": "Legendary", "BEA": "Epic", "EMZ": "Epic", "MR. P": "Mythic", "MAX": "Mythic", "JACKY": "Super Rare", "GALE": "Epic", "NANI": "Epic", "SPROUT": "Mythic", "SURGE": "Legendary", "COLETTE": "Epic", "AMBER": "Legendary", "LOU": "Mythic", "BYRON": "Mythic", "EDGAR": "Epic", "RUFFS": "Mythic", "STU": "Epic", "BELLE": "Epic", "SQUEAK": "Mythic", "GROM": "Epic", "BUZZ": "Mythic", "GRIFF": "Epic", "ASH": "Epic", "MEG": "Legendary", "LOLA": "Epic", "FANG": "Mythic", "EVE": "Mythic", "JANET": "Mythic", "BONNIE": "Epic", "OTIS": "Mythic", "SAM": "Epic", "GUS": "Super Rare", "BUSTER": "Mythic", "CHESTER": "Legendary", "GRAY": "Mythic", "MANDY": "Epic", "R-T": "Mythic", "WILLOW": "Mythic", "MAISIE": "Epic", "HANK": "Epic", "CORDELIUS": "Legendary", "DOUG": "Mythic", "PEARL": "Epic", "CHUCK": "Mythic", "CHARLIE": "Mythic", "MICO": "Mythic", "KIT": "Legendary", "LARRY & LAWRIE": "Epic", "MELODIE": "Mythic", "ANGELO": "Epic", "DRACO": "Legendary", "LILY": "Mythic", "BERRY": "Epic", "CLANCY": "Mythic", "MOE": "Mythic", "KENJI": "Legendary", "SHADE": "Epic", "JUJU": "Mythic", "MEEPLE": "Epic", "OLLIE": "Mythic", "LUMI": "Mythic", "FINX": "Mythic", "JAE-YONG": "Mythic", "KAZE": "Ultra Legendary", "ALLI": "Mythic", "TRUNK": "Epic", "MINA": "Mythic", "ZIGGY": "Mythic", "PIERCE": "Legendary", "GIGI": "Mythic", "GLOWY": "Mythic", "SIRIUS": "Ultra Legendary", "NAJIA": "Mythic", "DAMIAN": "Mythic", "STARR NOVA": "Mythic", "BOLT": "Epic", "NORI": "Legendary", "WENDY": "Legendary"
};

function getBrawlerClass(brawler) {
  if (!brawler) return '';
  if (brawler.class) return brawler.class;
  const bId = String(brawler.id || '');
  const guide = state.guides?.[bId];
  if (guide?.class) return guide.class;
  const cat = (state.catalog || []).find((c) => String(c.id) === bId || (c.name || '').toUpperCase() === (brawler.name || '').toUpperCase());
  if (cat?.class) return cat.class;
  return BRAWLER_CLASSES_BY_NAME[(brawler.name || '').toUpperCase()] || '';
}

function getBrawlerRarity(brawler) {
  if (!brawler) return '';
  if (brawler.rarity) return brawler.rarity;
  const bId = String(brawler.id || '');
  const cat = (state.catalog || []).find((c) => String(c.id) === bId || (c.name || '').toUpperCase() === (brawler.name || '').toUpperCase());
  if (cat?.rarity) return cat.rarity;
  return BRAWLER_RARITIES_BY_NAME[(brawler.name || '').toUpperCase()] || 'Common';
}

function isHyperchargeReleasedForBrawler(brawler) {
  if (!brawler) return false;
  const bId = String(brawler.id || '');
  const visual = state.visualAssets?.brawlers?.[bId]?.hypercharge;
  if (visual && visual.released === false) return false;
  const guide = state.guides?.[bId];
  if (guide?.hypercharge && (guide.hypercharge.released === false || guide.hypercharge.name?.toLowerCase() === 'unreleased')) {
    return false;
  }
  return true;
}

function matchesEquipment(brawler, filter = state.equipment) {
  if (!brawler) return false;
  if (!filter || filter === 'all') return true;

  const isOwned = Boolean(brawler.owned);

  // CLASS (evaluates catalog: matches both owned and unowned brawlers)
  const bClass = (getBrawlerClass(brawler) || '').toLowerCase().trim();
  switch (filter) {
    case 'class_damage_dealer':
      return bClass === 'damage dealer';
    case 'class_assassin':
      return bClass === 'assassin';
    case 'class_marksman':
      return bClass === 'marksman';
    case 'class_artillery':
      return bClass === 'artillery';
    case 'class_tank':
      return bClass === 'tank';
    case 'class_support':
      return bClass === 'support';
    case 'class_controller':
      return bClass === 'controller';
  }

  // RARITY (evaluates catalog: matches both owned and unowned brawlers)
  const bRarity = (getBrawlerRarity(brawler) || '').toLowerCase().trim();
  switch (filter) {
    case 'rarity_rare':
      return bRarity === 'rare';
    case 'rarity_super_rare':
      return bRarity === 'super rare';
    case 'rarity_epic':
      return bRarity === 'epic';
    case 'rarity_mythic':
      return bRarity === 'mythic';
    case 'rarity_legendary':
      return bRarity.includes('legendary');
  }

  // BUFFIE AVAILABILITY (evaluates catalog: matches brawlers with buffies released)
  if (filter === 'buffies_available') {
    return isBuffieReleased(brawler);
  }
  if (filter === 'buffies_not_available') {
    return !isBuffieReleased(brawler);
  }

  // HYPERCHARGE NOT AVAILABLE (evaluates catalog)
  if (filter === 'hc_not_available') {
    return !isHyperchargeReleasedForBrawler(brawler);
  }

  // Progression & ownership filters require the player to own the brawler
  if (!isOwned) return false;

  const gadgetCount = (brawler.gadgets || []).length;
  const spCount = (brawler.star_powers || brawler.starPowers || []).length;
  const gearCount = (brawler.gears || []).length;
  const isHcOwned = hasHypercharge(brawler);
  const hasGadgetBuffy = hasBuffie(brawler, 'gadget');
  const hasSpBuffy = hasBuffie(brawler, 'star_power');
  const hasHcBuffy = hasBuffie(brawler, 'hypercharge');
  const buffieCount = (hasGadgetBuffy ? 1 : 0) + (hasSpBuffy ? 1 : 0) + (hasHcBuffy ? 1 : 0);
  const hasAnyBuffy = buffieCount > 0;

  const trophies = brawler.trophies || 0;
  const brawlerPrestige = getPrestigeLevel(brawler);

  switch (filter) {
    // GADGETS
    case 'gadgets_0':
    case 'no_gadget':
      return gadgetCount === 0;
    case 'gadgets_1':
    case 'has_gadget_1':
      return gadgetCount === 1;
    case 'gadgets_2':
    case 'has_gadget_2':
      return gadgetCount >= 2;
    case 'has_gadget_1_or_more':
    case 'has_gadget':
      return gadgetCount >= 1;

    // STAR POWERS
    case 'sp_0':
    case 'no_sp':
      return spCount === 0;
    case 'sp_1':
    case 'has_sp_1':
      return spCount === 1;
    case 'sp_2':
    case 'has_sp_2':
      return spCount >= 2;
    case 'has_sp_1_or_more':
    case 'has_sp':
      return spCount >= 1;

    // GEARS
    case 'gears_0':
    case 'no_gear':
      return gearCount === 0;
    case 'gears_1':
    case 'has_gear_1':
    case 'has_1_gear':
      return gearCount === 1;
    case 'gears_2_plus':
    case 'has_gears_2_or_more':
    case 'has_2_gears':
    case 'has_gear_1_or_more':
      return gearCount >= 2;
    case 'all_gears':
      return gearCount >= getBrawlerGearRoster(brawler).length;

    // HYPERCHARGE
    case 'hc_available_unowned':
      return isHyperchargeReleasedForBrawler(brawler) && !isHcOwned;
    case 'hc_stored':
    case 'stored_hypercharge':
      return isHcOwned && brawler.power < 11;
    case 'hc_active':
    case 'active_hypercharge':
      return isHcOwned && brawler.power === 11;
    case 'has_hypercharge':
      return isHcOwned;
    case 'no_hypercharge':
      return !isHcOwned;

    // BUFFIE OWNERSHIP
    case 'buffies_owned_0':
      return buffieCount === 0;
    case 'buffies_owned_at_least_1':
    case 'has_buffies':
      return buffieCount >= 1;
    case 'buffies_owned_at_least_2':
      return buffieCount >= 2;
    case 'buffies_owned_3':
      return buffieCount === 3;

    // BUFFIE COMBINATIONS
    case 'buffie_combo_0':
      return isBuffieReleased(brawler) && buffieCount === 0;
    case 'buffie_combo_gadget':
      return hasGadgetBuffy && !hasSpBuffy && !hasHcBuffy;
    case 'buffie_combo_sp':
      return !hasGadgetBuffy && hasSpBuffy && !hasHcBuffy;
    case 'buffie_combo_hc':
      return !hasGadgetBuffy && !hasSpBuffy && hasHcBuffy;
    case 'buffie_combo_gadget_sp':
      return hasGadgetBuffy && hasSpBuffy && !hasHcBuffy;
    case 'buffie_combo_gadget_hc':
      return hasGadgetBuffy && !hasSpBuffy && hasHcBuffy;
    case 'buffie_combo_sp_hc':
      return !hasGadgetBuffy && hasSpBuffy && hasHcBuffy;
    case 'buffie_combo_complete':
      return hasGadgetBuffy && hasSpBuffy && hasHcBuffy;

    // INDIVIDUAL BUFFIES
    case 'buffie_ind_gadget_owned':
    case 'has_buffies_gadget':
      return hasGadgetBuffy;
    case 'buffie_ind_gadget_unowned':
      return isBuffieReleased(brawler) && !hasGadgetBuffy;
    case 'buffie_ind_sp_owned':
    case 'has_buffies_sp':
      return hasSpBuffy;
    case 'buffie_ind_sp_unowned':
      return isBuffieReleased(brawler) && !hasSpBuffy;
    case 'buffie_ind_hc_owned':
    case 'has_buffies_hc':
      return hasHcBuffy;
    case 'buffie_ind_hc_unowned':
      return isBuffieReleased(brawler) && !hasHcBuffy;

    // TROPHIES
    case 'trophies_0_249':
      return trophies >= 0 && trophies <= 249;
    case 'trophies_250_499':
      return trophies >= 250 && trophies <= 499;
    case 'trophies_500_749':
      return trophies >= 500 && trophies <= 749;
    case 'trophies_750_999':
      return trophies >= 750 && trophies <= 999;
    case 'trophies_1000_plus':
      return trophies >= 1000;

    // PRESTIGE
    case 'prestige_0':
      return brawlerPrestige === 0;
    case 'prestige_1':
      return brawlerPrestige === 1;
    case 'prestige_2':
      return brawlerPrestige === 2;
    case 'prestige_3_plus':
      return brawlerPrestige >= 3;

    // MAX OUT
    case 'max_out':
      return brawler.power === 11 && gadgetCount >= 1 && spCount >= 1 && gearCount >= 2 && isHcOwned && hasGadgetBuffy && hasSpBuffy && hasHcBuffy;

    default:
      return true;
  }
}

function renderBrawlers() {
  if (!state.brawlers || state.brawlers.length === 0) {
    state.brawlers = mergeCatalog(state.ownedBrawlers);
  }
  const searchInput = $('brawler-search');
  const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
  const sort = $('brawler-sort')?.value || 'power_asc';
  const equipmentFilter = $('equipment-filter')?.value || state.equipment || 'all';
  state.equipment = equipmentFilter;

  let brawlers = (state.brawlers || []).filter((brawler) => {
    const matchesQuery = !query || (brawler.name && brawler.name.toLowerCase().includes(query));
    let matchesLevel = true;
    if (state.level && state.level !== 'all') {
      const targetLevel = Number(state.level);
      matchesLevel = brawler.owned && (brawler.power === targetLevel);
    }
    const matchesEquip = matchesEquipment(brawler, equipmentFilter);

    return matchesQuery && matchesLevel && matchesEquip;
  });

  brawlers.sort((a, b) => {
    if (sort === 'name') return (a.name || '').localeCompare(b.name || '');
    if (sort === 'trophies') return (b.trophies || 0) - (a.trophies || 0) || (a.name || '').localeCompare(b.name || '');
    if (sort === 'prestige_desc') return getPrestigeLevel(b) - getPrestigeLevel(a) || (b.trophies || 0) - (a.trophies || 0) || (a.name || '').localeCompare(b.name || '');
    if (sort === 'prestige_asc') return getPrestigeLevel(a) - getPrestigeLevel(b) || (a.trophies || 0) - (b.trophies || 0) || (a.name || '').localeCompare(b.name || '');
    if (sort === 'prestige_next') {
      if (a.owned !== b.owned) return a.owned ? -1 : 1;
      return getPrestigeState(a).remaining - getPrestigeState(b).remaining || (b.trophies || 0) - (a.trophies || 0);
    }
    if (sort === 'power_desc') {
      if (a.owned !== b.owned) return a.owned ? -1 : 1;
      return (b.power || 0) - (a.power || 0) || (b.trophies || 0) - (a.trophies || 0) || (a.name || '').localeCompare(b.name || '');
    }
    if (sort === 'power_asc') {
      if (a.owned !== b.owned) return a.owned ? -1 : 1;
      return (a.power || 0) - (b.power || 0) || (b.trophies || 0) - (a.trophies || 0) || (a.name || '').localeCompare(b.name || '');
    }
    return 0;
  });

  const holder = $('brawler-grid');
  if (holder) {
    holder.replaceChildren();
    holder.classList.toggle('table-mode', state.view === 'table');
    brawlers.forEach((brawler) => holder.append(cardFor(brawler)));
    scheduleBrawlerNameFit(holder);
  }
  const empty = $('brawler-empty');
  if (empty) empty.classList.toggle('hidden', brawlers.length > 0);
}

function prioritySteps(brawler, guide = {}) {
  const build = guide.recommended_build || {};
  if (!brawler.owned) {
    return [
      { title: `Unlock ${brawler.name}`, reason: 'This brawler is in the catalog but is not present in the loaded player account.', tag: 'LOCKED' },
      { title: build.gadget ? `Plan for ${build.gadget}` : 'Plan for Primary Gadget', reason: 'The curated guide marks this as the general-purpose first Gadget choice.', tag: 'FUTURE BUILD' },
      { title: build.star_power ? `Plan for ${build.star_power}` : 'Plan for Primary Star Power', reason: 'Use this as the default Star Power, then adapt for the map and mode.', tag: 'FUTURE BUILD' },
      { title: build.gears?.length ? `Plan for ${build.gears.join(' + ')}` : 'Plan for Recommended Gears', reason: 'These are the guide’s general-purpose Gear choices for standard map pools.', tag: 'FUTURE BUILD' }
    ];
  }

  const steps = [];
  if (brawler.power < 11) {
    steps.push({
      title: `Reach Power Level ${brawler.power + 1}`,
      reason: `Upgrade from Power ${brawler.power} to ${brawler.power + 1} to increase base health, attack, and Super damage scaling.`,
      tag: 'NEXT LEVEL'
    });
  }

  if (!brawler.gadgets.length) {
    steps.push({
      title: brawler.power < 7 ? 'Reach Power Level 7 for Gadgets' : (build.gadget ? `Unlock ${build.gadget}` : 'Unlock a Gadget'),
      reason: brawler.power < 7
        ? 'Gadgets and an owned Gadget Buffy remain stored until this brawler reaches Power Level 7.'
        : (build.gadget ? `The curated guide recommends ${build.gadget} as the primary active utility tool.` : 'No owned Gadget is recorded in the player response.'),
      tag: brawler.power < 7 ? 'LEVEL 7' : 'LOADOUT GAP'
    });
  } else if (brawler.gadgets.length < (guide.gadgets || []).length) {
    const missingGadget = (guide.gadgets || []).find(g => !brawler.gadgets.some(bg => bg.name?.toLowerCase() === g.name?.toLowerCase() || bg.id === g.id));
    if (missingGadget) {
      steps.push({
        title: `Consider Alternate Gadget (${missingGadget.name})`,
        reason: 'Unlocking alternate gadgets gives situational flexibility across specialized maps.',
        tag: 'ADAPT'
      });
    }
  }

  if (!brawler.star_powers.length) {
    steps.push({
      title: brawler.power < 9 ? 'Reach Power Level 9 for Star Powers' : (build.star_power ? `Unlock ${build.star_power}` : 'Unlock a Star Power'),
      reason: brawler.power < 9
        ? 'Star Powers and an owned Star Power Buffy remain stored until this brawler reaches Power Level 9.'
        : (build.star_power ? `The curated guide recommends ${build.star_power} as the default permanent passive bonus.` : 'No owned Star Power is recorded in the player response.'),
      tag: brawler.power < 9 ? 'LEVEL 9' : 'LOADOUT GAP'
    });
  } else if (brawler.star_powers.length < (guide.star_powers || []).length) {
    const missingSP = (guide.star_powers || []).find(s => !brawler.star_powers.some(bs => bs.name?.toLowerCase() === s.name?.toLowerCase() || bs.id === s.id));
    if (missingSP) {
      steps.push({
        title: `Consider Alternate Star Power (${missingSP.name})`,
        reason: 'Having both Star Powers enables counter-picks depending on map geometry.',
        tag: 'ADAPT'
      });
    }
  }

  if (!brawler.gears.length) {
    steps.push({
      title: build.gears?.length ? `Build Gear: ${build.gears[0]}` : 'Equip First Gear',
      reason: build.gears?.length ? `Recommended starting gear from the curated general-purpose build.` : 'No equipped Gear recorded in the player profile.',
      tag: 'LOADOUT GAP'
    });
  } else if (brawler.gears.length === 1 && brawler.power >= 10) {
    steps.push({
      title: build.gears?.length > 1 ? `Build Second Gear: ${build.gears[1]}` : 'Equip Second Gear Slot',
      reason: 'At Power 10+, the second gear slot is unlocked for dual stat amplification.',
      tag: 'LOADOUT GAP'
    });
  }

  const hcReleased = guide.hypercharge && guide.hypercharge.released !== false && guide.hypercharge.name?.toLowerCase() !== 'unreleased';
  const hcOwned = hasHypercharge(brawler, guide);
  if (hcOwned && brawler.power < 11) {
    steps.push({
      title: 'Hypercharge Stored',
      reason: 'This Hypercharge is owned, but it cannot be used until the brawler reaches Power Level 11.',
      tag: 'LEVEL 11'
    });
  } else if (hcReleased && !hcOwned && brawler.power >= 11) {
    steps.push({
      title: `Unlock ${guide.hypercharge.name}`,
      reason: 'The Hypercharge is released and this brawler is eligible at Power Level 11, but the player response does not list it as owned.',
      tag: 'LOADOUT GAP'
    });
  }

  if (brawler.power === 11 && brawler.gadgets.length && brawler.star_powers.length && brawler.gears.length >= 1) {
    steps.push({
      title: 'Core Loadout Ready',
      reason: 'Primary build is fully online with recommended Gadget, Star Power, and Gears.',
      tag: 'READY'
    });
    steps.push({
      title: 'Ranked & Competitive Tournament Viable',
      reason: 'Meets full Power 11 requirements for draft mode and high-elo competitive matches.',
      tag: 'RANKED'
    });
    if (hcReleased) {
      steps.push({
        title: `Hypercharge Specification (${guide.hypercharge.name})`,
        reason: 'Review the official Hypercharge ability below for combat stat boosts and Super enhancement.',
        tag: 'OFFICIAL SPEC'
      });
    }
  }

  if (steps.length < 3) {
    steps.push({
      title: 'Refine Mode Strategy',
      reason: 'Review team synergies and master range spacing in top recommended modes.',
      tag: 'STRATEGY'
    });
  }

  return steps.slice(0, 4);
}

function renderGuideProfile(guide, brawler) {
  const panel = $('guide-profile-panel');
  if (!panel) return;
  const hasProfile = Array.isArray(guide.max_stats) && guide.max_stats.length > 0;
  panel.classList.toggle('hidden', !hasProfile);
  if (!hasProfile) return;

  // Stats will be rendered by renderPowerLadder after it determines the default level.
  // But if guide-only (no brawler context), render at max (level 11) right away.
  renderCombatStats(guide.max_stats, 11);

  const summaryIcon = document.querySelector('.hc-summary-emblem .hyper-icon-img');
  if (summaryIcon) {
    summaryIcon.alt = `${brawler?.name || 'Brawler'} Hypercharge`;
    setAssetImageSources(summaryIcon, getHyperchargeImageSources(brawler), 'HC');
  }

  if (!guide.hypercharge || guide.hypercharge.released === false || guide.hypercharge.name?.toLowerCase() === 'unreleased') {
    setText('hypercharge-name', 'Not Yet Released');
    setText('hypercharge-description', 'Supercell has not yet introduced an official Hypercharge for this brawler.');
  } else {
    setText('hypercharge-name', guide.hypercharge.name);
    setText('hypercharge-description', guide.hypercharge.description || 'Hypercharge ability for this brawler.');
  }

  const buildHolder = $('recommended-build');
  if (buildHolder) {
    buildHolder.replaceChildren();
    const build = guide.recommended_build || {};
    const gadget = (guide.gadgets || []).find((item) => normalizeKey(item.name) === normalizeKey(build.gadget)) || { name: build.gadget };
    const starPower = (guide.star_powers || []).find((item) => normalizeKey(item.name) === normalizeKey(build.star_power)) || { name: build.star_power };

    const items = [
      { label: 'Gadget', value: build.gadget, badgeClass: 'build-gadget', icons: [{ item: gadget, type: 'gadget' }] },
      { label: 'Star Power', value: build.star_power, badgeClass: 'build-star-power', icons: [{ item: starPower, type: 'star_power' }] },
      { label: 'Gears', value: build.gears?.join(' + '), badgeClass: 'build-gear', icons: (build.gears || []).map((name) => ({ item: { name }, type: 'gear' })) }
    ];

    items.forEach(({ label, value, badgeClass, icons }) => {
      if (!value) return;
      const row = document.createElement('div');
      row.className = `build-spec-row ${badgeClass}`;

      const labelWrap = document.createElement('div');
      labelWrap.className = 'build-spec-label';
      const iconsWrap = document.createElement('span');
      iconsWrap.className = 'build-spec-icons';
      icons.forEach(({ item, type }) => {
        const iconWrap = document.createElement('span');
        iconWrap.className = 'build-spec-icon';
        const fallback = document.createElement('span');
        fallback.className = 'build-spec-icon-fallback';
        fallback.textContent = type === 'gadget' ? 'G' : type === 'star_power' ? '★' : '◆';
        const iconUrl = getEquipmentImageUrl(item, type, brawler);
        if (iconUrl) {
          const image = document.createElement('img');
          image.alt = `${item.name} icon`;
          image.loading = 'lazy';
          const categoryFallback = type === 'gadget'
            ? '/assets/section_gadget.png'
            : type === 'star_power'
              ? '/assets/section_star_power.png'
              : '/assets/section_gear.png';
          setAssetImageSources(image, [iconUrl, categoryFallback], fallback.textContent);
          iconWrap.append(image);
        } else {
          iconWrap.append(fallback);
        }
        iconsWrap.append(iconWrap);
      });
      const labelText = document.createElement('span');
      labelText.className = 'build-spec-label-text';
      labelText.textContent = label;
      labelWrap.append(iconsWrap, labelText);

      const valueText = document.createElement('strong');
      valueText.className = 'build-spec-value';
      valueText.textContent = value;
      row.append(labelWrap, valueText);
      buildHolder.append(row);
    });

    if (build.note) {
      const noteCard = document.createElement('div');
      noteCard.className = 'build-spec-note';
      noteCard.innerHTML = `<p>${build.note}</p>`;
      buildHolder.append(noteCard);
    }
  }

  const strengthList = $('strength-list');
  if (strengthList) {
    strengthList.replaceChildren();
    (guide.strengths || []).forEach((item) => {
      const li = document.createElement('li');
      li.className = 'field-note-item strength-item';
      li.innerHTML = `
        <span class="field-note-bullet strength-bullet">✔</span>
        <span class="field-note-text">${item}</span>
      `;
      strengthList.append(li);
    });
  }

  const cautionList = $('caution-list');
  if (cautionList) {
    cautionList.replaceChildren();
    (guide.watch_out_for || []).forEach((item) => {
      const li = document.createElement('li');
      li.className = 'field-note-item caution-item';
      li.innerHTML = `
        <span class="field-note-bullet caution-bullet">!</span>
        <span class="field-note-text">${item}</span>
      `;
      cautionList.append(li);
    });
  }

  const modes = $('mode-list');
  if (modes) {
    modes.replaceChildren();
    (guide.mode_fit || []).forEach((mode) => {
      const chip = document.createElement('span');
      chip.className = 'mode-chip';
      chip.innerHTML = `${uiIconMarkup('modes', mode, 'mode-icon-img')}<span>${mode}</span>`;
      modes.append(chip);
    });
  }

  renderUsefulMaps(guide);
  renderMatchups(brawler, guide.matchups);
}

function renderUsefulMaps(guide) {
  const grid = $('useful-maps-grid');
  if (!grid) return;
  grid.replaceChildren();

  const maps = guide?.useful_maps || [];
  const panel = grid.closest('.useful-maps-panel');
  if (!maps.length) {
    if (panel) panel.style.display = 'none';
    return;
  }
  if (panel) panel.style.display = '';

  const hoverPreview = $('map-hover-preview');
  const hoverImg = $('map-hover-img');
  const hoverTitle = $('map-hover-title');

  const dialog = $('map-preview-dialog');
  const dialogImg = $('map-dialog-img');
  const dialogName = $('map-dialog-name');
  const dialogMode = $('map-dialog-mode');
  const dialogEventsBtn = $('map-dialog-events-btn');
  const dialogCloseBtn = $('map-dialog-close-btn');

  if (dialogCloseBtn && dialog && !dialogCloseBtn.dataset.bound) {
    dialogCloseBtn.dataset.bound = 'true';
    dialogCloseBtn.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) dialog.close();
    });
  }

  const hideHoverPreview = () => {
    if (hoverPreview) {
      hoverPreview.classList.add('hidden');
      hoverPreview.setAttribute('aria-hidden', 'true');
    }
  };

  // Ensure hover preview hides on page scroll
  window.removeEventListener('scroll', hideHoverPreview, { passive: true });
  window.addEventListener('scroll', hideHoverPreview, { passive: true });

  maps.forEach((m) => {
    const card = document.createElement('a');
    card.className = 'useful-map-card';
    card.href = `/events?map=${encodeURIComponent(m.name)}`;
    card.setAttribute('aria-label', `${m.name} in ${m.mode}`);
    card.dataset.mapName = m.name;
    card.dataset.mapMode = m.mode;
    card.dataset.mapUrl = m.image_url;

    const thumbFrame = document.createElement('div');
    thumbFrame.className = 'map-thumb-frame';
    thumbFrame.title = 'Tap to enlarge map';

    const thumbImg = document.createElement('img');
    thumbImg.className = 'map-thumb-img';
    thumbImg.src = m.image_url;
    thumbImg.alt = `${m.name} preview`;
    thumbImg.loading = 'lazy';
    thumbImg.onerror = () => {
      thumbImg.src = '/assets/player-mascot.png';
    };
    thumbFrame.append(thumbImg);

    if (m.is_active) {
      card.classList.add('useful-map-card-active');
    }

    const info = document.createElement('div');
    info.className = 'map-card-info';

    const nameEl = document.createElement('span');
    nameEl.className = 'map-card-name';
    nameEl.textContent = m.name;

    const modeRow = document.createElement('div');
    modeRow.className = 'map-card-mode-row';

    const modeEl = document.createElement('span');
    modeEl.className = 'map-card-mode';
    modeEl.textContent = m.mode;
    modeRow.append(modeEl);

    if (m.is_active) {
      const liveBadge = document.createElement('span');
      liveBadge.className = 'map-live-status';
      liveBadge.innerHTML = `<span class="live-dot-green"></span><span>LIVE</span>`;
      modeRow.append(liveBadge);
    }

    info.append(nameEl, modeRow);
    card.append(thumbFrame, info);

    const updatePreviewPosition = () => {
      if (!hoverPreview || !hoverImg || !hoverTitle) return;
      hoverImg.src = m.image_url;
      hoverTitle.innerHTML = `${m.name}${m.is_active ? `<span class="map-hover-live-tag"><span class="live-dot-green"></span>LIVE</span>` : ''}`;

      const rect = card.getBoundingClientRect();
      const previewWidth = 210;
      const previewHeight = 315;

      let left = rect.left + (rect.width / 2) - (previewWidth / 2);
      let top = rect.top - previewHeight - 12; // float above by default

      // Viewport boundary detection: flip below if clipped at top
      if (top < 12) {
        top = rect.bottom + 12;
      }

      // Horizontal clamp within viewport
      if (left < 12) {
        left = 12;
      } else if (left + previewWidth > window.innerWidth - 12) {
        left = window.innerWidth - previewWidth - 12;
      }

      hoverPreview.style.left = `${Math.round(left)}px`;
      hoverPreview.style.top = `${Math.round(top)}px`;
      hoverPreview.classList.remove('hidden');
      hoverPreview.setAttribute('aria-hidden', 'false');
    };

    // Desktop hover events
    card.addEventListener('mouseenter', updatePreviewPosition);
    card.addEventListener('mousemove', updatePreviewPosition);
    card.addEventListener('mouseleave', hideHoverPreview);
    card.addEventListener('click', hideHoverPreview);

    // Mobile / touch interactions: tap on thumbnail opens preview dialog without breaking navigation
    thumbFrame.addEventListener('click', (e) => {
      const isTouch = window.matchMedia('(hover: none)').matches || ('ontouchstart' in window);
      if (isTouch && dialog) {
        e.preventDefault();
        e.stopPropagation();
        hideHoverPreview();
        if (dialogImg) dialogImg.src = m.image_url;
        if (dialogName) dialogName.textContent = m.name;
        if (dialogMode) {
          dialogMode.innerHTML = `${m.mode}${m.is_active ? ` • <span class="map-live-status"><span class="live-dot-green"></span>LIVE</span>` : ''}`;
        }
        if (dialogEventsBtn) dialogEventsBtn.href = `/events?map=${encodeURIComponent(m.name)}`;
        dialog.showModal();
      }
    });

    grid.append(card);
  });
}

let matchupsExpanded = false;

function createMatchupCard(item, category) {
  const card = document.createElement('a');
  card.className = `matchup-card matchup-card-${category}`;
  card.href = `/brawlers/${item.id}`;
  card.setAttribute('aria-label', `${item.name}: ${item.win_rate}% win rate over ${format(item.total_battles)} matches`);
  card.dataset.brawlerId = item.id;

  const avatar = document.createElement('div');
  avatar.className = 'matchup-brawler-avatar';

  const img = document.createElement('img');
  img.className = 'matchup-avatar-img';
  img.loading = 'lazy';
  img.alt = item.name;
  img.src = (item.id === 16000108)
    ? '/assets/brawlers/thumbs/16000108.png?v=2'
    : `https://cdn.brawlify.com/brawlers/borders/${item.id}.png`;
  let fallbackStep = 0;
  img.onerror = () => {
    fallbackStep += 1;
    if (fallbackStep === 1) {
      img.src = `/assets/brawlers/thumbs/${item.id}.webp`;
    } else if (fallbackStep === 2) {
      img.src = `/assets/brawlers/${item.id}.png`;
    } else {
      avatar.innerHTML = `<span class="brawler-fallback">${initials(item.name)}</span>`;
    }
  };
  avatar.append(img);

  const meta = document.createElement('div');
  meta.className = 'matchup-card-meta';

  const name = document.createElement('strong');
  name.className = 'matchup-brawler-name';
  name.textContent = item.name;

  const count = document.createElement('span');
  count.className = 'matchup-match-count';
  count.textContent = `${format(item.total_battles)} matches`;

  meta.append(name, count);

  const pill = document.createElement('div');
  pill.className = `matchup-rate-pill pill-${category}`;
  const rateStr = `${Number(item.win_rate).toFixed(1)}%`;
  pill.innerHTML = `<span>${rateStr}</span>`;

  if (category === 'counters') {
    pill.title = `${rateStr} win rate when facing ${item.name} (${(100 - Number(item.win_rate)).toFixed(1)}% loss rate)`;
    card.title = `Facing ${item.name}: ${rateStr} win rate across ${format(item.total_battles)} battles`;
  } else if (category === 'favorable') {
    pill.title = `${rateStr} win rate against ${item.name}`;
    card.title = `Against ${item.name}: ${rateStr} win rate across ${format(item.total_battles)} battles`;
  } else {
    pill.title = `${rateStr} team win rate alongside ${item.name}`;
    card.title = `Paired with ${item.name}: ${rateStr} team win rate across ${format(item.total_battles)} battles`;
  }

  card.append(avatar, meta, pill);

  card.addEventListener('click', (e) => {
    e.preventDefault();
    history.pushState({ path: `/brawlers/${item.id}` }, '', `/brawlers/${item.id}`);
    window.scrollTo(0, 0);
    handleRoute({ isPop: false });
  });

  return card;
}

async function renderMatchups(brawler, matchupsData = null, resetExpanded = true) {
  const panel = $('matchups-teammates-panel');
  if (!panel) return;

  const toggleBtn = $('matchups-toggle-btn');
  const toggleLabel = $('matchups-toggle-label');
  if (resetExpanded) {
    matchupsExpanded = false;
    if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
    if (toggleLabel) toggleLabel.textContent = 'View All Matchups';
  }

  let data = matchupsData;
  if (!data || !data.strong_against) {
    try {
      data = await request(`/api/brawlers/${brawler.id}/matchups`);
    } catch {
      data = null;
    }
  }

  if (!data || (!data.strong_against?.length && !data.struggles_against?.length && !data.best_alongside?.length)) {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = '';

  const favTitle = $('favorable-col-title');
  if (favTitle) {
    favTitle.textContent = `${brawler.name || 'Brawler'} beats`;
  }

  const favList = $('matchup-favorable-list');
  const cntList = $('matchup-counters-list');
  const synList = $('matchup-synergy-list');

  const populateLists = (expanded) => {
    const limit = expanded ? 12 : 6;

    if (favList) {
      favList.replaceChildren();
      (data.strong_against || []).slice(0, limit).forEach((item) => {
        favList.append(createMatchupCard(item, 'favorable'));
      });
    }

    if (cntList) {
      cntList.replaceChildren();
      (data.struggles_against || []).slice(0, limit).forEach((item) => {
        cntList.append(createMatchupCard(item, 'counters'));
      });
    }

    if (synList) {
      synList.replaceChildren();
      (data.best_alongside || []).slice(0, limit).forEach((item) => {
        synList.append(createMatchupCard(item, 'synergy'));
      });
    }
  };

  populateLists(matchupsExpanded);

  if (toggleBtn && !toggleBtn.dataset.bound) {
    toggleBtn.dataset.bound = 'true';
    toggleBtn.addEventListener('click', () => {
      matchupsExpanded = !matchupsExpanded;
      toggleBtn.setAttribute('aria-expanded', String(matchupsExpanded));
      if (toggleLabel) {
        toggleLabel.textContent = matchupsExpanded ? 'Show Less Matchups' : 'View All Matchups';
      }
      populateLists(matchupsExpanded);
    });
  }

  // Bind manual sync trigger
  const syncBtn = $('matchups-sync-btn');
  if (syncBtn && !syncBtn.dataset.bound) {
    syncBtn.dataset.bound = 'true';
    syncBtn.addEventListener('click', async () => {
      syncBtn.classList.add('spinning');
      try {
        const freshData = await request(`/api/brawlers/${brawler.id}/matchups/refresh`, { method: 'POST' });
        if (freshData) {
          renderMatchups(brawler, freshData, false);
        }
      } catch {
        // quiet fallback
      } finally {
        setTimeout(() => syncBtn.classList.remove('spinning'), 600);
      }
    });
  }

  // Bind info button click toggle for mobile / click interactions
  const infoBtn = $('matchups-info-btn');
  const infoWrap = infoBtn?.closest('.matchups-info-wrap');
  if (infoBtn && infoWrap && !infoBtn.dataset.bound) {
    infoBtn.dataset.bound = 'true';
    infoBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      infoWrap.classList.toggle('is-open');
    });
    document.addEventListener('click', () => {
      infoWrap.classList.remove('is-open');
    });
  }
}

let detailRefreshTimer = null;
function setupDetailAutoRefresh(id) {
  if (detailRefreshTimer) clearInterval(detailRefreshTimer);
  detailRefreshTimer = setInterval(async () => {
    if (state.page !== 'detail') {
      clearInterval(detailRefreshTimer);
      detailRefreshTimer = null;
      return;
    }
    try {
      const refreshedGuide = await request(`/api/guides/${id}`);
      if (refreshedGuide) {
        if (refreshedGuide.useful_maps) {
          renderUsefulMaps(refreshedGuide);
        }
        if (refreshedGuide.matchups) {
          renderMatchups({ id: refreshedGuide.id || id, name: refreshedGuide.name }, refreshedGuide.matchups, false);
        }
      }
    } catch {
      // quiet background refresh
    }
  }, 45000);
}

document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && state.page === 'detail') {
    const id = Number(location.pathname.split('/').filter(Boolean).pop());
    if (id) {
      try {
        const refreshedGuide = await request(`/api/guides/${id}`);
        if (refreshedGuide) {
          if (refreshedGuide.useful_maps) {
            renderUsefulMaps(refreshedGuide);
          }
          if (refreshedGuide.matchups) {
            renderMatchups({ id: refreshedGuide.id || id, name: refreshedGuide.name }, refreshedGuide.matchups, false);
          }
        }
      } catch {}
    }
  }
});

function renderDetailArtwork(brawler) {
  const stage = $('hero-art-stage');
  if (!stage) return;
  stage.replaceChildren();
  const image = new Image();
  image.alt = `${brawler.name} generated artwork`;
  image.decoding = 'async';
  image.src = brawler.id === 16000038 && !brawler.owned
    ? '/assets/surge-guide-art.png'
    : [16000107, 16000108].includes(brawler.id)
      ? `/assets/brawlers/generated/${brawler.id}.png`
      : `/assets/brawlers/${brawler.id}.png`;
  image.onerror = () => {
    image.remove();
    stage.textContent = brawler.name;
  };
  stage.append(image);
}

function renderPrestigeProgress(brawler) {
  const panel = $('prestige-progress-panel');
  if (!panel) return;
  const owned = Boolean(brawler?.owned);
  const prestige = getPrestigeState(brawler);
  panel.classList.toggle('catalog-preview', !owned);

  const emblem = $('detail-prestige-emblem');
  if (emblem) {
    emblem.classList.remove('hidden');
    emblem.alt = `${brawler?.name || 'Brawler'} ${prestige.label} Prestige emblem`;
    applyPrestigeImage(emblem, brawler);
  }

  setText('detail-prestige-label', owned ? prestige.label : 'Path to Prestige');
  setText('detail-prestige-source', owned ? (prestige.authoritative ? 'OFFICIAL API' : 'DERIVED FALLBACK') : 'CATALOG PREVIEW');
  setText('detail-prestige-current', owned
    ? (prestige.level > 0 ? `${format(prestige.trophiesInLevel)} / 1,000 Prestige Trophies` : `${format(brawler.trophies)} total Trophies`)
    : 'Connect a player to view progress');
  setText('detail-prestige-remaining', owned
    ? (prestige.remaining === 0 ? 'Milestone reached' : `${format(prestige.remaining)} to ${prestige.level > 0 ? `Prestige ${prestige.nextLevel}` : prestige.nextTotal}`)
    : 'Progress is player-specific');
  setText('detail-prestige-reward', owned && prestige.nextReward
    ? `Milestone reward: ${prestige.nextReward} (availability only; ownership is not exposed by the API)`
    : 'No confirmed cosmetic reward at the next level; reward ownership is not exposed by the API.');
  setText('detail-prestige-summary', owned
    ? (prestige.level > 0
      ? `${format(brawler.trophies)} cumulative API Trophies; ${format(prestige.trophiesInLevel)} earned since Prestige ${prestige.level}. Prestige progress is permanent.`
      : `${prestige.label} milestone on the permanent path to Prestige 1 at 1,000 Trophies.`)
    : 'Prestige is permanent and begins after this Brawler reaches the 1,000-Trophy milestone.');

  const bar = $('detail-prestige-bar');
  if (bar) bar.style.width = `${owned ? Math.max(0, Math.min(100, prestige.progress)) : 0}%`;
  const track = bar?.parentElement;
  if (track) track.setAttribute('aria-valuenow', String(owned ? Math.round(prestige.progress) : 0));

  const visualNote = $('detail-prestige-visual-note');
  if (visualNote) {
    visualNote.classList.toggle('hidden', !owned || !prestige.visualFallback);
    visualNote.textContent = prestige.visualFallback ? `Prestige ${prestige.level} · P10 frame fallback` : '';
  }
}

async function renderDetail() {
  const id = Number(location.pathname.split('/').filter(Boolean).pop());
  if (!state.catalog || state.catalog.length === 0) {
    await loadCatalog();
  }
  if (!state.player && !state.ownedBrawlers.length) {
    await loadInitialAccount();
  }
  if (!state.brawlers || state.brawlers.length === 0) {
    state.brawlers = mergeCatalog(state.ownedBrawlers);
  }
  let brawler = (state.brawlers || []).find((item) => item.id === id);
  if (!brawler && (state.catalog || []).length > 0) {
    const cat = state.catalog.find((item) => item.id === id);
    if (cat) {
      brawler = { ...cat, owned: false, power: 0, rank: 0, prestige_level: 0, trophies: 0, highest_trophies: 0, gadgets: [], star_powers: [], gears: [], hypercharges: [], buffies: { gadget: false, star_power: false, hypercharge: false } };
    }
  }
  if (!brawler) {
    brawler = { id, name: 'Brawler', rarity: 'common', owned: false, power: 0, rank: 0, prestige_level: 0, trophies: 0, highest_trophies: 0, gadgets: [], star_powers: [], gears: [], hypercharges: [], buffies: { gadget: false, star_power: false, hypercharge: false } };
  }
  hideNotice();
  let guide = {};
  try { guide = await request(`/api/guides/${id}`); } catch { guide = {}; }
  setText('page-title', '');
  $('page-title')?.classList.add('hidden');
  setText('detail-name', brawler.name);
  
  const rawRarity = (guide.rarity || brawler.rarity || 'common').toLowerCase().replace(/\s+/g, '_');
  const rarityEl = $('detail-rarity');
  if (rarityEl) {
    rarityEl.className = `rarity-badge ${rawRarity}`;
    rarityEl.textContent = (guide.rarity || brawler.rarity || 'BRAWLER').toUpperCase();
  }

  const bClass = guide.class || brawler.class || (brawler.owned ? 'Damage Dealer' : 'Brawler');
  const classEl = $('detail-class');
  if (classEl) {
    classEl.className = `class-badge ${bClass.toLowerCase().replace(/\s+/g, '_')}`;
    classEl.innerHTML = `${uiIconMarkup('classes', bClass, 'class-icon')}<span>${bClass.toUpperCase()}</span>`;
  }

  const statusEl = $('detail-account-status');
  if (statusEl) {
    statusEl.textContent = brawler.owned ? 'OWNED IN ACCOUNT' : 'CATALOG PREVIEW';
    statusEl.className = `data-label ${brawler.owned ? '' : 'demo'}`;
  }

  setText('detail-intro', guide.intro || (brawler.owned ? `${brawler.name} is Power ${brawler.power} on this account. Progression and owned equipment below come from the loaded player data.` : `${brawler.name} is part of the 106-brawler catalog but is not present in this account. Use the level journey below to preview future progression.`));
  const prestige = getPrestigeState(brawler);
  setText('detail-power', brawler.owned ? brawler.power : '—');
  setText('detail-trophies', brawler.owned ? format(brawler.trophies) : '—');
  setText('detail-prestige', brawler.owned ? (prestige.level > 0 ? prestige.level : prestige.label) : '—');
  setText('detail-prestige-progress', brawler.owned ? `${format(prestige.trophiesInLevel)} / 1,000` : '—');
  renderPrestigeProgress(brawler);
  setText('attack-name', guide.attack?.name || 'Main attack');
  setText('attack-description', guide.attack?.description || 'Detailed combat notes are not curated yet.');
  setText('super-name', guide.super?.name || 'Super');
  setText('super-description', guide.super?.description || 'Detailed combat notes are not curated yet.');

  const portraitEl = $('detail-portrait-icon');
  if (portraitEl) {
    portraitEl.src = (brawler.id === 16000108)
      ? brawlerImage(brawler, true)
      : `https://cdn.brawlify.com/brawlers/borders/${brawler.id}.png`;
    portraitEl.alt = `${brawler.name} official portrait`;
    portraitEl.onerror = () => {
      portraitEl.src = brawlerImage(brawler, true);
    };
  }

  renderDetailArtwork(brawler);

  const howTo = $('how-to-list');
  if (howTo) {
    howTo.replaceChildren();
    const steps = (guide.how_to_use || guide.how_to || [brawler.owned ? 'Review the current equipment and complete the highest-priority gap shown here.' : 'Unlock this brawler before planning account-specific equipment upgrades.']);
    steps.forEach((text, index) => {
      const li = document.createElement('li');
      li.className = 'how-to-item';
      li.innerHTML = `
        <span class="how-to-step-num">${index + 1}</span>
        <span class="how-to-text">${text}</span>
      `;
      howTo.append(li);
    });
  }

  updateDetailReadiness(brawler, guide);

  renderGuideProfile(guide, brawler);
  renderPowerLadder(brawler.owned ? brawler.power : 0, guide);
  renderEquipment('gadget-list', guide.gadgets || [], brawler.gadgets, brawler.owned ? 'No Gadget data recorded.' : 'Unlock this brawler to track Gadgets.', 'gadget', brawler, guide);
  renderEquipment('star-power-list', guide.star_powers || [], brawler.star_powers, brawler.owned ? 'No Star Power data recorded.' : 'Unlock this brawler to track Star Powers.', 'star_power', brawler, guide);
  const gearDescriptions = {
    'SPEED': 'Increases movement speed by 15% when moving inside bushes.',
    'HEALTH': 'Recover health 50% more effectively and quickly.',
    'DAMAGE': 'Deals 15% extra damage when brawler health falls below 50%.',
    'VISION': 'Reveals hidden opponents for 2.0 seconds after dealing damage to them.',
    'SHIELD': 'Grants +900 extra consumable shield health (regenerates in 10s at max health).',
    'GADGET COOLDOWN': 'Reduces Gadget cooldown by 15%.',
    'RELOAD SPEED': 'Increases brawler basic attack reload speed by +15%.',
    'SUPER CHARGE': 'Increases Super attack charge rate by +10%.',
    'PET POWER': 'Spawnables and pets deal +25% extra damage or healing.',
    'QUADRUPLETS': "Eve's Baby Boom Super hatches 4 alien hatchlings instead of 3.",
    'THICC HEAD': "Tick's Head gains +1,000 extra health.",
    'TALK TO THE HAND': "Increases Gene's Super hand range by 1 tile.",
    'EXHAUSTING STORM': "Enemies inside Sandy's Sandstorm deal 20% less damage.",
    'SUPER TURRET': "Mama's Kiss turret healing power is increased by +20%.",
    'STICKY OIL': "Amber's oil puddles slow enemies down by 10%.",
  };

  const gearGuide = (guide.gears || []).map((name) => ({
    name,
    description: gearDescriptions[name] || gearDescriptions[name.toUpperCase()] || 'Available Gear option; confirm current unlock requirements in-game.'
  }));
  renderEquipment('gear-list', gearGuide, brawler.gears, brawler.owned ? 'No Gear data recorded.' : 'Unlock this brawler to track Gears.', 'gear', brawler, guide);
  const liveHypercharge = Array.isArray(brawler.hypercharges) ? brawler.hypercharges[0] : null;
  const hyperchargeForDisplay = liveHypercharge
    ? { ...(guide.hypercharge || {}), ...liveHypercharge, released: true }
    : guide.hypercharge;
  renderHypercharge('hypercharge-list', hyperchargeForDisplay, brawler, guide);

  const sources = $('guide-sources');
  if (sources) {
    sources.replaceChildren();
    const brawlerName = guide?.name || brawler?.name || 'this brawler';

    const sourceItems = [
      { label: 'Brawl Stars Gears', url: 'https://support.supercell.com/brawl-stars/en/articles/gears-8.html' },
      { label: 'Brawl Stars Gadgets', url: 'https://support.supercell.com/brawl-stars/en/articles/gadgets-4.html' },
      { label: 'Brawl Stars Star Powers', url: 'https://support.supercell.com/brawl-stars/en/articles/star-powers-3.html' },
      { label: 'Brawl Stars Hypercharge', url: 'https://support.supercell.com/brawl-stars/en/articles/hypercharge-5.html' },
      { label: 'Brawl Stars Release Notes', url: 'https://supercell.com/en/games/brawlstars/blog/' },
      { label: 'Brawl Stars Balance Changes & Meta', url: 'https://supercell.com/en/games/brawlstars/blog/release-notes/release-notes-august-2026/' },
    ];

    sourceItems.forEach((source) => {
      const link = document.createElement('a');
      link.href = source.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = source.label;
      sources.append(link);
    });
  }

  setupDetailAutoRefresh(id);
}

function updateDetailReadiness(brawler, guide) {
  const ownedGears = brawler.owned ? (brawler.gears || []).length : 0;
  setText('readiness-power-val', brawler.owned ? `LVL ${brawler.power}` : 'LOCKED');
  setText('readiness-gadget-val', brawler.owned ? `${brawler.gadgets.length}/${(guide.gadgets || []).length || 2}` : '0/2');
  setText('readiness-star-val', brawler.owned ? `${brawler.star_powers.length}/${(guide.star_powers || []).length || 2}` : '0/2');
  setText('readiness-gear-val', ownedGears);

  const priorities = $('priority-list');
  if (priorities) {
    priorities.replaceChildren();
    prioritySteps(brawler, guide).forEach((step, index) => {
      const row = document.createElement('article');
      row.className = 'priority-card-item';
      
      let tagClass = 'tag-ready';
      const t = (step.tag || '').toUpperCase();
      if (t.includes('READY')) tagClass = 'tag-ready';
      else if (t.includes('GAP') || t.includes('LOCKED')) tagClass = 'tag-gap';
      else if (t.includes('LEVEL') || t.includes('NEXT')) tagClass = 'tag-next';
      else if (t.includes('FUTURE')) tagClass = 'tag-future';

      row.innerHTML = `
        <span class="priority-step-num">${index + 1}</span>
        <div class="priority-copy">
          <h3 class="priority-title">${step.title}</h3>
          <p class="priority-reason">${step.reason}</p>
        </div>
        <span class="priority-status-pill ${tagClass}">${step.tag}</span>
      `;
      priorities.append(row);
    });
  }
}

function getHyperchargeIcon(brawlerName, hyperchargeName) {
  const b = normalizeKey(brawlerName);
  const h = normalizeKey(hyperchargeName);
  
  if (b === 'buzz' || h.includes('buzzzilla') || h.includes('buzzwatch')) return '🦖';
  if (b === 'shelly' || h.includes('doublebarrel')) return '💥';
  if (b === 'colt' || h.includes('dualwielding') || h.includes('tootoomuch')) return '🔫';
  if (b === 'bull' || h.includes('juggernaut')) return '🐂';
  if (b === 'brock' || h.includes('rocketbarrage') || h.includes('rocketrain')) return '🚀';
  if (b === 'rico' || h.includes('trickshot')) return '⚡';
  if (b === 'spike' || h.includes('bloomingseason')) return '🌵';
  if (b === 'barley' || h.includes('bottlehurl')) return '🍾';
  if (b === 'jessie' || h.includes('scrappy')) return '⚙️';
  if (b === 'nita' || h.includes('hyperbear')) return '🐻';
  if (b === 'dynamike' || h.includes('boomer')) return '💣';
  if (b === 'elprimo' || h.includes('gravityleap') || h.includes('meteor')) return '☄️';
  if (b === 'mortis' || h.includes('bloodtransfusion') || h.includes('batstorm')) return '🦇';
  if (b === 'crow' || h.includes('utilitydaggers')) return '🦅';
  if (b === 'poco' || h.includes('medicsmelody')) return '🎸';
  if (b === 'bo' || h.includes('clusterarrow')) return '🏹';
  if (b === 'piper' || h.includes('poppin')) return '☂️';
  if (b === 'pam' || h.includes('superturret')) return '❤️‍🩹';
  if (b === 'tara' || h.includes('supermassive')) return '🌀';
  if (b === 'darryl' || h.includes('barrelroll')) return '🛡️';
  if (b === 'penny' || h.includes('megacannon')) return '🏴‍☠️';
  if (b === 'frank' || h.includes('seismicsmash')) return '🔨';
  if (b === 'gene' || h.includes('hyperhand')) return '✋';
  if (b === 'tick' || h.includes('thickhead')) return '🧨';
  if (b === 'leon' || h.includes('limbo')) return '🦎';
  if (b === 'rosa' || h.includes('graspgrowth')) return '🥊';
  if (b === 'carl' || h.includes('supercutter')) return '⛏️';
  if (b === 'bibi' || h.includes('outrageousbubble')) return '⚾';
  if (b === '8bit' || h.includes('aimassist')) return '🕹️';
  if (b === 'sandy' || h.includes('exhaustingstorm')) return '💤';
  if (b === 'bea' || h.includes('hivemind')) return '🐝';
  if (b === 'emz' || h.includes('overprotective')) return '💨';
  if (b === 'max' || h.includes('unlimitedenergy')) return '⚡';
  if (b === 'jacky' || h.includes('seismicshake')) return '🕳️';
  if (b === 'gale' || h.includes('blizzardburst')) return '❄️';
  if (b === 'nani' || h.includes('peepoverload')) return '👁️';
  if (b === 'sprout' || h.includes('thornythicket')) return '🌱';
  if (b === 'surge' || h.includes('level5evolution') || h.includes('partytime')) return '🦾';
  if (b === 'colette' || h.includes('teenageangst')) return '📖';
  if (b === 'amber' || h.includes('firestorm')) return '🔥';
  if (b === 'lou' || h.includes('subzero')) return '🍧';
  if (b === 'edgar' || h.includes('outburst')) return '🧣';
  if (b === 'ruffs' || h.includes('airsupport')) return '🐶';
  if (b === 'stu' || h.includes('infinitenitro')) return '🏎️';
  if (b === 'belle' || h.includes('magneticshot')) return '⚡';
  if (b === 'squeak' || h.includes('stickybomb')) return '💧';
  if (b === 'grom' || h.includes('seismiccross')) return '💣';
  if (b === 'ash' || h.includes('trashcompactor')) return '🗑️';
  if (b === 'fang' || h.includes('dragonskick')) return '👟';
  if (b === 'eve' || h.includes('infestation')) return '🛸';
  if (b === 'janet' || h.includes('skyrocketing')) return '🎤';
  if (b === 'otis' || h.includes('silentspray')) return '🎨';
  if (b === 'sam' || h.includes('knuckleblast')) return '🥊';
  if (b === 'buster' || h.includes('blockbuster')) return '📽️';
  if (b === 'chester' || h.includes('jackinthebox')) return '🃏';
  if (b === 'gray' || h.includes('grandfinale')) return '🚪';
  if (b === 'rt' || b === 'r-t' || h.includes('overdrive')) return '📡';
  if (b === 'maisie' || h.includes('afterburn')) return '💥';
  if (b === 'cordelius' || h.includes('shadowrealm')) return '🍄';
  if (b === 'pearl' || h.includes('pyroclastic')) return '🍪';
  if (b === 'charlie' || h.includes('arachnidarmy')) return '🕷️';
  if (b === 'mico' || h.includes('soundcheck')) return '🎙️';
  if (b === 'melodie' || h.includes('harmonicnotes')) return '🎶';
  if (b === 'angelo' || h.includes('swampflight')) return '🦟';
  if (b === 'draco' || h.includes('dragonrage')) return '🐉';
  if (b === 'clancy' || h.includes('shellshock')) return '🦞';
  if (b === 'moe' || h.includes('superdrill')) return '🐀';
  if (b === 'kenji' || h.includes('slashstorm')) return '🍣';
  if (b === 'shade' || h.includes('shadowwalk')) return '👻';
  if (b === 'juju' || h.includes('voodoovortex')) return '🔮';
  
  return '⚡';
}

function createHyperchargeEmblem(brawler, hypercharge) {
  const emblemWrap = document.createElement('div');
  emblemWrap.className = 'ability-emblem-wrap hyper-wrap';

  const emblem = document.createElement('div');
  emblem.className = 'official-hypercharge-emblem';
  emblem.title = hypercharge?.name || 'Hypercharge';
  const image = document.createElement('img');
  image.alt = `${brawler?.name || 'Brawler'} Hypercharge`;
  image.className = 'ability-icon-img hyper-icon-img';
  setAssetImageSources(
    image,
    getHyperchargeImageSources(brawler),
    'HC',
  );
  emblem.append(image);
  emblemWrap.append(emblem);
  return emblemWrap;
}

function getVisualAssetEntry(brawlerOrName) {
  const entries = state.visualAssets?.brawlers || {};
  const id = typeof brawlerOrName === 'object' ? brawlerOrName?.id : null;
  if (id != null && entries[String(id)]) return entries[String(id)];
  const name = typeof brawlerOrName === 'object' ? brawlerOrName?.name : brawlerOrName;
  const key = normalizeKey(name);
  return Object.values(entries).find((entry) => normalizeKey(entry?.name) === key) || null;
}

function uniqueAssetSources(sources) {
  return [...new Set((sources || []).filter(Boolean))];
}

function setAssetImageSources(image, sources, textFallback) {
  const candidates = uniqueAssetSources(sources);
  let index = 0;
  image.onerror = () => {
    index += 1;
    if (index < candidates.length) {
      image.src = candidates[index];
      return;
    }
    image.onerror = null;
    const placeholder = document.createElement('span');
    placeholder.className = 'asset-text-placeholder';
    placeholder.textContent = textFallback;
    placeholder.setAttribute('role', 'img');
    placeholder.setAttribute('aria-label', image.alt || textFallback);
    image.replaceWith(placeholder);
  };
  if (candidates.length) {
    image.src = candidates[0];
  } else {
    image.onerror();
  }
}

function getHyperchargeImageSources(brawler) {
  const entry = getVisualAssetEntry(brawler);
  const fallbacks = state.visualAssets?.fallbacks?.hypercharge || [
    '/assets/section_hypercharge.png',
    '/assets/hypercharge_icon.webp',
  ];
  return uniqueAssetSources([entry?.hypercharge?.local_url, ...fallbacks]);
}

function getBuffieImageSources(brawler, abilityType) {
  const entry = getVisualAssetEntry(brawler);
  const unreleasedFallbacks = state.visualAssets?.fallbacks?.buffy_unreleased || [
    '/assets/buffies/generic.png',
    '/assets/buffie_icon.webp',
  ];
  if (entry?.buffies?.released !== true) {
    return uniqueAssetSources(unreleasedFallbacks);
  }
  const fallbacks = state.visualAssets?.fallbacks?.buffy?.[abilityType] || [
    abilityType === 'gadget'
      ? '/assets/section_gadget.png'
      : abilityType === 'star_power'
        ? '/assets/section_star_power.png'
        : '/assets/section_hypercharge.png',
    '/assets/buffie_icon.webp',
  ];
  return uniqueAssetSources([entry?.buffies?.[abilityType]?.local_url, ...fallbacks]);
}

function getBuffieIcon(brawlerName, abilityName, type) {
  const norm = normalizeKey(abilityName);
  if (type === 'hypercharge') return '⚡';
  
  if (norm.includes('buoy') || norm.includes('hook') || norm.includes('grapple')) return '🛟';
  if (norm.includes('shade') || norm.includes('sight') || norm.includes('vision') || norm.includes('eye') || norm.includes('peek')) return '👁️';
  if (norm.includes('torpedo') || norm.includes('missile') || norm.includes('rocket') || norm.includes('bullet')) return '🚀';
  if (norm.includes('heal') || norm.includes('aid') || norm.includes('hug') || norm.includes('pulse') || norm.includes('recovery')) return '💚';
  if (norm.includes('speed') || norm.includes('dash') || norm.includes('forward') || norm.includes('boots') || norm.includes('stride')) return '👟';
  if (norm.includes('shield') || norm.includes('armor') || norm.includes('tough') || norm.includes('defense') || norm.includes('resilien')) return '🛡️';
  if (norm.includes('damage') || norm.includes('power') || norm.includes('berserk') || norm.includes('stomp') || norm.includes('strike')) return '⚔️';
  if (norm.includes('stun') || norm.includes('freeze') || norm.includes('shock') || norm.includes('slow') || norm.includes('toxic') || norm.includes('poison')) return '❄️';
  if (norm.includes('bomb') || norm.includes('blast') || norm.includes('explode') || norm.includes('dynamite') || norm.includes('burst')) return '💥';
  if (norm.includes('magic') || norm.includes('spirit') || norm.includes('shadow') || norm.includes('ghost') || norm.includes('sneak')) return '🔮';
  if (norm.includes('clay') || norm.includes('pigeon') || norm.includes('target') || norm.includes('sniper') || norm.includes('scope')) return '🎯';
  if (norm.includes('spin') || norm.includes('wheel') || norm.includes('shovel') || norm.includes('twist')) return '🌀';
  
  return type === 'gadget' ? '🔧' : '⭐';
}

function isBuffieReleased(brawler) {
  if (!brawler) return false;
  const visualEntry = getVisualAssetEntry(brawler);
  if (visualEntry?.buffies && typeof visualEntry.buffies.released === 'boolean') {
    return visualEntry.buffies.released;
  }
  const brawlerName = typeof brawler === 'object' ? brawler.name : brawler;
  const bNorm = normalizeKey(brawlerName);
  const released = state.buffiesDb?.released_brawlers || [
    '8-BIT', '8BIT', '8 BIT', 'AMBER', 'BIBI', 'BO', 'BROCK', 'BULL', 'CHUCK', 'COLETTE',
    'COLT', 'CROW', 'EDGAR', 'EL PRIMO', 'ELPRIMO', 'EMZ', 'FRANK', 'GRIFF', 'GUS',
    'LEON', 'MAX', 'MEG', 'MORTIS', 'NITA', 'POCO', 'RICO', 'SHADE', 'SHELLY', 'SPIKE', 'SURGE'
  ];
  return released.some((r) => normalizeKey(r) === bNorm);
}

function renderHypercharge(targetId, hypercharge, brawler, guide = null) {
  const holder = $(targetId);
  if (!holder) return;
  holder.replaceChildren();

  // Edge case: Brawler does not yet have a Hypercharge officially released in Brawl Stars (e.g. Nori, Wendy, etc.)
  if (!hypercharge || hypercharge.released === false || !hypercharge.name || hypercharge.name.toLowerCase() === 'unreleased') {
    const unreleasedCard = document.createElement('article');
    unreleasedCard.className = 'hypercharge-unreleased-card';
    unreleasedCard.innerHTML = `
      <div class="ability-header-row">
        <div class="ability-title-wrap">
          <span class="ability-emblem unreleased-emblem">⏳</span>
          <strong style="color:#536888;">HYPERCHARGE UNRELEASED</strong>
        </div>
        <span class="missing-status">COMING SOON</span>
      </div>
      <p style="margin:6px 0 0; color:#788ea8; font-size:11px; line-height:1.5;">
        Supercell has not yet released an official Hypercharge for this brawler. Stay tuned for future Brawl Talk update releases!
      </p>
    `;
    holder.append(unreleasedCard);
    return;
  }

  const buffiesReleased = isBuffieReleased(brawler);
  const hasHcBuffie = Boolean(brawler?.owned) && hasBuffie(brawler, 'hypercharge');
  const isOwned = Boolean(brawler?.owned) && hasHypercharge(brawler, guide);
  const isHcActive = isOwned && ((brawler?.power || 0) >= 11);
  const useState = equipmentUseState(brawler, 'hypercharge', isOwned);

  // Condition 1 & 2 (if stored, don't light up!):
  const isLitUp = buffiesReleased
    ? (isHcActive && hasHcBuffie)
    : isHcActive;

  const row = document.createElement('article');
  row.className = `equipment-card hypercharge-card ${isOwned ? 'owned' : 'unowned'} ${isLitUp ? 'lit-up' : 'not-lit'} ${useState.key}`;

  // Header row with integrated Hypercharge emblem
  const header = document.createElement('div');
  header.className = 'ability-header-row';

  const titleWrap = document.createElement('div');
  titleWrap.className = 'ability-title-wrap';

  const emblemWrap = createHyperchargeEmblem(brawler, hypercharge);
  const name = document.createElement('strong');
  name.textContent = hypercharge.name;

  titleWrap.append(emblemWrap, name);

  const statusPill = document.createElement('span');
  statusPill.className = useState.key === 'active' ? 'hypercharge-owned-status' : useState.className;
  statusPill.textContent = useState.label;

  header.append(titleWrap, statusPill);

  // Description
  const description = document.createElement('p');
  description.textContent = hypercharge.description || 'Official Hypercharge ability for this brawler.';

  // Integrated Buffie Subfield for Hypercharge
  const buffieReleased = isBuffieReleased(brawler);
  const buffieState = buffieUseState(brawler, 'hypercharge');

  const buffieBox = document.createElement('div');
  const buffieVisualState = !buffieReleased ? 'disabled-buffie' : buffieState.key === 'active' ? 'active-buffie' : buffieState.key === 'stored' ? 'inventory-buffie' : 'inactive-buffie';
  const buffieIconClass = buffieReleased && (buffieState.key === 'active' || buffieState.key === 'stored') ? 'hypercharge-buffie-badge' : 'disabled-buffie-badge';
  const buffieStatus = buffieReleased ? buffieState.label : 'COMING SOON';
  const buffieStatusClass = buffieReleased ? buffieState.className : 'unreleased-rank-pill';
  const buffieDescription = buffieReleased
    ? (hypercharge.buffie_description || 'The exact Hypercharge Buffy effect is not available in the verified data snapshot.')
    : `Buffies have not been released for ${brawler.name || 'this brawler'}.`;
  buffieBox.className = `buffie-subfield hypercharge-buffie ${buffieVisualState}`;
  buffieBox.innerHTML = `
    <div class="buffie-header-row">
      <div class="buffie-badge-wrap">
        <div class="buffie-icon-badge ${buffieIconClass}"><img alt="${brawler.name} Hypercharge Buffy icon" class="buffie-fandom-icon"></div>
        <span class="buffie-tag">HYPERCHARGE BUFFIE</span>
      </div>
      <span class="buffie-rank-pill ${buffieStatusClass}">${buffieStatus}</span>
    </div>
    <p class="buffie-effect">${buffieDescription}</p>
  `;
  setAssetImageSources(
    buffieBox.querySelector('.buffie-fandom-icon'),
    getBuffieImageSources(brawler, 'hypercharge'),
    'HC',
  );

  row.append(header, description, buffieBox);

  holder.append(row);
}

// Brawl Stars stat scaling multipliers per level relative to Level 11 Max (Linear +10% base per level)
// Level 1 = 50% of Level 11, Level 2 = 55%, ..., Level 11 = 100%
const POWER_MULTIPLIERS = [0, 0.500, 0.550, 0.600, 0.650, 0.700, 0.750, 0.800, 0.850, 0.900, 0.950, 1.000];

function scaleStatString(valueStr, mult, label) {
  if (!valueStr) return '';
  if (mult === 1.000) return valueStr;

  const nonScalingKeywords = ['range', 'speed', 'reload', 'movement', 'duration', 'aura', 'radius', 'charges', 'delay', 'spread', 'bullets', 'projectiles', 'width', 'tile', 'second', 'shield', '%', 'percent', 'reduction', 'multiplier', 'decay'];
  const labelLower = (label || '').toLowerCase();
  const isNonScaling = nonScalingKeywords.some((kw) => labelLower.includes(kw));
  if (isNonScaling || String(valueStr).includes('%')) {
    return valueStr;
  }

  // Scale any damage / health numbers (50 or higher), preserving commas, multipliers, and surrounding text
  return String(valueStr).replace(/\b\d{1,3}(?:,\d{3})+\b|\b\d{2,}\b/g, (match) => {
    const rawNum = parseInt(match.replace(/,/g, ''), 10);
    if (isNaN(rawNum) || rawNum < 50) return match;
    const scaled = Math.round(rawNum * mult);
    return scaled.toLocaleString();
  });
}

function renderCombatStats(maxStats, level) {
  const stats = $('combat-stats');
  if (!stats || !Array.isArray(maxStats)) return;
  const mult = POWER_MULTIPLIERS[level] ?? 1.000;
  stats.replaceChildren();

  // Update headers
  setText('stats-header-title', level === 11 ? 'Core statistics (Level 11 Max)' : `Core statistics (Level ${level} Preview)`);
  const snapLabel = document.getElementById('guide-level-chip');
  if (snapLabel) snapLabel.textContent = level === 11 ? 'LEVEL 11 MAX STATS' : `LEVEL ${level} PREVIEW`;

  maxStats.forEach((stat) => {
    const row = document.createElement('div');
    row.className = 'combat-stat-row';
    
    // Choose color dot based on stat label
    let dotClass = 'stat-dot-default';
    const l = (stat.label || '').toLowerCase();
    if (l.includes('health') || l.includes('hp')) dotClass = 'stat-dot-health';
    else if (l.includes('damage') || l.includes('attack')) dotClass = 'stat-dot-damage';
    else if (l.includes('super')) dotClass = 'stat-dot-super';
    else if (l.includes('speed') || l.includes('movement') || l.includes('range')) dotClass = 'stat-dot-utility';
    else if (l.includes('reload')) dotClass = 'stat-dot-reload';

    const labelWrap = document.createElement('div');
    labelWrap.className = 'stat-label-wrap';
    labelWrap.innerHTML = `
      <span class="stat-dot ${dotClass}"></span>
      <span class="stat-label-text">${stat.label}</span>
    `;

    const valueEl = document.createElement('strong');
    valueEl.className = 'stat-val-text';
    valueEl.textContent = scaleStatString(stat.value, mult, stat.label);
    
    row.append(labelWrap, valueEl);
    stats.append(row);
  });
}

function renderPowerLadder(current, guide) {
  const holder = $('power-ladder');
  if (!holder) return;
  holder.replaceChildren();

  // Default selected level = current brawler level (or 11 for unowned catalog brawlers)
  let selectedLevel = current || 11;

  function selectLevel(level) {
    selectedLevel = level;
    holder.querySelectorAll('.ladder-chip').forEach((el) => el.classList.remove('level-selected'));
    const target = holder.querySelector(`[data-level="${level}"]`);
    if (target) target.classList.add('level-selected');
    
    // Update stats label pill
    const pill = $('current-power-label');
    if (pill) {
      if (current) {
        pill.textContent = level === current ? `CURRENT: LEVEL ${current}` : `LEVEL ${current} ➜ VIEWING L${level}`;
      } else {
        pill.textContent = `PREVIEWING LEVEL ${level}`;
      }
    }
    
    // Re-render combat stats for this level
    if (guide && guide.max_stats) renderCombatStats(guide.max_stats, level);
  }

  for (let level = 1; level <= 11; level += 1) {
    const item = document.createElement('div');
    item.dataset.level = level;
    item.className = `ladder-chip ${level < current ? 'complete' : level === current ? 'current' : level === current + 1 ? 'next' : 'future'}`;
    item.title = `Preview stats at Level ${level}`;
    
    // Special milestone tags for Brawl Stars
    let unlockBadge = '';
    if (level === 7) unlockBadge = '<small class="milestone-badge">GADGET</small>';
    else if (level === 8) unlockBadge = '<small class="milestone-badge">GEAR SLOT 1</small>';
    else if (level === 9) unlockBadge = '<small class="milestone-badge">STAR ★</small>';
    else if (level === 10) unlockBadge = '<small class="milestone-badge">GEAR SLOT 2</small>';
    else if (level === 11) unlockBadge = '<small class="milestone-badge">HYPER ⚡</small>';
    
    item.innerHTML = `
      <span class="chip-number">L${level}</span>
      <span class="chip-status">${level < current ? 'Reached' : level === current ? 'Current' : level === current + 1 ? (current ? 'Next' : 'L1') : 'Target'}</span>
      ${unlockBadge}
    `;
    item.addEventListener('click', () => selectLevel(level));
    holder.append(item);
  }

  // Apply default selection ring immediately
  selectLevel(selectedLevel);
}

function getEquipmentImageUrl(item, type, brawler) {
  if (item && item.image_url) {
    return item.image_url;
  }

  const rawName = (item.name || '').toUpperCase().trim();
  const norm = normalizeKey(rawName);

  // 1. Check in official equipment database loaded from Supercell API
  if (state.equipmentDb && state.equipmentDb[rawName]) {
    return state.equipmentDb[rawName].image_url;
  }
  
  if (state.equipmentDb) {
    for (const [key, val] of Object.entries(state.equipmentDb)) {
      if (normalizeKey(key) === norm) {
        return val.image_url;
      }
    }
  }

  // 2. If item has an id directly
  if (item.id) {
    if (type === 'gadget') return `/assets/equipment/gadgets/${item.id}.png`;
    if (type === 'star_power') return `/assets/equipment/star-powers/${item.id}.png`;
    if (type === 'gear') return `/assets/equipment/gears/${item.id}.png`;
  }

  // 3. Universal, Epic, and Mythic Gear mappings live in the audited manifest.
  if (type === 'gear') {
    const gear = Object.entries(state.visualAssets?.gears || {})
      .find(([name]) => normalizeKey(name) === norm)?.[1];
    return gear?.local_url || '/assets/section_gear.png';
  }

  return null;
}

function createAbilityBuffie(brawler, type, ability, abilityOwned) {
  if (type !== 'gadget' && type !== 'star_power') return null;

  const brawlerName = brawler?.name || 'Brawler';
  const released = isBuffieReleased(brawler);
  const stateInfo = buffieUseState(brawler, type, abilityOwned);
  const label = type === 'gadget' ? 'GADGET BUFFIE' : 'STAR POWER BUFFIE';

  const card = document.createElement('div');
  const visualState = !released ? 'disabled-buffie' : stateInfo.key === 'active' ? 'active-buffie' : stateInfo.key === 'stored' ? 'inventory-buffie' : 'inactive-buffie';
  card.className = `buffie-subfield buffie-ability-card ${type}-buffie ${visualState}`;

  const header = document.createElement('div');
  header.className = 'buffie-header-row';
  const badgeWrap = document.createElement('div');
  badgeWrap.className = 'buffie-badge-wrap';
  const iconBadge = document.createElement('div');
  const isStored = stateInfo.key === 'stored';
  const isActive = stateInfo.key === 'active';
  const iconBadgeClass = (isActive || isStored) ? `${type}-buffie-badge` : 'disabled-buffie-badge';
  iconBadge.className = `buffie-icon-badge ${iconBadgeClass}`;
  const image = document.createElement('img');
  image.alt = `${label} icon`;
  image.className = 'buffie-fandom-icon';
  setAssetImageSources(
    image,
    getBuffieImageSources(brawler, type),
    type === 'gadget' ? 'G' : 'SP',
  );
  iconBadge.append(image);
  const title = document.createElement('span');
  title.className = 'buffie-tag';
  title.textContent = label;
  badgeWrap.append(iconBadge, title);

  const status = document.createElement('span');
  status.className = `buffie-rank-pill ${released ? stateInfo.className : 'unreleased-rank-pill'}`;
  status.textContent = released ? stateInfo.label : 'COMING SOON';
  header.append(badgeWrap, status);

  const description = document.createElement('p');
  description.className = 'buffie-effect';
  description.textContent = released
    ? (ability?.buffie_description || 'The exact Buffy effect is not available in the verified data snapshot.')
    : `Buffies have not been released for ${brawlerName}.`;

  card.append(header, description);
  return card;
}

function renderEquipment(targetId, available, owned, emptyMessage, type, brawler, guide = null) {
  const holder = $(targetId);
  if (!holder) return;
  holder.replaceChildren();

  const ownedKeys = new Set((owned || []).map((item) => normalizeKey(item.name || item)).filter(Boolean));
  const ownedIds = new Set((owned || []).map((item) => String(item.id || '')).filter(Boolean));

  // Canonical official equipment from guide (strictly 2 for gadgets, 2 for star powers)
  const combined = (available || []).map((item) => ({ ...item }));

  if (!combined.length) {
    const empty = document.createElement('p');
    empty.className = 'equipment-empty';
    empty.textContent = emptyMessage;
    holder.append(empty);
    return;
  }

  const buffiesReleased = isBuffieReleased(brawler);
  const hasBuffieForType = Boolean(brawler?.owned) && hasBuffie(brawler, type);

  combined.forEach((item) => {
    const isOwned = Boolean(brawler?.owned) && (
      ownedKeys.has(normalizeKey(item.name)) ||
      (item.id != null && ownedIds.has(String(item.id)))
    );
    const useState = equipmentUseState(brawler, type, isOwned);

    // Condition 1 & 2:
    let isLitUp = false;
    if (type === 'gear') {
      isLitUp = isOwned;
    } else {
      isLitUp = buffiesReleased
        ? (isOwned && hasBuffieForType)
        : isOwned;
    }

    const row = document.createElement('article');
    row.className = `equipment-card ${type}-card ${isOwned ? 'owned' : 'unowned'} ${isLitUp ? 'lit-up' : 'not-lit'} ${useState.key}`;

    // Header row with integrated emblem and status pill
    const header = document.createElement('div');
    header.className = 'ability-header-row';

    const titleWrap = document.createElement('div');
    titleWrap.className = 'ability-title-wrap';

    // Unique official icon image from CDN with fallback to emblem
    const imgUrl = getEquipmentImageUrl(item, type, brawler);
    const emblemWrap = document.createElement('div');
    emblemWrap.className = `ability-emblem-wrap ${type}-wrap`;

    if (imgUrl) {
      const iconImg = document.createElement('img');
      iconImg.className = 'ability-icon-img';
      iconImg.alt = item.name;
      iconImg.loading = 'lazy';
      const categoryFallback = type === 'gadget'
        ? '/assets/section_gadget.png'
        : type === 'star_power'
          ? '/assets/section_star_power.png'
          : '/assets/section_gear.png';
      setAssetImageSources(
        iconImg,
        [imgUrl, categoryFallback],
        type === 'gadget' ? 'G' : type === 'star_power' ? 'SP' : 'GEAR',
      );
      emblemWrap.append(iconImg);
    } else {
      const emblem = document.createElement('span');
      emblem.className = `ability-emblem ${type}-emblem`;
      emblem.textContent = type === 'gadget' ? 'G' : type === 'star_power' ? '★' : '◆';
      emblemWrap.append(emblem);
    }

    const name = document.createElement('strong');
    name.textContent = item.name;

    titleWrap.append(emblemWrap, name);

    const status = document.createElement('span');
    status.className = useState.className;
    status.textContent = useState.label;

    header.append(titleWrap, status);

    // Ability Description
    const description = document.createElement('p');
    description.textContent = item.description || 'Equipment recorded for this brawler.';

    row.append(header, description);

    const abilityBuffie = createAbilityBuffie(brawler, type, item, isOwned);
    if (abilityBuffie) row.append(abilityBuffie);

    holder.append(row);
  });
}

function bindEvents() {
  $('connect-button')?.addEventListener('click', () => {
    $('dialog-error')?.classList.add('hidden');
    $('connect-dialog')?.showModal();
  });

  $('dialog-close-btn')?.addEventListener('click', () => $('connect-dialog')?.close());
  $('recreator-close-btn')?.addEventListener('click', () => $('recreator-dialog')?.close());
  $('header-back-btn')?.addEventListener('click', () => {
    if (state.page === 'detail') {
      history.pushState({ path: '/brawlers' }, '', '/brawlers');
      window.scrollTo(0, 0);
      handleRoute({ isPop: false });
      return;
    }
    if (window.history.length > 1 && document.referrer && document.referrer.includes(window.location.host)) {
      window.history.back();
      return;
    }
    if (state.page !== 'overview') {
      history.pushState({ path: '/' }, '', '/');
      window.scrollTo(0, 0);
      handleRoute({ isPop: false });
      return;
    }
    window.history.back();
  });

  // Battle filters
  $('battle-filter-all')?.addEventListener('click', (e) => {
    setBattleFilter('all', e.currentTarget);
  });
  $('battle-filter-3v3')?.addEventListener('click', (e) => {
    setBattleFilter('3v3', e.currentTarget);
  });
  $('battle-filter-sd')?.addEventListener('click', (e) => {
    setBattleFilter('sd', e.currentTarget);
  });

  // Leaderboard tabs & regions
  $('tab-rankings-players')?.addEventListener('click', () => {
    state.rankingsType = 'players';
    $('tab-rankings-players').className = 'primary-button';
    $('tab-rankings-clubs').className = 'subtle-button';
    renderLeaderboard();
  });

  $('tab-rankings-clubs')?.addEventListener('click', () => {
    state.rankingsType = 'clubs';
    $('tab-rankings-clubs').className = 'primary-button';
    $('tab-rankings-players').className = 'subtle-button';
    renderLeaderboard();
  });

  $('ranking-region-select')?.addEventListener('change', (e) => {
    state.rankingsRegion = e.target.value;
    loadLeaderboards();
  });

  const dialog = $('connect-dialog');
  if (dialog) {
    dialog.addEventListener('click', (e) => {
      const rect = dialog.getBoundingClientRect();
      const isInDialog = (rect.top <= e.clientY && e.clientY <= rect.top + rect.height
        && rect.left <= e.clientX && e.clientX <= rect.left + rect.width);
      if (!isInDialog) dialog.close();
    });
  }

  $('connect-form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const tag = $('tag-input')?.value.trim();
    if (tag) loadSmartTag(tag);
  });

  $('load-demo')?.addEventListener('click', () => {
    sessionStorage.removeItem(ACCOUNT_CACHE_KEY);
    $('connect-dialog')?.close();
    loadDemo();
    if (state.page !== 'overview' && state.page !== 'brawlers' && state.page !== 'battles') {
      history.pushState(null, '', '/');
      configurePage();
      showView();
    }
  });

  $('load-demo-club')?.addEventListener('click', () => {
    sessionStorage.removeItem(CLUB_CACHE_KEY);
    $('connect-dialog')?.close();
    loadDemoClub();
  });

  $('error-connect-btn')?.addEventListener('click', () => {
    $('dialog-error')?.classList.add('hidden');
    $('connect-dialog')?.showModal();
  });

  $('roster-search')?.addEventListener('input', () => {
    if (state.club?.members) renderClubMembers(state.club.members);
  });

  $('brawler-search')?.addEventListener('input', renderBrawlers);
  $('brawler-sort')?.addEventListener('change', renderBrawlers);
  $('equipment-filter')?.addEventListener('change', (event) => { state.equipment = event.target.value; renderBrawlers(); });
  $('level-filter')?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-level]');
    if (!button) return;
    document.querySelectorAll('.level-chip').forEach((chip) => chip.classList.remove('active'));
    button.classList.add('active');
    state.level = button.dataset.level;
    renderBrawlers();
  });
  $('grid-view')?.addEventListener('click', () => setView('grid'));
  $('table-view')?.addEventListener('click', () => setView('table'));
  window.addEventListener('resize', () => scheduleBrawlerNameFit($('brawler-grid') || document));

  $('copy-club-hero-tag')?.addEventListener('click', (e) => {
    e.preventDefault();
    const tag = state.club?.tag;
    if (tag) {
      navigator.clipboard.writeText(tag);
      showNotice(`Club tag ${tag} copied to clipboard! ✓`);
    }
  });

  $('copy-club-tag')?.addEventListener('click', (e) => {
    const tag = state.player?.club?.tag;
    if (tag && tag !== '—') {
      navigator.clipboard.writeText(tag);
      const btn = e.currentTarget;
      const old = btn.textContent;
      btn.textContent = 'Tag Copied! ✓';
      setTimeout(() => { btn.textContent = old; }, 1500);
    }
  });

  document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link || !link.getAttribute('href')) return;
    const href = link.getAttribute('href');
    if (href.startsWith('/') && !href.startsWith('//') && !link.target && !link.hasAttribute('download')) {
      e.preventDefault();
      const currentKey = location.pathname + location.search;
      scrollPositions.set(currentKey, window.scrollY);
      history.pushState({ path: href }, '', href);
      window.scrollTo(0, 0);
      handleRoute({ isPop: false });
    }
  });
}

const scrollPositions = new Map();
if ('scrollRestoration' in history) {
  history.scrollRestoration = 'manual';
}

function setBattleFilter(filter, btn) {
  state.battleFilter = filter;
  document.querySelectorAll('.battle-filter-tabs .level-chip').forEach((c) => c.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderBattles();
}

function setView(view) {
  state.view = view;
  $('grid-view')?.classList.toggle('active', view === 'grid');
  $('table-view')?.classList.toggle('active', view === 'table');
  renderBrawlers();
}

async function handleRoute(options = {}) {
  configurePage();
  showView();
  if (!options.isPop) {
    window.scrollTo(0, 0);
  }

  const urlParams = new URLSearchParams(location.search);
  const playerParam = urlParams.get('player') || urlParams.get('tag');

  if (playerParam) {
    await loadPlayer(playerParam);
  } else if (!state.player) {
    await loadInitialAccount();
  }

  if (state.page === 'brawlers') {
    if (!state.brawlers || state.brawlers.length === 0) {
      state.brawlers = mergeCatalog(state.ownedBrawlers);
    }
    renderBrawlers();
  } else if (state.page === 'detail') {
    await renderDetail();
  } else if (state.page === 'club') {
    await loadInitialClub();
  } else if (state.page === 'battles') {
    await loadBattles();
  } else if (state.page === 'events') {
    await loadEvents();
  } else if (state.page === 'leaderboards') {
    await loadLeaderboards();
  }

  if (options.isPop && typeof options.scrollY === 'number') {
    requestAnimationFrame(() => {
      window.scrollTo(0, options.scrollY);
    });
  }
}

window.addEventListener('popstate', (e) => {
  const targetKey = location.pathname + location.search;
  const savedY = scrollPositions.get(targetKey) || 0;
  handleRoute({ isPop: true, scrollY: savedY });
});

document.addEventListener('DOMContentLoaded', async () => {
  configurePage();
  bindEvents();
  await Promise.all([loadStatus(), loadCatalog()]);
  await handleRoute({ isPop: false });
});
