import json
from unittest.mock import MagicMock, patch

import pytest
import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy

from src.models.character import CharacterDescriptionCreate
from src.services.character_service import create


VALID_LLM_RESPONSE = json.dumps(
    {
        "name": "Kael",
        "hero_class": "rogue",
        "biography": "A former street thief who found purpose after a chance encounter with a dying knight.",
        "age": 24,
        "story_so_far": "",
        "strength": 4,
        "perception": 8,
        "endurance": 5,
        "charisma": 6,
        "intelligence": 6,
        "agility": 9,
        "luck": 7,
    }
)


class TestCharacterServiceCreate:
    """Unit tests for character_service.create, with mocked LLM and DB."""

    @patch("src.services.character_service.create_character")
    def test_create_returns_character_on_success(self, mock_create_character):
        mock_create_character.return_value = VALID_LLM_RESPONSE

        session = MagicMock()
        session.refresh = MagicMock(side_effect=lambda c: setattr(c, "id", 1))

        description = CharacterDescriptionCreate(
            description="A quick and cunning thief with sharp eyes",
            campaign_id=1,
        )
        result = create(description, session)

        assert result.name == "Kael"
        assert result.hero_class == "rogue"
        assert result.agility == 9
        assert result.id == 1

    @patch("src.services.character_service.create_character")
    def test_create_sets_description_from_input(self, mock_create_character):
        mock_create_character.return_value = VALID_LLM_RESPONSE

        session = MagicMock()
        description_text = "A quick and cunning thief with sharp eyes"
        description = CharacterDescriptionCreate(description=description_text, campaign_id=1)

        result = create(description, session)

        assert result.description == description_text

    @patch("src.services.character_service.create_character")
    def test_create_passes_description_to_dm_agent(self, mock_create_character):
        mock_create_character.return_value = VALID_LLM_RESPONSE

        session = MagicMock()
        description_text = "A quick and cunning thief with sharp eyes"
        description = CharacterDescriptionCreate(description=description_text, campaign_id=1)

        create(description, session)

        mock_create_character.assert_called_once_with(description_text)

    @patch("src.services.character_service.create_character")
    def test_create_saves_character_to_session(self, mock_create_character):
        mock_create_character.return_value = VALID_LLM_RESPONSE

        session = MagicMock()
        description = CharacterDescriptionCreate(
            description="A quick and cunning thief with sharp eyes",
            campaign_id=1,
        )

        create(description, session)

        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()

    @patch("src.services.character_service.create_character")
    def test_create_raises_when_llm_fails(self, mock_create_character):
        mock_create_character.return_value = None

        session = MagicMock()
        description = CharacterDescriptionCreate(
            description="A quick and cunning thief with sharp eyes",
            campaign_id=1,
        )

        with pytest.raises(ValueError, match="LLM did not return a response"):
            create(description, session)

        session.add.assert_not_called()

    @patch("src.services.character_service.create_character")
    def test_create_raises_when_llm_returns_empty(self, mock_create_character):
        mock_create_character.return_value = ""

        session = MagicMock()
        description = CharacterDescriptionCreate(
            description="A quick and cunning thief with sharp eyes",
            campaign_id=1,
        )

        with pytest.raises(ValueError, match="LLM did not return a response"):
            create(description, session)

        session.add.assert_not_called()
