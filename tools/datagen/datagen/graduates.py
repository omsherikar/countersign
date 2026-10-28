"""graduates.jsonl: students who finished in the year before the roll, for the degree proof.

Final-year students of 2025-26 (year of study = the programme's duration) at colleges
affiliated to the demo university (MSTU, the coe@univ.demo login), ABC College of
Engineering among them, and at a few other universities. They are new people: no graduate is
on the 2026-27 roll, and their APAAR ids, mobiles and email addresses are used nowhere else.
Most are LINKED with an APAAR the mockgov registry holds; a few have only a provisional id.

A random stream of its own, seeded from the run's seed, leaves every other file unchanged.
"""

from __future__ import annotations

import datetime as dt
import random
from collections import Counter
from typing import Any

from . import geo
from .institutions import ABC_ID, approved_intake
from .names import NameGenerator
from .students import CATEGORIES, EMAIL_DOMAINS, World, academic_year_start, admission_window

GRADUATE_FIELDS = [
    "institution_aicte_id", "programme_code", "academic_year", "year_of_study", "name", "dob",
    "gender", "apaar_id", "consent_status", "provisional_id", "email", "mobile", "nationality",
    "year_of_award", "admission_route", "category", "admission_date", "status_date",
]  # fmt: skip
BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
AGE_AT_ADMISSION = {"UG": (17, 19), "PG": (21, 25), "DIPLOMA": (16, 18)}
GOVERNMENT_TYPES = {"GOVERNMENT", "GOVERNMENT_AIDED", "UNIVERSITY_DEPARTMENT"}
ABC_CSE = 4  # ABC graduates of B.Tech CSE, all LINKED, for the degree proof demo


