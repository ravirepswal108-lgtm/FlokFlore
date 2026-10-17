"""Stage 2b — Embed: turn review comments into vectors.

`tfidf` works offline with no model downloads. `openai` calls any OpenAI-compatible
embeddings endpoint (DigitalOcean serverless inference, Ollama, vLLM, ...).
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from .config import EndpointConfig
from .filters import clean_text
from .llm import OpenAICompatClient
from .models import ReviewComment

_IDENT = re.compile(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*")


def embedding_text(comment: ReviewComment) -> str:
    """What gets embedded: the cleaned review text, the identifiers on the line the comment
    points at (so "use the logger" lands near other comments on console.log), and a hint
    about the file type."""
    text = clean_text(comment.body)
    hunk = [ln for ln in (comment.diff_hunk or "").splitlines() if not ln.startswith("@@")]
    idents = _IDENT.findall(hunk[-1]) if hunk else []
    idents = [i for i in idents if len(i) > 2][:6]
    if idents:
        text += " | code: " + " ".join(idents)
    suffix = PurePosixPath(comment.path).suffix.lstrip(".") if comment.path else ""
    return f"{text} [{suffix} file]" if suffix else text


class TfidfEmbedder:
    name = "tfidf"

    def __init__(self, max_dims: int = 128):
        self.max_dims = max_dims

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1))
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            stop_words="english",
            min_df=1,
            token_pattern=r"(?u)\b[\w.]{2,}\b",
        )
        matrix = vectorizer.fit_transform(texts)
        n_features = matrix.shape[1]
        if n_features > self.max_dims and len(texts) > self.max_dims:
            reduced = TruncatedSVD(n_components=self.max_dims, random_state=0).fit_transform(matrix)
            return normalize(reduced)
        return normalize(matrix.toarray())


class RemoteEmbedder:
    name = "openai"

    def __init__(self, endpoint: EndpointConfig):
        self.client = OpenAICompatClient(endpoint)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1))
        return normalize(np.asarray(self.client.embed(texts), dtype=float))


def make_embedder(endpoint: EndpointConfig):
    if endpoint.provider == "openai":
        return RemoteEmbedder(endpoint)
    return TfidfEmbedder()
