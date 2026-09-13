"""The intake wizard: dump everything in, review what the model made of it.

Motion notes, since it is deliberate rather than decorative:

  This is a rare, first-time flow -- you fill your profile once -- which is the
  only tier where a delight budget is justified. Every animation here still
  names a purpose:

    step change      spatial consistency (where you came from, where you went)
    processing       state indication (the model is working; don't touch it)
    card reveal      preventing a jarring change (twenty cards teleporting in)
    accept / skip    feedback (the click registered)
    mic ring         state indication -- and a privacy signal: it must be
                     obvious the microphone is live

  transform and opacity only, so nothing triggers layout. Transitions for
  anything clickable twice in a second (accept, skip, step nav) because they
  retarget from the current value; CSS animations only for the processing state
  and the reveal, which are predetermined and better off the main thread while
  the page is parsing a large JSON response.
"""

from __future__ import annotations

import json
from typing import Any

CSS = """
/* legibility: never put text directly on a scene (docs/design/README rule 2) */
.step h1, .step h2, .step > p:first-of-type, .step .sub, .step .lede {
  position: relative;
  display: inline-block;
  background: rgba(255,255,255,0.92);
  border: 2px solid #000;
  padding: 12px 16px;
  border-radius: 4px;
  box-shadow: 4px 4px 0 #000;
}

:root{
  --ease-out:cubic-bezier(0.23,1,0.32,1);
}
*{box-sizing:border-box}
body.collage{margin:0;overflow-x:hidden}
a{color:inherit}

/* ---- header ---- */
.site-header{
  position:sticky;top:0;z-index:40;display:flex;align-items:center;gap:16px;
  padding:10px clamp(14px,4vw,32px);background:var(--paper);
  border-bottom:3px solid var(--ink);
}
.site-header .logo-dot{flex:none;width:52px;height:52px;font-size:20px}
.site-header nav{display:flex;flex-wrap:wrap;gap:2px;margin-left:auto}
.site-header nav .nav-link{
  font-family:var(--f-body);font-size:13px;color:var(--ink);text-decoration:none;
  padding:10px 12px;border-radius:4px;min-height:44px;display:inline-flex;align-items:center;
}
.site-header nav .nav-link:hover{background:rgba(0,0,0,.07)}
.site-header nav .nav-link.on{background:var(--violet);color:#fff}

/* ---- step rail: four numbered stops on cream strokes ---- */
.rail-wrap{max-width:720px;margin:0 auto;padding:20px clamp(14px,4vw,32px) 4px}
.rail{display:flex;align-items:center;justify-content:center}
.rail i{
  font-style:normal;position:relative;flex:none;display:flex;align-items:center;justify-content:center;
  width:52px;height:52px;border-radius:50%;
  background:url(/static/landing2/img/asset-2409278a72.gif) center/cover no-repeat;
  transform:rotate(-3deg);transition:transform 200ms var(--ease-out),background-color 200ms var(--ease-out);
}
.rail i b{font-family:var(--f-label);font-weight:700;font-size:16px;color:var(--ink)}
.rail i .lbl{
  position:absolute;top:100%;margin-top:6px;font-family:var(--f-body);
  font-size:10px;color:#1a1a1a;white-space:nowrap;
}
.rail i.now{background:var(--violet);transform:rotate(-4deg) scale(1.15)}
.rail i.now b{color:#fff}
.rail i.done::after{
  content:'';position:absolute;inset:-14px;
  background:url(/static/landing2/img/asset-36cc96ea5e.gif) center/contain no-repeat;
}
.rail em.link{
  font-style:normal;width:30px;height:18px;flex:none;margin:0 -3px;
  background:url(/static/landing2/img/asset-191a616ef1.gif) center/contain no-repeat;
  transform:rotate(90deg);
}
@media (max-width:600px){
  .rail i{width:40px;height:40px}
  .rail i b{font-size:13px}
  .rail i .lbl{display:none}
  .rail em.link{width:16px}
}

/* ---- step scaffolding: decor layer (absolute, --rpx) + content layer (flow, px) ---- */
.stepwrap{position:relative}
.step{display:none;max-width:720px;margin:0 auto;padding:28px clamp(14px,4vw,32px) 140px}
.step.live{display:block}
.step.live>*{animation:rise 260ms var(--ease-out) both}
@keyframes rise{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:none}}
.stepwrap[data-step="review"] .step{max-width:960px}

.decor{display:none}
.decor.live{display:block}

.decor[data-step="sources"] .scene{
  width:100%;height:calc(260*var(--rpx));object-fit:cover;
}
.decor[data-step="sources"] .fade{
  top:calc(180*var(--rpx));left:0;right:0;height:calc(140*var(--rpx));
  background:linear-gradient(180deg,transparent,var(--paper) 85%);
}
.decor[data-step="sources"] .corner-x{
  top:calc(210*var(--rpx));right:6%;width:calc(70*var(--rpx));height:calc(68*var(--rpx));
  background:url(/static/landing2/img/asset-36cc96ea5e.gif) center/contain no-repeat;
  transform:rotate(12deg);
}
.decor[data-step="interview"] .scene{inset:0;width:100%;height:100%;object-fit:cover;opacity:.85}
.decor[data-step="interview"] .wash{inset:0;background:rgba(224,224,255,.55)}
.decor[data-step="review"] .squiggle,
.decor[data-step="working"] .squiggle{
  top:calc(8*var(--rpx));left:calc(-10*var(--rpx));width:calc(40*var(--rpx));height:calc(96*var(--rpx));
  background:url(/static/landing2/img/asset-191a616ef1.gif) center/contain no-repeat;
  transform:rotate(18deg);
}

/* ---- headings & sub copy ---- */
h1{position:relative;display:inline-block;font-size:26px;margin:10px 0 6px;padding:10px 22px}
h1::before{
  content:'';position:absolute;inset:-8px -14px;z-index:-1;
  background:url(/static/landing2/img/asset-2409278a72.gif) center/100% 100% no-repeat;
  transform:rotate(-2.5deg);
}
.sub{font-family:var(--f-body);font-size:15px;line-height:1.5;margin:0 0 22px;max-width:64ch}

.card{background:var(--plate-light);border:2px solid var(--ink);box-shadow:var(--lift-black);
  border-radius:6px;padding:18px 20px;margin-bottom:18px}
.card>h3{margin:0 0 4px;font-family:var(--f-label);font-weight:700;font-size:15px}
.card>p.hint{margin:0 0 15px;color:#333;font-size:13px;max-width:70ch;font-family:var(--f-body)}

label span.l{display:block;color:#333;font-size:11px;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:5px;font-family:var(--f-label);font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}

/* ---- buttons: `.btn/.btn-primary/.btn-secondary` come from collage.css (min 48px,
   hard shadow, no rotation). Smaller inline controls (remove/accept/skip/tiny) stay
   plain <button> and get their own compact-but-still-48px-tall treatment here. ---- */
button{
  min-height:48px;padding:0 14px;font-family:var(--f-label);font-weight:700;font-size:13px;
  border:2px solid var(--ink);border-radius:4px;background:#fff;color:var(--ink);
  cursor:pointer;transform:none;
}
button:disabled{opacity:.4;cursor:not-allowed}
button:focus-visible{outline:3px solid var(--magenta);outline-offset:2px}
button:active:not(:disabled){transform:translate(2px,2px)}
button.ghost{background:transparent}
button.tiny{font-size:12px;padding:0 12px}
button.mic{border-radius:24px}

/* ---- dictation ---- */
.dictate{position:relative}
.dictate textarea{min-height:190px;resize:vertical}
.microw{display:flex;gap:12px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
.mic{display:inline-flex;gap:8px;align-items:center;position:relative}
.mic.live{background:#ffe3fe;border-color:var(--magenta);color:#7a0f74}
.mic.live::after{content:'';position:absolute;inset:-5px;border-radius:10px;
  border:2px solid var(--magenta);animation:ring 1400ms linear infinite;pointer-events:none}
@keyframes ring{0%{opacity:.9;transform:scale(.98)}100%{opacity:0;transform:scale(1.14)}}
.count{position:absolute;bottom:10px;right:10px;color:#444;font-size:11px;
  background:#fff;padding:2px 6px;border-radius:4px;pointer-events:none}

/* ---- dropzone: the money moment on step 1 ---- */
.drop{
  background:var(--plate-light);border:3px dashed var(--violet);border-radius:10px;
  padding:36px 20px;text-align:center;cursor:pointer;position:relative;min-height:170px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
  box-shadow:var(--lift-black);transform:rotate(var(--tilt-c));
  transition:transform 220ms var(--ease-out),border-color 220ms var(--ease-out),background 220ms var(--ease-out);
}
.drop::before{
  content:'';width:44px;height:54px;margin-bottom:4px;border:2px solid var(--ink);border-radius:2px;
  background:
    linear-gradient(#fff,#fff) padding-box,
    linear-gradient(135deg,transparent 12px,var(--ink) 12.5px) border-box;
}
.drop-main{font-family:var(--f-label);font-weight:700;font-size:16px}
.drop-sub{font-family:var(--f-body);font-size:13px;color:#3a3a3a}
.drop.over{
  background:rgba(91,76,219,.08);border-color:var(--magenta);border-style:solid;
  transform:rotate(0deg) scale(1.01);
}
.files{display:flex;flex-direction:column;gap:14px;margin-top:16px;align-items:stretch}
.files>button{align-self:flex-start}
.file{
  display:flex;gap:10px;align-items:center;flex-wrap:wrap;
  background:var(--plate-dark);color:#fff;border-radius:6px;padding:12px 14px;
  box-shadow:var(--lift-magenta);animation:rise 220ms var(--ease-out) both;
}
.file:nth-child(odd){transform:rotate(var(--tilt-a))}
.file:nth-child(even){transform:rotate(var(--tilt-b))}
.file .nm{font-family:var(--f-label);font-weight:700;font-size:13px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;max-width:190px}
.file .ok{color:#8be3a6;font-size:12px;font-family:var(--f-body);white-space:nowrap}
.file .bad{color:#ff9f9d;font-size:12px;font-family:var(--f-body)}
.file input{flex:1;min-width:140px}

/* ---- step 2: painted progress ---- */
.working{padding:40px 0;text-align:center;display:flex;flex-direction:column;align-items:center;gap:6px}
.barrow{display:flex;align-items:center;gap:16px;width:100%;max-width:420px;margin:0 auto 20px}
.scan{
  flex:1;height:22px;position:relative;overflow:hidden;border:2px solid var(--ink);
  background:url(/static/landing2/img/asset-2409278a72.gif) center/cover no-repeat;
}
.scan .fill{position:absolute;top:0;left:0;bottom:0;width:0%;background:var(--violet);
  transition:width 300ms var(--ease-out)}
.spin-sticker{width:52px;height:56px;object-fit:contain;flex:none}
.working .what{font-family:var(--f-display);font-weight:700;font-size:19px;margin-bottom:4px}
.working .who{display:flex;flex-direction:column;align-items:center;gap:8px;width:100%;max-width:420px}
.tick{
  background:var(--plate-light);border:2px solid var(--ink);border-radius:6px;
  padding:8px 14px 8px 34px;font-size:13px;font-family:var(--f-body);position:relative;
  animation:rise 220ms var(--ease-out) both;box-shadow:3px 3px 0 var(--ink);
}
.tick::before{
  content:'';position:absolute;left:8px;top:50%;transform:translateY(-50%);
  width:16px;height:16px;background:url(/static/landing2/img/asset-36cc96ea5e.gif) center/contain no-repeat;
}
.elapsed{color:#555;font-size:12px;margin-top:14px;font-variant-numeric:tabular-nums;font-family:var(--f-body)}

/* ---- step 3: review cards ---- */
.group{margin-bottom:8px}
.group>h2{
  grid-column:1/-1;display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  font-family:var(--f-label);font-weight:700;font-size:13px;text-transform:uppercase;
  letter-spacing:.05em;margin:0 0 12px;padding:8px 14px;width:fit-content;
  background:url(/static/landing2/img/asset-513fbcc041.gif) center/100% 100% no-repeat;
}
.group>h2 .n{color:#333;font-weight:400;text-transform:none}
.bulk{
  display:flex;gap:10px;align-items:center;background:var(--plate-light);
  border:2px solid var(--ink);border-radius:8px;padding:12px 16px;margin-bottom:20px;flex-wrap:wrap;
}
.bulk .t{color:#333;font-size:13px;flex:1;min-width:180px;font-family:var(--f-body)}
.saved{background:var(--plate-light);border:2px solid var(--ink);border-radius:8px;
  padding:16px 18px;margin-bottom:20px;font-size:13px;box-shadow:var(--lift-violet)}
.saved .left{margin-top:10px;color:#333}
.failed{background:#ffe2e0;border:2px solid var(--ink);border-radius:8px;
  padding:16px 18px;margin-bottom:20px;color:#7a1210;font-size:13px}
.failed ul{margin:8px 0 0;padding-left:20px}
@media (min-width:900px){
  .stepwrap[data-step="review"] .group{display:grid;grid-template-columns:1fr 1fr;gap:14px 16px}
}
.prop{
  background:#fff;border:2px solid var(--ink);border-radius:6px;box-shadow:var(--lift-black);
  padding:14px 16px;margin-bottom:14px;animation:rise 220ms var(--ease-out) both;
  animation-delay:calc(var(--i)*40ms);align-self:start;
  transition:opacity 160ms var(--ease-out),transform 160ms var(--ease-out),background 160ms var(--ease-out);
}
.prop:nth-child(odd){transform:rotate(var(--tilt-b))}
.prop:nth-child(even){transform:rotate(var(--tilt-a))}
.prop.yes{background:#eafbee}
.prop.no{opacity:.4}
.prop .top{display:flex;gap:12px;align-items:baseline;margin-bottom:8px;flex-wrap:wrap}
.prop .t{font-family:var(--f-label);font-weight:700;flex:1;font-size:14px}
.prop .src{color:#555;font-size:11px;white-space:nowrap;font-family:var(--f-body)}
.prop .val{color:#222;font-size:13px;white-space:pre-wrap;font-family:var(--f-body)}
.prop .val ul{margin:6px 0 0;padding-left:18px}
.prop .val .k{color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  margin-right:8px;font-family:var(--f-label);font-weight:700}
.prop .val li{margin-bottom:3px}
.prop .was{color:#555;font-size:12px;margin-top:8px;padding-top:8px;border-top:1px solid #ccc;
  font-family:var(--f-body)}
.prop .acts{display:flex;gap:8px;margin-top:12px}
.prop .acts button.on{background:var(--violet);color:#fff}

.note{background:#fff4d6;border:2px solid var(--ink);border-radius:6px;padding:12px 16px;
  margin-bottom:10px;font-size:13px;animation:rise 220ms var(--ease-out) both;
  animation-delay:calc(var(--i)*40ms)}
.note.info{background:var(--plate-light)}
.note .k{color:#8a6d00;font-size:10px;text-transform:uppercase;letter-spacing:.06em;
  margin-right:8px;font-family:var(--f-label);font-weight:700}
.note.info .k{color:#555}

/* ---- step 4: interview ---- */
.q{
  background:#fff;border:2px solid var(--ink);border-radius:6px;box-shadow:var(--lift-black);
  padding:16px 18px;margin-bottom:16px;position:relative;animation:rise 240ms var(--ease-out) both;
  animation-delay:calc(var(--i)*50ms);
}
.q:nth-child(odd){transform:rotate(var(--tilt-c))}
.q:nth-child(even){transform:rotate(var(--tilt-b))}
.q .qt{font-family:var(--f-label);font-weight:700;font-size:15px;margin-bottom:5px}
.q .why{color:#444;font-size:12px;margin-bottom:10px;font-family:var(--f-body)}
.q textarea{min-height:76px;resize:vertical}
.q.answered{border-color:var(--violet)}
.q.answered::after{
  content:'';position:absolute;top:-14px;right:-14px;width:46px;height:44px;
  background:url(/static/landing2/img/asset-36cc96ea5e.gif) center/contain no-repeat;
}
.closing{
  margin-top:24px;padding:28px 22px;border-radius:8px;border:2px solid var(--ink);
  background-image:linear-gradient(rgba(224,224,255,.55),rgba(224,224,255,.55)),
    url(/static/landing2/img/asset-7356a2b7f2.jpg);
  background-size:cover;background-position:center;text-align:center;box-shadow:var(--lift-black);
}
.closing p{font-family:var(--f-display);font-weight:700;font-size:19px;margin:0 0 16px}

/* ---- sticky action bar ---- */
.actions{
  position:fixed;left:0;right:0;bottom:0;z-index:30;pointer-events:none;
  background:var(--paper);border-top:3px solid var(--ink);
  padding:16px clamp(14px,4vw,32px);display:flex;justify-content:center;
}
.actions .inner{width:100%;max-width:960px;display:flex;gap:14px;align-items:center;pointer-events:none}
.actions button{pointer-events:auto}
.msg{font-size:12.5px;color:#333;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font-family:var(--f-body)}
.msg.ok{color:#136c2e}.msg.bad{color:#8a1310}.msg.warn{color:#8a6d00}
.spacer{flex:1}

@media (max-width:620px){
  .step{padding:22px 14px 150px}
  h1{font-size:20px}
  .site-header{padding:8px 14px;gap:10px}
  .site-header nav .nav-link{font-size:11px;padding:8px}
  .card{padding:14px}
  .actions{padding:12px 14px}
  .actions .inner{flex-wrap:wrap;gap:10px}
  .actions .msg{order:-1;width:100%;text-align:center}
  .actions .spacer{display:none}
  .actions button{flex:1;white-space:nowrap}
  .actions button.btn-primary{flex:2}
  .file{flex-wrap:wrap}
  .file .nm{max-width:100%}
  .prop .top{flex-wrap:wrap;gap:4px}
}

@media (prefers-reduced-motion:reduce){
  .step.live>*,.file,.prop,.note,.q,.tick{animation:fade 180ms ease both}
  @keyframes fade{from{opacity:0}to{opacity:1}}
  .mic.live::after{animation:pulse 1400ms ease-in-out infinite}
  @keyframes pulse{0%,100%{opacity:.25}50%{opacity:1}}
  .rail i.now{transform:rotate(-4deg)}
  button:active:not(:disabled){transform:none}
  .prop.no{transform:none}
  .drop.over{transform:rotate(0deg)}
}
@media (hover:hover) and (pointer:fine){
  .prop:hover{filter:brightness(0.98)}
}
"""

