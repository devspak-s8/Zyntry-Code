"""Provider-native completion streaming and the public completion SSE route."""

import json

import httpx
from fastapi.testclient import TestClient

from app import app
from providers.base import LLMResult
from providers.anthropic import AnthropicProvider
from providers.openai_compat import OpenAICompatProvider


def _stream_response(body: str, request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content=body.encode(),
        request=request,
    )


async def test_openai_complete_stream_parses_deltas_and_usage(monkeypatch):
    stream = (
        'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":2}}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert payload["stream_options"] == {"include_usage": True}
        assert request.url.path == "/v1/chat/completions"
        return _stream_response(stream, request)

    provider = OpenAICompatProvider(type("Runtime", (), {
        "get": lambda self, key, default=None: {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://example.test/v1",
        }.get(key, default),
    })())
    monkeypatch.setattr(provider, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    tokens: list[str] = []

    result = await provider.complete_stream("gpt-test", "say hello", on_token=tokens.append)

    assert result.error is None
    assert result.text == "Hello"
    assert tokens == ["Hel", "lo"]
    assert result.tokens_in == 7
    assert result.tokens_out == 2


async def test_anthropic_complete_stream_parses_text_events_and_usage(monkeypatch):
    stream = (
        'event: message_start\n'
        'data: {"type":"message_start","message":{"usage":{"input_tokens":5}}}\n\n'
        'event: content_block_delta\n'
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hi"}}\n\n'
        'event: content_block_delta\n'
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"!"}}\n\n'
        'event: message_delta\n'
        'data: {"type":"message_delta","usage":{"output_tokens":2}}\n\n'
        'event: message_stop\n'
        'data: {"type":"message_stop"}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert request.url.path == "/v1/messages"
        return _stream_response(stream, request)

    provider = AnthropicProvider(type("Runtime", (), {
        "get": lambda self, key, default=None: {
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_BASE_URL": "https://example.test",
        }.get(key, default),
    })())
    monkeypatch.setattr(provider, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    tokens: list[str] = []

    result = await provider.complete_stream("claude-test", "say hi", on_token=tokens.append)

    assert result.error is None
    assert result.text == "Hi!"
    assert tokens == ["Hi", "!"]
    assert result.tokens_in == 5
    assert result.tokens_out == 2


async def test_completion_stream_endpoint_emits_token_and_done_events(runtime, monkeypatch):
    import routers.completion as completion_router

    class FakeProvider:
        async def complete_stream(self, model, prompt, system=None, temperature=0.2,
                                  max_tokens=None, on_token=None):
            await on_token("one")
            await on_token(" two")
            return LLMResult(text="one two", model=model, provider="fake",
                             tokens_in=3, tokens_out=2)

    monkeypatch.setattr(completion_router, "build_provider", lambda name, rt: FakeProvider())
    client = TestClient(app)

    response = client.post("/completion/stream", json={
        "provider": "fake",
        "model": "test-model",
        "prompt": "say something",
    })

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    from routers.stream import parse_sse_chunk
    events, leftover = parse_sse_chunk(response.text)
    assert leftover == ""
    assert [event["type"] for event in events] == ["token", "token", "done"]
    assert "".join(event["text"] for event in events if event["type"] == "token") == "one two"
    assert events[-1]["text"] == "one two"
