# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Dungeon Master backend: a FastAPI service where players sign in with Discord, generate characters, start campaigns built from pre-authored checkpoints, and play a text adventure narrated by Claude. Characters use a custom 7-stat system (1-10 scale), not D&D 5e. The frontend is the sibling repo `../dungeon-web`.

See `README.md` for the API surface and local setup.

## How We Work

- AI-driven and fast: build features end to end, push until something breaks, then fix it. This is no longer a step-by-step learning project.
- Design specs and plans go in `docs/plans/` or `docs/superpowers/`. Both are gitignored, so they stay local working notes and never get committed.
- Keep `README.md`, `docs/architecture.md` (Mermaid C4 diagrams, committed), and this file accurate when behavior changes. Update the diagrams when containers, external systems, or service boundaries change. Update the README's Roadmap section when features land.

## Commands

```bash
uv sync                              # Install dependencies
uv sync --upgrade-package anthropic  # Upgrade anthropic SDK

make lr                              # Start postgres+flyway, run uvicorn locally
make lr-down                         # Tear down local env (wipes db volume)
make dr / make dr-down               # Full docker stack (API + DB)

uv run pytest                        # Run tests
uv run pytest tests/test_file.py::test_name
uv run ruff check . && uv run ruff format .
uv run mypy src
```

## Architecture

**Layered design**: FastAPI routers (`src/api/`) → services (`src/services/`) → `dm_agent.py` (Claude) → PostgreSQL + pgvector

