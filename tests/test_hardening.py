"""Hardening tests: streaming (SSE parse + endpoint), provider fallback,
agent loop, budget cap, workspace secrets/delivery/token auth, and D1-backed
rate limiting."""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

import store
import tools_service
from app import app
from domain.catalog import ModelSpec
from domain.enums import TaskStatus
from providers.base import LLMResult
from util import uuid_str

_CAPS = frozenset({"code", "reason", "plan", "review", "security", "long_context"})
PLAIN_PYTHON = "```python\ndef ok():\n    return 1\n```"


def _fake_model(cid: str = "fake-strong", provider: str = "fake", tier: int = 4,
                cost: float = 0.0) -> ModelSpec:
    return ModelSpec(cid, provider, f"Fake {tier}", tier, 128_000, cost, cost, _CAPS, "fast")


class ValidProvider:
    name = "fake"

    def __init__(self, runtime):
        self.runtime = runtime

    async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
        return LLMResult(text=PLAIN_PYTHON, model=model, provider="fake",
                         tokens_in=10, tokens_out=10)


def _patch_execution(monkeypatch, provider_factory, models, providers=frozenset({"fake"})):
    import executor
    models = list(models)
    monkeypatch.setattr("domain.catalog.MODELS", models)
    monkeypatch.setattr("domain.routing.MODELS", models)
    monkeypatch.setattr("domain.escalation.MODELS", models)
    monkeypatch.setattr(executor, "build_provider", provider_factory)
    monkeypatch.setattr(executor, "available_providers", lambda rt: providers)
    monkeypatch.setattr(executor, "provider_order", lambda rt: sorted(providers))


async def _make_task(runtime, prompt: str = "implement a thing",
                     kinds: tuple[str, ...] = ("implement",)) -> str:
    db = runtime.db
    task_id = await store.create_task(
        db, prompt=prompt, repo=None, status=TaskStatus.PLANNED.value, risk_level="low",
        complexity="low", task_kind="other", constraints={})
    plan_id = await store.create_plan(db, task_id, "test plan")
    ids = [uuid.uuid4().hex for _ in kinds]
    for i, kind in enumerate(kinds):
        await store.create_stage(
            db, plan_id, stage_id=ids[i], kind=kind, title=f"stage {i}",
            description="Complete the stage.", dependencies=[],
            verification_types=["syntax"], risk_level="low", position=i)
    return task_id


# ---- streaming (SSE) ---------------------------------------------------------

def test_sse_parse_chunks():
    from routers.stream import format_sse, parse_sse_chunk

    first = format_sse({"type": "stage_succeeded", "message": "ok"})
    second = format_sse({"type": "done", "summary": {"task": {"id": "t"}}})
    assert first.startswith("data: ")

    events, leftover = parse_sse_chunk(first + second)
    assert [e["type"] for e in events] == ["stage_succeeded", "done"]
    assert leftover == ""
    assert events[1]["summary"]["task"]["id"] == "t"

    # A partial frame is retained and completed by the next chunk.
    events, leftover = parse_sse_chunk('data: {"type": "part')
    assert events == [] and leftover.startswith("data: ")
    events, _ = parse_sse_chunk(leftover + 'ial"}\n\n')
    assert events[0]["type"] == "partial"


async def test_stream_endpoint_emits_valid_sse(runtime, monkeypatch):
    _patch_execution(monkeypatch, lambda name, rt: ValidProvider(rt), [_fake_model()])
    task_id = await _make_task(runtime)
    from routers.stream import parse_sse_chunk

    client = TestClient(app)
    events: list[dict] = []
    with client.stream("POST", f"/tasks/{task_id}/execute/stream") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        leftover = ""
        for chunk in resp.iter_text():
            parsed, leftover = parse_sse_chunk(leftover + chunk)
            events.extend(parsed)
            if any(e["type"] in ("done", "error") for e in parsed):
                break

    types = [e["type"] for e in events]
    assert "stage_succeeded" in types
    done = next(e for e in events if e["type"] == "done")
    assert done["summary"]["task"]["status"] == "completed"


# ---- provider fallback -------------------------------------------------------

