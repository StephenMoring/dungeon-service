from sqlmodel import Field, SQLModel
from datetime import datetime, timezone


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    discord_id: str
    username: str
    avatar_url: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CallBackCode(SQLModel):
    code: str
