"""Inbound webhooks from external systems (CI, deployment).

CI posts status for a delivered workspace; the status lands on the task and
becomes visible in the chat timeline. Keep this endpoint permissive on input
(shallow validation) but write only task-scoped state.
"""

import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from runtime import Runtime, get_runtime
from schemas import CiWebhookRequest
from security import insecure_local_allowed
import store

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/ci")
async def ci_status(body: CiWebhookRequest, request: Request,
                    runtime: Runtime = Depends(get_runtime)) -> dict:
    """CI posts this after a delivered push: status is recorded on the task."""
    secret = runtime.get("CI_WEBHOOK_SECRET")
    timestamp = request.headers.get("x-webhook-timestamp", "")
    signature = request.headers.get("x-webhook-signature", "")
    if secret:
        try:
            age = abs(time.time() - float(timestamp))
        except (TypeError, ValueError):
            age = float("inf")
        expected = "sha256=" + hmac.new(
            str(secret).encode(),
            f"{timestamp}.".encode() + await request.body(),
            hashlib.sha256,
        ).hexdigest()
        if age > 300 or not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="invalid webhook signature")
    elif not insecure_local_allowed(runtime):
        raise HTTPException(status_code=503, detail="CI_WEBHOOK_SECRET is not configured")
    ws = await store.get_workspace(runtime.db, body.workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    task_id = ws.get("task_id")
    if not task_id:
        raise HTTPException(status_code=409, detail="workspace is not attached to a task")

    status = "failed" if body.status in ("failure", "failed") else body.status
    await store.set_ci_status(runtime.db, task_id, status, body.url, body.detail)

    # Fold it into the task's latest execution timeline when one exists.
    execution = await store.get_latest_execution(runtime.db, task_id)
    if execution:
        await store.add_event(
            runtime.db, execution["id"], task_id, None, "ci_status",
            f"CI reported {status}", {"status": status, "url": body.url, "detail": body.detail})

    return {"task_id": task_id, "status": status, "recorded": True}
