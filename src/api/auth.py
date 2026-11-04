import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session

from src.api.dependencies import get_current_user
from src.config import (
    COOKIE_SECURE,
    DISCORD_CLIENT_ID,
    DISCORD_CLIENT_SECRET,
    DISCORD_REDIRECT_URI,
)
from src.db.db import get_session
from src.models.user import CallBackCode, User, UserPublic
from src.services.auth_service import (
    SESSION_COOKIE,
    SESSION_DAYS,
    add_user,
    create_jwt,
    user_for_token,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _public(user: User) -> UserPublic:
    assert user.id is not None
    return UserPublic(id=user.id, username=user.username, avatar_url=user.avatar_url)


@auth_router.post("/discord/callback", status_code=201)
async def discord_callback(
    code: CallBackCode, response: Response, session: Session = Depends(get_session)
) -> dict[str, UserPublic]:
    async with httpx.AsyncClient() as client:  # type: ignore[reportGeneralTypeIssues]
        token_response = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code.code,
                "redirect_uri": DISCORD_REDIRECT_URI,
            },
        )
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Invalid or expired Discord code"
            )

        access_token = token_response.json()["access_token"]

        user_response = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch discord user")

        discord_user = user_response.json()
        user = add_user(discord_user, session)

        # The token never reaches page JavaScript: only the browser holds it.
        response.set_cookie(
            SESSION_COOKIE,
            create_jwt(user),
            max_age=SESSION_DAYS * 24 * 3600,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            path="/",
        )
        return {"user": _public(user)}


@auth_router.get("/me")
def me(user: User = Depends(get_current_user)) -> UserPublic:
    """Who is signed in; the frontend asks this since it cannot read the cookie."""
    return _public(user)


@auth_router.post("/logout", status_code=204)
def logout(
    request: Request, response: Response, session: Session = Depends(get_session)
) -> None:
    """End every session for this user and clear this browser's cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        try:
            user = user_for_token(token, session)
        except ValueError:
            pass  # already invalid: nothing to revoke, still clear the cookie
        else:
            user.token_version += 1
            session.add(user)
            session.commit()
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, secure=COOKIE_SECURE, samesite="lax"
    )