async def test_provider_fallback_on_error(runtime, monkeypatch):
    """A provider error mid-attempt falls back to a same-tier other provider."""
    import executor

    class ErrorProvider(ValidProvider):
        name = "fake"

        async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
            return LLMResult(text="", model=model, provider="fake", tokens_in=1, tokens_out=1,
                             error="upstream outage")

    alt_calls: list[str] = []

    class AltProvider(ValidProvider):
        name = "fake2"

        async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
            alt_calls.append(model)
            return LLMResult(text=PLAIN_PYTHON, model=model, provider="fake2",
                             tokens_in=10, tokens_out=10)

    models = [_fake_model(cid="primary", provider="fake"),
              _fake_model(cid="alt", provider="fake2")]
    _patch_execution(monkeypatch,
                     lambda name, rt: ErrorProvider(rt) if name == "fake" else AltProvider(rt),
                     models, providers=frozenset({"fake", "fake2"}))

    task_id = await _make_task(runtime)
    from executor import execute_task
    summary = await execute_task(runtime, task_id)

    assert summary["task"]["status"] == "completed"
    assert alt_calls, "fallback provider was never tried"
    assert all(stage["assigned_model"] == "primary" for stage in summary["stages"])


# ---- agent loop --------------------------------------------------------------

def test_parse_agent_reply_variants():
    from agent import parse_agent_reply

    assert parse_agent_reply('{"tool": "fs.read", "params": {"path": "a.py"}}') == {
        "tool": "fs.read", "params": {"path": "a.py"}}
    assert parse_agent_reply('{"final": "done"}') == {"final": "done"}
    assert parse_agent_reply("not json at all") is None
    assert parse_agent_reply('{"tool": "unknown.tool", "params": {}}')["tool"] == "unknown.tool"


async def test_agent_loop_inspects_then_finalizes(runtime):
    from agent import run_agent_loop

    replies = iter([
        LLMResult(text='{"tool": "fs.read", "params": {"path": "README.md"}}',
                  model="m", provider="fake", tokens_in=5, tokens_out=5),
        LLMResult(text='{"final": "the file says hello"}',
                  model="m", provider="fake", tokens_in=5, tokens_out=5),
    ])

    class ScriptedProvider:
        name = "fake"

        def __init__(self, runtime):
            self.runtime = runtime

        async def complete(self, model, prompt, system=None, temperature=0.1, max_tokens=None):
            return next(replies)

    db = runtime.db
    task_id = await store.create_task(
        db, prompt="inspect the repo", repo=None, status=TaskStatus.PLANNED.value,
        risk_level="low", complexity="low", task_kind="other", constraints={})
    await store.create_workspace(db, workspace_id="ws-agent", task_id=task_id,
                                 repo_url=None, branch=None, provider="remote",
                                 commands={}, env={}, allowed_commands=[],
                                 auto_commit=False, timeout_seconds=60)
    workspace = store.workspace_dict(await store.get_workspace_for_task(db, task_id))
    plan_id = await store.create_plan(db, task_id, "p")
    execution_id = await store.create_execution(db, task_id, plan_id)

    done = asyncio.Event()

    async def completer():
        while not done.is_set():
            req = await store.next_queued_tool_request(db, "ws-agent")
            if req is None:
                await asyncio.sleep(0.01)
                continue
            if req["tool"] == "fs.read":
                await tools_service.submit_tool_result(
                    db, request_id=req["id"], status="succeeded",
                    result={"path": "README.md", "content": "hello"})
            else:
                await tools_service.submit_tool_result(
                    db, request_id=req["id"], status="failed",
                    result={"error": f"unsupported tool {req['tool']}"})

    ct = asyncio.create_task(completer())
    try:
        final, usage, error = await run_agent_loop(
            db, workspace, emit=None, execution_id=execution_id,
            stage={"id": uuid_str()}, attempt_id="attempt-1",
            runtime=runtime,
            provider=ScriptedProvider(runtime), model=_fake_model(cid="agent-model"),
            prompt="look at README.md", max_rounds=4, per_round_timeout=10.0)
    finally:
        done.set()
        ct.cancel()
        try:
            await ct
        except asyncio.CancelledError:
            pass

    assert final == "the file says hello"
    assert error is None
    assert len(usage) == 1
    assert usage[0]["tool"] == "fs.read"
    assert usage[0]["status"] == "succeeded"


# ---- budget cap --------------------------------------------------------------

