"""Category eligibility: three optional upload columns and the cases planted against them.

Columns, after `admission_date` in every upload file:

- `tfw_income_certified`: `yes` on every TFW row (the family income certificate the tuition
  fee waiver needs was reported), blank elsewhere. One planted TFW row leaves it blank.
- `nri_sponsored`: on every NRI-route row, `NRI` (the student is a non-resident Indian) or
  `NRI_SPONSORED` (a ward sponsored by an NRI); blank elsewhere. One planted NRI-route row
  says `NO`: the student is neither, so the NRI seat is not theirs.
- `ciwg`: `yes` on the rows of children of Indian workers in the Gulf (INTERNATIONAL route,
  nationality IN), who may take the CIWG-reserved international seats; blank elsewhere.

Planted, each recorded in ground truth:

- CIWG_ADMISSION (not flagged): new CIWG first-years with a Study in India record, on seats
  reserved for them.
- ELIGIBILITY_BREACH (MEDIUM): the NRI-route row marked `NO`; the SEAT row is CONTRADICTED.
- TFW_INCOME_NOT_REPORTED (not a case): the TFW row without the marker; its SEAT row is
  PENDING "TFW income certificate not reported" until the college reports it.

A random stream of its own, seeded from the run's seed, leaves every other row unchanged.
"""

from __future__ import annotations

import random

from .anomalies import Planter
from .institutions import ABC_ID
from .students import World, academic_year_start

CIWG_SOURCE = "APH 2024-27 cl. 2.9 (CIWG seats within the international seats)"
NRI_SOURCE = "APH 2024-27 cl. 2.8(b)"


class EligibilityPlanner:
    def __init__(self, world: World, planter: Planter):
        self.w = world
        self.planter = planter
        self.cfg = world.cfg.eligibility
        self.rng = random.Random(f"eligibility:{world.seed}")
        self.new_rows: list[dict] = []

    # ------------------------------------------------------------------- CIWG

    def ciwg_places(self) -> list[tuple[dict, dict]]:
        """First-year cohorts with CIWG-reserved seats and no planted seat case."""
        w = self.w
        out = []
        for inst in w.institutions:
            if inst["type"] not in {"PRIVATE_SELF_FINANCED", "DEEMED"}:
                continue
            aid = inst["aicte_permanent_id"]
            for prog in inst["programmes"]:
                key = (aid, prog["code"])
                if prog["mode"] != "PHYSICAL" or key in w.seat_cases or key == (ABC_ID, "CSE"):
                    continue
                if w.refill_programmes.get(aid) == prog["code"]:
                    continue
                pools = w.cohort_pools(prog, 1)
                if pools is not None and pools.ciwg > 0:
                    out.append((inst, prog))
        return out

    def add_ciwg_rows(self) -> list[dict]:
        """New CIWG first-years, one per cohort, placed before the rows are settled."""
        w = self.w
        places = self.ciwg_places()
        picked = self.rng.sample(places, min(self.cfg.get("ciwg_rows", 0), len(places)))
        start = academic_year_start(w.cfg.academic_year)
        with w.using_rng(self.rng):
            for inst, prog in picked:
                row = w.base_row(inst, prog, 1, start)
                row["dob"] = w.dob(start, prog["level"])
                row.update(
                    {
                        "apaar_id": "",
                        "consent_status": "INTERNATIONAL",
                        "nationality": "IN",
                        "passport_no": w.new_passport(),
                        "category": "GENERAL",
                        "ciwg": "yes",
                    }
                )
                w.set_route(row, inst, "INTERNATIONAL")
                w.add_row(row)
                self.new_rows.append(row)
                self.planter.record(
                    "CIWG_ADMISSION", [row],
                    expected_flag=None, institution_ids=[inst["aicte_permanent_id"]],
                    programme_code=prog["code"], seat_type="INTERNATIONAL",
                    source=CIWG_SOURCE,
                    note="Child of an Indian worker in the Gulf on a CIWG-reserved international "
                    "seat, with a Study in India record; must not be flagged.",
                )  # fmt: skip
        return self.new_rows

    # ---------------------------------------------------------------- markers

    def mark(self) -> None:
        """Markers on every row, once every route is final."""
        share = float(self.cfg.get("nri_sponsored_share", 0.3))
        for row in self.w.all_rows + self.w.update_only_rows:
            route = row["admission_route"]
            row["tfw_income_certified"] = "yes" if route == "TFW" else ""
            if route == "NRI":
                row["nri_sponsored"] = "NRI_SPONSORED" if self.rng.random() < share else "NRI"
            else:
                row["nri_sponsored"] = ""
            if row["ciwg"] and route != "INTERNATIONAL":
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

    def plant(self, avoid: set[str] = frozenset()) -> None:
        for row in self.pick("NRI", self.cfg.get("nri_breach", 0), avoid):
            row["nri_sponsored"] = "NO"
            self.planter.record(
                "ELIGIBILITY_BREACH", [row],
                expected_flag="ELIGIBILITY_BREACH", severity="MEDIUM",
                institution_ids=[row["_inst"]], programme_code=row["programme_code"],
                seat_type="NRI", marker={"nri_sponsored": "NO"}, source=NRI_SOURCE,
                note="Admitted on the NRI route, but the college reports the student as "
                "neither an NRI nor NRI-sponsored, so the NRI seat is not theirs.",
            )  # fmt: skip
        for row in self.pick("TFW", self.cfg.get("tfw_not_reported", 0), avoid):
            row["tfw_income_certified"] = ""
            self.planter.record(
                "TFW_INCOME_NOT_REPORTED", [row],
                expected_flag=None, institution_ids=[row["_inst"]],
                programme_code=row["programme_code"], seat_type="TFW",
                expected_check={"type": "SEAT", "status": "PENDING"},
                note="TFW admission without tfw_income_certified: the SEAT row waits as "
                "PENDING (TFW income certificate not reported); no case.",
            )  # fmt: skip

    def pick(self, route: str, k: int, avoid: set[str]) -> list[dict]:
        pool = self.candidates(route, avoid)
        return self.rng.sample(pool, min(k, len(pool)))