JS = r"""
const $ = (t, a = {}, kids = []) => {
  const el = document.createElement(t);
  for (const [k, v] of Object.entries(a)) {
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) el.setAttribute(k, v);
  }
  for (const kid of [].concat(kids)) if (kid) el.append(kid);
  return el;
};
const txt = s => document.createTextNode(s == null ? '' : String(s));
const byId = id => document.getElementById(id);

const S = {
  step: 'sources',
  links: { linkedin: '', github: '', website: '' },
  extraLinks: [],
  files: [],          // {name, label, text, chars, error}
  dump: '',
  cards: [], notes: [], questions: [], saved: null,
  msg: { text: '', cls: '' },
  decisions: {},      // cardId -> true (accept) | false (skip)
  answers: {},        // question index -> answer text
  rounds: 0,          // how many organize passes have run
  moreQuestions: [],  // held back rather than pushed at you again
};

function msg(text, cls = '') {
  // Held in state, not only in the node: drawActions() rebuilds the bar, and
  // writing straight to the DOM meant a save confirmation vanished instantly.
  S.msg = { text, cls };
  const m = byId('msg');
  if (m) { m.className = 'msg ' + cls; m.textContent = text; }
}

const STEPS = ['sources', 'working', 'review', 'interview'];
function go(step) {
  if (step !== S.step) S.msg = { text: '', cls: '' };
  S.step = step;
  for (const s of STEPS) byId('step-' + s).classList.toggle('live', s === step);
  for (const d of document.querySelectorAll('.decor[data-step]')) d.classList.toggle('live', d.dataset.step === step);
  const order = { sources: 0, working: 1, review: 2, interview: 3 };
  [...document.querySelectorAll('.rail i')].forEach((el, i) => {
    el.classList.toggle('done', i < order[step]);
    el.classList.toggle('now', i === order[step]);
  });
  window.scrollTo({ top: 0, behavior: 'instant' });
  drawActions();
}

/* ---------------- step 1: sources ---------------- */
function drawSources() {
  const root = byId('step-sources');
  root.innerHTML = '';

  root.append($('h1', {}, txt("Let's see what you've got")));
  root.append($('p', { class: 'sub' }, txt(
    'Drop a resume, paste a LinkedIn, or point at a folder. jobbot reads it once '
    + 'and reuses it forever. Nothing here has to be tidy — the point of the next '
    + 'step is that it does not have to be.')));

  // links
  const linkCard = $('div', { class: 'card' }, [
    $('h3', {}, txt('Links')),
    $('p', { class: 'hint' }, txt(
      'These go on the resume verbatim. Nothing is fetched from them — GitHub '
      + 'and LinkedIn both block automated reading, and a scraped bio is exactly '
      + 'the kind of fact this system will not assert for you. Paste what you '
      + 'want said; describe the rest below.')),
  ]);
  const lg = $('div', { class: 'grid' });
  for (const [k, ph] of [['linkedin', 'https://linkedin.com/in/you'],
                         ['github', 'https://github.com/you'],
                         ['website', 'https://you.dev']]) {
    const i = $('input', { type: 'text', placeholder: ph, value: S.links[k] });
    i.addEventListener('input', () => { S.links[k] = i.value; drawActions(); });
    lg.append($('label', {}, [$('span', { class: 'l' }, txt(k)), i]));
  }
  linkCard.append(lg);
  const more = $('div', { class: 'files' });
  const drawMore = () => {
    more.innerHTML = '';
    S.extraLinks.forEach((row, idx) => {
      const lab = $('input', { type: 'text', placeholder: 'label (e.g. Devpost, blog, paper)', value: row.label });
      const url = $('input', { type: 'text', placeholder: 'https://…', value: row.url });
      lab.addEventListener('input', () => { row.label = lab.value; });
      url.addEventListener('input', () => { row.url = url.value; drawActions(); });
      more.append($('div', { class: 'file' }, [lab, url,
        $('button', { class: 'tiny ghost', onclick: () => { S.extraLinks.splice(idx, 1); drawMore(); drawActions(); } }, txt('remove'))]));
    });
    more.append($('button', { class: 'tiny ghost', onclick: () => { S.extraLinks.push({ label: '', url: '' }); drawMore(); } }, txt('+ another link')));
  };
  drawMore();
  linkCard.append(more);
  root.append(linkCard);

  // resumes
  const dropCard = $('div', { class: 'card' }, [
    $('h3', {}, txt('Resumes')),
    $('p', { class: 'hint' }, txt(
      'Drop as many as you like — the ML one, the backend one, the old one. '
      + 'Label each so the model knows which role it was aimed at. Several '
      + 'resumes describe one career, so they get merged per role rather than '
      + 'duplicated, and anything they disagree on is flagged instead of picked.')),
  ]);
  const drop = $('div', { class: 'drop' }, [
    $('div', { class: 'drop-main' }, txt('drop your resume here')),
    $('div', { class: 'drop-sub' }, txt('or browse — PDF')),
  ]);
  const picker = $('input', { type: 'file', accept: '.pdf', multiple: 'true', style: 'display:none' });
  drop.addEventListener('click', () => picker.click());
  picker.addEventListener('change', () => addFiles([...picker.files]));
  drop.addEventListener('dragover', ev => { ev.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', ev => {
    ev.preventDefault(); drop.classList.remove('over');
    addFiles([...ev.dataTransfer.files].filter(f => /\.pdf$/i.test(f.name)));
  });
  dropCard.append(drop, picker, $('div', { class: 'files', id: 'filelist' }));
  root.append(dropCard);

  // dictation
  const dictCard = $('div', { class: 'card' }, [
    $('h3', {}, txt('Say everything else')),
    $('p', { class: 'hint' }, txt(
      'One long paragraph is fine. Ramble. What you have built, what the numbers '
      + 'actually were, what you want next, what you would rather not do, why you '
      + 'left, what you are proud of, anything an application might ask. The next '
      + 'step cleans up the filler and keeps the facts — it will not add any.')),
  ]);
  const wrap = $('div', { class: 'dictate' });
  const ta = $('textarea', { id: 'dump', placeholder:
    "e.g. So I'm a backend engineer, been at Example Corp about two years, the "
    + "big thing I did was rebuild the ingestion path and that took p99 from "
    + "840ms down to 95ms, also migrated 38 services with no downtime. I want "
    + "inference or infra roles, San Francisco or remote, can start two weeks "
    + "after an offer…" });
  ta.value = S.dump;
  ta.addEventListener('input', () => { S.dump = ta.value; byId('cc').textContent = S.dump.length ? S.dump.length + ' chars' : ''; drawActions(); });
  const mic = $('button', { class: 'mic', id: 'mic', title: 'dictate (speech to text)' });
  mic.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
    + 'stroke="currentColor" stroke-width="2" stroke-linecap="round">'
    + '<rect x="9" y="2" width="6" height="11" rx="3"/>'
    + '<path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>'
    + '<span id="miclabel">Dictate</span>';
  mic.addEventListener('click', toggleMic);
  dictCard.append($('div', { class: 'microw' }, [
    mic,
    $('span', { id: 'micnote', style: 'color:var(--dim);font-size:12px' }, txt('')),
  ]));
  wrap.append(ta, $('span', { class: 'count', id: 'cc' },
    txt(S.dump.length ? S.dump.length + ' chars' : '')));
  dictCard.append(wrap);
  root.append(dictCard);
  drawFiles();
}

function addFiles(list) {
  for (const f of list) {
    const rec = { name: f.name, label: '', text: '', chars: 0, error: '', busy: true };
    S.files.push(rec);
    drawFiles();
    f.arrayBuffer().then(async buf => {
      const res = await fetch('/api/resume-text', { method: 'POST', body: buf });
      const out = await res.json();
      rec.busy = false;
      if (out.ok) { rec.text = out.text; rec.chars = out.chars; }
      else rec.error = out.error || 'could not read';
      drawFiles(); drawActions();
    });
  }
}

function drawFiles() {
  const box = byId('filelist');
  if (!box) return;
  box.innerHTML = '';
  S.files.forEach((f, i) => {
    const lab = $('input', { type: 'text', value: f.label,
      placeholder: 'what was this one tailored for? (e.g. ML infra roles)' });
    lab.addEventListener('input', () => { f.label = lab.value; });
    const state = f.busy ? $('span', { class: 'ok' }, txt('reading…'))
      : f.error ? $('span', { class: 'bad' }, txt(f.error.slice(0, 40)))
      : $('span', { class: 'ok' }, txt(f.chars.toLocaleString() + ' chars'));
    box.append($('div', { class: 'file' }, [
      $('span', { class: 'nm' }, txt(f.name)), state, lab,
      $('button', { class: 'tiny ghost', onclick: () => { S.files.splice(i, 1); drawFiles(); drawActions(); } }, txt('remove')),
    ]));
  });
}

/* ---------------- dictation via the browser's own recogniser ---------------- */
let rec = null, recOn = false, baseText = '';
function toggleMic() {
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  const note = byId('micnote');
  if (!Rec) {
    note.textContent = window.isSecureContext
      ? 'This browser has no speech recognition — Chrome or Safari do. Typing works the same.'
      : 'Dictation needs a secure context. Open the https:// tailnet address and the mic works.';
    return;
  }
  if (recOn) { rec.stop(); return; }
  rec = new Rec();
  rec.continuous = true; rec.interimResults = true; rec.lang = 'en-US';
  baseText = byId('dump').value;
  rec.onstart = () => {
    recOn = true;
    byId('mic').classList.add('live');
    byId('miclabel').textContent = 'Stop';
    note.textContent = 'listening — speak normally, it keeps up';
  };
  rec.onerror = ev => { note.textContent = 'mic error: ' + ev.error; };
  rec.onend = () => {
    recOn = false;
    byId('mic').classList.remove('live');
    byId('miclabel').textContent = 'Dictate';
    note.textContent = '';
  };
  rec.onresult = ev => {
    let done = '', interim = '';
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const r = ev.results[i];
      if (r.isFinal) done += r[0].transcript;
      else interim += r[0].transcript;
    }
    if (done) baseText = (baseText + ' ' + done.trim()).trim();
    const ta = byId('dump');
    ta.value = (baseText + (interim ? ' ' + interim : '')).trim();
    S.dump = baseText;
    byId('cc').textContent = ta.value.length + ' chars';
    ta.scrollTop = ta.scrollHeight;
    drawActions();
  };
  rec.start();
}

/* ---------------- step 2: working ---------------- */
const TICKS = [
  'reading what you gave it',
  'merging roles across resumes',
  'keeping your numbers exactly as written',
  'writing down anything it had to interpret',
  'leaving screening answers alone — those are yours',
];
let tickTimer = null, elapsedTimer = null;
function startWorking(what) {
  go('working');
  const root = byId('step-working');
  root.innerHTML = '';
  root.append($('div', { class: 'working' }, [
    $('div', { class: 'barrow' }, [
      $('div', { class: 'scan' }, [$('div', { class: 'fill', id: 'scanfill' })]),
      $('img', { class: 'spin-sticker', src: '/static/landing2/img/asset-5060552dc3.gif', alt: '' }),
    ]),
    $('div', { class: 'what' }, txt(what)),
    $('div', { class: 'who', id: 'ticks' }),
    $('div', { class: 'elapsed', id: 'elapsed' }),
  ]));
  let i = 0;
  const next = () => {
    if (i >= TICKS.length) return;
    byId('ticks').append($('div', { class: 'tick' }, txt(TICKS[i++])));
    const fill = byId('scanfill');
    if (fill) fill.style.width = Math.round((i / TICKS.length) * 100) + '%';
    tickTimer = setTimeout(next, 1600);
  };
  next();
  // The call takes 15-30s. Once the ticks run out a static screen reads as
  // hung, so keep a number moving -- it is information, not decoration.
  const t0 = Date.now();
  elapsedTimer = setInterval(() => {
    const el = byId('elapsed');
    if (el) el.textContent = Math.round((Date.now() - t0) / 1000) + 's';
  }, 1000);
}
function stopWorking() { clearTimeout(tickTimer); clearInterval(elapsedTimer); }

/* ---------------- step 3: review ---------------- */
const GROUPS = [
  ['identity', 'Contact details'], ['headline', 'Headline'], ['summary', 'Summary'],
  ['experience', 'Experience'], ['education', 'Education'], ['project', 'Projects'],
  ['skills', 'Skills'], ['list', 'Lists'], ['compensation', 'Compensation'],
  ['preference', 'Preferences'], ['extra', 'Free-form facts'],
];

function renderValue(card) {
  const b = card.body;
  if (Array.isArray(b)) {
    return $('div', { class: 'val' }, [$('ul', {}, b.map(x => $('li', {}, txt(
      typeof x === 'string' ? x : JSON.stringify(x)))))]);
  }
  if (b && typeof b === 'object') {
    const bits = [];
    const nice = k => k.replace(/_/g, ' ');
    for (const [k, v] of Object.entries(b)) {
      // `source` is shown in the card header; `name`/`label` are the card title
      // already, so repeating them is noise on the thing you are reading.
      if (k === 'source' || v === '' || v == null) continue;
      // Anything already spelled out in the card heading is noise in the body:
      // "Backend Engineer — Example Corp" does not need COMPANY and TITLE rows.
      const sv = String(v).trim();
      if (sv.length > 1 && sv.length < 70 && String(card.title).includes(sv)) continue;
      if (Array.isArray(v)) {
        if (!v.length) continue;
        bits.push($('div', {}, [$('span', { class: 'k' }, txt(nice(k))),
          $('ul', {}, v.map(x => $('li', {}, txt(x))))]));
      } else {
        bits.push($('div', {}, [$('span', { class: 'k' }, txt(nice(k) + ' ')), txt(v)]));
      }
    }
    return $('div', { class: 'val' }, bits);
  }
  return $('div', { class: 'val' }, txt(b));
}

/* Decisions are applied to the one card that was clicked. Re-rendering the
   whole list on every click destroyed and rebuilt every node, which restarted
   the staggered entrance animation on all of them -- so a click looked like a
   page flicker rather than a change of state. */
function setDecision(id, val) {
  S.decisions[id] = val;
  const el = document.querySelector(`.prop[data-id="${id}"]`);
  if (el) {
    el.classList.toggle('yes', val === true);
    el.classList.toggle('no', val === false);
    el.querySelectorAll('.acts button').forEach(b => {
      b.classList.toggle('on', (b.dataset.act === 'accept') === (val === true));
    });
  }
  refreshCounts();
}

function decideMany(ids, val) {
  for (const id of ids) setDecision(id, val);
}

function refreshCounts() {
  for (const h of document.querySelectorAll('.group[data-kind]')) {
    const kind = h.dataset.kind;
    const mine = S.cards.filter(c => c.kind === kind);
    const yes = mine.filter(c => S.decisions[c.id] === true).length;
    const label = h.querySelector('h2 .n');
    if (label) label.textContent = `· ${yes}/${mine.length}`;
  }
  const total = S.cards.length;
  const yes = S.cards.filter(c => S.decisions[c.id] === true).length;
  const count = byId('bulkcount');
  if (count) {
    count.textContent = total
      ? `${yes} of ${total} accepted` + (yes === total ? ' — ready to save' : '')
      : '';
  }
  const yesBtn = byId('bulkyes'), noBtn = byId('bulkno');
  if (yesBtn) yesBtn.disabled = yes === total;
  if (noBtn) noBtn.disabled = yes === 0;
  drawActions();
}

function drawReview() {
  const root = byId('step-review');
  root.innerHTML = '';
  root.append($('h1', {}, txt(S.saved ? 'Saved' : 'Here is what it made of that')));
  if (S.saved) {
    const sv = S.saved;
    const done = $('div', { class: 'saved' }, [
      $('div', {}, txt(`In your profile now: ${sv.roles} roles, ${sv.years} years, `
        + `${sv.screening} screening answers.`)),
    ]);
    if (sv.missing.length) {
      // The only part intake cannot do for him, stated once, with the way to it.
      done.append($('div', { class: 'left' }, [
        txt(`${sv.missing.length} screening answers are still unset, and a run will `
          + `not start without them. They are the only thing here that has to be `
          + `you: `),
        $('a', { href: '/edit#screening' }, txt('set them in the editor →')),
      ]));
    }
    if (sv.identity.length) {
      done.append($('div', { class: 'left' }, [
        txt('An application cannot be submitted without '
          + sv.identity.map(f => f.replace('identity.', '').replace('_', ' ')).join(', ')
          + '. Saved anyway — add it in '),
        $('a', { href: '/edit#identity' }, txt('the editor')),
        txt(' or just say it here and organize again.'),
      ]));
    }
    if (sv.undated.length) {
      done.append($('div', { class: 'left' }, txt(
        sv.undated.length + ' role(s) have no start date: ' + sv.undated.join('; ')
        + '. Dates drive years-of-experience answers, so they are worth adding.')));
    }
    if ((sv.untitled || []).length) {
      done.append($('div', { class: 'left' }, txt(
        'No job title was stated for: ' + sv.untitled.join('; ')
        + '. It was left blank rather than guessed — add it and organize again.')));
    }
    if (S.moreQuestions.length) {
      done.append($('div', { class: 'left' }, [
        $('button', { class: 'tiny ghost', onclick: () => {
          S.questions = S.moreQuestions; S.moreQuestions = []; drawInterview();
        } }, txt(`it has ${S.moreQuestions.length} more questions — ask me`)),
      ]));
    }
    root.append(done);
  }
  root.append($('p', { class: 'sub' }, txt(S.saved
    ? (S.cards.length
        ? 'These are the ones you skipped. Accept any of them and save again, '
          + 'or add more material from the start.'
        : 'Everything you accepted is in the profile. Add more material any time '
          + '— it merges, it does not overwrite.')
    : 'Everything is already accepted — press save and you are done. Skip '
      + 'anything that is wrong first; each card shows which file or which '
      + 'sentence it came from.')));

  if (S.cards.length) {
    const ids = S.cards.map(c => c.id);
    // The count is live and the buttons disable when there is nothing left to
    // do. Cards arrive pre-accepted, so "accept everything" on a fresh review
    // was a genuine no-op with no feedback -- a working button that looked dead.
    root.append($('div', { class: 'bulk' }, [
      $('span', { class: 't', id: 'bulkcount' }, txt('')),
      $('button', { class: 'tiny', id: 'bulkyes',
        onclick: () => { decideMany(ids, true); msg(`accepted all ${ids.length}`, 'ok'); } },
        txt('accept everything')),
      $('button', { class: 'tiny ghost', id: 'bulkno',
        onclick: () => { decideMany(ids, false); msg(`skipped all ${ids.length}`, 'warn'); } },
        txt('skip everything')),
    ]));
  }

  if (!S.cards.length && !S.notes.length) {
    root.append($('div', { class: 'card' }, [$('p', { class: 'hint' }, txt(
      'It found nothing new to add — either the profile already has it, or the '
      + 'sources did not actually state anything it could use.'))]));
    return;
  }

  let n = 0;
  for (const [kind, label] of GROUPS) {
    const mine = S.cards.filter(c => c.kind === kind);
    if (!mine.length) continue;
    const g = $('div', { class: 'group', 'data-kind': kind });
    const yes = mine.filter(c => S.decisions[c.id] === true).length;
    const head = $('h2', {}, [txt(label),
      $('span', { class: 'n' }, txt(`· ${yes}/${mine.length}`))]);
    head.append($('span', { class: 'spacer', style: 'flex:1' }));
    const myIds = mine.map(c => c.id);
    head.append($('button', { class: 'tiny ghost', onclick: () => decideMany(myIds, true) }, txt('accept all')));
    head.append($('button', { class: 'tiny ghost', onclick: () => decideMany(myIds, false) }, txt('skip all')));
    g.append(head);

    for (const c of mine) {
      const d = S.decisions[c.id];
      const el = $('div', {
        class: 'prop' + (d === true ? ' yes' : d === false ? ' no' : ''),
        'data-id': c.id,
        style: '--i:' + (n++ % 14),
      });
      const top = $('div', { class: 'top' }, [$('span', { class: 't' }, txt(c.title))]);
      if (c.source) top.append($('span', { class: 'src' }, txt(c.source)));
      el.append(top, renderValue(c));
      if (c.replaces) el.append($('div', { class: 'was' }, txt('replaces: ' + c.replaces.slice(0, 160))));
      const acts = $('div', { class: 'acts' }, [
        $('button', { class: 'tiny' + (d === true ? ' on' : ''), 'data-act': 'accept',
          onclick: () => setDecision(c.id, true) }, txt('accept')),
        $('button', { class: 'tiny' + (d === false ? ' on' : ''), 'data-act': 'skip',
          onclick: () => setDecision(c.id, false) }, txt('skip')),
      ]);
      el.append(acts);
      g.append(el);
    }
    root.append(g);
  }

  if (S.notes.length) {
    const g = $('div', { class: 'group' });
    g.append($('h2', {}, txt('What it wants you to know')));
    S.notes.forEach((nt, i) => {
      const sev = nt.severity || 'info';
      g.append($('div', { class: 'note' + (sev === 'info' ? ' info' : ''), style: '--i:' + i }, [
        $('span', { class: 'k' }, txt(sev)), txt(nt.observation),
      ]));
    });
    root.append(g);
  }

  if (S.questions.length) {
    const g = $('div', { class: 'group' });
    g.append($('h2', {}, txt('Optional — only if you want to go deeper')));
    const box = $('div', { class: 'card' }, [
      $('p', { class: 'hint' }, txt(
        (S.saved ? 'Already saved. ' : 'Save first; this changes nothing about that. ')
        + 'It has ' + S.questions.length + ' questions that would fill in the thin '
        + 'parts, but the profile works without them.')),
    ]);
    const row = $('div', { style: 'display:flex;gap:9px;flex-wrap:wrap' }, [
      $('button', { class: 'btn btn-secondary', onclick: () => drawInterview() },
        txt('Answer ' + S.questions.length + ' questions →')),
      $('button', { class: 'tiny ghost', onclick: () => { S.questions = []; drawReview(); } },
        txt("no thanks, I'm done")),
    ]);
    box.append(row);
    g.append(box);
    root.append(g);
  }
  refreshCounts();
}

/* ---------------- interview ---------------- */
function drawInterview() {
  go('interview');
  const root = byId('step-interview');
  root.innerHTML = '';
  root.append($('h1', {}, txt('A few questions')));
  root.append($('p', { class: 'sub' }, txt(
    'Answer in whatever order you like, as loosely as you like — same deal, it '
    + 'cleans up the wording and keeps your facts. Skip any that do not apply.')));
  S.questions.forEach((q, i) => {
    const box = $('div', { class: 'q' + (S.answers[i] ? ' answered' : ''), style: '--i:' + (i % 12) });
    box.append($('div', { class: 'qt' }, txt(q.question)));
    if (q.why) box.append($('div', { class: 'why' }, txt(q.why)));
    const ta = $('textarea', { placeholder: q.placeholder || 'type or dictate…' });
    ta.value = S.answers[i] || '';
    ta.addEventListener('input', () => {
      S.answers[i] = ta.value;
      box.classList.toggle('answered', !!ta.value.trim());
      drawActions();
    });
    box.append(ta);
    root.append(box);
  });
  root.append($('div', { class: 'closing' }, [
    $('p', {}, txt("That's it. jobbot has what it needs.")),
    $('a', { class: 'btn btn-primary', href: '/' }, txt('Back to overview →')),
  ]));
}

/* ---------------- actions bar ---------------- */
function drawActions() {
  const bar = byId('actbar');
  bar.innerHTML = '';
  const accepted = Object.values(S.decisions).filter(v => v === true).length;
  const hasSource = !!(S.dump.trim() || S.files.some(f => f.text)
    || Object.values(S.links).some(v => v.trim())
    || S.extraLinks.some(l => l.url.trim()));
  const answered = Object.values(S.answers).filter(a => a && a.trim()).length;

  if (S.step === 'sources') {
    bar.append($('button', { class: 'btn btn-secondary', onclick: askQuestions }, txt('Interview me instead')));
    bar.append($('span', { class: 'spacer' }));
    bar.append($('span', { class: 'msg ' + S.msg.cls, id: 'msg' }, txt(
      S.msg.text || (hasSource ? '' : 'add a link, a resume, or a paragraph'))));
    const b = $('button', { class: 'btn btn-primary', onclick: organize }, txt('Organize this →'));
    b.disabled = !hasSource;
    bar.append(b);
  } else if (S.step === 'working') {
    bar.append($('span', { class: 'msg', id: 'msg' }, txt('')));
  } else if (S.step === 'review') {
    bar.append($('button', { class: 'btn btn-secondary', onclick: () => go('sources') }, txt('← back')));
    bar.append($('span', { class: 'spacer' }));
    bar.append($('span', { class: 'msg ' + S.msg.cls, id: 'msg' }, txt(S.msg.text)));
    const label = accepted ? `Save ${accepted} to profile`
      : S.saved ? (S.cards.length ? 'Accept something to save it' : 'All saved')
      : 'Nothing accepted yet';
    const b = $('button', { class: 'btn btn-primary', onclick: applyAccepted }, txt(label));
    b.disabled = !accepted;
    bar.append(b);
    if (S.saved && !S.cards.length) {
      bar.append($('button', { class: 'btn btn-secondary', onclick: () => {
        S.dump = ''; S.files = []; S.saved = null; S.notes = [];
        drawSources(); go('sources');
      } }, txt('Add more →')));
    }
  } else {
    bar.append($('button', { class: 'btn btn-secondary', onclick: () => go(S.cards.length ? 'review' : 'sources') }, txt('← back')));
    bar.append($('span', { class: 'spacer' }));
    bar.append($('span', { class: 'msg ' + S.msg.cls, id: 'msg' }, txt(
      S.msg.text || (answered ? `${answered} answered` : 'answer at least one'))));
    const b = $('button', { class: 'btn btn-primary', onclick: organizeAnswers }, txt('Organize answers →'));
    b.disabled = !answered;
    bar.append(b);
  }
}

/* ---------------- server calls ---------------- */
async function post(url, body) {
  const res = await fetch(url, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return res.json();
}

function sourcePayload() {
  const links = { ...S.links };
  S.extraLinks.forEach(l => { if (l.url.trim()) links[l.label.trim() || l.url] = l.url; });
  return {
    dump: S.dump,
    links,
    resumes: S.files.filter(f => f.text).map(f => ({ name: f.name, label: f.label, text: f.text })),
  };
}

async function organize() {
  startWorking('Organizing what you gave it');
  const out = await post('/api/intake/organize', sourcePayload());
  stopWorking();
  if (!out.ok) { go('sources'); msg(out.error || 'that did not work', 'bad'); return; }
  S.rounds++;
  S.cards = out.cards; S.notes = out.notes || []; S.questions = out.questions || [];
  S.decisions = {};
  for (const c of S.cards) S.decisions[c.id] = true;   // opt-out, not opt-in
  go('review'); drawReview();
  msg(`${S.cards.length} proposals · ${out.usage.input_tokens} in / ${out.usage.output_tokens} out tokens`);
}

async function organizeAnswers() {
  startWorking('Working your answers in');
  const payload = sourcePayload();
  payload.answers = S.questions.map((q, i) => ({ question: q.question, answer: S.answers[i] || '' }))
    .filter(a => a.answer.trim());
  const out = await post('/api/intake/organize', payload);
  stopWorking();
  if (!out.ok) { drawInterview(); msg(out.error || 'that did not work', 'bad'); return; }
  S.rounds++;
  S.cards = out.cards; S.notes = out.notes || [];
  // Do NOT put a fresh batch of questions in front of you again. One answer
  // round is enough to be useful; more only if you ask for it.
  S.moreQuestions = out.questions || [];
  S.questions = [];
  S.answers = {};
  S.decisions = {};
  for (const c of S.cards) S.decisions[c.id] = true;
  go('review'); drawReview();
}

async function askQuestions() {
  startWorking('Working out what to ask you');
  const out = await post('/api/intake/questions', { dump: S.dump });
  stopWorking();
  if (!out.ok) { go('sources'); msg(out.error || 'that did not work', 'bad'); return; }
  S.questions = out.questions || [];
  if (!S.questions.length) { go('sources'); msg('nothing to ask — the profile looks complete', 'ok'); return; }
  drawInterview();
}

async function applyAccepted() {
  const patches = S.cards.filter(c => S.decisions[c.id] === true).map(c => c.patch);
  msg('saving…');
  const out = await post('/api/intake/apply', { patches });
  if (!out.ok) {
    // The bar truncates, so a rejection has to be legible in the page itself.
    msg('not saved — see the reason above', 'bad');
    const root = byId('step-review');
    const box = $('div', { class: 'failed' }, [
      $('div', {}, txt('Not saved. Nothing was written, so nothing was lost.')),
      $('ul', {}, (out.errors || [out.error || 'unknown error']).map(e => $('li', {}, txt(e)))),
    ]);
    root.insertBefore(box, root.firstChild);
    window.scrollTo({ top: 0, behavior: 'instant' });
    return;
  }
  const m = out.missing_core || [];
  S.cards = S.cards.filter(c => S.decisions[c.id] !== true);
  Object.keys(S.decisions).forEach(k => {
    if (!S.cards.some(c => c.id === k)) delete S.decisions[k];
  });
  S.saved = {
    roles: out.roles, years: out.years, screening: out.screening_set, missing: m,
    identity: out.missing_identity || [], undated: out.undated_roles || [],
    untitled: out.untitled_roles || [],
  };
  drawReview();
  msg(m.length ? `saved · ${m.length} screening answers still need you`
               : 'saved · preflight clear', m.length ? 'warn' : 'ok');
}
"""


