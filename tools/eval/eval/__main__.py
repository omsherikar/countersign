"""python -m eval run --generated DIR --out DIR [--skip-perf] [--skip-access]

Scores the database the seed of DIR produced (run `make demo-reset` first; `make eval` does)
against DIR/ground_truth.json, times the 50,000-row file of DIR/perf/ through `run_batch`
against the configured sources, asks the api for other colleges' data as each college, and
writes eval_report.md and eval.json to --out. Exits 1 when a target is missed.

`python -m eval pytest [args]` runs the evaluation's own tests.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from . import detection, effort, false_alarms, report, signals, timing, truth


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m eval", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="score the seeded database and write the report")
    run.add_argument("--generated", type=Path, required=True, help="datagen output directory")
    run.add_argument("--out", type=Path, required=True, help="where the report files go")
    run.add_argument("--skip-perf", action="store_true", help="do not run the 50,000-row file")
    run.add_argument(
        "--skip-access", action="store_true", help="do not make the cross-college requests"
    )
    return parser


async def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.db.session import dispose_engine, session_factory
    from app.main import app

    from . import access, snapshot

    facts = truth.load(args.generated)
    year = get_settings().academic_year
    factory = session_factory()
    exclude = {truth.PERF_INSTITUTION}
    try:
        perf = None
        if not args.skip_perf and facts.perf:
            print(f"timing {facts.perf['file']} ({facts.perf['rows']:,} rows) ...", flush=True)
            perf = await timing.run_perf(factory, args.generated, facts.perf)
            print(f"  {perf['seconds']} s, {perf['status']}", flush=True)
        async with factory() as session:
            snap = await snapshot.take(session, exclude=exclude)
        resolved = truth.resolve(facts.records, snap.row_index)
        named = truth.named_enrolments(facts.records, resolved)
        clean = false_alarms.known_clean(snap.records, named, exclude)
        planted_deadlines = [r.institution for r in facts.records if r.expected_deadline_state]
        states = await access.deadline_states(app, factory, planted_deadlines, year)
        access_result = None
        if not args.skip_access:
            print("asking for other colleges' data as each college ...", flush=True)
            access_result = await access.cross_college(app, factory)
        return report.assemble(
            dataset={
                "size": facts.size,
                "seed": facts.seed,
                "institutions": sum(1 for code in snap.institutions if code not in exclude),
                "records": snap.active_records(exclude),
                "ground_truth_records": len(facts.records),
                "rows_without_enrolment": sum(
                    1 for ids in resolved.values() for e in ids if e is None
                ),
            },
            detection=detection.score_detection(facts.records, resolved, snap.cases).as_dict(),
            record_status=detection.score_record_status(facts.records, resolved, snap.records),
            deadlines=detection.score_deadlines(facts.records, states),
            false_alarms=false_alarms.score_false_alarms(clean, snap.records, snap.cases),
            controls=false_alarms.score_controls(facts.records, resolved, snap.records, snap.cases),
            uploads=timing.upload_timing(snap.batches, exclude),
            perf=perf,
            effort=effort.review_effort(snap.cases, snap.active_records(exclude), exclude),
            signals=signals.score_signals(facts.records, resolved, snap.signals),
            access=access_result,
        )
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "pytest":
        import pytest

        args = argv[1:]
        if not any(Path(a.split("::")[0]).exists() for a in args if not a.startswith("-")):
            args.append(str(Path(__file__).resolve().parent.parent / "tests"))
        return pytest.main(args)
    args = build_parser().parse_args(argv)
    # the evaluation measures scope, not rate limits: hundreds of requests per second come
    # from one process
    os.environ.setdefault("RATE_LIMITS_ENABLED", "false")
    result = asyncio.run(evaluate(args))
    md_path, json_path = report.write(args.out, result)
    print(report.render(result))
    print(f"wrote {md_path} and {json_path}")
    missed = report.failed(result)
    if missed:
        print(f"targets missed: {', '.join(missed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
