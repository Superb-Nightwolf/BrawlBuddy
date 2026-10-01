# Vince catalog verification — 2026-10-01

Vince (`16000110`) is represented throughout the 108-entry catalog, guide,
equipment index, visual manifest, local portraits and character artwork.
Existing account ownership stays API-driven; adding a catalog entry does not
claim that an account owns Vince.

## Cross-checks

- [Supercell's release notes](https://supercell.com/en/games/brawlstars/blog/release-notes/release-notes-august-2026/): Mythic Damage Dealer, trait, attack/Super, four named abilities, 1,200 healing.
- [BrawlAPI's Vince record](https://api.brawlapi.com/v1/brawlers/16000110): brawler ID, rarity, two Gadget IDs (`23001452`, `23001453`) and two Star Power IDs (`23001450`, `23001451`). Its class string is a trait slogan, so the role comes from Supercell, not that string.
- [Vince Wiki](https://brawlstars.fandom.com/wiki/Vince), accessed through its public MediaWiki API: Power 1 health 3,400, attack 1,100, Super base damage 400, range 8.33/9 tiles, reload 1.45 seconds, cooldowns 15/13 seconds and staged Super mechanics.
- [69.230 client snapshot](https://github.com/tailsjs/brawl-stars-assets/tree/master/69.230), a community mirror: independent numeric cross-check and localization for the three higher Super stages. Power 11 health/attack/base Super component are 6,800/2,200/800. These components are not a total combo damage estimate.

## Explicit limits

Brawlify currently sets `released: true`, but the Wiki still labels Vince as a
future update and other references have unconfirmed October dates. No exact
unlock date or price is asserted. No Hypercharge or Buffies are confirmed in
the checked release/client data. No reliable matchup sample was established:
the profile stores empty lists so the service does not use its synthetic
fallback. Build, mode and map suggestions are provisional practice ideas,
not measured best picks. Super-charge hit count remains unverified.

Only Vince was freshly reviewed. The global older-brawler verification date
is unchanged; his dated update is recorded separately in game_data_sources.

## Artwork provenance

The official full-body and portrait PNGs are cached separately with their Wiki
source URLs in hero-artwork.json. Equipment icons use the existing Brawlify
CDN convention. The generated full-body asset is
`app/ui/assets/brawlers/generated/16000110.png`; built-in image generation
used the official full-body/face references and Cosmo only as a render-style
reference. It is not presented as official artwork.

Final prompt: "Create one polished, full-body Vince cutout on a genuinely
transparent square canvas, preserving the official pale face, half-lidded
yellow eyes, purple eyelids, teal hair, yellow shirt, magenta apron, striped
purple trousers, black shoes, caterpillar and moth companions and coffee-cup
motif. Use the glossy stylized 3D finish of the existing Cosmo hero, without
Cosmo's robot features or space effects. Keep the whole figure and companions
visible; no environment, lettering, watermark, border or logos."

## Repeatable checks

Run `python scripts/sync_vince_data.py` for the targeted numeric/ID/ability
checks and equipment sync, `python scripts/build_brawler_thumbnails.py
16000110` for the portrait, then `python scripts/audit_catalog.py --online`
and `python -m pytest -q`. The sync refuses changed expected source facts
instead of silently publishing a different kit.
