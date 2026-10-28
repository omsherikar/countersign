"""Category eligibility: three optional upload columns and the rows planted against them.

Columns, after `admission_date` in every upload file (API_CONTRACT A4.16), `yes` or `no`,
blank when not reported:

- `tfw_income_certified`: `yes` on every legitimate TFW row (the family income certificate
  the tuition fee waiver needs was reported).
- `nri_sponsored`: `yes` on every legitimate NRI-route row (the student is an NRI or is
  sponsored by one).
- `ciwg`: `yes` on every INTERNATIONAL row of nationality `IN` (a child of an Indian worker in
  the Gulf, who may take the CIWG-reserved international seats).

Planted, each recorded in ground truth (rules of A4.4):

- CIWG_ADMISSION (not flagged): new CIWG first-years with a Study in India record, on the
  seats reserved for them.
- ELIGIBILITY_BREACH, one rule each: NRI_STATUS (an NRI seat whose row says `nri_sponsored`
  no; MEDIUM), TFW_INCOME (a TFW seat whose row says `tfw_income_certified` no; MEDIUM) and
  INTERNATIONAL_CIWG (a new international first-year of nationality IN not marked `ciwg`, on an
  ordinary international seat; HIGH).
- TFW_INCOME_NOT_REPORTED (not a case): TFW rows with the certificate blank; their SEAT row
  waits as PENDING.

A random stream of its own, seeded from the run's seed, leaves every other row unchanged.
"""

from __future__ import annotations

import random

from .anomalies import Planter
from .institutions import ABC_ID
from .students import World, academic_year_start

CLAUSES = {
    "NRI_STATUS": "APH 2024-27 cl. 2.8(b)",
    "TFW_INCOME": "APH 2024-27 cl. 6.42(d)",
    "INTERNATIONAL_CIWG": "APH 2024-27 cl. 2.9",
}
SEVERITY = {"NRI_STATUS": "MEDIUM", "TFW_INCOME": "MEDIUM", "INTERNATIONAL_CIWG": "HIGH"}


