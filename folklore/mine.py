"""Stage 1 — Mine: pull review feedback from a repository's recent pull requests."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path

from .github import GitHubClient, pr_number_from_url
from .models import ReviewComment

Progress = Callable[[str], None]


def mine(
    client: GitHubClient,
    repo: str,
    max_prs: int = 300,
    include_review_bodies: bool = True,
    progress: Progress | None = None,
) -> list[ReviewComment]:
    """Fetch inline review comments and review summaries for the latest closed PRs."""
    say = progress or (lambda _msg: None)

    say(f"Listing up to {max_prs} closed pull requests in {repo}")
    pulls = {p["number"]: p for p in client.closed_pulls(repo, limit=max_prs)}
    if not pulls:
        return []
    oldest = min(p["created_at"] for p in pulls.values())
    authors = {n: (p.get("user") or {}).get("login", "") for n, p in pulls.items()}

    say("Reading inline review comments")
    comments: list[ReviewComment] = []
    for raw in client.review_comments(repo, since=oldest):
        number = pr_number_from_url(raw.get("pull_request_url", ""))
        if number not in pulls:
            continue
        user = raw.get("user") or {}
        comments.append(
            ReviewComment(
                id=raw["id"],
                pr_number=number,
                body=raw.get("body") or "",
                reviewer=user.get("login", ""),
                reviewer_association=raw.get("author_association", "NONE"),
                pr_author=authors.get(number, ""),
                path=raw.get("path") or "",
                diff_hunk=raw.get("diff_hunk") or "",
                created_at=raw.get("created_at") or "",
                url=raw.get("html_url") or "",
                kind="inline",
                in_reply_to_id=raw.get("in_reply_to_id"),
            )
        )

    if include_review_bodies:
        say(f"Reading review summaries for {len(pulls)} pull requests")
        for number in pulls:
            for review in client.reviews(repo, number):
                body = (review.get("body") or "").strip()
                if not body:
                    continue
                user = review.get("user") or {}
                comments.append(
                    ReviewComment(
                        id=review["id"],
                        pr_number=number,
                        body=body,
                        reviewer=user.get("login", ""),
                        reviewer_association=review.get("author_association", "NONE"),
                        pr_author=authors.get(number, ""),
                        created_at=review.get("submitted_at") or "",
                        url=review.get("html_url") or "",
                        kind="review",
                    )
                )

    say(f"Collected {len(comments)} pieces of review feedback")
    return comments


def save_comments(comments: Iterable[ReviewComment], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for comment in comments:
            fh.write(json.dumps(comment.to_dict(), ensure_ascii=False) + "\n")
    return path


def load_comments(path: str | Path) -> list[ReviewComment]:
    out = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(ReviewComment.from_dict(json.loads(line)))
    return out
