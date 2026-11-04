import json
from collections import defaultdict

from sqlmodel import Session, col, select

from src.models.campaign import (
    Campaign,
    CampaignCheckpoint,
    CampaignCheckpointRead,
    CampaignWithDetails,
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


def list_for_user(session: Session, user: User) -> list[CampaignWithDetails]:
    """The user's campaigns, each with the user's characters in it and its checkpoints in order."""
    # Campaigns have no owner column; a campaign belongs to whoever owns its character.
    campaigns = session.exec(
        select(Campaign)
        .join(Character, col(Character.campaign_id) == Campaign.id)
        .where(Character.user_id == user.id)
        .distinct()
    ).all()
    if not campaigns:
        return []
    campaign_ids = [c.id for c in campaigns]

    characters = session.exec(
        select(Character).where(
            col(Character.campaign_id).in_(campaign_ids),
            Character.user_id == user.id,
        )
    ).all()
    checkpoints = session.exec(
        select(CampaignCheckpoint)
        .where(col(CampaignCheckpoint.campaign_id).in_(campaign_ids))
        .order_by(col(CampaignCheckpoint.campaign_id), col(CampaignCheckpoint.order))
    ).all()

    characters_by_campaign: dict[int | None, list[Character]] = defaultdict(list)
    for character in characters:
        characters_by_campaign[character.campaign_id].append(character)
    checkpoints_by_campaign: dict[int, list[CampaignCheckpointRead]] = defaultdict(list)
    for checkpoint in checkpoints:
        checkpoints_by_campaign[checkpoint.campaign_id].append(
            CampaignCheckpointRead.model_validate(checkpoint, from_attributes=True)
        )

    return [
        CampaignWithDetails(
            id=campaign.id,
            name=campaign.name,
            theme=campaign.theme,
            description=campaign.description,
            characters=characters_by_campaign[campaign.id],
            campaign_checkpoints=checkpoints_by_campaign[campaign.id]
            if campaign.id
            else [],
        )
        for campaign in campaigns
    ]
