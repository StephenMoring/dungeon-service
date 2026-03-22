from sqlmodel import Session, col, select
from src.models.character import Character
from src.models.campaign import Campaign, CampaignCheckpoint, Checkpoint
from src.models.message_history import MessageHistory
from src.services.dm_agent import process_turn


def take_turn(id: int, message: str, session: Session) -> str:
    character = session.get(Character, id)
    if not character:
        raise ValueError("campaign: {id} not found")

    campaign = session.get(Campaign, character.campaign_id)
    if not campaign:
        raise ValueError("Character: {character.campaign_id} not found")

    # grab the first checkpoint that is not complete from the campaign
    statement = (
        select(CampaignCheckpoint)
        .where(CampaignCheckpoint.campaign_id == campaign.id)
        .where(col(CampaignCheckpoint.status).not_in(["campaign", "locked"]))
        .order_by(col(CampaignCheckpoint.order))
        .limit(1)
    )

    current_campaign_checkpoint = session.exec(statement).first()
    if not current_campaign_checkpoint:
        raise ValueError("Checkpoint for campaign could not be found")

    current_checkpoint_detail = session.get(
        Checkpoint, current_campaign_checkpoint.checkpoint_id
    )

    recent_messages_statement = (
        select(MessageHistory)
        .where(MessageHistory.campaign_id == campaign.id)
        .where(MessageHistory.character_id == character.id)
        .order_by(col(MessageHistory.created_at).desc())
        .limit(10)
    )
    recent_messages = list(reversed(session.exec(recent_messages_statement).all()))

    turn_request = {
        "character": character,
        "campaign": campaign,
        "current_checkpoint": current_checkpoint_detail,
        "recent_messages": recent_messages,
        "message": message,
    }

    response = process_turn(turn_request, session)

    assert campaign.id is not None
    assert character.id is not None

    session.add(
        MessageHistory(
            campaign_id=campaign.id,
            character_id=character.id,
            role="user",
            content=message,
        )
    )
    session.add(
        MessageHistory(
            campaign_id=campaign.id,
            character_id=character.id,
            role="assistant",
            content=response,
        )
    )
    session.commit()

    return response
