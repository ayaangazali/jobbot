# 02 — design tokens

Extracted from `templates/landing2.html`. Counts are actual occurrences.

## Typeface roles

| Font | Uses | Role | Notes |
|---|---|---|---|
| **Space Mono** | 51 | Body copy, all long-form paragraphs | The workhorse. Monospace is what makes the page feel like a zine rather than a SaaS site. |
| **National Park** | 8 | Headings, `font-weight:700`, centred | Substitute for the reference's self-hosted NationalPark-Variable. |
| **Lato** | 9 | Card titles, small bold labels | Only used inside `<strong>`. |
| **Zilla Slab Highlight** | 4 | Word-marks (ATS names), accent lines | Has a built-in highlight effect. |
| **Nanum Pen Script** | 2 | The logo, handwritten asides | Handwriting register. |
| **Monofett** | 1 | The "your job hunt needs an operator" label | Heavy decorative display. Use sparingly — one per page. |
| **VT323** | 1 | Terminal-flavoured stamp | |
| **Roboto Mono** | 1 | Fallback mono | |

Loaded in one `<link>`:

```
https://fonts.googleapis.com/css2?family=Lato:ital,wght@0,400;0,700;1,400;1,700
&family=Monofett&family=Space+Mono:ital,wght@0,400;0,700;1,400;1,700
&family=Nanum+Pen+Script&family=BIZ+UDMincho:wght@400;700
&family=Zilla+Slab+Highlight:wght@400;700&family=VT323
&family=Open+Sans:ital,wght@0,400;0,700;1,400;1,700
&family=Roboto+Mono:ital,wght@0,400;0,700;1,400;1,700&display=swap
```

## Type scale

In design units. Always `font-size: calc(N * var(--rpx))`.

| Unit | Role |
|---|---|
| 34 | Logo wordmark |
| 26 | Hero statement |
| 20 – 22 | Section headings, plan titles |
| 17 – 17.6 | Body copy (the default) |
| 15 – 16 | Secondary copy, long story columns |
| 13 – 14.3 | Captions, word-marks, small labels |
| 12.8 | Footnotes, stamps |

Line-height is `1.25` for body and `1.4` for headings. Nothing else appears.

## Colour

There is no palette object; colours are inline. These are the real roles:

| Value | Role |
|---|---|
| `rgb(224,224,255)` | **Page background.** Pale lavender. The one constant. |
| `#000` / `rgb(0,0,0)` | Body and heading text (15 uses) |
| `#ffffff` / `rgb(255,255,255)` | Text on dark plates, card fills (10 uses) |
| `#1c1c1f` | Dark card plates (4 uses) |
| `#5b4cdb` | **Brand violet.** The logo circle, Ashby word-mark. |
| `#ff5dfc` / `rgb(255,93,252)` | Hot magenta accent — card edges, the "Application Chief" line |
| `#e6533c` | Warm red word-mark |
| `rgba(255,255,255,0.92)` | Legibility plate behind text on busy scenes |

**Rule:** black on lavender, white on `#1c1c1f`, and never text directly on a
photographic scene without a plate.

## Rotation

30 of 89 blocks are rotated. The distribution is deliberate:

| Band | Count | Use |
|---|---|---|
| -7.4° … -3.1° | 18 | Cards, plates, text blocks — the default "pinned by hand" tilt |
| +5° … +19° | 7 | Stickers and cutouts, counter-rotating against the cards |
| ±33° … ±59° | 4 | Squiggles and arrows only |
| -180° | 1 | A flipped cutout |

Pick from the -7…-3 band for anything rectangular. Never rotate body text
beyond ±8° — it becomes hard to read.

## Surfaces

```css
/* dark card plate */
background: #1c1c1f;
box-shadow: calc(6*var(--rpx)) calc(6*var(--rpx)) 0 #ff5dfc;   /* hard offset, no blur */

/* legibility plate on a scene */
background: rgba(255,255,255,0.92);
border-radius: calc(10*var(--rpx));
padding: calc(4*var(--rpx)) calc(10*var(--rpx));
box-shadow: 0 0 0 1px rgba(0,0,0,0.05);

/* logo circle */
border-radius: 50%;
background: #5b4cdb;
box-shadow: inset 0 calc(-6*var(--rpx)) 0 rgba(0,0,0,0.15);
```

Shadows are **hard offsets with zero blur** in an accent colour. No soft
drop-shadows anywhere — they read as Material Design and break the paper feel.

## Motion

Almost none. The animated GIFs supply all the movement. Add no scroll-jacking,
no parallax, no reveal animations. The only interactive affordance is the logo
link and, in the onboarding, the form controls.
