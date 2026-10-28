# Data model (api database `countersign`)

All tables carry `id UUID PK default gen_random_uuid()`, `created_at timestamptz default now()`, `updated_at timestamptz` (trigger or ORM onupdate) unless marked append-only (then only `id`/`seq` and `at`). Enums are Postgres `ENUM` types named `<table>_<column>` with the UPPER_SNAKE values from `ARCHITECTURE.md` §9. FKs are `ON DELETE RESTRICT` except where noted. Migration `0001_initial` creates everything below. Migration `0002` (Week 2) changes the columns listed under "Migration 0002" near the end of this file; where the two disagree, 0002 wins. Migration `0003` (Week 3) is listed under "Migration 0003" after it; the per-table reference below already shows the 0003 columns of `flags`, `case_actions`, `notifications`, `credentials`, `consents` and `data_requests` and the four new tables.

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
| assignee_id | FK users nullable | the officer the flag is assigned to (0003: set by ASSIGN and optionally by ESCALATE) |
| opened_at / resolved_at | timestamptz | `resolved_at` set on CLEAR and CONFIRM, cleared on REOPEN |
| dedupe_key | text unique | stops re-raising the same flag on re-run |
| docs_due_on | date nullable | 0003: the reply-by date of the latest REQUEST_DOCS; null when none was given or the flag is reopened |
| response_received | bool NOT NULL default false | 0003: true once the college responds to the latest REQUEST_DOCS; a new REQUEST_DOCS or a REOPEN sets it back to false |
| last_action_at | timestamptz nullable | 0003: time of the latest `case_actions` row (any action, system notes included) |

Index: `(institution_id, status)`, `(type, status)`, `(enrolment_id)`.

### `case_actions` (append-only)
| column | type | notes |
|---|---|---|
| seq | bigserial PK | |
| flag_id | FK flags | indexed |
| actor_id | FK users nullable | 0003: null for SYSTEM_NOTE rows |
| action | enum case_actions_action | CLEAR, REQUEST_DOCS, ESCALATE, CONFIRM, NOTE, COLLEGE_RESPONSE; 0003 adds ASSIGN, REOPEN, SYSTEM_NOTE |
| note | text nullable | required for every action except ASSIGN (DECISIONS D25); the fixed sentence for SYSTEM_NOTE |
| attachments | jsonb | Week 1 placeholder, always `[]` from 0003 on: files live in `case_attachments` |
| from_status | enum flags_status nullable | 0003: the flag's status before the action |
| to_status | enum flags_status nullable | 0003: the status after it; equal to `from_status` for NOTE, ASSIGN, COLLEGE_RESPONSE and SYSTEM_NOTE |
| due_date | date nullable | 0003: REQUEST_DOCS reply-by date |
| assignee_id | FK users nullable | 0003: the officer chosen by ASSIGN or ESCALATE; null on ASSIGN means "unassigned" |
| at | timestamptz | |

Why: the history of a flag is these rows in `seq` order; nothing else records a decision.

### `case_attachments` (0003)
| column | type | notes |
|---|---|---|
| flag_id | FK flags | indexed |
| case_action_seq | bigint FK case_actions.seq | the COLLEGE_RESPONSE row the file came with |
| filename | text | the uploaded name, cleaned (path parts and control characters removed, at most 120 characters) |
| content_type | text | `application/pdf`, `image/png` or `image/jpeg`, from the file's first bytes |
| size_bytes | int | at most 5 MB (5,242,880) |
| sha256 | char(64) | hex digest of the original bytes |
| storage_key | text unique | random UUID hex; the file is `CASE_FILES_DIR/<storage_key>`, Fernet-encrypted with `PII_FERNET_KEY` |
| uploaded_by_id | FK users | the registrar |
| created_at | timestamptz | |

Why: documents a college sends may hold personal data, so they stay outside the database, encrypted, and are read only through the scoped, audited download.

