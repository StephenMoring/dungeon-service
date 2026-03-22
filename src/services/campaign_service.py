# TODO: campaign service layer for storing messages and updating character stats.

import json
from sqlmodel import Session
from src.models.campaign import Campaign, CampaignCheckpoint, CampaignDescriptionCreate
from src.services.dm_agent import create_campaign


def create(campaign_description: CampaignDescriptionCreate, session: Session) -> str:
    campaign_json = create_campaign(campaign_description.description, session)
    # TODO: will need to also pass in the character we are creating this campaign with
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
    checkpoint_ids = campaign.pop("checkpoint_ids")
    new_campaign = Campaign(**campaign)
    try:
        with session:
            session.add(new_campaign)
            session.flush()

            if not new_campaign.id:
                raise ValueError("campaign failed to create")

            for order, id in enumerate(checkpoint_ids):
                new_campaign_checkpoint = CampaignCheckpoint(
                    campaign_id=new_campaign.id,
                    checkpoint_id=id,
                    campaign=new_campaign,
                    order=order,
                    status="new",
                )
                session.add(new_campaign_checkpoint)

            session.commit()
            session.refresh(new_campaign)
            return new_campaign
    except Exception as e:
        raise ValueError(f"failed to save Campaign and Checkpoints {e}") from e
