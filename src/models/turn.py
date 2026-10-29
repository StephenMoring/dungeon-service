from sqlmodel import SQLModel


class TurnRequest(SQLModel):
    message: str
