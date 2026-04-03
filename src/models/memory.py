from datetime import datetime
from typing import Optional
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlmodel import Field, SQLModel


class NpcMemory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    name: str
    role: str | None = None
    disposition: str | None = None
    known_facts: str | None = None
    secrets: str | None = None
    embedding: Optional[list[float]] = Field(
        default=None, sa_column=Column(Vector(1024))
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LocationMemory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    name: str
    description: str | None = None
    events: str | None = None
    embedding: Optional[list[float]] = Field(
        default=None, sa_column=Column(Vector(1024))
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ItemMemory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    name: str
    description: str | None = None
    where_found: str | None = None
    status: str | None = Field(default="held")
    embedding: Optional[list[float]] = Field(
        default=None, sa_column=Column(Vector(1024))
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EventMemory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    summary: str
    category: str | None = None
    embedding: Optional[list[float]] = Field(
        default=None, sa_column=Column(Vector(1024))
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None
