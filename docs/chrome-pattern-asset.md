# Site background and header/footer textures

- Active asset: `app/ui/assets/brawl-lobby-pattern-hd.png`.
- Generated with the built-in image generation tool, using the previous lobby pattern as a style reference.
- Output dimensions: 1254 × 1254 pixels, RGBA PNG with genuine transparency.
- Rendered as a 512 × 512 CSS-pixel repeating watermark, providing approximately 2.45× pixel density while retaining large symbols.
- Low-opacity blue silhouettes are applied directly without the old JPEG's grayscale, inversion, and contrast filters.
- The generated pattern now covers the shared site background and navy sidebar, replacing the Colt character wallpaper. The site background uses soft blue and lavender washes to fit the roster and Prestige cover.
- Header and footer use the same 20-pixel dot texture as the Brawler roster, defined by the shared `--roster-dot-pattern` CSS token.
- Original reference asset: `app/ui/assets/brawl-lobby-pattern.jpg` (1024 × 576 JPEG).
- Reference source: [SanekOgon's Brawl Stars x SFM collection](https://steamcommunity.com/sharedfiles/filedetails/?id=1994880266).
- Reference image: https://images.steamusercontent.com/ugc/772867190387629749/933CDCA800D2D7CB45EF9AAE546324F0700EE2F1/

## Generation prompt

```text
Use case: style-transfer. Asset type: high-resolution seamless repeating website watermark tile. Input image 1 is the reference for the exact Brawl Stars lobby motif family and staggered diagonal arrangement. Recreate this pattern cleanly as a premium 2048 x 2048 square raster asset with a genuinely transparent background. Use only the reference's chunky six-point badge stars, circular skull emblems with two eyes and small nose cutouts, rounded square badge silhouettes, and compact toy blaster silhouettes. Repeat them in an evenly spaced staggered approximately 8 by 8 pattern, with similar playful alternating slight rotations. Make the individual symbols generous, clean and instantly readable, not tiny or crowded. All symbols are a single uniform muted slate blue #597DA5, fully opaque; holes and surrounding background are transparent. Smooth precise anti-aliased edges, crisp flat vector-like silhouettes rendered at high resolution. Pattern must tile seamlessly at all four edges, including matched cropped edge motifs. No blue background, no gradients, no texture, no JPEG noise, no blur, no jagged edges, no glow, no outlines, no shadows, no typography, no logo, no watermark text, no characters. This will be displayed as large low-opacity decorative symbols behind light header/footer text. Keep the recognizable reference motifs and their proportions, improve edge quality and resolution.
```
