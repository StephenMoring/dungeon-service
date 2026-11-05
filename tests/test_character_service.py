import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy

from src.models.character import CharacterDescriptionCreate
from src.services.character_service import (
    InvalidPreview,
    create_from_preview,
    create_preview,
)
from src.config import SECRET_KEY
from src.services.auth_service import create_jwt
from src.models.user import User


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


def preview_token(user, **overrides):
    """A token as create_preview would issue it, for `user`."""
    with patch("src.services.character_service.create_character") as llm:
        llm.return_value = json.dumps({**json.loads(VALID_LLM_RESPONSE), **overrides})
        return create_preview(DESCRIPTION, user)["preview_token"]


class TestCreate:
    def test_saves_exactly_the_generated_sheet_for_the_user(self, user):
        session = MagicMock()

        result = create_from_preview(preview_token(user), session, user)

        (saved,) = session.add.call_args.args
        assert saved is result
        assert saved.user_id == user.id
        assert saved.id is None and saved.campaign_id is None
        assert (saved.name, saved.hero_class, saved.age) == ("Kael", "rogue", 24)
        assert (saved.strength, saved.agility, saved.luck) == (4, 9, 7)
        assert saved.biography.startswith("A former street thief")
        session.commit.assert_called_once()

    def test_refuses_another_players_preview(self, user):
        other = User(id=2, discord_id="2", username="other", avatar_url="")

        with pytest.raises(InvalidPreview):
            create_from_preview(preview_token(other), MagicMock(), user)

    def test_refuses_a_tampered_preview(self, user):
        header, payload, signature = preview_token(user).split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
        claims["sheet"]["strength"] = 10
        forged = (
            base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        )

        with pytest.raises(InvalidPreview):
            create_from_preview(f"{header}.{forged}.{signature}", MagicMock(), user)

    def test_refuses_an_expired_preview(self, user):
        claims = jwt.decode(preview_token(user), options={"verify_signature": False})
        claims["exp"] = datetime.now(UTC) - timedelta(minutes=1)
        expired = jwt.encode(claims, SECRET_KEY, algorithm="HS256")

        with pytest.raises(InvalidPreview, match="expired"):
            create_from_preview(expired, MagicMock(), user)

    def test_a_session_token_is_not_a_preview(self, user):
        with pytest.raises(InvalidPreview):
            create_from_preview(create_jwt(user), MagicMock(), user)


class TestCreatePreview:
    @patch("src.services.character_service.create_character")
    def test_returns_parsed_sheet(self, mock_create_character, user):
        mock_create_character.return_value = VALID_LLM_RESPONSE

        result = create_preview(DESCRIPTION, user)

        assert result["agility"] == 9
        assert result["age"] == 24

    @patch("src.services.character_service.create_character")
    def test_sends_all_fields_to_dm_agent(self, mock_create_character, user):
        mock_create_character.return_value = VALID_LLM_RESPONSE

        create_preview(DESCRIPTION, user)

        prompt = mock_create_character.call_args.args[0]
        for value in ("Kael", "sharp eyes", "rogue", "human"):
            assert value in prompt

    @pytest.mark.parametrize("llm_output", [None, ""])
    @patch("src.services.character_service.create_character")
    def test_raises_when_llm_returns_nothing(
        self, mock_create_character, llm_output, user
    ):
        mock_create_character.return_value = llm_output

        with pytest.raises(ValueError, match="LLM did not return a response"):
            create_preview(DESCRIPTION, user)

    @patch("src.services.character_service.create_character")
    def test_raises_on_invalid_json(self, mock_create_character, user):
        mock_create_character.return_value = "not json"

        with pytest.raises(ValueError, match="LLM returned invalid json"):
            create_preview(DESCRIPTION, user)


class TestPreviewSheet:
    @patch("src.services.character_service.create_character")
    def test_returns_the_sheet_and_a_token_for_it(self, llm, user):
        llm.return_value = VALID_LLM_RESPONSE

        preview = create_preview(DESCRIPTION, user)

        assert preview["strength"] == 4
        assert preview["biography"].startswith("A former street thief")
        assert isinstance(preview["preview_token"], str)

    @pytest.mark.parametrize(("generated", "kept"), [(11, 10), (0, 1), (-4, 1), (7, 7)])
    @patch("src.services.character_service.create_character")
    def test_keeps_generated_stats_on_the_1_to_10_scale(
        self, llm, user, generated, kept
    ):
        llm.return_value = json.dumps(
            {**json.loads(VALID_LLM_RESPONSE), "luck": generated}
        )

        preview = create_preview(DESCRIPTION, user)

        assert preview["luck"] == kept
        saved = create_from_preview(preview["preview_token"], MagicMock(), user)
        assert saved.luck == kept
