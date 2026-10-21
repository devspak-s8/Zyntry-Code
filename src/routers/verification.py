"""Verification report endpoints — the repo-side runner posts real results.

The VS Code extension (running inside the developer's repository) executes
tests/lint/build/visual checks and posts the outcome here. The execution engine
merges these reports into each stage's verification decision: failed reports
trigger escalation; passed reports clear the corresponding limitations.
"""

from fastapi import APIRouter, Depends, HTTPException

import store
from runtime import Runtime, get_runtime
from schemas import VerificationReportRequest

router = APIRouter(prefix="/executions", tags=["verification"])


@router.post("/{execution_id}/stages/{stage_id}/verification")
async def post_verification_report(execution_id: str, stage_id: str,
                                   body: VerificationReportRequest,
                                   runtime: Runtime = Depends(get_runtime)) -> dict:
    execution = await store.get_execution(runtime.db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    stage = await store.get_stage(runtime.db, stage_id)
    if stage is None or stage["plan_id"] != execution["plan_id"]:
        raise HTTPException(status_code=404, detail="stage not found in this execution")

    report_id = await store.create_verification_report(
        runtime.db, execution_id=execution_id, stage_id=stage_id,
        attempt_id=body.attempt_id, tool=body.tool, status=body.status,
        output=body.output, duration_ms=body.duration_ms)
    return {"report_id": report_id, "tool": body.tool, "status": body.status}


@router.get("/{execution_id}/stages/{stage_id}/verification")
async def get_verification_reports(execution_id: str, stage_id: str,
                                   runtime: Runtime = Depends(get_runtime)) -> dict:
    execution = await store.get_execution(runtime.db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    stage = await store.get_stage(runtime.db, stage_id)
    if stage is None or stage["plan_id"] != execution["plan_id"]:
        raise HTTPException(status_code=404, detail="stage not found in this execution")
    reports = await store.get_verification_reports(runtime.db, stage_id)
    return {"reports": reports}
