"""The degree QR, its short names and length, and the printed insert."""

from __future__ import annotations

import base64
import json
import re
import zlib
from types import SimpleNamespace

import pytest
from jwcrypto.jws import JWS

from app.credentials import degree, keys

# The longest names datagen seeds (tools/datagen, --size full --seed 42): the longest
# student name, the longest institution, the two longest programmes, a four-letter
# university code and a provisional id, which signs longer than the last four digits.
LONGEST_STUDENT = "Hrishikesh Chaitanya Deshpande"
LONGEST_INSTITUTION = "Atal Bihari Vajpayee College of Engineering and Technology, Kanchipuram"
LONGEST_PROGRAMMES = (
    "Bachelor of Computer Applications (Open and Distance Learning)",
    "B.Tech CSE (Artificial Intelligence and Machine Learning)",
    "B.Tech Electronics and Telecommunication Engineering",
)
# the graduate whose link was longest at 28 characters (408)
LONGEST_GRADUATE = (
    "Tamilselvan Balasubramanian",
    "B.Tech Electrical Engineering",
    "Sanskar School of Engineering",
    "CBEU",
    "6865",
)


@pytest.mark.parametrize(
    ("name", "short"),
    [
        ("B.Tech Computer Science and Engineering", "B.Tech CS & Engg."),
        ("ABC College of Engineering", "ABC College of Engg."),
        ("B.Tech Information Technology", "B.Tech IT"),
        ("Master of Business Administration", "Master of Business"),
        ("B.Tech CSE (Artificial Intelligence and Machine Learning)", "B.Tech CSE"),
        ("Lal Bahadur Shastri Institute of Technology", "Lal Bahadur Shastri Inst."),
        ("Maharashtra State Technical University", "Maharashtra State Technical"),
        ("XYZ Institute of Technology", "XYZ Inst. of Tech."),
    ],
)
def test_short_names(name, short):
    assert degree.short_name(name) == short
    assert len(degree.short_name(name)) <= 28


def test_masks_and_proof_ids():
    assert degree.mask_provisional("PRV-7Q2MK4PX") == "PRV-XXXXK4PX"
    assert degree.normalise_short_id(" 4zk8-m2qd ") == "4ZK8M2QD"
    assert degree.normalise_short_id("4ZK8M2QO") == "4ZK8M2Q0"
    assert degree.normalise_short_id("4ZK8M2Q") is None
    assert degree.normalise_short_id("4ZK8M2QU") is None


def _record(name, programme, institution, university, apaar_last4=None, provisional=None):
    return SimpleNamespace(
        student=SimpleNamespace(name=name, apaar_last4=apaar_last4, provisional_id=provisional),
        programme=SimpleNamespace(name=programme),
        institution=SimpleNamespace(name=institution),
        university=SimpleNamespace(code=university),
        enrolment=SimpleNamespace(academic_year="2025-26"),
    )


def _decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def test_the_contract_example_keeps_its_short_names():
    key = keys.IssuerKey(kid=(issuer_key := keys.generate())["kid"], jwk=issuer_key)
    record = _record(
        "Asha Patil",
        "B.Tech Computer Science and Engineering",
        "ABC College of Engineering",
        "MSTU",
        apaar_last4="0011",
    )
    jws = degree.sign_degree(key, record, "4ZK8M2QD")
    assert _decode(jws.split(".")[1]).decode() == (
        '{"v":1,"cid":"4ZK8M2QD","n":"Asha Patil","p":"B.Tech CS & Engg.",'
        '"i":"ABC College of Engg.","u":"MSTU","y":2026,"a":"0011"}'
    )
    assert json.loads(_decode(jws.split(".")[0])) == {"alg": "ES256", "kid": key.kid}
    assert len(degree.verify_url(jws)) == 373  # the contract's "near 350"
    token = JWS()
    token.deserialize(jws)
    token.verify(issuer_key)
    assert degree.sign_degree(key, record, "4ZK8M2QD") != jws  # signed afresh, both verify


