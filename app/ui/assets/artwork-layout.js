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

  const api = { visibleBounds };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.BrawlBuddyArtwork = api;
})(globalThis);
