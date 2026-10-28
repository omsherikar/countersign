"""Student rows (what a college uploads) and the generation world they live in.

Every row is a dict with the upload columns (the nineteen of the contract, then the three
optional eligibility markers) plus internal keys prefixed `_` that drive registry emission and
anomaly bookkeeping. Internal keys never reach a file.
"""

from __future__ import annotations

import datetime as dt
import math
import random
import re
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from faker import Faker

from . import geo
from .config import Config
from .institutions import InstitutionBuilder, approved_intake, assign_autonomy, credit_issuer
from .matching import name_key
from .names import NameGenerator

CONTRACT_COLUMNS = [
    "apaar_id", "name", "dob", "gender", "mobile", "email", "address", "nationality",
    "passport_no", "programme_code", "academic_year", "year_of_study", "admission_route",
    "counselling_ref", "category", "consent_status", "status", "status_date", "admission_date",
]  # fmt: skip
# Optional category-eligibility markers (eligibility.py), after the contract's columns.
ELIGIBILITY_COLUMNS = ["tfw_income_certified", "nri_sponsored", "ciwg"]
UPLOAD_COLUMNS = CONTRACT_COLUMNS + ELIGIBILITY_COLUMNS

DEMO_APAAR = "123456784417"
DEMO_NAME = "Ravi Kumar Sharma"
DEMO_DOB = "2007-03-21"
DEMO_EMAIL = "ravi.sharma@example.demo"
DEMO_MOBILE = "9876504521"
DEMO_ROLL = "MHCET-2026-004512"
DEMO_ALLOTMENT = "MHCET-2026-R1-004512"

COUNSELLED_ROUTES = {"COUNSELLING", "TFW", "LATERAL"}
APAAR_DIGITS = re.compile(r"[0-9]{12}")
EMAIL_DOMAINS = ["example.com", "example.net", "example.org", "mail.example"]
CATEGORIES = (["GENERAL", "OBC", "SC", "ST", "EWS", "OTHER"], [40, 30, 12, 5, 10, 3])
YEAR3_SHARE = 0.35
# Admissions inside the window are dated up to LATE_DAYS before its last day; the final
# LATE_DAYS are kept for the planted overflow rows, so they are always the last admitted.
LATE_DAYS = 10


def has_usable_apaar(row: dict) -> bool:
    """True when the api keys the student on the APAAR (12 digits, consent LINKED)."""
    return row["consent_status"] == "LINKED" and bool(APAAR_DIGITS.fullmatch(row["apaar_id"]))


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def academic_year_label(start: int) -> str:
    return f"{start}-{(start + 1) % 100:02d}"


def academic_year_start(label: str) -> int:
    return int(label[:4])


def admission_window(rules: dict, cohort_start: int) -> tuple[dt.date, dt.date]:
    """1 July of the cohort's start year up to its cutoff in rules.yaml, else 30 September."""
    cutoff = rules.get("cutoff_dates", {}).get(academic_year_label(cohort_start))
    end = dt.date.fromisoformat(cutoff) if cutoff else dt.date(cohort_start, 9, 30)
    return dt.date(cohort_start, 7, 1), end


