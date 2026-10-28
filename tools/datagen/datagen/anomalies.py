"""Planted anomalies and the named demo scenarios, each recorded in ground truth.

Ground-truth records follow API_CONTRACT section E and A2.24 (`anomaly_type`,
`institution_aicte_id`, `programme_code`, `student_refs`, `expected_flag`, `note`) and add
`severity_expected`, `institution_aicte_ids` and `rows` (file + row_no per referenced upload
row) so every reference can be resolved mechanically.

Every case is planted so the rules in docs/ENGINES.md produce its flag as written: seat
cases overflow exactly the pool they name and their overflow rows are the last admitted;
renamed duplicates keep the blocking key and the mobile; registry names of a mismatch
score below 75. Rows nobody planted stay inside every pool.
"""

from __future__ import annotations

from . import names
from .institutions import ABC_ID, XYZ_ID, approved_intake
from .matching import match_names, name_key, normalise_name
from .students import World

SEVERITY = {
    "EXCESS_ADMISSION": "HIGH",
    "QUOTA_BREACH": "MEDIUM",
    "LATE_REFILL": "MEDIUM",
    "DUPLICATE_WITHIN_UPLOAD": "MEDIUM",
    "DUPLICATE_CROSS_INSTITUTION": "HIGH",
    "DUAL_ENROLMENT_ALLOWED": "LOW",
    "GHOST_RING": "HIGH",
    "INVALID_APAAR": "MEDIUM",
    "NO_ACADEMIC_ACTIVITY": "MEDIUM",
    "STUDENT_DENIED": "HIGH",
    "NAME_MISMATCH": "MEDIUM",
}
GOVERNMENT_TYPES = {"GOVERNMENT", "GOVERNMENT_AIDED", "UNIVERSITY_DEPARTMENT"}


def is_physical(row: dict) -> bool:
    return row["_prog"]["mode"] == "PHYSICAL"


def is_linked(row: dict) -> bool:
    return row["consent_status"] == "LINKED" and bool(row["apaar_id"])


def clean_linked_physical(row: dict) -> bool:
    return is_linked(row) and is_physical(row)


def quota_severity(seat_type: str, unseated: int) -> str:
    """ENGINES.md section 10: HIGH when an NRI or INTERNATIONAL pool is more than 2 over."""
    return "HIGH" if seat_type in {"NRI", "INTERNATIONAL"} and unseated > 2 else "MEDIUM"


