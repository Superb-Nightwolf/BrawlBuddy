/* Background-only themes. Character identity wins; rarity supplies the border/fallback. */
(function (root) {
  const families = {
    fire: { primary: '#ec771b', secondary: '#ffd34c', accent: '#ffae36', deep: '#2b1519', surface: '#ffedb4', effectType: 'embers', spotlightPosition: [48, 46] },
    frost: { primary: '#3cadde', secondary: '#c6f7ff', accent: '#75e1ff', deep: '#101e3c', surface: '#e1f8ff', effectType: 'frost', spotlightPosition: [51, 42] },
    electric: { primary: '#4778ed', secondary: '#73e8ff', accent: '#a78cff', deep: '#17142e', surface: '#e3f3ff', effectType: 'energy', spotlightPosition: [45, 44] },
    flora: { primary: '#339e60', secondary: '#b3ed72', accent: '#81dc94', deep: '#12251c', surface: '#e8f5d0', effectType: 'organic', spotlightPosition: [46, 49] },
    toxin: { primary: '#649d2a', secondary: '#c9ed61', accent: '#9ae63d', deep: '#16251b', surface: '#edf4ca', effectType: 'haze', spotlightPosition: [51, 45] },
    tide: { primary: '#158eb3', secondary: '#8ff2e4', accent: '#52dfff', deep: '#102c3b', surface: '#dbf8f1', effectType: 'flow', spotlightPosition: [54, 50] },
    wind: { primary: '#5b91bc', secondary: '#d7f5e9', accent: '#90e5e8', deep: '#18283b', surface: '#e5f5f1', effectType: 'flow', spotlightPosition: [52, 43] },
    arcane: { primary: '#9460cf', secondary: '#f2b6ec', accent: '#c2a2ff', deep: '#271734', surface: '#f3e2fc', effectType: 'dust', spotlightPosition: [48, 40] },
    cosmic: { primary: '#5473de', secondary: '#d3a6f6', accent: '#7fe7ff', deep: '#13192f', surface: '#e9e8fb', effectType: 'stars', spotlightPosition: [49, 42] },
    shadow: { primary: '#7746ba', secondary: '#e5a7f0', accent: '#b98ef2', deep: '#191424', surface: '#ece0f6', effectType: 'haze', spotlightPosition: [48, 47] },
    sonic: { primary: '#bf559b', secondary: '#ffd1e2', accent: '#ed8cdf', deep: '#2e1834', surface: '#ffe6ee', effectType: 'energy', spotlightPosition: [49, 44] },
    tech: { primary: '#427ca4', secondary: '#94e7f9', accent: '#6cd7ee', deep: '#172637', surface: '#dff2f7', effectType: 'energy', spotlightPosition: [50, 47] },
    blast: { primary: '#c78136', secondary: '#ffda83', accent: '#ffb44b', deep: '#342322', surface: '#ffedc8', effectType: 'embers', spotlightPosition: [46, 50] },
    earth: { primary: '#97703f', secondary: '#eac488', accent: '#d9ae70', deep: '#292522', surface: '#f4e9d0', effectType: 'dust', spotlightPosition: [43, 52] },
    sand: { primary: '#b48a4f', secondary: '#f7dc8e', accent: '#e9c779', deep: '#2b2335', surface: '#fcf0d1', effectType: 'dust', spotlightPosition: [52, 54] },
    sugar: { primary: '#d76ca5', secondary: '#ffd9ae', accent: '#ffaac8', deep: '#482841', surface: '#ffedf2', effectType: 'dust', spotlightPosition: [52, 48] },
    impact: { primary: '#8378bd', secondary: '#f2cf9e', accent: '#bab8f0', deep: '#25243a', surface: '#f3eada', effectType: 'dust', spotlightPosition: [47, 46] },
    web: { primary: '#a3557a', secondary: '#f8c7b7', accent: '#ee98c1', deep: '#301c2b', surface: '#ffe8e3', effectType: 'flow', spotlightPosition: [52, 44] },
    steam: { primary: '#557f89', secondary: '#d4dfbd', accent: '#9be0df', deep: '#172b30', surface: '#e8f1e3', effectType: 'haze', spotlightPosition: [46, 51] },
    money: { primary: '#b18a39', secondary: '#ffe49d', accent: '#ecc764', deep: '#302722', surface: '#fff0d1', effectType: 'dust', spotlightPosition: [48, 48] },
  };
  const rarityFallbacks = {
    common: { ...families.tech, border: '#9dd6ef' },
    rare: { ...families.flora, border: '#73d36c' },
    super_rare: { ...families.tide, border: '#65b9f4' },
    epic: { ...families.arcane, border: '#c781f0' },
    mythic: { ...families.sonic, border: '#f68baf' },
    legendary: { ...families.fire, border: '#f1ce58' },
    ultra_legendary: { ...families.cosmic, border: '#c79bf3' },
  };
  // Artwork accents are sampled once at authoring time; no runtime image processing.
  const brawlerThemes = {
    "SHELLY": {"family": "impact", "artwork": ["#6d1f93", "#f59a0f"]},
    "COLT": {"family": "impact", "artwork": ["#a31328", "#2e3979"]},
    "BULL": {"family": "impact", "artwork": ["#9d1825", "#205dd1"]},
    "BROCK": {"family": "fire", "artwork": ["#f7650d", "#1031b3"]},
    "RICO": {"family": "tech", "artwork": ["#0c29c0", "#0c29c0"]},
    "SPIKE": {"family": "flora", "artwork": ["#e63850", "#98c83d"]},
    "BARLEY": {"family": "fire", "artwork": ["#7f451a", "#14d4e5"]},
    "JESSIE": {"family": "electric", "artwork": ["#a73f2f", "#1353c8"]},
    "NITA": {"family": "flora", "artwork": ["#2bd1e6", "#8f3525"]},
    "DYNAMIKE": {"family": "blast", "artwork": ["#a95221", "#26458c"]},
    "EL PRIMO": {"family": "impact", "artwork": ["#1731c2", "#d56d31"]},
    "MORTIS": {"family": "shadow", "artwork": ["#692291", "#9c146f"]},
    "CROW": {"family": "toxin", "artwork": ["#55c110", "#23348e"]},
    "POCO": {"family": "sonic", "artwork": ["#d9962d", "#b70a4f"]},
    "BO": {"family": "flora", "artwork": ["#bb1620", "#0c41a2"]},
    "PIPER": {"family": "impact", "artwork": ["#b5672d", "#6f9bf2"]},
    "PAM": {"family": "tech", "artwork": ["#b91422", "#233892"]},
    "TARA": {"family": "arcane", "artwork": ["#2d1f89", "#a017b2"]},
    "DARRYL": {"family": "impact", "artwork": ["#9b5029", "#203080"]},
    "PENNY": {"family": "blast", "artwork": ["#a85820", "#0d8397"]},
    "FRANK": {"family": "earth", "artwork": ["#4f17ac", "#195fe0"]},
    "GENE": {"family": "arcane", "artwork": ["#9b46d8", "#1da8f8"]},
    "TICK": {"family": "blast", "artwork": ["#c58022", "#b50d1d"]},
    "LEON": {"family": "shadow", "artwork": ["#3cdcf1", "#eed516"]},
    "ROSA": {"family": "flora", "artwork": ["#46881b", "#b6633c"]},
    "CARL": {"family": "earth", "artwork": ["#98501f", "#1cdbf3"]},
    "BIBI": {"family": "sugar", "artwork": ["#cf1989", "#df887c"]},
    "8-BIT": {"family": "tech", "artwork": ["#0b2296", "#26effd"]},
    "SANDY": {"family": "sand", "artwork": ["#eaa439", "#7240c4"]},
    "BEA": {"family": "flora", "artwork": ["#fbd71e", "#33cfda"]},
    "EMZ": {"family": "toxin", "artwork": ["#9958cb", "#c82092"]},
    "MR. P": {"family": "tech", "artwork": ["#b70e24", "#1f2d6c"]},
    "MAX": {"family": "wind", "artwork": ["#fde221", "#d60e1d"]},
    "JACKY": {"family": "earth", "artwork": ["#c60d52", "#e59710"]},
    "GALE": {"family": "frost", "artwork": ["#d41b35", "#2a519f"]},
    "NANI": {"family": "tech", "artwork": ["#1bd4df", "#c17e10"]},
    "SPROUT": {"family": "flora", "artwork": ["#ec6073", "#2ee1eb"]},
    "SURGE": {"family": "electric", "artwork": ["#fce00d", "#1228ae"]},
    "COLETTE": {"family": "impact", "artwork": ["#c12543", "#8d50b2"]},
    "LOU": {"family": "frost", "artwork": ["#109ae5", "#dd1330"]},
    "BYRON": {"family": "toxin", "artwork": ["#9d5629", "#8b2b9c"]},
    "EDGAR": {"family": "impact", "artwork": ["#570a8d", "#a00e3f"]},
    "RUFFS": {"family": "tech", "artwork": ["#aa1422", "#ea9c1f"]},
    "STU": {"family": "fire", "artwork": ["#e86315", "#112998"]},
    "BELLE": {"family": "electric", "artwork": ["#50288f", "#cc8c2f"]},
    "SQUEAK": {"family": "tide", "artwork": ["#1d75fa", "#1d75fa"]},
    "GROM": {"family": "blast", "artwork": ["#d8122f", "#37345c"]},
    "BUZZ": {"family": "tide", "artwork": ["#0f9f92", "#cb1525"]},
    "GRIFF": {"family": "money", "artwork": ["#e19218", "#ae0e1c"]},
    "ASH": {"family": "earth", "artwork": ["#b04f19", "#1656b4"]},
    "MEG": {"family": "tech", "artwork": ["#e3920e", "#c51e28"]},
    "LOLA": {"family": "tech", "artwork": ["#253ab3", "#a7066f"]},
    "FANG": {"family": "impact", "artwork": ["#b30e1d", "#dd901d"]},
    "EVE": {"family": "flora", "artwork": ["#43be93", "#e66173"]},
    "JANET": {"family": "sonic", "artwork": ["#d8223b", "#40e9fc"]},
    "BONNIE": {"family": "blast", "artwork": ["#b91522", "#1c37a7"]},
    "OTIS": {"family": "tide", "artwork": ["#e11b92", "#0dafba"]},
    "SAM": {"family": "impact", "artwork": ["#c55f26", "#313b76"]},
    "GUS": {"family": "shadow", "artwork": ["#d78b1f", "#83affb"]},
    "BUSTER": {"family": "tech", "artwork": ["#461c94", "#e6a030"]},
    "CHESTER": {"family": "sugar", "artwork": ["#d61288", "#c08017"]},
    "GRAY": {"family": "arcane", "artwork": ["#144ca6", "#950d1e"]},
    "MANDY": {"family": "sugar", "artwork": ["#c12256", "#b56733"]},
    "R-T": {"family": "tech", "artwork": ["#cf2031", "#1292d6"]},
    "WILLOW": {"family": "toxin", "artwork": ["#cfba24", "#689f47"]},
    "MAISIE": {"family": "blast", "artwork": ["#dd6424", "#4de3f3"]},
    "HANK": {"family": "tide", "artwork": ["#b27c2e", "#2194d4"]},
    "CORDELIUS": {"family": "toxin", "artwork": ["#9bde23", "#7817b7"]},
    "DOUG": {"family": "tide", "artwork": ["#14c5e1", "#df402f"]},
    "PEARL": {"family": "fire", "artwork": ["#c86129", "#c86129"]},
    "CHUCK": {"family": "steam", "artwork": ["#3ccbdc", "#7d4f30"]},
    "CHARLIE": {"family": "web", "artwork": ["#ab0e20", "#da56e9"]},
    "MICO": {"family": "impact", "artwork": ["#d58b0f", "#10636a"]},
    "KIT": {"family": "impact", "artwork": ["#dc681e", "#c8235f"]},
    "LARRY & LAWRIE": {"family": "electric", "artwork": ["#e59516", "#0b31c9"]},
    "MELODIE": {"family": "sonic", "artwork": ["#e52d99", "#1093d4"]},
    "ANGELO": {"family": "toxin", "artwork": ["#14c3db", "#c58d33"]},
    "DRACO": {"family": "fire", "artwork": ["#c5101f", "#df951b"]},
    "LILY": {"family": "flora", "artwork": ["#c127ad", "#607c28"]},
    "BERRY": {"family": "sugar", "artwork": ["#db4da2", "#8357bc"]},
    "CLANCY": {"family": "tide", "artwork": ["#db2b1c", "#25488a"]},
    "MOE": {"family": "earth", "artwork": ["#7c4220", "#12e2f1"]},
    "KENJI": {"family": "impact", "artwork": ["#26b9c9", "#d57649"]},
    "SHADE": {"family": "shadow", "artwork": ["#3724b4", "#14e7fd"]},
    "JUJU": {"family": "arcane", "artwork": ["#a45621", "#249ba9"]},
    "MEEPLE": {"family": "arcane", "artwork": ["#d99a33", "#2437b4"]},
    "OLLIE": {"family": "sonic", "artwork": ["#1c67df", "#b7d816"]},
    "LUMI": {"family": "frost", "artwork": ["#b74831", "#41b5f7"]},
    "FINX": {"family": "arcane", "artwork": ["#dd9b34", "#20b2c6"]},
    "JAE-YONG": {"family": "electric", "artwork": ["#542a98", "#d341c5"]},
    "KAZE": {"family": "wind", "artwork": ["#c81e35", "#5ba88b"]},
    "ALLI": {"family": "flora", "artwork": ["#bf5c20", "#922a54"]},
    "TRUNK": {"family": "flora", "artwork": ["#d99322", "#617db1"]},
    "MINA": {"family": "wind", "artwork": ["#d1885a", "#52d0c9"]},
    "ZIGGY": {"family": "electric", "artwork": ["#4131ab", "#e49d19"]},
    "PIERCE": {"family": "impact", "artwork": ["#299ad1", "#cd7a4f"]},
    "GIGI": {"family": "arcane", "artwork": ["#cf4471", "#d08557"]},
    "GLOWY": {"family": "arcane", "artwork": ["#1980bf", "#a0592c"]},
    "SIRIUS": {"family": "shadow", "artwork": ["#38279a", "#af7046"]},
    "NAJIA": {"family": "toxin", "artwork": ["#d29b49", "#af2751"]},
    "DAMIAN": {"family": "fire", "artwork": ["#a42513", "#fde64a"]},
    "STARR NOVA": {"family": "arcane", "artwork": ["#2d43be", "#da43a4"]},
    "BOLT": {"family": "fire", "artwork": ["#ea6d19", "#1759da"]},
    "NORI": {"family": "tide", "artwork": ["#3cdff4", "#d1594a"]},
    "WENDY": {"family": "tech", "artwork": ["#27cbe3", "#e3722c"]},
    "COSMO": {"family": "arcane", "artwork": ["#2c68ca", "#4a15b0"]},
    "VINCE": {"family": "flora", "artwork": ["#b7581e", "#bb2d67"]},
    AMBER: { family: 'fire', primary: '#ee771a', secondary: '#ffd74e', accent: '#ffb52d', deep: '#2b151a', glow: '#ffd15b', surface: '#ffedb5', spotlightPosition: [48, 46], spotlightIntensity: .98, spotlightSize: '128%', effectType: 'embers' },
  };

  // Explicit identities refine the shared families without affecting artwork or content.
  Object.assign(brawlerThemes.COSMO, { family: 'cosmic' });
  Object.assign(brawlerThemes['STARR NOVA'], { family: 'cosmic' });
  Object.assign(brawlerThemes.GLOWY, { family: 'tide', glow: '#8df5de' });
  Object.assign(brawlerThemes.NITA, { primary: '#37a6b0', secondary: '#a5e8db', deep: '#163237', surface: '#e2f4e4' });
  Object.assign(brawlerThemes.LOU, { primary: '#3295df', secondary: '#c0f5ff', accent: '#71d9fa', deep: '#15273d', surface: '#e0f5fc', spotlightPosition: [50, 42] });
  Object.assign(brawlerThemes.CROW, { primary: '#649d2a', secondary: '#c2e954', deep: '#122819', glow: '#b2ed4a', surface: '#ecf4c8', spotlightPosition: [51, 47] });
  Object.assign(brawlerThemes.LUMI, { primary: '#65bde4', secondary: '#ffbd71', accent: '#8fddfc', deep: '#241c32', glow: '#a3eaff', surface: '#e9f4f1', effectType: 'dual', spotlightPosition: [49, 43] });
  Object.assign(brawlerThemes.FINX, { primary: '#bb933e', secondary: '#9be4ef', deep: '#18273a', glow: '#ffdd88', surface: '#f8f0d6' });
  Object.assign(brawlerThemes.WENDY, { primary: '#34bac7', secondary: '#c0ec96', deep: '#183035', glow: '#9cedda', surface: '#e5f4e8' });
  Object.assign(brawlerThemes.EDGAR, { family: 'shadow' });
  Object.assign(brawlerThemes.SAM, { family: 'tech' });
  Object.assign(brawlerThemes.SPIKE, { spotlightPosition: [47, 53] });
  Object.assign(brawlerThemes.NANI, { spotlightPosition: [52, 44] });
  Object.assign(brawlerThemes.TARA, { spotlightPosition: [49, 41] });
  Object.assign(brawlerThemes.SURGE, { spotlightPosition: [46, 47] });
  Object.assign(brawlerThemes.SANDY, { spotlightPosition: [46, 53] });
  Object.assign(brawlerThemes.LEON, { spotlightPosition: [45, 49] });
  Object.assign(brawlerThemes['R-T'], { spotlightPosition: [51, 46] });
  Object.assign(brawlerThemes.GALE, { spotlightPosition: [53, 52] });

  function familyFromKit(guide) {
    const kit = `${guide.attack?.description || ''} ${guide.super?.description || ''}`;
    const cues = [
      ['frost', /\b(ice|icy|snow|freez\w*|frost)\b/i], ['fire', /\b(flam\w*|fire|burn\w*|heat|inferno)\b/i],
      ['electric', /\b(electr\w*|lightning|taser)\b/i], ['toxin', /\b(poison\w*|toxic\w*|venom)\b/i],
      ['tide', /\b(water|ink|fish|goo)\b/i], ['flora', /\b(seed\w*|vine\w*|thorn\w*|plant\w*|mushroom\w*)\b/i],
      ['sonic', /\b(music|soundwave\w*|melody|sing\w*)\b/i], ['wind', /\b(wind|hurricane|tempest|gust)\b/i],
      ['shadow', /\b(shadow\w*|ghost\w*|spirit\w*|invisib\w*)\b/i], ['cosmic', /\b(gravity|orbit\w*|magnet\w*)\b/i],
      ['arcane', /\b(magic\w*|teleport\w*)\b/i], ['tech', /\b(laser\w*|robot\w*|beam\w*|generator)\b/i],
      ['blast', /\b(bomb\w*|dynamite|rocket\w*|mine\w*)\b/i],
    ];
    return cues.find(([, cue]) => cue.test(kit))?.[0];
  }

  function mix(a, b, share) {
    const rgb = hex => hex.match(/[0-9a-f]{2}/gi).map(channel => parseInt(channel, 16));
    const one = rgb(a), two = rgb(b);
    return '#' + one.map((value, i) => Math.round(value * (1 - share) + two[i] * share).toString(16).padStart(2, '0')).join('');
  }

  function getTheme(brawler, guide = {}) {
    const rarityKey = String(guide.rarity || brawler.rarity || 'common').toLowerCase().replace(/[\s-]+/g, '_');
    const rarity = rarityFallbacks[rarityKey === 'starting' ? 'common' : rarityKey] || rarityFallbacks.common;
    const name = String(guide.name || brawler.name || '').trim().toUpperCase();
    const dedicated = brawlerThemes[name] || {};
    const family = families[dedicated.family || familyFromKit(guide)];
    const theme = { spotlightIntensity: .9, spotlightSize: '126%', ...rarity, ...family, ...dedicated, border: rarity.border };
    if (dedicated.artwork) {
      theme.primary = dedicated.primary || mix(theme.primary, dedicated.artwork[0], .32);
      theme.secondary = dedicated.secondary || mix(theme.secondary, dedicated.artwork[1], .22);
      theme.deep = dedicated.deep || mix(theme.deep, dedicated.artwork[0], .1);
    }
    theme.glow ||= theme.secondary;
    return theme;
  }

  function apply(element, brawler, guide) {
    if (!element) return;
    const theme = getTheme(brawler, guide);
    for (const key of ['primary', 'secondary', 'accent', 'deep', 'glow', 'surface']) element.style.setProperty(`--theme-${key}`, theme[key]);
    element.style.setProperty('--rarity-accent', theme.border);
    element.style.setProperty('--spotlight-x', `${theme.spotlightPosition[0]}%`);
    element.style.setProperty('--spotlight-y', `${theme.spotlightPosition[1]}%`);
    element.style.setProperty('--spotlight-intensity', theme.spotlightIntensity);
    element.style.setProperty('--spotlight-size', theme.spotlightSize);
    element.dataset.heroEffect = theme.effectType;
  }
  const api = { getTheme, apply };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.BrawlBuddyHeroThemes = api;
})(globalThis);
