"""End-to-end recall eval: plant a clue, bury it under filler turns, probe for it.

1. Creates an isolated eval user, character and campaign in the local database.
2. Saves the plant and filler exchanges as message history and runs the real memory
   extraction on each, exactly as a played turn would (Claude + Voyage).
3. Runs the probe turn through the real turn path (load_turn_context, which does
   retrieval, then process_turn_stream) several times without saving it, and scores:
     - recalled: did the clue reach the DM's prompt ("What You Remember")?
     - mentioned: does the reply contain an evidence term (cheap keyword check)?
     - judged: does a Claude grader, given the rubric, say the DM used the clue?
4. Deletes the eval rows, unless --keep.

Needs the local database, DUNGEON_ANTHROPIC_API_KEY and VOYAGE_API_KEY. A run with the
default 25 filler exchanges and 5 probes makes about 40 Claude calls.

    uv run python -m evals.recall_scenario
    uv run python -m evals.recall_scenario --filler 10 --probes 3 --keep
    uv run python -m evals.recall_scenario --voyage-rpm 3   # Voyage free-tier limit
"""

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, col, delete

from src.db.db import engine
from src.models.campaign import Campaign, CampaignCheckpoint
from src.models.character import Character
from src.models.memory import EventMemory, ItemMemory, LocationMemory, NpcMemory
from src.models.message_history import MessageHistory
from src.models.user import User
from src.services import embedding_service
from src.services.dm_agent import TextDelta, client, process_turn_stream
from src.services.embedding_service import extract_and_store_memories
from src.services.prompts import format_memories
from src.services.turn_service import load_turn_context

HERE = Path(__file__).parent
SCENARIO = HERE / "recall_scenario.json"
RESULTS = HERE / "results"
JUDGE_MODEL = "claude-sonnet-4-5-20250929"


def throttle_voyage(per_minute: float) -> None:
    """Wait between Voyage calls. A rate-limited lookup during a probe is logged and
    skipped by the app, which would score as the DM forgetting."""
    gap = 60 / per_minute + 1
    last = [0.0]

    def spaced(fn):
        def call(*args, **kwargs):
            wait = last[0] + gap - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                return fn(*args, **kwargs)
            finally:
                last[0] = time.monotonic()

        return call

    # embed_query (used by retrieval) calls embed_queries through this module.
    embedding_service.embed = spaced(embedding_service.embed)
    embedding_service.embed_queries = spaced(embedding_service.embed_queries)


def create_world(session: Session, scenario: dict) -> Character:
    user = User(discord_id="eval-recall", username="[eval]", avatar_url="")
    campaign = Campaign(**scenario["campaign"])
    session.add_all([user, campaign])
    session.flush()
    assert campaign.id is not None and user.id is not None
    # Any shared checkpoint will do; the probe needs an active one to load a turn.
    session.add(
        CampaignCheckpoint(
            campaign_id=campaign.id, checkpoint_id=1, order=0, status="new"
        )
    )
    character = Character(
        **scenario["character"], campaign_id=campaign.id, user_id=user.id
    )
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


def play_scripted(character: Character, exchanges: list[dict], label: str) -> None:
    """Save each exchange and extract its memories, as a played turn would."""
    assert character.id is not None and character.campaign_id is not None
    for i, exchange in enumerate(exchanges, 1):
        with Session(engine) as session:
            session.add_all(
                [
                    MessageHistory(
                        campaign_id=character.campaign_id,
                        character_id=character.id,
                        role=role,
                        content=exchange[key],
                    )
                    for role, key in (("user", "player"), ("assistant", "dm"))
                ]
            )
            session.commit()
        extract_and_store_memories(
            character.campaign_id, [exchange["player"], exchange["dm"]]
        )
        print(f"  {label} {i}/{len(exchanges)}", end="\r", flush=True)
    print()


async def dm_reply(turn: dict) -> str:
    return "".join(
        [e.text async for e in process_turn_stream(turn) if isinstance(e, TextDelta)]
    )


def judge(rubric: str, player: str, reply: str) -> tuple[bool, str]:
    message = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=200,
        system=(
            "You grade replies from an AI dungeon master. "
            "Answer with YES or NO on the first line, then one sentence of reasoning."
        ),
        messages=[
            {
                "role": "user",
                "content": f"{rubric}\n\nPlayer: {player}\n\nDM reply:\n{reply}",
            }
        ],
    )
    text = "".join(b.text for b in message.content if b.type == "text").strip()
    return text.upper().startswith("YES"), text


