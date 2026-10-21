"""Authentication, request limits, and command-policy helpers."""

import asyncio
import hmac
import re
import time
from collections import defaultdict, deque
from pathlib import PurePosixPath

from fastapi import Request
from fastapi.responses import JSONResponse


def secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        now = time.time()
        async with self._lock:
            window = self._hits[key]
            while window and now - window[0] > window_s:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(now)
            return True


rate_limiter = RateLimiter()
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC_PATHS = {"/health"}
_SHELL_META = re.compile(r"[;&|<>`\r\n]|\$\(")


def insecure_local_allowed(runtime) -> bool:
    """Only tests/local development may explicitly opt out of auth."""
    return runtime.get_bool("ALLOW_INSECURE_LOCAL", False) and runtime.env is None


def has_shell_metacharacters(command: str) -> bool:
    single = double = escaped = False
    text = command or ""
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and not single:
            escaped = True
            continue
        if char == "'" and not double:
            single = not single
            continue
        if char == '"' and not single:
            double = not double
            continue
        if not single and not double and (char in ";&|<>\r\n" or ord(char) == 96 or text[index:index + 2] == '$('):
            return True
    return single or double


def is_sensitive_path(path: str) -> bool:
    parts = {part.lower() for part in PurePosixPath(path.replace("\\", "/")).parts}
    name = PurePosixPath(path.replace("\\", "/")).name.lower()
    return bool(parts & {".git", ".ssh", ".aws", ".gnupg"}) or name in {
        ".env", ".env.local", ".env.production", ".dev.vars", "credentials.json",
        "service-account.json", "id_rsa", "id_ed25519",
    } or name.endswith((".pem", ".key", ".p12", ".pfx"))


def require_runner_token(request: Request, runtime) -> None:
    """Require a runner-scoped credential for worker-only endpoints."""
    # Never fall back to the user/API token: runner endpoints can return
    # decrypted workspace secrets and must have an independently rotatable
    # credential.
    expected = runtime.get("RUNNER_TOKEN")
    if not expected:
        if insecure_local_allowed(runtime):
            return
        raise PermissionError("runner authentication is not configured")
    bearer = request.headers.get("authorization", "")
    supplied = request.headers.get("x-runner-token", "")
    if not (secure_compare(bearer, f"Bearer {expected}") or
            secure_compare(supplied, str(expected))):
        raise PermissionError("missing or invalid runner credential")


async def security_middleware(request: Request, call_next):
    from runtime import get_runtime

    runtime = get_runtime(request)
    path = request.url.path

    content_length = request.headers.get("content-length")
    try:
        if request.method in MUTATING_METHODS and content_length and int(content_length) > 25 * 1024 * 1024:
            return JSONResponse(status_code=413, content={"error": "request_too_large"})
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "invalid_content_length"})

    if path not in PUBLIC_PATHS and request.method != "OPTIONS":
        token = runtime.get("API_TOKEN")
        header = request.headers.get("authorization", "")
        if not token:
            if not insecure_local_allowed(runtime):
                return JSONResponse(status_code=503, content={
                    "error": "auth_not_configured",
                    "detail": "API_TOKEN must be configured before serving protected routes",
                })
        elif not secure_compare(header, f"Bearer {token}"):
            return JSONResponse(status_code=401, content={
                "error": "unauthorized",
                "detail": "missing or invalid bearer token",
            })

    if request.method in MUTATING_METHODS:
        limit = runtime.get_int("RATE_LIMIT_PER_MINUTE", 120)
        proxy_ip = request.headers.get("cf-connecting-ip") if runtime.get_bool("TRUST_PROXY_HEADERS") else None
        host = request.client.host if request.client else None
        client = proxy_ip or host or "unknown"
        try:
            import store
            allowed = await store.rate_limit_allow(runtime.db, client, limit)
        except Exception:  # noqa: BLE001
            allowed = await rate_limiter.allow(client, limit)
        if not allowed:
            return JSONResponse(status_code=429, content={
                "error": "rate_limited", "detail": "too many requests",
            })

    return await call_next(request)
