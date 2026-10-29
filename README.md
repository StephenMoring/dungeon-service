# Dungeon Service

Backend for an AI dungeon master game. Players sign in with Discord, generate a character from a short description, start a campaign built from pre-authored scenarios, and play a text adventure narrated by Claude. Risky actions are settled by real dice rolls on the server.

The frontend is the sibling repo `../dungeon-web`. Its Vite dev server (`http://localhost:5173`) proxies `/api` to this service on `:8000`.

## Features

- **Discord sign-in**: The frontend sends the OAuth code to `/auth/discord/callback`. The service exchanges it with Discord, creates or updates the user, and returns a 30-day JWT. Every other route (except `/health`) requires that JWT.
- **Characters**: The player gives a name, class, race and free-text description. Claude returns a character sheet with age, biography and 7 stats on a 1–10 scale (strength, perception, endurance, charisma, intelligence, agility, luck), using structured output. The player previews it, then saves it.
- **Campaigns**: The player picks a character and describes the campaign they want. Claude classifies the request into tags, calls the `search_checkpoints` tool to pull matching pre-authored scenarios, and returns a campaign with an ordered list of checkpoints and an opening message. The first checkpoint is active and the rest are locked. The character joins the campaign, and the opening message starts its history.
- **Streaming turns**: Each player message goes to Claude with the campaign, character sheet, active checkpoint, relevant campaign memories and the last 10 messages. The reply streams back as Server-Sent Events (`thinking`, `roll`, `text`, `done`, `error`). Both sides of the exchange are saved when the stream finishes; nothing is saved if it fails.
- **Dice checks**: When an action's outcome is uncertain and failure would matter (sneaking, persuading, spotting something hidden), Claude calls the `roll_check` tool with a stat, a difficulty and a reason. The server rolls a d20 and adds the stat, and the action passes if the total meets the target: easy 10, medium 15, hard 20 (ties pass). The result streams to the browser as a `roll` event, which the frontend animates before revealing the narration. Claude must narrate failures as failures. At most one roll per turn, and rolls are not stored.
- **Campaign memory (RAG)**: After each turn, a background task asks Claude to extract NPCs, locations, items and events from the exchange, embeds them with Voyage AI (`voyage-3.5`, 1024 dimensions), and upserts them into pgvector tables per campaign. Before each turn, the DM's last reply plus the player's message are embedded as a search query, and a cosine-similarity search pulls up to 3 close matches of each kind from that campaign (cutoff: cosine distance 0.6). The matches go into the DM's prompt as "What You Remember", including secrets the player has uncovered, so the DM stays consistent with what the player knows and characters' lies can be caught. If the lookup fails, the turn continues without memories.
- **Per-user data**: All users share one database, and every route that returns player data filters by the signed-in user. Characters carry a `user_id`; campaigns belong to whoever owns their character. Checkpoints, classes and races are shared content.

## Stack

- Python 3.12+, FastAPI, SQLModel, psycopg2
- PostgreSQL 16 + pgvector, migrations with Flyway (Docker)
- Anthropic Claude (`claude-sonnet-4-5`) for all generation, with tool use, streaming and structured output; Voyage AI for embeddings
- Discord OAuth + PyJWT for auth
- uv, Ruff, mypy, pytest (+ pytest-mock, anyio)

## Architecture

C4 diagrams (system context, containers, components), sequence diagrams for a turn and for campaign creation, and the data model are in [docs/architecture.md](./docs/architecture.md).

## Layout

```
src/
  api/          FastAPI routers: auth, characters, campaigns; get_current_user dependency
  services/     dm_agent (all Claude calls), prompts, memory retrieval, turn/campaign/character/auth/embedding services
  tools/        Claude tools: search_checkpoints (campaign creation), roll_check (dice)
  models/       SQLModel tables and request/response schemas
  db/           engine + session dependency
  config/       env var loading
db/
  migrations/   Flyway versioned migrations (V*)
  seeds/        local-only seed data (R__): checkpoints, classes, races, test users
infra/local/    docker-compose (postgres, flyway, app)
tests/          pytest suite; mocks Claude, Voyage and the DB
docs/           architecture.md (committed); plans/ and superpowers/ are local-only
```

## API

All routes except `/health` and `/auth/*` need a `Bearer` JWT. Routes only return the signed-in user's data.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/discord/callback` | Exchange a Discord OAuth code for a JWT |
| GET | `/characters/` | Your characters, each with its campaign |
| POST | `/characters/` | Save a character |
| POST | `/characters/preview` | Generate a character sheet without saving |
| GET | `/characters/classes` | List classes |
| GET | `/characters/races` | List races |
| GET | `/characters/{id}` | One of your characters |
| GET | `/characters/{id}/turns` | Message history for your character |
| POST | `/characters/{id}/turns/stream` | Play a turn (SSE: `thinking`, `roll`, `text`, `done`, `error`) |
| GET | `/campaigns/` | Your campaigns |
| POST | `/campaigns/` | Generate and save a campaign for one of your characters |
| GET | `/campaigns/{id}/characters` | Your characters in a campaign |
| GET | `/health` | Health check |

### Turn stream events

```
event: thinking   data: {}
event: roll       data: {"stat", "stat_value", "roll", "total", "difficulty", "target", "success", "reason"}
event: text       data: {"text": "..."}          (repeated)
event: done       data: {"message_id": 123}
event: error      data: {"detail": "..."}        (ends the stream; nothing saved)
```

## Running locally

Create `.env`:

```
ANTHROPIC_API_KEY=
VOYAGE_API_KEY=
DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/dungeon_pg_db
POSTGRES_USER=
POSTGRES_PASSWORD=
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_REDIRECT_URI=
SECRET_KEY=
```

All of these are required; the app fails at startup if any is missing. Use a `SECRET_KEY` of at least 32 bytes.

Then:

```bash
uv sync
make lr        # start postgres + run flyway migrations/seeds, then uvicorn --reload on :8000
make lr-down   # stop and wipe the local db
```

`make dr` / `make dr-down` run the whole stack, API included, in Docker.

## Development

```bash
uv run pytest                              # no DB or API keys used; .env must exist
uv run ruff check . && uv run ruff format .
uv run mypy src
```

## Roadmap

- Tune memory retrieval (per-kind limit, distance cutoff) from real play
- Checkpoint progression: detect when an objective is done, summarize it, move to the next checkpoint
- Tune how often the DM calls for rolls, based on real play

## Known gaps

- `mypy src` reports existing errors in `embedding_service.py` and `models/memory.py`
- Saving a turn runs synchronously inside the stream; fine for a few players, not for many at once
- The DM's stat and difficulty choices are limited by the tool schema but not re-checked on the server
