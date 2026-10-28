# Engines (internal Python contract, Week 2)

This file is the only thing the two api branches may assume about each other's Python code. `API_CONTRACT.md` (Addendum 2) is the wire contract, `DATA_MODEL.md` ("Migration 0002") is the schema and `DECISIONS.md` D14 to D22 are the rules being implemented. If a function, field or behaviour another branch needs is not written here, add it here first.

Two branches build in parallel:

- **backend-pipeline** (`api/upload-pipeline`): turns a file or JSON rows into students and enrolments and drives every stage (`run_batch`).
- **backend-engines** (`api/engines`): the engines `run_batch` calls (Seat Ledger, checks, duplicates, flags, score, matching) and the read endpoints over their output.

## 1. Ownership

| Path under `services/api/` | Owner | Notes |
|---|---|---|
| `alembic/versions/0002_week2_engine_columns.py` | pipeline | everything in DATA_MODEL "Migration 0002", nothing else |
| `app/models/*.py`, `app/models/enums.py` | pipeline | only the 0002 changes; engines never edit models |
| `app/core/config.py`, `../../.env.example` | pipeline | the settings in §2.3, for both branches |
| `pyproject.toml`, `uv.lock` | pipeline | every new dependency for both branches (§2.2) |
| `../../docker-compose.yml`, `../../Makefile` | pipeline | spool volume, worker concurrency 1, seed order |
| `app/engine/contracts.py` | both, identical bytes | §3; change this doc first |
| `app/engine/upload/` (`__init__.py`, `parse.py`, `validate.py`, `upsert.py`, helpers) | pipeline | §5 |
| `app/engine/pipeline.py` | pipeline | `run_batch`, `default_engines` (§4) |
| `app/routers/uploads.py`, `app/schemas/uploads.py` | pipeline | API_CONTRACT §A2.4 to §A2.9 |
| `app/worker.py` | pipeline | Celery task `countersign.run_batch` |
| `app/seed/` | pipeline | seed through `run_batch` (D22) |
| `tests/fixtures/mini_generated/` | pipeline | add the three optional columns and an update file |
| `app/engine/matching.py` | engines | §6 |
| `app/engine/ledger.py` | engines | §7 |
| `app/engine/checks/` (`__init__.py`, `base.py`, `identity.py`, `admission.py`, `seat.py`, `studying.py`, `student.py`) | engines | §8 |
| `app/engine/duplicates.py` | engines | §9 |
| `app/engine/flags.py`, `app/engine/evidence.py` | engines | §10; evidence and check-detail sentences from API_CONTRACT §A2.14 and §A2.17 |
| `app/engine/score.py` | engines | §11 |
| `app/routers/flags.py`, `app/routers/enrolments.py`, `app/schemas/flags.py`, `app/schemas/enrolments.py` | engines | new |
| `app/routers/dashboard.py`, `institutions.py`, `students.py`, `_stats.py`; `app/schemas/common.py`, `dashboard.py`, `institutions.py`, `students.py` | engines | count and countersign changes (API_CONTRACT §A2.10, §A2.18 to §A2.20) |
| `app/main.py` | both | pipeline: multipart exemption and the uploads router; engines: flags and enrolments routers (§2.4) |
| `app/engine/seatpools.py`, `app/core/cohort.py`, `app/core/audit.py`, `app/core/crypto.py`, `app/adapters/**` | nobody | read and call them; change only through the lead |
| `tests/pipeline/`, `tests/engines/` | pipeline, engines | each branch puts new tests (and its own `conftest.py`) in its own package; nobody edits `tests/conftest.py` |

## 2. Merge order and shared files

### 2.1 The schema-and-dependencies commit lands first

The first commit on `api/upload-pipeline` contains, and only contains: migration 0002, the model and enum edits, the new settings and `.env.example` keys, the new dependencies with a refreshed `uv.lock`, and `app/engine/contracts.py`. The lead merges it to `main` as soon as `make test` passes on it. backend-engines then merges `main` into `api/engines`.

Until it lands, backend-engines builds and tests the pure modules (`matching.py`, `evidence.py`, `score.py`, dedupe keys, the check decision tables with fake subjects) and may add `app/engine/contracts.py` itself, byte for byte from §3, so the later merge is clean. Database-backed engine tests start once the merge is in.

### 2.2 Dependencies (added by pipeline for both)

`openpyxl` (XLSX parsing), `python-multipart` (FastAPI form uploads), `jellyfish` (metaphone), `indic-transliteration` (Devanagari to Latin). `rapidfuzz` is already present. backend-engines does not edit `pyproject.toml` or `uv.lock`; a missing dependency is a request to the lead.

### 2.3 Settings (added by pipeline for both)

| Setting (env) | Default | Used by |
|---|---|---|
| `checks_concurrency` (`CHECKS_CONCURRENCY`) | `32` | `run_batch` and the recheck endpoints pass it to the checks engine |
| `upload_max_bytes` (`UPLOAD_MAX_BYTES`) | `20971520` (20 MB) | `POST /uploads` |
| `upload_max_rows` (`UPLOAD_MAX_ROWS`) | `50000` | parse stage |
| `upload_rows_api_max` (`UPLOAD_ROWS_API_MAX`) | `5000` | `POST /uploads/rows` |
| `upload_spool_dir` (`UPLOAD_SPOOL_DIR`) | `/data/spool` | api and worker, compose volume `upload-spool` |
| `upload_inline` (`UPLOAD_INLINE`) | `false` | `true` runs `run_batch` in the api process after the response (tests); `false` enqueues the Celery task |

### 2.4 `app/main.py`

Both branches add routers, so the `from app.routers import ...` line conflicts once. The lead resolves it to the sorted list `admin, auth, dashboard, enrolments, flags, healthz, institutions, meta, students, uploads` (as `ruff format` lays it out) and the registrations to `healthz, auth, dashboard, institutions, enrolments, flags, uploads, students, meta, admin` in that order. Pipeline also exempts `POST /uploads` (multipart) from the JSON-only 415 check; that is the only exemption.

## 3. `app/engine/contracts.py` (identical on both branches)

Shared dataclasses and the `EngineSuite` protocol `run_batch` calls. It passes `ruff check` and `ruff format --check` with the repo settings and imports cleanly against Week 1 `main`.

