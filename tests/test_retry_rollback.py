"""Tests for stage retry (with prior-output reuse), rollback, repo rule packs,
and the CI webhook."""

import pytest
from fastapi.testclient import TestClient

import store
from app import app
from conftest import fake_create_and_plan
from domain.catalog import ModelSpec
from domain.enums import StageStatus, TaskStatus
from providers.base import LLMResult

_CAPS = frozenset({"code", "reason", "plan", "review", "security", "long_context"})
FAKE_MODEL = ModelSpec("fake-strong", "fake", "Fake Strong", 4, 128_000, 0.0, 0.0, _CAPS, "slow")
VALID_PYTHON = "```python\ndef example():\n    return 42\n```"


class RecordingProvider:
    name = "fake"

    def __init__(self, runtime):
        self.runtime = runtime
        self.prompts: list[str] = []

    async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
        self.prompts.append(prompt)
        return LLMResult(text=VALID_PYTHON, model=model, provider="fake", tokens_in=10, tokens_out=10)


def _patch_execution(monkeypatch, runtime, provider):
    import executor
    monkeypatch.setattr("domain.catalog.MODELS", [FAKE_MODEL])
    monkeypatch.setattr("domain.routing.MODELS", [FAKE_MODEL])
    monkeypatch.setattr("domain.escalation.MODELS", [FAKE_MODEL])
    monkeypatch.setattr(executor, "build_provider", lambda name, rt: provider)
    monkeypatch.setattr(executor, "available_providers", lambda rt: {"fake"})
    monkeypatch.setattr(executor, "provider_order", lambda rt: ["fake"])
    return runtime


async def _make_task(runtime):
    result = await fake_create_and_plan(runtime, prompt="Add a helper to the users service",
                                        repo=None, constraints=None,
                                        max_attempts_per_stage=2, budget_usd=None)
    return result


# ---- retry a single failed stage ---------------------------------------------

async def test_retry_stage_reuses_prior_outputs(runtime, monkeypatch):
    from executor import execute_task

    created = await _make_task(runtime)
    task_id = created["task"]["id"]
    stages = created["plan"]["stages"]
    by_kind = {s["kind"]: s for s in stages}

    provider = RecordingProvider(runtime)
    _patch_execution(monkeypatch, runtime, provider)
    await execute_task(runtime, task_id)

    # Simulate a flaky later stage: mark "test" failed and the task failed.
    test_stage = by_kind["test"]
    await store.update_stage(runtime.db, test_stage["id"], status=StageStatus.FAILED.value)
    await store.update_task(runtime.db, task_id, status=TaskStatus.FAILED.value)

    provider.prompts.clear()
    summary = await execute_task(runtime, task_id, retry_stage_ids=[test_stage["id"]])

    assert summary["task"]["status"] == "completed"
    # The retried test stage received its dependency's persisted output.
    test_prompts = [p for p in provider.prompts if "# Stage" in p and "resulting code" not in p]
    assert any("def example()" in p for p in provider.prompts), "prior outputs were not reused"
    # verify (downstream of test) re-ran too — the closure includes dependents.
    plan = await store.get_plan_for_task(runtime.db, task_id)
    statuses = await store.get_stage_statuses(runtime.db, plan["id"])
    assert statuses[by_kind["verify"]["id"]] == "succeeded"
    # retry_started event recorded.
    execution = await store.get_latest_execution(runtime.db, task_id)
    events = await store.get_events(runtime.db, execution["id"])
    assert any(e["type"] == "retry_started" for e in events)


async def test_retry_rejects_unknown_stage(runtime):
    created = await _make_task(runtime)
    task_id = created["task"]["id"]
    client = TestClient(app)
    resp = client.post(f"/tasks/{task_id}/retry", json={"stage_ids": ["nope"]})
    assert resp.status_code == 404


# ---- rollback ----------------------------------------------------------------

async def test_rollback_requires_workspace(runtime):
    created = await _make_task(runtime)
    client = TestClient(app)
    resp = client.post(f"/tasks/{created['task']['id']}/rollback")
    assert resp.status_code == 409
    assert "workspace" in resp.json()["detail"].lower()


async def test_rollback_queues_git_restore(runtime):
    created = await _make_task(runtime)
    task_id = created["task"]["id"]
    ws_id = "ws-rollback"
    await store.create_workspace(
        runtime.db, workspace_id=ws_id, task_id=task_id, repo_url=None,
        branch="main", provider="remote", commands={}, env={}, allowed_commands=[],
        auto_commit=False, timeout_seconds=600, runner_token=None)
    execution_id = await store.create_execution(runtime.db, task_id, None)
    await store.create_artifact(runtime.db, execution_id=execution_id, stage_id=None,
                                path="src/app.py", content="x = 1")

    client = TestClient(app)
    resp = client.post(f"/tasks/{task_id}/rollback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paths"] == ["src/app.py"]
    assert data["tool_request"]["tool"] == "git.restore"
    assert data["tool_request"]["status"] == "awaiting_approval"


# ---- repo rule packs ---------------------------------------------------------

async def test_repo_rules_roundtrip(runtime):
    created = await _make_task(runtime)
    ws_id = "ws-rules"
    await store.create_workspace(
        runtime.db, workspace_id=ws_id, task_id=created["task"]["id"],
        repo_url=None, branch="main", provider="remote", commands={}, env={},
        allowed_commands=[], auto_commit=False, timeout_seconds=600, runner_token=None)

    client = TestClient(app)
    rules = [
        {"name": "no-console", "kind": "regex", "spec": r"console\.log", "enabled": True},
        {"name": "no-api-keys", "kind": "constitution", "spec": "Never commit API keys.", "enabled": True},
        {"name": "typecheck", "kind": "command", "spec": "npm run typecheck", "enabled": True},
    ]
    put = client.put(f"/workspaces/{ws_id}/rules", json={"rules": rules})
    assert put.status_code == 200

    got = client.get(f"/workspaces/{ws_id}/rules")
    assert got.status_code == 200
    assert {r["name"] for r in got.json()["rules"]} == {"no-console", "no-api-keys", "typecheck"}


# ---- CI webhook --------------------------------------------------------------

async def test_ci_webhook_records_status(runtime):
    created = await _make_task(runtime)
    task_id = created["task"]["id"]
    ws_id = "ws-ci"
    await store.create_workspace(
        runtime.db, workspace_id=ws_id, task_id=task_id, repo_url=None,
        branch="main", provider="remote", commands={}, env={}, allowed_commands=[],
        auto_commit=False, timeout_seconds=600, runner_token=None)

    client = TestClient(app)
    resp = client.post("/webhooks/ci", json={
        "workspace_id": ws_id, "status": "success", "url": "https://ci.example/build/1"})
    assert resp.status_code == 200

    task = client.get(f"/tasks/{task_id}").json()
    assert task["ci"]["status"] == "success"

    # "failure" normalizes to "failed".
    client.post("/webhooks/ci", json={"workspace_id": ws_id, "status": "failure"})
    task = client.get(f"/tasks/{task_id}").json()
    assert task["ci"]["status"] == "failed"

    resp = client.post("/webhooks/ci", json={"workspace_id": "missing", "status": "success"})
    assert resp.status_code == 404