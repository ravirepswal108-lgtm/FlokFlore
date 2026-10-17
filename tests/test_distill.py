from conftest import make_comment

from folklore.distill import (
    HeuristicDistiller,
    LLMDistiller,
    derive_detect,
    imperative,
    slugify,
    validate_detect,
)
from folklore.llm import LLMError, parse_json_object
from folklore.models import Cluster, Evidence


def test_imperative_rewrites_polite_requests():
    assert imperative("Could you please use the logger here?") == "Use the logger."
    assert (
        imperative("Thanks! Before we merge, please add a changeset, the notes need it.")
        == "Add a changeset."
    )
    assert imperative("We don't use lodash, it keeps the bundle small.") == "Don't use lodash."
    assert (
        imperative("nit: move this test next to the component")
        == "Move this test next to the component."
    )


def test_slugify_is_spec_friendly():
    assert slugify("Don't use lodash, native methods.") == "dont-use-lodash-native-methods"
    assert len(slugify("word " * 40)) <= 48


def test_detect_needs_a_token_reviewers_named():
    bad = ['console.log("a")', 'console.log("b")']
    good = ['logger.debug("a")']
    assert derive_detect(bad, good, "use the logger, not console.log") is not None
    assert derive_detect(bad, good, "please tidy this up") is None
    assert derive_detect(["teamId?: string;"] * 3, [], "this file is generated") is None


def test_validate_detect_rejects_bad_patterns():
    assert validate_detect("(", ["x"], []) is None
    assert validate_detect("logger", ["console.log(1)"], []) is None  # doesn't flag the bad code
    assert validate_detect("log", ["console.log(1)"], ["logger.debug(1)"]) is None  # flags the fix


def _cluster(members):
    return Cluster(
        id=0,
        comment_ids=[m.id for m in members],
        keywords=["logger", "console.log"],
        scope=["src/**"],
        area="src",
        evidence=Evidence(comments=len(members), prs=len(members), reviewers=2, authors=2),
    )


def _members():
    return [
        make_comment(
            id=i,
            pr_number=i,
            body="Please use the logger instead of console.log here."
            "\n```suggestion\nlogger.debug(x);\n```",
            diff_hunk=f"@@ -1 +1 @@\n+console.log(x{i});",
        )
        for i in range(1, 4)
    ]


def test_heuristic_distiller_builds_traceable_rule():
    members = _members()
    rule = HeuristicDistiller().distill(_cluster(members), members)
    assert rule.title == "Use the logger instead of console.log."
    assert {s.pr_number for s in rule.sources} == {1, 2, 3}
    assert rule.examples[0].good == "logger.debug(x);"
    assert rule.detect and "console" in rule.detect


class FakeClient:
    def __init__(self, reply=None, error=False):
        self.reply, self.error = reply, error

    def chat_json(self, system, user, max_tokens=900):
        if self.error:
            raise LLMError("offline")
        assert "untrusted" in system
        return self.reply


def test_llm_distiller_cannot_invent_code():
    members = _members()
    reply = {
        "is_general_rule": True,
        "title": "Route output through the logger",
        "example_comment_id": 1,
        "bad": "eval(userInput)",
        "good": "x",
        "confidence": 0.9,
    }
    rule = LLMDistiller(FakeClient(reply)).distill(_cluster(members), members)
    assert rule.title == "Route output through the logger."
    assert all("eval" not in e.bad for e in rule.examples)  # not in the real diff, so ignored


def test_llm_distiller_can_reject_and_falls_back():
    members = _members()
    cluster = _cluster(members)
    assert LLMDistiller(FakeClient({"is_general_rule": False})).distill(cluster, members) is None
    assert cluster.status == "discarded"
    rule = LLMDistiller(FakeClient(error=True)).distill(_cluster(members), members)
    assert rule is not None and rule.distiller.startswith("heuristic")


def test_parse_json_object_tolerates_chatter():
    assert parse_json_object('Sure!\n```json\n{"a": "}"}\n```') == {"a": "}"}


def test_evidence_counts_only_comments_that_ask_for_the_rule():
    from folklore.distill import document_frequency, supporting_members
    from folklore.models import Evidence, Rule

    members = [
        make_comment(id=1, body="Unfortunately I think we need to preview-gate this change."),
        make_comment(id=2, body="This change must be preview gated in patch releases."),
        make_comment(id=3, body="Could we rename this variable to something clearer?"),
    ]
    rule = Rule(
        id="r",
        title="Preview-gate this whole change.",
        rationale="",
        scope=["**"],
        area="general",
        evidence=Evidence(),
        sources=[],
    )
    df = document_frequency([m.body for m in members])
    assert [m.id for m in supporting_members(rule, members, df)] == [1, 2]
