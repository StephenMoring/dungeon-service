# TODO: campaign service layer for storing messages and updating character stats.

import json
from sqlmodel import Session
from src.models.campaign import Campaign, CampaignDescriptionCreate
from src.services.dm_agent import create_campaign


def create(campaign_description: CampaignDescriptionCreate, session: Session) -> str:
    campaign_json = create_campaign(campaign_description.description, session)
    if not campaign_json:
        raise ValueError("LLM did not return a response")
    try:
        campaign = json.loads(campaign_json)
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid json")

    campaign["description"] = campaign_description.description
    new_campaign = Campaign(**campaign)
    with session:
        session.add(new_campaign)
        session.commit()
        session.refresh(new_campaign)
        return new_campaign.name
