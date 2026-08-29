# BrawlBuddy - Quality Assurance & Mistake Prevention Log

This document tracks all identified UI, calculation, and data integration discrepancies, their root causes, and verified fixes to ensure complete accuracy.

---

## Logged Issues & Corrective Actions

### Issue 1: Brawler Prestige Counting 0 on Season-Reset Accounts
- **Root Cause**: Brawlers with peak trophies $\ge 1,000$ (e.g. Shelly at $1,014$ peak, Bibi at $1,032$ peak) were evaluated only on current post-decay trophies ($906$ and $948$) rather than their peak/highest milestone record $\max(\text{trophies}, \text{highest\_trophies})$.
- **Fix**: Updated both Python backend model property `PlayerProfile.brawler_prestige_level` and frontend JavaScript calculation in `app.js` to compute $\sum \lfloor \max(\text{trophies}, \text{highest\_trophies}) / 1000 \rfloor$.
- **Result**: Accurately credits 1 prestige point for each 1,000 trophies milestone across all brawlers.

---

### Issue 2: Championship Challenge Status Display
- **Root Cause**: Championship qualification status text defaulted to a vague "Pending" label without clear context on the 15-win tournament requirement.
- **Fix**: Linked `is_qualified_from_championship_challenge` directly to `🏆 Qualified ✓` (when true) or `🏆 15-Win Challenge` (when in progress), with a dedicated glowing championship badge in the hero banner.

---

### Issue 3: Prestige Badge Number Highlighting & Visual Contrast
- **Root Cause**: The numerical value inside `👑 PRESTIGE 210` blended directly with the label text.
- **Fix**: Encapsulated the number in a dedicated `.prestige-num-bubble` with high-contrast obsidian-gold depth styling and highlighted `#hero-prestige-count` in the stats grid.

---

### Issue 4: "Updated Now" Status Format Matching Master League
- **Root Cause**: `Updated now` was rendered as plain low-contrast text.
- **Fix**: Converted into `.freshness-pill` with a pulsating live status dot (`🟢 Live Updated`), glowing border, and frosted-glass backdrop matching the Master League badge tier.

---

### Issue 5: Topbar Header Left-Flush Vertical Alignment
- **Root Cause**: Eyebrow, h1 title, and subtitle text had subtle margins and emoji offset differences resulting in staggered alignment ("aage pichhe").
- **Fix**: Wrapped in `.topbar-header-copy` with strict `0` left margin, `align-items: flex-start`, and matching text-align baselines to achieve a 100% flush, laser-straight left edge.

---

### Issue 6: Hero Tile Bottom Border & Alignment
- **Root Cause**: Spacing inside the main player card caused potential bottom-edge clipping.
- **Fix**: Applied balanced padding (`24px 28px 24px 20px`), margin bottom (`24px`), and flex spacing across all hero child elements.

---

### Issue 7: Brawlers Catalog & Detail View Blank on Navigation
- **Root Cause**: 
  1. `mergeCatalog()` did a strict case-sensitive name check `owned.name.toUpperCase() === entry.name.toUpperCase()`, which failed on brawlers with special characters or slight API naming differences.
  2. When navigating to `/brawlers` or `/brawlers/:id` directly or via client link, `renderBrawlers()` was not executed in `showView()` / `handleRoute()` if state was already partially loaded.
  3. Direct visits to `/brawlers/:id` halted if `state.brawlers` had not finished populating from the catalog.
- **Fix**: 
  1. Made `mergeCatalog()` match by both ID and normalized name, and included any uncataloged owned brawlers automatically.
  2. Added automatic `renderBrawlers()` trigger in `showView()` when visiting the `/brawlers` page.
  3. Made `renderDetail()` auto-initialize account/catalog state and gracefully fall back to catalog data for unowned brawlers.
  4. Added SPA client-side click routing for instant link navigation without full-page reloads.

---

