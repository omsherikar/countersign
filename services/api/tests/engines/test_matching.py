"""Name matching (ENGINES.md section 6, D17): the must-pass table plus Indian name edges."""

from __future__ import annotations

from datetime import date

import pytest

from app.engine.matching import match_names, name_key, normalise_name, transliterate, verdict

NAMES = [
    "Shri. R. K. Sharma",
    "Mohd. Irfan Khan",
    "Md Irfan Khan",
    "Muhammad Irfan Khan",
    "Mohamed Irfan Khan",
    "Muhammed Irfan Khan",
    "रवि कुमार शर्मा",
    "मोहम्मद इरफ़ान ख़ान",
    "Dr. (Mrs.) Priya  Sharma-Verma",
    "Smt. Sunita Devi",
    "Kumari Anjali",
    "Km. Pooja Yadav",
    "Sri Ramesh",
    "José Álvarez",
    "  Ravi\tKumar\nSharma  ",
    "",
    "Dr.",
    "सिंह",
    "चंद्र प्रकाश",
]


# ------------------------------------------------------------------ normalise_name


def test_honorifics_and_punctuation_are_dropped() -> None:
    assert normalise_name("Shri. R. K. Sharma") == "r k sharma"
    assert normalise_name("Dr. (Mrs.) Priya  Sharma-Verma") == "priya sharma verma"
    assert normalise_name("Smt. Sunita Devi") == "sunita devi"
    assert normalise_name("Kumari Anjali") == "anjali"
    assert normalise_name("Km. Pooja Yadav") == "pooja yadav"
    assert normalise_name("Sri Ramesh") == "ramesh"
    assert normalise_name("Mr Ms Mrs Dr Shri Smt Kumari Km Sri") == ""


@pytest.mark.parametrize(
    "raw",
    [
        "Mohd. Irfan Khan",
        "Md Irfan Khan",
        "Muhammad Irfan Khan",
        "Mohammad Irfan Khan",
        "Mohammed Irfan Khan",
        "Mohamed Irfan Khan",
        "Muhammed Irfan Khan",
        "MD. IRFAN KHAN",
    ],
)
def test_mohammed_family_folds_to_one_token(raw: str) -> None:
    assert normalise_name(raw) == "mohammed irfan khan"


def test_mohammed_folding_is_whole_token_only() -> None:
    assert normalise_name("Mdhavi Rao") == "mdhavi rao"
    assert normalise_name("Ahmed Mohdin") == "ahmed mohdin"


def test_accents_and_whitespace() -> None:
    assert normalise_name("José Álvarez") == "jose alvarez"
    assert normalise_name("  Ravi\tKumar\nSharma  ") == "ravi kumar sharma"
    assert normalise_name("") == ""


@pytest.mark.parametrize("raw", NAMES)
def test_normalise_is_idempotent(raw: str) -> None:
    once = normalise_name(raw)
    assert normalise_name(once) == once


def test_normalise_adds_no_spelling_folds() -> None:
    # Spelling folds belong to match_names only; the registry never applies them.
    assert normalise_name("Pooja Shrivastava") == "pooja shrivastava"
    assert normalise_name("Ashwin Laxmi") == "ashwin laxmi"


# ------------------------------------------------------------------- Devanagari


def test_devanagari_must_pass() -> None:
    assert normalise_name("रवि कुमार शर्मा") == "ravi kumar sharma"


@pytest.mark.parametrize(
    ("devanagari", "latin"),
    [
        ("मोहम्मद इरफ़ान ख़ान", "mohammed irfan khan"),  # medial and final schwa, nukta
        ("सौरभ", "saurabh"),  # medial schwa kept before a deleted final one
        ("जगदीश", "jagdish"),
        ("कमला", "kamla"),
        ("अमित", "amit"),
        ("दीपक", "dipak"),
        ("चंद्र प्रकाश", "chandra prakash"),  # schwa kept after a final conjunct
        ("कृष्ण", "krishna"),
        ("गंगा", "ganga"),  # anusvara before a velar
        ("संपत", "sampat"),  # anusvara before a labial
        ("सिंह", "singh"),
        ("लक्ष्मी", "lakshmi"),
        ("छाया", "chhaya"),
        ("ज्ञान", "gyan"),
    ],
)
def test_devanagari_transliteration(devanagari: str, latin: str) -> None:
    assert normalise_name(devanagari) == latin


def test_transliterate_leaves_latin_alone() -> None:
    assert transliterate("Ravi Kumar") == "Ravi Kumar"
    assert transliterate("Ravi शर्मा") == "Ravi sharma"


def test_mixed_script_and_honorific_in_devanagari() -> None:
    assert normalise_name("श्री रवि शर्मा") == "ravi sharma"


# ------------------------------------------------------------------- match_names


def test_initials_must_pass() -> None:
    result = match_names("R. K. Sharma", "Ravi Kumar Sharma")
    assert 90 <= result.score <= 99
    assert result.method == "INITIALS"
    assert result.verdict == "MATCH"
    assert result.a == "r k sharma"
    assert result.b == "ravi kumar sharma"


def test_exact_must_pass() -> None:
    result = match_names("Ravi Kumar Sharma", "Ravi Kumar Sharma")
    assert (result.score, result.method, result.verdict) == (100, "EXACT", "MATCH")


