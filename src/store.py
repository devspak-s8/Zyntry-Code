"""Data repository layer (raw SQL over the Database abstraction)."""

from typing import Any

from db import Database
from secret_crypto import decrypt, encrypt
from security import is_sensitive_path
from util import json_dumps, json_loads, now_iso, uuid_str

_TASK_COLS = ("id", "prompt", "repo", "status", "risk_level", "complexity", "task_kind", "constraints", "created_at", "updated_at")
_PLAN_COLS = ("id", "task_id", "summary", "status", "source", "created_at")
_STAGE_COLS = ("id", "plan_id", "kind", "title", "description", "dependencies", "assigned_model", "model_reasoning", "risk_level", "status", "position", "verification_types", "created_at")
_EXEC_COLS = ("id", "task_id", "plan_id", "status", "attempt_count", "escalation_count", "total_cost", "total_tokens", "started_at", "finished_at", "summary")
_ATTEMPT_COLS = ("id", "execution_id", "stage_id", "attempt_number", "model_id", "provider", "status", "input_prompt", "output", "verification_status", "verification_output", "tokens_in", "tokens_out", "cost", "latency_ms", "error", "created_at", "finished_at")
_EVENT_COLS = ("id", "execution_id", "task_id", "stage_id", "type", "message", "data", "created_at")
_TASK_UPDATE_FIELDS = {"prompt", "repo", "status", "risk_level", "complexity", "task_kind", "constraints"}


# ---- tasks -----------------------------------------------------------------

async def create_task(db: Database, *, prompt: str, repo: str | None, status: str,
                      risk_level: str | None, complexity: str | None, task_kind: str | None,
                      constraints: dict | None) -> str:
    task_id = uuid_str()
    ts = now_iso()
    await db.execute(
        "INSERT INTO tasks (id, prompt, repo, status, risk_level, complexity, task_kind, constraints, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, prompt, repo, status, risk_level, complexity, task_kind, json_dumps(constraints or {}), ts, ts),
    )
    return task_id


async def get_task(db: Database, task_id: str) -> dict | None:
    return await db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,), _TASK_COLS)


