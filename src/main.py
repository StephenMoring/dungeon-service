from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.api.characters import character_router
from src.api.campaigns import campaigns_router
from src.api.auth import auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(character_router)
app.include_router(campaigns_router)
app.include_router(auth_router)


@app.get("/health")
def hello():
    return "App is up and healthy"
