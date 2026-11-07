from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from src.api.dependencies import enforce_limit, get_current_user
from src.db.db import get_session
from src.models.character import (
    Character,
    CharacterDescriptionCreate,
    CharacterSaveRequest,
    HeroClass,
    Race,
)
from src.models.combat import CombatActionRequest
from src.models.message_history import MessageHistory
from src.models.turn import TurnRequest
from src.models.user import User
from src.services.character_service import (
    InvalidPreview,
    create_from_preview,
    create_preview,
    get_all_races,
    get_character_turns,
    get_hero_classes,
    get_user_characters,
)
from src.services.combat_service import (
    CannotRest,
    InvalidTarget,
    NoActiveEncounter,
    active_encounter,
    current_state,
    describe_action,
    finish_rest,
    load_bestiary,
    play_round,
    start_rest,
)
from src.services.turn_service import (
    load_turn_context,
    stream_combat_round,
    stream_turn,
)
from collections.abc import Sequence

character_router = APIRouter(prefix="/characters", tags=["characters"])


@character_router.get("/", status_code=201)
def get_characters(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    return get_user_characters(session, user)


@character_router.post("/", status_code=201)
def create_character(
    request: CharacterSaveRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        return create_from_preview(request.preview_token, session, user)
    except InvalidPreview as e:
        raise HTTPException(status_code=400, detail=str(e))


@character_router.post("/preview", status_code=201)
def create_character_preview(
    character_description: CharacterDescriptionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    enforce_limit(session, user, "preview")
    try:
        return create_preview(character_description, user)
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


@character_router.post("/{id}/turns/stream")
def play_turn_stream(
    id: int,
    turn_request: TurnRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    character = owned_character(id, session, user)
    refuse_if_dead(character)
    if active_encounter(session, id):
        raise HTTPException(
            status_code=409, detail="You're in a fight. Choose a combat action."
        )
    if character.rest_started_at is not None:
        raise HTTPException(status_code=409, detail="You're resting by the fire.")
    enforce_limit(session, user, "turn")
    try:
        turn = load_turn_context(id, turn_request.message, session)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return StreamingResponse(
        stream_turn(turn, background_tasks), media_type="text/event-stream"
    )


def owned_character(id: int, session: Session, user: User) -> Character:
    character = session.get(Character, id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    if character.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return character


def refuse_if_dead(character: Character) -> None:
    if character.died_at is not None:
        raise HTTPException(
            status_code=409, detail=f"{character.name} has died. Their story is over."
        )


@character_router.get("/{id}/encounter")
def get_encounter(
    id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict | None:
    """The character's active fight, or null."""
    character = owned_character(id, session, user)
    return current_state(session, character, load_bestiary(session))


@character_router.post("/{id}/combat/stream")
def play_combat_round(
    id: int,
    request: CombatActionRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """One combat round: the server rolls and applies it (committed before the DM
    narrates), then streams `round`, `combat`, `text` and `done`."""
    character = owned_character(id, session, user)
    refuse_if_dead(character)
    if not active_encounter(session, id):
        raise HTTPException(status_code=409, detail="There's no fight going on.")
    enforce_limit(session, user, "turn")
    bestiary = load_bestiary(session)
    try:
        result, state = play_round(
            session, character, bestiary, request.action, request.target_id
        )
    except NoActiveEncounter as e:
        raise HTTPException(status_code=409, detail=str(e))
    except InvalidTarget as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        turn = load_turn_context(id, describe_action(result), session)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return StreamingResponse(
        stream_combat_round(turn, result, state, background_tasks),
        media_type="text/event-stream",
    )


@character_router.post("/{id}/rest")
def rest(
    id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Start resting, or get the rest already under way: `seconds_left` until
    POST .../rest/finish heals. No Claude call, so no rate limit."""
    character = owned_character(id, session, user)
    try:
        return start_rest(session, character)
    except CannotRest as e:
        raise HTTPException(status_code=409, detail=str(e))


@character_router.post("/{id}/rest/finish")
def finish_resting(
    id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Character:
    """Heal to full, once the rest has lasted long enough (409 before that)."""
    character = owned_character(id, session, user)
    try:
        return finish_rest(session, character)
    except CannotRest as e:
        raise HTTPException(status_code=409, detail=str(e))
