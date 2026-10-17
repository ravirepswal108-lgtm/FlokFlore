"""Stage 3 — Cluster: find feedback that keeps coming back, and weigh the evidence."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import PurePosixPath

import numpy as np
from sklearn.cluster import HDBSCAN, AgglomerativeClustering
from sklearn.feature_extraction.text import CountVectorizer

from .config import Config
from .filters import clean_text
from .models import Cluster, Evidence, ReviewComment

AGGLOMERATIVE_MAX = 1500

# Words reviewers use all the time that say nothing about the rule itself.
GENERIC_WORDS = {
    "please",
    "use",
    "instead",
    "add",
    "make",
    "like",
    "just",
    "think",
    "need",
    "needs",
    "should",
    "let",
    "code",
    "file",
    "files",
    "change",
    "changes",
    "pr",
    "thanks",
    "sure",
    "maybe",
    "really",
    "way",
    "thing",
    "things",
    "want",
    "does",
    "doesn",
    "don",
    "we",
    "ll",
    "ve",
    "re",
    "isn",
    "it",
    "this",
    "that",
    "here",
    "there",
    "also",
    "can",
    "could",
    "would",
    "one",
    "new",
    "using",
    "used",
    "line",
    "lines",
    "nit",
    "file]",
    "ts file",
    "js file",
    "py file",
    "tsx file",
}

GENERIC_DIRS = {"src", "lib", "app", "source", "pkg", "internal", "main", "java", "kotlin"}

LANGUAGES = {
    "py": "python",
    "ts": "typescript",
    "tsx": "typescript",
    "js": "javascript",
    "jsx": "javascript",
    "go": "go",
    "rs": "rust",
    "rb": "ruby",
    "java": "java",
    "kt": "kotlin",
    "swift": "swift",
    "cs": "csharp",
    "cpp": "cpp",
    "c": "c",
    "md": "docs",
    "yml": "config",
    "yaml": "config",
    "json": "config",
    "css": "styles",
    "scss": "styles",
}


def cluster_labels(vectors: np.ndarray, cfg: Config) -> np.ndarray:
    n = len(vectors)
    if n < 2:
        return np.full(n, -1)
    algorithm = cfg.algorithm
    if algorithm == "auto":
        algorithm = "agglomerative" if n <= AGGLOMERATIVE_MAX else "hdbscan"
    if algorithm == "hdbscan":
        model = HDBSCAN(min_cluster_size=max(2, cfg.min_comments), min_samples=1)
        return model.fit_predict(vectors)
    model = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=cfg.effective_distance_threshold,
    )
    labels = model.fit_predict(vectors)
    sizes = Counter(labels)
    return np.array([label if sizes[label] >= 2 else -1 for label in labels])


def split_broad_clusters(
    labels: np.ndarray, vectors: np.ndarray, sims: np.ndarray, cfg: Config
) -> np.ndarray:
    """Re-cluster any large group whose comments do not share wording, with a tighter
    threshold, until each part is coherent or too small to matter.

    On a few hundred real reviews a single loose threshold merges several topics into one
    blob; splitting recovers the real patterns inside it.
    """
    labels = labels.copy()
    next_label = int(labels.max()) + 1 if len(labels) else 0
    start = cfg.effective_distance_threshold
    queue = [(int(label), start) for label in set(labels.tolist()) if label >= 0]
    while queue:
        label, threshold = queue.pop()
        idx = np.where(labels == label)[0]
        if len(idx) < 2 * cfg.min_comments:
            continue
        pair = sims[np.ix_(idx, idx)]
        coherence = (pair.sum() - np.trace(pair)) / (len(idx) * (len(idx) - 1))
        if coherence >= cfg.min_coherence:
            continue
        threshold *= 0.85
        if threshold < 0.3:
            continue
        sub = AgglomerativeClustering(
            n_clusters=None, metric="cosine", linkage="average", distance_threshold=threshold
        ).fit_predict(vectors[idx])
        sizes = Counter(sub.tolist())
        if len(sizes) == 1:
            queue.append((label, threshold))
            continue
        for part, size in sizes.items():
            members = idx[sub == part]
            if size < 2:
                labels[members] = -1
                continue
            labels[members] = next_label
            queue.append((next_label, threshold))
            next_label += 1
    return labels


def infer_scope(paths: list[str]) -> tuple[list[str], str]:
    """Guess which part of the codebase a rule applies to, from the files it was raised on."""
    paths = [p for p in paths if p]
    if not paths:
        return ["**"], "general"
    dir_glob, area = "", ""
    for depth in (3, 2, 1):
        prefixes = Counter(
            "/".join(PurePosixPath(p).parts[:depth])
            for p in paths
            if len(PurePosixPath(p).parts) > depth
        )
        if not prefixes:
            continue
        prefix, count = prefixes.most_common(1)[0]
        if count / len(paths) >= 0.7:
            dir_glob = f"{prefix}/**"
            meaningful = [p for p in prefix.split("/") if p not in GENERIC_DIRS]
            area = meaningful[-1] if meaningful else prefix.split("/")[0]
            break
    suffixes = Counter(PurePosixPath(p).suffix.lstrip(".") for p in paths)
    suffix, count = suffixes.most_common(1)[0]
    ext_glob = f"*.{suffix}" if suffix and count / len(paths) >= 0.8 else ""
    if dir_glob and ext_glob:
        scope = [f"{dir_glob}/{ext_glob}"]
    elif dir_glob:
        scope = [dir_glob]
    elif ext_glob:
        scope = [f"**/{ext_glob}"]
        area = LANGUAGES.get(suffix, suffix)
    else:
        scope = ["**"]
    return scope, (area or "general")


def keywords_by_cluster(texts: list[str], labels: np.ndarray, top: int = 6) -> dict[int, list[str]]:
    """Class-based TF-IDF: words frequent in one cluster but rare in the others."""
    clusters = sorted({int(label) for label in labels if label >= 0})
    if not clusters:
        return {}
    docs = [" ".join(texts[i] for i in range(len(texts)) if labels[i] == c) for c in clusters]
    try:
        vectorizer = CountVectorizer(
            stop_words="english", ngram_range=(1, 2), token_pattern=r"(?u)\b[\w.]{2,}\b"
        )
        counts = vectorizer.fit_transform(docs).toarray().astype(float)
    except ValueError:
        return {c: [] for c in clusters}
    vocab = vectorizer.get_feature_names_out()
    tf = counts / np.maximum(counts.sum(axis=1, keepdims=True), 1)
    avg_words = counts.sum() / len(clusters)
    idf = np.log(1 + avg_words / np.maximum(counts.sum(axis=0), 1))
    scores = tf * idf
    out: dict[int, list[str]] = {}
    for row, cluster in enumerate(clusters):
        words: list[str] = []
        for idx in np.argsort(-scores[row]):
            word = vocab[idx]
            if scores[row, idx] <= 0 or word in GENERIC_WORDS:
                continue
            if any(part in GENERIC_WORDS for part in word.split()) and " " in word:
                continue
            if any(word in w or w in word for w in words):
                continue
            words.append(word)
            if len(words) == top:
                break
        out[cluster] = words
    return out


def text_coherence(texts: list[str]) -> np.ndarray:
    """Pairwise similarity of the review *wording* alone (no code), used to reject clusters
    whose members only share the code they were left on."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    try:
        matrix = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(texts)
    except ValueError:
        return np.zeros((len(texts), len(texts)))
    matrix = normalize(matrix)
    return (matrix @ matrix.T).toarray()


