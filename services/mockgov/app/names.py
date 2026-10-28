"""Name normalisation, kept in step with the Countersign API's own helper.

Lowercase, strip honorifics and punctuation, collapse whitespace, and fold the common
spellings of Mohammed to one token so "Mohd Irfan" and "Mohammad Irfan" compare equal.
"""

import re
import unicodedata

from rapidfuzz import fuzz

HONORIFICS = frozenset({"mr", "ms", "mrs", "dr", "shri", "smt", "kumari", "km", "sri"})
MOHAMMED_VARIANTS = frozenset(
    {"mohd", "mohammed", "md", "mohammad", "muhammad", "mohamed", "muhammed"}
)

_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _NON_ALNUM.sub(" ", text.lower())
    tokens = []
    for token in text.split():
        if token in HONORIFICS:
            continue
        tokens.append("mohammed" if token in MOHAMMED_VARIANTS else token)
    return " ".join(tokens)


def name_score(a: str, b: str) -> int:
    """RapidFuzz token_set_ratio on already-normalised names, as an integer 0-100."""
    if not a or not b:
        return 0
    return round(fuzz.token_set_ratio(a, b))


def mask_name(name: str) -> str:
    """Each word as its first letter and one star per remaining character, so a list can be
    shared without the names: "Ravi Kumar Sharma" -> "R*** K**** S*****"."""
    return " ".join(word[0] + "*" * (len(word) - 1) for word in name.split())
