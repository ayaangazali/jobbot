# 04 — onboarding redesign spec

Rebuild `/intake` in the collage language. This is the spec the implementation
follows; deviations should be argued, not silently taken.

## What exists today

`jobbot/intake_ui.py` (946 lines) renders a four-step wizard driven entirely by
client JS:

```
STEPS = ['sources', 'working', 'review', 'interview']
<div class=step id=step-sources></div>   …drawn by drawSources()
```

- `render(nav_active)` emits the shell: `<header>` with nav + a 3-dot progress
  rail, `<main>` with four empty step divs, a fixed `.actions` bar.
- `go(step)` toggles `.live` on one step at a time. `CSS` and `JS` are module
  constants in the same file.
- Backend endpoints, already working and **not to be changed**:
  `POST /api/intake/organize`, `/api/intake/questions`, `/api/intake/apply`.

It is a competent dark utilitarian form. It shares nothing visually with
landing2, so clicking the logo drops the user off a cliff.

## Goal

The user clicks the violet jobbot circle on `/landing2` and lands somewhere that
is obviously the same product: lavender canvas, Space Mono, painted strokes,
tilted plates, stickers. The wizard must stay as usable as it is now.

## Hard constraints

1. **Do not change the four steps or the API contract.** Same step ids, same
   endpoints, same payloads. This is a re-skin plus layout, not a rewrite of the
   intake logic.
2. **Forms are not collage.** Inputs, file drops and buttons must stay
   rectangular, axis-aligned, and obviously clickable. Rotate the *plate behind*
   a form, never the form controls. Touch targets ≥ 48px.
3. **Scaling.** Reuse the `--rpx` idea for decoration, but the form column
   itself must stay a normal responsive flow element with real `px`/`rem`
   sizing. A form that shrinks to 0.65 on mobile is unusable. This is the one
   place where landing2's rules are deliberately broken — decoration scales,
   controls do not.
4. **Legibility beats texture.** Any text over a scene gets a plate. Contrast
   ≥ 4.5:1 for body, ≥ 3:1 for large text.
5. **Reuse existing assets** from `/static/landing2/img/`. No new downloads.

## Layout

Two layers on every step:

```
┌──────────────────────────────────────────────┐
│ DECOR LAYER  (position:absolute, pointer-events:none, --rpx-scaled)
│   scene strip at top, strokes, squiggles, stickers
├──────────────────────────────────────────────┤
│ CONTENT LAYER (normal flow, max-width 720px, centred)
│   header · step rail · the actual form · action bar
└──────────────────────────────────────────────┘
```

Decor never intercepts clicks (`pointer-events:none` on the whole layer).

### Header

Reuse the landing2 identity: the violet circle logo (Nanum Pen Script, 34u) at
top-left linking back to `/landing2`, and the nav as small Space Mono links.
Page background `rgb(224,224,255)`.

### Step rail

Replace the three grey dots with four numbered stops in the collage idiom:

- Each stop: a small cream stroke (`asset-2409278a72.gif`) with the step number
  in Lato bold and the label in Space Mono 13u beneath.
- Current step: violet `#5b4cdb` fill, slight scale-up, tilt -4°.
- Completed: black X sticker (`asset-36cc96ea5e.gif`) laid over the stop.
- Connected by the yellow squiggle (`asset-191a616ef1.gif`) rotated 90°.

### Step 1 — sources (the "upload your resume" moment)

This is the page the landing CTA lands on, so it carries the most design weight.

- Heading: **"Let's see what you've got"** — National Park 700, 26u, centred,
  on a stroke.
- Sub: Space Mono 17.6u — "Drop a resume, paste a LinkedIn, or point at a
  folder. jobbot reads it once and reuses it forever."
- **Dropzone**: a large dashed-border panel on a `rgba(255,255,255,0.92)`
  plate, tilted **-1.5°** (just enough to read as pinned, not enough to feel
  broken). Dashed 3px `#5b4cdb`. Centre: a file-cutout sticker and
  "drop your resume here / or browse". On dragover: fill tints violet at 8%,
  border goes solid magenta `#ff5dfc`, tilt animates to 0°.
- Each added source becomes a **card**: dark `#1c1c1f` plate, hard magenta
  offset shadow, filename in Lato bold, type + size in Space Mono 13u, a
  remove X. Alternate card tilt `-4.77°` / `+3°` down the list.
- Scene strip behind the whole step: `asset-7d08b9b774.jpg` (valley), 240u tall,
  `object-fit:cover`, with a lavender fade to the content below.

### Step 2 — working

The extraction progress state. Keep the existing progress logic.

- Heading: "jobbot is reading."
- Progress rendered as a **painted bar**: the track is a cream stroke, the fill
  is solid violet with a hard edge — not a rounded CSS progress bar.
- Each completed task drops in as a small plate with a black X sticker.
- One animated sticker (`asset-5060552dc3.gif`) parked beside the bar so the
  step has motion without a spinner.

### Step 3 — review

Cards for everything extracted (roles, skills, education).

- Two-column grid at ≥ 900px, one column below.
- Each card: white plate, tilt alternating ±3°, editable fields inline.
- Section headings on strokes.
- A "looks right" primary and "fix something" secondary in the action bar.

### Step 4 — interview

Screening questions.

- Each question on its own white plate with the question in Lato bold and the
  answer field in Space Mono.
- Answered questions get the X sticker in the corner.
- Closing: "That's it. jobbot has what it needs." over the art-deco interior
  scene (`asset-7356a2b7f2.jpg`), with a primary CTA back to `/` (overview).

### Action bar

Fixed to the bottom, lavender with a 3px black top border (echoing the dashed
rule under the landing2 header).

- Primary button: violet `#5b4cdb`, white Lato bold, hard black offset shadow
  `4px 4px 0`, no radius beyond 4px, **no rotation**.
- Secondary: transparent with a 2px black border.
- Both ≥ 48px tall.

## Overview page

`/` currently renders the plain dashboard. Bring it into the same family with
the cheapest possible change:

- Same lavender background, Space Mono body, National Park headings.
- The pipeline strip becomes stops on a painted rail, matching the intake step
  rail.
- Tiles become tilted plates with hard offset shadows.
- Keep every table as a table — data density beats texture. Tables get a white
  plate and a black border, nothing more.

## Acceptance

- `/intake` returns 200, all four steps reachable, existing JS step logic intact.
- `POST /api/intake/organize|questions|apply` unchanged and still wired.
- Logo click path `/landing2 → /intake` looks continuous: same background,
  same fonts, same violet.
- No console errors, no broken images, no horizontal scroll at 1440 or 390.
- Every form control ≥ 48px touch target and axis-aligned.
- Contrast ≥ 4.5:1 on body text — check the dropzone hint and card meta lines,
  which are the likely failures.
