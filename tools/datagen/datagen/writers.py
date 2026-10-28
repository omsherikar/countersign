"""File writers for the section E contract: JSON, CSV, XLSX, JSONL, manifest and summary."""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from . import geo
from .digilocker import AccountBuilder
from .graduates import records as graduate_records
from .graduates import registry_records as graduate_registry_records
from .institutions import ABC_ID, XYZ_ID, public_institution
from .notices import ReplyPlanner
from .students import DEMO_APAAR, DEMO_NAME, UPLOAD_COLUMNS, World

PASSWORD = "Countersign!2026"
FIXED_XLSX_TIME = dt.datetime(2026, 7, 1, 0, 0, 0)


def upload_filename(aicte_id: str, academic_year: str, ext: str = "csv") -> str:
    return f"uploads/{aicte_id}_{academic_year}.{ext}"


def update_filename(aicte_id: str, academic_year: str, n: int = 1, ext: str = "csv") -> str:
    return f"uploads/{aicte_id}_{academic_year}_update{n}.{ext}"


def materialise(row: dict) -> None:
    """An update row of an existing student repeats every column of its initial row."""
    initial = row.get("_initial")
    if initial is None:
        return
    for column in UPLOAD_COLUMNS:
        if column not in {"status", "status_date"}:
            row[column] = initial[column]


def row_sort_key(inst: dict):
    order = {p["code"]: i for i, p in enumerate(inst["programmes"])}

    def key(row: dict):
        return (order[row["programme_code"]], row["year_of_study"], row["_seq"])

    return key


APAAR_RE = re.compile(r"[0-9]{12}")


def student_ref(row: dict, file: str) -> str:
    """The APAAR when the api will key the student on it, else `<file>#<row_no>`."""
    if APAAR_RE.fullmatch(row["apaar_id"]) and row["consent_status"] == "LINKED":
        return row["apaar_id"]
    return f"{file}#{row['row_no']}"


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def dump_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
            fh.write("\n")


_MODIFIED_RE = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")
_CREATED_RE = re.compile(rb"(<dcterms:created[^>]*>)[^<]*(</dcterms:created>)")


def normalize_zip(path: Path) -> None:
    """Rewrite a zip with fixed entry and document timestamps so the same data gives the
    same bytes. openpyxl stamps `dcterms:modified` with the wall clock on every save."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    stamp = FIXED_XLSX_TIME.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                data = _MODIFIED_RE.sub(rb"\g<1>" + stamp + rb"\g<2>", data)
                data = _CREATED_RE.sub(rb"\g<1>" + stamp + rb"\g<2>", data)
            fixed = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = info.external_attr
            dst.writestr(fixed, data)
    os.replace(tmp, path)


def headers_for(world: World, aicte_id: str) -> list[str]:
    """The template columns, under the college's own headers when it uses some."""
    own = world.header_maps.get(aicte_id, {})
    return [own.get(column, column) for column in UPLOAD_COLUMNS]


def write_xlsx(path: Path, rows: list[dict], headers: list[str] = UPLOAD_COLUMNS) -> None:
    wb = Workbook(write_only=True)
    wb.properties.created = FIXED_XLSX_TIME
    wb.properties.modified = FIXED_XLSX_TIME
    wb.properties.creator = "datagen"
    wb.properties.lastModifiedBy = "datagen"
    ws = wb.create_sheet("students")
    ws.append(headers)
    for row in rows:
        # A blank stays an empty cell, as in a sheet a registrar fills in by hand.
        ws.append([None if row[c] == "" else row[c] for c in UPLOAD_COLUMNS])
    wb.save(path)
    normalize_zip(path)


def write_csv(path: Path, rows: list[dict], headers: list[str] = UPLOAD_COLUMNS) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row[c] for c in UPLOAD_COLUMNS])