@pytest.mark.parametrize("programme", LONGEST_PROGRAMMES)
def test_the_degree_url_stays_under_400_for_the_longest_seeded_names(programme):
    issuer_key = keys.generate()
    key = keys.IssuerKey(kid=issuer_key["kid"], jwk=issuer_key)
    for record in (
        _record(
            LONGEST_STUDENT, programme, LONGEST_INSTITUTION, "ODTU", provisional="PRV-GQ4DKN7A"
        ),
        _record(*LONGEST_GRADUATE[:4], apaar_last4=LONGEST_GRADUATE[4]),
    ):
        jws = degree.sign_degree(key, record, "4ZK8M2QD")
        url = degree.verify_url(jws)
        assert url.startswith("http://localhost:3000/verify/d/")
        assert len(url) < 400, len(url)
        payload = json.loads(_decode(jws.split(".")[1]))
        assert payload["n"] == record.student.name  # the name is never shortened
        assert payload["a"] == ("6865" if record.student.apaar_last4 else "PRV-XXXXKN7A")
        # programme and institution only ever lose words from the end
        for part, full in (("p", record.programme.name), ("i", record.institution.name)):
            assert payload[part] and degree.short_name(full).startswith(payload[part])
        token = JWS()
        token.deserialize(jws)
        token.verify(issuer_key)


def _pdf_text(pdf: bytes) -> str:
    """The page content of a reportlab PDF: ASCII85, then zlib."""
    text = []
    for raw in re.findall(rb"\nstream\r?\n(.*?)endstream", pdf, re.S):
        data = raw.strip()
        if data.endswith(b"~>"):
            data = base64.a85decode(data[:-2])
        text.append(zlib.decompress(data).decode("latin-1"))
    return "\n".join(text)


def _print_data(id_kind="APAAR", id_masked="XXXX XXXX 0011"):
    return {
        "enrolment_id": "g1",
        "student": {"name": "Asha Patil", "id_kind": id_kind, "id_masked": id_masked},
        "programme": {"code": "CSE", "name": "B.Tech Computer Science and Engineering"},
        "institution": {"name": "ABC College of Engineering", "aicte_permanent_id": "1-ABC-0001"},
        "university": {"code": "MSTU", "name": "Maharashtra State Technical University"},
        "academic_year": "2025-26",
        "year_of_award": 2026,
        "degree": {
            "short_id": "4ZK8M2QD",
            "issued_at": "2026-10-29T07:00:00Z",
            "verify_url": "http://localhost:3000/verify/d/eyJhbGciOiJFUzI1NiJ9.e30.sig",
            "lookup_url": "http://localhost:3000/verify/degree/4ZK8M2QD",
        },
    }


def test_the_insert_renders():
    pdf = degree.insert_pdf(_print_data())
    assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
    assert pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 1
    assert b"/MediaBox [ 0 0 595.2756 841.8898 ]" in pdf
    text = _pdf_text(pdf)
    for line in (
        "Maharashtra State Technical University",
        "This insert accompanies the degree awarded to",
        "Asha Patil",
        "Programme: B.Tech Computer Science and Engineering",
        "Institution: ABC College of Engineering",
        "Year of award: 2026",
        "APAAR XXXX XXXX 0011",
        "Proof id 4ZK8M2QD",
        "Scan to verify at localhost:3000/verify",
        "Proof issued 29 Oct 2026",
        degree.FOOTER,
    ):
        assert f"({line})" in text, line
    assert "verify/d/" not in text  # the QR's link is never printed as text
    assert " rg" not in text.replace("0 0 0 rg", "")  # black only

    provisional = _pdf_text(degree.insert_pdf(_print_data("PROVISIONAL", "PRV-XXXXN7A")))
    assert "(Provisional id PRV-XXXXN7A)" in provisional
