/* Presentation only. All readiness percentages and resource amounts come from
   ReadinessService; this file never recomputes costs or Claw probabilities. */
let readinessRequestSequence = 0;
let readinessSelectedBrawler = null;
const readinessPoolOverrides = new Map();

function readinessElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text != null) element.textContent = text;
  return element;
}

function readinessCurrencyIcon(currency) {
  const icon = readinessElement('span', `readiness-currency-icon currency-${currency}`);
  icon.setAttribute('aria-hidden', 'true');
  const files = { coins: 'coins', powerPoints: 'power-points', gems: 'gems' };
  const image = document.createElement('img');
  const assetUrl = getUiIconRecord('currencies', currency)?.local_url || `/assets/currencies/${files[currency] || files.coins}.png`;
  image.src = `${assetUrl}?v=20261002-2`;
  image.alt = '';
  image.decoding = 'async';
  icon.append(image);
  return icon;
}

function readinessNumber(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);
}

function readinessProbability(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value * 100);
}

function readinessSetRing(id, value, label, valueId) {
  const ring = $(id);
  if (!ring) return;
  ring.style.setProperty('--progress', value ?? 0);
  ring.classList.toggle('is-unavailable', value == null);
  ring.setAttribute('role', value == null ? 'img' : 'progressbar');
  ring.setAttribute('aria-label', value == null ? `${label}: not applicable` : label);
  if (value == null) {
    ring.removeAttribute('aria-valuenow');
    ring.removeAttribute('aria-valuemin');
    ring.removeAttribute('aria-valuemax');
  } else {
    ring.setAttribute('aria-valuemin', '0');
    ring.setAttribute('aria-valuemax', '100');
    ring.setAttribute('aria-valuenow', String(value));
    ring.setAttribute('aria-valuetext', `${readinessNumber(value)}% ready, ${readinessNumber(100 - value)}% remaining`);
  }
  setText(valueId, value == null ? '—' : `${readinessNumber(value)}%`);
}

function readinessCostContent(cost, estimated = false, currencies = null) {
  const holder = readinessElement('span', 'readiness-row-cost');
  const labels = { powerPoints: 'PP', coins: 'Coins', gems: 'Gems' };
  for (const currency of currencies || ['powerPoints', 'coins', 'gems']) {
    if (!currencies && !(cost[currency] > 0)) continue;
    const part = readinessElement('span', `readiness-cost-part cost-${currency}`);
    part.append(readinessCurrencyIcon(currency), readinessElement('span', '',
      `${readinessNumber(cost[currency])} ${labels[currency]}`));
    if (currency === 'gems' && estimated) part.title = 'Uses the configured reference Gem price. See readiness information for price details.';
    holder.append(part);
  }
  if (!holder.childElementCount) holder.textContent = '—';
  return holder;
}

function readinessItemIcon(row) {
  const holder = readinessElement('span', 'readiness-item-icon');
  if (row.category === 'power') {
    holder.append(readinessCurrencyIcon('powerPoints'));
  } else if (row.imageUrl) {
    const image = document.createElement('img');
    image.src = row.imageUrl;
    image.alt = '';
    image.loading = 'lazy';
    image.onerror = () => { holder.replaceChildren(readinessElement('span', '', row.category === 'buffies' ? '✦' : '◆')); };
    holder.append(image);
  } else holder.textContent = row.category === 'buffies' ? '✦' : '◆';
  holder.setAttribute('aria-hidden', 'true');
  return holder;
}

function readinessStatus(row) {
  const labels = { owned: '✓ Owned', stored: '✓ Stored', missing: 'Missing', unavailable: 'N/A' };
  const holder = readinessElement('span', `readiness-row-status status-${row.status}`, labels[row.status]);
  if (row.status === 'stored' || (row.status === 'missing' && row.unlockPower > (state.readiness?.currentPower || 0))) {
    holder.title = `Usable at Power ${row.unlockPower}`;
  }
  return holder;
}

