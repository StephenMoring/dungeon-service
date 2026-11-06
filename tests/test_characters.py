from datetime import UTC, datetime
from unittest.mock import patch

from src.models.campaign import Campaign
from src.models.character import HeroClass, Race
from src.models.message_history import MessageHistory
from src.services.dm_agent import TextDelta
from src.services.prompts import known_context
from src.services.character_service import InvalidPreview
from src.services.usage_service import RateLimited
from src.services.turn_service import SavedTurn
from src.tools.dice_tools import RollResult
from tests.conftest import make_character

CHARACTER_BODY = {
    "name": "Gandalf",
    "hero_class": "wizard",
    "biography": "A learned wizard who has spent his life in a library",
    "description": "Tall and ragged, with an aura of great wisdom",
    "age": 55,
    "user_id": 1,
    "strength": 7,
    "perception": 6,
    "endurance": 4,
    "charisma": 8,
    "intelligence": 10,
    "agility": 3,
    "luck": 5,
}

PREVIEW_BODY = {
    "name": "Kael",
    "description": "A quick and cunning thief with sharp eyes",
    "hero_class": "rogue",
    "race": "human",
}


class TestListCharacters:
    @patch("src.api.characters.get_user_characters")
    def test_returns_current_users_characters(self, mock_get, client, user):
        mock_get.return_value = []

        response = client.get("/characters/")

        assert response.json() == []
        assert mock_get.call_args.args[1] is user


class TestCreateCharacter:
    @patch("src.api.characters.create_from_preview")
    def test_saves_the_signed_preview(self, create, client, session, user):
        create.return_value = make_character()

        response = client.post("/characters/", json={"preview_token": "signed"})

        assert response.status_code == 201
        assert response.json()["name"] == "Gandalf"
        create.assert_called_once_with("signed", session, user)

    @patch("src.api.characters.create_from_preview")
    def test_stats_in_the_body_are_ignored(self, create, client):
        # Stats come only from the server-signed preview, never from the client.
        create.return_value = make_character()

        client.post("/characters/", json={"preview_token": "signed", **CHARACTER_BODY})

        assert create.call_args.args[0] == "signed"
        assert len(create.call_args.args) == 3

    def test_requires_a_preview_token(self, client):
        assert client.post("/characters/", json=CHARACTER_BODY).status_code == 422

    @patch(
        "src.api.characters.create_from_preview",
        side_effect=InvalidPreview(
            "This character preview expired. Generate it again."
        ),
    )
    def test_bad_preview_is_a_400_with_the_reason(self, _create, client):
        response = client.post("/characters/", json={"preview_token": "old"})

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "This character preview expired. Generate it again."
        )


class TestCharacterPreview:
    @patch("src.api.characters.create_preview")
    def test_returns_generated_sheet(self, mock_preview, client, user):
        mock_preview.return_value = {"age": 24, "agility": 9, "preview_token": "t"}

        response = client.post("/characters/preview", json=PREVIEW_BODY)

        assert response.status_code == 201
        assert response.json() == {"age": 24, "agility": 9, "preview_token": "t"}
        assert mock_preview.call_args.args[1] is user

    def test_requires_all_fields(self, client):
        response = client.post("/characters/preview", json={"name": "Kael"})

        assert response.status_code == 422

    @patch("src.api.characters.create_preview")
    def test_returns_502_when_llm_fails(self, mock_preview, client):
        mock_preview.side_effect = ValueError("LLM did not return a response")

        response = client.post("/characters/preview", json=PREVIEW_BODY)

        assert response.status_code == 502
        assert response.json()["detail"] == "LLM did not return a response"


class TestLookups:
    @patch("src.api.characters.get_hero_classes")
    def test_classes(self, mock_classes, client):
        mock_classes.return_value = [
            HeroClass(id=1, class_name="wizard", description="casts spells")
        ]

        response = client.get("/characters/classes")

        assert response.json()[0]["class_name"] == "wizard"

    @patch("src.api.characters.get_all_races")
    def test_races(self, mock_races, client):
        mock_races.return_value = [Race(id=1, race="elf", description="pointy ears")]

        response = client.get("/characters/races")

        assert response.json()[0]["race"] == "elf"


class TestGetCharacter:
    def test_returns_owned_character(self, client, session):
        session.get.return_value = make_character()

        response = client.get("/characters/1")

        assert response.status_code == 200
        assert response.json()["name"] == "Gandalf"

    def test_returns_404_when_missing(self, client, session):
        session.get.return_value = None

        response = client.get("/characters/1")

        assert response.status_code == 404


class TestGetTurns:
    @patch("src.api.characters.get_character_turns")
    def test_returns_history(self, mock_turns, client, session):
        session.get.return_value = make_character()
        mock_turns.return_value = [
            MessageHistory(
                id=1, campaign_id=1, character_id=1, role="user", content="hello"
            )
        ]

        response = client.get("/characters/1/turns")

        assert response.status_code == 200
        assert response.json()[0]["content"] == "hello"

    def test_returns_403_for_other_users_character(self, client, session):
        session.get.return_value = make_character(user_id=2)

        response = client.get("/characters/1/turns")

        assert response.status_code == 403


