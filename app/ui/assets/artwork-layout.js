/* Measure transparent padding, without changing the original character art. */
(function (root) {
  function visibleBounds(pixels, width, height) {
    let left = width, top = height, right = -1, bottom = -1;
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        // Ignore almost-transparent glow/shadow pixels when aligning the body.
        if (pixels[(y * width + x) * 4 + 3] <= 24) continue;
        left = Math.min(left, x);
        top = Math.min(top, y);
        right = Math.max(right, x);
        bottom = Math.max(bottom, y);
      }
    }
    return right < left
      ? { left: 0, top: 0, width, height }
      : { left, top, width: right - left + 1, height: bottom - top + 1 };
  }

  // Use the visible artwork, rather than transparent canvas padding, for icons.
  // Each frame is [canvas width, canvas height, left, top, width, height].
  const iconFrames = {
    'currencies/power-points.png': [1024, 576, 208, 14, 608, 549],
    'section_gadget.png': [1254, 1254, 99, 92, 1049, 1050],
    'section_gear.png': [1254, 1254, 185, 186, 880, 869],
    'section_hypercharge.png': [1254, 1254, 175, 85, 901, 1037],
    'brawl-stars-symbol-official.png': [1502, 852, 502, 177, 498, 498],
  };
  function framedIconMarkup(url, className = '') {
    const asset = String(url).replace(/^\/assets\//, '').split(/[?#]/)[0];
    const frame = iconFrames[asset];
    if (!frame) return null;
    const escape = (value) => String(value).replace(/[&<>"']/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[character]);
    const [width, height, x, y, w, h] = frame;
    const source = String(url).startsWith('/assets/') ? url : `/assets/${url}`;
    return `<svg class="${escape(className)} game-icon-art" viewBox="${x} ${y} ${w} ${h}" aria-hidden="true" focusable="false"><image href="${escape(source)}" width="${width}" height="${height}"/></svg>`;
  }

  const api = { visibleBounds, framedIconMarkup };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.BrawlBuddyArtwork = api;
})(globalThis);
