# BrawlBuddy portrait generation record

The local brawler portraits were created with the built-in ImageGen tool and saved as transparent PNG assets. Existing approved portraits were retained; missing catalog portraits and the corrected Tara portrait were generated in twelve reviewed batches.

## Shared final prompt template

```text
Use case: stylized-concept
Asset type: BrawlBuddy local portrait for {BRAWLER_NAME}
Primary request: Create an original arena-fighter reinterpretation.
Subject: {UNIQUE_BRAWLER_ARCHETYPE_AND_ACTION}.
Color palette: {UNIQUE_PALETTE}.
Style/medium: premium polished colorful 3D mobile-arena game key art, toy-like materials, chunky readable silhouette, energetic original character design.
Composition/framing: square full-body character centered, generous safe margin, readable at roster-card size.
Lighting/mood: vivid arcade rim lighting, playful and powerful.
Constraints: genuinely transparent background; no text; no letters; no watermark; no logos; do not copy an existing game character exactly; create an original fan-art reinterpretation.
```

The subject and palette placeholders were customized for every portrait. Examples include a one-wheeled stunt robot with fire trails for Stu, a floating egg-shaped alien bio-ship for Eve, twin ticket-guard robots for Larry & Lawrie, a time-magic sphinx with clocks and sand for Finx, and a fishing prodigy with luminous fish spirits for Nori.

## Generated portrait batches

- Batch 1: Rico, Barley, Jessie, Nita, Dynamike, El Primo, Mortis, Crow
- Batch 2: Poco, Bo, Pam, Tara, Darryl, Frank, Tick, Leon
- Batch 3: Carl, 8-Bit, Sandy, Emz, Mr. P, Max, Jacky, Gale
- Batch 4: Nani, Sprout, Colette, Amber, Lou, Byron, Edgar, Ruffs
- Batch 5: Stu, Belle, Grom, Buzz, Griff, Ash, Meg, Lola
- Batch 6: Fang, Eve, Janet, Bonnie, Otis, Sam, Gus, Buster
- Batch 7: Chester, Gray, Mandy, R-T, Willow, Maisie, Hank, Cordelius
- Batch 8: Doug, Pearl, Chuck, Charlie, Mico, Kit, Larry & Lawrie, Melodie
- Batch 9: Angelo, Draco, Lily, Berry, Clancy, Moe, Kenji, Shade
- Batch 10: Juju, Meeple, Ollie, Lumi, Finx, Jae-Yong, Kaze, Alli
- Batch 11: Trunk, Mina, Ziggy, Pierce, Gigi, Glowy, Sirius, Najia
- Batch 12: Damian, Starr Nova, Bolt, Nori

## Runtime assets

- Full-resolution portraits: `app/ui/assets/brawlers/{id}.png`
- Optimized collection thumbnails: `app/ui/assets/brawlers/thumbs/{id}.webp`
- Thumbnail builder: `scripts/build_brawler_thumbnails.py`
