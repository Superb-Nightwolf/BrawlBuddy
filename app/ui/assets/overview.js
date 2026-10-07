/* Charts and exploration for the server-calculated account snapshot */
(() => {
  const colors = ['#2585ee', '#8d63d7', '#29b18d', '#e7ad27', '#ed6587', '#41b5d2', '#f08c47', '#8395af'];
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

  function empty(message = 'This information was not returned for this account') {
    return `<div class="ov-empty"><span>◇</span><p>${esc(message)}</p></div>`;
  }

  function head(number, id, title, subtitle, badge = 'Calculated') {
    return `<div class="ov-section-heading" id="${id}"><span class="ov-section-number">${number}</span><div><h2>${title}</h2><p>${subtitle}</p></div><span class="ov-source">${badge}</span></div>`;
  }

  function card(title, body, note = '', span = 6, kicker = '') {
    return `<article class="ov-card ov-span-${span}"><div class="ov-card-heading"><div>${kicker ? `<span class="ov-kicker">${kicker}</span>` : ''}<h3>${title}</h3></div></div>${body}${note ? `<p class="ov-note">${esc(note)}</p>` : ''}</article>`;
  }

  function metric(label, value, detail, color = 'blue', id = '') {
    return `<article class="ov-stat ov-stat-${color}"><span>${label}</span><strong ${id ? `id="${id}"` : ''}>${value}</strong><small>${esc(detail)}</small></article>`;
  }

  function stats(items) {
    return `<div class="ov-mini-stats">${items.map(([label, value]) => `<div><span>${esc(label)}</span><strong>${value}</strong></div>`).join('')}</div>`;
  }

  function donut(rows, center, label) {
    const valid = rows.filter((r) => Number.isFinite(r.value) && r.value > 0);
    const total = valid.reduce((sum, row) => sum + row.value, 0);
    let angle = 0;
    const stops = valid.map((row, i) => {
      const start = angle;
      angle += row.value / total * 360;
      return `${row.color || colors[i % colors.length]} ${start}deg ${angle}deg`;
    });
    const description = rows.map((r) => `${r.label} ${num(r.value)}`).join(', ');
    return `<div class="ov-donut-layout"><div class="ov-donut" role="img" aria-label="${esc(description)}" style="--ov-gradient:${total ? `conic-gradient(${stops.join(',')})` : '#e8eef6'}"><div><strong>${center}</strong><span>${label}</span></div></div><div class="ov-legend">${rows.map((r, i) => `<div><i style="--ov-color:${r.color || colors[i % colors.length]}"></i><span>${esc(r.label)}</span><strong>${num(r.value)}</strong><small>${total && r.value != null ? pct(r.value / total * 100) : '—'}</small></div>`).join('')}</div></div>`;
  }

  function bars(rows, options = {}) {
    const max = options.max || Math.max(1, ...rows.map((r) => r.value || 0));
    if (!rows.length) return empty();
    return `<div class="ov-bars ${options.compact ? 'ov-bars-compact' : ''}">${rows.map((r, i) => {
      const label = r.id ? `<a href="/brawlers/${r.id}">${brawlerIconMarkup(r)}<span>${esc(r.label)}</span></a>` : `<span>${esc(r.label)}</span>`;
      return `<div class="ov-bar-row"><div class="ov-bar-label">${label}<strong>${options.percent ? pct(r.value) : num(r.value)}${options.suffix || ''}</strong></div><div class="ov-track"><i style="width:${Math.min(100, Math.max(0, (r.value || 0) / max * 100))}%;--ov-color:${r.color || colors[i % colors.length]}"></i></div>${r.sub ? `<small>${esc(r.sub)}</small>` : ''}</div>`;
    }).join('')}</div>`;
  }

  function columns(rows, color = '#2585ee') {
    const max = Math.max(1, ...rows.map((r) => r.value || 0));
    return `<div class="ov-columns" role="img" aria-label="${esc(rows.map((r) => `${r.label}: ${r.value}`).join(', '))}">${rows.map((r, i) => `<div class="ov-column"><strong>${num(r.value)}</strong><div class="ov-column-track"><i style="height:${(r.value || 0) / max * 100}%;--ov-color:${Array.isArray(color) ? color[i % color.length] : color}"></i></div><span>${esc(r.label)}</span></div>`).join('')}</div>`;
  }

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
    return `<div class="ov-equipment-grid">${s.equipment.map((e, i) => `<div class="ov-equipment-tile"><img src="/assets/${['section_gadget.png','section_star_power.png','section_gear.png','section_hypercharge.png'][i]}" alt=""><h4>${e.label}</h4><strong>${num(e.owned)} <small>items owned</small></strong><div class="ov-bar-label"><span>Brawler coverage</span><b>${pct(e.coverage_pct)}</b></div><div class="ov-track"><i style="width:${e.coverage_pct || 0}%;--ov-color:${colors[i]}"></i></div><p>${e.covered} / ${e.known} observed brawlers have at least one</p><div class="ov-equipment-completion"><span>Item collection</span><b>${pct(e.completion_pct)}</b></div><small>${e.available == null ? 'Catalogue total unavailable' : `${e.owned} owned items · ${e.available} available for observed brawlers`}${e.unknown ? ` · ${e.unknown} inventories unknown` : ''}</small></div>`).join('')}</div>`;
  }

  function recentSection(b) {
    if (b.source === 'UNAVAILABLE') return card('Recent performance', empty('Recent battles could not be fetched — refresh to try again'), '', 12);
    if (!b.count) return card('Recent performance', empty('No matching recent battles were returned for this account'), '', 12);
    const resultRows = [
      {label:'Wins',value:b.wins,color:'#29b18d'}, {label:'Losses',value:b.losses,color:'#ed6587'},
      {label:'Draws',value:b.draws,color:'#e7ad27'}, {label:'Placements / unknown',value:b.placements+b.unknown,color:'#8395af'}];
    let markup = card('Recent outcomes', donut(resultRows, pct(b.win_rate), 'WIN RATE'),
      `${b.decisive} result-bearing matches · Draws and placements excluded from win rate`, 4, `${b.count} MATCH SAMPLE`);
    markup += card('Modes played', bars(b.modes.map((r) => ({...r,label:modeLabel(r.label)})), {compact:true}), 'Match counts in this returned window', 4);
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
    let club = c ? `<div class="ov-club-header"><span class="ov-club-emblem">♜</span><div><h4>${esc(c.name)}</h4><span>${esc(c.tag)} · ${esc(c.type)}</span></div><a href="/club/${encodeURIComponent(c.tag)}">Open club →</a></div>` + stats([
      ['Club trophies',num(c.trophies)], ['Members',num(c.members)], ['Your position',c.position ? `#${c.position}` : '—'],
      ['Your role',esc(c.role || 'Unavailable')], ['Average trophies',num(c.average)], ['Required trophies',num(c.required_trophies)]])
      + (c.contribution != null ? `<div class="ov-bar-label"><span>Your trophy contribution</span><strong>${pct(c.contribution)}</strong></div><div class="ov-track"><i style="width:${Math.min(100,c.contribution)}%;--ov-color:#8d63d7"></i></div>` : '')
      + (c.description ? `<p class="ov-note">${esc(c.description)}</p>` : '')
      : empty(state.player?.club ? 'Club details are unavailable for this account' : 'This account is not currently in a club');
    const e = data.events;
    const slots = e.items.filter((r) => r.active !== false).slice(0,6);
    const events = e.source === 'UNAVAILABLE' ? empty('Event rotation is unavailable — refresh to try again') : slots.length ? `<div class="ov-events">${slots.map((r) => `<a href="/events" class="ov-event"><img src="${getUiIconRecord('modes',r.mode)?.local_url || '/assets/modes/duels.png'}" alt="" onerror="this.style.visibility='hidden'"><div><strong>${esc(r.map)}</strong><span>${esc(modeLabel(r.mode))}${r.modifiers.length ? ` · ${esc(r.modifiers.join(', '))}` : ''}</span><div class="ov-track"><i style="width:${e.source === 'DEMO' ? 0 : r.progress || 0}%;--ov-color:#2585ee"></i></div></div><b data-ov-event-end="${e.source === 'DEMO' ? '' : esc(r.end)}">${e.source === 'DEMO' ? 'Sample' : r.remaining_seconds == null ? '—' : timeLabel(r.remaining_seconds)}</b></a>`).join('')}</div>` : empty('No active event slots were returned');
    return card('Your club',club,'Club totals and positions use the returned member roster',6,'TEAM CONTEXT')
      + card('Live arena rotation',events,e.source === 'DEMO' ? 'Sample rotation — no live countdown' : 'Time remaining until each slot changes',6,'EVENTS & MAPS');
  }

  function goalsSection(s) {
    const b=s.builds;
    const cost = stats([['Coins',num(b.cost.coins)],['Power Points',num(b.cost.powerPoints)],['Direct Buffie Gems',num(b.cost.gems)]]);
    const powerCoins=b.power_cost.coins;
    const buildCoins=b.goals.length ? 'Recommended items' : 'Known chosen builds';
    let markup=card('What remains to complete your chosen builds',cost + bars([
      {label:'Power upgrades across the roster',value:powerCoins,color:'#2585ee'},
      {label:buildCoins,value:b.build_coin_cost,color:'#8d63d7'}]),
      `${b.known}/${s.collection.owned} brawlers have observed inventory and build data · ${b.all_costs_complete ? 'Complete cost coverage' : 'Known requirements only'} · Direct Buffie purchases shown separately in Gems`,8,'COIN COST BREAKDOWN');
    markup+=card('Build readiness',donut([{label:'Complete',value:b.complete,color:'#29b18d'},
      {label:'In progress',value:b.known-b.complete,color:'#2585ee'}, {label:'Unknown',value:s.collection.owned-b.known,color:'#cbd6e5'}],num(b.complete),'COMPLETE')
      + `<div class="ov-readiness-mean"><span>Average known readiness</span><strong>${pct(b.mean_progress)}</strong></div>`,
      'Calculated against maintained recommended builds — a progression measure',4);
    markup+=card('Readiness distribution',columns(b.histogram,colors),`${b.known} brawlers with known inventory · Power, chosen equipment and available Buffies`,6);
    markup+=card('Closest trophy milestones',`<div class="ov-milestones">${s.milestones.map((r) => `<a href="/brawlers/${r.id}">${brawlerIconMarkup(r)}<span><strong>${esc(r.name)}</strong><small>${esc(r.target)}${r.source === 'INFERRED' ? ' · estimated path' : ''}</small></span><b>${num(r.remaining)}<small>trophies away</small></b></a>`).join('') || empty('No brawler milestones available')}</div>`,'Targets use the maintained Prestige rules',6);
    const goals=b.goals.map((r) => `<a class="ov-goal" href="/brawlers/${r.id}"><div class="ov-goal-title">${brawlerIconMarkup(r)}<div><strong>${esc(r.name)}</strong><span>Power ${r.power} → 11</span></div><b>${pct(r.progress)}</b></div><div class="ov-track"><i style="width:${r.progress || 0}%;--ov-color:#29b18d"></i></div><p>${esc(r.missing.slice(0,3).join(' · ') || 'Finish the remaining Power upgrades')}${r.missing.length > 3 ? ` +${r.missing.length-3} more` : ''}</p><div class="ov-cost-chips"><span>${num(r.cost.coins)} Coins</span><span>${num(r.cost.powerPoints)} PP</span>${r.cost.gems ? `<span>${num(r.cost.gems)} Gems</span>` : ''}</div><small>${r.affordable === true ? 'Within your saved balances' : r.affordable === false ? 'Above your saved balances' : r.costs_complete ? 'Open the full build plan →' : 'Some prices or build requirements are unavailable'}</small></a>`).join('');
    markup+=card('Six practical next steps',`<div class="ov-goals">${goals || empty('All observed chosen builds are complete')}</div>`,
      'Ordered by known remaining Coin cost — each card is a separate plan, rather than a combined spending budget',12,'LOWEST REMAINING COST');
    const resources=data.resources;
    const walletForm=`<details class="ov-wallet-editor"><summary>${resources ? 'Update your balances' : 'Enter your balances'}</summary><form id="ov-wallet-form"><div class="ov-wallet-fields">${[['coins','Coins'],['power_points','Power Points'],['gems','Gems'],['credits','Credits'],['bling','Bling']].map(([key,label])=>`<label>${label}<input name="${key}" type="number" min="0" max="100000000" step="1" required value="${resources?.[key] ?? ''}" ${s.source === 'DEMO' ? 'disabled' : ''}></label>`).join('')}</div><p id="ov-wallet-status" role="status">${s.source === 'DEMO' ? 'Connect your player tag to save your own balances' : 'Enter your current in-game balances — these values are stored as manual input'}</p><button class="subtle-button" type="submit" ${s.source === 'DEMO' ? 'disabled' : ''}>Save balances</button></form></details>`;
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
    const classColors = {'Damage Dealer':'#ed6587','Assassin':'#8d63d7','Tank':'#2585ee','Marksman':'#e7ad27','Controller':'#41b5d2','Support':'#29b18d','Artillery':'#f08c47'};
    const rank=s.ranked.rows[0];
    let html=`<div class="ov-snapshot-meta"><span><i></i>${s.source === 'DEMO' ? 'Demo account' : 'Account snapshot'} · ${esc(new Date(s.fetched_at).toLocaleString())}</span><span>Hover charts for details · Open brawlers to explore</span></div><div class="ov-stats-grid">`
      +metric('COLLECTION',`${num(s.collection.unlocked)}<em> / ${num(s.collection.total)}</em>`,`${pct(s.collection.pct)} unlocked`,'blue','brawler-count')
      +metric('AVERAGE POWER',num(s.power.average),`Median ${num(s.power.median)} · ${s.power.remaining_levels} levels to max`,'yellow','average-power')
      +metric('POWER 11',num(s.power.maxed),`${pct(s.power.maxed_pct)} of owned brawlers`,'pink','power-eleven')
      +metric('EQUIPPED',num(rows.filter((r)=>(r.equipment.gadgets || 0)+(r.equipment.star_powers || 0)>0).length),'With at least one Gadget or Star Power','green','equipped-count')
      +metric('BUILD READY',num(s.builds.complete),`${s.builds.known} chosen builds observed`,'purple')
      +metric('BEST WIN STREAK',num(s.streaks.record),`${s.streaks.known} brawlers report streaks`,'orange')+'</div>';
    html+=head('01','ov-collection','Your collection, unpacked','Power, roles, rarity and permanent progression');
    html+='<div class="ov-grid">';
    html+=card('Power distribution',columns(s.power.bars,Array.from({length:11},(_,i)=>i===10?'#ed6587':i>=8?'#8d63d7':'#2585ee')),
      'Number of owned brawlers at every Power level',8,'ROSTER DEVELOPMENT');
    html+=card('Collection completion',donut([{label:'Unlocked',value:s.collection.unlocked,color:'#2585ee'},
      {label:'Locked',value:s.collection.locked,color:'#dce6f3'}],pct(s.collection.pct),'UNLOCKED'),
      `${num(s.collection.total)} in the ${s.collection.catalog_source === 'OFFICIAL_API' ? 'live official' : 'maintained'} catalogue${s.collection.unknown_catalog_ids ? ` · ${s.collection.unknown_catalog_ids} owned IDs not yet matched` : ''}`,4);
    html+=card('Combat roles',donut(s.classes.map((r)=>({...r,color:classColors[r.label]})),num(s.collection.owned),'BRAWLERS'),'Classes use maintained game metadata',4);
    html+=card('Rarity mix',bars(s.rarities,{compact:true}),'Owned brawlers by rarity from game metadata',4);
    html+=card('Permanent Prestige',bars(s.prestige.bars,{compact:true})+stats([['Total Prestige',num(s.prestige.total)],['Prestiged brawlers',num(s.prestige.brawlers)]]),
      `${s.prestige.known}/${s.collection.owned} brawlers have reported Prestige · Total source ${s.prestige.source === 'INFERRED' ? 'derived' : s.prestige.source === 'DEMO' ? 'demo' : 'official'}`,4);
    html+='</div>'+head('02','ov-trophies','Trophies & battle identity','Where your trophies sit and how your victories are distributed');
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
      : empty('Win streaks were not returned for this account'),`Highest current streak ${num(s.streaks.current_max)} · ${s.streaks.known} brawlers observed`,6);
    html+='</div>'+head('03','ov-equipment','The equipment vault','Ownership, coverage and the next missing pieces');
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
    html+='</div>'+head('04','ov-competitive','Competitive & personal records','Official Ranked ratings, Fame and profile records','Official API');
    html+='<div class="ov-grid">';
    html+=card('Ranked rating comparison',s.ranked.rows.some((r)=>r.value != null)
      ? `<div class="ov-ranked-current"><span>${esc(rank.rank || 'Rank unavailable')}</span><strong>${num(rank.value)} <small>Elo</small></strong><b>Season ${num(s.ranked.season)}</b></div>`
        +bars(s.ranked.rows.map((r)=>({...r,sub:r.rank || 'Rank unavailable'}))) : empty('Ranked information was not returned for this account'),
      'Current, season best and all-time best share the same rating scale',8);
    html+=card('Fame',s.fame.value == null ? empty('Fame information was not returned for this account')
      : `<div class="ov-fame"><span class="ov-fame-star">✦</span><strong>${num(s.fame.value)}</strong><span>${esc(s.fame.tier || 'Tier unavailable')}</span></div>`,'Profile Fame — separate from spendable Credits',4);
    html+=card('Account records',stats([['Experience level',num(s.records.level)],['Experience points',num(s.records.xp)],
      ['Championship',s.records.championship == null ? 'Unavailable' : s.records.championship ? 'Qualified' : 'Not qualified'],
      ['Robo Rumble record',s.records.robo ? `API record ${s.records.robo}` : 'Not reported'],
      ['Big Brawler survival',s.records.big_brawler ? timeLabel(s.records.big_brawler) : 'Not reported'],
      ['Historic Power Play',s.records.power_play == null ? 'Not reported' : num(s.records.power_play)]]),
      'Legacy records are shown only when returned — no placeholder achievements',12);
    html+='</div>'+head('05','ov-recent','Your recent arena activity','Results and habits in the returned battle window',data.battles.source === 'DEMO' ? 'Demo sample' : 'Recent API sample');
    html+='<div class="ov-grid">'+recentSection(data.battles)+'</div>';
    html+=head('06','ov-context','Club & live context','Your team and the arenas currently in rotation','Live context');
    html+='<div class="ov-grid">'+contextSection()+'</div>';
    html+=head('07','ov-goals','Make your next upgrade count','Progression costs and practical goals based on your inventory');
    html+='<div class="ov-grid">'+goalsSection(s)+'</div>';
    html+=`<details class="ov-ledger"><summary><span><small>EVERY BRAWLER, EVERY DETAIL</small><strong>Explore the full account inventory</strong></span><b>${rows.length} brawlers <i>＋</i></b></summary><div class="ov-ledger-controls"><label>Search <input id="ov-roster-search" type="search" placeholder="Brawler, role or rarity" value="${esc(rosterSearch)}"></label><label>Sort <select id="ov-roster-sort">${[['trophies','Current trophies'],['highest_trophies','Personal best'],['power','Power'],['prestige','Prestige'],['best_streak','Best streak'],['name','Name']].map(([v,label])=>`<option value="${v}" ${rosterSort === v ? 'selected' : ''}>${label}</option>`).join('')}</select></label></div><div id="ov-roster-table" class="ov-table-scroll" role="region" aria-label="Brawler inventory table" tabindex="0">${rosterTable()}</div><p class="ov-note">G / SP / Gear / HC are owned item counts · — means unknown · Returned skin is not the full cosmetic collection</p></details>`;
    html+=`<p class="ov-footer-note">Account data comes from the player API · Roles, rarity, prices and chosen builds use maintained game data · Historical trends need saved observations</p>`;
    $('overview-dashboard').innerHTML=html;
    $('overview-dashboard').setAttribute('aria-busy','false');
    renderOverviewMetrics();
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
    if(button) {button.disabled=true;button.textContent='↻ Updating';}
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
          if(button) {button.disabled=false;button.textContent='↻ Refresh data';}
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