function readinessRenderTotals(result) {
  const cost = result.costs.guaranteed;
  for (const id of ['readiness-overview-totals', 'readiness-plan-totals']) {
    const holder = $(id);
    if (!holder) continue;
    holder.replaceChildren();
    for (const [currency, label] of [['powerPoints', 'Power Points'], ['coins', 'Coins'], ['gems', 'Gems']]) {
      const card = readinessElement('div', `readiness-total-item total-${currency}`);
      const heading = readinessElement('span', 'readiness-total-label', label);
      heading.prepend(readinessCurrencyIcon(currency));
      const value = readinessNumber(cost[currency]);
      if (currency === 'gems' && cost.gemsEstimated) card.title = 'Uses the configured reference Gem price. See readiness information for price details.';
      card.append(heading, readinessElement('strong', '', value));
      holder.append(card);
    }
  }
  document.querySelectorAll('[data-readiness-total-title]').forEach((title, index) => {
    title.textContent = result.costsComplete ? 'TOTAL TO MAX READY' : 'KNOWN RESOURCE REQUIREMENTS';
    if (!title.parentElement.querySelector('.readiness-info-wrap')) {
      const info = readinessInfo('Total resource requirements', `readiness-total-info-${index}`);
      info.querySelector('.readiness-info-tooltip').append(readinessElement('p', '', 'Power upgrades + missing recommended equipment + direct Gems for Buffies.'));
      title.parentElement.append(info);
      readinessBindInfo(info);
    }
  });
  readinessRenderRoutes(result);
}

function readinessInfo(label, id) {
  const wrap = readinessElement('div', 'matchups-info-wrap readiness-info-wrap');
  const button = readinessElement('button', 'matchups-info-btn');
  button.type = 'button';
  button.setAttribute('aria-label', label);
  button.setAttribute('aria-controls', id);
  button.setAttribute('aria-expanded', 'false');
  const icon = readinessElement('span', 'matchups-info-icon', 'i');
  icon.setAttribute('aria-hidden', 'true');
  button.append(icon);
  const tooltip = readinessElement('div', 'matchups-info-tooltip readiness-info-tooltip');
  tooltip.id = id;
  tooltip.setAttribute('role', 'tooltip');
  tooltip.append(readinessElement('h3', '', label));
  wrap.append(button, tooltip);
  return wrap;
}

function readinessMoveInfoNotes(host, label, id, noteIds) {
  if (!host || host.querySelector(`#${id}`)) return;
  const info = readinessInfo(label, id);
  const tooltip = info.querySelector('.readiness-info-tooltip');
  for (const noteId of noteIds) {
    const note = $(noteId);
    if (!note) continue;
    note.className = '';
    tooltip.append(note);
  }
  host.append(info);
  readinessBindInfo(info);
}

