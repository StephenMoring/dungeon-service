from unittest.mock import MagicMock, patch

from sqlalchemy.dialects import postgresql

from src.models.memory import EventMemory, ItemMemory, LocationMemory, NpcMemory
from src.services.memory_service import (
    MAX_COSINE_DISTANCE,
    MEMORIES_PER_KIND,
    RetrievedMemories,
    retrieve_memories,
)

QUERY_VECTOR = [0.1, 0.2, 0.3]


def session_returning(by_model: dict) -> MagicMock:
    """A session whose exec() returns the rows registered for the queried model."""
    session = MagicMock()

    def exec_(statement):
        model = statement.column_descriptions[0]["entity"]
        result = MagicMock()
        result.all.return_value = by_model.get(model, [])
        return result

    session.exec.side_effect = exec_
    return session


@patch("src.services.memory_service.embed_query", return_value=QUERY_VECTOR)
def test_groups_results_by_kind(_embed):
    mira = NpcMemory(campaign_id=7, name="Mira", secrets="Serves the cult")
    ledger = ItemMemory(campaign_id=7, name="Ledger", description="Cult payments")
    session = session_returning({NpcMemory: [mira], ItemMemory: [ledger]})

    memories = retrieve_memories(7, "I confront Mira", session)

    assert memories.npcs == [mira]
    assert memories.items == [ledger]
    assert memories.locations == []
    assert memories.events == []


@patch("src.services.memory_service.embed_query", return_value=QUERY_VECTOR)
def test_embeds_the_query_text(embed):
    retrieve_memories(7, "I confront Mira", session_returning({}))

    embed.assert_called_once_with("I confront Mira")


@patch("src.services.memory_service.embed_query", return_value=QUERY_VECTOR)
def test_each_query_is_scoped_ranked_and_capped(_embed):
    session = session_returning({})

    retrieve_memories(7, "I confront Mira", session)

    queried = [c.args[0] for c in session.exec.call_args_list]
    models = [q.column_descriptions[0]["entity"] for q in queried]
    assert models == [NpcMemory, LocationMemory, ItemMemory, EventMemory]
    for statement in queried:
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        assert ".campaign_id = %(campaign_id_1)s" in sql
        assert "<=> %(embedding_1)s) < %(param_1)s" in sql
        assert "ORDER BY" in sql and "<=>" in sql.split("ORDER BY")[1]
        assert compiled.params["campaign_id_1"] == 7
        assert compiled.params["embedding_1"] == QUERY_VECTOR
        assert compiled.params["param_1"] == MAX_COSINE_DISTANCE
        assert compiled.params["param_2"] == MEMORIES_PER_KIND


def test_is_empty():
    assert RetrievedMemories().is_empty()
    assert not RetrievedMemories(
        events=[EventMemory(campaign_id=1, summary="x")]
    ).is_empty()
