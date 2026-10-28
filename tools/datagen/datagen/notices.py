"""notice_replies.jsonl: how each student answers the enrolment notice in the seeded demo.

Once a batch is processed the api sends every ACTIVE enrolment a notice ("ABC College says
you joined B.Tech CSE. Is that right?") by email, and on DigiLocker when the student has an
APAAR. A notice only points the student to the claim page: an answer counts only after the
student signs in through DigiLocker (DECISIONS D37), so every planned answer is on the
DIGILOCKER_SIGNIN channel and names the account that signs in. The seed applies them through
the same service the claim page uses:

- every planted STUDENT_DENIED row (`will_deny`) answers NO; three of them leave a short
  comment, the deck sample ("I never joined this college.") always among them;
- a few refused-consent students (no APAAR) answer YES after claiming their record with the
  provisional id their college gave them (`claim_provisional_id: true`);
- about 70% of the clean rows whose student signs in with the record's own APAAR answer YES;
- every other row stays unanswered (NONE): rows of other planted cases, rows a later update
  file withdraws or transfers, international students (no DigiLocker account), students
  without an APAAR who do not claim, and the notices the live demo answers by hand (Ravi
  Kumar Sharma, his duplicate row "R. K. Sharma", and one more ABC CSE first-year named in
  the manifest).

One line per row of each initial upload file, in file and row order. Rows the api holds back
as upload errors never become enrolments and have no line; update files have none either
(their refills get notices but no planned answer).

A random stream of its own, seeded from the run's seed, leaves every other file unchanged.
"""

from __future__ import annotations

import random
import re

from .digilocker import AccountBuilder
from .institutions import ABC_ID
from .matching import normalise_name
from .students import World, has_usable_apaar

REPLY_FIELDS = [
    "file", "row_no", "reply", "channel", "comment", "reply_after_days",
    "claim_provisional_id", "digilocker_id",
]  # fmt: skip
CHANNEL = "DIGILOCKER_SIGNIN"
YES_SHARE = 0.70
YES_DAYS = (0, 12)
NO_DAYS = (0, 5)
# Rows of these ground-truth records are legitimate students, so they answer like any other.
LEGITIMATE = {"CONSENT_REFUSED_NO_APAAR"}
NOT_ME_COMMENT = "I never joined this college."
COMMENTS = (
    "This is not me. I study at another college.",
    "I did not take admission here and have never been to this college.",
    "I have never heard of this college. Please remove my name.",
)
_MOBILE = re.compile(r"[0-9]{10}")


def held_back(rows: list[dict]) -> set[int]:
    """Indexes of the rows the api rejects as DUPLICATE_IN_FILE (validate.file_duplicates):
    a later row with the APAAR it uses as identity, the passport number, or, with neither,
    the normalised name, DOB and mobile of an earlier row of the same file."""
    by_apaar: set[str] = set()
    by_passport: set[str] = set()
    by_person: set[tuple[str, str, str]] = set()
    out: set[int] = set()
    for i, row in enumerate(rows):
        apaar = row["apaar_id"] if has_usable_apaar(row) else ""
        passport = re.sub(r"\s+", "", row["passport_no"]).upper()
        mobile = row["mobile"] if _MOBILE.fullmatch(row["mobile"] or "") else ""
        person = (normalise_name(row["name"]), row["dob"], mobile)
        if (
            (apaar and apaar in by_apaar)
            or (passport and passport in by_passport)
            or (not apaar and not passport and person in by_person)
        ):
            out.add(i)
            continue
        if apaar:
            by_apaar.add(apaar)
        if passport:
            by_passport.add(passport)
        if not apaar and not passport:
            by_person.add(person)
    return out


