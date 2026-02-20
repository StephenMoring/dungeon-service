from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.api.characters import character_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(character_router)


@app.get("/health")
def hello():
    return "App is up and healthy"
