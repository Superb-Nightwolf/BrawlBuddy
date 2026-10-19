/* Meta explorer: observed performance, draft support and a transparent local training pipeline. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = value => value == null ? '—' : Number(value).toLocaleString();
  const pct = value => value == null ? '—' : `${(Number(value)*100).toFixed(1)}%`;
  const titleMode = value => String(value).replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase());
  const appState = () => typeof state === 'undefined' ? {} : state;
  const tabs = {tierlist:'Meta picks', draft:'Draft room', teams:'Team combinations', personal:'Your roster', transparency:'Model & data', operations:'Pipeline'};
  const modes = ['brawlBall','gemGrab','knockout','hotZone','bounty','heist','wipeout'];
  const ui = {tab:'tierlist', mode:'brawlBall', map:'', type:'', owned:false, activeSlot:'ally_1',
    allies:[null,null,null], enemies:[null,null,null], filters:null, status:null, timer:null, epoch:0, controller:null};
  const icon = id => typeof officialBrawlerIconSource === 'function' ? officialBrawlerIconSource({id:Number(id)}) : `/assets/brawlers/portraits/${Number(id)}.webp`;
  const name = id => appState().catalog?.find(b => Number(b.id) === Number(id))?.name || `Brawler ${id}`;
  const help = (title, text) => ExplorationPages.infoMarkup(title,text);
  const heading = (title, text) => `<div class="meta-section-heading"><h3>${esc(title)}</h3>${help(title,text)}</div>`;
  const empty = (title, text) => `<div class="meta-empty"><strong>${esc(title)}</strong><p>${esc(text)}</p></div>`;
  async function request(url, payload) {
    const response = await fetch(url, {signal:ui.controller?.signal,cache:'no-store',
      ...(payload === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the selected draft and try again.');
    return data;
  }
  function stop() {
    clearTimeout(ui.timer); ui.timer=null;
    ui.controller?.abort(); ui.epoch++;
  }
  async function load() {
    stop(); ui.controller=new AbortController(); const epoch=ui.epoch;
    if(new URLSearchParams(location.search).get('section')==='pipeline') ui.tab='operations';
    $('meta-view').innerHTML='<div class="meta-empty" role="status">Loading the meta explorer…</div>';
    try {
      const [status, filters] = await Promise.all([request('/api/ml/model-status'),request('/api/meta/filters')]);
      if (epoch !== ui.epoch) return;
      ui.status=status; ui.filters=filters.data;
      renderShell(); await refresh();
      if(new URLSearchParams(location.search).get('section')==='pipeline' && ui.tab==='operations')
        $('meta-view').querySelector('.meta-bulk-panel')?.scrollIntoView({block:'start'});
    } catch (error) {
      if (error.name !== 'AbortError') $('meta-view').innerHTML=empty('Meta explorer is unavailable',error.message);
    }
  }
  function renderShell() {
    const ds=ui.status?.dataset || {}, metrics=ui.status?.metrics;
    $('meta-view').innerHTML=`<div class="meta-container">
      <section class="meta-cover">
        <div class="meta-cover-top"><div class="meta-cover-emblem"><img src="/assets/rarity-skull.svg" alt=""></div>
          <div class="meta-cover-copy"><span class="meta-eyebrow">Competitive intelligence</span><h2>Make every pick count</h2><p>Explore observed performance, build a team and learn where your roster can grow.</p></div>
          ${help('How to use the meta explorer','These results describe collected matches, not the entire player population. Draft scores combine observed win rates, team pairs and opposing picks. A learned probability is available only for complete supported matchups. Unverified older records are retained but excluded from training and rankings. The Model & data tab explains coverage and validation.')}
        </div>
        <div class="meta-cover-metrics">
          ${metric('Tracked players',num(ds.total_discovered_players),'blue')}
          ${metric('Current matches',num(ds.verified_matches),'mint')}
          ${metric('Active model',metrics?.model_name || 'Awaiting training','purple')}
          ${metric('Holdout ROC-AUC',metrics ? Number(metrics.roc_auc).toFixed(3) : '—','gold')}
        </div>
      </section>
      <nav class="meta-tabs" aria-label="Meta explorer sections">${Object.entries(tabs).map(([id,label])=>`<button type="button" data-meta-tab="${id}" aria-pressed="${ui.tab===id}" class="${ui.tab===id?'active':''}">${label}</button>`).join('')}</nav>
      <div class="meta-filters"><label>Mode<select id="meta-mode">${modes.map(m=>`<option value="${m}" ${m===ui.mode?'selected':''}>${titleMode(m)}</option>`).join('')}</select></label>
        <label>Map<select id="meta-map"><option value="">All maps in this mode</option>${mapOptions()}</select></label>
        <label>Match type<select id="meta-type"><option value="">All match types</option>${(ui.filters?.match_types || []).map(t=>`<option value="${esc(t)}" ${t===ui.type?'selected':''}>${esc(titleMode(t))}</option>`).join('')}</select></label>
      </div>
      <div id="meta-content" aria-live="polite"></div>
    </div>`;
    $('meta-mode').onchange=e=>{ui.mode=e.target.value;ui.map='';$('meta-map').innerHTML='<option value="">All maps in this mode</option>'+mapOptions();refresh();};
    $('meta-map').onchange=e=>{ui.map=e.target.value;refresh();};
    $('meta-type').onchange=e=>{ui.type=e.target.value;refresh();};
    $('meta-view').querySelectorAll('[data-meta-tab]').forEach(button=>button.onclick=()=>{ui.tab=button.dataset.metaTab;
      $('meta-view').querySelectorAll('[data-meta-tab]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});refresh();});
    ExplorationPages.bind($('meta-view'));
  }
  function mapOptions() { return (ui.filters?.maps_by_mode?.[ui.mode] || []).map(m=>`<option value="${esc(m.map)}" ${m.map===ui.map?'selected':''}>${esc(m.map)}</option>`).join(''); }
  function metric(label,value,tone) {return `<div class="meta-metric tone-${tone}"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;}
  function query(path) {return path+`?mode=${encodeURIComponent(ui.mode)}`+(ui.map?`&map=${encodeURIComponent(ui.map)}`:'');}
  async function refresh() {
    clearTimeout(ui.timer);ui.timer=null; ui.controller?.abort();ui.controller=new AbortController();const epoch=++ui.epoch;
    const area=$('meta-content');if(!area)return;
    area.innerHTML='<div class="meta-empty" role="status">Loading this section…</div>';
    const filtered=['tierlist','personal'].includes(ui.tab);
    $('meta-type').disabled=!filtered;
    $('meta-view').querySelector('.meta-filters').hidden=['transparency','operations'].includes(ui.tab);
    try {
      let markup;
      if (ui.tab==='tierlist' || ui.tab==='personal') {
        const data=await request(query('/api/meta/brawlers')+(ui.type?`&match_type=${encodeURIComponent(ui.type)}`:''));
        markup=ui.tab==='personal'?personal(data.brawlers):tierlist(data.brawlers);
      } else if(ui.tab==='teams') {const data=await request(query('/api/meta/teams')+'&min_matches=2');markup=teams(data.teams);}
      else if(ui.tab==='draft') {
        const team=ui.allies.filter((v,i)=>v && `ally_${i+1}`!==ui.activeSlot), enemy=ui.enemies.filter((v,i)=>v && `enemy_${i+1}`!==ui.activeSlot);
        const step=await request('/api/ml/draft/step',{mode:ui.mode,map:ui.map || null,draftAllies:team,draftEnemies:enemy,activeSlot:ui.activeSlot,
          ownedBrawlersOnly:ui.owned && ui.activeSlot.startsWith('ally'),playerTag:appState().player?.tag || null,top_k:12});
        let prediction=null;
        if(ui.allies.every(Boolean) && ui.enemies.every(Boolean)) prediction=(await request('/api/ml/predict-match',{
          mode:ui.mode,map:ui.map || 'Unknown Map',teamBrawlers:ui.allies,enemyBrawlers:ui.enemies})).data;
        markup=draft(step.data,prediction);
      } else if(ui.tab==='transparency') {markup=transparency(await request('/api/ml/transparency/summary'));}
      else {
        const [data,bulk]=await Promise.all([request('/api/ml/operations/telemetry'),request('/api/ml/bulk-dataset/status')]);
        markup=operations(data,bulk);
      }
      if(epoch!==ui.epoch)return;
      area.innerHTML=markup;ExplorationPages.bind(area);bindContent();
      if(ui.tab==='operations') pollOperations();
    } catch(error) {if(epoch===ui.epoch && error.name!=='AbortError') area.innerHTML=empty('This section could not load',error.message);}
  }
  function brawlerCard(b) {
    return `<a class="meta-brawler-card" href="/brawlers/${Number(b.brawler_id)}"><div class="meta-brawler-heading"><img src="${esc(icon(b.brawler_id))}" alt=""><strong>${esc(b.brawler_name)}</strong><span class="meta-tier">${esc(b.tier)}</span></div>
      <div class="meta-card-values"><div><strong>${pct(b.smoothed_win_rate)}</strong><small>Smoothed wins</small></div><div><strong>${num(b.total_picks)}</strong><small>Labeled picks</small></div></div>
      <div class="meta-card-footer"><span>${esc(b.confidence.toLowerCase())} sample coverage</span><span aria-hidden="true">›</span></div></a>`;
  }
  function tierlist(rows) {
    return `<section class="meta-panel">${heading('Observed meta picks','Win rates are smoothed toward the observed pool average with a prior weight of 20. Tiers compare picks within your selected filter; they are not official ratings. Sample coverage describes the number of observations, not certainty that a pick will win. Draws, unknown outcomes and legacy labels are excluded. Pick rates use actual participant slots.')}
      ${rows.length?`<div class="meta-card-grid">${rows.map(brawlerCard).join('')}</div>`:empty('No verified picks in this selection','Collect current battles in Pipeline, or try another mode and map.')}</section>`;
  }
  function personal(rows) {
    const owned=appState().ownedBrawlers || [], ids=new Set(owned.map(b=>Number(b.id)));
    const observed=rows.filter(b=>ids.has(b.brawler_id));
    return `<section class="meta-panel">${heading('Your roster in this meta','This section matches collected performance with your connected collection. It does not assume that higher observed win rate causes better results for every player. Open a guide to review equipment and upgrade readiness.')}
      ${!appState().player?empty('Connect your player tag','Use Connect tag in the page header to explore your collection.'):observed.length?`<div class="meta-card-grid">${observed.map(brawlerCard).join('')}</div>`:empty('No observed matches for your owned picks','Try another filter or collect additional matches.')}</section>`;
  }
  function teams(rows) {return `<section class="meta-panel">${heading('Observed team combinations','Each trio needs at least two labeled team observations in this filter. Results are smoothed toward 50% with a weight of 5. Repeated team members are not independent evidence, and this is not a controlled measure of team synergy.')}
    ${rows.length?`<div class="meta-card-grid">${rows.map(t=>`<article class="meta-team-card"><div class="meta-team-portraits">${t.brawler_ids.map(id=>`<a href="/brawlers/${Number(id)}" aria-label="Open ${esc(name(id))}"><img src="${esc(icon(id))}" alt="${esc(name(id))}"></a>`).join('')}</div><strong>${t.brawler_names.map(esc).join(' · ')}</strong><div class="meta-card-values"><div><strong>${pct(t.smoothed_win_rate)}</strong><small>Smoothed wins</small></div><div><strong>${num(t.matches)}</strong><small>Team observations</small></div></div></article>`).join('')}</div>`:empty('More team observations needed','Collect battles or broaden your map selection.')}</section>`;}
  function draft(step,prediction) {
    const selected=new Set([...ui.allies,...ui.enemies].filter(Boolean));const catalog=appState().catalog || [];
    const slots=(side,prefix)=>side.map((id,index)=>`<label class="meta-draft-slot ${ui.activeSlot===`${prefix}_${index+1}`?'selected':''}"><span>${prefix==='ally'?'Your pick':'Opponent'} ${index+1}</span><select data-slot="${prefix}_${index+1}"><option value="">Choose a brawler</option>${catalog.map(b=>`<option value="${Number(b.id)}" ${Number(b.id)===id?'selected':''} ${selected.has(Number(b.id)) && Number(b.id)!==id?'disabled':''}>${esc(b.name)}</option>`).join('')}</select></label>`).join('');
    return `<div class="meta-split"><section class="meta-panel">${heading('Build a matchup','Choose unique picks for each side. Suggestions target the selected slot, so an existing pick in that slot is temporarily removed while it is evaluated. Partial drafts use observed performance; a learned matchup estimate needs all six picks plus a map and mode seen in training. The displayed matchup assumes equal average power on both teams. Owned filtering applies only to your team.')}
      <div class="meta-draft-controls"><label>Suggest for<select id="meta-active-slot">${['ally_1','ally_2','ally_3','enemy_1','enemy_2','enemy_3'].map(slot=>`<option value="${slot}" ${slot===ui.activeSlot?'selected':''}>${slot.replace('ally','Your pick').replace('enemy','Opponent').replace('_',' ')}</option>`).join('')}</select></label><label class="meta-checkbox"><input id="meta-owned" type="checkbox" ${ui.owned?'checked':''}>Only my owned picks</label><button id="meta-clear-draft" type="button">Clear draft</button></div>
      <div class="meta-draft-teams"><div>${slots(ui.allies,'ally')}</div><div>${slots(ui.enemies,'enemy')}</div></div>
      <div class="meta-match-estimate"><span>Matchup estimate</span><strong>${prediction?.source==='outcome_model'?pct(prediction.win_probability):'Awaiting coverage'}</strong><small>${prediction?.source==='outcome_model'?'Your team · uncalibrated model estimate':'Choose six supported picks and a known map for a learned estimate.'}</small></div>
    </section><section class="meta-panel">${heading('Suggested picks','Scores combine a model estimate when supported (45%), smoothed win rate (35%), observed same-team performance (10%) and observed opposing-team performance (10%). For partial drafts the model term is a neutral 50% baseline. These scores rank options; they are not win probabilities. Pair and counter queries respect the selected map.')}
      ${step.candidates?.length?`<div class="meta-suggestions">${step.candidates.map(c=>`<button type="button" class="meta-suggestion" data-pick="${Number(c.brawler_id)}"><img src="${esc(icon(c.brawler_id))}" alt=""><span><strong>${esc(c.brawler_name)}</strong><small>${num(c.sample_size)} labeled picks · ${pct(c.smoothed_win_rate)} smoothed wins</small></span><b>${Number(c.score).toFixed(1)}</b><span aria-hidden="true">›</span></button>`).join('')}</div>`:empty('No eligible observed picks','Collect matches, broaden the map filter, or connect a player for owned filtering.')}</section></div>`;
  }
  function transparency(data) {
    const ds=data.dataset, m=data.metrics, validation=data.validation || {}, benchmarks=data.benchmark_leaderboard || [];
    return `<section class="meta-panel">${heading('Model and data coverage','Training uses complete verified 3v3 matches. The two perspectives of a match stay together, as do matches with the same timestamp. Expanding earlier-time folds select the model by validation log loss. The latest time group holdout is used for final reporting only. Inputs are ally/enemy picks, mode, map and power difference. Post-match features are excluded. Estimates have not been probability calibrated, and repeated players plus leaderboard sampling limit generalization. The mode totals below include legacy records for auditing; training-ready matches exclude them.')}
      <div class="meta-summary-grid">${metric('Training-ready matches',num(ds.trainable_3v3_matches),'mint')}${metric('Legacy records excluded',num(ds.legacy_matches),'gold')}${metric('Active model',data.active_model_name==='Not Loaded'?'Awaiting training':data.active_model_name,'purple')}${metric('Holdout accuracy',m?pct(m.accuracy):'—','blue')}</div>
      ${!m?empty('A verified model has not been trained','Older model files remain on disk. They are excluded because their validation and outcome labels need correction. Collect verified battles, then train in Pipeline.'): `<p class="meta-validation">${num(validation.train_matches)} training matches · ${num(validation.test_matches)} holdout matches · ${num(validation.folds)} temporal folds</p>`}
      ${benchmarks.length?`<div class="meta-table-wrap"><table><thead><tr><th>Model</th><th>Validation log loss</th><th>Holdout ROC-AUC</th><th>Holdout accuracy</th></tr></thead><tbody>${benchmarks.map(b=>`<tr><td>${esc(b.name)}${b.is_best?' · Selected':''}</td><td>${Number(b.cv_log_loss_mean).toFixed(4)}</td><td>${Number(b.test_roc_auc).toFixed(4)}</td><td>${pct(b.test_accuracy)}</td></tr>`).join('')}</tbody></table></div>`:''}
      <h4>Stored matches by mode</h4><div class="meta-summary-grid">${(ds.modes_distribution || []).map(item=>metric(titleMode(item.mode),num(item.matches),'blue')).join('')}</div>
    </section>`;
  }
  function bulkProgress(data) {
    if(!data.available)return empty('Collection report unavailable',data.message || 'The worker has not published its first report.');
    const target=Number(data.target_players) || 100000, recordTarget=Number(data.target_observations) || 5000000;
    const stale=data.is_stale && ['running','backoff'].includes(data.state);
    const tags=Number(data.selected_players) || Number(data.candidate_tags) || 0;
    const bar=(label,value,max)=>`<div class="meta-bulk-progress"><div><span>${esc(label)}</span><strong>${pct(Math.min(1,value/max))}</strong></div><progress value="${Math.max(0,Math.min(max,value))}" max="${max}" aria-label="${esc(label)}"></progress><small>${num(value)} / ${num(max)}</small></div>`;
    const labels={running:'Running',backoff:'Retrying after a service delay',complete:'Complete',incomplete:'Finished with gaps',stopped:'Stopped',needs_token:'Token needs attention',disk_low:'Paused · low disk space',error:'Worker error'};
    return `<div class="meta-bulk-state"><span class="meta-bulk-badge ${stale?'is-stale':''}">${esc(stale?'Awaiting a fresh worker report':labels[data.state] || data.state)}</span><span>${data.phase==='collection'?'Collecting recent player matches':'Discovering player tags'}</span></div>
      <div class="meta-summary-grid">${metric('Players polled',num(data.players_polled),'blue')}${metric('Captured match records',num(data.player_match_observations),'mint')}${metric('Unique matches',num(data.unique_matches),'purple')}${metric('Eligible 3v3 matches',num(data.eligible_3v3_matches),'gold')}</div>
      <div class="meta-bulk-bars">${bar('Player tags',tags,target)}${bar('Players with 50 matches',Number(data.players_at_target) || 0,target)}${bar('Match records',Number(data.player_match_observations) || 0,recordTarget)}</div>
      <div class="meta-bulk-activity"><span>Latest worker activity</span><strong>${esc(data.message)}</strong><small>Last report ${esc(new Date(data.updated_at).toLocaleTimeString())} · publishes about every 30 seconds${stale?' · check the worker before assuming collection is active':''}</small></div>`;
  }
  function operations(data,bulk) {
    const t=data.telemetry, running=data.operation_state.running;
    return `<section class="meta-panel meta-bulk-panel">${heading('Live collection · 100,000 players','This separate background worker targets 100,000 player tags and 50 distinct captured matches per player. It publishes progress about every 30 seconds; this panel checks automatically. Each poll supplies up to 25 recent matches, so reaching 50 needs new activity. Shared matches are deduplicated, while player-relative results remain separate. The temporary CSV sample is not yet imported into the current model data. Stale reports are flagged; completed or unavailable players are skipped. All counts come from worker checkpoints.')}
      <div id="meta-bulk-live">${bulkProgress(bulk)}</div></section>
      <section class="meta-panel">${heading('Collect, verify and train','These manual controls operate on the current model data, separately from the bulk CSV sample above. Discovery gathers tags from leaderboards and club rosters, then follows observed participants in bounded batches. The target is a collection goal, not a guarantee. Collection is rate limited and stops on credential or exhausted rate-limit errors. Training runs in a worker thread while pages remain available. Only one operation runs at a time in this local server process. Saved rows survive restarts; in-flight manual jobs do not resume automatically.')}
      <div class="meta-summary-grid">${metric('Player pool',num(t.total_players),'blue')}${metric('Polled players',num(t.polled_players),'mint')}${metric('Stored matches',num(t.total_matches),'purple')}</div>
      <div class="meta-operation-grid"><form data-operation="scale-players"><h4>Discover players</h4><label>Pool target<input name="target_players" type="number" value="5000" min="100" max="100000" required></label><button type="submit" ${running?'disabled':''}>Discover tags</button></form>
        <form data-operation="collect"><h4>Collect current battles</h4><label>Players in this batch<input name="max_players" type="number" value="50" min="1" max="1000" required></label><label>Requests per second<input name="rps" type="number" value="2" min="1" max="10" step=".5" required></label><button type="submit" ${running?'disabled':''}>Collect battles</button></form>
        <form data-operation="retrain"><h4>Train a verified model</h4><p>Requires at least 25 complete 3v3 matches across six or more timestamps.</p><button type="submit" ${running?'disabled':''}>Train and evaluate</button></form></div>
      <div class="meta-operation-status"><strong id="meta-operation-title">${running?'Running: '+esc(data.operation_state.task):'Ready'}</strong><p id="meta-operation-message" role="status">${esc(data.operation_state.message)}</p><button id="meta-stop-operation" type="button" ${!running?'disabled':''}>Stop collection</button></div>
    </section>`;
  }
  function bindContent() {
    $('meta-active-slot')?.addEventListener('change',e=>{ui.activeSlot=e.target.value;refresh();});
    $('meta-owned')?.addEventListener('change',e=>{ui.owned=e.target.checked;refresh();});
    $('meta-clear-draft')?.addEventListener('click',()=>{ui.allies=[null,null,null];ui.enemies=[null,null,null];refresh();});
    $('meta-content').querySelectorAll('[data-slot]').forEach(select=>select.onchange=()=>{
      const [team,slot]=select.dataset.slot.split('_');(team==='ally'?ui.allies:ui.enemies)[Number(slot)-1]=select.value?Number(select.value):null;
      ui.activeSlot=select.dataset.slot;refresh();});
    $('meta-content').querySelectorAll('[data-pick]').forEach(button=>button.onclick=()=>{const [team,slot]=ui.activeSlot.split('_');
      (team==='ally'?ui.allies:ui.enemies)[Number(slot)-1]=Number(button.dataset.pick);const sequence=['ally_1','enemy_1','enemy_2','ally_2','ally_3','enemy_3'];
      ui.activeSlot=sequence.find(slot=>{const [side,n]=slot.split('_');return !(side==='ally'?ui.allies:ui.enemies)[Number(n)-1];}) || ui.activeSlot;refresh();});
    $('meta-content').querySelectorAll('[data-operation]').forEach(form=>form.onsubmit=async event=>{
      event.preventDefault();if(!form.reportValidity())return;
      const payload={};new FormData(form).forEach((value,key)=>payload[key]=Number(value));
      $('meta-content').querySelectorAll('[type="submit"]').forEach(button=>button.disabled=true);
      try {await request(`/api/ml/operations/${form.dataset.operation}`,payload);await refresh();}
      catch(error) {if(error.name!=='AbortError'){$('meta-operation-message').textContent=error.message;$('meta-content').querySelectorAll('[type="submit"]').forEach(button=>button.disabled=false);}}
    });
    $('meta-stop-operation')?.addEventListener('click',async()=>{try{await request('/api/ml/operations/cancel',{});await refresh();}
      catch(error){if(error.name!=='AbortError')$('meta-operation-message').textContent=error.message;}});
  }
  async function pollOperations() {
    if(ui.tab!=='operations' || location.pathname!=='/meta' || document.hidden) {ui.timer=setTimeout(pollOperations,3000);return;}
    const epoch=ui.epoch;
    try {
      const [op,bulk]=await Promise.all([request('/api/ml/operations/status'),request('/api/ml/bulk-dataset/status')]);if(epoch!==ui.epoch)return;
      const bulkMarkup=bulkProgress(bulk), bulkArea=$('meta-bulk-live');
      if(bulkArea && bulkArea.innerHTML!==bulkMarkup)bulkArea.innerHTML=bulkMarkup;
      if($('meta-operation-title'))$('meta-operation-title').textContent=op.running?'Running: '+op.task:'Ready';
      if($('meta-operation-message'))$('meta-operation-message').textContent=op.message;
      $('meta-content')?.querySelectorAll('[type="submit"]').forEach(button=>button.disabled=op.running);
      if($('meta-stop-operation'))$('meta-stop-operation').disabled=!op.running || op.task==='Model Training';
      const resultKey=JSON.stringify(op.last_result);
      if(!op.running && op.last_result && ui.lastCompleted!==resultKey) {
        ui.lastCompleted=resultKey;
        const [status, data]=await Promise.all([request('/api/ml/model-status'),request('/api/ml/operations/telemetry')]);
        if(epoch!==ui.epoch)return;
        ui.status=status;
        const ds=status.dataset, metrics=status.metrics;
        const cover=$('meta-view').querySelector('.meta-cover-metrics');
        if(cover)cover.innerHTML=metric('Tracked players',num(ds.total_discovered_players),'blue')+
          metric('Current matches',num(ds.verified_matches),'mint')+
          metric('Active model',metrics?.model_name || 'Awaiting training','purple')+
          metric('Holdout ROC-AUC',metrics?Number(metrics.roc_auc).toFixed(3):'—','gold');
        const summary=$('meta-content').querySelector('.meta-panel:not(.meta-bulk-panel) .meta-summary-grid');
        if(summary)summary.innerHTML=metric('Player pool',num(data.telemetry.total_players),'blue')+
          metric('Polled players',num(data.telemetry.polled_players),'mint')+metric('Stored matches',num(data.telemetry.total_matches),'purple');
      }
    } catch(error) {if(error.name==='AbortError')return;if($('meta-operation-message'))$('meta-operation-message').textContent='Connection interrupted. Retrying…';}
    if(epoch===ui.epoch && ui.tab==='operations')ui.timer=setTimeout(pollOperations,2500);
  }
  window.MetaExplorer={load,stop};
})();
