# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Dungeon Master - a CLI-based D&D game with an AI DM powered by Claude and RAG-based SRD retrieval. Players create characters, start campaigns, and engage in text-based adventures with accurate D&D 5e rules.

## Commands

```bash
# Dependencies
uv sync                              # Install dependencies

# Development
uvicorn src.main:app --reload        # Start dev server
docker-compose up                    # Full local environment (API + PostgreSQL)
docker-compose up -d db              # PostgreSQL only

# Testing & Quality
pytest                               # Run tests
pytest tests/test_file.py::test_name # Run single test
ruff check .                         # Lint
ruff format .                        # Format
mypy src                             # Type check

# SRD Ingestion
python scripts/ingest_srd.py         # Embed SRD content into pgvector
```

## Architecture

**Layered design**: CLI → FastAPI Routers → DM Agent Service → (Retrieval Service + LLM Service) → PostgreSQL/pgvector

**Key services in `src/services/`**:
- `dm_agent.py` - Orchestrates DM responses: manages conversation state, constructs prompts with persona + context, coordinates retrieval and LLM calls
- `retrieval.py` - RAG pipeline: query embedding → pgvector similarity search → context ranking
- `llm.py` - Claude API client for DM responses

**Database tables**:
- `campaigns` - Campaign metadata and summaries
- `characters` - Player characters with stats (JSON field)
- `message_history` - Conversation persistence
- `srd_embeddings` - Chunked SRD content with vector embeddings

**Data flow for player messages**:
1. Player input → FastAPI endpoint
2. DM Agent extracts query, calls Retrieval Service
3. Retrieval embeds query (OpenAI), searches pgvector, ranks results
4. DM Agent builds prompt: system prompt + SRD context + history + character info + message
5. LLM call (Claude) → response saved to history → returned to player

## Tech Stack

- **Python 3.11+**, FastAPI, SQLModel, Typer (CLI)
- **PostgreSQL + pgvector** for data and vector search
- **Claude API** for DM responses, **OpenAI text-embedding-3-small** for embeddings
- **Ruff** for linting/formatting, **mypy** for types, **pytest** for tests

## Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY` - Claude API access
- `OPENAI_API_KEY` - Embeddings API access
- `DATABASE_URL` - PostgreSQL connection string
