"""Tests for the gap-closure features: parallel execution, budget, cycles,
auth, ingestion, verification reports, artifacts, learning stats, LLM planning,
streaming, and metrics."""

import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient

import store
from app import app
from domain.catalog import ModelSpec
from domain.enums import TaskStatus
from domain.verification import merge_reports
from providers.base import LLMResult
from planner import parse_plan_json

PLAIN_PYTHON = "```python\ndef ok():\n    return 1\n```"
PATHED_PYTHON = "```python:src/app.py\ndef ok():\n    return 1\n```"

_CAPS = frozenset({"code", "reason", "plan", "review", "security", "long_context"})


def _fake_model(cid: str = "fake-strong", provider: str = "fake", tier: int = 4,
                cost: float = 0.0) -> ModelSpec:
    return ModelSpec(cid, provider, f"Fake {tier}", tier, 128_000, cost, cost, _CAPS, "fast")


class ValidProvider:
    name = "fake"

    def __init__(self, runtime, text: str = PLAIN_PYTHON):
        self.runtime = runtime
        self.text = text

    async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
        return LLMResult(text=self.text, model=model, provider="fake", tokens_in=10, tokens_out=10)


class ConcurrencyProvider(ValidProvider):
    def __init__(self, runtime):
        super().__init__(runtime)
        self.active = 0
        self.max_active = 0

    async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.15)
            return LLMResult(text=PLAIN_PYTHON, model=model, provider="fake",
                             tokens_in=10, tokens_out=10)
        finally:
            self.active -= 1


def _patch_execution(monkeypatch, provider_factory, models):
    import executor
    models = list(models)
    monkeypatch.setattr("domain.catalog.MODELS", models)
    monkeypatch.setattr("domain.routing.MODELS", models)
    monkeypatch.setattr("domain.escalation.MODELS", models)
    monkeypatch.setattr(executor, "build_provider", provider_factory)
    monkeypatch.setattr(executor, "available_providers", lambda rt: {"fake"})
    monkeypatch.setattr(executor, "provider_order", lambda rt: ["fake"])


def _patch_tasks_planner(monkeypatch):
    """Point the POST /tasks router at the deterministic fake planner so
    TestClient tests don't need a configured LLM provider."""
    from conftest import fake_create_and_plan
    from routers import tasks as tasks_mod
    monkeypatch.setattr(tasks_mod, "create_and_plan", fake_create_and_plan)


async def _make_task(runtime, prompt: str, specs: list[dict], risk: str = "low",
                     constraints: dict | None = None) -> str:
    db = runtime.db
    task_id = await store.create_task(
        db, prompt=prompt, repo=None, status=TaskStatus.PLANNED.value, risk_level=risk,
        complexity="low", task_kind="other", constraints=constraints or {})
    plan_id = await store.create_plan(db, task_id, "test plan")
    ids = [uuid.uuid4().hex for _ in specs]
    for i, spec in enumerate(specs):
        deps = [ids[d] for d in spec.get("deps", [])]
        await store.create_stage(
            db, plan_id, stage_id=ids[i], kind=spec["kind"], title=spec.get("title", f"stage {i}"),
            description=spec.get("description", "Complete the stage."), dependencies=deps,
            verification_types=spec.get("vtypes", ["syntax"]), risk_level=risk, position=i)
    return task_id


# ---- parallel execution ------------------------------------------------------

async def test_independent_stages_run_concurrently(runtime, monkeypatch):
    provider = ConcurrencyProvider(runtime)
    _patch_execution(monkeypatch, lambda name, rt: provider, [_fake_model()])
    task_id = await _make_task(runtime, "do two independent things", [
        {"kind": "implement"}, {"kind": "implement"},
    ])
    from executor import execute_task
    summary = await execute_task(runtime, task_id)
    assert summary["task"]["status"] == "completed"
    assert provider.max_active >= 2


async def test_dependent_stages_still_respected(runtime, monkeypatch):
    provider = ConcurrencyProvider(runtime)
    _patch_execution(monkeypatch, lambda name, rt: provider, [_fake_model()])
    # chain of 3: 0 -> 1 -> 2. Max concurrency must be 1.
    task_id = await _make_task(runtime, "sequential chain", [
        {"kind": "implement"}, {"kind": "implement", "deps": [0]},
        {"kind": "implement", "deps": [1]},
    ])
    from executor import execute_task
    summary = await execute_task(runtime, task_id)
    assert summary["task"]["status"] == "completed"
    assert provider.max_active == 1


# ---- budget enforcement -----------------------------------------------------

