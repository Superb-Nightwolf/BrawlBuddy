/* Illustrated controls enhance the existing selects and keep their filter values. */
(() => {
  const art = {
    all: '/assets/roster-all.svg',
    gadget: '/assets/section_gadget.png?v=2',
    star: '/assets/section_star_power.webp',
    hyper: '/assets/section_hypercharge.png?v=2',
    gear: '/assets/section_gear.png?v=2',
    buffie: '/assets/buffies/generic.png',
    trophy: '/assets/icon_trophy.png',
    power_asc: '/assets/sort-power-asc.svg',
    power_desc: '/assets/sort-power-desc.svg',
    prestige: '/assets/filter-prestige.png',
    newest: '/assets/sort-newest.svg',
    oldest: '/assets/sort-oldest.svg',
    name: '/assets/sort-name-az.svg',
    name_desc: '/assets/sort-name-za.svg',
    rarity: '/assets/roster-rarity.svg',
  };
  const rarityTiers = {
    rarity_common: 'S',
    rarity_rare: 'R',
    rarity_super_rare: 'SR',
    rarity_epic: 'E',
    rarity_mythic: 'M',
    rarity_legendary: 'L',
    rarity_ultra_legendary: 'UL',
  };
  // Visible artwork bounds exclude the different transparent margins in each source.
  const equipmentFrames = {
    gear: [1254, 1254, 185, 186, 880, 869],
    gadget: [1254, 1254, 99, 92, 1049, 1050],
    star: [872, 910, 0, 0, 872, 910],
    hyper: [1254, 1254, 175, 85, 901, 1037],
    buffie: [452, 552, 17, 4, 416, 539],
  };
  const groups = {
    ALL: ['Full roster', 'all'],
    GEARS: ['Gears', 'gear'],
    GADGETS: ['Gadgets', 'gadget'],
    'STAR POWERS': ['Star Powers', 'star'],
    HYPERCHARGE: ['Hypercharge', 'hyper'],
    'BUFFIE OWNERSHIP': ['Buffies', 'buffie'],
    'BUFFIE COMBINATIONS': ['Buffie sets', 'buffie'],
    CLASS: ['Brawler class', 'class_damage_dealer'],
    RARITY: ['Brawler rarity', 'rarity'],
  };
  const metadata = {
    power_asc: ['power_asc', 'Lowest Power Level first'],
    power_desc: ['power_desc', 'Highest Power Level first'],
    newest: ['newest', 'Most recently released Brawlers first'],
    oldest: ['oldest', 'Earliest released Brawlers first'],
    trophies: ['trophy', 'Highest current trophy count first', '↓'],
    trophies_asc: ['trophy', 'Lowest current trophy count first', '↑'],
    prestige_next: ['prestige', 'Fewest trophies to the next Prestige milestone', '↑'],
    name: ['name', 'Alphabetical order, A to Z'],
    name_desc: ['name_desc', 'Alphabetical order, Z to A'],
    all: ['all', 'Show the full roster within your other filters'],
    gadgets_0: ['gadget', 'Unlocked Brawlers with no Gadgets owned', '0/2', true],
    gadgets_1: ['gadget', 'Unlocked Brawlers with exactly one Gadget owned', '1/2'],
    gadgets_2: ['gadget', 'Unlocked Brawlers with both Gadgets owned', '2/2'],
    sp_0: ['star', 'Unlocked Brawlers with no Star Powers owned', '0/2', true],
    sp_1: ['star', 'Unlocked Brawlers with exactly one Star Power owned', '1/2'],
    sp_2: ['star', 'Unlocked Brawlers with both Star Powers owned', '2/2'],
    gears_0: ['gear', 'Unlocked Brawlers with no Gears owned', '0', true],
    gears_1: ['gear', 'Unlocked Brawlers with exactly one Gear owned', '1'],
    gears_2_plus: ['gear', 'Unlocked Brawlers with two or more Gears owned', '2+'],
    all_gears: ['gear', 'Every available Gear owned for that Brawler', 'ALL'],
    hc_not_available: ['hyper', 'Brawlers whose Hypercharge has not been released', '', true],
    hc_available_unowned: ['hyper', 'Hypercharge is released, but you do not own it', '', true],
    hc_stored: ['hyper', 'Hypercharge owned; Power Level 11 still needed', 'OWN'],
    hc_active: ['hyper', 'Hypercharge owned and usable at Power Level 11', '11'],
    buffies_owned_0: ['buffie', 'Released Buffies, with none of the three owned', '0/3', true],
    buffies_owned_at_least_1: ['buffie', 'At least one of the three Buffies owned', '1+'],
    buffies_owned_at_least_2: ['buffie', 'At least two of the three Buffies owned', '2+'],
    buffies_owned_3: ['buffie', 'All three Buffies owned for that Brawler', '3/3'],
    buffie_combo_0: ['buffie', 'No Gadget, Star Power, or Hypercharge Buffie owned', '0/3', true],
    buffie_combo_gadget: [['gadget'], 'Only the Gadget Buffie owned'],
    buffie_combo_sp: [['star'], 'Only the Star Power Buffie owned'],
    buffie_combo_hc: [['hyper'], 'Only the Hypercharge Buffie owned'],
    buffie_combo_gadget_sp: [['gadget', 'star'], 'Gadget and Star Power Buffies owned; Hypercharge missing'],
    buffie_combo_gadget_hc: [['gadget', 'hyper'], 'Gadget and Hypercharge Buffies owned; Star Power missing'],
    buffie_combo_sp_hc: [['star', 'hyper'], 'Star Power and Hypercharge Buffies owned; Gadget missing'],
    buffie_combo_complete: [['gadget', 'star', 'hyper'], 'Gadget, Star Power, and Hypercharge Buffies all owned'],
    class_damage_dealer: ['class_damage_dealer', 'Brawlers in the Damage Dealer class'],
    class_assassin: ['class_assassin', 'Brawlers in the Assassin class'],
    class_marksman: ['class_marksman', 'Brawlers in the Marksman class'],
    class_artillery: ['class_artillery', 'Brawlers in the Artillery class'],
    class_tank: ['class_tank', 'Brawlers in the Tank class'],
    class_support: ['class_support', 'Brawlers in the Support class'],
    class_controller: ['class_controller', 'Brawlers in the Controller class'],
    rarity_common: ['rarity_common', 'Starting Brawlers, including Shelly'],
    rarity_rare: ['rarity_rare', 'Brawlers in the Rare rarity'],
    rarity_super_rare: ['rarity_super_rare', 'Brawlers in the Super Rare rarity'],
    rarity_epic: ['rarity_epic', 'Brawlers in the Epic rarity'],
    rarity_mythic: ['rarity_mythic', 'Brawlers in the Mythic rarity'],
    rarity_legendary: ['rarity_legendary', 'Brawlers in the Legendary rarity'],
    rarity_ultra_legendary: ['rarity_ultra_legendary', 'Brawlers in the Ultra Legendary rarity'],
  };
  const controls = [];
  const chevron = '<svg class="roster-select-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';

  function icon(key) {
    const holder = document.createElement('span');
    holder.className = 'roster-option-art';
    const keys = Array.isArray(key) ? key : [key];
    if (keys.length > 1) holder.classList.add('roster-option-art-set');
    keys.forEach((name, index) => {
      if (index > 0) {
        const plus = document.createElement('span');
        plus.className = 'roster-icon-plus';
        plus.textContent = '+';
        holder.append(plus);
      }
      if (name.startsWith('rarity_')) {
        holder.classList.add('roster-rarity-art', `roster-rarity-${name.slice(7)}`);
        const skull = document.createElement('img');
        skull.src = '/assets/rarity-skull.svg?v=2';
        skull.alt = '';
        skull.setAttribute('aria-hidden', 'true');
        skull.className = 'roster-rarity-skull';
        holder.append(skull);
        return;
      }
      if (equipmentFrames[name]) {
        const [width, height, x, y, visibleWidth, visibleHeight] = equipmentFrames[name];
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', `${x} ${y} ${visibleWidth} ${visibleHeight}`);
        svg.setAttribute('aria-hidden', 'true');
        const image = document.createElementNS(svg.namespaceURI, 'image');
        image.setAttribute('href', art[name]);
        image.setAttribute('width', width);
        image.setAttribute('height', height);
        svg.append(image);
        holder.append(svg);
        return;
      }
      const image = document.createElement('img');
      image.alt = '';
      image.setAttribute('aria-hidden', 'true');
      if (name.startsWith('class_')) {
        image.src = `/assets/classes/${name.slice(6).replaceAll('_', '-')}.png`;
        image.className = 'roster-class-icon';
      } else {
        image.src = art[name];
      }
      holder.append(image);
    });
    return holder;
  }

  function optionArt(value) {
    const [key, , badge, missing] = metadata[value];
    let holder;
    if (value.startsWith('buffie_combo_') && value !== 'buffie_combo_0') {
      holder = document.createElement('span');
      holder.className = 'roster-option-art roster-buffie-set-art';
      const buffie = icon('buffie');
      buffie.classList.add('roster-buffie-set-symbol');
      const types = icon(key);
      types.classList.add('roster-buffie-set-types');
      holder.append(buffie, types);
    } else holder = icon(key);
    if (missing) holder.classList.add('roster-option-art-missing');
    if (badge) {
      const count = document.createElement('span');
      count.className = 'roster-art-badge';
      count.textContent = badge;
      holder.append(count);
    }
    holder.setAttribute('aria-hidden', 'true');
    return holder;
  }

  function enhance(select) {
    const sort = select.id === 'brawler-sort';
    const field = sort ? 'Sort brawlers' : 'Filter equipment and roster categories';
    const wrapper = document.createElement('div');
    wrapper.className = `roster-select ${sort ? 'roster-sort-select' : 'roster-category-select'}`;
    select.before(wrapper);
    wrapper.append(select);
    const trigger = document.createElement('button');
    trigger.className = 'roster-select-trigger';
    trigger.type = 'button';
    trigger.id = `${select.id}-trigger`;
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', `${select.id}-listbox`);
    const menu = document.createElement('div');
    menu.className = `roster-select-menu${sort ? ' roster-sort-menu' : ''}`;
    menu.id = `${select.id}-listbox`;
    menu.setAttribute('popover', 'auto');
    menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-label', field);
    wrapper.append(trigger, menu);
    const buttons = [];
    let options = [...select.children];
    if (!sort) {
      const order = Object.keys(groups);
      options.sort((a, b) => order.indexOf(a.label) - order.indexOf(b.label));
    }
    for (const child of options) {
      const group = document.createElement('div');
      if (child.tagName === 'OPTGROUP') {
        const [label, key] = groups[child.label];
        group.setAttribute('role', 'group');
        group.setAttribute('aria-label', label);
        const heading = document.createElement('div');
        heading.className = 'roster-option-group';
        heading.setAttribute('aria-hidden', 'true');
        heading.append(icon(key));
        const title = document.createElement('span');
        title.textContent = label;
        heading.append(title);
        group.append(heading);
      }
      const entries = child.tagName === 'OPTGROUP' ? [...child.children] : [child];
      entries.forEach((entry) => {
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'roster-option';
        row.id = `${select.id}-option-${entry.value}`;
        row.dataset.value = entry.value;
        row.setAttribute('role', 'option');
        row.setAttribute('aria-selected', 'false');
        row.tabIndex = -1;
        row.append(optionArt(entry.value));
        const copy = document.createElement('span');
        copy.className = 'roster-option-copy';
        const label = document.createElement('strong');
        label.textContent = entry.textContent;
        const guide = document.createElement('small');
        guide.textContent = metadata[entry.value][1];
        if (rarityTiers[entry.value]) {
          label.className = 'roster-rarity-label';
          const name = document.createElement('span');
          name.textContent = entry.textContent;
          const tier = document.createElement('span');
          tier.className = 'roster-rarity-tier';
          tier.textContent = rarityTiers[entry.value];
          tier.setAttribute('aria-hidden', 'true');
          label.replaceChildren(name, tier);
          copy.append(label);
        } else copy.append(label, guide);
        const radio = document.createElement('span');
        radio.className = 'roster-option-radio';
        radio.setAttribute('aria-hidden', 'true');
        row.append(copy, radio);
        row.addEventListener('click', () => {
          select.value = entry.value;
          sync();
          menu.hidePopover();
          trigger.focus();
          select.dispatchEvent(new Event('change', { bubbles: true }));
        });
        buttons.push(row);
        group.append(row);
      });
      menu.append(group);
    }

    function sync() {
      const current = select.selectedOptions[0];
      trigger.replaceChildren(optionArt(current.value));
      const label = document.createElement('span');
      label.className = 'roster-select-label';
      label.textContent = current.textContent;
      trigger.append(label);
      trigger.insertAdjacentHTML('beforeend', chevron);
      trigger.setAttribute('aria-label', `${field}: ${current.textContent}`);
      trigger.title = metadata[current.value][1];
      buttons.forEach((button) => button.setAttribute('aria-selected', String(button.dataset.value === current.value)));
    }

    function position() {
      const rect = trigger.getBoundingClientRect();
      const viewportWidth = document.documentElement.clientWidth;
      const width = Math.min(sort ? 370 : 490, viewportWidth - 24);
      const below = window.innerHeight - rect.bottom - 16;
      const above = rect.top - 16;
      const upwards = below < 220 && above > below;
      const height = Math.min(560, Math.max(120, upwards ? above : below));
      menu.style.width = `${width}px`;
      menu.style.maxHeight = `${height}px`;
      menu.style.left = `${Math.max(12, Math.min(rect.left, viewportWidth - width - 12))}px`;
      menu.style.top = upwards ? 'auto' : `${rect.bottom + 8}px`;
      menu.style.bottom = upwards ? `${window.innerHeight - rect.top + 8}px` : 'auto';
    }
    function reveal(row) {
      // Scroll the popup itself so the surrounding roster stays in place.
      const top = row.offsetTop;
      const bottom = top + row.offsetHeight;
      if (top < menu.scrollTop) menu.scrollTop = Math.max(0, top - 8);
      else if (bottom > menu.scrollTop + menu.clientHeight) menu.scrollTop = bottom - menu.clientHeight + 8;
    }
    function show() {
      position();
      menu.showPopover();
      const selected = buttons.find((button) => button.dataset.value === select.value);
      selected.focus({ preventScroll: true });
      if (selected === buttons[0]) menu.scrollTop = 0;
      else reveal(selected);
    }
    trigger.addEventListener('click', () => menu.matches(':popover-open') ? menu.hidePopover() : show());
    trigger.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        show();
      }
    });
    menu.addEventListener('toggle', () => {
      const opened = menu.matches(':popover-open');
      trigger.setAttribute('aria-expanded', String(opened));
      wrapper.classList.toggle('roster-select-open', opened);
    });
    let typed = '';
    let typeTimer;
    menu.addEventListener('keydown', (event) => {
      const active = buttons.indexOf(document.activeElement);
      let next;
      if (event.key === 'ArrowDown') next = (active + 1) % buttons.length;
      if (event.key === 'ArrowUp') next = (active - 1 + buttons.length) % buttons.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = buttons.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        buttons[next].focus({ preventScroll: true });
        reveal(buttons[next]);
      } else if (event.key === 'Escape' || event.key === 'Tab') {
        menu.hidePopover();
        trigger.focus();
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); }
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && event.key !== ' ') {
        typed += event.key.toLowerCase();
        clearTimeout(typeTimer);
        typeTimer = setTimeout(() => { typed = ''; }, 700);
        const found = buttons.find((button) => button.querySelector('strong').textContent.toLowerCase().startsWith(typed));
        if (found) { found.focus({ preventScroll: true }); reveal(found); }
      }
    });
    window.addEventListener('resize', () => { if (menu.matches(':popover-open')) position(); });
    window.addEventListener('scroll', (event) => {
      if (menu.matches(':popover-open') && !menu.contains(event.target)) position();
    }, { capture: true, passive: true });
    select.addEventListener('change', sync);
    select.hidden = true;
    sync();
    controls.push({ sync, menu });
  }

  window.RosterDropdowns = {
    init() {
      if (typeof HTMLElement.prototype.showPopover !== 'function' || controls.length) return;
      ['brawler-sort', 'equipment-filter'].forEach((id) => enhance(document.getElementById(id)));
    },
    sync() { controls.forEach((control) => control.sync()); },
    close() { controls.forEach(({ menu }) => { if (menu.matches(':popover-open')) menu.hidePopover(); }); },
  };
})();
