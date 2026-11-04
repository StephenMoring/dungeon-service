from datetime import datetime, timezone, timedelta
import jwt
from sqlmodel import Session, select
from src.config import SECRET_KEY
from src.models.user import User


SESSION_COOKIE = "dungeon_session"
SESSION_DAYS = 7


def create_jwt(user: User) -> str:
    """A session token for `user`, sent to the browser only as an httpOnly cookie."""
    payload = {
        "sub": str(user.id),
        "ver": user.token_version,
        "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def add_user(discord_user: dict, session: Session):
    user = session.exec(
        select(User).where(User.discord_id == discord_user["id"])
    ).first()
    if not user:
        user = User(
            discord_id=discord_user["id"],
            username=discord_user["username"],
            avatar_url=f"https://cdn.discordapp.com/avatars/{discord_user['id']}/{discord_user['avatar']}.png",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def validate_jwt(token: str) -> dict:
    return jwt.decode(
        token, SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "sub"]}
    )


def user_for_token(token: str, session: Session) -> User:
    """The user a session token belongs to. Raises ValueError with a reason if the
    token is invalid, expired, for an unknown user, or from before a logout."""
    try:
        payload = validate_jwt(token)
    except jwt.ExpiredSignatureError:
        raise ValueError("Session expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid session")
    user = session.get(User, int(payload["sub"]))
    if not user:
        raise ValueError("Invalid session")
    if payload.get("ver") != user.token_version:
        raise ValueError("Session ended")
    return user
