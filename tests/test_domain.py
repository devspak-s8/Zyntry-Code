"""Unit tests for assessment, routing, verification, and escalation."""

from domain import assessment, escalation, routing, verification
from domain.catalog import ModelSpec, MODELS
from domain.enums import Capability, RiskLevel, StageKind


def test_assessment_risk_classification():
    assert assessment.assess("fix a typo in the button label")["risk_level"] == "low"
    assert assessment.assess("change payment webhook retries")["risk_level"] == "critical"
    assert assessment.assess("add authentication to the admin panel")["risk_level"] == "critical"


def test_assessment_kind():
    assert assessment.assess("build a notification system with persistence and frontend")["task_kind"] == "full_stack"
    assert assessment.assess("add an API endpoint for users")["task_kind"] == "backend"
    assert assessment.assess("fix the responsive navigation css")["task_kind"] == "frontend"


def test_routing_escalates_with_risk():
    avail = {"openai", "anthropic", "workers_ai"}
    low, _, _ = routing.select_model(StageKind.IMPLEMENT.value, RiskLevel.LOW.value, avail, ["openai", "anthropic", "workers_ai"])
    high, _, _ = routing.select_model(StageKind.IMPLEMENT.value, RiskLevel.CRITICAL.value, avail, ["openai", "anthropic", "workers_ai"])
    assert low is not None and high is not None
    # Critical risk requires a stronger (higher-tier) model than low risk.
    assert high.tier >= low.tier


def test_routing_respects_available_providers():
    selected, _, _ = routing.select_model(
        StageKind.IMPLEMENT.value, RiskLevel.LOW.value, {"anthropic"}, ["anthropic"])
    assert selected is not None
    assert selected.provider == "anthropic"


def test_routing_security_review_requires_strong_model():
    selected, candidates, _ = routing.select_model(
        StageKind.SECURITY_REVIEW.value, RiskLevel.LOW.value, {"anthropic", "openai"}, ["anthropic", "openai"])
    assert selected is not None
    assert selected.tier >= 3


def test_verification_detects_bad_python():
    outcome = verification.verify_stage(
        StageKind.IMPLEMENT.value, ["syntax", "tests"],
        "```python\ndef broken(:\n```")
    assert outcome.status == "failed"
    assert any("syntax" in f for f in outcome.failures)


def test_verification_reports_environment_limitation():
    outcome = verification.verify_stage(
        StageKind.IMPLEMENT.value, ["syntax", "tests"],
        "```python\ndef ok():\n    return 1\n```")
    assert outcome.status == "limited"          # tests require repo sandbox
    assert any("tests" in l for l in outcome.limitations)


def test_verification_no_code_fails():
    outcome = verification.verify_stage(StageKind.IMPLEMENT.value, ["syntax"], "Here is a plan, no code though.")
    assert outcome.status == "failed"


def test_verification_ts_not_parsed_as_python():
    """TypeScript must NOT be ast-parsed as Python (regression: `import { } from`)."""
    ts_code = "```typescript:src/auth/session.ts\nimport { TokenPair } from './tokens';\n\nexport class Session {\n  async getToken(): Promise<string> {\n    return 'x';\n  }\n}\n```"
    outcome = verification.verify_stage(StageKind.IMPLEMENT.value, ["syntax"], ts_code)
    assert outcome.status == "passed"          # no failure, syntax check skipped for TS
    assert any(c["type"] == "syntax" and c["status"] == "skipped" for c in outcome.checks)


def test_verification_unfenced_ts_import_not_misdetected():
    """Bare `import { ... } from` without a fence must not trip the Python parser."""
    outcome = verification.verify_stage(
        StageKind.IMPLEMENT.value, ["syntax"],
        "import { TokenPair, refreshToken } from './tokens';\nexport class A {}")
    assert outcome.status != "failed"


def test_escalation_candidates_are_stronger():
    current = ModelSpec("gpt-4.1-mini", "openai", "mini", 1, 128_000, 0.4, 1.6,
                        frozenset({Capability.CODE.value}), "fast")
    candidates = escalation.escalation_candidates(current, {"code"}, {"openai", "anthropic"}, MODELS)
    assert candidates
    assert all(m.tier > current.tier for m in candidates)


def test_estimate_tokens_and_cost():
    assert escalation.estimate_tokens("") == 0
    assert escalation.estimate_tokens("12345678") == 2  # 8 chars // 4
    model = ModelSpec("m", "openai", "m", 1, 1000, 1.0, 2.0, frozenset({"code"}), "fast")
    cost = escalation.attempt_cost(model, 1_000_000, 1_000_000)
    assert abs(cost - 3.0) < 1e-9