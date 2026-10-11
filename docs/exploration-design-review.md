# BrawlBuddy page design review

Reviewed and implemented on 11 October 2026. This review uses the current local application and its existing artwork, rather than a new visual theme.

The design changes are isolated on `feature/brawlbuddy_v0.0.9` in the attached `design-v0-0-9` worktree. Preview server: `http://127.0.0.1:8001/`. The original checkout remains on `ml`; ML routes, models, dependencies and the AI Meta page were excluded from this worktree.

## What the four reference pages teach us

| Reference page | Information and layout | Strong design pattern | What carries forward |
| --- | --- | --- | --- |
| Overview | Player identity, tag, club and XP lead into trophy, victory, Prestige and ranked tiles. Collection completion has its own action. The dashboard then covers roster progression, trophies, equipment, competitive records, recent play, club context and upgrade planning. | A framed player portrait anchors the cover. Pastel tiles separate different kinds of progress. Large values have concise labels; definitions and assumptions live in ⓘ controls. Collection is not repeated as another summary tile. | One prominent cover, a small set of meaningful metrics, distinct content sections, simple nested headings, and contextual explanations. Keep the portrait and collection panel balanced rather than stretching the statistic tiles. |
| Brawlers / Roster Lab | Prestige progression establishes the account context. Search, power filters and roster controls help users find a brawler. Cards combine official portraits, ownership, power and trophy progression. | The cover feels substantial while the repeated cards remain compact. Controls appear beside the content they filter. A card leads directly to a detailed guide. | Make filters easy to find, keep repeated cards consistent, preserve game artwork, show a useful empty state, and provide a clear next action. |
| Brawler information | Rarity and combat role introduce the brawler. Artwork, description, account power/trophies and Prestige form the cover. The page expands into combat guidance, equipment, readiness, recommended builds and useful maps. | Artwork remains large without forcing every other component to be tall. Rarity colours carry meaning. The same ⓘ component handles hover, keyboard focus and click. Item icons represent the actual item or currency. | Keep details in context, reuse the established information control, link portraits and recommendations to guides, and show the full map when inspecting a layout. |
| Club Hub | Club identity, tag, admission type and description lead into trophies, membership, entry requirements and shared progress. The page includes composition, trophy distribution, contributions, planning and a searchable roster. | The cover follows Overview's structure. Neighboring panels share row height, but their content starts naturally below the heading. Club explanations are hidden behind ⓘ rather than filling the cover. | Use the same cover scale, consistent title rows, balanced grids, clear numeric units, and search/filter controls that preserve the meaning of the original rankings. |

The useful consistency is the relationship between components, not identical markup everywhere. A player portrait, a map preview and a trophy podium serve different jobs. They should share spacing, typography, colour language and interaction rules while retaining those jobs.

## Shared rules applied

| Element | Rule |
| --- | --- |
| Cover height | The three exploration covers now use the existing `--profile-cover-height: 400px` on desktop above 1180px. Smaller layouts use content-driven height. The established brawler detail cover remains unchanged. |
| Cover spacing | Equal 28px desktop padding, 24px spacing between cover regions, framed artwork and a separate compact metric row. |
| Metric tiles | Four complementary pastel tiles. Large values, concise labels, a consistent icon slot and an ⓘ explanation. No visible source-status tile displacing a useful metric. |
| Icon scale | The same visual size within each role: 22px inline game icons, 28px summary icons, 38px battle/standing portraits and 112px cover artwork. A decorative cover image should not be forced into the size of a small row icon. |
| Headings | One main title per panel. Repeated nested heading icons are removed. Cover artwork establishes page identity; the title row remains easy to scan. |
| Information buttons | Reuse `readinessInfo` and `readinessBindInfo`, matching the brawler guide. Hover/focus reveal help, click pins it, and Escape or an outside click dismisses the pinned state. Positioning considers the viewport; active panels rise above adjacent cards. |
| Actions | Consistent right-aligned chevrons and short action labels. Actions stay at the bottom of repeated cards, even when content above them varies. |
| Height | Compact metric tiles and content spacing; preserve substantial covers. Equal-height neighbors do not require large empty gaps above their content. |
| Colours | Retain the existing page accents: pink for Battle Log, mint for Events & Maps, gold for Leaderboards, with blue/pink/mint/gold metric surfaces. Tier labels use pastel colours from this same language. |

## Changes by destination page

