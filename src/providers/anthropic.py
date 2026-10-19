"""Anthropic provider."""

import json

import httpx

from providers.base import (Provider, LLMResult, emit_token, iter_sse_events,
                            with_retries, with_stream_retries)
from domain.escalation import estimate_tokens


class AnthropicProvider(Provider):
    name = "anthropic"

    def _client(self) -> httpx.Client:
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
        key = str(self.runtime.get("ANTHROPIC_API_KEY", "") or "")
        if not key:
            return LLMResult(model=model, provider=self.name, error="ANTHROPIC_API_KEY is not configured")

        base = str(self.runtime.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") or "").rstrip("/")
        payload = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        def call() -> LLMResult:
            try:
                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(f"{base}/v1/messages", json=payload, headers=headers)
                if resp.status_code >= 400:
                    return LLMResult(model=model, provider=self.name,
                                     error=f"provider returned {resp.status_code}: {resp.text[:500]}")
                data = resp.json()
                content = data.get("content") or []
                text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
                usage = data.get("usage", {})
                tokens_in = usage.get("input_tokens", estimate_tokens(prompt))
                tokens_out = usage.get("output_tokens", estimate_tokens(text))
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
        """Complete a message using Anthropic's event-based SSE stream."""
        key = str(self.runtime.get("ANTHROPIC_API_KEY", "") or "")
        if not key:
            return LLMResult(model=model, provider=self.name,
                             error="ANTHROPIC_API_KEY is not configured")

        base = str(self.runtime.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") or "").rstrip("/")
        payload = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": True,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async def attempt() -> LLMResult:
            parts: list[str] = []
            events: list[dict] = []
            input_tokens = 0
            output_tokens = 0
            try:
                with self._client() as client:
                    with client.stream("POST", f"{base}/v1/messages",
                                       json=payload, headers=headers) as resp:
                        if resp.status_code >= 400:
                            resp.read()
                            return LLMResult(
                                text="".join(parts), model=model, provider=self.name,
                                error=f"provider returned {resp.status_code}: {resp.text[:500]}",
                                raw=events,
                            )

                        for event_text in iter_sse_events(resp.iter_lines()):
                            try:
                                data = json.loads(event_text)
                            except (TypeError, ValueError):
                                continue
                            if not isinstance(data, dict):
                                continue
                            events.append(data)
                            event_type = data.get("type")
                            if event_type == "message_start":
                                usage = (data.get("message") or {}).get("usage") or {}
                                input_tokens = usage.get("input_tokens") or input_tokens
                            elif event_type == "message_delta":
                                usage = data.get("usage") or {}
                                output_tokens = usage.get("output_tokens") or output_tokens
                            elif event_type == "content_block_delta":
                                delta = data.get("delta") or {}
                                if delta.get("type") != "text_delta":
                                    continue
                                text = delta.get("text") or ""
                                if not isinstance(text, str) or not text:
                                    continue
                                parts.append(text)
                                await emit_token(on_token, text)
                            elif event_type == "error":
                                error = (data.get("error") or {}).get("message") or "provider stream error"
                                return LLMResult(
                                    text="".join(parts), model=model, provider=self.name,
                                    tokens_in=int(input_tokens or estimate_tokens(prompt)),
                                    tokens_out=int(output_tokens or estimate_tokens("".join(parts))),
                                    error=str(error), raw=events,
                                )
            except httpx.HTTPError as exc:
                return LLMResult(text="".join(parts), model=model, provider=self.name,
                                 tokens_in=int(input_tokens or estimate_tokens(prompt)),
                                 tokens_out=int(output_tokens or estimate_tokens("".join(parts))),
                                 error=f"http error: {exc}", raw=events)

            text = "".join(parts)
            return LLMResult(
                text=text, model=model, provider=self.name,
                tokens_in=int(input_tokens or estimate_tokens(prompt)),
                tokens_out=int(output_tokens or estimate_tokens(text)),
                raw=events,
            )

        return await with_stream_retries(attempt)
