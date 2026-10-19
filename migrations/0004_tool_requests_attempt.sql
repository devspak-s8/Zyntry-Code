-- Zyntry Code - attempt scoping for tool requests
-- Idempotent. Applied after 0003_execution_environment.sql.

ALTER TABLE tool_requests ADD COLUMN attempt_id TEXT;