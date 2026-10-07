/* Club analytics describe the current returned roster, rather than activity history */
(() => {
  const UI = DashboardUI, {num,pct} = UI;
  const esc = value => escapeMarkup(formatUiCopy(value));
  const roleColors = {president:'#e7ad27',vicepresident:'#8d63d7',senior:'#41b5d2',member:'#29b18d',unknown:'#8395af'};
  let payload = null, currentTag = '', target = 0, refreshing = false;
  let sort = 'trophies', role = 'all';

  function card(title,body,note,span=6,key='chart',kicker='') {
    return UI.card({title,body,note,span,kicker,symbol:UI.icon(key)});
  }
  function section(id,title,subtitle,tone,key,kicker,body) {
    return `<section class="ov-group ov-tone-${tone}" aria-labelledby="${id}-title"><div class="ov-section-heading" id="${id}"><span class="ov-section-emblem">${UI.icon(key)}</span><div class="ov-section-copy"><span class="ov-section-kicker">${kicker}</span><h2 id="${id}-title">${title}</h2><p>${subtitle}</p></div><span class="ov-source">From member roster</span></div><div class="ov-grid">${body}</div></section>`;
  }
  function concentration(s) {
    if (!s.roster_trophies) return UI.empty('Trophy contribution shares require a non-zero roster total');
    const points = ['45,190',...s.rows.map((row,i)=>`${45+(i+1)/s.member_count*450},${190-row.cumulative_share/100*160}`)].join(' ');
    return `<svg class="ov-line-chart club-concentration-chart" viewBox="0 0 535 235" role="img" aria-label="Cumulative share of roster trophies from highest to lowest member"><title>This is a snapshot contribution curve, not a history of trophy growth</title><g class="ov-plot-grid">${[0,50,100].map(value=>`<line x1="45" x2="495" y1="${190-value*1.6}" y2="${190-value*1.6}"/><text x="35" y="${194-value*1.6}" text-anchor="end">${value}%</text>`).join('')}</g><line x1="45" y1="190" x2="495" y2="30" stroke="#a9bdd4" stroke-dasharray="5 5"/><polyline points="${points}" fill="none" stroke="#8d63d7" stroke-width="3" stroke-linejoin="round"/>${[0,Math.floor(s.member_count/2),s.member_count].map(value=>`<text x="${45+value/s.member_count*450}" y="215" text-anchor="middle">${value} members</text>`).join('')}</svg><div class="ov-chart-key"><span><i style="background:#8d63d7"></i>Current roster</span><span><i style="background:#a9bdd4"></i>Even contribution reference</span></div>`;
  }
  function planning(s) {
    const gap = Math.max(0,target-s.roster_trophies), progress = Math.min(100,s.roster_trophies/target*100);
    return `<label class="club-target-control" for="club-target-input">Your trophy target <input id="club-target-input" type="number" min="1" max="100000000" step="1" value="${target}"></label><div class="club-plan-values"><div><small>ROSTER NOW</small><strong>${num(s.roster_trophies)}</strong></div><div><small>TO YOUR TARGET</small><strong>${num(gap)}</strong></div><span>${pct(progress)}</span></div><div class="ov-track ov-track-large"><i style="width:${progress}%;--ov-color:#29b18d"></i></div>${UI.stats([['Target total',num(target)],['Per current member',s.member_count ? num(Math.ceil(gap/s.member_count)) : '—'],['Status',gap ? 'In progress' : 'Target reached']])}`;
  }
  function personal(s) {
    const member = s.rows.find(row=>row.tag.toUpperCase() === state.player?.tag?.toUpperCase());
    if (!state.player || state.player.source === 'DEMO') return UI.empty('Connect your player tag to compare yourself with this club');
    if (!member) return UI.empty('Your connected player is not in this returned member roster');
    const signed = value => `${value > 0 ? '+' : ''}${num(value)}`;
    return `<a class="club-personal-name" href="/?player=${encodeURIComponent(member.tag)}"><span class="club-position">#${member.rank}</span><strong>${esc(member.name)}</strong></a>${UI.stats([['Your trophies',num(member.trophies)],['Your contribution',pct(member.share)],['Versus mean',signed(member.gap_to_average)],['Versus median',signed(member.gap_to_median)]])}<span class="club-role-caption">${esc(roleLabel(member.role_key))}</span>`;
  }
  function roleLabel(key) {return {president:'President',vicepresident:'Vice president',senior:'Senior',member:'Member',unknown:'Other role'}[key] || 'Other role';}

  function render(nextPayload) {
    if (!nextPayload?.club || !nextPayload.analytics?.rows) return;
    payload = nextPayload;
    const c = payload.club, s = payload.analytics;
    if (currentTag !== c.tag) {
      currentTag=c.tag;target=s.next_target;sort='trophies';role='all';
      $('roster-search').value = '';
      setText('club-refresh-status','');
    }
    const source = c.source === 'DEMO' ? 'Demo club' : payload.freshness?.cache_hit ? 'Cached club snapshot' : 'Official club snapshot';
    let html = `<div class="ov-snapshot-meta"><span><i></i>${source} · ${esc(new Date(c.fetched_at).toLocaleString())}</span><span>${num(s.member_count)} returned members · Derived measures use their trophy sum</span></div>`;
    if (!s.totals_match) html += `<div class="club-data-note" role="status">Club total ${num(s.reported_trophies)} · Member trophy sum ${num(s.roster_trophies)} · The returned totals differ by ${num(s.total_difference)} — charts use the member sum</div>`;
    html += '<div class="ov-stats-grid">'
      +UI.metric('ROSTER TROPHIES',num(s.roster_trophies),'Sum of returned member trophies','yellow',UI.icon('trophy','ov-stat-art'))
      +UI.metric('AVERAGE TROPHIES',num(s.average_trophies),'Mean per returned member','blue',UI.icon('trophy','ov-stat-art'))
      +UI.metric('MEDIAN TROPHIES',num(s.median_trophies),'The middle of your roster','purple',UI.icon('chart','ov-stat-art'))
      +UI.metric('OPEN SPOTS',num(s.open_slots),`${pct(s.capacity_percent)} of 30 places filled`,'green',UI.icon('team','ov-stat-art'))
      +UI.metric('LEADERSHIP',num(s.leadership_count),'Presidents and vice presidents','pink',UI.icon('roles','ov-stat-art'))
      +UI.metric('TOP 5 SHARE',pct(s.top5_share),`${s.top5_count} members in this cohort`,'orange',UI.icon('chart','ov-stat-art'))+'</div>';

    let body = card('Room for the next teammate',UI.donut([{label:'Occupied',value:s.member_count,color:'#8d63d7'},
      {label:'Open places',value:s.open_slots,color:'#dce6f3'}],`${s.member_count} / 30`,'MEMBERS'),
      'Current capacity from the member roster',4,'team');
    body += card('Club roles',UI.donut(s.roles.map(row=>({...row,color:roleColors[row.key]})),num(s.member_count),'MEMBERS'),
      'Club roles are distinct from brawler combat classes',4,'roles');
    body += card('Entry setting versus roster',UI.donut([{label:'At or above minimum',value:s.at_or_above_entry,color:'#29b18d'},
      {label:'Below minimum',value:s.below_entry,color:'#e7ad27'}],num(c.required_trophies),'MIN TROPHIES'),
      'The joining minimum is a setting — existing members can remain below it',4,'lock');
    html += section('club-composition','The shape of your club','Capacity, leadership and the current admission setting','purple','team','CLUB SNAPSHOT',body);

    body = card('Member trophy distribution',UI.columns(s.distribution,UI.palette),'Each band includes its lower bound and excludes its upper bound · 100k+ has no upper bound',8,'trophy','ROSTER TROPHIES');
    body += card('Typical member & spread',UI.stats([['Lowest',num(s.min_trophies)],['Highest',num(s.max_trophies)],
      ['Lower quartile',num(s.q1)],['Upper quartile',num(s.q3)],['Range',num(s.trophy_range)],['Standard deviation',num(s.standard_deviation)]]),
      'Quartiles use linear interpolation · Spread measures trophy differences, not player skill',4,'chart');
    html += section('club-distribution','Where your roster stands','Trophy bands and the differences within the returned roster','gold','trophy','TROPHY LANDSCAPE',body);

    body = card('Top 10 member contributions',UI.bars(s.rows.slice(0,10).map(row=>({...row,label:row.name,value:row.trophies,sub:`${pct(row.share)} of roster trophies · ${roleLabel(row.role_key)}`})),{compact:true}),
      'Open a member to inspect their player account · Shares use the member trophy sum',6,'trophy');
    body += card('How trophies are shared',UI.donut([{label:`Top ${s.top5_count} members`,value:s.top5_trophies,color:'#8d63d7'},
      {label:'Rest of roster',value:s.roster_trophies-s.top5_trophies,color:'#2585ee'}],pct(s.top5_share),'IN TOP 5')
      +UI.stats([['Top 10 share',pct(s.top10_share)],['Above the mean',`${s.above_average} / ${s.member_count}`]]),
      'Contribution concentration describes this roster snapshot',6,'chart');
    body += card('Trophies by club role',UI.bars(s.roles.map(row=>({...row,value:row.trophies,color:roleColors[row.key],sub:`${row.value} members · ${pct(row.share)} of roster trophies`}))),
      'Total trophies in each returned club role',6,'roles');
    body += card('Average trophies by role',UI.bars(s.roles.filter(row=>row.value).map(row=>({...row,value:row.average,color:roleColors[row.key],sub:`${row.value} members in this role`}))),
      'Each role uses its own member count as the denominator',6,'roles');
    body += card('Cumulative roster contribution',concentration(s),'Members are ordered from most to fewest trophies · This curve shows concentration, not trophy growth over time',6,'chart');
    html += section('club-contributions','Every member counts','Contributions by member, cohort and club role','blue','team','SHARED PROGRESS',body);

    body = card('Set your next club target',`<div id="club-target-plan">${planning(s)}</div>`,'A planning scenario using the member trophy sum · Per-member amounts assume the gap is shared equally',8,'target','PLANNING SCENARIO');
    body += card('Your place in this club',personal(s),'Comparison uses your connected player tag and this returned member roster',4,'team');
    body += card('Recruitment at the current minimum',UI.stats([['Open places',num(s.open_slots)],['Joining minimum',num(c.required_trophies)],
      ['Added trophies at minimum',num(s.open_slots*c.required_trophies)],['Scenario roster total',num(s.roster_trophies+s.open_slots*c.required_trophies)]]),
      'Assumes each open place is filled at the current joining minimum and no member leaves · This is a scenario, not a forecast',12,'team');
    html += section('club-planning','Give your club a next step','Compare your position and explore a transparent trophy target','green','target','CLUB PLANNING',body);
    html += '<p class="ov-footer-note">Club and member values come from the club API · Activity, Mega Pig participation, member equipment, win rates and historical growth need additional data</p>';
    $('club-dashboard').innerHTML = html;
    $('club-refresh').disabled = refreshing;
    renderRoster();
  }

  function renderRoster() {
    if (!payload) return;
    const query = ($('roster-search')?.value || '').trim().toLowerCase();
    const rows = payload.analytics.rows.filter(row=>(role === 'all' || row.role_key === role) && `${row.name} ${row.tag}`.toLowerCase().includes(query))
      .sort((a,b)=>sort === 'name' ? a.name.localeCompare(b.name) : sort === 'trophies_asc' ? a.trophies-b.trophies : b.trophies-a.trophies);
    const html = rows.map(row=>`<tr class="roster-row"><td class="roster-rank"><span class="rank-medal rank-${row.rank}">${row.rank}</span></td><td class="roster-name"><a href="/?player=${encodeURIComponent(row.tag)}" class="ranking-person"><img src="https://cdn.brawlify.com/profile-icons/regular/${Number(row.icon_id) || 28000000}.png" alt="" loading="lazy" onerror="this.onerror=null;this.src='/assets/rarity-skull.svg'"><strong>${esc(row.name)}</strong></a></td><td><span class="role-badge club-role-${row.role_key}">${esc(roleLabel(row.role_key))}</span></td><td class="roster-trophies">${UI.icon('trophy','table-trophy-icon')}${num(row.trophies)}</td><td class="club-share-cell"><strong>${pct(row.share)}</strong><span class="ov-track"><i style="width:${row.share || 0}%;--ov-color:#8d63d7"></i></span></td><td>${row.gap_to_average > 0 ? '+' : ''}${num(row.gap_to_average)}</td><td><a class="member-tag-pill" href="/?player=${encodeURIComponent(row.tag)}">${esc(row.tag)}</a></td><td><a class="small-action" href="/?player=${encodeURIComponent(row.tag)}">Inspect profile →</a></td></tr>`).join('');
    $('club-members-tbody').innerHTML = html || (payload.analytics.member_count
      ? '<tr><td colspan="8"><div class="empty-state"><strong>No matching members</strong>Try another name, tag or role</div></td></tr>'
      : '<tr><td colspan="8"><div class="empty-state"><strong>No members returned</strong>This club snapshot contains an empty roster</div></td></tr>');
    setText('club-roster-summary',`${rows.length} of ${payload.analytics.member_count} members · Positions use trophy rank, including ties · Shares use the member sum`);
    $('club-roster-sort').value = sort;
    $('club-role-filter').value = role;
  }

  async function refresh() {
    if (!payload || refreshing) return;
    const tag = payload.club.tag;
    refreshing = true;
    const button = $('club-refresh');
    button.disabled = true;
    button.textContent = 'Updating';
    setText('club-refresh-status','Refreshing the club snapshot');
    try {
      const result = await request(payload.club.source === 'DEMO' ? '/api/demo/club' : `/api/club?tag=${encodeURIComponent(tag)}&refresh=true`);
      if (state.club?.tag !== tag) return;
      sessionStorage.setItem(CLUB_CACHE_KEY,JSON.stringify(result));
      renderClub(result);
      setText('club-refresh-status','Club snapshot updated');
    } catch (error) {setText('club-refresh-status',error.message);}
    finally {refreshing=false;button.disabled=false;button.textContent='Refresh club';}
  }
  document.addEventListener('click',event=>{
    if (event.target.closest('#club-refresh')) refresh();
    if (event.target.closest('#club-retry')) loadInitialClub();
  });
  document.addEventListener('input',event=>{
    if (event.target.id === 'roster-search') renderRoster();
  });
  document.addEventListener('change',event=>{
    if (event.target.id === 'club-roster-sort') {sort=event.target.value;renderRoster();}
    if (event.target.id === 'club-role-filter') {role=event.target.value;renderRoster();}
    if (event.target.id === 'club-target-input' && event.target.reportValidity()) {
      target = Math.trunc(Number(event.target.value));
      $('club-target-plan').innerHTML = planning(payload.analytics);
    }
  });
  globalThis.ClubDashboard = {render,renderRoster,refresh};
})();
