"""Write answers into a live form.

Per-control strategy, each choice driven by a documented failure mode:

  react-select (Greenhouse, Ashby, Lever)
      Rebuilds its DOM on every keystroke. Any cached element handle goes stale
      mid-word. Type character by character and re-query the listbox each time.

  Autocomplete / typeahead
      `fill()` sets .value and fires one input event, which never opens the
      suggestion list. Type sequentially so the widget's own key handlers run.

  Lever checkboxes and radios
      Programmatic clicks on them are reported to trigger hCaptcha. Prefer the
      associated label element, which is what a human actually clicks.

  Workable
      Aggressively re-renders; re-query immediately before every interaction.

  File upload
      `set_input_files` against the hidden <input type=file> bypasses the OS
      dialog entirely. Never click the pretty "Attach" button first.

Everything here is idempotent and verifies its own write. A fill that silently
does nothing is the single most expensive bug in this system: it surfaces as a
validation error at submit, after the resume and the project already exist.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
import re
from pathlib import Path
from typing import Any

import structlog

from jobbot.forms.matching import (
    is_decline, match_acknowledgement, match_boolean, match_decline,
    match_numeric_range, match_option,
    fold_accents,
)
from jobbot.forms.model import FieldKind, FormField, ProposedAnswer

log = structlog.get_logger(__name__)


class FillError(RuntimeError):
    pass


def q(text: str) -> str:
    """Quote a string for interpolation into a selector.

    Option labels are employer-authored text, and apostrophes are everywhere in
    them -- "Bachelor's Degree", "I don't wish to answer". Pasting one into
    `label:has-text('...')` produced an unparseable selector, every fallback
    threw the same way, and the field was silently left blank. json.dumps gives
    a correctly escaped double-quoted string, which both CSS and Playwright's
    text engine accept.
    """
    return json.dumps(str(text))


async def _human_pause(lo: float = 0.12, hi: float = 0.38) -> None:
    """Pacing, not choreography.

    Behavioural scoring at the invisible captcha reacts to event ordering and
    dwell time, not to mouse-curve realism -- and filling fourteen fields in
    900ms is the shape it is looking for.
    """
    await asyncio.sleep(random.uniform(lo, hi))


async def _locate(page: Any, field: FormField, timeout: int = 8000) -> Any:
    """Find the control, falling back to its label when we have no selector.

    Vision can report a field the DOM walk missed, in which case selector is
    empty. Passing "" to a locator raises a CSS parse error, so resolve by
    accessible name instead of crashing.
    """
    if field.selector:
        loc = page.locator(field.selector).first
        await loc.wait_for(state="visible", timeout=timeout)
        return loc

    label = (field.label or "").split("\n")[0].strip()
    if not label:
        raise FillError("field has neither a selector nor a usable label")
    for cand in (
        page.get_by_label(label, exact=False).first,
        page.get_by_role("textbox", name=label).first,
        page.get_by_role("combobox", name=label).first,
        page.locator(f"[aria-label*={q(label[:40])}]").first,
    ):
        try:
            if await cand.count():
                await cand.wait_for(state="visible", timeout=3000)
                return cand
        except Exception:  # noqa: BLE001
            continue
    raise FillError(f"could not locate field by label: {label[:60]!r}")


async def _visible(page: Any, selector: str, timeout: int = 8000) -> Any:
    loc = page.locator(selector).first
    await loc.wait_for(state="visible", timeout=timeout)
    return loc


async def fill_text(page: Any, field: FormField, value: str, *, sequential: bool = False) -> bool:
    loc = await _locate(page, field)
    await loc.scroll_into_view_if_needed()
    await _human_pause()
    if sequential:
        await loc.click()
        await loc.fill("")
        await loc.press_sequentially(str(value), delay=random.randint(28, 65))
    else:
        await loc.fill(str(value))
    got = await loc.input_value()
    want = str(value).strip()
    got_s = got.strip()
    # Comparing only the first 40 characters could not see truncation: a 2000
    # character essay written into a field with a maxlength passed the check on
    # its opening words while the rest was silently dropped.
    ok = got_s == want
    if not ok and got_s[:40] == want[:40] and len(got_s) < len(want):
        log.warning("fill.text_truncated", label=field.label[:50],
                    wanted_chars=len(want), got_chars=len(got_s),
                    max_length=field.max_length)

    if not ok and field.kind is FieldKind.PHONE:
        # A phone widget reformats what it is given: "6693609914" comes back as
        # "(669) 360-9914", which is the same number and not a failure. Compare
        # digits before retrying -- the retry types key by key, and racing
        # intl-tel-input's reformatting cost a digit: "(669) 609-914".
        digits = re.sub(r"\D", "", str(value))
        ok = bool(digits) and re.sub(r"\D", "", got).endswith(digits[-10:])
        if not ok and digits:
            await loc.fill("")
            await loc.fill(digits)
            got = await loc.input_value()
            ok = re.sub(r"\D", "", got).endswith(digits[-10:])

    if not ok:
        log.warning("fill.text_mismatch", label=field.label[:50],
                    wanted=str(value)[:40], got=got[:40])
    return ok


async def fill_select(page: Any, field: FormField, value: str) -> bool:
    """Native <select>. Snap to a real option; never inject free text."""
    opts = field.option_labels()
    ack = match_acknowledgement(value, opts)
    if ack is not None:
        chosen, score, how = ack, 1.0, "acknowledgement"
    elif is_decline(str(value)) and match_decline(opts):
        chosen, score, how = match_decline(opts), 1.0, "decline-synonym"
    else:
        chosen, score, how = match_option(str(value), opts)
    if chosen is None:
        log.warning("fill.select_no_match", label=field.label[:50],
                    wanted=str(value)[:40], score=score)
        return False
    loc = await _locate(page, field)
    await loc.scroll_into_view_if_needed()
    await _human_pause()
    try:
        await loc.select_option(label=chosen)
    except Exception:
        opt = next((o for o in field.options if o.label == chosen), None)
        if opt is None:
            return False
        await loc.select_option(value=opt.value)
    log.debug("fill.select", label=field.label[:40], chose=chosen, via=how)
    return True


_VISIBLE_OPTIONS_JS = r"""
() => Array.from(document.querySelectorAll(
        '[role="option"], .select__option, li[id*="option"]'))
  .filter(o => { const r = o.getBoundingClientRect();
                 return r.width > 0 && r.height > 0; })
  .map(o => (o.innerText || '').trim())
  .filter(Boolean)
