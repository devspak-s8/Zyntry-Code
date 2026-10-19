"""LLM provider abstraction.

Each provider exposes a single ``complete`` coroutine. Providers are selected at
routing time based on which credentials/bindings are actually configured.

Streaming providers additionally implement ``complete_stream``, which emits
tokens incrementally through an ``on_token(text)`` callback. The base class
fallback streams the final text as a single chunk.
"""

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator

from runtime import Runtime


@dataclass
class LLMResult:
    text: str = ""
    model: str = ""
    provider: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None
    raw: Any = None


class Provider:
    name: str = "base"

    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    async def complete(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResult:
        raise NotImplementedError

    def supports_streaming(self) -> bool:
        return False

    async def complete_stream(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        on_token=None,
    ) -> LLMResult:
        """Stream tokens; ``on_token(text)`` is called per chunk. Defaults to a
        single-chunk fallback over ``complete``."""
        result = await self.complete(model, prompt, system=system,
                                     temperature=temperature, max_tokens=max_tokens)
        if result.text:
            await emit_token(on_token, result.text)
        return result


async def emit_token(on_token, text: str) -> None:
    """Invoke an ``on_token`` callback, awaiting it if it returns an awaitable.

    Callbacks may be plain functions (sync) or coroutine functions; both are
    supported so providers stay agnostic to the consumer.
    """
    if on_token is None or not text:
        return
    result = on_token(text)
    if inspect.isawaitable(result):
        await result


def iter_sse_events(lines: Iterable[str]) -> Iterator[str]:
    """Yield each SSE event's ``data:`` payload from an iterable of raw lines.

    ``data:`` lines accumulate until a blank line terminates the event — the
    framing used by both OpenAI and Anthropic streaming APIs. Multiple data
    lines are joined with newlines, and a trailing event without a blank line
    is still yielded.
    """
    data_parts: list[str] = []
    for line in lines:
        line = line.rstrip("\r\n")
        if line.startswith("data:"):
            data_parts.append(line[len("data:"):].strip())
        elif line == "" and data_parts:
            yield "\n".join(data_parts)
            data_parts = []
    if data_parts:
        yield "\n".join(data_parts)


async def with_retries(call: Callable[[], LLMResult], retries: int = 3,
                       base_delay: float = 0.5) -> LLMResult:
    """Retry transient provider failures (429/5xx/network) with backoff.

    ``call`` is synchronous (sync httpx per Python Workers guidance); the
    backoff sleeps happen on the event loop between attempts.
    """
    last: LLMResult | None = None
    for attempt in range(retries):
        result = call()
        if not result.error or attempt == retries - 1:
            return result
        if not is_transient_error(result.error):
            return result
        last = result
        await asyncio.sleep(base_delay * (2 ** attempt))
    return last or LLMResult(error="retries exhausted")


async def with_stream_retries(attempt: Callable[[], Any], retries: int = 3,
                              base_delay: float = 0.5) -> LLMResult:
    """Retry transient failures of an async streaming attempt.

    Unlike ``with_retries`` this never re-runs an attempt once any tokens have
    been emitted (``result.text`` is non-empty), because re-streaming would
    send duplicate tokens to the client. A partial result with an error is
    returned as-is so the consumer can report the interruption.
    """
    last: LLMResult | None = None
    for attempt_number in range(retries):
        result = await attempt()
        if (not result.error or attempt_number == retries - 1
                or not is_transient_error(result.error) or result.text):
            return result
        last = result
        await asyncio.sleep(base_delay * (2 ** attempt_number))
    return last or LLMResult(error="retries exhausted")


def is_transient_error(error: str) -> bool:
    lowered = error.lower()
    return any(k in lowered for k in ("429", "500", "502", "503", "504", "timeout", "connection", "rate limit"))


def available_providers(runtime: Runtime) -> set[str]:
    names: set[str] = set()
    if runtime.get("OPENAI_API_KEY"):
        names.add("openai")
    if runtime.get("ANTHROPIC_API_KEY"):
        names.add("anthropic")
    if runtime.workers_ai is not None:
        names.add("workers_ai")
    return names


def provider_order(runtime: Runtime) -> list[str]:
    raw = runtime.get("PROVIDER_ORDER", "openai,anthropic,workers_ai")
    order = [p.strip() for p in str(raw).split(",") if p.strip()]
    avail = available_providers(runtime)
    return [p for p in order if p in avail]


def build_provider(name: str, runtime: Runtime) -> Provider:
    if name == "openai":
        from providers.openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(runtime)
    if name == "anthropic":
        from providers.anthropic import AnthropicProvider
        return AnthropicProvider(runtime)
    if name == "workers_ai":
        from providers.workers_ai import WorkersAIProvider
        return WorkersAIProvider(runtime)
    raise ValueError(f"unknown provider: {name}")