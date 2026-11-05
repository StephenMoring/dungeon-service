from sqlalchemy.engine import URL, make_url
from sqlmodel import Session, SQLModel, create_engine

from src.config import DATABASE_URL, DB_ECHO


def engine_url(database_url: str) -> URL:
    """The database URL with the psycopg2 driver named explicitly: SQLAlchemy 2.1 maps
    a bare postgresql:// to psycopg 3, which this project doesn't install."""
    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    return url


# DB_ECHO logs every SQL statement, players' story text included: local debugging only.
engine = create_engine(engine_url(DATABASE_URL), echo=DB_ECHO)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