function readinessRenderRoutes(result) {
  const claw = result.costs.buffieClawAlternative;
  const hasTargets = result.isOwned && result.costs.buffieDirect.missing > 0;
  $('readiness-plan-routes').classList.toggle('has-claw-route', hasTargets);
  $('readiness-plan-divider').classList.toggle('hidden', !hasTargets);
  const groupHolder = $('readiness-plan-claw-group');
  groupHolder.replaceChildren();
  groupHolder.classList.toggle('hidden', !hasTargets || !claw.group);
  if (hasTargets && claw.group) groupHolder.append(readinessClawGroup(claw.group));
  document.querySelectorAll('[data-readiness-direct-route]').forEach((label, index) => {
    label.classList.toggle('hidden', !hasTargets);
    if (!label.querySelector('.readiness-info-wrap')) {
      const info = readinessInfo('Direct Gems route information', `readiness-direct-route-info-${index}`);
      info.querySelector('.readiness-info-tooltip').append(readinessElement('p', '', 'Guaranteed acquisition using direct Gem purchases. Totals include Power upgrades, missing recommended equipment, and missing Buffies. Owned items cost nothing.'));
      label.append(info);
      readinessBindInfo(info);
    }
  });
  document.querySelectorAll('[data-readiness-route-comparison]').forEach((holder, index) => {
    holder.replaceChildren();
    holder.classList.toggle('hidden', !hasTargets);
    if (!hasTargets) return;
    if (!claw.available) {
      const heading = readinessElement('div', 'readiness-route-heading');
      const info = readinessInfo('Claw Machine route information', `readiness-claw-unavailable-info-${index}`);
      info.querySelector('.readiness-info-tooltip').append(readinessElement('p', '', claw.reason));
      heading.append(readinessElement('h4', 'readiness-route-title', 'Claw Machine unavailable'), info);
      holder.append(heading);
      readinessBindInfo(info);
      return;
    }
    const divider = readinessElement('div', 'readiness-route-divider');
    divider.append(readinessElement('span', '', 'OR'));
    const heading = readinessElement('div', 'readiness-route-heading');
    const actions = readinessElement('div', 'readiness-route-actions');
    const infoWrap = readinessElement('div', 'matchups-info-wrap readiness-info-wrap');
    const infoButton = readinessElement('button', 'matchups-info-btn');
    const tooltip = readinessElement('div', 'matchups-info-tooltip readiness-info-tooltip');
    tooltip.id = `readiness-claw-info-tooltip-${index}`;
    tooltip.setAttribute('role', 'tooltip');
    infoButton.type = 'button';
    infoButton.setAttribute('aria-label', 'Claw Machine route information');
    infoButton.setAttribute('aria-controls', tooltip.id);
    infoButton.setAttribute('aria-expanded', 'false');
    const icon = readinessElement('span', 'matchups-info-icon', 'i');
    icon.setAttribute('aria-hidden', 'true');
    infoButton.append(icon);
    infoWrap.append(infoButton, tooltip);
    actions.append(readinessElement('span', 'readiness-route-badge', '0 Gems'), infoWrap);
    heading.append(readinessElement('h4', 'readiness-route-title', 'Claw Machine route'), actions);
    const scenarios = readinessElement('div', 'readiness-route-scenarios');
    for (const [key, label] of [['bestCase', 'Best case'], ['expected', 'Average'], ['worstCase', 'Worst case']]) {
      const card = readinessElement('div', `readiness-route-scenario route-${key}`);
      const pulls = claw[key].pulls;
      card.append(readinessElement('strong', '', label), readinessElement('small', 'readiness-route-pulls',
        `${key === 'expected' ? '~' : key === 'worstCase' ? 'Up to ' : ''}${readinessNumber(pulls)} ${pulls === 1 ? 'pull' : 'pulls'}`));
      const costs = readinessElement('div', 'readiness-route-costs');
      for (const [currency, label] of [['powerPoints', 'Power Points'], ['coins', 'Coins']]) {
        const resource = readinessElement('div', `readiness-route-resource route-${currency}`);
        const resourceLabel = readinessElement('span', 'readiness-total-label', label);
        resourceLabel.prepend(readinessCurrencyIcon(currency));
        resource.append(resourceLabel, readinessElement('strong', '', readinessNumber(claw.totalToMaxReady[key][currency])));
        costs.append(resource);
      }
      card.append(costs);
      card.append(readinessElement('small', 'readiness-route-chance', key === 'expected'
        ? 'Expected cost'
        : `${readinessProbability(claw.completionProbabilities[key])}% chance to finish${key === 'worstCase' ? ' by then' : ''}`));
      scenarios.append(card);
    }
    const poolNote = claw.poolSource === 'trio_pool'
      ? `${claw.group.name}: ${claw.group.owned} / ${claw.group.total} Buffies owned across ${claw.group.members.map((member) => member.name).join(', ')}. ${claw.poolSize} eligible rewards remain.${claw.group.excluded ? ` ${claw.group.excluded} rewards for locked Brawlers are excluded.` : ''} Counts come from your loaded collection.`
      : claw.isEstimate ? `Reference pool: ${claw.poolSize} remaining rewards. Verify your machine’s count in the Claw section below.`
        : `${claw.poolSize} remaining rewards in ${claw.poolSource === 'user_input' ? 'your machine' : claw.poolName}.`;
    tooltip.append(readinessElement('h3', '', 'Claw Machine costs & odds'),
      readinessElement('p', '', `${readinessProbability(claw.startingTargetProbability)}% chance of a needed Buffie next pull`),
      readinessElement('p', 'readiness-route-note', `Totals include Power upgrades and the recommended build. ${poolNote} Odds assume every missing Buffie is in this pool and rewards are equally likely.`),
      readinessElement('p', '', 'Each pull awards one new Buffie with no duplicates, so the reward pool shrinks after every pull. Average costs are estimates, not guarantees. Choose either route; their costs are alternatives.'));
    if (holder.closest('.readiness-total-compact')) holder.append(divider);
    holder.append(heading);
    holder.append(scenarios);
    readinessBindInfo(infoWrap);
  });
}

