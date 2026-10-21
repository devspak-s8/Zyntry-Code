"""Workspace lifecycle + runner bridge.

One protocol, two runners:
- ``provider=local``  — the VS Code extension runs operations in the user's repo
- ``provider=remote`` — a worker (see ``worker/``) runs them on cloud infra

Runners long-poll for queued tool requests and post real results back. Command
results automatically become verification reports, closing the loop:
generate code -> apply changes -> run checks -> inspect failures -> escalate.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from domain import tools as tools_domain
from runtime import Runtime, get_runtime
from security import require_runner_token
from schemas import (DeliverRequest, McpServersRequest, RepoRulesRequest,
                     SecretSetRequest, ToolApproveRequest, ToolDispatchRequest,
                     ToolResultRequest, WorkspaceAttachRequest, WorkspaceCreate,
                     WorkspaceStateRequest)
import store
import tools_service
from util import now_iso, uuid_str

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

_LONG_POLL_SECONDS = 25.0
_APPROVAL_REQUIRED_TOOLS = {
    "fs.write", "fs.edit", "fs.delete", "git.commit", "git.push", "git.restore",
    "github.pr", "command.start", "terminal.start", "terminal.input",
    "terminal.output", "terminal.resize", "terminal.stop", "mcp.call",
}


def _check_local_token(request: Request, ws: dict) -> None:
    """Local-provider workspaces require the per-workspace runner token."""
    if ws.get("provider") != "local":
        return
    expected = ws.get("runner_token")
    provided = request.headers.get("x-workspace-token", "")
    if not expected or provided != expected:
        raise HTTPException(status_code=403, detail="missing or invalid x-workspace-token for this workspace")


@router.post("")
async def create_workspace(body: WorkspaceCreate, runtime: Runtime = Depends(get_runtime)) -> dict:
    db = runtime.db
    workspace_id = uuid_str()
    runner_token = uuid_str() if body.provider == "local" else None

    commands = {k: v.model_dump() for k, v in body.commands.items()}
    if not commands and body.repo_url:
        # auto-detect project commands if the task has an ingested repo snapshot
        if body.task_id:
            repo_files = await store.get_repo_files(db, body.task_id)
            commands = tools_domain.detect_commands(repo_files)

    mcp_servers = [m.model_dump() for m in body.mcp_servers]
    await store.create_workspace(
        db, workspace_id=workspace_id, task_id=body.task_id, repo_url=body.repo_url,
        branch=body.branch, provider=body.provider, commands=commands, env=body.env,
        allowed_commands=body.allowed_commands, auto_commit=body.auto_commit,
        timeout_seconds=body.timeout_seconds, runner_token=runner_token)
    if mcp_servers:
        await store.update_workspace(db, workspace_id, mcp_servers=store.json_dumps(mcp_servers))

    result = store.workspace_public_dict(await store.get_workspace(db, workspace_id))
    if runner_token:
        # Shown exactly once; store it in the local runner's settings.
        result["runner_token"] = runner_token
    return result


@router.get("")
async def list_workspaces(request: Request, runtime: Runtime = Depends(get_runtime),
                          pending: bool = False, provider: str = "remote") -> dict:
    if pending:
        rows = await store.pending_workspaces(runtime.db, provider)
        if provider == "remote":
            try:
                require_runner_token(request, runtime)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            return {"workspaces": [store.workspace_runner_dict(w) for w in rows]}
        return {"workspaces": [store.workspace_public_dict(w) for w in rows]}
    rows = await store.list_all_workspaces(runtime.db)
    return {"workspaces": [store.workspace_public_dict(w) for w in rows]}


@router.post("/{workspace_id}/attach")
async def attach_workspace(workspace_id: str, body: WorkspaceAttachRequest,
                           runtime: Runtime = Depends(get_runtime)) -> dict:
    """Attach an existing workspace to a task.

    Runner-owned (local) workspaces are created by the VS Code extension, which
    holds the runner token; attaching here makes the executor dispatch file ops
    and verification commands to that runner on the next execution.
    """
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    task = await store.get_task(runtime.db, body.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    await store.update_workspace(runtime.db, workspace_id, task_id=body.task_id)
    return store.workspace_public_dict(await store.get_workspace(runtime.db, workspace_id))


@router.post("/{workspace_id}/state")
async def update_workspace_state(workspace_id: str, body: WorkspaceStateRequest,
                                 request: Request, runtime: Runtime = Depends(get_runtime)) -> dict:
    """Runner-reported state: base/head commit, workdir, status, error."""
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    try:
        _check_local_token(request, ws)
        if ws.get("provider") != "local":
            require_runner_token(request, runtime)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    await store.update_workspace(runtime.db, workspace_id, **fields)
    return store.workspace_public_dict(await store.get_workspace(runtime.db, workspace_id))


# ---- secrets + delivery -----------------------------------------------------

@router.post("/{workspace_id}/secrets")
async def set_workspace_secret(workspace_id: str, body: SecretSetRequest,
                               runtime: Runtime = Depends(get_runtime)) -> dict:
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    await store.set_secret(runtime.db, workspace_id, body.key, body.value,
                           runtime.get("SECRET_ENCRYPTION_KEY"))
    return {"workspace_id": workspace_id, "key": body.key, "stored": True}


@router.get("/{workspace_id}/secrets")
async def list_workspace_secrets(workspace_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    """Returns keys only — values are never returned via the API."""
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    row = await runtime.db.query("SELECT key FROM secrets WHERE workspace_id = ? ORDER BY key",
                                 (workspace_id,), ("key",))
    return {"workspace_id": workspace_id, "keys": [item["key"] for item in row]}


@router.get("/{workspace_id}/secrets/values")
async def get_workspace_secret_values(workspace_id: str, request: Request,
                                      runtime: Runtime = Depends(get_runtime),
                                      keys: list[str] = Query(default=[])) -> dict:
    """Runner-only secret delivery; values never appear in public serializers."""
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    try:
        _check_local_token(request, ws)
        if ws.get("provider") != "local":
            require_runner_token(request, runtime)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if len(keys) > 20:
        raise HTTPException(status_code=400, detail="too many secret keys")
    values = await store.get_secrets(runtime.db, workspace_id, keys or None,
                                     runtime.get("SECRET_ENCRYPTION_KEY"))
    return {"workspace_id": workspace_id, "secrets": values}


@router.put("/{workspace_id}/mcp-servers")
async def set_mcp_servers(workspace_id: str, body: McpServersRequest,
                          runtime: Runtime = Depends(get_runtime)) -> dict:
    """Configure the MCP servers the agent may call via mcp.call / mcp.list_tools."""
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    servers = [m.model_dump() for m in body.servers]
    await store.update_workspace(runtime.db, workspace_id, mcp_servers=store.json_dumps(servers))
    return {"workspace_id": workspace_id,
            "mcp_servers": [{k: v for k, v in server.items() if k != "env"} for server in servers]}


@router.get("/{workspace_id}/mcp-servers")
async def get_mcp_servers(workspace_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    ws = store.workspace_public_dict(ws)
    return {"workspace_id": workspace_id, "mcp_servers": ws.get("mcp_servers") or []}


# ---- repo rule packs (per-repo custom verification) --------------------------

@router.put("/{workspace_id}/rules")
async def set_repo_rules(workspace_id: str, body: RepoRulesRequest,
                         runtime: Runtime = Depends(get_runtime)) -> dict:
    """Replace the workspace's repo rule pack.

    - ``regex`` rules are scanned against every generated stage output;
    - ``command`` rules run as extra verification commands (approval-gated);
    - ``constitution`` rules are injected into every stage prompt as guardrails.
    """
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    rules = [r.model_dump() for r in body.rules]
    await store.replace_repo_rules(runtime.db, workspace_id, rules)
    return {"workspace_id": workspace_id, "rules": rules}


@router.get("/{workspace_id}/rules")
async def get_repo_rules(workspace_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return {"workspace_id": workspace_id,
            "rules": await store.get_repo_rules(runtime.db, workspace_id)}


@router.post("/{workspace_id}/deliver")
async def deliver_workspace(workspace_id: str, body: DeliverRequest,
                            runtime: Runtime = Depends(get_runtime)) -> dict:
    """Phase 5 delivery: commit -> push -> PR.

    git.commit is dispatched immediately; git.push and github.pr are dangerous
    and therefore held in ``awaiting_approval`` until explicitly approved.
    Secret values (GIT_PUSH_TOKEN / GITHUB_TOKEN) are attached ONLY to the
    tool request that needs them and are never stored in results or logs.
    """
    ws = store.workspace_dict(await store.get_workspace(runtime.db, workspace_id))
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    dispatched = []

    commit_id = await store.create_tool_request(
        runtime.db, workspace_id=workspace_id, tool="git.commit",
        params={"message": body.title[:200]}, status="queued")
    dispatched.append({"id": commit_id, "tool": "git.commit", "status": "queued"})

    push_id = await store.create_tool_request(
        runtime.db, workspace_id=workspace_id, tool="git.push",
        params={"remote": ws.get("repo_url"), "branch": None,
                "secret_keys": ["GIT_PUSH_TOKEN"]},
        dangerous=True, status="awaiting_approval")
    dispatched.append({"id": push_id, "tool": "git.push", "status": "awaiting_approval"})

    pr_id = await store.create_tool_request(
        runtime.db, workspace_id=workspace_id, tool="github.pr",
        params={"title": body.title, "body": body.body,
                "base": body.base_branch or ws.get("branch") or "main",
                "head": None,
                "secret_keys": ["GITHUB_TOKEN"]},
        dangerous=True, status="awaiting_approval")
    dispatched.append({"id": pr_id, "tool": "github.pr", "status": "awaiting_approval"})

    return {"workspace_id": workspace_id, "tool_requests": dispatched,
            "note": "approve git.push / github.pr with POST /tool-requests/{id}/approve"}


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return store.workspace_public_dict(ws)


@router.post("/{workspace_id}/stop")
async def stop_workspace(workspace_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    await store.update_workspace(runtime.db, workspace_id, status="stopped")
    return {"workspace_id": workspace_id, "status": "stopped"}


@router.post("/{workspace_id}/resume")
async def resume_workspace(workspace_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    await store.update_workspace(runtime.db, workspace_id, status="ready")
    return {"workspace_id": workspace_id, "status": "ready"}


@router.get("/{workspace_id}/tool-requests")
async def list_tool_requests(workspace_id: str, runtime: Runtime = Depends(get_runtime),
                             status: str | None = None) -> dict:
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    rows = await store.list_tool_requests(runtime.db, workspace_id, status=status)
    return {"tool_requests": [store.tool_request_public_dict(r) for r in rows]}


@router.post("/{workspace_id}/tool-requests")
async def dispatch_tool_request(workspace_id: str, body: ToolDispatchRequest,
                                runtime: Runtime = Depends(get_runtime)) -> dict:
    """Dispatch a tool request into the workspace.

    ``command.run`` goes through the security gate (approval for unknown or
    dangerous commands); other tools (``fs.write``, ``git.commit``, ...) are
    queued directly for the runner.
    """
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    ws = store.workspace_dict(ws)

    if body.tool not in tools_domain.TOOL_SPECS:
        raise HTTPException(status_code=400, detail="unsupported tool")

    if body.tool == "command.run" or (body.command and body.tool == "command.run"):
        cmd = body.command or str(body.params.get("cmd", ""))
        req = await tools_service.dispatch_command(
            runtime.db, workspace_id=workspace_id, command=cmd,
            allowed_commands=ws.get("allowed_commands") or [])
        return {"tool_request": store.tool_request_public_dict(req)}

    needs_approval = body.tool in _APPROVAL_REQUIRED_TOOLS or tools_domain.TOOL_SPECS[body.tool]["mutates"]
    request_id = await store.create_tool_request(
        runtime.db, workspace_id=workspace_id, tool=body.tool,
        params={**body.params, **({"cmd": body.command} if body.command else {})},
        dangerous=needs_approval,
        status="awaiting_approval" if needs_approval else "queued")
    return {"tool_request": store.tool_request_public_dict(await store.get_tool_request(runtime.db, request_id))}


@router.get("/{workspace_id}/tool-requests/next")
async def next_tool_request(workspace_id: str, request: Request,
                            runtime: Runtime = Depends(get_runtime)) -> dict | None:
    """Long-poll: claim the next queued operation for a runner."""
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    try:
        _check_local_token(request, ws)
        if ws.get("provider") != "local":
            require_runner_token(request, runtime)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if ws["status"] == "stopped":
        raise HTTPException(status_code=409, detail="workspace is stopped")

    runner_id = request.headers.get("x-runner-id")
    if runner_id and ws.get("runner_id") and ws["runner_id"] != runner_id:
        raise HTTPException(status_code=409, detail="workspace is claimed by another runner")
    if runner_id and not ws.get("runner_id"):
        await store.update_workspace(runtime.db, workspace_id, runner_id=runner_id)

    deadline = asyncio.get_event_loop().time() + _LONG_POLL_SECONDS
    while True:
        claimed = await store.next_queued_tool_request(runtime.db, workspace_id, runner_id)
        if claimed:
            params = claimed.get("params") or {}
            secret_keys = params.get("secret_keys") or []
            if secret_keys:
                secrets = await store.get_secrets(
                    runtime.db, workspace_id, secret_keys,
                    runtime.get("SECRET_ENCRYPTION_KEY"))
                params = {key: value for key, value in params.items() if key != "secret_keys"}
                if "GIT_PUSH_TOKEN" in secrets:
                    params["token"] = secrets["GIT_PUSH_TOKEN"]
                if "GITHUB_TOKEN" in secrets:
                    params["token"] = secrets["GITHUB_TOKEN"]
                claimed["params"] = params
            return {"tool_request": claimed}
        if asyncio.get_event_loop().time() >= deadline:
            return {"tool_request": None}
        await asyncio.sleep(1.0)


@router.post("/{workspace_id}/tool-requests/{request_id}/result")
async def submit_tool_result(workspace_id: str, request_id: str, body: ToolResultRequest,
                             request: Request, runtime: Runtime = Depends(get_runtime)) -> dict:
    ws = await store.get_workspace(runtime.db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    try:
        _check_local_token(request, ws)
        if ws.get("provider") != "local":
            require_runner_token(request, runtime)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    req = await store.get_tool_request(runtime.db, request_id)
    if req is None or req["workspace_id"] != workspace_id:
        raise HTTPException(status_code=404, detail="tool request not found in this workspace")

    secret_values = await store.get_secrets(
        runtime.db, workspace_id, encryption_key=runtime.get("SECRET_ENCRYPTION_KEY"))
    updated = await tools_service.submit_tool_result(
        runtime.db, request_id=request_id, status=body.status, result=body.result,
        redact_values=list(secret_values.values()))
    if updated is None:
        raise HTTPException(status_code=404, detail="tool request not found")
    return {"tool_request": store.tool_request_public_dict(await store.get_tool_request(runtime.db, request_id))}


@router.post("/{workspace_id}/tool-requests/{request_id}/approve")
async def approve_tool_request(workspace_id: str, request_id: str, body: ToolApproveRequest,
                               runtime: Runtime = Depends(get_runtime)) -> dict:
    req = await store.get_tool_request(runtime.db, request_id)
    if req is None or req["workspace_id"] != workspace_id:
        raise HTTPException(status_code=404, detail="tool request not found")
    if req["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="tool request is not awaiting approval")
    new_status = "queued" if body.approved else "cancelled"
    await store.update_tool_request(runtime.db, request_id, status=new_status,
                                    finished_at=None if body.approved else now_iso())
    return {"tool_request_id": request_id, "status": new_status}
