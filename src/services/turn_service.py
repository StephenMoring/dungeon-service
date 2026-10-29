import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import asdict

from fastapi import BackgroundTasks
from sqlmodel import Session, col, select
from src.db.db import engine
from src.models.character import Character
from src.models.campaign import Campaign, CampaignCheckpoint, Checkpoint
from src.models.message_history import MessageHistory
from src.services.dm_agent import TextDelta, process_turn_stream
from src.services.embedding_service import extract_and_store_memories
from src.services.memory_service import RetrievedMemories, retrieve_memories
from src.tools.dice_tools import RollResult

logger = logging.getLogger(__name__)


def load_turn_context(character_id: int, message: str, session: Session) -> dict:
    character = session.get(Character, character_id)
    if not character:
        raise ValueError(f"Character {character_id} not found")

    campaign = session.get(Campaign, character.campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {character.campaign_id} not found")

    # grab the first checkpoint that is not complete from the campaign
    statement = (
        select(CampaignCheckpoint)
        .where(CampaignCheckpoint.campaign_id == campaign.id)
        .where(col(CampaignCheckpoint.status).not_in(["complete", "locked"]))
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

    assert campaign.id is not None
    memories = _recall(campaign.id, recent_messages, message, session)

    return {
        "character": character,
        "campaign": campaign,
        "current_checkpoint": current_checkpoint_detail,
        "recent_messages": recent_messages,
        "message": message,
        "memories": memories,
    }


def _recall(
    campaign_id: int,
    recent_messages: list[MessageHistory],
    message: str,
    session: Session,
) -> RetrievedMemories:
    """Find campaign memories related to this moment. Never fails the turn."""
    # The player often says "her" or "it"; the DM's last reply usually names who/what.
    last_dm = next(
        (m.content for m in reversed(recent_messages) if m.role == "assistant"), None
    )
    query = f"{last_dm}\n\n{message}" if last_dm else message
    try:
        return retrieve_memories(campaign_id, query, session)
    except Exception:
        logger.exception("Memory lookup failed", extra={"campaign_id": campaign_id})
        return RetrievedMemories()


def save_turn(
    campaign_id: int, character_id: int, player_message: str, dm_message: str
) -> int:
    # Runs after the response has started streaming, so it manages its own session.
    with Session(engine) as session:
        session.add(
            MessageHistory(
                campaign_id=campaign_id,
                character_id=character_id,
                role="user",
                content=player_message,
            )
        )
        dm = MessageHistory(
            campaign_id=campaign_id,
            character_id=character_id,
            role="assistant",
            content=dm_message,
        )
        session.add(dm)
        session.commit()
        assert dm.id is not None
        return dm.id


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_turn(
    turn: dict, background_tasks: BackgroundTasks
) -> AsyncGenerator[str, None]:
    campaign_id = turn["campaign"].id
    character_id = turn["character"].id
    player_message = turn["message"]

    yield sse("thinking", {})
    try:
        text_parts: list[str] = []
        async for event in process_turn_stream(turn):
            if isinstance(event, RollResult):
                yield sse("roll", asdict(event))
            elif isinstance(event, TextDelta):
                text_parts.append(event.text)
                yield sse("text", {"text": event.text})

        dm_message = "".join(text_parts)
        message_id = save_turn(campaign_id, character_id, player_message, dm_message)
    except ValueError as e:
        yield sse("error", {"detail": str(e)})
        return
    except Exception:
        # Don't leak API or database internals to the player.
        logger.exception("Turn stream failed", extra={"campaign_id": campaign_id})
        yield sse("error", {"detail": "The Dungeon Master lost the thread. Try again."})
        return

    background_tasks.add_task(
        extract_and_store_memories, campaign_id, [player_message, dm_message]
    )
    yield sse("done", {"message_id": message_id})
