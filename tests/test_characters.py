from unittest.mock import patch

from src.models.character import HeroClass, Race
from src.models.message_history import MessageHistory
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


class TestPlayTurn:
    @patch("src.api.characters.extract_and_store_memories")
    @patch("src.api.characters.take_turn")
    def test_returns_dm_message(self, mock_take_turn, mock_memories, client, session):
        session.get.return_value = make_character()
        mock_take_turn.return_value = "The door creaks open."

        response = client.post(
            "/characters/1/turns", json={"message": "I open the door"}
        )

        assert response.status_code == 201
        assert response.json() == {"message": "The door creaks open."}

    @patch("src.api.characters.extract_and_store_memories")
    @patch("src.api.characters.take_turn")
    def test_schedules_memory_extraction(
        self, mock_take_turn, mock_memories, client, session
    ):
        session.get.return_value = make_character(campaign_id=7)
        mock_take_turn.return_value = "The door creaks open."

        client.post("/characters/1/turns", json={"message": "I open the door"})

        mock_memories.assert_called_once_with(
            7, ["I open the door", "The door creaks open."]
        )

    @patch("src.api.characters.extract_and_store_memories")
    @patch("src.api.characters.take_turn")
    def test_returns_404_when_missing(
        self, mock_take_turn, mock_memories, client, session
    ):
        session.get.return_value = None

        response = client.post("/characters/1/turns", json={"message": "hi"})

        assert response.status_code == 404
        mock_take_turn.assert_not_called()

    @patch("src.api.characters.extract_and_store_memories")
    @patch("src.api.characters.take_turn")
    def test_returns_403_for_other_users_character(
        self, mock_take_turn, mock_memories, client, session
    ):
        session.get.return_value = make_character(user_id=2)

        response = client.post("/characters/1/turns", json={"message": "hi"})

        assert response.status_code == 403
        mock_take_turn.assert_not_called()

    @patch("src.api.characters.extract_and_store_memories")
    @patch("src.api.characters.take_turn")
    def test_returns_502_when_turn_fails(
        self, mock_take_turn, mock_memories, client, session
    ):
        session.get.return_value = make_character()
        mock_take_turn.side_effect = ValueError("DM did not return a response")

        response = client.post("/characters/1/turns", json={"message": "hi"})

        assert response.status_code == 502
        mock_memories.assert_not_called()
