from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class MessageHistory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    character_id: int = Field(foreign_key="character.id")
    role: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