```python
"""Shared engine contract (docs/ENGINES.md section 3).

Both api branches add this file with identical bytes. Change docs/ENGINES.md first,
then copy the new text into this file on every branch.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterSet
from app.models.enums import CheckStatus, CheckType, FlagStatus, FlagType, SeatType, Severity
from app.models.verification import Flag

CHUNK_SIZE = 500
DEFAULT_CHECK_CONCURRENCY = 32

CHECK_ORDER: tuple[CheckType, ...] = (
    CheckType.IDENTITY,
    CheckType.ADMISSION,
    CheckType.SEAT,
    CheckType.STUDYING,
    CheckType.STUDENT,
)
UNRESOLVED_FLAG_STATUSES: tuple[FlagStatus, ...] = (
    FlagStatus.OPEN,
    FlagStatus.DOCS_REQUESTED,
    FlagStatus.ESCALATED,
)

NameVerdict = Literal["MATCH", "REVIEW", "NO_MATCH"]
NameMethod = Literal["EXACT", "INITIALS", "FUZZY"]


@dataclass(frozen=True, slots=True)
class NameMatch:
    """Result of matching.match_names(a, b). `a` and `b` are the normalised inputs."""

    score: int
    verdict: NameVerdict
    method: NameMethod
    a: str
    b: str


@dataclass(frozen=True, slots=True)
class PoolRef:
    """One seat pool: the approval it belongs to and its seat type."""

    approval_id: uuid.UUID
    seat_type: SeatType


@dataclass(frozen=True, slots=True)
class FlagIntent:
    """A flag an engine wants raised; flags.raise_flag(**intent fields) writes it."""

    type: FlagType
    severity: Severity
    institution_id: uuid.UUID
    academic_year: str
    dedupe_key: str
    evidence: dict[str, Any]
    programme_id: uuid.UUID | None = None
    enrolment_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class RaisedFlag:
    """What flags.raise_flag returns: the row, and whether it was created or changed."""

    flag: Flag
    created: bool
    changed: bool


@dataclass(slots=True)
class FlagTally:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    flag_ids: list[uuid.UUID] = field(default_factory=list)

    def count(self, raised: RaisedFlag) -> None:
        if raised.created:
            self.created += 1
        elif raised.changed:
            self.updated += 1
        else:
            self.unchanged += 1
        self.flag_ids.append(raised.flag.id)

    def merge(self, other: FlagTally) -> None:
        self.created += other.created
        self.updated += other.updated
        self.unchanged += other.unchanged
        self.flag_ids.extend(other.flag_ids)


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    """One check's verdict for one enrolment. `detail` always carries a `summary`."""

    type: CheckType
    status: CheckStatus
    source: str
    detail: dict[str, Any]
    flags: tuple[FlagIntent, ...] = ()
    calls: tuple[str, ...] = ()
    unavailable: tuple[str, ...] = ()


@dataclass(slots=True)
class LedgerResult:
    seated: list[uuid.UUID] = field(default_factory=list)
    released: list[uuid.UUID] = field(default_factory=list)
    unseated: list[uuid.UUID] = field(default_factory=list)
    late_refills: list[uuid.UUID] = field(default_factory=list)
    touched_pools: set[PoolRef] = field(default_factory=set)
    flags: FlagTally = field(default_factory=FlagTally)

    def merge(self, other: LedgerResult) -> None:
        self.seated.extend(other.seated)
        self.released.extend(other.released)
        self.unseated.extend(other.unseated)
        self.late_refills.extend(other.late_refills)
        self.touched_pools |= other.touched_pools
        self.flags.merge(other.flags)


@dataclass(slots=True)
class ChecksResult:
    enrolments: int = 0
    changed: int = 0
    statuses: dict[str, dict[str, int]] = field(default_factory=dict)
    calls: dict[str, int] = field(default_factory=dict)
    unavailable: dict[str, int] = field(default_factory=dict)
    flags: FlagTally = field(default_factory=FlagTally)

    def merge(self, other: ChecksResult) -> None:
        self.enrolments += other.enrolments
        self.changed += other.changed
        for check_type, by_status in other.statuses.items():
            mine = self.statuses.setdefault(check_type, {})
            for status, n in by_status.items():
                mine[status] = mine.get(status, 0) + n
        for source, n in other.calls.items():
            self.calls[source] = self.calls.get(source, 0) + n
        for source, n in other.unavailable.items():
            self.unavailable[source] = self.unavailable.get(source, 0) + n
        self.flags.merge(other.flags)


@dataclass(slots=True)
class DuplicatesResult:
    within: int = 0
    cross: int = 0
    dual: int = 0
    flags: FlagTally = field(default_factory=FlagTally)

    def merge(self, other: DuplicatesResult) -> None:
        self.within += other.within
        self.cross += other.cross
        self.dual += other.dual
        self.flags.merge(other.flags)


@dataclass(slots=True)
class RecheckResult:
    enrolments: int = 0
    rechecked: int = 0
    now_pass: int = 0
    now_fail: int = 0
    now_na: int = 0
    still_pending: int = 0
    flags: FlagTally = field(default_factory=FlagTally)


class EngineSuite(Protocol):
    """What run_batch needs from the engine modules. Tests pass a fake."""

    def normalise_name(self, raw: str) -> str: ...

    def name_key(self, name: str, dob: date) -> str: ...

    async def assign_seats(
        self,
        session: AsyncSession,
        enrolment_ids: Sequence[uuid.UUID],
        *,
        actor_id: uuid.UUID | None,
    ) -> LedgerResult: ...

    async def run_checks(
        self,
        session: AsyncSession,
        enrolment_ids: Sequence[uuid.UUID],
        adapters: AdapterSet,
        *,
        concurrency: int = DEFAULT_CHECK_CONCURRENCY,
        actor_id: uuid.UUID | None = None,
    ) -> ChecksResult: ...

    async def detect_duplicates(
        self,
        session: AsyncSession,
        institution_id: uuid.UUID,
        academic_year: str,
        enrolment_ids: Sequence[uuid.UUID],
        *,
        actor_id: uuid.UUID | None = None,
    ) -> DuplicatesResult: ...

    async def refresh_seat_flags(
        self,
        session: AsyncSession,
        pools: Sequence[PoolRef],
        *,
        actor_id: uuid.UUID | None = None,
    ) -> FlagTally: ...
```

Field meanings:

- `LedgerResult.seated`: enrolments given a seat by this call, including earlier unseated enrolments of a touched pool (§7). `released`: enrolments whose seat was released. `unseated`: enrolments from the input that are ACTIVE and still without a seat after the call. `late_refills`: enrolments whose assignment raised LATE_REFILL. `touched_pools`: every pool where something was assigned or released or an input enrolment stayed unseated.
- `ChecksResult.enrolments`: ACTIVE enrolments evaluated. `changed`: check rows whose status changed or that were created. `statuses`: counts of the resulting status per check type, keyed by the enum values. `calls` and `unavailable`: adapter calls and `SourceUnavailable` results per check source (`APAAR`, `COUNSELLING`, `ABC`, `SII`).
- `DuplicatesResult.within`, `cross`, `dual`: pairs found this call (a pair already flagged still counts; `flags` tells created from updated).
- `RecheckResult`: `rechecked` checks re-run; `now_pass`, `now_fail`, `now_na` how many of them left PENDING; `still_pending` how many did not.
- `FlagTally`: `created` new dedupe keys, `updated` existing flags whose evidence or severity changed, `unchanged` the rest.

