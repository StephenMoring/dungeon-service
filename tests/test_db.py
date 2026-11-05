import pytest

from src.config.config import flag
from src.db.db import engine_url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@localhost:5432/dungeon",
        "postgresql+psycopg2://u:p@localhost:5432/dungeon",
    ],
)
def test_uses_the_installed_psycopg2_driver(url):
    # SQLAlchemy 2.1 maps a bare postgresql:// to psycopg 3, which isn't installed.
    assert engine_url(url).drivername == "postgresql+psycopg2"
    assert engine_url(url).database == "dungeon"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), ("", False), ("false", False), ("0", False), ("true", True), ("1", True), ("TRUE", True)],
)
def test_sql_logging_is_off_unless_turned_on(value, expected):
    # SQL logging writes every query, players' story text included, to the logs.
    assert flag(value) is expected


def test_api_docs_can_be_turned_off(monkeypatch):
    # Production sets API_DOCS=false so /docs and /openapi.json aren't public.
    from fastapi.testclient import TestClient

    import src.main as main

    off = main.create_app(api_docs=False)
    on = main.create_app(api_docs=True)

    assert TestClient(off).get("/openapi.json").status_code == 404
    assert TestClient(off).get("/docs").status_code == 404
    assert TestClient(on).get("/openapi.json").status_code == 200
