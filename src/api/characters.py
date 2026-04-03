from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session
from src.api.dependencies import get_current_user
from src.db.db import get_session
from src.models.character import Character, CharacterDescriptionCreate, HeroClass, Race
from src.models.message_history import MessageHistory
from src.models.turn import TurnRequest, TurnResponse
from src.models.user import User
from src.services.character_service import (
    create,
    create_preview,
    get_all_races,
    get_character_turns,
    get_hero_classes,
    get_user_characters,
)
from src.services.embedding_service import extract_and_store_memories
from src.services.turn_service import take_turn
from collections.abc import Sequence

character_router = APIRouter(prefix="/characters", tags=["characters"])


@character_router.get("/", status_code=201)
def get_characters(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    print(f"got user {user}")
    return get_user_characters(session, user)


@character_router.post("/", status_code=201)
def create_character(
    character: Character,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        return create(character, session, user)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@character_router.post("/preview", status_code=201)
def create_character_preview(
    character_description: CharacterDescriptionCreate,
    _: User = Depends(get_current_user),
):
    try:
        return create_preview(character_description)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@character_router.get("/classes", status_code=201)
def get_classes(
    session: Session = Depends(get_session), _: User = Depends(get_current_user)
) -> Sequence[HeroClass]:
    return get_hero_classes(session)


@character_router.get("/races", status_code=201)
def get_races(
    session: Session = Depends(get_session), _: User = Depends(get_current_user)
) -> Sequence[Race]:
    return get_all_races(session)


@character_router.get("/{id}")
def get_character(
    id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    character = session.get(Character, id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    if character.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return character


@character_router.get("/{id}/turns")
def get_turns(
    id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Sequence[MessageHistory]:
    character = session.get(Character, id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    if character.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return get_character_turns(id, session)


@character_router.post("/{id}/turns", status_code=201)
def play_turn(
    id: int,
    turn_request: TurnRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TurnResponse:
    character = session.get(Character, id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    if character.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        message = take_turn(id, turn_request.message, session, user)
        assert character.campaign_id is not None
        background_tasks.add_task(
            extract_and_store_memories,
            character.campaign_id,
            [turn_request.message, message],
        )
        return TurnResponse(message=message)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
