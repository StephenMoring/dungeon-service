from unittest.mock import MagicMock, patch

from src.models.campaign import Campaign, CampaignCheckpoint, CreateCampaignResponse
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


def exec_results(session, *results):
    """Make each successive session.exec(...).all() return the next list."""
    session.exec.side_effect = [
        MagicMock(all=MagicMock(return_value=r)) for r in results
    ]


class TestListCampaigns:
    def test_returns_campaigns(self, client, session):
        exec_results(session, [make_campaign()], [], [])

        response = client.get("/campaigns/")

        assert response.status_code == 200
        assert response.json()[0]["name"] == "Shadows Over Thornwall"

    def test_only_lists_campaigns_with_the_users_characters(self, client, session):
        exec_results(session, [])

        client.get("/campaigns/")

        sql = compiled_sql(session.exec.call_args_list[0].args[0])
        assert "JOIN character ON character.campaign_id = campaign.id" in sql
        assert "character.user_id = 1" in sql

    def test_includes_each_campaigns_characters_and_checkpoints(self, client, session):
        exec_results(
            session,
            [make_campaign(id=1), make_campaign(id=2, name="The Darkening North")],
            [
                make_character(id=10, campaign_id=1),
                make_character(id=11, campaign_id=2),
                make_character(id=12, campaign_id=2),
            ],
            [
                CampaignCheckpoint(
                    id=1, campaign_id=1, checkpoint_id=4, order=1, status="new"
                ),
                CampaignCheckpoint(id=2, campaign_id=1, checkpoint_id=5, order=2),
            ],
        )

        body = client.get("/campaigns/").json()

        first, second = body
        assert [c["id"] for c in first["characters"]] == [10]
        assert [c["id"] for c in second["characters"]] == [11, 12]
        assert [cp["checkpoint_id"] for cp in first["campaign_checkpoints"]] == [4, 5]
        assert first["campaign_checkpoints"][0]["status"] == "new"
        assert second["campaign_checkpoints"] == []

    def test_only_includes_the_users_characters(self, client, session):
        exec_results(session, [make_campaign(id=3)], [], [])

        client.get("/campaigns/")

        sql = compiled_sql(session.exec.call_args_list[1].args[0])
        assert "character.user_id = 1" in sql
        assert "character.campaign_id IN (3)" in sql

    def test_orders_checkpoints_within_a_campaign(self, client, session):
        exec_results(session, [make_campaign(id=3)], [], [])

        client.get("/campaigns/")

        sql = compiled_sql(session.exec.call_args_list[2].args[0])
        assert "campaigncheckpoint.campaign_id IN (3)" in sql
        assert (
            'ORDER BY campaigncheckpoint.campaign_id, campaigncheckpoint."order"' in sql
        )


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
