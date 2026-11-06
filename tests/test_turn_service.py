import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from src.models.campaign import Campaign, CampaignCheckpoint, Checkpoint
from src.models.character import Character
from src.models.memory import EventMemory, ItemMemory, NpcMemory
from src.models.message_history import MessageHistory
from src.services.dm_agent import TextDelta
from src.services.embedding_service import extract_and_store_memories
from src.services.memory_service import RetrievedMemories
from src.services.turn_service import (
    SavedTurn,
    load_turn_context,
    save_turn,
    stream_turn,
)
from src.tools.dice_tools import RollResult
from tests.conftest import compiled_sql, make_character


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


@patch("src.services.turn_service.retrieve_memories")
class TestTurnMemories:
    def test_searches_with_last_dm_reply_and_player_message(self, retrieve):
        newest_first = [
            MessageHistory(
                id=2,
                campaign_id=1,
                character_id=1,
                role="assistant",
                content="Mira wipes the bar and smiles.",
            ),
            MessageHistory(
                id=1,
                campaign_id=1,
                character_id=1,
                role="user",
                content="I enter",
            ),
        ]
        session = default_session(history=newest_first)

        load_turn_context(1, "I confront her", session)

        retrieve.assert_called_once_with(
            1, "Mira wipes the bar and smiles.\n\nI confront her", session
        )

    def test_searches_with_message_alone_when_no_history(self, retrieve):
        session = default_session()

        load_turn_context(1, "I look around", session)

        assert retrieve.call_args.args[1] == "I look around"

    def test_logs_what_was_recalled(self, retrieve, caplog):
        retrieve.return_value = RetrievedMemories(
            npcs=[NpcMemory(campaign_id=1, name="Aldo")],
            items=[ItemMemory(campaign_id=1, name="Aldo's Letter")],
            events=[EventMemory(campaign_id=1, summary="Found the letter in his desk")],
        )

        with caplog.at_level("INFO", logger="src.services.turn_service"):
            load_turn_context(1, "Where were you that night?", default_session())

        (record,) = [r for r in caplog.records if r.msg.startswith("Recalled")]
        line = record.getMessage()
        assert "npcs=['Aldo']" in line
        assert 'items=["Aldo\'s Letter"]' in line
        assert "events=['Found the letter in his desk']" in line
        assert "locations=[]" in line

    def test_adds_memories_to_turn(self, retrieve):
        memories = RetrievedMemories()
        retrieve.return_value = memories

        turn = load_turn_context(1, "hi", default_session())

        assert turn["memories"] is memories

    def test_lookup_failure_does_not_break_the_turn(self, retrieve):
        retrieve.side_effect = RuntimeError("voyage down")

        turn = load_turn_context(1, "hi", default_session())

        assert turn["memories"].is_empty()


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
        "memories": RetrievedMemories(npcs=[NpcMemory(campaign_id=1, name="Aldo")]),
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
    @patch("src.services.turn_service.save_turn", return_value=SavedTurn(42))
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

    @patch("src.services.turn_service.save_turn", return_value=SavedTurn(42))
    async def test_saves_concatenated_text(self, save):
        with patch(
            "src.services.turn_service.process_turn_stream",
            fake_dm(ROLL, TextDelta("a"), TextDelta("b")),
        ):
            await run_stream()

        save.assert_called_once_with(1, 1, "I sneak", "ab", None)

    @patch("src.services.turn_service.save_turn", return_value=SavedTurn(42))
    async def test_schedules_memory_extraction(self, _save):
        tasks = MagicMock()
        with patch(
            "src.services.turn_service.process_turn_stream",
            fake_dm(TextDelta("a"), TextDelta("b")),
        ):
            await run_stream(tasks)

        # The memories this turn recalled go along, so extraction can tell when the
        # exchange contradicts something already known (e.g. catches a lie).
        # Passed as text: the task runs after the turn's DB session has closed.
        (task, campaign_id, messages, already_known), _ = tasks.add_task.call_args
        assert (task, campaign_id, messages) == (
            extract_and_store_memories,
            1,
            ["I sneak", "ab"],
        )
        assert isinstance(already_known, str)
        assert "Aldo" in already_known

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

        saved_turn = save_turn(1, 1, "I sneak", "Caught.")

        saved = [c.args[0] for c in session.add.call_args_list]
        assert [(m.role, m.content) for m in saved] == [
            ("user", "I sneak"),
            ("assistant", "Caught."),
        ]
        session.commit.assert_called_once()
        assert saved_turn == SavedTurn(message_id=2)


