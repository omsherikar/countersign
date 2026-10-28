"""notice_replies.jsonl: the planned answer of every initial upload row to its notice."""

import re
from collections import Counter

from datagen.cli import generate
from datagen.notices import held_back

FIELDS = ["file", "row_no", "reply", "channel", "comment", "reply_after_days"]
ABC_FILE = "uploads/1-ABC-0001_2026-27.csv"
DEMO_APAAR = "123456784417"
APAAR = re.compile(r"[0-9]{12}")
# Rows of these records are legitimate students; they answer like any clean row.
LEGITIMATE = {"CONSENT_REFUSED_NO_APAAR"}


def replies(gen) -> list[dict]:
    return gen.lines("notice_replies.jsonl")


def by_row(gen) -> dict[tuple[str, int], dict]:
    return {(r["file"], r["row_no"]): r for r in replies(gen)}


def usable_apaar(row: dict) -> bool:
    return bool(APAAR.fullmatch(row["apaar_id"])) and row["consent_status"] == "LINKED"


def referenced_rows(gen, skip: set[str] = frozenset()) -> set[tuple[str, int]]:
    """Initial upload rows any ground-truth record points at (update rows by their initial)."""
    out = set()
    for rec in gen.json("ground_truth.json"):
        if rec["anomaly_type"] in skip:
            continue
        for row in rec["rows"]:
            out.add((row["file"], row["row_no"]))
            if "initial_file" in row:
                out.add((row["initial_file"], row["initial_row_no"]))
    return out


def test_one_line_per_initial_upload_row_in_file_order(small):
    expected = []
    for aid in sorted(small.institutions()):
        name = f"uploads/{aid}_2026-27.csv"
        expected += [(name, n) for n in range(2, len(small.file(name)) + 2)]
    lines = replies(small)
    assert [(r["file"], r["row_no"]) for r in lines] == expected
    for r in lines:
        assert list(r) == FIELDS
        assert r["reply"] in {"YES", "NO", "NONE"}
        assert r["channel"] in {"DIGILOCKER", "EMAIL"}
        assert r["comment"] is None or (isinstance(r["comment"], str) and r["comment"])
        assert isinstance(r["reply_after_days"], int) and 0 <= r["reply_after_days"] <= 29
        if r["reply"] == "NONE":
            assert r["comment"] is None and r["reply_after_days"] == 0
    assert not any("_update" in r["file"] for r in lines)


def test_every_will_deny_row_answers_no(small):
    records = [r for r in small.json("ground_truth.json") if r["anomaly_type"] == "STUDENT_DENIED"]
    assert len(records) == 8
    deny = set()
    for rec in records:
        assert rec["will_deny"] is True
        assert rec["rows"] and all({"file", "row_no"} <= set(row) for row in rec["rows"])
        deny |= {(row["file"], row["row_no"]) for row in rec["rows"]}
    lines = by_row(small)
    registry = {r["apaar_id"] for r in small.jsonl("apaar_registry.jsonl")}
    for key in deny:
        reply, row = lines[key], small.row(*key)
        assert reply["reply"] == "NO", key
        on_digilocker = usable_apaar(row) and row["apaar_id"] in registry
        assert reply["channel"] == ("DIGILOCKER" if on_digilocker else "EMAIL")
        assert 0 <= reply["reply_after_days"] <= 7
    assert {k for k, r in lines.items() if r["reply"] == "NO"} == deny

    comments = [lines[k]["comment"] for k in deny if lines[k]["comment"]]
    assert len(comments) == 3
    for text in comments:
        assert len(text) <= 120 and "—" not in text and "–" not in text
    not_me = next(r for r in records if r.get("scenario") == "not_me")["rows"][0]
    assert lines[(not_me["file"], not_me["row_no"])]["comment"] == "I never joined this college."


