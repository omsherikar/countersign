"""Signals the anomaly and ring detectors should raise, and last year's admissions.

Signals are for officers only and never set a record's status (DECISIONS D45). Ground truth
lists what should stand out so the evaluation can score signal precision and recall:

- every GHOST_RING record becomes `expected_flag: null` with `expected_signal: "GHOST_RING"`
  (signals never raise a case on their own; the rings are planted by anomalies.py, the named
  one 40 students across 3 colleges sharing contacts);
- ANOMALY records (`expected_flag` null, `expected_signal: "ANOMALY"`) name one college each
  and `features`, the anomaly model's features (ENGINES 17.11) that should make it stand out,
  with every feature's `values` and the peers' medians:
  - `admission_growth` (first-years over second-years on the roll): the college admits extra
    first-years into its free REGULAR seats (never above the approved intake) until it has
    about three times last year's admissions, while its peers stay level;
  - `management_share` and `nri_share` (MANAGEMENT plus SPOT, and NRI, first-years over all
    first-years): its counselled and spot first-years move to the management route and its
    NRI seats fill up, all inside the seat pools.

`history.json` holds last year's (the roll's previous academic year) first-year admissions
per college and programme: second-years still on the roll divided by a retention drawn per
programme, or this year's count near level for open and online programmes, which have no
second-year cohort here. The planted growth is measured against it like for like.

A random stream of its own, seeded from the run's seed, leaves every other row unchanged.
"""

from __future__ import annotations

import math
import random
import statistics

from .anomalies import Planter
from .institutions import ABC_ID, XYZ_ID, approved_intake
from .students import World, academic_year_label, academic_year_start

FEATURE_GROWTH = "admission_growth"
STABLE_GROWTH = 1.25  # a spike college is picked among colleges growing at most this much
MAX_GROWTH = 3.0  # and grows no further than this
SHARE_MOVE = 0.95  # of the share college's counselled first-years move to management
MIN_RECORDS = 20  # the model leaves out smaller colleges


