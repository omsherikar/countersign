"""The state admission authority's joinings and the cases planted against them.

`mockgov/admission_joinings.jsonl` (API_CONTRACT A4.25) holds one line per joining of every
cohort on the roll: every uploaded student (late refills included) except international
admissions (Study in India holds those), a renamed duplicate row (its person already has a
line) and the rows planted as never joined; plus the students colleges left out of their
upload. One state's record format, simulated for every state.

- `academic_year` is the year the student joined this programme: the cohort's year, and for
  a lateral entrant the year it entered year 2.
- `roll_no` is the entrance-exam roll number for counselled, TFW and lateral admissions (the
  one counselling.jsonl holds) and the authority's number `<STATE>AA-<year>-<nnnnnn>` for
  management, NRI and spot admissions.
- `joined_on` is a few days after the admission and never after the year's reporting
  deadline, except for a few clean first-years who joined late and for refills admitted
  after the deadline.
- `apaar_id` is the student's APAAR when the registry holds it under that student, else null.
- One state has published nothing for the previous academic year: its second-years have no
  line, so their Joining record reads pending, never contradicted (`unpublished`).

Planted, each in ground truth:

- NOT_IN_JOINING_RECORD (MEDIUM): uploaded rows of students who never joined; their
  counselling allotment, when they had one, stays. With the named scenarios one of them is
  the sample card: the ABC College CSE first-year who answers No (STUDENT_DENIED, scenario
  `not_me`), whose APAAR verifies and whose seat fits; the record reads Disputed.
- MISSING_FROM_UPLOAD (MEDIUM, one record per college and year): first-years with a joining
  line (and an APAAR, a counselling allotment where counselled, a DigiLocker account) whom
  their college left out of its upload; XYZ Institute of Technology is one such college.

A random stream of its own, seeded from the run's seed, leaves every other row unchanged.
"""

from __future__ import annotations

import datetime as dt
import random
from collections import defaultdict

from .anomalies import Planter
from .institutions import ABC_ID, XYZ_ID
from .students import World, academic_year_label, academic_year_start, admission_window

SAMPLE_CARD_ROWS = {
    "IDENTITY": "CONFIRMED",
    "SEAT": "CONFIRMED",
    "ADMISSION": "CONTRADICTED",
    "STUDYING": "NOT_YET_DUE",
    "STUDENT": "CONTRADICTED",
}
JOINING_FIELDS = [
    "state", "academic_year", "name", "dob", "roll_no", "institution_code", "programme",
    "joined_on", "round", "route", "category", "apaar_id",
]  # fmt: skip


def joining_year(row: dict, academic_year: str) -> str:
    """The academic year the student joined the programme, as the api reads it from the row:
    the cohort's year, or year 2's for a lateral entrant."""
    start = academic_year_start(academic_year) - (row["year_of_study"] - 1)
    if row["admission_route"] == "LATERAL":
        start += 1
    return academic_year_label(start)


def owns_apaar(row: dict) -> bool:
    """The row's APAAR is the student's own: LINKED, 12 digits, held under this name."""
    return (
        row["consent_status"] == "LINKED"
        and len(row["apaar_id"]) == 12
        and row["apaar_id"].isdigit()
        and row["_registry"] == "match"
    )


