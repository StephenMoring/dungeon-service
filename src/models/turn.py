from sqlmodel import Field, SQLModel


class TurnRequest(SQLModel):
    message: str = Field(min_length=1, max_length=2000)
