"""Execution detail + change-tracking endpoints."""

from fastapi import APIRouter, Depends, HTTPException

import store
from reporter import build_summary
from runtime import Runtime, get_runtime
from schemas import ChangeRecordRequest

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("/{execution_id}")
async def get_execution(execution_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    execution = await store.get_execution(runtime.db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return await build_summary(runtime, execution_id)


@router.post("/{execution_id}/changes")
async def post_changes(execution_id: str, body: ChangeRecordRequest,
                       runtime: Runtime = Depends(get_runtime)) -> dict:
    execution = await store.get_execution(runtime.db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    change_id = await store.record_change(
        runtime.db, execution_id=execution_id, path=body.path, op=body.op,
        before=body.before, after=body.after)
    return {"change_id": change_id}


@router.get("/{execution_id}/changes")
async def get_changes(execution_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    execution = await store.get_execution(runtime.db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return {"changes": await store.get_changes(runtime.db, execution_id)}