def users_payload(world: World) -> list[dict]:
    abc = world.inst_by_id[ABC_ID]
    xyz = world.inst_by_id[XYZ_ID]
    users = [
        {"email": "admin@aicte.demo", "password": PASSWORD, "role": "AICTE_ADMIN",
         "name": "AICTE Administrator"},
        {"email": "ro.west@aicte.demo", "password": PASSWORD, "role": "RO_OFFICER",
         "name": "Regional Officer, Western Region", "region": "WEST"},
        {"email": "ro.south@aicte.demo", "password": PASSWORD, "role": "RO_OFFICER",
         "name": "Regional Officer, Southern Region", "region": "SOUTH"},
        {"email": "registrar@abc.edu.demo", "password": PASSWORD, "role": "INSTITUTION",
         "name": f"Registrar, {abc['name']}", "institution_aicte_id": ABC_ID},
        {"email": "registrar@xyz.edu.demo", "password": PASSWORD, "role": "INSTITUTION",
         "name": f"Registrar, {xyz['name']}", "institution_aicte_id": XYZ_ID},
        {"email": "student@demo", "password": PASSWORD, "role": "STUDENT",
         "name": DEMO_NAME, "student_ref": DEMO_APAAR},
        {"email": "coe@univ.demo", "password": PASSWORD, "role": "UNIVERSITY",
         "name": "Controller of Examinations, Maharashtra State Technical University",
         "university_code": "MSTU"},
    ]  # fmt: skip
    for inst in world.institutions:
        if inst["aicte_permanent_id"] in {ABC_ID, XYZ_ID}:
            continue
        users.append(
            {
                "email": f"registrar@{inst['_slug']}.edu.demo",
                "password": PASSWORD,
                "role": "INSTITUTION",
                "name": f"Registrar, {inst['name']}",
                "institution_aicte_id": inst["aicte_permanent_id"],
            }
        )
    return users


def row_detail(row: dict) -> dict:
    detail = {
        "file": row["_file"],
        "row_no": row["row_no"],
        "institution_aicte_id": row["_inst"],
        "apaar_id": row["apaar_id"] or None,
        "name": row["name"],
        "programme_code": row["programme_code"],
        "year_of_study": row["year_of_study"],
    }
    initial = row.get("_initial")
    if initial is not None:
        detail["initial_file"] = initial["_file"]
        detail["initial_row_no"] = initial["row_no"]
    return detail


def finalize_ground_truth(world: World) -> list[dict]:
    out = []
    for rec in world.ground_truth:
        rows = rec.pop("_rows")
        released = rec.pop("_released", None)
        rec["student_refs"] = [student_ref(row, row["_file"]) for row in rows]
        rec["rows"] = [row_detail(row) for row in rows]
        if released is not None:
            rec["released_rows"] = [row_detail(row) for row in released]
        out.append(rec)
    return out


DEMO_ROLES = (
    "DEMO_STUDENT", "SECOND_DEMO_NOTICE", "PROVISIONAL_CLAIM", "SOMEONE_ELSE", "SAMPLE_CARD",
)  # fmt: skip


def demo_digilocker_accounts(
    world: World, planner: ReplyPlanner, accounts: AccountBuilder
) -> list[dict]:
    """The accounts the live demo signs in with, each with the upload row it stands for."""
    if not world.cfg.scenarios:
        return []
    rows = dict(planner.demo_rows())
    rows.update(world.demo_rows)
    sample = next((r for r in world.ground_truth if r.get("scenario") == "not_me"), None)
    if sample is not None:
        rows["SAMPLE_CARD"] = sample["_rows"][0]
    out = []
    for role in DEMO_ROLES:
        row = rows.get(role)
        account_id = accounts.account_of(row) if row is not None else None
        if account_id is None:
            continue
        account = accounts.get(account_id)
        out.append(
            {
                "role": role,
                "digilocker_id": account_id,
                "name": account["name"],
                "dob": account["dob"],
                "apaar_id": account["apaar_id"],
                "file": row["_file"],
                "row_no": row["row_no"],
            }
        )
    return out