def test_budget_caps_output_tokens():
    from executor import _budget_max_tokens

    class Ctx:
        budget = 0.001
        spend = 0.0

    ctx = Ctx()
    expensive = _fake_model(cost=1.0)     # $1 per M input/output tokens
    assert _budget_max_tokens(ctx, expensive) == 1000

    ctx.spend = 0.001                     # nothing left in budget
    assert _budget_max_tokens(ctx, expensive) == 64

    ctx.budget = None                     # no budget -> no cap
    assert _budget_max_tokens(ctx, expensive) is None

    ctx.budget = 100.0
    ctx.spend = 0.0
    free = _fake_model(cost=0.0)          # free model -> no cap
    assert _budget_max_tokens(ctx, free) is None


# ---- secrets / delivery / token auth -----------------------------------------

def test_secrets_stored_but_values_never_returned(runtime):
    client = TestClient(app)
    ws = client.post("/workspaces", json={"provider": "remote"}).json()
    ws_id = ws["id"]

    r = client.post(f"/workspaces/{ws_id}/secrets",
                    json={"key": "GITHUB_TOKEN", "value": "ghp_supersecret"})
    assert r.status_code == 200 and r.json()["stored"] is True

    listing = client.get(f"/workspaces/{ws_id}/secrets")
    assert listing.status_code == 200
    assert listing.json()["keys"] == ["GITHUB_TOKEN"]
    assert "ghp_supersecret" not in listing.text


def test_deliver_attaches_secrets_only_to_tool_requests(runtime):
    client = TestClient(app)
    ws = client.post("/workspaces",
                     json={"provider": "remote", "repo_url": "https://github.com/o/r.git"}).json()
    ws_id = ws["id"]
    client.post(f"/workspaces/{ws_id}/secrets", json={"key": "GITHUB_TOKEN", "value": "ghp_secret"})
    client.post(f"/workspaces/{ws_id}/secrets", json={"key": "GIT_PUSH_TOKEN", "value": "push_secret"})

    r = client.post(f"/workspaces/{ws_id}/deliver", json={"title": "feat: x", "body": "y"})
    assert r.status_code == 200
    assert len(r.json()["tool_requests"]) == 3

    rows = client.get(f"/workspaces/{ws_id}/tool-requests").json()["tool_requests"]
    by_tool = {t["tool"]: t for t in rows}
    assert by_tool["git.commit"]["status"] == "queued"
    assert by_tool["git.push"]["status"] == "awaiting_approval"
    assert by_tool["github.pr"]["status"] == "awaiting_approval"
    # Secrets are attached ONLY to the tool request that needs them.
    assert by_tool["git.commit"]["params"].get("token") is None
    assert by_tool["git.push"]["params"]["token"] == "push_secret"
    assert by_tool["github.pr"]["params"]["token"] == "ghp_secret"


def test_local_workspace_requires_runner_token(runtime):
    client = TestClient(app)
    ws = client.post("/workspaces",
                     json={"provider": "local", "repo_url": "https://github.com/o/r.git"}).json()
    ws_id, token = ws["id"], ws["runner_token"]
    assert token

    async def _queue():
        await store.create_tool_request(runtime.db, workspace_id=ws_id, tool="fs.write",
                                        params={"path": "x.txt"}, status="queued")

    asyncio.run(_queue())

    # Claiming requires the per-workspace token.
    denied = client.get(f"/workspaces/{ws_id}/tool-requests/next")
    assert denied.status_code == 403
    claimed = client.get(f"/workspaces/{ws_id}/tool-requests/next",
                         headers={"x-workspace-token": token})
    assert claimed.status_code == 200
    req_id = claimed.json()["tool_request"]["id"]

    # Posting results also requires it.
    denied = client.post(f"/workspaces/{ws_id}/tool-requests/{req_id}/result",
                         json={"status": "succeeded", "result": {}})
    assert denied.status_code == 403
    posted = client.post(f"/workspaces/{ws_id}/tool-requests/{req_id}/result",
                         headers={"x-workspace-token": token},
                         json={"status": "succeeded", "result": {"files": []}})
    assert posted.status_code == 200


# ---- rate limiting (D1-backed counter via the middleware) --------------------

def test_rate_limit_enforced_via_store(runtime, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    client = TestClient(app)
    for _ in range(2):
        assert client.post("/workspaces", json={"provider": "remote"}).status_code == 200
    r = client.post("/workspaces", json={"provider": "remote"})
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"