import json

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage


MOCK_CHARACTER_JSON = json.dumps({
    "name": "Aldric the Grey",
    "hero_class": "wizard",
    "biography": "A wizard who studied forgotten tomes in a crumbling tower.",
    "age": 45,
    "story_so_far": "",
    "strength": 3,
    "perception": 7,
    "endurance": 4,
    "charisma": 5,
    "intelligence": 9,
    "agility": 4,
    "luck": 5,
})

MOCK_CAMPAIGN_JSON = json.dumps({
    "name": "Shadows Over Thornwall",
    "theme": "A city teeters on the edge of civil war while something darker stirs beneath the streets.",
    "description": "A gothic urban campaign blending political intrigue with creeping horror.",
    "checkpoint_ids": [1, 2, 3],
})


def _make_message(content: list, stop_reason: str) -> Message:
    return Message(
        id="mock_msg_01",
        content=content,
        model="mock",
        role="assistant",
        stop_reason=stop_reason,
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=0, output_tokens=0),
    )


def text_response(text: str) -> Message:
    """Build a mock end_turn Message with a single TextBlock."""
    return _make_message(
        [TextBlock(text=text, type="text", citations=None)],
        "end_turn",
    )


def tool_use_response(tool_name: str, tool_input: dict) -> Message:
    """Build a mock tool_use Message with a single ToolUseBlock."""
    return _make_message(
        [ToolUseBlock(id="mock_tool_use_01", input=tool_input, name=tool_name, type="tool_use")],
        "tool_use",
    )