| Page / component | Before | Implemented result |
| --- | --- | --- |
| Battle Log cover | Shorter cover than the reference pages; engineering-oriented copy and a fixed claim of 25 matches. | Matching desktop cover height, framed battle artwork, clearer copy and four compact metrics: victories, defeats, win rate and trophy change. The actual returned match count remains visible. |
| Battle filters | Controls did not communicate their selected state to assistive technology. | All matches, Team modes and Showdown retain their behavior and now expose the selected state. Counts and empty states describe the current view. |
| Battle cards | Less consistent spacing, repeated decoration and portraits without guide navigation. | Equal team panels, standardized portraits and mode/trophy icons, linked brawler guides, a consistent tactical action and per-match ⓘ details. |
| Tactical details | Missing duration and team power could be replaced by invented defaults. Team labels implied a home/opponent relationship. | Missing values show “Not reported.” Blue/red labels describe supplied lineups. The overlay explains that positions are illustrative, with a pastel shell matching the site. |
| Leaderboards cover | A source-status metric occupied one of the summary positions. | Region, competitor count, leading score and trophy spread. Source context and the distinction between snapshots and growth live in ⓘ help. |
| Leaderboard controls | Player rankings were labeled “Brawlers”; no standings search. | Players / Clubs tabs, region selection and search by name/tag/club. Search filters the table while the podium and original rank numbers remain unchanged. |
| Leaderboard podium/table | Uneven presentation and raw in-game colour tags in names. | Equal-height podium cards, aligned profile actions, normalized portrait/icon sizes, clean display names and a sticky table heading. Profile buttons still work when search has no matches. |
| Events & Maps cover | Shorter cover and visible source decoration. | Matching cover with mode count, unique map count, next rotation and modified-slot count. Definitions and source context sit behind ⓘ. |
| Rotation cards | Map images were cropped, and differing body content affected action placement. | Full map bounds use `object-fit: contain`. Consistent mode icons, equal card heights, contextual map information and aligned inspection actions. |
| Map preview | A darker unrelated shell; close binding depended on the brawler guide having been visited. | A matching pastel overlay, full map artwork and a close button bound on every page. The brawler guide can still use the shared preview. |
| Brawler suggestions | Labels implied every list was a map-specific competitive ranking. | “Brawlers to explore,” with help explaining that curated map picks are used where available and general suggestions otherwise. These are not measured win rates. |
| Tier section | Saturated tier cells differed from the website's pastel surfaces. | Pastel tier labels, a simpler heading and ⓘ context for the curated list. Guide links remain available. |

## Data meaning preserved

Battle summary values describe the selected recent-match subset; they are not lifetime records. The current connected player has 24 returned matches, so the cover does not claim that exactly 25 were received. Some matches do not report trophy change or a star player.

Leaderboard search does not recalculate rank. Trophy spread is the highest minus the lowest trophy total in the returned standings, not progress over time. The podium always reflects the top three of the selected player/club leaderboard and region.

Rotation summaries describe all returned slots; search and mode filters affect the visible card list. Timers use reported end times. Sample rotations do not represent a live countdown. Some map suggestions currently fall back to a general brawler list, and the interface explains this limitation instead of presenting that list as measured map performance.

## Verification

| Check | Result |
| --- | --- |
| JavaScript syntax | `app.js` and `exploration-pages.js` pass `node --check`. |
| Existing service tests | Battle log, rankings and events tests: 3 passed. |
| Product route/guide test | Overview, Brawlers, Battle Log, Events, Leaderboards and the existing Surge guide: passed. |
| Isolated branch validation | Re-ran the three service tests, two Overview metrics tests and the product route/guide test from the 0.0.9 worktree: 6 passed. |
| Desktop covers | All three destination covers measured 400px at the browser's actual 1280px viewport. |
| Battle interaction | All/Team/Showdown filters, empty Showdown state, tactical overlay and match ⓘ verified. |
| Events interaction | Map search returns the expected slot; Brawl Ball filter returns 3 slots; preview shows the full map; close button verified. First-row cards measured equal height. |
| Rankings interaction | Search for Mikee returns one row while preserving three podium cards. Empty search result, club mode, India region, and player-profile navigation verified. Original connected player restored after testing. Podium cards measured equal height. |
| Club-opening regression fix | Podium and table profile actions now use direct profile links through the shared page router. They no longer call the dialog-only Connect tag flow. Verified Heaven, CODE: LENAIN, and @toxicgenie, including a podium click with an empty search result; player navigation also verified. Ranking and club service tests: 3 passed. |
| Information controls | Click and Escape verified; the rightmost metric tooltip stays within the desktop viewport. |
| Browser errors | No JavaScript console errors observed on the three updated pages. |
| Responsive scope | Responsive rules added for tablet and phone layouts, including stacked teams/dialog content and table scrolling. The browser viewport override did not change its actual width, so phone screenshots were not verified in this session. |

Implementation lives in `app/ui/assets/exploration-pages.css`, `app/ui/assets/exploration-pages.js`, the existing page markup and rendering functions. Existing backend endpoints and the four reference-page covers retain their behavior.