def evidence_for(members: list[ReviewComment], cfg: Config, now: datetime) -> Evidence:
    created = sorted(c.created for c in members)
    ages = [max(0.0, (now - c.created).total_seconds() / 86400) for c in members]
    recency = sum(math.pow(0.5, age / cfg.recency_half_life_days) for age in ages)
    return Evidence(
        comments=len(members),
        prs=len({c.pr_number for c in members}),
        reviewers=len({c.reviewer for c in members}),
        authors=len({c.pr_author for c in members if c.pr_author}),
        first_seen=created[0].isoformat(),
        last_seen=created[-1].isoformat(),
        recency_score=round(recency, 3),
    )


def evidence_problems(evidence: Evidence, cfg: Config) -> list[str]:
    reasons = []
    if evidence.comments < cfg.min_comments:
        reasons.append(f"only {evidence.comments} comments (needs {cfg.min_comments})")
    if evidence.prs < cfg.min_prs:
        reasons.append(f"only {evidence.prs} PR (needs {cfg.min_prs})")
    if evidence.authors < cfg.min_authors:
        reasons.append(
            f"aimed at {evidence.authors} contributor (needs {cfg.min_authors}); "
            "may be one person's repeated mistake"
        )
    if evidence.reviewers < cfg.min_reviewers:
        reasons.append(f"raised by {evidence.reviewers} maintainer (needs {cfg.min_reviewers})")
    return reasons


def build_clusters(
    comments: list[ReviewComment],
    vectors: np.ndarray,
    cfg: Config,
    now: datetime,
) -> list[Cluster]:
    texts = [clean_text(c.body) for c in comments]
    sims = text_coherence(texts)
    labels = cluster_labels(vectors, cfg)
    if cfg.algorithm != "hdbscan" and len(comments) <= AGGLOMERATIVE_MAX:
        labels = split_broad_clusters(labels, vectors, sims, cfg)
    keywords = keywords_by_cluster(texts, labels)
    groups: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        if label >= 0:
            groups[int(label)].append(index)

    clusters: list[Cluster] = []
    for label, members in groups.items():
        members_c = [comments[i] for i in members]
        created = sorted(c.created for c in members_c)
        reviewers = sorted({c.reviewer for c in members_c})
        evidence = evidence_for(members_c, cfg, now)
        pair = sims[np.ix_(members, members)]
        n = len(members)
        coherence = float((pair.sum() - np.trace(pair)) / (n * (n - 1))) if n > 1 else 1.0
        scope, area = infer_scope([c.path for c in members_c])
        cluster = Cluster(
            id=label,
            comment_ids=[c.id for c in members_c],
            keywords=keywords.get(label, []),
            scope=scope,
            area=area,
            evidence=evidence,
            reviewers=reviewers,
            coherence=round(coherence, 3),
        )
        days_since = (now - created[-1]).total_seconds() / 86400
        reasons = evidence_problems(evidence, cfg)
        if coherence < cfg.min_coherence:
            reasons.append(
                "the comments do not share a message (too broad; try a lower "
                "cluster.distance_threshold)"
                if evidence.comments >= 2 * cfg.min_comments
                else "the comments share code but not a message"
            )
        if reasons:
            cluster.status, cluster.reason = "discarded", "; ".join(reasons)
        elif days_since > cfg.stale_after_days:
            cluster.status = "stale"
            cluster.reason = (
                f"last raised {int(days_since)} days ago; the project may have moved on"
            )
        clusters.append(cluster)

    clusters.sort(key=lambda c: (-c.evidence.recency_score, -c.evidence.comments))
    return clusters
