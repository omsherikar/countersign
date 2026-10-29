"""The two detectors as pure functions: rings over contact hashes, the forest over features."""

from __future__ import annotations

import uuid

from app.signals import anomaly, rings
from app.signals.anomaly import FEATURES, InstitutionFeatures
from app.signals.rings import Member

A, B, C = (uuid.UUID(int=i) for i in (1, 2, 3))


def member(student: int, college: uuid.UUID, *, mobile=None, email=None, address=None) -> Member:
    return Member(
        enrolment_id=uuid.UUID(int=10_000 + student),
        student_id=uuid.UUID(int=student),
        institution_id=college,
        mobile_hmac=mobile.encode() if mobile else None,
        email=email,
        address_hmac=address.encode() if address else None,
        mobile_last4=mobile[-4:] if mobile else None,
    )


def find(members):
    return rings.find_rings(members, min_cross=3, min_colleges=2, min_single=5)


def test_a_chain_of_shared_contacts_is_one_ring_across_colleges():
    members = [
        member(1, A, mobile="9800001234"),
        member(2, B, mobile="9800001234", address="1 Ring Road"),
        member(3, C, address="1 Ring Road", email="desk@example.com"),
        member(4, A, email="desk@example.com"),
        member(5, A, mobile="9811112222"),  # alone
    ]
    [ring] = find(members)
    assert ring.students == 4 and ring.institution_ids == {A, B, C}
    assert ring.shared == (
        ("MOBILE", "XXXXXX1234", 2),
        ("EMAIL", "d***@example.com", 2),
        ("ADDRESS", "Same address", 2),
    )
    names = {A: "ABC College", B: "PQR College", C: "XYZ College"}
    assert rings.summary(ring, names) == (
        "4 students across 3 colleges share 1 mobile number, 1 email address and 1 address."
    )


def test_thresholds_two_across_colleges_or_four_in_one_are_not_rings():
    pair = [member(1, A, mobile="9800000001"), member(2, B, mobile="9800000001")]
    four = [member(10 + i, A, address="Hostel Block C") for i in range(4)]
    assert find(pair + four) == []
    five = [member(20 + i, B, address="Hostel Block D") for i in range(5)]
    [ring] = find(pair + four + five)
    assert ring.students == 5 and ring.institution_ids == {B}
    assert rings.summary(ring, {B: "PQR College"}) == "5 students at PQR College share 1 address."


def test_a_student_enrolled_twice_is_one_node_with_both_enrolments():
    twin = Member(uuid.UUID(int=99), uuid.UUID(int=1), B, b"9800000001", None, None, "0001")
    members = [
        member(1, A, mobile="9800000001"),
        twin,
        member(2, A, mobile="9800000001"),
        member(3, B, mobile="9800000001"),
    ]
    [ring] = find(members)
    assert ring.students == 3 and len(ring.members) == 4
    assert ring.shared == (("MOBILE", "XXXXXX0001", 3),)


def test_sharing_students_counts_any_contact_shared_with_someone_else():
    members = [
        member(1, A, email="Same@x.org".lower()),
        member(2, B, email="same@x.org"),
        member(3, A, email="own@x.org"),
    ]
    assert rings.sharing_students(members) == {uuid.UUID(int=1), uuid.UUID(int=2)}


def peers(n: int = 40) -> list[InstitutionFeatures]:
    out = []
    for i in range(n):
        wobble = (i % 5) / 100
        out.append(
            InstitutionFeatures(
                institution_id=uuid.UUID(int=1000 + i),
                records=30,
                values={
                    "admission_growth": 1.05 + wobble,
                    "nri_share": 0.04 + wobble / 4,
                    "management_share": 0.15 + wobble,
                    "contradiction_rate": 0.02 + wobble / 5,
                    "contact_sharing_rate": 0.0,
                },
            )
        )
    return out


def test_the_forest_finds_planted_colleges_and_says_which_features_stand_out():
    rows = peers()
    spike = uuid.UUID(int=1)
    share = uuid.UUID(int=2)
    rows[0] = InstitutionFeatures(spike, {**rows[0].values, "admission_growth": 3.1}, 50)
    rows[1] = InstitutionFeatures(
        share, {**rows[1].values, "nri_share": 0.35, "management_share": 0.5}, 30
    )
    found = anomaly.score(rows, contamination=0.05, n_estimators=200, random_state=0)
    assert {o.institution_id for o in found} == {spike, share}
    by_id = {o.institution_id: o for o in found}
    assert by_id[spike].standing_out == ["admission_growth"]
    assert set(by_id[share].standing_out) == {"nri_share", "management_share"}
    growth = by_id[spike].features[0]
    assert growth["name"] == "admission_growth" and growth["value"] == 3.1
    assert growth["peer_low"] <= growth["peer_median"] <= growth["peer_high"] < 3.1
    assert growth["robust_z"] >= 2 and [f["name"] for f in by_id[spike].features] == list(FEATURES)
    # deterministic for a given random_state
    again = anomaly.score(rows, contamination=0.05, n_estimators=200, random_state=0)
    assert [(o.institution_id, o.score) for o in again] == [
        (o.institution_id, o.score) for o in found
    ]


def test_a_feature_that_cannot_be_measured_takes_the_peers_median():
    rows = peers(10)
    rows[3] = InstitutionFeatures(
        rows[3].institution_id, {**rows[3].values, "admission_growth": None}, 30
    )
    found = anomaly.score(rows, contamination=0.1, n_estimators=50, random_state=0)
    assert rows[3].institution_id not in {o.institution_id for o in found}
    assert anomaly.score(rows[:1], contamination=0.1, n_estimators=50, random_state=0) == []


def test_sentences_follow_the_copy_deck():
    assert anomaly.rule(0.05, 50) == (
        "Model: Isolation Forest, contamination 5%, trained on this year's 50 colleges."
    )
    assert anomaly.feature_words(["nri_share", "management_share", "admission_growth"]) == (
        "NRI share of admissions, management share of admissions and admission growth on last year"
    )
    assert anomaly.summary("PQR College", 39, "2026-27", ["nri_share"]) == (
        "PQR College stands out from 39 similar colleges in 2026-27 on NRI share of admissions."
    )
    fact = anomaly.feature_fact(
        {"name": "nri_share", "value": 0.31, "peer_low": 0.02, "peer_high": 0.07}, "Model"
    )
    assert fact == {
        "label": "NRI share of admissions",
        "value": "31% (similar colleges 2% to 7%)",
        "source": "Model",
    }
    assert rings.rule(min_cross=3, min_colleges=2, min_single=5).startswith(
        "Rule: students linked by a shared mobile number, email or address form a group; a group "
        "of 3 or more across 2 or more colleges, or of 5 or more in one college, is a signal."
    )
