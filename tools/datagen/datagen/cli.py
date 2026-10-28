"""`datagen generate` and `datagen summary`."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from .config import Config


def generate(size: str, seed: int, out: Path, *, scenarios: bool = True, xlsx: bool | None = None):
    from .anomalies import Planter
    from .eligibility import EligibilityPlanner
    from .graduates import GraduateBuilder
    from .joining import JoiningPlanner
    from .signals import SignalPlanner
    from .students import World
    from .updates import UpdatePlanner
    from .writers import write_all

    started = time.perf_counter()
    cfg = Config.build(size, scenarios=scenarios)
    world = World(cfg, seed)
    t = time.perf_counter()
    world.build_institutions()
    world.build_students()
    world.timings["generate_rows"] = time.perf_counter() - t
    t = time.perf_counter()
    planter = Planter(world)
    planter.plant_all()
    world.timings["plant_anomalies"] = time.perf_counter() - t
    t = time.perf_counter()
    UpdatePlanner(world, planter).plan()
    world.timings["plan_updates"] = time.perf_counter() - t
    t = time.perf_counter()
    world.finalise()
    world.timings["finalise_rows"] = time.perf_counter() - t
    t = time.perf_counter()
    GraduateBuilder(world).build()
    world.timings["graduates"] = time.perf_counter() - t
    # Everything below draws from streams of its own, so the rows above keep their values.
    t = time.perf_counter()
    eligibility = EligibilityPlanner(world, planter)
    added = eligibility.add_ciwg_rows()
    signals = SignalPlanner(world, planter)
    added += signals.plant()
    world.history = signals.history
    world.settle(added, random.Random(f"settle:{seed}"))
    eligibility.mark()
    eligibility.plant(avoid=signals.colleges)
    world.timings["eligibility_signals"] = time.perf_counter() - t
    t = time.perf_counter()
    JoiningPlanner(world, planter, avoid=signals.colleges).plan()
    world.timings["joining_records"] = time.perf_counter() - t
    want_xlsx = cfg.size.xlsx if xlsx is None else xlsx
    summary = write_all(world, out, xlsx=want_xlsx)
    summary["timings_seconds"]["total"] = round(time.perf_counter() - started, 3)
    with open(out / "summary.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return summary


def print_summary(summary: dict, stream=None) -> None:
    stream = stream or sys.stdout
    counts = summary["counts"]
    header = f"datagen {summary['size']} seed={summary['seed']} ({summary['generated_at']})"
    print(header, file=stream)
    for key, value in counts.items():
        if key == "ground_truth_by_type":
            continue
        print(f"  {key:<18} {value:>8}", file=stream)
    print("  ground truth by type:", file=stream)
    for key, value in counts["ground_truth_by_type"].items():
        print(f"    {key:<28} {value:>5}", file=stream)
    if summary.get("xlsx_note"):
        print(f"  note: {summary['xlsx_note']}", file=stream)
    timings = summary.get("timings_seconds", {})
    if timings:
        parts = ", ".join(f"{k}={v}s" for k, v in timings.items())
        print(f"  timings: {parts}", file=stream)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="datagen", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write synthetic data to a directory")
    gen.add_argument("--size", choices=["small", "full"], default="small")
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--out", type=Path, required=True)
    gen.add_argument(
        "--scenarios",
        dest="scenarios",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="plant the named demo scenarios (default on)",
    )
    gen.add_argument(
        "--xlsx",
        dest="xlsx",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="also write .xlsx uploads (default from datagen.yaml per size)",
    )

    summ = sub.add_parser("summary", help="print summary.json of a generated directory")
    summ.add_argument("dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "pytest":
        # `docker compose run datagen pytest -q` runs through the image entrypoint.
        import pytest

        return pytest.main(argv[1:])
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        summary = generate(args.size, args.seed, args.out, scenarios=args.scenarios, xlsx=args.xlsx)
        print_summary(summary)
        return 0
    path = args.dir / "summary.json"
    if not path.is_file():
        path = args.dir / "manifest.json"
    if not path.is_file():
        print(f"no summary.json or manifest.json under {args.dir}", file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as fh:
        print_summary(json.load(fh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
