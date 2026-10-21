"""Delivery: create pull requests on GitHub (Phase 5)."""

import re
from urllib.parse import urlparse

import httpx


async def create_pull_request(*, repo_url: str | None, token: str | None,
                              title: str, body: str, base: str, head: str) -> dict:
    """Open a PR via the GitHub REST API.

    ``repo_url`` must be an https GitHub URL (e.g. https://github.com/o/r).
    ``token`` is a GitHub PAT (or GITHUB_TOKEN) — never logged.
    """
    if not token:
        return {"created": False, "error": "missing GitHub token (workspace secret GITHUB_TOKEN)"}
    slug = _repo_slug(repo_url)
    if not slug:
        return {"created": False, "error": f"cannot derive GitHub repo from {repo_url}"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{slug}/pulls",
                json={"title": title[:256], "body": body[:5000], "base": base, "head": head},
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json",
                         "X-GitHub-Api-Version": "2022-11-28"})
        if resp.status_code >= 400:
            return {"created": False, "error": f"github returned {resp.status_code}"}
        data = resp.json()
        return {"created": True, "number": data.get("number"), "url": data.get("html_url")}
    except httpx.HTTPError as exc:
        return {"created": False, "error": f"http error: {exc}"}


def _repo_slug(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    parsed = urlparse(repo_url.strip().rstrip("/"))
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.query or parsed.fragment:
        return None
    slug = parsed.path.strip("/")
    if slug.endswith(".git"):
        slug = slug[:-4]
    parts = slug.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part or "") for part in parts):
        return None
    return slug