@pytest.mark.anyio
class TestStreamTurnStartsAFight:
    async def test_saves_the_plan_with_the_turn_and_sends_combat(self):
        from src.tools.combat_tools import EncounterPlan

        plan = EncounterPlan()
        state = {"id": 5, "status": "active", "enemies": [], "player": {}}
        with (
            patch(
                "src.services.turn_service.save_turn",
                return_value=SavedTurn(42, encounter=state),
            ) as save,
            patch(
                "src.services.turn_service.process_turn_stream",
                fake_dm(plan, TextDelta("Goblins!")),
            ),
        ):
            events = await run_stream()

        save.assert_called_once_with(1, 1, "I sneak", "Goblins!", plan)
        assert [name for name, _ in events] == ["thinking", "text", "combat", "done"]
        assert events[2][1] == state


class TestSaveTurnWithEncounter:
    @patch("src.services.turn_service.combatants_of", return_value=[])
    @patch("src.services.turn_service.begin_encounter")
    @patch("src.services.turn_service.Session")
    def test_encounter_is_saved_in_the_same_commit(
        self, session_cls, begin, _combatants
    ):
        from src.models.combat import Encounter
        from src.tools.combat_tools import EncounterPlan, PlannedCombatant
        from tests.test_combat_service import GOBLIN

        session = session_cls.return_value.__enter__.return_value
        session.commit.side_effect = lambda: setattr(
            session.add.call_args_list[1].args[0], "id", 2
        )
        session.get.return_value = make_character()
        begin.return_value = Encounter(id=9, campaign_id=1, character_id=1)
        plan = EncounterPlan([PlannedCombatant(GOBLIN, "Goblin")])

        saved = save_turn(1, 1, "I draw steel", "They charge.", plan)

        begin.assert_called_once_with(session, 1, 1, plan)
        session.commit.assert_called_once()
        assert saved.encounter is not None and saved.encounter["id"] == 9

    @patch("src.services.turn_service.begin_encounter")
    @patch("src.services.turn_service.Session")
    def test_a_plan_with_no_enemies_starts_nothing(self, session_cls, begin):
        from src.tools.combat_tools import EncounterPlan

        session = session_cls.return_value.__enter__.return_value
        session.commit.side_effect = lambda: setattr(
            session.add.call_args_list[1].args[0], "id", 2
        )

        saved = save_turn(1, 1, "a", "b", EncounterPlan())

        begin.assert_not_called()
        assert saved.encounter is None


@pytest.mark.anyio
class TestStreamCombatRound:
    async def run(self, narration, tasks=None):
        from src.services.turn_service import stream_combat_round
        from tests.test_prompts import STATE, _round

        with patch("src.services.turn_service.narrate_round_stream", narration):
            return parse_sse(
                [
                    chunk
                    async for chunk in stream_combat_round(
                        make_turn(), _round(), STATE, tasks or MagicMock()
                    )
                ]
            )

    @patch("src.services.turn_service.save_turn", return_value=SavedTurn(7))
    async def test_sends_dice_and_health_before_narration(self, save):
        async def narration(_turn, _round, _state):
            yield TextDelta("Steel flashes.")

        tasks = MagicMock()
        events = await self.run(narration, tasks)

        assert [name for name, _ in events] == ["round", "combat", "text", "done"]
        assert events[0][1]["attack"]["damage"] == 9
        assert events[1][1]["enemies"][1]["hp"] == 2
        save.assert_called_once_with(1, 1, "I sneak", "Steel flashes.")
        tasks.add_task.assert_called_once()

    @patch("src.services.turn_service.save_turn")
    async def test_failed_narration_keeps_the_round(self, save):
        async def narration(_turn, _round, _state):
            raise RuntimeError("overloaded")
            yield  # pragma: no cover

        events = await self.run(narration)

        assert [name for name, _ in events] == ["round", "combat", "error"]
        assert "the round stands" in events[-1][1]["detail"]
        save.assert_not_called()