class Planter:
    def __init__(self, world: World):
        self.w = world
        self.rng = world.rng
        self.cfg = world.cfg
        self.counts = world.cfg.anomalies
        self.used_programmes: set[tuple[str, str]] = set()

    # ---------------------------------------------------------------- record

    def record(
        self,
        anomaly_type: str,
        rows: list[dict],
        *,
        expected_flag: str | None,
        institution_ids: list[str],
        programme_code: str | None,
        note: str,
        severity: str | None = None,
        **extra,
    ) -> dict:
        if expected_flag and severity is None:
            severity = SEVERITY[expected_flag]
        for row in rows:
            row["_tags"].append(anomaly_type)
        rec = {
            "anomaly_type": anomaly_type,
            "expected_flag": expected_flag,
            "severity_expected": severity if expected_flag else None,
            "institution_aicte_id": institution_ids[0],
            "institution_aicte_ids": institution_ids,
            "programme_code": programme_code,
            "student_refs": [],
            "rows": [],
            "note": note,
            "_rows": rows,
        }
        rec.update(extra)
        self.w.ground_truth.append(rec)
        return rec

    # ---------------------------------------------------------------- picks

    def pick_programme(self, predicate=None):
        candidates = []
        for inst in self.w.institutions:
            for prog in inst["programmes"]:
                key = (inst["aicte_permanent_id"], prog["code"])
                if key in self.used_programmes or prog["mode"] != "PHYSICAL":
                    continue
                if key == (ABC_ID, "CSE"):
                    continue
                if approved_intake(prog, self.cfg.academic_year) is None:
                    continue
                if predicate and not predicate(inst, prog):
                    continue
                candidates.append((inst, prog))
        if not candidates:
            return None
        inst, prog = self.rng.choice(candidates)
        self.used_programmes.add((inst["aicte_permanent_id"], prog["code"]))
        return inst, prog

    def copy_row(self, src: dict, inst: dict, prog: dict, **overrides) -> dict:
        """The same person on a second row. Both rows share a DOB group so the identity
        checks keep their dates of birth equal."""
        row = self.w.base_row(inst, prog, src["year_of_study"], src["_adm_year"])
        for key in (
            "apaar_id", "name", "dob", "gender", "mobile", "email", "address", "nationality",
            "passport_no", "category", "consent_status", "_group",
        ):  # fmt: skip
            row[key] = src[key]
        row["admission_route"] = "MANAGEMENT"
        row["counselling_ref"] = ""
        src["_dob_group"] = src["_dob_group"] or src["_seq"]
        row["_dob_group"] = src["_dob_group"]
        row.update(overrides)
        return self.w.add_row(row)

    def extra_route(self, inst: dict) -> str:
        return "SPOT" if inst["type"] in GOVERNMENT_TYPES else "MANAGEMENT"

    def has_room(self, row: dict, inst: dict, prog: dict, route: str = "MANAGEMENT") -> bool:
        return self.w.room(inst["aicte_permanent_id"], prog, row["year_of_study"], route) >= 1

    def first_years(self, aicte_id: str, code: str) -> list[dict]:
        return sorted(self.w.cohort_rows(aicte_id, code, 1), key=lambda r: r["_seq"])

    # ----------------------------------------------------------- scenarios

    def plant_named_scenarios(self) -> None:
        w = self.w
        abc = w.inst_by_id[ABC_ID]
        cse = w.programme(ABC_ID, "CSE")
        ravi = next(r for r in w.rows_by_inst[ABC_ID] if "DEMO_STUDENT" in r["_tags"])

        # 1. "Ravi Kumar Sharma" / "R. K. Sharma": same DOB, mobile and email, no APAAR yet.
        dup = self.copy_row(
            ravi, abc, cse, name=names.with_initials(ravi["name"]), apaar_id="",
            consent_status="PENDING", _late=True,
        )  # fmt: skip
        ravi["_tags"].remove("DEMO_STUDENT")
        rec = self.record(
            "DUPLICATE_WITHIN_UPLOAD", [ravi, dup],
            expected_flag="DUPLICATE_WITHIN_UPLOAD", institution_ids=[ABC_ID],
            programme_code="CSE", variant="INITIALS", scenario="demo_student",
            note="Demo student listed twice in ABC College CSE: full name and initials, same DOB.",
        )  # fmt: skip
        ravi["_tags"].append("DEMO_STUDENT")
        rec["demo_student_apaar"] = ravi["apaar_id"]

        # 2. ABC College CSE 2026-27: approved 120 (REGULAR 114 + NRI 6, both full),
        # uploaded 132 first-years: 11 more plus the duplicate, admitted last, unseated.
        extras = [self.w.new_student(abc, cse, 1, "MANAGEMENT") for _ in range(11)]
        for row in extras:
            row["_late"] = True
        self.used_programmes.add((ABC_ID, "CSE"))
        counts = w.pool_counts(ABC_ID, "CSE", 1)
        pools = w.cohort_pools(cse, 1)
        self.record(
            "EXCESS_ADMISSION", extras + [dup],
            expected_flag="EXCESS_ADMISSION", institution_ids=[ABC_ID], programme_code="CSE",
            approved_intake=120, admitted=counts["REGULAR"] + counts["NRI"],
            unseated=counts["REGULAR"] - pools.regular, scenario="abc_cse_132",
            note="ABC College of Engineering uploaded 132 first-years against 120 approved "
            "CSE seats.",
        )  # fmt: skip
        w.seat_cases[(ABC_ID, "CSE")] = "REGULAR"
        assert w.y1_count[(ABC_ID, "CSE")] == 132 and counts["NRI"] == pools.nri

        # 3. Ghost ring: 40 students across three WEST colleges sharing four mobiles.
        ring_ids = [ABC_ID, w.institutions[3]["aicte_permanent_id"],
                    w.institutions[4]["aicte_permanent_id"]]  # fmt: skip
        self.plant_ring(ring_ids, size=40, shared_mobiles=4, scenario="ghost_ring_40",
                        exclude_programme=(ABC_ID, "CSE"))

        # 4. A second-year at XYZ with zero credits for two semesters.
        victim = w.pick_row(
            lambda r: r["_inst"] == XYZ_ID
            and r["year_of_study"] == 2
            and r["admission_route"] != "LATERAL"
            and is_linked(r)
        )
        victim["_credits"] = "zero"
        self.record(
            "NO_ACADEMIC_ACTIVITY", [victim],
            expected_flag="NO_ACADEMIC_ACTIVITY", institution_ids=[XYZ_ID],
            programme_code=victim["programme_code"], scenario="xyz_zero_credits",
            note="Second-year at XYZ Institute of Technology with 0 credits in both semesters "
            "of 2025-26.",
        )  # fmt: skip

        # 5. One demo student who will answer "No" to the enrolment notice.
        denier = w.pick_row(
            lambda r: r["_inst"] == ABC_ID and r["programme_code"] == "CSE"
            and r["year_of_study"] == 1 and is_linked(r) and r["admission_route"] == "COUNSELLING"
        )
        self.record(
            "STUDENT_DENIED", [denier],
            expected_flag="STUDENT_DENIED", institution_ids=[ABC_ID], programme_code="CSE",
            will_deny=True, scenario="not_me",
            note="Student replies 'No' to the DigiLocker notice; the demo scripts this reply.",
        )  # fmt: skip

        # 6. A legal dual enrolment: ABC B.Tech plus an ODL BCA elsewhere.
        src = w.pick_row(
            lambda r: r["_inst"] == ABC_ID and r["programme_code"] != "CSE"
            and r["_prog"]["level"] == "UG" and r["year_of_study"] == 1 and is_linked(r)
        )
        self.plant_dual(src, scenario="legal_dual_abc")

        # 7. Keep one ABC programme out of the seat cases: its update file refills it late.
        self.reserve_refill_programme(ABC_ID)

    def reserve_refill_programme(self, aicte_id: str) -> str | None:
        """The programme whose first-year REGULAR pool the college's update file refills:
        the one closest to full, so topping it up adds the fewest rows."""
        w = self.w
        best = None
        for prog in w.inst_by_id[aicte_id]["programmes"]:
            key = (aicte_id, prog["code"])
            if key in self.used_programmes or key in w.seat_cases or prog["mode"] != "PHYSICAL":
                continue
            pools = w.cohort_pools(prog, 1)
            if pools is None or not pools.regular:
                continue
            gap = pools.regular - w.pool_counts(aicte_id, prog["code"], 1)["REGULAR"]
            if best is None or gap < best[0]:
                best = (gap, prog["code"])
        if best is None:
            return None
        self.used_programmes.add((aicte_id, best[1]))
        w.refill_programmes[aicte_id] = best[1]
        return best[1]

    # ------------------------------------------------------------- planters

    def plant_ring(
        self, inst_ids: list[str], size: int, shared_mobiles: int, scenario: str | None = None,
        exclude_programme: tuple[str, str] | None = None,
    ) -> None:
        w = self.w
        per_college = [size // len(inst_ids)] * len(inst_ids)
        for i in range(size - sum(per_college)):
            per_college[i] += 1
        members: list[dict] = []
        for inst_id, k in zip(inst_ids, per_college, strict=True):
            def ok(r, inst_id=inst_id):
                if r["_inst"] != inst_id or r["year_of_study"] != 1 or not clean_linked_physical(r):
                    return False
                # Moving a counselled member to MANAGEMENT must keep it in the same pool.
                if w.route_pool(r["admission_route"]) != "REGULAR":
                    return False
                return exclude_programme != (r["_inst"], r["programme_code"])
            picked = w.pick_rows(k, ok)
            members.extend(picked)
        mobiles = [w.new_mobile() for _ in range(shared_mobiles)]
        state = w.inst_by_id[inst_ids[0]]["state_code"]
        addresses = [w.new_address(state) for _ in range(shared_mobiles)]
        emails = [w.new_email("admissions.desk") for _ in range(max(1, shared_mobiles // 2))]
        for i, row in enumerate(members):
            row["mobile"] = mobiles[i % len(mobiles)]
            row["address"] = addresses[i % len(addresses)]
            if self.rng.random() < 0.6:
                row["email"] = emails[i % len(emails)]
            if row["admission_route"] == "COUNSELLING":
                row["admission_route"] = "MANAGEMENT"
                row["counselling_ref"] = ""
                row["_roll_no"] = ""
                row["_round"] = 0
        self.record(
            "GHOST_RING", members,
            expected_flag="GHOST_RING", institution_ids=inst_ids, programme_code=None,
            shared_mobiles=mobiles, shared_addresses=addresses, scenario=scenario,
            note=f"{len(members)} students across {len(inst_ids)} colleges share "
            f"{len(mobiles)} mobile numbers and {len(addresses)} addresses.",
        )  # fmt: skip

    def target_with_room(self, src: dict, candidates: list[tuple[dict, dict]]):
        """A random (institution, programme) whose cohort has a seat for a copy of `src`."""
        self.rng.shuffle(candidates)
        return next((c for c in candidates if self.has_room(src, *c)), None)

    def plant_dual(self, src: dict, scenario: str | None = None) -> bool:
        w = self.w
        picked = self.target_with_room(src, [
            (inst, prog)
            for inst in w.institutions
            for prog in inst["programmes"]
            if prog["mode"] != "PHYSICAL" and inst["aicte_permanent_id"] != src["_inst"]
        ])  # fmt: skip
        if picked is None:
            return False
        inst, prog = picked
        twin = self.copy_row(src, inst, prog)
        self.record(
            "DUAL_ENROLMENT_ALLOWED", [src, twin],
            expected_flag="DUAL_ENROLMENT_ALLOWED",
            institution_ids=[src["_inst"], inst["aicte_permanent_id"]],
            programme_code=src["programme_code"], modes=["PHYSICAL", prog["mode"]],
            scenario=scenario,
            note=f"Same student in {src['programme_code']} (physical) and {prog['code']} "
            f"({prog['mode']}); permitted under UGC 2022 dual-degree rules.",
        )  # fmt: skip
        return True

    def plant_excess(self) -> None:
        """Fill the REGULAR pool, then admit `unseated` more: the REGULAR and NRI routes
        (what EXCESS_ADMISSION counts) end up above the approved intake."""
        w = self.w
        picked = self.pick_programme(lambda i, p: approved_intake(p, self.cfg.academic_year) >= 60)
        if not picked:
            return
        inst, prog = picked
        aid, code = inst["aicte_permanent_id"], prog["code"]
        intake = approved_intake(prog, self.cfg.academic_year)
        pools = w.cohort_pools(prog, 1)
        counts = w.pool_counts(aid, code, 1)
        extra = self.rng.randint(3, max(3, intake // 8))
        fill = pools.regular - counts["REGULAR"]
        overflow = intake + extra - counts["REGULAR"] - counts["NRI"] - fill
        route = self.extra_route(inst)
        for _ in range(fill):
            w.new_student(inst, prog, 1, route)
        rows = [w.new_student(inst, prog, 1, route) for _ in range(overflow)]
        for row in rows:
            row["_late"] = True
        w.seat_cases[(aid, code)] = "REGULAR"
        self.record(
            "EXCESS_ADMISSION", rows,
            expected_flag="EXCESS_ADMISSION", institution_ids=[aid], programme_code=code,
            approved_intake=intake, admitted=intake + extra, unseated=overflow,
            note=f"{intake + extra} first-years on REGULAR and NRI routes uploaded against "
            f"{intake} approved seats in {code}; {overflow} find no REGULAR seat.",
        )  # fmt: skip

    def plant_quota(self, seat_type: str) -> None:
        """Move first-years onto the NRI or INTERNATIONAL route until the pool is over its
        capacity. The moved rows with the highest sequence are admitted last and stay
        unseated; the REGULAR pool only shrinks, so no excess admission rides along."""
        w = self.w

        def fits(inst, prog):
            if approved_intake(prog, self.cfg.academic_year) < 60:
                return False
            if inst["type"] not in {"PRIVATE_SELF_FINANCED", "DEEMED"}:
                return False
            return seat_type == "NRI" or w.cohort_pools(prog, 1).international > 0

        for _ in range(20):
            picked = self.pick_programme(fits)
            if not picked or self.plant_quota_in(seat_type, *picked):
                return

    def plant_quota_in(self, seat_type: str, inst: dict, prog: dict) -> bool:
        w = self.w
        aid, code = inst["aicte_permanent_id"], prog["code"]
        pools = w.cohort_pools(prog, 1)
        capacity = pools.nri if seat_type == "NRI" else pools.international
        usable = pools.usable()[seat_type]
        current = [r for r in self.first_years(aid, code) if r["admission_route"] == seat_type]
        target = capacity + (
            self.rng.randint(2, 5) if seat_type == "NRI" else self.rng.randint(1, 3)
        )
        unseated = target - usable
        movable = [
            r for r in self.first_years(aid, code)
            if not r["_tags"] and r["admission_route"] in {"MANAGEMENT", "SPOT", "COUNSELLING"}
        ]  # fmt: skip
        movable.sort(key=lambda r: (r["admission_route"] == "COUNSELLING", r["_seq"]))
        need = target - len(current)
        if len(movable) < need:
            return False
        movable = movable[:need]
        movable.sort(key=lambda r: r["_seq"])
        overflow = movable[len(movable) - unseated :]
        for row in movable:
            if seat_type == "INTERNATIONAL":
                w.make_international(row)
            w.set_route(row, inst, seat_type)
        for row in overflow:
            row["_late"] = True
        w.seat_cases[(aid, code)] = seat_type
        words = "NRI" if seat_type == "NRI" else "international"
        self.record(
            "QUOTA_BREACH", overflow,
            expected_flag="QUOTA_BREACH", severity=quota_severity(seat_type, unseated),
            institution_ids=[aid], programme_code=code, seat_type=seat_type,
            capacity=capacity, admitted=target, unseated=unseated,
            approved_intake=pools.intake,
            note=f"{target} {words} admissions against {capacity} {words} seats in {code}; "
            f"{unseated} find no seat they may take.",
        )  # fmt: skip
        return True

    def plant_duplicate_within(self, variant: str) -> None:
        w = self.w

        def ok(r):
            if not clean_linked_physical(r):
                return False
            if r["_inst"] == ABC_ID and r["programme_code"] == "CSE":
                return False
            if variant == "MOHD":
                if r["_group"] != "muslim":
                    return False
                # Swapping one spelling of Mohammed for another keeps the first initial.
                if not normalise_name(r["name"]).startswith("mohammed "):
                    return False
            elif r["_group"] == "muslim":
                return False
            return self.has_room(r, w.inst_by_id[r["_inst"]], r["_prog"])

        for _ in range(50):
            src = w.pick_row(ok)
            if src is None:
                return
            if variant == "INITIALS":
                alt = names.with_initials(src["name"])
            elif variant == "TRANSLITERATION":
                alt = names.transliteration_variant(src["name"])
            else:
                alt = names.mohd_variant(src["name"], self.rng)
            # Rule A blocks on name_key and then compares with match_names; the copy must
            # pass both even without the shared mobile. A Devanagari spelling, recorded
            # for the demo, must read back to the same key.
            key = name_key(src["name"], src["dob"])
            spellings = [alt]
            if variant == "TRANSLITERATION":
                spellings.append(names.devanagari(src["name"]))
            if alt != src["name"] and all(
                name_key(s, src["dob"]) == key and match_names(s, src["name"]).score >= 90
                for s in spellings
            ):
                break
        else:
            return
        inst = w.inst_by_id[src["_inst"]]
        dup = self.copy_row(
            src, inst, src["_prog"], name=alt, apaar_id="", consent_status="PENDING"
        )
        extra = {}
        if variant == "TRANSLITERATION":
            extra["devanagari"] = names.devanagari(src["name"])
        self.record(
            "DUPLICATE_WITHIN_UPLOAD", [src, dup],
            expected_flag="DUPLICATE_WITHIN_UPLOAD", institution_ids=[src["_inst"]],
            programme_code=src["programme_code"], variant=variant,
            note=f"'{src['name']}' also listed as '{alt}' with the same DOB, mobile and email.",
            **extra,
        )  # fmt: skip

    def plant_duplicate_cross(self) -> None:
        w = self.w
        src = w.pick_row(lambda r: clean_linked_physical(r) and r["year_of_study"] <= 2)
        if src is None:
            return
        level = src["_prog"]["level"]
        picked = self.target_with_room(src, [
            (inst, prog)
            for inst in w.institutions
            if inst["aicte_permanent_id"] != src["_inst"]
            for prog in inst["programmes"]
            if prog["mode"] == "PHYSICAL" and prog["level"] == level
        ])  # fmt: skip
        if picked is None:
            return
        inst, prog = picked
        twin = self.copy_row(src, inst, prog)
        self.record(
            "DUPLICATE_CROSS_INSTITUTION", [src, twin],
            expected_flag="DUPLICATE_CROSS_INSTITUTION",
            institution_ids=[src["_inst"], inst["aicte_permanent_id"]],
            programme_code=src["programme_code"],
            note=f"Same APAAR enrolled full-time at two colleges ({src['programme_code']} "
            f"and {prog['code']}).",
        )  # fmt: skip

    def plant_invalid_apaar(self, kind: str) -> None:
        w = self.w
        row = w.pick_row(lambda r: clean_linked_physical(r) and r["_inst"] != ABC_ID)
        if row is None:
            return
        if kind == "SHORT":
            row["apaar_id"] = w.new_apaar()[:11]
        elif kind == "LONG":
            row["apaar_id"] = w.new_apaar() + self.rng.choice("0123456789")
        elif kind == "LETTERS":
            row["apaar_id"] = w.new_apaar()[:10] + "AB"
        else:  # UNKNOWN: well-formed but not in the registry
            row["apaar_id"] = w.new_apaar()
        row["_registry"] = "absent"
        self.record(
            "INVALID_APAAR", [row],
            expected_flag="INVALID_APAAR", severity="HIGH" if kind == "UNKNOWN" else "MEDIUM",
            institution_ids=[row["_inst"]], programme_code=row["programme_code"], kind=kind,
            note={
                "SHORT": "APAAR has 11 digits.",
                "LONG": "APAAR has 13 digits.",
                "LETTERS": "APAAR contains letters.",
                "UNKNOWN": "APAAR is well-formed but absent from the registry.",
            }[kind],
        )  # fmt: skip

    def plant_no_activity(self) -> None:
        # A year-2 lateral entrant joined this year: the api treats STUDYING as NA for them,
        # so planting "no activity" there would be a false ground truth.
        row = self.w.pick_row(
            lambda r: clean_linked_physical(r)
            and r["year_of_study"] >= 2
            and not (r["admission_route"] == "LATERAL" and r["year_of_study"] == 2)
        )
        if row is None:
            return
        row["_credits"] = "none"
        self.record(
            "NO_ACADEMIC_ACTIVITY", [row],
            expected_flag="NO_ACADEMIC_ACTIVITY", institution_ids=[row["_inst"]],
            programme_code=row["programme_code"],
            note=f"Year {row['year_of_study']} student with no ABC credit record at all.",
        )  # fmt: skip

    def plant_denied(self) -> None:
        row = self.w.pick_row(clean_linked_physical)
        if row is None:
            return
        self.record(
            "STUDENT_DENIED", [row],
            expected_flag="STUDENT_DENIED", institution_ids=[row["_inst"]],
            programme_code=row["programme_code"], will_deny=True,
            note="Student will answer 'No' to the enrolment notice.",
        )  # fmt: skip

    def plant_name_mismatch(self) -> None:
        w = self.w
        row = w.pick_row(lambda r: clean_linked_physical(r) and r["_group"] != "international")
        if row is None:
            return
        other = names.materially_different(row["name"], w.names, row["_group"], row["gender"])
        row["_registry"] = "mismatch"
        row["_registry_name"] = other
        self.record(
            "NAME_MISMATCH", [row],
            expected_flag="NAME_MISMATCH", institution_ids=[row["_inst"]],
            programme_code=row["programme_code"], registry_name=other,
            note=f"Uploaded as '{row['name']}'; the APAAR registry holds '{other}' for this id.",
        )  # fmt: skip

    def plant_refused_consent(self) -> None:
        w = self.w
        row = w.pick_row(lambda r: r["consent_status"] == "REFUSED" and is_physical(r))
        if row is None:
            row = w.pick_row(clean_linked_physical)
            if row is None:
                return
            row["apaar_id"] = ""
            row["consent_status"] = "REFUSED"
        self.record(
            "CONSENT_REFUSED_NO_APAAR", [row],
            expected_flag=None, institution_ids=[row["_inst"]],
            programme_code=row["programme_code"],
            note="No APAAR because consent was refused; lawful (DPDP), must not be flagged.",
        )  # fmt: skip

    # --------------------------------------------------------------- driver

    def plant_all(self) -> None:
        planted: dict[str, int] = {}
        if self.cfg.scenarios:
            self.plant_named_scenarios()
            for rec in self.w.ground_truth:
                planted[rec["anomaly_type"]] = planted.get(rec["anomaly_type"], 0) + 1

        def remaining(key: str, anomaly_type: str) -> int:
            return max(0, self.counts.get(key, 0) - planted.get(anomaly_type, 0))

        for _ in range(remaining("EXCESS_ADMISSION", "EXCESS_ADMISSION")):
            self.plant_excess()
        for _ in range(self.counts.get("QUOTA_BREACH_NRI", 0)):
            self.plant_quota("NRI")
        for _ in range(self.counts.get("QUOTA_BREACH_INTERNATIONAL", 0)):
            self.plant_quota("INTERNATIONAL")
        variants = ["INITIALS", "TRANSLITERATION", "MOHD"]
        for i in range(remaining("DUPLICATE_WITHIN_UPLOAD", "DUPLICATE_WITHIN_UPLOAD")):
            self.plant_duplicate_within(variants[i % 3])
        for _ in range(self.counts.get("DUPLICATE_CROSS_INSTITUTION", 0)):
            self.plant_duplicate_cross()
        for _ in range(remaining("DUAL_ENROLMENT_ALLOWED", "DUAL_ENROLMENT_ALLOWED")):
            src = self.w.pick_row(
                lambda r: clean_linked_physical(r) and r["year_of_study"] == 1
            )
            if src:
                self.plant_dual(src)
        lo_size, hi_size = self.cfg.ghost_ring["size"]
        lo_c, hi_c = self.cfg.ghost_ring["colleges"]
        lo_m, hi_m = self.cfg.ghost_ring["shared_mobiles"]
        ids = [i["aicte_permanent_id"] for i in self.w.institutions]
        for _ in range(remaining("GHOST_RING", "GHOST_RING")):
            colleges = self.rng.sample(ids, self.rng.randint(lo_c, hi_c))
            self.plant_ring(
                colleges, size=self.rng.randint(lo_size, hi_size),
                shared_mobiles=self.rng.randint(lo_m, hi_m),
            )
        kinds = ["UNKNOWN", "SHORT", "UNKNOWN", "LONG", "UNKNOWN", "LETTERS"]
        for i in range(self.counts.get("INVALID_APAAR", 0)):
            self.plant_invalid_apaar(kinds[i % len(kinds)])
        for _ in range(remaining("NO_ACADEMIC_ACTIVITY", "NO_ACADEMIC_ACTIVITY")):
            self.plant_no_activity()
        for _ in range(remaining("STUDENT_DENIED", "STUDENT_DENIED")):
            self.plant_denied()
        for _ in range(self.counts.get("NAME_MISMATCH", 0)):
            self.plant_name_mismatch()
        for _ in range(self.counts.get("CONSENT_REFUSED_NO_APAAR", 0)):
            self.plant_refused_consent()
