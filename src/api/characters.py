from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from src.db.db import get_session
from src.models.character import CharacterDescriptionCreate
from src.services.character_service import create
from src.services.turn_service import take_turn

character_router = APIRouter(prefix="/characters", tags=["characters"])


@character_router.post("/", status_code=201)
def create_character(
    character_description: CharacterDescriptionCreate,
    session: Session = Depends(get_session),
):
    try:
        return create(character_description, session)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@character_router.post("/{id}/turns", status_code=201)
def play_turn(
    id: str,  # what the hell do I take in here
    session: Session = Depends(get_session),
):
    print(id)
    try:
        return take_turn(id, session)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
