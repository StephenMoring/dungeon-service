from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.api.characters import character_router
from src.db.db import create_db_and_tables
from src.models import (
    character,
)  # TODO - temporary until we are deploying in more of a production state


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(character_router)


@app.get("/health")
def hello():
    return "App is up and healthy"
