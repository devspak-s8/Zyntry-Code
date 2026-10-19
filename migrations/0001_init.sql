-- Zyntry Code — initial schema (D1 / SQLite)
-- Applied automatically by pywrangler D1 migrations, or manually:
--   uv run pywrangler d1 execute zyntry-code --local --file migrations/0001_init.sql

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    prompt      TEXT NOT NULL,
    repo        TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    risk_level  TEXT,
    complexity  TEXT,
    task_kind   TEXT,
    constraints TEXT,          -- JSON object
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL REFERENCES tasks(id),
    summary     TEXT,
    status      TEXT NOT NULL DEFAULT 'planned',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stages (
    id                 TEXT PRIMARY KEY,
    plan_id            TEXT NOT NULL REFERENCES plans(id),
    kind               TEXT NOT NULL,
    title              TEXT NOT NULL,
    description        TEXT,
    dependencies       TEXT NOT NULL DEFAULT '[]',  -- JSON array of stage ids
    assigned_model     TEXT,
    model_reasoning    TEXT,
    risk_level         TEXT,
    status             TEXT NOT NULL DEFAULT 'pending',
    position           INTEGER NOT NULL DEFAULT 0,
    verification_types TEXT NOT NULL DEFAULT '[]',  -- JSON array
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS executions (
    id               TEXT PRIMARY KEY,
    task_id          TEXT NOT NULL REFERENCES tasks(id),
    plan_id          TEXT,
    status           TEXT NOT NULL DEFAULT 'running',
    attempt_count    INTEGER NOT NULL DEFAULT 0,
    escalation_count INTEGER NOT NULL DEFAULT 0,
    total_cost       REAL NOT NULL DEFAULT 0,
    total_tokens     INTEGER NOT NULL DEFAULT 0,
    started_at       TEXT,
    finished_at      TEXT,
    summary          TEXT            -- JSON execution summary
);

CREATE TABLE IF NOT EXISTS attempts (
    id                 TEXT PRIMARY KEY,
    execution_id       TEXT NOT NULL REFERENCES executions(id),
    stage_id           TEXT NOT NULL REFERENCES stages(id),
    attempt_number     INTEGER NOT NULL,
    model_id           TEXT NOT NULL,
    provider           TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'running',
    input_prompt       TEXT,
    output             TEXT,
    verification_status TEXT,
    verification_output TEXT,        -- JSON
    tokens_in          INTEGER NOT NULL DEFAULT 0,
    tokens_out         INTEGER NOT NULL DEFAULT 0,
    cost               REAL NOT NULL DEFAULT 0,
    latency_ms         INTEGER,
    error              TEXT,
    created_at         TEXT NOT NULL,
    finished_at        TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id           TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL REFERENCES executions(id),
    task_id      TEXT,
    stage_id     TEXT,
    type         TEXT NOT NULL,
    message      TEXT,
    data         TEXT,              -- JSON
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plans_task         ON plans(task_id);
CREATE INDEX IF NOT EXISTS idx_stages_plan        ON stages(plan_id);
CREATE INDEX IF NOT EXISTS idx_executions_task    ON executions(task_id);
CREATE INDEX IF NOT EXISTS idx_attempts_execution ON attempts(execution_id);
CREATE INDEX IF NOT EXISTS idx_events_execution   ON events(execution_id);