from typing import Optional
from sqlmodel import Field, Relationship, SQLModel


class Campaign(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    characters: list["Character"] = Relationship(back_populates="campaign")  # type: ignore[name-defined]
    theme: str
    campaign_checkpoints: list["CampaignCheckpoint"] = Relationship(
        back_populates="campaign"
    )
    description: str


class CreateCampaignRequest(SQLModel):
    character_id: int
    description: str


class CreateCampaignResponse(SQLModel):
    campaign: Campaign
    opening_message: str


class Checkpoint(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str
    setting: str
    key_npcs: str | None = None
    objective: str
    tags: str


class CampaignCheckpoint(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    checkpoint_id: int = Field(foreign_key="checkpoint.id")
    campaign: Optional["Campaign"] = Relationship(back_populates="campaign_checkpoints")
    checkpoint: Optional["Checkpoint"] = Relationship()
    order: int
    status: str = Field(default="locked")
    summary: str | None = None


# potential link table if many to many relationship for characters and campaigns
# class CampaignCharacterLink(SQLModel, table=True):