### `notifications`
| column | type | notes |
|---|---|---|
| student_id | FK students | indexed |
| enrolment_id | FK enrolments | |
| channel | enum notifications_channel | EMAIL, DIGILOCKER |
| token_hash | text unique | 0003 (renamed from `token`): hex SHA-256 of the link token; the token itself (32 random bytes, URL-safe) exists only in the message |
| message | text | the text sent on this channel, without the link |
| delivery_status | enum notifications_delivery NOT NULL default QUEUED | 0003: QUEUED, SENT, FAILED |
| attempts | int NOT NULL default 0 | 0003: delivery tries so far (at most 3) |
| last_error | text nullable | 0003: one plain sentence, never PII, e.g. "No DigiLocker account for this APAAR" |
| sent_at | timestamptz nullable | when the delivery succeeded |
| opened_at | timestamptz nullable | first view of the notice page |
| response | enum notifications_response nullable | YES, NO; null = no reply (neutral) |
| responded_at | timestamptz nullable | time of the first reply |
| comment | text nullable | 0003: the student's optional comment with a No (at most 500 characters); shown to officers only |
| previous_response | enum notifications_response nullable | 0003: the first answer, set when the student changes it (once) |
| changed_at | timestamptz nullable | 0003: when the answer was changed |
| resent_by_id | FK users nullable | 0003: the user who asked for a resend; null for notices sent after a batch |
| expires_at | timestamptz | creation time plus `notices.expiry_days` |

Index: `(enrolment_id, channel)` (0003).

Words used by the api and ENGINES §16: a notice is **answered** when `response` is set; **live** when it is not answered, `delivery_status` is not FAILED and `expires_at` is in the future. An enrolment **needs a notice** when it has no live and no answered notice.

## Credentials and consent

### `credentials`
| column | type | notes |
|---|---|---|
| student_id | FK students | indexed |
| enrolment_id | FK enrolments | |
| kind | enum credentials_kind | ENROLMENT, DEGREE |
| vct | text NOT NULL | 0003: `countersign:enrolment:v1` or `countersign:degree:v1` |
| short_id | text unique NOT NULL | 0003: 8 Crockford base32 characters, e.g. `7Q2MK4PX`; the `cid` of the degree QR |
| sd_jwt | text | the issued SD-JWT: issuer-signed JWT and every disclosure, `~`-joined, ending in `~` |
| status_list_index | int unique | a random unused position in status list 1 (0 to 131,071) |
| disclosable | text[] NOT NULL default `'{}'` | 0003: the claim names the holder may disclose, in display order |
| revoked | bool | |
| issued_at / revoked_at | timestamptz | |
| expires_at | timestamptz nullable | 0003: the SD-JWT `exp` (31 August after the academic year ends, 23:59:59 IST); null for DEGREE |
| revoked_reason | text nullable | 0003: one plain sentence, e.g. "Enrolment withdrawn on 20 Oct 2026." |
| revoked_by_id | FK users nullable | 0003: null when the system revoked it (ledger, seed) |
| issuer_key_id | text | the `kid` of the signing key |

Index (0003): unique partial `(enrolment_id, kind) WHERE revoked = false`, so an enrolment holds at most one active credential of each kind.

### `credential_presentations` (0003)
| column | type | notes |
|---|---|---|
| credential_id | FK credentials | indexed |
| code_hash | char(64) unique | hex SHA-256 of the share code in display form (`K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF`) |
| presentation | text | the SD-JWT presentation with its key-binding JWT (nonce = the code) |
| disclosed | text[] | the disclosed claim names |
| created_at | timestamptz | |
| expires_at | timestamptz | `created_at` plus 10 minutes; set to the withdrawal time when share consent is withdrawn |
| first_verified_at / last_verified_at | timestamptz nullable | |
| verify_count | int default 0 | every verification of this code, whatever the result |

Why: the code is the only way to reach a presentation, and only its hash is stored.

### `signing_keys` (0003)
| column | type | notes |
|---|---|---|
| kid | text PK | the RFC 7638 JWK thumbprint (SHA-256, base64url) |
| alg | text | `ES256` |
| purpose | text default `ISSUER` | |
| public_jwk | jsonb | `{kty, crv, x, y, kid, use: "sig", alg}` as published in the JWKS |
| private_jwk_encrypted | text | Fernet(`PII_FERNET_KEY`) of the private JWK JSON |
| active | bool | unique partial index on `(purpose) WHERE active`: one active key per purpose |
| created_at | timestamptz | |

Retired keys stay (inactive) and stay in the JWKS, so proofs signed with them still verify.

### `holder_keys` (0003)
| column | type | notes |
|---|---|---|
| student_id | uuid PK, FK students | |
| public_jwk | jsonb | the `cnf.jwk` of the student's Enrolment proofs |
| private_jwk_encrypted | text | Fernet(`PII_FERNET_KEY`); custodial demo wallet only |
| created_at | timestamptz | |

