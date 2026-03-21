from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from src.db.db import get_session
from src.models.campaign import CampaignDescriptionCreate
from src.services.campaign_service import create, take_turn

campaigns_router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@campaigns_router.post("/", status_code=201)
def create_campaign(
    campaign_description: CampaignDescriptionCreate,
    session: Session = Depends(get_session),
):
    try:
        return create(campaign_description, session)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@campaigns_router.post("/{id}/turns", status_code=201)
def play_campaign_turn(
    id: str,  # what the hell do I take in here
    session: Session = Depends(get_session),
):
    print(id)
    try:
        return take_turn(id, session)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
