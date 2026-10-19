"""Shared test fixtures."""

import glob
import os
import sys
import uuid

import pytest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

MIGRATIONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")

from db import SQLiteDatabase  # noqa: E402
from runtime import Runtime, set_local_runtime  # noqa: E402


def pytest_configure(config) -> None:
    """Point pytest's temp dir at a path this machine's cloud filter allows."""
    basetemp = os.environ.get("PYTEST_BASETEMP")
    if not basetemp:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        basetemp = os.path.join(base, "Temp", "opencode", "pytest-tmp")
    config.option.basetemp = basetemp


async def _migrate(db: SQLiteDatabase) -> None:
    from db import split_sql
    for path in sorted(glob.glob(os.path.join(MIGRATIONS, "*.sql"))):
        with open(path, "r", encoding="utf-8") as fh:
            sql = fh.read()
        for stmt in split_sql(sql):
            await db.execute(stmt)


@pytest.fixture
async def runtime() -> Runtime:
    db = SQLiteDatabase(":memory:")
    await _migrate(db)
    rt = Runtime(env=None, db=db)
    set_local_runtime(rt)
    return rt


# A deterministic stand-in plan shape for tests that need a persisted plan but
# must not depend on a configured LLM provider (planning is LLM-only).
_FAKE_PLAN_STAGES = [
    ("understand", [], "Understand the repository"),
    ("analyze", [0], "Analyze requirements and dependencies"),
    ("plan", [1], "Create an implementation plan"),
    ("implement", [2], "Implement the change"),
    ("test", [3], "Generate and run tests"),
    ("review", [3], "Review the change"),
    ("verify", [4, 5], "Verify the final result"),
]


async def fake_create_and_plan(runtime: Runtime, *, prompt: str, repo: str | None,
                               constraints: dict | None, max_attempts_per_stage: int | None,
                               budget_usd: float | None) -> dict:
    """Deterministic stand-in for ``planner.create_and_plan`` (tests only).

    Mirrors the real intake flow (assessment -> approval gate -> persisted plan
    and stages) so execution, ingestion, auth, and reporting tests can run
    without a configured provider.
    """
    import store
    from domain import assessment
    from domain.enums import RiskLevel, StageKind, TaskStatus
    from domain.verification import VERIFICATION_BY_KIND

    db = runtime.db
    result = assessment.assess(prompt)
    risk = result["risk_level"]

    merged = dict(constraints or {})
    if max_attempts_per_stage is not None:
        merged.setdefault("max_attempts_per_stage", max_attempts_per_stage)
    if budget_usd is not None:
        merged.setdefault("budget_usd", budget_usd)

    needs_approval = risk in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
    status = TaskStatus.AWAITING_APPROVAL.value if needs_approval else TaskStatus.PLANNED.value

    task_id = await store.create_task(
        db, prompt=prompt, repo=repo, status=status, risk_level=risk,
        complexity=result["complexity"], task_kind=result["task_kind"],
        constraints=merged)

    plan_id = await store.create_plan(db, task_id, "fake plan", source="llm")
    stage_ids = [uuid.uuid4().hex for _ in _FAKE_PLAN_STAGES]
    for i, (kind, deps, title) in enumerate(_FAKE_PLAN_STAGES):
        await store.create_stage(
            db, plan_id, stage_id=stage_ids[i], kind=kind, title=title,
            # Empty description: the executor falls back to its per-kind
            # STAGE_INSTRUCTIONS, matching the real planner's stage prompts.
            description="",
            dependencies=[stage_ids[d] for d in deps],
            verification_types=list(VERIFICATION_BY_KIND.get(StageKind(kind), [])),
            risk_level=risk, position=i)

    stages = [store.stage_dict(s) for s in await store.get_stages(db, plan_id)]
    return {
        "task": store.task_dict(await store.get_task(db, task_id)),
        "plan": {"id": plan_id, "summary": "fake plan", "source": "llm", "stages": stages},
        "assessment": result,
        "requires_approval": needs_approval,
    }