def test_live_demo_notices_stay_unanswered(small):
    lines = by_row(small)
    ravi = small.row(ABC_FILE, 2)
    assert (ravi["name"], ravi["apaar_id"]) == ("Ravi Kumar Sharma", DEMO_APAAR)
    dup = next(r for r in small.json("ground_truth.json") if r.get("scenario") == "demo_student")
    rk = next(row for row in dup["rows"] if row["row_no"] != 2)
    assert rk["name"] == "R. K. Sharma"

    unanswered = small.json("manifest.json")["demo_unanswered_notices"]
    assert [(u["role"], u["file"], u["row_no"]) for u in unanswered[:2]] == [
        ("DEMO_STUDENT", ABC_FILE, 2),
        ("DEMO_STUDENT_DUPLICATE", ABC_FILE, rk["row_no"]),
    ]
    assert len(unanswered) == 3
    second = unanswered[2]
    assert second["role"] == "SECOND_DEMO_NOTICE" and second["file"] == ABC_FILE
    row = small.row(ABC_FILE, second["row_no"])
    assert second["name"] == row["name"] and second["apaar_id"] == row["apaar_id"]
    assert row["programme_code"] == "CSE" and row["year_of_study"] == "1"
    assert row["admission_route"] == "COUNSELLING"
    assert usable_apaar(row) and row["email"] and row["status"] == ""
    registry = {r["apaar_id"] for r in small.jsonl("apaar_registry.jsonl")}
    assert row["apaar_id"] in registry
    assert (ABC_FILE, second["row_no"]) not in referenced_rows(small)
    for u in unanswered:
        assert lines[(u["file"], u["row_no"])]["reply"] == "NONE"
    assert small.summary["demo_unanswered_notices"] == unanswered


def test_about_seventy_percent_of_clean_rows_answer_yes(small):
    lines = replies(small)
    planted = referenced_rows(small, skip=LEGITIMATE)
    demo = {
        (u["file"], u["row_no"]) for u in small.json("manifest.json")["demo_unanswered_notices"]
    }
    clean = [r for r in lines if (r["file"], r["row_no"]) not in planted | demo]
    share = sum(r["reply"] == "YES" for r in clean) / len(clean)
    assert 0.67 <= share <= 0.73, share
    for r in lines:
        if (r["file"], r["row_no"]) in planted and r["reply"] == "YES":
            raise AssertionError(f"a planted row answers YES: {r}")

    registry = {r["apaar_id"] for r in small.jsonl("apaar_registry.jsonl")}
    channels = Counter()
    for r in lines:
        row = small.row(r["file"], r["row_no"])
        if r["channel"] == "DIGILOCKER":
            assert usable_apaar(row) and row["apaar_id"] in registry, r
        if r["reply"] == "YES":
            channels[r["channel"]] += 1
            assert r["comment"] is None
    assert channels["DIGILOCKER"] and channels["EMAIL"]

    counts = small.json("manifest.json")["counts"]
    tally = Counter(r["reply"] for r in lines)
    assert counts["notice_replies"] == len(lines)
    assert (counts["notice_replies_yes"], counts["notice_replies_no"]) == (tally["YES"], 8)
    assert counts["notice_replies_none"] == tally["NONE"]
    assert small.summary["counts"]["notice_replies"] == len(lines)


def test_same_seed_same_replies_other_seed_different(small, tmp_path):
    again = tmp_path / "again"
    generate("small", 42, again, xlsx=False)
    for name in ("notice_replies.jsonl", "graduates.jsonl"):
        assert (again / name).read_bytes() == (small.path / name).read_bytes(), name
    other = tmp_path / "other"
    generate("small", 7, other, xlsx=False)
    for name in ("notice_replies.jsonl", "graduates.jsonl"):
        assert (other / name).read_bytes() != (small.path / name).read_bytes(), name


def test_rows_the_api_would_reject_get_no_line():
    def row(name, apaar="", consent="PENDING", passport="", mobile="9876500001"):
        return {
            "name": name, "dob": "2007-01-01", "mobile": mobile, "apaar_id": apaar,
            "consent_status": consent, "passport_no": passport,
        }  # fmt: skip

    rows = [
        row("Asha Rao", "123456780001", "LINKED"),
        row("Asha R", "123456780001", "LINKED"),  # same APAAR: DUPLICATE_IN_FILE
        row("Kiran Das", "123456780001", "PENDING"),  # APAAR not used without consent
        row("Omar Ali", passport="N1234567"),
        row("Omar Ali Khan", passport="n 1234567"),  # same passport
        row("Meena Iyer"),
        row("meena  iyer"),  # same name, DOB and mobile, no APAAR or passport
        row("Meena Iyer", mobile="9876500002"),
    ]
    assert held_back(rows) == {1, 4, 6}
