"""Tool-request service: dispatch operations and fold results into the engine.

This is the "execution adapter" — it translates the engine's needs (apply these
files, run these checks) into authorized workspace operations, and translates
the runner's real results back into verification evidence.
"""

from typing import Any

from db import Database
from domain import tools as tools_domain
from util import json_dumps, now_iso
import store


async def dispatch_apply_artifact(db: Database, *, workspace_id: str, execution_id: str,
                                  stage_id: str, attempt_id: str, path: str, content: str) -> str:
    """Request that an artifact be applied to the workspace working tree."""
    return await store.create_tool_request(
        db, workspace_id=workspace_id, execution_id=execution_id, stage_id=stage_id,
        attempt_id=attempt_id,
        tool="fs.write", params={"path": path, "content": content},
        dangerous=False, status="queued")


async def dispatch_verification_command(db: Database, *, workspace_id: str, execution_id: str,
                                        stage_id: str, attempt_id: str, command_key: str,
                                        command: str, verify_as: str, dangerous: bool) -> str:
    return await store.create_tool_request(
        db, workspace_id=workspace_id, execution_id=execution_id, stage_id=stage_id,
        attempt_id=attempt_id,
        tool="command.run", params={"cmd": command, "cwd": "."},
        verify_as=verify_as, dangerous=dangerous, status="queued")


async def dispatch_command(db: Database, *, workspace_id: str, command: str,
                           allowed_commands: list[str], execution_id: str | None = None,
                           stage_id: str | None = None, attempt_id: str | None = None) -> dict:
    """Dispatch an arbitrary command through the security policy.

    Unknown or dangerous commands are held in ``awaiting_approval``.
    Returns the request dict (status reflects the gate).
    """
    dangerous = tools_domain.is_dangerous(command)
    allowed = tools_domain.is_allowed(command, allowed_commands)
    status = "awaiting_approval" if (dangerous or not allowed) else "queued"
    request_id = await store.create_tool_request(
        db, workspace_id=workspace_id, execution_id=execution_id, stage_id=stage_id,
        attempt_id=attempt_id,
        tool="command.run", params={"cmd": command, "cwd": "."},
        dangerous=dangerous or not allowed, status=status)
    return store.tool_request_dict(await store.get_tool_request(db, request_id))


async def submit_tool_result(db: Database, *, request_id: str, status: str,
                             result: dict | None = None) -> dict | None:
    """Record a runner's result for a tool request.

    Side effects:
    - command.run results become verification reports (keyed by ``verify_as``);
    - fs operations report their per-file changes, recorded in ``changes``;
    - failed file application produces a failing ``fs_apply`` report so the
      stage's verification fails and the engine can escalate.
    """
    request = await store.get_tool_request(db, request_id)
    if request is None:
        return None

    terminal = status in ("succeeded", "failed", "timed_out", "cancelled")
    fields: dict[str, Any] = {
        "status": status,
        "result": json_dumps(result or {}),
    }
    if terminal:
        fields["finished_at"] = now_iso()
    await store.update_tool_request(db, request_id, **fields)

    req = store.tool_request_dict(await store.get_tool_request(db, request_id))
    result = result or {}

    can_report = bool(req.get("execution_id") and req.get("stage_id"))

    # Verification evidence for verification-mapped commands.
    if req["tool"] == "command.run" and req.get("verify_as") and can_report:
        tool = req["verify_as"]
        passed = status == "succeeded" and int(result.get("exit_code") or 0) == 0
        await store.create_verification_report(
            db, execution_id=req["execution_id"], stage_id=req["stage_id"],
            attempt_id=req.get("attempt_id"), tool=tool,
            status="passed" if passed else "failed",
            output=f"exit_code={result.get('exit_code')}\nstdout:\n{result.get('stdout', '')}\nstderr:\n{result.get('stderr', '')}"[:4000],
            duration_ms=result.get("duration_ms"))

    # File-change evidence for fs operations.
    for change in result.get("files") or []:
        if change.get("path") and can_report:
            await store.record_change(
                db, execution_id=req["execution_id"], stage_id=req["stage_id"],
                workspace_id=req["workspace_id"], path=change["path"],
                op=change.get("op", "modify"),
                before=change.get("before"), after=change.get("after"))

    # A failed file application fails verification (triggers escalation).
    if req["tool"] in ("fs.write", "fs.edit", "fs.delete") and status == "failed" and can_report:
        await store.create_verification_report(
            db, execution_id=req["execution_id"], stage_id=req["stage_id"],
            attempt_id=req.get("attempt_id"), tool="fs_apply", status="failed",
            output=f"{req['tool']} failed: {result.get('error') or result.get('stderr') or ''}"[:1000])

    return req


async def dispatch_readonly_tool(db: Database, *, workspace_id: str, execution_id: str,
                                 stage_id: str, attempt_id: str, tool: str,
                                 params: dict) -> str:
    """Dispatch a read-only workspace tool (no approval gate)."""
    return await store.create_tool_request(
        db, workspace_id=workspace_id, execution_id=execution_id, stage_id=stage_id,
        attempt_id=attempt_id,
        tool=tool, params=params, dangerous=False, status="queued")


async def dispatch_agent_tool(db: Database, *, workspace_id: str, execution_id: str,
                              stage_id: str, attempt_id: str, tool: str, params: dict,
                              allowed_commands: list[str]) -> dict:
    """Dispatch a non-readonly agent tool.

    ``command.run`` goes through the security gate; MCP and terminal operations
    are trusted (they target user-configured servers / local sessions) and are
    queued directly.
    """
    if tool == "command.run":
        return await dispatch_command(
            db, workspace_id=workspace_id, command=str(params.get("cmd", "")),
            allowed_commands=allowed_commands, execution_id=execution_id,
            stage_id=stage_id, attempt_id=attempt_id)
    request_id = await store.create_tool_request(
        db, workspace_id=workspace_id, execution_id=execution_id, stage_id=stage_id,
        attempt_id=attempt_id, tool=tool, params=params, dangerous=False, status="queued")
    return store.tool_request_dict(await store.get_tool_request(db, request_id))


async def await_tool_results(db: Database, execution_id: str, timeout_seconds: float,
                             poll_interval: float = 1.0) -> dict[str, dict]:
    """Wait until every dispatched request for an execution is terminal.

    Returns the terminal requests keyed by id. Approval-gated requests that
    never get approved are reported as ``awaiting_approval`` and NOT treated
    as failures (the caller decides how to surface them).
    """
    import asyncio
    import time

    deadline = time.monotonic() + timeout_seconds
    while True:
        pending = await store.pending_tool_requests(db, execution_id)
        actionable = [r for r in pending if r["status"] != "awaiting_approval"]
        if not actionable:
            break
        if time.monotonic() >= deadline:
            break
        await asyncio.sleep(poll_interval)

    terminal: dict[str, dict] = {}
    rows = await db.query(
        "SELECT * FROM tool_requests WHERE execution_id = ? ORDER BY created_at ASC",
        (execution_id,), ("id", "execution_id", "stage_id", "workspace_id", "tool", "params",
                          "verify_as", "dangerous", "status", "result", "created_at",
                          "dispatched_at", "finished_at"))
    for r in rows:
        req = store.tool_request_dict(r)
        if req["status"] in ("succeeded", "failed", "timed_out", "cancelled", "awaiting_approval"):
            terminal[req["id"]] = req
    return terminal