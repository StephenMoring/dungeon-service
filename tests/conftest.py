from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

import src.models.campaign  # noqa: F401 - ensures Campaign is registered with SQLAlchemy
from src.api.dependencies import get_current_user
from src.db.db import get_session
from src.main import app
from src.models.character import Character
from src.models.user import User


@pytest.fixture(autouse=True)
def no_memory_lookup():
    """Keep tests off Voyage: turn context loads with no memories unless a test patches it."""
    from src.services.memory_service import RetrievedMemories

    with patch(
        "src.services.turn_service.retrieve_memories",
        return_value=RetrievedMemories(),
    ):
        yield


@pytest.fixture(autouse=True)
def no_combat_lookups():
    """Turn routes and context load with no fight going on and an empty bestiary,
    unless a test patches these again."""
    with (
        patch("src.services.turn_service.load_bestiary", return_value=[]),
        patch("src.api.characters.active_encounter", return_value=None),
    ):
        yield


@pytest.fixture(autouse=True)
def no_rate_limits():
    """Route tests don't count Claude calls unless they patch check_and_record."""
    with patch("src.api.dependencies.check_and_record"):
        yield


# Sent by dungeon-web on every request; the API refuses writes without it (CSRF).
FRONTEND_HEADERS = {"X-Requested-With": "dungeon-web"}


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
    yield TestClient(app, headers=FRONTEND_HEADERS)
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(session):
    """TestClient with real auth (no user override) and a mocked DB session."""
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app, headers=FRONTEND_HEADERS)
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


def compiled_sql(statement) -> str:
    """Render a SQLModel statement as Postgres SQL with literal values, for asserting filters."""
    return str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
