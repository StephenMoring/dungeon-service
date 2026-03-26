import os
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import MessageParam, TextBlock, ToolUseBlock
from typing import AsyncGenerator
from src.tools.campaign_tools import handle_search_checkpoints, search_checkpoints_tool
from src.services.prompts import (
    build_turn_system_prompt,
    campaign_creation_prompt,
    character_creation_prompt,
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


def process_turn(turn: dict, session) -> str:
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

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=400,
        system=system_prompt,
        messages=messages,
    )

    if response.content and isinstance(response.content[0], TextBlock):
        return response.content[0].text
    raise ValueError("DM did not return a response")


async def process_turn_stream(turn: dict) -> AsyncGenerator[str, None]:
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
        max_tokens=400,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text
