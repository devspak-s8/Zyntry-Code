"""OpenAI-compatible provider.

Works with OpenAI and any OpenAI-compatible endpoint (OpenRouter, Groq, Together,
Ollama, vLLM, ...) by setting ``OPENAI_BASE_URL``.

Uses the synchronous ``httpx.Client``: this is the outbound-HTTP style that is
known to work inside Python Workers (see the official ``sync-http-clients``
example), whereas stdlib raw-socket clients do not.
"""

import asyncio
import json

import httpx

from providers.base import (Provider, LLMResult, emit_token, iter_sse_events,
                            with_retries, with_stream_retries)
from domain.escalation import estimate_tokens


class OpenAICompatProvider(Provider):
    name = "openai"

    def _config(self) -> tuple[str, str]:
        key = str(self.runtime.get("OPENAI_API_KEY", "") or "")
        base = str(self.runtime.get("OPENAI_BASE_URL", "https://api.openai.com/v1") or "").rstrip("/")
        return key, base

    def _client(self) -> httpx.Client:
        """Sync httpx client — the outbound-HTTP style known to work on Workers."""
        return httpx.Client(timeout=120.0)

    def supports_streaming(self) -> bool:
        return True

    async def complete(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResult:
        key, base = self._config()
        if not key:
            return LLMResult(model=model, provider=self.name, error="OPENAI_API_KEY is not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
        }
        # Reasoning models (o1/o3/o4/gpt-5) only accept the default temperature.
        if not model.lower().startswith(("o1", "o3", "o4", "gpt-5")):
            payload["temperature"] = temperature
        if max_tokens:
            # Reasoning models (o1/o3/o4/gpt-5) use max_completion_tokens.
            if model.lower().startswith(("o1", "o3", "o4", "gpt-5")):
                payload["max_completion_tokens"] = max_tokens
            else:
                payload["max_tokens"] = max_tokens

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        def call() -> LLMResult:
            try:
                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(f"{base}/chat/completions", json=payload, headers=headers)
                if resp.status_code >= 400:
                    return LLMResult(model=model, provider=self.name,
                                     error=f"provider returned {resp.status_code}: {resp.text[:500]}")
                data = resp.json()
                choice = data["choices"][0]["message"]
                text = choice.get("content") or ""
                usage = data.get("usage", {})
                tokens_in = usage.get("prompt_tokens", estimate_tokens(prompt))
                tokens_out = usage.get("completion_tokens", estimate_tokens(text))
                return LLMResult(text=text, model=model, provider=self.name,
                                 tokens_in=int(tokens_in), tokens_out=int(tokens_out), raw=data)
            except httpx.HTTPError as exc:
                return LLMResult(model=model, provider=self.name, error=f"http error: {exc}")

        return await with_retries(call)

    async def complete_stream(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        on_token=None,
    ) -> LLMResult:
        """Complete a chat request using OpenAI's SSE streaming protocol.

        OpenAI sends one JSON object per ``data:`` frame and terminates the
        stream with ``data: [DONE]``.  Usage is normally sent in a final chunk
        when ``stream_options.include_usage`` is enabled; token estimates keep
        the result useful for compatible endpoints that do not implement it.
        """
        key, base = self._config()
        if not key:
            return LLMResult(model=model, provider=self.name,
                             error="OPENAI_API_KEY is not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            # OpenAI includes usage in a separate terminal chunk when this is
            # requested.  OpenAI-compatible servers may simply ignore it.
            "stream_options": {"include_usage": True},
        }
        # Reasoning models (o1/o3/o4/gpt-5) only accept the default temperature.
        if not model.lower().startswith(("o1", "o3", "o4", "gpt-5")):
            payload["temperature"] = temperature
        if max_tokens:
            # Reasoning models (o1/o3/o4/gpt-5) use max_completion_tokens.
            if model.lower().startswith(("o1", "o3", "o4", "gpt-5")):
                payload["max_completion_tokens"] = max_tokens
            else:
                payload["max_tokens"] = max_tokens

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        async def attempt() -> LLMResult:
            parts: list[str] = []
            events: list[dict] = []
            usage: dict = {}
            try:
                with self._client() as client:
                    with client.stream("POST", f"{base}/chat/completions",
                                       json=payload, headers=headers) as resp:
                        if resp.status_code >= 400:
                            # A streamed response has not been read yet;
                            # consume it before accessing ``resp.text``.
                            resp.read()
                            return LLMResult(
                                text="".join(parts), model=model, provider=self.name,
                                error=f"provider returned {resp.status_code}: {resp.text[:500]}",
                                raw=events,
                            )

                        for event_text in iter_sse_events(resp.iter_lines()):
                            if event_text == "[DONE]":
                                break
                            try:
                                data = json.loads(event_text)
                            except (TypeError, ValueError):
                                # Keep the stream tolerant of comments or
                                # vendor-specific non-JSON data frames.
                                continue
                            if not isinstance(data, dict):
                                continue
                            events.append(data)
                            usage.update(data.get("usage") or {})
                            choices = data.get("choices") or []
                            if not choices:
                                continue
                            delta = choices[0].get("delta") or {}
                            text = delta.get("content") or ""
                            if isinstance(text, list):
                                text = "".join(
                                    item.get("text", "") for item in text
                                    if isinstance(item, dict))
                            if not isinstance(text, str) or not text:
                                continue
                            parts.append(text)
                            await emit_token(on_token, text)
            except httpx.HTTPError as exc:
                return LLMResult(text="".join(parts), model=model, provider=self.name,
                                 error=f"http error: {exc}", raw=events)

            text = "".join(parts)
            tokens_in = usage.get("prompt_tokens", estimate_tokens(prompt))
            tokens_out = usage.get("completion_tokens", estimate_tokens(text))
            return LLMResult(text=text, model=model, provider=self.name,
                             tokens_in=int(tokens_in), tokens_out=int(tokens_out),
                             raw=events)

        return await with_stream_retries(attempt)