def render(nav_active: str = "/intake") -> bytes:
    nav = "".join(
        f'<a href="{p}" class="nav-link{" on" if p == nav_active else ""}">{n}</a>'
        for p, n in [("/", "overview"), ("/answers", "answers"),
                     ("/edit", "edit profile"), ("/intake", "intake"),
                     ("/status", "status")])
    return f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700&family=Space+Mono:wght@400;700&family=Nanum+Pen+Script&family=Zilla+Slab+Highlight:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/collage.css">
<title>jobbot — intake</title>
<style>{CSS}</style></head>
<body class=collage>
<header class="site-header layer-content">
  <a class="logo-dot hand" href="/landing2" title="Back to landing">jobbot</a>
  <nav role="navigation" aria-label="main">{nav}</nav>
</header>
<div class="rail-wrap layer-content">
  <div class=rail>
    <i class=now><b>1</b><span class=lbl>sources</span></i>
    <em class=link aria-hidden=true></em>
    <i><b>2</b><span class=lbl>working</span></i>
    <em class=link aria-hidden=true></em>
    <i><b>3</b><span class=lbl>review</span></i>
    <em class=link aria-hidden=true></em>
    <i><b>4</b><span class=lbl>interview</span></i>
  </div>
</div>
<main>
  <section class=stepwrap data-step=sources>
    <div class=decor data-step=sources aria-hidden=true>
      <img class=scene src="/static/landing2/img/asset-7d08b9b774.jpg" alt="">
      <div class=fade></div>
      <img class=corner-x src="/static/landing2/img/asset-36cc96ea5e.gif" alt="">
    </div>
    <div class="step layer-content" id=step-sources></div>
  </section>
  <section class=stepwrap data-step=working>
    <div class=decor data-step=working aria-hidden=true>
      <img class=squiggle src="/static/landing2/img/asset-191a616ef1.gif" alt="">
    </div>
    <div class="step layer-content" id=step-working></div>
  </section>
  <section class=stepwrap data-step=review>
    <div class=decor data-step=review aria-hidden=true>
      <img class=squiggle src="/static/landing2/img/asset-191a616ef1.gif" alt="">
    </div>
    <div class="step layer-content" id=step-review></div>
  </section>
  <section class=stepwrap data-step=interview>
    <div class=decor data-step=interview aria-hidden=true>
      <img class=scene src="/static/landing2/img/asset-7356a2b7f2.jpg" alt="">
      <div class=wash></div>
    </div>
    <div class="step layer-content" id=step-interview></div>
  </section>
</main>
<div class=actions><div class=inner id=actbar></div></div>
<script>{JS}
drawSources(); go('sources');
</script></body></html>""".encode()
