# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Dungeon Master - a FastAPI-based D&D game with an AI DM powered by Claude. Players create characters, start campaigns, and engage in text-based adventures with accurate D&D 5e rules.

## Commands

```bash
# Dependencies
uv sync                              # Install dependencies
uv sync --upgrade-package anthropic  # Upgrade anthropic SDK

# Development
uvicorn src.main:app --reload        # Start dev server locally
make lr                              # Start postgres+flyway, run uvicorn locally
make lr-down                         # Tear down local env
make dr                              # Full docker run (API + DB)
make dr-down                         # Tear down docker env

# Docker (compose file is at infra/local/docker-compose.yml)
docker-compose -f infra/local/docker-compose.yml --profile noapp up   # DB + migrations only
docker-compose -f infra/local/docker-compose.yml --profile all up     # Full environment

# Testing & Quality
pytest                               # Run tests
pytest tests/test_file.py::test_name # Run single test
ruff check .                         # Lint
ruff format .                        # Format
mypy src                             # Type check
```

## Architecture

**Layered design**: FastAPI Routers → Service Layer → DM Agent → PostgreSQL

**Key services in `src/services/`**:
- `dm_agent.py` - Anthropic client, system prompts, and LLM functions (`create_character()`, `create_campaign()`, `process_turn()`). Uses tool_use loop for campaign creation. Uses `output_config` structured output for character creation.
- `prompts.py` - All prompt strings and `build_turn_system_prompt()` which assembles campaign/character/checkpoint context
- `campaign_service.py` - Calls dm_agent, parses LLM JSON response (strips markdown fences defensively), persists campaign + checkpoint links
- `character_service.py` - Calls dm_agent, parses LLM JSON response, persists character
- `turn_service.py` - Handles gameplay turns: loads character, campaign, active checkpoint, recent message history, calls `process_turn`, returns DM response

**API routers in `src/api/`**:
- `characters.py` - POST /characters/, POST /characters/{id}/turns
- `campaigns.py` - POST /campaigns/

**Config**: `src/config/config.py` — loads `ANTHROPIC_API_KEY` and `DATABASE_URL` from environment

**Tools in `src/tools/`**:
- `campaign_tools.py` - Anthropic tool_use definition for `search_checkpoints` + handler; used by dm_agent during campaign creation

**Database tables**:
- `campaign` - Campaign metadata (name, theme, description)
- `character` - Player characters with 7 stats on 1-10 scale, FK to campaign
- `checkpoint` - Pre-authored scenario checkpoints with tags; 20 seeded via Flyway
- `campaigncheckpoint` - Join table linking campaigns to ordered checkpoints with status/summary
- `message_history` - Per-turn conversation history (campaign_id, character_id, role, content, created_at)

**Database migrations**:
- `db/migrations/` — versioned schema migrations (run everywhere)
- `db/seeds/` — repeatable seed data (`R__` prefix, local only); mounted separately in docker-compose

**Data flow for campaign creation**:
1. POST /campaigns/ → `campaign_service.create()`
2. Calls `dm_agent.create_campaign()` — enters tool_use loop with Anthropic API
3. Claude calls `search_checkpoints` tool → handler queries DB by tags → results returned
4. Loop continues appending assistant + tool_result messages until `stop_reason == "end_turn"`
5. Service parses final JSON, persists campaign + checkpoint associations

**Data flow for taking a turn**:
1. POST /characters/{id}/turns → `turn_service.take_turn()`
2. Loads character → campaign → active checkpoint (first where status not in `complete`/`locked`) → last 10 messages
3. Calls `dm_agent.process_turn()` with assembled context
4. Returns DM response (message persistence not yet implemented)

## Tech Stack

- **Python 3.12+**, FastAPI, SQLModel, psycopg2
- **PostgreSQL** for data storage; **Flyway** (via Docker) for migrations
- **Claude API** (`claude-sonnet-4-5-20250929` hardcoded in `dm_agent.py`) for DM responses
- **Ruff** for linting/formatting, **mypy** for types, **pytest** + **httpx** + **pytest-mock** for tests

## Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY` - Claude API access
- `DATABASE_URL` - PostgreSQL connection string
- `POSTGRES_USER` / `POSTGRES_PASSWORD` - Used by docker-compose

## Gotchas

- **Markdown fence stripping**: `campaign_service.py` defensively strips ` ```json ``` ` fences before JSON parsing; `character_service.py` does not (uses `output_config` structured output instead)
- **`output_config` requires SDK >= 0.86.0**: Character creation uses `output_config` for structured JSON output — upgrade with `uv sync --upgrade-package anthropic` if Pyright complains
- **Session lifecycle**: Do not use `with session:` in service functions that receive a FastAPI-injected session — FastAPI DI manages the lifecycle. Only use it when managing a session manually (e.g. inside tool handlers called outside the request lifecycle)
- **`col()` for SQL expressions**: Use `col(Model.field)` when chaining SQL methods like `.not_in()`, `.contains()` — plain model fields are typed as Python types and won't have these methods
- **F821 ruff suppression**: Model files use string forward references (e.g., `"Campaign"`) to avoid import loops — F821 errors are suppressed for those files
- **Alembic in deps but unused**: Flyway handles migrations via Docker; Alembic is a leftover dependency

## Next Up

- Persist player + DM messages to `message_history` after each turn
- Checkpoint completion detection (lightweight classifier LLM call after each turn)
- Checkpoint advancement + summary generation
