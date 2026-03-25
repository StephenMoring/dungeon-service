from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from src.db.db import get_session
from src.services.auth_service import add_user, create_jwt
import httpx
from src.config import (
    DISCORD_CLIENT_SECRET,
    DISCORD_REDIRECT_URI,
    DISCORD_CLIENT_ID,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/discord/callback", status_code=201)
async def discord_callback(code: str, session: Session = Depends(get_session)):
    async with httpx.AsyncClient() as client:  # type: ignore[reportGeneralTypeIssues]
        response = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
            },
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Invalid or expired Discord code"
            )

        access_token = response.json()["access_token"]

        user_response = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch discord user")

        discord_user = user_response.json()
        user = add_user(discord_user, session)

        assert user.id is not None
        token = create_jwt(user.id)

        return {"access_token": token, "token_type": "bearer"}
