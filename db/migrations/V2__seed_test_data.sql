-- Checkpoints
INSERT INTO checkpoint (title, description, setting, key_npcs, objective, tags) VALUES
(
    'The Collapsed Bridge',
    'A once-sturdy stone bridge has crumbled into a ravine. Desperate refugees are stranded on the far side, and something lurks in the darkness below.',
    'A crumbling stone bridge over a deep forested ravine at dusk',
    'Sister Maren, a healer tending the wounded; Grak, a troll who claims the ravine as his toll road',
    'Find a way to cross the ravine and escort the refugees to safety',
    'exploration,puzzle,social,troll,wilderness'
),
(
    'The Burning Village',
    'Smoke rises on the horizon. A farming village is under attack by a raiding warband. The villagers are outmatched and fleeing in panic.',
    'A small rural village with several buildings ablaze, surrounded by rolling farmland',
    'Aldric the farmer, protecting his family; Vorra, the warband captain seeking something specific',
    'Drive off the raiders and discover what they were actually searching for',
    'combat,rescue,investigation,fire,urgent'
),
(
    'The Whispering Tomb',
    'An ancient tomb has been unsealed by grave robbers who never returned. Locals report hearing voices at night. The dead are restless.',
    'A moss-covered stone tomb set into a hillside, its iron doors hanging open',
    'The ghost of Lord Edwyn, bound to the tomb by an unresolved betrayal',
    'Uncover the betrayal that binds the ghost and put the dead to rest',
    'undead,dungeon,horror,mystery,ghost'
),
(
    'The Merchant''s Debt',
    'A wealthy merchant has hired the party under false pretenses. The cargo they''re guarding is stolen, and its original owners are closing in.',
    'A winding mountain road, a heavily loaded merchant wagon, and riders approaching fast',
    'Cassius Brent, the sweating merchant with too many secrets; the Ironveil trading house enforcers',
    'Decide who to side with and survive the confrontation on the mountain pass',
    'social,intrigue,moral-choice,ambush,travel'
),
(
    'Lair of the Scaled King',
    'A young dragon has made its lair in an abandoned silver mine, and it has developed a taste for the nearby town''s livestock — and its people.',
    'A collapsed mine entrance in a rocky hillside, bones scattered at the threshold',
    'Skarrix, an arrogant but not entirely evil young dragon with a grudge',
    'Negotiate, drive out, or slay the dragon before it attacks the town again',
    'boss,dragon,combat,negotiation,dungeon'
),
(
    'The Flooded Crypts',
    'Spring floods have broken through into the city''s ancient burial crypts. Something has escaped from the sealed lower chambers.',
    'Ankle-deep murky water in low stone corridors, torchlight reflecting off the surface',
    NULL,
    'Navigate the flooded crypts, reseal the lower chambers, and deal with whatever got out',
    'dungeon,undead,exploration,horror,urban'
),
(
    'Festival of Masks',
    'The city''s annual masquerade festival is the perfect cover for an assassination plot. The target is attending — and so is the killer.',
    'A grand ballroom filled with masked nobles, musicians, and hidden daggers',
    'Lady Voss, the target who knows she is in danger; the Pale Hand, a masked assassin guild',
    'Identify the assassin among hundreds of masked guests before the midnight bell',
    'intrigue,social,investigation,urban,stealth'
),
(
    'The Giant''s Causeway',
    'A stone giant is methodically destroying a trade road, boulder by boulder. It isn''t attacking people — it''s building something. Nobody knows what.',
    'A ruined section of cobbled road, massive stone blocks rearranged into a strange pattern',
    'Thurm, a stone giant who does not speak the common tongue but is clearly distressed',
    'Discover why the giant is destroying the road and find a resolution without bloodshed',
    'social,puzzle,giant,wilderness,non-combat'
),
(
    'Shipwreck at Daggerpoint',
    'A ship has run aground on a notorious reef. Survivors cling to the wreckage. So does something that was locked in the cargo hold.',
    'Sharp black rocks, crashing waves, a listing merchant vessel slowly breaking apart',
    'Captain Rhen, injured but commanding; an unnamed creature sealed in a iron-banded crate',
    'Rescue the survivors and decide what to do with the creature in the hold',
    'rescue,horror,coastal,exploration,moral-choice'
),
(
    'The Poisoned Well',
    'The village''s only water source has been deliberately poisoned. People are sick. Someone in the village did it — but the motive is unclear.',
    'A quiet village with a central well, shuttered windows, and suspicious eyes',
    'Healer Brix, overwhelmed and desperate; multiple villagers with possible motives',
    'Identify who poisoned the well and why before more people die',
    'investigation,mystery,social,urban,poison'
),
(
    'Siege at Thornwall Keep',
    'A small keep is under siege by an army of hobgoblins with siege weapons. The garrison is down to twenty soldiers and three days of food.',
    'A battered stone keep on a hill, surrounded by a disciplined hobgoblin encampment',
    'Commander Aldis, grimly determined; General Mokk, the methodical hobgoblin commander',
    'Break the siege — through reinforcements, sabotage, negotiation, or a desperate sortie',
    'combat,military,siege,boss,strategy'
),
(
    'The Cartographer''s Map',
    'A dying explorer has given the party a map to something extraordinary. Three other groups received the same map. The race has begun.',
    'Competing camps along a jungle trail, tension rising as everyone moves toward the same destination',
    'Expedition rivals with varying levels of willingness to play dirty',
    'Reach the map''s destination first — and deal with what''s there',
    'exploration,rival,wilderness,race,dungeon'
),
(
    'Night of the Red Moon',
    'Once a generation, the red moon rises and lycanthropes lose all control. Tonight is that night, and the party is in a city that doesn''t know.',
    'A crowded city at dusk, lanterns being lit, citizens unaware of what is coming',
    'Wren, a cursed city guard fighting to warn people; the city watch captain who won''t believe it',
    'Warn the city, protect civilians, and survive until dawn',
    'horror,urban,combat,werewolf,urgent'
),
(
    'The Sunken Temple',
    'Coastal tides have receded unusually far, revealing the roof of a submerged temple. Scholars say it has been underwater for three hundred years.',
    'A barnacle-crusted temple entrance in a tidal flat, water still draining from inside',
    NULL,
    'Explore the temple before the tides return, and retrieve what lies in the innermost chamber',
    'exploration,dungeon,aquatic,puzzle,timed'
),
(
    'A Debt of Blood',
    'A crime lord has called in a favour the party owes. The job: break someone out of a well-guarded prison. The prisoner''s crime is unclear.',
    'A fortified city prison with rotating guard shifts and multiple locked wings',
    'Madame Vex, the crime lord with leverage; the prisoner, whose story may change everything',
    'Complete the extraction — and decide what to do once you learn who the prisoner really is',
    'heist,stealth,urban,moral-choice,intrigue'
),
(
    'The Wandering Lighthouse',
    'Ships have been disappearing along a coastline that''s been safe for decades. Survivors speak of a lighthouse that appears where no lighthouse should be.',
    'A cliff-top lighthouse in the wrong location, its beam sweeping across a foggy sea',
    'The Keeper, an ancient figure who may not be entirely human',
    'Discover the truth behind the lighthouse and stop the disappearances',
    'mystery,horror,coastal,investigation,supernatural'
),
(
    'Crown Without a Head',
    'The king is dead and no one will admit it. Three factions are maneuvering for power while the body is kept on ice. The city is three days from civil war.',
    'A royal palace locked down under the pretense of the king''s illness, full of scheming nobles',
    'The queen regent with her own agenda; the spymaster who knows too much',
    'Navigate the power struggle and prevent the city from tearing itself apart',
    'intrigue,political,social,investigation,urban'
),
(
    'The Frostbound Pass',
    'A mountain pass essential for winter trade has been blocked by an unnatural blizzard that doesn''t move. People are freezing on both sides.',
    'A mountain pass choked with snow, wind that cuts through armour, and a stillness at the centre',
    'A frost spirit bound to the location by a long-forgotten bargain',
    'Find the source of the unnatural storm and end it before both communities are cut off for winter',
    'exploration,supernatural,wilderness,puzzle,cold'
),
(
    'Bones of the Old God',
    'Miners have unearthed bones of impossible size — and a cult has arrived to excavate them properly. The bones are doing something to people nearby.',
    'A deep mining operation in rocky hills, cultists setting up camp, miners looking wrong',
    'Overseer Dann, trying to keep his workers safe; the Cult Archivist who believes this is sacred',
    'Stop the excavation or control it — before whatever is in those bones fully wakes',
    'horror,cult,boss,investigation,supernatural'
),
(
    'The Last Inn',
    'There is only one inn for fifty miles, and it''s full of people who all seem to be waiting for something. None of them will say what.',
    'A warm but tense roadside inn during a storm, no one leaving, everyone watching the door',
    'The innkeeper who knows exactly what is happening; a dozen guests with a shared secret',
    'Uncover what everyone is waiting for — and survive the night when it arrives',
    'mystery,social,horror,investigation,enclosed'
);