function readinessClawGroup(group) {
  const holder = readinessElement('div', 'readiness-claw-group');
  const heading = readinessElement('div', 'readiness-claw-group-summary');
  const actions = readinessElement('div', 'readiness-heading-actions');
  const info = readinessInfo('Claw Machine group information', 'readiness-claw-group-info-tooltip');
  info.querySelector('.readiness-info-tooltip').append(readinessElement('p', '', `${group.name}: Buffie ownership across ${group.members.map((member) => member.name).join(', ')} comes from your loaded collection. Owned Buffies are removed from the reward pool. Gray icons are missing or locked; colored icons are owned.`));
  if (group.excluded) info.querySelector('.readiness-info-tooltip').append(readinessElement('p', '', `${group.remaining} eligible rewards remain; ${group.excluded} rewards for locked Brawlers are excluded.`));
  actions.append(readinessElement('span', '', `${group.owned} / ${group.total} owned · ${group.missing} missing`), info);
  heading.append(readinessElement('strong', '', 'Claw Machine group'), actions);
  readinessBindInfo(info);
  const members = readinessElement('div', 'readiness-claw-group-members');
  for (const member of group.members) {
    const card = readinessElement('div', 'readiness-claw-member');
    const name = readinessElement('div', 'readiness-claw-member-name');
    const portrait = readinessElement('span', 'readiness-claw-portrait');
    addImageWithFallback(portrait, { id: member.brawlerId, name: member.name }, 'readiness-claw-portrait-img');
    name.append(portrait, readinessElement('strong', '', member.name));
    const ownedCount = readinessElement('small', 'readiness-claw-member-count', member.isOwned ? `${member.owned} / ${member.total}` : 'Locked');
    ownedCount.title = member.isOwned ? `${member.owned} of ${member.total} Buffies owned` : 'Brawler locked';
    card.append(name, ownedCount);
    const items = readinessElement('div', 'readiness-claw-member-items');
    for (const [category, label] of [['gadget', 'Gadget'], ['star_power', 'Star Power'], ['hypercharge', 'Hypercharge']]) {
      const status = !member.isOwned ? 'locked' : member.categories[category] ? 'owned' : 'missing';
      const item = readinessElement('span', `buffie-${status}`);
      item.title = `${label} Buffie: ${status}`;
      const image = document.createElement('img');
      image.src = state.visualAssets?.brawlers?.[String(member.brawlerId)]?.buffies?.[category]?.local_url
        || `/assets/equipment/buffies/${member.brawlerId}-${category.replace('_', '-')}.png`;
      image.alt = `${member.name} ${item.title}`;
      image.decoding = 'async';
      item.append(image);
      items.append(item);
    }
    card.append(items);
    members.append(card);
  }
  holder.append(heading, members);
  return holder;
}

function readinessRequirementRow(item, result) {
  const row = readinessElement('tr', `readiness-requirement status-${item.status}`);
  const label = readinessElement('th');
  label.scope = 'row';
  const content = readinessElement('div', 'readiness-requirement-copy');
  const text = readinessElement('div');
  text.append(readinessElement('strong', '', item.category === 'power' ? item.label : item.name));
  if (item.category === 'build') text.append(readinessElement('small', '', item.label));
  content.append(readinessItemIcon(item), text);
  label.append(content);
  const status = readinessElement('td');
  status.append(readinessStatus(item));
  const cost = readinessElement('td');
  cost.append(readinessCostContent(item.cost, item.gemsEstimated));
  row.append(label, status, cost);
  return row;
}

function readinessSubtotalRow(category, heading, result) {
  const subtotal = result.costs.subtotals[category];
  const row = readinessElement('tr', 'readiness-subtotal');
  const label = readinessElement('th', '', `${heading} subtotal`);
  label.colSpan = 2;
  label.scope = 'row';
  const cost = readinessElement('td');
  cost.append(readinessCostContent(subtotal, subtotal.gemsEstimated,
    category === 'power' ? ['powerPoints', 'coins'] : category === 'build' ? ['coins'] : ['gems']));
  row.append(label, cost);
  return row;
}

function readinessRenderBreakdown(result) {
  const body = $('readiness-breakdown-body');
  if (!body) return;
  body.replaceChildren();
  const groups = [['power', 'Power upgrades'], ['build', 'Recommended build'], ['buffies', 'Buffies']];
  for (const [category, heading] of groups) {
    const rows = result.breakdown.filter((row) => row.category === category);
    const header = readinessElement('tr', 'readiness-section-row');
    const cell = readinessElement('th', '', heading);
    cell.colSpan = 3;
    cell.scope = 'colgroup';
    header.append(cell);
    body.append(header);
    if (!rows.length) {
      const row = readinessElement('tr');
      const empty = readinessElement('td', 'readiness-table-empty', category === 'power'
        ? `✓ Power ${result.currentPower} already reaches your target`
        : category === 'buffies' ? 'Buffies not released' : 'No build recommendation available');
      empty.colSpan = 3;
      row.append(empty);
      body.append(row);
    }
    for (const item of rows) body.append(readinessRequirementRow(item, result));
    body.append(readinessSubtotalRow(category, heading, result));
  }
}

