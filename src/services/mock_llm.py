import json

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from src.services.prompts import campaign_creation_prompt, character_creation_prompt

MOCK_CHARACTER_JSON = json.dumps({
    "name": "Aldric the Grey",
    "hero_class": "wizard",
    "biography": "Aldric spent his formative years studying forgotten tomes in a crumbling tower on the edge of the empire.",
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


def _character_creation_sequence(step: int) -> Message:
    return _make_message(
        [TextBlock(text=MOCK_CHARACTER_JSON, type="text", citations=None)],
        "end_turn",
    )


def _campaign_creation_sequence(step: int) -> Message:
    if step == 0:
        return _make_message(
            [ToolUseBlock(
                id="mock_tool_use_01",
                input={"tags": "urban,intrigue", "limit": 5},
                name="search_checkpoints",
                type="tool_use",
            )],
            "tool_use",
        )
    return _make_message(
        [TextBlock(text=MOCK_CAMPAIGN_JSON, type="text", citations=None)],
        "end_turn",
    )


TOOL_SEQUENCES = {
    frozenset(["search_checkpoints"]): _campaign_creation_sequence,
}

NO_TOOL_SEQUENCES = {
    character_creation_prompt: _character_creation_sequence,
}


class MockAnthropicMessages:
    def create(self, *, messages, system=None, tools=None, **kwargs) -> Message:
        def _content_type(c) -> str | None:
            return c.get("type") if isinstance(c, dict) else getattr(c, "type", None)

        step = sum(
            1 for m in messages
            if isinstance(m.get("content"), list)
            and any(_content_type(c) == "tool_result" for c in m["content"])
        )

        if tools:
            tool_names = frozenset(t["name"] for t in tools)
            sequence_fn = TOOL_SEQUENCES.get(tool_names)
            if sequence_fn is None:
                raise ValueError(
                    f"No mock sequence registered for tools: {tool_names}. "
                    "Add it to TOOL_SEQUENCES in src/services/mock_llm.py."
                )
            return sequence_fn(step)

        sequence_fn = NO_TOOL_SEQUENCES.get(system)
        if sequence_fn is None:
            raise ValueError(
                f"No mock sequence registered for system prompt (first 50 chars): {str(system)[:50]!r}. "
                "Add it to NO_TOOL_SEQUENCES in src/services/mock_llm.py."
            )
        return sequence_fn(step)


class MockAnthropicClient:
    def __init__(self):
        self.messages = MockAnthropicMessages()