def probe(character_id: int, scenario: dict) -> dict:
    with Session(engine) as session:
        turn = load_turn_context(character_id, scenario["probe"]["message"], session)
        remembered = format_memories(turn["memories"])
        reply = asyncio.run(dm_reply(turn))
    terms = scenario["evidence_terms"]
    judged, reasoning = judge(scenario["rubric"], scenario["probe"]["message"], reply)
    return {
        "recalled": any(t in remembered.lower() for t in terms),
        "mentioned": any(t in reply.lower() for t in terms),
        "judged": judged,
        "judge_reasoning": reasoning,
        "what_you_remember": remembered,
        "reply": reply,
    }


def clean_up(campaign_id: int, user_id: int) -> None:
    with Session(engine) as session:
        for model in (
            NpcMemory,
            LocationMemory,
            ItemMemory,
            EventMemory,
            MessageHistory,
        ):
            session.exec(delete(model).where(col(model.campaign_id) == campaign_id))  # type: ignore[call-overload]
        session.exec(
            delete(CampaignCheckpoint).where(
                col(CampaignCheckpoint.campaign_id) == campaign_id
            )
        )  # type: ignore[call-overload]
        session.exec(delete(Character).where(col(Character.campaign_id) == campaign_id))  # type: ignore[call-overload]
        session.exec(delete(Campaign).where(col(Campaign.id) == campaign_id))  # type: ignore[call-overload]
        session.exec(delete(User).where(col(User.id) == user_id))  # type: ignore[call-overload]
        session.commit()


def main() -> None:
    engine.echo = False  # the app logs every SQL statement locally; too noisy here
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--filler", type=int, help="filler exchanges to play (default: all)"
    )
    parser.add_argument("--probes", type=int, default=5, help="probe repeats to score")
    parser.add_argument(
        "--keep", action="store_true", help="leave the eval campaign in the db"
    )
    parser.add_argument(
        "--voyage-rpm",
        type=float,
        help="space Voyage calls to this many per minute (3 on a Voyage account "
        "with no payment method), so no lookup is silently skipped",
    )
    args = parser.parse_args()
    if args.voyage_rpm:
        throttle_voyage(args.voyage_rpm)

    scenario = json.loads(SCENARIO.read_text())
    filler = scenario["filler"][: args.filler] if args.filler else scenario["filler"]

    with Session(engine) as session:
        character = create_world(session, scenario)
    assert character.id is not None and character.campaign_id is not None
    print(f"Eval campaign {character.campaign_id}, character {character.id}")

    try:
        play_scripted(character, scenario["plant"], "plant")
        play_scripted(character, filler, "filler")
        play_scripted(
            character,
            [
                {
                    "player": "I head back to the manor.",
                    "dm": scenario["probe"]["last_dm"],
                }
            ],
            "lead-in",
        )
        probes = []
        for i in range(args.probes):
            probes.append(probe(character.id, scenario))
            print(f"  probe {i + 1}/{args.probes}", end="\r", flush=True)
        print()
    finally:
        if not args.keep:
            clean_up(character.campaign_id, character.user_id)

    n = len(probes)
    summary = {
        "filler_exchanges": len(filler),
        "messages_between_clue_and_probe": 2 * (len(filler) + 1),
        "recalled": f"{sum(p['recalled'] for p in probes)}/{n}",
        "mentioned": f"{sum(p['mentioned'] for p in probes)}/{n}",
        "judged_used": f"{sum(p['judged'] for p in probes)}/{n}",
    }
    print(
        f"\n{summary['messages_between_clue_and_probe']} messages after the clue:\n"
        f"  clue in the DM's prompt:      {summary['recalled']}\n"
        f"  reply mentions the evidence:  {summary['mentioned']}\n"
        f"  grader says DM used the clue: {summary['judged_used']}"
    )
    for i, p in enumerate(probes, 1):
        print(f"\n--- probe {i}: {p['judge_reasoning']}\n{p['reply'][:400]}")

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"recall-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"summary": summary, "probes": probes}, indent=2))
    print(f"\nFull results: {out}")


if __name__ == "__main__":
    main()
