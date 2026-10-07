/* Shared charts and semantic symbols for account and club snapshots */
(() => {
  const palette = ['#2585ee','#8d63d7','#29b18d','#e7ad27','#ed6587','#41b5d2','#f08c47','#8395af'];
  const esc = (value) => escapeMarkup(formatUiCopy(value));
  const num = (value) => value == null ? '—' : new Intl.NumberFormat(undefined,{maximumFractionDigits:2}).format(value);
  const pct = (value) => value == null ? '—' : `${num(value)}%`;
  const assets = {
    trophy:'icon_trophy.png', gadget:'section_gadget.png', starPower:'section_star_power.webp',
    gear:'section_gear.png', hypercharge:'section_hypercharge.png', buffie:'buffies/generic.png',
    coins:'currencies/coins.png', powerPoints:'currencies/power-points.png', gems:'currencies/gems.png',
    prestige:'filter-prestige.png', collection:'brawl-stars-symbol-official.png',
  };
  // Match the roster's visible artwork bounds while retaining the original files
  const frames = {
    'section_gadget.png':[1254,1254,99,92,1049,1050],
    'section_gear.png':[1254,1254,185,186,880,869],
    'section_hypercharge.png':[1254,1254,175,85,901,1037],
    'brawl-stars-symbol-official.png':[1502,852,502,177,498,498],
  };
  const paths = {
    power:'<path d="m13 2-9 12h7l-1 8 10-13h-7z"/>',
    streak:'<path d="M3 17h5l4-5 4 2 5-8M17 6h4v4"/><path d="M3 7h5M3 11h3"/>',
    team:'<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M21 21v-3a6 6 0 0 0-4-5"/>',
    roles:'<rect x="8" y="2" width="8" height="6" rx="1"/><path d="M12 8v5M4 13h16M4 13v3M20 13v3"/><rect x="1" y="16" width="6" height="6" rx="1"/><rect x="17" y="16" width="6" height="6" rx="1"/>',
    build:'<path d="M9 3h6M8 4H5v18h14V4h-3"/><path d="m8 11 2 2 5-5M8 18h7"/>',
    equipment:'<path d="M14 4a6 6 0 0 0-7 7l-5 5 6 6 5-5a6 6 0 0 0 7-7l-4 4-6-6z"/>',
    wins:'<path d="M7 3h10v5a5 5 0 0 1-10 0zM12 13v6M7 22h10M8 19h8"/><path d="M7 5H3v2a5 5 0 0 0 5 5M17 5h4v2a5 5 0 0 1-5 5"/>',
    battle:'<path d="m4 3 13 13M3 4l4-1-1 4M20 3 7 16M21 4l-4-1 1 4M3 17l4 4M17 21l4-4M5 19l-2 2M19 19l2 2"/>',
    chart:'<path d="M3 3v18h18M7 17v-5M12 17V8M17 17V4"/>',
    records:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6M9 11h6M9 15h3"/>',
    target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    lock:'<rect x="5" y="10" width="14" height="12" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 15v3"/>',
    refresh:'<path d="M21 8a9 9 0 0 0-16-3L2 8M2 3v5h5M3 16a9 9 0 0 0 16 3l3-3M22 21v-5h-5"/>',
    copy:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  };
  function image(asset, className = 'ov-art') {
    const frame = frames[asset];
    if (!frame) return sectionIconMarkup(asset,className);
    const [width,height,x,y,w,h] = frame;
    return `<svg class="${className} ov-game-art" viewBox="${x} ${y} ${w} ${h}" aria-hidden="true"><image href="/assets/${asset}" width="${width}" height="${height}"/></svg>`;
  }
  function icon(key, className = 'ov-art') {
    if (assets[key]) return image(assets[key],className);
    if (!paths[key]) return '';
    return `<svg class="${className} ov-ui-symbol" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[key]}</svg>`;
  }
  function rowLabel(row) {
    let symbol = row.icon ? icon(row.icon,'ov-row-icon') : row.art ? image(row.art,'ov-row-icon')
      : row.iconGroup ? uiIconMarkup(row.iconGroup,row.iconValue || row.label,'ov-row-icon') : '';
    if (row.id) return `<a href="/brawlers/${Number(row.id)}">${brawlerIconMarkup(row)}<span>${esc(row.label)}</span></a>`;
    if (row.tag) return `<a href="/?tag=${encodeURIComponent(row.tag)}"><img src="https://cdn.brawlify.com/profile-icons/regular/${Number(row.icon_id) || 28000000}.png" alt="" loading="lazy" onerror="this.onerror=null;this.src='/assets/rarity-skull.svg'"><span>${esc(row.label)}</span></a>`;
    return `<span class="ov-row-name">${symbol}<span>${esc(row.label)}</span></span>`;
  }
  function empty(message = 'This information was not returned') {
    return `<div class="ov-empty">${icon('records','ov-empty-art')}<p>${esc(message)}</p></div>`;
  }
  function card({title,body,note='',span=6,kicker='',symbol=''}) {
    return `<article class="ov-card ov-span-${span}"><div class="ov-card-heading"><div>${kicker ? `<span class="ov-kicker">${esc(kicker)}</span>` : ''}<h3>${esc(title)}</h3></div>${symbol ? `<span class="ov-card-emblem">${symbol}</span>` : ''}</div><div class="ov-card-body">${body}</div>${note ? `<p class="ov-note">${esc(note)}</p>` : ''}</article>`;
  }
  function metric(label,value,detail,tone='blue',symbol='',id='') {
    return `<article class="ov-stat ov-stat-${tone}"><div class="ov-stat-heading"><span>${esc(label)}</span>${symbol}</div><strong ${id ? `id="${id}"` : ''}>${value}</strong><small>${esc(detail)}</small></article>`;
  }
  function stats(items) {
    return `<div class="ov-mini-stats">${items.map(([label,value,key])=>`<div><span>${key ? icon(key,'ov-resource-icon') : ''}${esc(label)}</span><strong>${value}</strong></div>`).join('')}</div>`;
  }
  function donut(rows,center,label) {
    const valid = rows.filter(row=>Number.isFinite(row.value) && row.value > 0);
    const total = valid.reduce((sum,row)=>sum+row.value,0);
    let angle = 0;
    const stops = valid.map((row,i)=>{const start=angle;angle+=row.value/total*360;return `${row.color || palette[i%palette.length]} ${start}deg ${angle}deg`;});
    return `<div class="ov-donut-layout"><div class="ov-donut" role="img" aria-label="${esc(rows.map(row=>`${row.label} ${num(row.value)}`).join(', '))}" style="--ov-gradient:${total ? `conic-gradient(${stops.join(',')})` : '#e8eef6'}"><div><strong>${center}</strong><span>${esc(label)}</span></div></div><div class="ov-legend">${rows.map((row,i)=>`<div><i style="--ov-color:${row.color || palette[i%palette.length]}"></i>${rowLabel(row)}<strong>${num(row.value)}</strong><small>${total && row.value != null ? pct(row.value/total*100) : '—'}</small></div>`).join('')}</div></div>`;
  }
  function bars(rows,options={}) {
    if (!rows.length) return empty();
    const max = options.max || Math.max(1,...rows.map(row=>row.value || 0));
    return `<div class="ov-bars ${options.compact ? 'ov-bars-compact' : ''}">${rows.map((row,i)=>`<div class="ov-bar-row"><div class="ov-bar-label">${rowLabel(row)}<strong>${options.percent ? pct(row.value) : num(row.value)}${options.suffix || ''}</strong></div><div class="ov-track"><i style="width:${Math.min(100,Math.max(0,(row.value || 0)/max*100))}%;--ov-color:${row.color || palette[i%palette.length]}"></i></div>${row.sub ? `<small>${esc(row.sub)}</small>` : ''}</div>`).join('')}</div>`;
  }
  function columns(rows,color=palette[0]) {
    const max = Math.max(1,...rows.map(row=>row.value || 0));
    return `<div class="ov-columns" role="img" aria-label="${esc(rows.map(row=>`${row.label}: ${num(row.value)}`).join(', '))}">${rows.map((row,i)=>`<div class="ov-column"><strong>${num(row.value)}</strong><div class="ov-column-track"><i style="height:${(row.value || 0)/max*100}%;--ov-color:${Array.isArray(color) ? color[i%color.length] : color}"></i></div><span>${esc(row.label)}</span></div>`).join('')}</div>`;
  }
  function hydrate(root = document) {
    root.querySelectorAll('[data-dashboard-icon]').forEach(element=>{
      element.innerHTML = icon(element.dataset.dashboardIcon,'ov-art');
    });
  }
  globalThis.DashboardUI = {image,icon,empty,card,metric,stats,donut,bars,columns,num,pct,palette,hydrate};
  hydrate();
})();
