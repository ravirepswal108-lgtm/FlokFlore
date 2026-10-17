"""Minimal client for any OpenAI-compatible endpoint.

Works with DigitalOcean serverless inference (https://inference.do-ai.run/v1), a local
Ollama (http://localhost:11434/v1), vLLM, llama.cpp's server, and similar.
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from .config import EndpointConfig


class LLMError(RuntimeError):
    pass


class OpenAICompatClient:
    def __init__(self, endpoint: EndpointConfig, session: requests.Session | None = None):
        if not endpoint.model:
            raise LLMError("No model configured. Set `model` in .folklore.yml.")
        self.endpoint = endpoint
        self.session = session or requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        if endpoint.api_key:
            self.session.headers["Authorization"] = f"Bearer {endpoint.api_key}"

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.endpoint.base_url.rstrip('/')}{path}"
        try:
            resp = self.session.post(url, json=payload, timeout=120)
        except requests.RequestException as exc:
            raise LLMError(f"Could not reach {url}: {exc}") from exc
        if resp.status_code >= 400:
            raise LLMError(f"{url} returned {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def chat_json(self, system: str, user: str, max_tokens: int = 900) -> dict[str, Any]:
        payload = {
            "model": self.endpoint.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        data = self._post("/chat/completions", payload)
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected response shape: {str(data)[:200]}") from exc
        return parse_json_object(content)

    def embed(self, texts: list[str], batch: int = 64) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch):
            data = self._post(
                "/embeddings", {"model": self.endpoint.model, "input": texts[start : start + batch]}
            )
            rows = sorted(data.get("data", []), key=lambda r: r.get("index", 0))
            vectors.extend(row["embedding"] for row in rows)
        if len(vectors) != len(texts):
            raise LLMError("Embedding endpoint returned the wrong number of vectors.")
        return vectors


def parse_json_object(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply (tolerates fences and chatter)."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    start = text.find("{")
    if start < 0:
        raise LLMError("Model reply contained no JSON object.")
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as exc:
                    raise LLMError(f"Model reply was not valid JSON: {exc}") from exc
    raise LLMError("Model reply had an unterminated JSON object.")
