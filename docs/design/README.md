# jobbot design system — collage

Everything here is reverse-engineered from `templates/landing2.html`, which is a
clone of an mmm.page collage. The numbers are extracted from the file, not
estimated. If a value here disagrees with the template, the template wins —
re-run the extraction rather than trusting prose.

| Doc | What it covers |
|---|---|
| [01-landing2-anatomy.md](./01-landing2-anatomy.md) | The stage/block coordinate engine, `--rpx` scaling, z-order, section map |
| [02-design-tokens.md](./02-design-tokens.md) | Fonts, type scale, colour roles, rotation, shadow, radius |
| [03-collage-system.md](./03-collage-system.md) | Asset taxonomy (scene / stroke / sticker), layering rules, composition recipes |
| [04-onboarding-redesign.md](./04-onboarding-redesign.md) | Spec for rebuilding `/intake` in this language |

## The one-paragraph version

A fixed-width **stage** (600 design units) holds absolutely-positioned **blocks**.
Every block carries `--x --y --w --h --z --rot` and every length is multiplied by
`--rpx`, a single scalar that shrinks the whole canvas on small screens. There is
no reflow and no media queries — the page scales as one image. Depth comes from
stacking three asset classes: full-bleed **scenes** at the back, painted
**strokes** behind text for legibility, and **stickers** on top for punctuation.
Type is `Space Mono` for body and `National Park` bold for headings.

## Non-negotiables

1. **Never use `px` for anything that must scale.** Use `calc(N * var(--rpx))`.
   A raw `px` font-size silently breaks mobile — this caused a real bug where
   six of nine fonts lost their sizing.
2. **Text needs a stroke or plate under it.** Dark text on a busy scene is
   unreadable. Every text block in landing2 sits on a painted stroke, a solid
   plate, or a flat colour band.
3. **Rotation is the texture.** 30 of 89 blocks are rotated. Most sit between
   -7° and +5°. Perfectly axis-aligned content reads as a web page, not a collage.
4. **Assets are heavy.** 28 MB across 38 files. Reuse what is already in
   `jobbot/static/landing2/img/` rather than adding new art.
