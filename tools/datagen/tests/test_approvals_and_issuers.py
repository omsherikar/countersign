"""Approval versions in institutions.json, autonomous colleges and the issuer of ABC credits."""

from collections import Counter

from datagen.config import load_datagen_config

ABC, XYZ = "1-ABC-0001", "1-XYZ-0002"


def test_every_approval_has_version_one_and_the_current_intake(small):
    revised = []
    for inst in small.json("institutions.json")["institutions"]:
        for prog in inst["programmes"]:
            for approval in prog["approvals"]:
                versions = approval["versions"]
                assert [v["version"] for v in versions] == list(range(1, len(versions) + 1))
                first = versions[0]
                year = approval["academic_year"]
                assert first["effective_from"] == f"{year[:4]}-05-15"
                assert first["source"] == f"AICTE approval {year} (sample approval data)"
                assert approval["approved_intake"] == versions[-1]["approved_intake"]
                dates = [v["effective_from"] for v in versions]
                assert dates == sorted(dates)
                if len(versions) > 1:
                    revised.append((inst["aicte_permanent_id"], prog["code"], year))
    assert revised == [(ABC, "IT", "2026-27")]


def test_abc_it_2026_27_is_raised_mid_year_after_admissions(small):
    abc = small.institutions()[ABC]
    it = next(p for p in abc["programmes"] if p["code"] == "IT")
    approval = next(a for a in it["approvals"] if a["academic_year"] == "2026-27")
    v1, v2 = approval["versions"]
    assert (v1["approved_intake"], v2["approved_intake"]) == (60, 90)
    assert approval["approved_intake"] == 90
    assert v2["effective_from"] == "2026-10-21" and "60 to 90" in v2["source"]
    # The first-years were admitted against version 1, before the revision took effect.
    first_years = [r for r in small.upload(ABC) if r["programme_code"] == "IT"]
    first_years = [r for r in first_years if r["year_of_study"] == "1"]
    assert len(first_years) == 60
    assert max(r["admission_date"] for r in first_years) < v2["effective_from"]


def test_about_thirty_percent_of_colleges_are_autonomous(small):
    insts = small.institutions()
    share = load_datagen_config()["autonomous_share"]
    autonomous = {aid for aid, i in insts.items() if i["autonomous"]}
    assert len(autonomous) == int(len(insts) * share + 0.5)
    assert XYZ in autonomous and ABC not in autonomous
    assert all(i["autonomous"] for i in insts.values() if i["type"] == "DEEMED")


def test_credits_name_their_issuer(small):
    insts = small.institutions()
    universities = {u["code"]: u["name"] for u in small.json("institutions.json")["universities"]}
    colleges: dict[str, set[str]] = {}
    for aid, rows in small.all_uploads().items():
        for row in rows:
            if row["apaar_id"]:
                colleges.setdefault(row["apaar_id"], set()).add(aid)
    # A planted cross-college duplicate holds one APAAR at two colleges; skip those.
    college_of = {apaar: next(iter(c)) for apaar, c in colleges.items() if len(c) == 1}
    kinds = Counter()
    for credit in small.jsonl("abc_credits.jsonl"):
        if credit["apaar_id"] not in college_of:
            continue
        inst = insts[college_of[credit["apaar_id"]]]
        issuer = credit["issuer"]
        kinds[issuer["type"]] += 1
        if inst["autonomous"]:
            assert issuer == {
                "type": "INSTITUTION",
                "code": inst["aicte_permanent_id"],
                "name": inst["name"],
            }
        else:
            code = inst["university_code"]
            assert issuer == {"type": "UNIVERSITY", "code": code, "name": universities[code]}
    assert kinds["INSTITUTION"] and kinds["UNIVERSITY"]
    xyz = {c["issuer"]["code"] for c in small.jsonl("abc_credits.jsonl")
           if college_of.get(c["apaar_id"]) == XYZ}  # fmt: skip
    assert xyz == {XYZ}
