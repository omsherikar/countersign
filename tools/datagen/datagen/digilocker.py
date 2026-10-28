"""mockgov/digilocker_accounts.jsonl: the synthetic accounts of the DigiLocker sign-in simulator.

One account per person, international students excluded (they have no DigiLocker here):

- every APAAR the registry holds has an account with that APAAR and the registry's name,
  date of birth and gender: students on the roll, late refills, students their college left
  out of its upload, graduates, and the person behind a NAME_MISMATCH APAAR;
- every other person on the roll or left out has an account without an APAAR, under the
  uploaded name: consent refused or pending, an uploaded APAAR that is malformed or unknown
  to the registry, or another person's APAAR (the uploaded side of a NAME_MISMATCH). Rows
  that describe one person (a renamed duplicate, the same student at two colleges) count once;
- graduates without an APAAR have one too.

`digilocker_id` is `DL-` and two groups of four letters and digits; the demo student's is
fixed (`DL-RAVI-4417`). A random stream of its own, seeded from the run's seed, leaves every
other file unchanged.
"""

from __future__ import annotations

import random

from .students import DEMO_APAAR, World, has_usable_apaar

DEMO_DIGILOCKER_ID = "DL-RAVI-4417"
ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
ACCOUNT_FIELDS = ["digilocker_id", "name", "dob", "gender", "apaar_id"]


class AccountBuilder:
    def __init__(self, world: World, registry: list[dict]):
        self.w = world
        self.registry = registry
        self.rng = random.Random(f"digilocker:{world.seed}")
        self.used: set[str] = {DEMO_DIGILOCKER_ID}
        self.accounts: list[dict] = []
        self.by_apaar: dict[str, str] = {}
        self.by_unit: dict[int, str] = {}

    def new_id(self) -> str:
        while True:
            chars = "".join(self.rng.choices(ALPHABET, k=8))
            candidate = f"DL-{chars[:4]}-{chars[4:]}"
            if candidate not in self.used:
                self.used.add(candidate)
                return candidate

    def add(self, name: str, dob: str, gender: str | None, apaar: str | None) -> str:
        account_id = DEMO_DIGILOCKER_ID if apaar == DEMO_APAAR else self.new_id()
        values = (account_id, name, dob, gender, apaar)
        self.accounts.append(dict(zip(ACCOUNT_FIELDS, values, strict=True)))
        return account_id

    def signs_in_with_apaar(self, row: dict) -> bool:
        """The row's APAAR is the student's own: the registry holds it under this person."""
        return (
            has_usable_apaar(row)
            and row["_registry"] == "match"
            and (row["apaar_id"] in self.by_apaar)
        )

    def build(self) -> list[dict]:
        w = self.w
        for rec in self.registry:
            self.by_apaar[rec["apaar_id"]] = self.add(
                rec["name"], rec["dob"], rec.get("gender"), rec["apaar_id"]
            )
        for row in w.all_rows + w.update_only_rows + w.omitted_rows:
            if row["admission_route"] == "INTERNATIONAL":
                continue
            unit = w.unit_of(row)
            if unit in self.by_unit:
                continue
            if self.signs_in_with_apaar(row):
                self.by_unit[unit] = self.by_apaar[row["apaar_id"]]
                continue
            # Every row of one person shares the unit; the first one names the account.
            self.by_unit[unit] = self.add(row["name"], row["dob"], row["gender"], None)
        for grad in w.graduates:
            if not grad["apaar_id"]:
                self.add(grad["name"], grad["dob"], grad["gender"], None)
        return self.accounts

    def account_of(self, row: dict) -> str | None:
        """The account the student behind an upload row signs in with."""
        if row["admission_route"] == "INTERNATIONAL":
            return None
        if self.signs_in_with_apaar(row):
            return self.by_apaar[row["apaar_id"]]
        return self.by_unit.get(self.w.unit_of(row))