function readinessRenderClaw(result) {
  const claw = result.costs.buffieClawAlternative;
  const hasTargets = result.isOwned && result.costs.buffieDirect.missing > 0;
  const scenarios = $('readiness-claw-scenarios');
  const odds = $('readiness-claw-odds');
  scenarios.replaceChildren();
  odds.replaceChildren();
  setText('readiness-claw-odds-note', '');
  $('readiness-claw-each').replaceChildren();
  for (const id of ['readiness-claw-each', 'readiness-pool-note', 'readiness-claw-odds', 'readiness-claw-scenarios', 'readiness-claw-footnote']) {
    $(id).classList.toggle('hidden', !hasTargets);
  }
  $('readiness-pool-form').classList.toggle('hidden', !hasTargets || claw.poolSource === 'trio_pool');
  $('readiness-pool-error').classList.add('hidden');
  setText('readiness-claw-intro', hasTargets
    ? 'Want to save Gems? Each pull gives one random new Buffie.'
    : !result.counts.buffiesTotal ? 'Buffies are not available for this Brawler yet.'
      : !result.isOwned ? 'Unlock this Brawler before planning Claw rewards.'
        : 'All Buffies for this Brawler are already owned. No Claw pulls are needed.');
  if (!hasTargets) return;
  const input = $('readiness-pool-size');
  input.min = String(claw.targetCount);
  input.value = String(claw.poolSize ?? claw.targetCount);
  setText('readiness-pool-note', claw.poolSource === 'trio_pool'
    ? `${claw.poolName}: ${claw.group.owned} / ${claw.group.total} Buffies owned across the trio. ${claw.poolSize} eligible rewards remain. Calculated automatically from your collection.${claw.group.excluded ? ` ${claw.group.excluded} rewards for locked Brawlers are excluded.` : ''}`
    : claw.poolSource === 'reference'
    ? 'Reference pool estimate. Enter the remaining reward count from your machine for accurate odds.'
    : claw.poolSource === 'configured_pool' ? `${claw.poolName} · owned rewards and locked Brawlers excluded`
      : 'Using the remaining reward count you entered. All desired Buffies must be in this machine.');
  if (!claw.available) {
    odds.append(readinessElement('p', 'readiness-pool-error', claw.reason));
    $('readiness-claw-each').classList.add('hidden');
    $('readiness-claw-footnote').classList.add('hidden');
    return;
  }
  $('readiness-claw-each').replaceChildren(readinessElement('strong', '', 'Each pull'), readinessCostContent(claw.perPull));
  odds.append(readinessElement('strong', '', `${readinessProbability(claw.startingTargetProbability)}% chance of a target next pull`));
  setText('readiness-claw-odds-note', `${claw.targetCount} desired / ${claw.poolSize} remaining rewards · ${readinessProbability(claw.individualTargetProbability)}% for one specific Buffie`);
  for (const [key, label] of [['bestCase', 'Best case'], ['expected', 'Estimated RNG cost'], ['worstCase', 'Worst ordering']]) {
    const cost = claw[key];
    const card = readinessElement('div', `readiness-claw-scenario scenario-${key}`);
    const copies = readinessElement('div');
    copies.append(readinessElement('strong', '', label), readinessElement('small', '',
      `${key === 'worstCase' ? 'Up to ' : key === 'expected' ? '~' : ''}${readinessNumber(cost.pulls)} ${cost.pulls === 1 ? 'pull' : 'pulls'} for ${claw.targetCount === 1 ? 'your Buffie' : `all ${claw.targetCount} Buffies`}`));
    card.append(copies, readinessCostContent(cost));
    scenarios.append(card);
  }
}

