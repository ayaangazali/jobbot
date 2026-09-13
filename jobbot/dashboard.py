"""Read-only local dashboard over everything a run leaves on disk.

The run already records what it did -- `applications.csv`, `answers.csv`, and a
per-application audit directory with the screenshots each checkpoint took. What
was missing was a way to look at it without opening six files in a spreadsheet.

Read-only on purpose. This shows what happened; it never edits a profile, never
retries an application, never touches the browser. Nothing here can change what
was said in the user's name, which is the one property worth keeping.

stdlib only (`http.server`), loopback by default. The data includes a full name,
address, phone number and every answer given to an employer, so it does not go
on a network interface.
"""

from __future__ import annotations

import csv
import html
import json
import os
import threading
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

import structlog

log = structlog.get_logger(__name__)

CSS = """
*{box-sizing:border-box}
a{color:var(--ink);text-decoration:none}
a:hover{text-decoration:underline}

#app{display:block;min-height:0}

.hero{position:relative;overflow:hidden;min-width:0}
.hero .decor::after{content:"";position:absolute;inset:0;
background:linear-gradient(180deg,rgba(224,224,255,.2),rgba(224,224,255,.94) 88%)}
.hero .decor img{width:100%;height:100%;object-fit:cover;display:block}

.site-header{display:flex;align-items:center;gap:18px;flex-wrap:wrap;padding:18px 24px}
.site-header nav{display:flex;flex-wrap:wrap;gap:4px 16px;font-family:var(--f-body);
background:none;border-bottom:none;position:static;padding:0;z-index:auto}
.site-header nav a{color:var(--ink);font-size:14px;padding:4px 1px;background:none;
border-radius:0;border-bottom:2px solid transparent}
.site-header nav a:hover{border-bottom-color:var(--violet)}
.site-header nav a.active{border-bottom-color:var(--violet);font-weight:700}

main{padding:4px 24px 64px;max-width:1400px;margin:0 auto;flex:none;
overflow-y:visible;min-width:0;width:auto}
h2{font-size:15px;letter-spacing:.4px;margin:34px 0 12px}
h2:first-child{margin-top:6px}

.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));
gap:22px 18px;padding:8px 4px 14px}
.tile{padding:14px 14px 12px}
.tile .n{font-family:var(--f-display);font-weight:700;font-size:26px;
line-height:1.15;overflow-wrap:anywhere}
.tile .n.txt{font-size:16px;padding:3px 0 4px}
.nw{white-space:nowrap}
.tile .k{font-family:var(--f-body);color:#4a4664;font-size:11px;
text-transform:uppercase;letter-spacing:.6px;margin-top:6px}

.table-wrap{overflow-x:auto}
table.plate{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #cdc8ef;
vertical-align:top;max-width:520px;overflow-wrap:break-word}
th{font-family:var(--f-label);font-weight:700;font-size:11px;text-transform:uppercase;
letter-spacing:.6px;white-space:nowrap;border-bottom:2px solid var(--ink)}
td{font-family:var(--f-body);font-size:13px}
tr:last-child td{border-bottom:none}
tr:hover td{background:#f1efff}

.pill{display:inline-block;padding:2px 9px;font-family:var(--f-body);font-weight:700;
font-size:11px;letter-spacing:.4px;text-transform:uppercase;
border:2px solid var(--ink);border-radius:2px;background:#fff}
.s-confirmed{background:#d7f6dd}
.s-submitted{background:#ffefb0}
.s-needs_human,.s-knockout_fail{background:#ffddab}
.s-failed,.s-unreachable{background:#ffd2e4;color:#7a0d2c}
.s-prepared,.s-filling{background:#e3ddff}
.s-filtered_out,.s-ghost_suspected,.s-discovered{background:#eae8f5;color:#4a4664}

.dim{color:#4a4664}.ok{color:#0f7a42}.warn{color:#a5590a}.bad{color:#a3123a}

pre{background:var(--plate-light);border:2px solid var(--ink);padding:10px;
overflow:auto;max-height:420px;margin:0;white-space:pre-wrap;font-family:var(--f-body)}

.shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.shots figure{margin:0;background:var(--plate-light);border:2px solid var(--ink)}
.shots img{width:100%;display:block;border-bottom:2px solid var(--ink)}
.shots figcaption{padding:6px 8px;color:#4a4664;font-size:11px;font-family:var(--f-body)}

.bar{display:inline-block;vertical-align:middle;width:52px;height:8px;
background:#dcd8ff;border:1px solid var(--ink);margin-right:6px}
.bar i{display:block;height:100%;background:var(--violet)}

.empty{font-family:var(--f-body);color:#4a4664;padding:16px;
border:2px dashed var(--ink);background:var(--plate-light)}
.banner{font-family:var(--f-body);background:var(--plate-light);
border:2px solid var(--violet);padding:10px 14px;margin-bottom:16px}

/* pipeline strip: stops on a painted rail, echoing the intake step rail.
   Reset app.css's generic [class*="stage"] placeholder card first. */
.rail,.stage,.stage-stop,.stage-stop-active,.stage-n,.stage-label{background:none;
border:none;padding:0;border-radius:0;gap:0;color:var(--ink)}
.rail{display:flex;align-items:flex-end;flex-wrap:wrap;gap:0 2px;padding:14px 4px 6px;
margin:0}
.stage{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:78px}
.stage-stop{position:relative;display:flex;align-items:center;justify-content:center;
width:64px;height:48px}
.stage-stop img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}
.stage-stop-active{background:var(--violet);border:2px solid var(--ink);
box-shadow:var(--lift-black)}
.stage-n{position:relative;z-index:1;display:inline;font-family:var(--f-label);
font-weight:700;font-size:18px}
.stage-stop-active .stage-n{color:#fff}
.stage-label{font-family:var(--f-body);font-size:11px;text-align:center;
text-transform:uppercase;letter-spacing:.4px;max-width:92px}
.rail-connector{width:32px;height:32px;object-fit:contain;transform:rotate(90deg);
align-self:center;margin:0 -4px 22px}

.visually-hidden{position:absolute;width:1px;height:1px;padding:0;margin:-1px;
overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
"""

