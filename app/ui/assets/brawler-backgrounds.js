/* Background motifs follow the curated attack/Super kit, independently of rarity. */
(function (root) {
  const groups = {
    fire: ['AMBER', 'DRACO', 'PEARL', 'STU', 'DAMIAN', 'BOLT', 'BARLEY', 'BROCK'],
    frost: ['LOU', 'GALE', 'LUMI'],
    electric: ['BELLE', 'ZIGGY', 'JESSIE', 'SURGE', 'JAE-YONG', 'LARRY & LAWRIE'],
    flora: ['SPIKE', 'ROSA', 'SPROUT', 'LILY', 'TRUNK', 'BEA', 'NITA', 'BO', 'ALLI', 'VINCE', 'EVE'],
    toxin: ['CROW', 'BYRON', 'EMZ', 'WILLOW', 'ANGELO', 'NAJIA', 'CORDELIUS'],
    tide: ['OTIS', 'HANK', 'NORI', 'BUZZ', 'DOUG', 'SQUEAK', 'CLANCY'],
    wind: ['KAZE', 'MINA', 'MAX'],
    arcane: ['TARA', 'GENE', 'COSMO', 'FINX', 'GIGI', 'JUJU', 'STARR NOVA', 'MEEPLE', 'GLOWY', 'GRAY'],
    shadow: ['MORTIS', 'GUS', 'SHADE', 'SIRIUS', 'LEON'],
    sonic: ['POCO', 'JANET', 'MELODIE', 'OLLIE'],
    tech: ['RICO', 'PAM', '8-BIT', 'NANI', 'MR. P', 'RUFFS', 'MEG', 'R-T', 'WENDY', 'LOLA', 'BUSTER'],
    blast: ['DYNAMIKE', 'TICK', 'PENNY', 'GROM', 'BONNIE', 'MAISIE'],
    earth: ['FRANK', 'JACKY', 'CARL', 'MOE', 'ASH'],
    sand: ['SANDY'],
    sugar: ['BIBI', 'CHESTER', 'MANDY', 'BERRY'],
    impact: ['SHELLY', 'COLT', 'BULL', 'EL PRIMO', 'PIPER', 'DARRYL', 'COLETTE', 'EDGAR', 'FANG', 'SAM', 'MICO', 'KIT', 'KENJI', 'PIERCE'],
    web: ['CHARLIE'],
    steam: ['CHUCK'],
    money: ['GRIFF'],
  };
  const byName = new Map(Object.entries(groups).flatMap(([theme, names]) => names.map(name => [name, theme])));

  function themeFor(brawler, guide = {}) {
    const name = String(guide.name || brawler.name || '').trim().toUpperCase();
    if (byName.has(name)) return byName.get(name);
    // New arrivals get a motif only from their own attack/Super, not counter tips.
    const kit = `${guide.attack?.name || ''} ${guide.attack?.description || ''} ${guide.super?.name || ''} ${guide.super?.description || ''}`;
    const cues = [
      ['frost', /\b(ice|icy|snow|freez\w*|frost)\b/i],
      ['fire', /\b(flam\w*|fire|burn\w*|heat|inferno)\b/i],
      ['electric', /\b(electr\w*|lightning|taser)\b/i],
      ['toxin', /\b(poison\w*|toxic\w*|venom)\b/i],
      ['tide', /\b(water|ink|fish|wave|goo)\b/i],
      ['flora', /\b(seed\w*|vine\w*|thorn\w*|plant\w*|mushroom\w*)\b/i],
      ['sonic', /\b(music|soundwave\w*|melody|sing\w*)\b/i],
      ['wind', /\b(wind|hurricane|tempest|gust)\b/i],
      ['shadow', /\b(shadow\w*|ghost\w*|spirit\w*|invisib\w*)\b/i],
      ['arcane', /\b(magic\w*|gravity|orbit\w*|teleport\w*)\b/i],
      ['tech', /\b(laser\w*|robot\w*|beam\w*|generator)\b/i],
      ['blast', /\b(bomb\w*|dynamite|rocket\w*|mine\w*)\b/i],
    ];
    return cues.find(([, cue]) => cue.test(kit))?.[0] || 'impact';
  }

  const coverMotifs = {
    'NITA': 'earth', 'BO': 'arrows', 'CROW': 'daggers', 'BEA': 'swarm',
    'SPIKE': 'thorns', 'LILY': 'thorns', 'CORDELIUS': 'spores', 'EVE': 'eggs',
    'VINCE': 'swarm', 'KIT': 'claws', 'ALLI': 'claws', 'EDGAR': 'ribbons',
  };

  function coverFor(brawler, guide = {}) {
    const name = String(guide.name || brawler.name || '').trim().toUpperCase();
    const theme = themeFor(brawler, guide);
    return {
      motif: coverMotifs[name] || theme,
      leftMotif: name === 'LUMI' ? 'fire' : coverMotifs[name] || theme,
      variant: name === 'LUMI' ? 'fire-ice' : 'kit',
    };
  }

  // Read a small sample of the existing RGBA artwork; never modify the image.
  // Transparent padding, dark outlines and pale highlights must not dominate.
  function paletteFromPixels(pixels, width, height) {
    const buckets = Array.from({ length: 24 }, () => ({ weight: 0, rgb: [0, 0, 0] }));
    const stride = Math.max(1, Math.floor(width * height / 10000));
    for (let i = 0; i < pixels.length; i += stride * 4) {
      if (pixels[i + 3] < 190) continue;
      const rgb = [pixels[i], pixels[i + 1], pixels[i + 2]];
      const max = Math.max(...rgb), min = Math.min(...rgb), delta = max - min;
      if (max < 65 || delta / max < .32) continue;
      let hue = max === rgb[0] ? (rgb[1] - rgb[2]) / delta
        : max === rgb[1] ? (rgb[2] - rgb[0]) / delta + 2
          : (rgb[0] - rgb[1]) / delta + 4;
      hue = (hue * 60 + 360) % 360;
      const bucket = buckets[Math.floor(hue / 15)];
      const weight = delta / max * (.4 + max / 255);
      bucket.weight += weight;
      rgb.forEach((channel, index) => { bucket.rgb[index] += channel * weight; });
    }
    const ranked = buckets.map((bucket, hue) => ({ ...bucket, hue }))
      .filter(bucket => bucket.weight > 0).sort((a, b) => b.weight - a.weight);
    if (!ranked.length) return null;
    const primary = ranked[0];
    const secondary = ranked.find(bucket => {
      const distance = Math.abs(bucket.hue - primary.hue);
      return Math.min(distance, 24 - distance) >= 3 && bucket.weight >= primary.weight * .12;
    }) || primary;
    const hex = bucket => `#${bucket.rgb.map(channel => Math.round(channel / bucket.weight).toString(16).padStart(2, '0')).join('')}`;
    return { primary: hex(primary), secondary: hex(secondary) };
  }

  const api = { themeFor, coverFor, paletteFromPixels };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.BrawlBuddyBackgrounds = api;
})(globalThis);
