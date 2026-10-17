"""A small GitHub REST client: only the endpoints Folklore needs."""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from typing import Any

import requests

API = "https://api.github.com"
USER_AGENT = "folklore-skills/0.1 (+https://github.com/ravirepswal108-lgtm/Folklore)"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(
        self, token: str = "", base_url: str = API, session: requests.Session | None = None
    ):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": USER_AGENT,
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    # -- low level -----------------------------------------------------------------

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        if not url.startswith("http"):
            url = f"{self.base_url}{url}"
        for attempt in range(4):
            resp = self.session.request(method, url, timeout=30, **kwargs)
            if resp.status_code in (500, 502, 503, 504):
                time.sleep(2**attempt)
                continue
            if resp.status_code in (403, 429) and resp.headers.get("X-RateLimit-Remaining") == "0":
                reset = int(resp.headers.get("X-RateLimit-Reset", "0"))
                wait = max(0, reset - int(time.time())) + 1
                if wait > 300:
                    raise GitHubError(
                        f"GitHub rate limit reached; it resets in {wait // 60} minutes. "
                        "Set GITHUB_TOKEN to get a higher limit."
                    )
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                raise GitHubError(
                    f"GitHub {method} {url} failed with {resp.status_code}: {resp.text[:200]}"
                )
            return resp
        raise GitHubError(f"GitHub {method} {url} kept failing; giving up.")

    def paginate(
        self, path: str, params: dict[str, Any] | None = None, limit: int | None = None
    ) -> Iterator[dict]:
        params = {"per_page": 100, **(params or {})}
        url: str | None = path
        count = 0
        while url:
            resp = self._request("GET", url, params=params)
            params = None  # the "next" link already carries the query string
            for item in resp.json():
                yield item
                count += 1
                if limit and count >= limit:
                    return
            url = resp.links.get("next", {}).get("url")

    # -- endpoints -----------------------------------------------------------------

    def closed_pulls(self, repo: str, limit: int) -> Iterator[dict]:
        return self.paginate(
            f"/repos/{repo}/pulls",
            {"state": "closed", "sort": "updated", "direction": "desc"},
            limit=limit,
        )

    def review_comments(
        self, repo: str, since: str | None = None, limit: int | None = None
    ) -> Iterator[dict]:
        params: dict[str, Any] = {"sort": "created", "direction": "desc"}
        if since:
            params["since"] = since
        return self.paginate(f"/repos/{repo}/pulls/comments", params, limit=limit)

    def reviews(self, repo: str, number: int) -> Iterator[dict]:
        return self.paginate(f"/repos/{repo}/pulls/{number}/reviews")

    def pull(self, repo: str, number: int) -> dict:
        return self._request("GET", f"/repos/{repo}/pulls/{number}").json()

    def pull_files(self, repo: str, number: int, limit: int = 300) -> list[dict]:
        return list(self.paginate(f"/repos/{repo}/pulls/{number}/files", limit=limit))

    def issue_comments(self, repo: str, number: int) -> Iterator[dict]:
        return self.paginate(f"/repos/{repo}/issues/{number}/comments")

    def create_issue_comment(self, repo: str, number: int, body: str) -> dict:
        return self._request(
            "POST", f"/repos/{repo}/issues/{number}/comments", json={"body": body}
        ).json()

    def update_issue_comment(self, repo: str, comment_id: int, body: str) -> dict:
        return self._request(
            "PATCH", f"/repos/{repo}/issues/comments/{comment_id}", json={"body": body}
        ).json()

    def delete_issue_comment(self, repo: str, comment_id: int) -> None:
        self._request("DELETE", f"/repos/{repo}/issues/comments/{comment_id}")


_PR_URL = re.compile(r"/pulls/(\d+)$")


def pr_number_from_url(url: str) -> int | None:
    match = _PR_URL.search(url or "")
    return int(match.group(1)) if match else None
