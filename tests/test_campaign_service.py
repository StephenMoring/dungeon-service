import json
from unittest.mock import MagicMock, patch

import pytest
import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy

from src.models.campaign import Campaign, CampaignCheckpoint, CreateCampaignRequest
from src.models.message_history import MessageHistory
from src.services.campaign_service import create, delete_for_user
from tests.conftest import compiled_sql, make_character


VALID_LLM_RESPONSE = json.dumps(
    {
        "name": "Shadows Over Thornwall",
        "theme": "A city teeters on the edge of civil war while something darker stirs beneath the streets.",
        "checkpoint_ids": [4, 5, 6],
        "opening_message": "Rain lashes the cobbles as you reach the gates.",
    }
)

DESCRIPTION_TEXT = "A dark gothic city riven by political scheming and ancient evil"
REQUEST = CreateCampaignRequest(character_id=1, description=DESCRIPTION_TEXT)


def make_session(character=None, campaign_id: int = 10) -> MagicMock:
    """MagicMock session that returns `character` from get() and assigns campaign.id on flush."""
    session = MagicMock()
    session.get.return_value = character
    added: list = []

    def set_id_on_flush() -> None:
        for obj in added:
            if isinstance(obj, Campaign):
                obj.id = campaign_id

    session.add = MagicMock(side_effect=added.append)
    session.flush = MagicMock(side_effect=set_id_on_flush)
    session.added = added
    return session


class TestCampaignServiceCreate:
    @patch("src.services.campaign_service.create_campaign")
    def test_returns_campaign_and_opening_message(self, mock_create_campaign, user):
        mock_create_campaign.return_value = VALID_LLM_RESPONSE
        session = make_session(make_character(campaign_id=None))

        result = create(REQUEST, session, user)

        assert result.campaign.name == "Shadows Over Thornwall"
        assert result.campaign.description == DESCRIPTION_TEXT
        assert result.opening_message.startswith("Rain lashes")

    @patch("src.services.campaign_service.create_campaign")
    def test_passes_description_to_dm_agent(self, mock_create_campaign, user):
        mock_create_campaign.return_value = VALID_LLM_RESPONSE
        session = make_session(make_character(campaign_id=None))

        create(REQUEST, session, user)

        mock_create_campaign.assert_called_once_with(DESCRIPTION_TEXT, session)

    @patch("src.services.campaign_service.create_campaign")
    def test_links_checkpoints_in_order_first_unlocked(
        self, mock_create_campaign, user
    ):
        mock_create_campaign.return_value = VALID_LLM_RESPONSE
        session = make_session(make_character(campaign_id=None))

        create(REQUEST, session, user)

        links = [o for o in session.added if isinstance(o, CampaignCheckpoint)]
        assert [(cp.checkpoint_id, cp.order, cp.status) for cp in links] == [
            (4, 0, "new"),
            (5, 1, "locked"),
            (6, 2, "locked"),
        ]
        assert all(cp.campaign_id == 10 for cp in links)

    @patch("src.services.campaign_service.create_campaign")
    def test_assigns_character_and_saves_opening_message(
        self, mock_create_campaign, user
    ):
        mock_create_campaign.return_value = VALID_LLM_RESPONSE
        character = make_character(campaign_id=None)
        session = make_session(character)

        create(REQUEST, session, user)

        assert character.campaign_id == 10
        messages = [o for o in session.added if isinstance(o, MessageHistory)]
        assert len(messages) == 1
        assert messages[0].role == "assistant"
        assert messages[0].campaign_id == 10
        session.commit.assert_called_once()

    @patch("src.services.campaign_service.create_campaign")
    def test_raises_when_character_missing(self, mock_create_campaign, user):
        session = make_session(None)

        with pytest.raises(ValueError, match="Character not found"):
            create(REQUEST, session, user)

        mock_create_campaign.assert_not_called()

    @patch("src.services.campaign_service.create_campaign")
    def test_raises_when_character_belongs_to_another_user(
        self, mock_create_campaign, user
    ):
        session = make_session(make_character(user_id=2))

        with pytest.raises(ValueError, match="does not belong"):
            create(REQUEST, session, user)

        mock_create_campaign.assert_not_called()

    @pytest.mark.parametrize("llm_output", [None, ""])
    @patch("src.services.campaign_service.create_campaign")
    def test_raises_when_llm_returns_nothing(
        self, mock_create_campaign, llm_output, user
    ):
        mock_create_campaign.return_value = llm_output
        session = make_session(make_character())

        with pytest.raises(ValueError, match="LLM did not return a response"):
            create(REQUEST, session, user)

        session.add.assert_not_called()

    @patch("src.services.campaign_service.create_campaign")
    def test_raises_on_invalid_json(self, mock_create_campaign, user):
        mock_create_campaign.return_value = "not valid json"
        session = make_session(make_character())

        with pytest.raises(ValueError, match="LLM returned invalid json"):
            create(REQUEST, session, user)

        session.add.assert_not_called()


class TestDeadCharacters:
    @patch("src.services.campaign_service.create_campaign")
    def test_a_dead_character_cannot_start_a_campaign(self, mock_create_campaign, user):
        from datetime import UTC, datetime

        from src.services.campaign_service import DeadCharacter

        session = make_session(make_character(died_at=datetime.now(UTC)))

        with pytest.raises(DeadCharacter, match="has died"):
            create(REQUEST, session, user)

        mock_create_campaign.assert_not_called()


class TestDeleteForUser:
    def owned(self, *characters):
        session = MagicMock()
        session.exec.return_value.all.return_value = list(characters)
        session.get.return_value = Campaign(id=3, name="n", theme="t", description="d")
        return session

    def test_refuses_a_campaign_the_user_has_no_character_in(self, user):
        session = self.owned()

        with pytest.raises(LookupError):
            delete_for_user(3, session, user)

        ownership = compiled_sql(session.exec.call_args.args[0])
        assert "character.campaign_id = 3" in ownership
        assert "character.user_id = 1" in ownership
        session.delete.assert_not_called()
        session.commit.assert_not_called()

    def test_deletes_the_campaign_and_everything_in_it(self, user):
        session = self.owned(make_character(campaign_id=3))

        delete_for_user(3, session, user)

        statements = [compiled_sql(c.args[0]) for c in session.exec.call_args_list[1:]]
        for table in (
            "npcmemory",
            "locationmemory",
            "itemmemory",
            "eventmemory",
            "messagehistory",
            "encounter",
            "campaigncheckpoint",
        ):
            assert f"DELETE FROM {table} WHERE {table}.campaign_id = 3" in statements
        session.delete.assert_called_once_with(session.get.return_value)
        session.commit.assert_called_once()

    def test_keeps_characters_but_frees_them(self, user):
        session = self.owned(make_character(campaign_id=3))

        delete_for_user(3, session, user)

        statements = [compiled_sql(c.args[0]) for c in session.exec.call_args_list[1:]]
        assert (
            "UPDATE character SET campaign_id=NULL WHERE character.campaign_id = 3"
            in statements
        )
