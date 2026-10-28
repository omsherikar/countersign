# Data model (api database `countersign`)

All tables carry `id UUID PK default gen_random_uuid()`, `created_at timestamptz default now()`, `updated_at timestamptz` (trigger or ORM onupdate) unless marked append-only (then only `id`/`seq` and `at`). Enums are Postgres `ENUM` types named `<table>_<column>` with the UPPER_SNAKE values from `ARCHITECTURE.md` §9. FKs are `ON DELETE RESTRICT` except where noted. Migration `0001_initial` creates everything below. Migration `0002` (Week 2) changes the columns listed under "Migration 0002" near the end of this file; where the two disagree, 0002 wins.

## Geography and institutions

### `regions`
| column | type | notes |
|---|---|---|
| code | text unique | `WEST` etc. (ARCHITECTURE §8) |
| name | text | "Western" |
| hq_city | text | "Mumbai" |

Why: RO scoping unit and dashboard grouping.

### `states`
| column | type | notes |
|---|---|---|
| code | text unique | `MH` |
| name | text | |
| region_id | FK regions | |

### `universities`
| column | type | notes |
|---|---|---|
| code | text unique | `MSTU` |
| name | text | |
| state_id | FK states | |

Why: degree-awarding body; UNIVERSITY role scope; Week 3 degree QR.

### `institutions`
| column | type | notes |
|---|---|---|
| aicte_permanent_id | text unique | `1-ABC-0001` |
| name | text | |
| type | enum institution_type | GOVERNMENT, GOVERNMENT_AIDED, PRIVATE_SELF_FINANCED, UNIVERSITY_DEPARTMENT, DEEMED |
| state_id | FK states | |
| region_id | FK regions | denormalised from state for cheap scoping; must equal state.region |
| university_id | FK universities nullable | |
| address_city | text nullable | |
| established_year | int nullable | |

Index: `(region_id)`, `(state_id)`, `(university_id)`, trigram-free `lower(name)`.

### `programmes`
| column | type | notes |
|---|---|---|
| institution_id | FK institutions | |
| code | text | `CSE`; unique with institution_id + shift |
| name | text | |
| level | enum programme_level | DIPLOMA, UG, PG, POST_DIPLOMA |
| discipline | enum programme_discipline | ENGINEERING, MANAGEMENT, COMPUTER_APPLICATIONS, PHARMACY, ARCHITECTURE, PLANNING, DESIGN, HOTEL_MANAGEMENT, APPLIED_ARTS |
| shift | enum programme_shift | FIRST, SECOND |
| duration_years | int | 4 for UG engg, 2 for PG, 3 for diploma |

### `approvals`
| column | type | notes |
|---|---|---|
| programme_id | FK programmes | |
| academic_year | text | `2026-27`; unique with programme_id |
| approved_intake | int | |
| cutoff_date | date nullable | last admission date from rules.yaml; LATE_REFILL after this |

Why: the official number the claim is checked against.

## Seat Ledger

### `seat_pools`
| column | type | notes |
|---|---|---|
| approval_id | FK approvals | |
| seat_type | enum seat_type | REGULAR, NRI, TFW, LATERAL, INTERNATIONAL; unique with approval_id |
| capacity | int | from rules.yaml percentages |
| is_supernumerary | bool | |
| rule_source | text | "APH 2024-27 cl. 6.42(d)(i)" |

### `seats`
| column | type | notes |
|---|---|---|
| pool_id | FK seat_pools | |
| seat_code | text | `CSE-R-087`; unique with pool_id |
| status | enum seat_status | FREE, ASSIGNED, RELEASED |
| reserved_for | text nullable | `CIWG` on one third of INTERNATIONAL seats |
| enrolment_id | FK enrolments nullable | current holder; set only when ASSIGNED |

Index: partial `(pool_id) WHERE status = 'FREE'` (used by `SELECT … FOR UPDATE SKIP LOCKED` in Week 2); `(enrolment_id)`.

Why: every approved seat is a row, so excess admission is visible the day it is uploaded.

### `seat_events` (append-only)
| column | type | notes |
|---|---|---|
| seq | bigserial PK | |
| seat_id | FK seats | |
| enrolment_id | FK enrolments | |
| kind | enum seat_event_kind | ASSIGN, RELEASE |
| at | timestamptz | |
| actor_id | FK users nullable | null = system |
| reason | text nullable | "withdrawal", "transfer", "late refill" |

