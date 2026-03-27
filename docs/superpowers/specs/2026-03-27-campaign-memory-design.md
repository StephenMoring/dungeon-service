# Campaign Memory System Design

**Date:** 2026-03-27
**Status:** Approved
**Author:** Design session with Claude

---

## Problem

The current turn system loads the last 10 raw messages from `message_history` and passes them
directly to the LLM. This gives the DM a short-term memory of roughly the last 5 exchanges —
anything older is gone. In practice this means the DM forgets specific facts (items found,
secrets shared, deals struck, NPC names) within minutes of play.

The root cause: raw message history is a poor memory format. It's noisy, verbose, and entirely
linear. There's no way to ask "what do I know about this NPC?" without reading everything.

---

## Goals

- The DM remembers specific narrative facts across the full length of a campaign
- Facts are scoped per-campaign — no cross-contamination between users or sessions
- Memory is built up automatically as play progresses, without player intervention
- A foundation of world knowledge is established at campaign creation time
- The player can eventually build features on top (a journal, lore log, etc.)

---

## Non-Goals (for now)

- Rolling narrative summaries (Option C) — good future addition, not needed for V1
- RAG on raw message history — not worth complexity on top of structured extraction
- A player-facing memory UI

---

## Core Concepts

Before getting into the design, it helps to understand the two ideas the whole system is built on.

### What is an embedding?

An embedding is a way of turning text into a list of numbers (a vector) such that texts with
similar *meaning* end up with vectors that are mathematically close to each other. A sentence
about a friendly blacksmith and a sentence about a helpful armorer will have similar vectors,
even though they share no words.