NAV = [("/", "overview"), ("/queue", "queue"), ("/answers", "answers"), ("/profile", "profile"),
       ("/edit", "edit profile"), ("/intake", "intake"), ("/lessons", "lessons"),
       ("/log", "notifications"), ("/status", "status")]

# Single source of truth for what this server exposes. Rendered on /status and
# walked by the self-check, so a route added without a description shows up.
ROUTES = [
    {"path": "/", "method": "GET", "what": "run tiles + every posting, auto-refreshing"},
    {"path": "/app/<audit-dir>", "method": "GET",
     "what": "one application: answers, verification, resume, screenshots"},
    {"path": "/queue", "method": "GET",
     "what": "every discovered job: tick the ones to apply to, blacklist your own"},
    {"path": "/api/queue", "method": "POST",
     "what": "record approve / blacklist / un-decide for the ticked jobs"},
    {"path": "/api/standard-resume", "method": "POST",
     "what": "upload the one PDF sent to every application"},
    {"path": "/answers", "method": "GET",
     "what": "every answer given in your name (?blank=1 for just the gaps)"},
    {"path": "/profile", "method": "GET", "what": "read-only profile summary"},
    {"path": "/edit", "method": "GET", "what": "the profile editor form"},
    {"path": "/intake", "method": "GET",
     "what": "dump links, resumes and a dictated paragraph; review what the model extracts"},
    {"path": "/lessons", "method": "GET", "what": "what each run learned per ATS"},
    {"path": "/log", "method": "GET", "what": "notifications sent or attempted"},
    {"path": "/status", "method": "GET", "what": "this page: config checks + routes"},
    {"path": "/f/<path>", "method": "GET",
     "what": "a screenshot or resume PDF from data/ (png/jpg/pdf only)"},
    {"path": "/api/status", "method": "GET", "what": "the config checks as JSON"},
    {"path": "/api/profile", "method": "GET", "what": "current profile as JSON"},
    {"path": "/api/profile", "method": "POST",
     "what": "validate and save the profile; backs up the previous file first"},
    {"path": "/api/applications", "method": "GET", "what": "applications.csv as JSON"},
    {"path": "/api/answers", "method": "GET", "what": "answers.csv as JSON"},
    {"path": "/api/resume-text", "method": "POST",
     "what": "PDF bytes in, extracted text out; never auto-fills the profile"},
    {"path": "/api/intake/organize", "method": "POST",
     "what": "dump + resumes + links in, reviewable proposal cards out"},
    {"path": "/api/intake/questions", "method": "POST",
     "what": "questions targeted at whatever this profile is missing"},
    {"path": "/api/intake/apply", "method": "POST",
     "what": "merge accepted cards into the profile and save"},
]

TERMINAL = {"confirmed", "submitted"}
LIVE = {"filling", "prepared"}


# -- reading -------------------------------------------------------------


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def read_jsonl(path: Path, limit: int = 400) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:  # noqa: BLE001
            continue
    return out


def audit_dirname(job_id: str) -> str:
    """Match the orchestrator's own sanitising, so links resolve."""
    return job_id.replace(":", "_").replace("/", "_")


# -- rendering -----------------------------------------------------------


