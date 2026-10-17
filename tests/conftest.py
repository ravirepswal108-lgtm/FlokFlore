from datetime import datetime, timezone
from importlib import resources

import pytest

from folklore.analyze import analyze
from folklore.config import Config
from folklore.mine import load_comments
from folklore.models import ReviewComment

NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def demo_comments():
    with resources.as_file(resources.files("folklore").joinpath("data/demo_comments.jsonl")) as p:
        return load_comments(p)


@pytest.fixture(scope="session")
def demo_analysis(demo_comments):
    return analyze(demo_comments, Config(), now=NOW, repo="example-org/widgetkit")


def make_comment(**kw) -> ReviewComment:
    base = dict(
        id=1,
        pr_number=10,
        body="Please use the logger instead of console.log here.",
        reviewer="maya",
        reviewer_association="MEMBER",
        pr_author="sam",
        path="src/a.ts",
        diff_hunk="@@ -1 +1 @@\n+console.log(x);",
        created_at="2026-10-01T00:00:00Z",
    )
    base.update(kw)
    return ReviewComment(**base)
