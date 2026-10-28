# Data model (api database `countersign`)

All tables carry `id UUID PK default gen_random_uuid()`, `created_at timestamptz default now()`, `updated_at timestamptz` (trigger or ORM onupdate) unless marked append-only (then only `id`/`seq` and `at`). Enums are Postgres `ENUM` types named `<table>_<column>` with the UPPER_SNAKE values from `ARCHITECTURE.md` §9. FKs are `ON DELETE RESTRICT` except where noted. Migration `0001_initial` creates everything below.

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
