from fastapi.testclient import TestClient

from unittest.mock import patch
from src.main import app
from src.models.character import Character
import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy

client = TestClient(app)


class TestCharacterCreation:
    """TDD tests for character creation endpoint."""

    @patch("src.api.characters.create")
    def test_create_character_returns_201(self, mock_create):
        """POST /characters should return 201 Created."""
        mock_create.return_value = Character(
            id=1,
            name="Gandalf",
            hero_class="wizard",
            biography="A learned wizard who has spent his life in a library",
            description="Tall and ragged, with an aura of great wisdom. Slow to speak but all listen when he does",
            age=55,
            strength=7,
            perception=6,
            endurance=4,
            charisma=8,
            intelligence=10,
            agility=3,
            luck=5,
        )
        response = client.post(
            "/characters",
            json={
                "description": "Tall and ragged, with an aura of great wisdom. Slow to speak but all listen when he does",
                "campaign_id": 1,
            },
        )
        assert response.status_code == 201
        mock_create.assert_called_once()

    @patch("src.api.characters.create")
    def test_create_character_returns_character_with_id(self, mock_create):
        """Created character should have an assigned ID."""

        mock_create.return_value = Character(
            id=1,
            name="Legolas",
            hero_class="ranger",
            biography="An elven archer raised in the magical forests of Elaran, next in line to the throne",
            description="lean and toned, his piercing eyes can see all",
            age=2405,
            strength=5,
            perception=9,
            endurance=6,
            charisma=7,
            intelligence=5,
            agility=9,
            luck=6,
        )
        response = client.post(
            "/characters",
            json={
                "description": "lean and toned, his piercing eyes can see all",
                "campaign_id": 1,
            },
        )
        data = response.json()
        assert "id" in data
        assert data["name"] == "Legolas"
        assert data["hero_class"] == "ranger"

    def test_create_character_requires_description(self):
        """Should return 422 if description is missing."""
        response = client.post(
            "/characters",
            json={},
        )
        assert response.status_code == 422

    @patch("src.api.characters.create")
    def test_create_character_returns_502_when_llm_fails(self, mock_create):
        """Should return 502 when the service raises ValueError."""
        mock_create.side_effect = ValueError("LLM did not return a response")
        response = client.post(
            "/characters",
            json={
                "description": "A mysterious wanderer from the northern wastes",
                "campaign_id": 1,
            },
        )
        assert response.status_code == 502
        assert "LLM did not return a response" in response.json()["detail"]

    @patch("src.api.characters.create")
    def test_create_character_returns_502_on_invalid_json(self, mock_create):
        """Should return 502 when the LLM returns invalid JSON."""
        mock_create.side_effect = ValueError("LLM returned invalid json")
        response = client.post(
            "/characters",
            json={
                "description": "A mysterious wanderer from the northern wastes",
                "campaign_id": 1,
            },
        )
        assert response.status_code == 502
        assert "LLM returned invalid json" in response.json()["detail"]

    @patch("src.api.characters.take_turn")
    def test_play_campaign_turn_returns_201(self, mock_create):
        mock_create.return_value = "Hello"

        response = client.post("/characters/1/turns", json={"message": "hello"})

        assert response.status_code == 201
        mock_create.assert_called_once()


class TestStreamingTurn:
    """Tests for the streaming turn endpoint."""

    @patch("src.api.characters.get_session")
    @patch("src.api.characters.process_turn_stream")
    def test_play_turn_stream_returns_200(self, mock_process_turn_stream, mock_get_session):
        """POST /characters/{id}/turns/stream should return 200 with streamed content."""
        from src.models.character import Character
        from src.models.campaign import Campaign, CampaignCheckpoint, Checkpoint
        from src.models.message_history import MessageHistory
        from unittest.mock import MagicMock

        async def mock_stream(*args, **kwargs):
            for chunk in ["Hello", " world"]:
                yield chunk

        mock_process_turn_stream.side_effect = mock_stream

        mock_character = Character(
            id=1,
            name="Gandalf",
            hero_class="wizard",
            biography="A learned wizard",
            description="Tall and ragged",
            age=55,
            strength=7,
            perception=6,
            endurance=4,
            charisma=8,
            intelligence=10,
            agility=3,
            luck=5,
            campaign_id=1,
        )
        mock_campaign = Campaign(id=1, name="Test Campaign", description="A test campaign")
        mock_checkpoint = Checkpoint(id=1, name="Start", description="Starting point", tags="start")
        mock_campaign_checkpoint = CampaignCheckpoint(
            id=1, campaign_id=1, checkpoint_id=1, order=1, status="active"
        )

        mock_session = MagicMock()
        mock_session.get.side_effect = lambda model, id: (
            mock_character if model is Character else
            mock_campaign if model is Campaign else
            mock_checkpoint if model is Checkpoint else None
        )
        mock_session.exec.return_value.first.return_value = mock_campaign_checkpoint
        mock_session.exec.return_value.all.return_value = []

        mock_persist_session = MagicMock()
        mock_persist_session.__enter__ = MagicMock(return_value=mock_persist_session)
        mock_persist_session.__exit__ = MagicMock(return_value=False)

        mock_get_session.return_value = iter([mock_persist_session])

        with patch("src.api.characters.session", mock_session, create=True):
            from fastapi.testclient import TestClient
            from src.main import app

            def override_get_session():
                yield mock_session

            app.dependency_overrides[__import__("src.db.db", fromlist=["get_session"]).get_session] = override_get_session

            test_client = TestClient(app)
            response = test_client.post(
                "/characters/1/turns/stream",
                json={"message": "I explore the dungeon"},
            )

            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert "Hello" in response.text
        assert " world" in response.text