def write_all(
    world: World, out: Path, *, xlsx: bool = True, submissions=None, perf: int | None = None
) -> dict:
    import time

    out.mkdir(parents=True, exist_ok=True)
    (out / "uploads").mkdir(exist_ok=True)
    (out / "mockgov").mkdir(exist_ok=True)
    year = world.cfg.academic_year

    t = time.perf_counter()
    dump_json(
        out / "institutions.json",
        {
            "regions": geo.REGIONS,
            "states": geo.STATES,
            "universities": world.universities,
            "institutions": [public_institution(i) for i in world.institutions],
        },
    )
    dump_json(out / "users.json", users_payload(world))
    dump_json(
        out / "column_mappings.json",
        {aid: {header: column for column, header in own.items()}
         for aid, own in sorted(world.header_maps.items())},
    )  # fmt: skip
    world.timings["write_institutions_users"] = time.perf_counter() - t

    t = time.perf_counter()
    files: list[tuple[str, list[dict]]] = []
    for inst in world.institutions:
        aid = inst["aicte_permanent_id"]
        if aid in world.overdue:
            continue  # an overdue college sent no file
        rows = world.rows_by_inst[aid]
        rows.sort(key=row_sort_key(inst))
        files.append((upload_filename(aid, year), rows))
    updates: list[tuple[str, list[dict]]] = []
    for inst in world.institutions:
        aid = inst["aicte_permanent_id"]
        if world.update_files.get(aid):
            updates.append((update_filename(aid, year), world.update_files[aid]))
    for name, rows in files + updates:
        # Spreadsheet numbering, as the api reports it: the header is row 1.
        for i, row in enumerate(rows, start=2):
            materialise(row)
            row["row_no"] = i
            row["_file"] = name
        write_csv(out / name, rows, headers_for(world, name.split("/")[1].split("_")[0]))
    world.timings["write_csv"] = time.perf_counter() - t

    world.xlsx_written = False
    if xlsx:
        t = time.perf_counter()
        for name, rows in files + updates:
            headers = headers_for(world, name.split("/")[1].split("_")[0])
            write_xlsx(out / name.replace(".csv", ".xlsx"), rows, headers)
        world.timings["write_xlsx"] = time.perf_counter() - t
        world.xlsx_written = True

    t = time.perf_counter()
    registry = world.registry_records() + graduate_registry_records(world.graduates)
    counselling = world.counselling_records()
    abc = world.abc_records()
    sii = world.sii_records()
    dump_jsonl(out / "mockgov" / "apaar_registry.jsonl", registry)
    dump_jsonl(out / "mockgov" / "counselling.jsonl", counselling)
    dump_jsonl(out / "mockgov" / "abc_credits.jsonl", abc)
    dump_jsonl(out / "mockgov" / "sii.jsonl", sii)
    dump_jsonl(out / "mockgov" / "admission_joinings.jsonl", world.joining_records)
    world.timings["write_mockgov"] = time.perf_counter() - t

    t = time.perf_counter()
    dump_jsonl(out / "graduates.jsonl", graduate_records(world.graduates))
    planner = ReplyPlanner(world, files, {r["apaar_id"] for r in registry})
    replies = planner.plan()
    dump_jsonl(out / "notice_replies.jsonl", replies)
    accounts = AccountBuilder(world, registry)
    accounts.build()
    demo_accounts = demo_digilocker_accounts(world, planner, accounts)
    accounts.put_first([d["digilocker_id"] for d in demo_accounts])
    dump_jsonl(out / "mockgov" / "digilocker_accounts.jsonl", accounts.accounts)
    sample = next((r for r in world.ground_truth if r.get("scenario") == "sample_card"), None)
    world.timings["write_graduates_replies"] = time.perf_counter() - t

    ground_truth = finalize_ground_truth(world)
    sample_card = (
        {"file": sample["rows"][0]["file"], "row_no": sample["rows"][0]["row_no"]}
        if sample
        else None
    )
    dump_json(out / "ground_truth.json", ground_truth)
    dump_json(out / "history.json", world.history)

    by_type: dict[str, int] = {}
    for rec in ground_truth:
        by_type[rec["anomaly_type"]] = by_type.get(rec["anomaly_type"], 0) + 1
    counts = {
        "regions": len(geo.REGIONS),
        "states": len(geo.STATES),
        "universities": len(world.universities),
        "institutions": len(world.institutions),
        "programmes": sum(len(i["programmes"]) for i in world.institutions),
        "approvals": sum(len(p["approvals"]) for i in world.institutions for p in i["programmes"]),
        "users": 7 + len(world.institutions) - 2,
        "upload_files": len(files),
        "update_files": len(updates),
        "update_rows": sum(len(rows) for _, rows in updates),
        "students": sum(len(rows) for _, rows in files),
        "apaar_registry": len(registry),
        "counselling": len(counselling),
        "abc_credits": len(abc),
        "sii": len(sii),
        "admission_joinings": len(world.joining_records),
        "admission_joinings_late": sum(
            r["joined_on"] > world.cfg.reporting_deadline(r["academic_year"])
            for r in world.joining_records
        ),
        "missing_from_upload": len(world.omitted_rows),
        "digilocker_accounts": len(accounts.accounts),
        "graduates": len(world.graduates),
        "notice_replies": len(replies),
        "notice_replies_yes": sum(r["reply"] == "YES" for r in replies),
        "notice_replies_no": sum(r["reply"] == "NO" for r in replies),
        "notice_replies_none": sum(r["reply"] == "NONE" for r in replies),
        "history_institutions": len(world.history.get("institutions", [])),
        "ground_truth": len(ground_truth),
        "ground_truth_by_type": dict(sorted(by_type.items())),
    }
    generated_at = os.environ.get("SOURCE_DATE_EPOCH")
    if generated_at:
        stamp = dt.datetime.fromtimestamp(int(generated_at), tz=dt.UTC)
    else:
        stamp = dt.datetime.now(tz=dt.UTC)
    manifest = {
        "size": world.cfg.size.name,
        "seed": world.seed,
        "generated_at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": counts,
        # Notices the live demo answers by hand; notice_replies.jsonl leaves them unanswered.
        "demo_unanswered_notices": planner.unanswered,
        "reporting_deadline": {year: world.cfg.reporting_deadline(year)},
        # When each file arrived; the seed sets its batch's upload time from it.
        "uploads": submissions.submitted([n for n, _ in files], [n for n, _ in updates])
        if submissions
        else [],
        "late_colleges": list(world.late),
        "overdue_colleges": list(world.overdue),
        "demo_digilocker_accounts": demo_accounts,
        # The deck's sample record (ABC College CSE), or null without the named scenarios.
        "sample_card": sample_card,
    }
    if perf:
        from .perf import PerfBuilder

        t = time.perf_counter()
        manifest["perf"] = PerfBuilder(world, perf).write(out, write_csv, dump_json, dump_jsonl)
        world.timings["perf"] = time.perf_counter() - t
    dump_json(out / "manifest.json", manifest)
    summary = dict(manifest)
    summary.update(
        {
            "academic_year": year,
            "scenarios": world.cfg.scenarios,
            "xlsx_written": world.xlsx_written,
            "xlsx_note": None
            if world.xlsx_written
            else "XLSX uploads skipped for this run; CSV files carry the same rows.",
            "upload_columns": UPLOAD_COLUMNS,
            "row_numbering": "row_no is the spreadsheet row: the header is row 1, the first "
            "data row is row 2.",
            "timings_seconds": {k: round(v, 3) for k, v in world.timings.items()},
        }
    )
    dump_json(out / "summary.json", summary)
    return summary
