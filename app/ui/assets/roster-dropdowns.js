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
    trophies: ['trophy', 'Highest current trophy count first', '↑'],
    trophies_asc: ['trophy', 'Lowest current trophy count first', '↓'],
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
  const controls = new Map();
  let controlSequence = 0;
  let observer;
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

  function optionArt(value, details = metadata[value] || ['all', '']) {
    const [key, , badge, missing] = details;
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

  function semanticArt(key, badge = '') {
    const holder = document.createElement('span');
    holder.className = 'roster-option-art roster-semantic-art';
    holder.setAttribute('aria-hidden', 'true');
    const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 32 32');
    const use = document.createElementNS(svg.namespaceURI,'use');
    use.setAttribute('href',`/assets/dropdown-icons.svg#${key}`);
    svg.append(use); holder.append(svg);
    if (badge) {
      const count = document.createElement('span'); count.className = 'roster-art-badge';
      count.textContent = badge; holder.append(count);
    }
    return holder;
  }

  function enhance(select) {
    if (!select || select.multiple || select.dataset.native === 'true' || controls.has(select)) return;
    const roster = ['brawler-sort', 'equipment-filter'].includes(select.id);
    const category = select.id === 'equipment-filter';
    const labelHost = select.labels?.[0];
    const labelText = labelHost ? [...labelHost.childNodes]
      .filter(node => node.nodeType === 3 || node.nodeName === 'SPAN').map(node => node.textContent).join(' ').trim() : '';
    const field = select.getAttribute('aria-label') || labelText || select.dataset.slot?.replaceAll('_', ' ') || 'Choose an option';
    if (!select.id) select.id = `shared-select-${++controlSequence}`;
    const wrapper = document.createElement('div');
    wrapper.className = `roster-select ${category ? 'roster-category-select' : roster ? 'roster-sort-select' : 'roster-shared-select'}`;
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
    menu.className = `roster-select-menu${category ? '' : ' roster-sort-menu'}${roster ? '' : ' roster-shared-menu'}`;
    menu.id = `${select.id}-listbox`;
    menu.setAttribute('popover', 'auto');
    menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-label', field);
    wrapper.append(trigger, menu);
    let buttons = [], fingerprint = '';

    function optionLabel(entry) {
      return select.id === 'ranking-region-select' ? entry.textContent.replace(/^[^A-Za-z0-9]+/u,'') : entry.textContent;
    }
    function details(entry) {
      if (roster) return metadata[entry.value] || ['all', ''];
      const sortKeys = {
        trophies:['trophy','','↓'], trophies_asc:['trophy','','↑'], highest_trophies:['trophy','','PB'],
        power:['power_desc',''], prestige:['prestige',''], name:['name',''], name_desc:['name_desc',''],
      };
      return sortKeys[entry.value] || ['all',''];
    }
    function artwork(entry) {
      let src, country = false;
      if (roster) return optionArt(entry.value,details(entry));
      if (select.id === 'ranking-region-select') {
        if (entry.value === 'global') return semanticArt('globe');
        if (['us','in','br','de','jp','fr','gb'].includes(entry.value)) {
          src = `/assets/flags/${entry.value}.svg`; country = true;
        } else return semanticArt('globe');
      } else if (select.id === 'club-role-filter') {
        return semanticArt(({all:'roles',president:'crown',vicepresident:'vice',senior:'senior',member:'member',unknown:'unknown'})[entry.value] || 'roles');
      } else if (select.id === 'meta-map') {
        return semanticArt(entry.value ? 'map' : 'maps');
      } else if (select.id === 'meta-type') {
        const type = entry.value.toLowerCase().replace(/[^a-z]/g,'');
        if (type === 'ranked' || type === 'soloranked') src = '/assets/ranked/masters.png';
        else if (type === 'tournament') src = '/assets/icon_trophy.png';
        else return semanticArt(type === 'challenge' ? 'challenge' : 'match-types');
      } else if (select.id === 'meta-active-slot') {
        const [side,number] = entry.value.split('_');
        return semanticArt(side === 'enemy' ? 'enemy' : 'ally',number);
      } else if (select.dataset.slot) {
        if (entry.value) src = officialBrawlerIconSource({id:Number(entry.value)});
        else {
          const [side,number] = select.dataset.slot.split('_');
          return semanticArt(side === 'enemy' ? 'enemy' : 'ally',number);
        }
      } else if (select.id === 'meta-mode' || select.id === 'event-mode-filter') {
        src = getUiIconRecord('modes',entry.value)?.local_url;
        if (!src) return semanticArt('gamepad');
      } else if (entry.value === 'best_streak') {
        return semanticArt('streak');
      } else if (details(entry)[0] !== 'all') {
        return optionArt(entry.value,details(entry));
      } else return semanticArt('choices');
      const holder = document.createElement('span');
      holder.className = `roster-option-art${country ? ' roster-country-art' : ''}`;
      holder.setAttribute('aria-hidden', 'true');
      const image = document.createElement('img');
      image.src = src; image.alt = '';
      holder.append(image);
      return holder;
    }
    function build() {
      buttons = [];
      menu.replaceChildren();
      let children = [...select.children];
      if (category) {
        const order = Object.keys(groups);
        children.sort((a,b) => order.indexOf(a.label)-order.indexOf(b.label));
      }
      for (const child of children) {
        const group = document.createElement('div');
        if (child.tagName === 'OPTGROUP') {
          const [label,key] = category && groups[child.label] ? groups[child.label] : [child.label,'all'];
          group.setAttribute('role','group'); group.setAttribute('aria-label',label);
          const heading = document.createElement('div');
          heading.className = 'roster-option-group'; heading.setAttribute('aria-hidden','true');
          const title = document.createElement('span'); title.textContent = label;
          heading.append(icon(key),title); group.append(heading);
        }
        const entries = child.tagName === 'OPTGROUP' ? [...child.children] : [child];
        entries.filter(entry => entry.tagName === 'OPTION' && !entry.hidden).forEach((entry) => {
          const row = document.createElement('button');
          row.type = 'button'; row.className = 'roster-option';
          row.id = `${select.id}-option-${buttons.length}`; row.dataset.value = entry.value;
          row.setAttribute('role','option'); row.tabIndex = -1;
          row.disabled = entry.disabled || child.tagName === 'OPTGROUP' && child.disabled;
          row.setAttribute('aria-disabled', String(row.disabled));
          row.append(artwork(entry));
          const copy = document.createElement('span'); copy.className = 'roster-option-copy';
          const label = document.createElement('strong'); label.textContent = optionLabel(entry);
          copy.append(label);
          if (roster && rarityTiers[entry.value]) {
            label.className = 'roster-rarity-label';
            const name = document.createElement('span'); name.textContent = entry.textContent;
            const tier = document.createElement('span'); tier.className = 'roster-rarity-tier';
            tier.textContent = rarityTiers[entry.value]; tier.setAttribute('aria-hidden','true');
            label.replaceChildren(name,tier);
          } else if (details(entry)[1]) {
            const guide = document.createElement('small'); guide.textContent = details(entry)[1]; copy.append(guide);
          }
          const radio = document.createElement('span'); radio.className = 'roster-option-radio'; radio.setAttribute('aria-hidden','true');
          row.append(copy,radio);
          row.addEventListener('click', () => {
            if (select.disabled || row.disabled) return;
            select.value = entry.value; sync(); menu.hidePopover(); trigger.focus();
            select.dispatchEvent(new Event('change',{bubbles:true}));
          });
          buttons.push(row); group.append(row);
        });
        menu.append(group);
      }
    }
    function sync() {
      const next = [...select.options].map(option => [option.value,option.textContent,option.disabled,option.hidden,option.parentElement.label,option.parentElement.disabled].join('|')).join('\n');
      if (next !== fingerprint) { fingerprint = next; build(); }
      const current = select.selectedOptions[0] || select.options[0];
      trigger.disabled = select.disabled || !current || !buttons.some(button => !button.disabled);
      trigger.replaceChildren();
      if (current) trigger.append(artwork(current));
      const label = document.createElement('span'); label.className = 'roster-select-label';
      label.textContent = current ? optionLabel(current) : 'No options available';
      trigger.append(label); trigger.insertAdjacentHTML('beforeend',chevron);
      trigger.setAttribute('aria-label', `${field}: ${label.textContent}`);
      trigger.title = current && details(current)[1] || field;
      buttons.forEach(button => button.setAttribute('aria-selected',String(button.dataset.value === current?.value)));
      if (trigger.disabled && menu.matches(':popover-open')) menu.hidePopover();
    }
    function position() {
      const rect = trigger.getBoundingClientRect(), viewportWidth = document.documentElement.clientWidth;
      const width = Math.min(category ? 490 : roster ? 370 : Math.max(300,rect.width),viewportWidth-24);
      const below = window.innerHeight-rect.bottom-16, above = rect.top-16;
      const upwards = below < 220 && above > below;
      menu.style.width = `${width}px`; menu.style.maxHeight = `${Math.min(560,Math.max(80,upwards ? above : below))}px`;
      menu.style.left = `${Math.max(12,Math.min(rect.left,viewportWidth-width-12))}px`;
      menu.style.top = upwards ? 'auto' : `${rect.bottom+8}px`;
      menu.style.bottom = upwards ? `${window.innerHeight-rect.top+8}px` : 'auto';
    }
    function reveal(row) {
      const top = row.offsetTop, bottom = top+row.offsetHeight;
      if (top < menu.scrollTop) menu.scrollTop = Math.max(0,top-8);
      else if (bottom > menu.scrollTop+menu.clientHeight) menu.scrollTop = bottom-menu.clientHeight+8;
    }
    function show() {
      sync(); if (trigger.disabled) return;
      position(); menu.showPopover();
      const selected = buttons.find(button => !button.disabled && button.dataset.value === select.value) || buttons.find(button => !button.disabled);
      if (selected) { selected.focus({preventScroll:true}); reveal(selected); }
    }
    trigger.addEventListener('click',()=>menu.matches(':popover-open') ? menu.hidePopover() : show());
    trigger.addEventListener('keydown',event=>{
      if (['ArrowDown','ArrowUp'].includes(event.key)) {event.preventDefault(); show();}
    });
    menu.addEventListener('toggle',()=>{
      const opened = menu.matches(':popover-open'); trigger.setAttribute('aria-expanded',String(opened));
      wrapper.classList.toggle('roster-select-open',opened);
    });
    let typed = '', typeTimer;
    menu.addEventListener('keydown',event=>{
      const enabled = buttons.filter(button=>!button.disabled), active = enabled.indexOf(document.activeElement);
      let next;
      if (event.key === 'ArrowDown') next = (active+1)%enabled.length;
      if (event.key === 'ArrowUp') next = (active-1+enabled.length)%enabled.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = enabled.length-1;
      if (next !== undefined && enabled[next]) {event.preventDefault(); enabled[next].focus({preventScroll:true}); reveal(enabled[next]);}
      else if (event.key === 'Escape' || event.key === 'Tab') {
        menu.hidePopover(); trigger.focus();
        if (event.key === 'Escape') {event.preventDefault(); event.stopPropagation();}
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && event.key !== ' ') {
        typed += event.key.toLowerCase(); clearTimeout(typeTimer); typeTimer = setTimeout(()=>{typed='';},700);
        const found = enabled.find(button=>button.querySelector('strong').textContent.toLowerCase().startsWith(typed));
        if (found) {found.focus({preventScroll:true}); reveal(found);}
      }
    });
    select.addEventListener('change',sync);
    select.hidden = true;
    controls.set(select,{sync,menu,position});
    sync();
  }

  function scan(root = document) {
    if (root.matches?.('select')) enhance(root);
    root.querySelectorAll?.('select').forEach(enhance);
    for (const [select] of controls) if (!select.isConnected) controls.delete(select);
  }
  window.addEventListener('resize',()=>controls.forEach(({menu,position})=>{if(menu.matches(':popover-open')) position();}));
  window.addEventListener('scroll',event=>controls.forEach(({menu,position})=>{if(menu.matches(':popover-open') && !menu.contains(event.target)) position();}),{capture:true,passive:true});
  window.RosterDropdowns = {
    init() {
      if (typeof HTMLElement.prototype.showPopover !== 'function') return;
      scan();
      if (observer) return;
      observer = new MutationObserver(records=>{
        const changed = new Set();
        for (const record of records) {
          const select = (record.target.nodeType === 1 ? record.target : record.target.parentElement)?.closest('select');
          if (select && controls.has(select)) changed.add(select);
          for (const node of record.addedNodes) if (node.nodeType === 1 && !node.closest('.roster-select-menu')) scan(node);
        }
        changed.forEach(select=>controls.get(select)?.sync());
        for (const [select] of controls) if (!select.isConnected) controls.delete(select);
      });
      observer.observe(document.body,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['disabled','selected','label','value','hidden']});
    },
    sync() { scan(); controls.forEach(control=>control.sync()); },
    close() { controls.forEach(({menu})=>{if(menu.matches(':popover-open')) menu.hidePopover();}); },
  };
})();
