import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import cast

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import MessageParam, TextBlock, ToolUseBlock

from src.config import ANTHROPIC_API_KEY
from src.services.prompts import (
    KnownNames,
    build_memory_extraction_prompt,
    build_turn_system_prompt,
    campaign_creation_prompt,
    character_creation_prompt,
    combat_round_section,
)
from src.tools.campaign_tools import handle_search_checkpoints, search_checkpoints_tool
from src.tools.combat_tools import EncounterPlan, plan_encounter, start_encounter_tool
from src.tools.dice_tools import RollResult, handle_roll_check, roll_check_tool

logger = logging.getLogger(__name__)

client = Anthropic(api_key=ANTHROPIC_API_KEY)
async_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


CHARACTER_SCHEMA = {
    "type": "object",
    "properties": {
        "age": {"type": "integer"},
        "biography": {"type": "string"},
        "strength": {"type": "integer"},
        "perception": {"type": "integer"},
        "endurance": {"type": "integer"},
        "charisma": {"type": "integer"},
        "intelligence": {"type": "integer"},
        "agility": {"type": "integer"},
        "luck": {"type": "integer"},
    },
    "required": [
        "age",
        "biography",
        "strength",
        "perception",
        "endurance",
        "charisma",
        "intelligence",
        "agility",
        "luck",
    ],
    "additionalProperties": False,
}


def create_character(character_description):
    message = client.messages.create(
        max_tokens=175,
        system=character_creation_prompt,
        messages=[
            {
                "role": "user",
                "content": character_description,
            }
        ],
        model="claude-sonnet-4-5-20250929",
        output_config={"format": {"type": "json_schema", "schema": CHARACTER_SCHEMA}},
    )
    # Metadata only: the content is the player's character.
    logger.debug(
        "create_character: stop_reason=%s usage=%s", message.stop_reason, message.usage
    )
    if message.content and isinstance(message.content[0], TextBlock):
        message_text = message.content[0].text
        return message_text


CAMPAIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "theme": {"type": "string"},
        "checkpoint_ids": {"type": "array", "items": {"type": "integer"}},
        "opening_message": {"type": "string"},
    },
    "required": ["name", "theme", "checkpoint_ids", "opening_message"],
    "additionalProperties": False,
}


def create_campaign(campaign_description, session):
    tools = [search_checkpoints_tool]
    messages: list[MessageParam] = [{"role": "user", "content": campaign_description}]

    while True:
        message = client.messages.create(
            max_tokens=1024,
            system=campaign_creation_prompt,
            tools=tools,
            messages=messages,
            model="claude-sonnet-4-5-20250929",
            output_config={
                "format": {"type": "json_schema", "schema": CAMPAIGN_SCHEMA}
            },
        )

        if message.stop_reason == "tool_use":
            tool_use = next(b for b in message.content if isinstance(b, ToolUseBlock))
            tool_input = tool_use.input

            tags = tool_input.get("tags", "")
            limit = tool_input.get("limit", 10)

            if not isinstance(tags, str) or not isinstance(limit, int):
                raise ValueError(f"Unexpected tool_input types: {tool_input}")

            result = handle_search_checkpoints(session=session, tags=tags, limit=limit)

            messages.append({"role": "assistant", "content": message.content})
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": str(result),
                        }
                    ],
                }
            )
        else:
            if message.content and isinstance(message.content[0], TextBlock):
                return message.content[0].text
            break


MEMORIES_SCHEMA = {
    "type": "object",
    "properties": {
        "npcs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "disposition": {"type": "string"},
                    "known_facts": {"type": "string"},
                    "secrets": {"type": "string"},
                },
                "required": ["name", "role", "disposition", "known_facts", "secrets"],
                "additionalProperties": False,
            },
        },
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "events": {"type": "string"},
                },
                "required": ["name", "description", "events"],
                "additionalProperties": False,
            },
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "where_found": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["held", "lost", "used", "given away"],
                    },
                },
                "required": ["name", "description", "where_found", "status"],
                "additionalProperties": False,
            },
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["decision", "revelation", "deal", "consequence"],
                    },
                },
                "required": ["summary", "category"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["npcs", "locations", "items", "events"],
    "additionalProperties": False,
}


