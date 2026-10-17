"""Configuration, read from `.folklore.yml` in the target repository."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILE = ".folklore.yml"

DEFAULT_CONFIG_YAML = """\
# Folklore configuration. Every key is optional; these are the defaults.
repo: ""                      # owner/name, e.g. excalidraw/excalidraw

mine:
  max_prs: 300                # most recent closed PRs to read
  include_review_bodies: true # also read review summaries (one extra API call per PR)

filter:
  # Whose feedback counts as project folklore (GitHub author_association values).
  maintainer_associations: [OWNER, MEMBER, COLLABORATOR]
  include_reviewers: []       # extra logins to treat as maintainers
  frequent_reviewer_prs: 3    # also count anyone reviewing this many PRs by others (0 = off)
  exclude_reviewers: []       # logins to ignore entirely
  min_comment_chars: 30

cluster:
  algorithm: auto             # auto | agglomerative | hdbscan
  distance_threshold: auto    # agglomerative only; lower = tighter clusters (auto: 0.9 tfidf, 0.45 dense)
  min_comments: 3             # a rule needs at least this many comments...
  min_prs: 2                  # ...spread over at least this many PRs...
  min_authors: 2              # ...aimed at at least this many different PR authors
  min_reviewers: 1            # raise to 2 to drop single-maintainer preferences
  min_coherence: 0.12         # comments must also share wording, not just code
  recency_half_life_days: 180
  stale_after_days: 365       # clusters not seen for this long are reported as stale

distill:
  max_rules: 12

embedding:
  provider: tfidf             # tfidf (offline) | openai (any OpenAI-compatible endpoint)
  model: ""                   # e.g. an embedding model ID from your provider
  base_url: https://inference.do-ai.run/v1
  api_key_env: FOLKLORE_API_KEY

llm:
  provider: none              # none (heuristic, offline) | openai (any OpenAI-compatible endpoint)
  model: openai-gpt-oss-20b
  base_url: https://inference.do-ai.run/v1
  api_key_env: FOLKLORE_API_KEY

enforce:
  mode: deterministic         # deterministic (regex rules only) | llm (also judgment rules)
  require_label: ""           # only run when the PR has this label, e.g. "folklore"
  max_hints: 5
  max_files: 60

# Rules a maintainer has rejected. They will not be proposed again.
rejected_rules: []
"""


@dataclass
class EndpointConfig:
    provider: str = "none"
    model: str = ""
    base_url: str = "https://inference.do-ai.run/v1"
    api_key_env: str = "FOLKLORE_API_KEY"

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


@dataclass
class Config:
    repo: str = ""
    # mine
    max_prs: int = 300
    include_review_bodies: bool = True
    # filter
    maintainer_associations: list[str] = field(
        default_factory=lambda: ["OWNER", "MEMBER", "COLLABORATOR"]
    )
    include_reviewers: list[str] = field(default_factory=list)
    frequent_reviewer_prs: int = 3
    exclude_reviewers: list[str] = field(default_factory=list)
    min_comment_chars: int = 30
    # cluster
    algorithm: str = "auto"
    distance_threshold: float | None = None  # None = pick a default for the embedder
    min_comments: int = 3
    min_prs: int = 2
    min_authors: int = 2
    min_reviewers: int = 1
    min_coherence: float = 0.12
    recency_half_life_days: float = 180
    stale_after_days: float = 365
    # distill
    max_rules: int = 12
    embedding: EndpointConfig = field(default_factory=lambda: EndpointConfig(provider="tfidf"))
    llm: EndpointConfig = field(
        default_factory=lambda: EndpointConfig(provider="none", model="openai-gpt-oss-20b")
    )
    # enforce
    enforce_mode: str = "deterministic"
    require_label: str = ""
    max_hints: int = 5
    max_files: int = 60
    rejected_rules: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> Config:
        raw = raw or {}
        cfg = cls()
        cfg.repo = str(raw.get("repo") or "")
        sections = {
            "mine": ["max_prs", "include_review_bodies"],
            "filter": [
                "maintainer_associations",
                "include_reviewers",
                "frequent_reviewer_prs",
                "exclude_reviewers",
                "min_comment_chars",
            ],
            "cluster": [
                "algorithm",
                "distance_threshold",
                "min_comments",
                "min_prs",
                "min_authors",
                "min_reviewers",
                "min_coherence",
                "recency_half_life_days",
                "stale_after_days",
            ],
            "distill": ["max_rules"],
        }
        for section, keys in sections.items():
            values = raw.get(section) or {}
            for key in keys:
                if key in values and values[key] is not None and values[key] != "auto":
                    setattr(cfg, key, values[key])
        for name in ("embedding", "llm"):
            values = raw.get(name) or {}
            endpoint: EndpointConfig = getattr(cfg, name)
            for key in ("provider", "model", "base_url", "api_key_env"):
                if values.get(key) is not None:
                    setattr(endpoint, key, str(values[key]))
        enforce = raw.get("enforce") or {}
        cfg.enforce_mode = str(enforce.get("mode", cfg.enforce_mode))
        cfg.require_label = str(enforce.get("require_label") or "")
        cfg.max_hints = int(enforce.get("max_hints", cfg.max_hints))
        cfg.max_files = int(enforce.get("max_files", cfg.max_files))
        cfg.rejected_rules = [str(r) for r in raw.get("rejected_rules") or []]
        cfg.maintainer_associations = [a.upper() for a in cfg.maintainer_associations]
        return cfg

    @property
    def effective_distance_threshold(self) -> float:
        if self.distance_threshold is not None:
            return float(self.distance_threshold)
        return 0.9 if self.embedding.provider == "tfidf" else 0.45

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        path = Path(path or CONFIG_FILE)
        if not path.exists():
            return cls()
        with path.open(encoding="utf-8") as fh:
            return cls.from_mapping(yaml.safe_load(fh))


def write_default_config(path: str | Path = CONFIG_FILE, repo: str = "") -> Path:
    path = Path(path)
    text = DEFAULT_CONFIG_YAML
    if repo:
        text = text.replace('repo: ""', f"repo: {repo}", 1)
    path.write_text(text, encoding="utf-8")
    return path
