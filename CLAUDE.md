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
- `dm_agent.py` - Anthropic clients and all LLM calls: `create_character()` (structured output via `output_config`), `create_campaign()` (tool_use loop), `process_turn_stream()` (async; yields `TextDelta` and at most one `RollResult` via the `roll_check` tool, second request uses `tool_choice: none`), `extract_memories()`
- `prompts.py` - Prompt strings and `build_turn_system_prompt()` (campaign + character + checkpoint context)
- `turn_service.py` - `load_turn_context()` loads character → campaign → active checkpoint → last 10 messages; `stream_turn()` turns `process_turn_stream` output into SSE events (`thinking`, `roll`, `text`, `done`, `error`), then `save_turn()` persists both messages with its own `Session(engine)` and schedules memory extraction. Nothing is saved on error
- `embedding_service.py` - `extract_and_store_memories()` runs as a FastAPI BackgroundTask after each turn: extracts NPC/location/item/event memories, embeds with Voyage `voyage-3.5` (1024 dims), upserts by name per campaign
- `campaign_service.py` - Verifies the requesting user owns `character_id`, calls `create_campaign`, persists the campaign + ordered checkpoints (first `new`, rest `locked`), assigns the character to it, and saves the opening message as the first assistant `messagehistory` row
- `character_service.py` - `create_preview()` generates a sheet via dm_agent without saving; `create()` saves a client-submitted character for the current user
- `auth_service.py` - Discord user upsert, JWT create/validate (`SECRET_KEY`)

**Auth**: `src/api/dependencies.py:get_current_user` validates the Bearer JWT; all routes except `/health` and `/auth/*` depend on it. Character routes also check `character.user_id == user.id`.

**Tenancy**: Shared tables, one tenant per user. `campaign` has no owner column: a campaign belongs to the user who owns its character, so campaign queries join `character` and filter `character.user_id`. Any new route returning user data must filter by the current user (`checkpoint`, `heroclass` and `race` are shared content).

**Tools**: `src/tools/campaign_tools.py` - `search_checkpoints` (campaign creation). `src/tools/dice_tools.py` - `roll_check` (turns): d20 + stat vs easy 10 / medium 15 / hard 20, ties pass; `roll_d20()` is the patch point for tests

**Database tables**: `user`, `campaign`, `character`, `checkpoint`, `campaigncheckpoint` (ordered checkpoints per campaign with status/summary), `heroclass`, `race`, `messagehistory`, and memory tables `npcmemory`, `locationmemory`, `itemmemory`, `eventmemory` (each with `vector(1024)` + HNSW cosine index)

**Migrations**: `db/migrations/` versioned (`V*`, run everywhere); `db/seeds/` repeatable (`R__`, local only, mounted separately in docker-compose)

## Testing

- Tests never hit a real DB or LLM. `tests/conftest.py` provides `client` (auth + session overridden via `app.dependency_overrides`), `anon_client` (real JWT auth, mocked session), `session` (MagicMock), `user`, and `make_character()`
- Patch service functions where the router imports them (e.g. `src.api.characters.load_turn_context`)
- Always patch `src.services.turn_service.extract_and_store_memories` in turn route tests. TestClient runs background tasks, so an unpatched turn test calls Claude and Voyage for real
- Async tests use `@pytest.mark.anyio` (anyio's pytest plugin ships with FastAPI). `tests/helpers.py:FakeStream` stands in for `async_client.messages.stream`
- `src/config` raises at import if env vars are missing, so `.env` must exist to run tests

## Tech Stack

- Python 3.12+, FastAPI, SQLModel, psycopg2, pgvector
- Claude model `claude-sonnet-4-5-20250929` is hardcoded in several places in `dm_agent.py`
- Voyage AI for embeddings; Discord OAuth + PyJWT for auth

## Environment Variables

All required (loaded in `src/config/config.py`, which raises at import if any are missing): `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `DATABASE_URL`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `SECRET_KEY`. docker-compose also needs `POSTGRES_USER` / `POSTGRES_PASSWORD`.

## Gotchas

- **Structured output everywhere**: character, campaign, and memory extraction all use `output_config` JSON schemas (`CHARACTER_SCHEMA`, `CAMPAIGN_SCHEMA`, `MEMORIES_SCHEMA` in `dm_agent.py`), so services `json.loads` directly with no fence stripping
- **`output_config` requires SDK >= 0.86.0**: upgrade with `uv sync --upgrade-package anthropic` if Pyright complains
- **Session lifecycle**: Don't use `with session:` on a FastAPI-injected session. Background tasks and tool handlers run outside the request, so they open their own `Session(engine)`
- **`col()` for SQL expressions**: Use `col(Model.field)` for `.not_in()`, `.contains()`, etc.
- **F821 ruff suppression**: Model files use string forward refs (e.g. `"Campaign"`); F821 is suppressed for `src/models/*.py`
- **Alembic in deps but unused**: Flyway handles migrations
- **Typer in deps but unused**: leftover from the original CLI plan
