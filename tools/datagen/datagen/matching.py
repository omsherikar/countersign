"""Name rules as the services apply them, so planted cases land where they are meant to.

`normalise_name` and `name_key` follow the api (docs/ENGINES.md section 6): the duplicate
rules block candidates on `name_key`. `registry_score` follows mockgov
(services/mockgov/app/names.py), which scores every APAAR, counselling and Study in India
lookup.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata

import jellyfish
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from rapidfuzz import fuzz

HONORIFICS = frozenset({"mr", "ms", "mrs", "dr", "shri", "smt", "kumari", "km", "sri"})
MOHAMMED = frozenset({"mohd", "md", "mohammad", "muhammad", "mohammed"})

REGISTRY_HONORIFICS = frozenset({"mr", "ms", "mrs", "dr", "shri", "smt", "kumari"})
REGISTRY_MOHAMMED = MOHAMMED | {"mohamed", "muhammed"}

_DEVANAGARI_RUN = re.compile(r"[ऀ-ॿ]+")
_CONSONANT = re.compile(r"[क-हक़-य़]$")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def _latin(run: str) -> str:
    """One Devanagari word in ITRANS, without the inherent vowel after a final consonant."""
    out = transliterate(run, sanscript.DEVANAGARI, sanscript.ITRANS)
    if _CONSONANT.search(run) and out.endswith("a"):
        out = out[:-1]
    return out


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def normalise_name(raw: str) -> str:
    """The api's normaliser: Devanagari to Latin, accents and punctuation dropped,
    honorifics removed, the spellings of Mohammed folded. Idempotent."""
    text = _DEVANAGARI_RUN.sub(lambda m: _latin(m.group(0)), raw)
    text = _NON_ALNUM.sub(" ", _fold(text))
    tokens = []
    for token in text.split():
        if token in HONORIFICS:
            continue
        tokens.append("mohammed" if token in MOHAMMED else token)
    return " ".join(tokens)


def name_key(name: str, dob: dt.date | str) -> str:
    """The duplicate-blocking key: date of birth, first initial, metaphone of the surname."""
    if isinstance(dob, str):
        dob = dt.date.fromisoformat(dob)
    tokens = normalise_name(name).split()
    initial = tokens[0][0] if tokens else "?"
    surname = jellyfish.metaphone(tokens[-1]) if tokens else ""
    return f"{dob.isoformat()}|{initial}|{surname}"


def registry_normalise(name: str) -> str:
    """mockgov's normaliser, applied to both sides of every registry lookup."""
    text = re.sub(r"[^a-z0-9\s]+", " ", _fold(name))
    tokens = []
    for token in text.split():
        if token in REGISTRY_HONORIFICS:
            continue
        tokens.append("mohammed" if token in REGISTRY_MOHAMMED else token)
    return " ".join(tokens)


def registry_score(uploaded: str, stored: str) -> int:
    """The `name_score` mockgov returns: the api sends its normalised name, mockgov
    normalises both sides and takes RapidFuzz token_set_ratio."""
    a = registry_normalise(normalise_name(uploaded))
    b = registry_normalise(stored)
    if not a or not b:
        return 0
    return round(fuzz.token_set_ratio(a, b))
