"""Workspace + runner bridge + executor integration tests.

A "fake runner" consumes tool requests exactly like the real worker (or VS Code
extension) would: claim -> execute -> post results. This validates the full
loop: generated code -> applied to workspace -> checks run -> evidence merged
into verification -> escalation on failure.
"""

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
FAKE_FAST = ModelSpec("fake-fast", "fake", "Fake Fast", 2, 128_000, 0.0, 0.0, _CAPS, "fast")
FAKE_STRONG = ModelSpec("fake-strong", "fake", "Fake Strong", 4, 128_000, 0.0, 0.0, _CAPS, "slow")

PATHED_PYTHON = "```python:src/endpoint.py\ndef endpoint():\n    return {'ok': True}\n```"


def _patch(monkeypatch, provider_cls):
    import executor
    models = [FAKE_FAST, FAKE_STRONG]
    monkeypatch.setattr("domain.catalog.MODELS", models)
    monkeypatch.setattr("domain.routing.MODELS", models)
    monkeypatch.setattr("domain.escalation.MODELS", models)
    monkeypatch.setattr(executor, "build_provider", lambda name, rt: provider_cls(rt))
    monkeypatch.setattr(executor, "available_providers", lambda rt: {"fake"})
    monkeypatch.setattr(executor, "provider_order", lambda rt: ["fake"])


class ValidProvider:
    name = "fake"

    def __init__(self, runtime):
        self.runtime = runtime

    async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
        return LLMResult(text=PATHED_PYTHON, model=model, provider="fake", tokens_in=10, tokens_out=10)


async def _create_task_with_workspace(runtime, *, commands: dict, vtypes: list[str],
                                      constraints: dict | None = None) -> tuple[str, str]:
    db = runtime.db
    task_id = await store.create_task(db, prompt="implement an endpoint", repo=None,
                                      status=TaskStatus.PLANNED.value, risk_level="low",
                                      complexity="low", task_kind="other",
                                      constraints=constraints or {})
    plan_id = await store.create_plan(db, task_id, "ws plan")
    stage_id = uuid_str()
    await store.create_stage(db, plan_id, stage_id=stage_id, kind="implement",
                             title="implement", description="Implement it.",
                             dependencies=[], verification_types=vtypes,
                             risk_level="low", position=0)
    ws_id = uuid_str()
    await store.create_workspace(db, workspace_id=ws_id, task_id=task_id, repo_url=None,
                                 branch=None, provider="remote", commands=commands, env={},
                                 allowed_commands=[], auto_commit=False, timeout_seconds=60)
    return task_id, ws_id


