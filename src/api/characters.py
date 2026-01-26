from fastapi import APIRouter
from services.dm_agent import chat

character_router = APIRouter(prefix="/characters", tags=["characters"])


@character_router.post("/", status_code=201)
def create_character():
    # needs to take in the txt submitted by user and stores to db, not sureif actually needs to send this part to llm
    print("character created successfully")
