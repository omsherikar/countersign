"""Name rules mirrored from the api (ENGINES.md section 6) and mockgov (services/mockgov)."""

import datetime as dt

import pytest

from datagen import matching


def test_normalise_name_examples_from_the_engines_contract():
    assert matching.normalise_name("Shri. R. K. Sharma") == "r k sharma"
    for raw in (
        "Mohd. Irfan Khan", "Md Irfan Khan", "Muhammad Irfan Khan", "Mohammad Irfan Khan",
        "Mohamed Irfan Khan", "Muhammed Irfan Khan", "Mohammed Irfan Khan",
    ):  # fmt: skip
        assert matching.normalise_name(raw) == "mohammed irfan khan"
    assert matching.normalise_name("Km. Pooja Yadav") == "pooja yadav"
    assert matching.normalise_name("Sri Harsha D'Souza") == "harsha d souza"
    assert matching.normalise_name("Pooja Shrivastava") == "pooja shrivastava"
    for raw in ("Ravi Kumar Sharma", "Md. Irfan", "  Dr  Anjali   Nair ", "सिंह"):
        once = matching.normalise_name(raw)
        assert matching.normalise_name(once) == once


@pytest.mark.parametrize(
    ("devanagari", "latin"),
    [
        ("रवि कुमार शर्मा", "ravi kumar sharma"),
        ("मोहम्मद इरफ़ान ख़ान", "mohammed irfan khan"),
        ("सौरभ", "saurabh"),
        ("कमला", "kamla"),
        ("दीपक", "dipak"),
        ("चंद्र प्रकाश", "chandra prakash"),
        ("संपत", "sampat"),
        ("सिंह", "singh"),
        ("छाया", "chhaya"),
        ("ज्ञान", "gyan"),
    ],
)
def test_devanagari_reads_as_the_api_reads_it(devanagari, latin):
    assert matching.normalise_name(devanagari) == latin


def test_match_names_table_from_the_engines_contract():
    m = matching.match_names("R. K. Sharma", "Ravi Kumar Sharma")
    assert 90 <= m.score <= 99 and m.method == "INITIALS" and m.verdict == "MATCH"
    assert matching.match_names("Ravi Kumar Sharma", "Ravi Kumar Sharma").score == 100
    assert matching.match_names("Mohd Irfan Khan", "Mohammed Irfan Khan").method == "EXACT"
    assert matching.match_names("Ravi Sharma", "Ravi Kumar Sharma").score >= 90
    assert matching.match_names("रवि कुमार शर्मा", "Ravi Kumar Sharma").score >= 90
    assert matching.match_names("S. K. Sharma", "Ravi Kumar Sharma").score < 90
    assert matching.match_names("R. K. Sharma", "Rohit Kumar Verma").score < 75


def test_name_key_blocks_initials_with_the_full_name():
    dob = dt.date(2007, 3, 21)
    assert matching.name_key("R. K. Sharma", dob) == "2007-03-21|r|XRM"
    assert matching.name_key("Ravi Kumar Sharma", dob) == "2007-03-21|r|XRM"
    assert matching.name_key("Ravi Kumar Sharma", "2007-03-21") == "2007-03-21|r|XRM"
    assert matching.name_key("", dob) == "2007-03-21|?|"


def test_registry_score_is_mockgov_token_set_ratio():
    assert matching.registry_score("Ravi Kumar Sharma", "ravi kumar sharma") == 100
    assert matching.registry_score("Mohd Irfan Khan", "Muhammed Irfan Khan") == 100
    assert matching.registry_score("Sri Harsha Reddy", "Sri Harsha Reddy") == 100
    assert matching.registry_score("Ravi Sharma", "Ravi Kumar Sharma") == 100
    assert matching.registry_score("Priya Patil", "Sneha Kulkarni") < 75
