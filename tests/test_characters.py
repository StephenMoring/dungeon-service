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
            },
        )
        assert response.status_code == 502
        assert "LLM returned invalid json" in response.json()["detail"]
