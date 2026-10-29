from dataclasses import dataclass, field
from typing import Any, cast

from sqlmodel import Session, col, select

from src.models.memory import EventMemory, ItemMemory, LocationMemory, NpcMemory
from src.services.embedding_service import embed_query

# Tunable: how many memories of each kind reach the prompt, and how far (cosine
# distance, 0 = identical) a memory may be from the query and still count as relevant.
MEMORIES_PER_KIND = 3
MAX_COSINE_DISTANCE = 0.6


@dataclass
class RetrievedMemories:
    npcs: list[NpcMemory] = field(default_factory=list)
    locations: list[LocationMemory] = field(default_factory=list)
    items: list[ItemMemory] = field(default_factory=list)
    events: list[EventMemory] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.npcs or self.locations or self.items or self.events)


def _nearest[M: (NpcMemory, LocationMemory, ItemMemory, EventMemory)](
    model: type[M], campaign_id: int, vector: list[float], session: Session
) -> list[M]:
    # pgvector's comparator adds cosine_distance (<=>); it ships no type stubs.
    distance = cast(Any, col(model.embedding)).cosine_distance(vector)
    statement = (
        select(model)
        .where(model.campaign_id == campaign_id)
        .where(distance < MAX_COSINE_DISTANCE)
        .order_by(distance)
        .limit(MEMORIES_PER_KIND)
    )
    return list(session.exec(statement).all())


def retrieve_memories(
    campaign_id: int, query_text: str, session: Session
) -> RetrievedMemories:
    vector = embed_query(query_text)
    return RetrievedMemories(
        npcs=_nearest(NpcMemory, campaign_id, vector, session),
        locations=_nearest(LocationMemory, campaign_id, vector, session),
        items=_nearest(ItemMemory, campaign_id, vector, session),
        events=_nearest(EventMemory, campaign_id, vector, session),
    )
