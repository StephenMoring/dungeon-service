import json
from unittest.mock import MagicMock, patch

import pytest
import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy

from src.models.character import CharacterCreate, CharacterDescriptionCreate
from src.services.character_service import create, create_preview


VALID_LLM_RESPONSE = json.dumps(
    {
        "biography": "A former street thief who found purpose after a chance encounter with a dying knight.",
        "age": 24,
        "strength": 4,
        "perception": 8,
        "endurance": 5,
        "charisma": 6,
        "intelligence": 6,
        "agility": 9,
        "luck": 7,
    }
)

DESCRIPTION = CharacterDescriptionCreate(
    name="Kael",
    description="A quick and cunning thief with sharp eyes",
    hero_class="rogue",
    race="human",
)


class TestCreate:
    def test_saves_a_new_character_for_the_user(self, user):
        session = MagicMock()
        details = CharacterCreate(
            name="Gandalf",
            hero_class="wizard",
            biography="b",
            description="d",
            age=55,
            strength=7,
            perception=6,
            endurance=4,
            charisma=8,
            intelligence=10,
            agility=3,
            luck=5,
        )

        result = create(details, session, user)

        (saved,) = session.add.call_args.args
        assert saved is result
        assert saved.user_id == user.id
        assert saved.id is None
        assert saved.campaign_id is None
        assert (saved.name, saved.strength, saved.luck) == ("Gandalf", 7, 5)
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(saved)


class TestCreatePreview:
    @patch("src.services.character_service.create_character")
    def test_returns_parsed_sheet(self, mock_create_character):
        mock_create_character.return_value = VALID_LLM_RESPONSE

        result = create_preview(DESCRIPTION)

        assert result["agility"] == 9
        assert result["age"] == 24

    @patch("src.services.character_service.create_character")
    def test_sends_all_fields_to_dm_agent(self, mock_create_character):
        mock_create_character.return_value = VALID_LLM_RESPONSE

        create_preview(DESCRIPTION)

        prompt = mock_create_character.call_args.args[0]
        for value in ("Kael", "sharp eyes", "rogue", "human"):
            assert value in prompt

    @pytest.mark.parametrize("llm_output", [None, ""])
    @patch("src.services.character_service.create_character")
    def test_raises_when_llm_returns_nothing(self, mock_create_character, llm_output):
        mock_create_character.return_value = llm_output

        with pytest.raises(ValueError, match="LLM did not return a response"):
            create_preview(DESCRIPTION)

    @patch("src.services.character_service.create_character")
    def test_raises_on_invalid_json(self, mock_create_character):
        mock_create_character.return_value = "not json"

        with pytest.raises(ValueError, match="LLM returned invalid json"):
            create_preview(DESCRIPTION)
