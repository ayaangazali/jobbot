# 03 — the collage system

38 assets, 28 MB, in `jobbot/static/landing2/img/`. They fall into exactly three
classes and the class determines size, z-band and behaviour.

## Asset taxonomy

### 1. Scene — the backdrop (6 assets, `.jpg`)

Full-bleed vintage illustration or photograph. One per section. Width ≥ 1250
design units so it bleeds past both edges at any viewport.

| Asset | KB | Size | Subject |
|---|---|---|---|
| `asset-8bd696a182.jpg` | 2305 | 1317×883 | Blue painted sky — hero |
| `asset-f4e9f6c6ec.jpg` | 837 | 1857×1034 | Cave / stalactites |
| `asset-16db47fb62.jpg` | 828 | 1470×976 | Jungle valley |
| `asset-3c461998a9.jpg` | 828 | 1566×1409 | Jungle, second plate |
| `asset-7d08b9b774.jpg` | 629 | 1606×763 | Yellow valley lithograph |
| `asset-7356a2b7f2.jpg` | 568 | 1555×895 | Art-deco interior |
| `asset-3544e4a2b0.jpg` | 107 | 1258×1699 | Tall jungle filler |

Rules: `z` 49645–49700. `object-fit: cover`. Never rotate. Never put text
directly on one.

### 2. Stroke — painted texture behind text (6 assets, `.gif`)

A brush-stroke or paint smear whose only job is to make text readable on a
scene. 200–900 units wide.

| Asset | Size | Use |
|---|---|---|
| `asset-2409278a72.gif` | 308×227 | Cream stroke — the default text bed, used 3× |
| `asset-a6df01bc62.gif` | 514×307 | Wide pink/cream smear, used 3× |
| `asset-7828a9144c.gif` | 874×626 | Huge wash for full-width blocks |
| `asset-b08f74c793.gif` | 525×310 | Medium wash |
| `asset-8a674a5af5.gif` | 348×151 | Narrow banner stroke |
| `asset-513fbcc041.gif` | 245×218 | Small stroke for captions |

Rules: `z` 49700–50100, always **directly beneath** the text block it serves,
sized ~10% larger than the text box. Rotate ±3–7° so the stroke and text are
not parallel.

### 3. Sticker — punctuation (26 assets, `.gif`/`.png`)

Cutouts, arrows, squiggles, figures, marks. 36–540 units. They sit on top of
everything and carry the personality.

High-traffic ones:

| Asset | Size | Uses | What it is |
|---|---|---|---|
| `asset-191a616ef1.gif` | 50×120 | 5 | Yellow squiggle connector — links two blocks vertically |
| `asset-36cc96ea5e.gif` | 82×80 | 3 | Black X mark |
| `asset-5060552dc3.gif` | 107×115 | 2 | Black dot |
| `asset-ae687c70ea.gif` | 70×46 | 1 | Small dark figure |
| `asset-1c5039b36d.gif` | 89×59 | 1 | Closing mark |
| `asset-730d4bf698.gif` | 36×45 | 1 | Tiny arrow |

Rules: `z` 50100–50350. Rotate freely. Overlap a card edge by 20–40% — a
sticker fully inside its card looks like an icon, not a sticker.

## Layering recipe

Every content unit is built back-to-front:

```
z 49650   SCENE        full-bleed .jpg, object-fit cover, no rotation
z 49820   PLATE        solid #1c1c1f or rgba(255,255,255,.92), rot -4.77°
z 49900   STROKE       painted .gif, ~110% of the text box, rot -6.5°
z 50300   TEXT         Space Mono 17.6u on the stroke, rot 0 or matching plate
z 50330   STICKER      cutout overlapping the plate corner, rot +15°
```

The counter-rotation between plate (-4.77°) and sticker (+15°) is what creates
the hand-assembled look. Matching rotations look like a CSS mistake.

## Composition recipes

**Section header.** Heading block (National Park 20–26u, centred, width 375–600)
over a `asset-2409278a72.gif` stroke at ~110% width, rotated -5°. Optionally a
squiggle below linking to the next block.

**Body paragraph.** `text-block` 432 units wide, Space Mono 17.6u / 1.25, on a
wide smear (`asset-a6df01bc62.gif`) rotated -6.5°.

**Card.** Dark `#1c1c1f` plate rotated -4.77°, hard magenta offset shadow
`6u 6u 0 #ff5dfc`, white Lato title + Space Mono body inside, one sticker
breaking the top-right corner.

**Connector.** `asset-191a616ef1.gif` (yellow squiggle) placed between two
stacked blocks, x roughly centred, height spanning the gap.

## Budget

28 MB is already heavy for a local dashboard. Before adding art, reuse. The
five multi-use assets (`191a616ef1`, `36cc96ea5e`, `2409278a72`, `a6df01bc62`,
`5060552dc3`) exist precisely so sections rhyme. If a new page needs a scene,
prefer one of the seven existing `.jpg`s over downloading another.

Any asset that stops being referenced should be deleted — a prune after the
pricing/testimonial cut removed 30 files and 4 MB.