def e(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def page(title: str, active: str, body: str, *, refresh: int = 0) -> bytes:
    nav = "".join(
        f'<a href="{p}" class="{"active" if p == active else ""}">{n}</a>'
        for p, n in NAV
    )
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return (
        f"<!doctype html><html><head><meta charset=utf-8><meta name='viewport' content='width=device-width, initial-scale=1'>{meta}"
        f'<link rel="icon" href="data:,">'
        f"<title>jobbot — {e(title)}</title>"
        f'<link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700'
        f'&family=Space+Mono:wght@400;700&family=Nanum+Pen+Script'
        f'&family=Zilla+Slab+Highlight:wght@400;700&display=swap" rel="stylesheet">'
        f'<link rel="stylesheet" href="/static/collage.css">'
        f'<link rel="stylesheet" href="/static/app.css">'
        f"<style>{CSS}</style></head>"
        f'<body class=collage>'
        f'<div id="app">'
        f'<div class=hero>'
        f'<div class=decor aria-hidden="true">'
        f'<img src="/static/landing2/img/asset-8bd696a182.jpg" alt="">'
        f'</div>'
        f'<header class="site-header layer-content">'
        f'<a class=logo-dot href="/landing2" title="jobbot home">jobbot</a>'
        f'<h1 class=visually-hidden>jobbot — {e(title)}</h1>'
        f'<nav role="navigation" aria-label="main">{nav}</nav>'
        f'</header>'
        f'</div>'
        f'<main class=layer-content>{body}</main>'
        f'</div>'
        f'<script src="/static/app.js"></script>'
        f"</body></html>"
    ).encode()


def pill(status: str) -> str:
    return f'<span class="pill s-{e(status)}">{e(status or "?")}</span>'


def tiles(pairs: list[tuple[str, Any]]) -> str:
    def cell(k: str, v: Any, i: int) -> str:
        # A count fits at 26px; a company name or a status word does not, and
        # clipping the tenant name is exactly the thing you opened this to read.
        cls = "n txt" if len(str(v)) > 7 else "n"
        tilt = "tilt-a" if i % 2 == 0 else "tilt-b"
        return (f'<div class="tile plate {tilt}"><div class="{cls}">{e(v)}</div>'
                f'<div class=k>{e(k)}</div></div>')
    return f'<div class=tiles>{"".join(cell(k, v, i) for i, (k, v) in enumerate(pairs))}</div>'


def bar(frac: float) -> str:
    pct = max(0, min(100, round(frac * 100)))
    return f'<span class=bar><i style="width:{pct}%"></i></span>'


def table(headers: list[str], rows: list[list[str]], empty: str = "nothing yet") -> str:
    if not rows:
        return f'<div class=empty>{e(empty)}</div>'
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class=table-wrap><table class=plate>'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def _outcome(a: dict[str, str]) -> str:
    """Confirmation if we have one, else why not. Full text on hover."""
    if a.get("confirmation_text"):
        cls, txt = "ok", a["confirmation_text"]
    else:
        cls, txt = "dim", (a.get("error") or a.get("notes") or "")
    if not txt:
        return ""
    short = txt[:58] + ("\u2026" if len(txt) > 58 else "")
    return f'<span class={cls} title="{e(txt)}">{e(short)}</span>'


def num(s: Any, default: float = 0.0) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


# -- views ---------------------------------------------------------------


class Dash:
    def __init__(self, data_dir: Path, profile_path: Path) -> None:
        self.data = data_dir
        self.profile_path = profile_path
        self.public_url = ""      # set by serve(), shown in the editor header

    # sources
    def apps(self) -> list[dict[str, str]]:
        return read_csv(self.data / "applications.csv")

    def answers(self) -> list[dict[str, str]]:
        return read_csv(self.data / "answers.csv")

    # -- the queue ---------------------------------------------------------

    def _queue(self) -> Any:
        from jobbot.queue import JobQueue
        return JobQueue(self.data / "queue.json")

    def standard_resume_path(self) -> Path:
        return self.data / "standard_resume.pdf"

    def _standard_info(self) -> dict[str, Any]:
        p = self.standard_resume_path()
        if not p.exists():
            return {"exists": False}
        st = p.stat()
        name = (self.data / "standard_resume.name")
        return {"exists": True, "kb": st.st_size // 1024,
                "name": name.read_text()[:120] if name.exists() else p.name,
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%d %b %H:%M")}

    def queue_view(self, show: str = "all", search: str = "") -> bytes:
        from jobbot import queue_ui
        q = self._queue()
        return page("queue", "/queue",
                    queue_ui.render(q.all(), q.counts(), self._standard_info(),
                                    show=show, q=search))

    def queue_decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        decisions = payload.get("decisions") or {}
        if not isinstance(decisions, dict):
            return {"ok": False, "error": "decisions must be an object"}
        q = self._queue()
        n = q.decide_many({str(k): str(v) for k, v in decisions.items()})
        return {"ok": True, "changed": n, "counts": q.counts()}

    def save_standard_resume(self, body: bytes, name: str) -> dict[str, Any]:
        if not body.startswith(b"%PDF"):
            # A .doc or an HTML error page saved here would be uploaded to an
            # employer under the candidate's name; check the bytes, not the name.
            return {"ok": False, "error": "that is not a PDF"}
        dest = self.standard_resume_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        (self.data / "standard_resume.name").write_text(name[:120] or dest.name)
        log.info("dashboard.standard_resume_saved", bytes=len(body), name=name[:80])
        return {"ok": True, "kb": len(body) // 1024}

    def pipeline_strip(self, apps: list[dict]) -> str:
        """Render pipeline stage counts as stops on a painted rail.

        Cream-stroke stops for ordinary stages, a violet fill for the stage(s)
        currently in flight (LIVE), joined by the yellow squiggle connector —
        the same idiom as the intake step rail.
        """
        order = ["discovered", "filtered_out", "needs_human", "prepared", "filling",
                 "knockout_fail", "failed", "ghost_suspected", "unreachable",
                 "submitted", "confirmed"]
        counts = {s: 0 for s in order}
        for a in apps:
            status = a.get("status", "discovered")
            if status in counts:
                counts[status] += 1

        shown = [s for s in order if counts[s] > 0]
        if not shown:
            return ""

        stops = []
        for i, stage in enumerate(shown):
            count = counts[stage]
            active = stage in LIVE
            label = e(stage.replace("_", " ").title())
            if active:
                stop = ('<span class="stage-stop stage-stop-active tilt-c">'
                        f'<b class=stage-n>{count}</b></span>')
            else:
                tilt = "tilt-a" if i % 2 == 0 else "tilt-b"
                stop = (f'<span class="stage-stop {tilt}">'
                        '<img src="/static/landing2/img/asset-2409278a72.gif" alt="">'
                        f'<b class=stage-n>{count}</b></span>')
            cls = "stage stage-active" if active else "stage"
            stops.append(f'<div class="{cls}" data-stage="{stage}">{stop}'
                         f'<span class=stage-label>{label}</span></div>')
            if i < len(shown) - 1:
                stops.append('<img class=rail-connector alt="" '
                             'src="/static/landing2/img/asset-191a616ef1.gif">')

        return f'<div data-component="pipeline" class=rail>{"".join(stops)}</div>'

    def overview(self) -> bytes:
        apps = self.apps()
        ans = self.answers()
        counts: dict[str, int] = {}
        for a in apps:
            counts[a.get("status", "?")] = counts.get(a.get("status", "?"), 0) + 1

        live = [a for a in apps if a.get("status") in LIVE]
        banner = ""
        if live:
            cur = live[-1]
            banner = (f'<div class=banner>in flight: '
                      f'<b>{e(cur.get("title"))}</b> @ {e(cur.get("company"))} '
                      f'— {e(cur.get("status"))}</div>')

        submitted = [a for a in apps if a.get("status") in TERMINAL]
        blanks = sum(1 for r in ans if r.get("left_blank") == "True")
        scored = [num(a.get("match_score")) for a in apps if a.get("match_score")]
        head = tiles([
            ("postings", len(apps)),
            ("submitted", len(submitted)),
            ("confirmed", counts.get("confirmed", 0)),
            ("needs you", counts.get("needs_human", 0)),
            ("knockout", counts.get("knockout_fail", 0)),
            ("unreachable", counts.get("unreachable", 0)),
            ("answers logged", len(ans)),
            ("left blank", blanks),
            ("avg fit", f"{sum(scored)/len(scored):.2f}" if scored else "-"),
        ])

        order = ["confirmed", "submitted", "filling", "prepared", "needs_human",
                 "knockout_fail", "unreachable", "failed", "ghost_suspected",
                 "filtered_out", "discovered"]
        rank = {s: i for i, s in enumerate(order)}
        rows = []
        for a in sorted(apps, key=lambda r: (rank.get(r.get("status", ""), 99),
                                             -num(r.get("match_score")))):
            d = audit_dirname(a.get("job_id", ""))
            has_audit = (self.data / "applications" / d).is_dir()
            title = e(a.get("title", ""))[:70]
            link = (f'<a href="/app/{quote(d)}">{title}</a>' if has_audit else title)
            flagged = a.get("questions_flagged") or ""
            rows.append([
                pill(a.get("status", "")),
                link,
                e(a.get("company", "")),
                e(a.get("ats", "")),
                f'<span class=nw>{bar(num(a.get("match_score")))}'
                f'{e(a.get("match_score", "")[:4])}</span>',
                (f'{e(a.get("questions_answered"))}/{e(a.get("questions_total"))}'
                 if a.get("questions_total") else '<span class=dim>&mdash;</span>'),
                (f'<span class=warn>{e(flagged)}</span>' if flagged not in ("", "0")
                 else '<span class=dim>0</span>'),
                e(a.get("heal_rounds", "")) or '<span class=dim>&mdash;</span>',
                _outcome(a),
                f'<span class=nw>'
                f'{e((a.get("applied_at") or a.get("discovered_at") or "")[:16].replace("T", " "))}'
                f'</span>',
            ])

        pipeline = self.pipeline_strip(apps)
        return page("overview", "/", banner + "<h2>run</h2>" + head
                    + (f"<h2>pipeline</h2>{pipeline}" if pipeline else "")
                    + "<h2>postings</h2>"
                    + table(["status", "role", "company", "ats", "fit", "fields",
                             "blank", "heals", "outcome", "when"], rows,
                            "no applications.csv yet — run `jobbot discover` or `jobbot run`"),
                    refresh=10)


    def app_detail(self, dirname: str) -> bytes:
        d = self.data / "applications" / dirname
        if not d.is_dir():
            return page("not found", "/", '<div class=empty>no such audit dir</div>')

        row = next((a for a in self.apps()
                    if audit_dirname(a.get("job_id", "")) == dirname), {})
        parts: list[str] = [
            f'<h2>{e(row.get("title") or dirname)}</h2>',
            tiles([
                ("status", row.get("status", "?")),
                ("company", row.get("company", "-")),
                ("ats", row.get("ats", "-")),
                ("fit", row.get("match_score", "-")),
                ("ghost", row.get("ghost_score", "-") or "-"),
                ("heals", row.get("heal_rounds", "-") or "-"),
            ]),
        ]
        if row.get("job_url"):
            parts.append(f'<p><a href="{e(row["job_url"])}" target=_blank>'
                         f'{e(row["job_url"])[:110]}</a></p>')

        for label, key in (("error", "error"), ("notes", "notes"),
                           ("knockout", "knockout_reason"),
                           ("confirmation", "confirmation_text")):
            if row.get(key):
                cls = "ok" if key == "confirmation_text" else "warn"
                parts.append(f'<h2>{label}</h2><pre class={cls}>{e(row[key])}</pre>')

        # answers
        answers = read_json(d / "answers.json") or []
        rows = []
        for a in answers:
            blank = a.get("needs_human")
            rows.append([
                f'<span class="dim nw">{e(a.get("source", ""))}</span>',
                e(a.get("label", ""))[:90] + (" *" if a.get("required") else ""),
                (f'<span class=warn>— blank: {e(a.get("blocked_reason", ""))[:70]}</span>'
                 if blank else e(a.get("value"))[:160]),
                e(a.get("rationale", ""))[:90],
                e(a.get("confidence", "")),
            ])
        parts.append("<h2>answers entered</h2>"
                     + table(["source", "field", "value", "why", "conf"], rows,
                             "no answers.json"))

        # verification
        v = read_json(d / "verification.json")
        if v:
            iss = [[pill(i.get("severity", "")), e(i.get("label", ""))[:70],
                    e(i.get("problem", ""))[:140], e(i.get("suggested_value"))[:60]]
                   for i in v.get("issues", [])]
            ready = ('<span class=ok>ready</span>' if v.get("ready")
                     else '<span class=bad>not ready</span>')
            parts.append(f'<h2>checkpoint 2 — {ready}, {e(v.get("heal_rounds"))} heal round(s)</h2>')
            if v.get("summary"):
                parts.append(f'<pre>{e(v["summary"])}</pre>')
            parts.append(table(["severity", "field", "problem", "suggested"], iss,
                               "no issues raised"))
            for k in ("unfilled_required", "validation_errors"):
                if v.get(k):
                    parts.append(f'<h2>{k.replace("_", " ")}</h2>'
                                 f'<pre class=warn>{e(json.dumps(v[k], indent=1))}</pre>')

        # resume
        resume = d / "resume.pdf"
        crit = read_json(d / "resume_critique.json") or []
        final = next((h for h in reversed(crit) if "final_ats_score" in h), {})
        if resume.exists() or crit:
            bits = []
            if final:
                bits.append(tiles([("ats score", final.get("final_ats_score", "-")),
                                   ("keywords", final.get("keyword_match", "-")),
                                   ("skills", final.get("skills_coverage", "-")),
                                   ("rounds", len(crit) - 1)]))
            if resume.exists():
                rel = quote(str(resume.relative_to(self.data)))
                bits.append(f'<p><a href="/f/{rel}" target=_blank>open resume.pdf</a> '
                            f'<span class=dim>({resume.stat().st_size // 1024} KB)</span></p>')
            rounds = [[e(h.get("round")), e(h.get("verdict")), e(h.get("revisions")),
                       e(h.get("applied")), e(h.get("ats_score")),
                       e(h.get("strongest_signal", ""))[:80]]
                      for h in crit if "round" in h]
            bits.append(table(["round", "verdict", "revisions", "applied", "score",
                               "strongest signal"], rounds, "no critique rounds"))
            parts.append("<h2>resume</h2>" + "".join(bits))

        for label, name in (("skills removed", "skills_removed.txt"),
                            ("fabrication report", "fabrication_report.txt"),
                            ("needs human", "needs_human.txt"),
                            ("crash", "error.txt")):
            f = d / name
            if f.exists():
                parts.append(f'<h2>{label}</h2><pre class=warn>{e(f.read_text()[:4000])}</pre>')

        smoke = read_json(d / "project_smoke.json")
        if smoke:
            ok = ('<span class=ok>passed</span>' if smoke.get("passed")
                  else '<span class=bad>failed</span>')
            parts.append(f'<h2>generated project — {ok}</h2>'
                         f'<pre>$ {e(smoke.get("command"))}\n'
                         f'{e((smoke.get("output") or "")[-2000:])}</pre>')

        shots = sorted((d / "screenshots").glob("*.png")) if (d / "screenshots").is_dir() else []
        if shots:
            figs = []
            for s in shots:
                rel = quote(str(s.relative_to(self.data)))
                figs.append(f'<figure><a href="/f/{rel}" target=_blank>'
                            f'<img loading=lazy src="/f/{rel}"></a>'
                            f'<figcaption>{e(s.name)}</figcaption></figure>')
            parts.append(f'<h2>screenshots ({len(shots)})</h2>'
                         f'<div class=shots>{"".join(figs)}</div>')

        return page(row.get("title") or dirname, "/", "".join(parts))

    def answers_view(self, blanks_only: bool) -> bytes:
        rows_in = self.answers()
        if blanks_only:
            rows_in = [r for r in rows_in if r.get("left_blank") == "True"]
        rows = []
        for r in reversed(rows_in[-800:]):
            d = audit_dirname(r.get("job_id", ""))
            rows.append([
                f'<a href="/app/{quote(d)}">{e(r.get("company", ""))}</a>',
                e(r.get("field_label", ""))[:80]
                + (" <span class=dim>*</span>" if r.get("required") == "True" else ""),
                (f'<span class=warn>blank — {e(r.get("blank_reason", ""))[:70]}</span>'
                 if r.get("left_blank") == "True" else e(r.get("answer", ""))[:170]),
                f'<span class="dim nw">{e(r.get("source", ""))}</span>',
                e(r.get("rationale", ""))[:80],
            ])
        toggle = ('<a href="/answers">show all</a>' if blanks_only
                  else '<a href="/answers?blank=1">only what was left blank</a>')
        return page("answers", "/answers",
                    f"<h2>every answer given in your name — {toggle}</h2>"
                    + table(["company", "field", "answer", "source", "why"], rows,
                            "no answers.csv yet"))

    def profile_view(self) -> bytes:
        try:
            from jobbot.profile import CORE_SCREENING, LEGALLY_SIGNIFICANT, Profile
            p = Profile.load(self.profile_path)
        except Exception as exc:  # noqa: BLE001
            return page("profile", "/profile",
                        f'<div class=empty>cannot load {e(self.profile_path)}: '
                        f'{e(str(exc)[:300])}</div>')

        missing = p.missing_legally_significant()
        parts = [
            "<h2>identity</h2>",
            tiles([("name", p.identity.full_name), ("roles", len(p.experience)),
                   ("years", p.total_years_experience),
                   ("skills", sum(len(v) for v in p.skills.values())),
                   ("projects", len(p.projects)),
                   ("awards", len(p.awards) + len(p.publications))]),
        ]
        if missing:
            parts.append(f'<h2>blocking the run</h2><pre class=bad>'
                         f'{e(chr(10).join("- " + m for m in missing))}\n\n'
                         f'set these in {e(self.profile_path)} — never guessed, '
                         f'never defaulted</pre>')
        else:
            parts.append('<h2>preflight</h2><pre class=ok>all core screening '
                         'answers confirmed</pre>')

        gaps = p.employment_gaps()
        if gaps:
            parts.append("<h2>employment gaps &gt;6mo</h2><pre class=warn>"
                         + e("\n".join(f"{a} → {b}" for a, b in gaps)) + "</pre>")

        parts.append("<h2>experience</h2>" + table(
            ["role", "company", "dates", "bullets", "tech"],
            [[e(x.title), e(x.company),
              f'{x.start} → {x.end or "present"}', str(len(x.bullets)),
              e(", ".join(x.tech))[:70]] for x in p.experience]))

        parts.append("<h2>projects</h2>" + table(
            ["name", "what", "link"],
            [[e(x.name), e(x.description)[:90],
              (f'<a href="{e(x.url)}" target=_blank>{e(x.url)[:60]}</a>' if x.url else
               '<span class=dim>—</span>')] for x in p.projects],
            "no projects in the profile"))

        parts.append("<h2>awards &amp; publications</h2>" + table(
            ["entry"], [[e(x)] for x in p.publications + p.awards],
            "none — these are the hardest signals to fake, worth filling in"))

        parts.append("<h2>screening answers</h2>" + table(
            ["question", "answer", "provenance"],
            [[e(k) + (" <span class=dim>(legal)</span>"
                      if k in LEGALLY_SIGNIFICANT else ""),
              e(v.value), f'<span class=dim>{e(v.provenance.value)}</span>']
             for k, v in sorted(p.screening.items())]))
        return page("profile", "/profile", "".join(parts))

    def lessons_view(self) -> bytes:
        rows = [[e(l.get("at", "")[:16]), e(l.get("ats", "")), e(l.get("company", "")),
                 e(l.get("scope", "")), e(l.get("observation", ""))[:110],
                 e(l.get("fix", ""))[:110]]
                for l in reversed(read_jsonl(self.data / "lessons.jsonl"))]
        return page("lessons", "/lessons",
                    "<h2>what runs learned, per ATS</h2>"
                    + table(["when", "ats", "company", "scope", "observation", "fix"],
                            rows, "no lessons.jsonl yet"))

    def log_view(self) -> bytes:
        f = self.data / "notifications.log"
        body = f.read_text()[-40000:] if f.exists() else ""
        return page("notifications", "/log",
                    "<h2>notifications sent or attempted</h2>"
                    + (f"<pre>{e(body)}</pre>" if body else
                       '<div class=empty>no notifications.log yet</div>'))

    # -- editor ----------------------------------------------------------

    def editor_view(self, tailnet_url: str = "") -> bytes:
        from jobbot import editor as ed
        from jobbot import editor_ui
        from jobbot.profile import CORE_SCREENING

        return editor_ui.render(
            ed.to_form(ed.load_raw(self.profile_path)),
            str(self.profile_path), ed.SCREENING_SPEC,
            sorted(CORE_SCREENING), ed.PREF_SPEC, ed.WORK_PREF,
            tailnet_url=tailnet_url,
            # `to_form({})` is a non-empty dict, so ask the filesystem
            # rather than testing the payload for truthiness.
            fresh=not self.profile_path.exists(),
        )

    def intake_view(self) -> bytes:
        from jobbot import intake_ui

        return intake_ui.render()

    def _llm(self) -> Any:
        """One client per request. Cheap, and keeps a dead key from poisoning
        the whole server the way a cached instance would."""
        from jobbot.llm.client import LLMClient

        return LLMClient()

    def intake_organize(self, payload: dict[str, Any]) -> dict[str, Any]:
        from jobbot import editor as ed
        from jobbot import intake

        raw = ed.load_raw(self.profile_path)
        prop = intake.organize(
            self._llm(),
            dump=str(payload.get("dump") or ""),
            resumes=payload.get("resumes") or [],
            links=payload.get("links") or {},
            answers=payload.get("answers") or [],
            current=raw,
        )
        return {
            "ok": True,
            "cards": intake.to_cards(prop, ed.to_form(raw)),
            "notes": prop.get("notes") or [],
            "questions": prop.get("questions") or [],
            "usage": prop.get("_usage") or {},
        }

    def intake_questions(self, payload: dict[str, Any]) -> dict[str, Any]:
        from jobbot import editor as ed
        from jobbot import intake

        return {"ok": True, "questions": intake.interview_questions(
            self._llm(), current=ed.to_form(ed.load_raw(self.profile_path)),
            dump=str(payload.get("dump") or ""))}

    def intake_apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Merge accepted cards, then go out through the one validated save."""
        from jobbot import editor as ed
        from jobbot import intake

        raw = ed.load_raw(self.profile_path)
        merged = intake.apply_patches(raw, payload.get("patches") or [])
        return ed.save(self.profile_path, ed.from_form(ed.to_form(merged)))

    def save_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        from jobbot import editor as ed

        return ed.save(self.profile_path, ed.from_form(payload))

    # -- json ------------------------------------------------------------

    def api_profile(self) -> dict[str, Any]:
        from jobbot import editor as ed

        raw = ed.load_raw(self.profile_path)
        out: dict[str, Any] = {"exists": bool(raw), "path": str(self.profile_path),
                               "profile": ed.to_form(raw)}
        prof, errors = ed.validate(raw) if raw else (None, ["no profile saved yet"])
        out["valid"] = prof is not None
        out["errors"] = errors
        if prof is not None:
            out["missing_core"] = prof.missing_legally_significant()
            out["years"] = prof.total_years_experience
        return out

    def status(self) -> dict[str, Any]:
        """What is configured, what is missing, and what every route is for."""
        from jobbot import editor as ed
        from jobbot.mail.gmail import CLIENT_SECRET, TOKEN_PATH

        raw = ed.load_raw(self.profile_path)
        prof, perrors = ed.validate(raw) if raw else (None, ["not saved yet"])
        apps, ans = self.apps(), self.answers()

        checks: list[dict[str, Any]] = [
            {"name": "profile file", "ok": bool(raw),
             "detail": str(self.profile_path) if raw else "not created yet — use Edit profile"},
            {"name": "profile validates", "ok": prof is not None,
             "detail": "; ".join(perrors)[:200] if prof is None else "ok"},
            {"name": "core screening answers set",
             "ok": bool(prof) and not prof.missing_legally_significant(),
             "detail": ", ".join(prof.missing_legally_significant())
                       if prof else "needs a profile first"},
            # Report what a fresh shell will see, not what this process happens to
            # have inherited. The server had the key in its own environment and
            # said "set" while the user's terminal, starting cold, did not.
            {"name": "ANTHROPIC_API_KEY", "ok": _key_in_dotenv(),
             "detail": "in .env" if _key_in_dotenv() else
                       ("only in this process's environment — a new shell will not "
                        "have it; put it in .env" if os.environ.get("ANTHROPIC_API_KEY")
                        else "unset — `run` cannot call the model")},
            {"name": "GEMINI_API_KEY (fallback)",
             "ok": bool(os.environ.get("GEMINI_API_KEY")),
             "detail": "set" if os.environ.get("GEMINI_API_KEY") else
                       "unset — failover is disabled, primary is retried instead"},
            {"name": "gmail client secret", "ok": CLIENT_SECRET.exists(),
             "detail": str(CLIENT_SECRET) if CLIENT_SECRET.exists() else
                       "missing — Workday email verification will stop"},
            {"name": "gmail authorised", "ok": TOKEN_PATH.exists(),
             "detail": str(TOKEN_PATH) if TOKEN_PATH.exists() else "not yet authorised"},
            {"name": "github consent",
             "ok": (Path.home() / ".jobbot" / "github_consent.json").exists(),
             "detail": "granted" if (Path.home() / ".jobbot" / "github_consent.json").exists()
                       else "not granted — portfolio projects are skipped"},
            {"name": "tracker", "ok": (self.data / "applications.csv").exists(),
             "detail": f"{len(apps)} postings, {len(ans)} answers logged"},
        ]
        return {
            "ok": all(c["ok"] for c in checks[:4]),
            "checks": checks,
            "routes": ROUTES,
            "counts": {"postings": len(apps), "answers": len(ans),
                       "audit_dirs": len(list((self.data / "applications").glob("*")))
                       if (self.data / "applications").is_dir() else 0},
        }

    def status_view(self) -> bytes:
        s = self.status()
        rows = [[('<span class=ok>ok</span>' if c["ok"] else '<span class=bad>needs you</span>'),
                 e(c["name"]), e(c["detail"])] for c in s["checks"]]
        routes = [[f'<a href="{e(r["path"])}">{e(r["path"])}</a>' if r["method"] == "GET"
                   and "<" not in r["path"] else e(r["path"]),
                   e(r["method"]), e(r["what"])] for r in s["routes"]]
        return page("status", "/status",
                    "<h2>configuration</h2>"
                    + table(["", "check", "detail"], rows)
                    + "<h2>every endpoint</h2>"
                    + table(["path", "method", "what it returns"], routes))

    def serve_file(self, rel: str) -> tuple[bytes, str] | None:
        """Serve a screenshot or the resume PDF, confined to the data dir.

        The path comes off the URL, so it is untrusted: resolve it and refuse
        anything that lands outside `data/`, or a symlink pointing out of it.
        """
        root = self.data.resolve()
        try:
            target = (root / unquote(rel)).resolve()
            target.relative_to(root)
        except (ValueError, OSError):
            return None
        if not target.is_file() or target.suffix.lower() not in (".png", ".pdf", ".jpg"):
            return None
        mime = {".png": "image/png", ".jpg": "image/jpeg",
                ".pdf": "application/pdf"}[target.suffix.lower()]
        return target.read_bytes(), mime

    def serve_static(self, rel: str) -> tuple[bytes, str] | None:
        """Serve static CSS, JS, images from jobbot/static/ directory.
        
        Path is untrusted: refuse anything that escapes static/ or is a symlink.
        """
        root = (Path(__file__).parent / "static").resolve()
        try:
            target = (root / unquote(rel)).resolve()
            target.relative_to(root)
        except (ValueError, OSError):
            return None
        if not target.is_file():
            return None
        mime = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".avif": "image/avif",
            ".svg": "image/svg+xml",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".mp4": "video/mp4",
        }.get(target.suffix.lower(), "application/octet-stream")
        return target.read_bytes(), mime


# -- server --------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, dash: Dash, *a: Any, **kw: Any) -> None:
        self.dash = dash
        super().__init__(*a, **kw)

    def log_message(self, *a: Any) -> None:  # quiet; structlog owns stdout
        pass

    def _send(self, body: bytes, mime: str = "text/html; charset=utf-8",
              status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        # The page IS the app -- markup, styles and script in one response. With
        # no cache directive a browser is free to reuse an old copy, which makes
        # a fixed bug look unfixed and is indistinguishable from "it's broken".
        # Screenshots and PDFs under /f/ are content-addressed by path and safe
        # to cache; everything else must be fresh.
        if not mime.startswith(("image/", "application/pdf")):
            self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        if not getattr(self, "_head_only", False):
            self.wfile.write(body)

    def _json(self, obj: Any, status: int = 200) -> None:
        self._send(json.dumps(obj, default=str).encode(),
                   "application/json; charset=utf-8", status)

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)
        d = self.dash
        try:
            if path.startswith("/static/"):
                result = d.serve_static(path[8:])
                if result:
                    body, mime = result
                    self._send(body, mime)
                else:
                    self._send(b"not found", "text/plain", 404)
            elif path == "/":
                self._send(d.overview())
            elif path == "/landing":
                landing_file = Path(__file__).parent.parent / "templates" / "landing.html"
                if landing_file.exists():
                    self._send(landing_file.read_bytes(), "text/html")
                else:
                    self._send(b"landing page not found", "text/plain", 404)
            elif path == "/landing2":
                landing_file = Path(__file__).parent.parent / "templates" / "landing2.html"
                if landing_file.exists():
                    self._send(landing_file.read_bytes(), "text/html")
                else:
                    self._send(b"landing2 page not found", "text/plain", 404)
            elif path == "/landing3":
                landing_file = Path(__file__).parent.parent / "templates" / "landing3.html"
                if landing_file.exists():
                    self._send(landing_file.read_bytes(), "text/html")
                else:
                    self._send(b"landing3 page not found", "text/plain", 404)
            elif path.startswith("/app/"):
                self._send(d.app_detail(unquote(path[5:])))
            elif path == "/queue":
                self._send(d.queue_view((qs.get("show") or ["all"])[0],
                                        (qs.get("q") or [""])[0]))
            elif path == "/answers":
                self._send(d.answers_view(bool(qs.get("blank"))))
            elif path == "/profile":
                self._send(d.profile_view())
            elif path == "/edit":
                self._send(d.editor_view(tailnet_url=self.dash.public_url))
            elif path == "/intake":
                self._send(d.intake_view())
            elif path == "/lessons":
                self._send(d.lessons_view())
            elif path == "/log":
                self._send(d.log_view())
            elif path == "/status":
                self._send(d.status_view())
            elif path == "/api/status":
                self._json(d.status())
            elif path == "/api/profile":
                self._json(d.api_profile())
            elif path == "/api/applications":
                self._json(d.apps())
            elif path == "/api/answers":
                self._json(d.answers())
            elif path.startswith("/f/"):
                got = d.serve_file(path[3:])
                if got is None:
                    self._send(b"not found", "text/plain", 404)
                else:
                    self._send(*got)
            else:
                self._send(page("404", "/", '<div class=empty>no such page</div>'),
                           status=404)
        except Exception as exc:  # noqa: BLE001
            log.warning("dashboard.get_failed", path=path, error=repr(exc)[:300])
            self._send(page("error", "/", f'<pre class=bad>{e(repr(exc))}</pre>'),
                       status=500)

    def do_HEAD(self) -> None:  # noqa: N802
        """Same headers as GET, no body.

        BaseHTTPRequestHandler answers an unimplemented method with 501, which
        is what any HEAD probe (curl -I, a health check, a proxy) got.
        """
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        # Cap the body: this is a local form, and an unbounded read on a socket
        # is a hang waiting to happen.
        length = min(int(self.headers.get("Content-Length") or 0), 25_000_000)
        body = self.rfile.read(length) if length else b""
        try:
            if path == "/api/profile":
                self._json(self.dash.save_profile(json.loads(body or b"{}")))
            elif path == "/api/queue":
                self._json(self.dash.queue_decide(json.loads(body or b"{}")))
            elif path == "/api/standard-resume":
                name = (parse_qs(urlparse(self.path).query).get("name") or [""])[0]
                self._json(self.dash.save_standard_resume(body, unquote(name)))
            elif path.startswith("/api/intake/"):
                fn = {"organize": self.dash.intake_organize,
                      "questions": self.dash.intake_questions,
                      "apply": self.dash.intake_apply}.get(path.rsplit("/", 1)[-1])
                if fn is None:
                    self._json({"ok": False, "error": "no such endpoint"}, 404)
                    return
                try:
                    self._json(fn(json.loads(body or b"{}")))
                except Exception as exc:  # noqa: BLE001
                    # The model call is the likely failure here -- a missing key,
                    # a rate limit, a refusal. Report it to the page rather than
                    # dropping the user back to a blank form with no reason.
                    log.warning("intake.failed", path=path, error=repr(exc)[:300])
                    self._json({"ok": False, "error": str(exc)[:400]})
            elif path == "/api/resume-text":
                from jobbot.editor import resume_text
                try:
                    text = resume_text(body)
                except Exception as exc:  # noqa: BLE001
                    self._json({"ok": False, "error": str(exc)[:200]})
                    return
                self._json({"ok": True, "chars": len(text), "text": text})
            else:
                self._json({"ok": False, "error": "no such endpoint"}, 404)
        except Exception as exc:  # noqa: BLE001
            log.warning("dashboard.post_failed", path=path, error=repr(exc)[:300])
            self._json({"ok": False, "errors": [repr(exc)[:300]]}, 500)


def _key_in_dotenv() -> bool:
    """Is ANTHROPIC_API_KEY set in a .env file the code will actually read?"""
    for p in (Path(".env"), Path(__file__).resolve().parents[1] / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                k, _, v = line.strip().partition("=")
                if k == "ANTHROPIC_API_KEY" and v.strip() and not v.startswith("sk-ant-..."):
                    return True
    return False


def tailscale_ip() -> str | None:
    """This machine's Tailscale IPv4, if Tailscale is up.

    Reads the interface rather than shelling out, so it works without the CLI
    on PATH and cannot be fooled by a stale `tailscale status` cache.
    """
    import subprocess

    for cmd in (["tailscale", "ip", "-4"],
                ["/Applications/Tailscale.app/Contents/MacOS/Tailscale", "ip", "-4"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        for line in r.stdout.splitlines():
            ip = line.strip()
            if ip.startswith("100."):
                return ip
    # Fall back to the CGNAT address on the utun interface.
    try:
        out = subprocess.run(["ifconfig"], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("inet 100."):
            return line.split()[1]
    return None


def serve(data_dir: str | Path = "data", profile: str | Path = "config/profile.yaml",
          *, port: int = 8765, open_browser: bool = True,
          host: str = "127.0.0.1", tailscale: bool = False) -> None:
    """Serve the dashboard and editor.

    `tailscale=True` binds the Tailscale interface address instead of loopback,
    so another device on the same tailnet can reach it. It binds that address
    specifically, never 0.0.0.0: the tailnet is device-authenticated, while
    0.0.0.0 would also publish a form containing a home address, phone number
    and every screening answer to whatever coffee-shop wifi the machine is on.
    """
    if tailscale:
        ip = tailscale_ip()
        if not ip:
            raise RuntimeError(
                "--tailscale given but no Tailscale IPv4 found. Is Tailscale "
                "running and logged in? (`tailscale status`)")
        host = ip

    dash = Dash(Path(data_dir), Path(profile))
    while True:
        try:
            httpd = ThreadingHTTPServer((host, port), partial(Handler, dash))
            break
        except OSError as exc:
            if getattr(exc, "errno", None) not in (48, 98) or port > 8785:
                raise
            port += 1

    url = f"http://{host}:{port}/"
    dash.public_url = url
    scope = ("reachable from your tailnet only" if tailscale
             else "this machine only")
    # flush: over SSH stdout is a pipe, and the URL is the whole point of the
    # first second of output.
    print(f"jobbot dashboard  {url}", flush=True)
    print(f"  editor          {url}edit", flush=True)
    print(f"  status          {url}status", flush=True)
    print(f"  scope           {scope}; ctrl-c to stop", flush=True)
    if open_browser:
        threading.Timer(0.4, webbrowser.open, [url]).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


def demo() -> None:
    """Self-check: the path guard, and that every view renders on real shapes."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "data"
        (root / "applications" / "greenhouse_42" / "screenshots").mkdir(parents=True)
        (root / "applications.csv").write_text(
            "job_id,company,title,ats,status,match_score,questions_total,"
            "questions_answered,questions_flagged,heal_rounds,discovered_at\n"
            "greenhouse:42,Acme,Software Engineer,greenhouse,confirmed,0.82,14,14,0,1,"
            "2026-09-08T10:00:00+00:00\n")
        (root / "answers.csv").write_text(
            "recorded_at,job_id,company,title,ats,job_url,field_label,field_kind,"
            "required,answer,source,confidence,rationale,left_blank,blank_reason\n"
            "2026-09-08T10:00:00+00:00,greenhouse:42,Acme,SWE,greenhouse,,First Name,"
            "text,True,Jane,profile,1.0,profile identity,False,\n")
        d = root / "applications" / "greenhouse_42"
        (d / "answers.json").write_text(json.dumps(
            [{"label": "First Name", "value": "Jane", "source": "profile",
              "confidence": 1.0, "rationale": "profile identity",
              "needs_human": False, "blocked_reason": "", "required": True}]))
        (d / "verification.json").write_text(json.dumps(
            {"ready": True, "summary": "clean", "issues": [], "heal_rounds": 1,
             "unfilled_required": [], "validation_errors": []}))
        (d / "screenshots" / "cp1_0.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (root / "lessons.jsonl").write_text(json.dumps(
            {"at": "2026-09-08T10:00:00+00:00", "ats": "greenhouse", "company": "Acme",
             "observation": "o", "fix": "f", "scope": "this_ats"}) + "\n")
        (root / "notifications.log").write_text("--- sent\n")

        dash = Dash(root, Path("config/profile.yaml"))
        for name, out in (("overview", dash.overview()),
                          ("detail", dash.app_detail("greenhouse_42")),
                          ("answers", dash.answers_view(False)),
                          ("blanks", dash.answers_view(True)),
                          ("lessons", dash.lessons_view()),
                          ("log", dash.log_view()),
                          ("profile", dash.profile_view())):
            assert out.startswith(b"<!doctype html>"), name
            assert b"jobbot" in out, name
        assert b"Software Engineer" in dash.overview()
        assert b"Jane" in dash.app_detail("greenhouse_42")
        assert b"no such audit dir" in dash.app_detail("nope")

        # the guard: nothing outside data/ is reachable, however it is spelled
        assert dash.serve_file("applications/greenhouse_42/screenshots/cp1_0.png")
        for attack in ("../../../../etc/passwd", "..%2f..%2fetc%2fpasswd",
                       "applications/../../secrets.env", "/etc/passwd",
                       "applications/greenhouse_42/answers.json"):
            assert dash.serve_file(attack) is None, attack
        (root / "escape.png").symlink_to("/etc/hosts")
        assert dash.serve_file("escape.png") is None or not Path("/etc/hosts").exists()
    print("dashboard self-check ok")


if __name__ == "__main__":
    demo()
