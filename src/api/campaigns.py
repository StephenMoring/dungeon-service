from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from src.db.db import get_session
from src.models.campaign import Campaign, CampaignDescriptionCreate
from src.models.character import Character
from src.models.user import User
from src.api.dependencies import get_current_user
from src.services.campaign_service import create

campaigns_router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@campaigns_router.post("/", status_code=201)
def create_campaign(
    campaign_description: CampaignDescriptionCreate,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    try:
        return create(campaign_description, session)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@campaigns_router.get("/")
def list_campaigns(
    session: Session = Depends(get_session), _: User = Depends(get_current_user)
):
    return session.exec(select(Campaign)).all()


@campaigns_router.get("/{id}/characters")
def list_characters(
    id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    return session.exec(select(Character).where(Character.campaign_id == id)).all()
