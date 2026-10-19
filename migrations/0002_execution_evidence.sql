-- Zyntry Code - execution evidence, repo ingestion, and learning (gap closure)
-- Idempotent. Applied after 0001_init.sql.

ALTER TABLE plans ADD COLUMN source TEXT NOT NULL DEFAULT 'template';

CREATE TABLE IF NOT EXISTS repo_files (
    id         TEXT PRIMARY KEY,
    task_id    TEXT NOT NULL REFERENCES tasks(id),
    path       TEXT NOT NULL,
    language   TEXT,
    size       INTEGER NOT NULL DEFAULT 0,
    content    TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_repo_files_task ON repo_files(task_id);

CREATE TABLE IF NOT EXISTS artifacts (
    id           TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL REFERENCES executions(id),
    stage_id     TEXT,
    path         TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'file',   -- file | patch | result
    language     TEXT,
    source       TEXT NOT NULL DEFAULT 'auto',   -- auto | extension
    content      TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_execution ON artifacts(execution_id);

CREATE TABLE IF NOT EXISTS verification_reports (
    id           TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL REFERENCES executions(id),
    stage_id     TEXT NOT NULL,
    attempt_id   TEXT,
    tool         TEXT NOT NULL,                  -- tests | lint | type_check | build | visual | security | benchmark | contract | migration
    status       TEXT NOT NULL,                  -- passed | failed
    output       TEXT,
    duration_ms  INTEGER,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vreports_execution ON verification_reports(execution_id);
CREATE INDEX IF NOT EXISTS idx_vreports_stage ON verification_reports(stage_id);

CREATE TABLE IF NOT EXISTS routing_stats (
    id              TEXT PRIMARY KEY,
    stage_kind      TEXT NOT NULL,
    risk_level      TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    provider        TEXT NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    successes       INTEGER NOT NULL DEFAULT 0,
    failures        INTEGER NOT NULL DEFAULT 0,
    escalations     INTEGER NOT NULL DEFAULT 0,
    avg_latency_ms  REAL NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_routing_stats_key ON routing_stats(stage_kind, risk_level, model_id);