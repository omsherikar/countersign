"""eval.json and eval_report.md. Every number in both is synthetic and says so.

Labels come from the copy deck (docs/ux/05-copy-deck.md §29).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .access import all_refused
from .timing import TARGET_SECONDS, throughput_met

TARGETS = {
    "recall": 0.95,
    "false_alarm_rate": 0.05,
    "throughput_seconds": TARGET_SECONDS,
    "access": "all refused",
}
LIMIT = (
    "We can only check data we receive, and a student who colludes cannot always be caught. "
    "These numbers measure the test bed, not the real world."
)


def passed(result: dict[str, Any]) -> dict[str, bool | None]:
    recall = result["detection"]["overall_recall"]
    rate = result["false_alarms"]["rate"]
    return {
        "recall": recall is not None and recall >= TARGETS["recall"],
        "false_alarms": rate is not None and rate < TARGETS["false_alarm_rate"],
        "throughput": throughput_met(result["timing"]["perf_50k"]),
        "access": all_refused(result["access"]) if result.get("access") else None,
    }


def assemble(
    *,
    dataset: dict[str, Any],
    detection: dict[str, Any],
    record_status: dict[str, Any],
    deadlines: dict[str, Any],
    false_alarms: dict[str, Any],
    controls: dict[str, Any],
    uploads: dict[str, Any],
    perf: dict[str, Any] | None,
    effort: dict[str, Any],
    signals: dict[str, Any],
    access: dict[str, Any] | None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "generated_at": (generated_at or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "synthetic": True,
        "note": "Every number in this file comes from synthetic data.",
        "dataset": dataset,
        "targets": TARGETS,
        "detection": detection,
        "record_status": record_status,
        "deadlines": deadlines,
        "false_alarms": false_alarms,
        "controls": controls,
        "timing": {"uploads": uploads, "perf_50k": perf},
        "effort": effort,
        "signals": signals,
        "access": access,
    }
    result["passed"] = passed(result)
    return result


def failed(result: dict[str, Any]) -> list[str]:
    """The targets that were run and missed."""
    return [name for name, ok in result["passed"].items() if ok is False]


# ------------------------------------------------------------------ markdown


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def _n(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.1f}"
    return f"{int(value):,}"


def _met(ok: bool | None) -> str:
    return {True: "Met", False: "Not met", None: "Not run"}[ok]


def _row(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |"


def render(result: dict[str, Any]) -> str:
    ds = result["dataset"]
    det = result["detection"]
    fa = result["false_alarms"]
    perf = result["timing"]["perf_50k"]
    uploads = result["timing"]["uploads"]
    effort = result["effort"]
    sig = result["signals"]
    acc = result["access"]
    ok = result["passed"]
    run_at = result["generated_at"][:16].replace("T", " ") + " UTC"

    lines = [
        "# Evaluation",
        "",
        "**Synthetic data.** How Countersign performs on the synthetic test bed: generated "
        "colleges, students and planted cases. Every number here is synthetic.",
        "",
        f"Run {run_at} · seed {ds.get('seed')} · {_n(ds.get('institutions'))} colleges · "
        f"{_n(ds.get('records'))} records",
        "",
        _row("Measure", "Result (synthetic)", "Target", "Met"),
        _row("---", "---", "---", "---"),
        _row(
            "Seeded inconsistencies caught",
            f"{_pct(det['overall_recall'])} ({_n(det['found'])} of {_n(det['planted'])})",
            "95% or more",
            _met(ok["recall"]),
        ),
        _row(
            "Cases raised on legitimate records",
            f"{_pct(fa['rate'])} ({_n(fa['flagged'])} of {_n(fa['clean_records'])} "
            "known-clean records)",
            "Under 5%",
            _met(ok["false_alarms"]),
        ),
        _row(
            "Time to process 50,000 rows",
            "not run" if perf is None else f"{perf['seconds']:,.1f} s ({_n(perf['rows'])} rows)",
            "Under 2 minutes",
            _met(ok["throughput"]),
        ),
        _row(
            "Processing time per upload (median)",
            f"{_n(uploads['median_ms'])} ms ({_n(uploads['count'])} uploads)",
            "Reported",
            "",
        ),
        _row(
            "Officer review effort",
            f"{_n(effort['cases_per_1000'])} cases per 1,000 records, "
            f"{_n(effort['facts_per_case'])} evidence rows per case",
            "Reported",
            "",
        ),
        _row(
            "Signals against planted rings and anomalies",
            f"Precision {_pct(sig['precision'])}, recall {_pct(sig['recall'])}",
            "Reported",
            "",
        ),
        _row(
            "Cross-college access attempts refused",
            "not run" if acc is None else f"{_n(acc['refused'])} of {_n(acc['attempts'])}",
            "All refused",
            _met(ok["access"]),
        ),
        "",
        "## Detection by case type",
        "",
        _row("Case type", "Planted", "Caught", "Recall", "Severity as planted"),
        _row("---", "---:", "---:", "---:", "---:"),
    ]
    for case_type, s in det["by_type"].items():
        lines.append(
            _row(
                case_type,
                _n(s["planted"]),
                _n(s["found"]),
                _pct(s["recall"]),
                _pct(s["severity_match"]),
            )
        )
    lines += ["", "## Details (synthetic)", ""]
    lines += _details(result)
    lines += ["", LIMIT, ""]
    return "\n".join(lines)


def _details(result: dict[str, Any]) -> list[str]:
    det = result["detection"]
    rs = result["record_status"]
    dl = result["deadlines"]
    fa = result["false_alarms"]
    controls = result["controls"]
    perf = result["timing"]["perf_50k"]
    uploads = result["timing"]["uploads"]
    effort = result["effort"]
    sig = result["signals"]
    acc = result["access"]
    out = [
        f"- Record statuses: {_n(rs['matched'])} of {_n(rs['checked'])} planted records read "
        f"their expected status; {_n(rs['rows_matched'])} of {_n(rs['rows_checked'])} planted "
        "evidence rows read their expected state.",
    ]
    if dl["available"]:
        out.append(
            f"- Reporting deadlines: {_n(dl['matched'])} of {_n(dl['checked'])} planted late or "
            "overdue colleges show that state."
        )
    else:
        out.append(
            f"- Reporting deadlines: {_n(dl['checked'])} planted late or overdue colleges; the api "
            "has no completeness route to read their state from."
        )
    out.append(
        f"- Planted controls (refused consent, CIWG seats, unreported TFW certificates and "
        f"the like): {_n(controls['flagged'])} of {_n(controls['records'])} named by a case or "
        "under review."
    )
    if fa["causes"]:
        causes = ", ".join(f"{k} {v}" for k, v in fa["causes"].items())
        out.append(f"- What named the known-clean records that were flagged: {causes}.")
    out.append(
        f"- Uploads: {_n(uploads['count'])} files, {_n(uploads['rows'])} rows; median "
        f"{_n(uploads['median_ms'])} ms, 95th percentile {_n(uploads['p95_ms'])} ms, longest "
        f"{_n(uploads['max_ms'])} ms; {_n(uploads['rows_per_second'])} rows per second."
    )
    if perf is not None:
        stages = ", ".join(f"{k} {v / 1000:,.1f} s" for k, v in perf["stages_ms"].items())
        out.append(
            f"- 50,000-row run: {perf['seconds']:,.1f} s, {_n(perf['rows_per_second'])} rows per "
            f"second, status {perf['status']}; stages: {stages}."
        )
        if not perf["fresh"]:
            out.append(
                "- The throughput college was already loaded, so the run above re-read unchanged "
                "rows and does not count. Run make eval, which starts from a fresh database."
            )
    out.append(
        f"- Review effort: {_n(effort['unresolved_cases'])} unresolved cases over "
        f"{_n(effort['active_records'])} active records; {_n(effort['records_per_case'])} "
        "records per case."
    )
    rings, anomalies = sig["rings"], sig["anomalies"]
    if sig["signals_run"]:
        out.append(
            f"- Signals: {_n(rings['found'])} of {_n(rings['planted'])} planted rings found "
            f"({_n(rings['correct'])} of {_n(rings['signals'])} ring signals match one); "
            f"{_n(anomalies['found'])} of {_n(anomalies['planted'])} planted anomalies found "
            f"({_n(anomalies['correct'])} of {_n(anomalies['signals'])} anomaly signals match one)."
        )
    else:
        out.append("- Signals: none in the database; the signal run has not been made.")
    if acc is not None:
        out.append(
            f"- Access: {_n(acc['attempts'])} attempts, {_n(acc['refused'])} refused, "
            f"{_n(len(acc['leaks']))} answered, {_n(acc['error_count'])} other errors; "
            f"{_n(acc['controls']['ok'])} of {_n(acc['controls']['attempts'])} requests for a "
            "college's own data answered."
        )
        if acc["skipped_paths"]:
            out.append(f"- Routes the api does not serve yet: {', '.join(acc['skipped_paths'])}.")
    if det["misses"]:
        out.append("- Planted cases not caught:")
        for miss in det["misses"]:
            out.append(
                f"  - {miss['type']} at {miss['institution']}"
                f"{' ' + miss['programme_code'] if miss['programme_code'] else ''}: {miss['note']}"
            )
    return out


def write(out_dir: Path, result: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval.json"
    md_path = out_dir / "eval_report.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render(result), encoding="utf-8")
    return md_path, json_path
