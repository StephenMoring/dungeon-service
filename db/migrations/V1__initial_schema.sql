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
