import os
from dataclasses import dataclass
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import MessageParam, TextBlock, ToolUseBlock
from typing import AsyncGenerator, cast
from src.tools.campaign_tools import handle_search_checkpoints, search_checkpoints_tool
from src.tools.dice_tools import RollResult, handle_roll_check, roll_check_tool
from src.services.prompts import (
    build_turn_system_prompt,
    campaign_creation_prompt,
    character_creation_prompt,
    memory_extraction_prompt,
)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
async_client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


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
    print(message)
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


def extract_memories(player_message: str, dm_message: str) -> str | None:
    prompt = memory_extraction_prompt.format(
        player_message=player_message,
        dm_message=dm_message,
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


async def process_turn_stream(
    turn: dict,
) -> AsyncGenerator[TextDelta | RollResult, None]:
    """Stream a DM turn. Claude may call roll_check once; the server rolls and the
    reply continues with tools disabled."""
    character = turn["character"]
    campaign = turn["campaign"]
    checkpoint = turn["current_checkpoint"]
    recent_messages = turn["recent_messages"]
    player_message = turn["message"]

    system_prompt = build_turn_system_prompt(campaign, character, checkpoint)

    messages: list[MessageParam] = [
        {"role": msg.role, "content": msg.content} for msg in recent_messages
    ]
    messages.append({"role": "user", "content": player_message})

    async with async_client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
        tools=[roll_check_tool],
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
    if tool_use.name != "roll_check":
        raise ValueError(f"Unexpected tool call: {tool_use.name}")

    tool_input = cast(dict, tool_use.input)
    roll = handle_roll_check(
        character, tool_input["stat"], tool_input["difficulty"], tool_input["reason"]
    )
    yield roll
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
                    "content": roll.to_tool_result(),
                }
            ],
        }
    )

    async with async_client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
        tools=[roll_check_tool],
        tool_choice={"type": "none"},
    ) as stream:
        async for event in stream:
            if event.type == "text":
                yield TextDelta(event.text)
