"""Name rules mirrored from the api (ENGINES.md section 6) and mockgov (services/mockgov)."""

import datetime as dt

from datagen import matching


def test_normalise_name_examples_from_the_engines_contract():
    assert matching.normalise_name("Shri. R. K. Sharma") == "r k sharma"
    for raw in ("Mohd. Irfan Khan", "Md Irfan Khan", "Muhammad Irfan Khan"):
        assert matching.normalise_name(raw) == "mohammed irfan khan"
    assert matching.normalise_name("रवि कुमार शर्मा") == "ravi kumar sharma"
    assert matching.normalise_name("Sri Harsha D'Souza") == "harsha d souza"
    for raw in ("Ravi Kumar Sharma", "Md. Irfan", "  Dr  Anjali   Nair "):
        once = matching.normalise_name(raw)
        assert matching.normalise_name(once) == once


def test_name_key_blocks_initials_with_the_full_name():
    dob = dt.date(2007, 3, 21)
    assert matching.name_key("R. K. Sharma", dob) == "2007-03-21|r|XRM"
    assert matching.name_key("Ravi Kumar Sharma", dob) == "2007-03-21|r|XRM"
    assert matching.name_key("", dob) == "2007-03-21|?|"


def test_registry_score_is_mockgov_token_set_ratio():
    assert matching.registry_score("Ravi Kumar Sharma", "ravi kumar sharma") == 100
    assert matching.registry_score("Mohd Irfan Khan", "Mohammed Irfan Khan") == 100
    assert matching.registry_score("Ravi Sharma", "Ravi Kumar Sharma") == 100
    assert matching.registry_score("Priya Patil", "Sneha Kulkarni") < 75
