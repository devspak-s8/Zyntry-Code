-- Zyntry Code - retry/rollback support: repo rule packs + CI status
-- Idempotent. Applied after 0007_semantic_index.sql.

-- Per-repo verification rule packs. kind: regex | command | constitution.
-- spec: regex pattern / command string / constitution rule text.
CREATE TABLE IF NOT EXISTS repo_rules (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL,
    spec         TEXT NOT NULL,
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_repo_rules_workspace ON repo_rules(workspace_id);

-- CI status reported by a webhook after delivery push.
CREATE TABLE IF NOT EXISTS ci_statuses (
    task_id    TEXT PRIMARY KEY,
    status     TEXT NOT NULL,
    url        TEXT,
    detail     TEXT,
    updated_at TEXT NOT NULL
);