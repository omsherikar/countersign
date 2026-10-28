"""Planted anomalies and the named demo scenarios, each recorded in ground truth.

Ground-truth records follow API_CONTRACT section E (`anomaly_type`, `institution_aicte_id`,
`programme_code`, `student_refs`, `expected_flag`, `note`) and add `severity_expected`,
`institution_aicte_ids` and `rows` (file + row_no per referenced upload row) so every
reference can be resolved mechanically.
"""

from __future__ import annotations

from . import names
from .institutions import ABC_ID, XYZ_ID, approved_intake
from .students import World

SEVERITY = {
    "EXCESS_ADMISSION": "HIGH",
    "QUOTA_BREACH": "MEDIUM",
    "DUPLICATE_WITHIN_UPLOAD": "MEDIUM",
    "DUPLICATE_CROSS_INSTITUTION": "HIGH",
    "DUAL_ENROLMENT_ALLOWED": "LOW",
    "GHOST_RING": "HIGH",
    "INVALID_APAAR": "MEDIUM",
    "NO_ACADEMIC_ACTIVITY": "MEDIUM",
    "STUDENT_DENIED": "HIGH",
    "NAME_MISMATCH": "MEDIUM",
}


def is_physical(row: dict) -> bool:
    return row["_prog"]["mode"] == "PHYSICAL"


def is_linked(row: dict) -> bool:
    return row["consent_status"] == "LINKED" and bool(row["apaar_id"])


