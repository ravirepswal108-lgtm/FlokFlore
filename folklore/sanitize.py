"""Keep untrusted text out of instructions that coding agents will trust.

Review examples are quoted from pull-request diffs, which anyone can write. A generated
SKILL.md is loaded by coding agents as trusted guidance, so anything copied into it must be
treated as hostile: no instruction-like lines, no fence break-outs, nothing long.
"""

from __future__ import annotations

import re
import textwrap

MAX_EXAMPLE_LINES = 8
MAX_EXAMPLE_CHARS = 400
MAX_TEXT_CHARS = 240

_INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above) ",
    r"\b(ai|llm|coding) (agents?|assistants?|models?)\s*[:,]",
    r"\byou are (now )?(an? |the )?(ai|assistant|agent|language model)\b",
    r"\bsystem prompt\b",
    r"\bnew instructions?\b",
    r"(curl|wget|iwr|invoke-webrequest)\b[^\n|]*\|\s*(sh|bash|zsh|python\d?|iex|pwsh)\b",
    r"base64\s+(-d|--decode)[^\n]*\|\s*(sh|bash)",
    r"\brm\s+-rf\s+(/|~|\$home)",
    r"\b(exfiltrate|api[_ -]?key|secret[_ -]?token|private key)\b",
    r"<\s*/?\s*(system|instructions?|assistant|user)\s*>",
]
_INJECTION = re.compile("|".join(f"(?:{p})" for p in _INJECTION_PATTERNS), re.IGNORECASE)
_FENCE = re.compile(r"`{3,}|~{3,}")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION.search(text or ""))


def sanitize_code(code: str) -> tuple[str, bool]:
    """Return (safe_code, removed_anything)."""
    removed = False
    lines = []
    for line in _CONTROL.sub("", code or "").splitlines():
        if looks_like_injection(line):
            removed = True
            continue
        lines.append(_FENCE.sub("''", line.rstrip()))
    lines = textwrap.dedent("\n".join(lines)).splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if len(lines) > MAX_EXAMPLE_LINES:
        lines = lines[:MAX_EXAMPLE_LINES]
        removed = True
    out = "\n".join(lines)
    if len(out) > MAX_EXAMPLE_CHARS:
        out = out[:MAX_EXAMPLE_CHARS].rstrip()
        removed = True
    return out, removed


def sanitize_text(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    """One-line, markup-free prose. Returns "" when the text looks like an injection."""
    text = _CONTROL.sub("", text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # markdown links -> label
    text = _FENCE.sub(" ", text)
    text = re.sub(r"(?<![\w`])@[A-Za-z0-9-]+", "", text)  # no @mentions in generated text
    text = re.sub(r"\s+", " ", text).strip()
    if looks_like_injection(text):
        return ""
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text
