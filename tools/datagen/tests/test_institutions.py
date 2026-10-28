import random
import re

from datagen import geo, institutions
from datagen.config import Config

TYPES = {
    "GOVERNMENT", "GOVERNMENT_AIDED", "PRIVATE_SELF_FINANCED", "UNIVERSITY_DEPARTMENT", "DEEMED",
}  # fmt: skip
LEVELS = {"DIPLOMA", "UG", "PG", "POST_DIPLOMA"}
DISCIPLINES = {
    "ENGINEERING", "MANAGEMENT", "COMPUTER_APPLICATIONS", "PHARMACY", "ARCHITECTURE",
    "PLANNING", "DESIGN", "HOTEL_MANAGEMENT", "APPLIED_ARTS",
}  # fmt: skip


def build(size="small", seed=42):
    cfg = Config.build(size)
    return institutions.InstitutionBuilder(random.Random(seed), cfg).build()


def test_demo_institutions_are_fixed():
    insts = build()
    abc, xyz = insts[0], insts[1]
    assert abc["aicte_permanent_id"] == "1-ABC-0001"
    assert abc["name"] == "ABC College of Engineering"
    assert abc["state_code"] == "MH" and abc["_region"] == "WEST"
    assert abc["university_code"] == "MSTU"
    assert abc["type"] == "PRIVATE_SELF_FINANCED"
    cse = next(p for p in abc["programmes"] if p["code"] == "CSE")
    assert institutions.approved_intake(cse, "2026-27") == 120
    assert sum(institutions.approved_intake(p, "2026-27") for p in abc["programmes"]) == 540
    assert len(abc["programmes"]) == 6
    assert xyz["aicte_permanent_id"] == "1-XYZ-0002"
    assert xyz["name"] == "XYZ Institute of Technology"
    assert xyz["state_code"] == "TN" and xyz["_region"] == "SOUTH"


def test_counts_ids_and_enums():
    insts = build()
    assert len(insts) == 50
    ids = [i["aicte_permanent_id"] for i in insts]
    assert len(set(ids)) == 50
    assert all(re.fullmatch(r"1-\d{10}", i) for i in ids[2:])
    assert len({i["name"] for i in insts}) == 50
    assert len({i["_slug"] for i in insts}) == 50
    for inst in insts:
        assert inst["type"] in TYPES
        assert inst["_region"] == geo.REGION_OF_STATE[inst["state_code"]]
        assert inst["programmes"]
        codes = [p["code"] for p in inst["programmes"]]
        assert len(set(codes)) == len(codes)
        for p in inst["programmes"]:
            assert p["level"] in LEVELS and p["discipline"] in DISCIPLINES
            assert p["shift"] in {"FIRST", "SECOND"}
            assert p["mode"] in {"PHYSICAL", "ODL", "ONLINE"}
            years = [a["academic_year"] for a in p["approvals"]]
            assert "2026-27" in years
            assert all(a["approved_intake"] in institutions.INTAKE_LADDER for a in p["approvals"])
        if inst["type"] == "DEEMED":
            assert inst["university_code"] is None
        else:
            assert inst["university_code"]


def test_an_odl_programme_always_exists():
    insts = build()
    odl = [(i, p) for i in insts for p in i["programmes"] if p["mode"] in {"ODL", "ONLINE"}]
    assert odl
    assert any(i["aicte_permanent_id"] != "1-ABC-0001" for i, _ in odl)


def test_second_year_cohorts_possible():
    insts = build()
    with_prev = [
        p for i in insts for p in i["programmes"]
        if any(a["academic_year"] == "2025-26" for a in p["approvals"])
    ]  # fmt: skip
    assert len(with_prev) > 0.7 * sum(len(i["programmes"]) for i in insts)


def test_deterministic():
    assert build(seed=5) == build(seed=5)
    assert build(seed=5) != build(seed=6)


def test_public_shape_drops_internal_keys():
    pub = institutions.public_institution(build()[0])
    assert not any(k.startswith("_") for k in pub)
    assert set(pub) == {
        "aicte_permanent_id", "name", "type", "state_code", "university_code",
        "address_city", "established_year", "programmes",
    }  # fmt: skip
