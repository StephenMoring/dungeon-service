from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class LlmUsage(SQLModel, table=True):
    """One accepted request that calls Claude (a turn, a preview, a campaign)."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    action: str
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
