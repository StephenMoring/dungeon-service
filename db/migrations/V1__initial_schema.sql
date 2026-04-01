CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE "user" (
  id SERIAL PRIMARY KEY,
  discord_id TEXT NOT NULL UNIQUE,
  username TEXT NOT NULL,
  avatar_url TEXT,
  created_at TIMESTAMP DEFAULT TIMEZONE('utc', NOW())
);

CREATE TABLE campaign (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    theme TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE character (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    hero_class TEXT NOT NULL,
    biography TEXT NOT NULL,
    description TEXT NOT NULL,
    age INTEGER NOT NULL,
    campaign_id INTEGER REFERENCES campaign(id),
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    strength INTEGER,
    perception INTEGER,
    endurance INTEGER,
    charisma INTEGER,
    intelligence INTEGER,
    agility INTEGER,
    luck INTEGER
);

CREATE TABLE checkpoint (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    setting TEXT NOT NULL,
    key_npcs TEXT,
    objective TEXT NOT NULL,
    tags TEXT NOT NULL
);

CREATE TABLE campaigncheckpoint (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaign(id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoint(id),
    "order" INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'locked',
    summary TEXT
);

CREATE TABLE heroclass (
  id SERIAL PRIMARY KEY,
  class_name TEXT NOT NULL,
  description TEXT NOT NUll
);

CREATE TABLE race (
  id SERIAL PRIMARY KEY,
  race TEXT NOT NULL,
  description TEXT NOT NULL
);

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
