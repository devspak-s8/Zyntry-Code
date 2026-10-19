"""Tests for semantic repo search: chunking, embedding, ranking, API, agent tool."""

import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient

import semantic
import store
from app import app
from domain.catalog import ModelSpec
from domain.enums import TaskStatus
from providers.base import LLMResult
from util import uuid_str

_CAPS = frozenset({"code", "reason", "plan", "review", "security", "long_context"})
FAKE_MODEL = ModelSpec("fake-strong", "fake", "Fake", 4, 128_000, 0.0, 0.0, _CAPS, "fast")

_VOCAB = ["login", "auth", "session", "payment", "retry", "user", "database", "cache", "api", "test"]


async def _fake_embed(runtime, texts):
    return [[float(text.lower().count(w)) for w in _VOCAB] for text in texts]


def _repo_files():
    return [
        {"path": "src/auth.py", "language": "python",
         "content": "def login(user):\n    check credentials\n    create session token\n    return token\n"},
        {"path": "src/payments.py", "language": "python",
         "content": "def charge():\n    retry logic for payment gateway\n    handle failures\n"},
    ]


async def _mk_workspace_with_repo(runtime) -> str:
    db = runtime.db
    task_id = await store.create_task(db, prompt="x", repo=None,
                                      status=TaskStatus.PLANNED.value, risk_level="low",
                                      complexity="low", task_kind="other", constraints={})
    await store.replace_repo_files(db, task_id, _repo_files())
    ws_id = uuid_str()
    await store.create_workspace(db, workspace_id=ws_id, task_id=task_id, repo_url=None,
                                 branch=None, provider="remote", commands={}, env={},
                                 allowed_commands=[], auto_commit=False, timeout_seconds=60)
    return ws_id


# ---- chunking + ranking -----------------------------------------------------

def test_chunk_file_overlap_and_bounds():
    content = "\n".join(f"line {i}" for i in range(1000)) + "\n"
    chunks = semantic.chunk_file("f.py", "python", content)
    assert chunks
    # chunks overlap and cover the file
    assert chunks[0]["start_line"] == 1
    assert chunks[-1]["end_line"] == 1000
    assert chunks[1]["start_line"] <= chunks[0]["end_line"]  # overlap


def test_chunk_files_skips_empty():
    chunks = semantic.chunk_files([{"path": "a.py", "content": ""},
                                   {"path": "b.py", "content": "x = 1\n"}])
    assert len(chunks) == 1 and chunks[0]["path"] == "b.py"


async def test_cosine_ranking_prefers_related_chunk():
    q = (await _fake_embed(None, ["authentication login"]))[0]
    auth = (await _fake_embed(None, ["def login: create session"]))[0]
    pay = (await _fake_embed(None, ["payment retry logic"]))[0]
    assert semantic.cosine(q, auth) > semantic.cosine(q, pay)


# ---- index + search flow ----------------------------------------------------

async def test_index_and_search_roundtrip(runtime, monkeypatch):
    monkeypatch.setattr(semantic, "embed", _fake_embed)
    ws_id = await _mk_workspace_with_repo(runtime)

    info = await semantic.index_workspace(runtime, ws_id)
    assert info["files"] == 2 and info["chunks"] >= 2

    results = await semantic.search_query(runtime, ws_id, "authentication", top_k=2)
    assert results and results[0]["path"] == "src/auth.py"
    assert "score" in results[0] and "content" in results[0]


async def test_search_before_index_errors(runtime, monkeypatch):
    monkeypatch.setattr(semantic, "embed", _fake_embed)
    ws_id = await _mk_workspace_with_repo(runtime)
    with pytest.raises(ValueError):
        await semantic.search_query(runtime, ws_id, "anything")


# ---- API endpoints ----------------------------------------------------------

def test_semantic_api_endpoints(runtime, monkeypatch):
    monkeypatch.setattr(semantic, "embed", _fake_embed)
    client = TestClient(app)
    import asyncio as aio

    ws_id = aio.run(_mk_workspace_with_repo(runtime))

    r = client.post(f"/workspaces/{ws_id}/semantic/index")
    assert r.status_code == 200 and r.json()["chunks"] >= 2

    r = client.post(f"/workspaces/{ws_id}/semantic/search",
                    json={"query": "payment retries", "top_k": 3})
    assert r.status_code == 200
    assert r.json()["results"][0]["path"] == "src/payments.py"

    r = client.get(f"/workspaces/{ws_id}/semantic/status")
    assert r.status_code == 200 and r.json()["indexed"] is True


# ---- agent calls fs.search_semantic inline ----------------------------------

async def test_agent_semantic_tool_inline(runtime, monkeypatch):
    import executor as executor_mod
    from executor import execute_task
    monkeypatch.setattr(semantic, "embed", _fake_embed)

    class SemanticAgentProvider:
        name = "fake"

        def __init__(self, runtime):
            self.runtime = runtime
            self.calls = 0

        async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
            self.calls += 1
            if self.calls == 1:
                return LLMResult(
                    text='{"tool": "fs.search_semantic", "params": {"query": "authentication", "top_k": 3}}',
                    model=model, provider="fake", tokens_in=5, tokens_out=5)
            return LLMResult(
                text='{"final": "```python:src/ok.py\\ndef ok():\\n    return 1\\n```"}',
                model=model, provider="fake", tokens_in=5, tokens_out=5)

    monkeypatch.setattr("domain.catalog.MODELS", [FAKE_MODEL])
    monkeypatch.setattr("domain.routing.MODELS", [FAKE_MODEL])
    monkeypatch.setattr("domain.escalation.MODELS", [FAKE_MODEL])
    monkeypatch.setattr(executor_mod, "available_providers", lambda rt: {"fake"})
    monkeypatch.setattr(executor_mod, "provider_order", lambda rt: ["fake"])
    monkeypatch.setattr(executor_mod, "build_provider", lambda name, rt: SemanticAgentProvider(rt))

    db = runtime.db
    ws_id = await _mk_workspace_with_repo(runtime)
    await semantic.index_workspace(runtime, ws_id)

    task_id = await store.create_task(db, prompt="find auth", repo=None,
                                      status=TaskStatus.PLANNED.value, risk_level="low",
                                      complexity="low", task_kind="other",
                                      constraints={"agentic_rounds": 2})
    plan_id = await store.create_plan(db, task_id, "semantic test")
    stage_id = uuid_str()
    await store.create_stage(db, plan_id, stage_id=stage_id, kind="implement",
                             title="s", description="d", dependencies=[],
                             verification_types=["syntax"], risk_level="low", position=0)
    await store.update_workspace(db, ws_id, task_id=task_id)

    summary = await execute_task(runtime, task_id)

    assert summary["task"]["status"] == "completed"
    semantic_events = [e for e in summary["events"]
                       if e["type"] == "agent_tool_call" and e["data"].get("tool") == "fs.search_semantic"]
    assert semantic_events, "agent never called fs.search_semantic"