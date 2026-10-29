import json

import pytest

from src.models.campaign import Campaign
from src.services.dm_agent import (
    TextDelta,
    create_campaign,
    create_character,
    process_turn_stream,
)
from src.tools.dice_tools import RollResult, roll_check_tool
from tests.conftest import make_character
from tests.helpers import (
    FakeStream,
    MOCK_CAMPAIGN_JSON,
    MOCK_CHARACTER_JSON,
    text_response,
    tool_use_response,
)


class TestCreateCharacter:
    def test_returns_character_json(self, mocker):
        mocker.patch(
            "src.services.dm_agent.client.messages.create",
            return_value=text_response(MOCK_CHARACTER_JSON),
        )
        result = create_character("a cunning rogue")
        assert result == MOCK_CHARACTER_JSON

    def test_parsed_response_has_required_fields(self, mocker):
        mocker.patch(
            "src.services.dm_agent.client.messages.create",
            return_value=text_response(MOCK_CHARACTER_JSON),
        )
        result = create_character("a cunning rogue")
        data = json.loads(result)
        assert "name" in data
        assert "strength" in data
        assert "story_so_far" in data


class TestCreateCampaign:
    def test_tool_use_loop_returns_campaign_json(self, mocker):
        session = mocker.MagicMock()
        mocker.patch(
            "src.services.dm_agent.client.messages.create",
            side_effect=[
                tool_use_response(
                    "search_checkpoints", {"tags": "urban,intrigue", "limit": 5}
                ),
                text_response(MOCK_CAMPAIGN_JSON),
            ],
        )
        mocker.patch("src.services.dm_agent.handle_search_checkpoints", return_value=[])

        result = create_campaign("a dark gothic city", session)
        assert result == MOCK_CAMPAIGN_JSON

    def test_search_checkpoints_called_with_tool_args(self, mocker):
        session = mocker.MagicMock()
        mocker.patch(
            "src.services.dm_agent.client.messages.create",
            side_effect=[
                tool_use_response(
                    "search_checkpoints", {"tags": "urban,intrigue", "limit": 5}
                ),
                text_response(MOCK_CAMPAIGN_JSON),
            ],
        )
        mock_search = mocker.patch(
            "src.services.dm_agent.handle_search_checkpoints",
            return_value=[],
        )

        create_campaign("a dark gothic city", session)
        mock_search.assert_called_once_with(
            session=session, tags="urban,intrigue", limit=5
        )

    def test_llm_called_twice_for_tool_use_loop(self, mocker):
        session = mocker.MagicMock()
        mock_llm = mocker.patch(
            "src.services.dm_agent.client.messages.create",
            side_effect=[
                tool_use_response(
                    "search_checkpoints", {"tags": "urban,intrigue", "limit": 5}
                ),
                text_response(MOCK_CAMPAIGN_JSON),
            ],
        )
        mocker.patch("src.services.dm_agent.handle_search_checkpoints", return_value=[])

        create_campaign("a dark gothic city", session)
        assert mock_llm.call_count == 2


async def collect(gen):
    return [event async for event in gen]


ROLL = RollResult(
    stat="agility",
    stat_value=6,
    roll=7,
    total=13,
    difficulty="hard",
    target=20,
    success=False,
    reason="sneak",
)
ROLL_INPUT = {"stat": "agility", "difficulty": "hard", "reason": "sneak"}


def make_turn():
    return {
        "character": make_character(),
        "campaign": Campaign(id=1, name="Thornwall", theme="gothic", description="d"),
        "current_checkpoint": None,
        "recent_messages": [],
        "message": "I sneak past the guards",
    }


@pytest.mark.anyio
class TestProcessTurnStream:
    async def test_no_roll_yields_text_only(self, mocker):
        stream = mocker.patch(
            "src.services.dm_agent.async_client.messages.stream",
            side_effect=[FakeStream(["You ", "walk."], text_response("You walk."))],
        )

        events = await collect(process_turn_stream(make_turn()))

        assert events == [TextDelta("You "), TextDelta("walk.")]
        assert stream.call_count == 1
        assert stream.call_args.kwargs["tools"] == [roll_check_tool]

    async def test_roll_yields_roll_then_text(self, mocker):
        mocker.patch(
            "src.services.dm_agent.async_client.messages.stream",
            side_effect=[
                FakeStream([], tool_use_response("roll_check", ROLL_INPUT)),
                FakeStream(["They spot you."], text_response("They spot you.")),
            ],
        )
        handler = mocker.patch(
            "src.services.dm_agent.handle_roll_check", return_value=ROLL
        )
        turn = make_turn()

        events = await collect(process_turn_stream(turn))

        assert events == [ROLL, TextDelta("They spot you.")]
        handler.assert_called_once_with(turn["character"], "agility", "hard", "sneak")

    async def test_second_request_has_tool_result_and_no_tools(self, mocker):
        stream = mocker.patch(
            "src.services.dm_agent.async_client.messages.stream",
            side_effect=[
                FakeStream([], tool_use_response("roll_check", ROLL_INPUT)),
                FakeStream(["They spot you."], text_response("They spot you.")),
            ],
        )
        mocker.patch("src.services.dm_agent.handle_roll_check", return_value=ROLL)

        await collect(process_turn_stream(make_turn()))

        second = stream.call_args_list[1].kwargs
        assert second["tool_choice"] == {"type": "none"}
        assert second["messages"][-2]["role"] == "assistant"
        last = second["messages"][-1]
        assert last["role"] == "user"
        tool_result = last["content"][0]
        assert tool_result["type"] == "tool_result"
        assert tool_result["tool_use_id"] == "mock_tool_use_01"
        assert tool_result["content"] == ROLL.to_tool_result()

    async def test_text_before_tool_call_is_yielded_first(self, mocker):
        mocker.patch(
            "src.services.dm_agent.async_client.messages.stream",
            side_effect=[
                FakeStream(
                    ["You creep forward. "],
                    tool_use_response("roll_check", ROLL_INPUT),
                ),
                FakeStream(["Caught."], text_response("Caught.")),
            ],
        )
        mocker.patch("src.services.dm_agent.handle_roll_check", return_value=ROLL)

        events = await collect(process_turn_stream(make_turn()))

        assert events == [TextDelta("You creep forward. "), ROLL, TextDelta("Caught.")]

    async def test_unknown_tool_raises(self, mocker):
        mocker.patch(
            "src.services.dm_agent.async_client.messages.stream",
            side_effect=[FakeStream([], tool_use_response("other", {}))],
        )

        with pytest.raises(ValueError):
            await collect(process_turn_stream(make_turn()))