async def test_budget_enforced(runtime, monkeypatch):
    _patch_execution(monkeypatch, lambda name, rt: ValidProvider(rt), [_fake_model(cost=1.0)])
    task_id = await _make_task(runtime, "add an endpoint", [{"kind": "implement", "vtypes": []}],
                               constraints={"budget_usd": 1e-9})
    from executor import execute_task
    summary = await execute_task(runtime, task_id)
    assert summary["budget"]["exceeded"] is True
    assert summary["execution"]["status"] == "failed"
    assert summary["task"]["status"] == "failed"


async def test_budget_allows_within_limit(runtime, monkeypatch):
    _patch_execution(monkeypatch, lambda name, rt: ValidProvider(rt), [_fake_model(cost=1.0)])
    task_id = await _make_task(runtime, "add an endpoint", [{"kind": "implement", "vtypes": []}],
                               constraints={"budget_usd": 100.0})
    from executor import execute_task
    summary = await execute_task(runtime, task_id)
    assert summary["budget"]["exceeded"] is False
    assert summary["execution"]["status"] == "completed"


# ---- cycle handling ---------------------------------------------------------

async def test_cyclic_plan_does_not_hang(runtime, monkeypatch):
    _patch_execution(monkeypatch, lambda name, rt: ValidProvider(rt), [_fake_model()])
    db = runtime.db
    task_id = await store.create_task(db, prompt="cycle", repo=None, status=TaskStatus.PLANNED.value,
                                      risk_level="low", complexity="low", task_kind="other", constraints={})
    plan_id = await store.create_plan(db, task_id, "cycle")
    a, b = uuid.uuid4().hex, uuid.uuid4().hex
    for sid, dep in ((a, b), (b, a)):
        await store.create_stage(db, plan_id, stage_id=sid, kind="implement",
                                 title=sid, description="x", dependencies=[dep],
                                 verification_types=["syntax"], risk_level="low", position=0)
    from executor import execute_task
    summary = await asyncio.wait_for(execute_task(runtime, task_id), timeout=30)
    assert summary["execution"]["status"] == "completed"


# ---- auth / rate limiting ---------------------------------------------------