Index: `(seat_id, seq)`, `(enrolment_id)`.

## Students and enrolments

### `students`
| column | type | notes |
|---|---|---|
| apaar_hmac | bytea unique nullable | HMAC-SHA256(PII_HMAC_KEY, apaar_id) |
| apaar_encrypted | bytea nullable | Fernet(apaar_id) |
| apaar_last4 | text nullable | |
| consent_status | enum consent_status | LINKED, REFUSED, PENDING, INTERNATIONAL |
| provisional_id | text unique nullable | `PRV-` + 8 base32; issued whenever apaar is absent |
| name | text | as uploaded |
| name_normalized | text | engine.normalize(name) (Week 2 fills; Week 1 lowercased, punctuation stripped) |
| dob | date | |
| gender | enum gender | M, F, O, U |
| mobile_hmac | bytea nullable | |
| mobile_last4 | text nullable | |
| email | text nullable | |
| address_hmac | bytea nullable | |
| nationality | text | ISO-3166 alpha-2, `IN` default |
| passport_hmac | bytea nullable | international students |

Index: `(apaar_hmac)`, `(dob, name_normalized)`, `(mobile_hmac)`, `(email)`, `(address_hmac)`.

Why: identity is resolved through HMACs so matching works without ever indexing plaintext ids.

### `enrolments`
| column | type | notes |
|---|---|---|
| student_id | FK students | |
| institution_id | FK institutions | |
| programme_id | FK programmes | |
| academic_year | text | |
| year_of_study | int | 1..6 |
| admission_route | enum admission_route | COUNSELLING, MANAGEMENT, NRI, SPOT, LATERAL, INTERNATIONAL, TFW |
| counselling_ref | text nullable | |
| category | enum category | GENERAL, EWS, OBC, SC, ST, OTHER |
| seat_id | FK seats nullable | null = unseated (excess) |
| status | enum enrolment_status | ACTIVE, WITHDRAWN, TRANSFERRED, GRADUATED |
| upload_batch_id | FK upload_batches nullable | null for Week 1 seed |
| source_row_no | int nullable | row in the upload file |
| uploaded_at | timestamptz | |

Unique: `(student_id, institution_id, programme_id, academic_year)`. Index: `(institution_id, academic_year, status)`, `(programme_id, academic_year)`, `(student_id)`.

## Upload pipeline

### `upload_batches`
| column | type | notes |
|---|---|---|
| institution_id | FK institutions | |
| academic_year | text | |
| filename | text | |
| kind | enum upload_kind | INITIAL, UPDATE |
| status | enum upload_status | QUEUED, VALIDATING, CHECKING, DONE, FAILED |
| rows_total / rows_ok / rows_error | int | |
| progress_pct | int | |
| uploaded_by | FK users | |
| started_at / finished_at | timestamptz nullable | |

### `upload_row_errors`
| column | type | notes |
|---|---|---|
| batch_id | FK upload_batches ON DELETE CASCADE | |
| row_no | int | |
| field | text nullable | |
| code | text | `APAAR_FORMAT`, `DUPLICATE_IN_FILE`, `UNKNOWN_PROGRAMME`, ... |
| message | text | human text |
| raw | jsonb | the row, PII-masked |

## Verification

### `checks`
| column | type | notes |
|---|---|---|
| enrolment_id | FK enrolments ON DELETE CASCADE | |
| type | enum check_type | IDENTITY, ADMISSION, SEAT, STUDYING, STUDENT |
| status | enum check_status | PASS, FAIL, PENDING, NA |
| detail | jsonb | human-readable evidence (`{"summary": "...", "facts": [...]}`) |
| source | text | `APAAR`, `COUNSELLING`, `SEAT_LEDGER`, `ABC`, `STUDENT_NOTICE` |
| checked_at | timestamptz nullable | |
| attempts | int | retries on PENDING |

Unique: `(enrolment_id, type)`. Why: one row per source per enrolment; score = PASS / non-NA.

### `flags`
| column | type | notes |
|---|---|---|
| type | enum flag_type | ARCHITECTURE §9 |
| severity | enum severity | LOW, MEDIUM, HIGH |
| status | enum flag_status | OPEN, DOCS_REQUESTED, CLEARED, ESCALATED, CONFIRMED |
| institution_id | FK institutions | |
| programme_id | FK programmes nullable | |
| enrolment_id | FK enrolments nullable | |
| related_enrolment_ids | uuid[] | duplicates / rings |
| evidence | jsonb | human-readable, never auto-reject |
| assignee_id | FK users nullable | |
| opened_at / resolved_at | timestamptz | |
| dedupe_key | text unique | stops re-raising the same flag on re-run |

