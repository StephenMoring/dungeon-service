from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from src.models.campaign import Campaign, CampaignCheckpoint, Checkpoint
from src.models.character import Character
from src.models.message_history import MessageHistory
from src.services.turn_service import take_turn
from tests.conftest import make_character


def make_session(character=None, campaign=None, checkpoint_link=None, history=()):
    session = MagicMock()
    checkpoint = Checkpoint(
        id=3,
        title="The Gate",
        description="A locked gate",
        setting="city",
        objective="Get inside",
        tags="urban",
    )
    by_model = {Character: character, Campaign: campaign, Checkpoint: checkpoint}
    session.get.side_effect = lambda model, _id: by_model.get(model)
    session.exec.return_value.first.return_value = checkpoint_link
    session.exec.return_value.all.return_value = list(history)
    return session


def default_session(**overrides):
    kwargs = dict(
        character=make_character(),
        campaign=Campaign(id=1, name="Thornwall", theme="gothic", description="d"),
        checkpoint_link=CampaignCheckpoint(
            id=1, campaign_id=1, checkpoint_id=3, order=0, status="new"
        ),
    )
    kwargs.update(overrides)
    return make_session(**kwargs)


def compiled_sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


class TestTakeTurn:
    @patch("src.services.turn_service.process_turn")
    def test_returns_dm_response(self, mock_process_turn, user):
        mock_process_turn.return_value = "The gate groans open."

        result = take_turn(1, "I push the gate", default_session(), user)

        assert result == "The gate groans open."

    @patch("src.services.turn_service.process_turn")
    def test_passes_context_to_dm(self, mock_process_turn, user):
        mock_process_turn.return_value = "ok"
        newest_first = [
            MessageHistory(
                id=2, campaign_id=1, character_id=1, role="assistant", content="b"
            ),
            MessageHistory(
                id=1, campaign_id=1, character_id=1, role="user", content="a"
            ),
        ]
        session = default_session(history=newest_first)

        take_turn(1, "I push the gate", session, user)

        turn = mock_process_turn.call_args.args[0]
        assert turn["character"].name == "Gandalf"
        assert turn["campaign"].name == "Thornwall"
        assert turn["current_checkpoint"].title == "The Gate"
        assert turn["message"] == "I push the gate"
        assert [m.content for m in turn["recent_messages"]] == ["a", "b"]

    @patch("src.services.turn_service.process_turn")
    def test_persists_player_and_dm_messages(self, mock_process_turn, user):
        mock_process_turn.return_value = "The gate groans open."
        session = default_session()

        take_turn(1, "I push the gate", session, user)

        saved = [c.args[0] for c in session.add.call_args_list]
        assert [(m.role, m.content) for m in saved] == [
            ("user", "I push the gate"),
            ("assistant", "The gate groans open."),
        ]
        session.commit.assert_called_once()

    @patch("src.services.turn_service.process_turn")
    def test_active_checkpoint_skips_complete_and_locked(self, mock_process_turn, user):
        mock_process_turn.return_value = "ok"
        session = default_session()

        take_turn(1, "hi", session, user)

        checkpoint_query = compiled_sql(session.exec.call_args_list[0].args[0])
        assert "NOT IN ('complete', 'locked')" in checkpoint_query

    @pytest.mark.parametrize(
        "overrides, error",
        [
            ({"character": None}, "Character 1 not found"),
            ({"campaign": None}, "Campaign 1 not found"),
            ({"checkpoint_link": None}, "Checkpoint for campaign"),
        ],
    )
    @patch("src.services.turn_service.process_turn")
    def test_raises_when_context_missing(
        self, mock_process_turn, overrides, error, user
    ):
        with pytest.raises(ValueError, match=error):
            take_turn(1, "hi", default_session(**overrides), user)

        mock_process_turn.assert_not_called()
