/* Small, interruptible effects: UI state changes never wait for an animation. */
(() => {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const running = new Map();

  function animate(element, frames, duration) {
    if (!element || reducedMotion.matches || !element.animate || !element.getClientRects().length) return;
    running.get(element)?.cancel();
    const effect = element.animate(frames, {
      duration,
      easing: 'cubic-bezier(.2,.75,.25,1)',
    });
    running.set(element, effect);
    const clean = () => { if (running.get(element) === effect) running.delete(element); };
    effect.addEventListener('finish', clean, { once: true });
    effect.addEventListener('cancel', clean, { once: true });
  }

  function enter(element, subtle = false) {
    animate(element, [
      { opacity: subtle ? .72 : 0, translate: `0 ${subtle ? 5 : 12}px` },
      { opacity: 1, translate: '0 0' },
    ], subtle ? 180 : 280);
  }

  function init() {
    document.addEventListener('click', (event) => {
      const control = event.target.closest('button, a.brawler-card, a.quick-brawler, a.matchup-card');
      if (!control || control.disabled) return;
      // Run after selection handlers, including those that replace className.
      requestAnimationFrame(() => animate(control, [
        { scale: '1' }, { scale: '.96', offset: .35 }, { scale: '1' },
      ], 200));
    });
    document.addEventListener('change', (event) => {
      if (event.target.matches('select, input[type="checkbox"], input[type="radio"]')) enter(event.target, true);
    });
    reducedMotion.addEventListener('change', () => {
      if (reducedMotion.matches) {
        for (const effect of running.values()) effect.cancel();
        running.clear();
      }
    });
  }

  window.BrawlBuddyMotion = { enter, init };
})();
