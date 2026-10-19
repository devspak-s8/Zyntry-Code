"""End-to-end execution tests using a fake provider (tests only — never shipped)."""

import pytest

from conftest import fake_create_and_plan
from domain.catalog import ModelSpec
from providers.base import LLMResult

_CAPS = frozenset({"code", "reason", "plan", "review", "security", "long_context"})

# Two models under the "fake" provider: a fast/cheap one and a stronger one.
FAKE_FAST = ModelSpec("fake-fast", "fake", "Fake Fast", 2, 128_000, 0.0, 0.0, _CAPS, "fast")
FAKE_STRONG = ModelSpec("fake-strong", "fake", "Fake Strong", 4, 128_000, 0.0, 0.0, _CAPS, "slow")

VALID_PYTHON = "```python\ndef example():\n    return 42\n```"


class AlwaysValidProvider:
    name = "fake"

    def __init__(self, runtime):
        self.runtime = runtime

    async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
        return LLMResult(text=VALID_PYTHON, model=model, provider="fake", tokens_in=10, tokens_out=10)


class EscalatingProvider:
    """Fails its first code-producing call, then succeeds — to exercise escalation."""

    name = "fake"

    def __init__(self, runtime):
        self.runtime = runtime
        self.failed_once = False

    async def complete(self, model, prompt, system=None, temperature=0.2, max_tokens=None):
        if not self.failed_once and "resulting code" in prompt:
            self.failed_once = True
            return LLMResult(text="```python\ndef broken(:\n```", model=model,
                             provider="fake", tokens_in=10, tokens_out=10)
        return LLMResult(text=VALID_PYTHON, model=model, provider="fake", tokens_in=10, tokens_out=10)


def _patch(monkeypatch, runtime, provider_cls, models):
    import executor
    models = list(models)
    monkeypatch.setattr("domain.catalog.MODELS", models)
    monkeypatch.setattr("domain.routing.MODELS", models)
    monkeypatch.setattr("domain.escalation.MODELS", models)
    monkeypatch.setattr(executor, "build_provider", lambda name, rt: provider_cls(rt))
    monkeypatch.setattr(executor, "available_providers", lambda rt: {"fake"})
    monkeypatch.setattr(executor, "provider_order", lambda rt: ["fake"])
    return runtime


@pytest.fixture
def patch_valid(monkeypatch, runtime):
    return _patch(monkeypatch, runtime, AlwaysValidProvider, [FAKE_STRONG])


@pytest.fixture
def patch_escalating(monkeypatch, runtime):
    return _patch(monkeypatch, runtime, EscalatingProvider, [FAKE_FAST, FAKE_STRONG])


async def _create_task(runtime, prompt):
    result = await fake_create_and_plan(runtime, prompt=prompt, repo=None, constraints=None,
                                        max_attempts_per_stage=2, budget_usd=None)
    return result["task"]["id"]


async def test_execute_completes_end_to_end(runtime, patch_valid):
    task_id = await _create_task(runtime, "Add a new API endpoint to the users service")
    from executor import execute_task
    summary = await execute_task(runtime, task_id)

    assert summary["task"]["status"] == "completed"
    assert summary["execution"]["status"] == "completed"
    assert len(summary["stages"]) >= 4
    assert all(s["assigned_model"] == "fake-strong" for s in summary["stages"])
    assert summary["escalation"]["occurred"] is False
    assert summary["cost"]["estimated_usd"] == 0.0


async def test_execute_escalates_on_verification_failure(runtime, patch_escalating):
    task_id = await _create_task(runtime, "Add a new API endpoint to return user profiles")
    from executor import execute_task
    summary = await execute_task(runtime, task_id)

    assert summary["task"]["status"] == "completed"
    assert summary["escalation"]["occurred"] is True
    assert summary["escalation"]["count"] >= 1
    assert summary["attempts"]["total"] > len(summary["stages"])


async def test_high_risk_task_requires_approval(runtime, patch_valid):
    result = await fake_create_and_plan(runtime, prompt="Change payment processing retries",
                                        repo=None, constraints=None, max_attempts_per_stage=None,
                                        budget_usd=None)
    assert result["requires_approval"] is True
    assert result["task"]["status"] == "awaiting_approval"

    from executor import execute_task
    with pytest.raises(PermissionError):
        await execute_task(runtime, result["task"]["id"])