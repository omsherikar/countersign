"""Indian student names by naming group, and the variants used for renamed duplicates."""

from __future__ import annotations

import random
import unicodedata

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

from .config import load_data

GROUPS: tuple[str, ...] = (
    "hindi", "marathi", "tamil", "telugu", "kannada", "malayalam", "bengali",
    "punjabi", "gujarati", "odia", "assamese", "muslim", "christian",
)  # fmt: skip

# Groups where a father's name commonly sits between given name and surname.
_MIDDLE_NAME_GROUPS = {"marathi", "gujarati", "hindi"}
_HINDI_MIDDLE_M = ("Kumar", "Prasad", "Kant", "Nath", "Chandra", "Pratap", "Mohan", "Lal")
_HINDI_MIDDLE_F = ("Kumari", "Devi", "Rani", "Lata", "Bala", "Priya")

# Latin spellings that commonly vary between documents (both directions are used).
_SPELLING_VARIANTS: dict[str, str] = {
    "deepak": "dipak", "sharma": "sarma", "srinivas": "shrinivas", "vijay": "vijai",
    "kumar": "kumaar", "anjali": "anjaly", "priya": "priyaa", "patil": "paatil",
    "sunil": "suneel", "sanjay": "sanjai", "rajesh": "rajeesh", "deshmukh": "deshmukhe",
    "ravi": "ravee", "sushma": "sushmaa", "meena": "mina", "neha": "nehaa",
    "geeta": "gita", "seema": "sima", "reena": "rina", "preeti": "priti",
    "shruti": "shruthi", "swati": "swathi", "kavita": "kavitha", "sunita": "sunitha",
    "lakshmi": "laxmi", "ashok": "ashoke", "mahesh": "maheshwar", "suresh": "sureesh",
    "chaudhary": "choudhury", "mukherjee": "mukhopadhyay", "banerjee": "bandyopadhyay",
    "chatterjee": "chattopadhyay", "sheikh": "shaikh", "syed": "sayed", "qureshi": "quraishi",
    "ansari": "ansaree", "verma": "varma", "mishra": "misra", "tiwari": "tiwary",
    "pandey": "pandeya", "yadav": "yadhav", "singh": "singhh", "kaur": "kour",
    "nair": "nayar", "pillai": "pillay", "reddy": "reddi", "naidu": "naidoo",
    "gowda": "gouda", "shetty": "shetti", "hegde": "hegade", "bhat": "bhatt",
}

_MUSLIM_PREFIXES = ("Mohammed", "Mohammad", "Muhammad", "Mohd", "Md", "Md.")


class NameGenerator:
    def __init__(self, rng: random.Random):
        self.rng = rng
        data = load_data("names.json")
        self.groups = data["groups"]
        self.international = data["international"]

    def pick_group(self, weights: dict[str, float]) -> str:
        names = list(weights)
        return self.rng.choices(names, weights=[weights[n] for n in names], k=1)[0]

    def indian_name(self, group: str, gender: str) -> str:
        g = self.groups[group]
        first = self.rng.choice(g["M"] if gender == "M" else g["F"])
        surname = self.rng.choice(g["surnames"])
        if group == "muslim":
            return f"{first} {surname}"
        if group in _MIDDLE_NAME_GROUPS and self.rng.random() < 0.45:
            if group == "hindi":
                middle = self.rng.choice(_HINDI_MIDDLE_M if gender == "M" else _HINDI_MIDDLE_F)
            else:
                middle = self.rng.choice(g["M"])
            return f"{first} {middle} {surname}"
        if group == "tamil" and self.rng.random() < 0.35:
            # South Indian style: given name followed by an initial.
            return f"{first} {surname[0]}"
        return f"{first} {surname}"

    def international_name(self, nationality: str, gender: str) -> str:
        pool = self.international[nationality]
        return self.rng.choice(pool["M"] if gender == "M" else pool["F"])

    def nationalities(self) -> list[str]:
        return list(self.international)


# ---------------------------------------------------------------------------
# Variants for renamed duplicates
# ---------------------------------------------------------------------------


def with_initials(name: str) -> str:
    """'Ravi Kumar Sharma' -> 'R. K. Sharma'. Single-token names are returned as-is."""
    parts = name.split()
    if len(parts) < 2:
        return name
    return " ".join(f"{p[0]}." for p in parts[:-1]) + " " + parts[-1]


def devanagari(name: str) -> str:
    """The name as a college clerk might type it in Devanagari."""
    return transliterate(name.lower(), sanscript.ITRANS, sanscript.DEVANAGARI)


def _strip_diacritics(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def transliteration_variant(name: str) -> str:
    """Round-trip the name through Devanagari and back (IAST, diacritics dropped).

    Produces the spelling drift seen between documents: Sharma/Sarma, Deepak/Dipak,
    Rajesh/Rajes. Tokens that survive the round trip unchanged fall back to a common
    Latin spelling variant so the result always differs from the input.
    """
    out: list[str] = []
    changed = False
    for token in name.split():
        low = token.lower().strip(".")
        if len(low) <= 1:
            out.append(token)
            continue
        dev = transliterate(low, sanscript.ITRANS, sanscript.DEVANAGARI)
        back = _strip_diacritics(transliterate(dev, sanscript.DEVANAGARI, sanscript.IAST))
        if back.endswith("a") and not low.endswith("a") and len(back) > 2:
            back = back[:-1]
        if back and back != low:
            changed = True
            out.append(back.capitalize())
        else:
            out.append(token)
    if not changed:
        return spelling_variant(name)
    return " ".join(out)


def spelling_variant(name: str) -> str:
    """Swap the first token that has a known alternate Latin spelling."""
    reverse = {v: k for k, v in _SPELLING_VARIANTS.items()}
    parts = name.split()
    for i, token in enumerate(parts):
        low = token.lower()
        alt = _SPELLING_VARIANTS.get(low) or reverse.get(low)
        if alt:
            parts[i] = alt.capitalize()
            return " ".join(parts)
    # Last resort: double a vowel in the first token so the string still differs.
    first = parts[0]
    for j, ch in enumerate(first):
        if ch.lower() in "aeiou":
            parts[0] = first[: j + 1] + ch.lower() + first[j + 1 :]
            return " ".join(parts)
    parts[0] = first + "a"
    return " ".join(parts)


def mohd_variant(name: str, rng: random.Random) -> str:
    """'Mohammed Irfan Khan' -> 'Mohd Irfan Khan' / 'Md. Irfan Khan'. Prefix is added if absent."""
    parts = name.split()
    if parts and parts[0] in _MUSLIM_PREFIXES:
        choices = [p for p in _MUSLIM_PREFIXES if p != parts[0]]
        parts[0] = rng.choice(choices)
        return " ".join(parts)
    return rng.choice(["Mohd", "Md.", "Md"]) + " " + name


def materially_different(name: str, generator: NameGenerator, group: str, gender: str) -> str:
    """A name that shares at most the surname with the original (registry mismatch)."""
    for _ in range(20):
        candidate = generator.indian_name(group, gender)
        if candidate.split()[0] != name.split()[0]:
            return candidate
    return "Unknown Applicant"
