/* Charts and exploration for the server-calculated account snapshot */
(() => {
  const UI = DashboardUI;
  const colors = UI.palette;
  const esc = (value) => escapeMarkup(formatUiCopy(value));
  const num = (value) => value == null ? '—' : new Intl.NumberFormat(undefined, {maximumFractionDigits: 2}).format(value);
  const pct = (value) => value == null ? '—' : `${num(value)}%`;
  let data = null;
  let activeKey = '';
  let loadedAt = 0;
  let pending = null;
  let controller = null;
  let trophySort = 'trophies';
  let rosterSort = 'trophies';
  let rosterSearch = '';
  let sectionObserver = null;

  const sections = {
    'ov-collection': {art:'brawl-stars-symbol-official.png', label:'ROSTER LAB', tone:'blue'},
    'ov-trophies': {art:'icon_trophy.png', label:'TROPHY ROAD', tone:'gold'},
    'ov-equipment': {art:'equipment', label:'COMBAT KIT', tone:'purple'},
    'ov-competitive': {art:'wins', label:'PLAYER RECORDS', tone:'purple'},
    'ov-recent': {art:'battle', label:'ARENA REPORT', tone:'pink'},
    'ov-context': {art:'team', label:'BRAWL TOGETHER', tone:'blue'},
    'ov-goals': {art:'currencies/coins.png', label:'YOUR NEXT MOVE', tone:'green'},
  };
  const cardArtwork = {
    'Power distribution':'power', 'Collection completion':'collection', 'Combat roles':'battle',
    'Rarity mix':'collection', 'Permanent Prestige':'prestige', 'Your next account target':'target',
    'Trophy distribution':'trophy', 'Your top 10 brawlers':'trophy', 'Power versus trophies':'chart',
    'Lifetime victory composition':'wins', 'Trophy concentration':'chart', 'Win streak records':'streak',
    'Inventory coverage':'equipment', 'Hypercharge inventory':'hypercharge', 'Buffies by category':'buffie',
    'Ranked rating comparison':'wins', 'Account records':'records', 'Recent outcomes':'wins',
    'Modes played':'battle', 'Brawlers played':'collection', 'Your recent run':'streak',
    'Trophy movement in the sample':'trophy', 'Your club':'team', 'Live arena rotation':'battle',
    'What remains to complete your chosen builds':'coins', 'Build readiness':'build',
    'Readiness distribution':'chart', 'Closest trophy milestones':'prestige',
    'Six practical next steps':'target', 'Your resource balances':'coins', 'Recent performance':'chart',
  };
  const metricArtwork = {
    'COLLECTION':'collection', 'AVERAGE POWER':'power', 'POWER 11':'power',
    'EQUIPPED':'equipment', 'BUILD READY':'build', 'BEST WIN STREAK':'streak',
  };
  const currencyArtwork = {'Coins':'currencies/coins.png', 'Power Points':'currencies/power-points.png',
    'Direct Buffie Gems':'currencies/gems.png', 'Gems':'currencies/gems.png'};
  const art = (asset, className = 'ov-art') => asset.includes('.') ? UI.image(asset,className) : UI.icon(asset,className);

  function rankAsset(name) {
    const key = normalizeKey(name);
    const league = ['bronze','silver','gold','diamond','mythic','legendary','masters','pro'].find((value) => key.startsWith(value));
    return league ? `ranked/${league}.png` : null;
  }

  function empty(message = 'This information was not returned for this account') {
    return UI.empty(message);
  }

  function head(number, id, title, subtitle, badge = 'Calculated') {
    const section = sections[id];
    return `<section class="ov-group ov-tone-${section.tone}" aria-labelledby="${id}-title"><div class="ov-section-heading" id="${id}"><span class="ov-section-emblem">${art(section.art)}<small>${number}</small></span><div class="ov-section-copy"><span class="ov-section-kicker">${section.label}</span><h2 id="${id}-title">${title}</h2><p>${subtitle}</p></div><span class="ov-source">${badge}</span></div>`;
  }

  function card(title, body, note = '', span = 6, kicker = '') {
    const key = cardArtwork[title];
    return UI.card({title,body,note,span,kicker,symbol:key ? art(key) : ''});
  }

  function metric(label, value, detail, color = 'blue', id = '') {
    return UI.metric(label,value,detail,color,art(metricArtwork[label],'ov-stat-art'),id);
  }

  function stats(items) {
    const keys = {'Coins':'coins','Power Points':'powerPoints','Direct Buffie Gems':'gems','Gems':'gems'};
    return UI.stats(items.map(([label,value])=>[label,value,keys[label]]));
  }

  function donut(rows, center, label) { return UI.donut(rows,center,label); }

  function bars(rows, options = {}) { return UI.bars(rows,options); }

  function columns(rows, color = '#2585ee') { return UI.columns(rows,color); }

  function timeLabel(value) {
    if (value == null) return '—';
    return value >= 3600 ? `${Math.floor(value / 3600)}h ${Math.floor(value % 3600 / 60)}m`
      : `${Math.floor(value / 60)}m ${value % 60}s`;
  }

  function battleDate(value) {
    if (!value) return 'Unavailable';
    const iso = value.replace(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(.*)$/, '$1-$2-$3T$4:$5:$6$7');
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? value : new Intl.DateTimeFormat(undefined, {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}).format(d);
  }

  function scatter(rows) {
    if (!rows.length) return empty('Unlock brawlers to see the Power and trophy relationship');
    const max = Math.max(1000, ...rows.map((r) => r.trophies));
    const x = (p) => 45 + (p - 1) / 10 * 445;
    const y = (t) => 205 - t / max * 175;
    const grid = [0, .5, 1].map((v) => `<line x1="45" y1="${y(v * max)}" x2="500" y2="${y(v * max)}"/><text x="38" y="${y(v * max) + 4}" text-anchor="end">${num(Math.round(v * max))}</text>`).join('');
    return `<svg class="ov-scatter" viewBox="0 0 535 245" role="img" aria-label="Power versus trophies across ${rows.length} brawlers"><title>Each point is an owned brawler, horizontal position is Power and vertical position is current trophies</title><g class="ov-plot-grid">${grid}</g><g class="ov-plot-labels">${[1,3,5,7,9,11].map((p) => `<text x="${x(p)}" y="224" text-anchor="middle">P${p}</text>`).join('')}</g>${rows.map((r) => `<circle cx="${x(r.power)}" cy="${y(r.trophies)}" r="4.5" fill="${r.prestige ? '#8d63d7' : '#2585ee'}" fill-opacity=".65" tabindex="0"><title>${esc(r.name)} — Power ${r.power}, ${num(r.trophies)} trophies</title></circle>`).join('')}</svg><div class="ov-chart-key"><span><i style="background:#2585ee"></i>Prestige path</span><span><i style="background:#8d63d7"></i>Prestiged</span></div>`;
  }

  function trophyTop() {
    const rows = [...data.summary.rows].filter((r) => r[trophySort] != null)
      .sort((a,b) => b[trophySort] - a[trophySort]).slice(0,10);
    return bars(rows.map((r) => ({id:r.id, name:r.name, label:r.name, value:r[trophySort]})), {compact:true});
  }

  function equipmentRows(s) {
    const equipmentColors = ['#31b46f','#e3ac23','#2585ee','#9560de'];
    return `<div class="ov-equipment-grid">${s.equipment.map((e, i) => `<div class="ov-equipment-tile">${art(['gadget','starPower','gear','hypercharge'][i])}<h4>${e.label}</h4><strong>${num(e.owned)} <small>items owned</small></strong><div class="ov-bar-label"><span>Brawler coverage</span><b>${pct(e.coverage_pct)}</b></div><div class="ov-track"><i style="width:${e.coverage_pct || 0}%;--ov-color:${equipmentColors[i]}"></i></div><p>${e.covered} / ${e.known} observed brawlers have at least one</p><div class="ov-equipment-completion"><span>Item collection</span><b>${pct(e.completion_pct)}</b></div><small>${e.available == null ? 'Catalogue total unavailable' : `${e.owned} owned items · ${e.available} available for observed brawlers`}${e.unknown ? ` · ${e.unknown} inventories unknown` : ''}</small></div>`).join('')}</div>`;
  }

  function recentSection(b) {
    if (b.source === 'UNAVAILABLE') return card('Recent performance', empty('Recent battles could not be fetched — refresh to try again'), '', 12);
    if (!b.count) return card('Recent performance', empty('No matching recent battles were returned for this account'), '', 12);
    const resultRows = [
      {label:'Wins',value:b.wins,color:'#29b18d'}, {label:'Losses',value:b.losses,color:'#ed6587'},
      {label:'Draws',value:b.draws,color:'#e7ad27'}, {label:'Placements / unknown',value:b.placements+b.unknown,color:'#8395af'}];
    let markup = card('Recent outcomes', donut(resultRows, pct(b.win_rate), 'WIN RATE'),
      `${b.decisive} result-bearing matches · Draws and placements excluded from win rate`, 4, `${b.count} MATCH SAMPLE`);
    markup += card('Modes played', bars(b.modes.map((r) => ({...r,label:modeLabel(r.label),iconGroup:'modes',iconValue:r.label})), {compact:true}), 'Match counts in this returned window', 4);
    markup += card('Brawlers played', bars(b.brawlers.slice(0,5), {compact:true}), 'Most used in this sample', 4);
    const timeline = b.samples.map((r) => `<a href="/brawlers/${r.id}" class="ov-result ov-result-${r.result}" title="${esc(`${r.brawler} · ${modeLabel(r.mode)} · ${r.map} · ${battleDate(r.time)} · ${r.result}${r.rank ? ` #${r.rank}` : ''}`)}" aria-label="${esc(`${r.brawler} ${r.result} on ${r.map}`)}">${r.result === 'victory' ? 'W' : r.result === 'defeat' ? 'L' : r.result === 'draw' ? 'D' : r.rank ? `#${r.rank}` : '?'}</a>`).join('');
    markup += card('Your recent run', `<div class="ov-run-label"><span>${esc(battleDate(b.oldest))}</span><span>${esc(battleDate(b.newest))} →</span></div><div class="ov-result-timeline">${timeline}</div>` + stats([
      ['Star Player',num(b.star_player)], ['Recorded battle time',timeLabel(b.play_seconds)],
      ['Net trophy change',b.trophy_change == null ? '—' : `${b.trophy_change > 0 ? '+' : ''}${num(b.trophy_change)}`],
      ['Avg team Power gap',b.power_gap == null ? '—' : `${b.power_gap > 0 ? '+' : ''}${num(b.power_gap)}`]]),
      `Oldest → newest · Duration available for ${b.durations_known}/${b.count} matches · Trophy change for ${b.trophies_known}/${b.count} · Team Power for ${b.power_gap_count}/${b.count}`, 12);
    const changes = b.samples.filter((r) => r.trophy_change != null);
    if (changes.length) {
      let sum = 0;
      const values = [0,...changes.map((r) => sum += r.trophy_change)];
      const lo = Math.min(0,...values), hi = Math.max(1,...values);
      const points = values.map((v,i) => `${35+i/(values.length-1)*665},${175-(v-lo)/(hi-lo)*140}`).join(' ');
      markup += card('Trophy movement in the sample', `<svg class="ov-line-chart" viewBox="0 0 730 210" role="img" aria-label="Cumulative trophy change ${num(sum)} across ${changes.length} matches"><title>Cumulative change from matches where trophy change is available</title><line x1="35" x2="700" y1="${175-(0-lo)/(hi-lo)*140}" y2="${175-(0-lo)/(hi-lo)*140}" stroke="#d8e5f3"/><polyline points="${points}" fill="none" stroke="#2585ee" stroke-width="3" stroke-linejoin="round"/><text x="35" y="200">Start at 0</text><text x="700" y="200" text-anchor="end">${num(sum)} trophies</text></svg>`, 'Only supplied trophy changes are included — this is a recent sample, not account history', 12);
    }
    return markup;
  }

  function contextSection() {
    const c = data.club;
    let club = c ? `<div class="ov-club-header"><span class="ov-club-emblem">${c.badge_id ? `<img src="https://cdn.brawlify.com/club-badges/regular/${Number(c.badge_id)}.png" alt="" onerror="this.onerror=null;this.src='/assets/rarity-skull.svg'">` : art('team')}</span><div><h4>${esc(c.name)}</h4><span>${esc(c.tag)} · ${esc(c.type)}</span></div><a href="/club/${encodeURIComponent(c.tag)}">Open club →</a></div>` + stats([
      ['Club trophies',num(c.trophies)], ['Members',num(c.members)], ['Your position',c.position ? `#${c.position}` : '—'],
      ['Your role',esc(c.role || 'Unavailable')], ['Average trophies',num(c.average)], ['Required trophies',num(c.required_trophies)]])
      + (c.contribution != null ? `<div class="ov-bar-label"><span>Your trophy contribution</span><strong>${pct(c.contribution)}</strong></div><div class="ov-track"><i style="width:${Math.min(100,c.contribution)}%;--ov-color:#8d63d7"></i></div>` : '')
      + (c.description ? `<p class="ov-note">${esc(c.description)}</p>` : '')
      : empty(state.player?.club ? 'Club details are unavailable for this account' : 'This account is not currently in a club');
    const e = data.events;
    const slots = e.items.filter((r) => r.active !== false).slice(0,6);
    const events = e.source === 'UNAVAILABLE' ? empty('Event rotation is unavailable — refresh to try again') : slots.length ? `<div class="ov-events">${slots.map((r) => `<a href="/events" class="ov-event"><img src="${getUiIconRecord('modes',r.mode)?.local_url || '/assets/rarity-skull.svg'}" alt="" onerror="this.style.visibility='hidden'"><div><strong>${esc(r.map)}</strong><span>${esc(modeLabel(r.mode))}${r.modifiers.length ? ` · ${esc(r.modifiers.join(', '))}` : ''}</span><div class="ov-track"><i style="width:${e.source === 'DEMO' ? 0 : r.progress || 0}%;--ov-color:#2585ee"></i></div></div><b data-ov-event-end="${e.source === 'DEMO' ? '' : esc(r.end)}">${e.source === 'DEMO' ? 'Sample' : r.remaining_seconds == null ? '—' : timeLabel(r.remaining_seconds)}</b></a>`).join('')}</div>` : empty('No active event slots were returned');
    return card('Your club',club,'Club totals and positions use the returned member roster',6,'TEAM CONTEXT')
      + card('Live arena rotation',events,e.source === 'DEMO' ? 'Sample rotation — no live countdown' : 'Time remaining until each slot changes',6,'EVENTS & MAPS');
  }

  function goalsSection(s) {
    const b=s.builds;
    const cost = stats([['Coins',num(b.cost.coins)],['Power Points',num(b.cost.powerPoints)],['Direct Buffie Gems',num(b.cost.gems)]]);
    const powerCoins=b.power_cost.coins;
    const buildCoins=b.goals.length ? 'Recommended items' : 'Known chosen builds';
    let markup=card('What remains to complete your chosen builds',cost + bars([
      {label:'Power upgrades across the roster',value:powerCoins,color:'#2585ee',art:'currencies/power-points.png'},
      {label:buildCoins,value:b.build_coin_cost,color:'#8d63d7',art:'section_gear.png'}]),
      `${b.known}/${s.collection.owned} brawlers have observed inventory and build data · ${b.all_costs_complete ? 'Complete cost coverage' : 'Known requirements only'} · Direct Buffie purchases shown separately in Gems`,8,'COIN COST BREAKDOWN');
    markup+=card('Build readiness',donut([{label:'Complete',value:b.complete,color:'#29b18d'},
      {label:'In progress',value:b.known-b.complete,color:'#2585ee'}, {label:'Unknown',value:s.collection.owned-b.known,color:'#cbd6e5'}],num(b.complete),'COMPLETE')
      + `<div class="ov-readiness-mean"><span>Average known readiness</span><strong>${pct(b.mean_progress)}</strong></div>`,
      'Calculated against maintained recommended builds — a progression measure',4);
    markup+=card('Readiness distribution',columns(b.histogram,colors),`${b.known} brawlers with known inventory · Power, chosen equipment and available Buffies`,6);
    markup+=card('Closest trophy milestones',`<div class="ov-milestones">${s.milestones.map((r) => `<a href="/brawlers/${r.id}">${brawlerIconMarkup(r)}<span><strong>${esc(r.name)}</strong><small>${esc(r.target)}${r.source === 'INFERRED' ? ' · estimated path' : ''}</small></span><b>${num(r.remaining)}<small>trophies away</small></b></a>`).join('') || empty('No brawler milestones available')}</div>`,'Targets use the maintained Prestige rules',6);
    const goals=b.goals.map((r) => `<a class="ov-goal" href="/brawlers/${r.id}"><div class="ov-goal-title">${brawlerIconMarkup(r)}<div><strong>${esc(r.name)}</strong><span>Power ${r.power} → 11</span></div><b>${pct(r.progress)}</b></div><div class="ov-track"><i style="width:${r.progress || 0}%;--ov-color:#29b18d"></i></div><p>${esc(r.missing.slice(0,3).join(' · ') || 'Finish the remaining Power upgrades')}${r.missing.length > 3 ? ` +${r.missing.length-3} more` : ''}</p><div class="ov-cost-chips"><span>${art('currencies/coins.png')}${num(r.cost.coins)} Coins</span><span>${art('currencies/power-points.png')}${num(r.cost.powerPoints)} PP</span>${r.cost.gems ? `<span>${art('currencies/gems.png')}${num(r.cost.gems)} Gems</span>` : ''}</div><small>${r.affordable === true ? 'Within your saved balances' : r.affordable === false ? 'Above your saved balances' : r.costs_complete ? 'Open the full build plan →' : 'Some prices or build requirements are unavailable'}</small></a>`).join('');
    markup+=card('Six practical next steps',`<div class="ov-goals">${goals || empty('All observed chosen builds are complete')}</div>`,
      'Ordered by known remaining Coin cost — each card is a separate plan, rather than a combined spending budget',12,'LOWEST REMAINING COST');
    const resources=data.resources;
    const walletForm=`<details class="ov-wallet-editor"><summary>${resources ? 'Update your balances' : 'Enter your balances'}</summary><form id="ov-wallet-form"><div class="ov-wallet-fields">${[['coins','Coins'],['power_points','Power Points'],['gems','Gems'],['credits','Credits'],['bling','Bling']].map(([key,label])=>`<label><span>${currencyArtwork[label] ? art(currencyArtwork[label], 'ov-resource-icon') : ''}${label}</span><input name="${key}" type="number" min="0" max="100000000" step="1" required value="${resources?.[key] ?? ''}" ${s.source === 'DEMO' ? 'disabled' : ''}></label>`).join('')}</div><p id="ov-wallet-status" role="status">${s.source === 'DEMO' ? 'Connect your player tag to save your own balances' : 'Enter your current in-game balances — these values are stored as manual input'}</p><button class="subtle-button" type="submit" ${s.source === 'DEMO' ? 'disabled' : ''}>Save balances</button></form></details>`;
    // Keep balance entry in the Overview so the user can immediately check their goals
    markup+=card('Your resource balances',(resources ? stats([['Coins',num(resources.coins)],['Power Points',num(resources.power_points)],
      ['Gems',num(resources.gems)],['Credits',num(resources.credits)],['Bling',num(resources.bling)]])
      : `<div class="ov-wallet-empty"><img src="/assets/currencies/coins.png" alt=""><div><strong>Add your balances to check affordability</strong><p>The player API does not return spendable resources</p></div></div>`)+walletForm,
      resources ? `Manually entered · Updated ${new Date(resources.updated_at).toLocaleString()}` : 'Upgrade costs are available even before you add balances',12,'MANUAL INVENTORY');
    return markup;
  }

  function rosterTable() {
    const rows=[...data.summary.rows].filter((r) => `${r.name} ${r.class} ${r.rarity}`.toLowerCase().includes(rosterSearch.toLowerCase()))
      .sort((a,b) => rosterSort === 'name' ? a.name.localeCompare(b.name) : (b[rosterSort] ?? -1)-(a[rosterSort] ?? -1));
    return `<table class="ov-table"><thead><tr><th>Brawler</th><th>Power</th><th>Trophies</th><th>Best</th><th>Prestige</th><th>Streak / best</th><th>G / SP / Gear / HC</th><th>Buffies</th><th>Returned skin</th></tr></thead><tbody>${rows.map((r) => `<tr><td><a href="/brawlers/${r.id}">${brawlerIconMarkup(r)}<span><strong>${esc(r.name)}</strong><small>${esc(r.class)} · ${esc(r.rarity)}</small></span></a></td><td>${r.power}</td><td>${num(r.trophies)}</td><td>${num(r.highest_trophies)}</td><td>${r.prestige}${r.prestige_source === 'INFERRED' ? '<small>estimated</small>' : ''}</td><td>${num(r.current_streak)} / ${num(r.best_streak)}</td><td>${Object.values(r.equipment).map(num).join(' / ')}</td><td>${num(r.buffies)}</td><td>${esc(r.skin?.name || 'Unavailable')}</td></tr>`).join('')}</tbody></table>${!rows.length ? empty('No brawlers match this search') : ''}`;
  }

  function render() {
    if (!data || state.page !== 'overview') return;
    const s=data.summary;
    const rows=s.rows;
    const classColors = Object.fromEntries(Object.values(BRAWLER_CLASSES).map((r) => [r.label, r.color]));
    const rarityOrder = ['common','rare','superrare','epic','mythic','legendary','ultralegendary'];
    const rarityColors = {'common':'var(--rarity-common)','rare':'var(--rarity-rare)','superrare':'var(--rarity-super-rare)','epic':'var(--rarity-epic)','mythic':'var(--rarity-mythic)','legendary':'var(--rarity-legendary)','ultralegendary':'var(--rarity-ultra)'};
    const rank=s.ranked.rows[0];
    cardArtwork['Ranked rating comparison'] = rankAsset(rank.rank) || 'wins';
    let html=`<div class="ov-snapshot-meta"><span><i></i>${s.source === 'DEMO' ? 'Demo account' : 'Account snapshot'} · ${esc(new Date(s.fetched_at).toLocaleString())}</span><span>Hover charts for details · Open brawlers to explore</span></div><div class="ov-stats-grid">`
      +metric('COLLECTION',`${num(s.collection.unlocked)}<em> / ${num(s.collection.total)}</em>`,`${pct(s.collection.pct)} unlocked`,'blue','brawler-count')
      +metric('AVERAGE POWER',num(s.power.average),`Median ${num(s.power.median)} · ${s.power.remaining_levels} levels to max`,'yellow','average-power')
      +metric('POWER 11',num(s.power.maxed),`${pct(s.power.maxed_pct)} of owned brawlers`,'pink','power-eleven')
      +metric('EQUIPPED',num(rows.filter((r)=>(r.equipment.gadgets || 0)+(r.equipment.star_powers || 0)>0).length),'With at least one Gadget or Star Power','green','equipped-count')
      +metric('BUILD READY',num(s.builds.complete),`${s.builds.known} chosen builds observed`,'purple')
      +metric('BEST WIN STREAK',num(s.streaks.record),`${s.streaks.known} brawlers report streaks`,'orange')+'</div>';
    const buildGap = Math.max(0,s.builds.known-s.builds.complete);
    html += `<nav class="ov-insight-links" aria-label="Account planning shortcuts"><a href="#ov-collection">${UI.icon('power')}<span><small>POWER PROGRESSION</small><strong>${num(s.collection.owned-s.power.maxed)} brawlers below Power 11</strong></span><b aria-hidden="true">→</b></a><a href="#ov-trophies">${UI.icon('target')}<span><small>YOUR NEXT TROPHY TARGET</small><strong>${num(s.trophies.to_goal)} to reach ${num(s.trophies.next_goal)}</strong></span><b aria-hidden="true">→</b></a><a href="#ov-goals">${UI.icon('build')}<span><small>KNOWN BUILD PLANS</small><strong>${s.builds.known ? buildGap ? `${num(buildGap)} observed builds to finish` : 'Observed builds complete' : 'Inventory data needed'}</strong></span><b aria-hidden="true">→</b></a></nav>`;
    html+=head('01','ov-collection','Your collection, unpacked','Power, roles, rarity and permanent progression');
    html+='<div class="ov-grid">';
    html+=card('Power distribution',columns(s.power.bars,Array.from({length:11},(_,i)=>i===10?'#ed6587':i>=8?'#8d63d7':'#2585ee')),
      'Number of owned brawlers at every Power level',8,'ROSTER DEVELOPMENT');
    html+=card('Collection completion',donut([{label:'Unlocked',value:s.collection.unlocked,color:'#2585ee'},
      {label:'Locked',value:s.collection.locked,color:'#dce6f3'}],pct(s.collection.pct),'UNLOCKED'),
      `${num(s.collection.total)} in the ${s.collection.catalog_source === 'OFFICIAL_API' ? 'live official' : 'maintained'} catalogue${s.collection.unknown_catalog_ids ? ` · ${s.collection.unknown_catalog_ids} owned IDs not yet matched` : ''}`,4);
    html+=card('Combat roles',donut(s.classes.map((r)=>({...r,color:classColors[r.label],iconGroup:'classes'})),num(s.collection.owned),'BRAWLERS'),'Classes use maintained game metadata',6);
    html+=card('Rarity mix',bars([...s.rarities].sort((a,b)=>(rarityOrder.indexOf(normalizeKey(a.label)) < 0 ? 99 : rarityOrder.indexOf(normalizeKey(a.label)))-(rarityOrder.indexOf(normalizeKey(b.label)) < 0 ? 99 : rarityOrder.indexOf(normalizeKey(b.label)))).map((r)=>({...r,color:rarityColors[normalizeKey(r.label)] || '#8395af'})),{compact:true}),'Owned brawlers by rarity from game metadata',6);
    html+=card('Permanent Prestige',`<div class="ov-prestige-layout"><div>${bars(s.prestige.bars,{compact:true})}</div><div>${stats([['Total Prestige',num(s.prestige.total)],['Prestiged brawlers',num(s.prestige.brawlers)]])}</div></div>`,
      `${s.prestige.known}/${s.collection.owned} brawlers have reported Prestige · Total source ${s.prestige.source === 'INFERRED' ? 'derived' : s.prestige.source === 'DEMO' ? 'demo' : 'official'}`,12);
    html+='</div></section>'+head('02','ov-trophies','Trophies & battle identity','Where your trophies sit and how your victories are distributed');
    html+='<div class="ov-grid">';
    html+=card('Your next account target',`<div class="ov-target"><img src="/assets/icon_trophy.png" alt=""><div><span>Next 5,000-trophy target</span><strong>${num(s.trophies.next_goal)}</strong><small>${num(s.trophies.to_goal)} trophies to go</small></div><b>${pct(s.trophies.goal_pct)}</b></div><div class="ov-track ov-track-large"><i style="width:${s.trophies.goal_pct || 0}%;--ov-color:#e7ad27"></i></div>`
      +stats([['Current trophies',num(s.trophies.current)],['Personal best',num(s.trophies.best)],['Gap to best',num(s.trophies.gap)],['Average / brawler',num(s.trophies.average)],['Median / brawler',num(s.trophies.median)]]),
      'A round-number planning target, rather than an official Trophy Road reward',12);
    html+=card('Trophy distribution',columns(s.trophies.distribution,['#41b5d2','#2585ee','#8d63d7','#e7ad27','#ed6587','#29b18d']),'Brawler counts grouped by current trophies',6);
    html+=card('Your top 10 brawlers',`<label class="ov-select-label">Compare <select id="ov-trophy-sort"><option value="trophies">Current trophies</option><option value="highest_trophies" ${trophySort === 'highest_trophies' ? 'selected' : ''}>Personal best</option></select></label><div id="ov-top-trophies">${trophyTop()}</div>`,'Open any bar label to inspect that brawler',6);
    html+=card('Power versus trophies',scatter(rows),'Hover or focus a point to see the brawler — trophies do not measure upgrade readiness',6);
    html+=card('Lifetime victory composition',s.victories.complete ? donut(s.victories.rows,num(s.victories.total),'VICTORIES')
      : bars(s.victories.rows),'Share of recorded victories — lifetime losses are not available, so this is not a win rate',6);
    html+=card('Trophy concentration',donut([{label:'Top 5 brawlers',value:s.trophies.top5,color:'#8d63d7'},
      {label:'Rest of roster',value:Math.max(0,s.trophies.roster_total-s.trophies.top5),color:'#2585ee'}],pct(s.trophies.top5_pct),'IN TOP 5'),
      'Uses the sum of individual brawler trophies',6);
    const streakRows=[...rows].filter((r)=>r.best_streak != null).sort((a,b)=>b.best_streak-a.best_streak).slice(0,5);
    html+=card('Win streak records',streakRows.length ? bars(streakRows.map((r)=>({id:r.id,name:r.name,label:r.name,value:r.best_streak,sub:`Current streak ${num(r.current_streak)}`})),{compact:true})
      : empty('Win streaks were not returned for this account'),`Highest current streak ${num(s.streaks.current_max)} · ${s.streaks.known} brawlers observed`,12);
    html+='</div></section>'+head('03','ov-equipment','The equipment vault','Ownership, coverage and the next missing pieces');
    html+='<div class="ov-grid">'+card('Inventory coverage',equipmentRows(s),'Coverage counts brawlers once · Item completion uses exact available IDs where a catalogue is available',12);
    html+=card('Hypercharge inventory',donut([{label:'Active at Power 11',value:s.hypercharges.active,color:'#8d63d7'},
      {label:'Stored below Power 11',value:s.hypercharges.stored,color:'#e7ad27'},
      {label:'No base HC owned',value:s.hypercharges.missing,color:'#dce6f3'},
      ...(s.hypercharges.unknown ? [{label:'Unknown',value:s.hypercharges.unknown,color:'#8395af'}] : [])],num(s.hypercharges.active+s.hypercharges.stored),'OWNED'),
      'Base Hypercharge ownership is separate from its Buffie',4);
    html+=card('Buffies by category',bars(s.buffies.map((r,i)=>({label:r.label,value:r.pct,color:colors[i+1],
      sub:`${r.owned} owned / ${r.known} observed eligible brawlers${r.unknown ? ` · ${r.unknown} unknown` : ''}${!r.eligible ? ' · not applicable' : ''}`})),{max:100,percent:true})
      +stats([['Gadget Buffies',num(s.buffies[0].owned)],['Star Power Buffies',num(s.buffies[1].owned)],['Hypercharge Buffies',num(s.buffies[2].owned)]]),
      'Only brawlers with released category Buffies enter the denominator',8);
    html+='</div></section>'+head('04','ov-competitive','Competitive & personal records','Official Ranked ratings, Fame and profile records','Official API');
    html+='<div class="ov-grid">';
    html+=card('Ranked rating comparison',s.ranked.rows.some((r)=>r.value != null)
      ? `<div class="ov-ranked-current">${rankAsset(rank.rank) ? art(rankAsset(rank.rank), 'ov-rank-badge') : ''}<span>${esc(rank.rank || 'Rank unavailable')}</span><strong>${num(rank.value)} <small>Elo</small></strong><b>Season ${num(s.ranked.season)}</b></div>`
        +bars(s.ranked.rows.map((r)=>({...r,sub:r.rank || 'Rank unavailable',art:rankAsset(r.rank)}))) : empty('Ranked information was not returned for this account'),
      'Current, season best and all-time best share the same rating scale',8);
    html+=card('Fame',s.fame.value == null ? empty('Fame information was not returned for this account')
      : `<div class="ov-fame"><span class="ov-fame-label">PROFILE FAME</span><strong>${num(s.fame.value)}</strong><span>${esc(s.fame.tier || 'Tier unavailable')}</span></div>`,'Profile Fame — separate from spendable Credits',4);
    html+=card('Account records',stats([['Experience level',num(s.records.level)],['Experience points',num(s.records.xp)],
      ['Championship',s.records.championship == null ? 'Unavailable' : s.records.championship ? 'Qualified' : 'Not qualified'],
      ['Robo Rumble record',s.records.robo ? `API record ${s.records.robo}` : 'Not reported'],
      ['Big Brawler survival',s.records.big_brawler ? timeLabel(s.records.big_brawler) : 'Not reported'],
      ['Historic Power Play',s.records.power_play == null ? 'Not reported' : num(s.records.power_play)]]),
      'Legacy records are shown only when returned — no placeholder achievements',12);
    html+='</div></section>'+head('05','ov-recent','Your recent arena activity','Results and habits in the returned battle window',data.battles.source === 'DEMO' ? 'Demo sample' : 'Recent API sample');
    html+='<div class="ov-grid">'+recentSection(data.battles)+'</div></section>';
    html+=head('06','ov-context','Club & live context','Your team and the arenas currently in rotation','Live context');
    html+='<div class="ov-grid">'+contextSection()+'</div></section>';
    html+=head('07','ov-goals','Make your next upgrade count','Progression costs and practical goals based on your inventory');
    html+='<div class="ov-grid">'+goalsSection(s)+'</div></section>';
    html+=`<details class="ov-ledger"><summary>${art('brawl-stars-symbol-official.png', 'ov-ledger-art')}<span><small>EVERY BRAWLER, EVERY DETAIL</small><strong>Explore the full account inventory</strong></span><b>${rows.length} brawlers <i>＋</i></b></summary><div class="ov-ledger-controls"><label>Search <input id="ov-roster-search" type="search" placeholder="Brawler, role or rarity" value="${esc(rosterSearch)}"></label><label>Sort <select id="ov-roster-sort">${[['trophies','Current trophies'],['highest_trophies','Personal best'],['power','Power'],['prestige','Prestige'],['best_streak','Best streak'],['name','Name']].map(([v,label])=>`<option value="${v}" ${rosterSort === v ? 'selected' : ''}>${label}</option>`).join('')}</select></label></div><div id="ov-roster-table" class="ov-table-scroll" role="region" aria-label="Brawler inventory table" tabindex="0">${rosterTable()}</div><p class="ov-note">G / SP / Gear / HC are owned item counts · — means unknown · Returned skin is not the full cosmetic collection</p></details>`;
    html+=`<p class="ov-footer-note">Account data comes from the player API · Roles, rarity, prices and chosen builds use maintained game data · Historical trends need saved observations</p>`;
    $('overview-dashboard').innerHTML=html;
    $('overview-dashboard').setAttribute('aria-busy','false');
    renderOverviewMetrics();
    const heroRankIcon = document.querySelector('#overview-view .champ-stat-icon img');
    if (heroRankIcon) heroRankIcon.src = `/assets/${rankAsset(rank.rank) || 'icon_trophy.png'}`;
    sectionObserver?.disconnect();
    sectionObserver = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a,b) => a.boundingClientRect.top-b.boundingClientRect.top)[0];
      if (!visible) return;
      document.querySelectorAll('.ov-jump-nav a').forEach((link) => {
        if (link.hash === `#${visible.target.id}`) link.setAttribute('aria-current','location');
        else link.removeAttribute('aria-current');
      });
    }, {rootMargin:'-10% 0px -65% 0px'});
    document.querySelectorAll('.ov-section-heading').forEach((heading) => sectionObserver.observe(heading));
    setText('hero-brawler-count', `${s.collection.unlocked} / ${s.collection.total}`);
  }

  async function load(refresh = false) {
    if (!state.player || state.page !== 'overview') return;
    const key=`${state.player.source}:${state.player.tag}`;
    if (!refresh && key === activeKey && pending) return pending;
    if (!refresh && key === activeKey && data && Date.now()-loadedAt<60000) {render(); return;}
    controller?.abort();
    controller=new AbortController();
    const signal=controller.signal;
    const changed=key!==activeKey;
    activeKey=key;
    if(changed) data=null;
    const button=$('overview-refresh');
    if(button) {button.disabled=true;button.textContent='Updating';}
    const holder=$('overview-dashboard');
    holder?.setAttribute('aria-busy','true');
    if(!data && holder) holder.innerHTML='<div class="ov-loading" role="status"><span class="ov-loading-dot"></span> Building your account analytics</div>';
    pending=(async()=>{
      try {
        const payload=await request(`/api/overview?tag=${encodeURIComponent(state.player.tag)}&demo=${state.player.source === 'DEMO'}&refresh=${refresh}`,{signal});
        if(signal.aborted || key!==`${state.player.source}:${state.player.tag}`) return;
        data=payload;
        loadedAt=Date.now();
        if(state.page==='overview') {
          renderAccount(payload,{skipOverview:true});
          sessionStorage.setItem(ACCOUNT_CACHE_KEY,JSON.stringify(payload));
          render();
        }
      } catch(error) {
        if(error.name==='AbortError') return;
        if(holder && activeKey===key) holder.innerHTML=`<div class="ov-empty ov-load-error" role="status"><strong>Account analytics could not be loaded</strong><p>${esc(error.message)}</p><button type="button" data-ov-retry>Try again</button></div>`;
      } finally {
        if(activeKey===key && !signal.aborted) {
          pending=null;
          holder?.setAttribute('aria-busy','false');
          if(button) {button.disabled=false;button.textContent='Refresh data';}
        }
      }
    })();
    return pending;
  }

  document.addEventListener('click',(event)=>{
    if(event.target.closest('#overview-refresh, [data-ov-retry]')) load(true);
  });
  document.addEventListener('change',(event)=>{
    if(event.target.id==='ov-trophy-sort') {trophySort=event.target.value;$('ov-top-trophies').innerHTML=trophyTop();}
    if(event.target.id==='ov-roster-sort') {rosterSort=event.target.value;$('ov-roster-table').innerHTML=rosterTable();}
  });
  document.addEventListener('input',(event)=>{
    if(event.target.id==='ov-roster-search') {rosterSearch=event.target.value;$('ov-roster-table').innerHTML=rosterTable();}
  });
  document.addEventListener('submit',async(event)=>{
    if(event.target.id!=='ov-wallet-form') return;
    event.preventDefault();
    const form=event.target;
    if(!form.reportValidity()) return;
    const button=form.querySelector('button');
    const status=$('ov-wallet-status');
    button.disabled=true;
    status.textContent='Saving balances';
    try {
      const values=Object.fromEntries([...new FormData(form)].map(([key,value])=>[key,Number(value)]));
      await request(`/api/resources/${encodeURIComponent(state.player.tag)}`,{
        method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({player_tag:state.player.tag,...values})});
      await load(true);
    } catch(error) {status.textContent=formatUiCopy(error.message);button.disabled=false;}
  });
  setInterval(()=>{
    if(state.page!=='overview') return;
    document.querySelectorAll('[data-ov-event-end]').forEach((el)=>{
      if(!el.dataset.ovEventEnd) return;
      const raw=el.dataset.ovEventEnd.replace(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(.*)$/, '$1-$2-$3T$4:$5:$6$7');
      const seconds=Math.max(0,Math.floor((Date.parse(raw)-Date.now())/1000));
      if(Number.isFinite(seconds)) el.textContent=seconds ? timeLabel(seconds) : 'Refresh due';
    });
  },1000);
  globalThis.OverviewDashboard={load};
})();
