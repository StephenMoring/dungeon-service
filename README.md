# Dungeon Service

Backend for an AI dungeon master game. Players sign in with Discord, generate a character from a short description, start a campaign built from pre-authored scenarios, and play a text adventure narrated by Claude. Risky actions are settled by real dice rolls on the server.

The frontend is the sibling repo `../dungeon-web`. Its Vite dev server (`http://localhost:5173`) proxies `/api` to this service on `:8000`.

## Features

- **Discord sign-in and sessions**: The frontend sends the OAuth code to `/auth/discord/callback`. The service exchanges it with Discord, creates or updates the user, and sets a 7-day session JWT as an httpOnly, Secure, `SameSite=Lax` cookie (`dungeon_session`), so page JavaScript never sees the token. Every route except `/health` and the sign-in callback needs that cookie, and the user is always read from it: request bodies never choose an owner. Logging out bumps the user's `token_version`, which ends every copy of the token. Requests that change data (POST/PUT/PATCH/DELETE) must also send `X-Requested-With: dungeon-web`, which other sites cannot add to a forged cross-site request.
- **Characters**: The player gives a name, class, race and free-text description. Claude returns a character sheet with age, biography and 7 stats on a 1–10 scale (strength, perception, endurance, charisma, intelligence, agility, luck), using structured output. The player previews it, then saves it.
- **Campaigns**: The player picks a character and describes the campaign they want. Claude classifies the request into tags, calls the `search_checkpoints` tool to pull matching pre-authored scenarios, and returns a campaign with an ordered list of checkpoints and an opening message. The first checkpoint is active and the rest are locked. The character joins the campaign, and the opening message starts its history.
- **Streaming turns**: Each player message goes to Claude with the campaign, character sheet, active checkpoint, relevant campaign memories and the last 10 messages. The reply streams back as Server-Sent Events (`thinking`, `roll`, `text`, `done`, `error`). Both sides of the exchange are saved when the stream finishes; nothing is saved if it fails.
- **Dice checks**: When an action's outcome is uncertain and failure would matter (sneaking, persuading, spotting something hidden), Claude calls the `roll_check` tool with a stat, a difficulty and a reason. The server rolls a d20 and adds the stat, and the action passes if the total meets the target: easy 10, medium 15, hard 20 (ties pass). The result streams to the browser as a `roll` event, which the frontend animates before revealing the narration. Claude must narrate failures as failures. At most one roll per turn, and rolls are not stored.
- **Campaign memory (RAG)**: After each turn, a background task asks Claude to extract NPCs, locations, items and events from the exchange, embeds them with Voyage AI (`voyage-3.5`, 1024 dimensions), and upserts them into pgvector tables per campaign. Before each turn, the DM's last reply plus the player's message are embedded as a search query, and a cosine-similarity search pulls up to 3 close matches of each kind from that campaign (cutoff: cosine distance 0.6). The matches go into the DM's prompt as "What You Remember", including secrets the player has uncovered, so the DM stays consistent with what the player knows and characters' lies can be caught. If the lookup fails, the turn continues without memories.
- **Limits on Claude calls**: Turns, character previews and campaign creation are limited per user (per minute and per rolling 24 hours) and for everyone together (per 24 hours), so one player, or many free Discord accounts, can't run up the API bill. Defaults: turns 10/min, 300/day, 3,000/day overall; previews 5/min, 30/day, 300/day overall; campaigns 2/min, 10/day, 100/day overall (`src/services/usage_service.py:LIMITS`). Over a limit, the route answers 429 with `Retry-After` and a message for the player. Each accepted call is a row in `llmusage`, so limits hold across restarts; a call counts even if Claude then fails.
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
evals/          memory evals against real Claude/Voyage (see Evals); results/ is git-ignored
```

## API

All routes except `/health` and `/auth/discord/callback` need the `dungeon_session` cookie (`Authorization: Bearer` is not accepted). Data-changing requests also need `X-Requested-With: dungeon-web`, or they get a 403. Routes only return the signed-in user's data.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/discord/callback` | Exchange a Discord OAuth code; sets the session cookie and returns the user |
| GET | `/auth/me` | The signed-in user (`id`, `username`, `avatar_url`) |
| POST | `/auth/logout` | End every session for the user and clear the cookie |
| GET | `/characters/` | Your characters, each with its campaign |
| POST | `/characters/` | Save a character: send `{preview_token}` from `/characters/preview`; the server saves the sheet it generated and signed (stats are never chosen by the client), sets the owner, and only campaign creation puts a character in a campaign |
| POST | `/characters/preview` | Generate a character sheet without saving, with a `preview_token` (signed for you, valid 1 hour) to save it |
| GET | `/characters/classes` | List classes |
| GET | `/characters/races` | List races |
| GET | `/characters/{id}` | One of your characters |
| GET | `/characters/{id}/turns` | Message history for your character |
| POST | `/characters/{id}/turns/stream` | Play a turn (SSE: `thinking`, `roll`, `text`, `done`, `error`) |
| GET | `/campaigns/` | Your campaigns, each with your characters in it and its checkpoints in order |
| POST | `/campaigns/` | Generate and save a campaign for one of your characters |
| GET | `/campaigns/{id}/characters` | Your characters in a campaign |
| DELETE | `/campaigns/{id}` | Delete one of your campaigns with its checkpoints, history and memories; its characters are kept and freed (404 if it is not yours) |
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
DUNGEON_ANTHROPIC_API_KEY=
VOYAGE_API_KEY=
DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/dungeon_pg_db
POSTGRES_USER=
POSTGRES_PASSWORD=
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_REDIRECT_URI=
SECRET_KEY=
```

All of these are required; the app fails at startup if any is missing. Optional: `COOKIE_SECURE=false` drops the cookie's Secure flag (not needed for `http://localhost`, which browsers treat as secure). If the frontend is ever served from a different site than the API, the cookie and CORS settings must change (today the frontend proxies `/api` so both are same-origin). The Claude key is named `DUNGEON_ANTHROPIC_API_KEY`, not `ANTHROPIC_API_KEY`, so it doesn't clash with Claude Code, which reads that name itself. `SECRET_KEY` must be at least 32 bytes (the app refuses to start otherwise): `python3 -c 'import secrets; print(secrets.token_hex(32))'`.