def test_mohammed_spellings_are_exact() -> None:
    result = match_names("Mohd Irfan Khan", "Mohammed Irfan Khan")
    assert (result.score, result.method) == (100, "EXACT")
    assert match_names("Muhammed Irfan Khan", "Mohamed Irfan Khan").method == "EXACT"


def test_dropped_middle_name_matches() -> None:
    assert match_names("Ravi Sharma", "Ravi Kumar Sharma").score >= 90


def test_devanagari_against_latin_matches() -> None:
    assert match_names("रवि कुमार शर्मा", "Ravi Kumar Sharma").score >= 90
    assert match_names("मोहम्मद इरफ़ान ख़ान", "Mohd. Irfan Khan").score >= 90


def test_wrong_first_initial_is_not_a_match() -> None:
    result = match_names("S. K. Sharma", "Ravi Kumar Sharma")
    assert result.score < 90
    assert result.verdict != "MATCH"


def test_different_person_with_same_initials_is_no_match() -> None:
    result = match_names("R. K. Sharma", "Rohit Kumar Verma")
    assert result.score < 75
    assert result.verdict == "NO_MATCH"


def test_initials_against_full_names_either_side() -> None:
    assert match_names("Ravi Kumar Sharma", "R. K. Sharma").method == "INITIALS"
    assert match_names("R Sharma", "Ravi Kumar Sharma").verdict == "MATCH"
    assert match_names("Ravi K. Sharma", "R. Kumar Sharma").verdict == "MATCH"


def test_initials_must_align_in_order() -> None:
    result = match_names("K. R. Sharma", "Ravi Kumar Sharma")
    assert result.method == "FUZZY"
    assert result.verdict != "MATCH"


def test_initials_score_is_never_100() -> None:
    assert match_names("R. K. Sharma", "R K Sharma").score == 100  # normalised equal: EXACT
    for a, b in [("R. K. Sharma", "Ravi Kumar Sharma"), ("R Sharma", "Ravi Sharma")]:
        assert 90 <= match_names(a, b).score <= 99


def test_more_initials_aligned_scores_higher() -> None:
    full = match_names("Ravi K. Sharma", "Ravi Kumar Sharma").score
    initials = match_names("R. K. Sharma", "Ravi Kumar Sharma").score
    assert full > initials


def test_swapped_order_matches() -> None:
    assert match_names("Sharma Ravi Kumar", "Ravi Kumar Sharma").verdict == "MATCH"
    swapped = match_names("Sharma R. K.", "Ravi Kumar Sharma")
    assert swapped.method == "INITIALS"
    assert swapped.verdict == "MATCH"


def test_south_indian_initial_first() -> None:
    result = match_names("S. Priya", "Priya Subramanian")
    assert result.method == "INITIALS"
    assert result.verdict == "MATCH"


def test_single_letter_surname() -> None:
    # A trailing initial is read as an initial (South Indian "Arun S." for Arun, son of
    # Suresh), never as a surname that confirms a family name on its own.
    assert match_names("Arun S.", "Arun Suresh").method == "INITIALS"
    assert match_names("Arun S.", "Arun Kumar").verdict != "MATCH"
    assert match_names("Arun S.", "Kiran S.").verdict == "NO_MATCH"
    assert match_names("Arun S.", "Arun S").method == "EXACT"


def test_married_name_change_is_not_a_match() -> None:
    result = match_names("Priya Sharma", "Priya Verma")
    assert result.verdict != "MATCH"
    assert match_names("P. Sharma", "Priya Verma").verdict == "NO_MATCH"
    # nor does the blocking key put them together, even with the same date of birth
    dob = date(2006, 5, 1)
    assert name_key("Priya Sharma", dob) != name_key("Priya Verma", dob)


def test_spelling_folds_apply_only_when_matching() -> None:
    result = match_names("Pooja Shrivastava", "Puja Srivastava")
    assert result.verdict == "MATCH"
    assert result.a == "pooja shrivastava"  # the inputs as normalised, folds not applied
    assert match_names("Ashwin Laxmi", "Ashvin Lakshmi").verdict == "MATCH"
    assert match_names("Seetha Raman", "Sita Raman").verdict == "MATCH"


def test_empty_names_never_match() -> None:
    assert match_names("", "").verdict == "NO_MATCH"
    assert match_names("Dr.", "Ravi Sharma").score == 0


def test_verdict_thresholds_come_from_rules() -> None:
    assert verdict(100) == "MATCH"
    assert verdict(90) == "MATCH"
    assert verdict(89) == "REVIEW"
    assert verdict(75) == "REVIEW"
    assert verdict(74) == "NO_MATCH"
    assert verdict(0) == "NO_MATCH"


# ----------------------------------------------------------------------- name_key


def test_name_key_must_pass() -> None:
    dob = date(2007, 3, 21)
    assert name_key("R. K. Sharma", dob) == "2007-03-21|r|XRM"
    assert name_key("Ravi Kumar Sharma", dob) == "2007-03-21|r|XRM"


def test_name_key_devanagari_and_honorifics() -> None:
    dob = date(2007, 3, 21)
    assert name_key("रवि कुमार शर्मा", dob) == "2007-03-21|r|XRM"
    assert name_key("Shri Ravi Sharma", dob) == "2007-03-21|r|XRM"


def test_name_key_without_tokens() -> None:
    assert name_key("Dr.", date(2007, 3, 21)) == "2007-03-21|?|"
    assert name_key("Ravi", date(2007, 3, 21)) == "2007-03-21|r|RF"
