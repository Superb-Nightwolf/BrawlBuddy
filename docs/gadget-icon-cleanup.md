# Gadget icon background cleanup

- Target: `app/ui/assets/section_gadget.png` (existing project Gadget icon).
- Mode: built-in imagegen edit, `transparent_background: true`.
- Change requested: remove the baked white square outside the icon.
- Output: 1254 × 1254 RGBA PNG; corners and the former square corners have zero alpha.
- The shared asset path is retained so existing Gadget fallbacks also receive the cleanup.
- Generated original: `C:/Users/bhala/.codex/generated_images/01a101e2-cdbb-7e11-b7a0-5ba40ba4da1f/exec-4fea839a-9e43-4e89-ab69-e78c7f2473a1.png`.

## Edit prompt

Use case: background-extraction. Edit target: the supplied Brawl Stars Gadget icon.
Remove only the white square background outside the green four-lobed circular
icon. Make every pixel outside the icon's black outer outline genuinely
transparent, including the white square corners. Preserve the exact existing
icon silhouette, thick black outline, bright green and dark green shading, two
white gloss highlights INSIDE the icon, and dark green circular centre. Do not
redesign, add symbols, change its proportions, add glow, or alter its colours.
Keep it centred on a square canvas with tight even transparent margins and
crisp antialiased edges, suitable for display as a small website icon. Output
PNG with true alpha transparency, with no checkerboard, white rectangle, or
background shadow baked into the image.
