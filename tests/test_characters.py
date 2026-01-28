from fastapi.testclient import TestClient

from unittest.mock import patch
from src.main import app
from src.models.character import Character

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
            story_so_far=None,
            strength=None,
            perception=None,
            endurance=None,
            charisma=None,
            intelligence=None,
            agility=None,
            luck=None,
        )
        response = client.post(
            "/characters",
            json={
                "name": "Gandalf",
                "hero_class": "wizard",
                "biography": "A learned wizard who has spent his life in a library",
                "description": "Tall and ragged, with an aura of great wisdom. Slow to speak but all listen when he does",
                "age": 55,
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
            story_so_far=None,
            strength=None,
            perception=None,
            endurance=None,
            charisma=None,
            intelligence=None,
            agility=None,
            luck=None,
        )
        response = client.post(
            "/characters",
            json={
                "name": "Legolas",
                "hero_class": "ranger",
                "biography": "An elven archer raised in the magical forests of Elaran, next in line to the throne",
                "description": "lean and toned, his piercing eyes can see all",
                "age": 2405,
            },
        )
        data = response.json()
        assert "id" in data
        assert data["name"] == "Legolas"
        assert data["hero_class"] == "ranger"

    def test_create_character_requires_name(self):
        """Should return 422 if name is missing."""
        response = client.post(
            "/characters",
            json={
                "hero_class": "ranger",
                "biography": "An elven archer raised in the magical forests of Elaran, next in line to the throne",
                "description": "lean and toned, his piercing eyes can see all",
                "age": 2405,
            },
        )
        assert response.status_code == 422

    def test_create_character_requires_class_type(self):
        """Should return 422 if class_type is missing."""
        response = client.post(
            "/characters",
            json={
                "name": "Aragorn",
                "biography": "A learned wizard who has spent his life in a library",
                "description": "Tall and ragged, with an aura of great wisdom. Slow to speak but all listen when he does",
                "age": 1,
            },
        )
        assert response.status_code == 422
