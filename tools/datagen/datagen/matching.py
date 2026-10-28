"""Name rules as the services apply them, so planted cases land where they are meant to.

`transliterate`, `normalise_name`, `match_names` and `name_key` follow the api's matcher
(docs/ENGINES.md section 6, `services/api/app/engine/matching.py`): the duplicate rules
block candidates on `name_key` and compare them with `match_names`. `registry_score`
follows mockgov (`services/mockgov/app/names.py`), which scores every APAAR, counselling
and Study in India lookup. Keep both in step with those files.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Literal, NamedTuple

import jellyfish
from indic_transliteration import sanscript
from rapidfuzz import fuzz

from .config import load_rules

NameVerdict = Literal["MATCH", "REVIEW", "NO_MATCH"]
NameMethod = Literal["EXACT", "INITIALS", "FUZZY"]


class NameMatch(NamedTuple):
    score: int
    verdict: NameVerdict
    method: NameMethod
    a: str
    b: str


HONORIFICS = frozenset({"mr", "ms", "mrs", "dr", "shri", "smt", "kumari", "km", "sri"})
# Kept in step with services/mockgov/app/names.py, which folds the same spellings.
MOHAMMED_VARIANTS = frozenset(
    {"mohd", "md", "mohammad", "muhammad", "mohammed", "mohamed", "muhammed"}
)
MOHAMMED = "mohammed"

# Folds applied to both names inside match_names only, longest pattern first.
SPELLING_FOLDS: tuple[tuple[str, str], ...] = (
    ("ksh", "x"),
    ("chh", "ch"),
    ("aa", "a"),
    ("ee", "i"),
    ("ii", "i"),
    ("oo", "u"),
    ("uu", "u"),
    ("ph", "f"),
    ("th", "t"),
    ("w", "v"),
)
_FOLD_RE = re.compile("|".join(re.escape(src) for src, _ in SPELLING_FOLDS))
_FOLD_MAP = dict(SPELLING_FOLDS)

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_HAS_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Letters and signs only: digits (U+0966 to U+096F), dandas and the abbreviation sign
# (U+0964, U+0965, U+0970) end a word.
_DEVANAGARI_WORD = re.compile(r"[ऀ-ॣॱ-ॿ]+")

# ------------------------------------------------------------------ Devanagari

NUKTA = "़"
VIRAMA = "्"
ANUSVARA = "ं"
VISARGA = "ः"

# Consonant + nukta written as two code points, composed to the single code points the
# transliterator knows. Unicode NFC never composes these (composition exclusions).
_NUKTA_COMPOSE = {
    "क़": "क़",  # qa
    "ख़": "ख़",  # Ka (Urdu kh)
    "ग़": "ग़",  # Ga (Urdu gh)
    "ज़": "ज़",  # za
    "ड़": "ड़",  # .Da (flapped r)
    "ढ़": "ड़",  # rha, read as the flapped r
    "ढ़": "ड़",
    "फ़": "फ़",  # fa
    "य़": "य़",  # Ya
}
# Letters the transliterator does not know, mapped to the nearest one it does.
_DEVANAGARI_SUBSTITUTES = str.maketrans(
    {
        "ऑ": "ओ",  # candra o -> o
        "ॉ": "ो",  # candra o sign -> o sign
        "ऍ": "ए",  # candra e -> e
        "ॅ": "े",  # candra e sign -> e sign
        "ऎ": "ए",  # short e -> e
        "ॆ": "े",
        "ऒ": "ओ",  # short o -> o
        "ॊ": "ो",
        "॑": None,  # Vedic accents
        "॒": None,
        "‌": None,  # zero-width non-joiner and joiner
        "‍": None,
    }
)
_DEVANAGARI_DIGITS_AND_MARKS = str.maketrans(
    {
        **{chr(0x0966 + d): str(d) for d in range(10)},
        "।": " ",
        "॥": " ",
        "॰": " ",
    }
)


def _is_consonant(ch: str) -> bool:
    cp = ord(ch)
    return 0x0915 <= cp <= 0x0939 or 0x0958 <= cp <= 0x095F or 0x0978 <= cp <= 0x097F


def _is_vowel_sign(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x093A <= cp <= 0x093B
        or 0x093E <= cp <= 0x094C
        or 0x094E <= cp <= 0x094F
        or 0x0955 <= cp <= 0x0957
        or 0x0962 <= cp <= 0x0963
    )


def _is_modifier(ch: str) -> bool:
    return 0x0900 <= ord(ch) <= 0x0903


def _is_independent_vowel(ch: str) -> bool:
    cp = ord(ch)
    return 0x0904 <= cp <= 0x0914 or 0x0960 <= cp <= 0x0961 or 0x0972 <= cp <= 0x0977


@dataclass(slots=True)
class _Unit:
    """One consonant with its vowel sign or virama, an independent vowel, or anything else."""

    kind: str  # "C", "V" or "X"
    base: str
    sign: str = ""  # vowel sign or VIRAMA; empty means the inherent schwa
    mods: str = ""  # candrabindu, anusvara, visarga
    schwa_deleted: bool = False

    @property
    def inherent(self) -> bool:
        return self.kind == "C" and not self.sign and not self.schwa_deleted

    @property
    def has_vowel(self) -> bool:
        if self.kind == "V":
            return True
        return self.kind == "C" and self.sign != VIRAMA and not self.schwa_deleted

    @property
    def closed(self) -> bool:
        """Anusvara or visarga closes the syllable, so the next schwa is pronounced."""
        return ANUSVARA in self.mods or VISARGA in self.mods

    def render(self) -> str:
        sign = VIRAMA if self.schwa_deleted else self.sign
        return self.base + sign + self.mods


def _units(word: str) -> list[_Unit]:
    units: list[_Unit] = []
    for ch in word:
        last = units[-1] if units else None
        if _is_consonant(ch):
            units.append(_Unit("C", ch))
        elif ch == NUKTA:
            continue  # nukta on a consonant without a composed form: read the plain one
        elif (ch == VIRAMA or _is_vowel_sign(ch)) and last and last.kind == "C" and not last.sign:
            last.sign = ch
        elif _is_modifier(ch) and last is not None:
            last.mods += ch
        elif _is_independent_vowel(ch):
            units.append(_Unit("V", ch))
        else:
            units.append(_Unit("X", ch))
    return units


def _delete_schwas(units: list[_Unit]) -> None:
    """Hindi schwa deletion: word-final, then V C a C V -> V C C V from the right.

    The final schwa stays after a conjunct (chandra, krishna) and in one-letter words.
    A medial schwa goes when the syllable before it is open and a consonant with a
    vowel follows (irafAna -> irfAn, kamalA -> kamlA, but saurabha -> saurabh).
    """
    n = len(units)
    last = units[-1] if units else None
    if (
        n >= 2
        and last is not None
        and last.inherent
        and not last.mods
        and not (units[-2].kind == "C" and units[-2].sign == VIRAMA)
    ):
        last.schwa_deleted = True
    for i in range(n - 2, 0, -1):
        unit, left, right = units[i], units[i - 1], units[i + 1]
        if (
            unit.inherent
            and not unit.mods
            and left.has_vowel
            and not left.closed
            and right.kind == "C"
            and right.has_vowel
        ):
            unit.schwa_deleted = True


_ANUSVARA_LABIAL = re.compile(r"M(?=[pbm])")
_ANUSVARA_FINAL_H = re.compile(r"Mh$")
# ITRANS spellings that lower-casing alone would read wrongly, in order.
_ITRANS_TO_LATIN: tuple[tuple[str, str], ...] = (
    ("RRi", "ri"),
    ("RRI", "ri"),
    ("LLi", "li"),
    ("LLI", "li"),
    ("j~n", "gy"),
    ("~N", "n"),
    ("~n", "n"),
    (".N", "n"),
    ("OM", "om"),
    (".D", "r"),
    (".a", ""),
    ("Ch", "chh"),
    ("K", "kh"),
    ("G", "gh"),
    ("H", "h"),
)


def _transliterate_word(word: str) -> str:
    units = _units(word)
    _delete_schwas(units)
    itrans = sanscript.transliterate(
        "".join(u.render() for u in units), sanscript.DEVANAGARI, sanscript.ITRANS
    )
    itrans = _ANUSVARA_FINAL_H.sub("ngh", itrans)  # siMh -> singh
    itrans = _ANUSVARA_LABIAL.sub("m", itrans)  # saMpat -> sampat
    for src, dst in _ITRANS_TO_LATIN:
        itrans = itrans.replace(src, dst)
    return itrans.replace("M", "n").lower()  # gaMgA -> ganga


def transliterate(raw: str) -> str:
    """Devanagari runs to lower-case Latin; anything else unchanged."""
    if not _HAS_DEVANAGARI.search(raw):
        return raw
    text = raw.translate(_DEVANAGARI_SUBSTITUTES)
    for decomposed, composed in _NUKTA_COMPOSE.items():
        text = text.replace(decomposed, composed)
    text = _DEVANAGARI_WORD.sub(lambda m: _transliterate_word(m.group()), text)
    return text.translate(_DEVANAGARI_DIGITS_AND_MARKS)


# --------------------------------------------------------------- normalise_name


@lru_cache(maxsize=65536)
def normalise_name(raw: str) -> str:
    """Transliterate, fold accents and case, drop punctuation and honorifics, fold
    Mohammed spellings, collapse spaces. Idempotent."""
    text = transliterate(raw)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = _NON_ALNUM.sub(" ", text)
    tokens = [
        MOHAMMED if token in MOHAMMED_VARIANTS else token
        for token in text.split()
        if token not in HONORIFICS
    ]
    return " ".join(tokens)


# ------------------------------------------------------------------- match_names


def verdict(score: int) -> NameVerdict:
    thresholds = load_rules()["name_matching"]
    if score >= thresholds["pass_threshold"]:
        return "MATCH"
    if score >= thresholds["review_threshold"]:
        return "REVIEW"
    return "NO_MATCH"


def _fold(text: str) -> str:
    return _FOLD_RE.sub(lambda m: _FOLD_MAP[m.group()], text)


@dataclass(frozen=True, slots=True)
class _Token:
    plain: str
    folded: str


def _tokens(normalised: str) -> list[_Token]:
    return [_Token(t, _fold(t)) for t in normalised.split()]


def _pair_quality(x: _Token, y: _Token) -> float | None:
    """How well two given-name tokens align: 0.5 for an initial, the ratio for full
    tokens scoring at least 90, None when they do not align."""
    for short, long_ in ((x, y), (y, x)):
        if len(short.plain) == 1 and (
            long_.plain.startswith(short.plain) or long_.folded.startswith(short.folded)
        ):
            return 0.5
    if len(x.plain) == 1 or len(y.plain) == 1:
        return None
    ratio = fuzz.ratio(x.folded, y.folded)
    return ratio / 100 if ratio >= 90 else None


def _initials_score(a: list[_Token], b: list[_Token]) -> int | None:
    """Initials-aware score (90 to 99) when the surnames agree and every other token of
    the shorter name aligns, in order, with a token of the longer one."""
    if not a or not b:
        return None
    sur_a, sur_b = a[-1], b[-1]
    if len(sur_a.plain) < 2 or len(sur_b.plain) < 2:
        return None  # a surname given as an initial cannot confirm the family name
    surname_ratio = fuzz.ratio(sur_a.folded, sur_b.folded)
    if surname_ratio < 90:
        return None
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    rest = longer[:-1]
    qualities = [surname_ratio / 100]
    j = 0
    for token in shorter[:-1]:
        while j < len(rest):
            quality = _pair_quality(token, rest[j])
            j += 1
            if quality is not None:
                qualities.append(quality)
                break
        else:
            return None
    mean = sum(qualities) / len(longer)  # tokens of the longer name left unmatched add 0
    return min(99, 90 + int(9 * mean))


def _surname_first(tokens: list[_Token]) -> list[_Token]:
    """The same name with its first token moved to the end ("Sharma R K" -> "R K Sharma")."""
    return tokens[1:] + tokens[:1] if len(tokens) >= 2 else tokens


def match_names(a: str, b: str) -> NameMatch:
    """Compare two names (raw or normalised). See docs/ENGINES.md section 6."""
    na, nb = normalise_name(a), normalise_name(b)
    if not na or not nb:
        return NameMatch(score=0, verdict="NO_MATCH", method="FUZZY", a=na, b=nb)
    if na == nb:
        return NameMatch(score=100, verdict=verdict(100), method="EXACT", a=na, b=nb)

    ta, tb = _tokens(na), _tokens(nb)
    method: NameMethod = "FUZZY"
    score: int | None = None
    if any(len(t.plain) == 1 for t in ta + tb):
        candidates = [
            _initials_score(x, y)
            for x in (ta, _surname_first(ta))
            for y in (tb, _surname_first(tb))
        ]
        found = [c for c in candidates if c is not None]
        if found:
            score, method = max(found), "INITIALS"
    if score is None:
        folded_a = " ".join(t.folded for t in ta)
        folded_b = " ".join(t.folded for t in tb)
        score = round(fuzz.token_set_ratio(folded_a, folded_b))
    return NameMatch(score=score, verdict=verdict(score), method=method, a=na, b=nb)


# ---------------------------------------------------------------------- name_key


def name_key(name: str, dob: date | str) -> str:
    """Blocking key "<dob ISO>|<first initial>|<metaphone of surname>"."""
    if isinstance(dob, str):
        dob = date.fromisoformat(dob)
    tokens = normalise_name(name).split()
    initial = tokens[0][0] if tokens else "?"
    surname = tokens[-1] if tokens else ""
    return f"{dob.isoformat()}|{initial}|{jellyfish.metaphone(surname) if surname else ''}"


# ------------------------------------------------------------------ registry side


def registry_normalise(name: str) -> str:
    """mockgov's normaliser (steps 2 to 6 of the api's), applied to both sides of a lookup."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s]+", " ", text.lower())
    tokens = [
        MOHAMMED if token in MOHAMMED_VARIANTS else token
        for token in text.split()
        if token not in HONORIFICS
    ]
    return " ".join(tokens)


def registry_score(uploaded: str, stored: str) -> int:
    """The `name_score` mockgov returns: the api sends its normalised name, mockgov
    normalises both sides and takes RapidFuzz token_set_ratio."""
    a = registry_normalise(normalise_name(uploaded))
    b = registry_normalise(stored)
    if not a or not b:
        return 0
    return round(fuzz.token_set_ratio(a, b))
