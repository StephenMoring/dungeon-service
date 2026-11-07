-- Resting heals to full, but only after a wait the server enforces
-- (combat_service.REST_SECONDS), so skipping the campfire animation skips nothing.
-- Set while resting; cleared when the rest is finished.
ALTER TABLE character ADD COLUMN rest_started_at TIMESTAMPTZ;