function readinessRenderResult(result) {
  state.readiness = result;
  const overviewTooltip = $('readiness-info-tooltip');
  if ($('readiness-overview-copy').parentElement !== overviewTooltip) {
    overviewTooltip.insertBefore($('readiness-overview-copy'), $('readiness-scoring-copy'));
  }
  readinessMoveInfoNotes($('readiness-plan-info'), 'Readiness plan information', 'readiness-plan-info-tooltip', ['readiness-plan-note']);
  readinessMoveInfoNotes($('readiness-breakdown-info'), 'Upgrade breakdown information', 'readiness-breakdown-info-tooltip', ['readiness-breakdown-notes']);
  readinessMoveInfoNotes($('readiness-buffie-info'), 'Buffie progress information', 'readiness-buffie-info-tooltip', ['readiness-buffie-note']);
  readinessMoveInfoNotes($('readiness-direct-info'), 'Direct Gems information', 'readiness-direct-info-tooltip', ['readiness-direct-note']);
  readinessMoveInfoNotes($('readiness-claw-details-info'), 'Claw Machine information', 'readiness-claw-details-info-tooltip', ['readiness-claw-intro', 'readiness-pool-note', 'readiness-claw-odds-note', 'readiness-claw-footnote']);
  setText('readiness-source', result.inventorySource === 'DEMO' ? 'DEMO ACCOUNT' : 'YOUR BUILD');
  setText('readiness-plan-source', result.inventorySource === 'DEMO' ? 'DEMO ACCOUNT' : 'YOUR BUILD');
  setText('readiness-status', !result.isOwned ? 'UNLOCK FIRST' : result.complete ? 'MAX READY' : 'IN PROGRESS');
  setText('readiness-power-target', result.isOwned ? `Power ${result.currentPower} → Target ${result.targetPower}` : `After unlock: Power 1 → ${result.targetPower}`);
  setText('readiness-overview-copy', !result.isOwned ? 'Unlock this Brawler to track your readiness. The costs below preview the build after unlock.'
    : result.complete ? 'Your Power, recommended equipment, and available Buffies are complete.'
      : `Progress toward Power ${result.targetPower} and your recommended build.`);
  readinessSetRing('readiness-overall-ring', result.overallProgress, 'Overall readiness', 'readiness-overall-value');
  for (const [key, label] of [['power', 'Power Level'], ['buffies', 'Buffies']]) {
    readinessSetRing(`readiness-${key}-ring`, result.progress[key], `${label} progress`, `readiness-${key}-percent`);
  }
  for (const [key, label] of [['gears', 'Gears'], ['abilities', 'Gadget + Star Power'], ['hypercharge', 'Hypercharge']]) {
    const category = result.categoryProgress[key];
    readinessSetRing(`readiness-${key}-ring`, category.progress, `${label} progress`, `readiness-${key}-percent`);
    setText(`readiness-${key}-caption`, category.total ? `${category.owned} / ${category.total} owned` : 'Not available');
  }
  setText('readiness-power-caption', result.isOwned ? `${result.currentPower} → ${result.targetPower}` : 'After unlock');
  setText('readiness-buffies-caption', result.counts.buffiesTotal ? `${result.counts.buffiesOwned} / ${result.counts.buffiesTotal} owned` : 'Not released');
  const note = !result.isOwned ? 'Preview from Power 1 after unlocking this Brawler. Brawler unlock cost is separate.'
    : !result.costsComplete ? 'Some build or price information is unavailable. Totals cover the known requirements only.'
      : result.inventorySource === 'DEMO' ? 'Sample account inventory. Connect your player tag for your own readiness and costs.' : 'Only missing items in the recommended build are charged. Owned items below their unlock Power are stored.';
  setText('readiness-plan-note', note);
  readinessRenderTotals(result);
  readinessRenderBreakdown(result);
  const breakdownNotes = $('readiness-breakdown-notes');
  breakdownNotes.replaceChildren(readinessElement('p', '', 'Only missing items in the recommended build are charged. Owned equipment below its unlock Power is stored.'));
  for (const row of result.breakdown) {
    const notes = [row.note];
    if (row.available && row.unlockPower > result.currentPower && row.category !== 'power') notes.push(`Usable at Power ${row.unlockPower}`);
    if (notes.some(Boolean)) breakdownNotes.append(readinessElement('p', '', `${row.label}: ${notes.filter(Boolean).join(' · ')}`));
  }
  setText('readiness-buffie-note', result.counts.buffiesTotal ? 'Buffie progress counts owned Buffies. Cosmetic Buffies do not count.' : 'Buffies are not released for this Brawler. They do not reduce readiness.');
  setText('readiness-buffie-count', result.counts.buffiesTotal ? `${result.counts.buffiesOwned} / ${result.counts.buffiesTotal} owned` : 'Not released');
  const buffies = $('readiness-buffie-list');
  buffies.replaceChildren();
  for (const row of result.breakdown.filter((row) => row.category === 'buffies')) {
    buffies.append(readinessRequirementRow(row, result));
  }
  if (!buffies.childElementCount) {
    const row = readinessElement('tr');
    const cell = readinessElement('td', 'readiness-table-empty', 'Buffies not released');
    cell.colSpan = 3;
    row.append(cell);
    buffies.append(row);
  }
  buffies.append(readinessSubtotalRow('buffies', 'Buffies', result));
  $('readiness-direct-card').classList.toggle('hidden', !result.counts.buffiesTotal);
  const direct = result.costs.buffieDirect;
  $('readiness-direct-gems').replaceChildren(readinessCurrencyIcon('gems'),
    readinessElement('span', '', `${readinessNumber(direct.gems)} Gems`));
  setText('readiness-direct-note', direct.missing ? `${direct.missing} missing ${direct.missing === 1 ? 'Buffie' : 'Buffies'}. ${direct.estimated ? 'Uses configured reference prices; see the readiness info button for details.' : 'Using the configured direct-purchase prices.'}` : 'All available Buffies are owned. No Gems needed.');
  readinessRenderClaw(result);
  const scoring = $('readiness-scoring-copy');
  scoring.replaceChildren(readinessElement('p', '', 'Power progress uses current Power divided by target Power. Build progress counts only the exact recommended items. Buffie progress counts Buffies only.'));
  const weightLabels = { power: 'Power', gadget: 'Gadget', star_power: 'Star Power', gears: 'Gears', hypercharge: 'Hypercharge', buffies: 'Buffies' };
  const weights = readinessElement('p', '', Object.entries(result.weights).map(([key, value]) => `${weightLabels[key]} ${value}`).join(' · '));
  scoring.append(weights, readinessElement('p', '', 'These are relative weights. Unreleased or unavailable components are excluded and the remaining weights are normalized. Cosmetic Buffies do not count.'));
  const pricedBuffies = result.breakdown.filter((row) => row.category === 'buffies' && row.available);
  if (pricedBuffies.length) {
    scoring.append(readinessElement('h4', '', 'Gem prices used'));
    for (const row of pricedBuffies) {
      scoring.append(readinessElement('p', 'readiness-info-price', `${row.label}: ${readinessNumber(row.directGemPrice)} Gems${row.directGemPriceEstimated ? ' (reference price)' : ''}`));
    }
    scoring.append(readinessElement('p', '', pricedBuffies.some((row) => row.directGemPriceEstimated)
      ? 'Reference prices may differ from the current in-game shop offer.'
      : 'Totals use standard direct-purchase prices. Limited-time shop offers may cost less. Owned Buffies cost 0 Gems.'));
    const sources = readinessElement('p', 'readiness-info-sources');
    for (const source of result.buffiePriceSources || []) {
      if (!source.url.startsWith('https://')) continue;
      if (sources.childNodes.length) sources.append(document.createTextNode(' · '));
      const link = readinessElement('a', '', source.label);
      link.href = source.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.title = source.scope;
      sources.append(link);
    }
    if (sources.childNodes.length) scoring.append(sources);
  }
  $('readiness-loading').classList.add('hidden');
  $('readiness-overview').classList.remove('hidden');
  $('readiness-planning-panel').classList.remove('hidden');
}