def test_auth_middleware(runtime, monkeypatch):
    _patch_tasks_planner(monkeypatch)
    monkeypatch.setenv("API_TOKEN", "sekret")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.post("/tasks", json={"prompt": "do a thing"}).status_code == 401
    r = client.post("/tasks", json={"prompt": "do a thing"},
                    headers={"Authorization": "Bearer sekret"})
    assert r.status_code == 200
    r = client.post("/tasks", json={"prompt": "do a thing"},
                    headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_no_token_required_when_unset(runtime, monkeypatch):
    _patch_tasks_planner(monkeypatch)
    monkeypatch.delenv("API_TOKEN", raising=False)
    client = TestClient(app)
    r = client.post("/tasks", json={"prompt": "do a thing"})
    assert r.status_code == 200


# ---- repo ingestion ---------------------------------------------------------

def test_repo_ingest_and_read(runtime, monkeypatch):
    _patch_tasks_planner(monkeypatch)
    client = TestClient(app)
    tid = client.post("/tasks", json={"prompt": "add an endpoint"}).json()["task"]["id"]
    r = client.post(f"/tasks/{tid}/repo", json={"files": [
        {"path": "src/app.py", "language": "python", "size": 42, "content": "print('hi')"},
    ]})
    assert r.status_code == 200 and r.json()["files_ingested"] == 1
    files = client.get(f"/tasks/{tid}/repo").json()["files"]
    assert files[0]["path"] == "src/app.py"
    assert files[0]["content"] == "print('hi')"


async def test_repo_context_reaches_prompt(runtime, monkeypatch):
    captured = {}

    class CaptureProvider(ValidProvider):
        async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
            captured["prompt"] = prompt
            return LLMResult(text=PLAIN_PYTHON, model=model, provider="fake",
                             tokens_in=10, tokens_out=10)

    _patch_execution(monkeypatch, lambda name, rt: CaptureProvider(rt), [_fake_model()])
    task_id = await _make_task(runtime, "understand the app", [{"kind": "understand", "vtypes": []}])
    await store.replace_repo_files(runtime.db, task_id, [
        {"path": "src/main.py", "language": "python", "size": 10, "content": "def main(): pass"},
    ])
    from executor import execute_task
    await execute_task(runtime, task_id)
    assert "src/main.py" in captured["prompt"]
    assert "def main" in captured["prompt"]


# ---- verification reports ---------------------------------------------------

def test_merge_reports_failed_triggers_failure():
    from domain.verification import verify_stage
    outcome = verify_stage("implement", ["syntax", "tests"], PLAIN_PYTHON)
    merged = merge_reports(outcome, [{"tool": "tests", "status": "failed", "output": "2 failed"}])
    assert merged.status == "failed"
    assert any("tests" in f for f in merged.failures)


def test_merge_reports_passed_clears_limitations():
    from domain.verification import verify_stage
    outcome = verify_stage("implement", ["syntax", "tests"], PLAIN_PYTHON)
    merged = merge_reports(outcome, [{"tool": "tests", "status": "passed", "output": "14 passed"}])
    assert merged.status == "passed"
    assert not merged.limitations


def test_merge_reports_partial_keeps_limitations():
    from domain.verification import verify_stage
    outcome = verify_stage("implement", ["syntax", "tests", "lint"], PLAIN_PYTHON)
    merged = merge_reports(outcome, [{"tool": "tests", "status": "passed", "output": "14 passed"}])
    assert merged.status == "limited"
    assert any("lint" in l for l in merged.limitations)


def test_verification_report_endpoint(runtime, monkeypatch):
    _patch_tasks_planner(monkeypatch)
    client = TestClient(app)
    tid = client.post("/tasks", json={"prompt": "add an endpoint"}).json()["task"]["id"]
    plan_id = client.get(f"/tasks/{tid}").json()["plan"]["id"]
    stage = client.get(f"/tasks/{tid}").json()["plan"]["stages"][0]
    exec_id = None
    import asyncio
    async def _mk():
        nonlocal exec_id
        exec_id = await store.create_execution(runtime.db, tid, plan_id)
    asyncio.run(_mk())
    r = client.post(f"/executions/{exec_id}/stages/{stage['id']}/verification",
                    json={"tool": "tests", "status": "passed", "output": "14 passed", "duration_ms": 120})
    assert r.status_code == 200
    reports = client.get(f"/executions/{exec_id}/stages/{stage['id']}/verification").json()["reports"]
    assert reports and reports[0]["status"] == "passed"


# ---- artifacts --------------------------------------------------------------

async def test_artifacts_auto_detected(runtime, monkeypatch):
    _patch_execution(monkeypatch, lambda name, rt: ValidProvider(rt, PATHED_PYTHON), [_fake_model()])
    task_id = await _make_task(runtime, "write the app", [{"kind": "implement"}])
    from executor import execute_task
    summary = await execute_task(runtime, task_id)
    assert summary["files_changed"] == 1
    assert summary["artifacts"][0]["path"] == "src/app.py"
    assert summary["artifacts"][0]["source"] == "auto"


def test_artifact_endpoint(runtime, monkeypatch):
    _patch_tasks_planner(monkeypatch)
    client = TestClient(app)
    tid = client.post("/tasks", json={"prompt": "add an endpoint"}).json()["task"]["id"]
    plan_id = client.get(f"/tasks/{tid}").json()["plan"]["id"]
    stage = client.get(f"/tasks/{tid}").json()["plan"]["stages"][0]
    import asyncio
    exec_id = None
    async def _mk():
        nonlocal exec_id
        exec_id = await store.create_execution(runtime.db, tid, plan_id)
    asyncio.run(_mk())
    r = client.post(f"/executions/{exec_id}/stages/{stage['id']}/artifacts",
                    json={"path": "src/app.py", "kind": "patch", "language": "python",
                          "content": "- old\n+ new"})
    assert r.status_code == 200
    arts = client.get(f"/executions/{exec_id}/artifacts").json()["artifacts"]
    assert arts and arts[0]["path"] == "src/app.py" and arts[0]["source"] == "extension"


# ---- learning stats ---------------------------------------------------------

async def test_routing_stats_recorded(runtime, monkeypatch):
    _patch_execution(monkeypatch, lambda name, rt: ValidProvider(rt), [_fake_model()])
    task_id = await _make_task(runtime, "implement thing", [{"kind": "implement"}])
    from executor import execute_task
    await execute_task(runtime, task_id)
    stats = await store.get_routing_stats(runtime.db, "implement", "low")
    assert "fake-strong" in stats
    assert stats["fake-strong"]["attempts"] >= 1
    assert stats["fake-strong"]["successes"] >= 1


# ---- LLM planning -----------------------------------------------------------

def test_parse_plan_json_valid():
    text = ('{"summary": "s", "stages": ['
            '{"kind": "implement", "title": "t", "dependencies": [], "verification": ["syntax"]},'
            '{"kind": "test", "title": "t2", "dependencies": [0], "verification": ["tests"]}]}')
    parsed = parse_plan_json(text)
    assert parsed["summary"] == "s"
    assert [s["kind"] for s in parsed["stages"]] == ["implement", "test"]
    assert parsed["stages"][1]["dependencies"] == [0]


def test_parse_plan_json_rejects_invalid():
    assert parse_plan_json("not json at all") is None
    assert parse_plan_json('{"stages": [{"kind": "bogus_kind"}]}') is None
    assert parse_plan_json('{"stages": [{"kind": "implement", "dependencies": [7]}]}') is None
    assert parse_plan_json('{"stages": []}') is None


async def test_llm_plan_used_when_available(runtime, monkeypatch):
    import planner as planner_mod
    import providers

    plan_json = json.dumps({
        "summary": "llm-authored plan",
        "stages": [
            {"kind": "understand", "title": "u", "dependencies": [], "verification": []},
            {"kind": "implement", "title": "i", "dependencies": [0], "verification": ["syntax"]},
        ],
    })
    monkeypatch.setattr("domain.routing.MODELS", [_fake_model(cid="plan-model")])
    monkeypatch.setattr(providers, "available_providers", lambda rt: {"fake"})
    monkeypatch.setattr(providers, "provider_order", lambda rt: ["fake"])
    monkeypatch.setattr(providers, "build_provider", lambda name, rt: ValidProvider(rt, plan_json))
    result = await planner_mod.create_and_plan(runtime, prompt="add endpoint", repo=None,
                                               constraints=None, max_attempts_per_stage=None,
                                               budget_usd=None)
    assert result["plan"]["source"] == "llm"
    assert len(result["plan"]["stages"]) == 2


async def test_llm_plan_fails_loudly_without_providers(runtime, monkeypatch):
    """No providers configured -> RuntimeError, never a silent template plan."""
    import planner as planner_mod
    import providers
    monkeypatch.setattr(providers, "available_providers", lambda rt: set())
    with pytest.raises(RuntimeError, match="provider"):
        await planner_mod.create_and_plan(runtime, prompt="add endpoint", repo=None,
                                          constraints=None, max_attempts_per_stage=None,
                                          budget_usd=None)


async def test_llm_plan_fails_loudly_on_invalid_json(runtime, monkeypatch):
    """Model never produces valid JSON -> RuntimeError after refinement."""
    import planner as planner_mod
    import providers
    monkeypatch.setattr(providers, "available_providers", lambda rt: {"fake"})
    monkeypatch.setattr(providers, "provider_order", lambda rt: ["fake"])
    monkeypatch.setattr(providers, "build_provider", lambda name, rt: ValidProvider(rt, "garbage {{{"))
    monkeypatch.setattr("domain.routing.MODELS", [_fake_model(cid="plan-model")])
    with pytest.raises(RuntimeError, match="schema"):
        await planner_mod.create_and_plan(runtime, prompt="add endpoint", repo=None,
                                          constraints=None, max_attempts_per_stage=None,
                                          budget_usd=None)


async def test_llm_plan_refines_invalid_json(runtime, monkeypatch):
    import planner as planner_mod
    import providers

    valid = json.dumps({
        "summary": "refined plan",
        "stages": [
            {"kind": "understand", "title": "u", "dependencies": [], "verification": []},
            {"kind": "implement", "title": "i", "dependencies": [0], "verification": ["syntax"]},
        ],
    })

    class RefiningProvider:
        name = "fake"

        def __init__(self, runtime):
            self.runtime = runtime
            self.calls = 0

        async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
            self.calls += 1
            if self.calls == 1:
                return LLMResult(text="this is not json at all", model=model, provider="fake")
            return LLMResult(text=valid, model=model, provider="fake")

    inst = RefiningProvider(runtime)
    monkeypatch.setattr("domain.routing.MODELS", [_fake_model(cid="plan-model")])
    monkeypatch.setattr(providers, "available_providers", lambda rt: {"fake"})
    monkeypatch.setattr(providers, "provider_order", lambda rt: ["fake"])
    monkeypatch.setattr(providers, "build_provider", lambda name, rt: inst)
    result = await planner_mod.create_and_plan(runtime, prompt="add endpoint", repo=None,
                                               constraints=None, max_attempts_per_stage=None,
                                               budget_usd=None)
    assert result["plan"]["source"] == "llm"          # refined instead of failing
    assert inst.calls == 2                            # exactly one refinement
    assert result["plan"]["summary"] == "refined plan"


# ---- streaming + metrics ----------------------------------------------------

async def test_stream_endpoint(runtime, monkeypatch):
    _patch_execution(monkeypatch, lambda name, rt: ValidProvider(rt), [_fake_model()])
    task_id = await _make_task(runtime, "stream me", [{"kind": "implement"}])
    client = TestClient(app)
    r = client.post(f"/tasks/{task_id}/execute/stream")
    assert r.status_code == 200
    assert "stage_succeeded" in r.text
    assert '"done"' in r.text


def test_metrics_endpoint(runtime):
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "counters" in data and "histograms" in data