## 4. `app/engine/pipeline.py` (pipeline)

### 4.1 Signature

```python
async def run_batch(
    batch_id: uuid.UUID,
    *,
    factory: async_sessionmaker[AsyncSession] | None = None,   # default: app.db.session.session_factory()
    adapters: AdapterSet | None = None,                        # default: build_adapters(), closed at the end
    engines: EngineSuite | None = None,                        # default: default_engines()
    source: Path | list[dict[str, Any]] | None = None,         # default: the batch's spool file
) -> UploadBatch: ...

def default_engines() -> EngineSuite: ...   # imports app.engine.{matching,ledger,checks,duplicates,flags} lazily
```

`run_batch` never raises for anything a row or a source does. Any exception inside a stage rolls back that chunk, marks the batch FAILED (below) and returns the batch. Callers: the Celery task `countersign.run_batch(batch_id: str)` (`acks_late=True`; `asyncio.run`), `POST /uploads` and `POST /uploads/rows` when `upload_inline` is true, and `app/seed/cli.py` in-process with `source=<path>` (D22). The worker runs with `--concurrency=1`, so batches never overlap; this keeps cross-institution duplicate detection free of races.

`default_engines()` imports the engine modules inside the function, never at module import time, so the pipeline branch imports and tests cleanly before the engines branch is merged. Pipeline tests always pass a fake `EngineSuite` (§14).

### 4.2 Stages, in order (D15)

| # | `stage` | `status` | work items (`stage_total`) | what happens | engine call |
|---|---|---|---|---|---|
| 1 | `PARSE` | VALIDATING | rows | read the spool file, path or rows; CSV (UTF-8, BOM allowed) or XLSX (first sheet); normalise and check the header; build raw rows with `row_no`; set `total_rows` | none |
| 2 | `VALIDATE` | VALIDATING | rows | field rules and row errors (API_CONTRACT §A2.2, §A2.3); one query for the institution's programmes and approvals | none |
| 3 | `FILE_DUPLICATES` | VALIDATING | rows | identity collisions inside the file give DUPLICATE_IN_FILE on the later row | `engines.normalise_name` (provisional key) |
| 4 | `UPSERT` | PROCESSING | accepted rows | resolve identity, upsert students and enrolments (§5) | `engines.normalise_name`, `engines.name_key` |
| 5 | `LEDGER` | PROCESSING | accepted enrolments | releases and assignments | `engines.assign_seats(session, chunk, actor_id=...)` |
| 6 | `CHECKS` | PROCESSING | the check set (§4.4) | five checks | `engines.run_checks(session, chunk, adapters, concurrency=settings.checks_concurrency, actor_id=...)` |
| 7 | `DUPLICATES` | PROCESSING | created and updated ACTIVE enrolments | within and across institutions | `engines.detect_duplicates(session, batch.institution_id, batch.academic_year, chunk, actor_id=...)` |
| 8 | `FLAGS` | PROCESSING | touched pools | refresh EXCESS_ADMISSION and QUOTA_BREACH evidence with the final numbers | `engines.refresh_seat_flags(session, pools, actor_id=...)` once |
| 9 | `DONE` | DONE | | finalise `counts`, `finished_at`, delete the spool file, audit the batch | none |

A file-level failure in PARSE (unreadable, not CSV or XLSX, no data rows, a required header missing, more than `upload_max_rows` rows) sets FAILED with `error` from API_CONTRACT §A2.7 and stops. Nothing after PARSE fails the batch for data reasons.

LEDGER chunk order: enrolments whose status this batch changed to WITHDRAWN or TRANSFERRED come first, then the rest in row order, so every release in a batch happens before any assignment.

### 4.3 Transactions, chunks and progress

- `run_batch` owns every session and every commit. Each chunk of at most `CHUNK_SIZE` (500) work items runs in its own `async with factory() as session:` block, and the chunk's work, its `upload_row_errors`, its audit entries and the batch's `stage`, `stage_total` and `processed_rows` are committed together in that one transaction. Progress is therefore saved at least every 500 rows (D15) and is never ahead of the data.
- Engine functions never call `commit()`, `rollback()` or `close()` and never open their own session. They may `flush()`.
- On an exception: roll back the chunk, open a new session, set `status = FAILED`, keep `stage`, set `error = "Processing stopped while <stage words>. Upload the file again; rows already saved are kept."` (no exception text that could carry PII; log the traceback), set `finished_at`, delete the spool file, commit. Committed chunks stay: re-uploading the file is the retry, and it is idempotent (§13).
- `actor_id` passed to engines and to audit entries: `batch.uploaded_by` for FILE and API batches, `None` (system) for SEED batches.
- `timings_ms[stage]` is wall time per stage, stored in `counts` at the end of each stage.

### 4.4 Which enrolments each engine receives

- LEDGER: every accepted enrolment of the batch (created, updated and unchanged). The ledger is idempotent, so unchanged ones cost a read.
- CHECKS, the check set: created and updated enrolments that are ACTIVE, plus `LedgerResult.seated` (backlog enrolments that just got a seat need SEAT and ADMISSION re-evaluated), plus accepted enrolments that have no check rows yet (a batch that failed earlier), plus accepted enrolments with any PENDING check other than STUDENT (retry). De-duplicated, row order.
- DUPLICATES: created and updated enrolments that are ACTIVE.
- FLAGS: the union of `touched_pools` from every LEDGER chunk, sorted by `(approval_id, seat_type)`.

### 4.5 Counts

`counts.rows = total_rows`; `accepted` and `errors` from VALIDATE and FILE_DUPLICATES (a row with any ERROR entry is rejected; `errors` counts rejected rows, not entries); `warnings` accepted rows with at least one WARNING; `created`, `updated`, `unchanged`, `withdrawn`, `transferred` from UPSERT; `seated = len(seated)` and `released = len(released)` summed over LEDGER chunks; `unseated` = batch enrolments that are ACTIVE and without a seat after LEDGER; `flags_raised` and `flags_updated` = the summed `FlagTally.created` and `.updated` of LEDGER, CHECKS, DUPLICATES and FLAGS; `sources` from `ChecksResult.calls` and `.unavailable`.