### Issue 8: Page Header Intro Overwritten Across Different Tabs
- **Root Cause**: `renderAccount()` unconditionally overwrote the topbar title (`#page-title`) and subtitle (`#page-subtitle`) with the Overview text even when on Battle Log, Events, or other tabs.
- **Fix**: Guarded topbar title overrides in `renderAccount()` with `state.page === 'overview'`, and ensured `configurePage()` dynamically populates dedicated, custom titles and subtitles for every view.

---

### Issue 9: Missing Individual Brawler Prestige Box in Detail View
- **Root Cause**: Individual brawler guides only displayed `POWER`, `TROPHIES`, and `RANK`.
- **Fix**: Added a dedicated `PRESTIGE` stat tile before `RANK` in `.detail-account-stats` that computes the brawler's lifetime prestige $\lfloor \max(\text{trophies}, \text{highest\_trophies}) / 1000 \rfloor$.

---

### Issue 10: Topbar Header Symbols & Action Buttons Balance
- **Root Cause**: Main eyebrow and title had `⚡` icons causing visual clutter, and topbar actions lacked clear visual hierarchy between informational indicators and interactive CTA buttons.
- **Fix**: Removed `⚡` from topbar eyebrow and title. Standardized all 3 action elements to a unified `42px` height with clear differentiation: non-clickable informational status pill (`#api-status`), compact clickable secondary action button (`#share-card-btn`), and bold clickable primary CTA (`#connect-button`).

---

### Issue 11: Hero Collection Box Alignment
- **Root Cause**: `.hero-collection-link` had an intentional 2-degree tilt and uneven text alignment causing off-center visuals.
- **Fix**: Removed rotation, applied strict center alignment across all child elements (`VIEW COLLECTION`, `13 / 106`, `Brawlers →`), with balanced vertical spacing.

---

### Issue 12: Brawler Rarity & Role Badges in Details Page
- **Root Cause**: Rarity and combat role (e.g. Tank, Damage Dealer) were rendered in plain text labels without distinct 3D pill boxes.
- **Fix**: Rebuilt `.rarity-badge` with official Supercell color themes (Epic violet, Legendary amber, Mythic red, Rare green, Super Rare blue) and `.class-badge` with role icons (`🛡 TANK`, `⚔ DAMAGE DEALER`, `🎯 MARKSMAN`, `🗡 ASSASSIN`, etc.).

---

### Issue 13: High-Definition Authentic Brawler Artwork Display
- **Root Cause**: The detail hero card previously used a hardcoded fallback artwork rather than loading the official high-resolution brawler portrait on the side.
- **Fix**: Pointed `#detail-image` dynamically to `/assets/brawlers/${brawler.id}.png` (high-res official transparent render) with automatic CDN fallback and framed with a natural radial starburst effect matching the page aesthetic.

---

### Issue 14: Comprehensive Authentic Brawler Imagery Across Roster & Grids
- **Root Cause**: Roster grid cards previously used low-resolution webp thumbnails or border crops rather than full authentic brawler character artwork.
- **Fix**: Upgraded `addImageWithFallback` to load `/assets/brawlers/${brawler.id}.png` directly for all brawlers, with a resilient fallback chain.

---

### Issue 15: "Player" Terminology Normalized to "Brawler" (P to B)
- **Root Cause**: Multiple UI elements still displayed generic "Player" labels (e.g. `DEMO DATA` / `OFFICIAL BRAWLER`, `Copy Player Tag`, `Top Players`, `Player Card`, `Player Tag` headers).
- **Fix**: Updated all UI labels and action buttons across Overview, Club Hub, Leaderboards, Share Card, and Connect Dialog to "Brawler" (`OFFICIAL BRAWLER`, `Copy Brawler Tag`, `Top Brawlers`, `Brawler Tag`, `Brawler Card`).

---

### Issue 16: Leaderboard & Clan Player Name Contrast & Color Legibility
- **Root Cause**: Light Supercell custom name colors (yellow, pastel, cyan, white) were washed out and invisible on white/light table rows.
- **Fix**: Introduced `readableNameColor()` luminance calculation that automatically deepens light colors (below luminance threshold) while preserving hue, paired with high-contrast text rendering for both player and club columns.

