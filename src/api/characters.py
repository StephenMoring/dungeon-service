from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, col
from src.api.dependencies import get_current_user
from src.db.db import get_session, engine
from src.models.character import Character, CharacterDescriptionCreate, HeroClass
from src.models.campaign import Campaign, CampaignCheckpoint, Checkpoint
from src.models.message_history import MessageHistory
from src.models.turn import TurnRequest
from src.models.user import User
from src.services.character_service import (
    create,
    create_preview,
    get_hero_classes,
    get_user_characters,
)
from src.services.turn_service import take_turn
from src.services.dm_agent import process_turn_stream

character_router = APIRouter(prefix="/characters", tags=["characters"])


@character_router.get("/", status_code=201)
def get_characters(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
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


@character_router.get("/{id}")
def get_character(
    id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    character = session.get(Character, id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


@character_router.post("/{id}/turns", status_code=201)
def play_turn(
    id: int,  # what the hell do I take in here
    turn_request: TurnRequest,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    try:
        return take_turn(id, turn_request.message, session)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@character_router.get("/classes", status_code=201)
def get_classes(
    session: Session = Depends(get_session), _: User = Depends(get_current_user)
):
    return get_hero_classes(session)


# @character_router.post("/{id}/turns/stream")
# async def play_turn_stream(
#     id: int,
#     turn_request: TurnRequest,
#     session: Session = Depends(get_session),
# ):
#     character = session.get(Character, id)
#     if not character:
#         raise HTTPException(status_code=404, detail=f"Character {id} not found")
#
#     campaign = session.get(Campaign, character.campaign_id)
#     if not campaign:
#         raise HTTPException(status_code=404, detail="Campaign not found")
#
#     statement = (
#         select(CampaignCheckpoint)
#         .where(CampaignCheckpoint.campaign_id == campaign.id)
#         .where(col(CampaignCheckpoint.status).not_in(["campaign", "locked"]))
#         .order_by(col(CampaignCheckpoint.order))
#         .limit(1)
#     )
#     current_campaign_checkpoint = session.exec(statement).first()
#     if not current_campaign_checkpoint:
#         raise HTTPException(status_code=404, detail="No active checkpoint found")
#
#     current_checkpoint_detail = session.get(
#         Checkpoint, current_campaign_checkpoint.checkpoint_id
#     )
#
#     recent_messages_statement = (
#         select(MessageHistory)
#         .where(MessageHistory.campaign_id == campaign.id)
#         .where(MessageHistory.character_id == character.id)
#         .order_by(col(MessageHistory.created_at).desc())
#         .limit(10)
#     )
#     recent_messages = list(reversed(session.exec(recent_messages_statement).all()))
#
#     turn = {
#         "character": character,
#         "campaign": campaign,
#         "current_checkpoint": current_checkpoint_detail,
#         "recent_messages": recent_messages,
#         "message": turn_request.message,
#     }
#
#     full_response = []
#
#     async def generate():
#         async for chunk in process_turn_stream(turn):
#             full_response.append(chunk)
#             yield chunk
#         # Persist after streaming completes using a fresh session
#         response_text = "".join(full_response)
#         with Session(engine) as persist_session:
#             persist_session.add(MessageHistory(
#                 campaign_id=campaign.id,
#                 character_id=character.id,
#                 role="user",
#                 content=turn_request.message,
#             ))
#             persist_session.add(MessageHistory(
#                 campaign_id=campaign.id,
#                 character_id=character.id,
#                 role="assistant",
#                 content=response_text,
#             ))
#             persist_session.commit()
#
#     return StreamingResponse(generate(), media_type="text/plain")
