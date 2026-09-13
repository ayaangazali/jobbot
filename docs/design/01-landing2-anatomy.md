# 01 — landing2 anatomy

How `templates/landing2.html` is actually built. 89 blocks, 38 unique assets,
one CSS coordinate system, zero media queries.

## The stage

```css
:root { --rpx: min(calc(100vw / 600), 1px); }

.stage {
  position: relative;
  height: calc(6228 * var(--rpx));   /* total canvas height in design units */
}

.block {
  position: absolute;
  left:   calc(50% + (var(--x) - 300) * var(--rpx));
  top:    calc(var(--y) * var(--rpx));
  width:  calc(var(--w) * var(--rpx));
  height: calc(var(--h) * var(--rpx));
  z-index: var(--z);
  transform: rotate(calc(var(--rot) * 1deg));
}
```

**The design unit.** The canvas is 600 units wide. `--rpx` is the number of CSS
pixels per design unit: `1px` on any viewport ≥ 600px, and `100vw/600` below
that. So at 1440px the page renders 1:1 and is 600 units wide centred; at 390px
every length is multiplied by `0.65` and the whole collage shrinks as one piece.

**Why `--x - 300`.** X is measured from the left edge of the 600-unit canvas.
Subtracting half the canvas re-centres it, so `left: 50% + (x - 300)` puts unit
300 at the viewport centre. Blocks can sit at negative x or beyond 600 and bleed
off-screen; `overflow-x: hidden` on the body clips them.

**Verification.** At 1440 the document is 6228px tall; at 390 it is 4048px.
6228 × 0.65 = 4048. Every rendered text leaf scales by exactly 0.6500. If any
element deviates, it has a hardcoded `px` somewhere.

## Block anatomy

Three shapes, all `.block`:

```html
<!-- 1. bare: an image or a colour shape (68 of 89) -->
<div class="block" style="--x:223;--y:8;--w:82;--h:80;--z:49730;--rot:0;">
  <img src="/static/landing2/img/asset-36cc96ea5e.gif" style="object-fit:contain">
</div>

<!-- 2. text-block: body copy on a painted stroke (14 of 89) -->
<div class="block text-block" style="--x:314;--y:676;--w:432;--h:220;--z:50220;--rot:0;">
  <div class="text-inner">
    <p style="font-family:'Space Mono';font-size:calc(17.6 * var(--rpx));line-height:1.25">…</p>
  </div>
</div>

<!-- 3. heading: centred display type (7 of 89) -->
<div class="block heading" style="--x:304;--y:192;--w:600;--h:288;--z:50235;--rot:0;">
  <div style="font-family:'National Park',sans-serif;font-weight:700;
              font-size:calc(26 * var(--rpx));line-height:1.25;text-align:center">…</div>
</div>
```

### The quoting trap

Font names with spaces must use **single** quotes inside the double-quoted
`style` attribute:

```html
style="font-family:'Space Mono'"     <!-- correct -->
style="font-family:"Space Mono""     <!-- attribute ends at the 2nd quote -->
```

The second form silently drops every declaration after `font-family:`. This
shipped once and cost six fonts their sizing on mobile. If type looks right on
desktop and wrong on mobile, check this first.

## Z-order

All z-values live in **49645 – 50350**. They are not arbitrary; they encode depth
class:

| Range | Layer | Contents |
|---|---|---|
| 49645 – 49700 | **Scene** | Full-bleed backdrop images, one per section |
| 49700 – 50100 | **Mid** | Painted strokes, colour shapes, card plates |
| 50100 – 50350 | **Front** | Text blocks, headings, stickers, the logo |

Keep new elements inside the band that matches their role. Scenes must never
exceed 49700 or they will cover their own content.

## Section map

Coordinates are current (post-edit). Section boundaries are the seams where one
scene ends and the next begins.

| y range | Section | Backdrop |
|---|---|---|
| 0 – 1257 | Hero: logo, operator label, Chuck Norris line, intro paragraph | `asset-8bd696a182.jpg` (blue paint) |
| 1406 – 2931 | The lighthouse-keeper story, two long Space Mono columns | cave / jungle plates |
| 2428 – 3404 | "Boards jobbot has beaten" — ATS names as coloured word-marks | `asset-16db47fb62.jpg` |
| 3372 – 4427 | "Work with jobbot" + the recruiter-cost argument | `asset-7d08b9b774.jpg` (valley lithograph) |
| 4427 – 5322 | "What is jobbot anyway?" | `asset-7356a2b7f2.jpg` (art-deco interior) |
| 5322 – 6228 | Bio cards, principles, closing CTA | comics + mountain + purple paint |

**Removed sections.** Pricing plans and testimonials used to occupy
y 3779–5430 and 6078–7180. They were cut and the 2753 units collapsed. Restore
from commit `9279c0c` if needed.

## Collapsing space correctly

Deleting blocks leaves holes, because nothing reflows. To remove a band:

1. Delete every block fully inside `[cut_start, cut_end)`.
2. Shift every block at `y >= cut_end` up by `cut_end - cut_start`.
3. For a **scene** that straddles a boundary, clip its height instead of
   deleting: overlapping the top edge → `h = cut_start - y`; starting inside and
   ending below → `y = cut_start, h = bottom - cut_end`.
4. Small decorative blocks that straddle a seam should be deleted, not clipped.
5. Reduce `.stage` height by the total cut.
6. **Process cuts bottom-up.** Top-down shifting moves later blocks out of the
   next cut's range before it is evaluated.