### 4.6 `progress_pct` (computed by the uploads router, never stored)

Stage weights: PARSE 5, VALIDATE 10, FILE_DUPLICATES 5, UPSERT 15, LEDGER 10, CHECKS 45, DUPLICATES 5, FLAGS 5 (sum 100). `progress_pct = floor(sum of the weights of finished stages + weight(stage) * processed_rows / max(stage_total, 1))`, 0 while QUEUED, 100 when DONE; a FAILED batch reports the value it had.

## 5. Upload modules (pipeline)

Internal to the pipeline branch; listed so the engines branch knows what the database will hold.

```python
# app/engine/upload/parse.py
def parse_upload(data: bytes | Path, filename: str) -> ParsedUpload: ...        # raises UploadFileError(code, message)
def parse_rows(rows: list[dict[str, Any]]) -> ParsedUpload: ...
# app/engine/upload/validate.py
def validate_rows(parsed: ParsedUpload, ctx: ValidationContext) -> ValidationResult: ...   # pure
def file_duplicates(rows: list[CleanRow], normalise_name: Callable[[str], str]) -> ValidationResult: ...
# app/engine/upload/upsert.py
async def upsert_rows(session, batch: UploadBatch, rows: Sequence[CleanRow], *, engines: EngineSuite,
                      actor_id: uuid.UUID | None) -> UpsertResult: ...
```

Rules the engines rely on:

1. **Identity** (D14), in this order. (a) A usable APAAR (12 digits after removing spaces, and consent LINKED or blank) resolves by `students.apaar_hmac`. If no student has it but this institution's provisional student for the row exists (same provisional id as rule c), that student is upgraded in place (APAAR fields set, `consent_status = LINKED`), so a later consent does not create a duplicate. (b) Else a passport number resolves by `students.passport_hmac` (oldest match). (c) Else the provisional id `"PRV-" + base32(hmac_bytes(f"{aicte_id}|{normalise_name(name)}|{dob ISO}|{normalise(mobile, 'mobile')}", "generic"))[:8]` (the Week 1 `provisional_id_for` with the new normaliser) resolves by `students.provisional_id`; `normalise_name` is `engines.normalise_name`. Every student without an APAAR gets a provisional id; international students too.
2. **Students**: `name` as uploaded, `name_normalized = engines.normalise_name(name)`, `name_key = engines.name_key(name, dob)`, HMAC, Fernet and last-4 columns as in Week 1 plus `passport_encrypted`. An APAAR student's fields are last-writer-wins; every change is audited with masked values only.
3. **APAAR problems**: an APAAR that would be used but is malformed is dropped, the student is resolved by rule (b) or (c), `enrolments.apaar_problem` gets the reason ("has 11 digits, expected 12" or "contains characters other than digits") and the row carries an APAAR_FORMAT WARNING. The engines read `apaar_problem` (IDENTITY fails with INVALID_APAAR).
4. **Consent**: APAAR is used only when consent is LINKED (given or derived from a blank with an APAAR present). REFUSED, PENDING or INTERNATIONAL with an APAAR present: the APAAR is not stored and the row gets a CONSENT_CONFLICT WARNING. LINKED with no APAAR is stored as PENDING with the same warning.
5. **CIWG**: an INTERNATIONAL-route row with nationality `IN` is a CIWG student (children of Indian workers in the Gulf are Indian nationals). Nothing is stored for it; the ledger derives it from route and nationality.
6. **Enrolments** upsert on `(student_id, institution_id, programme_id, academic_year)`. Compared fields: `year_of_study`, `admission_route`, `counselling_ref`, `category`, `status`, `admission_date`, `apaar_problem`. Blank `status`: ACTIVE for a new enrolment, unchanged for an existing one. Blank `admission_date`: the upload date for a new enrolment, unchanged otherwise. `status_date`: the given date, else the upload date when the status changes, else unchanged. `cohort_year` is recomputed on every write. `upload_batch_id` and `source_row_no` are set on create and on update and left alone when unchanged. A WITHDRAWN or TRANSFERRED row with no earlier enrolment creates one in that status (no seat, no checks) and carries a NOT_PREVIOUSLY_ENROLLED WARNING. `GRADUATED` is never set by an upload.
7. **Programme code** resolves within the institution; when a code exists in both shifts the FIRST shift is used (as in Week 1).
8. `kind` is INITIAL when the institution has no earlier DONE batch for the academic year, else UPDATE. The declaration is stored on the batch (`declared_at`, `declaration_text`).
9. The spool file is the upload Fernet-encrypted with `PII_FERNET_KEY` at `<upload_spool_dir>/<batch_id>.<csv|xlsx|json>.enc`, written by the api before the batch is committed as QUEUED and deleted when the batch is DONE or FAILED.

## 6. `app/engine/matching.py` (engines, pure functions, D17)

```python
def transliterate(raw: str) -> str: ...                 # Devanagari runs to Latin; anything else unchanged
def normalise_name(raw: str) -> str: ...                # idempotent
def match_names(a: str, b: str) -> NameMatch: ...       # raw or normalised inputs
def name_key(name: str, dob: date) -> str: ...          # raw or normalised name
def verdict(score: int) -> NameVerdict: ...             # thresholds from rules.yaml name_matching
```

`normalise_name`, in this order:

1. Devanagari (U+0900 to U+097F) runs go through `indic_transliteration.sanscript.transliterate(run, DEVANAGARI, ITRANS)`, then word-final schwa deletion (a word that ends in a bare consonant loses the trailing inherent "a": कुमार gives `kumar`, शर्मा gives `sharma`).
2. Unicode NFKD, combining marks dropped, lower case.
3. Anything other than `a-z`, `0-9` and spaces becomes a space.
4. Honorific tokens dropped: `mr ms mrs dr shri smt kumari km sri`.
5. `mohd md mohammad muhammad mohammed` become `mohammed`.
6. Spaces collapsed, ends trimmed.

The output of `normalise_name` is what is sent to the APAAR registry and the counselling list and stored in `students.name_normalized`. It must not add other spelling folds: the mock registry normalises its own names with steps 2 to 6 (`services/mockgov/app/names.py`), and extra folds on one side only would lower genuine scores. Spelling folds (`aa` to `a`, `ee` and `ii` to `i`, `oo` and `uu` to `u`, and any others the engines branch adds) apply only inside `match_names` when two names are compared.

