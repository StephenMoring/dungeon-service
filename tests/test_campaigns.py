from unittest.mock import patch

from src.models.campaign import Campaign, CreateCampaignResponse
from tests.conftest import compiled_sql, make_character

DESCRIPTION_TEXT = "A dark gothic city riven by political scheming and ancient evil"
CREATE_BODY = {"character_id": 1, "description": DESCRIPTION_TEXT}


def make_campaign(**kwargs) -> Campaign:
    defaults = dict(
        id=1,
        name="Shadows Over Thornwall",
        theme="A city teeters on the edge of civil war.",
        description=DESCRIPTION_TEXT,
    )
    defaults.update(kwargs)
    return Campaign(**defaults)


class TestCampaignCreation:
    @patch("src.api.campaigns.create")
    def test_returns_201_with_campaign_and_opening(self, mock_create, client, user):
        mock_create.return_value = CreateCampaignResponse(
            campaign=make_campaign(), opening_message="You arrive at dusk."
        )

        response = client.post("/campaigns/", json=CREATE_BODY)

        assert response.status_code == 201
        body = response.json()
        assert body["campaign"]["name"] == "Shadows Over Thornwall"
        assert body["opening_message"] == "You arrive at dusk."
        assert mock_create.call_args.args[2] is user

    def test_requires_description_and_character(self, client):
        response = client.post("/campaigns/", json={})

        assert response.status_code == 422

    @patch("src.api.campaigns.create")
    def test_returns_502_when_service_fails(self, mock_create, client):
        mock_create.side_effect = ValueError("LLM did not return a response")

        response = client.post("/campaigns/", json=CREATE_BODY)

        assert response.status_code == 502
        assert response.json()["detail"] == "LLM did not return a response"


class TestListCampaigns:
    def test_returns_campaigns(self, client, session):
        session.exec.return_value.all.return_value = [make_campaign()]

        response = client.get("/campaigns/")

        assert response.status_code == 200
        assert response.json()[0]["name"] == "Shadows Over Thornwall"

    def test_only_lists_campaigns_with_the_users_characters(self, client, session):
        session.exec.return_value.all.return_value = []

        client.get("/campaigns/")

        sql = compiled_sql(session.exec.call_args.args[0])
        assert "JOIN character ON character.campaign_id = campaign.id" in sql
        assert "character.user_id = 1" in sql


class TestListCampaignCharacters:
    def test_returns_characters(self, client, session):
        session.exec.return_value.all.return_value = [make_character()]

        response = client.get("/campaigns/1/characters")

        assert response.status_code == 200
        assert response.json()[0]["name"] == "Gandalf"

    def test_only_lists_the_users_characters(self, client, session):
        session.exec.return_value.all.return_value = []

        client.get("/campaigns/5/characters")

        sql = compiled_sql(session.exec.call_args.args[0])
        assert "character.campaign_id = 5" in sql
        assert "character.user_id = 1" in sql
