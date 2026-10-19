"""Execution reporting: builds the auditable summary for a finished execution."""

from runtime import Runtime
import store
from util import truncate


def _parse_iso(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        from datetime import datetime
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return 0.0


async def build_summary(runtime: Runtime, execution_id: str) -> dict:
    db = runtime.db
    execution = await store.get_execution(db, execution_id)
    if execution is None:
        raise ValueError("execution not found")

    task = await store.get_task(db, execution["task_id"]) or {}
    attempts = [store.attempt_dict(a) for a in await store.get_attempts(db, execution_id)]
    events = [store.event_dict(e) for e in await store.get_events(db, execution_id)]
    artifacts = await store.get_artifacts(db, execution_id)

    plan = await store.get_plan_for_task(db, execution["task_id"])
    stages = [store.stage_dict(s) for s in await store.get_stages(db, plan["id"])] if plan else []

    # Verification reports per stage.
    reports_by_stage: dict[str, list[dict]] = {}
    for s in stages:
        reports_by_stage[s["id"]] = await store.get_verification_reports(db, s["id"])

    failed_attempts = [a for a in attempts if a["status"] == "failed"]
    escalation_reasons = [
        e.get("data", {}).get("failures") or e.get("message")
        for e in events if e["type"] in ("verification_failed", "attempt_failed")
    ]
    limitations: list[str] = []
    for e in events:
        if e["type"] == "verification_limited":
            limitations.extend(e.get("data", {}).get("limitations", []))

    started = _parse_iso(execution.get("started_at"))
    finished = _parse_iso(execution.get("finished_at"))
    total_time_s = round(max(0.0, finished - started), 2)

    artifact_paths = sorted({a["path"] for a in artifacts})
    implemented = [s for s in stages if s["kind"].startswith("implement") or s["kind"] == "database"]

    budget_exceeded = any(e["type"] == "budget_exceeded" for e in events)
    constraints = store.task_dict(task).get("constraints") or {}
    budget_limit = constraints.get("budget_usd")

    return {
        "task": {
            "id": task.get("id"),
            "prompt": task.get("prompt"),
            "status": task.get("status"),
            "risk_level": task.get("risk_level"),
            "complexity": task.get("complexity"),
        },
        "execution": {
            "id": execution["id"],
            "status": execution["status"],
            "plan_id": execution["plan_id"],
        },
        "plan": {
            "summary": plan.get("summary") if plan else None,
            "source": plan.get("source") if plan else None,
        },
        "stages": [
            {
                "id": s["id"],
                "kind": s["kind"],
                "title": s["title"],
                "status": s["status"],
                "assigned_model": s["assigned_model"],
                "verification_types": s.get("verification_types"),
                "verification_reports": [
                    {"tool": r["tool"], "status": r["status"], "duration_ms": r["duration_ms"]}
                    for r in reports_by_stage.get(s["id"], [])
                ],
            }
            for s in stages
        ],
        "files_changed": len(artifact_paths) or len(implemented),
        "artifacts": [
            {"path": a["path"], "kind": a["kind"], "language": a["language"],
             "source": a["source"], "stage_id": a["stage_id"]}
            for a in artifacts
        ],
        "tests": {
            "status": "limited" if limitations else ("passed" if not failed_attempts else "failed"),
            "detail": "Test execution requires the repo sandbox; not run by the backend."
            if any("tests" in l for l in limitations) else None,
        },
        "attempts": {
            "total": len(attempts),
            "failed": len(failed_attempts),
            "detail": [
                {
                    "id": a["id"],
                    "stage_id": a["stage_id"],
                    "attempt": a["attempt_number"],
                    "model": a["model_id"],
                    "status": a["status"],
                    "verification": a["verification_status"],
                    "error": (a.get("error") or "")[:300],
                    "output": truncate(a.get("output") or "", 600),
                }
                for a in attempts
            ],
        },
        "escalation": {
            "occurred": execution["escalation_count"] > 0,
            "count": execution["escalation_count"],
            "reasons": escalation_reasons,
        },
        "verification": {
            "limitations": limitations,
        },
        "budget": {
            "limit_usd": budget_limit,
            "spent_usd": round(execution["total_cost"], 6),
            "exceeded": budget_exceeded,
        },
        "cost": {
            "estimated_usd": round(execution["total_cost"], 6),
            "total_tokens": execution["total_tokens"],
        },
        "timing": {
            "total_seconds": total_time_s,
        },
        "events": events,
    }