"""`--perf N`: a throughput dataset for the evaluation (API_CONTRACT A4.25), under `perf/`.

- `perf/institutions.json`: the regions, states and universities of the main file and one
  synthetic college, "Countersign Throughput Test College" (`9-PERF-0001`, Maharashtra,
  affiliated to MSTU), whose ten B.Tech programmes have approvals for 2025-26 and 2026-27
  large enough to seat every row.
- `perf/9-PERF-0001_2026-27.csv`: exactly N rows, every one legitimate: a linked APAAR the
  registry holds under the same name, a REGULAR-pool route, a seat, a joining line, credits
  for a second-year, no duplicate, no shared contact.
- `perf/mockgov/apaar_registry.jsonl`, `admission_joinings.jsonl`, `abc_credits.jsonl` and
  `digilocker_accounts.jsonl`: those students' lines.

Nothing in `perf/` is loaded by `make seed`. Ids, mobiles and emails never repeat those of the
main dataset. A random stream of its own leaves every other file unchanged.
"""

from __future__ import annotations

import datetime as dt
import math
import random
from pathlib import Path

from . import geo
from .digilocker import ALPHABET
from .institutions import approvals_for, programme_record, public_institution
from .students import (
    LATE_DAYS,
    World,
    academic_year_label,
    academic_year_start,
    admission_window,
    share_of,
)

PERF_ID = "9-PERF-0001"
PERF_NAME = "Countersign Throughput Test College"
PERF_CODES = ["CSE", "IT", "ECE", "EEE", "EE", "MECH", "CIVIL", "AIML", "AIDS", "ETC"]
SECOND_YEAR_SHARE = 0.3


def perf_institution(rows: int) -> dict:
    """Every programme admits rows / 10 students a year at most; its intake leaves REGULAR
    seats (intake minus the NRI share) for all of them."""
    per_cohort = math.ceil(rows / len(PERF_CODES))
    intake = per_cohort
    while intake - share_of(intake, 0.05) < per_cohort:
        intake += 1
    return {
        "aicte_permanent_id": PERF_ID,
        "name": PERF_NAME,
        "type": "PRIVATE_SELF_FINANCED",
        "state_code": "MH",
        "university_code": "MSTU",
        "address_city": "Pune",
        "established_year": 2001,
        "_autonomous": False,
        "programmes": [
            programme_record(code, approvals_for(intake, ("2025-26", "2026-27")))
            for code in PERF_CODES
        ],
    }