async def fake_dm(_turn):
    yield ROLL
    yield TextDelta("They spot ")
    yield TextDelta("you.")


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


def turn_context():
    return {
        "character": make_character(campaign_id=7),
        "campaign": Campaign(id=7, name="Thornwall", theme="gothic", description="d"),
        "current_checkpoint": None,
        "recent_messages": [],
        "message": "I sneak",
    }


@patch("src.services.turn_service.extract_and_store_memories")
@patch("src.services.turn_service.save_turn", return_value=SavedTurn(99))
@patch("src.services.turn_service.process_turn_stream", fake_dm)
@patch("src.api.characters.load_turn_context")
class TestPlayTurnStream:
    def test_streams_events(self, mock_load, _save, _memories, client, session):
        session.get.return_value = make_character()
        mock_load.return_value = turn_context()

        response = client.post(
            "/characters/1/turns/stream", json={"message": "I sneak"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.text
        assert body.index("event: roll") < body.index("event: text")
        assert body.index("event: text") < body.index("event: done")

    def test_runs_memory_extraction_after_stream(
        self, mock_load, _save, memories, client, session
    ):
        session.get.return_value = make_character()
        turn = turn_context()
        mock_load.return_value = turn

        client.post("/characters/1/turns/stream", json={"message": "I sneak"})

        memories.assert_called_once_with(
            7, ["I sneak", "They spot you."], known_context(turn.get("memories"))
        )

    def test_returns_404_when_missing(
        self, mock_load, _save, _memories, client, session
    ):
        session.get.return_value = None

        response = client.post("/characters/1/turns/stream", json={"message": "hi"})

        assert response.status_code == 404
        mock_load.assert_not_called()

    def test_returns_403_for_other_users_character(
        self, mock_load, _save, _memories, client, session
    ):
        session.get.return_value = make_character(user_id=2)

        response = client.post("/characters/1/turns/stream", json={"message": "hi"})

        assert response.status_code == 403
        mock_load.assert_not_called()

    def test_returns_502_when_context_fails(
        self, mock_load, _save, _memories, client, session
    ):
        session.get.return_value = make_character()
        mock_load.side_effect = ValueError("Checkpoint for campaign could not be found")

        response = client.post("/characters/1/turns/stream", json={"message": "hi"})

        assert response.status_code == 502
        assert response.json()["detail"] == "Checkpoint for campaign could not be found"

    def test_old_turn_route_is_gone(self, _load, _save, _memories, client):
        response = client.post("/characters/1/turns", json={"message": "hi"})

        assert response.status_code == 405


class TestClaudeRateLimits:
    """Routes that call Claude check the caller's limit before doing so."""

    @patch("src.api.dependencies.check_and_record")
    @patch("src.api.characters.create_preview", return_value={})
    def test_preview_is_limited(self, _preview, check, client, session, user):
        client.post("/characters/preview", json=PREVIEW_BODY)

        check.assert_called_once_with(session, user, "preview")

    @patch("src.api.characters.create_preview")
    @patch(
        "src.api.dependencies.check_and_record",
        side_effect=RateLimited(42, "You're going too fast."),
    )
    def test_over_the_limit_returns_429_without_calling_claude(
        self, _check, preview, client
    ):
        response = client.post("/characters/preview", json=PREVIEW_BODY)

        assert response.status_code == 429
        assert response.headers["retry-after"] == "42"
        assert response.json()["detail"] == "You're going too fast."
        preview.assert_not_called()

    @patch("src.api.characters.stream_turn")
    @patch("src.api.characters.load_turn_context")
    @patch("src.api.dependencies.check_and_record")
    def test_turn_is_limited_after_the_ownership_check(
        self, check, _load, stream, client, session, user
    ):
        stream.return_value = iter([])
        session.get.return_value = make_character(user_id=2)

        client.post("/characters/1/turns/stream", json={"message": "hi"})
        check.assert_not_called()  # someone else's character: refused, not counted

        session.get.return_value = make_character()
        client.post("/characters/1/turns/stream", json={"message": "hi"})
        check.assert_called_once_with(session, user, "turn")


class TestTurnsDuringAndAfterAFight:
    @patch("src.api.characters.load_turn_context")
    def test_free_text_turns_wait_until_the_fight_ends(self, load, client, session):
        session.get.return_value = make_character()
        with patch("src.api.characters.active_encounter", return_value=object()):
            response = client.post(
                "/characters/1/turns/stream", json={"message": "I talk"}
            )

        assert response.status_code == 409
        assert response.json()["detail"] == "You're in a fight. Choose a combat action."
        load.assert_not_called()

    @patch("src.api.characters.load_turn_context")
    def test_the_dead_take_no_turns(self, load, client, session):
        session.get.return_value = make_character(died_at=datetime.now(UTC))

        response = client.post("/characters/1/turns/stream", json={"message": "hi"})

        assert response.status_code == 409
        assert response.json()["detail"] == "Gandalf has died. Their story is over."
        load.assert_not_called()


ROUND_STATE = {"id": 5, "status": "active", "round": 1, "enemies": [], "player": {}}


def combat_round():
    from src.services.combat_service import RoundResult

    return RoundResult(round=1, action="defend", character="Gandalf", defended=True)


async def fake_narration(_turn, _round, _state):
    yield TextDelta("You brace.")


@patch("src.services.turn_service.extract_and_store_memories")
@patch("src.services.turn_service.save_turn", return_value=SavedTurn(99))
@patch("src.services.turn_service.narrate_round_stream", fake_narration)
@patch("src.api.characters.load_turn_context")
@patch("src.api.characters.play_round")
class TestCombatRoundRoute:
    def in_a_fight(self):
        return patch("src.api.characters.active_encounter", return_value=object())

    def test_resolves_then_streams_the_round(
        self, play, load, _save, _memories, client, session
    ):
        character = make_character()
        session.get.return_value = character
        play.return_value = (combat_round(), ROUND_STATE)
        load.return_value = turn_context()

        with self.in_a_fight():
            response = client.post(
                "/characters/1/combat/stream", json={"action": "defend"}
            )

        assert response.status_code == 200
        body = response.text
        assert body.index("event: round") < body.index("event: combat")
        assert body.index("event: combat") < body.index("event: text")
        assert play.call_args.args[1] is character
        assert play.call_args.args[3:] == ("defend", None)
        load.assert_called_once_with(1, "I raise my guard and defend.", session)

    def test_passes_the_target(self, play, load, _save, _memories, client, session):
        session.get.return_value = make_character()
        play.return_value = (combat_round(), ROUND_STATE)
        load.return_value = turn_context()

        with self.in_a_fight():
            client.post(
                "/characters/1/combat/stream",
                json={"action": "attack", "target_id": 12},
            )

        assert play.call_args.args[3:] == ("attack", 12)

    def test_unknown_action_is_rejected(
        self, play, _load, _save, _memories, client, session
    ):
        session.get.return_value = make_character()

        with self.in_a_fight():
            response = client.post(
                "/characters/1/combat/stream", json={"action": "cast fireball"}
            )

        assert response.status_code == 422
        play.assert_not_called()

    def test_no_fight_is_a_409(self, play, _load, _save, _memories, client, session):
        session.get.return_value = make_character()

        response = client.post("/characters/1/combat/stream", json={"action": "flee"})

        assert response.status_code == 409
        play.assert_not_called()

    def test_bad_target_is_a_400(self, play, _load, _save, _memories, client, session):
        from src.services.combat_service import InvalidTarget

        session.get.return_value = make_character()
        play.side_effect = InvalidTarget("That enemy isn't standing in this fight.")

        with self.in_a_fight():
            response = client.post(
                "/characters/1/combat/stream",
                json={"action": "attack", "target_id": 999},
            )

        assert response.status_code == 400

    def test_another_players_character_is_a_403(
        self, play, _load, _save, _memories, client, session
    ):
        session.get.return_value = make_character(user_id=2)

        response = client.post("/characters/1/combat/stream", json={"action": "flee"})

        assert response.status_code == 403
        play.assert_not_called()

    def test_the_dead_cannot_fight(
        self, play, _load, _save, _memories, client, session
    ):
        session.get.return_value = make_character(died_at=datetime.now(UTC))

        with self.in_a_fight():
            response = client.post(
                "/characters/1/combat/stream", json={"action": "attack"}
            )

        assert response.status_code == 409
        play.assert_not_called()

    def test_counts_against_the_turn_limit(
        self, play, _load, _save, _memories, client, session, user
    ):
        from src.services.usage_service import RateLimited

        session.get.return_value = make_character()
        with (
            self.in_a_fight(),
            patch(
                "src.api.dependencies.check_and_record",
                side_effect=RateLimited(30, "Too many turns"),
            ) as check,
        ):
            response = client.post(
                "/characters/1/combat/stream", json={"action": "defend"}
            )

        assert response.status_code == 429
        check.assert_called_once_with(session, user, "turn")
        play.assert_not_called()


class TestGetEncounter:
    @patch("src.api.characters.load_bestiary", return_value=[])
    @patch("src.api.characters.current_state", return_value=ROUND_STATE)
    def test_returns_the_active_fight(self, _state, _bestiary, client, session):
        session.get.return_value = make_character()

        assert client.get("/characters/1/encounter").json() == ROUND_STATE

    @patch("src.api.characters.load_bestiary", return_value=[])
    @patch("src.api.characters.current_state", return_value=None)
    def test_null_when_not_fighting(self, _state, _bestiary, client, session):
        session.get.return_value = make_character()

        response = client.get("/characters/1/encounter")

        assert response.status_code == 200
        assert response.json() is None

    def test_another_players_character_is_a_403(self, client, session):
        session.get.return_value = make_character(user_id=2)

        assert client.get("/characters/1/encounter").status_code == 403
