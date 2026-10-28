# Engines (internal Python contract, Weeks 2 and 3)

This file is the only thing the api's code areas may assume about each other's Python code. Sections 1 to 15 are Week 2; section 16 adds Week 3. `API_CONTRACT.md` (Addendum 2) is the wire contract, `DATA_MODEL.md` ("Migration 0002") is the schema and `DECISIONS.md` D14 to D22 are the rules being implemented. If a function, field or behaviour another branch needs is not written here, add it here first.

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
| `app/routers/dashboard.py`, `institutions.py`, `students.py`, `_stats.py`; `app/schemas/common.py`, `dashboard.py`, `institutions.py`, `students.py` | engines | count and countersign changes, including `admitted` (API_CONTRACT §A2.10, §A2.18 to §A2.21) |
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
3. **APAAR problems**: an APAAR that would be used but is malformed is dropped, the student is resolved by rule (b) or (c), `enrolments.apaar_problem` gets the reason ("has 11 digits, expected 12" or "contains characters other than digits"), consent is stored as PENDING, and the row carries an APAAR_FORMAT WARNING (not CONSENT_CONFLICT). The engines read `apaar_problem` (IDENTITY fails with INVALID_APAAR).
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
5. `mohd md mohammad muhammad mohamed muhammed mohammed` become `mohammed` (the same seven spellings mockgov folds).
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
- Route `LATERAL` in year 2: NA ("Joined in year 2 as a lateral entrant; no completed year to check yet."). A lateral entrant joined in year 2, so its completed years start at k = 2: a year-3 lateral is checked on year 2 only.
- No APAAR: NA.
- Completed years k = 1 (2 for `LATERAL`) to `year_of_study - 1`; year k's label is `year_label(start_year(academic_year) - (year_of_study - k))`; its expected semesters are `2k - 1` and `2k`. One `adapters.abc.credits(apaar_id, label)` call per year.
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
- QUOTA_BREACH (any other pool T): `capacity` = T's capacity; `admitted` = ACTIVE cohort enrolments whose route maps to T; `unseated` = those without a seat; related = those unseated enrolments. Severity MEDIUM, HIGH when T is INTERNATIONAL or NRI and `unseated > 2`.
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

applicable = checks whose status is not NA; passes = PASS. PENDING is applicable and not a pass (D18). An enrolment with no check rows has `score` None and is left out of both percentages (API_CONTRACT §A2.19).

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

Tests each branch owes (the demo scenarios plus the edges of this contract):

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
- mockgov folds the same seven Mohammed spellings and drops the same honorifics (including `km` and `sri`) since 2026-10-28, so registry scores and our matcher agree on these.

## 16. Week 3: notices, the Student check, cases, credentials, verifier, degrees, privacy and audit reads

The wire contract is `API_CONTRACT.md` Addendum 3, the schema `DATA_MODEL.md` "Migration 0003" (already on `main`), the rules DECISIONS D23 to D33. Sections 1 to 15 still hold. This section fixes the Python packages, the function signatures one area calls in another, and who opens and commits transactions, so the four code areas below can be built side by side. If a function another area needs is not written here, add it here first.

Areas: **notices** (notices, the Student check, resends, seed replies), **cases** (flag actions, attachments, history, users, privacy, audit reads and the tamper tool), **credentials** (keys, issuance, wallet, verifier, status list, degrees), **seed data** (datagen, mockgov, the graduates importer), and **web**. Small result and query types named in the signatures below (`ReplyOutcome`, `DeliveryTally`, `NoticeContext`, `ActionResult`, `CredentialFilters`, `GraduateQuery`, `DataRequestQuery`) are internal to their area; only the functions and the dataclasses spelled out here cross areas.

### 16.1 Ownership

| Path (under `services/api/` unless rooted) | Area | Notes |
|---|---|---|
| `app/notices/` (`__init__.py`, `mailer.py`, `dispatch.py`, `service.py`, `student_check.py`) | notices | §16.3. `mailer.py` is also used by cases |
| `app/routers/notices.py`, `app/schemas/notices.py` | notices | `GET` and `POST /notices/{token}`, `POST /enrolments/{id}/notices/resend` |
| `app/engine/checks/student.py`; in `app/engine/checks/base.py` the new `CheckSubject` fields; in `app/engine/checks/__init__.py` their loading in `load_subjects` and the new `refresh_student` | notices | §16.4 |
| `app/routers/students.py`, `app/schemas/students.py` (`notices`, `credentials` of `/students/me`); `app/routers/enrolments.py`, `app/schemas/enrolments.py` (`notices`, `resend`, `credentials` of enrolment detail); the `issue_if_eligible` call after `POST /enrolments/{id}/recheck` and `POST /institutions/{id}/recheck` (`app/routers/institutions.py`) | notices | reads credentials through `holder.wallet_summary` and `holder.credential_refs` (§16.6) |
| `app/worker.py`: the new task `countersign.deliver_notices` and the requeue of QUEUED notices on start (`countersign.send_notices`, `enqueue_notices` and the chaining after DONE are in place) | notices | §16.3 |
| `app/adapters/inmemory/__init__.py`: `InMemoryDigiLocker.notify` raises `AdapterRequestError("digilocker", 404, ...)` for an APAAR it does not know, as mockgov now answers | notices | API_CONTRACT §A3.2 |
| the uploads router: `send_notices_for_batch` after `run_batch` when `UPLOAD_INLINE` is true | notices | |
| `app/seed/replies.py`; the notice step in `app/seed/cli.py`; the `seed` and `demo-reset` lines of the `Makefile` | notices | D31 |
| `app/cases/` (`__init__.py`, `transitions.py`, `service.py`, `attachments.py`) | cases | §16.5 |
| `app/routers/flags.py`, `app/schemas/flags.py` (filters, new fields, `history`, `allowed_actions`, `can_respond`); new `app/routers/cases.py` (actions, response, attachment download); new `app/routers/users.py` | cases | |
| `app/engine/flags.py`: the system note in `raise_flag` | cases | §16.5 |
| `app/privacy/` (`__init__.py`, `notice.py`, `service.py`); new `app/routers/privacy.py`, `app/schemas/privacy.py` | cases | §16.7 |
| `app/engine/upload/upsert.py`: one call to `privacy.service.record_apaar_link` | cases | §16.7 |
| `app/routers/admin.py`, `app/schemas/admin.py` (audit filters, `actor_role`, `via`); new `app/core/audit_tamper.py`; the `audit-tamper` line of the `Makefile` | cases | §16.8 |
| `app/credentials/` (`__init__.py`, `keys.py`, `issuer.py`, `holder.py`, `verifier.py`, `status_list.py`, `degree.py`) | credentials | §16.6; `revoke_for_enrolment` is already implemented in `__init__.py` |
| new `app/routers/credentials.py`, `issuer.py`, `verify.py`, `university.py` and their schemas | credentials | |
| `app/engine/ledger.py`: the call to `credentials.revoke_for_enrolment` | in place | §16.2 |
| `app/seed/graduates.py` and its call in `app/seed/importer.py` (in place); `tools/datagen/**`; `services/mockgov/**` | seed data | API_CONTRACT §A3.28 |
| `apps/web/**`; the `e2e` line of the `Makefile` | web | ARCHITECTURE §12 |
| `app/main.py` | every backend area | §16.9 |
| `app/models/**`, `alembic/**`, `app/core/config.py`, `.env.example`, `rules.yaml`, `docker-compose.yml`, `pyproject.toml`, `uv.lock` | nobody | in place with Migration 0003; change only by agreement |
| `app/core/audit.py`, `crypto.py`, `deps.py`, `errors.py`, `ratelimit.py`, `app/adapters/**` | nobody | read and call them |
| `tests/notices/`, `tests/cases/`, `tests/credentials/` | notices, cases, credentials | each area keeps its tests and its own `conftest.py` in its package |

