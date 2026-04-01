from sqlmodel import SQLModel


class TurnRequest(SQLModel):
    message: str


class TurnResponse(SQLModel):
    message: str
