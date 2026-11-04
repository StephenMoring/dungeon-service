from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from src.db.db import get_session
from src.models.user import User
from src.services.auth_service import SESSION_COOKIE, user_for_token


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """The signed-in user, from the httpOnly session cookie. Every route that returns
    player data filters by this user's id; the client can never choose it."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")
    try:
        return user_for_token(token, session)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
