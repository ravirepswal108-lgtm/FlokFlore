"""Run filter → embed → cluster → distill and collect everything the report needs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .cluster import build_clusters
from .config import Config
from .distill import make_distiller, rank_members
from .embed import embedding_text, make_embedder
from .filters import clean_text, filter_comments
from .models import ReviewComment, Rule
from .sanitize import sanitize_text


def analyze(
    comments: list[ReviewComment],
    cfg: Config,
    now: datetime | None = None,
    repo: str = "",
    embedder=None,
    distiller=None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    embedder = embedder or make_embedder(cfg.embedding)
    distiller = distiller or make_distiller(cfg)

    filtered = filter_comments(comments, cfg)
    kept = filtered.kept
    vectors = embedder.embed([embedding_text(c) for c in kept])
    clusters = build_clusters(kept, vectors, cfg, now) if kept else []

    index = {c.id: i for i, c in enumerate(kept)}
    rules: list[Rule] = []
    rejected: list[dict[str, Any]] = []
    rejected_ids = set(cfg.rejected_rules)
    for cluster in clusters:
        if cluster.status != "candidate":
            continue
        rows = [index[cid] for cid in cluster.comment_ids]
        members = rank_members([kept[r] for r in rows], vectors[rows])
        rule = distiller.distill(cluster, members)
        if rule is None:
            if cluster.status == "candidate":
                cluster.status, cluster.reason = "discarded", "no clear rule could be phrased"
            continue
        base_id, n = rule.id, 2
        while any(r.id == rule.id for r in rules):
            rule.id = f"{base_id}-{n}"
            n += 1
        if rule.id in rejected_ids:
            cluster.status, cluster.reason = (
                "rejected",
                f"rule '{rule.id}' was rejected by a maintainer",
            )
            rejected.append({"id": rule.id, "title": rule.title})
            continue
        cluster.status = "rule"
        cluster.reason = rule.id
        rules.append(rule)

    rules.sort(key=lambda r: -(r.evidence.recency_score * (1 + 0.25 * (r.evidence.reviewers - 1))))
    overflow = rules[cfg.max_rules :]
    rules = rules[: cfg.max_rules]
    for rule in overflow:
        for cluster in clusters:
            if cluster.reason == rule.id:
                cluster.status, cluster.reason = "discarded", "below the max_rules cut-off"

    by_id = {c.id: c for c in kept}
    other_clusters = []
    for cluster in clusters:
        if cluster.status == "rule":
            continue
        samples = []
        for cid in cluster.comment_ids[:3]:
            text = sanitize_text(clean_text(by_id[cid].body), limit=160)
            if text:
                samples.append(text)
        other_clusters.append(
            {
                "status": cluster.status,
                "reason": cluster.reason,
                "keywords": cluster.keywords,
                "scope": cluster.scope,
                "coherence": cluster.coherence,
                "evidence": cluster.evidence.__dict__,
                "samples": samples,
            }
        )

    return {
        "tool": f"folklore {__version__}",
        "repo": repo or cfg.repo,
        "generated_at": now.isoformat(timespec="seconds"),
        "settings": {
            "embedder": getattr(embedder, "name", "custom"),
            "distiller": getattr(distiller, "name", "custom"),
            "algorithm": cfg.algorithm,
            "thresholds": {
                "min_comments": cfg.min_comments,
                "min_prs": cfg.min_prs,
                "min_authors": cfg.min_authors,
                "min_reviewers": cfg.min_reviewers,
            },
        },
        "stats": {
            "feedback_total": filtered.total,
            "feedback_kept": len(kept),
            "pull_requests": len({c.pr_number for c in comments}),
            "maintainers": len({c.reviewer for c in kept}),
            "maintainers_inferred": len(filtered.inferred_maintainers),
            "clusters": len(clusters),
            "rules": len(rules),
            "stale": sum(1 for c in clusters if c.status == "stale"),
            "discarded": sum(1 for c in clusters if c.status == "discarded"),
            "rejected": len(rejected),
        },
        "funnel": filtered.funnel(),
        "rules": [r.to_dict() for r in rules],
        "other_clusters": other_clusters,
    }


def save_analysis(analysis: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_analysis(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rules_from_analysis(analysis: dict[str, Any]) -> list[Rule]:
    return [Rule.from_dict(r) for r in analysis.get("rules", [])]
