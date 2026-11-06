-- Combat: hit points on characters, a bestiary of enemy types, and encounters.
-- The server owns every number in a fight. The DM picks enemies from the bestiary
-- (start_encounter tool) and narrates; combat_service rolls and applies damage.

-- Hit points. max_hp comes from endurance (combat_service.max_hp_for: 10 + 2 x END).
-- A character at 0 HP is dead for good (died_at set); the row is kept. The default
-- (average endurance) only covers inserts that don't set HP, like the local seed
-- file, which sets the real values after; the app always sets both.
ALTER TABLE character ADD COLUMN max_hp INTEGER DEFAULT 20;
ALTER TABLE character ADD COLUMN current_hp INTEGER DEFAULT 20;
ALTER TABLE character ADD COLUMN died_at TIMESTAMPTZ;
UPDATE character SET max_hp = 10 + 2 * COALESCE(endurance, 5);
UPDATE character SET current_hp = max_hp;
ALTER TABLE character ALTER COLUMN max_hp SET NOT NULL;
ALTER TABLE character ALTER COLUMN current_hp SET NOT NULL;
ALTER TABLE character ADD CONSTRAINT character_hp_in_range
    CHECK (max_hp > 0 AND current_hp BETWEEN 0 AND max_hp);

-- Enemy types, shared game content like checkpoints. `key` is what the DM names in
-- start_encounter. An attack hits when d20 + attack_bonus >= the target's defense,
-- and deals damage_dice d damage_die + damage_bonus.
CREATE TABLE enemy (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    tier INTEGER NOT NULL CHECK (tier BETWEEN 1 AND 3), -- 1 minion, 2 fighter, 3 boss
    max_hp INTEGER NOT NULL CHECK (max_hp > 0),
    defense INTEGER NOT NULL,
    attack_bonus INTEGER NOT NULL,
    damage_dice INTEGER NOT NULL CHECK (damage_dice > 0),
    damage_die INTEGER NOT NULL CHECK (damage_die > 1),
    damage_bonus INTEGER NOT NULL DEFAULT 0
);

-- One fight. status: active, won (every enemy down), fled, lost (character died).
CREATE TABLE encounter (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaign(id),
    character_id INTEGER NOT NULL REFERENCES character(id),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'won', 'fled', 'lost')),
    round INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);
-- A character is in at most one fight at a time.
CREATE UNIQUE INDEX encounter_one_active_per_character
    ON encounter (character_id) WHERE status = 'active';
CREATE INDEX encounter_campaign ON encounter (campaign_id);

-- An enemy in a fight, with its own name ("Goblin 2", or one the DM gave it) and HP.
CREATE TABLE combatant (
    id SERIAL PRIMARY KEY,
    encounter_id INTEGER NOT NULL REFERENCES encounter(id) ON DELETE CASCADE,
    enemy_id INTEGER NOT NULL REFERENCES enemy(id),
    name TEXT NOT NULL,
    position INTEGER NOT NULL,
    max_hp INTEGER NOT NULL CHECK (max_hp > 0),
    current_hp INTEGER NOT NULL CHECK (current_hp BETWEEN 0 AND max_hp)
);
CREATE INDEX combatant_encounter ON combatant (encounter_id);

-- The bestiary. A character with average stats (5) has 20 HP, defense 12 and hits
-- defense 11 three times in four; a goblin falls in about two hits, an ogre takes six.
INSERT INTO enemy (key, name, description, tier, max_hp, defense, attack_bonus, damage_dice, damage_die, damage_bonus) VALUES
('giant_rat',      'Giant Rat',      'A dog-sized rat with yellow teeth, bold in packs.',                                 1,  4, 10, 2, 1, 4, 0),
('goblin',         'Goblin',         'A small, wiry raider with a rusty blade. Brave in numbers, quick to run.',          1,  7, 11, 3, 1, 6, 0),
('goblin_archer',  'Goblin Archer',  'A goblin with a short bow who keeps its distance.',                                 1,  6, 11, 4, 1, 6, 0),
('skeleton',       'Skeleton',       'Animated bones in rotted mail, tireless and silent.',                               1,  9, 12, 3, 1, 6, 1),
('cultist',        'Cultist',        'A robed zealot with a curved dagger and nothing left to lose.',                    1,  9, 11, 3, 1, 6, 0),
('wolf',           'Wolf',           'A lean grey hunter that circles and lunges for the legs.',                          1, 11, 12, 4, 2, 4, 0),
('bandit',         'Bandit',         'A desperate road thief with a club or short sword.',                                1, 11, 12, 3, 1, 6, 1),
('zombie',         'Zombie',         'A shambling corpse, slow but hard to put down.',                                    1, 16, 9,  3, 1, 6, 1),
('giant_spider',   'Giant Spider',   'A horse-sized spider whose bite carries a numbing venom.',                         2, 18, 13, 5, 1, 8, 1),
('orc_warrior',    'Orc Warrior',    'A scarred, heavily muscled fighter with a cleaver-like axe.',                      2, 20, 13, 5, 1, 10, 2),
('bandit_captain', 'Bandit Captain', 'The leader of a bandit crew: a duellist in a stolen breastplate.',                 2, 24, 14, 5, 1, 8, 2),
('wraith',         'Wraith',         'A cold shadow of a dead lord whose touch drains warmth and strength.',             2, 22, 13, 5, 2, 6, 0),
('werewolf',       'Werewolf',       'A cursed hunter in half-beast form, all claws and fury.',                          3, 32, 14, 6, 2, 6, 2),
('ogre',           'Ogre',           'A hulking brute with a tree-trunk club. Slow-witted, devastating when it connects.', 3, 38, 11, 6, 2, 8, 3),
('troll',          'Troll',          'A gangly, rubbery giant whose wounds close as you watch.',                         3, 44, 13, 7, 2, 6, 4),
('young_dragon',   'Young Dragon',   'A dragon no bigger than a carthorse, already proud, cunning and armoured.',        3, 55, 16, 8, 2, 10, 3);
