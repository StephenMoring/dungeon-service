import json

import pytest
from anthropic.types import TextBlock, ToolUseBlock

from src.services.mock_llm import MOCK_CAMPAIGN_JSON, MOCK_CHARACTER_JSON, MockAnthropicClient
from src.services.prompts import campaign_creation_prompt, character_creation_prompt
from src.tools.campaign_tools import search_checkpoints_tool


class TestCharacterCreation:
    def setup_method(self):
        self.client = MockAnthropicClient()
        self.messages = [{"role": "user", "content": "a cunning rogue"}]

    def test_returns_end_turn(self):
        response = self.client.messages.create(
            max_tokens=175,
            system=character_creation_prompt,
            messages=self.messages,
            model="mock",
        )
        assert response.stop_reason == "end_turn"

    def test_returns_text_block(self):
        response = self.client.messages.create(
            max_tokens=175,
            system=character_creation_prompt,
            messages=self.messages,
            model="mock",
        )
        assert isinstance(response.content[0], TextBlock)

    def test_returns_valid_character_json(self):
        response = self.client.messages.create(
            max_tokens=175,
            system=character_creation_prompt,
            messages=self.messages,
            model="mock",
        )
        data = json.loads(response.content[0].text)
        assert "name" in data
        assert "strength" in data
        assert "story_so_far" in data


class TestCampaignCreation:
    def setup_method(self):
        self.client = MockAnthropicClient()
        self.tools = [search_checkpoints_tool]

    def test_first_call_returns_tool_use(self):
        messages = [{"role": "user", "content": "a dark gothic city"}]
        response = self.client.messages.create(
            max_tokens=1024,
            system=campaign_creation_prompt,
            tools=self.tools,
            messages=messages,
            model="mock",
        )
        assert response.stop_reason == "tool_use"

    def test_first_call_returns_search_checkpoints_block(self):
        messages = [{"role": "user", "content": "a dark gothic city"}]
        response = self.client.messages.create(
            max_tokens=1024,
            system=campaign_creation_prompt,
            tools=self.tools,
            messages=messages,
            model="mock",
        )
        assert isinstance(response.content[0], ToolUseBlock)
        assert response.content[0].name == "search_checkpoints"

    def test_second_call_returns_end_turn(self):
        messages = [
            {"role": "user", "content": "a dark gothic city"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "x", "name": "search_checkpoints", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "[]"}]},
        ]
        response = self.client.messages.create(
            max_tokens=1024,
            system=campaign_creation_prompt,
            tools=self.tools,
            messages=messages,
            model="mock",
        )
        assert response.stop_reason == "end_turn"

    def test_second_call_returns_valid_campaign_json(self):
        messages = [
            {"role": "user", "content": "a dark gothic city"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "x", "name": "search_checkpoints", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "[]"}]},
        ]
        response = self.client.messages.create(
            max_tokens=1024,
            system=campaign_creation_prompt,
            tools=self.tools,
            messages=messages,
            model="mock",
        )
        data = json.loads(response.content[0].text)
        assert "name" in data
        assert "checkpoint_ids" in data
        assert isinstance(data["checkpoint_ids"], list)


class TestUnknownCallsRaise:
    def setup_method(self):
        self.client = MockAnthropicClient()

    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="No mock sequence registered for tools"):
            self.client.messages.create(
                max_tokens=1024,
                system="some system prompt",
                tools=[{"name": "unknown_tool", "description": "", "input_schema": {"type": "object", "properties": {}}}],
                messages=[{"role": "user", "content": "hello"}],
                model="mock",
            )

    def test_unknown_system_prompt_raises(self):
        with pytest.raises(ValueError, match="No mock sequence registered for system prompt"):
            self.client.messages.create(
                max_tokens=1024,
                system="some unregistered system prompt for a future feature",
                messages=[{"role": "user", "content": "hello"}],
                model="mock",
            )
