from src.config import DATABASE_URL
from sqlmodel import Session, create_engine, SQLModel

engine = create_engine(
    DATABASE_URL, echo=True
)  # echo=True for local development only, turns on db logging


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
