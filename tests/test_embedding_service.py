import json
from unittest.mock import MagicMock, patch

import pytest

from src.models.memory import ItemMemory, LocationMemory, NpcMemory
from src.services.embedding_service import embed_query, extract_and_store_memories


@patch("src.services.embedding_service.voyageai.Client")
def test_embed_query_uses_query_input_type(client_cls):
    client_cls.return_value.embed.return_value.embeddings = [[0.1, 0.2]]

    vector = embed_query("I confront Mira")

    assert vector == [0.1, 0.2]
    client_cls.return_value.embed.assert_called_once_with(
        ["I confront Mira"], model="voyage-3.5", input_type="query"
    )


def extraction(npcs=(), locations=(), items=(), events=()) -> str:
    return json.dumps(
        {
            "npcs": list(npcs),
            "locations": list(locations),
            "items": list(items),
            "events": list(events),
        }
    )


@pytest.fixture
def store():
    """Run extract_and_store_memories with Claude, Voyage and the DB mocked.

    `existing` maps a memory model to the row the upsert lookup should find.
    Returns the mocked session and embed so tests can inspect what was stored.
    """

    def run(extracted: str, existing: dict | None = None):
        existing = existing or {}
        session = MagicMock()

        def exec_(statement):
            model = statement.column_descriptions[0]["entity"]
            return MagicMock(first=MagicMock(return_value=existing.get(model)))

        session.exec.side_effect = exec_
        embed = MagicMock(
            side_effect=lambda texts: [[float(i)] for i in range(len(texts))]
        )
        with (
            patch("src.services.embedding_service.Session") as session_cls,
            patch(
                "src.services.embedding_service.extract_memories",
                return_value=extracted,
            ),
            patch("src.services.embedding_service.embed", embed),
        ):
            session_cls.return_value.__enter__.return_value = session
            extract_and_store_memories(7, ["player says", "dm says"])
        return session, embed

    return run


class TestMergedMemoriesAreReembedded:
    def test_npc_vector_covers_old_and_new_facts(self, store):
        aldo = NpcMemory(
            id=1,
            campaign_id=7,
            name="Aldo",
            known_facts="Claimed he was at the docks that night",
            secrets="A letter in his desk places him at the warehouse",
            embedding=[9.0],
        )

        session, embed = store(
            extraction(npcs=[{"name": "Aldo", "known_facts": "Poured you a drink"}]),
            existing={NpcMemory: aldo},
        )

        (text,) = embed.call_args.args[0]
        assert "docks" in text
        assert "warehouse" in text
        assert "Poured you a drink" in text
        assert aldo.embedding == [0.0]
        session.commit.assert_called_once()

    def test_location_vector_covers_old_and_new_events(self, store):
        warehouse = LocationMemory(
            id=1,
            campaign_id=7,
            name="The Warehouse",
            events="Found Aldo's bootprints in the ash",
        )

        _, embed = store(
            extraction(
                locations=[{"name": "The Warehouse", "events": "Guards changed shift"}]
            ),
            existing={LocationMemory: warehouse},
        )

        (text,) = embed.call_args.args[0]
        assert "bootprints" in text
        assert "Guards changed shift" in text

    def test_item_keeps_where_it_was_found(self, store):
        letter = ItemMemory(
            id=1,
            campaign_id=7,
            name="Aldo's Letter",
            description="Places Aldo at the warehouse",
            where_found="Aldo's desk",
        )

        _, embed = store(
            extraction(
                items=[{"name": "Aldo's Letter", "status": "given to the magistrate"}]
            ),
            existing={ItemMemory: letter},
        )

        (text,) = embed.call_args.args[0]
        assert "Aldo's desk" in text
        assert "given to the magistrate" in text

    def test_new_memories_are_embedded_and_added(self, store):
        session, embed = store(
            extraction(
                npcs=[{"name": "Mira", "role": "innkeeper"}],
                events=[{"summary": "Found the letter", "category": "revelation"}],
            )
        )

        texts = embed.call_args.args[0]
        assert len(texts) == 2
        added = [c.args[0] for c in session.add.call_args_list]
        assert {type(m).__name__ for m in added} == {"NpcMemory", "EventMemory"}
        assert all(m.embedding is not None for m in added)

    def test_nothing_is_embedded_when_nothing_was_extracted(self, store):
        session, embed = store(extraction())

        embed.assert_not_called()
        session.commit.assert_called_once()
