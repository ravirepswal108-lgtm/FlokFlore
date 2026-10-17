"""Stage 2a — Filter: keep only maintainer feedback that could be a reusable rule."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .config import Config
from .models import ReviewComment

KNOWN_BOTS = {
    "codecov",
    "coveralls",
    "dependabot",
    "renovate",
    "github-actions",
    "sonarcloud",
    "netlify",
    "vercel",
    "changeset-bot",
    "allcontributors",
    "folklore",
}

_LOW_SIGNAL = re.compile(
    r"^\W*(lgtm|looks good( to me)?|thanks?( you)?|thx|ty|\+1|:\+1:|👍|:shipit:|done|fixed|"
    r"nice( work| catch)?|great( work)?|approved?|ship it|same here|same as above|ditto)\W*$",
    re.IGNORECASE,
)
_SUGGESTION = re.compile(r"```suggestion[^\n]*\n(.*?)```", re.DOTALL)
_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_QUOTE = re.compile(r"^\s*>.*$", re.MULTILINE)
_URL = re.compile(r"https?://\S+")
_MENTION = re.compile(r"(?<![\w`])@[A-Za-z0-9-]+")
_HTML = re.compile(r"<[^>]+>")


@dataclass
class FilterResult:
    kept: list[ReviewComment] = field(default_factory=list)
    inferred_maintainers: list[str] = field(default_factory=list)
    dropped: Counter = field(default_factory=Counter)
    total: int = 0

    def funnel(self) -> list[dict]:
        """Ordered steps for the report: how many comments each filter removed."""
        order = [
            ("bot", "Bot comments"),
            ("not_maintainer", "Not from a maintainer"),
            ("self_review", "Author reviewing their own PR"),
            ("reply", "Replies inside a thread"),
            ("low_signal", "LGTM, thanks and similar"),
            ("too_short", "Too short to be a rule"),
        ]
        return [
            {"key": key, "label": label, "count": self.dropped.get(key, 0)} for key, label in order
        ]


def is_bot(login: str) -> bool:
    login = (login or "").lower()
    if login.endswith("[bot]") or login.endswith("-bot"):
        return True
    return login.split("[")[0] in KNOWN_BOTS


def extract_suggestion(body: str) -> str | None:
    """Return the code inside a GitHub ```suggestion block, if there is one."""
    match = _SUGGESTION.search(body or "")
    return match.group(1).rstrip("\n") if match else None


def clean_text(body: str) -> str:
    """Review text with code, quotes, links, mentions and markup removed."""
    text = _SUGGESTION.sub(" ", body or "")
    text = _CODE_BLOCK.sub(" ", text)
    text = _QUOTE.sub(" ", text)
    text = _URL.sub(" ", text)
    text = _MENTION.sub(" ", text)
    text = _HTML.sub(" ", text)
    text = text.replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def frequent_reviewers(comments: list[ReviewComment], min_prs: int) -> set[str]:
    """Reviewers who gave feedback on at least `min_prs` pull requests opened by other people.

    GitHub labels organisation members whose membership is private as CONTRIBUTOR, so
    `author_association` alone misses many real maintainers. Someone who keeps reviewing
    other people's pull requests is acting as a maintainer whatever the label says.
    """
    prs: dict[str, set[int]] = {}
    for c in comments:
        reviewer = (c.reviewer or "").lower()
        if not reviewer or is_bot(reviewer) or reviewer == (c.pr_author or "").lower():
            continue
        if c.reviewer_association.upper() in ("NONE", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER"):
            continue
        prs.setdefault(reviewer, set()).add(c.pr_number)
    return {r for r, numbers in prs.items() if len(numbers) >= min_prs}


def classify(comment: ReviewComment, cfg: Config, inferred: set[str] | None = None) -> str | None:
    """Return the reason a comment is dropped, or None to keep it."""
    reviewer = (comment.reviewer or "").lower()
    excluded = {r.lower() for r in cfg.exclude_reviewers}
    included = {r.lower() for r in cfg.include_reviewers}
    if is_bot(reviewer) or reviewer in excluded:
        return "bot"
    is_maintainer = (
        comment.reviewer_association.upper() in cfg.maintainer_associations
        or reviewer in included
        or reviewer in (inferred or set())
    )
    if not is_maintainer:
        return "not_maintainer"
    if comment.pr_author and reviewer == comment.pr_author.lower():
        return "self_review"
    if comment.in_reply_to_id:
        return "reply"
    text = clean_text(comment.body)
    if _LOW_SIGNAL.match(text) or (not text and not extract_suggestion(comment.body)):
        return "low_signal"
    if len(text) < cfg.min_comment_chars and not extract_suggestion(comment.body):
        return "too_short"
    return None


def filter_comments(comments: list[ReviewComment], cfg: Config) -> FilterResult:
    result = FilterResult(total=len(comments))
    inferred = (
        frequent_reviewers(comments, cfg.frequent_reviewer_prs)
        if cfg.frequent_reviewer_prs > 0
        else set()
    )
    result.inferred_maintainers = sorted(inferred)
    for comment in comments:
        reason = classify(comment, cfg, inferred)
        if reason:
            result.dropped[reason] += 1
        else:
            result.kept.append(comment)
    return result
