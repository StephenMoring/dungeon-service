from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy
from src.api.dependencies import get_current_user
from src.db.db import get_session
from src.main import app
from src.models.character import Character
from src.models.user import User


@pytest.fixture
def user() -> User:
    return User(id=1, discord_id="1234", username="tester", avatar_url="")


@pytest.fixture
def session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(user, session):
    """TestClient authenticated as `user`, with a mocked DB session."""
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(session):
    """TestClient with real auth (no user override) and a mocked DB session."""
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_character(**kwargs) -> Character:
    defaults = dict(
        id=1,
        user_id=1,
        campaign_id=1,
        name="Gandalf",
        hero_class="wizard",
        biography="A learned wizard who has spent his life in a library",
        description="Tall and ragged, with an aura of great wisdom",
        age=55,
        strength=7,
        perception=6,
        endurance=4,
        charisma=8,
        intelligence=10,
        agility=3,
        luck=5,
    )
    defaults.update(kwargs)
    return Character(**defaults)
