"""Approval versions in institutions.json, autonomous colleges and the issuer of ABC credits."""

from collections import Counter

from datagen.config import load_datagen_config

ABC, XYZ = "1-ABC-0001", "1-XYZ-0002"


def test_every_approval_lists_its_versions_with_the_current_intake(small):
    revised = 0
    total = 0
    for inst in small.json("institutions.json")["institutions"]:
        for prog in inst["programmes"]:
            for approval in prog["approvals"]:
                total += 1
                versions = approval["versions"]
                year = approval["academic_year"]
                assert [v["version"] for v in versions] == list(range(1, len(versions) + 1))
                assert approval["approved_intake"] == versions[-1]["approved_intake"]
                assert versions[0]["effective_from"] == f"{year[:4]}-03-15"
                assert versions[0]["source"] == f"AICTE EoA {year}"
                if len(versions) == 2:
                    revised += 1
                    v1, v2 = versions
                    assert v2["effective_from"] == f"{year[:4]}-05-20"
                    assert v2["source"] == f"AICTE EoA {year}, revised"
                    assert v1["approved_intake"] < v2["approved_intake"]
                assert len(versions) <= 2
    assert 0.05 <= revised / total <= 0.15


def test_abc_cse_2026_27_was_revised_from_90_to_120_before_admissions(small):
    abc = small.institutions()[ABC]
    cse = next(p for p in abc["programmes"] if p["code"] == "CSE")
    approval = next(a for a in cse["approvals"] if a["academic_year"] == "2026-27")
    assert approval == {
        "academic_year": "2026-27",
        "approved_intake": 120,
        "versions": [
            {"version": 1, "approved_intake": 90, "effective_from": "2026-03-15",
             "source": "AICTE EoA 2026-27"},
            {"version": 2, "approved_intake": 120, "effective_from": "2026-05-20",
             "source": "AICTE EoA 2026-27, revised"},
        ],
    }  # fmt: skip
    first_years = [r for r in small.upload(ABC) if r["programme_code"] == "CSE"]
    first_years = [r for r in first_years if r["year_of_study"] == "1"]
    assert len(first_years) == 132
    assert min(r["admission_date"] for r in first_years) > "2026-05-20"


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
        issuer = (credit["issuer"], credit["issuer_name"])
        if inst["autonomous"]:
            kinds["self"] += 1
            assert issuer == (inst["aicte_permanent_id"], inst["name"])
        else:
            kinds["university"] += 1
            code = inst["university_code"]
            assert issuer == (code, universities[code])
    assert kinds["self"] and kinds["university"]
    xyz = {c["issuer"] for c in small.jsonl("abc_credits.jsonl")
           if college_of.get(c["apaar_id"]) == XYZ}  # fmt: skip
    assert xyz == {XYZ}
