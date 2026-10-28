"""Update files: withdrawals, transfers and late refills (API_CONTRACT A2.24).

An update file, `uploads/<aicte_id>_<year>_update1.csv`, holds only rows that change
something. An existing student's row repeats every column of its initial row, so it
resolves to the same student, with a new `status` and `status_date`. A late refill is a
new first-year admitted after the cutoff in rules.yaml into a seat that a withdrawal in the
same file released. The first-year REGULAR pool being refilled is topped up to exactly full
in the initial file, so the released seats are the only free ones and every refill takes
one and raises LATE_REFILL.

Never touched: a first-year cohort holding a planted EXCESS_ADMISSION or QUOTA_BREACH (ABC
College's 132 against 120 included), the demo student, or any row another planted case
refers to.
"""

from __future__ import annotations

import datetime as dt

from .anomalies import GOVERNMENT_TYPES, Planter
from .institutions import ABC_ID
from .students import World


class UpdatePlanner:
    def __init__(self, world: World, planter: Planter):
        self.w = world
        self.planter = planter
        self.rng = world.rng
        self.cfg = world.cfg.updates
        cutoff = world.cfg.rules["cutoff_dates"][world.cfg.academic_year]
        self.cutoff = dt.date.fromisoformat(cutoff)
        lo, hi = self.cfg.status_dates
        self.status_from = dt.date.fromisoformat(lo)
        self.status_to = dt.date.fromisoformat(hi)

    # ------------------------------------------------------------------ driver

    def plan(self) -> None:
        w = self.w
        first = [ABC_ID] if w.cfg.scenarios else []
        others = [
            i["aicte_permanent_id"] for i in w.institutions if i["aicte_permanent_id"] != ABC_ID
        ]
        self.rng.shuffle(others)
        planned = 0
        for aid in first + others:
            if planned == self.cfg.colleges:
                break
            if self.plan_college(aid):
                planned += 1

    # ----------------------------------------------------------------- helpers

    def update_row(self, initial: dict, status: str, day: dt.date) -> dict:
        """An existing student's row; its columns are copied from `initial` when written."""
        return {
            "_initial": initial,
            "_inst": initial["_inst"],
            "_prog": initial["_prog"],
            "_seq": initial["_seq"],
            "_tags": [],
            "status": status,
            "status_date": day.isoformat(),
        }

    def movable(self, aid: str, refill_code: str) -> list[dict]:
        """Initial rows of the college that an update may withdraw or transfer."""
        seat_cases = self.w.seat_cases
        out = []
        for row in self.w.rows_by_inst[aid]:
            if row["_tags"]:
                continue
            if row["year_of_study"] == 1 and (
                row["programme_code"] == refill_code or (aid, row["programme_code"]) in seat_cases
            ):
                continue
            out.append(row)
        return out

    # ----------------------------------------------------------------- college

    def plan_college(self, aid: str) -> bool:
        w = self.w
        code = w.refill_programmes.get(aid) or self.planter.reserve_refill_programme(aid)
        if code is None:
            return False
        inst = w.inst_by_id[aid]
        prog = w.programme(aid, code)

        # Top the first-year REGULAR pool up to exactly full in the initial file.
        gap = w.cohort_pools(prog, 1).regular - w.pool_counts(aid, code, 1)["REGULAR"]
        for route in w.regular_routes(inst, gap):
            w.new_student(inst, prog, 1, route)

        k = self.rng.randint(*self.cfg.refills)
        seated = [
            r for r in sorted(w.cohort_rows(aid, code, 1), key=lambda r: r["_seq"])
            if not r["_tags"] and w.route_pool(r["admission_route"]) == "REGULAR"
        ]  # fmt: skip
        if len(seated) < k:
            return False
        lo, hi = self.cfg.withdrawals
        withdrawals = self.rng.randint(max(lo, k), hi)
        transfers = self.rng.randint(*self.cfg.transfers)
        pool = self.movable(aid, code)
        abc_cse = []
        if aid == ABC_ID and w.cfg.scenarios:
            # ABC withdraws a CSE student of an earlier cohort; the first-years stay as planted.
            abc_cse = [r for r in pool if r["programme_code"] == "CSE" and r["year_of_study"] > 1]
            withdrawals = max(withdrawals, k + 1)
        others = withdrawals - k
        if len(pool) < others + transfers + 1:
            return False

        released = self.rng.sample(seated, k)
        cse_pick = self.rng.choice(abc_cse) if abc_cse else None
        picked = [cse_pick] if cse_pick else []
        rest = [r for r in pool if r is not cse_pick]
        picked += self.rng.sample(rest, others + transfers - len(picked))
        leaving, moving = picked[:others], picked[others:]

        last_release = self.status_from + dt.timedelta(days=19)
        rows: list[dict] = []
        released_rows = []
        for row in released:
            upd = self.update_row(row, "WITHDRAWN", w.random_date(self.status_from, last_release))
            released_rows.append(upd)
        others_rows = [
            self.update_row(r, "WITHDRAWN", w.random_date(self.status_from, self.status_to))
            for r in leaving
        ]
        transfer_rows = [
            self.update_row(r, "TRANSFERRED", w.random_date(self.status_from, self.status_to))
            for r in moving
        ]
        order = {p["code"]: i for i, p in enumerate(inst["programmes"])}
        existing = sorted(
            released_rows + others_rows + transfer_rows,
            key=lambda u: (order[u["_prog"]["code"]], u["_initial"]["year_of_study"], u["_seq"]),
        )
        rows.extend(existing)

        refills = self.make_refills(inst, prog, k, max(u["status_date"] for u in released_rows))
        rows.extend(refills)
        w.update_files[aid] = rows

        for upd in released_rows + others_rows:
            initial = upd["_initial"]
            scenario = "abc_cse_withdrawal" if initial is cse_pick else None
            self.planter.record(
                "WITHDRAWAL", [upd],
                expected_flag=None, institution_ids=[aid], programme_code=initial["programme_code"],
                status_date=upd["status_date"], scenario=scenario,
                note=f"Withdrawn on {upd['status_date']}; the seat is released, nothing to flag.",
            )  # fmt: skip
        for upd in transfer_rows:
            initial = upd["_initial"]
            self.planter.record(
                "TRANSFER", [upd],
                expected_flag=None, institution_ids=[aid], programme_code=initial["programme_code"],
                status_date=upd["status_date"],
                note=f"Transferred out on {upd['status_date']}; nothing to flag.",
            )  # fmt: skip
        self.planter.record(
            "LATE_REFILL", refills,
            expected_flag="LATE_REFILL", institution_ids=[aid], programme_code=code,
            seat_type="REGULAR", cutoff_date=self.cutoff.isoformat(), _released=released_rows,
            scenario="late_refill" if aid == ABC_ID and w.cfg.scenarios else None,
            note=f"{k} first-year {code} seat(s) released by withdrawal and filled after the "
            f"last admission date {self.cutoff.isoformat()}.",
        )  # fmt: skip
        return True

    def make_refills(self, inst: dict, prog: dict, k: int, released_on: str) -> list[dict]:
        """New first-years with an APAAR, admitted after the cutoff and after the release."""
        w = self.w
        route = "SPOT" if inst["type"] in GOVERNMENT_TYPES else None
        start = dt.date.fromisoformat(released_on) + dt.timedelta(days=1)
        start = max(start, self.cutoff + dt.timedelta(days=1))
        out = []
        for _ in range(k):
            row = w.make_student(inst, prog, 1, route or self.rng.choice(["MANAGEMENT", "SPOT"]))
            if row["consent_status"] != "LINKED":
                row["consent_status"] = "LINKED"
                row["apaar_id"] = w.new_apaar()
            row["status"] = "ACTIVE"
            row["admission_date"] = w.random_date(start, self.status_to).isoformat()
            w.update_only_rows.append(row)
            out.append(row)
        return out
