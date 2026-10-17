from datetime import datetime, timezone
from pathlib import Path

import pytest

from folklore.analyze import analyze
from folklore.config import Config
from folklore.mine import load_comments
from folklore.models import ReviewComment

NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def fixture_comments():
    # Synthetic test fixture with known answers (see fixtures/make_synthetic_comments.py).
    return load_comments(Path(__file__).parent / "fixtures" / "synthetic_comments.jsonl")


@pytest.fixture(scope="session")
def fixture_analysis(fixture_comments):
    return analyze(fixture_comments, Config(), now=NOW, repo="example-org/widgetkit")


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
