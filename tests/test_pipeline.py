from folklore.analyze import rules_from_analysis
from folklore.publish import publish, validate_skill


def titles(analysis):
    return [r["title"] for r in analysis["rules"]]


def test_finds_the_planted_conventions(fixture_analysis):
    found = " ".join(titles(fixture_analysis)).lower()
    for word in ("lodash", "logger", "codegen", "changeset", "tests", "hardcode"):
        assert word in found, word
    assert fixture_analysis["stats"]["rules"] == 6


def test_sets_aside_stale_and_single_author_patterns(fixture_analysis):
    statuses = {c["status"]: c["reason"] for c in fixture_analysis["other_clusters"]}
    assert "stale" in statuses
    assert "1 contributor" in statuses["discarded"]
    assert not any(
        "moment" in t.lower() or "prettier" in t.lower() for t in titles(fixture_analysis)
    )


def test_one_off_feedback_never_becomes_a_rule(fixture_analysis):
    joined = " ".join(titles(fixture_analysis)).lower()
    assert "safari" not in joined and "split this pr" not in joined


def test_single_maintainer_rule_is_flagged(fixture_analysis):
    i18n = next(r for r in fixture_analysis["rules"] if "hardcode" in r["title"].lower())
    assert i18n["single_reviewer"] is True


def test_every_rule_traces_to_real_sources(fixture_analysis, fixture_comments):
    known = {(c.id, c.pr_number) for c in fixture_comments}
    for rule in fixture_analysis["rules"]:
        assert rule["sources"]
        assert all((s["comment_id"], s["pr_number"]) in known for s in rule["sources"])


def test_published_skill_is_valid_and_safe(fixture_analysis, tmp_path):
    skill = publish(rules_from_analysis(fixture_analysis), "example-org/widgetkit", tmp_path)
    assert validate_skill(skill) == []
    text = "\n".join(p.read_text() for p in skill.rglob("*.md"))
    assert "ignore previous instructions" not in text.lower()
    assert "evil.example" not in text
    for contributor in (
        "arjun-dev",
        "priya-s",
        "sam-p",
        "maya-k",
    ):  # no names, not even maintainers
        assert contributor not in text
