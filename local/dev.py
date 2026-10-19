"""Local development server (uvicorn) — no Cloudflare tooling required.

Usage:
    uv run uvicorn local.dev:app --reload --port 8787
or, with plain Python:
    python -m pip install -e ".[dev]"   # or: pip install fastapi httpx uvicorn
    python -m uvicorn local.dev:app --reload --port 8787

Provide LLM keys via a ``.env`` file in the project root (see .dev.vars.example):
    OPENAI_API_KEY=sk-...
    ANTHROPIC_API_KEY=sk-ant-...
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from local import env


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = env.configure()
    await env.init_db(runtime)
    yield


def build() -> FastAPI:
    from app import app
    return app


app = build()
app.router.lifespan_context = lifespan