# Dungeon Service

Backend for an AI dungeon master game. Players sign in with Discord, generate a character from a short description, start a campaign, and play a text adventure narrated by Claude.

The frontend lives in the sibling repo `../dungeon-web` (expected at `http://localhost:3000`).

## How it works

- **Characters**: The player gives a name, class, race, and free-text description. Claude returns a character sheet (age, biography, and 7 stats on a 1–10 scale: STR, PER, END, CHA, INT, AGI, LCK) through structured output. The player can preview it before saving.
- **Campaigns**: The player picks a character and describes the campaign they want. Claude runs a tool-use loop, calls `search_checkpoints` to pull pre-authored scenarios from the database by tag, and returns a campaign with an ordered list of checkpoints and an opening message. The character joins the campaign, and the opening message becomes the first entry in its history.
- **Turns**: Each player message is sent to Claude along with the campaign, the character sheet, the active checkpoint, and the last 10 messages. The reply streams back as Server-Sent Events. Both sides of the exchange are saved to `messagehistory` when the stream ends.
- **Dice checks**: When an action's outcome is uncertain and failure matters, Claude calls the `roll_check` tool with a stat, a difficulty and a reason. The server rolls a d20, adds the stat, and compares the total to the target (easy 10, medium 15, hard 20; ties pass). The result streams to the client as a `roll` event, and Claude narrates the success or failure. At most one roll per turn. Rolls are not stored.
- **Campaign memory**: After each turn, a background task asks Claude to pull NPCs, locations, items, and events out of the exchange. It embeds them with Voyage AI (`voyage-3.5`) and upserts them into pgvector tables. The DM doesn't read these memories back during turns yet.

## Stack

- Python 3.12+, FastAPI, SQLModel, psycopg2
- PostgreSQL 16 + pgvector, migrations via Flyway (Docker)
- Anthropic Claude for all generation, Voyage AI for embeddings
- Discord OAuth → JWT for auth
- uv, Ruff, mypy, pytest + pytest-mock

## Architecture

C4 diagrams (context, containers, components), request flows, and the data model are in [docs/architecture.md](./docs/architecture.md).

## Layout

```
src/
  api/          FastAPI routers: auth, characters, campaigns
  services/     dm_agent (Claude calls), prompts, turn/campaign/character/auth/embedding services
  tools/        Claude tool definitions + handlers (search_checkpoints)
  models/       SQLModel tables and request/response schemas
  db/           engine + session dependency
  config/       env var loading
db/
  migrations/   Flyway versioned migrations (V*)
  seeds/        local-only seed data (R__): checkpoints, classes, races, test users
infra/local/    docker-compose (postgres, flyway, app)
tests/
```

## API

All routes except `/health` and `/auth/*` need a `Bearer` JWT.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/discord/callback` | Exchange a Discord OAuth code for a JWT |
| GET | `/characters/` | List the current user's characters |
| POST | `/characters/` | Save a character |
| POST | `/characters/preview` | Generate a character sheet without saving |
| GET | `/characters/classes` | List classes |
| GET | `/characters/races` | List races |
| GET | `/characters/{id}` | Get one character |
| GET | `/characters/{id}/turns` | Message history for a character |
| POST | `/characters/{id}/turns/stream` | Play a turn (SSE: `thinking`, `roll`, `text`, `done`, `error`) |
| GET | `/campaigns/` | List campaigns |
| POST | `/campaigns/` | Generate and save a campaign |
| GET | `/campaigns/{id}/characters` | Characters in a campaign |
| GET | `/health` | Health check |

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

Then:

```bash
uv sync
make lr        # start postgres + run flyway migrations/seeds, then uvicorn --reload
make lr-down   # stop and wipe the local db
```

`make dr` / `make dr-down` run the whole stack, API included, in Docker.

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format .
uv run mypy src
```

## Roadmap

- Read campaign memories back into the turn prompt (vector search over the memory tables)
- Checkpoint progression: detect when an objective is done, summarize it, move to the next checkpoint