class FakeRunner:
    """Consumes a workspace's tool requests like a real runner would."""

    def __init__(self, db, workspace_id: str, test_failures_before: int = 0):
        self.db = db
        self.workspace_id = workspace_id
        self.test_failures_before = test_failures_before
        self.test_calls = 0
        self.fs_applies = 0

    async def serve_until_idle(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            req = await store.next_queued_tool_request(self.db, self.workspace_id)
            if req is None:
                await asyncio.sleep(0.05)
                continue
            await self._handle(req)

    async def _handle(self, req: dict) -> None:
        if req["tool"] == "fs.write":
            self.fs_applies += 1
            params = req["params"]
            await tools_service.submit_tool_result(
                self.db, request_id=req["id"], status="succeeded",
                result={"files": [{"path": params["path"], "op": "create",
                                   "before": None, "after": params["content"]}]})
        elif req["tool"] == "command.run":
            self.test_calls += 1
            if self.test_calls <= self.test_failures_before:
                await tools_service.submit_tool_result(
                    self.db, request_id=req["id"], status="failed",
                    result={"exit_code": 1, "stdout": "", "stderr": "2 tests failed",
                            "duration_ms": 10})
            else:
                await tools_service.submit_tool_result(
                    self.db, request_id=req["id"], status="succeeded",
                    result={"exit_code": 0, "stdout": "6 passed", "stderr": "",
                            "duration_ms": 10})
        else:
            await tools_service.submit_tool_result(
                self.db, request_id=req["id"], status="failed",
                result={"error": f"unexpected tool {req['tool']}"})


async def _run_with_fake_runner(runtime, task_id, ws_id, *, fail_first_n_tests=0):
    from executor import execute_task

    done = asyncio.Event()
    runner = FakeRunner(runtime.db, ws_id, test_failures_before=fail_first_n_tests)

    runner_task = asyncio.create_task(runner.serve_until_idle(done))
    try:
        summary = await execute_task(runtime, task_id)
    finally:
        done.set()
        runner_task.cancel()
        try:
            await runner_task
        except asyncio.CancelledError:
            pass
    return summary, runner


async def test_workspace_flow_tests_pass(runtime, monkeypatch):
    _patch(monkeypatch, ValidProvider)
    task_id, ws_id = await _create_task_with_workspace(
        runtime, commands={"test": {"cmd": "pytest", "dangerous": False}},
        vtypes=["syntax", "tests"])
    summary, runner = await _run_with_fake_runner(runtime, task_id, ws_id)

    assert summary["task"]["status"] == "completed"
    assert runner.fs_applies == 1
    assert runner.test_calls >= 1
    stage = summary["stages"][0]
    assert stage["verification_reports"][0]["tool"] == "tests"
    assert stage["verification_reports"][0]["status"] == "passed"
    changes = await store.get_changes(runtime.db, summary["execution"]["id"])
    assert any(c["path"] == "src/endpoint.py" and c["op"] == "create" for c in changes)


async def test_workspace_flow_failing_tests_escalate(runtime, monkeypatch):
    _patch(monkeypatch, ValidProvider)
    task_id, ws_id = await _create_task_with_workspace(
        runtime, commands={"test": {"cmd": "pytest", "dangerous": False}},
        vtypes=["syntax", "tests"], constraints={"max_attempts_per_stage": 2})
    summary, runner = await _run_with_fake_runner(runtime, task_id, ws_id, fail_first_n_tests=1)

    assert summary["task"]["status"] == "completed"          # retry with corrected code passed
    assert runner.test_calls == 2
    assert summary["escalation"]["occurred"] is True
    assert summary["escalation"]["count"] >= 1


async def test_workspace_fs_failure_fails_stage(runtime, monkeypatch):
    class FailingApplyRunner(FakeRunner):
        async def _handle(self, req):
            if req["tool"] == "fs.write":
                await tools_service.submit_tool_result(
                    self.db, request_id=req["id"], status="failed",
                    result={"error": "path outside workspace"})
            else:
                await super()._handle(req)

    _patch(monkeypatch, ValidProvider)
    task_id, ws_id = await _create_task_with_workspace(
        runtime, commands={"test": {"cmd": "pytest", "dangerous": False}},
        vtypes=["syntax", "tests"])
    done = asyncio.Event()
    runner = FailingApplyRunner(runtime.db, ws_id)
    runner_task = asyncio.create_task(runner.serve_until_idle(done))
    from executor import execute_task
    try:
        summary = await execute_task(runtime, task_id)
    finally:
        done.set()
        runner_task.cancel()
        try:
            await runner_task
        except asyncio.CancelledError:
            pass

    # fs_apply failure -> verification failed -> attempts exhausted -> stage failed
    assert summary["task"]["status"] == "failed"
    flat_reasons = [str(x) for r in summary["escalation"]["reasons"]
                    for x in (r if isinstance(r, list) else [r])]
    assert any("fs_apply" in x for x in flat_reasons)


# ---- lifecycle + bridge API -------------------------------------------------

def test_workspace_lifecycle_and_bridge(runtime):
    client = TestClient(app)
    r = client.post("/workspaces", json={
        "repo_url": "https://github.com/example/repo.git", "branch": "main",
        "commands": {"test": {"cmd": "pytest"}}, "provider": "remote"})
    assert r.status_code == 200
    ws = r.json()
    assert ws["status"] == "provisioning"
    assert ws["commands"]["test"]["cmd"] == "pytest"

    ws_id = ws["id"]

    # Runner reports state.
    r = client.post(f"/workspaces/{ws_id}/state", json={"status": "ready", "base_commit": "abc123"})
    assert r.status_code == 200 and r.json()["status"] == "ready"

    # Dispatch a verification command and a file apply.
    exec_id = None
    stage_id = None
    import asyncio as aio

    async def _mk():
        nonlocal exec_id, stage_id
        task_id = await store.create_task(runtime.db, prompt="x", repo=None,
                                          status=TaskStatus.PLANNED.value, risk_level="low",
                                          complexity="low", task_kind="other", constraints={})
        plan_id = await store.create_plan(runtime.db, task_id, "p")
        stage_id = uuid_str()
        await store.create_stage(runtime.db, plan_id, stage_id=stage_id, kind="implement",
                                 title="s", description="d", dependencies=[],
                                 verification_types=["tests"], risk_level="low", position=0)
        exec_id = await store.create_execution(runtime.db, task_id, plan_id)

    aio.run(_mk())

    req_id = aio.run(
        tools_service.dispatch_verification_command(
            runtime.db, workspace_id=ws_id, execution_id=exec_id, stage_id=stage_id,
            attempt_id="attempt-1", command_key="test", command="pytest",
            verify_as="tests", dangerous=False))

    # Runner claims it.
    r = client.get(f"/workspaces/{ws_id}/tool-requests/next", headers={"x-runner-id": "w1"})
    assert r.status_code == 200 and r.json()["tool_request"]["status"] == "dispatched"

    # Runner posts a failing result -> becomes a verification report.
    r = client.post(f"/workspaces/{ws_id}/tool-requests/{req_id}/result",
                    json={"status": "failed", "result": {"exit_code": 1, "stdout": "", "stderr": "boom"}})
    assert r.status_code == 200

    reports = aio.run(store.get_verification_reports(runtime.db, stage_id))
    assert reports and reports[0]["status"] == "failed" and reports[0]["tool"] == "tests"

    # Stop/resume lifecycle.
    assert client.post(f"/workspaces/{ws_id}/stop").json()["status"] == "stopped"
    assert client.post(f"/workspaces/{ws_id}/resume").json()["status"] == "ready"


def test_dangerous_command_requires_approval(runtime):
    import asyncio as aio

    async def _mk_ws() -> str:
        ws_id = uuid_str()
        await store.create_workspace(runtime.db, workspace_id=ws_id, task_id=None, repo_url=None,
                                     branch=None, provider="remote", commands={}, env={},
                                     allowed_commands=[], auto_commit=False, timeout_seconds=60)
        return ws_id

    ws_id = aio.run(_mk_ws())

    req = aio.run(tools_service.dispatch_command(
        runtime.db, workspace_id=ws_id, command="git push origin main", allowed_commands=[]))
    assert req["status"] == "awaiting_approval"
    assert req["dangerous"] == 1

    # Approved -> queued -> runner can claim it.
    client = TestClient(app)
    r = client.post(f"/workspaces/{ws_id}/tool-requests/{req['id']}/approve",
                    json={"approved": True})
    assert r.status_code == 200 and r.json()["status"] == "queued"

    r = client.get(f"/workspaces/{ws_id}/tool-requests/next")
    assert r.json()["tool_request"]["id"] == req["id"]


def test_worker_registry(runtime):
    client = TestClient(app)
    r = client.post("/workers/register", json={"name": "test-worker", "capabilities": ["fs", "command"]})
    assert r.status_code == 200
    worker_id = r.json()["worker_id"]
    assert client.post(f"/workers/{worker_id}/heartbeat").status_code == 200
    workers = client.get("/workers").json()["workers"]
    assert any(w["id"] == worker_id for w in workers)