class GraduateBuilder:
    def __init__(self, world: World):
        self.w = world
        self.cfg = world.cfg.graduates
        self.rng = random.Random(f"graduates:{world.seed}")
        self.names = NameGenerator(self.rng)
        self.provisional_ids: set[str] = set()

    # ---------------------------------------------------------------- places

    def programmes(self, inst: dict) -> list[dict]:
        """Programmes that had a final-year cohort in the graduates' year."""
        return [
            p for p in inst["programmes"]
            if p["mode"] == "PHYSICAL" and approved_intake(p, self.cfg.academic_year) is not None
        ]  # fmt: skip

    def colleges(self, university: str) -> list[dict]:
        return [
            i for i in self.w.institutions
            if i["university_code"] == university and self.programmes(i)
        ]  # fmt: skip

    def other_universities(self) -> list[str]:
        """The universities with the most affiliated colleges, the demo one excluded."""
        counts = Counter(
            i["university_code"] for i in self.w.institutions
            if i["university_code"] and i["university_code"] != self.cfg.university
            and self.programmes(i)
        )  # fmt: skip
        ranked = sorted(counts, key=lambda code: (-counts[code], code))
        return ranked[: self.cfg.other_universities]

    def places(self) -> list[dict]:
        """One college per graduate: ABC first, then the demo university's other colleges,
        then the other universities in turn."""
        n = self.cfg.count
        abc = self.w.inst_by_id[ABC_ID]
        neighbours = [i for i in self.colleges(self.cfg.university) if i is not abc]
        others = self.other_universities()
        abc_n = min(self.cfg.abc, n)
        home = n if not others else max(abc_n, round(n * self.cfg.university_share))
        if not neighbours:
            abc_n = home
        out = [abc] * abc_n
        out += [self.rng.choice(neighbours) for _ in range(home - abc_n)]
        for k in range(n - home):
            out.append(self.rng.choice(self.colleges(others[k % len(others)])))
        return out

    # ------------------------------------------------------------------- ids

    def new_apaar(self) -> str:
        while True:
            candidate = self.rng.choice("123456789") + "".join(self.rng.choices("0123456789", k=11))
            if candidate not in self.w.used_apaar:
                self.w.used_apaar.add(candidate)
                return candidate

    def new_provisional_id(self) -> str:
        while True:
            candidate = "PRV-" + "".join(self.rng.choices(BASE32, k=8))
            if candidate not in self.provisional_ids:
                self.provisional_ids.add(candidate)
                return candidate

    def new_mobile(self) -> str:
        while True:
            candidate = self.rng.choice("987") + "".join(self.rng.choices("0123456789", k=9))
            if candidate not in self.w.used_mobile:
                self.w.used_mobile.add(candidate)
                return candidate

    def new_email(self, name: str) -> str:
        tokens = ["".join(ch for ch in t.lower() if ch.isalnum()) for t in name.split()]
        base = ".".join(t for t in tokens if t)[:40] or "graduate"
        base = ".".join(base.split(".")[:2])
        while True:
            candidate = f"{base}{self.rng.randint(1, 9999)}@{self.rng.choice(EMAIL_DOMAINS)}"
            if candidate not in self.w.used_email:
                self.w.used_email.add(candidate)
                return candidate

    def random_date(self, lo: dt.date, hi: dt.date) -> dt.date:
        return lo + dt.timedelta(days=self.rng.randint(0, (hi - lo).days))

    # -------------------------------------------------------------- graduate

    def graduate(self, inst: dict, code: str | None = None) -> dict[str, Any]:
        """A final-year student of a programme of `inst`, picked by approved intake."""
        progs = self.programmes(inst)
        if code is not None:
            prog = next(p for p in progs if p["code"] == code)
        else:
            weights = [approved_intake(p, self.cfg.academic_year) for p in progs]
            prog = self.rng.choices(progs, weights=weights, k=1)[0]
        year_of_study = prog["duration_years"]
        start = academic_year_start(self.cfg.academic_year) - (year_of_study - 1)
        group = self.names.pick_group(geo.state_profile(inst["state_code"])["groups"])
        gender = "M" if self.rng.random() < 0.6 else "F"
        name = self.names.indian_name(group, gender)
        lo, hi = AGE_AT_ADMISSION.get(prog["level"], AGE_AT_ADMISSION["UG"])
        dob = dt.date(
            start - self.rng.randint(lo, hi), self.rng.randint(1, 12), self.rng.randint(1, 28)
        )
        window = admission_window(self.w.cfg.rules, start)
        if inst["type"] in GOVERNMENT_TYPES:
            route = "COUNSELLING"
        else:
            route = self.rng.choices(["COUNSELLING", "MANAGEMENT"], weights=[75, 25], k=1)[0]
        status_from, status_to = (dt.date.fromisoformat(d) for d in self.cfg.status_dates)
        return {
            "institution_aicte_id": inst["aicte_permanent_id"],
            "programme_code": prog["code"],
            "academic_year": self.cfg.academic_year,
            "year_of_study": year_of_study,
            "name": name,
            "dob": dob.isoformat(),
            "gender": gender,
            "apaar_id": self.new_apaar(),
            "consent_status": "LINKED",
            "provisional_id": None,
            "email": self.new_email(name),
            "mobile": self.new_mobile(),
            "nationality": "IN",
            "year_of_award": self.cfg.year_of_award,
            "admission_route": route,
            "category": self.rng.choices(CATEGORIES[0], weights=CATEGORIES[1], k=1)[0],
            "admission_date": self.random_date(*window).isoformat(),
            "status_date": self.random_date(status_from, status_to).isoformat(),
        }

    def unlink(self, grad: dict) -> None:
        """No APAAR: consent pending or refused, a provisional id instead."""
        self.w.used_apaar.discard(grad["apaar_id"])
        grad["apaar_id"] = None
        grad["consent_status"] = self.rng.choice(["PENDING", "PENDING", "REFUSED"])
        grad["provisional_id"] = self.new_provisional_id()

    # ---------------------------------------------------------------- driver

    def build(self) -> list[dict]:
        order = {i["aicte_permanent_id"]: n for n, i in enumerate(self.w.institutions)}
        grads = []
        abc_cse = 0  # ABC's first graduates take CSE, the demo programme
        for inst in self.places():
            code = None
            if inst["aicte_permanent_id"] == ABC_ID and abc_cse < ABC_CSE:
                code, abc_cse = "CSE", abc_cse + 1
            grads.append(self.graduate(inst, code))
        # A few have no APAAR: one at ABC outside CSE, the rest at other colleges.
        k = self.rng.randint(*self.cfg.provisional)
        at_abc = [
            g for g in grads
            if g["institution_aicte_id"] == ABC_ID and g["programme_code"] != "CSE"
        ]  # fmt: skip
        picked = self.rng.sample(at_abc, 1) if at_abc else []
        rest = [g for g in grads if g["institution_aicte_id"] != ABC_ID]
        picked += self.rng.sample(rest, min(len(rest), k - len(picked)))
        for grad in picked:
            self.unlink(grad)
        grads.sort(
            key=lambda g: (
                order[g["institution_aicte_id"]], g["programme_code"], g["name"], g["dob"]
            )
        )  # fmt: skip
        self.w.graduates = grads
        return grads


def records(graduates: list[dict]) -> list[dict]:
    """graduates.jsonl lines, fields in contract order."""
    return [{key: g[key] for key in GRADUATE_FIELDS} for g in graduates]


def registry_records(graduates: list[dict]) -> list[dict]:
    """The mockgov APAAR registry entries of the LINKED graduates."""
    return [
        {"apaar_id": g["apaar_id"], "name": g["name"], "dob": g["dob"], "gender": g["gender"]}
        for g in graduates
        if g["apaar_id"]
    ]
