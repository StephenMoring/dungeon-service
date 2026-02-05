from fastapi import APIRouter, Depends
from sqlmodel import Session
from src.db.db import get_session
from src.models.character import CharacterDescriptionCreate
from src.services.character_service import create

character_router = APIRouter(prefix="/characters", tags=["characters"])


@character_router.post("/", status_code=201)
def create_character(
    character_description: CharacterDescriptionCreate,
    session: Session = Depends(get_session),
):
    created_character = create(character_description, session)
    return created_character
