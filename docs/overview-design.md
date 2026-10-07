# Overview design

The Overview follows the Brawler detail page and Roster Lab with rounded frames, raised card edges, pale gradients, dot textures, and the same heading and body fonts

Collection, trophies, equipment, competitive records, recent play, club context, and goals each have a coordinated section color

Game artwork is reused for equipment, Buffies, currencies, modes, classes, Prestige, and brawler portraits
Rarity bars use the existing roster rarity variables and combat roles use BRAWLER_CLASSES
The original game skull is displayed at a larger CSS scale to compensate for its transparent padding without changing the source image

Ranked badges are cached unchanged from the [Brawlify CDN](https://github.com/Brawlify/CDN/tree/master/ranked), which provides artwork extracted from the game or supplied through the official Fan Kit
Their URLs, dimensions, and SHA-256 hashes are recorded in data/overview_artwork.json
The player's league determines the badge shown in the profile and current Ranked rating
Club badges use the returned badge ID with the existing CDN and a local team icon as the fallback

Generic decorative stars, chess pieces, and diamonds have been removed from the Overview
Fame displays the returned numeric value and tier without substituting an unrelated tier badge
Credits and Bling retain text labels because their artwork is not present in the current verified asset collection

Data meanings, source captions, charts, sorting, searches, refresh, and balance entry are preserved
Section navigation highlights the section in view and includes club and event context
Mobile navigation scrolls horizontally within its own container and cards stack at narrow widths
