from sqlmodel import Field, Relationship, SQLModel


class Campaign(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    characters: list["Character"] = Relationship(back_populates="campaign")  # type: ignore[name-defined]


# potential link table if many to many relationship for characters and campaigns
# class CampaignCharacterLink(SQLModel, table=True):
