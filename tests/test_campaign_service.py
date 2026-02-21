import json
from unittest.mock import MagicMock, patch

import pytest
import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy

from src.models.campaign import Campaign, CampaignDescriptionCreate
from src.services.campaign_service import create


VALID_LLM_RESPONSE = json.dumps(
    {
        "name": "Shadows Over Thornwall",
        "theme": "A city teeters on the edge of civil war while something darker stirs beneath the streets.",
        "description": "A gothic urban campaign blending political intrigue with creeping horror.",
        "checkpoint_ids": [1, 2, 3],
    }
)

DESCRIPTION_TEXT = "A dark gothic city riven by political scheming and ancient evil"


def make_session(campaign_id: int = 1) -> MagicMock:
    """Return a MagicMock session that populates campaign.id after flush."""
    session = MagicMock()
    campaign_holder: list[Campaign] = []

    def capture_add(obj: object) -> None:
        if isinstance(obj, Campaign) and not campaign_holder:
            campaign_holder.append(obj)

    def set_id_on_flush() -> None:
        if campaign_holder:
            campaign_holder[0].id = campaign_id

    session.add = MagicMock(side_effect=capture_add)
    session.flush = MagicMock(side_effect=set_id_on_flush)
    return session


class TestCampaignServiceCreate:
    """Unit tests for campaign_service.create, with mocked LLM and DB."""

    @patch("src.services.campaign_service.create_campaign")
    def test_create_returns_campaign_name_on_success(self, mock_create_campaign):
        mock_create_campaign.return_value = VALID_LLM_RESPONSE
        session = make_session()
        description = CampaignDescriptionCreate(description=DESCRIPTION_TEXT)

        result = create(description, session)

        assert result == "Shadows Over Thornwall"

    @patch("src.services.campaign_service.create_campaign")
    def test_create_passes_description_to_dm_agent(self, mock_create_campaign):
        mock_create_campaign.return_value = VALID_LLM_RESPONSE
        session = make_session()
        description = CampaignDescriptionCreate(description=DESCRIPTION_TEXT)

        create(description, session)

        mock_create_campaign.assert_called_once_with(DESCRIPTION_TEXT, session)

    @patch("src.services.campaign_service.create_campaign")
    def test_create_saves_campaign_and_checkpoints_to_session(self, mock_create_campaign):
        mock_create_campaign.return_value = VALID_LLM_RESPONSE
        session = make_session()
        description = CampaignDescriptionCreate(description=DESCRIPTION_TEXT)

        create(description, session)

        # 1 campaign + 3 checkpoints from checkpoint_ids
        assert session.add.call_count == 4
        session.flush.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()

    @patch("src.services.campaign_service.create_campaign")
    def test_create_strips_markdown_fences(self, mock_create_campaign):
        mock_create_campaign.return_value = f"```json\n{VALID_LLM_RESPONSE}\n```"
        session = make_session()
        description = CampaignDescriptionCreate(description=DESCRIPTION_TEXT)

        result = create(description, session)

        assert result == "Shadows Over Thornwall"

    @patch("src.services.campaign_service.create_campaign")
    def test_create_raises_when_llm_returns_none(self, mock_create_campaign):
        mock_create_campaign.return_value = None
        session = MagicMock()
        description = CampaignDescriptionCreate(description=DESCRIPTION_TEXT)

        with pytest.raises(ValueError, match="LLM did not return a response"):
            create(description, session)

        session.add.assert_not_called()

    @patch("src.services.campaign_service.create_campaign")
    def test_create_raises_when_llm_returns_empty(self, mock_create_campaign):
        mock_create_campaign.return_value = ""
        session = MagicMock()
        description = CampaignDescriptionCreate(description=DESCRIPTION_TEXT)

        with pytest.raises(ValueError, match="LLM did not return a response"):
            create(description, session)

        session.add.assert_not_called()

    @patch("src.services.campaign_service.create_campaign")
    def test_create_raises_when_llm_returns_invalid_json(self, mock_create_campaign):
        mock_create_campaign.return_value = "not valid json at all"
        session = MagicMock()
        description = CampaignDescriptionCreate(description=DESCRIPTION_TEXT)

        with pytest.raises(ValueError, match="LLM returned invalid json"):
            create(description, session)

        session.add.assert_not_called()
