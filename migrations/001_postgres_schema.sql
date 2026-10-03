-- Preserve the original prototype tables, then create the current AgentWatch schema.
-- Run once against the postgres database before deploying Lambda.
BEGIN;

ALTER TABLE IF EXISTS public.advisors RENAME TO legacy_advisors;
ALTER TABLE IF EXISTS public.agents RENAME TO legacy_agents;
ALTER TABLE IF EXISTS public.tasks RENAME TO legacy_tasks;
ALTER TABLE IF EXISTS public.events RENAME TO legacy_events;

CREATE TABLE advisors (
    id TEXT PRIMARY KEY,
    name TEXT,
    email TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    advisor_id TEXT NOT NULL REFERENCES advisors(id),
    name TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    advisor_id TEXT NOT NULL REFERENCES advisors(id),
    agent_id TEXT NOT NULL REFERENCES agents(id),
    prompt TEXT,
    task_type TEXT,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    agent_id TEXT NOT NULL REFERENCES agents(id),
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    tool_name TEXT,
    timestamp TEXT NOT NULL,
    duration_ms INTEGER,
    error_message TEXT,
    metadata JSONB NOT NULL
);

CREATE INDEX events_task_timestamp ON events(task_id, timestamp);
CREATE INDEX tasks_status ON tasks(status);
COMMIT;
