from datetime import datetime, timezone, timedelta
import jwt
from sqlmodel import Session, select
from src.config import SECRET_KEY
from src.models.user import User


def create_jwt(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
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
    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
