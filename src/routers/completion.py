"""Provider-backed token completion streaming."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from domain.catalog import get_model
from providers import available_providers, build_provider, provider_order
from providers.base import LLMResult
from routers.stream import format_sse
from runtime import Runtime, get_runtime
from schemas import CompletionStreamRequest

router = APIRouter(tags=["completion"])
_CONFIGURABLE_PROVIDERS = {"openai", "anthropic", "workers_ai"}


def _select_provider(body: CompletionStreamRequest, runtime: Runtime) -> str:
    if body.provider:
        if (body.provider in _CONFIGURABLE_PROVIDERS
                and body.provider not in available_providers(runtime)):
            raise HTTPException(
                status_code=503,
                detail=f"provider {body.provider!r} is not configured")
        return body.provider

    catalog_model = get_model(body.model)
    if catalog_model is not None:
        if catalog_model.provider not in available_providers(runtime):
            raise HTTPException(
                status_code=503,
                detail=f"provider {catalog_model.provider!r} is not configured")
        return catalog_model.provider

    order = provider_order(runtime)
    if order:
        return order[0]
    raise HTTPException(
        status_code=503,
        detail="no LLM provider is configured; set OPENAI_API_KEY, "
               "ANTHROPIC_API_KEY, or configure Workers AI")


def _result_payload(result: LLMResult) -> dict:
    return {
        "text": result.text,
        "model": result.model,
        "provider": result.provider,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
    }


@router.post("/completion/stream")
async def completion_stream(
    body: CompletionStreamRequest,
    runtime: Runtime = Depends(get_runtime),
) -> StreamingResponse:
    provider_name = _select_provider(body, runtime)
    try:
        provider = build_provider(provider_name, runtime)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)

    async def on_token(text: str) -> None:
        await queue.put({"type": "token", "text": text, "token": text})

    async def run_completion() -> None:
        try:
            result = await provider.complete_stream(
                body.model,
                body.prompt,
                system=body.system,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                on_token=on_token,
            )
            if result.error:
                await queue.put({
                    "type": "error",
                    "error": "provider request failed",
                    "detail": "provider request failed",
                    "text": result.text,
                })
            else:
                await queue.put({"type": "done", **_result_payload(result)})
        except Exception:  # noqa: BLE001 - keep the SSE stream terminable
            await queue.put({"type": "error", "error": "provider request failed",
                             "detail": "provider request failed"})

    task = asyncio.create_task(run_completion())

    async def event_stream():
        try:
            while True:
                event = await queue.get()
                yield format_sse(event)
                if event["type"] in ("done", "error"):
                    return
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