`match_names(a, b)`: normalise both; equal gives 100 and `EXACT`. Otherwise apply the spelling folds. If either side has a single-letter token, try the initials path: the last tokens (surnames) must score at least 90 with `rapidfuzz.fuzz.ratio`, and every other token of the shorter name must align, in order, with a token of the longer one (an initial matches a token starting with that letter; a full token matches a token scoring at least 90). When every token aligns the score is between 90 and 99 (never 100), method `INITIALS`. Otherwise the score is `round(rapidfuzz.fuzz.token_set_ratio(a, b))`, method `FUZZY`. `verdict`: `MATCH` at `pass_threshold` (90) and above, `REVIEW` from `review_threshold` (75) up to 89, `NO_MATCH` below 75.

`name_key(name, dob)`: tokens of `normalise_name(name)`; first initial = first letter of the first token (`?` when there is none); surname = the last token; `f"{dob.isoformat()}|{initial}|{jellyfish.metaphone(surname)}"` (jellyfish returns upper case; empty surname gives an empty last part).

Must pass (unit tests, in `tests/engines/test_matching.py`):

| call | expected |
|---|---|
| `normalise_name("Shri. R. K. Sharma")` | `"r k sharma"` |
| `normalise_name("Mohd. Irfan Khan")`, `("Md Irfan Khan")`, `("Muhammad Irfan Khan")` | `"mohammed irfan khan"` |
| `normalise_name("रवि कुमार शर्मा")` | `"ravi kumar sharma"` |
| `normalise_name(normalise_name(x)) == normalise_name(x)` | true for every name in the test set |
| `match_names("R. K. Sharma", "Ravi Kumar Sharma")` | score 90 to 99, `INITIALS`, `MATCH` |
| `match_names("Ravi Kumar Sharma", "Ravi Kumar Sharma")` | 100, `EXACT` |
| `match_names("Mohd Irfan Khan", "Mohammed Irfan Khan")` | 100, `EXACT` |
| `match_names("Ravi Sharma", "Ravi Kumar Sharma")` | at least 90 |
| `match_names("रवि कुमार शर्मा", "Ravi Kumar Sharma")` | at least 90 |
| `match_names("S. K. Sharma", "Ravi Kumar Sharma")` | below 90 |
| `match_names("R. K. Sharma", "Rohit Kumar Verma")` | below 75 |
| `name_key("R. K. Sharma", date(2007, 3, 21))` and `name_key("Ravi Kumar Sharma", date(2007, 3, 21))` | both `"2007-03-21\|r\|XRM"` |

## 7. `app/engine/ledger.py` (engines, D16)

```python
async def assign_seats(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID], *, actor_id: uuid.UUID | None
) -> LedgerResult: ...
```

Target pool of an ACTIVE enrolment: the approval for `(programme_id, cohort_year)` and the seat type `rules.admission_routes[admission_route].pool`. An enrolment is correctly seated when it holds an ASSIGNED seat in exactly that pool.

1. Load the enrolments for the ids (unknown ids are ignored).
2. **Releases first.** An enrolment that is not ACTIVE and holds a seat, or is ACTIVE and holds a seat that is not its target pool (route or year of study changed), releases it: seat `status = FREE`, `seat.enrolment_id = NULL`, `enrolment.seat_id = NULL`, a `RELEASE` seat event with `effective_date = enrolment.status_date` and `reason` `withdrawal`, `transfer` or `route or year changed`.
3. **Assignments per touched pool.** For every target pool of an input enrolment, the queue is every ACTIVE enrolment of that pool that is unseated, including earlier ones not in the input (the backlog), ordered by `(admission_date, uploaded_at, source_row_no, id)`. Free seats are taken with `SELECT id FROM seats WHERE pool_id = :pool AND status = 'FREE' AND <reserved filter> ORDER BY seat_code LIMIT :n FOR UPDATE SKIP LOCKED` (n = 1, or the queue length as a bulk form with the same semantics). Reserved filter: in the INTERNATIONAL pool a CIWG student (INTERNATIONAL route, nationality `IN`) takes `reserved_for = 'CIWG'` seats first, then unreserved ones; everyone else takes only `reserved_for IS NULL`. Other pools have no filter.
4. Each assignment sets the seat `ASSIGNED` with `enrolment_id`, sets `enrolment.seat_id`, and appends an `ASSIGN` seat event with `effective_date = enrolment.admission_date`.
5. **LATE_REFILL**: when the seat already has a `RELEASE` event, the approval has a `cutoff_date`, and `admission_date > cutoff_date`, raise LATE_REFILL (MEDIUM) through `flags.raise_flag` and add the enrolment to `late_refills`.
6. The ledger does not raise EXCESS_ADMISSION or QUOTA_BREACH; it reports `touched_pools` and the FLAGS stage calls `refresh_seat_flags` once with the final numbers.

Why the backlog: an earlier unseated admission gets a seat that frees up before a newer one, so per pool `seated = min(admitted, capacity)` always holds and the excess evidence adds up ("132 admitted, 120 seated, 12 without a seat"). A backlog admission dated before the cutoff never raises LATE_REFILL.

## 8. `app/engine/checks/` (engines, D18)

```python
# app/engine/checks/__init__.py
async def run_checks(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID], adapters: AdapterSet, *,
    concurrency: int = DEFAULT_CHECK_CONCURRENCY, actor_id: uuid.UUID | None = None,
) -> ChecksResult: ...

async def recheck_pending(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID], adapters: AdapterSet, *,
    concurrency: int = DEFAULT_CHECK_CONCURRENCY, actor_id: uuid.UUID | None = None,
) -> RecheckResult: ...

# app/engine/checks/<identity|admission|seat|studying|student>.py
async def evaluate(subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore) -> CheckOutcome: ...
```

`CheckSubject` (frozen dataclass in `checks/base.py`, engines-internal) carries everything an evaluator needs so evaluators never touch the session: enrolment, student, institution (`aicte_permanent_id`, name, state code and name), programme (`code`, `mode`), `academic_year`, `cohort_year`, `year_of_study`, `admission_route`, `counselling_ref`, `status`, the held seat (`seat_code`, `seat_type`, whether its pool belongs to the cohort approval), the target seat type and that pool's capacity (None when there is no cohort approval), `name`, `name_normalised`, `dob`, `nationality`, `consent_status`, `apaar_last4`, `apaar_problem`, and the decrypted `apaar_id` and `passport_no` (in memory only; never logged, never put in `detail`).

`run_checks`:

1. Load subjects for the ids that are ACTIVE (others are skipped and not counted), one query per chunk.
2. Evaluate the five checks for every subject with `asyncio.gather`. `gate = asyncio.Semaphore(concurrency)` wraps every adapter call and nothing else (`async with gate: result = await adapters.apaar.verify(...)`). The session is never used inside the gather.
3. Write sequentially: upsert `checks` on `(enrolment_id, type)` with `status`, `source`, `detail`; `checked_at = now()` when the row is new or its status or detail changed; `attempts += 1` when the evaluation met an unavailable source. Raise every `FlagIntent` through `flags.raise_flag`. One audit entry per enrolment whose statuses changed (§12).