class PerfBuilder:
    def __init__(self, world: World, rows: int):
        self.w = world
        self.n = rows
        self.rng = random.Random(f"perf:{world.seed}")
        self.inst = perf_institution(rows)
        self.year = world.cfg.academic_year
        self.used_ids: set[str] = set()

    def digilocker_id(self) -> str:
        while True:
            chars = "".join(self.rng.choices(ALPHABET, k=8))
            candidate = f"DL-P{chars[:3]}-{chars[3:7]}"
            if candidate not in self.used_ids:
                self.used_ids.add(candidate)
                return candidate

    def rows(self) -> list[dict]:
        w = self.w
        second = round(self.n * SECOND_YEAR_SHARE)
        seen: set[tuple[str, int, str, str]] = set()
        out = []
        with w.using_rng(self.rng):
            for i in range(self.n):
                prog = self.inst["programmes"][i % len(PERF_CODES)]
                year_of_study = 2 if i < second else 1
                route = self.rng.choices(["COUNSELLING", "MANAGEMENT", "SPOT"], [70, 24, 6])[0]
                row = w.make_student(self.inst, prog, year_of_study, route)
                if row["consent_status"] != "LINKED":
                    row["consent_status"] = "LINKED"
                    row["apaar_id"] = w.new_apaar()
                key = (prog["code"], year_of_study, row["name"], row["dob"])
                while key in seen:
                    row["dob"] = w.dob(row["_adm_year"], prog["level"])
                    key = (prog["code"], year_of_study, row["name"], row["dob"])
                seen.add(key)
                window = admission_window(w.cfg.rules, row["_cohort_start"])
                last = window[1] - dt.timedelta(days=LATE_DAYS)
                row["admission_date"] = w.random_date(window[0], last).isoformat()
                out.append(row)
        order = {p["code"]: n for n, p in enumerate(self.inst["programmes"])}
        out.sort(key=lambda r: (order[r["programme_code"]], r["year_of_study"], r["_seq"]))
        return out

    def registry(self, rows: list[dict]) -> list[dict]:
        return [
            {"apaar_id": r["apaar_id"], "name": r["name"], "dob": r["dob"], "gender": r["gender"]}
            for r in rows
        ]

    def joinings(self, rows: list[dict]) -> list[dict]:
        out = []
        counter = 0
        for r in rows:
            year = academic_year_label(r["_cohort_start"])
            roll = r["_roll_no"]
            if not roll:
                counter += 1
                roll = f"MHAA-P{year[:4]}-{counter:06d}"
            admitted = dt.date.fromisoformat(r["admission_date"])
            joined = min(
                admitted + dt.timedelta(days=self.rng.randint(0, 6)),
                dt.date.fromisoformat(self.w.cfg.reporting_deadline(year)),
            )
            out.append(
                {
                    "state": "MH", "academic_year": year, "name": r["name"], "dob": r["dob"],
                    "roll_no": roll, "institution_code": PERF_ID,
                    "programme": r["programme_code"], "joined_on": joined.isoformat(),
                    "round": r["_round"] or None, "route": r["admission_route"],
                    "category": r["category"], "apaar_id": r["apaar_id"],
                }
            )  # fmt: skip
        return out

    def credits(self, rows: list[dict]) -> list[dict]:
        last = academic_year_label(academic_year_start(self.year) - 1)
        names = {u["code"]: u["name"] for u in self.w.universities}
        out = []
        for r in rows:
            if r["year_of_study"] != 2:
                continue
            for sem, uploaded in ((1, "-01-20"), (2, "-06-30")):
                out.append(
                    {
                        "apaar_id": r["apaar_id"], "academic_year": last, "sem": sem,
                        "credits": self.rng.randint(18, 26),
                        "uploaded_at": f"{int(last[:4]) + 1}{uploaded}T00:00:00Z",
                        "result": "PASS", "issuer": "MSTU", "issuer_name": names["MSTU"],
                    }
                )  # fmt: skip
        return out

    def accounts(self, rows: list[dict]) -> list[dict]:
        return [
            {
                "digilocker_id": self.digilocker_id(), "name": r["name"], "dob": r["dob"],
                "gender": r["gender"], "apaar_id": r["apaar_id"],
            }
            for r in rows
        ]  # fmt: skip

    def write(self, out: Path, write_csv, dump_json, dump_jsonl) -> dict:
        rows = self.rows()
        folder = out / "perf"
        (folder / "mockgov").mkdir(parents=True, exist_ok=True)
        dump_json(
            folder / "institutions.json",
            {
                "regions": geo.REGIONS,
                "states": geo.STATES,
                "universities": self.w.universities,
                "institutions": [public_institution(self.inst)],
            },
        )
        name = f"{PERF_ID}_{self.year}.csv"
        write_csv(folder / name, rows)
        dump_jsonl(folder / "mockgov" / "apaar_registry.jsonl", self.registry(rows))
        dump_jsonl(folder / "mockgov" / "admission_joinings.jsonl", self.joinings(rows))
        dump_jsonl(folder / "mockgov" / "abc_credits.jsonl", self.credits(rows))
        dump_jsonl(folder / "mockgov" / "digilocker_accounts.jsonl", self.accounts(rows))
        return {
            "institutions_file": "perf/institutions.json",
            "file": f"perf/{name}",
            "rows": len(rows),
        }
