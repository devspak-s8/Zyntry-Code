-- Zyntry Code - semantic repo search index
-- Idempotent. Applied after 0006_mcp_servers.sql.

CREATE TABLE IF NOT EXISTS semantic_chunks (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    path         TEXT NOT NULL,
    start_line   INTEGER NOT NULL DEFAULT 0,
    end_line     INTEGER NOT NULL DEFAULT 0,
    language     TEXT,
    content      TEXT NOT NULL,
    embedding    TEXT NOT NULL,          -- JSON vector
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_semantic_workspace ON semantic_chunks(workspace_id);