class SignalPlanner:
    def __init__(self, world: World, planter: Planter):
        self.w = world
        self.planter = planter
        self.cfg = world.cfg.signals
        self.rng = random.Random(f"signals:{world.seed}")
        self.new_rows: list[dict] = []
        self.colleges: set[str] = set()
        self.history: dict = {}
        self.last_year = academic_year_label(academic_year_start(world.cfg.academic_year) - 1)

    # ---------------------------------------------------------------- history

    def build_history(self) -> dict:
        lo, hi = self.cfg.get("retention", [0.9, 0.98])
        insts = []
        for inst in self.w.institutions:
            aid = inst["aicte_permanent_id"]
            rows = self.w.rows_by_inst[aid]
            programmes: dict[str, int] = {}
            for prog in inst["programmes"]:
                if approved_intake(prog, self.last_year) is None:
                    continue
                code = prog["code"]
                if prog["mode"] == "PHYSICAL":
                    second = sum(
                        r["programme_code"] == code and r["year_of_study"] == 2
                        and r["admission_route"] != "LATERAL"
                        for r in rows
                    )  # fmt: skip
                    admitted = math.ceil(second / self.rng.uniform(lo, hi))
                else:
                    first = sum(
                        r["programme_code"] == code and r["year_of_study"] == 1 for r in rows
                    )
                    admitted = round(first * self.rng.uniform(0.9, 1.1))
                programmes[code] = admitted
            insts.append(
                {
                    "institution_aicte_id": aid,
                    "admitted": sum(programmes.values()),
                    "programmes": programmes,
                }
            )
        return {
            "academic_year": self.last_year,
            "note": "Synthetic. First-year admissions of the previous academic year per "
            "college and programme, for the year-over-year feature of the anomaly model.",
            "institutions": insts,
        }

    # ---------------------------------------------------------------- picking

    def busy(self) -> set[str]:
        """Colleges already carrying a named scenario, a ring, an update file, a seat case or
        a CIWG plant: the anomaly colleges stay clear of them."""
        w = self.w
        out = {ABC_ID, XYZ_ID} | set(w.update_files) | {aid for aid, _ in w.seat_cases}
        out |= set(w.overdue)
        for rec in w.ground_truth:
            if rec["anomaly_type"] in {"GHOST_RING", "CIWG_ADMISSION"}:
                out |= set(rec["institution_aicte_ids"])
        return out

    def first_years(self, aid: str) -> list[dict]:
        return [r for r in self.w.rows_by_inst[aid] if r["year_of_study"] == 1]

    def regular_room(self, inst: dict) -> list[tuple[dict, int]]:
        w = self.w
        out = []
        for prog in inst["programmes"]:
            if prog["mode"] != "PHYSICAL":
                continue
            room = w.room(inst["aicte_permanent_id"], prog, 1, "COUNSELLING")
            if room > 0:
                out.append((prog, room))
        return out

    def growth(self, aid: str, extra: int = 0) -> float:
        """Like for like: this year's first-years in the programmes that admitted last year,
        over last year's admissions in them (a programme new this year is not growth)."""
        ran = {code: n for code, n in self.last_year_of(aid).items() if n > 0}
        if not ran:
            return 0.0
        now = sum(r["programme_code"] in ran for r in self.first_years(aid))
        return (now + extra) / sum(ran.values())

    def last_year_of(self, aid: str) -> dict[str, int]:
        if not hasattr(self, "_by_id"):
            self._by_id = {e["institution_aicte_id"]: e for e in self.history["institutions"]}
        entry = self._by_id.get(aid)
        return entry["programmes"] if entry else {}

    def admitted_last_year(self, aid: str) -> int:
        return sum(self.last_year_of(aid).values())

    @staticmethod
    def share(rows: list[dict]) -> float:
        if not rows:
            return 0.0
        return sum(r["admission_route"] in {"NRI", "MANAGEMENT"} for r in rows) / len(rows)

    # ---------------------------------------------------------------- planting

    def stable(self, inst: dict) -> bool:
        """Every physical programme also ran last year and the college is near level, so a
        spike planted here is the only thing that makes it grow."""
        aid = inst["aicte_permanent_id"]
        if self.admitted_last_year(aid) < 40:
            return False
        if any(
            p["mode"] == "PHYSICAL" and approved_intake(p, self.last_year) is None
            for p in inst["programmes"]
        ):
            return False
        return self.growth(aid) <= STABLE_GROWTH

    def plant(self) -> list[dict]:
        """Spike and share colleges; returns the rows added (to be settled)."""
        self.history = self.build_history()
        busy = self.busy()
        candidates = [i for i in self.w.institutions if i["aicte_permanent_id"] not in busy]
        stable = [i for i in candidates if self.stable(i)]

        def reach(inst: dict) -> float:
            room = sum(n for _, n in self.regular_room(inst))
            return min(self.growth(inst["aicte_permanent_id"], room), MAX_GROWTH)

        ranked = sorted(stable, key=lambda i: (-reach(i), i["aicte_permanent_id"]))
        for inst in ranked[: self.cfg.get("admission_spike", 0)]:
            self.plant_spike(inst)
        private = [
            i for i in candidates
            if i["type"] == "PRIVATE_SELF_FINANCED"
            and i["aicte_permanent_id"] not in self.colleges
            and len(self.first_years(i["aicte_permanent_id"])) >= 40
        ]  # fmt: skip
        k = min(self.cfg.get("nri_management_share", 0), len(private))
        for inst in self.rng.sample(private, k):
            self.plant_share(inst)
        for rec in self.w.ground_truth:
            if rec["anomaly_type"] == "GHOST_RING":
                rec.update(expected_flag=None, severity_expected=None)
                rec["expected_signal"] = "GHOST_RING"
        return self.new_rows

    def model_features(self, aid: str) -> dict[str, float]:
        """admission_growth, nri_share and management_share as ENGINES 17.11 defines them."""
        rows = self.w.rows_by_inst[aid]
        first = [r for r in rows if r["year_of_study"] == 1]
        second = sum(r["year_of_study"] == 2 for r in rows)
        routes = [r["admission_route"] for r in first]
        n = len(first) or 1
        return {
            "admission_growth": round(len(first) / second, 3) if second else 0.0,
            "nri_share": round(routes.count("NRI") / n, 3),
            "management_share": round((routes.count("MANAGEMENT") + routes.count("SPOT")) / n, 3),
        }

    def peers(self) -> dict[str, float]:
        """Median of every feature over the colleges the model scores, the planted left out."""
        values: dict[str, list[float]] = {}
        for inst in self.w.institutions:
            aid = inst["aicte_permanent_id"]
            if aid in self.colleges or len(self.w.rows_by_inst[aid]) < MIN_RECORDS:
                continue
            for name, value in self.model_features(aid).items():
                values.setdefault(name, []).append(value)
        return {name: round(statistics.median(v), 3) for name, v in values.items()}

    def record(self, aid: str, features: list[str], note: str, **extra) -> None:
        self.planter.record(
            "ANOMALY", [],
            expected_flag=None, institution_ids=[aid], programme_code=None,
            expected_signal="ANOMALY", features=features, values=self.model_features(aid),
            peer_medians=self.peers(), first_years=len(self.first_years(aid)),
            academic_year=self.w.cfg.academic_year, note=note, **extra,
        )  # fmt: skip

    def peer_median(self, feature) -> float:
        values = [
            feature(i["aicte_permanent_id"]) for i in self.w.institutions
            if i["aicte_permanent_id"] not in self.colleges
            and self.admitted_last_year(i["aicte_permanent_id"])
        ]  # fmt: skip
        return statistics.median(values) if values else 0.0

    def plant_spike(self, inst: dict) -> None:
        w = self.w
        aid = inst["aicte_permanent_id"]
        added = []
        budget = int(
            MAX_GROWTH * self.admitted_last_year(aid)
            - self.growth(aid) * self.admitted_last_year(aid)
        )
        with w.using_rng(self.rng):
            for prog, room in self.regular_room(inst):
                n = max(0, min(room, budget - len(added)))
                for route in w.regular_routes(inst, n):
                    added.append(w.new_student(inst, prog, 1, route))
        self.new_rows += added
        self.colleges.add(aid)
        growth = self.growth(aid)
        last = self.admitted_last_year(aid)
        self.record(
            aid, [FEATURE_GROWTH],
            f"{len(self.first_years(aid))} first-years against {last} admitted last year "
            f"({growth:.2f} times, like for like); every admission is inside the approved "
            "intake.",
            admitted_last_year=last, growth_like_for_like=round(growth, 2),
            added_rows=len(added),
        )  # fmt: skip

    def plant_share(self, inst: dict) -> None:
        w = self.w
        aid = inst["aicte_permanent_id"]
        leaving = w.leaving_rows()
        for prog in inst["programmes"]:
            if prog["mode"] != "PHYSICAL":
                continue
            rows = [
                r for r in self.first_years(aid)
                if r["programme_code"] == prog["code"] and not r["_tags"]
                and id(r) not in leaving
            ]  # fmt: skip
            for row in rows:
                route = row["admission_route"]
                if route == "SPOT" or (route == "COUNSELLING" and self.rng.random() < SHARE_MOVE):
                    w.set_route(row, inst, "MANAGEMENT")
            free = w.room(aid, prog, 1, "NRI")
            movable = [r for r in rows if r["admission_route"] == "MANAGEMENT"]
            for row in movable[: max(0, free)]:
                w.set_route(row, inst, "NRI")
        self.colleges.add(aid)
        value = self.share(self.first_years(aid))
        self.record(
            aid, ["management_share", "nri_share"],
            f"{value:.0%} of its first-years came by the NRI or management route; every "
            "admission is inside its seat pool.",
        )  # fmt: skip