def clean_linked_physical(row: dict) -> bool:
    return is_linked(row) and is_physical(row)


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
        **extra,
    ) -> dict:
        severity = SEVERITY.get(expected_flag) if expected_flag else None
        for row in rows:
            row["_tags"].append(anomaly_type)
        rec = {
            "anomaly_type": anomaly_type,
            "expected_flag": expected_flag,
            "severity_expected": severity,
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

    def pick_programme(self, predicate=None, exclude_demo: bool = True):
        candidates = []
        for inst in self.w.institutions:
            for prog in inst["programmes"]:
                key = (inst["aicte_permanent_id"], prog["code"])
                if key in self.used_programmes or prog["mode"] != "PHYSICAL":
                    continue
                if exclude_demo and key == (ABC_ID, "CSE"):
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
        row = self.w.base_row(inst, prog, src["year_of_study"], src["_adm_year"])
        for key in (
            "apaar_id", "name", "dob", "gender", "mobile", "email", "address", "nationality",
            "passport_no", "category", "consent_status", "_group",
        ):  # fmt: skip
            row[key] = src[key]
        row["admission_route"] = "MANAGEMENT"
        row["counselling_ref"] = ""
        row.update(overrides)
        return self.w.add_row(row)

    def extra_row(self, inst: dict, prog: dict, year_of_study: int = 1) -> dict:
        row = self.w.new_student(inst, prog, year_of_study, "MANAGEMENT")
        return row

    # ----------------------------------------------------------- scenarios

    def plant_named_scenarios(self) -> None:
        w = self.w
        abc = w.inst_by_id[ABC_ID]
        cse = w.programme(ABC_ID, "CSE")
        ravi = next(r for r in w.rows_by_inst[ABC_ID] if "DEMO_STUDENT" in r["_tags"])

        # 1. "Ravi Kumar Sharma" / "R. K. Sharma": same DOB, mobile and email, no APAAR yet.
        dup = self.copy_row(
            ravi, abc, cse, name=names.with_initials(ravi["name"]), apaar_id="",
            consent_status="PENDING",
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

        # 2. ABC College CSE 2026-27: approved 120, uploaded 132 first-years (11 more + the dup).
        extras = [self.extra_row(abc, cse) for _ in range(11)]
        self.used_programmes.add((ABC_ID, "CSE"))
        self.record(
            "EXCESS_ADMISSION", extras + [dup],
            expected_flag="EXCESS_ADMISSION", institution_ids=[ABC_ID], programme_code="CSE",
            approved_intake=120, admitted=w.y1_count[(ABC_ID, "CSE")], scenario="abc_cse_132",
            note="ABC College of Engineering uploaded 132 first-years against 120 approved "
            "CSE seats.",
        )  # fmt: skip
        assert w.y1_count[(ABC_ID, "CSE")] == 132

        # 3. Ghost ring: 40 students across three WEST colleges sharing four mobiles.
        ring_ids = [ABC_ID, w.institutions[3]["aicte_permanent_id"],
                    w.institutions[4]["aicte_permanent_id"]]  # fmt: skip
        self.plant_ring(ring_ids, size=40, shared_mobiles=4, scenario="ghost_ring_40",
                        exclude_programme=(ABC_ID, "CSE"))

        # 4. A second-year at XYZ with zero credits for two semesters.
        victim = w.pick_row(
            lambda r: r["_inst"] == XYZ_ID and r["year_of_study"] == 2 and is_linked(r)
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
            if row["admission_route"] in {"COUNSELLING", "TFW", "LATERAL"}:
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

    def plant_dual(self, src: dict, scenario: str | None = None) -> None:
        w = self.w
        odl = [
            (inst, prog)
            for inst in w.institutions
            for prog in inst["programmes"]
            if prog["mode"] != "PHYSICAL" and inst["aicte_permanent_id"] != src["_inst"]
        ]
        inst, prog = self.rng.choice(odl)
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

    def plant_excess(self) -> None:
        picked = self.pick_programme(
            lambda i, p: approved_intake(p, self.cfg.academic_year) >= 60
        )
        if not picked:
            return
        inst, prog = picked
        intake = approved_intake(prog, self.cfg.academic_year)
        inst_id = inst["aicte_permanent_id"]
        extra = self.rng.randint(3, max(3, intake // 8))
        needed = intake - self.w.y1_count.get((inst_id, prog["code"]), 0) + extra
        rows = [self.extra_row(inst, prog) for _ in range(needed)]
        self.record(
            "EXCESS_ADMISSION", rows,
            expected_flag="EXCESS_ADMISSION", institution_ids=[inst_id],
            programme_code=prog["code"], approved_intake=intake,
            admitted=self.w.y1_count[(inst_id, prog["code"])],
            note=f"{intake + extra} first-years uploaded against {intake} approved seats "
            f"in {prog['code']}.",
        )  # fmt: skip

    def plant_quota_nri(self) -> None:
        picked = self.pick_programme(
            lambda i, p: approved_intake(p, self.cfg.academic_year) >= 60
            and i["type"] in {"PRIVATE_SELF_FINANCED", "DEEMED"}
        )
        if not picked:
            return
        inst, prog = picked
        inst_id = inst["aicte_permanent_id"]
        intake = approved_intake(prog, self.cfg.academic_year)
        cap = self.w.pools(prog, intake).nri
        rows = [
            r for r in self.w.rows_by_inst[inst_id]
            if r["programme_code"] == prog["code"] and r["year_of_study"] == 1
        ]  # fmt: skip
        current = [r for r in rows if r["admission_route"] == "NRI"]
        target = cap + self.rng.randint(2, 5)
        converts = [
            r for r in rows
            if not r["_tags"] and r["admission_route"] in {"MANAGEMENT", "SPOT"}
        ]  # fmt: skip
        self.rng.shuffle(converts)
        converts = converts[: target - len(current)]
        for r in converts:
            r["admission_route"] = "NRI"
            r["category"] = "GENERAL"
        self.record(
            "QUOTA_BREACH", current + converts,
            expected_flag="QUOTA_BREACH", institution_ids=[inst_id], programme_code=prog["code"],
            seat_type="NRI", capacity=cap, admitted=len(current) + len(converts),
            note=f"{len(current) + len(converts)} NRI admissions against {cap} NRI seats "
            f"(5% of {intake}) in {prog['code']}.",
        )  # fmt: skip

    def plant_quota_international(self) -> None:
        picked = self.pick_programme(
            lambda i, p: approved_intake(p, self.cfg.academic_year) >= 60
            and i["type"] in {"PRIVATE_SELF_FINANCED", "DEEMED"}
            and self.w.pools(p, approved_intake(p, self.cfg.academic_year)).international > 0
        )
        if not picked:
            return
        inst, prog = picked
        inst_id = inst["aicte_permanent_id"]
        intake = approved_intake(prog, self.cfg.academic_year)
        cap = self.w.pools(prog, intake).international
        rows = [
            r for r in self.w.rows_by_inst[inst_id]
            if r["programme_code"] == prog["code"] and r["year_of_study"] == 1
        ]  # fmt: skip
        current = [r for r in rows if r["admission_route"] == "INTERNATIONAL"]
        target = cap + self.rng.randint(1, 3)
        converts = [
            r for r in rows
            if not r["_tags"] and r["admission_route"] in {"MANAGEMENT", "SPOT", "COUNSELLING"}
        ]  # fmt: skip
        self.rng.shuffle(converts)
        converts = converts[: target - len(current)]
        for r in converts:
            self.w.make_international(r)
            self.w.set_route(r, inst, "INTERNATIONAL")
        self.record(
            "QUOTA_BREACH", current + converts,
            expected_flag="QUOTA_BREACH", institution_ids=[inst_id], programme_code=prog["code"],
            seat_type="INTERNATIONAL", capacity=cap, admitted=len(current) + len(converts),
            note=f"{len(current) + len(converts)} international admissions against {cap} "
            f"supernumerary international seats in {prog['code']}.",
        )  # fmt: skip

    def plant_duplicate_within(self, variant: str) -> None:
        w = self.w

        def ok(r):
            if not clean_linked_physical(r):
                return False
            if r["_inst"] == ABC_ID and r["programme_code"] == "CSE":
                return False
            if variant == "MOHD" and r["_group"] != "muslim":
                return False
            if variant != "MOHD" and r["_group"] == "muslim":
                return False
            return w.headroom(r["_inst"], r["_prog"]) >= 1 or r["year_of_study"] > 1

        src = w.pick_row(ok)
        if src is None:
            return
        if variant == "INITIALS":
            alt = names.with_initials(src["name"])
        elif variant == "TRANSLITERATION":
            alt = names.transliteration_variant(src["name"])
        else:
            alt = names.mohd_variant(src["name"], self.rng)
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
        targets = [
            (inst, prog)
            for inst in w.institutions
            if inst["aicte_permanent_id"] != src["_inst"]
            for prog in inst["programmes"]
            if prog["mode"] == "PHYSICAL" and prog["level"] == level
            and (src["year_of_study"] > 1 or w.headroom(inst["aicte_permanent_id"], prog) >= 1)
            and approved_intake(prog, "2025-26" if src["year_of_study"] == 2 else "2026-27")
        ]  # fmt: skip
        if not targets:
            return
        inst, prog = self.rng.choice(targets)
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
            row["_registry"] = "absent"
        elif kind == "LONG":
            row["apaar_id"] = w.new_apaar() + self.rng.choice("0123456789")
            row["_registry"] = "absent"
        elif kind == "LETTERS":
            row["apaar_id"] = w.new_apaar()[:10] + "AB"
            row["_registry"] = "absent"
        else:  # UNKNOWN: well-formed but not in the registry
            row["apaar_id"] = w.new_apaar()
            row["_registry"] = "absent"
        self.record(
            "INVALID_APAAR", [row],
            expected_flag="INVALID_APAAR", institution_ids=[row["_inst"]],
            programme_code=row["programme_code"], kind=kind,
            note={
                "SHORT": "APAAR has 11 digits.",
                "LONG": "APAAR has 13 digits.",
                "LETTERS": "APAAR contains letters.",
                "UNKNOWN": "APAAR is well-formed but absent from the registry.",
            }[kind],
        )  # fmt: skip

    def plant_no_activity(self) -> None:
        row = self.w.pick_row(lambda r: clean_linked_physical(r) and r["year_of_study"] >= 2)
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
            self.plant_quota_nri()
        for _ in range(self.counts.get("QUOTA_BREACH_INTERNATIONAL", 0)):
            self.plant_quota_international()
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
