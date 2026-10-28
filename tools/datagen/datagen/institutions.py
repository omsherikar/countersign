"""Institutions, programmes and approvals (institutions.json)."""

from __future__ import annotations

import random
import zlib
from typing import Any

from . import geo
from .config import Config, load_data

ACADEMIC_YEARS = ("2024-25", "2025-26", "2026-27")

# code -> (name, level, discipline, duration_years, mode)
PROGRAMMES: dict[str, tuple[str, str, str, int, str]] = {
    "CSE": ("B.Tech Computer Science and Engineering", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "IT": ("B.Tech Information Technology", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "ECE": ("B.Tech Electronics and Communication Engineering", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "EEE": ("B.Tech Electrical and Electronics Engineering", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "EE": ("B.Tech Electrical Engineering", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "MECH": ("B.Tech Mechanical Engineering", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "CIVIL": ("B.Tech Civil Engineering", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "AIML": ("B.Tech CSE (Artificial Intelligence and Machine Learning)", "UG", "ENGINEERING", 4,
             "PHYSICAL"),
    "AIDS": ("B.Tech Artificial Intelligence and Data Science", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "ETC": ("B.Tech Electronics and Telecommunication Engineering", "UG", "ENGINEERING", 4,
            "PHYSICAL"),
    "CHEM": ("B.Tech Chemical Engineering", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "BIOTECH": ("B.Tech Biotechnology", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "AUTO": ("B.Tech Automobile Engineering", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "AERO": ("B.Tech Aeronautical Engineering", "UG", "ENGINEERING", 4, "PHYSICAL"),
    "INSTRU": ("B.Tech Instrumentation and Control Engineering", "UG", "ENGINEERING", 4,
               "PHYSICAL"),
    "MTECH-CSE": ("M.Tech Computer Science and Engineering", "PG", "ENGINEERING", 2, "PHYSICAL"),
    "MTECH-VLSI": ("M.Tech VLSI Design", "PG", "ENGINEERING", 2, "PHYSICAL"),
    "MTECH-STR": ("M.Tech Structural Engineering", "PG", "ENGINEERING", 2, "PHYSICAL"),
    "MBA": ("Master of Business Administration", "PG", "MANAGEMENT", 2, "PHYSICAL"),
    "MCA": ("Master of Computer Applications", "PG", "COMPUTER_APPLICATIONS", 2, "PHYSICAL"),
    "BCA": ("Bachelor of Computer Applications", "UG", "COMPUTER_APPLICATIONS", 3, "PHYSICAL"),
    "BPHARM": ("Bachelor of Pharmacy", "UG", "PHARMACY", 4, "PHYSICAL"),
    "BARCH": ("Bachelor of Architecture", "UG", "ARCHITECTURE", 5, "PHYSICAL"),
    "D-CIVIL": ("Diploma in Civil Engineering", "DIPLOMA", "ENGINEERING", 3, "PHYSICAL"),
    "D-MECH": ("Diploma in Mechanical Engineering", "DIPLOMA", "ENGINEERING", 3, "PHYSICAL"),
    "D-CSE": ("Diploma in Computer Engineering", "DIPLOMA", "ENGINEERING", 3, "PHYSICAL"),
    "D-EEE": ("Diploma in Electrical Engineering", "DIPLOMA", "ENGINEERING", 3, "PHYSICAL"),
    "BCA-ODL": ("Bachelor of Computer Applications (Open and Distance Learning)", "UG",
                "COMPUTER_APPLICATIONS", 3, "ODL"),
    "MCA-ONLINE": ("Master of Computer Applications (Online)", "PG",
                   "COMPUTER_APPLICATIONS", 2, "ONLINE"),
}  # fmt: skip

_UG_ENGG = ["CSE", "IT", "ECE", "EEE", "EE", "MECH", "CIVIL", "AIML", "AIDS", "ETC", "CHEM",
            "BIOTECH", "AUTO", "AERO", "INSTRU"]  # fmt: skip
_UG_ENGG_WEIGHTS = [20, 10, 14, 8, 5, 12, 11, 8, 6, 5, 3, 3, 3, 2, 2]
_EXTRAS = ["MBA", "MCA", "BCA", "MTECH-CSE", "MTECH-VLSI", "MTECH-STR", "BPHARM", "BARCH",
           "D-CIVIL", "D-MECH", "D-CSE", "D-EEE"]  # fmt: skip
_EXTRA_WEIGHTS = [12, 8, 5, 5, 3, 3, 4, 2, 4, 4, 4, 2]

INTAKE_LADDER = [30, 60, 90, 120, 180, 240]
_INTAKES_UG = ([30, 60, 90, 120, 180, 240], [3, 40, 10, 30, 10, 7])
_INTAKES_OTHER = ([30, 60, 90, 120], [30, 50, 10, 10])

INSTITUTION_TYPES = (
    ["PRIVATE_SELF_FINANCED", "GOVERNMENT", "GOVERNMENT_AIDED", "UNIVERSITY_DEPARTMENT", "DEEMED"],
    [66, 12, 8, 7, 7],
)

ABC_ID = "1-ABC-0001"
XYZ_ID = "1-XYZ-0002"

# Approval versions (institutions.json `approvals[].versions`, API_CONTRACT A4.25). An
# approval is version 1 ("AICTE EoA <year>", effective 15 March) unless it was revised: then
# version 1 holds the earlier intake and version 2 ("..., revised", effective 20 May, before
# admissions open) the generated one, which every cohort was admitted against. ABC College
# CSE 2026-27 goes from 90 to 120, so its 132 first-years still exceed it; about one approval
# in ten elsewhere is revised up one step of the intake ladder.
V1_DAY, V2_DAY = "03-15", "05-20"
ABC_CSE_V1 = 90
REVISED_ONE_IN = 10

ABC_PROGRAMMES = [("CSE", 120), ("IT", 60), ("ECE", 120), ("MECH", 120), ("CIVIL", 60), ("MBA", 60)]
XYZ_PROGRAMMES = [("CSE", 120), ("ECE", 90), ("EEE", 60), ("MECH", 60), ("CIVIL", 60), ("MCA", 60)]


def programme_record(code: str, approvals: list[dict[str, Any]], shift: str = "FIRST") -> dict:
    name, level, discipline, duration, mode = PROGRAMMES[code]
    return {
        "code": code,
        "name": name,
        "level": level,
        "discipline": discipline,
        "shift": shift,
        "mode": mode,
        "duration_years": duration,
        "approvals": approvals,
    }


def approvals_for(intake: int, years: tuple[str, ...] = ACADEMIC_YEARS) -> list[dict[str, Any]]:
    return [{"academic_year": y, "approved_intake": intake} for y in years]


class InstitutionBuilder:
    def __init__(self, rng: random.Random, cfg: Config):
        self.rng = rng
        self.cfg = cfg
        self.colleges = load_data("colleges.json")
        self.used_names: set[str] = set()
        self.used_ids: set[str] = set()
        self.used_slugs: set[str] = set()
        self.universities = geo.universities()
        self.unis_by_state: dict[str, list[str]] = {}
        for u in self.universities:
            self.unis_by_state.setdefault(u["state_code"], []).append(u["code"])

    # -- ids and names ----------------------------------------------------

    def new_id(self) -> str:
        while True:
            candidate = "1-" + "".join(self.rng.choices("0123456789", k=10))
            if candidate not in self.used_ids:
                self.used_ids.add(candidate)
                return candidate

    def slug_for(self, name: str, aicte_id: str) -> str:
        if aicte_id == ABC_ID:
            base = "abc"
        elif aicte_id == XYZ_ID:
            base = "xyz"
        else:
            words = [w for w in name.replace(",", " ").split() if w[0].isalpha()]
            base = "".join(w[0].lower() for w in words)[:8] or "inst"
        slug = base
        n = 2
        while slug in self.used_slugs:
            slug = f"{base}{n}"
            n += 1
        self.used_slugs.add(slug)
        return slug

    def college_name(self, itype: str, state_code: str, city: str, group: str) -> str:
        patrons = self.colleges["patrons"]
        suffixes = self.colleges["suffixes"]
        for _ in range(50):
            pool = patrons.get(group, []) + patrons["common"]
            patron = self.rng.choice(pool)
            if itype == "GOVERNMENT":
                name = f"{self.rng.choice(suffixes['government'])}, {city}"
            elif itype == "GOVERNMENT_AIDED":
                name = f"{patron} {self.rng.choice(suffixes['aided'])}"
            elif itype == "UNIVERSITY_DEPARTMENT":
                name = f"{self.rng.choice(suffixes['university_dept'])}, {city}"
            elif itype == "DEEMED":
                name = f"{patron} {self.rng.choice(suffixes['deemed'])}"
            else:
                name = f"{patron} {self.rng.choice(suffixes['engineering'])}"
                if self.rng.random() < 0.3:
                    name = f"{name}, {city}"
            if name not in self.used_names:
                self.used_names.add(name)
                return name
        raise RuntimeError("ran out of college names")

    # -- programmes -------------------------------------------------------

    def intake(self, code: str) -> int:
        level = PROGRAMMES[code][1]
        values, weights = _INTAKES_UG if level == "UG" else _INTAKES_OTHER
        return self.rng.choices(values, weights=weights, k=1)[0]

    def random_programmes(self, itype: str, force_odl: bool = False) -> list[dict]:
        lo, hi = self.cfg.size.programmes_per_institution
        count = self.rng.randint(lo, hi)
        engg_count = max(1, count - (1 if count >= 3 and self.rng.random() < 0.6 else 0))
        codes: list[str] = []
        while len(codes) < engg_count:
            code = self.rng.choices(_UG_ENGG, weights=_UG_ENGG_WEIGHTS, k=1)[0]
            if code not in codes:
                codes.append(code)
        while len(codes) < count:
            code = self.rng.choices(_EXTRAS, weights=_EXTRA_WEIGHTS, k=1)[0]
            if code not in codes:
                codes.append(code)
        if force_odl or (itype in {"UNIVERSITY_DEPARTMENT", "DEEMED"} and self.rng.random() < 0.5):
            codes.append(self.rng.choice(["BCA-ODL", "MCA-ONLINE"]))
        out = []
        for code in codes:
            intake = self.intake(code)
            r = self.rng.random()
            if r < 0.10:
                approvals = approvals_for(intake, ("2026-27",))
            elif r < 0.30 and intake < INTAKE_LADDER[-1]:
                raised = INTAKE_LADDER[INTAKE_LADDER.index(intake) + 1]
                approvals = approvals_for(intake, ("2024-25", "2025-26"))
                approvals.append({"academic_year": "2026-27", "approved_intake": raised})
            else:
                approvals = approvals_for(intake)
            shift = "SECOND" if code.startswith("D-") and self.rng.random() < 0.3 else "FIRST"
            out.append(programme_record(code, approvals, shift))
        return out

    # -- institutions -----------------------------------------------------

    def fixed_institution(
        self,
        aicte_id: str,
        name: str,
        itype: str,
        state: str,
        university: str,
        city: str,
        year: int,
        programmes: list[tuple[str, int]],
    ) -> dict:
        self.used_ids.add(aicte_id)
        self.used_names.add(name)
        return {
            "aicte_permanent_id": aicte_id,
            "name": name,
            "type": itype,
            "state_code": state,
            "university_code": university,
            "address_city": city,
            "established_year": year,
            "programmes": [programme_record(c, approvals_for(i)) for c, i in programmes],
            "_region": geo.REGION_OF_STATE[state],
            "_slug": self.slug_for(name, aicte_id),
        }

    def random_institution(
        self, state: str, itype: str | None = None, force_odl: bool = False
    ) -> dict:
        profile = geo.state_profile(state)
        types, type_weights = INSTITUTION_TYPES
        itype = itype or self.rng.choices(types, weights=type_weights, k=1)[0]
        city = self.rng.choice(profile["cities"])
        groups = profile["groups"]
        group = self.rng.choices(list(groups), weights=list(groups.values()), k=1)[0]
        name = self.college_name(itype, state, city, group)
        aicte_id = self.new_id()
        if itype == "DEEMED":
            university = None
        else:
            university = self.rng.choice(self.unis_by_state[state])
        if itype == "GOVERNMENT":
            year = self.rng.randint(1955, 2010)
        elif itype == "DEEMED" or itype == "GOVERNMENT_AIDED":
            year = self.rng.randint(1960, 2005)
        else:
            year = self.rng.randint(1983, 2016)
        return {
            "aicte_permanent_id": aicte_id,
            "name": name,
            "type": itype,
            "state_code": state,
            "university_code": university,
            "address_city": city,
            "established_year": year,
            "programmes": self.random_programmes(itype, force_odl=force_odl),
            "_region": geo.REGION_OF_STATE[state],
            "_slug": self.slug_for(name, aicte_id),
        }

    def build(self) -> list[dict]:
        n = self.cfg.size.institutions
        out = [
            self.fixed_institution(
                ABC_ID,
                "ABC College of Engineering",
                "PRIVATE_SELF_FINANCED",
                "MH",
                "MSTU",
                "Pune",
                2004,
                ABC_PROGRAMMES,
            ),
            self.fixed_institution(
                XYZ_ID,
                "XYZ Institute of Technology",
                "PRIVATE_SELF_FINANCED",
                "TN",
                "TNTU",
                "Coimbatore",
                1998,
                XYZ_PROGRAMMES,
            ),
            # A deemed university with an ODL wing, so a legal dual enrolment always exists.
            self.random_institution("KA", "DEEMED", force_odl=True),
            # Two more Maharashtra colleges so the demo ghost ring can span three WEST colleges.
            self.random_institution("MH"),
            self.random_institution("MH"),
        ]
        codes, weights = zip(*geo.state_weights(), strict=True)
        while len(out) < n:
            state = self.rng.choices(codes, weights=weights, k=1)[0]
            out.append(self.random_institution(state))
        return out[:n]


def first_intake(aicte_id: str, code: str, approval: dict) -> int | None:
    """Version 1's intake when the approval was revised, else None (one version)."""
    year, intake = approval["academic_year"], approval["approved_intake"]
    if (aicte_id, code, year) == (ABC_ID, "CSE", "2026-27"):
        return ABC_CSE_V1
    if aicte_id in {ABC_ID, XYZ_ID} or intake not in INTAKE_LADDER[1:]:
        return None
    if zlib.crc32(f"{aicte_id}:{code}:{year}".encode()) % REVISED_ONE_IN:
        return None
    return INTAKE_LADDER[INTAKE_LADDER.index(intake) - 1]


def approval_versions(aicte_id: str, code: str, approval: dict) -> list[dict]:
    """Ascending versions, the last one's intake the approval's."""
    year, intake = approval["academic_year"], approval["approved_intake"]
    start = year[:4]
    first = first_intake(aicte_id, code, approval)
    if first is None:
        return [
            {
                "version": 1,
                "approved_intake": intake,
                "effective_from": f"{start}-{V1_DAY}",
                "source": f"AICTE EoA {year}",
            }
        ]
    return [
        {
            "version": 1,
            "approved_intake": first,
            "effective_from": f"{start}-{V1_DAY}",
            "source": f"AICTE EoA {year}",
        },
        {
            "version": 2,
            "approved_intake": intake,
            "effective_from": f"{start}-{V2_DAY}",
            "source": f"AICTE EoA {year}, revised",
        },
    ]


def public_approval(aicte_id: str, code: str, approval: dict) -> dict:
    """`approved_intake` is the current (latest) version's, the one generation used;
    `versions` keeps the history."""
    versions = approval_versions(aicte_id, code, approval)
    return {
        "academic_year": approval["academic_year"],
        "approved_intake": versions[-1]["approved_intake"],
        "versions": versions,
    }


def intake_on(approval: dict, day: str) -> int:
    """The intake in force on `day` (ISO date) for a public approval with versions."""
    in_force = [v for v in approval["versions"] if v["effective_from"] <= day]
    return (in_force or approval["versions"][:1])[-1]["approved_intake"]


def assign_autonomy(institutions: list[dict], seed: int, share: float) -> None:
    """Mark about `share` of the colleges autonomous (`_autonomous`), deterministically: XYZ
    Institute of Technology and every deemed university always, ABC College never, the rest
    drawn from a stream of its own so nothing else changes."""
    rng = random.Random(f"autonomous:{seed}")
    for inst in institutions:
        inst["_autonomous"] = inst["type"] == "DEEMED" or inst["aicte_permanent_id"] == XYZ_ID
    target = int(len(institutions) * share + 0.5)
    pool = [
        i for i in institutions
        if not i["_autonomous"] and i["aicte_permanent_id"] != ABC_ID and i["university_code"]
    ]  # fmt: skip
    need = max(0, target - sum(i["_autonomous"] for i in institutions))
    for inst in rng.sample(pool, min(need, len(pool))):
        inst["_autonomous"] = True


def credit_issuer(inst: dict, university_names: dict[str, str]) -> dict:
    """Who issues the college's ABC credits (`issuer`, `issuer_name`): the college itself, by
    its AICTE permanent id, when autonomous (or a deemed university, which has no affiliating
    university), else its affiliating university by code."""
    if inst.get("_autonomous") or not inst["university_code"]:
        return {"issuer": inst["aicte_permanent_id"], "issuer_name": inst["name"]}
    code = inst["university_code"]
    return {"issuer": code, "issuer_name": university_names[code]}


def public_institution(inst: dict) -> dict:
    """The institutions.json shape: internal keys dropped, approvals kept with versions."""
    aicte_id = inst["aicte_permanent_id"]
    return {
        "aicte_permanent_id": aicte_id,
        "name": inst["name"],
        "type": inst["type"],
        "state_code": inst["state_code"],
        "university_code": inst["university_code"],
        "address_city": inst["address_city"],
        "established_year": inst["established_year"],
        "autonomous": bool(inst.get("_autonomous", False)),
        "programmes": [
            {
                "code": p["code"],
                "name": p["name"],
                "level": p["level"],
                "discipline": p["discipline"],
                "shift": p["shift"],
                "mode": p["mode"],
                "duration_years": p["duration_years"],
                "approvals": [public_approval(aicte_id, p["code"], a) for a in p["approvals"]],
            }
            for p in inst["programmes"]
        ],
    }


def approved_intake(programme: dict, academic_year: str) -> int | None:
    for a in programme["approvals"]:
        if a["academic_year"] == academic_year:
            return a["approved_intake"]
    return None