Index: `(institution_id, status)`, `(type, status)`, `(enrolment_id)`.

### `case_actions` (append-only)
| column | type | notes |
|---|---|---|
| seq | bigserial PK | |
| flag_id | FK flags | |
| actor_id | FK users | |
| action | enum case_action | CLEAR, REQUEST_DOCS, ESCALATE, CONFIRM, NOTE, COLLEGE_RESPONSE |
| note | text nullable | |
| attachments | jsonb | `[{name, size, sha256}]` |
| at | timestamptz | |

### `notifications`
| column | type | notes |
|---|---|---|
| student_id | FK students | |
| enrolment_id | FK enrolments | |
| channel | enum notice_channel | EMAIL, DIGILOCKER |
| token | text unique | magic-link token (random 32 bytes urlsafe) |
| message | text | |
| sent_at | timestamptz nullable | |
| opened_at | timestamptz nullable | |
| response | enum notice_response nullable | YES, NO; null = no reply (neutral) |
| responded_at | timestamptz nullable | |
| expires_at | timestamptz | |

## Credentials and consent

### `credentials`
| column | type | notes |
|---|---|---|
| student_id | FK students | |
| enrolment_id | FK enrolments | |
| kind | enum credential_kind | ENROLMENT, DEGREE |
| sd_jwt | text | issued SD-JWT (Week 3) |
| status_list_index | int unique | position in the revocation status list |
| revoked | bool | |
| issued_at / revoked_at | timestamptz | |
| issuer_key_id | text | JWKS kid |

### `consents`
| column | type | notes |
|---|---|---|
| student_id | FK students | |
| purpose | enum consent_purpose | APAAR_LINK, NOTICE, CREDENTIAL_SHARE |
| status | enum consent_state | GIVEN, WITHDRAWN, REFUSED |
| notice_text | text | the exact text shown |
| recorded_at | timestamptz | |
| channel | text | `PORTAL`, `UPLOAD_DECLARATION` |

### `data_requests` (Week 3, created in 0001)
| column | type | notes |
|---|---|---|
| student_id | FK students | |
| kind | enum data_request_kind | ACCESS, CORRECTION, ERASURE |
| status | enum data_request_status | OPEN, DONE, REJECTED |
| payload | jsonb | |

## Scores and audit

### `institution_scores`
| column | type | notes |
|---|---|---|
| institution_id | FK institutions | |
| academic_year | text | unique with institution_id |
| integrity_index | numeric(5,2) | 0-100 |
| components | jsonb | `{penalty: {invalid_id: 3.5, ...}, weights: {...}}` |
| computed_at | timestamptz | |

### `audit_log` (append-only, hash-chained)
| column | type | notes |
|---|---|---|
| seq | bigserial PK | |
| at | timestamptz | |
| actor_id | FK users nullable | null = system / seed |
| action | enum audit_action | CREATE, UPDATE, DELETE, READ, LOGIN, LOGOUT, SEED |
| entity_type | text | `student`, `enrolment`, `flag`, ... |
| entity_id | uuid nullable | |
| before | jsonb nullable | masked, no PII |
| after | jsonb nullable | masked, no PII |
| request_id | text nullable | |
| prev_hash | text nullable | hex sha256 of previous row; null only for seq 1 |
| hash | text | sha256(prev_hash + canonical_json({seq, at, actor_id, action, entity_type, entity_id, before, after})) |

Writes happen in the same transaction as the change. `verify_chain()` walks seq ascending and returns the first row whose recomputed hash differs.

### `users`
| column | type | notes |
|---|---|---|
| email | citext unique | |
| password_hash | text | argon2id |
| name | text | |
| role | enum user_role | AICTE_ADMIN, RO_OFFICER, INSTITUTION, STUDENT, UNIVERSITY |
| institution_id | FK institutions nullable | INSTITUTION scope |
| region_id | FK regions nullable | RO_OFFICER scope |
| student_id | FK students nullable | STUDENT scope |
| university_id | FK universities nullable | UNIVERSITY scope |
| is_active | bool | |
| last_login_at | timestamptz nullable | |

