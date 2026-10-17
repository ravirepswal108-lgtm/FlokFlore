"""Drive the dashboard in a real browser and check that every feature works.

Skipped automatically when Playwright or its Chromium build is not installed:
    pip install playwright && python -m playwright install chromium
"""

import json

import pytest

from folklore.analyze import rules_from_analysis
from folklore.config import Config
from folklore.enforce import check, parse_unified_diff
from folklore.report import sample_diff, write_report

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # browser binary missing
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


@pytest.fixture()
def page(browser, fixture_analysis, tmp_path):
    analysis = dict(fixture_analysis)
    analysis["rules"] = [dict(r) for r in fixture_analysis["rules"]]
    analysis["rules"][-1]["title"] = '<img src=x onerror="window.pwned=1"> Untrusted title.'
    path = write_report(analysis, tmp_path / "report.html")
    context = browser.new_context()
    pg = context.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    pg.goto(path.as_uri())
    pg.errors = errors
    pg.rules = analysis["rules"]
    yield pg
    assert not errors, errors
    context.close()


def visible_titles(pg):
    return pg.locator("#rule-list .rule-title span:last-child").all_inner_texts()


def test_tabs_and_deep_links(page):
    assert page.locator("#panel-overview").is_visible()
    page.click("#tab-rules")
    assert (
        page.locator("#panel-rules").is_visible()
        and not page.locator("#panel-overview").is_visible()
    )
    page.keyboard.press("ArrowDown")
    assert page.locator("#panel-aside").is_visible()
    page.click("#tab-overview")
    page.locator("#panel-overview [data-goto='check']").click()
    assert page.locator("#panel-check").is_visible()
    page.goto(page.url.split("#")[0] + "#skill")  # same document, hash change only
    assert page.locator("#panel-skill").is_visible()


def test_untrusted_titles_are_text(page):
    page.click("#tab-rules")
    assert any("<img" in t for t in visible_titles(page))
    assert page.evaluate("window.pwned") is None


def test_search_area_sort_and_checkable_filters(page):
    page.click("#tab-rules")
    assert page.locator("#rule-count").inner_text() == "Showing 6 of 6 rules"
    page.fill("#rule-search", "logger")
    assert visible_titles(page) == ["Use the logger instead of console.log."]
    page.fill("#rule-search", "zzz-nothing")
    assert page.locator("#rule-empty").is_visible()
    page.click("#clear-filters")
    assert len(visible_titles(page)) == 6
    page.select_option("#rule-area", "tests")
    assert visible_titles(page) == [
        "Tests go next to the file they test, not in the top-level tests folder."
    ]
    page.select_option("#rule-area", "all")
    page.check("#rule-checkable")
    assert len(visible_titles(page)) == sum(1 for r in page.rules if r["detect"])
    page.uncheck("#rule-checkable")
    page.select_option("#rule-sort", "recent")
    recent = sorted(page.rules, key=lambda r: r["evidence"]["last_seen"], reverse=True)
    assert visible_titles(page)[0] == recent[0]["title"]


def test_decisions_command_and_persistence(page):
    page.click("#tab-rules")
    second = page.rules[1]
    page.locator(f'.rule[data-id="{second["id"]}"] [data-act="reject"]').click()
    page.locator(f'.rule[data-id="{page.rules[2]["id"]}"] [data-act="approve"]').click()
    cmd = page.locator("#cmd-rules").inner_text()
    assert cmd.startswith(f"folklore reject {second['id']}")
    page.click("#rule-status [data-status='rejected']")
    assert len(visible_titles(page)) == 1
    page.click("#rule-status [data-status='all']")
    page.reload()
    page.click("#tab-overview")
    assert page.locator("[data-stat='rejected']").first.inner_text() == "1"
    assert page.locator("[data-stat='approved']").first.inner_text() == "1"
    page.click("#tab-rules")
    page.click("#approve-rest")
    assert page.locator("[data-stat='undecided']").first.inner_text() == "0"
    page.click("#reset-decisions")
    assert page.locator("#cmd-rules").inner_text() == "folklore publish --agents-md"


def test_expand_shows_evidence(page):
    page.click("#tab-rules")
    page.click("#expand-all")
    assert page.locator(".rule-detail").count() == 6
    assert page.locator(".rule-detail .metric").first.is_visible()
    page.click("#expand-all")
    assert page.locator(".rule-detail").count() == 0


def test_diff_checker_matches_python(page, fixture_analysis):
    page.click("#tab-check")
    diff = sample_diff(fixture_analysis)
    py = {
        h.rule.id
        for h in check(rules_from_analysis(fixture_analysis), parse_unified_diff(diff), Config())
    }
    js = page.evaluate("(d) => window.folklore.checkDiff(d).hints.map(h => h.rule.id)", diff)
    assert set(js) == py and py
    page.click("#diff-sample")
    assert page.locator("#diff-result .hint").count() == len(py)
    page.click("#diff-clear")
    assert "Paste the output" in page.locator("#diff-result").inner_text()
    page.fill("#diff-input", "this is not a diff")
    page.click("#diff-check")
    assert "No changed files" in page.locator("#diff-result").inner_text()
    clean = "diff --git a/x.md b/x.md\n--- a/x.md\n+++ b/x.md\n@@ -1 +1,2 @@\n a\n+fine\n"
    page.fill("#diff-input", clean)
    page.click("#diff-check")
    assert "No known review conventions are broken" in page.locator("#diff-result").inner_text()


def test_rejected_rules_are_skipped_by_checker(page):
    checkable = next(r for r in page.rules if r["detect"])
    page.click("#tab-rules")
    page.locator(f'.rule[data-id="{checkable["id"]}"] [data-act="reject"]').click()
    page.click("#tab-check")
    page.click("#diff-sample")
    ids = page.eval_on_selector_all("#diff-result .hint", "els => els.map(e => e.dataset.rule)")
    assert checkable["id"] not in ids


def test_skill_files_and_copy(page):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.click("#tab-skill")
    assert page.locator("#file-name").inner_text().endswith("SKILL.md")
    assert page.locator("text=Valid Agent Skill").is_visible()
    page.locator("#file-list button").nth(1).click()
    assert "/references/" in page.locator("#file-name").inner_text()
    page.locator("#file-list button").last.click()
    assert json.loads(page.locator("#file-body").inner_text())["rules"]
    page.click("[data-copy-target='file-body']")
    page.wait_for_selector("#toast:not([hidden])")
    assert (
        "Cop" in page.locator("#toast").inner_text()
        or "Press" in page.locator("#toast").inner_text()
    )


def test_phone_layout_has_no_sideways_scroll(browser, fixture_analysis, tmp_path):
    path = write_report(dict(fixture_analysis), tmp_path / "r.html")
    pg = browser.new_page(viewport={"width": 390, "height": 844})
    pg.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    for tab in ("overview", "rules", "aside", "check", "skill"):
        pg.goto(path.as_uri() + "#" + tab)
        if tab == "rules":
            pg.click("#expand-all")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 390, tab
    pg.close()
