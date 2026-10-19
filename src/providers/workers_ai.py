"""Cloudflare Workers AI provider (edge inference via the ``AI`` binding).

Requires the ``AI`` binding configured in ``wrangler.jsonc``; no API key needed.
"""

from providers.base import Provider, LLMResult
from domain.escalation import estimate_tokens


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

        usage: dict = {}
        if isinstance(result, dict):
            text = result.get("response", "")
            if not isinstance(text, str):
                text = str(text)
            usage = result.get("usage") or {}
        else:
            text = str(result)
            result = {}

        tokens_in = usage.get("prompt_tokens") or estimate_tokens(prompt)
        tokens_out = usage.get("completion_tokens") or estimate_tokens(text)

        return LLMResult(text=text, model=model, provider=self.name,
                         tokens_in=int(tokens_in), tokens_out=int(tokens_out),
                         raw=result)