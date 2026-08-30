const state = {
  page: 'overview',
  player: null,
  analytics: null,
  club: null,
  clubAnalytics: null,
  resources: null,
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
  calcPlan: null,
  calcReset: null,
  level: 'all',
  equipment: 'all',
  view: 'grid',
};

const ACCOUNT_CACHE_KEY = 'brawlbuddy_account_v3';
const CLUB_CACHE_KEY = 'brawlbuddy_club_v3';

const $ = (id) => document.getElementById(id);
const format = (value) => new Intl.NumberFormat().format(value ?? 0);

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
  if (path.startsWith('/calculator')) return 'calculator';
  if (path.startsWith('/resources')) return 'resources';
  if (path === '/' || path === '') return 'overview';
  return 'error';
}

function configurePage() {
  state.page = pageFromPath();
  const copy = {
    overview: ['BRAWL COMMAND CENTER', `Command HQ: <span id="welcome-name">${state.player?.name || 'Brawler'}</span>`, `Holding ${format(state.player?.trophies)} trophies across ${state.player?.brawlers?.length || 0} brawlers • ${format(state.analytics?.total_victories || 0)} victories • Next tier: ${format(state.analytics?.next_trophy_milestone || 0)} ★`],
    battles: ['ARENA TELEMETRY', 'Battle Log & Recreator', 'Inspect your 25 recent arena encounters with interactive 2D tactical breakdowns.'],
    events: ['LIVE ROTATION & MAPS', 'Event Rotation', 'Active modes, countdown timers, modifiers, and curated meta brawler picks.'],
    leaderboards: ['HALL OF CHAMPIONS', 'Leaderboards', 'Top 200 global & regional players and clubs with 1-click inspection.'],
    calculator: ['RESOURCE OPTIMIZER', 'Upgrade Calculator', 'Exact Supercell power level math synced to your local wallet & trophy reset calculations.'],
    brawlers: ['ROSTER LAB', 'Brawlers', 'Filter every exact power level and inspect your owned loadouts.'],
    club: ['🛡 ALLIANCE COMMAND CENTER', `Club Hub: ${state.club?.name || 'Alliance'}`, 'Inspect club roster, roles, trophy requirements, and syndicate power.'],
    resources: ['RESOURCE VAULT', 'Resources', 'Track the balances the public player API cannot see.'],
    detail: ['BRAWLER GUIDE', 'Brawler Details', 'Combat guidance, power journey, and account readiness.'],
    error: ['⚠️ ARENA OUTPOST', 'Lost in the Arena', 'Page or tag not found in the Brawl Stars database.'],
  }[state.page] || ['⚡ BRAWL COMMAND CENTER', 'Overview', 'Progression companion.'];

  setText('page-eyebrow', copy[0]);
  const title = $('page-title');
  if (title) {
    if (state.page === 'overview') {
      title.innerHTML = copy[1];
    } else {
      title.textContent = copy[1];
    }
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
  if (state.page === 'calculator') loadCalculator();
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
    const badge = $('api-status');
    if (badge) {
      badge.classList.add(status.live_api_configured ? 'live' : 'offline');
      const span = badge.querySelector('span');
      if (span) span.textContent = status.live_api_configured ? 'API token configured' : 'Demo mode';
    }
  } catch {
    const badge = $('api-status');
    if (badge) {
      const span = badge.querySelector('span');
      if (span) span.textContent = 'Service offline';
    }
  }
}

