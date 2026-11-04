from sqlmodel import Field, SQLModel
from datetime import datetime, timezone


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    discord_id: str
    username: str
    avatar_url: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    token_version: int = 0  # bumped on logout to end every session


class UserPublic(SQLModel):
    """What the API says about a user: never discord_id or token_version."""

    id: int
    username: str
    avatar_url: str | None  # NULL for users with no Discord avatar


class CallBackCode(SQLModel):
    code: str
