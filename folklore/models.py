"""Plain data types shared by every stage of the pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any


def parse_time(value: str) -> datetime:
    """Parse a GitHub ISO-8601 timestamp into an aware UTC datetime."""
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _from_dict(cls, data: dict[str, Any]):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class ReviewComment:
    """One piece of review feedback left on a pull request."""

    id: int
    pr_number: int
    body: str
    reviewer: str
    reviewer_association: str = "NONE"
    pr_author: str = ""
    path: str = ""
    diff_hunk: str = ""
    created_at: str = ""
    url: str = ""
    kind: str = "inline"  # "inline" (on a line of the diff) or "review" (review summary)
    in_reply_to_id: int | None = None
    reviewer_is_bot: bool = False  # GitHub's own account type says "Bot"

    @property
    def created(self) -> datetime:
        return parse_time(self.created_at)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewComment:
        return _from_dict(cls, data)


@dataclass
class Example:
    """A before/after pair quoted from a real pull request."""

    bad: str = ""
    good: str = ""
    source_comment_id: int | None = None
    sanitized: bool = False  # True when suspicious lines were removed

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Example:
        return _from_dict(cls, data)


@dataclass
class Source:
    comment_id: int
    pr_number: int
    url: str = ""
    excerpt: str = ""  # what the maintainer wrote (sanitized, shortened, no names)
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Source:
        return _from_dict(cls, data)


@dataclass
class Evidence:
    comments: int = 0
    prs: int = 0
    reviewers: int = 0
    authors: int = 0
    first_seen: str = ""
    last_seen: str = ""
    recency_score: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        return _from_dict(cls, data)


@dataclass
class Cluster:
    """A group of review comments that say roughly the same thing."""

    id: int
    comment_ids: list[int]
    keywords: list[str] = field(default_factory=list)
    scope: list[str] = field(default_factory=lambda: ["**"])
    area: str = "general"
    evidence: Evidence = field(default_factory=Evidence)
    reviewers: list[str] = field(default_factory=list)
    coherence: float = 1.0  # mean pairwise similarity of the comment wording
    status: str = "candidate"  # candidate | stale | discarded
    reason: str = ""  # why it was discarded or flagged


@dataclass
class Rule:
    """A distilled, evidence-backed review convention."""

    id: str
    title: str
    rationale: str
    scope: list[str]
    area: str
    evidence: Evidence
    sources: list[Source]
    examples: list[Example] = field(default_factory=list)
    detect: str | None = None  # regex for added lines, when the rule is mechanically checkable
    detect_sample: str = ""  # a real flagged line the pattern catches
    confidence: float = 0.5
    single_reviewer: bool = False
    keywords: list[str] = field(default_factory=list)
    distiller: str = "heuristic"
    seen_in: list[str] = field(default_factory=list)  # a few files the feedback was left on

    @property
    def checkable(self) -> bool:
        return bool(self.detect)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checkable"] = self.checkable
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rule:
        data = dict(data)
        data["evidence"] = Evidence.from_dict(data.get("evidence", {}))
        data["sources"] = [Source.from_dict(s) for s in data.get("sources", [])]
        data["examples"] = [Example.from_dict(e) for e in data.get("examples", [])]
        data.pop("checkable", None)
        return _from_dict(cls, data)
