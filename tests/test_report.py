import colorsys
import re

from folklore.report import CSS, render_report


def hues(css):
    for hex_ in re.findall(r"#([0-9a-fA-F]{6})\b", css):
        r, g, b = (int(hex_[i : i + 2], 16) / 255 for i in (0, 2, 4))
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        yield hex_, h * 360, s


def test_palette_has_no_blue():
    for hex_, hue, sat in hues(CSS):
        assert not (170 <= hue <= 270 and sat > 0.08), f"#{hex_} is blue-ish ({hue:.0f}°)"


def test_links_and_focus_override_browser_blue():
    assert re.search(r"a\s*\{[^}]*color:\s*var\(--accent\)", CSS)
    assert "a:visited" in CSS and ":focus-visible" in CSS and "::selection" in CSS


def test_report_embeds_data_safely(fixture_analysis):
    analysis = dict(fixture_analysis)
    evil = "</script><script>alert(1)</script>"
    analysis["rules"] = [dict(fixture_analysis["rules"][0], title=evil)] + fixture_analysis[
        "rules"
    ][1:]
    page = render_report(analysis)
    assert evil not in page  # the JSON payload cannot close its <script> tag
    assert page.startswith("<!doctype html>")
    for panel in ("panel-overview", "panel-rules", "panel-aside", "panel-check", "panel-skill"):
        assert f'id="{panel}"' in page
    fragment = render_report(fixture_analysis, standalone=False)
    assert fragment.startswith("<title>") and "<body>" not in fragment


def test_sample_diff_trips_every_checkable_rule(fixture_analysis):
    from folklore.analyze import rules_from_analysis
    from folklore.config import Config
    from folklore.enforce import check, parse_unified_diff
    from folklore.report import sample_diff

    rules = rules_from_analysis(fixture_analysis)
    hints = check(rules, parse_unified_diff(sample_diff(fixture_analysis)), Config())
    assert {h.rule.id for h in hints} == {r.id for r in rules if r.detect}


def test_skill_tab_matches_publish(fixture_analysis):
    from folklore.report import skill_files

    skill = skill_files(fixture_analysis)
    assert skill["problems"] == []
    assert skill["files"][0]["path"].endswith("/SKILL.md")