### `consents`
| column | type | notes |
|---|---|---|
| student_id | FK students | indexed |
| enrolment_id | FK enrolments nullable | 0003: the enrolment the consent was given for (APAAR_LINK and NOTICE); null for a share |
| purpose | enum consents_purpose | APAAR_LINK, NOTICE, CREDENTIAL_SHARE |
| status | enum consents_status | GIVEN, WITHDRAWN, REFUSED |
| notice_text | text | the exact text shown, placeholders filled |
| notice_version | text NOT NULL default `'v1'` | 0003: version of the privacy notice and consent texts (`app/privacy/notice.py`) |
| recorded_at | timestamptz | |
| withdrawn_at | timestamptz nullable | 0003: set when a GIVEN row is withdrawn (its status becomes WITHDRAWN) |
| channel | text | `COLLEGE_UPLOAD` (APAAR_LINK from the upload), `NOTICE_EMAIL` or `NOTICE_DIGILOCKER` (the Yes reply), `PORTAL` (shares and withdrawals by the signed-in student) |

The latest row per purpose (by `recorded_at`) is the student's current choice.

### `data_requests`
| column | type | notes |
|---|---|---|
| student_id | FK students | indexed |
| kind | enum data_requests_kind | ACCESS, CORRECTION, ERASURE |
| status | enum data_requests_status | OPEN, DONE, REJECTED; ACCESS rows are DONE when created |
| payload | jsonb | `{enrolment_id?}` |
| details | text nullable | 0003: what the student asked, as written |
| response | text nullable | 0003: the officer's answer (for ACCESS the fixed line that the export is ready) |
| resolved_at | timestamptz nullable | 0003 |
| resolved_by_id | FK users nullable | 0003; null for ACCESS |

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

From Week 3 (DECISIONS D29) READ rows may carry a small `after` object that says how the read happened, for example `{"via": "notice-link"}` for a notice page view or `{"via": "verifier", "ip_hash": "3f9a0c1d2e4b5a69", "result": "VALID"}` for a verifier call; it is part of the hashed payload like any other `after`. There is no separate `extra` column: `AuditEntry.extra` in `app/core/audit.py` is not stored, so writers put these keys in `after`.

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
| name_key | add, text NULL | blocking key `matching.name_key(name, dob)` = `"<dob ISO>\|<first initial>\|<metaphone of surname>"`, e.g. `2007-03-21\|r\|XRM`; written for every row from Week 2 on, nullable only so the migration needs no Python |
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

Evidence stored in `flags.evidence` (D20, API_CONTRACT §A2.17): `{summary, summary_for_institution?, facts: [{label, value, source, audience?}], related_enrolment_ids: [uuid], rule_source, data?}` (`audience` is `ALL` when absent, `OFFICER` or `INSTITUTION`). `flags.related_enrolment_ids` always equals `evidence.related_enrolment_ids`. `summary` never contains a student name or a full id.

## Migration 0003 (Week 3)

One Alembic revision `0003` (`down_revision = "0002"`, file `alembic/versions/0003_notices_cases_credentials.py`) plus the matching edits to `app/models/*.py` and `app/models/enums.py`. It implements DECISIONS D23 to D30 and lands on `main` before any Week 3 code that reads the new columns. `downgrade()` restores the 0002 schema exactly (Postgres cannot drop an enum value, so `case_actions_action` is rebuilt without the three new values; system rows are deleted and ASSIGN and REOPEN rows become NOTE first). Demo data is rebuilt by `make demo-reset`, but the migration still backfills existing rows so `alembic upgrade head` works on a seeded database.

### New and changed enum types

| Postgres type | Python enum (`app/models/enums.py`) | values |
|---|---|---|
| `notifications_delivery` (new) | `NoticeDelivery` | `QUEUED`, `SENT`, `FAILED` |
| `case_actions_action` (changed) | `CaseActionKind` | adds `ASSIGN`, `REOPEN`, `SYSTEM_NOTE` to `CLEAR`, `REQUEST_DOCS`, `ESCALATE`, `CONFIRM`, `NOTE`, `COLLEGE_RESPONSE` (`ALTER TYPE ... ADD VALUE IF NOT EXISTS`) |

`notifications_delivery` is the one type not named `<table>_<column>` (the column is `delivery_status`); the name is fixed by the migration. `case_actions.from_status` and `to_status` reuse the existing `flags_status` type.

### `notifications`
| column | change | notes |
|---|---|---|
| token | rename to `token_hash` | hex SHA-256 of the link token; existing values are hashed in place (`encode(sha256(convert_to(token, 'UTF8')), 'hex')`) and the unique constraint is renamed `uq_notifications_token_hash` |
| delivery_status | add, `notifications_delivery` NOT NULL DEFAULT `'QUEUED'` | backfilled to `SENT` where `sent_at` is set |
| attempts | add, int NOT NULL DEFAULT 0 | |
| last_error | add, text NULL | PII-free sentence |
| comment | add, text NULL | the student's comment with a No |
| previous_response | add, `notifications_response` NULL | the first answer, kept when the answer is changed |
| changed_at | add, timestamptz NULL | |
| resent_by_id | add, uuid NULL, FK users | |

