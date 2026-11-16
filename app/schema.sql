
CREATE TABLE IF NOT EXISTS scenarios (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    steps       JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runs (
    id            SERIAL PRIMARY KEY,
    scenario_id   INT REFERENCES scenarios(id) ON DELETE SET NULL,
    scenario_name TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'running',
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);


CREATE TABLE IF NOT EXISTS run_steps (
    id          SERIAL PRIMARY KEY,
    run_id      INT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    position    INT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT NOT NULL DEFAULT '',
    value       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL,
    message     TEXT NOT NULL DEFAULT '',
    duration_ms INT NOT NULL DEFAULT 0
);
