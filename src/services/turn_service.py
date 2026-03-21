from sqlmodel import Session, col, select
from src.models.character import Character
from src.models.campaign import Campaign, CampaignCheckpoint, Checkpoint
from src.models.message_history import MessageHistory


def take_turn(id: str, session: Session) -> str:
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

    current_checkpoint_detail = session.get(Checkpoint, current_campaign_checkpoint.checkpoint_id)

    recent_messages_statement = (
        select(MessageHistory)
        .where(MessageHistory.campaign_id == campaign.id)
        .where(MessageHistory.character_id == character.id)
        .order_by(col(MessageHistory.created_at).desc())
        .limit(10)
    )
    recent_messages = list(reversed(session.exec(recent_messages_statement).all()))

    print(character)
    print(campaign)
    print(current_checkpoint_detail)
    print(recent_messages)

    # make nice package to pass to dm

    return "played take_turn"
