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


def test_report_escapes_and_renders(demo_analysis):
    analysis = dict(demo_analysis)
    analysis["rules"] = [
        dict(demo_analysis["rules"][0], title="<script>alert(1)</script>")
    ] + demo_analysis["rules"][1:]
    page = render_report(analysis)
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert page.startswith("<!doctype html>")
    assert "Patterns set aside" in page
    fragment = render_report(demo_analysis, standalone=False)
    assert fragment.startswith("<title>") and "<body>" not in fragment
