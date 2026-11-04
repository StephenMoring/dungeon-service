-- Bumped on logout; a session token carries the version it was issued with, so
-- logging out ends every copy of the token, not just the one in this browser.
ALTER TABLE "user" ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0;
