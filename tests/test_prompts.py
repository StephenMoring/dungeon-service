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
