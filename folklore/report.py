"""The Folklore report: one self-contained HTML page a maintainer reviews before merging.

The page is rendered server-side (it reads fine with JavaScript off); a few lines of script
add search, area filters and copy buttons. The palette is deliberately free of blue.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

FONTS = (
    "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&"
    "family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&"
    "family=IBM+Plex+Serif:wght@500;600&display=swap"
)

CSS = """
/* Layout: one ledger column. Summary sieve first, then each proposed rule as an entry,
   then the clusters Folklore set aside and why. */
:root {
  --paper: #eef0e8;
  --surface: #f8f9f4;
  --ink: #22251e;
  --muted: #5b6153;
  --line: #d3d8c9;
  --accent: #8f6210;
  --accent-soft: #f0e2bf;
  --bad: #963726;
  --bad-bg: #f5e3dd;
  --good: #3b6431;
  --good-bg: #e1ecd9;
  --warn: #7e5300;
  --warn-bg: #f3e5c0;
  --code-bg: #e5e8de;
  --bar: #c9b27a;
  --bar-strong: #8f6210;
  --font-display: "IBM Plex Serif", Georgia, "Times New Roman", serif;
  --font-body: "IBM Plex Sans", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #151811; --surface: #1d2119; --ink: #e3e6da; --muted: #a2a995; --line: #343a2d;
    --accent: #e2ae4d; --accent-soft: #3a301c; --bad: #ec9583; --bad-bg: #3a1f1a;
    --good: #a2d08c; --good-bg: #1e2f18; --warn: #e8bb5f; --warn-bg: #3a2e13;
    --code-bg: #252a20; --bar: #6b5a32; --bar-strong: #e2ae4d; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #151811; --surface: #1d2119; --ink: #e3e6da; --muted: #a2a995; --line: #343a2d;
  --accent: #e2ae4d; --accent-soft: #3a301c; --bad: #ec9583; --bad-bg: #3a1f1a;
  --good: #a2d08c; --good-bg: #1e2f18; --warn: #e8bb5f; --warn-bg: #3a2e13;
  --code-bg: #252a20; --bar: #6b5a32; --bar-strong: #e2ae4d; color-scheme: dark;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 15px/1.6 var(--font-body);
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
}
::selection { background: var(--accent-soft); color: var(--ink); }
a { color: var(--accent); text-underline-offset: 2px; }
a:visited { color: var(--accent); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
input, button { accent-color: var(--accent); font: inherit; }
.page { max-width: 940px; margin: 0 auto; padding-block: 40px 64px; display: grid; gap: 40px; }
header.top { display: grid; gap: 10px; }
.eyebrow { font: 500 12px/1 var(--font-mono); letter-spacing: .12em; text-transform: uppercase; color: var(--accent); }
h1 { font: 600 clamp(28px, 5vw, 40px)/1.15 var(--font-display); margin: 0; text-wrap: balance; overflow-wrap: anywhere; }
h2 { font: 600 22px/1.3 var(--font-display); margin: 0; text-wrap: balance; }
h3 { font: 600 19px/1.35 var(--font-display); margin: 0; text-wrap: balance; }
.lede { margin: 0; color: var(--muted); max-width: 66ch; }
.meta { display: flex; flex-wrap: wrap; gap: 6px 18px; color: var(--muted); font-size: 13px; }
.meta b { color: var(--ink); font-weight: 500; }
code, .mono { font-family: var(--font-mono); font-size: .88em; }
section { display: grid; gap: 18px; min-width: 0; }
.section-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px 16px; border-bottom: 1px solid var(--line); padding-bottom: 10px; }
.section-head p { margin: 0; color: var(--muted); font-size: 14px; }

/* Sieve: how much review feedback survives each step */
.sieve { display: grid; gap: 10px; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 20px; }
.sieve-row { display: grid; grid-template-columns: minmax(150px, 210px) 1fr 48px; gap: 12px; align-items: center; }
.sieve-row .label { font-size: 14px; }
.sieve-row .track { height: 14px; background: var(--code-bg); border-radius: 2px; overflow: hidden; }
.sieve-row .fill { height: 100%; background: var(--bar); }
.sieve-row.final .fill { background: var(--bar-strong); }
.sieve-row .num { font: 500 15px var(--font-mono); text-align: right; font-variant-numeric: tabular-nums; }
.dropped { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 6px 0 0; padding: 12px 0 0; border-top: 1px dashed var(--line); list-style: none; font-size: 13px; color: var(--muted); }
.dropped li span { font-family: var(--font-mono); color: var(--ink); font-variant-numeric: tabular-nums; }

