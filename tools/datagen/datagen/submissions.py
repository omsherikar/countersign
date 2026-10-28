"""How colleges submit their files: dates, late and overdue colleges, their own headers.

API_CONTRACT A4.25 (manifest `uploads`, `late_colleges`, `overdue_colleges`) and A4.16
(column mapping):

- every initial and update file gets `submitted_at`, which the seed uses as the batch's
  upload time: initial files between 16 and 29 September (on time for the 30 September
  reporting deadline), the late colleges' initial files in October, update files after every
  date they carry;
- LATE_UPLOAD records name the colleges whose initial file came after the deadline;
- OVERDUE_UPLOAD records name the colleges that sent no file at all for the year. Their
  students still joined: they keep their joining lines, registry entries and accounts, and a
  MISSING_FROM_UPLOAD record counts them all. An overdue college carries no other plant;
- `column_mappings.json` maps the headers a few colleges use (XYZ Institute of Technology
  among them) to the template columns; their files, initial and update, are written with
  those headers.

A random stream of its own, seeded from the run's seed, leaves every other value unchanged.
"""

from __future__ import annotations

import datetime as dt
import random

from .anomalies import Planter
from .institutions import ABC_ID, XYZ_ID
from .joining import joining_year
from .students import World

# Header variants: template column -> the college's own header. No header normalises to a
# template column (trimmed, lower case, spaces and hyphens as underscores), so each needs the
# saved mapping.
HEADER_VARIANTS: tuple[dict[str, str], ...] = (
    {
        "name": "Student Name", "dob": "D.O.B.", "apaar_id": "APAAR No.", "mobile": "Mobile No",
        "email": "Email ID", "programme_code": "Course Code", "year_of_study": "Year",
        "admission_route": "Admission Type", "counselling_ref": "Allotment No",
        "category": "Caste Category", "consent_status": "APAAR Consent",
        "admission_date": "Date of Admission",
    },
    {
        "name": "Name of Student", "dob": "Date of Birth", "gender": "Gender (M/F)",
        "address": "Residential Address", "programme_code": "Branch",
        "year_of_study": "Current Year", "admission_route": "Quota",
        "counselling_ref": "CAP Allotment Ref", "category": "Social Category",
        "admission_date": "Admitted On",
    },
    {
        "name": "Candidate Name", "dob": "Birth Date", "mobile": "Contact Number",
        "passport_no": "Passport Number", "programme_code": "Programme",
        "year_of_study": "Year of Study (1-5)", "admission_route": "Route",
        "category": "Reservation Category", "tfw_income_certified": "TFW Income Certificate",
        "nri_sponsored": "NRI or NRI-Sponsored",
    },
)  # fmt: skip


def normalise_header(text: str) -> str:
    """As the api reads a header (API_CONTRACT A2.2)."""
    return text.strip().lower().replace(" ", "_").replace("-", "_")


class SubmissionPlanner:
    def __init__(self, world: World, planter: Planter):
        self.w = world
        self.planter = planter
        self.cfg = world.cfg.submissions
        self.rng = random.Random(f"submissions:{world.seed}")
        self.deadline = world.cfg.reporting_deadline(world.cfg.academic_year)

    def referenced(self) -> set[str]:
        out = set(self.w.update_files)
        for rec in self.w.ground_truth:
            out |= set(rec["institution_aicte_ids"])
        return out

    def choose(self) -> None:
        """Overdue colleges first (no plant of any kind may touch them), then late ones and
        the colleges with their own headers."""
        w = self.w
        ids = [i["aicte_permanent_id"] for i in w.institutions]
        quiet = [a for a in ids if a not in self.referenced() | {ABC_ID, XYZ_ID}]
        k = min(self.cfg.get("overdue_colleges", 0), len(quiet))
        w.overdue = sorted(self.rng.sample(quiet, k))
        rest = [a for a in ids if a not in set(w.overdue) | {ABC_ID, XYZ_ID}]
        k = min(self.cfg.get("late_colleges", 0), len(rest))
        w.late = sorted(self.rng.sample(rest, k))
        others = [a for a in rest if a not in w.late]
        k = max(0, min(self.cfg.get("mapped_colleges", 0) - 1, len(others)))
        mapped = [XYZ_ID] + self.rng.sample(others, k)
        w.header_maps = {
            aid: HEADER_VARIANTS[n % len(HEADER_VARIANTS)] for n, aid in enumerate(mapped)
        }

    def record(self, joining) -> None:
        """LATE_UPLOAD and OVERDUE_UPLOAD records; an overdue college's MISSING_FROM_UPLOAD."""
        w = self.w
        for aid in w.late:
            self.planter.record(
                "LATE_UPLOAD", [],
                expected_flag=None, institution_ids=[aid], programme_code=None,
                expected_deadline_state="LATE", academic_year=w.cfg.academic_year,
                deadline=self.deadline,
                note=f"The college's first {w.cfg.academic_year} file came after the "
                f"{self.deadline} reporting deadline.",
            )  # fmt: skip
        for aid in w.overdue:
            self.planter.record(
                "OVERDUE_UPLOAD", [],
                expected_flag=None, institution_ids=[aid], programme_code=None,
                expected_deadline_state="OVERDUE", academic_year=w.cfg.academic_year,
                deadline=self.deadline,
                note=f"The college sent no file for {w.cfg.academic_year}; the "
                f"{self.deadline} reporting deadline has passed.",
            )  # fmt: skip
            year = w.cfg.academic_year
            rows = [
                r for r in w.rows_by_inst[aid]
                if "_joined_on" in r and joining_year(r, year) == year
            ]  # fmt: skip
            joining.record_missing_college(
                aid, rows, len(rows), overdue=True,
                note=f"The college sent no {year} file: every student in the state admission "
                "authority's joining list for the year is missing.",
            )  # fmt: skip

    # ------------------------------------------------------------------ dates

    def stamp(self, lo: str, hi: str) -> str:
        first, last = dt.date.fromisoformat(lo), dt.date.fromisoformat(hi)
        day = first + dt.timedelta(days=self.rng.randint(0, (last - first).days))
        moment = dt.datetime(day.year, day.month, day.day, self.rng.randint(4, 12),
                             self.rng.choice([0, 15, 30, 45]), tzinfo=dt.UTC)  # fmt: skip
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")

    def submitted(self, files: list[str], updates: list[str]) -> list[dict]:
        """The manifest's `uploads`: initial files in name order, then the update files."""
        w = self.w
        out = []
        for name in sorted(files):
            aid = name.split("/")[1].rsplit("_", 1)[0]
            window = self.cfg["late"] if aid in w.late else self.cfg["on_time"]
            out.append(self.entry(name, aid, self.stamp(*window)))
        for name in sorted(updates):
            aid = name.split("/")[1].split("_")[0]
            out.append(self.entry(name, aid, self.stamp(*self.cfg["updates"])))
        return out

    def entry(self, name: str, aid: str, submitted_at: str) -> dict:
        return {
            "file": name,
            "aicte_id": aid,
            "academic_year": self.w.cfg.academic_year,
            "submitted_at": submitted_at,
        }