Then:

```bash
uv sync
make lr        # start postgres + run flyway migrations/seeds, then uvicorn --reload on :8000
make lr-down   # stop and wipe the local db
```

`make dr` / `make dr-down` run the whole stack, API included, in Docker.

Optional settings: `DB_ECHO=true` logs every SQL statement (players' story text included; off by default), `API_DOCS=false` hides `/docs` and `/openapi.json` (on by default, since the frontend's `generate-types` reads it), `COOKIE_SECURE=false` drops the cookie's Secure flag.

Game content (classes, races, the checkpoints campaigns are built from) is a migration (`V5__game_content.sql`) and loads everywhere. `db/seeds` holds only local test data (`seed_user` and its campaigns) and is never loaded in production.

## Deploying

`infra/prod/` runs the app on one server with Docker Compose: Caddy (HTTPS, the built frontend, `/api` proxy) is the only thing exposed; the API and Postgres have no published ports. [`infra/prod/DEPLOY.md`](./infra/prod/DEPLOY.md) walks through it from buying the domain and hardening the server to backups and updates.

## Development

```bash
uv run pytest                              # no DB or API keys used; .env must exist
uv run ruff check . && uv run ruff format .
uv run mypy src
```

## Evals

Unit tests mock Claude and Voyage. Evals call them for real and measure how well campaign memory works, so they cost money and their results vary between runs. Run them when you change something they measure (the extraction or DM prompt, `MEMORIES_PER_KIND` / `MAX_COSINE_DISTANCE`, the embedding text, or a model), and compare against an earlier run. Each writes its inputs, what was retrieved, outputs and scores to `evals/results/` (git-ignored).

A Voyage account with no payment method is limited to 3 requests a minute. The retrieval eval makes two requests per run; for the recall scenario pass `--voyage-rpm 3` (about 15 minutes), or a rate-limited lookup is skipped and scores as the DM forgetting.

| Eval | What it measures | Needs | Cost |
| --- | --- | --- | --- |
| `uv run python -m evals.retrieval` | Whether player turns recall the memories they should from a fixed set (`evals/retrieval_cases.json`), with rank and cosine distance. `--k` / `--max-distance` try other limits. Runs in a rolled-back transaction | DB, Voyage | Fractions of a cent |
| `uv run python -m evals.extraction` | Whether Claude stores the right facts from scripted exchanges (`evals/extraction_cases.json`), as a pass rate per check over `--runs` | Claude | One call per case per run |
| `uv run python -m evals.recall_scenario --scenario <name>` | End to end: plant a clue, play 25 filler exchanges through real extraction, then probe (5 times, `--probes` for more). Reports whether the clue reached the DM's prompt, whether the reply mentions it (and whether it should), and whether a Claude grader passes the reply against the scenario's rubric. Scenarios in `evals/scenarios/`: `ashford_liar` (a letter and a witness break a steward's alibi), `ashford_control` (same campaign, probing an honest witness: the DM must not treat him as a liar or drag in the evidence), `silk_merchant` (a second mystery: a staged robbery the liar repeats to someone else). Creates and deletes its own campaign (`--keep` to inspect it) | DB, Claude, Voyage | About 40 calls per scenario |

## Roadmap

- Tune memory retrieval (per-kind limit, distance cutoff) from real play
- Memory extraction: store what a character says as a claim ("Says...", "Claims..."), never as a plain fact. The `silk_merchant` recall scenario scores 1-2/10 because the liar's robbery story is stored as a known fact next to the secret that he lied, and the DM lets the lie pass when he repeats it to someone else. Re-run `silk_merchant` and `ashford_control` after the change. (The wording fix on branch `claude/dm-notices-overheard-lies` did not help.)
- Remove duplicate facts when merging a known NPC's record (an alibi can end up stored twice)
- Checkpoint progression: detect when an objective is done, summarize it, move to the next checkpoint
- Tune how often the DM calls for rolls, based on real play

## Known gaps

- `llmusage` rows are never pruned; only the last 24 hours are read, so old rows can be deleted at any time
- Two simultaneous requests can both pass a limit check that only one should (no lock); fine for per-minute bursts, at most a request or two over
- `mypy src` reports one existing error: `pgvector.sqlalchemy` ships no type stubs (`models/memory.py`)
- Saving a turn runs synchronously inside the stream; fine for a few players, not for many at once
- The DM's stat and difficulty choices are limited by the tool schema but not re-checked on the server