/* Toolbar */
.toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.toolbar input[type="search"] { flex: 1 1 220px; min-width: 0; padding: 8px 12px; border: 1px solid var(--line); border-radius: 4px; background: var(--surface); color: var(--ink); }
.chip-btn { padding: 6px 12px; border: 1px solid var(--line); border-radius: 999px; background: transparent; color: var(--ink); cursor: pointer; font-size: 13px; }
.chip-btn[aria-pressed="true"] { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.toolbar label { display: inline-flex; gap: 6px; align-items: center; font-size: 13px; color: var(--muted); cursor: pointer; }

/* Rules */
.rules { display: grid; gap: 0; list-style: none; margin: 0; padding: 0; counter-reset: rule; }
.rule { display: grid; gap: 12px; padding: 26px 0; border-bottom: 1px solid var(--line); min-width: 0; }
.rule:first-child { padding-top: 6px; }
.rule-head { display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; align-items: baseline; }
.rule-head .idx { font: 500 13px var(--font-mono); color: var(--muted); font-variant-numeric: tabular-nums; }
.rule-head h3 { grid-column: 2; }
.tags { grid-column: 2; display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.tag { font: 500 12px/1 var(--font-mono); padding: 5px 8px; border-radius: 3px; background: var(--code-bg); color: var(--ink); overflow-wrap: anywhere; }
.tag.check { background: var(--good-bg); color: var(--good); }
.tag.warn { background: var(--warn-bg); color: var(--warn); }
.rule-body { display: grid; gap: 12px; padding-left: calc(2ch + 14px); min-width: 0; }
.why { margin: 0; max-width: 68ch; }
.why b { font-weight: 600; }
.evidence { display: flex; flex-wrap: wrap; gap: 4px 18px; margin: 0; padding: 0; list-style: none; font-size: 13px; color: var(--muted); }
.evidence span { font: 500 14px var(--font-mono); color: var(--ink); font-variant-numeric: tabular-nums; }
.confidence { display: inline-flex; gap: 3px; vertical-align: middle; margin-left: 4px; }
.confidence i { width: 10px; height: 10px; border-radius: 2px; background: var(--line); }
.confidence i.on { background: var(--bar-strong); }
.example { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; min-width: 0; }
.example figure { margin: 0; min-width: 0; border-radius: 4px; overflow: hidden; border: 1px solid var(--line); }
.example figcaption { font: 500 11px/1 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; padding: 8px 10px; }
.example .before figcaption { background: var(--bad-bg); color: var(--bad); }
.example .after figcaption { background: var(--good-bg); color: var(--good); }
.example pre { margin: 0; padding: 10px; background: var(--surface); overflow-x: auto; font: 13px/1.5 var(--font-mono); }
.example .only { grid-column: 1 / -1; }
.note { font-size: 13px; color: var(--warn); background: var(--warn-bg); padding: 6px 10px; border-radius: 3px; margin: 0; }
.detect { font-size: 13px; color: var(--muted); margin: 0; overflow-wrap: anywhere; }
.sources { font-size: 13px; color: var(--muted); margin: 0; display: flex; flex-wrap: wrap; gap: 4px 10px; }
.sources a { font-family: var(--font-mono); }
.actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 13px; color: var(--muted); }
.copy { display: inline-flex; align-items: center; gap: 8px; padding: 5px 6px 5px 10px; border: 1px solid var(--line); border-radius: 4px; background: var(--surface); max-width: 100%; }
.copy code { overflow-wrap: anywhere; }
.copy button { border: 0; background: var(--code-bg); color: var(--ink); border-radius: 3px; padding: 3px 8px; cursor: pointer; font-size: 12px; }
.copy button:hover { background: var(--accent-soft); }
.empty { padding: 24px; text-align: center; color: var(--muted); border: 1px dashed var(--line); border-radius: 6px; }

/* Set-aside clusters */
.aside-list { display: grid; gap: 12px; list-style: none; margin: 0; padding: 0; }
.aside-item { display: grid; gap: 6px; padding: 14px 16px; background: var(--surface); border-left: 3px solid var(--line); min-width: 0; }
.aside-item.stale { border-left-color: var(--warn); }
.aside-item .status { font: 500 11px/1 var(--font-mono); letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
.aside-item.stale .status { color: var(--warn); }
.aside-item p { margin: 0; font-size: 14px; }
.aside-item q { color: var(--muted); font-style: italic; }
.how { display: grid; gap: 10px; font-size: 14px; }
.how ol { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
footer { color: var(--muted); font-size: 13px; border-top: 1px solid var(--line); padding-top: 16px; }

@media (max-width: 640px) {
  .sieve-row { grid-template-columns: 1fr 44px; }
  .sieve-row .track { grid-column: 1 / -1; grid-row: 2; }
  .example { grid-template-columns: 1fr; }
  .rule-body { padding-left: 0; }
  .rule-head { grid-template-columns: 1fr; }
  .rule-head h3, .tags { grid-column: 1; }
}
@media (prefers-reduced-motion: no-preference) {
  .sieve-row .fill { transition: width .4s ease-out; }
}
"""

SCRIPT = """
(function () {
  var search = document.getElementById('rule-search');
  var checkable = document.getElementById('only-checkable');
  var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-area-filter]'));
  var rules = Array.prototype.slice.call(document.querySelectorAll('.rule'));
  var empty = document.getElementById('no-match');
  var area = 'all';
  function apply() {
    var q = (search && search.value || '').trim().toLowerCase();
    var shown = 0;
    rules.forEach(function (r) {
      var ok = (area === 'all' || r.dataset.area === area)
        && (!q || r.dataset.text.indexOf(q) !== -1)
        && (!checkable || !checkable.checked || r.dataset.checkable === 'yes');
      r.hidden = !ok;
      if (ok) shown++;
    });
    if (empty) empty.hidden = shown !== 0;
  }
  buttons.forEach(function (b) {
    b.addEventListener('click', function () {
      area = b.dataset.areaFilter;
      buttons.forEach(function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); });
      apply();
    });
  });
  if (search) search.addEventListener('input', apply);
  if (checkable) checkable.addEventListener('change', apply);
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]');
    if (!btn) return;
    var text = btn.getAttribute('data-copy');
    var done = function () { btn.textContent = 'Copied'; setTimeout(function () { btn.textContent = 'Copy'; }, 1400); };
    var fallback = function () {
      var code = btn.parentNode.querySelector('code');
      var range = document.createRange(); range.selectNodeContents(code);
      var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
      btn.textContent = 'Press Ctrl+C';
    };
    try {
      navigator.clipboard.writeText(text).then(done, fallback);
    } catch (err) { fallback(); }
  });
})();
"""


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _plural(n: int, word: str, plural: str | None = None) -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _sieve(analysis: dict[str, Any]) -> str:
    stats = analysis["stats"]
    total = max(stats["feedback_total"], 1)
    clustered = sum(r["evidence"]["comments"] for r in analysis["rules"]) + sum(
        c["evidence"]["comments"] for c in analysis["other_clusters"]
    )
    behind_rules = sum(r["evidence"]["comments"] for r in analysis["rules"])
    rows = [
        ("Review feedback read", stats["feedback_total"], ""),
        ("Kept after filtering", stats["feedback_kept"], ""),
        ("Part of a recurring pattern", clustered, ""),
        ("Behind a proposed rule", behind_rules, "final"),
    ]
    out = [
        '<div class="sieve" role="img" aria-label="How much review feedback survived each step">'
    ]
    for label, value, cls in rows:
        pct = 100 * value / total
        out.append(
            f'<div class="sieve-row {cls}"><span class="label">{_e(label)}</span>'
            f'<span class="track"><span class="fill" style="width:{pct:.1f}%;display:block"></span></span>'
            f'<span class="num">{value}</span></div>'
        )
    dropped = [f for f in analysis["funnel"] if f["count"]]
    if dropped:
        out.append('<ul class="dropped" aria-label="Feedback removed by each filter">')
        for f in dropped:
            out.append(f"<li>{_e(f['label'])}: <span>{f['count']}</span></li>")
        out.append("</ul>")
    out.append("</div>")
    return "\n".join(out)


def _confidence(value: float) -> str:
    on = max(1, min(5, round(value * 5)))
    cells = "".join(f'<i class="{"on" if i < on else ""}"></i>' for i in range(5))
    return f'<span class="confidence" aria-label="confidence {value:.2f}">{cells}</span>'


def _copy(command: str) -> str:
    return (
        f'<span class="copy"><code>{_e(command)}</code>'
        f'<button type="button" data-copy="{_e(command)}">Copy</button></span>'
    )


def _rule(index: int, rule: dict[str, Any]) -> str:
    ev = rule["evidence"]
    tags = [
        f'<span class="tag">{_e(s)}</span>' if s != "**" else '<span class="tag">any file</span>'
        for s in rule["scope"]
    ]
    if rule.get("detect"):
        tags.append('<span class="tag check">checked automatically</span>')
    if rule.get("single_reviewer"):
        tags.append('<span class="tag warn">one maintainer only</span>')
    search_text = " ".join(
        [
            rule["title"],
            rule.get("rationale", ""),
            " ".join(rule["scope"]),
            " ".join(rule.get("keywords", [])),
        ]
    ).lower()
    parts = [
        f'<li class="rule" id="{_e(rule["id"])}" data-area="{_e(rule["area"])}" '
        f'data-checkable="{"yes" if rule.get("detect") else "no"}" data-text="{_e(search_text)}">',
        '<div class="rule-head">',
        f'<span class="idx">{index:02d}</span><h3>{_e(rule["title"])}</h3>',
        f'<div class="tags">{"".join(tags)}</div>',
        "</div>",
        '<div class="rule-body">',
    ]
    if rule.get("rationale"):
        parts.append(f'<p class="why"><b>Why:</b> {_e(rule["rationale"])}</p>')
    last = (ev.get("last_seen") or "")[:10]
    parts.append(
        '<ul class="evidence">'
        f"<li><span>{ev['comments']}</span> comments</li>"
        f"<li><span>{ev['prs']}</span> pull requests</li>"
        f"<li><span>{ev['reviewers']}</span> {'maintainer' if ev['reviewers'] == 1 else 'maintainers'}</li>"
        f"<li><span>{ev['authors']}</span> contributors corrected</li>"
        f"<li>last raised <span>{_e(last)}</span></li>"
        f"<li>confidence {_confidence(rule.get('confidence', 0.5))}</li>"
        "</ul>"
    )
    for example in rule.get("examples", [])[:2]:
        if example.get("good"):
            parts.append(
                '<div class="example">'
                f'<figure class="before"><figcaption>Before</figcaption><pre>{_e(example["bad"])}</pre></figure>'
                f'<figure class="after"><figcaption>After review</figcaption><pre>{_e(example["good"])}</pre></figure>'
                "</div>"
            )
        else:
            parts.append(
                '<div class="example">'
                f'<figure class="before only"><figcaption>Flagged in review</figcaption><pre>{_e(example["bad"])}</pre></figure>'
                "</div>"
            )
        if example.get("sanitized"):
            parts.append(
                '<p class="note">Folklore removed suspicious or excess lines from this quoted code '
                "before using it.</p>"
            )
    if rule.get("detect"):
        parts.append(
            f'<p class="detect">Flags added lines matching <code>{_e(rule["detect"])}</code></p>'
        )
    if rule.get("seen_in") and not rule.get("examples"):
        files = ", ".join(f"<code>{_e(p)}</code>" for p in rule["seen_in"])
        parts.append(f'<p class="detect">Raised on {files}</p>')
    links = []
    for src in rule.get("sources", [])[:8]:
        label = f"#{src['pr_number']}"
        links.append(
            f'<a href="{_e(src["url"])}" target="_blank" rel="noopener noreferrer">{_e(label)}</a>'
            if src.get("url")
            else f"<span>{_e(label)}</span>"
        )
    parts.append(f'<p class="sources">Sources: {" ".join(links)}</p>')
    parts.append(
        '<div class="actions">Not a real rule? ' + _copy(f"folklore reject {rule['id']}") + "</div>"
    )
    parts += ["</div>", "</li>"]
    return "\n".join(parts)


def _aside(cluster: dict[str, Any]) -> str:
    ev = cluster["evidence"]
    status = {"stale": "Stale", "discarded": "Set aside", "rejected": "Rejected"}.get(
        cluster["status"], cluster["status"].title()
    )
    keywords = ", ".join(cluster.get("keywords", [])[:4]) or "no clear topic"
    sample = cluster["samples"][0] if cluster.get("samples") else ""
    return (
        f'<li class="aside-item {_e(cluster["status"])}">'
        f'<span class="status">{_e(status)} · {_plural(ev["comments"], "comment")}, '
        f"{_plural(ev['prs'], 'PR')}</span>"
        f"<p><b>{_e(keywords)}</b>. {_e(cluster['reason'][:1].upper() + cluster['reason'][1:])}.</p>"
        + (f"<p><q>{_e(sample)}</q></p>" if sample else "")
        + "</li>"
    )


def render_report(analysis: dict[str, Any], standalone: bool = True) -> str:
    repo = analysis.get("repo") or "this repository"
    stats = analysis["stats"]
    settings = analysis["settings"]
    rules = analysis["rules"]
    areas = sorted({r["area"] for r in rules})
    generated = analysis.get("generated_at", "")[:10]
    th = settings["thresholds"]

    body: list[str] = [
        '<div class="page">',
        '<header class="top">',
        '<span class="eyebrow">Folklore report</span>',
        f"<h1>{_e(repo)}</h1>",
        '<p class="lede">These are the conventions maintainers kept repeating in pull-request '
        "reviews. Read each one, reject what isn't a real rule, and Folklore will publish the "
        "rest as an Agent Skill that contributors and their coding agents can load.</p>",
        '<div class="meta">'
        f"<span>Generated <b>{_e(generated)}</b></span>"
        f"<span><b>{_plural(stats['pull_requests'], 'pull request')}</b> read</span>"
        f"<span><b>{_plural(stats['maintainers'], 'maintainer')}</b> quoted</span>"
        f"<span>Rule needs <b>{th['min_comments']}+ comments</b> across "
        f"<b>{th['min_prs']}+ PRs</b> and <b>{th['min_authors']}+ contributors</b></span>"
        f"<span>Embedder <b>{_e(settings['embedder'])}</b>, distiller <b>{_e(settings['distiller'])}</b></span>"
        "</div>",
        "</header>",
        '<section aria-labelledby="sieve-h">',
        '<div class="section-head"><h2 id="sieve-h">What survived the sieve</h2>'
        "<p>Most review comments are not rules. Here is where they dropped out.</p></div>",
        _sieve(analysis),
        "</section>",
        '<section aria-labelledby="rules-h">',
        f'<div class="section-head"><h2 id="rules-h">{_plural(len(rules), "proposed rule")}</h2>'
        "<p>Ordered by how recently and how often maintainers asked.</p></div>",
    ]
    if rules:
        body.append('<div class="toolbar">')
        body.append(
            '<input type="search" id="rule-search" placeholder="Search rules, scopes, keywords" '
            'aria-label="Search rules">'
        )
        body.append(
            '<button type="button" class="chip-btn" data-area-filter="all" aria-pressed="true">All areas</button>'
        )
        for area in areas:
            body.append(
                f'<button type="button" class="chip-btn" data-area-filter="{_e(area)}" '
                f'aria-pressed="false">{_e(area)}</button>'
            )
        body.append(
            '<label for="only-checkable"><input type="checkbox" id="only-checkable"> '
            "Checked automatically</label>"
        )
        body.append("</div>")
        body.append('<ol class="rules">')
        body += [_rule(i, r) for i, r in enumerate(rules, 1)]
        body.append("</ol>")
        body.append('<p class="empty" id="no-match" hidden>No rule matches these filters.</p>')
    else:
        body.append(
            '<p class="empty">No pattern was strong enough to become a rule. Try reading more '
            "pull requests (<code>--max-prs</code>) or lowering the thresholds in "
            "<code>.folklore.yml</code>.</p>"
        )
    body.append("</section>")

    others = analysis.get("other_clusters", [])
    if others:
        body += [
            '<section aria-labelledby="aside-h">',
            '<div class="section-head"><h2 id="aside-h">Patterns set aside</h2>'
            "<p>Recurring feedback that did not become a rule, and the reason.</p></div>",
            '<ul class="aside-list">',
            *[_aside(c) for c in others],
            "</ul>",
            "</section>",
        ]

    body += [
        '<section aria-labelledby="next-h" class="how">',
        '<div class="section-head"><h2 id="next-h">Next steps</h2></div>',
        "<ol>",
        f"<li>Reject anything that isn't a real convention: {_copy('folklore reject <rule-id>')}</li>",
        f"<li>Write the skill and open it as a pull request for review: {_copy('folklore publish --agents-md')}</li>",
        "<li>Optionally add the pre-review GitHub Action so new contributors see these hints "
        "before a human reviewer does.</li>",
        "</ol>",
        "</section>",
        f"<footer>Made by {_e(analysis.get('tool', 'folklore'))}. Quoted code comes from pull "
        "requests and is shown as data. Contributor names are never included.</footer>",
        "</div>",
    ]

    head = [
        f"<title>{_e(repo)} folklore</title>",
        '<meta name="claude:viewport-fit-sides" content="cover">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        f'<link rel="stylesheet" href="{FONTS}">',
        f"<style>{CSS}</style>",
    ]
    content = "\n".join(head + body + [f"<script>{SCRIPT}</script>"])
    if not standalone:
        return content
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + "\n".join(head)
        + "\n</head>\n<body>\n"
        + "\n".join(body)
        + f"\n<script>{SCRIPT}</script>\n</body>\n</html>\n"
    )


def write_report(analysis: dict[str, Any], path: str | Path, standalone: bool = True) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(analysis, standalone=standalone), encoding="utf-8")
    return path