async def list_tasks(db: Database, limit: int = 50) -> list[dict]:
    return await db.query("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,), _TASK_COLS)


async def update_task(db: Database, task_id: str, **fields: Any) -> None:
    if not fields:
        return
    unknown = set(fields) - _TASK_UPDATE_FIELDS
    if unknown:
        raise ValueError(f"unsupported task fields: {sorted(unknown)}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values())
    await db.execute(f"UPDATE tasks SET {sets}, updated_at = ? WHERE id = ?", (*values, now_iso(), task_id))


# ---- plans -----------------------------------------------------------------

async def create_plan(db: Database, task_id: str, summary: str, source: str = "llm") -> str:
    plan_id = uuid_str()
    await db.execute(
        "INSERT INTO plans (id, task_id, summary, status, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (plan_id, task_id, summary, "planned", source, now_iso()),
    )
    return plan_id


async def get_plan_for_task(db: Database, task_id: str) -> dict | None:
    return await db.query_one("SELECT * FROM plans WHERE task_id = ? ORDER BY created_at DESC LIMIT 1", (task_id,), _PLAN_COLS)


async def create_stage(db: Database, plan_id: str, *, stage_id: str, kind: str, title: str,
                       description: str, dependencies: list[str], verification_types: list[str],
                       risk_level: str | None, position: int) -> None:
    await db.execute(
        "INSERT INTO stages (id, plan_id, kind, title, description, dependencies, assigned_model, model_reasoning, risk_level, status, position, verification_types, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, 'pending', ?, ?, ?)",
        (stage_id, plan_id, kind, title, description, json_dumps(dependencies), risk_level, position, json_dumps(verification_types), now_iso()),
    )


async def get_stages(db: Database, plan_id: str) -> list[dict]:
    return await db.query("SELECT * FROM stages WHERE plan_id = ? ORDER BY position ASC", (plan_id,), _STAGE_COLS)


async def get_stage(db: Database, stage_id: str) -> dict | None:
    return await db.query_one("SELECT * FROM stages WHERE id = ?", (stage_id,), _STAGE_COLS)


async def update_stage(db: Database, stage_id: str, **fields: Any) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(f"UPDATE stages SET {sets} WHERE id = ?", (*fields.values(), stage_id))


# ---- executions ------------------------------------------------------------

async def create_execution(db: Database, task_id: str, plan_id: str | None) -> str:
    execution_id = uuid_str()
    await db.execute(
        "INSERT INTO executions (id, task_id, plan_id, status, attempt_count, escalation_count, total_cost, total_tokens, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, 'running', 0, 0, 0, 0, ?, NULL, NULL)",
        (execution_id, task_id, plan_id, now_iso()),
    )
    return execution_id


async def get_execution(db: Database, execution_id: str) -> dict | None:
    return await db.query_one("SELECT * FROM executions WHERE id = ?", (execution_id,), _EXEC_COLS)


async def get_latest_execution(db: Database, task_id: str) -> dict | None:
    return await db.query_one("SELECT * FROM executions WHERE task_id = ? ORDER BY started_at DESC LIMIT 1", (task_id,), _EXEC_COLS)


async def update_execution(db: Database, execution_id: str, **fields: Any) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(f"UPDATE executions SET {sets} WHERE id = ?", (*fields.values(), execution_id))


# ---- attempts --------------------------------------------------------------

async def create_attempt(db: Database, *, execution_id: str, stage_id: str, attempt_number: int,
                         model_id: str, provider: str, input_prompt: str) -> str:
    attempt_id = uuid_str()
    await db.execute(
        "INSERT INTO attempts (id, execution_id, stage_id, attempt_number, model_id, provider, status, input_prompt, output, verification_status, verification_output, tokens_in, tokens_out, cost, latency_ms, error, created_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'running', ?, NULL, NULL, NULL, 0, 0, 0, NULL, NULL, ?, NULL)",
        (attempt_id, execution_id, stage_id, attempt_number, model_id, provider, input_prompt, now_iso()),
    )
    return attempt_id


async def update_attempt(db: Database, attempt_id: str, **fields: Any) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(f"UPDATE attempts SET {sets} WHERE id = ?", (*fields.values(), attempt_id))


async def get_attempts(db: Database, execution_id: str) -> list[dict]:
    return await db.query("SELECT * FROM attempts WHERE execution_id = ? ORDER BY created_at ASC", (execution_id,), _ATTEMPT_COLS)


# ---- events ----------------------------------------------------------------

async def add_event(db: Database, execution_id: str, task_id: str | None, stage_id: str | None,
                    type_: str, message: str, data: dict | None = None) -> None:
    await db.execute(
        "INSERT INTO events (id, execution_id, task_id, stage_id, type, message, data, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (uuid_str(), execution_id, task_id, stage_id, type_, message, json_dumps(data or {}), now_iso()),
    )


async def get_events(db: Database, execution_id: str, limit: int = 500) -> list[dict]:
    return await db.query("SELECT * FROM events WHERE execution_id = ? ORDER BY created_at ASC LIMIT ?", (execution_id, limit), _EVENT_COLS)


async def get_events_for_task(db: Database, task_id: str, limit: int = 500) -> list[dict]:
    return await db.query("SELECT * FROM events WHERE task_id = ? ORDER BY created_at ASC LIMIT ?", (task_id, limit), _EVENT_COLS)


# ---- repo ingestion ---------------------------------------------------------

_REPO_FILE_COLS = ("id", "task_id", "path", "language", "size", "content", "created_at")


async def replace_repo_files(db: Database, task_id: str, files: list[dict]) -> int:
    """Replace the repo file snapshot for a task. Each file dict: path, language, size, content."""
    await db.execute("DELETE FROM repo_files WHERE task_id = ?", (task_id,))
    ts = now_iso()
    safe_files = [f for f in files if not is_sensitive_path(str(f.get("path", "")))]
    for f in safe_files:
        await db.execute(
            "INSERT INTO repo_files (id, task_id, path, language, size, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid_str(), task_id, f.get("path", ""), f.get("language"), int(f.get("size", 0)), f.get("content"), ts),
        )
    return len(safe_files)


async def get_repo_files(db: Database, task_id: str) -> list[dict]:
    rows = await db.query("SELECT * FROM repo_files WHERE task_id = ? ORDER BY path ASC", (task_id,), _REPO_FILE_COLS)
    return [row for row in rows if not is_sensitive_path(str(row.get("path", "")))]


# ---- artifacts --------------------------------------------------------------

_ARTIFACT_COLS = ("id", "execution_id", "stage_id", "path", "kind", "language", "source", "content", "created_at")


async def create_artifact(db: Database, *, execution_id: str, stage_id: str | None, path: str,
                          kind: str = "file", language: str | None = None,
                          source: str = "auto", content: str | None = None) -> str:
    artifact_id = uuid_str()
    await db.execute(
        "INSERT INTO artifacts (id, execution_id, stage_id, path, kind, language, source, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (artifact_id, execution_id, stage_id, path, kind, language, source, content, now_iso()),
    )
    return artifact_id


async def get_artifacts(db: Database, execution_id: str) -> list[dict]:
    return await db.query("SELECT * FROM artifacts WHERE execution_id = ? ORDER BY created_at ASC", (execution_id,), _ARTIFACT_COLS)


# ---- verification reports ---------------------------------------------------

_VREPORT_COLS = ("id", "execution_id", "stage_id", "attempt_id", "tool", "status", "output", "duration_ms", "created_at")


async def create_verification_report(db: Database, *, execution_id: str, stage_id: str,
                                     attempt_id: str | None, tool: str, status: str,
                                     output: str | None = None, duration_ms: int | None = None) -> str:
    report_id = uuid_str()
    await db.execute(
        "INSERT INTO verification_reports (id, execution_id, stage_id, attempt_id, tool, status, output, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (report_id, execution_id, stage_id, attempt_id, tool, status, output, duration_ms, now_iso()),
    )
    return report_id


async def get_verification_reports(db: Database, stage_id: str,
                                   attempt_id: str | None = None) -> list[dict]:
    """Reports for a stage. When ``attempt_id`` is given, include attempt-agnostic
    reports (extension-posted without an attempt) plus that attempt's own."""
    if attempt_id:
        return await db.query(
            "SELECT * FROM verification_reports WHERE stage_id = ? AND (attempt_id IS NULL OR attempt_id = ?) ORDER BY created_at ASC",
            (stage_id, attempt_id), _VREPORT_COLS)
    return await db.query("SELECT * FROM verification_reports WHERE stage_id = ? ORDER BY created_at ASC", (stage_id,), _VREPORT_COLS)


# ---- routing stats (evidence-driven routing) --------------------------------

_ROUTING_STATS_COLS = ("id", "stage_kind", "risk_level", "model_id", "provider", "attempts", "successes", "failures", "escalations", "avg_latency_ms", "updated_at")


async def upsert_routing_stats(db: Database, *, stage_kind: str, risk_level: str, model_id: str,
                               provider: str, success: bool, latency_ms: int | None = None,
                               escalated: bool = False) -> None:
    """Atomic upsert (SQLite ``ON CONFLICT``) — safe under parallel stage execution."""
    latency = float(latency_ms) if latency_ms is not None else None
    await db.execute(
        """
        INSERT INTO routing_stats
            (id, stage_kind, risk_level, model_id, provider, attempts, successes, failures, escalations, avg_latency_ms, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
        ON CONFLICT(stage_kind, risk_level, model_id) DO UPDATE SET
            attempts = attempts + 1,
            successes = successes + excluded.successes,
            failures = failures + excluded.failures,
            escalations = escalations + excluded.escalations,
            avg_latency_ms = CASE
                WHEN excluded.avg_latency_ms IS NULL THEN avg_latency_ms
                ELSE (avg_latency_ms * attempts + excluded.avg_latency_ms) / (attempts + 1)
            END,
            provider = excluded.provider,
            updated_at = excluded.updated_at
        """,
        (uuid_str(), stage_kind, risk_level, model_id, provider,
         1 if success else 0, 0 if success else 1, 1 if escalated else 0, latency, now_iso()),
    )


async def get_routing_stats(db: Database, stage_kind: str, risk_level: str) -> dict[str, dict]:
    rows = await db.query(
        "SELECT * FROM routing_stats WHERE stage_kind = ? AND risk_level = ?",
        (stage_kind, risk_level), _ROUTING_STATS_COLS)
    return {r["model_id"]: r for r in rows}


async def get_global_routing_stats(db: Database) -> dict[str, dict]:
    """Per-model record across every stage kind — the prior that task-specific
    reliability estimates are shrunk toward when evidence is sparse."""
    rows = await db.query(
        """
        SELECT model_id,
               SUM(attempts)  AS attempts,
               SUM(successes) AS successes,
               SUM(failures)  AS failures,
               SUM(escalations) AS escalations
        FROM routing_stats
        GROUP BY model_id
        """,
        (), ("model_id", "attempts", "successes", "failures", "escalations"))
    return {r["model_id"]: r for r in rows}


# ---- workspaces -------------------------------------------------------------

_WORKSPACE_COLS = ("id", "task_id", "repo_url", "branch", "base_commit", "head_commit", "workdir",
                   "provider", "status", "commands", "env", "allowed_commands", "auto_commit",
                   "timeout_seconds", "runner_id", "runner_token", "error", "created_at", "updated_at",
                   "mcp_servers")


async def create_workspace(db: Database, *, workspace_id: str, task_id: str | None, repo_url: str | None,
                           branch: str | None, provider: str, commands: dict, env: dict,
                           allowed_commands: list[str], auto_commit: bool,
                           timeout_seconds: int, runner_token: str | None = None) -> None:
    await db.execute(
        "INSERT INTO workspaces (id, task_id, repo_url, branch, base_commit, head_commit, workdir, provider, status, commands, env, allowed_commands, auto_commit, timeout_seconds, runner_id, runner_token, error, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?, 'provisioning', ?, ?, ?, ?, ?, NULL, ?, NULL, ?, ?)",
        (workspace_id, task_id, repo_url, branch, provider, json_dumps(commands), json_dumps(env),
         json_dumps(allowed_commands), 1 if auto_commit else 0, timeout_seconds, runner_token,
         now_iso(), now_iso()),
    )


async def get_workspace(db: Database, workspace_id: str) -> dict | None:
    return await db.query_one("SELECT * FROM workspaces WHERE id = ?", (workspace_id,), _WORKSPACE_COLS)


async def get_workspace_for_task(db: Database, task_id: str) -> dict | None:
    return await db.query_one(
        "SELECT * FROM workspaces WHERE task_id = ? ORDER BY created_at DESC LIMIT 1", (task_id,), _WORKSPACE_COLS)


async def pending_workspaces(db: Database, provider: str, limit: int = 10) -> list[dict]:
    """Workspaces that have queued tool requests waiting for a runner."""
    return await db.query(
        "SELECT DISTINCT w.* FROM workspaces w JOIN tool_requests t ON t.workspace_id = w.id "
        "WHERE t.status = 'queued' AND w.provider = ? AND w.status != 'stopped' "
        "ORDER BY w.created_at ASC LIMIT ?",
        (provider, limit), _WORKSPACE_COLS)


async def list_all_workspaces(db: Database, limit: int = 50) -> list[dict]:
    """Every workspace (for the frontend runner panel)."""
    return await db.query(
        "SELECT * FROM workspaces ORDER BY created_at DESC LIMIT ?", (limit,), _WORKSPACE_COLS)


async def update_workspace(db: Database, workspace_id: str, **fields: Any) -> None:
    if not fields:
        return
    allowed = {"task_id", "repo_url", "branch", "base_commit", "head_commit", "workdir",
               "status", "commands", "env", "allowed_commands", "auto_commit",
               "timeout_seconds", "runner_id", "runner_token", "error", "mcp_servers"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unsupported workspace fields: {sorted(unknown)}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(f"UPDATE workspaces SET {sets}, updated_at = ? WHERE id = ?",
                     (*fields.values(), now_iso(), workspace_id))


def workspace_dict(row: dict) -> dict:
    d = dict(row)
    d["commands"] = json_loads(d.get("commands"), {})
    d["env"] = json_loads(d.get("env"), {})
    d["allowed_commands"] = json_loads(d.get("allowed_commands"), [])
    d["mcp_servers"] = json_loads(d.get("mcp_servers"), [])
    return d


def workspace_public_dict(row: dict) -> dict:
    """Return workspace metadata without runner credentials or environment values."""
    d = workspace_dict(row)
    d.pop("runner_token", None)
    d.pop("env", None)
    d["mcp_servers"] = [
        {key: value for key, value in server.items() if key != "env"}
        for server in (d.get("mcp_servers") or [])
    ]
    return d


def workspace_runner_dict(row: dict) -> dict:
    """Full workspace configuration, only for an authenticated runner."""
    return workspace_dict(row)


# ---- tool requests ----------------------------------------------------------

_TOOLREQ_COLS = ("id", "execution_id", "stage_id", "workspace_id", "tool", "params", "verify_as",
                 "dangerous", "status", "result", "created_at", "dispatched_at", "finished_at",
                 "attempt_id")


async def create_tool_request(db: Database, *, workspace_id: str, tool: str, params: dict,
                              execution_id: str | None = None, stage_id: str | None = None,
                              verify_as: str | None = None, dangerous: bool = False,
                              status: str = "queued", attempt_id: str | None = None) -> str:
    request_id = uuid_str()
    await db.execute(
        "INSERT INTO tool_requests (id, execution_id, stage_id, workspace_id, tool, params, verify_as, dangerous, status, result, created_at, dispatched_at, finished_at, attempt_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL, ?)",
        (request_id, execution_id, stage_id, workspace_id, tool, json_dumps(params), verify_as,
         1 if dangerous else 0, status, now_iso(), attempt_id),
    )
    return request_id


async def get_tool_request(db: Database, request_id: str) -> dict | None:
    return await db.query_one("SELECT * FROM tool_requests WHERE id = ?", (request_id,), _TOOLREQ_COLS)


async def list_tool_requests(db: Database, workspace_id: str, status: str | None = None) -> list[dict]:
    if status:
        return await db.query("SELECT * FROM tool_requests WHERE workspace_id = ? AND status = ? ORDER BY created_at ASC",
                              (workspace_id, status), _TOOLREQ_COLS)
    return await db.query("SELECT * FROM tool_requests WHERE workspace_id = ? ORDER BY created_at ASC",
                          (workspace_id,), _TOOLREQ_COLS)


async def next_queued_tool_request(db: Database, workspace_id: str, runner_id: str | None = None) -> dict | None:
    """Atomically claim the oldest queued request (conditional UPDATE)."""
    rows = await db.query(
        "SELECT * FROM tool_requests WHERE workspace_id = ? AND status = 'queued' ORDER BY created_at ASC LIMIT 1",
        (workspace_id,), _TOOLREQ_COLS)
    if not rows:
        return None
    row = rows[0]
    changed = await db.execute_changes(
        "UPDATE tool_requests SET status = 'dispatched', dispatched_at = ? WHERE id = ? AND status = 'queued'",
        (now_iso(), row["id"]))
    if changed == 0:
        return None  # claimed by another runner between select and update
    return tool_request_dict(await get_tool_request(db, row["id"]))


async def update_tool_request(db: Database, request_id: str, **fields: Any) -> None:
    if not fields:
        return
    allowed = {"execution_id", "stage_id", "tool", "params", "verify_as", "dangerous",
               "status", "result", "dispatched_at", "finished_at", "attempt_id"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unsupported tool request fields: {sorted(unknown)}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(f"UPDATE tool_requests SET {sets} WHERE id = ?", (*fields.values(), request_id))


def tool_request_dict(row: dict) -> dict:
    d = dict(row)
    d["params"] = json_loads(d.get("params"), {})
    d["result"] = json_loads(d.get("result"), None)
    return d


_SENSITIVE_PARAM_KEYS = {"token", "password", "secret", "api_key", "apikey",
                         "authorization", "env", "private_key"}


def _redact_sensitive(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in _SENSITIVE_PARAM_KEYS else _redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def tool_request_public_dict(row: dict) -> dict:
    d = tool_request_dict(row)
    d["params"] = _redact_sensitive(d.get("params") or {})
    d["result"] = _redact_sensitive(d.get("result"))
    return d


async def pending_tool_requests(db: Database, execution_id: str) -> list[dict]:
    return await db.query(
        "SELECT * FROM tool_requests WHERE execution_id = ? AND status IN ('queued','awaiting_approval','dispatched','running') ORDER BY created_at ASC",
        (execution_id,), _TOOLREQ_COLS)


# ---- changes ----------------------------------------------------------------

_CHANGE_COLS = ("id", "execution_id", "stage_id", "workspace_id", "path", "op", "before", "after", "created_at")


async def record_change(db: Database, *, execution_id: str, path: str, op: str,
                        stage_id: str | None = None, workspace_id: str | None = None,
                        before: str | None = None, after: str | None = None) -> str:
    change_id = uuid_str()
    await db.execute(
        "INSERT INTO changes (id, execution_id, stage_id, workspace_id, path, op, before, after, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (change_id, execution_id, stage_id, workspace_id, path, op, before, after, now_iso()),
    )
    return change_id


async def get_changes(db: Database, execution_id: str) -> list[dict]:
    return await db.query("SELECT * FROM changes WHERE execution_id = ? ORDER BY created_at ASC",
                          (execution_id,), _CHANGE_COLS)


# ---- workers ----------------------------------------------------------------

_WORKER_COLS = ("id", "name", "status", "capabilities", "last_heartbeat", "created_at")


async def register_worker(db: Database, worker_id: str, name: str | None, capabilities: list[str]) -> None:
    existing = await db.query_one("SELECT id FROM workers WHERE id = ?", (worker_id,), ("id",))
    if existing:
        await db.execute("UPDATE workers SET status = 'online', last_heartbeat = ? WHERE id = ?",
                         (now_iso(), worker_id))
    else:
        await db.execute(
            "INSERT INTO workers (id, name, status, capabilities, last_heartbeat, created_at) VALUES (?, ?, 'online', ?, ?, ?)",
            (worker_id, name or worker_id, json_dumps(capabilities), now_iso(), now_iso()),
        )


async def worker_heartbeat(db: Database, worker_id: str) -> None:
    await db.execute("UPDATE workers SET status = 'online', last_heartbeat = ? WHERE id = ?",
                     (now_iso(), worker_id))


async def list_workers(db: Database) -> list[dict]:
    return await db.query("SELECT * FROM workers ORDER BY last_heartbeat DESC", (), _WORKER_COLS)


# ---- secrets (workspace-scoped credentials) ---------------------------------

async def set_secret(db: Database, workspace_id: str, key: str, value: str,
                     encryption_key: str | None) -> None:
    encrypted = encrypt(value, encryption_key)
    existing = await db.query_one("SELECT id FROM secrets WHERE workspace_id = ? AND key = ?",
                                  (workspace_id, key), ("id",))
    if existing:
        await db.execute("UPDATE secrets SET value = ? WHERE id = ?", (encrypted, existing["id"]))
    else:
        await db.execute(
            "INSERT INTO secrets (id, workspace_id, key, value, created_at) VALUES (?, ?, ?, ?, ?)",
            (uuid_str(), workspace_id, key, encrypted, now_iso()),
        )


async def get_secrets(db: Database, workspace_id: str, keys: list[str] | None = None,
                      encryption_key: str | None = None) -> dict[str, str]:
    """Decrypt credentials only for internal delivery to an authenticated runner."""
    if keys:
        placeholders = ",".join("?" for _ in keys)
        rows = await db.query(
            f"SELECT key, value FROM secrets WHERE workspace_id = ? AND key IN ({placeholders})",
            (workspace_id, *keys), ("key", "value"))
    else:
        rows = await db.query("SELECT key, value FROM secrets WHERE workspace_id = ?",
                              (workspace_id,), ("key", "value"))
    values: dict[str, str] = {}
    for row in rows:
        raw = str(row["value"] or "")
        if raw.startswith("f1:"):
            values[row["key"]] = decrypt(raw, encryption_key)
            continue
        # Migrate legacy plaintext rows at the first authenticated read. This
        # keeps existing deployments recoverable while ensuring plaintext is
        # not left in the database after the security upgrade.
        values[row["key"]] = raw
        encrypted = encrypt(raw, encryption_key)
        await db.execute("UPDATE secrets SET value = ? WHERE workspace_id = ? AND key = ?",
                         (encrypted, workspace_id, row["key"]))
    return values


# ---- rate limiting (cross-isolate via D1) -----------------------------------

async def rate_limit_allow(db: Database, client_key: str, limit: int,
                           window_s: float = 60.0) -> bool:
    """Sliding-window counter persisted in D1 (shared across isolates)."""
    import time as _time

    now = _time.time()
    changed = await db.execute_changes(
        "INSERT INTO rate_limits (client_key, window_start, count) VALUES (?, ?, 1) "
        "ON CONFLICT(client_key) DO UPDATE SET "
        "window_start = CASE WHEN rate_limits.window_start <= ? THEN excluded.window_start ELSE rate_limits.window_start END, "
        "count = CASE WHEN rate_limits.window_start <= ? THEN 1 ELSE rate_limits.count + 1 END "
        "WHERE rate_limits.window_start <= ? OR rate_limits.count < ?",
        (client_key, now, now - window_s, now - window_s, now - window_s, limit),
    )
    return bool(changed)


# ---- stage retry (reuse prior outputs) --------------------------------------

async def get_latest_succeeded_output(db: Database, stage_id: str) -> str | None:
    """Latest successful attempt output for a stage — the context a retry reuses."""
    row = await db.query_one(
        "SELECT output FROM attempts WHERE stage_id = ? AND status = 'succeeded' "
        "ORDER BY attempt_number DESC LIMIT 1",
        (stage_id,), ("output",))
    return row["output"] if row else None


async def get_stage_statuses(db: Database, plan_id: str) -> dict[str, str]:
    rows = await db.query("SELECT id, status FROM stages WHERE plan_id = ?",
                          (plan_id,), ("id", "status"))
    return {r["id"]: r["status"] for r in rows}


# ---- CI status (delivery webhook) -------------------------------------------

_CI_COLS = ("task_id", "status", "url", "detail", "updated_at")


async def set_ci_status(db: Database, task_id: str, status: str, url: str | None,
                        detail: str | None) -> None:
    existing = await db.query_one("SELECT task_id FROM ci_statuses WHERE task_id = ?",
                                  (task_id,), ("task_id",))
    if existing:
        await db.execute(
            "UPDATE ci_statuses SET status = ?, url = ?, detail = ?, updated_at = ? WHERE task_id = ?",
            (status, url, detail, now_iso(), task_id))
    else:
        await db.execute(
            "INSERT INTO ci_statuses (task_id, status, url, detail, updated_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, status, url, detail, now_iso()))


async def get_ci_status(db: Database, task_id: str) -> dict | None:
    return await db.query_one("SELECT * FROM ci_statuses WHERE task_id = ?",
                              (task_id,), _CI_COLS)


# ---- repo rule packs (per-repo custom verification) --------------------------

_RULE_COLS = ("id", "workspace_id", "name", "kind", "spec", "enabled", "created_at")


async def replace_repo_rules(db: Database, workspace_id: str, rules: list[dict]) -> None:
    await db.execute("DELETE FROM repo_rules WHERE workspace_id = ?", (workspace_id,))
    for r in rules:
        await db.execute(
            "INSERT INTO repo_rules (id, workspace_id, name, kind, spec, enabled, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid_str(), workspace_id, r["name"], r["kind"], r["spec"],
             1 if r.get("enabled", True) else 0, now_iso()))


async def get_repo_rules(db: Database, workspace_id: str) -> list[dict]:
    rows = await db.query(
        "SELECT * FROM repo_rules WHERE workspace_id = ? AND enabled = 1 ORDER BY created_at ASC",
        (workspace_id,), _RULE_COLS)
    return [dict(r) for r in rows]


# ---- semantic index ---------------------------------------------------------

_SEMANTIC_COLS = ("id", "workspace_id", "path", "start_line", "end_line", "language",
                  "content", "embedding", "created_at")


async def replace_semantic_chunks(db: Database, workspace_id: str, chunks: list[dict]) -> None:
    await db.execute("DELETE FROM semantic_chunks WHERE workspace_id = ?", (workspace_id,))
    for c in chunks:
        await db.execute(
            "INSERT INTO semantic_chunks (id, workspace_id, path, start_line, end_line, language, content, embedding, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uuid_str(), workspace_id, c["path"], c["start_line"], c["end_line"],
             c.get("language"), c["content"], c["embedding"], now_iso()),
        )


async def get_semantic_chunks(db: Database, workspace_id: str) -> list[dict]:
    return await db.query("SELECT * FROM semantic_chunks WHERE workspace_id = ? ORDER BY path, start_line",
                          (workspace_id,), _SEMANTIC_COLS)


async def semantic_chunk_count(db: Database, workspace_id: str) -> int:
    rows = await db.query("SELECT COUNT(*) AS n FROM semantic_chunks WHERE workspace_id = ?",
                          (workspace_id,), ("n",))
    return int(rows[0]["n"]) if rows else 0


# ---- serialization helpers -------------------------------------------------

def stage_dict(row: dict) -> dict:
    d = dict(row)
    d["dependencies"] = json_loads(d.get("dependencies"), [])
    d["verification_types"] = json_loads(d.get("verification_types"), [])
    return d


def task_dict(row: dict) -> dict:
    d = dict(row)
    d["constraints"] = json_loads(d.get("constraints"), {})
    return d


def attempt_dict(row: dict) -> dict:
    d = dict(row)
    d["verification_output"] = json_loads(d.get("verification_output"), None)
    return d


def event_dict(row: dict) -> dict:
    d = dict(row)
    d["data"] = json_loads(d.get("data"), {})
    return d
