"""Retrieval eval: do player turns recall the campaign memories they should?

Loads hand-written memories into a throwaway campaign, embeds them with Voyage, and
runs each probe turn through the same search a real turn uses (last DM reply + player
message, top MEMORIES_PER_KIND per kind under MAX_COSINE_DISTANCE). Everything runs in
one transaction that is rolled back, so the database is left as it was.

Needs the local database (make lr) and VOYAGE_API_KEY. Makes no Claude calls.

    uv run python -m evals.retrieval
    uv run python -m evals.retrieval --k 5 --max-distance 0.7   # try other limits
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlmodel import Session, col, select

from src.db.db import engine
from src.models.campaign import Campaign
from src.models.memory import EventMemory, ItemMemory, LocationMemory, NpcMemory
from src.services import memory_service
from src.services.embedding_service import Memory, embed, embed_queries, memory_text

HERE = Path(__file__).parent
CASES = HERE / "retrieval_cases.json"
RESULTS = HERE / "results"

# Typed loosely: memory_service._nearest is generic over one concrete memory model.
MODELS: dict[str, Any] = {
    "npc": NpcMemory,
    "location": LocationMemory,
    "item": ItemMemory,
    "event": EventMemory,
}


def load_memories(session: Session, campaign_id: int, specs: list[dict]) -> dict:
    """Store the case memories with real embeddings; return {(model, id): key}."""
    memories: list[tuple[str, Memory]] = []
    for spec in specs:
        fields = {k: v for k, v in spec.items() if k not in ("key", "kind")}
        memories.append(
            (spec["key"], MODELS[spec["kind"]](campaign_id=campaign_id, **fields))
        )
    vectors = embed([memory_text(m) for _, m in memories])
    for (_, memory), vector in zip(memories, vectors, strict=True):
        memory.embedding = vector
        session.add(memory)
    session.flush()
    return {(type(m), m.id): key for key, m in memories}


def ranked(
    session: Session, model: type[Memory], campaign_id: int, vector: list[float]
) -> list[tuple[Any, float]]:
    """Every memory of one kind, nearest first, with its cosine distance."""
    distance = cast(Any, col(model.embedding)).cosine_distance(vector)
    rows = session.exec(
        select(model, distance)
        .where(model.campaign_id == campaign_id)
        .order_by(distance)
    ).all()
    return [(memory, float(d)) for memory, d in rows]


def probe_query(probe: dict) -> str:
    """The same query a real turn builds in turn_service._recall."""
    if probe.get("last_dm"):
        return f"{probe['last_dm']}\n\n{probe['message']}"
    return probe["message"]


def run_probe(
    session: Session, campaign_id: int, probe: dict, vector: list[float], keys: dict
) -> dict:
    query = probe_query(probe)

    recalled: list[str] = []
    nearest: dict[str, list[dict]] = {}
    for kind, model in MODELS.items():
        hits = memory_service._nearest(model, campaign_id, vector, session)
        recalled += [keys[(model, m.id)] for m in hits]
        nearest[kind] = [
            {"key": keys[(model, m.id)], "distance": round(d, 3)}
            for m, d in ranked(session, model, campaign_id, vector)[:5]
        ]

    by_key = {n["key"]: n for kind in nearest.values() for n in kind}
    expected = []
    for key in probe["expect"]:
        kind = key.split(":")[0]
        order = [n["key"] for n in nearest[{"loc": "location"}.get(kind, kind)]]
        expected.append(
            {
                "key": key,
                "recalled": key in recalled,
                "rank": order.index(key) + 1 if key in order else None,
                "distance": by_key.get(key, {}).get("distance"),
            }
        )
    return {
        "id": probe["id"],
        "query": query,
        "passed": all(e["recalled"] for e in expected),
        "expected": expected,
        "recalled": recalled,
        "nearest": nearest,
    }


def main() -> None:
    engine.echo = False  # the app logs every SQL statement locally; too noisy here
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--k", type=int, default=memory_service.MEMORIES_PER_KIND)
    parser.add_argument(
        "--max-distance", type=float, default=memory_service.MAX_COSINE_DISTANCE
    )
    args = parser.parse_args()
    memory_service.MEMORIES_PER_KIND = args.k
    memory_service.MAX_COSINE_DISTANCE = args.max_distance

    cases = json.loads(CASES.read_text())
    with Session(engine) as session:
        try:
            campaign = Campaign(
                name="[eval] retrieval", theme="eval", description="eval"
            )
            session.add(campaign)
            session.flush()
            assert campaign.id is not None
            keys = load_memories(session, campaign.id, cases["memories"])
            # One request for all probes keeps a run to two Voyage calls.
            vectors = embed_queries([probe_query(p) for p in cases["probes"]])
            results = [
                run_probe(session, campaign.id, probe, vector, keys)
                for probe, vector in zip(cases["probes"], vectors, strict=True)
            ]
        finally:
            session.rollback()

    scored = [r for r in results if r["expected"]]
    hits = [e for r in scored for e in r["expected"]]
    summary = {
        "k": args.k,
        "max_distance": args.max_distance,
        "probes_passed": f"{sum(r['passed'] for r in scored)}/{len(scored)}",
        "memories_recalled": f"{sum(e['recalled'] for e in hits)}/{len(hits)}",
    }

    for r in results:
        if not r["expected"]:
            print(f"  info  {r['id']}: recalled {r['recalled'] or 'nothing'}")
            continue
        print(f"  {'PASS' if r['passed'] else 'FAIL'}  {r['id']}")
        for e in r["expected"]:
            mark = "ok " if e["recalled"] else "MISS"
            print(
                f"          {mark} {e['key']}  rank {e['rank']}  distance {e['distance']}"
            )
    print(
        f"\nk={args.k} max_distance={args.max_distance}: "
        f"{summary['probes_passed']} probes passed, "
        f"{summary['memories_recalled']} expected memories recalled"
    )

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"retrieval-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(f"Full results: {out}")


if __name__ == "__main__":
    main()
