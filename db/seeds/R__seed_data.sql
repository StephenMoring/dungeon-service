-- Local test data only (never loaded in production): a seed user with campaigns
-- and characters. Game content (classes, races, checkpoints) is in
-- db/migrations/V5__game_content.sql. Re-runs reset only this test data.
TRUNCATE TABLE campaigncheckpoint, character, campaign, "user" RESTART IDENTITY CASCADE;

-- Seed user
INSERT INTO "user" (discord_id, username, avatar_url) VALUES
('000000000000000001', 'seed_user', NULL);

-- Campaigns
INSERT INTO campaign (name, theme, description) VALUES
(
    'Shadows Over Calrath',
    'A city of masks where every alliance is a transaction and every secret is a weapon',
    'The port city of Calrath hums with festival lights and whispered deals. Beneath the masquerade, a power struggle is pulling the city toward civil war — and the party is already owed by the wrong people. This is a campaign of intrigue, heists, and moral compromise in a city that rewards cunning over conscience.'
),
(
    'The Darkening North',
    'Something old and hungry is waking in the northern reaches, and the living are running out of time',
    'The northern villages are burning or going quiet. Refugees speak of dead things walking, moons running red, and a darkness spreading from somewhere deep in the hills. This is a campaign of survival horror and hard choices, where the enemy does not negotiate and help is far away.'
),
(
    'The Lost Horizon',
    'A race across the world''s edge to claim something that was never meant to be found',
    'A dying explorer''s map has set three factions on a collision course across uncharted wilderness, submerged ruins, and frozen passes. The destination promises power or catastrophe — possibly both. This is a campaign of exploration, discovery, and the creeping sense that some things were buried for good reason.'
);

-- Characters
INSERT INTO character (name, hero_class, biography, description, age, campaign_id, user_id, strength, perception, endurance, charisma, intelligence, agility, luck) VALUES
(
    'Darian Ashveil',
    'Rogue',
    'Darian grew up picking pockets in the port city of Calrath, eventually graduating to larger scores for a thieves'' guild that taught him everything before betraying him. He left the city with nothing but his knives and a long memory.',
    'A lean, sharp-eyed man with close-cropped dark hair and a habit of sitting with his back to walls. Quick with a smile that rarely reaches his eyes.',
    31, 1, 1,
    4, 8, 5, 7, 6, 9, 7
),
(
    'Bryndis Ironmantle',
    'Warrior',
    'Bryndis served fifteen years as a shield-bearer in the northern legions before a political purge forced her out with a scar and a grudge. She now sells her sword to causes that feel worth bleeding for.',
    'A broad-shouldered woman with iron-grey hair worn in tight braids, a shield strapped to her back, and the measured movements of someone who has survived too many battles to be careless.',
    42, 2, 1,
    9, 6, 8, 5, 4, 5, 4
),
(
    'Sollux of the Amber Eye',
    'Mage',
    'Sollux studied at the Conclave of Veth for twelve years before his experiments attracted the wrong kind of attention and his licence to practice was revoked. He has since learned that understanding magic and following its rules are different things.',
    'A tall, distracted man in his mid-thirties with mismatched eyes — one brown, one an unsettling amber — and ink-stained fingers that are rarely still.',
    35, 3, 1,
    3, 7, 4, 5, 10, 6, 5
),
(
    'Fenn Brackenwood',
    'Ranger',
    'Fenn was raised in a logging community on the edge of a vast old-growth forest that the community slowly destroyed. He chose the forest. He has not spoken to his family since.',
    'A quiet, weathered young man who moves without sound and watches without seeming to. Dressed in earthy browns and greens, with a shortbow always within reach and an expression that is more comfortable with trees than people.',
    24, 2, 1,
    6, 9, 7, 3, 6, 8, 5
),
(
    'Celestine Varro',
    'Cleric',
    'Celestine was a promising novice at the Temple of the Pale Dawn until a crisis of faith drove her into the streets, where she found the goddess was easier to believe in when people actually needed saving. She carries her holy symbol like a question she hasn''t answered yet.',
    'A composed woman in her late twenties with careful posture and kind eyes that miss very little. Her robes are well-worn and her hands are practiced at both prayer and bandaging wounds.',
    28, 1, 1,
    5, 6, 6, 8, 7, 5, 6
);

-- Hit points from endurance, as combat_service.max_hp_for sets them.
UPDATE character SET max_hp = 10 + 2 * COALESCE(endurance, 5), current_hp = 10 + 2 * COALESCE(endurance, 5);

-- Campaign 1 checkpoints: Festival of Masks → A Debt of Blood → Crown Without a Head
INSERT INTO campaigncheckpoint (campaign_id, checkpoint_id, "order", status) VALUES
(1, 7,  0, 'new'),
(1, 15, 1, 'locked'),
(1, 17, 2, 'locked');

-- Campaign 2 checkpoints: The Burning Village → The Whispering Tomb → Night of the Red Moon → The Last Inn
INSERT INTO campaigncheckpoint (campaign_id, checkpoint_id, "order", status) VALUES
(2, 2,  0, 'new'),
(2, 3,  1, 'locked'),
(2, 13, 2, 'locked'),
(2, 20, 3, 'locked');

-- Campaign 3 checkpoints: The Cartographer's Map → The Sunken Temple → The Frostbound Pass → Bones of the Old God
INSERT INTO campaigncheckpoint (campaign_id, checkpoint_id, "order", status) VALUES
(3, 12, 0, 'new'),
(3, 14, 1, 'locked'),
(3, 18, 2, 'locked'),
(3, 19, 3, 'locked');
