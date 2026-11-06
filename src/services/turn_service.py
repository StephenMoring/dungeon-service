import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import asdict, dataclass

from fastapi import BackgroundTasks
from sqlmodel import Session, col, select

from src.db.db import engine
from src.models.campaign import Campaign, CampaignCheckpoint, Checkpoint
from src.models.character import Character
from src.models.message_history import MessageHistory
from src.services.combat_service import (
    RoundResult,
    begin_encounter,
    bestiary_by_id,
    combatants_of,
    encounter_state,
    load_bestiary,
)
from src.services.dm_agent import TextDelta, narrate_round_stream, process_turn_stream
from src.services.embedding_service import extract_and_store_memories
from src.services.memory_service import RetrievedMemories, retrieve_memories
from src.services.prompts import known_context
from src.tools.combat_tools import EncounterPlan
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
        "bestiary": load_bestiary(session),
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
        memories = retrieve_memories(campaign_id, query, session)
    except Exception:
        logger.exception("Memory lookup failed", extra={"campaign_id": campaign_id})
        return RetrievedMemories()
    # One line per turn, so a forgotten fact can be traced to retrieval or to the DM.
    logger.info(
        "Recalled for campaign %s: npcs=%s locations=%s items=%s events=%s",
        campaign_id,
        [n.name for n in memories.npcs],
        [loc.name for loc in memories.locations],
        [i.name for i in memories.items],
        [e.summary for e in memories.events],
    )
    return memories


@dataclass
class SavedTurn:
    message_id: int
    encounter: dict | None = None  # the fight this turn started, as the UI shows it


def save_turn(
    campaign_id: int,
    character_id: int,
    player_message: str,
    dm_message: str,
    encounter: EncounterPlan | None = None,
) -> SavedTurn:
    """Save both messages and, if the DM started a fight, the encounter, together.
    Runs after the response has started streaming, so it manages its own session."""
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
        started = None
        enemies = []
        if encounter and encounter.combatants:
            started = begin_encounter(session, campaign_id, character_id, encounter)
            enemies = [c.enemy for c in encounter.combatants]
        session.commit()
        assert dm.id is not None
        state = None
        if started is not None:
            assert started.id is not None
            character = session.get(Character, character_id)
            assert character is not None
            state = encounter_state(
                started,
                combatants_of(session, started.id),
                character,
                bestiary_by_id(enemies),
            )
        return SavedTurn(message_id=dm.id, encounter=state)


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
        plan: EncounterPlan | None = None
        async for event in process_turn_stream(turn):
            if isinstance(event, RollResult):
                yield sse("roll", asdict(event))
            elif isinstance(event, EncounterPlan):
                plan = event
            elif isinstance(event, TextDelta):
                text_parts.append(event.text)
                yield sse("text", {"text": event.text})

        dm_message = "".join(text_parts)
        saved = save_turn(campaign_id, character_id, player_message, dm_message, plan)
    except ValueError as e:
        yield sse("error", {"detail": str(e)})
        return
    except Exception:
        # Don't leak API or database internals to the player.
        logger.exception("Turn stream failed", extra={"campaign_id": campaign_id})
        yield sse("error", {"detail": "The Dungeon Master lost the thread. Try again."})
        return

    background_tasks.add_task(
        extract_and_store_memories,
        campaign_id,
        [player_message, dm_message],
        known_context(turn.get("memories")),
    )
    if saved.encounter:
        yield sse("combat", saved.encounter)
    yield sse("done", {"message_id": saved.message_id})


async def stream_combat_round(
    turn: dict,
    round_result: RoundResult,
    state: dict,
    background_tasks: BackgroundTasks,
) -> AsyncGenerator[str, None]:
    """SSE for a combat round the server has already resolved and saved:
    `round` (every roll), `combat` (hit points after it), the DM's narration as
    `text`, then `done`. If narration fails the round still stands."""
    campaign_id = turn["campaign"].id
    character_id = turn["character"].id
    player_message = turn["message"]

    yield sse("round", asdict(round_result))
    yield sse("combat", state)
    try:
        text_parts: list[str] = []
        async for event in narrate_round_stream(turn, round_result, state):
            text_parts.append(event.text)
            yield sse("text", {"text": event.text})
        dm_message = "".join(text_parts)
        saved = save_turn(campaign_id, character_id, player_message, dm_message)
    except Exception:
        logger.exception("Combat narration failed", extra={"campaign_id": campaign_id})
        yield sse(
            "error",
            {"detail": "The Dungeon Master lost the thread, but the round stands."},
        )
        return

    background_tasks.add_task(
        extract_and_store_memories,
        campaign_id,
        [player_message, dm_message],
        known_context(turn.get("memories")),
    )
    yield sse("done", {"message_id": saved.message_id})
