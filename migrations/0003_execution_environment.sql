-- Zyntry Code - coding execution environment (workspaces, tool requests, changes, workers)
-- Idempotent. Applied after 0002_execution_evidence.sql.

CREATE TABLE IF NOT EXISTS workspaces (
    id                TEXT PRIMARY KEY,
    task_id           TEXT,
    repo_url          TEXT,
    branch            TEXT,
    base_commit       TEXT,
    head_commit       TEXT,
    workdir           TEXT,
    provider          TEXT NOT NULL DEFAULT 'remote',   -- local (extension) | remote (worker)
    status            TEXT NOT NULL DEFAULT 'provisioning',  -- provisioning | ready | running | stopped | failed | cleaned
    commands          TEXT NOT NULL DEFAULT '{}',       -- {test: {cmd, dangerous}, lint: {...}, ...}
    env               TEXT NOT NULL DEFAULT '{}',       -- command env vars (values never logged)
    allowed_commands  TEXT NOT NULL DEFAULT '[]',
    auto_commit       INTEGER NOT NULL DEFAULT 0,
    timeout_seconds   INTEGER NOT NULL DEFAULT 600,
    runner_id         TEXT,                             -- worker id or extension id
    error             TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workspaces_task ON workspaces(task_id);

CREATE TABLE IF NOT EXISTS tool_requests (
    id            TEXT PRIMARY KEY,
    execution_id  TEXT,
    stage_id      TEXT,
    workspace_id  TEXT NOT NULL REFERENCES workspaces(id),
    tool          TEXT NOT NULL,          -- fs.list|fs.read|fs.write|fs.edit|fs.delete|fs.search|git.diff|git.status|git.commit|command.run|command.start|command.stop
    params        TEXT NOT NULL DEFAULT '{}',
    verify_as     TEXT,                   -- tests|lint|build|type_check|visual|security|benchmark (for command.run)
    dangerous     INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'queued',   -- queued|awaiting_approval|dispatched|running|succeeded|failed|timed_out|cancelled
    result        TEXT,                   -- JSON {stdout, stderr, exit_code, duration_ms, error, files:[...]}
    created_at    TEXT NOT NULL,
    dispatched_at TEXT,
    finished_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_toolreq_workspace ON tool_requests(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_toolreq_execution ON tool_requests(execution_id);
CREATE INDEX IF NOT EXISTS idx_toolreq_stage ON tool_requests(stage_id);

CREATE TABLE IF NOT EXISTS changes (
    id           TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    stage_id     TEXT,
    workspace_id TEXT,
    path         TEXT NOT NULL,
    op           TEXT NOT NULL,           -- create|modify|delete
    before       TEXT,
    after        TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_changes_execution ON changes(execution_id);

CREATE TABLE IF NOT EXISTS workers (
    id            TEXT PRIMARY KEY,
    name          TEXT,
    status        TEXT NOT NULL DEFAULT 'online',   -- online|offline|draining
    capabilities  TEXT NOT NULL DEFAULT '[]',
    last_heartbeat TEXT,
    created_at    TEXT NOT NULL
);