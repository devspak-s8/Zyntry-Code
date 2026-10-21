"""Cloudflare Workers AI provider (edge inference via the ``AI`` binding).

Requires the ``AI`` binding configured in ``wrangler.jsonc``; no API key needed.
"""

import json

from providers.base import Provider, LLMResult, emit_token, iter_sse_events
from domain.escalation import estimate_tokens


def _text_from_dict(data: dict, depth: int = 0) -> str:
    """Dig generated text out of any Workers AI chat response shape.

    Known shapes:
    - legacy:      {"response": "...", "usage": {...}}
    - OpenAI-like: {"choices": [{"message": {"content": "..."}}], "usage": {...}}
    - content parts: {"choices": [{"message": {"content": [{"text": "..."}]}}]}
    - wrapped:     {"result": <one of the above>} or {"data": <...>}
    - raw SSE:     {"raw_response": "data: {...}\\n\\n..." } (frames carrying
      response / delta.content / message.content)
    """
    if depth > 4 or not isinstance(data, dict):
        return ""

    # 1) Legacy single-payload shape
    response = data.get("response")
    if isinstance(response, str) and response.strip():
        return response

    # 2) OpenAI-style chat completion
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message") or choice.get("delta") or {}
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                text = "".join(
                    str(part.get("text", "")) for part in content
                    if isinstance(part, dict))
                if text.strip():
                    return text

    # 3) Wrapped variants ({result: {...}} / {data: {...}} / {output: {...}})
    for key in ("result", "data", "output"):
        inner = data.get(key)
        if isinstance(inner, dict):
            text = _text_from_dict(inner, depth + 1)
            if text.strip():
                return text
        elif isinstance(inner, str) and inner.strip() and key in ("result", "output"):
            return inner

    # 4) Raw SSE stream frames (raw=True for chat models)
    raw = data.get("raw_response")
    if isinstance(raw, str) and raw.strip():
        text = ""
        for frame in iter_sse_events(raw.splitlines()):
            text += _text_from_frame(frame)
        return text
    if isinstance(raw, list):
        text = ""
        for frame in raw:
            if isinstance(frame, str):
                text += _text_from_frame(frame)
            elif isinstance(frame, dict):
                text += _text_from_dict(frame, depth + 1)
        if text.strip():
            return text

    # 5) Reasoning-style output (content empty, reasoning carries the answer)
    for key in ("reasoning_content", "reasoning"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return ""


def _text_from_frame(frame: str) -> str:
    """Extract incremental text from one SSE frame of a Workers AI raw stream."""
    text = ""
    stripped = frame.strip()
    if not stripped or stripped == "[DONE]":
        return ""
    try:
        data = json.loads(stripped.removeprefix("data:").strip())
    except (TypeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    response = data.get("response")
    if isinstance(response, str):
        text += response
    for key in ("choices", "delta", "message"):
        value = data.get(key)
        if isinstance(value, dict):
            content = value.get("content")
            if isinstance(content, str):
                text += content
    return text


def _usage_from_dict(data: dict) -> dict:
    if isinstance(data, dict):
        for key in ("usage",):
            value = data.get(key)
            if isinstance(value, dict) and value:
                return value
        for key in ("result", "data", "output"):
            inner = data.get(key)
            if isinstance(inner, dict):
                nested = _usage_from_dict(inner)
                if nested:
                    return nested
    return {}


class WorkersAIProvider(Provider):
    name = "workers_ai"

    async def complete(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResult:
        ai = self.runtime.workers_ai
        if ai is None:
            return LLMResult(model=model, provider=self.name,
                             error="Workers AI binding (AI) is not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {"messages": messages, "temperature": temperature}
        if max_tokens:
            body["max_tokens"] = max_tokens

        try:
            # Request the raw response so usage stats (tokens) are included when
            # the model provides them; fall back to the plain call if the local
            # runtime doesn't accept the options argument.
            try:
                result = await ai.run(model, body, {"raw": True})
            except TypeError:
                result = await ai.run(model, body)
        except Exception as exc:  # noqa: BLE001 - FFI raises generic exceptions
            return LLMResult(model=model, provider=self.name, error=f"workers ai error: {exc}")

        usage: dict = _usage_from_dict(result if isinstance(result, dict) else {})
        text = _text_from_dict(result) if isinstance(result, dict) else str(result or "")

        tokens_in = usage.get("prompt_tokens") or estimate_tokens(prompt)
        tokens_out = usage.get("completion_tokens") or estimate_tokens(text)

        return LLMResult(text=text, model=model, provider=self.name,
                         tokens_in=int(tokens_in), tokens_out=int(tokens_out),
                         raw=result)

    def supports_streaming(self) -> bool:
        return True

    async def complete_stream(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        on_token=None,
    ) -> LLMResult:
        """Stream via the non-raw ``run`` iterator when available, else fall
        back to a complete() call emitted as a single token."""
        ai = self.runtime.workers_ai
        if ai is None:
            return LLMResult(model=model, provider=self.name,
                             error="Workers AI binding (AI) is not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {"messages": messages, "temperature": temperature}
        if max_tokens:
            body["max_tokens"] = max_tokens

        try:
            result = await ai.run(model, body)
        except Exception as exc:  # noqa: BLE001
            return LLMResult(model=model, provider=self.name, error=f"workers ai error: {exc}")

        # Streaming on the Python binding requires a stream=True option whose
        # return type varies; emit the full response as a single token to stay
        # compatible, using the same shape-tolerant extraction as complete().
        usage = _usage_from_dict(result if isinstance(result, dict) else {})
        text = _text_from_dict(result) if isinstance(result, dict) else str(result or "")
        tokens_in = usage.get("prompt_tokens") or estimate_tokens(prompt)
        tokens_out = usage.get("completion_tokens") or estimate_tokens(text)
        await emit_token(on_token, text)
        return LLMResult(text=text, model=model, provider=self.name,
                         tokens_in=int(tokens_in), tokens_out=int(tokens_out),
                         raw=result if isinstance(result, dict) else {})