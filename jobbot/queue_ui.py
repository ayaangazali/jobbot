"""The queue page: tick the jobs to apply to, blacklist the ones you're doing yourself.

Nothing here decides anything. It renders what is in queue.json and posts back
changes; the run loop reads the same file. A job with no tick is never applied
to, which makes an empty queue safe rather than surprising.
"""

from __future__ import annotations

from html import escape as e
from typing import Any

CSS = """
.qbar{position:sticky;top:41px;z-index:4;background:var(--bg);
border-bottom:1px solid var(--line);padding:9px 0 11px;margin-bottom:10px;
display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.qbar button{background:var(--panel);color:var(--fg);border:1px solid var(--line);
border-radius:6px;padding:5px 11px;font:inherit;cursor:pointer;
transition:transform .16s cubic-bezier(.23,1,.32,1),background .16s ease-out}
.qbar button:hover:not(:disabled){background:#1c2029;transform:translateY(-1px)}
.qbar button:active:not(:disabled){transform:translateY(0)}
.qbar button:disabled{opacity:.4;cursor:default}
.qbar button.go{border-color:#2c4a35;color:var(--ok)}
.qbar button.no{border-color:#4a2b2b;color:var(--bad)}
.qbar .sep{width:1px;height:20px;background:var(--line);margin:0 4px}
.qbar .count{color:var(--dim);margin-left:auto}
.filters a{color:var(--dim);margin-right:12px}
.search{display:inline-flex;gap:6px;align-items:center;margin-top:4px}
.search input{background:var(--panel);border:1px solid var(--line);border-radius:6px;
color:var(--fg);font:inherit;padding:5px 9px;width:280px}
.search input:focus{outline:none;border-color:var(--acc)}
.search button{background:var(--panel);color:var(--fg);border:1px solid var(--line);
border-radius:6px;padding:5px 11px;font:inherit;cursor:pointer}
.filters a.on{color:var(--fg);text-decoration:underline}
td.tick{width:30px;text-align:center}
input[type=checkbox]{width:15px;height:15px;accent-color:var(--acc);cursor:pointer}
tr.row-approved td{background:#131e17}
tr.row-blacklist td{opacity:.45}
tr.row-applied td{background:#151922}
.d-approved{color:var(--ok);border-color:#2c4a35}
.d-blacklist{color:var(--bad);border-color:#4a2b2b}
.d-applied{color:var(--acc);border-color:#26405e}
.d-pending{color:var(--dim)}
.saved{color:var(--ok);opacity:0;transition:opacity .2s ease-out}
.saved.on{opacity:1}
.drop{border:1px dashed var(--line);border-radius:6px;padding:14px;
background:var(--panel);margin-bottom:16px}
.drop.have{border-color:#2c4a35}
.drop input[type=file]{display:none}
.drop label{color:var(--acc);cursor:pointer;text-decoration:underline}
@media (prefers-reduced-motion:reduce){.qbar button,.saved{transition:none}}
"""


def _resume_box(standard: dict[str, Any]) -> str:
    if standard.get("exists"):
        body = (f'<b class=ok>standard resume set</b> &mdash; '
                f'<a href="/f/standard_resume.pdf" target=_blank>{e(standard["name"])}</a> '
                f'<span class=dim>({standard["kb"]} KB, uploaded {e(standard["mtime"])})</span>'
                f'<div class=dim style="margin-top:6px">Every application sends this '
                f'file unchanged. No resume is generated.</div>')
        cls = "drop have"
    else:
        body = ('<b class=warn>no standard resume yet</b>'
                '<div class=dim style="margin-top:6px">Until one is uploaded, each '
                'application generates its own resume.</div>')
        cls = "drop"
    return (f'<div class="{cls}" id=resumebox>{body}'
            f'<div style="margin-top:9px">'
            f'<input type=file id=pdf accept="application/pdf">'
            f'<label for=pdf>choose a PDF</label> '
            f'<span id=upmsg class=dim></span></div></div>')