async function loadBrawlerReadiness(brawler, manualPoolSize) {
  const sequence = ++readinessRequestSequence;
  const isPoolUpdate = manualPoolSize !== undefined;
  readinessSelectedBrawler = brawler;
  if (!isPoolUpdate) {
    state.readiness = null;
    $('readiness-overview')?.classList.add('hidden');
    $('readiness-planning-panel')?.classList.add('hidden');
    setText('readiness-loading', 'Calculating your build…');
    $('readiness-loading')?.classList.remove('hidden');
  }
  $('readiness-pool-error')?.classList.add('hidden');
  const inventory = state.ownedBrawlers.map((item) => ({
    id: item.id, name: item.name, power: item.power,
    gadgets: item.gadgets || [], star_powers: item.star_powers || [], gears: item.gears || [],
    hypercharges: item.hypercharges || [], buffies: getBuffieFlags(item),
  }));
  const poolKey = `${state.player?.source || 'USER_INPUT'}:${state.player?.tag || 'preview'}:${brawler.id}`;
  const inventorySignature = JSON.stringify(inventory.map((item) => [item.id, item.buffies]));
  const savedPool = readinessPoolOverrides.get(poolKey);
  // A manually observed count expires when the account's Buffie inventory changes.
  const poolSize = isPoolUpdate ? manualPoolSize : savedPool?.inventorySignature === inventorySignature ? savedPool.size : undefined;
  try {
    const result = await request(`/api/brawlers/${brawler.id}/readiness`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brawlers: inventory, source: state.player?.source || 'USER_INPUT', remainingClawPoolSize: poolSize ?? null }),
    });
    if (sequence !== readinessRequestSequence || state.page !== 'detail' || Number(location.pathname.split('/').pop()) !== brawler.id) return;
    if (isPoolUpdate) readinessPoolOverrides.set(poolKey, { size: manualPoolSize, inventorySignature });
    readinessRenderResult(result);
  } catch (error) {
    if (sequence !== readinessRequestSequence || state.page !== 'detail' || Number(location.pathname.split('/').pop()) !== brawler.id) return;
    if (isPoolUpdate) {
      setText('readiness-pool-error', error.message);
      $('readiness-pool-error').classList.remove('hidden');
    } else {
      setText('readiness-loading', 'Readiness could not be loaded. Refresh the page to try again.');
    }
  }
}

