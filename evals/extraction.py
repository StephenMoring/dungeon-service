"""Extraction eval: does Claude store the right facts from an exchange?

Runs each scripted exchange through the real memory extraction (dm_agent.extract_memories)
several times and scores code checks on the JSON it returns. Extraction varies between
runs, so each check reports a pass rate. Nothing is written to the database.

Needs DUNGEON_ANTHROPIC_API_KEY. Makes one Claude call per case per run.

    uv run python -m evals.extraction            # 3 runs per case
    uv run python -m evals.extraction --runs 5 --case find-the-letter
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from src.services.dm_agent import extract_memories

HERE = Path(__file__).parent
CASES = HERE / "extraction_cases.json"
RESULTS = HERE / "results"


def _text(value: object) -> str:
    return "" if value is None else str(value).lower()


def check(extracted: dict, spec: dict) -> bool:
    records = extracted.get(spec["kind"], [])
    if "name" in spec:
        name_field = "summary" if spec["kind"] == "events" else "name"
        records = [r for r in records if spec["name"] in _text(r.get(name_field))]
    if "count" in spec:
        return len(records) == spec["count"]
    if not records:
        return False

    def values(record: dict) -> list[str]:
        if spec["field"] == "any":
            return [_text(v) for v in record.values()]
        return [_text(record.get(spec["field"]))]

    if spec.get("absent"):
        return all(not v for r in records for v in values(r))
    return any(
        phrase.lower() in v
        for r in records
        for v in values(r)
        for phrase in spec["any_of"]
    )


def label(spec: dict) -> str:
    target = f"{spec['kind']}[{spec['name']}]" if "name" in spec else spec["kind"]
    if "count" in spec:
        return f"{target} count == {spec['count']}"
    if spec.get("absent"):
        return f"{target}.{spec['field']} is empty"
    return f"{target}.{spec['field']} mentions {' / '.join(spec['any_of'])}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--case", help="run only the case with this id")
    args = parser.parse_args()

    cases = json.loads(CASES.read_text())["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]

    results = []
    total = passed = 0
    for case in cases:
        runs = []
        for _ in range(args.runs):
            raw = extract_memories(case["player"], case["dm"])
            extracted = json.loads(raw) if raw else {}
            runs.append(
                {
                    "extracted": extracted,
                    "checks": [check(extracted, spec) for spec in case["checks"]],
                }
            )
        print(f"  {case['id']}")
        for i, spec in enumerate(case["checks"]):
            hits = sum(run["checks"][i] for run in runs)
            total += args.runs
            passed += hits
            mark = "ok  " if hits == args.runs else "FAIL" if hits == 0 else "FLAKY"
            print(f"      {mark} {hits}/{args.runs}  {label(spec)}")
        results.append({"id": case["id"], "runs": runs})

    print(f"\n{passed}/{total} checks passed across {args.runs} runs per case")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"extraction-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"runs": args.runs, "results": results}, indent=2))
    print(f"Full results: {out}")


if __name__ == "__main__":
    main()