---

### Issue 17: Dual Side-by-Side Art & Official In-Game Portrait on Details
- **Root Cause**: The detail guide page did not display the official in-game portrait icon alongside the character title and custom/featured art.
- **Fix**: Added `.detail-title-row` with `.detail-portrait-box` rendering the authentic bordered in-game portrait (`https://cdn.brawlify.com/brawlers/borders/${id}.png`) right beside the brawler's name, while keeping the full character render on the left.

---

### Issue 18: Brawler Grid Square Photo Quality & Increased Sizing
- **Root Cause**: Grid cards displayed smaller, shrunken full-body PNGs where heads and portrait details were too small inside square containers.
- **Fix**: Standardized grid cards to display the official high-definition square bordered in-game portrait directly (`https://cdn.brawlify.com/brawlers/borders/${id}.png`), enlarged `.brawler-visual` height to `180px` and `.brawler-image` to `165px x 165px`, and expanded the detail portrait box to `88px x 88px`.

---

### Issue 19: New Brawler Wendy Added & Total Catalog Updated to 106
- **Root Cause**: Wendy was missing from the catalog and assets, leaving the total count at 105 instead of 106.
- **Fix**: Registered Wendy (`16000108`, Legendary Damage Dealer) in `data/brawler_catalog.json` and `data/brawler_guides.json`, and updated all catalog totals, banners, search placeholders, and test assertions to **106 brawlers**.

---

### Issue 20: Wendy Transparent Character Render, Portrait Box Enlargement & Sunburst Softening
- **Root Cause**: 
  1. The initial generated image for Wendy had a background scene rather than being an isolated transparent 3D character render like Nori (`16000107.png`).
  2. `.detail-burst` had a hard `450px` circular clipping boundary that created a visible harsh circle cutting the 360-degree rays.
- **Fix**: 
  1. Processed Wendy into a clean isolated transparent 3D character PNG (`16000108.png`) and dedicated facial crop thumbnail (`16000108.webp`).
  2. Replaced the harsh `450px` circular clipping in `.detail-burst` with an `800px` radial gradient fade-out mask and reduced opacity to `0.09` for a smooth, seamless 360 background effect.
  3. Expanded `.detail-portrait-box` to `88px × 88px` with a 3D glass-gold border.

---

### Issue 21: Wendy Flood-Fill Eye Transparency Fix & High-Definition Image Anti-Aliasing
- **Root Cause**:
  1. Simple white-color thresholding made Wendy's sclera (inner white eye pixels), teeth, and scarf transparent.
  2. CSS image rendering lacked explicit hardware-accelerated contrast optimization rules, causing subtle browser downscale aliasing on high-DPI displays.
- **Fix**:
  1. Implemented BFS flood-fill background eraser that starts exclusively from outer canvas edges, ensuring 100% of internal white pixels (eyes, teeth, highlights, scarf) remain completely solid and opaque.
  2. Applied `-webkit-optimize-contrast`, `transform: translateZ(0)`, and `backface-visibility: hidden` to `.brawler-image`, `.detail-art img`, and `.detail-portrait-box img` for razor-sharp rendering.

---

### Issue 22: Authentic In-Game Square Portrait Roster & Routing Speed
- **Root Cause**:
  1. The game roster cards previously swapped to full body character art instead of displaying the official square in-game portrait icons (`https://cdn.brawlify.com/brawlers/borders/${id}.png`).
  2. Page view transitions between `/brawlers` and detail guides had sequential rendering delays.
- **Fix**:
  1. Restored official square border portraits for all 106 brawlers in the Roster Lab grid (`https://cdn.brawlify.com/brawlers/borders/${id}.png` and `/assets/brawlers/thumbs/16000108.webp` for Wendy).
  2. Optimized `handleRoute()` with immediate `showView()` trigger for instantaneous page transitions.

---

