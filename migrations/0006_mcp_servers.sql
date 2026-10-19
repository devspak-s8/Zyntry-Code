-- Zyntry Code - MCP server configuration per workspace
-- Idempotent. Applied after 0005_final_gaps.sql.

ALTER TABLE workspaces ADD COLUMN mcp_servers TEXT NOT NULL DEFAULT '[]';