`recheck_pending` does the same for check types whose current status is PENDING, except STUDENT (which only the Week 3 student loop changes), and reports transitions in `RecheckResult`.

Source errors never give FAIL:

| exception | status | detail keys |
|---|---|---|
| `SourceUnavailable` | PENDING | `source_unavailable: true`, `source_error` (its `detail`, e.g. "HTTP 503") |
| `RealAdapterDisabled` | PENDING | `source_unavailable: true`, `source_disabled: true` |
| `AdapterRequestError` (4xx, our bug) | PENDING | `source_unavailable: true`, `source_error`; logged at ERROR |

Every `detail` carries `summary` (one sentence from API_CONTRACT §A2.14). No detail ever holds a full APAAR, passport or mobile.

### IDENTITY (source `APAAR`)

Call: `adapters.apaar.verify(apaar_id, subject.name_normalised, dob)`; thresholds from `rules.yaml`.

| condition, first match wins | status | flag |
|---|---|---|
| route INTERNATIONAL or consent INTERNATIONAL | NA | |
| `apaar_problem` set | FAIL | INVALID_APAAR, MEDIUM |
| no APAAR (consent REFUSED or PENDING) | NA | |
| `exists` false | FAIL | INVALID_APAAR, HIGH |
| `dob_match` false | FAIL | NAME_MISMATCH, MEDIUM |
| `name_score` at least 90 | PASS | |
| `name_score` 75 to 89 | PENDING, `needs_review: true` | NAME_MISMATCH, LOW |
| `name_score` below 75 | FAIL | NAME_MISMATCH, MEDIUM |

Detail keys: `summary`, `name_score`, `dob_match`, `needs_review`, `apaar_last4`.

### ADMISSION

| route | source | how | PASS | FAIL |
|---|---|---|---|---|
| COUNSELLING, TFW, LATERAL | `COUNSELLING` | `adapters.counselling.verify(state=<institution state code>, year=start_year(cohort_year), name=name_normalised, dob=dob, programme=programme_code, institution_aicte_id=<aicte id>)`, **without** `roll_no` | `found` | not found |
| MANAGEMENT, SPOT, NRI | `SEAT_LEDGER` | no call | the route's pool has capacity above 0 in the cohort approval and the enrolment holds a seat in it | otherwise |
| INTERNATIONAL | `SII` | `adapters.sii.verify(passport_no, name_normalised, nationality)` | `admitted` and `institution_aicte_id`, `programme` and `academic_year` equal ours (academic year compared with `cohort_year`) | otherwise |

The upload's `counselling_ref` is the allotment reference (`MHCET-2026-R1-004512`), not the roll number mockgov matches exactly, so it is not sent as `roll_no`. After a match the returned `allotment_ref` is compared with `counselling_ref`: equal or blank gives PASS; different still gives PASS with `ref_mismatch: true` and the summary says so. ADMISSION raises no flags in Week 2. Detail keys: `summary`, `round`, `allotment_ref`, `ref_mismatch`, `seat_type`.

### SEAT (source `SEAT_LEDGER`, no call)

PASS when the enrolment holds exactly one ASSIGNED seat in a pool of its cohort approval. FAIL otherwise, with `flag_type` (`EXCESS_ADMISSION` when the target pool is REGULAR, else `QUOTA_BREACH`), `seat_type` and `flag_dedupe_key` in `detail`, so the page can point at the flag; the flag itself comes from the FLAGS stage. Detail keys: `summary`, `seat_code`, `seat_type`, `flag_type`, `flag_dedupe_key`.

### STUDYING (source `ABC`)

- `year_of_study` 1: NA ("First year, no result yet.").
- No APAAR: NA.
- Completed years k = 1 to `year_of_study - 1`; year k's label is `year_label(start_year(academic_year) - (year_of_study - k))`; its expected semesters are `2k - 1` and `2k`. One `adapters.abc.credits(apaar_id, label)` call per year.
- Every call says `apaar_id_known` false: NA ("ABC has no record of this APAAR; see the Identity check."), so an unknown APAAR is not flagged twice.
- missing = expected semesters with no entry or with 0 credits. 0 missing: PASS. 1 missing: PENDING with `awaiting_semester`. 2 or more: FAIL and NO_ACADEMIC_ACTIVITY (MEDIUM).

Detail keys: `summary`, `expected`, `missing`, `semesters` (`[{academic_year, sem, credits}]`), `awaiting_semester`.

### STUDENT (source `STUDENT_NOTICE`, no call)

PENDING for every ACTIVE enrolment in Week 2, summary "Notice not sent yet.". The Week 3 student loop sets it.

## 9. `app/engine/duplicates.py` (engines, D19)

```python
async def detect_duplicates(
    session: AsyncSession, institution_id: uuid.UUID, academic_year: str,
    enrolment_ids: Sequence[uuid.UUID], *, actor_id: uuid.UUID | None = None,
) -> DuplicatesResult: ...
```

Only ACTIVE enrolments in `academic_year` take part. The repeated APAAR inside one file is not here: it is the DUPLICATE_IN_FILE row error from the pipeline's FILE_DUPLICATES stage.

| rule | candidates (blocked on `students.name_key`, which includes the date of birth) | pair qualifies when | flag |
|---|---|---|---|
| A, within the institution | same institution, different student, at least one of the two students without an APAAR | `match_names(...).score >= 90`, or both `mobile_hmac` present and equal | DUPLICATE_WITHIN_UPLOAD, MEDIUM, one flag |
| B, same student at two institutions | another ACTIVE enrolment of the same `student_id` at a different institution (same APAAR, or same passport) | always | modes allowed by `rules.yaml` `dual_enrolment.allowed_modes` (unordered): DUAL_ENROLMENT_ALLOWED, LOW; otherwise DUPLICATE_CROSS_INSTITUTION, HIGH. One flag per institution |
| C, no APAAR across institutions | different institution, at least one student without an APAAR | score at least 90 and both `mobile_hmac` present and equal | the same mode rule: DUAL_ENROLMENT_ALLOWED, LOW; otherwise DUPLICATE_CROSS_INSTITUTION, MEDIUM. One flag per institution |

Flag shape:

