"""Task intake, planning, approval, and execution endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from domain.enums import TaskStatus
from planner import create_and_plan
import store
from runtime import Runtime, get_runtime
from schemas import (ApproveRequest, RetryStagesRequest, TaskCreate,
                     TaskConstraintsUpdate, TaskMessageRequest)

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
async def list_tasks(runtime: Runtime = Depends(get_runtime),
                     limit: int = Query(default=50, ge=1, le=100)) -> dict:
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
    ci = await store.get_ci_status(runtime.db, task_id)
    return {
        "task": store.task_dict(task),
        "plan": {"id": plan["id"], "summary": plan["summary"], "stages": stages} if plan else None,
        "latest_execution_id": execution["id"] if execution else None,
        "ci": ci,
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
async def task_events(task_id: str, runtime: Runtime = Depends(get_runtime),
                     limit: int = Query(default=500, ge=1, le=500)) -> dict:
    events = await store.get_events_for_task(runtime.db, task_id, limit=limit)
    return {"events": [store.event_dict(e) for e in events]}


@router.post("/{task_id}/message")
async def post_task_message(task_id: str, body: TaskMessageRequest,
                            runtime: Runtime = Depends(get_runtime)) -> dict:
    """Steer a running task conversationally ("wait, do X instead").

    The message is recorded as a ``developer_message`` event on the task's
    latest execution; the executor folds it into every subsequent stage prompt.
    """
    task = await store.get_task(runtime.db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task["status"] not in (TaskStatus.EXECUTING.value, TaskStatus.PLANNED.value):
        raise HTTPException(status_code=409, detail="task is not running (steer an executing task)")

    execution = await store.get_latest_execution(runtime.db, task_id)
    if execution is None:
        raise HTTPException(status_code=409, detail="no active execution to steer yet")

    message = body.message.strip()
    await store.add_event(runtime.db, execution["id"], task_id, None, "developer_message",
                          message, {"source": "developer"})
    return {"task_id": task_id, "status": "steered", "message": message}


@router.post("/{task_id}/constraints")
async def update_task_constraints(task_id: str, body: TaskConstraintsUpdate,
                                  runtime: Runtime = Depends(get_runtime)) -> dict:
    """Merge constraints into a task — used by plan review to exclude stages."""
    task = await store.get_task(runtime.db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    existing = store.task_dict(task).get("constraints") or {}
    merged = {**existing, **body.constraints}
    await store.update_task(runtime.db, task_id, constraints=store.json_dumps(merged))
    return {"task_id": task_id, "constraints": merged}


@router.post("/{task_id}/retry")
async def retry_task_stages(task_id: str, body: RetryStagesRequest,
                            runtime: Runtime = Depends(get_runtime)) -> dict:
    """Re-run failed stage(s) and everything downstream, reusing prior outputs.

    Stages not in the retry closure keep their persisted results; their
    successful outputs feed the retried stages as context. Budget, routing,
    and verification all apply exactly as in a normal execution.
    """
    from executor import execute_task

    task = await store.get_task(runtime.db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    plan = await store.get_plan_for_task(runtime.db, task_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="task has no plan")
    stages = await store.get_stages(runtime.db, plan["id"])
    known = {s["id"] for s in stages}
    unknown = [sid for sid in body.stage_ids if sid not in known]
    if unknown:
        raise HTTPException(status_code=404,
                             detail=f"unknown stage id(s): {', '.join(unknown[:3])}")
    if task["status"] == TaskStatus.EXECUTING.value:
        raise HTTPException(status_code=409, detail="task is already executing")
    if task["status"] == TaskStatus.AWAITING_APPROVAL.value:
        raise HTTPException(status_code=409, detail="task requires approval first")

    try:
        return await execute_task(runtime, task_id, retry_stage_ids=body.stage_ids)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{task_id}/rollback")
async def rollback_task_changes(task_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    """Queue a git restore of everything this task wrote.

    Requires an attached runner workspace. The restore request is dangerous and
    therefore held in ``awaiting_approval`` until the developer approves it in
    the Runner panel — nothing is reverted silently.
    """
    task = await store.get_task(runtime.db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    ws = await store.get_workspace_for_task(runtime.db, task_id)
    if ws is None:
        raise HTTPException(status_code=409,
                            detail="attach a runner workspace first (changes are reverted via git)")
    ws = store.workspace_dict(ws)

    paths: set[str] = set()
    execution = await store.get_latest_execution(runtime.db, task_id)
    if execution:
        for art in await store.get_artifacts(runtime.db, execution["id"]):
            if art.get("path"):
                paths.add(art["path"])

    if not paths:
        raise HTTPException(status_code=409, detail="no recorded file changes to revert")

    request_id = await store.create_tool_request(
        runtime.db, workspace_id=ws["id"], execution_id=execution["id"] if execution else None,
        tool="git.restore", params={"paths": sorted(paths)},
        dangerous=True, status="awaiting_approval")
    return {"task_id": task_id, "workspace_id": ws["id"],
            "tool_request": store.tool_request_public_dict(await store.get_tool_request(runtime.db, request_id)),
            "paths": sorted(paths)}