### 16.2 The three fixed entry points

These are wired into existing code already and keep these names and signatures (extra keyword-only arguments with defaults are allowed).

```python
# app/credentials/__init__.py
async def revoke_for_enrolment(
    session: AsyncSession,
    enrolment_id: uuid.UUID,
    reason: str,
    actor_id: uuid.UUID | None,
    *,
    audit_sink: list[AuditEntry] | None = None,
) -> int: ...

async def issue_if_eligible(session: AsyncSession, enrolment_id: uuid.UUID) -> Credential | None: ...
    # a stub returning None today; becomes `return await issuer.issue_if_eligible(session, enrolment_id)`

# app/notices/dispatch.py
async def send_notices_for_batch(
    batch_id: uuid.UUID,
    *,
    factory: async_sessionmaker[AsyncSession] | None = None,   # default: app.db.session.session_factory()
    adapters: AdapterSet | None = None,                        # new; default: build_adapters(), closed at the end
    mailer: Mailer | None = None,                              # new; default: build_mailer()
) -> int: ...
```

**`revoke_for_enrolment`** (implemented). The Seat Ledger calls it in step 2 of `assign_seats` when it releases the seat of an enrolment that became WITHDRAWN or TRANSFERRED, inside the ledger's transaction and with the ledger's `audit_sink`; `cases.service` calls it on CONFIRM. It revokes every unrevoked credential of the enrolment (any kind), sets `revoked_at`, `revoked_reason` and `revoked_by_id` (`actor_id`: the batch's uploader, null for a seeded batch), writes one audit UPDATE per credential, flushes, never commits, and returns how many it revoked (0 is normal). One change is owed by the credentials area: it stores a reason **code** (API_CONTRACT §A3.18). The ledger passes its `REVOKE_REASONS` words, `Enrolment withdrawn` and `Enrolment transferred`; the function maps them to `ENROLMENT_WITHDRAWN` and `ENROLMENT_TRANSFERRED`, takes `FLAG_CONFIRMED` (and the three codes) as they are, raises `ValueError` for anything else, writes the code to `revoked_reason` and to the audit entry, and calls `status_list.invalidate()`. The ledger imports the package, never `issuer`, so the ledger never loads the SD-JWT code.

**`issue_if_eligible`.** Runs in the caller's transaction and never raises for an ineligible enrolment. Eligible (D26): the enrolment is ACTIVE; its STUDENT check is PASS; none of its checks is FAIL; no flag with status OPEN, DOCS_REQUESTED or ESCALATED and severity HIGH names it (as `enrolment_id` or in `related_enrolment_ids`, against its own institution, the rule of `_enrolment_rows.flags_for`); and it holds no unrevoked ENROLMENT credential. It locks the enrolment row (`SELECT ... FOR UPDATE`), creates the student's holder key if missing (§16.6), allocates a status-list index, signs the SD-JWT (API_CONTRACT §A3.15), inserts the `credentials` row inside a savepoint (a unique violation from the partial index means another transaction won: return None), writes an audit CREATE on `credential` with no actor (`after: {"kind", "enrolment_id", "short_id", "status_list_index"}`), flushes, and returns the new credential; otherwise None. Called after a reply (§16.3), after both recheck endpoints (for every enrolment rechecked), after a case CLEAR (the flag's `enrolment_id` and `related_enrolment_ids`), and by `send_notices_for_batch` for the batch's enrolments whose STUDENT check is PASS (an upload can clear the last FAIL after the student replied).

**`send_notices_for_batch`.** Owns its sessions and commits, like `run_batch` (§4.3). Returns the number of `notifications` rows it created, so a second run for the same batch creates nothing and returns 0. Steps:

1. Load the batch; anything but DONE returns 0.
2. The batch's ACTIVE enrolments (`enrolments.upload_batch_id = batch_id`) that need a notice (DATA_MODEL `notifications`); skip students whose latest NOTICE consent is WITHDRAWN and students with neither an email nor a linked APAAR.
3. `dispatch.create_notices` for them, in chunks of 500 enrolments, each chunk one transaction with its audit entries.
4. `dispatch.deliver` the new rows (§16.3).
5. In chunks of 500, one transaction each: `checks.refresh_student` for every enrolment of the batch (so UNREACHABLE and delivered states are written), then `issue_if_eligible` for those whose STUDENT check is PASS.

Callers: the Celery task `countersign.send_notices(batch_id: str) -> int`, queued by `run_batch_task` through `enqueue_notices` once a batch is DONE (in place); the uploads router after `run_batch` when `UPLOAD_INLINE` is true; and `app/seed/cli.py` once per batch, in upload order, after every upload (D31). The worker runs one task at a time, so a notice task never overlaps a batch.

### 16.3 `app/notices/`

```python
# app/notices/mailer.py
MAIL_BATCH = 500   # messages per SMTP connection (D23)

@dataclass(frozen=True, slots=True)
class MailMessage:
    to: str
    subject: str
    body: str                                   # plain text
    headers: Mapping[str, str] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class MailResult:
    ok: bool
    error: str | None = None                    # PII-free sentence for notifications.last_error
    transient: bool = False                     # worth another try

class Mailer(Protocol):
    def send_many(self, messages: Sequence[MailMessage]) -> list[MailResult]: ...   # one result per message, same order

class SmtpMailer:                               # stdlib smtplib; From = NOTICE_FROM
    def __init__(self, settings: Settings | None = None) -> None: ...
    def send_many(self, messages: Sequence[MailMessage]) -> list[MailResult]: ...

class MemoryMailer:                             # tests: keeps every message in .sent
    def send_many(self, messages: Sequence[MailMessage]) -> list[MailResult]: ...

def smtp_host_allowed(host: str, settings: Settings) -> bool: ...   # host in SMTP_ALLOWED_HOSTS, or ALLOW_REAL_SMTP
def build_mailer(settings: Settings | None = None) -> Mailer: ...   # SmtpMailer
```

- `send_many` is synchronous; async code calls `await asyncio.to_thread(mailer.send_many, messages)`.
- `SmtpMailer` checks the host on every call: a host that is not allowed fails every message with "Mail server not allowed." and opens no connection. It opens one connection per `MAIL_BATCH` messages (`SMTP_HOST`, `SMTP_PORT`). A refused recipient is "Email address was refused." (not transient); a connection or temporary error is "Mail server did not respond." (transient) for every message of that connection.
- The existing settings `mail_from` and `web_base_url` are superseded by `NOTICE_FROM` and `WEB_ORIGIN` and are not read by Week 3 code.

```python
# app/notices/dispatch.py
RETRY_PAUSES_SECONDS = (5, 20)   # before the second and the third try
MAX_ATTEMPTS = 3
DIGILOCKER_TRIP = 5              # consecutive unavailable calls that end a DigiLocker pass

def programme_short(name: str, code: str) -> str: ...            # API_CONTRACT §A3.1
def mint_token() -> tuple[str, str]: ...                          # (token, sha256 hex); secrets.token_urlsafe(32)
def notice_link(token: str) -> str: ...                           # f"{WEB_ORIGIN}/student/notices/{token}"
def notice_text(channel: NoticeChannel, facts: NoticeContext) -> tuple[str, str]: ...   # (subject or "", text without the link)

async def needs_notice(session: AsyncSession, enrolment_ids: Sequence[uuid.UUID]) -> list[uuid.UUID]: ...
async def create_notices(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID], *,
    resent_by_id: uuid.UUID | None, actor_id: uuid.UUID | None, now: datetime | None = None,
) -> list[Notification]: ...
async def deliver(
    factory: async_sessionmaker[AsyncSession], notification_ids: Sequence[uuid.UUID], *,
    adapters: AdapterSet, mailer: Mailer,
) -> DeliveryTally: ...
async def deliver_notices(notification_ids: Sequence[uuid.UUID], *, factory=None, adapters=None, mailer=None) -> int: ...
```

- **Tokens are minted at delivery, not at creation.** `create_notices` writes each row QUEUED with `token_hash` set to the hash of a random value nobody keeps (the column is NOT NULL and unique), `message` (text without link), `expires_at` = now + `notices.expiry_days`, and an audit CREATE on `notification` (`after: {"enrolment_id", "channel", "resent"}`). Each delivery try mints a fresh token, writes its hash, **commits**, and only then sends the link. So a plaintext token exists only in the process that sends it and in the message itself: it never sits in the database or in a queue, a resend can go through Celery safely, and a token from a failed try simply never works.
- **`deliver`**, in chunks of 500 rows, each chunk: one transaction to mint tokens and bump `attempts`; then the sends outside any transaction (email first, through one `send_many` per chunk; DigiLocker calls concurrently under a semaphore of `CHECKS_CONCURRENCY`, decrypting the APAAR in memory only); then one transaction to record `delivery_status`, `sent_at` and `last_error` (API_CONTRACT §A3.2 table). DigiLocker outcomes: a result with `delivered` true is SENT; `AdapterRequestError` with status 404 (mockgov's `APAAR_NOT_LINKED`) is FAILED "No DigiLocker account." at once; any other `AdapterRequestError` is FAILED "DigiLocker refused the notice." at once; `SourceUnavailable` is transient; `RealAdapterDisabled` is FAILED "DigiLocker is not connected." at once. `InMemoryDigiLocker` raises `AdapterRequestError(404)` for an APAAR it does not know, like mockgov. Rows that met a transient failure are tried again after `RETRY_PAUSES_SECONDS` in the same call; after `MAX_ATTEMPTS` they are FAILED. When `DIGILOCKER_TRIP` DigiLocker calls in a row are unavailable, the rest of that pass's DigiLocker rows are counted as a failed try without a call. Email never waits for DigiLocker.
- **`deliver_notices`** is the body of the Celery task `countersign.deliver_notices(notification_ids: list[str]) -> int` (used by resends); it delivers, then refreshes the STUDENT check of the enrolments involved (one transaction). `requeue_unfinished` in `app/worker.py` also enqueues `deliver_notices` for QUEUED rows created more than two minutes before the worker started, with fewer than three tries.

```python
# app/notices/service.py
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
# the change window is rules.yaml notices.change_window_days (7), read through app.core.rules

async def find_by_token(session: AsyncSession, token: str, *, for_update: bool = False) -> Notification: ...
    # 404 NOTICE_NOT_FOUND for a malformed or unknown token (identical error)
async def open_notice(session: AsyncSession, token: str) -> dict[str, Any]: ...
    # GET /notices/{token}: 410 rule, opened_at, READ audit, the §A3.3 body
async def respond(session: AsyncSession, token: str, response: NoticeResponse, comment: str | None) -> dict[str, Any]: ...
async def respond_for_enrolment(
    session: AsyncSession, enrolment_id: uuid.UUID, channel: NoticeChannel, response: NoticeResponse,
    comment: str | None, *, via: str = "demo-seed",
) -> Notification: ...                                          # seed replies (D31); no token needed
async def apply_reply(
    session: AsyncSession, notice: Notification, response: NoticeResponse, comment: str | None, *,
    via: str, now: datetime | None = None,
) -> ReplyOutcome: ...                                          # the one code path for both
async def resend(session: AsyncSession, enrolment: Enrolment, user: User) -> list[Notification]: ...
async def resend_state(session: AsyncSession, enrolment: Enrolment, user: User) -> dict[str, Any]: ...
async def notices_for_student(session: AsyncSession, student_id: uuid.UUID) -> list[dict[str, Any]]: ...
async def notices_for_enrolment(session: AsyncSession, enrolment_id: uuid.UUID) -> list[dict[str, Any]]: ...
def notice_state(notice: Notification, now: datetime) -> str: ...   # QUEUED, FAILED, AWAITING, EXPIRED, ANSWERED
```

- Services raise `app.core.errors.ApiError` with the Addendum 3 codes, so routers stay thin; the seed CLI catches `ApiError` per line.
- **`apply_reply`**, in the caller's transaction (the request's, or the seed chunk's): lock the notice (`FOR UPDATE`); apply rules 3 to 5 of API_CONTRACT §A3.4; audit UPDATE on `notification` with no actor and `after.via`; on YES, `privacy.service.record_consent(... NOTICE, GIVEN ...)`; `checks.refresh_student(session, [enrolment_id])`; when the answer changed from NO to YES, `cases.service.add_system_note(session, flag, REPLY_CHANGED_NOTE.format(changed_date=...))` on the enrolment's STUDENT_DENIED flag; finally `credentials.issue_if_eligible(session, enrolment_id)`.
- **`resend`** applies the order of API_CONTRACT §A3.5, then `create_notices(..., resent_by_id=user.id, actor_id=user.id)`; the router commits and enqueues `countersign.deliver_notices` (or calls `deliver_notices` inline when `UPLOAD_INLINE` is true).
- **`app/seed/replies.py`**: `python -m app.seed.replies --from DIR` reads `notice_replies.jsonl` (API_CONTRACT §A3.28), skips NONE lines, finds each enrolment by its initial upload batch (`upload_batches.filename` equal to the base name of `file`, source SEED) and `enrolments.source_row_no` = `row_no`, and calls `respond_for_enrolment` for the latest delivered notice of the line's `channel` (the latest notice of that channel when none was delivered). `reply_after_days` is not used. One transaction per 500 lines; prints the counts; a line that names nothing is reported and skipped.

```python
# app/notices/student_check.py
@dataclass(frozen=True, slots=True)
class NoticeFact:
    id: uuid.UUID
    channel: NoticeChannel
    delivery_status: NoticeDelivery
    sent_at: datetime | None
    expires_at: datetime
    response: NoticeResponse | None
    responded_at: datetime | None
    previous_response: NoticeResponse | None
    changed_at: datetime | None
    comment: str | None                 # in memory only; goes only into the officer-only evidence fact

async def load_notice_facts(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[NoticeFact, ...]]: ...
def derive(subject: CheckSubject, *, now: datetime | None = None) -> CheckOutcome: ...   # pure
def student_denied_evidence(notice: NoticeFact, *, enrolment_id: uuid.UUID) -> dict[str, Any]: ...
REPLY_CHANGED_NOTE = (
    "The student changed the reply from No to Yes on {changed_date}. "
    "The flag keeps its status until an officer decides."
)
```

`derive` implements the table of API_CONTRACT §A3.8 and returns a `CheckOutcome` of type STUDENT, source `STUDENT_NOTICE`, with one STUDENT_DENIED `FlagIntent` (HIGH, `dedupe_key` `STUDENT_DENIED:{enrolment_id}`) whenever a notice's current response is NO, or its `previous_response` is NO (the refreshed "then changed the reply to Yes" evidence). The STUDENT evidence and detail builders live in this module, not in `app/engine/evidence.py`; they use `evidence.fact` and `evidence.fmt_date`.

### 16.4 The STUDENT check inside the checks engine

`run_checks` keeps evaluating all five checks, so a re-upload re-derives STUDENT from the notices instead of resetting it.

- `CheckSubject` (`app/engine/checks/base.py`) gains three fields with defaults, after `passport_no`: `notices: tuple[NoticeFact, ...] = ()`, `has_email: bool = False`, `notice_consent_withdrawn: bool = False`. "Linked APAAR" is `consent_status is LINKED and apaar_last4 is not None`.
- `load_subjects` fills them with one extra query per chunk each (`student_check.load_notice_facts`, `students.email IS NOT NULL`, the latest NOTICE consent row).
- `app/engine/checks/student.py`: `evaluate(subject, adapters, gate)` returns `student_check.derive(subject)`; it makes no adapter call.
- New in `app/engine/checks/__init__.py`, the one way the notices area writes the STUDENT row:

```python
async def refresh_student(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID], *, actor_id: uuid.UUID | None = None
) -> ChecksResult: ...
```

It loads subjects, evaluates only STUDENT and writes through the same `_Writer` (check row, `checked_at` on change, flags through `raise_intents`, one audit UPDATE per enrolment whose status changed). Like every engine function it flushes and never commits. `recheck_pending` still skips STUDENT.

### 16.5 `app/cases/`

```python
# app/cases/transitions.py (pure)
OFFICER_ACTIONS: tuple[CaseActionKind, ...] = (CLEAR, REQUEST_DOCS, ESCALATE, CONFIRM, NOTE, ASSIGN, REOPEN)
NOTE_SHOWN_TO_COLLEGE: frozenset[CaseActionKind] = frozenset({CLEAR, REQUEST_DOCS, CONFIRM, COLLEGE_RESPONSE, SYSTEM_NOTE})
NOTE_INTERNAL: frozenset[CaseActionKind] = frozenset({ESCALATE, NOTE, REOPEN})
TABLE: Mapping[tuple[FlagStatus, CaseActionKind], tuple[FlagStatus, frozenset[UserRole]]]   # API_CONTRACT §A3.9

def target(status: FlagStatus, action: CaseActionKind) -> FlagStatus | None: ...        # None: not in the table
def allowed_actions(role: UserRole, status: FlagStatus) -> tuple[CaseActionKind, ...]: ...  # OFFICER_ACTIONS order
def check(role: UserRole, status: FlagStatus, action: CaseActionKind) -> FlagStatus: ...
    # the new status; ApiError 403 when another role could, 409 FLAG_TRANSITION_INVALID when nobody can
def note_required(action: CaseActionKind) -> bool: ...                                   # every officer action but ASSIGN
```

```python
# app/cases/attachments.py
MAX_FILES = 3
MAX_FILE_BYTES = 5_242_880
MAX_BODY_BYTES = 16 * 1024 * 1024
SIGNATURES = {b"%PDF-": "application/pdf", b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}

@dataclass(frozen=True, slots=True)
class StoredFile:
    storage_key: str          # uuid4 hex
    filename: str             # cleaned
    content_type: str
    size_bytes: int
    sha256: str               # of the original bytes

def sniff(head: bytes) -> str | None: ...
def clean_filename(name: str | None) -> str: ...      # base name only, control characters dropped, 120 characters, "attachment" when empty
async def store(upload: UploadFile) -> StoredFile: ...  # ApiError 413 ATTACHMENT_TOO_LARGE, 415 ATTACHMENT_TYPE
def read(storage_key: str) -> bytes: ...                # decrypted
def discard(storage_keys: Iterable[str]) -> None: ...
```

Files are Fernet-encrypted with `PII_FERNET_KEY` (like the upload spool) and written to `CASE_FILES_DIR/<storage_key>` through a temporary name and a rename. The router stores every file first; if one fails or the database work raises, it calls `discard` for those already written, so no file outlives a rolled-back response.

```python
# app/cases/service.py
EVIDENCE_UPDATED_NOTE = "Evidence updated after the decision."

async def scoped_flag(session: AsyncSession, user: User, flag_id: uuid.UUID, *, for_update: bool = False) -> Flag: ...
    # 404 "Flag not found." outside the caller's scope (flags.scope_flags rules)
async def apply_action(
    session: AsyncSession, user: User, flag_id: uuid.UUID, *, action: CaseActionKind, note: str | None,
    due_date: date | None, assignee_id: uuid.UUID | None,
) -> ActionResult: ...                                 # flag, case action row, mail to send after the commit
async def college_response(
    session: AsyncSession, user: User, flag_id: uuid.UUID, *, note: str, files: Sequence[StoredFile]
) -> CaseAction: ...
async def add_system_note(session: AsyncSession, flag: Flag, text: str) -> CaseAction: ...
async def history(session: AsyncSession, flag: Flag, user: User) -> list[dict[str, Any]]: ...   # redacted for INSTITUTION
async def assignable_officers(session: AsyncSession, user: User, *, roles: Sequence[UserRole], flag: Flag | None) -> Select: ...
async def docs_request_messages(session: AsyncSession, flag: Flag, action: CaseAction, user: User) -> list[MailMessage]: ...
```

- `apply_action`, in the request's transaction: `scoped_flag(..., for_update=True)`; `transitions.check`; field rules (API_CONTRACT §A3.10); the flag changes and the `case_actions` row of §A3.9; `last_action_at`; audit UPDATE on `flag`. CLEAR then calls `credentials.issue_if_eligible` for the flag's `enrolment_id` and every related enrolment; CONFIRM calls `credentials.revoke_for_enrolment(session, flag.enrolment_id, "FLAG_CONFIRMED", user.id)` when the flag names an enrolment. REQUEST_DOCS builds its emails with `docs_request_messages`; the router commits, then sends them with `await asyncio.to_thread(build_mailer().send_many, messages)` and only logs a failure.
- `college_response`: `scoped_flag`, the status must be DOCS_REQUESTED, then the COLLEGE_RESPONSE row, one `case_attachments` row per stored file (`case_action_seq` from the flushed row), `response_received`, `last_action_at`, audit entries.
- `add_system_note` writes a SYSTEM_NOTE row (no actor, `from_status` = `to_status` = the flag's status) and sets `last_action_at`. It has two callers: `raise_flag` and `notices.service.apply_reply` (§16.3).
- **The hook in `app/engine/flags.py`.** In `raise_flag`, when an existing flag `changed` and its status is CLEARED or CONFIRMED, call `add_system_note(session, flag, EVIDENCE_UPDATED_NOTE)` (imported inside the function). Nothing else in `raise_flag` changes: engines still never change a flag's status.
- `history` returns `CaseHistoryItem` dicts (API_CONTRACT §A3.13); for an INSTITUTION caller it leaves out ASSIGN rows, nulls the notes of `NOTE_INTERNAL` rows and nulls `assignee`.

### 16.6 `app/credentials/`

```python
# app/credentials/keys.py
@dataclass(frozen=True, slots=True)
class IssuerKey:
    kid: str
    jwk: jwcrypto.jwk.JWK         # private; never logged

async def active_issuer_key(session: AsyncSession) -> IssuerKey: ...
    # creates one on first use: INSERT ... ON CONFLICT (purpose) WHERE active DO NOTHING, then SELECT
async def jwks(session: AsyncSession) -> dict[str, Any]: ...            # {"keys": [public JWK of every ISSUER key]}
async def public_key(session: AsyncSession, kid: str) -> jwcrypto.jwk.JWK | None: ...   # reads jwks(), as a third party would
async def holder_key(session: AsyncSession, student_id: uuid.UUID, *, create: bool) -> jwcrypto.jwk.JWK | None: ...
def thumbprint(key: jwcrypto.jwk.JWK) -> str: ...                       # RFC 7638, SHA-256, base64url
```

```python
# app/credentials/status_list.py
SIZE = 131_072
LIST_ID = 1
TTL_SECONDS = 60

@dataclass(frozen=True, slots=True)
class StatusListToken:
    jwt: str
    iat: datetime
    bits: bytes                    # the 16,384 uncompressed bytes

def uri() -> str: ...                                     # f"{ISSUER_URL}/status-lists/1"
def encode(revoked_indexes: Iterable[int]) -> str: ...    # zlib + base64url, LSB first
def bit(bits: bytes, index: int) -> int: ...
async def current(session: AsyncSession) -> StatusListToken: ...   # rebuilt when older than TTL or invalidated
def invalidate() -> None: ...                                       # this process only
async def allocate_index(session: AsyncSession) -> int: ...          # random unused index; retried on a unique violation
```

```python
# app/credentials/issuer.py
ENROLMENT_VCT = "countersign:enrolment:v1"
DEGREE_VCT = "countersign:degree:v1"
ENROLMENT_DISCLOSABLE = ("name", "dob", "apaar_masked", "institution", "programme", "academic_year", "year_of_study", "countersigned")
DEGREE_DISCLOSABLE = ("name", "apaar_masked", "institution", "programme", "university", "year_of_award")
ALWAYS_DISCLOSED = ("institution", "programme")
REASON_CODES = ("ENROLMENT_WITHDRAWN", "ENROLMENT_TRANSFERRED", "FLAG_CONFIRMED")

async def eligibility(session: AsyncSession, enrolment_id: uuid.UUID) -> bool: ...
async def issue_if_eligible(session: AsyncSession, enrolment_id: uuid.UUID) -> Credential | None: ...
async def issue_degree(session: AsyncSession, enrolment_id: uuid.UUID, *, actor_id: uuid.UUID) -> tuple[Credential, bool]: ...
    # (credential, created); ApiError 409 CREDENTIAL_NOT_ELIGIBLE NOT_GRADUATED
async def revoke(session: AsyncSession, credential: Credential, *, reason: str, actor_id: uuid.UUID) -> None: ...
    # officer revocation; ApiError 409 CREDENTIAL_REVOKED
def reason_code(stored: str | None) -> str | None: ...    # the stored value when it is a code, else "ADMIN"
def claims_for(credential: Credential, ...) -> list[dict[str, Any]]: ...   # [{key, label, value, disclosable}]
```

Issuance builds the claims of API_CONTRACT §A3.15, marks the disclosable ones with the library's `SDObj`, and signs with `SDJWTIssuer(..., holder_key=<holder JWK> for ENROLMENT and None for DEGREE, sign_alg="ES256", add_decoy_claims=False, extra_header_parameters={"typ": "dc+sd-jwt", "kid": kid})`; check the argument names against the pinned `sd-jwt` version. The row stores `sd_jwt`, `vct`, `short_id` (8 random Crockford characters, retried on a clash), `disclosable`, `status_list_index`, `issuer_key_id`, `expires_at`.

```python
# app/credentials/holder.py
SHARE_TTL = timedelta(minutes=10)

def new_code() -> str: ...                         # six groups of four Crockford characters
def normalise_code(raw: str) -> str | None: ...     # API_CONTRACT §A3.15; None when malformed
def code_hash(code: str) -> str: ...
def qr_svg(url: str) -> str: ...                    # segno, error M, border 4, no XML declaration
async def present(session: AsyncSession, credential: Credential, user: User, *, fields: Sequence[str]) -> dict[str, Any]: ...
async def cards(session: AsyncSession, user: User, *, filters: CredentialFilters, page: PageParams) -> Page: ...
async def detail(session: AsyncSession, credential: Credential) -> dict[str, Any]: ...
async def presentations(session: AsyncSession, credential: Credential, page: PageParams) -> Page: ...
async def expire_live_presentations(session: AsyncSession, student_id: uuid.UUID, *, now: datetime) -> int: ...
async def wallet_summary(session: AsyncSession, student_id: uuid.UUID) -> list[dict[str, Any]]: ...   # /students/me
async def credential_refs(session: AsyncSession, enrolment_id: uuid.UUID) -> list[dict[str, Any]]: ...  # enrolment detail
```

`present` decrypts the holder key, calls `SDJWTHolder(credential.sd_jwt).create_presentation(...)` with the code as nonce and `{ISSUER_URL}/verify` as audience, stores the presentation, records the CREDENTIAL_SHARE consent through `privacy.service.record_consent`, and writes the audit entries of API_CONTRACT §A3.17. `expire_live_presentations` is called by `privacy.service.withdraw`.

```python
# app/credentials/verifier.py
async def verify_code(session: AsyncSession, raw_code: str, *, ip: str) -> dict[str, Any]: ...       # ApiError 404 PRESENTATION_NOT_FOUND
async def verify_presentation(session: AsyncSession, presentation: str, *, ip: str) -> dict[str, Any]: ...
async def verify_degree_jws(session: AsyncSession, jws: str, *, ip: str) -> dict[str, Any]: ...
async def verify_degree_id(session: AsyncSession, raw_short_id: str, *, ip: str) -> dict[str, Any]: ...  # register lookup
def ip_hash(ip: str) -> str: ...      # first 16 hex of HMAC-SHA256(PII_HMAC_KEY, ip)
```

Each returns the `VerifyResult` dict of API_CONTRACT §A3.20 and writes its READ audit entry and counters in the request's transaction. The key callback given to `SDJWTVerifier` is built from `keys.jwks()` (the document `/.well-known/jwks.json` serves), selects by `kid` and refuses any `iss` other than `ISSUER_URL`; the status bit comes from `status_list.current()`. For a pasted presentation the nonce and audience are read from the key-binding JWT first and passed as the expected values.

```python
# app/credentials/degree.py
def short_name(text: str, limit: int = 28) -> str: ...                 # API_CONTRACT §A3.21
def mask_provisional(provisional_id: str) -> str: ...                  # "PRV-XXXX" + last four
async def graduates(session: AsyncSession, user: User, query: GraduateQuery) -> Page: ...
async def print_data(session: AsyncSession, user: User, enrolment_id: uuid.UUID) -> dict[str, Any]: ...
async def compact_jws(session: AsyncSession, credential: Credential) -> str: ...
def insert_pdf(data: Mapping[str, Any]) -> bytes: ...                  # reportlab, pure
```

`mask_provisional` is the one masking rule for public surfaces; the notices area imports it for the notice page.

### 16.7 `app/privacy/`

```python
# app/privacy/notice.py
NOTICE_VERSION = "v1"
EFFECTIVE_FROM = date(2026, 10, 28)
PRIVACY_NOTICE: Mapping[str, Any]                       # title and sections, mirrored from the copy deck
CONSENT_TEXTS: Mapping[ConsentPurpose, str]             # copy deck §9, placeholders kept
WITHDRAW_TEXTS: Mapping[ConsentPurpose, str]            # the withdraw confirmation texts
def consent_text(purpose: ConsentPurpose, **values: str) -> str: ...
def public_notice() -> dict[str, Any]: ...              # the GET /privacy/notice body
```

```python
# app/privacy/service.py
async def record_consent(
    session: AsyncSession, *, student_id: uuid.UUID, purpose: ConsentPurpose, status: ConsentState,
    channel: str, notice_text: str, enrolment_id: uuid.UUID | None = None, actor_id: uuid.UUID | None = None,
) -> Consent: ...
async def record_apaar_link(
    session: AsyncSession, *, student_id: uuid.UUID, enrolment_id: uuid.UUID, consent_status: ConsentStatus,
    institution_name: str, actor_id: uuid.UUID | None,
) -> Consent | None: ...                                 # LINKED gives GIVEN, REFUSED gives REFUSED, else nothing
async def notice_consent_withdrawn(session: AsyncSession, student_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]: ...
async def consents_view(session: AsyncSession, student_id: uuid.UUID) -> dict[str, Any]: ...
async def withdraw(session: AsyncSession, student_id: uuid.UUID, purpose: ConsentPurpose, user: User) -> dict[str, Any]: ...
async def access_log(session: AsyncSession, student_id: uuid.UUID, *, own_user_id: uuid.UUID, page: PageParams) -> Page: ...
async def create_request(session: AsyncSession, student_id: uuid.UUID, user: User, body: DataRequestCreate) -> dict[str, Any]: ...
async def student_requests(session: AsyncSession, student_id: uuid.UUID, page: PageParams) -> Page: ...
async def admin_requests(session: AsyncSession, user: User, query: DataRequestQuery) -> Page: ...
async def resolve(session: AsyncSession, request_id: uuid.UUID, user: User, body: DataRequestResolve) -> dict[str, Any]: ...
async def export(session: AsyncSession, student_id: uuid.UUID, user: User) -> dict[str, Any]: ...
```

- `record_apaar_link` is called from `app/engine/upload/upsert.py` when a student row is created or its `consent_status` changes, in the upsert chunk's transaction, with the batch's uploader as actor; an unchanged re-upload writes nothing (§13 still holds).
- `notice_consent_withdrawn` is what `dispatch.needs_notice`, `resend` and `load_subjects` use.
- `access_log` reads `audit_log` READ entries for the student's ids (student, notifications, credentials, presentations), leaves out the student's own reads and maps them as API_CONTRACT §A3.22 says.
- `export` gathers everything in §A3.22 with the masking rules and the institution's flag summaries.

### 16.8 Audit reads and the tamper tool

- `app/core/audit.py` does not change. A READ entry that carries details is written with `record_many([AuditEntry(action=AuditAction.READ, entity_type=..., entity_id=..., actor_id=..., after={...})])`; `record_read` stays for plain reads. `AuditEntry.extra` is not stored, so details always go in `after`. The full list of Week 3 READ entries is API_CONTRACT §A3.23.
- `GET /admin/audit` gains its filters and the `actor_role` and `via` columns (`app/routers/admin.py`, a join to `users` for the role, `after ->> 'via'` for `via`).
- `app/core/audit_tamper.py`: `python -m app.core.audit_tamper --seq N`. Exit 2 with "audit-tamper runs only when DEMO_MODE=true." unless `DEMO_MODE` is true (it is true in the demo `.env`); exit 2 for an unknown entry; otherwise one `UPDATE audit_log SET "after" = CASE WHEN jsonb_typeof("after") = 'object' THEN "after" ELSE '{}'::jsonb END || '{"tampered": true}'::jsonb WHERE seq = N` and a printed line saying the chain will now break at N. The CASE covers both empty forms of `after`: SQL NULL, and the JSON `null` the ORM stores for `None`, which `coalesce` would keep and `||` would then turn into an array; either way `after` becomes an object with `"tampered": true`. It writes no audit entry. `make audit-tamper SEQ=n` runs it in the api container.

### 16.9 Routers and `app/main.py`

New router modules: `cases` (`/flags/{id}/actions`, `/flags/{id}/response`, `/flags/{id}/attachments/{attachment_id}`), `credentials` (`/credentials*`), `issuer` (`/.well-known/*`, `/status-lists/{id}`), `notices` (`/notices/*`, `/enrolments/{id}/notices/resend`), `privacy` (`/privacy/notice`, `/students/me/consents*`, `/students/me/access-log`, `/students/me/data-requests`, `/students/me/export.json`, `/data-requests*`), `university` (`/university/*`), `users` (`/users`), `verify` (`/verify*`). Every area adds its own routers, so the import line and the registrations conflict once; resolve them to:

```python
from app.routers import (
    admin, auth, cases, credentials, dashboard, enrolments, flags, healthz, institutions, issuer,
    meta, notices, privacy, students, university, uploads, users, verify,
)
# registration order
for router in (healthz, auth, issuer, notices, verify, privacy, dashboard, institutions, enrolments,
               flags, cases, users, uploads, students, credentials, university, meta, admin):
    app.include_router(router.router)
```

Inside `verify`, declare `/verify/d/{jws}` and `/verify/degree/{short_id}` before `/verify/{code}`. Public routes use `app.core.ratelimit.limiter` with their own limit strings (API_CONTRACT §A3.1); `ratelimit.py` itself does not change. `POST /flags/{id}/response` joins `POST /uploads` as an exemption from the JSON-only 415 check (the cases area adds it next to the existing one).

### 16.10 Transactions

| work | session and commit | engine-style functions inside it |
|---|---|---|
| any request handler | `get_session`: one session, committed when the handler returns; an error rolls everything back, READ audit entries included | flush only |
| resend, REQUEST_DOCS | the handler commits itself, then enqueues delivery or sends the email | |
| `POST /flags/{id}/response` | files stored before any database write; one transaction for the rows; files discarded if it fails | |
| `send_notices_for_batch`, `deliver_notices` | own sessions: one per chunk of 500 for creation, for each delivery step and for the refresh; sends happen between transactions | `refresh_student`, `issue_if_eligible` flush only |
| `run_batch` (ledger revocations, STUDENT re-derivation) | as §4.3 | `revoke_for_enrolment` and the STUDENT evaluator flush only |
| `app.seed.replies` | one transaction per 500 lines | `apply_reply` |
| `audit_tamper` | its own short transaction | |

### 16.11 Who calls whom

- `run_batch` → ledger → `credentials.revoke_for_enrolment`; → `run_checks` → `checks.student.evaluate` → `notices.student_check.derive`; `run_batch_task` → `enqueue_notices` → `countersign.send_notices` → `notices.dispatch.send_notices_for_batch` → `create_notices`, `deliver` (mailer, DigiLocker adapter), `checks.refresh_student`, `credentials.issue_if_eligible`.
- `POST /notices/{token}/respond` and `app.seed.replies` → `notices.service.apply_reply` → `privacy.service.record_consent`, `checks.refresh_student` (→ `raise_flag` → `cases.service.add_system_note` when the flag was decided), `cases.service.add_system_note` (reply changed), `credentials.issue_if_eligible`.
- `POST /enrolments/{id}/notices/resend` → `notices.service.resend` → `create_notices`; then `countersign.deliver_notices`.
- Recheck endpoints → `checks.recheck_pending` → `credentials.issue_if_eligible`.
- `POST /flags/{id}/actions` → `cases.service.apply_action` → `credentials.issue_if_eligible` (CLEAR) or `credentials.revoke_for_enrolment` (CONFIRM); mailer after commit (REQUEST_DOCS).
- `POST /credentials/{id}/present` → `credentials.holder.present` → `privacy.service.record_consent`.
- `POST /students/me/consents/CREDENTIAL_SHARE/withdraw` → `privacy.service.withdraw` → `credentials.holder.expire_live_presentations`.
- `GET /students/me` → `notices.service.notices_for_student`, `credentials.holder.wallet_summary`; `GET /enrolments/{id}` → `notices.service.notices_for_enrolment`, `resend_state`, `credentials.holder.credential_refs`.
- Upload UPSERT → `privacy.service.record_apaar_link`.

Until an area's code is merged, the others build against these signatures with fakes: a `MemoryMailer`; `issue_if_eligible` returning None (as on `main`); a `refresh_student` that writes a fixed outcome; `add_system_note` writing the row directly.

### 16.12 Tests each area owes

| area | test |
|---|---|
| notices | a DONE batch gets one notice per channel per ACTIVE enrolment whatever its Identity result; a second run creates none |
| notices | the mailer refuses a host outside `SMTP_ALLOWED_HOSTS` and opens one connection per 500 messages; DigiLocker 404 gives FAILED "No DigiLocker account." and never delays email |
| notices | only `sha256(token)` is stored; a token from a failed try never opens the notice; malformed and unknown tokens give identical 404 bodies |
| notices | every row of API_CONTRACT §A3.8, including UNREACHABLE and a No on one channel beating a Yes on the other |
| notices | No then Yes inside 7 days: check PASS, flag status unchanged, evidence `summary_changed`, one system note; a second change is 409; a re-upload of the row keeps the derived status |
| notices | resend: 409 while live or answered, 429 after three, the registrar only for its own students |
| cases | every cell of the §A3.9 table for AICTE officer, regional officer and registrar (403 versus 409), 404 out of scope |
| cases | response: three files accepted; a fourth, a 6 MB file and a renamed EXE each reject the whole response and leave no file behind; the download is scoped and audited |
| cases | the registrar's history hides ASSIGN rows and internal notes; CONFIRM leaves the enrolment and its seat untouched and revokes its proof; an engine refresh of a cleared flag adds the system note |
| credentials | issue, present three fields, verify VALID with only those three; the same code after 10 minutes is EXPIRED; after revocation REVOKED; a tampered disclosure or another code's key binding is INVALID |
| credentials | the status list bit order (index 48213 is bit 5 of byte 6026) and a round trip through the JWKS document only |
| credentials | ledger withdrawal revokes with `ENROLMENT_WITHDRAWN`; `revoked_reason_code` on the wire for all four causes |
| credentials | the degree URL stays under 400 characters for the longest seeded names; `/verify/d/{jws}` and `/verify/degree/{short_id}` agree; the PDF renders |
| cases (privacy) | APAAR_LINK rows from an upload and not again on re-upload; withdrawing share consent expires live proofs; the access log shows roles only and never the student's own reads; the export masks the APAAR |
| cases (audit) | `audit_tamper` refuses without `DEMO_MODE`; after it, verify reports that seq |

### 16.13 Known limits in Week 3

- There is no scheduler (Addendum 2 errata 1): an expired notice reads "No reply (expired)." only after the next refresh of that enrolment; the status is PENDING either way.
- Behind the web's `/api` rewrite the api sees the web server as the client, so per-address limits on public routes are shared by every browser that goes through the web. A deployment runs uvicorn with `--proxy-headers` behind a trusted proxy.
- The status-list cache is per process: a revocation made by the worker (ledger, seed) reaches the api's token within 60 seconds.
- The wallet is custodial: holder keys are on the server, encrypted; a real deployment keeps them on the student's device.
- There is no index on `audit_log.entity_id`; the access log scans by entity id, fine at demo size.
- The QR SVG and the PDF are generated per request and not cached.