Check constraint: exactly the scope column matching the role is non-null (admin: none).

## Migration 0002 (Week 2)

Owner: **backend-pipeline**, as one Alembic revision `0002` (`down_revision = "0001"`, file `alembic/versions/0002_week2_engine_columns.py`) plus the matching edits to `app/models/*.py` and `app/models/enums.py`. One migration, one owner: backend-engines never edits models or migrations. This revision lands on `main` before any other Week 2 api code (ENGINES.md §2). `downgrade()` reverses every step.

Demo data is always rebuilt by `make demo-reset`, but the migration still backfills existing rows so `alembic upgrade head` works on a seeded database.

### New enum types

| Postgres type | Python enum (`app/models/enums.py`) | values |
|---|---|---|
| `programmes_mode` | `ProgrammeMode` | `PHYSICAL`, `ODL`, `ONLINE` |
| `upload_batches_stage` | `UploadStage` | `PARSE`, `VALIDATE`, `FILE_DUPLICATES`, `UPSERT`, `LEDGER`, `CHECKS`, `DUPLICATES`, `FLAGS`, `DONE` |
| `upload_batches_source` | `UploadSource` | `FILE`, `API`, `SEED` |
| `upload_row_errors_level` | `RowErrorLevel` | `ERROR` (row rejected), `WARNING` (row accepted, note for the registrar) |

Changed enum: `upload_batches_status` value `CHECKING` is renamed to `PROCESSING` (`ALTER TYPE upload_batches_status RENAME VALUE 'CHECKING' TO 'PROCESSING'`); `UploadStatus.CHECKING` becomes `UploadStatus.PROCESSING`. Final values: `QUEUED`, `VALIDATING`, `PROCESSING`, `DONE`, `FAILED`.

### `programmes`
| column | change | notes |
|---|---|---|
| mode | add, `programmes_mode` NOT NULL DEFAULT `'PHYSICAL'` | the seed imports datagen's `mode`; drives DUAL_ENROLMENT_ALLOWED (D19) |

### `upload_batches`
| column | change | notes |
|---|---|---|
| academic_year | none | already in 0001; one batch is one institution and one academic year (D14) |
| rows_total | rename to `total_rows` | data rows in the file (header excluded) |
| processed_rows | add, int NOT NULL DEFAULT 0 | work items finished in the current `stage`; reset to 0 when the stage changes |
| stage_total | add, int NOT NULL DEFAULT 0 | work items in the current `stage` (rows for PARSE to FILE_DUPLICATES, enrolments after that); with `processed_rows` it gives the api's `progress_pct` |
| stage | add, `upload_batches_stage` NULL | null while QUEUED; on FAILED it keeps the stage that failed |
| source | add, `upload_batches_source` NOT NULL DEFAULT `'FILE'` | FILE (multipart), API (`POST /uploads/rows`), SEED (`make seed`) |
| counts | add, jsonb NOT NULL DEFAULT `'{}'` | keys below |
| error | add, text NULL | why the batch FAILED, one plain sentence, never PII |
| ignored_columns | add, text[] NOT NULL DEFAULT `'{}'` | header columns the parser did not recognise |
| file_sha256 | add, text NULL | hex sha256 of the uploaded bytes (of the canonical JSON for API rows); lets the page say "same file as the upload on ..." |
| declared_at | add, timestamptz NULL | when the registrar ticked the declaration; null for SEED |
| declaration_text | add, text NULL | the exact declaration text shown (copy deck `upload.declaration`); null for SEED |
| rows_ok, rows_error, progress_pct | drop | replaced by `counts` and the api-computed `progress_pct` |
| kind | none | now derived server side: INITIAL when the institution has no earlier DONE batch for that year, else UPDATE |

Index: `(institution_id, academic_year, created_at)`.

`counts` keys (all integers unless noted; every key present once the batch is DONE, zeros included): `rows`, `accepted`, `errors`, `warnings`, `created`, `updated`, `unchanged`, `withdrawn`, `transferred`, `seated`, `released`, `unseated`, `flags_raised`, `flags_updated`, plus `sources` (object: `{"APAAR": {"calls": n, "unavailable": n}, ...}` keyed by check source) and `timings_ms` (object keyed by stage name). Meanings are in API_CONTRACT Addendum 2 §A2.7.

