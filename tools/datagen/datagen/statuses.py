"""Records planted to check the record status rule (DECISIONS D35, API_CONTRACT A4.25).

Each is a ground-truth record with `expected_flag` null and `expected_record_status`, and its
row answers no notice (NONE in notice_replies.jsonl):

- CLEAN_INDEPENDENT: clean records whose joining line is their independent evidence: APAAR
  verified, seat fits, joined; COUNTERSIGNED without any reply.
- SELF_ISSUED_ONLY: second-years at an autonomous college in a state whose authority has
  published no joining record for the previous year, so their Joining record row is pending
  (never contradicted); their only confirmed enrolment row is the college's own credits, which
  are not independent, so they stay AWAITING_EVIDENCE.
- PROVISIONAL_UNCLAIMED: the refused-consent ABC College CSE first-year the demo claims by
  provisional id after DigiLocker sign-in (manifest `demo_digilocker_accounts`, role
  PROVISIONAL_CLAIM): AWAITING_EVIDENCE before the claim, COUNTERSIGNED after it.

The planner also picks the SOMEONE_ELSE demo account's student: a clean, linked first-year at
another college, whose account matches no notice the demo opens.

A random stream of its own, seeded from the run's seed, leaves every other row unchanged.
"""

from __future__ import annotations

import random
from collections import defaultdict

from .anomalies import Planter
from .institutions import ABC_ID, XYZ_ID
from .joining import JoiningPlanner, owns_apaar
from .matching import name_key
from .students import World


class StatusPlanner:
    def __init__(self, world: World, planter: Planter, avoid: set[str] = frozenset()):
        self.w = world
        self.planter = planter
        self.avoid = set(avoid)
        self.cfg = world.cfg.statuses
        self.rng = random.Random(f"statuses:{world.seed}")
        self.provisional: dict | None = None
        self.someone_else: dict | None = None
        self.self_issued_state: str | None = None

    def clean(self, row: dict, leaving: set[int]) -> bool:
        return (
            not row["_tags"]
            and id(row) not in leaving
            and row["_prog"]["mode"] == "PHYSICAL"
            and row["admission_route"] != "INTERNATIONAL"
            and (row["_inst"], row["programme_code"]) not in self.w.seat_cases
        )

    # ------------------------------------------------------------- before joining

    def plant_provisional(self) -> None:
        """The refused-consent ABC CSE first-year the demo claims; one is made from a linked
        classmate when the roll has none, never the second demo notice's student."""
        w = self.w
        if not w.cfg.scenarios:
            return
        leaving = w.leaving_rows()
        cohort = sorted(w.cohort_rows(ABC_ID, "CSE", 1), key=lambda r: r["_seq"])
        # ABC CSE holds the planted 132 against 120: only its seated (not late) rows qualify.
        cohort = [
            r for r in cohort
            if not r["_tags"] and id(r) not in leaving and not r["_late"] and r["email"]
            and r["admission_route"] in {"COUNSELLING", "MANAGEMENT", "SPOT"}
        ]  # fmt: skip
        refused = [r for r in cohort if r["consent_status"] == "REFUSED"]
        if refused:
            row = refused[0]
        else:
            linked = [r for r in cohort if owns_apaar(r)]
            second = next((r for r in linked if r["admission_route"] == "COUNSELLING"), None)
            keys = defaultdict(int)
            for r in w.rows_by_inst[ABC_ID]:
                keys[name_key(r["name"], r["dob"])] += 1
            options = [
                r for r in linked
                if r is not second and keys[name_key(r["name"], r["dob"])] == 1
            ]  # fmt: skip
            if not options:
                return
            row = options[0]
            row["apaar_id"] = ""
            row["consent_status"] = "REFUSED"
        self.provisional = row
        self.planter.record(
            "PROVISIONAL_UNCLAIMED", [row],
            expected_flag=None, institution_ids=[ABC_ID], programme_code="CSE",
            expected_record_status="AWAITING_EVIDENCE",
            expected_record_status_after_claim="COUNTERSIGNED",
            note="Refused APAAR consent: Identity waits for the student to sign in through "
            "DigiLocker and claim the record with the provisional id; then it is countersigned.",
        )  # fmt: skip

    def choose_self_issued_state(self) -> str | None:
        """A state (not ABC's or XYZ's) with an autonomous college that has enough clean
        second-years; the one with the fewest colleges, so the fewest records wait."""
        w = self.w
        k = self.cfg.get("self_issued_only", 0)
        if not k:
            return None
        colleges = defaultdict(int)
        for inst in w.institutions:
            colleges[inst["state_code"]] += 1
        fixed = {w.inst_by_id[ABC_ID]["state_code"], w.inst_by_id[XYZ_ID]["state_code"]}
        options = []
        for state, n in colleges.items():
            if state in fixed:
                continue
            rows = self.self_issued_rows(state)
            if len(rows) >= k:
                options.append((n, -len(rows), state))
        if not options:
            return None
        self.self_issued_state = min(options)[2]
        return self.self_issued_state

    def self_issued_rows(self, state: str) -> list[dict]:
        w = self.w
        leaving = w.leaving_rows()
        return [
            r for r in w.all_rows
            if w.inst_by_id[r["_inst"]]["state_code"] == state
            and w.inst_by_id[r["_inst"]].get("_autonomous")
            and r["_inst"] not in self.avoid
            and r["year_of_study"] == 2 and r["admission_route"] != "LATERAL"
            and owns_apaar(r) and r["_credits"] == "normal" and self.clean(r, leaving)
        ]  # fmt: skip

    # -------------------------------------------------------------- after joining

    def plant(self, joining: JoiningPlanner) -> None:
        w = self.w
        leaving = w.leaving_rows()
        if self.self_issued_state:
            rows = self.self_issued_rows(self.self_issued_state)
            for row in self.rng.sample(rows, min(len(rows), self.cfg["self_issued_only"])):
                self.planter.record(
                    "SELF_ISSUED_ONLY", [row],
                    expected_flag=None, institution_ids=[row["_inst"]],
                    programme_code=row["programme_code"],
                    expected_record_status="AWAITING_EVIDENCE",
                    expected_rows={"ADMISSION": "PENDING", "STUDYING": "CONFIRMED"},
                    unpublished={"state": self.self_issued_state,
                                 "academic_year": joining.last_year},
                    note="Second-year at an autonomous college whose state has published no "
                    "joining record for its year: only the college's own credits confirm it.",
                )  # fmt: skip
        clean = [
            r for r in w.all_rows
            if self.clean(r, leaving) and owns_apaar(r) and joining.published(r)
            and r["_inst"] not in self.avoid | {ABC_ID} and "_joined_on" in r
        ]  # fmt: skip
        picked = self.rng.sample(clean, min(len(clean) - 1, self.cfg.get("clean_independent", 0)))
        for row in picked:
            self.planter.record(
                "CLEAN_INDEPENDENT", [row],
                expected_flag=None, institution_ids=[row["_inst"]],
                programme_code=row["programme_code"],
                expected_record_status="COUNTERSIGNED", independent_row="ADMISSION",
                note="APAAR verified, the seat fits and the state admission authority's "
                "joining line confirms the enrolment: countersigned without any reply.",
            )  # fmt: skip
        taken = {id(r) for r in picked}
        first_years = [r for r in clean if id(r) not in taken and r["year_of_study"] == 1]
        self.someone_else = self.rng.choice(first_years) if first_years else None
