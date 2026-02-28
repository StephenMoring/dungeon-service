import json

from src.services.dm_agent import create_campaign, create_character
from tests.helpers import (
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
