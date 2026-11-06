from src.models.campaign import Campaign
from src.models.memory import EventMemory, ItemMemory, NpcMemory
from src.services.memory_service import RetrievedMemories
from src.services.prompts import (
    KnownNames,
    build_memory_extraction_prompt,
    build_turn_system_prompt,
    format_memories,
    known_context,
    master_system_prompt,
)
from tests.conftest import make_character


def test_prompt_mentions_roll_check():
    assert "roll_check" in master_system_prompt


def test_prompt_drops_soft_rules():
    assert "not strict determiners" not in master_system_prompt
    assert "Story trumps mechanics" not in master_system_prompt


def make_memories() -> RetrievedMemories:
    return RetrievedMemories(
        npcs=[
            NpcMemory(
                campaign_id=1,
                name="Mira the Innkeeper",
                role="quest-giver",
                disposition="friendly",
                known_facts="Runs the Rusty Flagon",
                secrets="Passes traveler movements to the thieves guild",
            )
        ],
        items=[
            ItemMemory(
                campaign_id=1,
                name="Guild Ledger",
                description="Lists payments to Mira",
                where_found="Under the inn's floorboards",
                status="held",
            )
        ],
        events=[
            EventMemory(
                campaign_id=1,
                summary="The player found proof Mira works for the guild",
                category="revelation",
            )
        ],
    )


def test_format_memories_includes_secrets_and_evidence():
    text = format_memories(make_memories())

    assert "## What You Remember" in text
    assert "Mira the Innkeeper" in text
    assert "Passes traveler movements to the thieves guild" in text
    assert "Guild Ledger" in text
    assert "Under the inn's floorboards" in text
    assert "The player found proof Mira works for the guild" in text
    assert "lies" in text


def test_format_memories_skips_empty_kinds():
    text = format_memories(make_memories())

    assert "Locations" not in text


def test_format_memories_empty_is_blank():
    assert format_memories(RetrievedMemories()) == ""


def test_turn_prompt_includes_memories():
    prompt = build_turn_system_prompt(
        make_campaign(), make_character(), None, make_memories()
    )

    assert "## What You Remember" in prompt
    assert "Guild Ledger" in prompt


def test_turn_prompt_without_memories_has_no_section():
    prompt = build_turn_system_prompt(make_campaign(), make_character(), None)

    assert "What You Remember" not in prompt


def make_campaign() -> Campaign:
    return Campaign(id=1, name="Thornwall", theme="gothic", description="d")


def test_extraction_prompt_lists_known_names():
    known = KnownNames(
        npcs=["Aldo Venn", "Old Hesk"], locations=["The Docks"], items=[]
    )

    prompt = build_memory_extraction_prompt("I ask the steward", "Aldo nods.", known)

    assert "Characters: Aldo Venn, Old Hesk" in prompt
    assert "Locations: The Docks" in prompt
    assert "Items: none yet" in prompt
    assert "use the recorded name exactly" in prompt


def test_extraction_prompt_with_nothing_known():
    prompt = build_memory_extraction_prompt("hi", "hello", KnownNames())

    assert "Characters: none yet" in prompt


def test_extraction_prompt_records_caught_lies_on_the_liar():
    prompt = build_memory_extraction_prompt("hi", "hello", KnownNames())

    assert "Lied about" in prompt
    assert "even if they are not in this exchange" in prompt


def test_extraction_prompt_shows_what_was_already_known():
    recalled = RetrievedMemories(
        npcs=[
            NpcMemory(
                campaign_id=1,
                name="Aldo Venn",
                known_facts="Claims he was at the docks the night of the fire",
            )
        ]
    )

    prompt = build_memory_extraction_prompt(
        "Hesk, was anyone from the manor here?",
        "Nobody. Certainly not the steward.",
        KnownNames(npcs=["Aldo Venn"]),
        known_context(recalled),
    )

    assert "Claims he was at the docks the night of the fire" in prompt
    assert prompt.index("Already Known") < prompt.index("## Exchange")


def test_extraction_prompt_without_recalled_memories():
    prompt = build_memory_extraction_prompt("hi", "hello", KnownNames())

    assert "Nothing relevant recalled" in prompt


def test_known_context_is_blank_without_memories():
    assert known_context(None) == ""
    assert known_context(RetrievedMemories()) == ""


def test_memories_tell_the_dm_to_show_what_the_player_knows():
    memories = RetrievedMemories(
        npcs=[
            NpcMemory(campaign_id=1, name="Aldo Venn", secrets="Lied about the docks")
        ]
    )

    section = format_memories(memories)

    # A repeated lie must not read as unchallenged, but the player decides what to do.
    assert "repeats a claim the player has evidence against" in section
    assert "never decide for the player" in section


class TestCombatPrompts:
    def test_dm_is_told_to_start_fights_with_the_tool(self):
        assert "start_encounter" in master_system_prompt
        assert "death is permanent" in master_system_prompt

    def test_turn_prompt_shows_health(self):
        campaign = Campaign(id=1, name="c", theme="t", description="d")
        character = make_character(max_hp=18, current_hp=11)

        prompt = build_turn_system_prompt(campaign, character, None)

        assert "**Health**: 11/18 HP" in prompt


def _round(outcome="active"):
    from src.services.combat_service import Attack, RoundResult

    return RoundResult(
        round=2,
        action="attack",
        character="Wren",
        attack=Attack("Wren", "Goblin 1", 15, 7, 22, 11, True, True, 9, 0, 7),
        enemy_attacks=[
            Attack("Goblin 2", "Wren", 4, 3, 7, 12, False, False, 0, 18, 18)
        ],
        outcome=outcome,
    )


STATE = {
    "enemies": [
        {"id": 1, "name": "Goblin 1", "kind": "goblin", "hp": 0, "max_hp": 7},
        {"id": 2, "name": "Goblin 2", "kind": "goblin", "hp": 2, "max_hp": 7},
    ],
    "player": {"hp": 18, "max_hp": 18, "defense": 12, "dead": False},
}


class TestCombatRoundSection:
    def test_states_the_outcome_as_fixed(self):
        from src.services.prompts import combat_round_section

        text = combat_round_section(_round(), STATE)

        assert "## Combat Round 2 (already resolved by the server)" in text
        assert (
            "- Wren lands a critical hit on Goblin 1 for 9 damage and drops them."
            in text
        )
        assert "- Goblin 2 attacks Wren and misses." in text
        assert "Wren: 18/18 HP. Goblin 1: down; Goblin 2: badly wounded." in text
        assert "never change who hit" in text

    def test_death_is_final(self):
        from src.services.prompts import combat_round_section

        text = combat_round_section(_round("lost"), STATE)

        assert "is dead. This is permanent" in text
        assert "No rescue, no revival" in text