def render(entries: list[Any], counts: dict[str, int], standard: dict[str, Any],
           *, show: str = "all", q: str = "", limit: int = 300) -> str:
    # A discovery sweep across thirty boards returns six thousand postings.
    # Rendering all of them is a 4MB page nobody can scroll, so the list is
    # searched and capped -- the tick is meant to be deliberate, not a scroll.
    needle = q.strip().lower()
    matched = [x for x in entries
               if (show == "all" or x.decision == show)
               and (not needle or needle in f"{x.company} {x.title} {x.location}".lower())]
    total_matched = len(matched)
    rows = []
    for x in matched[:limit]:
        fit = f"{x.fit:.2f}" if x.fit else ""
        rows.append(
            f'<tr class="row-{e(x.decision)}" data-id="{e(x.job_id)}">'
            f'<td class=tick><input type=checkbox class=pick '
            f'{"checked" if x.decision == "approved" else ""}></td>'
            f'<td>{e(x.company)}</td>'
            f'<td><a href="{e(x.url)}" target=_blank rel=noopener>{e(x.title[:90])}</a></td>'
            f'<td class=dim>{e(x.location[:34])}</td>'
            f'<td class=dim>{fit}</td>'
            f'<td><span class="pill d-{e(x.decision)}" data-d>{e(x.decision)}</span></td>'
            f'</tr>')

    table = ("".join(rows) and
             f'<table><thead><tr><th></th><th>company</th><th>title</th>'
             f'<th>location</th><th>fit</th><th>decision</th></tr></thead>'
             f'<tbody id=rows>{"".join(rows)}</tbody></table>'
             ) or '<div class=empty>nothing here yet &mdash; run a discovery</div>'

    search = (f'<form class=search method=get>'
              f'<input type=hidden name=show value="{e(show)}">'
              f'<input name=q value="{e(q)}" placeholder="search company or title" '
              f'autocomplete=off>'
              f'<button>search</button>'
              + (f' <a href="?show={e(show)}" class=dim>clear</a>' if needle else '')
              + f'</form>')
    shown = (f'<div class=dim style="margin:6px 0 10px">showing {len(rows)} of '
             f'{total_matched} match(es)'
             + (f' &mdash; narrow the search to see the rest' if total_matched > limit else '')
             + '</div>')

    filters = " ".join(
        f'<a href="?show={k}" class="{"on" if show == k else ""}">{k}'
        f'{f" ({counts.get(k, 0)})" if k != "all" else f" ({sum(counts.values())})"}</a>'
        for k in ("all", "pending", "approved", "blacklist", "applied"))

    return (
        f"<style>{CSS}</style>"
        + _resume_box(standard)
        + f'<div class=filters style="margin-bottom:8px">{filters}</div>'
        + search + shown
        + '<div class=qbar>'
          '<button id=all>select all</button>'
          '<button id=none>clear</button>'
          '<span class=sep></span>'
          '<button class=go id=approve>apply to selected</button>'
          '<button class=no id=blacklist>I\'ll do these myself</button>'
          '<button id=reset>un-decide</button>'
          '<span class=saved id=saved>saved</span>'
          '<span class=count id=count></span>'
          '</div>'
        + table
        + SCRIPT
    )


SCRIPT = """
<script>
const $ = s => document.querySelector(s);
const rows = () => [...document.querySelectorAll('#rows tr')];
const picked = () => rows().filter(r => r.querySelector('.pick').checked);

function refresh() {
  $('#count').textContent = picked().length + ' selected of ' + rows().length;
  for (const b of ['#approve', '#blacklist', '#reset'])
    $(b).disabled = picked().length === 0;
}

async function decide(decision) {
  const ids = picked().map(r => r.dataset.id);
  if (!ids.length) return;
  const body = {};
  ids.forEach(i => body[i] = decision);
  const r = await fetch('/api/queue', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({decisions: body})
  });
  const j = await r.json();
  if (!j.ok) { alert(j.error || 'could not save'); return; }
  for (const row of picked()) {
    row.className = 'row-' + decision;
    const pill = row.querySelector('[data-d]');
    pill.textContent = decision;
    pill.className = 'pill d-' + decision;
    row.querySelector('.pick').checked = decision === 'approved';
  }
  $('#saved').classList.add('on');
  setTimeout(() => $('#saved').classList.remove('on'), 1400);
  refresh();
}

$('#all').onclick = () => { rows().forEach(r => r.querySelector('.pick').checked = true); refresh(); };
$('#none').onclick = () => { rows().forEach(r => r.querySelector('.pick').checked = false); refresh(); };
$('#approve').onclick = () => decide('approved');
$('#blacklist').onclick = () => decide('blacklist');
$('#reset').onclick = () => decide('pending');
document.addEventListener('change', ev => { if (ev.target?.classList?.contains('pick')) refresh(); });

$('#pdf').onchange = async ev => {
  const f = ev.target.files[0];
  if (!f) return;
  $('#upmsg').textContent = 'uploading ' + f.name + '...';
  const r = await fetch('/api/standard-resume?name=' + encodeURIComponent(f.name), {
    method: 'POST', headers: {'Content-Type': 'application/pdf'}, body: f
  });
  const j = await r.json();
  $('#upmsg').textContent = j.ok ? 'saved -- reloading' : (j.error || 'upload failed');
  if (j.ok) setTimeout(() => location.reload(), 600);
};

refresh();
</script>
"""
