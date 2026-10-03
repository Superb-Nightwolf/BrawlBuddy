# Generic Gear and Hypercharge icons

Mode: built-in image_gen edit with transparent_background=true.

Outputs:
- `app/ui/assets/section_gear.png`: transparent cyan Gear frame; removes the baked checkerboard square.
- `app/ui/assets/section_hypercharge.png`: transparent purple flame with a white lightning bolt, used as the generic dropdown symbol and shared section fallback.

These are edited interface assets, not newly sourced official Supercell artwork. Individual Brawler Hypercharge artwork remains unchanged.

## Gear prompt

Use case: background-extraction. Asset type: shared generic Gear icon for BrawlBuddy menus. Edit target: supplied cyan diamond Gear icon. Remove only the black and white checkerboard rectangle outside the icon's black outer outline, making it truly transparent. Preserve the exact rounded diamond silhouette, thick black outline, cyan and blue shading, highlights, and navy circular centre. Keep the icon centred on a square canvas with tight even transparent margins, crisp antialiased edges, and high resolution. Do not redesign the icon or add a symbol. Output PNG with real alpha, no checkerboard, no background square, no glow or exterior shadow.

## Hypercharge prompt

Use case: precise-object-edit. Asset type: shared generic Hypercharge symbol for BrawlBuddy menus. Edit target: supplied purple flame Hypercharge frame. Remove the black and white checkerboard square outside its black outer outline and make that area genuinely transparent. Preserve the purple/magenta flame silhouette, thick dark outline, purple shading, and small white gloss highlight. Inside the dark purple circular centre, add a single bold white angular lightning bolt centred neatly, recognizable at 32px. This should be the clean generic purple flame-and-lightning Hypercharge symbol, not a skull or character-specific icon. Keep the frame centred on a square high-resolution canvas with tight even transparent margins and crisp edges. No text, skull, circle background outside the flame, checkerboard, background square, glow, or exterior shadow. Output PNG with real alpha transparency.

## Validation

Both PNGs have genuine alpha transparency outside their silhouettes. Checked the dropdown icons on the live local Brawlers page.