def share_of(value: int, share: float) -> int:
    """Whole seats for a share, rounded half up exactly as the api's seatpools module does."""
    seats = Decimal(str(value)) * Decimal(str(share))
    return max(0, int(seats.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


class Pools:
    """Seat-pool capacities for one approval, computed from rules.yaml."""

    def __init__(self, rules: dict, programme: dict, intake: int):
        sp = rules["seat_pools"]
        self.intake = intake
        self.nri = share_of(intake, sp["NRI"]["share"])
        self.tfw = share_of(intake, sp["TFW"]["share"])
        self.lateral = share_of(intake, sp["LATERAL"]["share"])
        self.regular = intake - self.nri
        share = 0.0
        for slab in sp["INTERNATIONAL"]["slabs"]:
            groups = slab["match"]["discipline_group"]
            groups = groups if isinstance(groups, list) else [groups]
            if programme["discipline"] in groups and programme["level"] in slab["match"]["level"]:
                share = slab["share"]
                break
        self.international = share_of(intake, share)
        # One third of the international seats are reserved for CIWG students (Indian
        # nationals), so a foreign national can take only the rest.
        self.ciwg = share_of(self.international, sp["INTERNATIONAL"]["ciwg_reserved_fraction"])

    def usable(self) -> dict[str, int]:
        """Seats a student who is not CIWG can take, per pool."""
        return {
            "REGULAR": self.regular,
            "NRI": self.nri,
            "TFW": self.tfw,
            "LATERAL": self.lateral,
            "INTERNATIONAL": self.international - self.ciwg,
        }


class World:
    """All generated state for one run."""

    def __init__(self, cfg: Config, seed: int):
        self.cfg = cfg
        self.seed = seed
        self.rng = random.Random(seed)
        Faker.seed(seed)
        self.fake = Faker("en_IN")
        self.fake.seed_instance(seed)
        self.names = NameGenerator(self.rng)
        self.institutions: list[dict] = []
        self.universities: list[dict] = []
        self.inst_by_id: dict[str, dict] = {}
        self.rows_by_inst: dict[str, list[dict]] = {}
        self.all_rows: list[dict] = []
        self.ground_truth: list[dict] = []
        self.used_apaar: set[str] = {DEMO_APAAR}
        self.used_mobile: set[str] = {DEMO_MOBILE}
        self.used_email: set[str] = {DEMO_EMAIL}
        self.used_passport: set[str] = set()
        self.counselling_seq: dict[str, int] = {}
        self.seq = 0
        self.y1_count: dict[tuple[str, str], int] = {}
        # Rows that exist only in update files (late refills); they take part in the
        # identity checks below and in the APAAR registry.
        self.update_only_rows: list[dict] = []
        # (aicte_id, programme_code) -> seat type of a planted EXCESS_ADMISSION or
        # QUOTA_BREACH in the first-year cohort; nothing else may be added to that cohort.
        self.seat_cases: dict[tuple[str, str], str] = {}
        # aicte_id -> the programme whose first-year REGULAR pool its update file refills.
        self.refill_programmes: dict[str, str] = {}
        # aicte_id -> rows of its update file, in file order (see updates.py).
        self.update_files: dict[str, list[dict]] = {}
        # graduates.jsonl records (graduates.py): people who are not on the roll.
        self.graduates: list[dict] = []
        self._name_keys: dict[tuple[str, str], str] = {}
        self.streets = [self.fake.street_name() for _ in range(1500)]
        self.localities = [self.fake.city() for _ in range(300)]
        self.scale = 1.0
        self.xlsx_written = True
        self.timings: dict[str, float] = {}

    # ------------------------------------------------------------------ ids

    def new_apaar(self) -> str:
        while True:
            candidate = "".join(self.rng.choices("0123456789", k=12))
            if candidate not in self.used_apaar and candidate[0] != "0":
                self.used_apaar.add(candidate)
                return candidate

    def new_mobile(self) -> str:
        while True:
            candidate = self.rng.choice("987") + "".join(self.rng.choices("0123456789", k=9))
            if candidate not in self.used_mobile:
                self.used_mobile.add(candidate)
                return candidate

    def new_email(self, name: str) -> str:
        tokens = [t.strip(".").lower() for t in name.split() if t.strip(".")]
        tokens = ["".join(ch for ch in t if ch.isalnum()) for t in tokens]
        tokens = [t for t in tokens if t]
        base = ".".join(tokens[:2]) if tokens else "student"
        while True:
            candidate = f"{base}{self.rng.randint(1, 9999)}@{self.rng.choice(EMAIL_DOMAINS)}"
            if candidate not in self.used_email:
                self.used_email.add(candidate)
                return candidate

    def new_passport(self) -> str:
        while True:
            candidate = self.rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") + "".join(
                self.rng.choices("0123456789", k=7)
            )
            if candidate not in self.used_passport:
                self.used_passport.add(candidate)
                return candidate

    def new_address(self, state_code: str, city: str | None = None) -> str:
        profile = geo.state_profile(state_code)
        city = city or self.rng.choice(profile["cities"])
        pin_prefix = profile["pin"]
        pin = pin_prefix + "".join(self.rng.choices("0123456789", k=6 - len(pin_prefix)))
        house = self.rng.choice(
            [
                f"H.No. {self.rng.randint(1, 99)}-{self.rng.randint(1, 999)}",
                f"Flat {self.rng.randint(1, 48)}, {self.rng.choice(self.localities)} Apartments",
                f"Plot {self.rng.randint(1, 400)}",
                f"{self.rng.randint(1, 250)}/{self.rng.randint(1, 20)}",
                f"House {self.rng.randint(1, 999)}",
            ]
        )
        street = self.rng.choice(self.streets)
        suffix = self.rng.choice([" Nagar", " Colony", " Road", ""])
        locality = self.rng.choice(self.localities) + suffix
        state_name = geo.STATE_BY_CODE[state_code]["name"]
        return f"{house}, {street}, {locality}, {city}, {state_name} - {pin}"

    def dob(self, admission_year: int, level: str, lateral: bool = False) -> str:
        if lateral:
            age = self.rng.randint(19, 21)
        elif level == "DIPLOMA":
            age = self.rng.choice([16, 17, 17, 18])
        elif level == "PG":
            age = self.rng.choice([21, 22, 22, 23, 24, 25])
        else:
            age = self.rng.choice([17, 18, 18, 18, 19, 20])
        year = admission_year - age
        month = self.rng.randint(1, 12)
        day = self.rng.randint(1, 28)
        return dt.date(year, month, day).isoformat()

    def next_counselling(self, exam: str, year: int, rnd: int) -> tuple[str, str]:
        key = f"{exam}-{year}"
        n = self.counselling_seq.get(key, 0) + 1
        self.counselling_seq[key] = n
        return f"{key}-{n:06d}", f"{exam}-{year}-R{rnd}-{n:06d}"

    # ----------------------------------------------------------------- rows

    def base_row(self, inst: dict, prog: dict, year_of_study: int, admission_year: int) -> dict:
        profile = geo.state_profile(inst["state_code"])
        group = self.names.pick_group(profile["groups"])
        gender = "M" if self.rng.random() < 0.62 else "F"
        name = self.names.indian_name(group, gender)
        self.seq += 1
        return {
            "apaar_id": "",
            "name": name,
            "dob": "",
            "gender": gender,
            "mobile": self.new_mobile(),
            "email": self.new_email(name),
            "address": self.new_address(inst["state_code"]),
            "nationality": "IN",
            "passport_no": "",
            "programme_code": prog["code"],
            "academic_year": self.cfg.academic_year,
            "year_of_study": year_of_study,
            "admission_route": "",
            "counselling_ref": "",
            "category": "",
            "consent_status": "",
            "status": "",
            "status_date": "",
            "admission_date": "",
            "tfw_income_certified": "",
            "nri_sponsored": "",
            "ciwg": "",
            "_inst": inst["aicte_permanent_id"],
            "_prog": prog,
            "_adm_year": admission_year,
            "_cohort_start": academic_year_start(self.cfg.academic_year) - (year_of_study - 1),
            "_late": False,
            "_dob_group": None,
            "_group": group,
            "_roll_no": "",
            "_round": 0,
            "_registry": "match",
            "_registry_name": None,
            "_credits": "normal",
            "_tags": [],
            "_seq": self.seq,
        }

    def give_consent(self, row: dict) -> None:
        r = self.rng.random()
        if r < 0.93:
            row["consent_status"] = "LINKED"
            row["apaar_id"] = self.new_apaar()
        elif r < 0.97:
            row["consent_status"] = "PENDING"
        else:
            row["consent_status"] = "REFUSED"

    def set_route(self, row: dict, inst: dict, route: str) -> None:
        row["admission_route"] = route
        if route in {"NRI", "INTERNATIONAL"}:
            row["category"] = "GENERAL"
        elif not row["category"]:
            row["category"] = self.rng.choices(CATEGORIES[0], weights=CATEGORIES[1], k=1)[0]
        if route in COUNSELLED_ROUTES:
            exam = geo.exam_for_state(inst["state_code"])
            rnd = self.rng.choices([1, 2, 3], weights=[60, 30, 10], k=1)[0]
            # The api looks allotments up by the cohort's start year (2025 for a year-2
            # lateral entrant of 2026-27), so the allotment is filed under that year.
            roll, allotment = self.next_counselling(exam, row["_cohort_start"], rnd)
            row["_roll_no"] = roll
            row["_round"] = rnd
            row["counselling_ref"] = allotment
        else:
            row["_roll_no"] = ""
            row["_round"] = 0
            row["counselling_ref"] = ""

    def make_international(self, row: dict) -> None:
        nationality = self.rng.choice(self.names.nationalities())
        row["nationality"] = nationality
        row["name"] = self.names.international_name(nationality, row["gender"])
        row["apaar_id"] = ""
        row["consent_status"] = "INTERNATIONAL"
        row["passport_no"] = self.new_passport()
        row["email"] = self.new_email(row["name"])
        row["category"] = "GENERAL"
        row["_group"] = "international"

    def add_row(self, row: dict) -> dict:
        self.rows_by_inst[row["_inst"]].append(row)
        self.all_rows.append(row)
        if row["year_of_study"] == 1:
            key = (row["_inst"], row["programme_code"])
            self.y1_count[key] = self.y1_count.get(key, 0) + 1
        return row

    def make_student(
        self, inst: dict, prog: dict, year_of_study: int, route: str, lateral: bool = False
    ) -> dict:
        """A new student's row, not yet placed in any file."""
        start = academic_year_start(self.cfg.academic_year)
        admission_year = start - (year_of_study - 1) if not lateral else start
        row = self.base_row(inst, prog, year_of_study, admission_year)
        row["dob"] = self.dob(admission_year, prog["level"], lateral=lateral)
        if route == "INTERNATIONAL":
            self.make_international(row)
        else:
            self.give_consent(row)
        self.set_route(row, inst, route)
        return row

    def new_student(
        self, inst: dict, prog: dict, year_of_study: int, route: str, lateral: bool = False
    ) -> dict:
        """A new student on the college's initial file."""
        return self.add_row(self.make_student(inst, prog, year_of_study, route, lateral))

    # --------------------------------------------------------------- cohorts

    def pools(self, prog: dict, intake: int) -> Pools:
        return Pools(self.cfg.rules, prog, intake)

    def route_mix(self, inst: dict, n: int, pools: Pools, allow_international: bool) -> list[str]:
        """Admission routes for a first-year cohort of n students, within every pool cap."""
        routes: list[str] = []
        govt = inst["type"] in {"GOVERNMENT", "GOVERNMENT_AIDED", "UNIVERSITY_DEPARTMENT"}
        nri = 0 if govt or self.rng.random() < 0.4 else self.rng.randint(1, pools.nri)
        tfw = self.rng.randint(0, pools.tfw) if self.rng.random() < 0.7 else 0
        intl = 0
        if allow_international and pools.international and self.rng.random() < 0.25:
            intl = self.rng.randint(1, min(3, pools.international))
        regular = n - nri - tfw - intl
        if regular > pools.regular:
            regular = pools.regular
        if regular < 0:
            regular = 0
        routes += ["NRI"] * nri + ["TFW"] * tfw + ["INTERNATIONAL"] * intl
        routes += self.regular_routes(inst, regular)
        return routes

    def regular_routes(self, inst: dict, n: int) -> list[str]:
        """Routes into the REGULAR pool, mixed as the college's type admits them."""
        if inst["type"] in {"GOVERNMENT", "GOVERNMENT_AIDED", "UNIVERSITY_DEPARTMENT"}:
            weights = {"COUNSELLING": 94, "MANAGEMENT": 0, "SPOT": 6}
        else:
            weights = {"COUNSELLING": 70, "MANAGEMENT": 24, "SPOT": 6}
        keys = list(weights)
        return self.rng.choices(keys, weights=[weights[k] for k in keys], k=n)

    def estimate_rows(self) -> float:
        """Expected row count at scale 1, used to size cohorts toward target_students."""
        start = academic_year_start(self.cfg.academic_year)
        lo, hi = self.cfg.size.year1_fill
        fill_mean = (lo + hi) / 2
        total = 0.0
        for inst in self.institutions:
            for prog in inst["programmes"]:
                if prog["mode"] != "PHYSICAL":
                    total += (approved_intake(prog, self.cfg.academic_year) or 0) * 0.5
                    continue
                for year_of_study in (1, 2, 3):
                    if year_of_study > prog["duration_years"]:
                        break
                    intake = approved_intake(prog, academic_year_label(start - year_of_study + 1))
                    if intake is None:
                        break
                    share = YEAR3_SHARE if year_of_study == 3 else 1.0
                    total += share * intake * fill_mean * (0.95 ** (year_of_study - 1))
                    if year_of_study == 2 and self.takes_lateral(prog):
                        total += 0.6 * (1 + self.pools(prog, intake).lateral) / 2
        return total

    @staticmethod
    def takes_lateral(prog: dict) -> bool:
        return prog["level"] == "UG" and prog["discipline"] == "ENGINEERING"

    def generate_cohorts(self, inst: dict, prog: dict) -> None:
        if prog["mode"] != "PHYSICAL":
            self.generate_odl_cohort(inst, prog)
            return
        start = academic_year_start(self.cfg.academic_year)
        lo, hi = self.cfg.size.year1_fill
        fill = self.rng.uniform(lo, hi) * self.scale
        allow_intl = inst["type"] in {"PRIVATE_SELF_FINANCED", "DEEMED"}
        max_year = prog["duration_years"]
        for year_of_study in (1, 2, 3):
            if year_of_study > max_year:
                break
            if year_of_study == 3 and self.rng.random() > YEAR3_SHARE:
                break
            label = academic_year_label(start - (year_of_study - 1))
            intake = approved_intake(prog, label)
            if intake is None:
                break
            pools = self.pools(prog, intake)
            cohort_fill = fill * (0.95 ** (year_of_study - 1))
            n = min(intake, round_half_up(intake * cohort_fill))
            routes = self.route_mix(inst, n, pools, allow_intl)
            for route in routes:
                self.new_student(inst, prog, year_of_study, route)
            if year_of_study == 2 and self.takes_lateral(prog) and self.rng.random() < 0.6:
                lateral = max(1, round_half_up(self.rng.randint(1, pools.lateral) * self.scale))
                for _ in range(lateral):
                    self.new_student(inst, prog, 2, "LATERAL", lateral=True)

    def generate_odl_cohort(self, inst: dict, prog: dict) -> None:
        intake = approved_intake(prog, self.cfg.academic_year)
        n = round_half_up(intake * self.rng.uniform(0.3, 0.7) * self.scale)
        for _ in range(max(n, 3)):
            self.new_student(inst, prog, 1, "MANAGEMENT")

    def generate_demo_cse(self, inst: dict, prog: dict) -> None:
        """ABC CSE 2026-27: exactly 120 first-years inside every pool, the demo student first."""
        start = academic_year_start(self.cfg.academic_year)
        pools = self.pools(prog, 120)
        ravi = self.base_row(inst, prog, 1, start)
        ravi.update(
            {
                "apaar_id": DEMO_APAAR,
                "name": DEMO_NAME,
                "dob": DEMO_DOB,
                "gender": "M",
                "mobile": DEMO_MOBILE,
                "email": DEMO_EMAIL,
                "address": self.new_address("MH", "Pune"),
                "admission_route": "COUNSELLING",
                "counselling_ref": DEMO_ALLOTMENT,
                "category": "GENERAL",
                "consent_status": "LINKED",
                "_group": "hindi",
                "_roll_no": DEMO_ROLL,
                "_round": 1,
                "_tags": ["DEMO_STUDENT"],
            }
        )
        self.add_row(ravi)
        routes = ["NRI"] * pools.nri + ["COUNSELLING"] * 85 + ["MANAGEMENT"] * 24 + ["SPOT"] * 4
        assert len(routes) + 1 == 120
        for route in routes:
            self.new_student(inst, prog, 1, route)
        # Second and third years as usual.
        for year_of_study, n in ((2, 112), (3, 104)):
            label = academic_year_label(start - (year_of_study - 1))
            pools = self.pools(prog, approved_intake(prog, label))
            for route in self.route_mix(inst, n, pools, True):
                self.new_student(inst, prog, year_of_study, route)
            if year_of_study == 2:
                for _ in range(8):
                    self.new_student(inst, prog, 2, "LATERAL", lateral=True)

    # ---------------------------------------------------------------- dates

    def random_date(self, lo: dt.date, hi: dt.date) -> dt.date:
        return lo + dt.timedelta(days=self.rng.randint(0, (hi - lo).days))

    def assign_admission_dates(self) -> None:
        """Every initial row gets a date in its cohort's admission window. Planted overflow
        rows (`_late`) take the window's last days so the ledger seats everyone else first."""
        rules = self.cfg.rules
        for row in self.all_rows:
            start, end = admission_window(rules, row["_cohort_start"])
            last_normal = end - dt.timedelta(days=LATE_DAYS)
            if row["_late"]:
                day = self.random_date(last_normal + dt.timedelta(days=1), end)
            else:
                day = self.random_date(start, last_normal)
            row["admission_date"] = day.isoformat()

    # -------------------------------------------------------------- identity

    @staticmethod
    def unit_of(row: dict) -> int:
        """Rows planted to describe one student (or a renamed copy) share a DOB group."""
        return row["_dob_group"] or row["_seq"]

    def identity_conflicts(self) -> list[list[int]]:
        """Groups of units whose dates of birth make a lookup or a duplicate rule misfire.

        - Duplicate rule A compares a student without a usable APAAR with every other
          student of the college sharing its name_key (DOB, first initial, metaphone of
          the surname). Outside planted pairs no such neighbour may exist.
        - mockgov finds a counselling allotment by name and DOB within state, year,
          programme and college; one allotment per DOB there keeps the lookup exact.
        """
        blocks: dict[tuple, dict[int, bool]] = {}
        allotments: dict[tuple, set[int]] = {}
        keys = self._name_keys
        for row in self.all_rows + self.update_only_rows:
            unit = self.unit_of(row)
            pair = (row["name"], row["dob"])
            if pair not in keys:
                keys[pair] = name_key(*pair)
            key = (row["_inst"], keys[pair])
            units = blocks.setdefault(key, {})
            units[unit] = units.get(unit, False) or not has_usable_apaar(row)
            if row["_roll_no"]:
                akey = (row["_inst"], row["programme_code"], row["_cohort_start"], row["dob"])
                allotments.setdefault(akey, set()).add(unit)
        out = [sorted(u) for u in blocks.values() if len(u) > 1 and any(u.values())]
        out += [sorted(u) for u in allotments.values() if len(u) > 1]
        return out

    def resolve_identity_conflicts(self, max_passes: int = 20) -> int:
        """Re-draw the DOB of every unit but one in each conflict until none is left. The
        demo student's group never moves; planted groups move together."""
        members: dict[int, list[dict]] = {}
        for row in self.all_rows + self.update_only_rows:
            members.setdefault(self.unit_of(row), []).append(row)

        def rank(unit: int) -> tuple:
            rows = members[unit]
            fixed = any("DEMO_STUDENT" in r["_tags"] for r in rows)
            return (not fixed, rows[0]["_dob_group"] is None, unit)

        moved = 0
        for _ in range(max_passes):
            conflicts = self.identity_conflicts()
            if not conflicts:
                return moved
            done: set[int] = set()
            for group in conflicts:
                keep, *rest = sorted(group, key=rank)
                for unit in rest:
                    if unit in done or rank(unit)[0] is False:
                        continue
                    done.add(unit)
                    moved += 1
                    old = dt.date.fromisoformat(members[unit][0]["dob"])
                    new = old
                    while new == old:
                        new = dt.date(old.year, self.rng.randint(1, 12), self.rng.randint(1, 28))
                    for row in members[unit]:
                        row["dob"] = new.isoformat()
        raise RuntimeError("could not separate look-alike students; try another seed")

    def finalise(self) -> None:
        self.resolve_identity_conflicts()
        self.assign_admission_dates()

    @contextmanager
    def using_rng(self, rng: random.Random) -> Iterator[None]:
        """Draw from `rng` instead of the run's stream, so steps added after the original
        generation leave every value the run's stream produces unchanged."""
        saved = self.rng, self.names.rng
        self.rng = self.names.rng = rng
        try:
            yield
        finally:
            self.rng, self.names.rng = saved

    def settle(self, rows: list[dict], rng: random.Random) -> None:
        """Rows added after finalise(): re-draw the date of birth of any that looks like an
        existing student (only new rows move, they rank last) and date their admissions."""
        if not rows:
            return
        with self.using_rng(rng):
            self.resolve_identity_conflicts()
            for row in rows:
                start, end = admission_window(self.cfg.rules, row["_cohort_start"])
                last_normal = end - dt.timedelta(days=LATE_DAYS)
                row["admission_date"] = self.random_date(start, last_normal).isoformat()

    def leaving_rows(self) -> set[int]:
        """ids of the initial rows an update file withdraws or transfers."""
        return {
            id(u["_initial"])
            for rows in self.update_files.values()
            for u in rows
            if u.get("_initial") is not None
        }

    # --------------------------------------------------------------- driver

    def build_institutions(self) -> None:
        self.universities = geo.universities()
        self.institutions = InstitutionBuilder(self.rng, self.cfg).build()
        assign_autonomy(self.institutions, self.seed, self.cfg.autonomous_share)
        for inst in self.institutions:
            self.inst_by_id[inst["aicte_permanent_id"]] = inst
            self.rows_by_inst[inst["aicte_permanent_id"]] = []

    def build_students(self) -> None:
        estimate = self.estimate_rows()
        self.scale = min(1.0, self.cfg.size.target_students / estimate) if estimate else 1.0
        for inst in self.institutions:
            for prog in inst["programmes"]:
                if (
                    self.cfg.scenarios
                    and inst["aicte_permanent_id"] == "1-ABC-0001"
                    and prog["code"] == "CSE"
                ):
                    self.generate_demo_cse(inst, prog)
                else:
                    self.generate_cohorts(inst, prog)

    # ------------------------------------------------------------- helpers

    def programme(self, aicte_id: str, code: str) -> dict:
        inst = self.inst_by_id[aicte_id]
        return next(p for p in inst["programmes"] if p["code"] == code)

    # ---------------------------------------------------------------- seats

    def route_pool(self, route: str) -> str:
        return self.cfg.rules["admission_routes"][route]["pool"]

    def cohort_pools(self, prog: dict, year_of_study: int) -> Pools | None:
        """Pools of the approval a year-of-study cohort was admitted against, if any."""
        start = academic_year_start(self.cfg.academic_year) - (year_of_study - 1)
        intake = approved_intake(prog, academic_year_label(start))
        return None if intake is None else self.pools(prog, intake)

    def cohort_rows(self, aicte_id: str, code: str, year_of_study: int) -> list[dict]:
        return [
            r for r in self.rows_by_inst[aicte_id]
            if r["programme_code"] == code and r["year_of_study"] == year_of_study
        ]  # fmt: skip

    def pool_counts(self, aicte_id: str, code: str, year_of_study: int) -> Counter:
        return Counter(
            self.route_pool(r["admission_route"])
            for r in self.cohort_rows(aicte_id, code, year_of_study)
        )

    def room(self, aicte_id: str, prog: dict, year_of_study: int, route: str) -> int:
        """Free seats a new non-CIWG admission by `route` would find in its cohort pool.
        A first-year cohort holding a planted seat case has none to give."""
        if year_of_study > prog["duration_years"]:
            return 0
        if year_of_study == 1 and (aicte_id, prog["code"]) in self.seat_cases:
            return 0
        pools = self.cohort_pools(prog, year_of_study)
        if pools is None:
            return 0
        pool = self.route_pool(route)
        return pools.usable()[pool] - self.pool_counts(aicte_id, prog["code"], year_of_study)[pool]

    def pick_row(self, predicate, attempts: int = 20000) -> dict | None:
        n = len(self.all_rows)
        for _ in range(attempts):
            row = self.all_rows[self.rng.randrange(n)]
            if not row["_tags"] and predicate(row):
                return row
        return None

    def pick_rows(self, k: int, predicate, attempts: int = 20000) -> list[dict]:
        out: list[dict] = []
        seen: set[int] = set()
        n = len(self.all_rows)
        for _ in range(attempts):
            if len(out) == k:
                break
            idx = self.rng.randrange(n)
            if idx in seen:
                continue
            row = self.all_rows[idx]
            if not row["_tags"] and predicate(row):
                seen.add(idx)
                out.append(row)
        return out

    # ----------------------------------------------------------- registries

    def registry_records(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out = []
        for row in self.all_rows + self.update_only_rows:
            apaar = row["apaar_id"]
            if not apaar or row["_registry"] == "absent" or apaar in seen:
                continue
            seen.add(apaar)
            name = row["_registry_name"] if row["_registry"] == "mismatch" else row["name"]
            out.append(
                {"apaar_id": apaar, "name": name, "dob": row["dob"], "gender": row["gender"]}
            )
        return out

    def counselling_records(self) -> list[dict[str, Any]]:
        out = []
        for row in self.all_rows:
            if not row["_roll_no"]:
                continue
            inst = self.inst_by_id[row["_inst"]]
            out.append(
                {
                    "state": inst["state_code"],
                    "year": row["_cohort_start"],
                    "name": row["name"],
                    "dob": row["dob"],
                    "roll_no": row["_roll_no"],
                    "programme": row["programme_code"],
                    "institution_aicte_id": row["_inst"],
                    "round": row["_round"],
                    "category": row["category"],
                    "allotment_ref": row["counselling_ref"],
                }
            )
        return out

    def abc_records(self) -> list[dict[str, Any]]:
        """Credits of every year a student completed, each naming its issuer: the college's
        affiliating university, or the college itself when it is autonomous."""
        out = []
        seen: set[tuple[str, str, int]] = set()
        start = academic_year_start(self.cfg.academic_year)
        names = {u["code"]: u["name"] for u in self.universities}
        issuers = {aid: credit_issuer(inst, names) for aid, inst in self.inst_by_id.items()}
        for row in self.all_rows:
            apaar = row["apaar_id"]
            if not apaar or row["_registry"] == "absent" or row["year_of_study"] < 2:
                continue
            if row["_credits"] == "none":
                continue
            years_done = row["year_of_study"] - 1
            for k in range(1, years_done + 1):
                year_start = start - years_done + (k - 1)
                label = academic_year_label(year_start)
                for sem_in_year in (1, 2):
                    sem = (k - 1) * 2 + sem_in_year
                    key = (apaar, label, sem)
                    if key in seen:
                        continue
                    seen.add(key)
                    if row["_credits"] == "zero":
                        credits, result = 0, "FAIL"
                    elif self.rng.random() < 0.05:
                        credits, result = self.rng.randint(6, 14), "FAIL"
                    else:
                        credits, result = self.rng.randint(18, 26), "PASS"
                    uploaded = (
                        f"{year_start + 1}-01-20T00:00:00Z"
                        if sem_in_year == 1
                        else f"{year_start + 1}-06-30T00:00:00Z"
                    )
                    out.append(
                        {
                            "apaar_id": apaar,
                            "academic_year": label,
                            "sem": sem,
                            "credits": credits,
                            "uploaded_at": uploaded,
                            "result": result,
                            "issuer": issuers[row["_inst"]],
                        }
                    )
        return out

    def sii_records(self) -> list[dict[str, Any]]:
        out = []
        seen: set[str] = set()
        for row in self.all_rows:
            if not row["passport_no"] or row["passport_no"] in seen:
                continue
            seen.add(row["passport_no"])
            out.append(
                {
                    "passport_no": row["passport_no"],
                    "name": row["name"],
                    "nationality": row["nationality"],
                    "institution_aicte_id": row["_inst"],
                    "programme": row["programme_code"],
                    "academic_year": academic_year_label(row["_adm_year"]),
                }
            )
        return out
