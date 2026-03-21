from sqlmodel import Field, Relationship, SQLModel


class message_history(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    message: str