class EligibilityPlanner:
    def __init__(self, world: World, planter: Planter):
        self.w = world
        self.planter = planter
        self.cfg = world.cfg.eligibility
        self.rng = random.Random(f"eligibility:{world.seed}")
        self.new_rows: list[dict] = []
        self.unmarked: list[dict] = []  # international rows of nationality IN, not CIWG

    # ------------------------------------------------------------------- CIWG

    def places(self, avoid: set[str]) -> list[tuple[dict, dict]]:
        """First-year cohorts with CIWG-reserved and ordinary international seats free, and
        no planted seat case."""
        w = self.w
        out = []
        for inst in w.institutions:
            aid = inst["aicte_permanent_id"]
            if inst["type"] not in {"PRIVATE_SELF_FINANCED", "DEEMED"} or aid in avoid:
                continue
            for prog in inst["programmes"]:
                key = (aid, prog["code"])
                if prog["mode"] != "PHYSICAL" or key in w.seat_cases or key == (ABC_ID, "CSE"):
                    continue
                if w.refill_programmes.get(aid) == prog["code"]:
                    continue
                pools = w.cohort_pools(prog, 1)
                if pools is None or pools.ciwg < 1:
                    continue
                if w.room(aid, prog, 1, "INTERNATIONAL") >= 1:
                    out.append((inst, prog))
        return out

    def add_rows(self, avoid: set[str] = frozenset()) -> list[dict]:
        """CIWG first-years (one per cohort) and the unmarked ones of INTERNATIONAL_CIWG,
        placed before the rows are settled."""
        w = self.w
        places = self.places(avoid)
        k_ciwg = self.cfg.get("ciwg_rows", 0)
        k_breach = self.cfg.get("international_ciwg", 0)
        picked = self.rng.sample(places, min(k_ciwg + k_breach, len(places)))
        start = academic_year_start(w.cfg.academic_year)
        with w.using_rng(self.rng):
            for n, (inst, prog) in enumerate(picked):
                row = w.base_row(inst, prog, 1, start)
                row["dob"] = w.dob(start, prog["level"])
                marked = n < k_ciwg
                row.update(
                    {
                        "apaar_id": "",
                        "consent_status": "INTERNATIONAL",
                        "nationality": "IN",
                        "passport_no": w.new_passport(),
                        "category": "GENERAL",
                        "ciwg": "yes" if marked else "",
                    }
                )
                w.set_route(row, inst, "INTERNATIONAL")
                w.add_row(row)
                self.new_rows.append(row)
                if marked:
                    self.planter.record(
                        "CIWG_ADMISSION", [row],
                        expected_flag=None, institution_ids=[inst["aicte_permanent_id"]],
                        programme_code=prog["code"], seat_type="INTERNATIONAL",
                        source=CLAUSES["INTERNATIONAL_CIWG"],
                        note="Child of an Indian worker in the Gulf on a CIWG-reserved "
                        "international seat, with a Study in India record; must not be flagged.",
                    )  # fmt: skip
                else:
                    self.unmarked.append(row)
        return self.new_rows

    # ---------------------------------------------------------------- markers

    def mark(self) -> None:
        """Markers on every row, once every route is final."""
        for row in self.w.all_rows + self.w.update_only_rows:
            route = row["admission_route"]
            row["tfw_income_certified"] = "yes" if route == "TFW" else ""
            row["nri_sponsored"] = "yes" if route == "NRI" else ""
            if route != "INTERNATIONAL" or row["nationality"] != "IN":
                row["ciwg"] = ""

    # ---------------------------------------------------------------- planted

    def candidates(self, route: str, avoid: set[str]) -> list[dict]:
        """Untouched first-years of `route` outside planted seat cases and ABC College."""
        w = self.w
        leaving = w.leaving_rows()
        return [
            r for r in w.all_rows
            if r["admission_route"] == route and r["year_of_study"] == 1 and not r["_tags"]
            and r["_inst"] != ABC_ID and r["_inst"] not in avoid
            and (r["_inst"], r["programme_code"]) not in w.seat_cases
            and id(r) not in leaving and r["_prog"]["mode"] == "PHYSICAL"
        ]  # fmt: skip

    def breach(self, row: dict, rule: str, marker: dict[str, str], note: str) -> None:
        row.update(marker)
        self.planter.record(
            "ELIGIBILITY_BREACH", [row],
            expected_flag="ELIGIBILITY_BREACH", severity=SEVERITY[rule],
            institution_ids=[row["_inst"]], programme_code=row["programme_code"],
            eligibility_rule=rule, marker=marker, source=CLAUSES[rule], note=note,
        )  # fmt: skip

    def plant(self, avoid: set[str] = frozenset()) -> None:
        for row in self.pick("NRI", self.cfg.get("nri_status", 0), avoid):
            self.breach(
                row, "NRI_STATUS", {"nri_sponsored": "no"},
                "Admitted to an NRI seat, but the college reports the student as neither an "
                "NRI nor NRI-sponsored.",
            )  # fmt: skip
        for row in self.pick("TFW", self.cfg.get("tfw_income", 0), avoid):
            self.breach(
                row, "TFW_INCOME", {"tfw_income_certified": "no"},
                "Admitted to a tuition fee waiver seat without a family income certificate.",
            )  # fmt: skip
        for row in self.unmarked:
            self.breach(
                row, "INTERNATIONAL_CIWG", {"ciwg": ""},
                "An Indian national on an international seat, not marked as a child of an "
                "Indian worker in the Gulf.",
            )  # fmt: skip
        for row in self.pick("TFW", self.cfg.get("tfw_not_reported", 0), avoid):
            row["tfw_income_certified"] = ""
            self.planter.record(
                "TFW_INCOME_NOT_REPORTED", [row],
                expected_flag=None, institution_ids=[row["_inst"]],
                programme_code=row["programme_code"], seat_type="TFW",
                expected_check={"type": "SEAT", "status": "PENDING"},
                note="TFW admission with tfw_income_certified blank: the SEAT row waits as "
                "PENDING (TFW income certificate not reported); no case.",
            )  # fmt: skip

    def pick(self, route: str, k: int, avoid: set[str]) -> list[dict]:
        pool = self.candidates(route, avoid)
        return self.rng.sample(pool, min(k, len(pool)))
