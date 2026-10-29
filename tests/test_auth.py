from datetime import datetime, timedelta, timezone

import jwt

from src.config import SECRET_KEY
from src.services.auth_service import create_jwt, validate_jwt
from tests.conftest import make_character


def expired_token(user_id: int = 1) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


class TestJwt:
    def test_create_and_validate_round_trip(self):
        payload = validate_jwt(create_jwt(42))

        assert payload["sub"] == "42"


class TestProtectedRoutes:
    """Uses anon_client so the real get_current_user dependency runs."""

    def test_missing_token_returns_401(self, anon_client):
        response = anon_client.get("/campaigns/")

        assert response.status_code == 401

    def test_invalid_token_returns_401(self, anon_client):
        response = anon_client.get(
            "/campaigns/", headers={"Authorization": "Bearer not-a-jwt"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid Token"

    def test_expired_token_returns_401(self, anon_client):
        response = anon_client.get(
            "/campaigns/", headers={"Authorization": f"Bearer {expired_token()}"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Token Expired"

    def test_unknown_user_returns_401(self, anon_client, session):
        session.get.return_value = None

        response = anon_client.get(
            "/campaigns/", headers={"Authorization": f"Bearer {create_jwt(99)}"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "User not found"

    def test_valid_token_is_accepted(self, anon_client, session, user):
        session.get.return_value = user
        session.exec.return_value.all.return_value = []

        response = anon_client.get(
            "/campaigns/", headers={"Authorization": f"Bearer {create_jwt(1)}"}
        )

        assert response.status_code == 200

    def test_character_owned_by_another_user_returns_403(self, client, session):
        session.get.return_value = make_character(user_id=2)

        response = client.get("/characters/1")

        assert response.status_code == 403
