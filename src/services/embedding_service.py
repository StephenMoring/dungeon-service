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

        all_memory_objects = npcs + locations + items + events
        all_memory_texts = [
            *[
                " ".join(
                    filter(
                        None,
                        [
                            f"A character named {npc.name}.",
                            f"Their role is {npc.role}." if npc.role else None,
                            f"Their disposition is {npc.disposition}."
                            if npc.disposition
                            else None,
                            f"Known facts: {npc.known_facts}."
                            if npc.known_facts
                            else None,
                            f"Secrets: {npc.secrets}." if npc.secrets else None,
                        ],
                    )
                )
                for npc in npcs
            ],
            *[
                " ".join(
                    filter(
                        None,
                        [
                            f"A location named {location.name}.",
                            f"Description: {location.description}."
                            if location.description
                            else None,
                            f"Events that occurred here: {location.events}."
                            if location.events
                            else None,
                        ],
                    )
                )
                for location in locations
            ],
            *[
                " ".join(
                    filter(
                        None,
                        [
                            f"An item named {item.name}.",
                            f"Description: {item.description}."
                            if item.description
                            else None,
                            f"Found at: {item.where_found}."
                            if item.where_found
                            else None,
                            f"Current status: {item.status}." if item.status else None,
                        ],
                    )
                )
                for item in items
            ],
            *[
                " ".join(
                    filter(
                        None,
                        [
                            f"An event occurred: {event.summary}.",
                            f"Category: {event.category}." if event.category else None,
                        ],
                    )
                )
                for event in events
            ],
        ]

        memory_embeddings = embed(all_memory_texts)

        for vector, memory in zip(memory_embeddings, all_memory_objects):
            memory.embedding = vector

        logger.info("upserting memories")
        for npc in npcs:
            existing = session.exec(
                select(NpcMemory).where(
                    NpcMemory.campaign_id == npc.campaign_id, NpcMemory.name == npc.name
                )
            ).first()
            if existing:
                existing.role = npc.role
                existing.disposition = npc.disposition
                if npc.known_facts:
                    existing.known_facts = (
                        f"{existing.known_facts}, {npc.known_facts}"
                        if existing.known_facts
                        else npc.known_facts
                    )
                if npc.secrets:
                    existing.secrets = (
                        f"{existing.secrets}, {npc.secrets}"
                        if existing.secrets
                        else npc.secrets
                    )
                existing.embedding = npc.embedding
            else:
                session.add(npc)

        for location in locations:
            existing = session.exec(
                select(LocationMemory).where(
                    LocationMemory.campaign_id == location.campaign_id,
                    LocationMemory.name == location.name,
                )
            ).first()
            if existing:
                existing.description = location.description
                if location.events:
                    existing.events = (
                        f"{existing.events}, {location.events}"
                        if existing.events
                        else location.events
                    )
                existing.embedding = location.embedding
            else:
                session.add(location)

        for item in items:
            existing = session.exec(
                select(ItemMemory).where(
                    ItemMemory.campaign_id == item.campaign_id,
                    ItemMemory.name == item.name,
                )
            ).first()
            if existing:
                existing.description = item.description
                if not existing.where_found:
                    existing.where_found = item.where_found
                existing.status = item.status
                existing.embedding = item.embedding
            else:
                session.add(item)

        for event in events:
            session.add(event)

        session.commit()
