-- One row per accepted request that calls Claude, so per-user and overall limits
-- hold across restarts and server processes. Only the last 24 hours are ever read.
CREATE TABLE llmusage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    action TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX llmusage_user_action_created ON llmusage (user_id, action, created_at);
CREATE INDEX llmusage_action_created ON llmusage (action, created_at);