async function loadCatalog() {
  try {
    const [catPayload, equipPayload, buffiesPayload] = await Promise.all([
      request('/api/brawlers/catalog'),
      request('/api/equipment').catch(() => ({})),
      request('/api/buffies').catch(() => ({}))
    ]);
    state.catalog = catPayload.list || [];
    state.equipmentDb = equipPayload || {};
    state.buffiesDb = buffiesPayload || {};
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
        rarity: entry.rarity || 'common',
        owned: true,
      };
    }
    return {
      ...entry,
      owned: false,
      power: 0,
      rank: 0,
      trophies: 0,
      highest_trophies: 0,
      gadgets: [],
      star_powers: [],
      gears: [],
    };
  });

  const catalogIds = new Set((state.catalog || []).map((c) => c.id));
  (ownedBrawlers || []).forEach((owned) => {
    if (!catalogIds.has(owned.id)) {
      catalogMerged.push({
        id: owned.id,
        name: owned.name,
        rarity: 'common',
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
      if (state.page !== 'overview' && state.page !== 'brawlers' && state.page !== 'resources' && state.page !== 'battles' && state.page !== 'calculator') {
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
    if (state.page !== 'overview' && state.page !== 'brawlers' && state.page !== 'resources' && state.page !== 'battles' && state.page !== 'calculator') {
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
  const brawlerPrestige = state.analytics.brawler_prestige_level ?? (payload.player.brawlers || []).reduce((acc, b) => {
    const peak = Math.max(b.trophies || 0, b.highest_trophies || b.highestTrophies || 0);
    return acc + Math.floor(peak / 1000);
  }, 0);
  const isChamp = Boolean(payload.player.is_qualified_from_championship_challenge);

  // Dynamic Epic Topbar for Player (only when on overview)
  if (state.page === 'overview') {
    const title = $('page-title');
    if (title) {
      title.innerHTML = `Command HQ: <span id="welcome-name">${payload.player.name}</span>`;
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
    prestigeBadge.textContent = `⚡ ${(state.analytics.prestige_tier || 'CHAMPION').toUpperCase()}`;
  }

  // Update share dialog data
  setText('share-player-name', payload.player.name);
  setText('share-player-tag', payload.player.tag);
  setText('share-club-name', payload.player.club?.name || 'No Club');
  setText('share-trophies', `${format(payload.player.trophies)} ★`);
  setText('share-highest', `${format(payload.player.highest_trophies)} ★`);
  setText('share-victories', `${format(state.analytics.total_victories)} ⚔`);
  setText('share-brawlers', `${payload.player.brawlers.length} / ${state.catalog.length || 106}`);
  setImgSrc('share-avatar-img', brawlerMascotSrc, iconSrc);

  // Visual modules
  renderArchetypeStrip(state.analytics, payload.player);
  renderFlagshipLoadouts(state.analytics.top_loadouts || []);
  renderTrophyRoad(payload.player.trophies, payload.player.highest_trophies, state.analytics.next_trophy_milestone);
  renderRoleDonut(payload.player.brawlers);
  renderEquipmentVault(payload.player.brawlers);
  renderRankTiers(state.analytics, payload.player.brawlers.length);
  renderSpecialEvents(payload.player);
  renderBattleRecords(payload.player);
  renderClubCard(payload.player.club);
  renderOverviewMetrics();
  renderQuickBrawlers();
  renderBrawlers();
  loadResources();
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

  setText('hypercharge-ready-val', `${analytics.power_11_count || 0} Brawlers (L11)`);
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
    card.innerHTML = `
      <div class="flagship-head">
        <div class="flagship-visual">
          <img src="/assets/brawlers/thumbs/${brawler.id}.webp" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${brawler.id}.png'" alt="${brawler.name}">
          <span class="power-badge power-${brawler.power}">L${brawler.power}</span>
        </div>
        <div class="flagship-title">
          <strong>${brawler.name}</strong>
          <span>★ ${format(brawler.trophies)} trophies · Rank ${brawler.rank}</span>
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
  let gadgets = 0, starPowers = 0, gears = 0;
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

function renderRankTiers(analytics, totalBrawlers) {
  const total = totalBrawlers || 1;
  const tiers = [
    { label: 'Rank 35 (God Tier)', count: analytics.rank_35_count || 0, color: 'linear-gradient(90deg, #ff0077, #ff5964)' },
    { label: 'Rank 30–34 (Master)', count: analytics.rank_30_plus_count || 0, color: 'linear-gradient(90deg, #be8209, #ffd32e)' },
    { label: 'Rank 25–29 (Elite)', count: analytics.rank_25_plus_count || 0, color: 'linear-gradient(90deg, #168cf0, #00d5ff)' },
    { label: 'Rank 20–24 (Gold)', count: analytics.rank_20_plus_count || 0, color: 'linear-gradient(90deg, #2b9348, #55a630)' },
    { label: 'Rank 15–19 (Silver)', count: analytics.rank_15_plus_count || 0, color: 'linear-gradient(90deg, #5d7297, #8da4c4)' },
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

    const modeLabels = { brawlBall: '⚽ Brawl Ball', knockout: '☠ Knockout', gemGrab: '💎 Gem Grab', soloShowdown: '👑 Solo Showdown', wipeout: '⚔ Wipeout', hotZone: '🎯 Hot Zone' };
    const modeLabel = modeLabels[battle.mode] || battle.mode;

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
                <img src="/assets/brawlers/thumbs/${p.brawler.id}.webp" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
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
                <img src="/assets/brawlers/thumbs/${p.brawler.id}.webp" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
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
              <img src="/assets/brawlers/thumbs/${p.brawler.id}.webp" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
              <strong>${p.name}</strong>
            </div>
          `).join('')}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="battle-card-top">
        <div class="battle-card-mode">
          <span class="mode-badge">${modeLabel}</span>
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

  const modeIcons = { brawlBall: '⚽', gemGrab: '💎', knockout: '☠', soloShowdown: '👑', wipeout: '⚔', hotZone: '🎯' };
  setText('rec-match-mode', (battle.mode || '3v3').toUpperCase());
  setText('rec-match-map', battle.event?.map || 'Arena Map');
  setText('arena-objective-icon', modeIcons[battle.mode] || '★');
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
        <img src="/assets/brawlers/thumbs/${p.brawler.id}.webp" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
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
        <img src="/assets/brawlers/thumbs/${p.brawler.id}.webp" onerror="this.src='https://cdn.brawlify.com/brawlers/borders/${p.brawler.id}.png'" alt="${p.brawler.name}">
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
    const modeIcons = { brawlBall: '⚽', knockout: '☠', gemGrab: '💎', soloShowdown: '👑', wipeout: '⚔', hotZone: '🎯' };
    const icon = modeIcons[slot.event.mode] || '★';

    card.innerHTML = `
      <div class="event-card-banner">
        <img src="${slot.event.image_url || 'https://cdn.brawlify.com/maps/regular/15000001.png'}" onerror="this.src='/assets/player-mascot.png'" alt="${slot.event.map}">
        <div class="event-banner-overlay">
          <span class="event-mode-tag">${icon} ${(slot.event.mode || 'BRAWL').toUpperCase()}</span>
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
async function loadCalculator() {
  const tag = state.player?.tag || DEFAULT_PLAYER_TAG;
  const brawlers = state.ownedBrawlers || [];
  try {
    const plan = await request('/api/calculator/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_tag: tag, brawlers })
    });
    state.calcPlan = plan;

    const reset = await request('/api/calculator/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brawlers })
    });
    state.calcReset = reset;

    renderCalculator();
  } catch (error) {
    showNotice(`Upgrade calculator: ${error.message}`, 'error');
  }
}

function renderCalculator() {
  if (!state.calcPlan) return;

  setText('calc-wallet-coins', `${format(state.calcPlan.wallet.coins)} Coins`);
  setText('calc-wallet-pp', `${format(state.calcPlan.wallet.power_points)} PP`);
  setText('calc-total-coins-needed', `${format(state.calcPlan.total_coins_to_max_all)} Coins`);
  setText('calc-total-pp-needed', `${format(state.calcPlan.total_pp_to_max_all)} PP required to max roster`);
  setText('calc-brawlers-ready-count', `${state.calcPlan.brawlers_can_max_immediately} Brawlers`);
  setText('calc-affordable-badge', state.calcPlan.brawlers_can_max_immediately);

  // Roster table
  const tbody = $('calc-roster-tbody');
  if (tbody) {
    tbody.replaceChildren();
    (state.calcPlan.brawler_plans || []).forEach((b) => {
      const tr = document.createElement('tr');
      tr.className = 'roster-row';
      const statusHtml = b.current_power === 11
        ? '<span class="owned-status">MAX POWER 11 ✓</span>'
        : b.can_max_now
        ? '<span class="owned-status" style="background: #ffd32e; color: #6e4c00;">READY TO MAX NOW ★</span>'
        : b.can_upgrade_next_level
        ? '<span class="owned-status">NEXT LEVEL READY</span>'
        : '<span class="missing-status">INSUFFICIENT RESOURCES</span>';

      tr.innerHTML = `
        <td class="roster-name"><strong>${b.name}</strong></td>
        <td><span class="power-badge power-${b.current_power}">L${b.current_power}</span></td>
        <td class="resource-gold">${b.current_power === 11 ? '—' : `${format(b.coins_to_max)} C`}</td>
        <td class="resource-purple">${b.current_power === 11 ? '—' : `${format(b.pp_to_max)} PP`}</td>
        <td>${statusHtml}</td>
        <td style="text-align: right;">
          <a class="small-action" href="/brawlers/${b.id}">View Guide →</a>
        </td>
      `;
      tbody.append(tr);
    });
  }

  // Trophy Reset summary
  if (state.calcReset) {
    setText('reset-eligible-count', state.calcReset.eligible_brawlers_count);
    setText('reset-decay-count', `${format(state.calcReset.total_trophies_decay)} ★`);
    setText('reset-bling-earned', `✦ ${format(state.calcReset.total_projected_bling)} Bling`);

    const resetHolder = $('reset-brawlers-list');
    if (resetHolder) {
      resetHolder.replaceChildren();
      if (state.calcReset.decaying_brawlers.length === 0) {
        resetHolder.innerHTML = '<p class="equipment-empty">No brawlers above 1000 trophies. Push past 1000 to earn monthly Bling!</p>';
      } else {
        state.calcReset.decaying_brawlers.forEach((db) => {
          const item = document.createElement('div');
          item.className = 'reset-brawler-item';
          item.innerHTML = `
            <strong>${db.name}</strong>
            <span>${format(db.current_trophies)} ★ → 1000 ★ (Decay: -${db.trophies_lost})</span>
            <b class="resource-pink">✦ +${db.projected_bling} Bling</b>
          `;
          resetHolder.append(item);
        });
      }
    }
  }
}

// -------------------------------------------------------------
// CLUB HUB RENDERING
// -------------------------------------------------------------
function renderClub(payload) {
  if (!payload || !payload.club) return;
  state.club = payload.club;
  state.clubAnalytics = payload.analytics || {};

  const title = $('page-title');
  if (title) {
    title.innerHTML = `🛡 Alliance HQ: <span id="welcome-club-name">${payload.club.name}</span> <span id="welcome-club-tier" class="topbar-tier-pill">⚡ ${(state.clubAnalytics.prestige_tier || 'ALLIANCE').toUpperCase()}</span>`;
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
    { label: 'RANK 20+ BRAWLERS', value: state.analytics?.rank_20_plus_count ?? 0, desc: 'Ranked battle ready' },
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
    ? `/assets/brawlers/thumbs/${brawler.id}.webp`
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
    ? '/assets/brawlers/thumbs/16000108.webp'
    : `https://cdn.brawlify.com/brawlers/borders/${brawler.id}.png`;
  image.src = primarySrc;
  image.alt = `${brawler.name} official portrait`;
  image.loading = 'lazy';
  image.decoding = 'async';
  let step = 0;
  image.onerror = () => {
    step += 1;
    if (step === 1) {
      image.src = `/assets/brawlers/thumbs/${brawler.id}.webp`;
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
  [
    ['SP', brawler.star_powers || []],
    ['Gadget', brawler.gadgets || []],
    ['Gear', brawler.gears || []],
  ].forEach(([label, items]) => {
    const chip = document.createElement('span');
    chip.className = `equipment-chip ${items.length ? 'owned' : 'missing'}`;
    chip.textContent = `${label} ${items.length ? '✓' : '—'}`;
    chip.title = items.length ? items.map((item) => item.name).join(', ') : `No ${label} owned`;
    holder.append(chip);
  });
}

function cardFor(brawler) {
  const link = document.createElement('a'); link.className = 'brawler-card'; link.href = `/brawlers/${brawler.id}`;
  const visual = document.createElement('div'); visual.className = 'brawler-visual';
  const frameBox = document.createElement('div'); frameBox.className = 'brawler-frame-box';
  addImageWithFallback(frameBox, brawler, 'brawler-image');
  visual.append(frameBox);
  const badge = document.createElement('span'); badge.className = `power-badge ${brawler.owned ? `power-${brawler.power}` : 'locked'}`; badge.textContent = brawler.owned ? `L${brawler.power}` : 'LOCKED'; visual.append(badge);
  const copy = document.createElement('div'); copy.className = 'brawler-card-copy';
  const top = document.createElement('div'); top.className = 'brawler-name-row'; const name = document.createElement('strong'); name.textContent = brawler.name; const rank = document.createElement('span'); rank.textContent = brawler.owned ? `RANK ${brawler.rank}` : (brawler.rarity || 'Brawler').toUpperCase(); top.append(name, rank);
  const stats = document.createElement('div'); stats.className = 'brawler-stats'; const trophies = document.createElement('span'); trophies.textContent = brawler.owned ? `★ ${format(brawler.trophies)}` : 'Catalog brawler'; const best = document.createElement('span'); best.textContent = brawler.owned ? `Best ${format(brawler.highest_trophies)}` : 'Not owned'; stats.append(trophies, best);
  const equipment = document.createElement('div'); equipment.className = 'equipment-row'; compactEquipmentSummary(equipment, brawler);
  const open = document.createElement('div'); open.className = 'open-guide'; open.innerHTML = '<span>VIEW GUIDE</span><b>→</b>';
  copy.append(top, stats, equipment, open); link.append(visual, copy); return link;
}

function matchesEquipment(brawler) {
  const rules = {
    all: true,
    has_sp: (brawler.star_powers || []).length > 0,
    no_sp: (brawler.star_powers || []).length === 0,
    has_gadget: (brawler.gadgets || []).length > 0,
    no_gadget: (brawler.gadgets || []).length === 0,
    has_gear: (brawler.gears || []).length > 0,
    no_gear: (brawler.gears || []).length === 0,
  };
  return rules[state.equipment];
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
    let matchesEquip = true;
    if (equipmentFilter === 'has_sp') matchesEquip = (brawler.star_powers || []).length > 0;
    else if (equipmentFilter === 'no_sp') matchesEquip = (brawler.star_powers || []).length === 0;
    else if (equipmentFilter === 'has_gadget') matchesEquip = (brawler.gadgets || []).length > 0;
    else if (equipmentFilter === 'no_gadget') matchesEquip = (brawler.gadgets || []).length === 0;
    else if (equipmentFilter === 'has_gear') matchesEquip = (brawler.gears || []).length > 0;
    else if (equipmentFilter === 'no_gear') matchesEquip = (brawler.gears || []).length === 0;
    else if (equipmentFilter === 'has_hypercharge') matchesEquip = (brawler.power === 11);
    else if (equipmentFilter === 'no_hypercharge') matchesEquip = (brawler.power !== 11);

    return matchesQuery && matchesLevel && matchesEquip;
  });

  brawlers.sort((a, b) => {
    if (sort === 'name') return (a.name || '').localeCompare(b.name || '');
    if (sort === 'trophies') return (b.trophies || 0) - (a.trophies || 0) || (a.name || '').localeCompare(b.name || '');
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
  }
  const empty = $('brawler-empty');
  if (empty) empty.classList.toggle('hidden', brawlers.length > 0);
}

async function loadResources() {
  if (!state.player) return;
  try {
    state.resources = await request(`/api/resources/${encodeURIComponent(state.player.tag)}`);
    renderResources();
  } catch (error) { showNotice(`Account loaded, but the local wallet could not be read: ${error.message}`, 'error'); }
}

function renderResources() {
  const resources = state.resources || {coins: 0, power_points: 0, gems: 0, credits: 0, bling: 0};
  const map = {coins: resources.coins, 'power-points': resources.power_points, gems: resources.gems, credits: resources.credits, bling: resources.bling};
  Object.entries(map).forEach(([key, value]) => {
    setText(`overview-${key}`, format(value));
    setText(`balance-${key}`, format(value));
    const input = $(key);
    if (input) input.value = value;
  });
}

async function saveResources(event) {
  event.preventDefault();
  const payload = {
    player_tag: state.player.tag,
    coins: Number($('coins')?.value || 0),
    power_points: Number($('power-points')?.value || 0),
    gems: Number($('gems')?.value || 0),
    credits: Number($('credits')?.value || 0),
    bling: Number($('bling')?.value || 0),
    source: 'USER_INPUT'
  };
  const button = $('resource-form')?.querySelector('button');
  if (button) {
    button.disabled = true;
    button.textContent = 'SAVING…';
  }
  try {
    state.resources = await request(`/api/resources/${encodeURIComponent(state.player.tag)}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    renderResources();
    if (button) {
      button.classList.add('saved');
      button.textContent = 'WALLET SAVED ✓';
      setTimeout(() => {
        button.classList.remove('saved');
        button.innerHTML = 'SAVE MY WALLET <span>→</span>';
      }, 1800);
    }
  } catch (error) {
    showNotice(error.message, 'error');
    if (button) button.innerHTML = 'SAVE MY WALLET <span>→</span>';
  } finally {
    if (button) button.disabled = false;
  }
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
      title: build.gadget ? `Unlock ${build.gadget}` : 'Unlock a Gadget',
      reason: build.gadget ? `The curated guide recommends ${build.gadget} as the primary active utility tool.` : 'No owned Gadget is recorded in the player response.',
      tag: 'LOADOUT GAP'
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
      title: build.star_power ? `Unlock ${build.star_power}` : 'Unlock a Star Power',
      reason: build.star_power ? `The curated guide recommends ${build.star_power} as the default permanent passive bonus.` : 'No owned Star Power is recorded in the player response.',
      tag: 'LOADOUT GAP'
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
    if (guide.hypercharge && guide.hypercharge.released !== false && guide.hypercharge.name?.toLowerCase() !== 'unreleased') {
      steps.push({
        title: `Maximize Hypercharge (${guide.hypercharge.name})`,
        reason: 'Leverage hypercharge stat boosts (+damage, speed, shield) for decisive team wipes.',
        tag: 'HYPER'
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

function renderGuideProfile(guide) {
  const panel = $('guide-profile-panel');
  if (!panel) return;
  const hasProfile = Array.isArray(guide.max_stats) && guide.max_stats.length > 0;
  panel.classList.toggle('hidden', !hasProfile);
  if (!hasProfile) return;

  // Stats will be rendered by renderPowerLadder after it determines the default level.
  // But if guide-only (no brawler context), render at max (level 11) right away.
  renderCombatStats(guide.max_stats, 11);

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
    
    const items = [
      { label: 'Gadget', value: build.gadget, badgeClass: 'build-gadget' },
      { label: 'Star Power', value: build.star_power, badgeClass: 'build-star-power' },
      { label: 'Gears', value: build.gears?.join(' + '), badgeClass: 'build-gear' }
    ];

    items.forEach(({ label, value, badgeClass }) => {
      if (!value) return;
      const row = document.createElement('div');
      row.className = `build-spec-row ${badgeClass}`;
      row.innerHTML = `
        <div class="build-spec-label">
          <span class="build-spec-dot"></span>
          <span>${label}</span>
        </div>
        <strong class="build-spec-value">${value}</strong>
      `;
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
    const modeIcons = {
      'heist': '🎯',
      'gem grab': '💎',
      'brawl ball': '⚽',
      'showdown': '💀',
      'solo showdown': '💀',
      'duo showdown': '👥',
      'bounty': '🌟',
      'knockout': '🥊',
      'hot zone': '🚩',
      'wipeout': '💥',
      'duels': '⚔️',
      'siege': '⚙️',
      'takedown': '🤖',
      'lone star': '⭐',
      'basket brawl': '🏀',
      'volley brawl': '🏐',
      'payload': '🚛'
    };
    (guide.mode_fit || []).forEach((mode) => {
      const chip = document.createElement('span');
      chip.className = 'mode-chip';
      const mNorm = mode.toLowerCase();
      const icon = Object.entries(modeIcons).find(([k]) => mNorm.includes(k))?.[1] || '🏆';
      chip.innerHTML = `<span class="mode-icon">${icon}</span> <span>${mode}</span>`;
      modes.append(chip);
    });
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
      brawler = { ...cat, owned: false, power: 0, rank: 0, trophies: 0, highest_trophies: 0, gadgets: [], star_powers: [], gears: [] };
    }
  }
  if (!brawler) {
    brawler = { id, name: 'Brawler', rarity: 'common', owned: false, power: 0, rank: 0, trophies: 0, highest_trophies: 0, gadgets: [], star_powers: [], gears: [] };
  }
  hideNotice();
  let guide = {};
  try { guide = await request(`/api/guides/${id}`); } catch { guide = {}; }
  setText('page-title', `${brawler.name} guide`);
  setText('detail-name', brawler.name);
  
  const rawRarity = (guide.rarity || brawler.rarity || 'common').toLowerCase().replace(/\s+/g, '_');
  const rarityEl = $('detail-rarity');
  if (rarityEl) {
    rarityEl.className = `rarity-badge ${rawRarity}`;
    rarityEl.textContent = (guide.rarity || brawler.rarity || 'BRAWLER').toUpperCase();
  }

  const roleIcons = {
    'tank': '🛡',
    'damage dealer': '⚔',
    'damage_dealer': '⚔',
    'assassin': '🗡',
    'marksman': '🎯',
    'support': '💖',
    'controller': '🌀',
    'artillery': '💣',
  };
  const bClass = guide.class || brawler.class || (brawler.owned ? 'Damage Dealer' : 'Brawler');
  const roleIcon = roleIcons[bClass.toLowerCase().trim()] || '★';
  const classEl = $('detail-class');
  if (classEl) {
    classEl.className = `class-badge ${bClass.toLowerCase().replace(/\s+/g, '_')}`;
    classEl.innerHTML = `<i>${roleIcon}</i> ${bClass.toUpperCase()}`;
  }

  const statusEl = $('detail-account-status');
  if (statusEl) {
    statusEl.textContent = brawler.owned ? 'OWNED IN ACCOUNT' : 'CATALOG PREVIEW';
    statusEl.className = `data-label ${brawler.owned ? '' : 'demo'}`;
  }

  setText('detail-intro', guide.intro || (brawler.owned ? `${brawler.name} is Power ${brawler.power} on this account. Progression and owned equipment below come from the loaded player data.` : `${brawler.name} is part of the 106-brawler catalog but is not present in this account. Use the level journey below to preview future progression.`));
  const brawlerPeak = Math.max(brawler.trophies || 0, brawler.highest_trophies || brawler.highestTrophies || 0);
  const brawlerPrestige = brawler.owned ? Math.floor(brawlerPeak / 1000) : 0;
  setText('detail-power', brawler.owned ? brawler.power : '—');
  setText('detail-trophies', brawler.owned ? format(brawler.trophies) : '—');
  setText('detail-prestige', brawler.owned ? brawlerPrestige : '—');
  setText('detail-rank', brawler.owned ? (brawler.rank || '—') : '—');
  setText('attack-name', guide.attack?.name || 'Main attack');
  setText('attack-description', guide.attack?.description || 'Detailed combat notes are not curated yet.');
  setText('super-name', guide.super?.name || 'Super');
  setText('super-description', guide.super?.description || 'Detailed combat notes are not curated yet.');

  const portraitEl = $('detail-portrait-icon');
  if (portraitEl) {
    portraitEl.src = (brawler.id === 16000108)
      ? '/assets/brawlers/thumbs/16000108.webp'
      : `https://cdn.brawlify.com/brawlers/borders/${brawler.id}.png`;
    portraitEl.alt = `${brawler.name} official portrait`;
    portraitEl.onerror = () => {
      portraitEl.src = `/assets/brawlers/thumbs/${brawler.id}.webp`;
    };
  }

  const imgEl = $('detail-image');
  if (imgEl) {
    imgEl.src = (brawler.id === 16000038 && !brawler.owned) ? '/assets/surge-guide-art.png' : `/assets/brawlers/${brawler.id}.png`;
    imgEl.alt = `${brawler.name} official artwork`;
    imgEl.onerror = () => {
      imgEl.onerror = () => {
        imgEl.src = `/assets/brawlers/thumbs/${brawler.id}.webp`;
      };
      imgEl.src = `https://cdn.brawlify.com/brawlers/borders/${brawler.id}.png`;
    };
  }

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

  setText('readiness-power-val', brawler.owned ? `LVL ${brawler.power}` : 'LOCKED');
  setText('readiness-gadget-val', brawler.owned ? `${brawler.gadgets.length}/${(guide.gadgets || []).length || 2}` : '0/2');
  setText('readiness-star-val', brawler.owned ? `${brawler.star_powers.length}/${(guide.star_powers || []).length || 2}` : '0/2');
  setText('readiness-gear-val', brawler.owned ? `${brawler.gears.length}/${(guide.gears || []).length || 5}` : '0/5');

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

  renderGuideProfile(guide);
  renderPowerLadder(brawler.owned ? brawler.power : 0, guide);
  renderEquipment('gadget-list', guide.gadgets || [], brawler.gadgets, brawler.owned ? 'No Gadget data recorded.' : 'Unlock this brawler to track Gadgets.', 'gadget', brawler);
  renderEquipment('star-power-list', guide.star_powers || [], brawler.star_powers, brawler.owned ? 'No Star Power data recorded.' : 'Unlock this brawler to track Star Powers.', 'star_power', brawler);
  const gearGuide = (guide.gears || []).map((name) => ({name, description: 'Available Gear option; confirm current unlock requirements in-game.'}));
  renderEquipment('gear-list', gearGuide, brawler.gears, brawler.owned ? 'No Gear data recorded.' : 'Unlock this brawler to track Gears.', 'gear', brawler);
  renderHypercharge('hypercharge-list', guide.hypercharge, brawler);

  const sources = $('guide-sources');
  if (sources) {
    sources.replaceChildren();
    const note = document.createElement('p');
    note.textContent = 'All information referenced by BrawlBuddy is sourced from the Brawl Stars Wiki. Last updated on August 29, 2026.';
    note.style.textAlign = 'center';
    sources.append(note);
  }
}

function getBuffieEffect(brawlerName, abilityName, type) {
  const normName = (abilityName || '').toUpperCase();
  const bName = (brawlerName || '').toUpperCase();

  // Buzz specific
  if (normName.includes('RESERVE BUOY')) {
    return 'Reduces Super activation latency and increases grapple launch velocity by +15%.';
  }
  if (normName.includes('X-RAY SHADES') || normName.includes('X-RAY-SHADES')) {
    return 'Extends bush visibility reveal radius by +2.0 tiles and grants +10% bonus movement speed in bushes.';
  }
  if (normName.includes('ENHANCED EYES')) {
    return 'Passive charging aura radius expanded by +12% with accelerated charge rate ticks.';
  }
  if (normName.includes('TOUGHER TORPEDO')) {
    return 'Guarantees +0.5s minimum stun duration and grants a brief 15% damage shield upon arrival.';
  }
  if (normName.includes('BUZZZILLA')) {
    return '+2.5s Hypercharge duration extension and +10% bonus damage shield during active overdrive.';
  }

  // Shelly specific
  if (normName.includes('FAST FORWARD')) return 'Dash distance +1.5 tiles with an instant reload of 0.5 ammo.';
  if (normName.includes('CLAY PIGEONS')) return 'Increases shotgun projectile velocity by +25% for 6.0 seconds.';
  if (normName.includes('SHELL SHOCK')) return 'Increases Super slow duration by +1.5 seconds.';
  if (normName.includes('BAND-AID')) return 'Band-Aid cooldown recovery timer accelerated by 3.5 seconds.';
  if (normName.includes('DOUBLE BARREL')) return '+2.5s Overdrive duration and +15% Super projectile spread concentration.';

  // Colt specific
  if (normName.includes('SPEED BOOTS') || normName.includes('SLICK BOOTS')) return 'Grants an extra +5% base movement speed and instant turning responsiveness.';
  if (normName.includes('MAGNUM SPECIAL')) return 'Increases bullet velocity by +12% and expands attack range by +1.0 tile.';
  if (normName.includes('SILVER BULLET')) return 'Increases projectile size and piercing impact damage against obstacles.';
  if (normName.includes('DUAL WIELDING')) return '+2.5s Overdrive duration with increased bullet spread density.';

  // Bull specific
  if (normName.includes('T-BONE')) return 'Heal value boosted by +20% and grants instant 10% damage shield for 2s.';
  if (normName.includes('STOMPER')) return 'Expands stomper slow shockwave radius by +1.5 tiles.';
  if (normName.includes('BERSERKER')) return 'Reload speed doubled when health drops below 50% instead of 40%.';
  if (normName.includes('TOUGH GUY')) return 'Shield activation threshold increased to 45% remaining health.';

  // Dynamic context generator for all other brawlers
  if (type === 'gadget') {
    return `Augments ${abilityName} with +15% enhanced activation efficiency and tactical responsiveness.`;
  }
  if (type === 'star_power') {
    return `Amplifies ${abilityName} passive scaling by +20% and reinforces combat survivability.`;
  }
  if (type === 'hypercharge') {
    return `Extends active Hypercharge overdrive state by +2.5s with amplified stat multipliers.`;
  }
  return 'Enhanced combat performance modifier.';
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
  
  emblemWrap.innerHTML = `
    <div class="official-hypercharge-emblem" title="${hypercharge?.name || 'Hypercharge'}">
      <img src="/assets/hypercharge_icon.png?v=12" alt="${hypercharge?.name || 'Hypercharge'}" class="ability-icon-img hyper-icon-img">
    </div>
  `;
  return emblemWrap;
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

function isBuffieReleased(brawlerName) {
  if (!brawlerName) return false;
  const bNorm = normalizeKey(brawlerName);
  const released = state.buffiesDb?.released_brawlers || [
    'SHELLY', 'COLT', 'SPIKE', 'MORTIS', 'FRANK', 'EMZ', 'BULL', 'CROW', 'BIBI', 
    'NITA', 'BO', 'LEON', 'COLETTE', 'EDGAR', 'GRIFF', 'RICO', 'BROCK', '8BIT', 
    '8-BIT', '8 BIT', 'MAX', 'SURGE', 'MEG'
  ];
  return released.some((r) => normalizeKey(r) === bNorm);
}

function getBuffieImageUrl(brawlerName, abilityType) {
  if (!state.buffiesDb || !brawlerName) return null;
  const bNorm = normalizeKey(brawlerName);
  
  for (const trio of (state.buffiesDb.trios || [])) {
    for (const b of (trio.brawlers || [])) {
      if (normalizeKey(b.name) === bNorm) {
        let fileKey = b.gadget_img_file;
        if (abilityType === 'star_power') fileKey = b.star_img_file;
        else if (abilityType === 'hypercharge') fileKey = b.hyper_img_file;
        
        if (fileKey && state.buffiesDb.image_urls && state.buffiesDb.image_urls[fileKey]) {
          return state.buffiesDb.image_urls[fileKey];
        }
      }
    }
  }
  return null;
}

function renderHypercharge(targetId, hypercharge, brawler) {
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

  // Power 11 = Hypercharge unlocked (eligible to use)
  const isP11 = brawler.owned && brawler.power === 11;
  const isOwned = brawler.owned;

  const row = document.createElement('article');
  if (isP11) {
    row.style.borderColor = '#d4a3ff';
    row.style.background = 'linear-gradient(135deg, #fdfaff 0%, #f6ecff 100%)';
  }

  // Header row with integrated Hypercharge emblem
  const header = document.createElement('div');
  header.className = 'ability-header-row';

  const titleWrap = document.createElement('div');
  titleWrap.className = 'ability-title-wrap';

  // Crisp, glowing official vector Hypercharge emblem
  const emblemWrap = createHyperchargeEmblem(brawler, hypercharge);

  const name = document.createElement('strong');
  name.textContent = hypercharge.name;

  titleWrap.append(emblemWrap, name);

  const status = document.createElement('span');
  if (!isOwned) {
    status.className = 'hypercharge-locked-status';
    status.textContent = 'NOT OWNED';
  } else if (isP11) {
    status.className = 'hypercharge-owned-status';
    status.textContent = '⚡ UNLOCKED';
  } else {
    status.className = 'hypercharge-locked-status';
    status.textContent = `🔒 NEED L11 (${brawler.power || 0}/11)`;
  }

  header.append(titleWrap, status);

  // Description
  const description = document.createElement('p');
  description.textContent = hypercharge.description || 'Hypercharge ability for this brawler.';

  // Integrated Buffie Subfield for Hypercharge
  const buffieReleased = isBuffieReleased(brawler.name);
  const buffieImgUrl = getBuffieImageUrl(brawler.name, 'hypercharge');
  const hasHcBuffieInInventory = brawler?.buffies 
    ? brawler.buffies.some((buf) => normalizeKey(buf) === normalizeKey(hypercharge.name) || normalizeKey(buf) === 'hypercharge' || normalizeKey(buf) === 'hyper')
    : (brawler?.owned && buffieReleased);

  const buffieBox = document.createElement('div');

  const buffieIconHtml = `<img src="${buffieImgUrl || '/assets/buffie_icon.webp'}" alt="Buffie" class="buffie-fandom-icon" onerror="this.src='/assets/buffie_icon.webp';">`;

  if (!buffieReleased) {
    buffieBox.className = 'buffie-subfield hypercharge-buffie disabled-buffie';
    buffieBox.innerHTML = `
      <div class="buffie-header-row">
        <div class="buffie-badge-wrap">
          <div class="buffie-icon-badge disabled-buffie-badge">
            ${buffieIconHtml}
          </div>
          <span class="buffie-tag">HYPERCHARGE BUFFIE</span>
        </div>
        <span class="buffie-rank-pill unreleased-rank-pill">⏳ COMING SOON</span>
      </div>
      <p class="buffie-effect disabled-effect">Supercell has not yet released Buffies for ${brawler.name || 'this brawler'}.</p>
    `;
  } else if (isP11) {
    buffieBox.className = 'buffie-subfield hypercharge-buffie active-buffie';
    buffieBox.innerHTML = `
      <div class="buffie-header-row">
        <div class="buffie-badge-wrap">
          <div class="buffie-icon-badge hypercharge-buffie-badge">
            ${buffieIconHtml}
          </div>
          <span class="buffie-tag">HYPERCHARGE BUFFIE</span>
        </div>
        <span class="buffie-rank-pill hypercharge-rank-pill"><img src="/assets/buffie_icon.png?v=5" alt="" class="buffie-rank-symbol"> ACTIVE</span>
      </div>
      <p class="buffie-effect">${getBuffieEffect(brawler.name, hypercharge.name, 'hypercharge')}</p>
    `;
  } else if (hasHcBuffieInInventory) {
    buffieBox.className = 'buffie-subfield hypercharge-buffie inventory-buffie';
    buffieBox.innerHTML = `
      <div class="buffie-header-row">
        <div class="buffie-badge-wrap">
          <div class="buffie-icon-badge disabled-buffie-badge">
            ${buffieIconHtml}
          </div>
          <span class="buffie-tag">HYPERCHARGE BUFFIE</span>
        </div>
        <span class="buffie-rank-pill inventory-rank-pill"><img src="/assets/buffie_icon.png?v=5" alt="" class="buffie-rank-symbol"> LOCKED 🔒 REQUIRES POWER 11</span>
      </div>
      <p class="buffie-effect inventory-effect">${getBuffieEffect(brawler.name, hypercharge.name, 'hypercharge')}</p>
    `;
  } else {
    buffieBox.className = 'buffie-subfield hypercharge-buffie disabled-buffie';
    buffieBox.innerHTML = `
      <div class="buffie-header-row">
        <div class="buffie-badge-wrap">
          <div class="buffie-icon-badge disabled-buffie-badge">
            ${buffieIconHtml}
          </div>
          <span class="buffie-tag">HYPERCHARGE BUFFIE</span>
        </div>
        <span class="buffie-rank-pill disabled-rank-pill">🔒 LOCKED</span>
      </div>
      <p class="buffie-effect disabled-effect">${getBuffieEffect(brawler.name, hypercharge.name, 'hypercharge')}</p>
    `;
  }

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
    else if (level === 9) unlockBadge = '<small class="milestone-badge">STAR ★</small>';
    else if (level === 10) unlockBadge = '<small class="milestone-badge">GEAR ◆</small>';
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


function normalizeKey(str) {
  return String(str || '').toLowerCase().replace(/[^a-z0-9]/g, '');
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
    if (type === 'gadget') return `https://cdn.brawlify.com/gadgets/regular/${item.id}.png`;
    if (type === 'star_power') return `https://cdn.brawlify.com/star-powers/regular/${item.id}.png`;
    if (type === 'gear') return `https://cdn.brawlify.com/gears/regular/${item.id}.png`;
  }

  // 3. Universal and Archetype Gear mappings
  if (type === 'gear') {
    if (rawName.includes('DAMAGE')) return 'https://cdn.brawlify.com/gears/regular/62000000.png';
    if (rawName.includes('HEALTH')) return 'https://cdn.brawlify.com/gears/regular/62000001.png';
    if (rawName.includes('SHIELD')) return 'https://cdn.brawlify.com/gears/regular/62000002.png';
    if (rawName.includes('SPEED') && !rawName.includes('RELOAD')) return 'https://cdn.brawlify.com/gears/regular/62000003.png';
    if (rawName.includes('VISION')) return 'https://cdn.brawlify.com/gears/regular/62000004.png';
    if (rawName.includes('GADGET') || rawName.includes('PLUS') || rawName.includes('COOLDOWN')) return 'https://cdn.brawlify.com/gears/regular/62000005.png';
    if (rawName.includes('SUPER') && (rawName.includes('CHARGE') || rawName.includes('TURRET'))) return 'https://cdn.brawlify.com/gears/regular/62000006.png';
    if (rawName.includes('RELOAD')) return 'https://cdn.brawlify.com/gears/regular/62000007.png';
    if (rawName.includes('PET')) return 'https://cdn.brawlify.com/gears/regular/62000008.png';
    return 'https://cdn.brawlify.com/gears/regular/62000000.png';
  }

  return null;
}

function renderEquipment(targetId, available, owned, emptyMessage, type, brawler) {
  const holder = $(targetId);
  if (!holder) return;
  holder.replaceChildren();

  // Set of normalized owned equipment keys and IDs from player API
  const ownedKeys = new Set((owned || []).map((item) => normalizeKey(item.name || item)));
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

  combined.forEach((item) => {
    const row = document.createElement('article');

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
      iconImg.src = imgUrl;
      iconImg.alt = item.name;
      iconImg.loading = 'lazy';
      
      const fallbackBadge = document.createElement('span');
      fallbackBadge.className = `ability-emblem ${type}-emblem`;
      fallbackBadge.textContent = type === 'gadget' ? 'G' : type === 'star_power' ? '★' : '◆';
      fallbackBadge.style.display = 'none';

      iconImg.onerror = () => {
        iconImg.style.display = 'none';
        fallbackBadge.style.display = 'grid';
      };

      emblemWrap.append(iconImg, fallbackBadge);
    } else {
      const emblem = document.createElement('span');
      emblem.className = `ability-emblem ${type}-emblem`;
      emblem.textContent = type === 'gadget' ? 'G' : type === 'star_power' ? '★' : '◆';
      emblemWrap.append(emblem);
    }

    const name = document.createElement('strong');
    name.textContent = item.name;

    titleWrap.append(emblemWrap, name);

    const isOwned = ownedKeys.has(normalizeKey(item.name)) || (item.id && ownedIds.has(String(item.id)));
    const status = document.createElement('span');
    status.className = isOwned ? 'owned-status' : 'missing-status';
    status.textContent = isOwned ? 'OWNED ✓' : 'NOT OWNED';

    header.append(titleWrap, status);

    // Ability Description
    const description = document.createElement('p');
    description.textContent = item.description || 'Equipment recorded for this brawler.';

    row.append(header, description);

    // Integrated Buffie Subfield for Gadgets and Star Powers
    if (type === 'gadget' || type === 'star_power') {
      const brawlerName = brawler?.name || 'Brawler';
      const buffieReleased = isBuffieReleased(brawlerName);
      const buffieImgUrl = getBuffieImageUrl(brawlerName, type);
      const hasBuffieInInventory = brawler?.buffies 
        ? brawler.buffies.some((buf) => normalizeKey(buf) === normalizeKey(item.name))
        : (brawler?.owned && buffieReleased);

      const buffieBox = document.createElement('div');

      const buffieIconHtml = `<img src="${buffieImgUrl || '/assets/buffie_icon.webp'}" alt="Buffie" class="buffie-fandom-icon" onerror="this.src='/assets/buffie_icon.webp';">`;

      if (!buffieReleased) {
        buffieBox.className = `buffie-subfield ${type}-buffie disabled-buffie`;
        buffieBox.innerHTML = `
          <div class="buffie-header-row">
            <div class="buffie-badge-wrap">
              <div class="buffie-icon-badge disabled-buffie-badge">
                ${buffieIconHtml}
              </div>
              <span class="buffie-tag">${type === 'gadget' ? 'GADGET BUFFIE' : 'STAR POWER BUFFIE'}</span>
            </div>
            <span class="buffie-rank-pill unreleased-rank-pill">⏳ COMING SOON</span>
          </div>
          <p class="buffie-effect disabled-effect">Supercell has not yet released Buffies for ${brawlerName}.</p>
        `;
      } else if (isOwned) {
        buffieBox.className = `buffie-subfield ${type}-buffie active-buffie`;
        buffieBox.innerHTML = `
          <div class="buffie-header-row">
            <div class="buffie-badge-wrap">
              <div class="buffie-icon-badge ${type}-buffie-badge">
                ${buffieIconHtml}
              </div>
              <span class="buffie-tag">${type === 'gadget' ? 'GADGET BUFFIE' : 'STAR POWER BUFFIE'}</span>
            </div>
            <span class="buffie-rank-pill ${type}-rank-pill"><img src="/assets/buffie_icon.png?v=5" alt="" class="buffie-rank-symbol"> ACTIVE</span>
          </div>
          <p class="buffie-effect">${getBuffieEffect(brawlerName, item.name, type)}</p>
        `;
      } else if (hasBuffieInInventory) {
        buffieBox.className = `buffie-subfield ${type}-buffie inventory-buffie`;
        buffieBox.innerHTML = `
          <div class="buffie-header-row">
            <div class="buffie-badge-wrap">
              <div class="buffie-icon-badge disabled-buffie-badge">
                ${buffieIconHtml}
              </div>
              <span class="buffie-tag">${type === 'gadget' ? 'GADGET BUFFIE' : 'STAR POWER BUFFIE'}</span>
            </div>
            <span class="buffie-rank-pill inventory-rank-pill"><img src="/assets/buffie_icon.png?v=5" alt="" class="buffie-rank-symbol"> LOCKED 🔒 REQUIRES ${type === 'gadget' ? 'GADGET' : 'STAR POWER'}</span>
          </div>
          <p class="buffie-effect inventory-effect">${getBuffieEffect(brawlerName, item.name, type)}</p>
        `;
      } else {
        buffieBox.className = `buffie-subfield ${type}-buffie disabled-buffie`;
        buffieBox.innerHTML = `
          <div class="buffie-header-row">
            <div class="buffie-badge-wrap">
              <div class="buffie-icon-badge disabled-buffie-badge">
                ${buffieIconHtml}
              </div>
              <span class="buffie-tag">${type === 'gadget' ? 'GADGET BUFFIE' : 'STAR POWER BUFFIE'}</span>
            </div>
            <span class="buffie-rank-pill disabled-rank-pill">🔒 LOCKED</span>
          </div>
          <p class="buffie-effect disabled-effect">${getBuffieEffect(brawlerName, item.name, type)}</p>
        `;
      }
      row.append(buffieBox);
    }

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
  $('share-close-btn')?.addEventListener('click', () => $('share-dialog')?.close());

  $('share-card-btn')?.addEventListener('click', () => $('share-dialog')?.showModal());

  $('copy-share-btn')?.addEventListener('click', (e) => {
    const p = state.player;
    if (!p) return;
    const text = `🏆 BrawlBuddy Brawler Summary: ${p.name} (${p.tag})\n★ Trophies: ${format(p.trophies)} (Peak: ${format(p.highest_trophies)})\n⚔ Victories: ${format(state.analytics?.total_victories || 0)}\n🛡 Club: ${p.club?.name || 'None'}\n⚡ Tier: ${state.analytics?.prestige_tier || 'Mythic Champion'}`;
    navigator.clipboard.writeText(text);
    const btn = e.currentTarget;
    btn.textContent = 'Summary Copied to Clipboard! ✓';
    setTimeout(() => { btn.textContent = '📋 Copy Brawler Summary'; }, 1800);
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
    if (state.page !== 'overview' && state.page !== 'brawlers' && state.page !== 'resources' && state.page !== 'battles' && state.page !== 'calculator') {
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
  $('resource-form')?.addEventListener('submit', saveResources);

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
  } else if (state.page === 'calculator') {
    await loadCalculator();
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
