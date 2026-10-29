from unittest.mock import patch

from src.models.campaign import Campaign
from src.models.character import HeroClass, Race
from src.models.message_history import MessageHistory
from src.services.dm_agent import TextDelta
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
    @patch("src.api.characters.create")
    def test_returns_201_with_character(self, mock_create, client, user):
        mock_create.return_value = make_character()

        response = client.post("/characters/", json=CHARACTER_BODY)

        assert response.status_code == 201
        assert response.json()["name"] == "Gandalf"
        assert mock_create.call_args.args[2] is user

    @patch("src.api.characters.create")
    def test_returns_502_when_service_fails(self, mock_create, client):
        mock_create.side_effect = ValueError("save failed")

        response = client.post("/characters/", json=CHARACTER_BODY)

        assert response.status_code == 502
        assert response.json()["detail"] == "save failed"


class TestCharacterPreview:
    @patch("src.api.characters.create_preview")
    def test_returns_generated_sheet(self, mock_preview, client):
        mock_preview.return_value = {"age": 24, "agility": 9}

        response = client.post("/characters/preview", json=PREVIEW_BODY)

        assert response.status_code == 201
        assert response.json() == {"age": 24, "agility": 9}

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
@patch("src.services.turn_service.save_turn", return_value=99)
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
        mock_load.return_value = turn_context()

        client.post("/characters/1/turns/stream", json={"message": "I sneak"})

        memories.assert_called_once_with(7, ["I sneak", "They spot you."])

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
