"""FastAPI application assembly for Zyntry Code."""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from metrics import metrics
from routers import (artifacts, completion, executions, health, ingest,
                     metrics as metrics_router, models, semantic, stream, tasks,
                     verification, webhooks, workers, workspaces)
from security import security_middleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zyntry-code")


def _allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()]


def _provider_overrides(request: Request) -> dict[str, str]:
    """Caller-supplied provider credentials (bring-your-own-key).

    The dashboard can send its own provider key per request:

    - ``X-Zyntry-Provider``:       openai | anthropic | openrouter (default openai)
    - ``X-Zyntry-Provider-Key``:   the caller's API key
    - ``X-Zyntry-Provider-Base``:  optional OpenAI-compatible base URL
      (e.g. OpenRouter); implied for the openrouter provider.

    The key is applied to this request's runtime only — nothing is stored,
    logged, or shared with other requests. Without a key the server's own
    (free Workers AI) providers are used, exactly as before.
    """
    key = (request.headers.get("x-zyntry-provider-key") or "").strip()
    if not key:
        return {}
    provider = ((request.headers.get("x-zyntry-provider") or "openai").strip() or "openai").lower()
    base = (request.headers.get("x-zyntry-provider-base") or "").strip()
    overrides: dict[str, str] = {}
    if provider == "anthropic":
        overrides["ANTHROPIC_API_KEY"] = key
    else:
        overrides["OPENAI_API_KEY"] = key
        if provider == "openrouter" and not base:
            base = "https://openrouter.ai/api/v1"
        if base:
            overrides["OPENAI_BASE_URL"] = base.rstrip("/")
    return overrides


app = FastAPI(
    title="Zyntry Code",
    description="Adaptive AI Engineering Agent — backend orchestration service",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    overrides = _provider_overrides(request)
    if overrides:
        request.scope["runtime_overrides"] = overrides
    response = await security_middleware(request, call_next)
    metrics.incr("http_requests_total")
    metrics.incr(f"http_requests_{request.method.lower()}")
    return response


app.include_router(health.router)
app.include_router(metrics_router.router)
app.include_router(models.router)
app.include_router(completion.router)
app.include_router(tasks.router)
app.include_router(stream.router)
app.include_router(ingest.router)
app.include_router(executions.router)
app.include_router(verification.router)
app.include_router(artifacts.router)
app.include_router(workspaces.router)
app.include_router(workers.router)
app.include_router(semantic.router)
app.include_router(webhooks.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    metrics.incr("http_errors_total")
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": "unexpected server error"})
