from unittest.mock import patch

import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

DESCRIPTION_TEXT = "A dark gothic city riven by political scheming and ancient evil"


class TestCampaignCreation:
    """Tests for the POST /campaigns/ endpoint."""

    @patch("src.api.campaigns.create")
    def test_create_campaign_returns_201(self, mock_create):
        mock_create.return_value = "Shadows Over Thornwall"

        response = client.post("/campaigns/", json={"description": DESCRIPTION_TEXT})

        assert response.status_code == 201
        mock_create.assert_called_once()

    @patch("src.api.campaigns.create")
    def test_create_campaign_returns_name(self, mock_create):
        mock_create.return_value = "Shadows Over Thornwall"

        response = client.post("/campaigns/", json={"description": DESCRIPTION_TEXT})

        assert response.json() == "Shadows Over Thornwall"

    def test_create_campaign_requires_description(self):
        response = client.post("/campaigns/", json={})

        assert response.status_code == 422

    @patch("src.api.campaigns.create")
    def test_create_campaign_returns_502_when_llm_fails(self, mock_create):
        mock_create.side_effect = ValueError("LLM did not return a response")

        response = client.post("/campaigns/", json={"description": DESCRIPTION_TEXT})

        assert response.status_code == 502
        assert "LLM did not return a response" in response.json()["detail"]

    @patch("src.api.campaigns.create")
    def test_create_campaign_returns_502_when_db_fails(self, mock_create):
        mock_create.side_effect = ValueError("failed to save Campaign and Checkpoints")

        response = client.post("/campaigns/", json={"description": DESCRIPTION_TEXT})

        assert response.status_code == 502
        assert "failed to save Campaign and Checkpoints" in response.json()["detail"]

    @patch("src.api.campaigns.take_turn")
    def test_play_campaign_turn_returns_201(self, mock_create):
        mock_create.side_effect = "Hello"

        response = client.post(
            "/campaigns/1/turns", json={"description": DESCRIPTION_TEXT}
        )

        assert response.status_code == 201
        mock_create.assert_called_once()
