"""API security: bearer-token auth and simple rate limiting.

- If ``API_TOKEN`` is configured (a Workers secret / env var), every endpoint
  except ``/health`` requires ``Authorization: Bearer <token>``.
- Mutating requests are rate-limited per client IP (in-memory sliding window;
  per-isolate on Workers). For production-scale enforcement, pair this with
  Cloudflare's rate limiting rules — the middleware is the local guarantee.

Constant-time comparison via ``hmac`` avoids naive string-timing leaks.
"""

import asyncio
import hmac
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse


def secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        now = time.monotonic()
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


async def security_middleware(request: Request, call_next):
    """Applied by app.py. Needs a runtime to resolve API_TOKEN / rate limits."""
    from runtime import get_runtime

    runtime = get_runtime(request)
    path = request.url.path

    if path != "/health":
        token = runtime.get("API_TOKEN")
        if token:
            header = request.headers.get("authorization", "")
            if not secure_compare(header, f"Bearer {token}"):
                return JSONResponse(status_code=401, content={"error": "unauthorized",
                                                              "detail": "missing or invalid bearer token"})

    if request.method in MUTATING_METHODS:
        limit = runtime.get_int("RATE_LIMIT_PER_MINUTE", 120)
        cf_ip = request.headers.get("cf-connecting-ip")
        host = request.client.host if request.client else None
        client = cf_ip or host or "unknown"

        # Cross-isolate counter in D1; fall back to the in-memory limiter if
        # the D1 write fails (never block a request because of telemetry).
        try:
            import store
            allowed = await store.rate_limit_allow(runtime.db, client, limit)
        except Exception:  # noqa: BLE001
            allowed = await rate_limiter.allow(client, limit)
        if not allowed:
            return JSONResponse(status_code=429, content={"error": "rate_limited",
                                                          "detail": "too many requests"})

    return await call_next(request)