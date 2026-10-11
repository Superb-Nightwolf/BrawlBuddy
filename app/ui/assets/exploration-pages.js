/* Shared information controls for matches, rankings and map exploration. */
(() => {
  let sequence = 0;
  function infoMarkup(title, details, id = `explore-help-${++sequence}`) {
    const wrap = readinessInfo(`${title} information`, id);
    const tooltip = wrap.querySelector('.readiness-info-tooltip');
    tooltip.querySelector('h3').textContent = formatUiCopy(title);
    const copy = document.createElement('p');
    copy.textContent = formatUiCopy(details);
    tooltip.append(copy);
    return wrap.outerHTML;
  }
  function bind(root = document) {
    root.querySelectorAll('.readiness-info-wrap').forEach(readinessBindInfo);
  }
  function updateInfo(id, title, details) {
    const host = document.getElementById(id);
    if (!host) return;
    if (!host.querySelector('.readiness-info-wrap')) host.innerHTML = infoMarkup(title, details);
    else {
      host.querySelector('.readiness-info-tooltip h3').textContent = formatUiCopy(title);
      host.querySelector('.readiness-info-tooltip p').textContent = formatUiCopy(details);
    }
    bind(host);
  }
  function sourceLabel(source) {
    return ({LIVE:'Current snapshot',OFFICIAL_API:'Current snapshot',CACHE:'Cached snapshot',DEMO:'Sample data'})[source] || 'Information unavailable';
  }
  const arrow = '<svg class="explore-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>';
  const roots = ['battles-view','events-view','leaderboards-view'].map(id=>document.getElementById(id));
  roots.filter(Boolean).forEach(root => {
    root.querySelectorAll('[data-explore-info]').forEach(host=>updateInfo(host.id,host.dataset.exploreTitle,host.dataset.exploreInfo));
    DashboardUI.hydrate(root);
  });
  globalThis.ExplorationPages = {infoMarkup,bind,updateInfo,sourceLabel,arrow};
})();