### `upload_row_errors`
| column | change | notes |
|---|---|---|
| level | add, `upload_row_errors_level` NOT NULL DEFAULT `'ERROR'` | |
| value_masked | add, text NULL | the offending value, masked per API_CONTRACT §A2.3 |
| raw | none | masked row as in Week 1 (no contact details, no full ids) |

Index: `(batch_id, row_no)`. `row_no` is the spreadsheet row number: the header is row 1, the first data row is row 2. For `POST /uploads/rows` it is the 1-based position in `rows`. `enrolments.source_row_no` uses the same convention.

### `students`
| column | change | notes |
|---|---|---|
| name_normalized | none (meaning changes) | now `matching.normalise_name(name)` (D17), including transliteration |
| name_key | add, text NULL | blocking key `matching.name_key(name, dob)` = `"<dob ISO>|<first initial>|<metaphone of surname>"`, e.g. `2007-03-21|r|XRM`; written for every row from Week 2 on, nullable only so the migration needs no Python |
| passport_encrypted | add, bytea NULL | Fernet(passport_no), so Study in India can be asked again on recheck; never returned |

Index: `(name_key)`, `(passport_hmac)` (not unique).

### `enrolments`
| column | change | notes |
|---|---|---|
| cohort_year | add, text NOT NULL | `cohort.cohort_year(academic_year, year_of_study)`, written on every insert and update; backfilled in SQL with the same arithmetic as `cohort_year_sql` |
| admission_date | add, date NOT NULL | from the upload, default the upload date; backfilled from `uploaded_at::date`; used for LATE_REFILL |
| status_date | add, date NOT NULL | date of the current status, default the upload date; backfilled from `uploaded_at::date` |
| apaar_problem | add, text NULL | why the uploaded APAAR was unusable, e.g. "has 11 digits, expected 12"; never the digits. Set means IDENTITY fails with INVALID_APAAR |

Indexes: `(programme_id, cohort_year, status)`; unique partial `uq_enrolments_seat_id` on `(seat_id) WHERE seat_id IS NOT NULL` (one holder per seat).

### `seat_events`
| column | change | notes |
|---|---|---|
| effective_date | add, date NULL | the business date: `admission_date` on ASSIGN, `status_date` on RELEASE. `at` stays the server time |

### `seats`
No column change. From Week 2 a released seat goes straight back to `FREE`; the `RELEASED` status value stays in the enum but is not written. "This seat was released before" means it has a `RELEASE` seat event.

### `checks`
Index: `(type, status)` for the enrolment list filters. No column change. `source` values: `APAAR`, `COUNSELLING`, `SEAT_LEDGER`, `ABC`, `SII`, `STUDENT_NOTICE`.

### `flags`
| column | change | notes |
|---|---|---|
| academic_year | add, text NULL | the roll year of the enrolments that raised it (the upload's academic year); every Week 2 write sets it; the dashboard counts flags of its `academic_year` |

Indexes: `(academic_year, status)`; GIN on `related_enrolment_ids`. `created_at` is when the flag was opened (same instant as `opened_at`); `updated_at` moves whenever an engine changes the evidence or severity.

Evidence stored in `flags.evidence` (D20, API_CONTRACT §A2.17): `{summary, summary_for_institution?, facts: [{label, value, source, officer_only?}], related_enrolment_ids: [uuid], rule_source, data?}`. `flags.related_enrolment_ids` always equals `evidence.related_enrolment_ids`. `summary` never contains a student name or a full id.

## mockgov database (`mockgov`, separate service)

| table | columns |
|---|---|
| `apaar_registry` | apaar_id text PK, name text, name_normalized text, dob date |
| `counselling_allotments` | id, state text, year int, name text, name_normalized text, dob date, roll_no text unique, programme text, institution_aicte_id text, round int, category text, allotment_ref text |
| `abc_credits` | id, apaar_id text, academic_year text, sem int, credits int, uploaded_at timestamptz, result text; unique (apaar_id, academic_year, sem) |
| `digilocker_inbox` | inbox_id text PK, apaar_id text, message text, callback_url text, received_at timestamptz, read bool |
| `sii_admissions` | id, passport_no text, name text, nationality text, institution_aicte_id text, programme text, academic_year text; unique (passport_no) |
| `chaos` | source text PK, latency_ms int, fail_rate numeric, down bool |

mockgov stores plaintext because it simulates the government's own registry; it is a separate database the api can never query directly.