You generate embeddings by sending text to an embedding model API (e.g. Voyage AI's `voyage-3`
or OpenAI's `text-embedding-3-small`). The API returns a list of ~1000 floating point numbers.
You store this alongside your data.

The embedding doesn't encode the *meaning* for you to read — it's just a compressed
representation that lets you measure similarity mathematically.

### What is vector similarity search?

Once you have embeddings, you can find the most relevant records to a query by:

1. Embedding the query text (e.g. the player's current message)
2. Comparing that query vector against all stored vectors using cosine similarity
3. Returning the top-K most similar records

Cosine similarity measures the angle between two vectors — 1.0 means identical direction
(very similar meaning), 0.0 means orthogonal (unrelated). This is how you ask "what stored
facts are most relevant to what the player just said?" without keyword matching.

**pgvector** is a PostgreSQL extension that stores vector columns and runs these similarity
queries natively in SQL, so you don't need a separate vector database.

---

## Architecture

The system has three new concerns layered on top of the existing turn flow:

```
Campaign creation
    └── seed_campaign_memories()     ← extracts initial NPCs, locations, facts from description + checkpoints

Each turn (existing flow)
    ├── retrieve_relevant_memories() ← embed player message, similarity search memory tables
    ├── build_turn_system_prompt()   ← inject retrieved memories as "World Knowledge" block
    ├── process_turn()               ← LLM call (unchanged)
    └── [background] extract_and_store_memories() ← extract new facts from the just-completed turn
```

The existing message window (last 10 messages) stays for short-term continuity.
The memory tables handle long-term facts.

---

## Database Schema

### Enable pgvector

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

This is a one-line migration. After this, you can use `vector(N)` as a column type, where N is
the number of dimensions your embedding model produces. Voyage AI's `voyage-3` produces 1024
dimensions. OpenAI's `text-embedding-3-small` produces 1536.

### Memory tables

All four tables follow the same pattern: structured fields for the fact itself, plus an
`embedding` column for similarity search, plus `campaign_id` as the tenant boundary.

```sql
CREATE TABLE npc_memory (
    id              SERIAL PRIMARY KEY,
    campaign_id     INTEGER NOT NULL REFERENCES campaign(id),
    name            TEXT NOT NULL,
    role            TEXT,                  -- e.g. "blacksmith", "villain", "quest-giver"
    disposition     TEXT,                  -- e.g. "friendly", "hostile", "neutral", "unknown"
    known_facts     TEXT,                  -- what the player knows: backstory, what they said
    secrets         TEXT,                  -- deals struck, hidden allegiances, things confided
    embedding       vector(1024),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE location_memory (
    id              SERIAL PRIMARY KEY,
    campaign_id     INTEGER NOT NULL REFERENCES campaign(id),
    name            TEXT NOT NULL,
    description     TEXT,
    events          TEXT,                  -- what happened here: discoveries, fights, conversations
    embedding       vector(1024),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE item_memory (
    id              SERIAL PRIMARY KEY,
    campaign_id     INTEGER NOT NULL REFERENCES campaign(id),
    name            TEXT NOT NULL,
    description     TEXT,
    where_found     TEXT,
    status          TEXT DEFAULT 'held',   -- "held", "lost", "used", "given away"
    embedding       vector(1024),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE event_memory (
    id              SERIAL PRIMARY KEY,
    campaign_id     INTEGER NOT NULL REFERENCES campaign(id),
    summary         TEXT NOT NULL,         -- plain language description of what happened
    category        TEXT,                  -- "decision", "revelation", "deal", "consequence"
    embedding       vector(1024),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

**Why four tables instead of one?** You could store everything in one `memory` table with a
`type` column, but typed tables let you query selectively (e.g. "only NPCs"), add
type-specific fields cleanly, and keep the data easier to reason about. The extraction prompt
also maps naturally to these four categories.

**Why `campaign_id` and not `character_id`?** NPCs, locations, and events belong to the
campaign world — multiple characters in the same campaign share that world. Items are also
stored at campaign level for simplicity, but you could add `character_id` to items later if
you want per-character inventory tracking.

**`updated_at` won't auto-update without a trigger.** The `DEFAULT now()` clause only fires on
`INSERT`. On `UPDATE`, Postgres won't touch `updated_at` unless you explicitly set it. You have
two options: (a) set `updated_at = now()` in your upsert SQL/application code whenever you
update a record, or (b) add a `BEFORE UPDATE` trigger in your migration. Option (a) is simpler
to start with. This matters for staleness detection later (see Open Questions).

### Indexes

```sql
-- B-tree indexes on campaign_id for filtering rows before/after vector search
CREATE INDEX ON npc_memory (campaign_id);
CREATE INDEX ON location_memory (campaign_id);
CREATE INDEX ON item_memory (campaign_id);
CREATE INDEX ON event_memory (campaign_id);

-- HNSW indexes for approximate nearest neighbor search
-- HNSW (Hierarchical Navigable Small World) builds a graph structure at index time
-- that allows very fast approximate similarity search at query time.
-- It trades a small amount of recall accuracy for a large speed gain.
-- For a game, "close enough" is fine — you don't need perfect recall.
CREATE INDEX ON npc_memory      USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON location_memory USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON item_memory     USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON event_memory    USING hnsw (embedding vector_cosine_ops);
```

**A note on how these two indexes interact:** The B-tree index on `campaign_id` and the HNSW
index on `embedding` do not compose into a single combined lookup. When you query
`WHERE campaign_id = $1 ORDER BY embedding <=> $2`, PostgreSQL will typically use the B-tree
to filter rows down to the campaign, then run a sequential vector scan over those filtered rows
(not the HNSW index). At small scale — a game with dozens of campaigns and hundreds of memory
records each — this is completely fine and will be fast. At large scale you'd investigate
pgvector's partitioned indexes or application-level sharding. For now, don't worry about it.

---

## Embedding Service

A thin module (`src/services/embedding_service.py`) responsible for one thing: turning text
into a vector. The rest of the system calls this without knowing or caring which provider is
used.

```python
def embed(text: str) -> list[float]:
    # Call Voyage AI or OpenAI embeddings API
    # Return list of floats (the vector)
    ...
```

**Provider choice:** Voyage AI (`voyage-3`, 1024 dimensions) is Anthropic's recommended
embedding partner. OpenAI's `text-embedding-3-small` (1536 dimensions) is also fine and very
cheap. Either works — just be consistent: whatever dimensionality you pick at setup must match
your `vector(N)` column definitions.

**What text to embed per table:** Concatenate the most meaningful fields into a single string
before embedding. Good defaults:
- `npc_memory`: `f"{name}. {role}. {known_facts}. {secrets}"`
- `location_memory`: `f"{name}. {description}. {events}"`
- `item_memory`: `f"{name}. {description}. Found: {where_found}"`
- `event_memory`: `summary` (already a full sentence)

The goal is that the embedding captures the semantic meaning of the record so that when a
player's message is also embedded, similar records float to the top.

**Why a separate service module?** Embedding providers change. If you abstract this into one
function, switching providers later means changing one file instead of hunting through the
codebase.

---

## Memory Extraction

### The extraction prompt

After each turn (and at campaign creation), you send a structured prompt to Claude asking it
to identify new or updated facts from the provided text. The prompt instructs Claude to return
JSON matching your four categories.

Example extraction prompt structure:

```
You are a memory extraction assistant for a narrative RPG.
Given the following exchange, identify any new or updated facts about:
- NPCs: names, roles, dispositions, what was said, any deals or secrets
- Locations: places mentioned or visited, what happened there
- Items: objects found, given, used, or described
- Events: significant decisions, revelations, or consequences

Return only a JSON object. If nothing new was established in a category, return an empty array.

{
  "npcs": [...],
  "locations": [...],
  "items": [...],
  "events": [...]
}

Exchange:
[user and assistant messages]
```

**Why use the LLM for this instead of regex/parsing?** Narrative text is unstructured.
"The innkeeper pressed a folded note into your hand — 'give this to no one'" contains an item
(the note), an NPC (the innkeeper), a secret (the note's sensitive nature), and possibly an
event (a deal or warning). No keyword matching can reliably extract that. The LLM can.

**Why a separate extraction call instead of asking the DM to return structured data?**
Mixing narrative generation with structured extraction in one prompt degrades both. The DM
prompt is tuned for immersive prose. Extraction is a different cognitive task. Separating them
gives you cleaner outputs from each.

### Async processing with FastAPI BackgroundTasks

FastAPI has a built-in `BackgroundTasks` mechanism. You can schedule a function to run after
the HTTP response is sent, without blocking the player from receiving the DM's reply.

**Important:** `BackgroundTasks` is a FastAPI dependency — it must be declared as a parameter
on the **route handler** in `characters.py`, not on the service function `take_turn()`. FastAPI
only injects dependencies into route handlers. The service layer doesn't know about it.

```python
# characters.py — the route handler (correct placement)
@character_router.post("/{id}/turns")
def play_turn(id, turn_request, session=Depends(...), user=Depends(...), background_tasks: BackgroundTasks):
    result = take_turn(id, turn_request.message, session, user)
    background_tasks.add_task(extract_and_store_memories, result["campaign_id"], ...)
    return result
```

**The background task needs its own database session.** By the time the background task runs,
the FastAPI-injected `Session` from the original request has already been closed and committed.
You cannot pass the request's session into the background task — it's dead. The background
task must open its own session:

```python
def extract_and_store_memories(campaign_id: int, messages: list):
    with Session(engine) as session:   # manages its own lifecycle
        # extraction and upsert logic here
        ...
```

This is consistent with how your existing tool handlers work (see `campaign_tools.py`), which
also manage their own sessions when called outside the request lifecycle.

**Why async?** The extraction LLM call adds ~1-3 seconds of latency. The player doesn't need
to wait for their *next* turn's memory to be ready — they need the DM's *current* response.
Running extraction after the response is returned means zero perceived latency increase.

**Trade-off to be aware of:** If a player sends two messages in rapid succession, the second
turn's memory retrieval might not yet include facts from the first turn's extraction (it's
still running in the background). For a text RPG where players read before responding, this is
almost never a problem in practice.

### Upsert, don't insert

When storing extracted facts, prefer upsert logic — if an NPC named "Aldric" already exists
for this campaign, update their record rather than creating a duplicate. Match on `(campaign_id,
name)` for NPCs and locations. The LLM may reference the same NPC across many turns.

---

## Campaign Creation Seeding

After `create_campaign()` resolves (in `campaign_service.py`), call a seeding function that
runs the same extraction logic against:

- The original campaign description the player provided
- The full text of each selected checkpoint (title, description, objective, key NPCs)

This pre-populates memory with the world's known facts before turn 1:
- The villain and their motivation
- Key locations from the checkpoints
- Quest-givers and allies the story assumes exist
- Any items or artifacts central to the plot

**Why this matters:** Without seeding, the DM starts with no world knowledge and has to
reconstruct it reactively from play. With seeding, the DM "knows" the world from the opening
message — the same way a human DM would have read the adventure module before the session.

The seeding call is synchronous (no BackgroundTasks) — campaign creation is already an async
process from the player's perspective, and you want memory ready before the first turn.

---

## Context Injection at Turn Time

In `turn_service.py`, before calling `build_turn_system_prompt()`:

1. Embed the player's incoming message
2. For each memory table, run a filtered similarity search:
   ```sql
   SELECT name, known_facts, secrets, disposition
   FROM npc_memory
   WHERE campaign_id = $1
   ORDER BY embedding <=> $2
   LIMIT 3
   ```
3. Collect the top results across all four tables (e.g. 3 NPCs, 2 locations, 2 items, 2 events)
4. Format them into a `## World Knowledge` block
5. Pass to `build_turn_system_prompt()` as a new parameter

The system prompt then looks like:

```
[master_system_prompt]
## Active Campaign ...
## Player Character ...
## Current Scenario ...
## World Knowledge
**NPCs**
- Aldric (blacksmith, friendly): Old war veteran. Told you about the hidden passage under the mill. Secretly working for the thieves' guild.
**Items**
- Sealed Note: Found in the tavern. Contents unknown. Aldric warned you to deliver it unopened.
...
```

**Why inject as text rather than structured JSON?** The LLM is a language model — it reasons
better over natural language prose than raw JSON in its context. Format the retrieved facts as
readable sentences.

**Why limit to top 3-5 per category?** Context window space is finite and expensive. You want
the *most relevant* facts, not all facts. The similarity search handles relevance ranking —
trust it to surface what matters for the current moment.

---

## Implementation Order (Suggested)

If you're building this yourself, here's a sequence that lets you test each piece
independently before wiring them together:

1. **Add pgvector to your Postgres setup** — one migration, verify it works locally
2. **Write the embedding service** — a function that calls Voyage/OpenAI and returns a vector. Test it standalone.
3. **Add the four memory tables** — Flyway migration with the schema above
4. **Write the extraction prompt + test it** — call Claude with a sample exchange, check the JSON output. Iterate on the prompt until extraction quality feels good.
5. **Write `memory_service.py`** — `seed_campaign_memories()` and `extract_and_store_memories()`. Test each against a real campaign.
6. **Wire extraction into campaign creation** — call seeding after `create_campaign()` resolves
7. **Write `retrieve_relevant_memories()`** — the similarity query function. Test it returns sensible results.
8. **Wire retrieval into `build_turn_system_prompt()`** — add the World Knowledge block
9. **Wire async extraction into `take_turn()`** — add BackgroundTasks
10. **End-to-end test** — play a campaign for 20+ turns, verify facts persist

---

## Open Questions / Future Work

- **Rolling summary**: Every N turns or on checkpoint completion, summarize the narrative arc into a short paragraph stored on the campaign record. Inject alongside World Knowledge. Cheap to add later.
- **Memory confidence / staleness**: Facts can become outdated (the NPC who was friendly is now hostile). Consider an `updated_at` field and a recency bias in retrieval.
- **Player-facing journal**: The memory tables are already structured data — a `/campaigns/{id}/memory` endpoint could expose them as a readable journal.
- **Checkpoint completion detection**: A related problem — a lightweight classifier call after each turn to detect if the current checkpoint's objective has been met.
