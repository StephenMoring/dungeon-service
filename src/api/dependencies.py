from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session
import jwt
from src.db.db import get_session
from src.models.user import User
from src.services.auth_service import validate_jwt

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    try:
        payload = validate_jwt(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token Expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Token")

    user = session.get(User, int(payload["sub"]))

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
