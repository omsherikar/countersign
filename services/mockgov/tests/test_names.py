import pytest

from app.names import name_score, normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ravi Kumar Sharma", "ravi kumar sharma"),
        ("  RAVI   KUMAR  SHARMA ", "ravi kumar sharma"),
        ("Mr. Ravi Kumar Sharma", "ravi kumar sharma"),
        ("Smt. Sunita Devi", "sunita devi"),
        ("Dr Anil S. Deshmukh", "anil s deshmukh"),
        ("Kumari Priya Nair", "priya nair"),
        ("R. K. Sharma", "r k sharma"),
        ("Mohd Irfan", "mohammed irfan"),
        ("Md. Irfan", "mohammed irfan"),
        ("Mohammad Irfan", "mohammed irfan"),
        ("Mohammed Irfan", "mohammed irfan"),
        ("José Álvarez", "jose alvarez"),
        ("O'Brien-Smith", "o brien smith"),
        ("", ""),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


def test_identical_names_score_100() -> None:
    assert name_score("ravi kumar sharma", "ravi kumar sharma") == 100


def test_token_order_does_not_matter() -> None:
    assert name_score("sharma ravi kumar", "ravi kumar sharma") == 100


def test_mohammed_variants_score_100_after_normalisation() -> None:
    a, b = normalize_name("Mohd Irfan Khan"), normalize_name("Mohammad Irfan Khan")
    assert name_score(a, b) == 100


def test_initials_score_below_the_counselling_threshold() -> None:
    score = name_score(normalize_name("R. K. Sharma"), normalize_name("Ravi Kumar Sharma"))
    assert 0 < score < 90


def test_empty_name_scores_zero() -> None:
    assert name_score("", "ravi kumar sharma") == 0
    assert name_score("ravi", "") == 0


def test_muhammad_spellings_fold_to_one_token():
    from app.names import normalize_name

    assert {normalize_name(n) for n in ("Muhammad Irfan", "Mohamed Irfan", "Md. Irfan")} == {
        normalize_name("Mohammed Irfan")
    }


def test_km_and_sri_are_dropped_as_honorifics():
    from app.names import normalize_name

    assert normalize_name("Km. Priya Patil") == normalize_name("Priya Patil")
    assert normalize_name("Sri Ramesh Rao") == normalize_name("Ramesh Rao")
