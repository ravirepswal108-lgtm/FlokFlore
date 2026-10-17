"""The Folklore dashboard: one self-contained HTML file a maintainer uses to review rules.

Everything works offline inside the single file:
* Overview of what was mined and what survived each filter.
* Rules: search, filter by area / status / auto-checkable, sort, expand for evidence,
  approve or reject each rule. Decisions are remembered in this browser and turned into the
  exact `folklore reject ...` command to run.
* Set aside: recurring feedback that did not become a rule, and why.
* Check a diff: paste `git diff` output and see which conventions it breaks (the same
  logic as `folklore check-diff`, ported to the browser).
* Skill file: the generated SKILL.md and reference files, validated, ready to copy.

The palette is deliberately free of blue (tests/test_report.py enforces it).
"""

from __future__ import annotations

import html
import json
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .models import Rule
from .publish import publish, validate_skill

FONTS = (
    "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&"
    "family=IBM+Plex+Sans:wght@400;500;600&display=swap"
)

CSS = """
/* Layout: app shell. A sidebar of sections on wide screens (a scrolling tab strip on phones)
   beside one working panel at a time: overview, rules, set aside, diff checker, skill file. */
:root {
  --bg: #f3f3ef;
  --panel: #ffffff;
  --panel-2: #f8f8f5;
  --ink: #1e201b;
  --ink-2: #464a40;
  --muted: #6c7064;
  --line: #e1e2db;
  --line-strong: #cbcdc2;
  --accent: #9c5d08;
  --accent-ink: #ffffff;
  --accent-soft: #f6ead3;
  --good: #2d6a39;
  --good-soft: #e2efe1;
  --bad: #a1392a;
  --bad-soft: #f8e4e0;
  --warn: #855800;
  --warn-soft: #f6ead0;
  --bar: #dccaa4;
  --bar-strong: #9c5d08;
  --code: #f1f1ec;
  --side: #1b1d18;
  --side-ink: #e6e7df;
  --side-muted: #a2a697;
  --side-active: #2c2f27;
  --shadow: 0 1px 2px rgba(30, 32, 27, .06), 0 4px 16px rgba(30, 32, 27, .05);
  --font-sans: "IBM Plex Sans", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #11130f; --panel: #191b16; --panel-2: #1f221c; --ink: #e7e8e1; --ink-2: #c4c7bb;
    --muted: #9a9e90; --line: #2b2e26; --line-strong: #3b3f34; --accent: #e3a54a;
    --accent-ink: #1b1305; --accent-soft: #392b13; --good: #90cf97; --good-soft: #1c2f1f;
    --bad: #f09a8b; --bad-soft: #3a1f1a; --warn: #e8bf62; --warn-soft: #362a11;
    --bar: #5a4c2d; --bar-strong: #e3a54a; --code: #23261f; --side: #0c0d0a;
    --side-ink: #e6e7df; --side-muted: #9a9e90; --side-active: #22251e;
    --shadow: 0 1px 2px rgba(0, 0, 0, .4); color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #11130f; --panel: #191b16; --panel-2: #1f221c; --ink: #e7e8e1; --ink-2: #c4c7bb;
  --muted: #9a9e90; --line: #2b2e26; --line-strong: #3b3f34; --accent: #e3a54a;
  --accent-ink: #1b1305; --accent-soft: #392b13; --good: #90cf97; --good-soft: #1c2f1f;
  --bad: #f09a8b; --bad-soft: #3a1f1a; --warn: #e8bf62; --warn-soft: #362a11;
  --bar: #5a4c2d; --bar-strong: #e3a54a; --code: #23261f; --side: #0c0d0a;
  --side-ink: #e6e7df; --side-muted: #9a9e90; --side-active: #22251e;
  --shadow: 0 1px 2px rgba(0, 0, 0, .4); color-scheme: dark;
}
* { box-sizing: border-box; }
html, body { min-height: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.55 var(--font-sans); }
::selection { background: var(--accent-soft); color: var(--ink); }
a { color: var(--accent); text-underline-offset: 2px; }
a:visited { color: var(--accent); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
button, input, select, textarea { font: inherit; color: inherit; accent-color: var(--accent); }
button { cursor: pointer; }
code, pre, .mono { font-family: var(--font-mono); }
.num { font-variant-numeric: tabular-nums; }

.app { display: grid; grid-template-columns: 232px minmax(0, 1fr); min-height: 100vh; }
.side {
  background: var(--side); color: var(--side-ink); display: flex; flex-direction: column; gap: 24px;
  padding-block: 20px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: 16px;
  position: sticky; top: 0; height: 100vh; overflow-y: auto;
}
.brand { display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 15px; letter-spacing: .01em; }
.brand svg { flex: none; }
.repo { display: grid; gap: 2px; padding: 12px; border-radius: 8px; background: var(--side-active); }
.repo span { font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--side-muted); }
.repo b { font-weight: 500; overflow-wrap: anywhere; }
.nav { display: grid; gap: 2px; }
.nav [role="tab"] {
  display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%;
  padding: 9px 12px; border: 0; border-radius: 6px; background: transparent; color: var(--side-muted);
  text-align: left; font-size: 14px;
}
.nav [role="tab"]:hover { color: var(--side-ink); background: var(--side-active); }
.nav [role="tab"][aria-selected="true"] { color: var(--side-ink); background: var(--side-active); box-shadow: inset 2px 0 0 var(--bar-strong); }
.nav .count { font: 500 12px var(--font-mono); color: var(--side-muted); }
.side-foot { margin-top: auto; font-size: 12px; color: var(--side-muted); display: grid; gap: 6px; }
.progress { height: 6px; border-radius: 3px; background: var(--side-active); overflow: hidden; }
.progress i { display: block; height: 100%; width: 0; background: var(--bar-strong); transition: width .25s; }

.main { min-width: 0; padding-block: 28px 56px; padding-left: 32px; padding-right: max(32px, env(safe-area-inset-right, 0px)); }
.panel-head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px 24px; margin-bottom: 20px; }
.panel-head h1 { margin: 0; font-size: 24px; line-height: 1.25; font-weight: 600; text-wrap: balance; }
.panel-head p { margin: 4px 0 0; color: var(--muted); max-width: 70ch; }
.notice { margin: 0 0 20px; padding: 10px 14px; border-radius: 8px; background: var(--warn-soft); color: var(--warn); font-size: 13px; }

.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; box-shadow: var(--shadow); min-width: 0; }
.card-pad { padding: 18px 20px; }
.card h2 { margin: 0 0 14px; font-size: 15px; font-weight: 600; }
.grid { display: grid; gap: 16px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.kpi { padding: 16px 18px; display: grid; gap: 2px; }
.kpi .label { font-size: 12px; color: var(--muted); }
.kpi .value { font: 600 28px/1.15 var(--font-sans); font-variant-numeric: tabular-nums; }
.kpi .sub { font-size: 12px; color: var(--muted); }
.two { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 16px; }

.bars { display: grid; gap: 12px; }
.bar-row { display: grid; grid-template-columns: minmax(120px, 190px) minmax(0, 1fr) 40px; gap: 12px; align-items: center; }
.bar-row .track { height: 10px; border-radius: 5px; background: var(--code); overflow: hidden; }
.bar-row .fill { display: block; height: 100%; background: var(--bar); border-radius: 5px; }
.bar-row.strong .fill { background: var(--bar-strong); }
.bar-row .val { text-align: right; font: 500 13px var(--font-mono); font-variant-numeric: tabular-nums; }
.dropped { margin: 16px 0 0; padding: 14px 0 0; border-top: 1px solid var(--line); list-style: none; display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 6px 16px; font-size: 13px; color: var(--muted); }
.dropped b { font: 500 13px var(--font-mono); color: var(--ink); }
.facts { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 8px 16px; font-size: 13px; }
.facts dt { color: var(--muted); }
.facts dd { margin: 0; overflow-wrap: anywhere; }

.btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 7px 12px; border-radius: 6px; border: 1px solid var(--line-strong); background: var(--panel); font-size: 13px; font-weight: 500; white-space: nowrap; }
.btn:hover { background: var(--panel-2); }
.btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.btn.primary:hover { filter: brightness(1.06); }
.btn.ghost { border-color: transparent; background: transparent; color: var(--muted); }
.btn.ghost:hover { color: var(--ink); background: var(--panel-2); }
.cmd { display: flex; align-items: center; gap: 8px; padding: 8px 8px 8px 12px; border: 1px solid var(--line); border-radius: 6px; background: var(--panel-2); min-width: 0; }
.cmd code { flex: 1; min-width: 0; font-size: 12.5px; overflow-wrap: anywhere; }
.decision-stats { display: flex; flex-wrap: wrap; gap: 8px 20px; margin: 0 0 12px; font-size: 13px; color: var(--muted); }
.decision-stats b { font: 600 18px var(--font-sans); color: var(--ink); font-variant-numeric: tabular-nums; margin-right: 4px; }
.row-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.hint-text { font-size: 12px; color: var(--muted); margin: 8px 0 0; }

.toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
.field { display: flex; align-items: center; gap: 8px; }
.field label { font-size: 12px; color: var(--muted); }
.toolbar input[type="search"], .toolbar select { height: 36px; padding: 0 10px; border: 1px solid var(--line-strong); border-radius: 6px; background: var(--panel); }
.toolbar input[type="search"] { flex: 1 1 240px; min-width: 0; }
.seg { display: inline-flex; flex-wrap: wrap; border: 1px solid var(--line-strong); border-radius: 6px; overflow: hidden; background: var(--panel); }
.seg button { border: 0; background: transparent; padding: 0 12px; height: 34px; font-size: 13px; color: var(--muted); }
.seg button + button { border-left: 1px solid var(--line); }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--panel); }
.check { display: inline-flex; gap: 6px; align-items: center; font-size: 13px; color: var(--ink-2); cursor: pointer; }
.result-count { font-size: 12px; color: var(--muted); margin: 0 0 10px; }

.rule-list { display: grid; gap: 10px; }
.rule { overflow: hidden; }
.rule[data-decision="rejected"] .rule-row { opacity: .7; }
.rule-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px 20px; padding: 16px 18px; align-items: center; }
.rule-main { display: grid; gap: 8px; min-width: 0; }
.rule-title { display: flex; gap: 10px; align-items: flex-start; border: 0; background: transparent; padding: 0; text-align: left; font-size: 15px; font-weight: 600; line-height: 1.4; }
.rule-title:hover span:last-child { text-decoration: underline; text-decoration-color: var(--line-strong); text-underline-offset: 3px; }
.rule-title .chev { flex: none; margin-top: 3px; transition: transform .15s; color: var(--muted); }
.rule-title[aria-expanded="true"] .chev { transform: rotate(90deg); }
.rule-title .idx { font: 500 12px/1.9 var(--font-mono); color: var(--muted); flex: none; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; padding-left: 50px; }
.chip { font: 500 11.5px/1 var(--font-mono); padding: 5px 7px; border-radius: 4px; background: var(--code); color: var(--ink-2); overflow-wrap: anywhere; }
.chip.good { background: var(--good-soft); color: var(--good); }
.chip.warn { background: var(--warn-soft); color: var(--warn); }
.chip.bad { background: var(--bad-soft); color: var(--bad); }
.rule-stats { display: flex; flex-wrap: wrap; gap: 4px 16px; padding-left: 50px; font-size: 12.5px; color: var(--muted); }
.rule-stats b { color: var(--ink); font-weight: 500; font-variant-numeric: tabular-nums; }
.meter { display: inline-flex; gap: 2px; vertical-align: -1px; margin-left: 6px; }
.meter i { width: 8px; height: 8px; border-radius: 2px; background: var(--line-strong); }
.meter i.on { background: var(--bar-strong); }
.decide { display: inline-flex; border: 1px solid var(--line-strong); border-radius: 6px; overflow: hidden; }
.decide button { display: inline-flex; align-items: center; gap: 6px; border: 0; background: var(--panel); padding: 7px 12px; font-size: 13px; font-weight: 500; color: var(--ink-2); }
.decide button:hover { background: var(--panel-2); }
.decide button + button { border-left: 1px solid var(--line-strong); }
.decide button[data-act="approve"][aria-pressed="true"] { background: var(--good-soft); color: var(--good); }
.decide button[data-act="reject"][aria-pressed="true"] { background: var(--bad-soft); color: var(--bad); }
.rule-detail { border-top: 1px solid var(--line); background: var(--panel-2); padding: 18px 18px 18px 68px; display: grid; gap: 14px; }
.rule-detail p { margin: 0; max-width: 72ch; }
.rule-detail code { overflow-wrap: anywhere; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
.metric { padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); display: grid; gap: 2px; }
.metric span { font-size: 11.5px; color: var(--muted); }
.metric b { font: 600 16px var(--font-sans); font-variant-numeric: tabular-nums; }
.example { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.example figure { margin: 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; min-width: 0; background: var(--panel); }
.example figcaption { font: 600 11px/1 var(--font-sans); text-transform: uppercase; letter-spacing: .08em; padding: 8px 12px; }
.example .before figcaption { background: var(--bad-soft); color: var(--bad); }
.example .after figcaption { background: var(--good-soft); color: var(--good); }
.example pre { margin: 0; padding: 12px; overflow-x: auto; font-size: 12.5px; line-height: 1.55; }
.example .only { grid-column: 1 / -1; }
.label-sm { display: block; margin-bottom: 6px; font-size: 11.5px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 600; }
.note { padding: 8px 12px; border-radius: 6px; background: var(--warn-soft); color: var(--warn); font-size: 13px; }
.links { display: flex; flex-wrap: wrap; gap: 6px; }
.links a, .links span { font: 500 12px var(--font-mono); padding: 4px 8px; border-radius: 4px; background: var(--panel); border: 1px solid var(--line); text-decoration: none; }
.empty { padding: 32px; text-align: center; color: var(--muted); border: 1px dashed var(--line-strong); border-radius: 10px; }

.aside-list { display: grid; gap: 10px; }
.aside { padding: 16px 18px; display: grid; gap: 8px; }
.aside .top { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between; }
.aside h3 { margin: 0; font-size: 14px; font-weight: 600; }
.aside p { margin: 0; color: var(--ink-2); }
.aside blockquote { margin: 0; padding-left: 12px; border-left: 2px solid var(--line-strong); color: var(--muted); font-style: italic; }

.checker { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.checker textarea { width: 100%; min-height: 360px; resize: vertical; padding: 12px; border: 1px solid var(--line-strong); border-radius: 8px; background: var(--panel-2); font: 12.5px/1.5 var(--font-mono); white-space: pre; overflow-wrap: normal; overflow-x: auto; }
.hint { padding: 14px 16px; display: grid; gap: 8px; }
.hint h3 { margin: 0; font-size: 14px; font-weight: 600; }
.hint p { margin: 0; color: var(--muted); }
.hint ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; }
.hint li { font: 12.5px/1.5 var(--font-mono); overflow-wrap: anywhere; }
.hint li b { color: var(--accent); font-weight: 500; }
.status-ok { padding: 14px 16px; border-radius: 8px; background: var(--good-soft); color: var(--good); }
.status-bad { padding: 14px 16px; border-radius: 8px; background: var(--bad-soft); color: var(--bad); }

.files { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 16px; align-items: start; }
.file-list { display: grid; gap: 2px; padding: 8px; }
.file-list button { text-align: left; border: 0; background: transparent; padding: 8px 10px; border-radius: 6px; font: 12.5px var(--font-mono); color: var(--ink-2); overflow-wrap: anywhere; }
.file-list button:hover { background: var(--panel-2); }
.file-list button[aria-current="true"] { background: var(--accent-soft); color: var(--ink); }
.file-view { overflow: hidden; }
.file-view header { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--line); }
.file-view header code { font-size: 12.5px; overflow-wrap: anywhere; }
.file-view .meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.file-view pre { margin: 0; padding: 16px; max-height: 640px; overflow: auto; font-size: 12.5px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.toast { position: fixed; bottom: calc(20px + env(safe-area-inset-bottom, 0px)); right: max(20px, env(safe-area-inset-right, 0px)); padding: 10px 14px; border-radius: 8px; background: var(--ink); color: var(--panel); font-size: 13px; box-shadow: var(--shadow); z-index: 20; }

@media (max-width: 900px) {
  .app { grid-template-columns: 1fr; }
  .side { position: static; height: auto; padding-block: 14px; padding-right: max(16px, env(safe-area-inset-right, 0px)); gap: 12px; }
  .repo, .side-foot { display: none; }
  .nav { display: flex; overflow-x: auto; gap: 4px; padding-bottom: 2px; }
  .nav [role="tab"] { width: auto; white-space: nowrap; }
  .main { padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 20px 40px; }
  .two, .checker, .files { grid-template-columns: 1fr; }
}
@media (max-width: 600px) {
  .rule-row { grid-template-columns: 1fr; }
  .chips, .rule-stats { padding-left: 0; }
  .rule-detail { padding-left: 18px; }
  .example { grid-template-columns: 1fr; }
  .bar-row { grid-template-columns: 1fr 40px; }
  .bar-row .track { grid-column: 1 / -1; grid-row: 2; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

SCRIPT = r"""
(function () {
  'use strict';
  var data = JSON.parse(document.getElementById('folklore-data').textContent);
  var rules = data.rules || [];
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  /* ---------- toast + copy ---------- */
  var toastTimer;
  function toast(msg) {
    var t = $('#toast');
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 2000);
  }
  function selectText(el) {
    var range = document.createRange(); range.selectNodeContents(el);
    var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
  }
  function copy(text, el) {
    var fallback = function () {
      if (el) selectText(el);
      toast('Text selected. Press Ctrl+C or Cmd+C to copy.');
    };
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) { fallback(); return; }
      navigator.clipboard.writeText(text).then(function () { toast('Copied to clipboard'); }, fallback);
    } catch (e) { fallback(); }
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy-target]');
    if (!btn) return;
    var el = document.getElementById(btn.getAttribute('data-copy-target'));
    if (el) copy(el.textContent, el);
  });

  /* ---------- tabs ---------- */
  var tabs = $$('[role="tab"]');
  function showTab(id, focus) {
    if (!document.getElementById('panel-' + id)) id = 'overview';
    tabs.forEach(function (t) {
      var on = t.dataset.tab === id;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      if (on && focus) t.focus();
    });
    $$('[role="tabpanel"]').forEach(function (p) { p.hidden = p.id !== 'panel-' + id; });
    try { history.replaceState(null, '', '#' + id); } catch (e) { /* sandboxed viewers */ }
  }
  tabs.forEach(function (t, i) {
    t.addEventListener('click', function () { showTab(t.dataset.tab); });
    t.addEventListener('keydown', function (e) {
      var dir = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
      if (!dir) return;
      e.preventDefault();
      showTab(tabs[(i + dir + tabs.length) % tabs.length].dataset.tab, true);
    });
  });
  document.addEventListener('click', function (e) {
    var go = e.target.closest('[data-goto]');
    if (!go) return;
    e.preventDefault();
    showTab(go.getAttribute('data-goto'));
    try { window.scrollTo(0, 0); } catch (err) { /* ignore */ }
  });

  /* ---------- decisions (kept in this browser only) ---------- */
  var KEY = 'folklore:' + data.repo + ':' + data.generated_at;
  var decisions = {};
  try { decisions = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { decisions = {}; }
  function saveDecisions() { try { localStorage.setItem(KEY, JSON.stringify(decisions)); } catch (e) { /* ignore */ } }
  function decisionOf(id) { return decisions[id] || 'undecided'; }
  function setDecision(id, value) {
    if (decisions[id] === value) delete decisions[id]; else decisions[id] = value;
    saveDecisions(); renderRules(); renderDecisions();
  }
  function renderDecisions() {
    var approved = rules.filter(function (r) { return decisionOf(r.id) === 'approved'; });
    var rejected = rules.filter(function (r) { return decisionOf(r.id) === 'rejected'; });
    var decided = approved.length + rejected.length;
    $$('[data-stat="approved"]').forEach(function (el) { el.textContent = approved.length; });
    $$('[data-stat="rejected"]').forEach(function (el) { el.textContent = rejected.length; });
    $$('[data-stat="undecided"]').forEach(function (el) { el.textContent = rules.length - decided; });
    $$('[data-stat="decided"]').forEach(function (el) { el.textContent = decided + ' of ' + plural(rules.length, 'rule') + ' reviewed'; });
    $$('.progress i').forEach(function (el) { el.style.width = (rules.length ? 100 * decided / rules.length : 0) + '%'; });
    var cmd = rejected.length
      ? 'folklore reject ' + rejected.map(function (r) { return r.id; }).join(' ') + ' && folklore analyze && folklore publish --agents-md'
      : 'folklore publish --agents-md';
    $$('[data-stat="command"]').forEach(function (el) { el.textContent = cmd; });
    $$('[data-stat="command-hint"]').forEach(function (el) {
      el.textContent = rejected.length
        ? 'Rejects ' + plural(rejected.length, 'rule') + ' for good, then rebuilds the skill without them. Run it in your repository.'
        : 'Nothing rejected yet. Run this in your repository to write the skill with every proposed rule.';
    });
  }
  $('#approve-rest').addEventListener('click', function () {
    var n = 0;
    rules.forEach(function (r) { if (!decisions[r.id]) { decisions[r.id] = 'approved'; n++; } });
    saveDecisions(); renderRules(); renderDecisions();
    toast(n ? 'Approved ' + plural(n, 'remaining rule') : 'Every rule already has a decision');
  });
  $('#reset-decisions').addEventListener('click', function () {
    decisions = {}; saveDecisions(); renderRules(); renderDecisions(); toast('Decisions cleared');
  });

  /* ---------- rules list ---------- */
  var state = { q: '', area: 'all', sort: 'evidence', status: 'all', checkable: false, open: {} };
  function meter(v) {
    var on = Math.max(1, Math.min(5, Math.round(v * 5))), out = '';
    for (var i = 0; i < 5; i++) out += '<i class="' + (i < on ? 'on' : '') + '"></i>';
    return '<span class="meter" role="img" aria-label="confidence ' + v.toFixed(2) + '">' + out + '</span>';
  }
  function scopeLabel(s) { return s === '**' ? 'any file' : s; }
  function sourceLinks(r) {
    return (r.sources || []).slice(0, 10).map(function (s) {
      var label = '#' + s.pr_number;
      if (!s.url) return '<span>' + esc(label) + '</span>';
      return '<a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer">' + esc(label) + '</a>';
    }).join('');
  }
  function exampleHTML(ex) {
    if (ex.good) {
      return '<div class="example"><figure class="before"><figcaption>Before review</figcaption><pre>' + esc(ex.bad) +
        '</pre></figure><figure class="after"><figcaption>After review</figcaption><pre>' + esc(ex.good) + '</pre></figure></div>' +
        (ex.sanitized ? '<div class="note">Folklore removed suspicious or excess lines from this quoted code.</div>' : '');
    }
    return '<div class="example"><figure class="before only"><figcaption>Flagged in review</figcaption><pre>' + esc(ex.bad) + '</pre></figure></div>';
  }
  function detailHTML(r) {
    var ev = r.evidence;
    return '<div class="rule-detail" id="detail-' + esc(r.id) + '">' +
      (r.rationale ? '<p><b>Why:</b> ' + esc(r.rationale) + '</p>' : '') +
      '<div class="metrics">' +
        '<div class="metric"><span>Comments</span><b>' + ev.comments + '</b></div>' +
        '<div class="metric"><span>Pull requests</span><b>' + ev.prs + '</b></div>' +
        '<div class="metric"><span>Maintainers</span><b>' + ev.reviewers + '</b></div>' +
        '<div class="metric"><span>Contributors corrected</span><b>' + ev.authors + '</b></div>' +
        '<div class="metric"><span>First raised</span><b>' + esc((ev.first_seen || '').slice(0, 10)) + '</b></div>' +
        '<div class="metric"><span>Last raised</span><b>' + esc((ev.last_seen || '').slice(0, 10)) + '</b></div>' +
      '</div>' +
      (r.examples || []).slice(0, 2).map(exampleHTML).join('') +
      (r.detect ? '<div><span class="label-sm">Detection pattern</span><code>' + esc(r.detect) + '</code></div>' : '') +
      ((r.seen_in || []).length ? '<div><span class="label-sm">Raised on</span>' + r.seen_in.map(function (p) { return '<code>' + esc(p) + '</code>'; }).join(', ') + '</div>' : '') +
      '<div><span class="label-sm">Source reviews</span><div class="links">' + sourceLinks(r) + '</div></div>' +
      '<div><span class="label-sm">Rule ID</span><div class="cmd"><code id="id-' + esc(r.id) + '">' + esc(r.id) + '</code>' +
      '<button type="button" class="btn ghost" data-copy-target="id-' + esc(r.id) + '">Copy</button></div></div>' +
    '</div>';
  }
  function ruleHTML(r) {
    var ev = r.evidence, d = decisionOf(r.id), open = !!state.open[r.id];
    var chips = r.scope.map(function (s) { return '<span class="chip">' + esc(scopeLabel(s)) + '</span>'; }).join('');
    if (r.detect) chips += '<span class="chip good">auto-checkable</span>';
    if (r.single_reviewer) chips += '<span class="chip warn">one maintainer</span>';
    if (d === 'approved') chips += '<span class="chip good">approved</span>';
    if (d === 'rejected') chips += '<span class="chip bad">rejected</span>';
    return '<article class="card rule" data-id="' + esc(r.id) + '" data-decision="' + d + '">' +
      '<div class="rule-row"><div class="rule-main">' +
        '<button type="button" class="rule-title" data-act="toggle" aria-expanded="' + open + '" aria-controls="detail-' + esc(r.id) + '">' +
          '<svg class="chev" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
          '<span class="idx">' + pad2(r._index) + '</span><span>' + esc(r.title) + '</span></button>' +
        '<div class="chips">' + chips + '</div>' +
        '<div class="rule-stats"><span><b>' + ev.comments + '</b> comments</span><span><b>' + ev.prs + '</b> PRs</span>' +
          '<span><b>' + ev.reviewers + '</b> ' + (ev.reviewers === 1 ? 'maintainer' : 'maintainers') + '</span>' +
          '<span>last <b>' + esc((ev.last_seen || '').slice(0, 10)) + '</b></span><span>confidence' + meter(r.confidence || 0.5) + '</span></div>' +
      '</div>' +
      '<div class="decide" role="group" aria-label="Decision">' +
        '<button type="button" data-act="approve" aria-pressed="' + (d === 'approved') + '">Approve</button>' +
        '<button type="button" data-act="reject" aria-pressed="' + (d === 'rejected') + '">Reject</button>' +
      '</div></div>' + (open ? detailHTML(r) : '') + '</article>';
  }
  rules.forEach(function (r, i) {
    r._index = i + 1;
    r._text = [r.title, r.rationale, (r.scope || []).join(' '), (r.keywords || []).join(' '), r.id].join(' ').toLowerCase();
  });
  function visibleRules() {
    var q = state.q.trim().toLowerCase();
    var list = rules.filter(function (r) {
      return (state.area === 'all' || r.area === state.area) &&
        (!q || r._text.indexOf(q) !== -1) &&
        (!state.checkable || !!r.detect) &&
        (state.status === 'all' || decisionOf(r.id) === state.status);
    });
    var key = {
      evidence: function (r) { return -(r.evidence.comments * 100 + r.evidence.prs); },
      recent: function (r) { return -(Date.parse(r.evidence.last_seen) || 0); },
      confidence: function (r) { return -(r.confidence || 0); },
      original: function (r) { return r._index; }
    }[state.sort];
    return list.slice().sort(function (a, b) { return (key(a) - key(b)) || (a._index - b._index); });
  }
  function renderRules() {
    var list = visibleRules();
    $('#rule-list').innerHTML = list.map(ruleHTML).join('');
    $('#rule-empty').hidden = list.length !== 0;
    $('#rule-count').textContent = 'Showing ' + list.length + ' of ' + plural(rules.length, 'rule');
    var allOpen = list.length && list.every(function (r) { return state.open[r.id]; });
    $('#expand-all').textContent = allOpen ? 'Collapse all' : 'Expand all';
  }
  $('#rule-list').addEventListener('click', function (e) {
    var btn = e.target.closest('[data-act]');
    if (!btn) return;
    var id = btn.closest('.rule').dataset.id, act = btn.dataset.act;
    if (act === 'toggle') {
      state.open[id] = !state.open[id]; renderRules();
      var again = document.querySelector('.rule[data-id="' + id + '"] .rule-title');
      if (again) again.focus();
    } else if (act === 'approve') setDecision(id, 'approved');
    else if (act === 'reject') setDecision(id, 'rejected');
  });
  $('#rule-search').addEventListener('input', function (e) { state.q = e.target.value; renderRules(); });
  $('#rule-area').addEventListener('change', function (e) { state.area = e.target.value; renderRules(); });
  $('#rule-sort').addEventListener('change', function (e) { state.sort = e.target.value; renderRules(); });
  $('#rule-checkable').addEventListener('change', function (e) { state.checkable = e.target.checked; renderRules(); });
  $$('#rule-status button').forEach(function (b) {
    b.addEventListener('click', function () {
      state.status = b.dataset.status;
      $$('#rule-status button').forEach(function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); });
      renderRules();
    });
  });
  $('#expand-all').addEventListener('click', function () {
    var list = visibleRules();
    var anyClosed = list.some(function (r) { return !state.open[r.id]; });
    list.forEach(function (r) { state.open[r.id] = anyClosed; });
    renderRules();
  });
  $('#clear-filters').addEventListener('click', function () {
    state.q = ''; state.area = 'all'; state.checkable = false; state.status = 'all';
    $('#rule-search').value = ''; $('#rule-area').value = 'all'; $('#rule-checkable').checked = false;
    $$('#rule-status button').forEach(function (o) { o.setAttribute('aria-pressed', o.dataset.status === 'all' ? 'true' : 'false'); });
    renderRules();
  });

  /* ---------- diff checker: same logic as `folklore check-diff` ---------- */
  var globCache = {};
  function globToRegex(pattern) {
    if (globCache[pattern]) return globCache[pattern];
    var out = '', i = 0;
    while (i < pattern.length) {
      if (pattern.substr(i, 3) === '**/') { out += '(?:.*/)?'; i += 3; }
      else if (pattern.substr(i, 2) === '**') { out += '.*'; i += 2; }
      else if (pattern[i] === '*') { out += '[^/]*'; i += 1; }
      else if (pattern[i] === '?') { out += '[^/]'; i += 1; }
      else { out += pattern[i].replace(/[.*+?^${}()|[\]\\\/-]/g, '\\$&'); i += 1; }
    }
    return (globCache[pattern] = new RegExp('^' + out + '$'));
  }
  function inScope(path, scope) { return scope.some(function (g) { return globToRegex(g).test(path); }); }
  function parseDiff(text) {
    var files = {}, current = null, newLine = 0;
    text.split(/\r?\n/).forEach(function (line) {
      if (line.indexOf('diff --git ') === 0) { current = null; return; }
      if (line.indexOf('+++ ') === 0) {
        var target = line.slice(4).trim();
        current = target === '/dev/null' ? null : target.replace(/^b\//, '');
        if (current && !files[current]) files[current] = [];
        return;
      }
      if (line.indexOf('--- ') === 0) return;
      if (line.indexOf('@@') === 0) { var m = /\+(\d+)/.exec(line); newLine = m ? parseInt(m[1], 10) : 0; return; }
      if (!current) return;
      if (line[0] === '+') { files[current].push({ line: newLine, text: line.slice(1) }); newLine += 1; }
      else if (line[0] === '-' || line[0] === '\\') { /* removed line, or "no newline" marker */ }
      else { newLine += 1; }
    });
    return files;
  }
  function checkDiff(text) {
    var files = parseDiff(text), hints = [];
    rules.forEach(function (r) {
      if (!r.detect || decisionOf(r.id) === 'rejected') return;
      var rx;
      try { rx = new RegExp(r.detect); } catch (e) { return; }
      var hits = [];
      Object.keys(files).forEach(function (path) {
        if (!inScope(path, r.scope)) return;
        files[path].forEach(function (l) { if (rx.test(l.text)) hits.push({ path: path, line: l.line, text: l.text }); });
      });
      if (hits.length) hints.push({ rule: r, hits: hits });
    });
    return { files: Object.keys(files).length, hints: hints };
  }
  function renderCheck() {
    var text = $('#diff-input').value, out = $('#diff-result');
    if (!text.trim()) {
      out.innerHTML = '<div class="empty">Paste the output of <code>git diff</code>, then press Check diff.</div>';
      return;
    }
    var res = checkDiff(text);
    if (!res.files) {
      out.innerHTML = '<div class="status-bad">No changed files found. Paste unified diff output, the kind <code>git diff</code> prints.</div>';
      return;
    }
    if (!res.hints.length) {
      out.innerHTML = '<div class="status-ok">' + plural(res.files, 'file') + ' checked. No known review conventions are broken.</div>';
      return;
    }
    out.innerHTML = '<div class="status-bad">' + plural(res.hints.length, 'convention') + ' broken in ' + plural(res.files, 'file') + ' checked.</div>' +
      res.hints.map(function (h) {
        return '<div class="card hint" data-rule="' + esc(h.rule.id) + '"><h3>' + esc(h.rule.title) + '</h3>' +
          (h.rule.rationale ? '<p>' + esc(h.rule.rationale) + '</p>' : '') +
          '<ul>' + h.hits.slice(0, 6).map(function (x) {
            return '<li><b>' + esc(x.path) + ':' + x.line + '</b> ' + esc(x.text.trim()) + '</li>';
          }).join('') + '</ul></div>';
      }).join('');
  }
  $('#diff-check').addEventListener('click', renderCheck);
  $('#diff-sample').addEventListener('click', function () { $('#diff-input').value = data.sample_diff; renderCheck(); });
  $('#diff-clear').addEventListener('click', function () { $('#diff-input').value = ''; renderCheck(); $('#diff-input').focus(); });
  $('#diff-input').addEventListener('keydown', function (e) { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') renderCheck(); });

  /* ---------- skill files ---------- */
  var files = (data.skill && data.skill.files) || [];
  function showFile(i) {
    var f = files[i]; if (!f) return;
    $('#file-name').textContent = f.path;
    $('#file-body').textContent = f.content;
    $('#file-lines').textContent = plural(f.content.split('\n').length, 'line');
    $$('#file-list button').forEach(function (b, j) { b.setAttribute('aria-current', j === i ? 'true' : 'false'); });
  }
  $$('#file-list button').forEach(function (b, i) { b.addEventListener('click', function () { showFile(i); }); });

  /* ---------- start ---------- */
  if ($('#diff-input')) $('#diff-input').value = data.sample_diff || '';
  renderRules(); renderDecisions(); renderCheck(); showFile(0);
  var initial = '';
  try { initial = (location.hash || '').slice(1); } catch (e) { initial = ''; }
  showTab(initial || 'overview');
  window.addEventListener('hashchange', function () {
    var id = '';
    try { id = (location.hash || '').slice(1); } catch (e) { id = ''; }
    if (id) showTab(id);
  });
  window.folklore = { checkDiff: checkDiff, parseDiff: parseDiff, globToRegex: globToRegex };
})();
"""

LOGO = (
    '<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">'
    '<rect x="3" y="3" width="18" height="18" rx="4" fill="var(--bar-strong)"/>'
    '<path d="M8 8h8M8 12h6M8 16h4" stroke="var(--side)" stroke-width="2" stroke-linecap="round"/>'
    "</svg>"
)


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _plural(n: int, word: str) -> str:
    return f"{n} {word if n == 1 else word + 's'}"


def skill_files(analysis: dict[str, Any]) -> dict[str, Any]:
    """Render the skill exactly as `folklore publish` would, and validate it."""
    rules = [Rule.from_dict(r) for r in analysis.get("rules", [])]
    if not rules:
        return {"name": "", "files": [], "problems": ["No rules to publish."]}
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = publish(
            rules, analysis.get("repo") or "project", tmp, analysis.get("generated_at")
        )
        problems = validate_skill(skill_dir)
        paths = [skill_dir / "SKILL.md", *sorted((skill_dir / "references").glob("*.md"))]
        paths.append(skill_dir / "assets" / "rules.json")
        files = [
            {
                "path": f"{skill_dir.name}/{p.relative_to(skill_dir).as_posix()}",
                "content": p.read_text(encoding="utf-8"),
            }
            for p in paths
        ]
        return {"name": skill_dir.name, "files": files, "problems": problems}


def sample_diff(analysis: dict[str, Any]) -> str:
    """A small diff that trips each auto-checkable rule once, plus one clean change."""
    chunks = []
    for rule in analysis.get("rules", []):
        bad = rule.get("detect_sample") or ""
        path = next(iter(rule.get("seen_in") or []), "")
        if not rule.get("detect") or not bad or not path:
            continue
        p = PurePosixPath(path)
        new_path = str(p.with_name(f"new-{p.name}"))
        chunks.append(
            f"diff --git a/{new_path} b/{new_path}\n--- a/{new_path}\n+++ b/{new_path}\n"
            f"@@ -1,2 +1,3 @@\n export function run() {{\n+{bad}\n }}\n"
        )
    chunks.append(
        "diff --git a/docs/notes.md b/docs/notes.md\n--- a/docs/notes.md\n+++ b/docs/notes.md\n"
        "@@ -1 +1,2 @@\n # Notes\n+This line breaks no convention.\n"
    )
    return "".join(chunks)


def _json_for_script(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text.replace("</", "<\\/").replace("<!--", "<\\!--")


def _bars(analysis: dict[str, Any]) -> str:
    stats = analysis["stats"]
    total = max(stats["feedback_total"], 1)
    clustered = sum(r["evidence"]["comments"] for r in analysis["rules"]) + sum(
        c["evidence"]["comments"] for c in analysis.get("other_clusters", [])
    )
    behind = sum(r["evidence"]["comments"] for r in analysis["rules"])
    rows = [
        ("Review feedback read", stats["feedback_total"], ""),
        ("Kept after filtering", stats["feedback_kept"], ""),
        ("In a recurring pattern", clustered, ""),
        ("Behind a proposed rule", behind, "strong"),
    ]
    out = ['<div class="bars">']
    for label, value, cls in rows:
        out.append(
            f'<div class="bar-row {cls}"><span>{_e(label)}</span>'
            f'<span class="track"><span class="fill" style="width:{100 * value / total:.1f}%"></span></span>'
            f'<span class="val">{value}</span></div>'
        )
    out.append("</div>")
    dropped = [f for f in analysis.get("funnel", []) if f["count"]]
    if dropped:
        out.append('<ul class="dropped" aria-label="Removed by each filter">')
        out += [f"<li>{_e(f['label'])}: <b>{f['count']}</b></li>" for f in dropped]
        out.append("</ul>")
    return "\n".join(out)


def _areas(rules: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for r in rules:
        counts[r["area"]] = counts.get(r["area"], 0) + 1
    if not counts:
        return '<p class="empty">No rules yet.</p>'
    top = max(counts.values())
    rows = [
        f'<div class="bar-row"><span class="mono">{_e(area)}</span>'
        f'<span class="track"><span class="fill" style="width:{100 * n / top:.0f}%"></span></span>'
        f'<span class="val">{n}</span></div>'
        for area, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return '<div class="bars">' + "".join(rows) + "</div>"


def _aside(cluster: dict[str, Any]) -> str:
    ev = cluster["evidence"]
    status = {"stale": "Stale", "discarded": "Set aside", "rejected": "Rejected"}.get(
        cluster["status"], cluster["status"].title()
    )
    chip = {"stale": "warn", "rejected": "bad"}.get(cluster["status"], "")
    keywords = ", ".join(cluster.get("keywords", [])[:4]) or "No clear topic"
    reason = cluster.get("reason", "")
    reason = reason[:1].upper() + reason[1:]
    sample = (cluster.get("samples") or [""])[0]
    return (
        '<article class="card aside"><div class="top">'
        f"<h3>{_e(keywords)}</h3>"
        f'<span class="chip {chip}">{_e(status)} · {_plural(ev["comments"], "comment")} · '
        f"{_plural(ev['prs'], 'PR')}</span></div>"
        f"<p>{_e(reason)}.</p>"
        + (f"<blockquote>{_e(sample)}</blockquote>" if sample else "")
        + "</article>"
    )


def _skill_panel(skill: dict[str, Any]) -> str:
    if not skill["files"]:
        return '<div class="empty">No rules yet, so there is no skill to show.</div>'
    buttons = "".join(
        f'<button type="button" aria-current="{"true" if i == 0 else "false"}">'
        f"{_e(f['path'].split('/', 1)[1])}</button>"
        for i, f in enumerate(skill["files"])
    )
    valid = (
        '<span class="chip good">Valid Agent Skill</span>'
        if not skill["problems"]
        else '<span class="chip bad">' + _e("; ".join(skill["problems"])) + "</span>"
    )
    return f"""
  <div class="files">
    <nav class="card file-list" id="file-list" aria-label="Skill files">{buttons}</nav>
    <div class="card file-view">
      <header><code id="file-name"></code><span class="meta">
        <span class="result-count" style="margin:0" id="file-lines"></span>{valid}
        <button type="button" class="btn" data-copy-target="file-body">Copy file</button></span></header>
      <pre id="file-body"></pre></div>
  </div>"""


def render_report(analysis: dict[str, Any], standalone: bool = True) -> str:
    repo = analysis.get("repo") or "this repository"
    stats = analysis["stats"]
    settings = analysis["settings"]
    rules = analysis["rules"]
    others = analysis.get("other_clusters", [])
    th = settings["thresholds"]
    skill = skill_files(analysis)
    checkable = sum(1 for r in rules if r.get("detect"))
    areas = sorted({r["area"] for r in rules})
    payload = {
        "repo": repo,
        "generated_at": analysis.get("generated_at", ""),
        "rules": rules,
        "skill": skill,
        "sample_diff": sample_diff(analysis),
    }

    tab_list = [
        ("overview", "Overview", ""),
        ("rules", "Rules", str(len(rules))),
        ("aside", "Set aside", str(len(others))),
        ("check", "Check a diff", ""),
        ("skill", "Skill file", str(len(skill["files"]))),
    ]
    nav = "".join(
        f'<button type="button" role="tab" id="tab-{tid}" data-tab="{tid}" aria-controls="panel-{tid}" '
        f'aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">'
        f"<span>{label}</span>"
        + (f'<span class="count">{count}</span>' if count else "")
        + "</button>"
        for i, (tid, label, count) in enumerate(tab_list)
    )
    area_options = '<option value="all">All areas</option>' + "".join(
        f'<option value="{_e(a)}">{_e(a)}</option>' for a in areas
    )

    overview = f"""
<section role="tabpanel" id="panel-overview" aria-labelledby="tab-overview">
  <div class="panel-head"><div><h1>Review folklore for {_e(repo)}</h1>
    <p>Conventions maintainers repeated in pull-request reviews. Approve the real ones,
    reject the rest, and publish them as an Agent Skill for contributors and their coding agents.</p></div>
    <button type="button" class="btn primary" data-goto="rules">Review {_plural(len(rules), "rule")}</button></div>
  <div class="grid">
    <div class="kpis">
      <div class="card kpi"><span class="label">Feedback read</span><span class="value">{stats["feedback_total"]}</span><span class="sub">from {_plural(stats["pull_requests"], "pull request")}</span></div>
      <div class="card kpi"><span class="label">Maintainer feedback kept</span><span class="value">{stats["feedback_kept"]}</span><span class="sub">from {_plural(stats["maintainers"], "maintainer")}</span></div>
      <div class="card kpi"><span class="label">Proposed rules</span><span class="value">{len(rules)}</span><span class="sub">from {_plural(stats["clusters"], "pattern")}</span></div>
      <div class="card kpi"><span class="label">Auto-checkable</span><span class="value">{checkable}</span><span class="sub">flagged by the PR bot</span></div>
      <div class="card kpi"><span class="label">Set aside</span><span class="value">{len(others)}</span><span class="sub">{stats["stale"]} stale</span></div>
    </div>
    <div class="two">
      <div class="card card-pad"><h2>What survived each filter</h2>{_bars(analysis)}</div>
      <div class="card card-pad"><h2>Your review</h2>
        <p class="decision-stats"><span><b data-stat="approved">0</b>approved</span>
          <span><b data-stat="rejected">0</b>rejected</span><span><b data-stat="undecided">0</b>to review</span></p>
        <div class="cmd"><code id="cmd-overview" data-stat="command"></code>
          <button type="button" class="btn ghost" data-copy-target="cmd-overview">Copy</button></div>
        <p class="hint-text" data-stat="command-hint"></p>
        <div class="row-actions"><button type="button" class="btn" data-goto="rules">Open rules</button>
          <button type="button" class="btn" data-goto="check">Try the diff checker</button></div>
      </div>
    </div>
    <div class="two">
      <div class="card card-pad"><h2>Rules by area</h2>{_areas(rules)}</div>
      <div class="card card-pad"><h2>About this run</h2><dl class="facts">
        <dt>Generated</dt><dd class="num">{_e(analysis.get("generated_at", "")[:10])}</dd>
        <dt>Rule needs</dt><dd>{th["min_comments"]}+ comments, {th["min_prs"]}+ PRs, {th["min_authors"]}+ contributors</dd>
        <dt>Embedder</dt><dd>{_e(settings["embedder"])}</dd>
        <dt>Distiller</dt><dd>{_e(settings["distiller"])}</dd>
        <dt>Skill</dt><dd><code>{_e(skill["name"] or "none")}</code></dd>
        <dt>Tool</dt><dd>{_e(analysis.get("tool", "folklore"))}</dd></dl></div>
    </div>
  </div>
</section>"""

    rules_panel = f"""
<section role="tabpanel" id="panel-rules" aria-labelledby="tab-rules" hidden>
  <div class="panel-head"><div><h1>Proposed rules</h1>
    <p>Open a rule to see its evidence, a real example and the reviews it came from.
    Your decisions are saved in this browser.</p></div>
    <div class="row-actions" style="margin:0">
      <button type="button" class="btn" id="expand-all">Expand all</button>
      <button type="button" class="btn" id="approve-rest">Approve remaining</button>
      <button type="button" class="btn ghost" id="reset-decisions">Reset decisions</button></div></div>
  <div class="toolbar">
    <input type="search" id="rule-search" placeholder="Search titles, scopes, keywords" aria-label="Search rules">
    <div class="field"><label for="rule-area">Area</label><select id="rule-area">{area_options}</select></div>
    <div class="field"><label for="rule-sort">Sort</label><select id="rule-sort">
      <option value="evidence">Most evidence</option><option value="recent">Most recent</option>
      <option value="confidence">Highest confidence</option><option value="original">Report order</option></select></div>
  </div>
  <div class="toolbar">
    <div class="seg" id="rule-status" role="group" aria-label="Filter by decision">
      <button type="button" data-status="all" aria-pressed="true">All</button>
      <button type="button" data-status="undecided" aria-pressed="false">To review</button>
      <button type="button" data-status="approved" aria-pressed="false">Approved</button>
      <button type="button" data-status="rejected" aria-pressed="false">Rejected</button></div>
    <label class="check" for="rule-checkable"><input type="checkbox" id="rule-checkable"> Auto-checkable only</label>
  </div>
  <p class="result-count" id="rule-count" aria-live="polite"></p>
  <div class="rule-list" id="rule-list"></div>
  <div class="empty" id="rule-empty" hidden>No rules match these filters.
    <button type="button" class="btn" id="clear-filters" style="margin-left:8px">Clear filters</button></div>
  <div class="card card-pad" style="margin-top:16px"><h2>Next step</h2>
    <div class="cmd"><code id="cmd-rules" data-stat="command"></code>
      <button type="button" class="btn ghost" data-copy-target="cmd-rules">Copy</button></div>
    <p class="hint-text" data-stat="command-hint"></p></div>
</section>"""

    aside_items = "".join(_aside(c) for c in others) or (
        '<div class="empty">Every recurring pattern became a rule.</div>'
    )
    aside_panel = f"""
<section role="tabpanel" id="panel-aside" aria-labelledby="tab-aside" hidden>
  <div class="panel-head"><div><h1>Set aside</h1>
    <p>Feedback that came up more than once but did not become a rule, and the reason.
    Nothing here reaches the skill.</p></div></div>
  <div class="aside-list">{aside_items}</div>
</section>"""

    check_panel = """
<section role="tabpanel" id="panel-check" aria-labelledby="tab-check" hidden>
  <div class="panel-head"><div><h1>Check a diff</h1>
    <p>Paste the output of <code>git diff</code> to see which auto-checkable conventions it breaks.
    This runs the same check as <code>folklore check-diff</code> and the PR bot, in your browser.
    Rejected rules are skipped. An example diff is loaded to start.</p></div></div>
  <div class="checker">
    <div class="grid" style="gap:10px">
      <label class="label-sm" for="diff-input" style="margin:0">Unified diff</label>
      <textarea id="diff-input" spellcheck="false" placeholder="diff --git a/src/app.ts b/src/app.ts"></textarea>
      <div class="row-actions" style="margin:0">
        <button type="button" class="btn primary" id="diff-check">Check diff</button>
        <button type="button" class="btn" id="diff-sample">Load example</button>
        <button type="button" class="btn ghost" id="diff-clear">Clear</button></div>
    </div>
    <div class="grid" style="gap:10px" id="diff-result" aria-live="polite"></div>
  </div>
</section>"""

    skill_panel = f"""
<section role="tabpanel" id="panel-skill" aria-labelledby="tab-skill" hidden>
  <div class="panel-head"><div><h1>Skill file</h1>
    <p>What <code>folklore publish</code> writes to <code>skills/{_e(skill["name"])}/</code>. Coding agents load
    <code>SKILL.md</code> first and open a reference file only when they need it.</p></div></div>
  {_skill_panel(skill)}
</section>"""

    body = f"""
<div class="app">
  <aside class="side">
    <div class="brand">{LOGO}<span>Folklore</span></div>
    <div class="repo"><span>Repository</span><b>{_e(repo)}</b></div>
    <div class="nav" role="tablist" aria-label="Sections" aria-orientation="vertical">{nav}</div>
    <div class="side-foot"><span data-stat="decided"></span><div class="progress"><i></i></div>
      <span>Quoted code is shown as data. No contributor names are included.</span></div>
  </aside>
  <main class="main">
    <noscript><p class="notice">This dashboard needs JavaScript for filtering, decisions and the diff checker.</p></noscript>
    {overview}{rules_panel}{aside_panel}{check_panel}{skill_panel}
  </main>
</div>
<div class="toast" id="toast" role="status" hidden></div>
<script type="application/json" id="folklore-data">{_json_for_script(payload)}</script>
<script>{SCRIPT}</script>"""

    head = "\n".join(
        [
            f"<title>{_e(repo.split('/')[-1])} folklore</title>",
            '<meta name="claude:viewport-fit-sides" content="cover">',
            '<link rel="preconnect" href="https://fonts.googleapis.com">',
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
            f'<link rel="stylesheet" href="{FONTS}">',
            f"<style>{CSS}</style>",
        ]
    )
    if not standalone:
        return head + "\n" + body
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{head}\n</head>\n<body>{body}\n</body>\n</html>\n"
    )


def write_report(analysis: dict[str, Any], path: str | Path, standalone: bool = True) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(analysis, standalone=standalone), encoding="utf-8")
    return path
