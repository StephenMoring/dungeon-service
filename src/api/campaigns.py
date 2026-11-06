from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from src.db.db import get_session
from src.models.campaign import (
    CampaignWithDetails,
    CreateCampaignRequest,
    CreateCampaignResponse,
)
from src.models.character import Character
from src.models.user import User
from src.api.dependencies import enforce_limit, get_current_user
from src.services.campaign_service import (
    DeadCharacter,
    create,
    delete_for_user,
    list_for_user,
)

campaigns_router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@campaigns_router.post("/", status_code=201)
def create_campaign(
    campaign_description: CreateCampaignRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> CreateCampaignResponse:
    enforce_limit(session, user, "campaign")
    try:
        return create(campaign_description, session, user)
    except DeadCharacter as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@campaigns_router.get("/")
def list_campaigns(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> list[CampaignWithDetails]:
    return list_for_user(session, user)


@campaigns_router.get("/{id}/characters")
def list_characters(
    id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return session.exec(
        select(Character).where(
            Character.campaign_id == id, Character.user_id == user.id
        )
    ).all()


@campaigns_router.delete("/{id}", status_code=204)
def delete_campaign(
    id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    try:
        delete_for_user(id, session, user)
    except LookupError:
        # 404 rather than 403, so another player's campaign ids are not confirmed.
        raise HTTPException(status_code=404, detail="Campaign not found")
