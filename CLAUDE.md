# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Dungeon Master - a FastAPI-based D&D game with an AI DM powered by Claude. Players create characters, start campaigns, and engage in text-based adventures with accurate D&D 5e rules.

## Commands

```bash
# Dependencies
uv sync                              # Install dependencies

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
- `dm_agent.py` - Anthropic client, system prompts, and LLM creation functions (`create_character()`, `create_campaign()`). Uses tool_use loop for campaign creation.
- `campaign_service.py` - Calls dm_agent, parses LLM JSON response (strips markdown fences defensively), persists campaign + checkpoint links
- `character_service.py` - Calls dm_agent, parses LLM JSON response, persists character

**API routers in `src/api/`**:
- `characters.py` - POST /characters/
- `campaigns.py` - POST /campaigns/

**Config**: `src/config/config.py` — loads `ANTHROPIC_API_KEY` and `DATABASE_URL` from environment

**Tools in `src/tools/`**:
- `campaign_tools.py` - Anthropic tool_use definition for `search_checkpoints` + handler; used by dm_agent during campaign creation

**Database tables**:
- `campaign` - Campaign metadata (name, theme, description)
- `character` - Player characters with 7 stats on 1-10 scale, FK to campaign
- `checkpoint` - Pre-authored scenario checkpoints with tags; 20 seeded via Flyway
- `campaigncheckpoint` - Join table linking campaigns to ordered checkpoints with status/summary

**Data flow for campaign creation**:
1. POST /campaigns/ → `campaign_service.create()`
2. Calls `dm_agent.create_campaign()` — enters tool_use loop with Anthropic API
3. Claude calls `search_checkpoints` tool → handler queries DB by tags → results returned
4. Loop continues appending assistant + tool_result messages until `stop_reason == "end_turn"`
5. Service parses final JSON, persists campaign + checkpoint associations

## Tech Stack

- **Python 3.12+**, FastAPI, SQLModel, psycopg2
- **PostgreSQL** for data storage; **Flyway** (via Docker) for migrations
- **Claude API** (`claude-sonnet-4-5-20250929` hardcoded in `dm_agent.py`) for DM responses
- **Ruff** for linting/formatting, **mypy** for types, **pytest** + **httpx** for tests

## Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY` - Claude API access
- `DATABASE_URL` - PostgreSQL connection string
- `POSTGRES_USER` / `POSTGRES_PASSWORD` - Used by docker-compose

## Gotchas

- **Markdown fence stripping**: LLM responses sometimes include ` ```json ``` ` fences; both service layers strip these before parsing
- **F821 ruff suppression**: Model files use string forward references (e.g., `"Campaign"`) to avoid import loops — F821 errors are suppressed for those files
- **Alembic in deps but unused**: Flyway handles migrations via Docker; Alembic is a leftover dependency

## Future State

Planned features not yet implemented:

**RAG / SRD Retrieval**:
- `src/services/retrieval.py` - RAG pipeline: query embedding → pgvector similarity search → context ranking
- `src/services/llm.py` - Standalone Claude API client for DM responses
- `srd_embeddings` table - Chunked SRD content with vector embeddings (pgvector)
- `message_history` table - Conversation persistence across sessions
- `scripts/ingest_srd.py` - Script to embed SRD content into pgvector
- `OPENAI_API_KEY` - Required once OpenAI text-embedding-3-small is integrated