- Rule A: `institution_id` the institution; `programme_id` the shared programme or null; `enrolment_id` the suspected copy (the one whose student has no APAAR; when both lack one, the later by `(uploaded_at, source_row_no, id)`); `related_enrolment_ids` both.
- Rules B and C: two flags, one per side, so each institution's flags tab and each regional officer sees it. Each side's flag has that side's `institution_id`, `programme_id` and `enrolment_id`; `related_enrolment_ids` both. The evidence `summary` names both institutions; `summary_for_institution` names only "another institution in {state_name}"; a fact that names the other institution carries `audience: "OFFICER"` and has an `audience: "INSTITUTION"` twin without the name (API_CONTRACT §A2.17).

## 10. `app/engine/flags.py` and `app/engine/evidence.py` (engines, D20)

```python
async def raise_flag(
    session: AsyncSession, *, type: FlagType, severity: Severity, institution_id: uuid.UUID,
    programme_id: uuid.UUID | None, enrolment_id: uuid.UUID | None, academic_year: str,
    dedupe_key: str, evidence: dict[str, Any], actor_id: uuid.UUID | None,
    replace_related: bool = False,
) -> RaisedFlag: ...

async def refresh_seat_flags(
    session: AsyncSession, pools: Sequence[PoolRef], *, actor_id: uuid.UUID | None = None
) -> FlagTally: ...

def dedupe_key(type: FlagType, *parts: object) -> str: ...   # ":".join([type.value, *map(str, parts)])
```

`raise_flag` is an upsert by `dedupe_key` (`INSERT ... ON CONFLICT (dedupe_key) DO NOTHING`, then `SELECT ... FOR UPDATE`):

- New: status OPEN, `opened_at = now()`, `flags.related_enrolment_ids = evidence["related_enrolment_ids"]`. Audit CREATE.
- Existing: `summary`, `summary_for_institution`, `facts`, `rule_source` and `data` are replaced by the new evidence; `related_enrolment_ids` becomes the union (old order, then new ids) unless `replace_related=True`, in which case it is the new list; severity becomes the higher of old and new (never lowered automatically); `status`, `assignee_id`, `opened_at` never change; `programme_id` and `enrolment_id` are filled only if they were null. `changed` is true when anything differs, and only then does `updated_at` move and an UPDATE audit entry get written.
- Raises `ValueError` when `evidence` lacks a non-empty `summary`, `facts` is not a list of `{label, value, source}` or `related_enrolment_ids` is not a list.
- Never deletes a flag and never resolves one. A flag whose cause has gone (a re-seated backlog, a corrected APAAR) stays OPEN with refreshed evidence until an officer acts in Week 3.

`refresh_seat_flags(pools)`: for each pool's approval, compute the REGULAR (EXCESS_ADMISSION) view and the touched pool's own view, and raise or update a flag when that pool has ACTIVE enrolments without a seat, or update the existing flag when one is already there (`replace_related=True`).

- EXCESS_ADMISSION (REGULAR pool): `approved` = `approved_intake`; `admitted` = ACTIVE enrolments with this programme and `cohort_year` whose route maps to REGULAR or NRI (the pools inside the intake); `seated` = ASSIGNED seats in the approval's REGULAR and NRI pools; `unseated = admitted - seated`; related = those unseated enrolments. Severity HIGH.
- QUOTA_BREACH (any other pool T): `capacity` = T's capacity; `admitted` = ACTIVE cohort enrolments whose route maps to T; `unseated` = those without a seat. Severity MEDIUM, HIGH when T is INTERNATIONAL or NRI and `unseated > 2`.
- `evidence.data = {approved | capacity, admitted, seated, unseated, peak_unseated}` with `peak_unseated` the highest value ever written; `academic_year` = the roll year of the pool's ACTIVE enrolments.

Severity table (D16 to D19): EXCESS_ADMISSION HIGH; QUOTA_BREACH MEDIUM or HIGH as above; LATE_REFILL MEDIUM; INVALID_APAAR HIGH when the registry says the id does not exist, MEDIUM when the uploaded id was malformed; NAME_MISMATCH MEDIUM below 75 or on a date-of-birth mismatch, LOW from 75 to 89; DUPLICATE_WITHIN_UPLOAD MEDIUM; DUPLICATE_CROSS_INSTITUTION HIGH with a shared APAAR or passport, MEDIUM without; DUAL_ENROLMENT_ALLOWED LOW; NO_ACADEMIC_ACTIVITY MEDIUM.

`dedupe_key` per flag type (UUIDs in canonical lower case; `low` and `high` are the two enrolment ids in string order):

| type | `dedupe_key` | raised by |
|---|---|---|
| EXCESS_ADMISSION | `EXCESS_ADMISSION:{programme_id}:{cohort_year}:REGULAR` | `refresh_seat_flags` |
| QUOTA_BREACH | `QUOTA_BREACH:{programme_id}:{cohort_year}:{seat_type}` | `refresh_seat_flags` |
| LATE_REFILL | `LATE_REFILL:{seat_id}:{enrolment_id}` | ledger |
| INVALID_APAAR | `INVALID_APAAR:{enrolment_id}` | IDENTITY check |
| NAME_MISMATCH | `NAME_MISMATCH:{enrolment_id}` | IDENTITY check |
| NO_ACADEMIC_ACTIVITY | `NO_ACADEMIC_ACTIVITY:{enrolment_id}` | STUDYING check |
| DUPLICATE_WITHIN_UPLOAD | `DUPLICATE_WITHIN_UPLOAD:{low}:{high}` | duplicates rule A |
| DUPLICATE_CROSS_INSTITUTION | `DUPLICATE_CROSS_INSTITUTION:{low}:{high}:{institution_id}` | duplicates rules B and C |
| DUAL_ENROLMENT_ALLOWED | `DUAL_ENROLMENT_ALLOWED:{low}:{high}:{institution_id}` | duplicates rules B and C |

Example: `EXCESS_ADMISSION:0b6f...e1:2026-27:REGULAR`. STUDENT_DENIED, GHOST_RING and ANOMALY are not raised in Week 2.

`app/engine/evidence.py` holds one builder per flag type and per check outcome. Each returns the dict described in API_CONTRACT §A2.17 (flags) or the `detail` of §A2.14 (checks), with the sentences exactly as written there. Officers and the web read these sentences verbatim; the web never rebuilds them.

## 11. `app/engine/score.py` (engines)

```python
def score(statuses: Iterable[CheckStatus | str]) -> tuple[int, int] | None: ...   # (passes, applicable); None when there are no checks
def countersign(checks: Iterable[Check]) -> dict[str, Any]: ...   # {"score": {"passes", "applicable"} | None, "checks": [{"type", "status"}]} in CHECK_ORDER
def is_countersigned(statuses: Iterable[CheckStatus | str]) -> bool: ...   # applicable >= 1 and passes == applicable
def is_clear(statuses: Iterable[CheckStatus | str]) -> bool: ...           # at least one check and none FAIL
def countersign_state_sq(...): ...  # SQL per enrolment: countersigned (bool), clear (bool), for the dashboard
```