**Services**:
- `dm_agent.py` - Anthropic clients and all LLM calls: `create_character()` (structured output via `output_config`), `create_campaign()` (tool_use loop), `process_turn_stream()` (async; yields `TextDelta` and at most one tool result, a `RollResult` from `roll_check` or an `EncounterPlan` from `start_encounter`; second request uses `tool_choice: none`), `narrate_round_stream()` (combat rounds), `extract_memories()`
- `prompts.py` - Prompt strings and `build_turn_system_prompt()` (campaign + character + checkpoint context)
- `turn_service.py` - `load_turn_context()` loads character → campaign → active checkpoint → last 10 messages → memories → bestiary; `stream_turn()` turns `process_turn_stream` output into SSE events (`thinking`, `roll`, `text`, `combat`, `done`, `error`), then `save_turn()` persists both messages (and any encounter the DM started) with its own `Session(engine)` and schedules memory extraction. Nothing is saved on error. `stream_combat_round()` sends `round` and `combat` for an already-committed round, then the narration; a narration error leaves the round standing
- `memory_service.py` - `retrieve_memories(campaign_id, query_text, session)`: embeds the query (`embed_query`, Voyage `input_type="query"`) and runs a pgvector cosine search (`<=>`) per memory table, scoped to the campaign, capped at `MEMORIES_PER_KIND` (3) and `MAX_COSINE_DISTANCE` (0.6). `turn_service.load_turn_context()` calls it with the last DM reply + player message; failures are logged and the turn continues with no memories. `prompts.format_memories()` renders the "What You Remember" section
- `embedding_service.py` - `extract_and_store_memories()` runs as a FastAPI BackgroundTask after each turn: extracts NPC/location/item/event memories, upserts by name per campaign (appending facts/secrets/events to a known record), then embeds every stored or merged record with Voyage `voyage-3.5` (1024 dims) from `memory_text()`. Embed after merging, never before, or a known NPC's vector covers only the latest mention. Extraction is given the campaign's recorded NPC/location/item names (`KnownNames`, so "the steward" joins "Aldo Venn" instead of starting a new record) and what the turn recalled (`prompts.known_context()`, so a contradicted claim is written to the liar's `secrets` as "Lied about ...; evidence: ..."). Records are matched by name ignoring case. `known_context` is rendered to text in `stream_turn` because the background task runs after the turn's DB session closes; never pass ORM rows to a background task
- `campaign_service.py` - Verifies the requesting user owns `character_id`, calls `create_campaign`, persists the campaign + ordered checkpoints (first `new`, rest `locked`), assigns the character to it, and saves the opening message as the first assistant `messagehistory` row. `list_for_user()` backs `GET /campaigns/`: the user's campaigns, each with only that user's characters and its `campaigncheckpoint` rows ordered by `order`
- `character_service.py` - `create_preview(description, user)` generates a sheet via dm_agent, clamps age and stats into range, and returns it with a `preview_token`: a JWT (`SECRET_KEY`, audience `character-preview`, 1 hour) over that exact sheet for that user. `create_from_preview(token, session, user)` saves only an unaltered, unexpired token of that user's (else `InvalidPreview`, a 400). Stats are never client input
- `combat_service.py` - All combat numbers (rules in its docstring): `max_hp_for` (10 + 2 x endurance), `defense_for`, `attack_stat` (by class), `resolve_round()` (pure: applies one attack/defend/flee round to the objects passed in), `play_round()` (locks the active encounter `FOR UPDATE`, refreshes the character, resolves, sets `died_at` on a loss, commits before any narration), `begin_encounter()`, `encounter_state()` (the `combat` SSE payload). The DM never decides a hit or damage: `start_encounter` (`src/tools/combat_tools.py`, kinds limited to the `enemy` table, max 4) only chooses enemies, saved by `turn_service.save_turn` in the same commit as the turn's messages. `dm_agent.narrate_round_stream()` narrates a resolved round in one request without tools; the round brief (`prompts.combat_round_section`) goes in the last user message, because in the system prompt Claude followed the conversation over it (a death went unnarrated). Death is permanent: `character.died_at` set, row kept; turn and combat routes and campaign creation refuse a dead character (409), and free-text turns are refused during a fight. Resting: `start_rest()` sets `character.rest_started_at` (idempotent; refused mid-fight, at full HP, or dead), `finish_rest()` heals to full only after `REST_SECONDS` (20), `rest_state()` gives `seconds_left`. The wait is the server's, so the frontend's campfire can't be skipped; free-text turns are refused while resting
- `usage_service.py` - `check_and_record(session, user, action)` for `turn`, `preview`, `campaign`: refuses (`RateLimited`) past `LIMITS` per user per minute, per user per 24 h, and all users per 24 h, else records a `llmusage` row. Routes call `src/api/dependencies.py:enforce_limit()` after their own validation (ownership) and before calling Claude; it maps `RateLimited` to 429 + `Retry-After`. Any new route that calls Claude must call `enforce_limit`
- `auth_service.py` - Discord user upsert; session JWT create/validate (`SECRET_KEY`, HS256, 7 days, carries `ver` = `user.token_version`); `user_for_token()` turns a cookie value into a user or a reason it is not valid

**Auth**: The session is an httpOnly `dungeon_session` cookie set by `/auth/discord/callback`; Bearer headers are not accepted. `src/api/dependencies.py:get_current_user` reads the cookie and rejects tokens whose `ver` no longer matches `user.token_version` (`/auth/logout` bumps it, ending every session). All routes except `/health` and the callback depend on it, and queries filter by that user's id. Character routes also check `character.user_id == user.id`. `src/main.py` refuses POST/PUT/PATCH/DELETE without `X-Requested-With: dungeon-web` (CSRF), so new write routes get that for free; the test clients send it by default (`tests/conftest.py:FRONTEND_HEADERS`).

**Tenancy**: Shared tables, one tenant per user. `campaign` has no owner column: a campaign belongs to the user who owns its character, so campaign queries join `character` and filter `character.user_id`. Any new route returning user data must filter by the current user (`checkpoint`, `heroclass` and `race` are shared content). Request bodies must be input models (e.g. `CharacterCreate`, which also bound player input: stats 1-10, names 60 chars, descriptions and turn messages 2000), never table models: a table model lets the client set `id`, `user_id` or `campaign_id`, which is how a player could once join another player's campaign. `campaign_service.delete_for_user()` backs `DELETE /campaigns/{id}`: it 404s unless the user has a character in the campaign, deletes its memories, history and checkpoints, and frees its characters

**Tools**: `src/tools/campaign_tools.py` - `search_checkpoints` (campaign creation). `src/tools/dice_tools.py` - `roll_check` (turns): d20 + stat vs easy 10 / medium 15 / hard 20, ties pass; `roll_d20()` and `roll_die()` are the patch points for tests (combat patches them in `src.services.combat_service`). `src/tools/combat_tools.py` - `start_encounter` (turns, offered when the bestiary is non-empty; at most one tool call per turn), `plan_encounter()` drops unknown kinds and numbers duplicates

**Database tables**: `user`, `campaign`, `character` (with `max_hp`, `current_hp`, `died_at`, `rest_started_at`), `enemy` (bestiary, shared content), `encounter` (one active per character, unique partial index) and `combatant` (an enemy's HP in one encounter; cascades with it), `checkpoint`, `campaigncheckpoint` (ordered checkpoints per campaign with status/summary), `heroclass`, `race`, `messagehistory`, and memory tables `npcmemory`, `locationmemory`, `itemmemory`, `eventmemory` (each with `vector(1024)` + HNSW cosine index)

**Migrations**: `db/migrations/` versioned (`V*`, run everywhere; `V5__game_content.sql` holds classes, races and checkpoints; `V6__combat.sql` the HP columns, combat tables and bestiary; `V7__rest.sql` `rest_started_at`); `db/seeds/` repeatable (`R__`, local test data only: `seed_user` and its campaigns, mounted only by the local docker-compose)

## Testing

- Tests never hit a real DB or LLM. `tests/conftest.py` provides `client` (auth + session overridden via `app.dependency_overrides`), `anon_client` (real cookie auth, mocked session; pass `Cookie: dungeon_session=...`), `session` (MagicMock), `user`, and `make_character()`
- Patch service functions where the router imports them (e.g. `src.api.characters.load_turn_context`)
- Always patch `src.services.turn_service.extract_and_store_memories` in turn route tests. TestClient runs background tasks, so an unpatched turn test calls Claude and Voyage for real
- Async tests use `@pytest.mark.anyio` (anyio's pytest plugin ships with FastAPI). `tests/helpers.py:FakeStream` stands in for `async_client.messages.stream`
- `conftest.py` has an autouse `no_rate_limits` fixture that stubs `src.api.dependencies.check_and_record`; patch it again to test a limit. An autouse `no_combat_lookups` fixture stubs `src.services.turn_service.load_bestiary` (empty) and `src.api.characters.active_encounter` (None); patch them again to test fights. It also has an autouse `no_memory_lookup` fixture that stubs `src.services.turn_service.retrieve_memories` (empty), so tests never call Voyage. Patch it again in a test to exercise retrieval
- `src/config` raises at import if env vars are missing, so `.env` must exist to run tests
- `evals/` is separate from the test suite: scripts that call real Claude/Voyage to measure memory (retrieval, extraction, end-to-end recall). See README "Evals". Run them before and after changing memory prompts, limits or embedding text; add a case when play turns up a memory failure

## Tech Stack

- Python 3.12+, FastAPI, SQLModel, psycopg2 (named explicitly in `db.py`: SQLAlchemy 2.1 maps bare `postgresql://` to psycopg 3), pgvector
- Claude model `claude-sonnet-4-5-20250929` is hardcoded in several places in `dm_agent.py`
- Voyage AI for embeddings; Discord OAuth + PyJWT for auth

## Environment Variables

All required (loaded in `src/config/config.py`, which raises at import if any are missing): `DUNGEON_ANTHROPIC_API_KEY` (the Claude API key; deliberately not `ANTHROPIC_API_KEY`, which Claude Code itself reads), `VOYAGE_API_KEY`, `DATABASE_URL`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `SECRET_KEY` (at least 32 bytes; `require_secret_key` refuses to start otherwise). docker-compose also needs `POSTGRES_USER` / `POSTGRES_PASSWORD`. Optional: `DB_ECHO` (SQL logging, off), `API_DOCS` (on; production sets false), `COOKIE_SECURE` (on).

## Deployment

`infra/prod/` (see `DEPLOY.md`): Compose with Caddy (built from `../dungeon-web`'s Dockerfile and Caddyfile) as the only service with `ports:`; never add `ports:` to `api` or `db` there (Docker's port rules bypass the host firewall). Flyway mounts only `db/migrations`, never `db/seeds`, so anything production needs (like game content) must be a `V*` migration. The `Dockerfile` installs `uv.lock --frozen` without dev tools and runs as a non-root user

## Gotchas

- **Structured output everywhere**: character, campaign, and memory extraction all use `output_config` JSON schemas (`CHARACTER_SCHEMA`, `CAMPAIGN_SCHEMA`, `MEMORIES_SCHEMA` in `dm_agent.py`), so services `json.loads` directly with no fence stripping
- **`output_config` requires SDK >= 0.86.0**: upgrade with `uv sync --upgrade-package anthropic` if Pyright complains
- **Session lifecycle**: Don't use `with session:` on a FastAPI-injected session. Background tasks and tool handlers run outside the request, so they open their own `Session(engine)`
- **`col()` for SQL expressions**: Use `col(Model.field)` for `.not_in()`, `.contains()`, etc.
- **F821 ruff suppression**: Model files use string forward refs (e.g. `"Campaign"`); F821 is suppressed for `src/models/*.py`
- **Migrations are Flyway SQL** (`db/migrations/V*`), not Alembic
