from src.models.memory import EventMemory, ItemMemory, LocationMemory, NpcMemory
from src.services.dm_agent import extract_memories
from sqlmodel import Session, select
from src.db.db import engine
from typing import cast
import logging
import json
import voyageai

logger = logging.getLogger(__name__)


def embed(texts: list[str]) -> list[list[float]]:
    vo = voyageai.Client()  # type: ignore
    result = vo.embed(texts, model="voyage-3.5", input_type="document")
    return cast(list[list[float]], result.embeddings)


def embed_query(text: str) -> list[float]:
    """Embed search text. Voyage tunes `query` embeddings to match stored `document` ones."""
    return embed_queries([text])[0]


def embed_queries(texts: list[str]) -> list[list[float]]:
    """Embed several search texts in one request (evals batch their probes this way)."""
    vo = voyageai.Client()  # type: ignore
    result = vo.embed(texts, model="voyage-3.5", input_type="query")
    return cast(list[list[float]], result.embeddings)


type Memory = NpcMemory | LocationMemory | ItemMemory | EventMemory


def _join(existing: str | None, new: str | None) -> str | None:
    """Append newly extracted text to what is already stored."""
    if not new:
        return existing
    return f"{existing}, {new}" if existing else new


def _sentences(*parts: str | None) -> str:
    return " ".join(part for part in parts if part)


def memory_text(memory: Memory) -> str:
    """The text a memory is embedded from: every stored field, as plain sentences."""
    match memory:
        case NpcMemory():
            return _sentences(
                f"A character named {memory.name}.",
                memory.role and f"Their role is {memory.role}.",
                memory.disposition and f"Their disposition is {memory.disposition}.",
                memory.known_facts and f"Known facts: {memory.known_facts}.",
                memory.secrets and f"Secrets: {memory.secrets}.",
            )
        case LocationMemory():
            return _sentences(
                f"A location named {memory.name}.",
                memory.description and f"Description: {memory.description}.",
                memory.events and f"Events that occurred here: {memory.events}.",
            )
        case ItemMemory():
            return _sentences(
                f"An item named {memory.name}.",
                memory.description and f"Description: {memory.description}.",
                memory.where_found and f"Found at: {memory.where_found}.",
                memory.status and f"Current status: {memory.status}.",
            )
        case EventMemory():
            return _sentences(
                f"An event occurred: {memory.summary}.",
                memory.category and f"Category: {memory.category}.",
            )


def extract_and_store_memories(campaign_id: int, messages: list):
    with Session(engine) as session:
        memories = extract_memories(messages[0], messages[1])
        if not memories:
            logger.warning(
                "Memory extraction returned no content",
                extra={"campaign_id": campaign_id},
            )
            return
        try:
            data: dict[str, list] = json.loads(memories)
        except json.JSONDecodeError:
            logger.warning(
                "LLM returned invalid json", extra={"campaign_id": campaign_id}
            )
            return

        npcs = [NpcMemory(campaign_id=campaign_id, **npc) for npc in data["npcs"]]
        locations = [
            LocationMemory(campaign_id=campaign_id, **location)
            for location in data["locations"]
        ]
        items = [ItemMemory(campaign_id=campaign_id, **item) for item in data["items"]]
        events = [
            EventMemory(campaign_id=campaign_id, **event) for event in data["events"]
        ]

        stored: list[Memory] = []

        logger.info("upserting memories")
        for npc in npcs:
            known_npc = session.exec(
                select(NpcMemory).where(
                    NpcMemory.campaign_id == npc.campaign_id, NpcMemory.name == npc.name
                )
            ).first()
            if known_npc:
                known_npc.role = npc.role
                known_npc.disposition = npc.disposition
                known_npc.known_facts = _join(known_npc.known_facts, npc.known_facts)
                known_npc.secrets = _join(known_npc.secrets, npc.secrets)
                stored.append(known_npc)
            else:
                session.add(npc)
                stored.append(npc)

        for location in locations:
            known_location = session.exec(
                select(LocationMemory).where(
                    LocationMemory.campaign_id == location.campaign_id,
                    LocationMemory.name == location.name,
                )
            ).first()
            if known_location:
                known_location.description = location.description
                known_location.events = _join(known_location.events, location.events)
                stored.append(known_location)
            else:
                session.add(location)
                stored.append(location)

        for item in items:
            known_item = session.exec(
                select(ItemMemory).where(
                    ItemMemory.campaign_id == item.campaign_id,
                    ItemMemory.name == item.name,
                )
            ).first()
            if known_item:
                known_item.description = item.description
                if not known_item.where_found:
                    known_item.where_found = item.where_found
                known_item.status = item.status
                stored.append(known_item)
            else:
                session.add(item)
                stored.append(item)

        for event in events:
            session.add(event)
            stored.append(event)

        # Embed after merging, so a known NPC's vector covers everything stored about
        # them, not just what this turn added.
        if stored:
            vectors = embed([memory_text(memory) for memory in stored])
            for memory, vector in zip(stored, vectors, strict=True):
                memory.embedding = vector

        session.commit()
