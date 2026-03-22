from unittest.mock import patch

import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy
from fastapi.testclient import TestClient

from src.main import app
from src.models.campaign import Campaign

client = TestClient(app)

DESCRIPTION_TEXT = "A dark gothic city riven by political scheming and ancient evil"


def make_campaign(**kwargs) -> Campaign:
    defaults = dict(
        id=1,
        name="Shadows Over Thornwall",
        theme="A city teeters on the edge of civil war while something darker stirs beneath the streets.",
        description=DESCRIPTION_TEXT,
    )
    defaults.update(kwargs)
    return Campaign(**defaults)


class TestCampaignCreation:
    """Tests for the POST /campaigns/ endpoint."""

    @patch("src.api.campaigns.create")
    def test_create_campaign_returns_201(self, mock_create):
        mock_create.return_value = make_campaign()

        response = client.post("/campaigns/", json={"description": DESCRIPTION_TEXT})

        assert response.status_code == 201
        mock_create.assert_called_once()

    @patch("src.api.campaigns.create")
    def test_create_campaign_returns_name(self, mock_create):
        mock_create.return_value = make_campaign()

        response = client.post("/campaigns/", json={"description": DESCRIPTION_TEXT})

        assert response.json()["name"] == "Shadows Over Thornwall"

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


class TestListCampaigns:
    """Tests for the GET /campaigns/ endpoint."""

    def test_list_campaigns_returns_200(self):
        response = client.get("/campaigns/")

        assert response.status_code == 200

    def test_list_campaigns_returns_a_list(self):
        response = client.get("/campaigns/")

        assert isinstance(response.json(), list)


class TestListCampaignCharacters:
    """Tests for the GET /campaigns/{id}/characters endpoint."""

    def test_list_campaign_characters_returns_200(self):
        response = client.get("/campaigns/1/characters")

        assert response.status_code == 200

    def test_list_campaign_characters_returns_a_list(self):
        response = client.get("/campaigns/1/characters")

        assert isinstance(response.json(), list)