class ReplyPlanner:
    """Plans one answer per initial upload row. Run after the rows have their row numbers."""

    def __init__(
        self,
        world: World,
        files: list[tuple[str, list[dict]]],
        registry: set[str],
        accounts: AccountBuilder,
    ):
        self.w = world
        self.files = sorted(files, key=lambda f: f[0])
        self.registry = registry
        self.accounts = accounts
        self.rng = random.Random(f"notice-replies:{world.seed}")
        self.unanswered: list[dict] = []
        # initial rows that an update file withdraws or transfers
        self.leaving: set[int] = set()
        # refused-consent rows that answer after claiming by provisional id
        self.claimers: set[int] = set()

    # ---------------------------------------------------------------- sign-in

    def on_digilocker(self, row: dict) -> bool:
        """A DigiLocker notice reaches the student only for an APAAR the registry holds."""
        return has_usable_apaar(row) and row["apaar_id"] in self.registry

    def claims(self, quiet: set[int]) -> set[int]:
        """Refused-consent students who claim their record by provisional id: the planted
        CONSENT_REFUSED_NO_APAAR rows first, then other clean refused rows."""
        k = self.w.cfg.digilocker.get("provisional_claims", 0)
        pool = []
        for _name, rows in self.files:
            rejected = held_back(rows)
            for i, row in enumerate(rows):
                if i in rejected or id(row) in quiet or id(row) in self.leaving:
                    continue
                tags = set(row["_tags"])
                if row["consent_status"] == "REFUSED" and tags <= LEGITIMATE:
                    pool.append((not tags, row["_file"], row["row_no"], row))
        pool.sort(key=lambda p: p[:3])
        planted = [p[3] for p in pool if not p[0]]
        others = [p[3] for p in pool if p[0]]
        picked = self.rng.sample(planted, min(k, len(planted)))
        picked += self.rng.sample(others, min(k - len(picked), len(others)))
        return {id(row) for row in picked}

    # ------------------------------------------------------------------ picks

    def demo_rows(self) -> list[tuple[str, dict]]:
        """The notices the live demo answers by hand, with their role."""
        if not self.w.cfg.scenarios:
            return []
        rec = next(r for r in self.w.ground_truth if r.get("scenario") == "demo_student")
        ravi, dup = rec["_rows"]
        abc = next(rows for _name, rows in self.files if rows and rows[0]["_inst"] == ABC_ID)
        # The first clean, linked, counselled ABC CSE first-year after Ravi, in file order.
        second = next(
            r for r in abc
            if r["programme_code"] == "CSE" and r["year_of_study"] == 1 and not r["_tags"]
            and r["admission_route"] == "COUNSELLING" and self.on_digilocker(r)
            and r["email"] and id(r) not in self.leaving
        )  # fmt: skip
        return [
            ("DEMO_STUDENT", ravi),
            ("DEMO_STUDENT_DUPLICATE", dup),
            ("SECOND_DEMO_NOTICE", second),
        ]

    def commented(self, deniers: list[dict]) -> dict[int, str]:
        """Three deniers leave a comment; the named "not me" student always does."""
        not_me = [
            r["_rows"][0] for r in self.w.ground_truth if r.get("scenario") == "not_me"
        ]  # fmt: skip
        others = [r for r in deniers if all(r is not n for n in not_me)]
        picked = not_me + self.rng.sample(others, min(len(others), 3 - len(not_me)))
        texts = [NOT_ME_COMMENT] * len(not_me) + list(COMMENTS)
        return {id(row): text for row, text in zip(picked, texts, strict=False)}

    # ----------------------------------------------------------------- driver

    def plan(self) -> list[dict]:
        self.leaving = {
            id(u["_initial"])
            for rows in self.w.update_files.values()
            for u in rows
            if u.get("_initial") is not None
        }
        demo = self.demo_rows()
        quiet = {id(row) for _, row in demo}
        self.claimers = self.claims(quiet)
        deniers = [
            row for _name, rows in self.files for row in rows if "STUDENT_DENIED" in row["_tags"]
        ]  # fmt: skip
        comments = self.commented(deniers)
        self.unanswered = [
            {
                "role": role,
                "file": row["_file"],
                "row_no": row["row_no"],
                "name": row["name"],
                "apaar_id": row["apaar_id"] or None,
            }
            for role, row in demo
        ]

        out = []
        for _name, rows in self.files:
            rejected = held_back(rows)
            for i, row in enumerate(rows):
                if i in rejected:
                    continue
                out.append(self.reply(row, quiet, comments))
        return out

    def reply(self, row: dict, quiet: set[int], comments: dict[int, str]) -> dict:
        """NONE carries 0 days; `digilocker_id` is the account the student signs in with
        (null for an international student, who has none)."""
        account = self.accounts.account_of(row)
        reply, comment, days, claim = "NONE", None, 0, False
        tags = set(row["_tags"])
        if id(row) in quiet or account is None:
            pass
        elif "STUDENT_DENIED" in tags:
            reply, comment = "NO", comments.get(id(row))
            days = self.rng.randint(*NO_DAYS)
        elif id(row) in self.claimers:
            reply, claim = "YES", True
            days = self.rng.randint(*YES_DAYS)
        elif tags <= LEGITIMATE and id(row) not in self.leaving and self.on_digilocker(row):
            if self.rng.random() < YES_SHARE:
                reply = "YES"
                days = self.rng.randint(*YES_DAYS)
        values = (row["_file"], row["row_no"], reply, CHANNEL, comment, days, claim, account)
        return dict(zip(REPLY_FIELDS, values, strict=True))
