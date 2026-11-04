import json
from unittest.mock import MagicMock, patch

import pytest

from src.models.memory import ItemMemory, LocationMemory, NpcMemory
from src.services.embedding_service import embed_query, extract_and_store_memories
from tests.conftest import compiled_sql


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

    def run(extracted: str, existing: dict | None = None, already_known: str = ""):
        existing = existing or {}
        session = MagicMock()

        def exec_(statement):
            model = statement.column_descriptions[0]["entity"]
            row = existing.get(model)
            return MagicMock(
                first=MagicMock(return_value=row),
                # The known-names lookup selects just the name column.
                all=MagicMock(return_value=[row.name] if row else []),
            )

        session.exec.side_effect = exec_
        embed = MagicMock(
            side_effect=lambda texts: [[float(i)] for i in range(len(texts))]
        )
        with (
            patch("src.services.embedding_service.Session") as session_cls,
            patch(
                "src.services.embedding_service.extract_memories",
                return_value=extracted,
            ) as extract,
            patch("src.services.embedding_service.embed", embed),
        ):
            session_cls.return_value.__enter__.return_value = session
            extract_and_store_memories(7, ["player says", "dm says"], already_known)
        session.extract = extract
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


class TestOneRecordPerName:
    def test_extraction_is_told_the_names_already_recorded(self, store):
        aldo = NpcMemory(id=1, campaign_id=7, name="Aldo Venn")
        letter = ItemMemory(id=1, campaign_id=7, name="Unsent letter")

        session, _ = store(extraction(), existing={NpcMemory: aldo, ItemMemory: letter})

        known = session.extract.call_args.args[2]
        assert known.npcs == ["Aldo Venn"]
        assert known.items == ["Unsent letter"]
        assert known.locations == []

    def test_known_names_are_looked_up_for_this_campaign_only(self, store):
        session, _ = store(extraction())

        names_query = compiled_sql(session.exec.call_args_list[0].args[0])
        assert "npcmemory.campaign_id = 7" in names_query

    def test_records_are_matched_ignoring_case(self, store):
        manor = LocationMemory(id=1, campaign_id=7, name="The Manor", events="Met Aldo")

        session, _ = store(
            extraction(locations=[{"name": "the manor", "events": "Fire alarm"}]),
            existing={LocationMemory: manor},
        )

        lookups = [compiled_sql(c.args[0]) for c in session.exec.call_args_list]
        assert any(
            "lower(locationmemory.name) = lower('the manor')" in q for q in lookups
        )
        assert manor.events == "Met Aldo, Fire alarm"
        session.add.assert_not_called()


def test_extraction_sees_what_the_turn_recalled(store):
    session, _ = store(
        extraction(), already_known="Aldo Venn: claims he was at the docks"
    )

    assert session.extract.call_args.args[3] == "Aldo Venn: claims he was at the docks"
