import os
from anthropic import Anthropic
from anthropic.types import MessageParam, TextBlock, ToolUseBlock
from src.tools.campaign_tools import handle_search_checkpoints, search_checkpoints_tool
from src.services.prompts import (
    master_system_prompt,
    campaign_creation_prompt,
    character_creation_prompt,
)

if os.getenv("MOCK_LLM"):
    from src.services.mock_llm import MockAnthropicClient
    client = MockAnthropicClient()
else:
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


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