function readinessPositionInfo(infoWrap) {
  const infoButton = infoWrap.querySelector('.matchups-info-btn');
  const tooltip = infoWrap.querySelector('.readiness-info-tooltip');
  const bounds = infoButton.getBoundingClientRect();
  const viewportWidth = document.documentElement.clientWidth;
  const tooltipWidth = Math.min(360, viewportWidth - 48);
  const tooltipRight = Math.min(viewportWidth - 24, Math.max(tooltipWidth + 24, bounds.right));
  tooltip.style.setProperty('--readiness-tooltip-width', `${tooltipWidth}px`);
  tooltip.style.setProperty('--readiness-tooltip-right', `${bounds.right - tooltipRight}px`);
  const navigation = document.querySelector('.mobile-nav');
  const viewportBottom = navigation && getComputedStyle(navigation).display !== 'none'
    ? navigation.getBoundingClientRect().top : window.innerHeight;
  const below = viewportBottom - bounds.bottom - 24;
  const above = bounds.top - 24;
  const opensAbove = below < Math.min(tooltip.scrollHeight, 340) && above > below;
  infoWrap.classList.toggle('opens-above', opensAbove);
  tooltip.style.setProperty('--readiness-tooltip-space', `${Math.max(80, opensAbove ? above : below)}px`);
}

function readinessSetInfoOpen(infoWrap, open) {
  const infoButton = infoWrap.querySelector('.matchups-info-btn');
  if (open) readinessPositionInfo(infoWrap);
  infoWrap.classList.toggle('is-open', open);
  infoWrap.classList.toggle('is-dismissed', !open);
  infoButton.classList.toggle('active', open);
  infoButton.setAttribute('aria-expanded', String(open));
}

function readinessBindInfo(infoWrap) {
  if (!infoWrap || infoWrap.dataset.bound) return;
  infoWrap.dataset.bound = 'true';
  const infoButton = infoWrap.querySelector('.matchups-info-btn');
  infoButton.addEventListener('click', () => readinessSetInfoOpen(infoWrap, !infoWrap.classList.contains('is-open')));
  infoWrap.addEventListener('mouseenter', () => {
    readinessPositionInfo(infoWrap);
    infoWrap.classList.remove('is-dismissed');
  });
  infoWrap.addEventListener('mouseleave', () => infoWrap.classList.remove('is-dismissed'));
  infoButton.addEventListener('focus', () => {
    readinessPositionInfo(infoWrap);
    infoWrap.classList.remove('is-dismissed');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  readinessBindInfo($('readiness-info-btn')?.closest('.readiness-info-wrap'));
  const repositionIfVisible = () => document.querySelectorAll('.readiness-info-wrap').forEach((wrap) => {
    if (wrap.classList.contains('is-open') || wrap.matches(':hover, :focus-within')) readinessPositionInfo(wrap);
  });
  window.addEventListener('resize', repositionIfVisible);
  window.addEventListener('scroll', repositionIfVisible, { passive: true });
  document.addEventListener('click', (event) => document.querySelectorAll('.readiness-info-wrap').forEach((wrap) => {
    if (!wrap.contains(event.target)) readinessSetInfoOpen(wrap, false);
  }));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') document.querySelectorAll('.readiness-info-wrap').forEach((wrap) => readinessSetInfoOpen(wrap, false));
  });
  $('readiness-pool-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!readinessSelectedBrawler) return;
    const input = $('readiness-pool-size');
    if (!input.reportValidity()) return;
    const button = event.currentTarget.querySelector('button');
    button.disabled = true;
    try { await loadBrawlerReadiness(readinessSelectedBrawler, Number(input.value)); }
    finally { button.disabled = false; }
  });
});
