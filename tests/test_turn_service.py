import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from src.models.campaign import Campaign, CampaignCheckpoint, Checkpoint
from src.models.character import Character
from src.models.message_history import MessageHistory
from src.services.dm_agent import TextDelta
from src.services.turn_service import (
    load_turn_context,
    save_turn,
    stream_turn,
)
from src.tools.dice_tools import RollResult
from src.services.embedding_service import extract_and_store_memories
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


class TestLoadTurnContext:
    def test_passes_context(self):
        newest_first = [
            MessageHistory(
                id=2, campaign_id=1, character_id=1, role="assistant", content="b"
            ),
            MessageHistory(
                id=1, campaign_id=1, character_id=1, role="user", content="a"
            ),
        ]
        session = default_session(history=newest_first)

        turn = load_turn_context(1, "I push the gate", session)

        assert turn["character"].name == "Gandalf"
        assert turn["campaign"].name == "Thornwall"
        assert turn["current_checkpoint"].title == "The Gate"
        assert turn["message"] == "I push the gate"
        assert [m.content for m in turn["recent_messages"]] == ["a", "b"]

    def test_active_checkpoint_skips_complete_and_locked(self):
        session = default_session()

        load_turn_context(1, "hi", session)

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
    def test_raises_when_context_missing(self, overrides, error):
        with pytest.raises(ValueError, match=error):
            load_turn_context(1, "hi", default_session(**overrides))


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


def make_turn():
    return {
        "character": make_character(),
        "campaign": Campaign(id=1, name="Thornwall", theme="gothic", description="d"),
        "current_checkpoint": None,
        "recent_messages": [],
        "message": "I sneak",
    }


def fake_dm(*events, error=None):
    async def gen(_turn):
        for event in events:
            yield event
        if error:
            raise error

    return gen


def parse_sse(chunks: list[str]) -> list[tuple[str, dict]]:
    parsed = []
    for chunk in chunks:
        event_line, data_line = chunk.strip().split("\n")
        parsed.append(
            (event_line.removeprefix("event: "), json.loads(data_line[len("data: ") :]))
        )
    return parsed


async def run_stream(background_tasks=None) -> list[tuple[str, dict]]:
    tasks = background_tasks or MagicMock()
    return parse_sse([chunk async for chunk in stream_turn(make_turn(), tasks)])


@pytest.mark.anyio
class TestStreamTurn:
    @patch("src.services.turn_service.save_turn", return_value=42)
    async def test_stream_event_order(self, _save):
        with patch(
            "src.services.turn_service.process_turn_stream",
            fake_dm(ROLL, TextDelta("a"), TextDelta("b")),
        ):
            events = await run_stream()

        assert [name for name, _ in events] == [
            "thinking",
            "roll",
            "text",
            "text",
            "done",
        ]
        assert events[1][1] == asdict(ROLL)
        assert events[2][1] == {"text": "a"}
        assert events[-1][1] == {"message_id": 42}

    @patch("src.services.turn_service.save_turn", return_value=42)
    async def test_saves_concatenated_text(self, save):
        with patch(
            "src.services.turn_service.process_turn_stream",
            fake_dm(ROLL, TextDelta("a"), TextDelta("b")),
        ):
            await run_stream()

        save.assert_called_once_with(1, 1, "I sneak", "ab")

    @patch("src.services.turn_service.save_turn", return_value=42)
    async def test_schedules_memory_extraction(self, _save):
        tasks = MagicMock()
        with patch(
            "src.services.turn_service.process_turn_stream",
            fake_dm(TextDelta("a"), TextDelta("b")),
        ):
            await run_stream(tasks)

        tasks.add_task.assert_called_once_with(
            extract_and_store_memories, 1, ["I sneak", "ab"]
        )

    @patch("src.services.turn_service.save_turn")
    async def test_error_after_roll_saves_nothing(self, save):
        tasks = MagicMock()
        with patch(
            "src.services.turn_service.process_turn_stream",
            fake_dm(ROLL, error=ValueError("boom")),
        ):
            events = await run_stream(tasks)

        assert events[-1] == ("error", {"detail": "boom"})
        save.assert_not_called()
        tasks.add_task.assert_not_called()

    @patch("src.services.turn_service.save_turn")
    async def test_unexpected_error_hides_internals(self, save):
        with patch(
            "src.services.turn_service.process_turn_stream",
            fake_dm(error=RuntimeError("SELECT password FROM user")),
        ):
            events = await run_stream()

        name, data = events[-1]
        assert name == "error"
        assert "SELECT" not in data["detail"]
        assert data["detail"] == "The Dungeon Master lost the thread. Try again."


class TestSaveTurn:
    @patch("src.services.turn_service.Session")
    def test_save_turn_persists_both_messages(self, session_cls):
        session = session_cls.return_value.__enter__.return_value

        def assign_ids():
            for i, call in enumerate(session.add.call_args_list, start=1):
                call.args[0].id = i

        session.commit.side_effect = assign_ids

        message_id = save_turn(1, 1, "I sneak", "Caught.")

        saved = [c.args[0] for c in session.add.call_args_list]
        assert [(m.role, m.content) for m in saved] == [
            ("user", "I sneak"),
            ("assistant", "Caught."),
        ]
        session.commit.assert_called_once()
        assert message_id == 2