def extract_memories(
    player_message: str,
    dm_message: str,
    known: KnownNames | None = None,
    already_known: str = "",
) -> str | None:
    prompt = build_memory_extraction_prompt(
        player_message, dm_message, known or KnownNames(), already_known
    )
    message = client.messages.create(
        max_tokens=1024,
        system=prompt,
        messages=[{"role": "user", "content": "Extract memories from this exchange."}],
        model="claude-sonnet-4-5-20250929",
        output_config={"format": {"type": "json_schema", "schema": MEMORIES_SCHEMA}},
    )
    if message.content and isinstance(message.content[0], TextBlock):
        return message.content[0].text
    return None


@dataclass
class TextDelta:
    text: str


def _history(turn: dict) -> list[MessageParam]:
    messages: list[MessageParam] = [
        {"role": msg.role, "content": msg.content} for msg in turn["recent_messages"]
    ]
    messages.append({"role": "user", "content": turn["message"]})
    return messages


async def process_turn_stream(
    turn: dict,
) -> AsyncGenerator[TextDelta | RollResult | EncounterPlan, None]:
    """Stream a DM turn. Claude may call one tool: roll_check (the server rolls) or
    start_encounter (yields the EncounterPlan for turn_service to save). The reply
    then continues with tools disabled."""
    character = turn["character"]
    bestiary = turn.get("bestiary") or []
    system_prompt = build_turn_system_prompt(
        turn["campaign"], character, turn["current_checkpoint"], turn.get("memories")
    )
    messages = _history(turn)
    tools = [roll_check_tool]
    if bestiary:
        tools.append(start_encounter_tool(bestiary))

    async with async_client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
        tools=tools,
        tool_choice={"type": "auto", "disable_parallel_tool_use": True},
    ) as stream:
        wrote_setup = False
        async for event in stream:
            if event.type == "text":
                wrote_setup = True
                yield TextDelta(event.text)
        final = await stream.get_final_message()

    if final.stop_reason != "tool_use":
        return

    tool_use = next(b for b in final.content if isinstance(b, ToolUseBlock))
    tool_input = cast(dict, tool_use.input)
    result: RollResult | EncounterPlan
    if tool_use.name == "roll_check":
        result = handle_roll_check(
            character,
            tool_input["stat"],
            tool_input["difficulty"],
            tool_input["reason"],
        )
    elif tool_use.name == "start_encounter":
        result = plan_encounter(bestiary, tool_input)
    else:
        raise ValueError(f"Unexpected tool call: {tool_use.name}")
    yield result
    if wrote_setup:
        # Setup text rarely ends with whitespace; keep it apart from the outcome.
        yield TextDelta("\n\n")

    messages.append({"role": "assistant", "content": final.content})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result.to_tool_result(),
                }
            ],
        }
    )

    async with async_client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
        tools=tools,
        tool_choice={"type": "none"},
    ) as stream:
        async for event in stream:
            if event.type == "text":
                yield TextDelta(event.text)


async def narrate_round_stream(
    turn: dict, round_result, state: dict
) -> AsyncGenerator[TextDelta, None]:
    """Stream the DM's narration of a combat round the server already resolved.
    One request, no tools. The resolved round rides in the player's message, not
    the system prompt: placed last, it outweighs a conversation that doesn't match
    it (e.g. the DM wrote nothing yet about the blow that kills the character)."""
    system_prompt = build_turn_system_prompt(
        turn["campaign"],
        turn["character"],
        turn["current_checkpoint"],
        turn.get("memories"),
    )
    messages = _history(turn)
    messages[-1] = {
        "role": "user",
        "content": f"{turn['message']}\n\n{combat_round_section(round_result, state)}",
    }
    async with async_client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=512,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for event in stream:
            if event.type == "text":
                yield TextDelta(event.text)