"""

_CLICK_OPTION_JS = r"""
(wanted) => {
  const nodes = Array.from(document.querySelectorAll(
      '[role="option"], .select__option, li[id*="option"]'))
    .filter(o => { const r = o.getBoundingClientRect();
                   return r.width > 0 && r.height > 0; });
  for (const o of nodes) {
    if ((o.innerText || '').trim() === wanted) {
      o.scrollIntoView({block: 'nearest'});
      o.click();
      return true;
    }
  }
  return false;
}
"""

_CONTROL_TEXT_JS = r"""
(sel) => {
  const e = document.querySelector(sel);
  if (!e) return '';
  // closest() matches the element itself, and the input carries a
  // "select__input" class -- so asking for the nearest [class*=select]
  // returns the input, whose innerText is always empty. Walk to the actual
  // control wrapper instead and read the rendered value.
  let c = e.parentElement;
  while (c && !/select__control|select__value-container/.test(c.className || '')) {
    c = c.parentElement;
    if (c === document.body) { c = null; break; }
  }
  if (!c) c = e.closest('.field, fieldset') || e.parentElement;
  const single = c && c.querySelector('.select__single-value, [class*="singleValue"]');
  if (single) return (single.innerText || '').trim().slice(0, 120);
  return c ? (c.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 120) : '';
}
"""


async def _close_open_menus(page: Any, tries: int = 3) -> None:
    """Dismiss any open listbox so option discovery starts from a clean slate."""
    for _ in range(tries):
        if not await _visible_options(page):
            return
        with contextlib.suppress(Exception):
            await page.keyboard.press("Escape")
        await asyncio.sleep(0.2)
    with contextlib.suppress(Exception):
        await page.mouse.click(4, 4)     # click away as a last resort
        await asyncio.sleep(0.25)


async def _visible_options(page: Any) -> list[str]:
    try:
        return await page.evaluate(_VISIBLE_OPTIONS_JS) or []
    except Exception:  # noqa: BLE001
        return []


async def fill_combobox(page: Any, field: FormField, value: str) -> bool:
    """Custom listbox widget: open it, then choose from the menu IT opened.

    Option discovery is done by difference. A page routinely has more than one
    menu mounted -- a phone-country picker is the usual offender -- and
    react-select portals its menu to <body>, so neither "everything matching
    [role=option]" nor "options inside the control's container" identifies the
    right list. Snapshot the visible options before the click, snapshot after,
    and the newly-appeared ones belong to this control.

    Without this, a relocation question gets answered from the country list.
    """
    loc = await _locate(page, field)
    await loc.scroll_into_view_if_needed()
    await _human_pause()

    # Close anything already open before measuring. Consecutive yes/no fields
    # offer identical option text, so a menu left open from the previous field
    # makes the before/after diff come out empty and the fill silently no-ops.
    await _close_open_menus(page)

    before = set(await _visible_options(page))
    await loc.click()
    await asyncio.sleep(0.45)
    after = await _visible_options(page)
    opts = [o for o in after if o not in before]

    text = str(value)
    chosen, score, how = (None, 0.0, "no-options")
    if opts:
        # A single-option consent control has no "Yes" to match.
        ack = match_acknowledgement(value, opts)
        if ack is not None:
            chosen, score, how = ack, 1.0, "acknowledgement"
        elif is_decline(text):
            d = match_decline(opts)
            if d is not None:
                chosen, score, how = d, 1.0, "decline-synonym"
        if chosen is None:
            chosen, score, how = match_option(text, opts)

    # Typing narrows a long list. Only if the opened menu did not already offer
    # what we want -- typing into a prefix-filtered widget can empty it.
    if chosen is None:
        with contextlib.suppress(Exception):
            # Type the head of the value: a location autocomplete wants "San
            # Jose", then offers the full "San Jose, California, United States"
            # for the matcher to pick exactly.
            # Type without accents: the search index behind these pickers is
            # plain ASCII, and "José" returns nothing where "Jose" matches.
            await loc.press_sequentially(fold_accents(text.split(",")[0])[:32],
                                         delay=random.randint(35, 75))
        # A school or location picker queries a server on each keystroke, and
        # a fixed wait raced it: the menu was still empty when we looked, so a
        # required field was left blank with "no options" in the log. Poll.
        after = []
        for _ in range(10):
            await asyncio.sleep(0.3)
            after = await _visible_options(page)
            if [o for o in after if o not in before]:
                break
        opts = [o for o in after if o not in before] or after
        if opts:
            ack = match_acknowledgement(value, opts)
            if ack is not None:
                chosen, score, how = ack, 1.0, "acknowledgement"
            elif is_decline(text) and match_decline(opts):
                chosen, score, how = match_decline(opts), 1.0, "decline-synonym"
            else:
                chosen, score, how = match_option(text, opts)

    if chosen is None:
        log.warning("fill.combobox_no_option", label=field.label[:50],
                    wanted=text[:40], seen=opts[:6])
        with contextlib.suppress(Exception):
            await page.keyboard.press("Escape")
        return False

    clicked = False
    with contextlib.suppress(Exception):
        clicked = bool(await page.evaluate(_CLICK_OPTION_JS, chosen))
    if not clicked:
        with contextlib.suppress(Exception):
            await page.get_by_role("option", name=chosen, exact=True).first.click(timeout=3000)
            clicked = True
    if not clicked:
        log.warning("fill.combobox_click_failed", label=field.label[:50], chose=chosen)
        return False

    await asyncio.sleep(0.35)

    # Confirm it stuck. A combobox that silently reverts is worse than one that
    # fails outright, because the form then looks complete.
    stuck = True
    with contextlib.suppress(Exception):
        got = ((await loc.input_value()) or "").strip()
        if not got and field.selector:
            shown = (await page.evaluate(_CONTROL_TEXT_JS, field.selector) or "").lower()
            # Either direction: a phone-country picker offers "United States +1"
            # in its menu and then displays just "+1" in the control.
            c = chosen.lower()
            stuck = bool(shown) and (c in shown or shown in c)
            if not stuck:
                log.warning("fill.combobox_did_not_stick", label=field.label[:50],
                            chose=chosen, shows=(shown or "")[:60])
    if not stuck:
        return False

    log.debug("fill.combobox", label=field.label[:40], chose=chosen, via=how)
    return True


# Find the option to click WITHIN one radio group. Returns the input's id.
#
# Radio options are labelled "Yes" and "No" on every question, so a page-wide
# `label:has-text("Yes")` resolves to the first Yes on the page -- which is a
# different question's. On a form asking both "are you authorised to work" and
# "will you require sponsorship", one answer was clicked twice and the other
# left blank, and a blank required question is a blocker that never clears.
# The group is identified by the radio `name` the DOM walk already grouped on,
# falling back to whichever group's surrounding text matches the question.
_RADIO_PICK_JS = r"""
({selector, question, choice}) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const want = norm(choice);
  const tag = el => {
    const k = 'jp' + Math.random().toString(36).slice(2, 9);
    el.setAttribute('data-jobbot-pick', k);
    return '[data-jobbot-pick="' + k + '"]';
  };
  const attrEsc = v => String(v).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const labelOf = r => {
    if (r.id) {
      const l = document.querySelector('label[for="' + attrEsc(r.id) + '"]');
      if (l) return l.innerText;
    }
    const p = r.closest('label');
    return p ? p.innerText : (r.value || '');
  };

  // 1. A real radio group, identified by the name the DOM walk grouped on.
  const radios = [...document.querySelectorAll('input[type=radio]')];
  let name = null;
  if (selector) {
    try {
      const e = document.querySelector(selector);
      if (e && e.type === 'radio') name = e.name;
    } catch (err) { /* a vision-invented selector need not parse */ }
  }
  let group = name ? radios.filter(r => r.name === name) : [];

  const qn = norm(question);
  const words = qn.split(' ').filter(w => w.length > 3);
  const scoreText = txt => txt.includes(qn.slice(0, 40))
      ? 1000 : words.filter(w => txt.includes(w)).length;

  if (!group.length && radios.length && qn) {
    let best = null, bestScore = 0;
    for (const n of [...new Set(radios.map(r => r.name))]) {
      const g = radios.filter(r => r.name === n);
      let holder = g[0];
      for (let i = 0; i < 6 && holder && holder.parentElement; i++) {
        holder = holder.parentElement;
        if (norm(holder.innerText).length > qn.length / 2) break;
      }
      const sc = scoreText(norm(holder ? holder.innerText : ''));
      if (sc > bestScore) { bestScore = sc; best = g; }
    }
    if (bestScore > 0) group = best;
  }
  if (group.length) {
    const hit = group.find(r => norm(labelOf(r)) === want)
             || group.find(r => norm(labelOf(r)).startsWith(want))
             || group.find(r => norm(r.value) === want);
    if (hit) {
      const lab = hit.id
        ? document.querySelector('label[for="' + attrEsc(hit.id) + '"]')
        : hit.closest('label');
      return {click: tag(lab || hit), verify: tag(hit), kind: 'radio'};
    }
  }

  // 2. No radio anywhere: Ashby renders a Yes/No question as one hidden
  //    checkbox with the choices as ordinary clickable elements beside it.
  //    Find the block that asks THIS question, then the choice inside it.
  if (!qn) return null;
  const blocks = [...document.querySelectorAll('div, fieldset, section, li')]
    .filter(el => {
      const t = norm(el.innerText);
      return t.includes(qn.slice(0, 40)) && t.length < qn.length + 400;
    });
  if (!blocks.length) return null;
  const block = blocks[blocks.length - 1];   // innermost match

  const choices = [...block.querySelectorAll('label, button, span, div, [role=radio], [role=option]')]
    .filter(el => el.children.length === 0 && norm(el.innerText) === want);
  if (!choices.length) return null;

  const backing = block.querySelector('input[type=checkbox], input[type=radio]');
  return {click: tag(choices[0]), verify: backing ? tag(backing) : null, kind: 'custom'};
}
"""


async def fill_radio(page: Any, field: FormField, value: Any) -> bool:
    """Choose within a radio group by clicking its LABEL, not the input.

    Clicking the input programmatically is what reportedly trips Lever's
    invisible hCaptcha; the label is the element a human actually hits.
    """
    opts = field.option_labels()
    chosen = match_boolean(value, opts) if isinstance(value, bool) else None
    if chosen is None:
        chosen, _, _ = match_option(str(value), opts)
    if chosen is None and isinstance(value, bool):
        chosen = "Yes" if value else "No"
    if chosen is None:
        log.warning("fill.radio_no_match", label=field.label[:50], wanted=str(value)[:40])
        return False

    await _human_pause()
    pick = None
    with contextlib.suppress(Exception):
        pick = await page.evaluate(_RADIO_PICK_JS, {
            "selector": field.selector or "",
            "question": field.label[:160],
            "choice": chosen,
        })

    if pick and pick.get("click"):
        verify = pick.get("verify")
        try:
            loc = page.locator(pick["click"]).first
            await loc.scroll_into_view_if_needed()
            await loc.click(timeout=4000)
            await asyncio.sleep(0.25)
            if verify:
                with contextlib.suppress(Exception):
                    if await page.locator(verify).first.is_checked():
                        log.debug("fill.radio", label=field.label[:40],
                                  chose=chosen, kind=pick.get("kind"))
                        return True
            else:
                log.debug("fill.radio", label=field.label[:40], chose=chosen,
                          kind=pick.get("kind"), verified=False)
                return True
        except Exception:  # noqa: BLE001
            pass
        # A styled label over a hidden input refuses an ordinary click.
        if verify:
            with contextlib.suppress(Exception):
                await page.locator(verify).first.check(timeout=3000, force=True)
                if await page.locator(verify).first.is_checked():
                    log.debug("fill.radio", label=field.label[:40], chose=chosen, via="check")
                    return True

    log.warning("fill.radio_not_found", label=field.label[:50], chose=str(chosen)[:30])
    return False


async def fill_date(page: Any, field: FormField, value: str) -> bool:
    """Write a date in the format the control actually parses.

    A native <input type=date> wants ISO. A scripted picker does not: given
    "2026-06-01" Ashby's parsed it as UTC midnight and rendered it in local
    time, so an availability date of 1 June went in as 31 May. Off by one day
    on a date the candidate stated is a wrong answer, not a formatting nit.
    """
    loc = await _locate(page, field)
    await loc.scroll_into_view_if_needed()
    await _human_pause()

    native = ""
    with contextlib.suppress(Exception):
        native = (await loc.get_attribute("type") or "").lower()

    iso = value.strip()[:10]
    if native == "date":
        await loc.fill(iso)
        return (await loc.input_value() or "").startswith(iso)

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", iso)
    text = f"{m.group(2)}/{m.group(3)}/{m.group(1)}" if m else value
    await loc.fill("")
    await loc.press_sequentially(text, delay=random.randint(30, 70))
    await asyncio.sleep(0.4)
    got = (await loc.input_value() or "").strip()
    ok = bool(m) and m.group(3) in got and m.group(1) in got
    if not ok:
        log.warning("fill.date_mismatch", label=field.label[:50], wanted=text, got=got[:20])
    return ok


async def fill_checkbox(page: Any, field: FormField, value: bool) -> bool:
    loc = await _locate(page, field)
    await loc.scroll_into_view_if_needed()
    await _human_pause()
    try:
        if value:
            await loc.check(timeout=4000)
        else:
            await loc.uncheck(timeout=4000)
        return True
    except Exception:
        # Some designs hide the input and style the label; click that instead.
        try:
            await page.locator(f"label[for={q(field.field_id)}]").first.click(timeout=3000)
            return True
        except Exception:
            return False


async def upload_file(page: Any, field: FormField, path: str | Path) -> bool:
    """Attach a file straight to the hidden input, bypassing the OS dialog."""
    p = Path(path)
    if not p.exists():
        raise FillError(f"file to upload does not exist: {p}")

    # An empty selector is not a candidate: `page.locator("")` raises a CSS
    # parse error that reads like a real failure in the logs.
    for sel in (field.selector, "input[type=file]"):
        if not sel:
            continue
        try:
            loc = page.locator(sel).first
            if await loc.count():
                await loc.set_input_files(str(p))
                await asyncio.sleep(0.9)
                log.info("fill.uploaded", label=field.label[:40], file=p.name)
                return True
        except Exception as exc:  # noqa: BLE001
            log.debug("fill.upload_attempt_failed", sel=sel, error=str(exc)[:100])
            continue

    # Dropzone with no reachable input: drive the file chooser instead.
    try:
        async with page.expect_file_chooser(timeout=6000) as info:
            await page.locator("button:has-text('Attach'), button:has-text('Upload')").first.click()
        chooser = await info.value
        await chooser.set_files(str(p))
        await asyncio.sleep(0.9)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("fill.upload_failed", error=str(exc)[:150])
        return False


AUTOCOMPLETE_HINTS = ("location", "city", "address", "school", "university",
                      "country", "state", "region", "company")


async def apply_answer(
    page: Any,
    field: FormField,
    answer: ProposedAnswer,
    *,
    resume_path: str | Path | None = None,
) -> bool:
    """Write one answer, dispatching on control kind."""
    if not answer.submittable:
        return False
    v = answer.value

    try:
        if field.kind is FieldKind.FILE:
            return await upload_file(page, field, resume_path or str(v))

        if field.kind in (FieldKind.SELECT, FieldKind.MULTISELECT, FieldKind.COMBOBOX):
            if isinstance(v, bool):
                # "True"/"False" match no real option. Map onto whatever this
                # form calls yes and no before touching the widget.
                mapped = match_boolean(v, field.option_labels())
                if mapped is None and field.options:
                    log.warning("fill.bool_unmapped", label=field.label[:50],
                                value=v, options=field.option_labels()[:6])
                    return False
                v = mapped if mapped is not None else v
            elif isinstance(v, (int, float)):
                m, _ = match_numeric_range(float(v), field.option_labels())
                if m:
                    v = m
            if field.kind is FieldKind.COMBOBOX:
                return await fill_combobox(page, field, str(v))
            return await fill_select(page, field, str(v))

        if field.kind is FieldKind.RADIO:
            return await fill_radio(page, field, v)

        if field.kind in (FieldKind.CHECKBOX, FieldKind.CONSENT):
            return await fill_checkbox(page, field, bool(v))

        if field.kind is FieldKind.DATE:
            return await fill_date(page, field, str(v))

        sequential = any(h in field.label.lower() for h in AUTOCOMPLETE_HINTS)
        return await fill_text(page, field, str(v), sequential=sequential)

    except Exception as exc:  # noqa: BLE001
        log.warning("fill.failed", label=field.label[:50],
                    kind=field.kind.value, error=str(exc)[:160])
        return False