applicable = checks whose status is not NA; passes = PASS. PENDING is applicable and not a pass (D18). An enrolment with no check rows has `score` None and is left out of both percentages (API_CONTRACT §A2.18).

## 12. Audit chain calls

Every write goes through `app.core.audit.record_many` in the caller's transaction, once per engine call or chunk (one advisory-lock acquisition), never per row. No payload carries a name, a full id, a mobile, an email or an address.

| writer | `entity_type` | `action` | `entity_id` | `before` / `after` |
|---|---|---|---|---|
| uploads router (POST) | `upload_batch` | CREATE | batch | after `{institution_id, academic_year, source, filename, file_sha256}` |
| pipeline, DONE or FAILED | `upload_batch` | UPDATE | batch | after `{status, stage, counts without sources}` |
| pipeline, UPSERT | `student` | CREATE or UPDATE | student | after `{apaar_last4, provisional_id, consent_status, changed: [field names]}` |
| pipeline, UPSERT | `enrolment` | CREATE or UPDATE | enrolment | after `{student_id, programme_id, academic_year, year_of_study, admission_route, status, batch_id, row_no}` |
| ledger | `seat` | UPDATE | seat | before `{status, enrolment_id}`, after `{status, enrolment_id, event: "ASSIGN" or "RELEASE", reason, effective_date}` |
| checks | `enrolment` | UPDATE | enrolment | before and after `{"checks": {"IDENTITY": "PASS", ...}}`, only when a status changed |
| flags | `flag` | CREATE or UPDATE | flag | after `{type, severity, status, dedupe_key, summary}`; UPDATE also before `{severity, summary}` |
| seed | as above with `actor_id` null, plus one `SEED` entry per file with counts | | | |
| GET endpoints returning student rows (enrolment detail, flag detail related rows) | `student` | READ | student | via `record_read` |

## 13. Idempotency

- Re-uploading a file: every row is `unchanged`, so no student, enrolment or audit write; the ledger sees correctly seated enrolments and does nothing; only enrolments with a PENDING check (other than STUDENT) or with no checks are re-checked; duplicates and flags hit their dedupe keys. Counts: `created 0, updated 0, seated 0, flags_raised 0`.
- `assign_seats` on a correctly seated enrolment is a no-op; releases and assignments happen only on real change, so seat events and audit entries are never duplicated.
- `run_checks` twice gives the same rows; `checked_at` moves only on change.
- `raise_flag` with the same key and the same evidence returns `changed=False` and writes nothing.
- A FAILED batch leaves committed chunks; re-uploading completes the rest (§4.4 includes enrolments with no checks).

## 14. Building in parallel: fakes and the tests that prove the decisions

backend-pipeline codes against `EngineSuite` with a fake in `tests/pipeline/fakes.py`, for example:

```python
class FakeEngines:
    def normalise_name(self, raw: str) -> str:
        return crypto.normalise_name(raw)            # Week 1 helper is good enough for tests

    def name_key(self, name: str, dob: date) -> str:
        tokens = crypto.normalise_name(name).split() or ["?"]
        return f"{dob.isoformat()}|{tokens[0][0]}|{tokens[-1].upper()}"

    async def assign_seats(self, session, enrolment_ids, *, actor_id):
        return LedgerResult()

    async def run_checks(self, session, enrolment_ids, adapters, *, concurrency=32, actor_id=None):
        return ChecksResult(enrolments=len(enrolment_ids))

    async def detect_duplicates(self, session, institution_id, academic_year, enrolment_ids, *, actor_id=None):
        return DuplicatesResult()

    async def refresh_seat_flags(self, session, pools, *, actor_id=None):
        return FlagTally()
```

backend-engines builds its database fixtures directly with the ORM (institution, programme with `mode`, approval with pools from `engine.seatpools.build_for_approval`, students with `name_key`, enrolments with `cohort_year`) and the `InMemory*` adapters (`GOV_ADAPTER=inmemory`), using their `down` switch for outages.

Tests each branch owes (they mirror the Week 2 verification list):

| branch | test |
|---|---|
| engines | ABC CSE shape: approval 120 (pools 114, 6, 6, 12, 18), 132 first-years (126 REGULAR routes, 6 NRI): 120 seated, 12 unseated, one EXCESS_ADMISSION whose summary starts "132 admitted against 120 approved seats in CSE (2026-27)" |
| engines | "R. K. Sharma" without APAAR and "Ravi Kumar Sharma" with APAAR, same date of birth and mobile, same institution: one DUPLICATE_WITHIN_UPLOAD linking both |
| engines | same APAAR ACTIVE in a PHYSICAL and an ODL programme at two institutions: two DUAL_ENROLMENT_ALLOWED (LOW); two PHYSICAL: two DUPLICATE_CROSS_INSTITUTION (HIGH) |
| engines | second-year with 0 credits in both semesters of 2025-26: STUDYING FAIL and NO_ACADEMIC_ACTIVITY |
| engines | APAAR adapter down: IDENTITY PENDING with `source_unavailable`; adapter up and `recheck_pending`: PASS |
| engines | withdrawal releases the seat (seat FREE, RELEASE event); a refill with `admission_date` after `cutoff_date` raises LATE_REFILL; a backlog admission dated before the cutoff does not |
| engines | every flag type's evidence passes the schema check in `raise_flag`; every summary matches its template |
| pipeline | each row error code in API_CONTRACT §A2.3, with level and message |
| pipeline | re-upload of the same file: all rows unchanged, no new audit entries for students or enrolments |
| pipeline | progress is committed per chunk of 500 and `progress_pct` never goes backwards |
| pipeline | a stage exception marks the batch FAILED with a PII-free `error` and keeps earlier chunks |
| pipeline | seed through `run_batch` with the mini fixture, initial files before update files |

## 15. Known limits in Week 2

- One roll year (2026-27). A seat is held by an enrolment row, so carrying a student into a second roll year (a second enrolment row for the same cohort) is not handled yet.
- The TFW "filled at least 50% last year" condition and the lateral pool's "plus first-year vacancies" are not applied; both pools are built as in Week 1.
- Student fields of an APAAR student are last-writer-wins across institutions.
- Flags are not resolved automatically when the cause goes away; officers clear them from Week 3.
- A programme code offered in both shifts resolves to the FIRST shift.
- mockgov folds `mohd`, `md`, `mohammad` and `mohammed` but not `muhammad`; until it does, a registry name spelt "Muhammad" scores below 100 against our `mohammed`.
