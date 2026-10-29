from src.models.campaign import Campaign
from src.models.memory import EventMemory, ItemMemory, NpcMemory
from src.services.memory_service import RetrievedMemories
from src.services.prompts import (
    build_turn_system_prompt,
    format_memories,
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
