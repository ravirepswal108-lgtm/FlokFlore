from conftest import make_comment

from folklore.config import Config
from folklore.filters import clean_text, extract_suggestion, filter_comments, is_bot


def reason(**kw):
    result = filter_comments([make_comment(**kw)], Config())
    return next(iter(result.dropped), None)


def test_keeps_maintainer_feedback():
    assert reason() is None


def test_drops_bots():
    assert is_bot("codecov[bot]") and is_bot("renovate") and not is_bot("maya")
    assert reason(reviewer="github-actions[bot]") == "bot"


def test_drops_non_maintainers_self_reviews_and_replies():
    assert reason(reviewer_association="CONTRIBUTOR") == "not_maintainer"
    assert reason(pr_author="maya") == "self_review"
    assert reason(in_reply_to_id=5) == "reply"


def test_drops_low_signal_and_short():
    assert reason(body="LGTM 👍") == "low_signal"
    assert reason(body="Thanks!") == "low_signal"
    assert reason(body="nit: typo") == "too_short"


def test_short_comment_with_suggestion_is_kept():
    assert reason(body="nit\n```suggestion\nlogger.debug(x)\n```") is None


def test_include_and_exclude_lists():
    cfg = Config(include_reviewers=["outside-expert"], exclude_reviewers=["maya"])
    kept = filter_comments(
        [make_comment(reviewer="outside-expert", reviewer_association="NONE"), make_comment(id=2)],
        cfg,
    )
    assert [c.reviewer for c in kept.kept] == ["outside-expert"]


def test_suggestion_and_clean_text():
    body = "Use the logger @maya, see https://x.y/z\n> quoted\n```suggestion\nlogger.debug(a)\n```"
    assert extract_suggestion(body) == "logger.debug(a)"
    assert clean_text(body) == "Use the logger , see"


def test_frequent_reviewers_count_as_maintainers():
    # Private org members show up as CONTRIBUTOR; reviewing others' PRs reveals them.
    comments = [
        make_comment(
            id=i,
            pr_number=i,
            reviewer="core-dev",
            reviewer_association="CONTRIBUTOR",
            pr_author=f"author{i}",
        )
        for i in range(1, 4)
    ] + [make_comment(id=9, pr_number=9, reviewer="drive-by", reviewer_association="CONTRIBUTOR")]
    result = filter_comments(comments, Config())
    assert {c.reviewer for c in result.kept} == {"core-dev"}
    assert result.inferred_maintainers == ["core-dev"]
    assert not filter_comments(comments, Config(frequent_reviewer_prs=0)).kept


def test_drops_feedback_that_asks_for_nothing():
    for body in (
        "Sorry for the delayed review, this makes sense to me now.",
        "With the ParamSpec stuff this looks much more straightforward.",
    ):
        assert reason(body=body) == "not_actionable", body
    assert reason(body="Tests go next to the file they test, not in the tests folder.") is None


def test_ai_reviewers_are_not_maintainers():
    assert reason(reviewer="Copilot", reviewer_association="CONTRIBUTOR") == "bot"
    assert reason(reviewer="coderabbitai[bot]") == "bot"
    assert reason(reviewer="some-app", reviewer_is_bot=True) == "bot"


def test_markdown_links_keep_their_label():
    assert clean_text("make it a [preview](https://x.y/p) change") == "make it a preview change"