### Issue 23: Profile Avatar Loaded in Existing Hero LVL 181 Frame
- **Root Cause**:
  1. An extra avatar pill was placed beside the player title, adding an unnecessary visual element.
  2. The main hero avatar frame (`.avatar-frame` where the `LVL 181` badge sits) loaded a generic mascot rather than the player's official equipped profile icon.
- **Fix**:
  1. Removed the extra avatar pill from the title line, keeping `#profile-name` clean and unaltered.
  2. Configured `#player-art` inside `.avatar-frame` (with the `LVL 181` badge) to display the player's official profile icon directly from the API (`https://cdn.brawlify.com/profile-icons/regular/${iconId}.png`), which dynamically changes with every player tag.

---

### Issue 24: 3D Frosted Glass Frames on Roster Cards & 100% Guaranteed Catalog Population
- **Root Cause**:
  1. Brawler cards in the roster grid lacked the distinct 3D frosted-glass framed aesthetic of `.avatar-frame`.
  2. In `styles.css`, `.brawler-grid` and `.brawler-card` rules had an incomplete line cutoff that broke card container dimensions.
  3. `loadCatalog()` did not immediately sync `state.brawlers`, causing unowned catalog brawlers to appear missing if route transitions fired asynchronously.
- **Fix**:
  1. Introduced `.brawler-frame-box` inside `.brawler-visual` with a $3.5\text{px}$ white glass bevel, $26\text{px}$ rounded corners, and soft depth shadows matching `.avatar-frame`.
  2. Fully rebuilt and verified all grid, flex card, and table mode CSS rules in `styles.css`.
  3. Updated `loadCatalog()` and `renderDetail()` to guarantee asynchronous catalog sync so all 106 brawlers populate and navigate instantly.

---

### Issue 25: 20% Title Frame Expansion & Typography Precision
- **Root Cause**: 
  1. The detail view title portrait box was previously $88\text{px} \times 88\text{px}$.
  2. Font sizing and spacing across card elements needed tightening for crisp visual hierarchy.
- **Fix**:
  1. Increased `.detail-portrait-box` by 20% to **`106px × 106px`** with a $4\text{px}$ solid white border, $26\text{px}$ rounded bevel, and expanded inner icon.
  2. Enlarged `.brawler-frame-box` in grid cards to $130\text{px} \times 130\text{px}$ inside a $185\text{px}$ container.
  3. Polished card typography: bold $16\text{px}$ brawler title, $11\text{px}$ stat metrics, and $12\text{px}$ full-bleed action footer with rounded corners.

---

### Issue 26: Roster Toolbar Filters & Power Level Selector Activation
- **Root Cause**: `renderBrawlers()` filtering did not re-sync fallback catalog data if triggered before asynchronous catalog completion, and select element states were not proactively propagated during filter changes.
- **Fix**: Rebuilt `renderBrawlers()` to guarantee complete filtering across search text, power level chips (`ALL`, `1` through `11`), equipment criteria (`has_sp`, `no_sp`, `has_gadget`, `no_gadget`, `has_gear`, `no_gear`), sort modes (`power_asc`, `power_desc`, `trophies`, `name`), and grid/table views.

---

### Issue 27: Roster Toolbar Layout CSS Styling & Forward/Back Scroll Restoration
- **Root Cause**: 
  1. CSS classes for `.collection-toolbar`, `.search-box`, `.view-toggle`, `.level-filter-label`, and `.level-chip` were missing explicit definitions in `styles.css`, rendering the filter controls as unstyled text clumps.
  2. Client-side navigation did not reset `window.scrollTo(0, 0)` on forward page clicks or remember scroll positions on back navigation.
- **Fix**:
  1. Added dedicated layout CSS for `.collection-toolbar`, `.search-box`, `.view-toggle`, `.level-filter-label`, `.level-filter`, and interactive `.level-chip` buttons.
  2. Configured SPA scroll restoration: saving scroll positions into a `scrollPositions` map per route, instantly scrolling to top `(0, 0)` on new page transitions, and restoring exact previous coordinates on browser back/forward (`popstate`).
