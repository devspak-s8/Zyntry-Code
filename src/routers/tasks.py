"""Task intake, planning, approval, and execution endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from domain.enums import TaskStatus
from planner import create_and_plan
import store
from runtime import Runtime, get_runtime
from schemas import ApproveRequest, TaskCreate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("")
async def create_task(body: TaskCreate, runtime: Runtime = Depends(get_runtime)) -> dict:
    try:
        result = await create_and_plan(
            runtime,
            prompt=body.prompt,
            repo=body.repo,
            constraints=body.constraints,
            max_attempts_per_stage=body.max_attempts_per_stage,
            budget_usd=body.budget_usd,
        )
    except RuntimeError as exc:
        # Planning is LLM-only: a failure here is loud and surfaced as 503.
        raise HTTPException(status_code=503, detail=str(exc))
    return result


@router.get("")
async def list_tasks(runtime: Runtime = Depends(get_runtime), limit: int = 50) -> dict:
    tasks = await store.list_tasks(runtime.db, limit=limit)
    return {"tasks": [store.task_dict(t) for t in tasks]}


@router.get("/{task_id}")
async def get_task(task_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    task = await store.get_task(runtime.db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    plan = await store.get_plan_for_task(runtime.db, task_id)
    stages = [store.stage_dict(s) for s in await store.get_stages(runtime.db, plan["id"])] if plan else []
    execution = await store.get_latest_execution(runtime.db, task_id)
    return {
        "task": store.task_dict(task),
        "plan": {"id": plan["id"], "summary": plan["summary"], "stages": stages} if plan else None,
        "latest_execution_id": execution["id"] if execution else None,
    }


@router.post("/{task_id}/approve")
async def approve_task(task_id: str, body: ApproveRequest, runtime: Runtime = Depends(get_runtime)) -> dict:
    task = await store.get_task(runtime.db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task["status"] != TaskStatus.AWAITING_APPROVAL.value:
        raise HTTPException(status_code=409, detail="task is not awaiting approval")
    if not body.approved:
        await store.update_task(runtime.db, task_id, status=TaskStatus.CANCELLED.value)
        return {"task_id": task_id, "status": TaskStatus.CANCELLED.value}
    await store.update_task(runtime.db, task_id, status=TaskStatus.PLANNED.value)
    if body.auto_execute:
        from executor import execute_task
        return await execute_task(runtime, task_id)
    return {"task_id": task_id, "status": TaskStatus.PLANNED.value}


@router.post("/{task_id}/execute")
async def execute_task_endpoint(task_id: str, runtime: Runtime = Depends(get_runtime),
                                mode: str = "sync") -> dict:
    from executor import execute_task

    if mode == "workflow":
        workflow = getattr(runtime.env, "EXECUTION_WORKFLOW", None) if runtime.env else None
        if workflow is None:
            raise HTTPException(
                status_code=400,
                detail="workflow mode requires the EXECUTION_WORKFLOW binding "
                       "(Cloudflare Workflows; available only on the deployed Worker).")
        instance = await workflow.create({"task_id": task_id})
        return {"mode": "workflow", "workflow_instance_id": instance.id, "task_id": task_id}

    try:
        return await execute_task(runtime, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{task_id}/events")
async def task_events(task_id: str, runtime: Runtime = Depends(get_runtime), limit: int = 500) -> dict:
    events = await store.get_events_for_task(runtime.db, task_id, limit=limit)
    return {"events": [store.event_dict(e) for e in events]}