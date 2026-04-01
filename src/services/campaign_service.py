import json
from sqlmodel import Session
from src.models.campaign import (
    Campaign,
    CampaignCheckpoint,
    CreateCampaignResponse,
    CreateCampaignRequest,
)
from src.models.character import Character
from src.models.message_history import MessageHistory
from src.models.user import User
from src.services.dm_agent import create_campaign


def create(
    campaign_description: CreateCampaignRequest, session: Session, user: User
) -> CreateCampaignResponse:
    character = session.get(Character, campaign_description.character_id)
    if not character:
        raise ValueError("Character not found")
    if character.user_id != user.id:
        raise ValueError("Character does not belong to this user")

    campaign_json = create_campaign(campaign_description.description, session)
    if not campaign_json:
        raise ValueError("LLM did not return a response")

    try:
        campaign = json.loads(campaign_json)
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid json")

    checkpoint_ids = campaign.pop("checkpoint_ids")
    opening_message = campaign.pop("opening_message")
    new_campaign = Campaign(**campaign, description=campaign_description.description)

    session.add(new_campaign)
    session.flush()

    if not new_campaign.id:
        raise ValueError("campaign failed to create")

    for order, checkpoint_id in enumerate(checkpoint_ids):
        session.add(
            CampaignCheckpoint(
                campaign_id=new_campaign.id,
                checkpoint_id=checkpoint_id,
                order=order,
                status="new" if order == 0 else "locked",
            )
        )

    character.campaign_id = new_campaign.id
    session.add(character)

    assert character.id is not None
    session.add(
        MessageHistory(
            campaign_id=new_campaign.id,
            character_id=character.id,
            role="assistant",
            content=opening_message,
        )
    )

    session.commit()
    session.refresh(new_campaign)
    return CreateCampaignResponse(
        campaign=new_campaign, opening_message=opening_message
    )
