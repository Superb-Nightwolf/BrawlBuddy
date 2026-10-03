# Roster dropdown artwork

Sorting and category menus reuse the game's existing local equipment, Buffie,
trophy, class, and Brawler artwork. Every option includes a brief explanation;
Buffie combinations show the corresponding equipment icons together. Counts
and direction badges are interface annotations. Rarity options use colour
markers matching the roster's rarity palette. These markers are interface
artwork; they are not presented as official rarity icons.

Existing asset provenance is recorded in `data/visual_asset_manifest.json`
and `data/prestige_assets.json`. Class and Buffie art comes from the game's
images mirrored by the Brawl Stars Wiki; the equipment section art and trophy
icon are the existing project assets. Supercell's official asset collection is
available at https://fankit.supercell.com/d/YvtsWV4pUQVm/game-assets.
The Gadget section icon's baked square background was subsequently removed
with the built-in image editor; see `docs/gadget-icon-cleanup.md` for the prompt.

The new `app/ui/assets/filter-prestige.png` is the same in-game Prestige 1
badge used by the roster's progression system, cached locally from
https://cdn.brawlify.com/prestiges/tiered/4.png on 2026-10-04.

The native select elements remain the source of the values. Browsers with
Popover API support receive illustrated menus; other browsers keep the native
selects. Existing filter semantics, including “at least one/two” Buffies, are
preserved. The Individual Ownership group exposes the existing owned/missing
equipment filters.