-- Characters
INSERT INTO character (name, hero_class, biography, description, age, campaign_id, strength, perception, endurance, charisma, intelligence, agility, luck) VALUES
(
    'Darian Ashveil',
    'Rogue',
    'Darian grew up picking pockets in the port city of Calrath, eventually graduating to larger scores for a thieves'' guild that taught him everything before betraying him. He left the city with nothing but his knives and a long memory.',
    'A lean, sharp-eyed man with close-cropped dark hair and a habit of sitting with his back to walls. Quick with a smile that rarely reaches his eyes.',
    31,
    NULL,
    4, 8, 5, 7, 6, 9, 7
),
(
    'Bryndis Ironmantle',
    'Warrior',
    'Bryndis served fifteen years as a shield-bearer in the northern legions before a political purge forced her out with a scar and a grudge. She now sells her sword to causes that feel worth bleeding for.',
    'A broad-shouldered woman with iron-grey hair worn in tight braids, a shield strapped to her back, and the measured movements of someone who has survived too many battles to be careless.',
    42,
    NULL,
    9, 6, 8, 5, 4, 5, 4
),
(
    'Sollux of the Amber Eye',
    'Mage',
    'Sollux studied at the Conclave of Veth for twelve years before his experiments attracted the wrong kind of attention and his licence to practice was revoked. He has since learned that understanding magic and following its rules are different things.',
    'A tall, distracted man in his mid-thirties with mismatched eyes — one brown, one an unsettling amber — and ink-stained fingers that are rarely still.',
    35,
    NULL,
    3, 7, 4, 5, 10, 6, 5
),
(
    'Fenn Brackenwood',
    'Ranger',
    'Fenn was raised in a logging community on the edge of a vast old-growth forest that the community slowly destroyed. He chose the forest. He has not spoken to his family since.',
    'A quiet, weathered young man who moves without sound and watches without seeming to. Dressed in earthy browns and greens, with a shortbow always within reach and an expression that is more comfortable with trees than people.',
    24,
    NULL,
    6, 9, 7, 3, 6, 8, 5
),
(
    'Celestine Varro',
    'Cleric',
    'Celestine was a promising novice at the Temple of the Pale Dawn until a crisis of faith drove her into the streets, where she found the goddess was easier to believe in when people actually needed saving. She carries her holy symbol like a question she hasn''t answered yet.',
    'A composed woman in her late twenties with careful posture and kind eyes that miss very little. Her robes are well-worn and her hands are practiced at both prayer and bandaging wounds.',
    28,
    NULL,
    5, 6, 6, 8, 7, 5, 6
);
