from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestCharacterCreation:
    """TDD tests for character creation endpoint."""

    def test_create_character_returns_201(self):
        """POST /characters should return 201 Created."""
        response = client.post(
            "/characters",
            json={
                "name": "Gandalf",
                "class_type": "wizard",
                "level": 1,
            },
        )
        assert response.status_code == 201

    def test_create_character_returns_character_with_id(self):
        """Created character should have an assigned ID."""
        response = client.post(
            "/characters",
            json={
                "name": "Legolas",
                "class_type": "ranger",
                "level": 1,
            },
        )
        data = response.json()
        assert "id" in data
        assert data["name"] == "Legolas"
        assert data["class_type"] == "ranger"

    def test_create_character_requires_name(self):
        """Should return 422 if name is missing."""
        response = client.post(
            "/characters",
            json={
                "class_type": "wizard",
                "level": 1,
            },
        )
        assert response.status_code == 422

    def test_create_character_requires_class_type(self):
        """Should return 422 if class_type is missing."""
        response = client.post(
            "/characters",
            json={
                "name": "Gandalf",
                "level": 1,
            },
        )
        assert response.status_code == 422
