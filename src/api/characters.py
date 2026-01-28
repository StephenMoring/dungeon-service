from fastapi import APIRouter, Depends
from sqlmodel import Session
from src.db.db import get_session
from src.models.character import Character

character_router = APIRouter(prefix="/characters", tags=["characters"])


@character_router.post("/", status_code=201)
def create_character(character: Character, session: Session = Depends(get_session)):
    # needs to take in the txt submitted by user and stores to db, not sureif actually needs to send this part to llm
    with session:
        session.add(character)
        session.commit()

    print("character created successfully")
