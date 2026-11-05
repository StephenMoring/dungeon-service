from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest

from src.config import SECRET_KEY
from src.models.user import User
from src.services.auth_service import (
    SESSION_COOKIE,
    SESSION_DAYS,
    create_jwt,
    validate_jwt,
)
from tests.conftest import make_character

CSRF = {"X-Requested-With": "dungeon-web"}


def token(user_id: int = 1, ver: int = 0, expires_in=timedelta(days=1)) -> str:
    payload = {
        "sub": str(user_id),
        "ver": ver,
        "exp": datetime.now(timezone.utc) + expires_in,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def session_cookie(value: str) -> dict:
    return {"Cookie": f"{SESSION_COOKIE}={value}"}


class TestJwt:
    def test_round_trip_carries_user_and_version(self):
        payload = validate_jwt(create_jwt(User(id=42, token_version=3)))

        assert payload["sub"] == "42"
        assert payload["ver"] == 3

    def test_lasts_a_week(self):
        payload = validate_jwt(create_jwt(User(id=42)))

        lifetime = payload["exp"] - datetime.now(timezone.utc).timestamp()
        assert (
            timedelta(days=SESSION_DAYS) - timedelta(minutes=1)
            < timedelta(seconds=lifetime)
            <= timedelta(days=SESSION_DAYS)
        )


class TestSessionCookie:
    """Uses anon_client so the real get_current_user dependency runs."""

    def test_missing_cookie_returns_401(self, anon_client):
        assert anon_client.get("/campaigns/").status_code == 401

    def test_bearer_header_is_no_longer_accepted(self, anon_client, session, user):
        session.get.return_value = user

        response = anon_client.get(
            "/campaigns/", headers={"Authorization": f"Bearer {token()}"}
        )

        assert response.status_code == 401

    def test_invalid_cookie_returns_401(self, anon_client):
        response = anon_client.get("/campaigns/", headers=session_cookie("not-a-jwt"))

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid session"

    def test_expired_cookie_returns_401(self, anon_client):
        expired = token(expires_in=timedelta(minutes=-1))

        response = anon_client.get("/campaigns/", headers=session_cookie(expired))

        assert response.status_code == 401
        assert response.json()["detail"] == "Session expired"

    def test_unknown_user_returns_401(self, anon_client, session):
        session.get.return_value = None

        response = anon_client.get("/campaigns/", headers=session_cookie(token(99)))

        assert response.status_code == 401

    def test_token_from_before_logout_returns_401(self, anon_client, session):
        # Logging out bumps token_version, so copies of the old token stop working.
        session.get.return_value = User(
            id=1, discord_id="1", username="u", token_version=1
        )

        response = anon_client.get("/campaigns/", headers=session_cookie(token(ver=0)))

        assert response.status_code == 401
        assert response.json()["detail"] == "Session ended"

    def test_valid_cookie_is_accepted(self, anon_client, session, user):
        session.get.return_value = user
        session.exec.return_value.all.return_value = []

        response = anon_client.get("/campaigns/", headers=session_cookie(token()))

        assert response.status_code == 200

    def test_character_owned_by_another_user_returns_403(self, client, session):
        session.get.return_value = make_character(user_id=2)

        response = client.get("/characters/1")

        assert response.status_code == 403


class TestCsrfHeader:
    """Requests that change data must carry X-Requested-With. Another site can't set
    a custom header on a cross-site request without a CORS preflight we refuse."""

    @pytest.mark.parametrize("value", ["", "evil-site"])
    def test_unsafe_request_without_header_is_refused(self, client, value):
        # The test client sends the header by default; override it.
        response = client.delete("/campaigns/3", headers={"X-Requested-With": value})

        assert response.status_code == 403
        assert response.json()["detail"] == "Missing X-Requested-With header"

    @patch("src.api.campaigns.delete_for_user")
    def test_unsafe_request_with_header_goes_through(self, _delete, client):
        assert client.delete("/campaigns/3", headers=CSRF).status_code == 204

    def test_reads_need_no_header(self, client, session):
        session.exec.return_value.all.return_value = []

        assert client.get("/campaigns/").status_code == 200


def discord(token_status=200, user_status=200, discord_user=None):
    """Patch the Discord token exchange and user lookup."""
    http = MagicMock()
    http.post = AsyncMock(
        return_value=MagicMock(
            status_code=token_status, json=lambda: {"access_token": "discord-token"}
        )
    )
    http.get = AsyncMock(
        return_value=MagicMock(
            status_code=user_status,
            json=lambda: (
                discord_user or {"id": "555", "username": "wren", "avatar": "abc"}
            ),
        )
    )
    client_cls = MagicMock()
    client_cls.return_value.__aenter__ = AsyncMock(return_value=http)
    client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return patch("src.api.auth.httpx.AsyncClient", client_cls)


@pytest.fixture
def signed_up():
    user = User(
        id=7, discord_id="555", username="wren", avatar_url="a.png", token_version=2
    )
    with patch("src.api.auth.add_user", return_value=user):
        yield user


class TestDiscordCallback:
    def test_sets_an_httponly_session_cookie(self, anon_client, signed_up):
        with discord():
            response = anon_client.post(
                "/auth/discord/callback", json={"code": "c"}, headers=CSRF
            )

        assert response.status_code == 201
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{SESSION_COOKIE}=")
        for flag in ("HttpOnly", "Secure", "SameSite=lax", "Path=/"):
            assert flag.lower() in cookie.lower()
        assert f"Max-Age={SESSION_DAYS * 24 * 3600}" in cookie
        payload = validate_jwt(cookie.split(";")[0].split("=", 1)[1])
        assert (payload["sub"], payload["ver"]) == ("7", 2)

    def test_returns_the_user_but_not_the_token(self, anon_client, signed_up):
        with discord():
            body = anon_client.post(
                "/auth/discord/callback", json={"code": "c"}, headers=CSRF
            ).json()

        assert "jwt" not in body
        assert body["user"] == {"id": 7, "username": "wren", "avatar_url": "a.png"}

    def test_discord_unreachable_is_a_502_not_a_crash(self, anon_client):
        http = MagicMock()
        http.post = AsyncMock(side_effect=httpx.ConnectError("no route to discord.com"))
        client_cls = MagicMock()
        client_cls.return_value.__aenter__ = AsyncMock(return_value=http)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.auth.httpx.AsyncClient", client_cls):
            response = anon_client.post(
                "/auth/discord/callback", json={"code": "c"}, headers=CSRF
            )

        assert response.status_code == 502
        assert response.json()["detail"] == "Couldn't reach Discord. Try again."
        assert "set-cookie" not in response.headers

    def test_bad_code_sets_no_cookie(self, anon_client):
        with discord(token_status=400):
            response = anon_client.post(
                "/auth/discord/callback", json={"code": "c"}, headers=CSRF
            )

        assert response.status_code == 400
        assert "set-cookie" not in response.headers


class TestMe:
    def test_returns_the_signed_in_user(self, client):
        response = client.get("/auth/me")

        assert response.status_code == 200
        assert response.json() == {"id": 1, "username": "tester", "avatar_url": ""}

    def test_requires_a_session(self, anon_client):
        assert anon_client.get("/auth/me").status_code == 401

    def test_user_without_an_avatar(self, client, user):
        user.avatar_url = None  # stored NULL, e.g. the seed user

        response = client.get("/auth/me")

        assert response.status_code == 200
        assert response.json()["avatar_url"] is None


class TestLogout:
    def test_clears_the_cookie_and_ends_every_session(self, anon_client, session):
        user = User(id=1, discord_id="1", username="u", token_version=0)
        session.get.return_value = user

        response = anon_client.post(
            "/auth/logout", headers={**CSRF, **session_cookie(token(ver=0))}
        )

        assert response.status_code == 204
        assert user.token_version == 1
        session.commit.assert_called_once()
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f'{SESSION_COOKIE}=""') or "Max-Age=0" in cookie

    def test_clears_the_cookie_even_without_a_valid_session(self, anon_client):
        response = anon_client.post(
            "/auth/logout", headers={**CSRF, **session_cookie("junk")}
        )

        assert response.status_code == 204
        assert SESSION_COOKIE in response.headers["set-cookie"]