class JoiningPlanner:
    def __init__(self, world: World, planter: Planter, avoid: set[str] = frozenset()):
        self.w = world
        self.planter = planter
        self.avoid = set(avoid)
        self.cfg = world.cfg.joining
        self.rng = random.Random(f"joining:{world.seed}")
        self.year = world.cfg.academic_year
        self.last_year = academic_year_label(academic_year_start(self.year) - 1)
        self.records: list[dict] = []
        self.missing: dict[str, list[dict]] = {}
        self.late: set[int] = set()
        # (state, academic_year) the authority has not published
        self.unpublished: set[tuple[str, str]] = set()

    # ---------------------------------------------------------------- driver

    def plan(self, self_issued_state: str | None = None) -> list[dict]:
        if self_issued_state:
            self.unpublished.add((self_issued_state, self.last_year))
        self.plant_never_joined()
        self.plant_omitted()
        self.pick_late_joiners()
        self.build_records()
        self.record_missing()
        self.w.joining_records = self.records
        return self.records

    def published(self, row: dict) -> bool:
        state = self.w.inst_by_id[row["_inst"]]["state_code"]
        return (state, joining_year(row, self.year)) not in self.unpublished

    # ---------------------------------------------------------------- picks

    def clean(self, row: dict) -> bool:
        """An untouched, linked, physical, non-international row outside ABC College and the
        colleges other plants keep, in a year the authority published."""
        return (
            not row["_tags"]
            and owns_apaar(row)
            and row["_prog"]["mode"] == "PHYSICAL"
            and row["admission_route"] != "INTERNATIONAL"
            and row["_inst"] != ABC_ID
            and row["_inst"] not in self.avoid
            and self.published(row)
        )

    def candidates(self, years: set[int]) -> list[dict]:
        leaving = self.w.leaving_rows()
        return [
            r for r in self.w.all_rows
            if r["year_of_study"] in years and self.clean(r) and id(r) not in leaving
        ]  # fmt: skip

    def plant_never_joined(self) -> None:
        w = self.w
        k = self.cfg.get("never_joined", 0)
        if w.cfg.scenarios and k:
            rec = next(r for r in w.ground_truth if r.get("scenario") == "not_me")
            self.never_joined(rec["_rows"][0], scenario="sample_card")
            k -= 1
        for row in self.rng.sample(self.candidates({1, 2}), k):
            self.never_joined(row)

    def never_joined(self, row: dict, scenario: str | None = None) -> None:
        year = joining_year(row, self.year)
        extra = {}
        if scenario == "sample_card":
            extra = {
                "expected_rows": SAMPLE_CARD_ROWS,
                "expected_record_status": "DISPUTED",
            }
            note = (
                "Sample card: ABC College says this student joined B.Tech CSE; the APAAR "
                "verifies and the seat fits, but the state admission authority has no "
                "joining line and the student answers No."
            )
        else:
            note = "Uploaded as enrolled, but the state admission authority has no joining line."
        self.planter.record(
            "NOT_IN_JOINING_RECORD", [row],
            expected_flag="NOT_IN_JOINING_RECORD", severity="MEDIUM",
            institution_ids=[row["_inst"]], programme_code=row["programme_code"],
            academic_year=year, reporting_deadline=self.w.cfg.reporting_deadline(year),
            scenario=scenario, note=note, **extra,
        )  # fmt: skip

    # --------------------------------------------------------------- omitted

    def omitting_colleges(self) -> list[dict]:
        w = self.w
        n = self.cfg.get("omitted_colleges", 0)
        first = [w.inst_by_id[XYZ_ID]] if w.cfg.scenarios and n else []
        pool = [
            i for i in w.institutions
            if i["aicte_permanent_id"] not in {ABC_ID, XYZ_ID} | self.avoid and self.places(i)
        ]  # fmt: skip
        return first + self.rng.sample(pool, min(len(pool), n - len(first)))

    def places(self, inst: dict) -> list[dict]:
        """Physical programmes whose first-year REGULAR pool would still take them."""
        w = self.w
        aid = inst["aicte_permanent_id"]
        return [
            p for p in inst["programmes"]
            if p["mode"] == "PHYSICAL" and w.refill_programmes.get(aid) != p["code"]
            and w.room(aid, p, 1, "COUNSELLING") >= 1
        ]  # fmt: skip

    def plant_omitted(self) -> None:
        w = self.w
        lo, hi = self.cfg.get("omitted_per_college", [2, 6])
        start = academic_year_start(self.year)
        window = admission_window(w.cfg.rules, start)
        last_day = window[1] - dt.timedelta(days=10)
        for inst in self.omitting_colleges():
            aid = inst["aicte_permanent_id"]
            places = self.places(inst)
            room = {p["code"]: w.room(aid, p, 1, "COUNSELLING") for p in places}
            taken = {
                (r["programme_code"], r["dob"]) for r in w.rows_by_inst[aid]
                if r["year_of_study"] == 1
            }  # fmt: skip
            out = []
            with w.using_rng(self.rng):
                for _ in range(self.rng.randint(lo, hi)):
                    open_places = [p for p in places if room[p["code"]] > 0]
                    if not open_places:
                        break
                    prog = self.rng.choice(open_places)
                    room[prog["code"]] -= 1
                    route = w.regular_routes(inst, 1)[0]
                    row = w.make_student(inst, prog, 1, route)
                    while (prog["code"], row["dob"]) in taken:
                        row["dob"] = w.dob(start, prog["level"])
                    taken.add((prog["code"], row["dob"]))
                    row["admission_date"] = w.random_date(window[0], last_day).isoformat()
                    out.append(row)
            w.omitted_rows.extend(out)
            self.missing[aid] = out

    def pick_late_joiners(self) -> None:
        start = academic_year_start(self.year)
        rows = [r for r in self.candidates({1}) if r["_cohort_start"] == start]
        k = min(self.cfg.get("late_joiners", 0), len(rows))
        self.late = {id(r) for r in self.rng.sample(rows, k)}

    # --------------------------------------------------------------- records

    def joined_on(self, row: dict) -> str:
        admitted = dt.date.fromisoformat(row["admission_date"])
        year = joining_year(row, self.year)
        if int(year[:4]) > admitted.year:
            # A lateral entrant's admission is dated in its cohort's window, a year before it
            # entered year 2.
            admitted = admitted.replace(year=int(year[:4]))
        deadline = dt.date.fromisoformat(self.w.cfg.reporting_deadline(year))
        if id(row) in self.late:
            return (deadline + dt.timedelta(days=self.rng.randint(1, 12))).isoformat()
        if admitted > deadline:  # a refill admitted after the deadline
            return (admitted + dt.timedelta(days=self.rng.randint(0, 2))).isoformat()
        lo, hi = self.cfg.get("joined_within_days", [0, 6])
        joined = admitted + dt.timedelta(days=self.rng.randint(lo, hi))
        return min(joined, deadline).isoformat()

    def joined_rows(self) -> list[dict]:
        w = self.w
        renamed = {
            id(rec["_rows"][1]) for rec in w.ground_truth
            if rec["anomaly_type"] == "DUPLICATE_WITHIN_UPLOAD"
        }  # fmt: skip
        out = []
        for row in w.all_rows + w.update_only_rows + w.omitted_rows:
            if row["admission_route"] == "INTERNATIONAL" or id(row) in renamed:
                continue
            if "NOT_IN_JOINING_RECORD" in row["_tags"] or not self.published(row):
                continue
            out.append(row)
        return out

    def build_records(self) -> None:
        w = self.w
        counters: dict[tuple[str, str], int] = defaultdict(int)
        order = {i["aicte_permanent_id"]: n for n, i in enumerate(w.institutions)}
        records = []
        for row in self.joined_rows():
            inst = w.inst_by_id[row["_inst"]]
            year = joining_year(row, self.year)
            roll = row["_roll_no"]
            if not roll:
                key = (inst["state_code"], year[:4])
                counters[key] += 1
                roll = f"{key[0]}AA-{key[1]}-{counters[key]:06d}"
            row["_joining_roll_no"] = roll
            row["_joined_on"] = self.joined_on(row)
            values = (
                inst["state_code"], year, row["name"], row["dob"], roll, row["_inst"],
                row["programme_code"], row["_joined_on"], row["_round"] or None,
                row["admission_route"], row["category"],
                row["apaar_id"] if owns_apaar(row) else None,
            )  # fmt: skip
            records.append(dict(zip(JOINING_FIELDS, values, strict=True)))
        records.sort(
            key=lambda r: (order[r["institution_code"]], r["academic_year"], r["programme"],
                           r["joined_on"], r["roll_no"])
        )  # fmt: skip
        self.records = records

    def record_missing(self) -> None:
        joined = defaultdict(int)
        for rec in self.records:
            if rec["academic_year"] == self.year:
                joined[rec["institution_code"]] += 1
        for aid, rows in self.missing.items():
            if not rows:
                continue
            self.record_missing_college(aid, rows, joined[aid])

    def record_missing_college(self, aid: str, rows: list[dict], joined: int, **extra) -> None:
        students = [
            {
                "roll_no": r["_joining_roll_no"],
                "name": r["name"],
                "dob": r["dob"],
                "programme_code": r["programme_code"],
                "academic_year": self.year,
                "joined_on": r["_joined_on"],
                "route": r["admission_route"],
                "apaar_id": r["apaar_id"] if owns_apaar(r) else None,
            }
            for r in rows
        ]
        self.planter.record(
            "MISSING_FROM_UPLOAD", [],
            expected_flag="MISSING_FROM_UPLOAD", severity="MEDIUM",
            institution_ids=[aid], programme_code=None, academic_year=self.year,
            missing=len(students), missing_students=students, joined=joined,
            uploaded_and_joined=joined - len(students),
            completeness_pct=round(100 * (joined - len(students)) / joined, 1),
            scenario=extra.pop("scenario", "xyz_missing" if aid == XYZ_ID else None),
            note=extra.pop(
                "note",
                f"{len(students)} first-years in the state admission authority's joining "
                f"list are missing from the college's {self.year} upload.",
            ),
            **extra,
        )  # fmt: skip