Index: `ix_notifications_enrolment_id_channel` on `(enrolment_id, channel)`.

### `case_actions`
| column | change | notes |
|---|---|---|
| actor_id | make nullable | system rows (SYSTEM_NOTE) have no actor |
| action | enum gains `ASSIGN`, `REOPEN`, `SYSTEM_NOTE` | |
| from_status | add, `flags_status` NULL | |
| to_status | add, `flags_status` NULL | |
| due_date | add, date NULL | |
| assignee_id | add, uuid NULL, FK users | |

### `flags`
| column | change | notes |
|---|---|---|
| docs_due_on | add, date NULL | |
| response_received | add, bool NOT NULL DEFAULT false | |
| last_action_at | add, timestamptz NULL | |

### New table `case_attachments`
`id` uuid PK (`gen_random_uuid()`), `flag_id` uuid NOT NULL FK flags (indexed), `case_action_seq` bigint NOT NULL FK `case_actions.seq`, `filename` text NOT NULL, `content_type` text NOT NULL, `size_bytes` int NOT NULL, `sha256` char(64) NOT NULL, `storage_key` text NOT NULL unique, `uploaded_by_id` uuid NOT NULL FK users, `created_at` timestamptz NOT NULL DEFAULT now().

### New table `signing_keys`
`kid` text PK, `alg` text NOT NULL, `purpose` text NOT NULL DEFAULT `'ISSUER'`, `public_jwk` jsonb NOT NULL, `private_jwk_encrypted` text NOT NULL, `active` bool NOT NULL DEFAULT true, `created_at` timestamptz NOT NULL DEFAULT now(). Unique partial index `uq_signing_keys_purpose_active` on `(purpose) WHERE active`.

### New table `holder_keys`
`student_id` uuid PK, FK students; `public_jwk` jsonb NOT NULL; `private_jwk_encrypted` text NOT NULL; `created_at` timestamptz NOT NULL DEFAULT now().

### `credentials`
| column | change | notes |
|---|---|---|
| vct | add, text NOT NULL | backfilled as `countersign:<kind in lower case>:v1` |
| short_id | add, text NOT NULL, unique | backfilled from the row id; new rows get 8 Crockford base32 characters |
| expires_at | add, timestamptz NULL | |
| revoked_reason | add, text NULL | |
| revoked_by_id | add, uuid NULL, FK users | |
| disclosable | add, text[] NOT NULL DEFAULT `'{}'` | |

Index: unique partial `uq_credentials_enrolment_id_kind` on `(enrolment_id, kind) WHERE revoked = false`.

### New table `credential_presentations`
`id` uuid PK (`gen_random_uuid()`), `credential_id` uuid NOT NULL FK credentials (indexed), `code_hash` char(64) NOT NULL unique, `presentation` text NOT NULL, `disclosed` text[] NOT NULL DEFAULT `'{}'`, `created_at` timestamptz NOT NULL DEFAULT now(), `expires_at` timestamptz NOT NULL, `first_verified_at` timestamptz NULL, `last_verified_at` timestamptz NULL, `verify_count` int NOT NULL DEFAULT 0.

### `consents`
| column | change | notes |
|---|---|---|
| enrolment_id | add, uuid NULL, FK enrolments | |
| notice_version | add, text NOT NULL DEFAULT `'v1'` | |
| withdrawn_at | add, timestamptz NULL | |

### `data_requests`
| column | change | notes |
|---|---|---|
| details | add, text NULL | |
| response | add, text NULL | |
| resolved_at | add, timestamptz NULL | |
| resolved_by_id | add, uuid NULL, FK users | |

### Not changed
`audit_log` keeps its columns (READ details go into `after`, see the table reference). `students`, `enrolments`, `checks` and `users` are unchanged: the STUDENT check keeps using the `checks` row of type STUDENT with source `STUDENT_NOTICE`, graduates are ordinary `enrolments` rows with status GRADUATED, and AICTE_ADMIN, RO_OFFICER and UNIVERSITY users need no new scope column. There is no index on `audit_log.entity_id`; the student access log (API_CONTRACT §A3.21) scans by entity id, which is fine at demo size and is noted as a known limit.

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
