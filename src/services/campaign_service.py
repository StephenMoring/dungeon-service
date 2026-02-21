# TODO: campaign service layer for storing messages and updating character stats.

import json
from sqlmodel import Session
from src.models.campaign import Campaign, CampaignCheckpoint, CampaignDescriptionCreate
from src.services.dm_agent import create_campaign


def create(campaign_description: CampaignDescriptionCreate, session: Session) -> str:
    campaign_json = create_campaign(campaign_description.description, session)
    print("the json returned from the llm")
    print(campaign_json)
    if not campaign_json:
        raise ValueError("LLM did not return a response")
    if campaign_json.startswith("```"):
        campaign_json = (
            campaign_json.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
    try:
        campaign = json.loads(campaign_json)
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid json")

    campaign["description"] = campaign_description.description
    checkpoint_ids = campaign["checkpoint_ids"]
    new_campaign = Campaign(**campaign)
    with session:
        session.add(new_campaign)
        session.commit()

        if not new_campaign.id:
            session.rollback()
            raise ValueError("campaign failed to create")

        for id in checkpoint_ids:
            new_campaign_checkpoint = CampaignCheckpoint(
                campaign_id=new_campaign.id,
                checkpoint_id=id,
                campaign=new_campaign,
                order=1,
                status="new",
            )
            session.add(new_campaign_checkpoint)
        session.commit()
        session.refresh(new_campaign)
        return new_campaign.name
