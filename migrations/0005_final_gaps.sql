-- Zyntry Code - final gap closure: secrets, rate limits, runner tokens, budgets
-- Idempotent. Applied after 0004_tool_requests_attempt.sql.

ALTER TABLE workspaces ADD COLUMN runner_token TEXT;

CREATE TABLE IF NOT EXISTS secrets (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    key          TEXT NOT NULL,
    value        TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_secrets_workspace ON secrets(workspace_id);

CREATE TABLE IF NOT EXISTS rate_limits (
    client_key  TEXT PRIMARY KEY,
    window_start REAL NOT NULL,
    count       INTEGER NOT NULL DEFAULT 0
);