# Countersign architecture (shared contract)

This document, `API_CONTRACT.md` and `DATA_MODEL.md` are the whole interface between the backend and the frontend. Both sides build against these files in parallel. If something is not written here, do not assume it: add it here first.

Tagline: **Every enrolment, countersigned.** A college upload is a claim. Five independent sources (Identity, Admission, Seat, Studying, Student) each countersign a record. Officers see which check failed and decide. Nothing is auto-rejected.

## 1. System diagram

```
 browser ──:3000──> apps/web (Next.js 16, App Router)
                      │  route handler proxy  /api/*  ──> http://api:8000/*   (cookies forwarded)
                      │
                      ▼
            services/api (FastAPI :8000) ──────────────┬──> postgres:5432  db=countersign
                      │                                ├──> redis:6379     (celery broker + cache)
                      │                                └──> mailpit:1025   (smtp)  ui :8025
                      │
                      │  adapters (GOV_ADAPTER=mockgov)  HTTP only, no imports
                      ▼
            services/mockgov (FastAPI :8001) ──────────────> postgres:5432  db=mockgov
                      (APAAR, Counselling, ABC, DigiLocker inbox, Study in India, chaos toggles)

            services/api worker (celery, same image, `celery -A app.worker worker`)  <── redis
            tools/datagen  (one-off compose service, writes /data/generated)
            tools/eval     (Week 4)
            Later: services/psi (Week 4, platform linux/amd64)
```

Ports (host): web 3000, api 8000, mockgov 8001, mailpit 8025 (web UI) and 1025 (SMTP), postgres 5432, redis 6379.

One Postgres instance, three databases: `countersign` (api), `mockgov`, `countersign_test` (pytest).

## 2. Repo layout and ownership

```
countersign/
  README.md                     progress agent
  Makefile                      backend
  docker-compose.yml            backend
  .env.example                  backend (frontend adds NEXT_PUBLIC_* keys by editing in place, nothing else)
  rules.yaml                    backend (seat pools, thresholds, weights; sourced from AICTE APH)
  docs/
    ARCHITECTURE.md             contract (this file)        } changes only by agreement
    API_CONTRACT.md             contract                    } of both sides
    DATA_MODEL.md               contract                    }
    ENGINES.md                  contract between the two api branches (Week 2)
    DECISIONS.md                progress agent
    PROGRESS.md                 progress agent
    DESIGN.md                   UI agent
    UX.md                       UX agent
  apps/web/                     frontend, except:
    app/globals.css               UI agent
    app/tokens.css                UI agent
    app/(admin)/admin/system      frontend (AICTE_ADMIN only: adapters ping, audit verify, chaos demo)
    components/ui/**              UI agent (shadcn primitives + theme)
    components/brand/**           UI agent (logo, wordmark, countersign mark)
  services/api/                 backend
  services/mockgov/             backend
  tools/datagen/                backend
  tools/eval/                   backend (Week 4)
  .github/workflows/ci.yml      backend
```

Rule: an agent edits only inside its own ownership. Anything else is a request to the owner through the parent.

### Week 2 branches

| Branch | Agent | Owns |
|---|---|---|
| `api/upload-pipeline` | backend-pipeline | in `services/api/`: `app/engine/upload/`, `app/engine/pipeline.py`, `app/routers/uploads.py`, `app/schemas/uploads.py`, `app/worker.py` (the `countersign.run_batch` task), `app/seed/`, `alembic/versions/0002_*` with the model and enum edits it needs, the new settings in `app/core/config.py`, every new dependency in `pyproject.toml` and `uv.lock`, the multipart exemption and uploads router in `app/main.py`, `tests/pipeline/`, `tests/fixtures/mini_generated/`; at the root: `.env.example` additions, `docker-compose.yml` (upload spool volume, worker concurrency 1) and the `Makefile` seed order (mockgov first, then the api seed through `run_batch`) |
| `api/engines` | backend-engines | in `services/api/`: `app/engine/matching.py`, `ledger.py`, `checks/`, `duplicates.py`, `flags.py`, `evidence.py`, `score.py`; `app/routers/flags.py`, `app/routers/enrolments.py` and their schemas; the count and countersign changes in `app/routers/dashboard.py`, `institutions.py`, `students.py`, `_stats.py` and `app/schemas/common.py`, `dashboard.py`, `institutions.py`, `students.py`, including `admitted` beside approved seats on the dashboard, the institutions list and institution detail (API_CONTRACT §A2.18); the flags and enrolments routers in `app/main.py`; `tests/engines/` |
| both api branches | | `services/api/app/engine/contracts.py`, identical bytes copied from ENGINES.md §3 |
| `datagen/week2` | datagen | `tools/datagen/**` (API_CONTRACT §A2.24) |
| `frontend/week2` | frontend | `apps/web/**` outside the UI agent's paths; pastes API_CONTRACT §A2.23 into `lib/types.ts`; teaches the proxy to stream multipart uploads and file downloads |
| `main` | architecture | `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, `docs/ENGINES.md`, DECISIONS D14 to D22 |
| `main` | ux | `docs/ux/**`, including the copy deck keys Addendum 2 points at (`rowerr.*`, `upload_status.PROCESSING`, `upload_stage.*`, `check.pending.*`, the QUOTA_BREACH and LATE_REFILL templates) |

Merge order: backend-pipeline's first commit (migration 0002, model and enum edits, settings, dependencies, `contracts.py`) is merged to `main` before anything else, and backend-engines merges `main` straight after (ENGINES.md §2.1). After that the branches merge in any order; the one expected conflict is the `from app.routers import ...` line in `app/main.py`, resolved as ENGINES.md §2.4 says. `services/mockgov` has no Week 2 work.

### services/api layout

```
services/api/
  app/main.py                 app factory, routers, middleware
  app/core/config.py          pydantic-settings, all env in .env.example
  app/core/security.py        argon2 (pwdlib), JWT (pyjwt), cookie helpers
  app/core/deps.py            current_user, require_roles, scope filters
  app/core/crypto.py          hmac_id, encrypt/decrypt (Fernet), mask_apaar, mask_mobile
  app/core/audit.py           hash-chained audit_log writer + verify_chain
  app/core/errors.py          error envelope exception handlers
  app/core/rules.py           rules.yaml loader (pydantic models)
  app/db/{base,session}.py    SQLAlchemy 2 async
  app/models/*.py             one module per domain
  app/schemas/*.py            Pydantic v2 response/request models
  app/routers/*.py            auth, me, dashboard, institutions, students, admin, healthz;
                              Week 2: uploads, enrolments, flags
  app/adapters/               base.py protocols; inmemory/, mockgov/, real/; factory.py
  app/engine/                 seatpools.py (Week 1); Week 2: contracts.py, pipeline.py, upload/ (parse,
                              validate, upsert), matching.py, ledger.py, checks/, duplicates.py, flags.py,
                              evidence.py, score.py (interfaces in ENGINES.md)
  app/seed/                   importer for datagen output; cli.py
  app/worker.py               celery app; Week 2 task countersign.run_batch (worker concurrency 1)
  alembic/                    migrations, 0001 = whole schema
  tests/
```

### apps/web layout

```
apps/web/
  app/layout.tsx                      root (fonts, QueryProvider, theme)
  app/(auth)/login/page.tsx
  app/(aicte)/aicte/...               national
  app/(ro)/ro/...                     region scoped
  app/(institution)/college/...
  app/(student)/student/...
  app/(university)/university/...
  app/verify/...                      public (Week 3)
  app/api/[...path]/route.ts          proxy to API_INTERNAL_URL, forwards cookies and status
  lib/api.ts                          typed fetch client (throws ApiError with the envelope)
  lib/types.ts                        pasted from API_CONTRACT.md
  lib/auth.ts                         server-side getMe() for layouts and redirects
  components/ui/**                    UI agent
  components/brand/**                 UI agent
  components/**                       frontend (tables, KPI tiles, shells)
```

## 3. Auth model

- `POST /auth/login` with `{email, password}` validates argon2 hash, returns the user and sets cookie `cs_access`.
- Cookie: name `cs_access`, value = JWT (HS256, `API_SECRET_KEY`), `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` only when `COOKIE_SECURE=true` (false in compose), `Max-Age` = `API_ACCESS_TOKEN_MINUTES * 60` (default 120).
- JWT claims: `sub` (user id), `role`, `exp`, `iat`, `jti`. Scope is not in the token; the api loads the user row on each request.
- `POST /auth/logout` clears the cookie (`Max-Age=0`) and returns 204.
- `GET /me` returns the current user and scope. 401 when the cookie is missing, expired or invalid.
- The web never stores the token; the browser only ever talks to `/api/*` on its own origin. The Next.js route handler `app/api/[...path]/route.ts` forwards method, path, query, JSON body, `Cookie` header and returns the upstream status, body and `Set-Cookie` unchanged.
- Server components call the api with `API_INTERNAL_URL` directly and pass the incoming `cs_access` cookie through.
- CSRF: `SameSite=Lax` cookie plus JSON-only request bodies (`Content-Type: application/json` required on every mutating route; form posts are rejected with 415). No CSRF token in Week 1. One exception from Week 2: `POST /uploads` takes `multipart/form-data` (the file); the proxy streams that body through with its own `Content-Type`, and passes CSV and XLSX downloads back with `Content-Type` and `Content-Disposition` unchanged (API_CONTRACT §A2.1).
- Public endpoints (no cookie): `GET /healthz`, Week 3 `/verify/*`. Public endpoints are rate-limited (60/min per IP); 429 uses the error envelope with code `RATE_LIMITED`.

### 401 shape

```json
{ "error": { "code": "UNAUTHENTICATED", "message": "Sign in to continue.", "details": {} } }
```

### 403 shape

```json
{ "error": { "code": "FORBIDDEN", "message": "Your role cannot access this resource.", "details": { "required_roles": ["AICTE_ADMIN", "RO_OFFICER"] } } }
```

Out-of-scope rows (an institution asking for another institution id) return **404 `NOT_FOUND`**, not 403, so existence is not leaked. Role mismatch on a route returns 403.

## 4. Roles and scoping

| Role | Scope | Landing route | Sees |
|---|---|---|---|
| `AICTE_ADMIN` | national | `/aicte` | every institution, region, flag, audit, admin tools |
| `RO_OFFICER` | `scope.region` | `/ro` | institutions whose `region` equals theirs; flags and enrolments of those institutions |
| `INSTITUTION` | `scope.institution_id` | `/college` | only its own institution, programmes, seats, enrolments, flags against it |
| `STUDENT` | `scope.student_id` | `/student` | only its own student row, enrolments, notices, consents, credentials |
| `UNIVERSITY` | `scope.university_id` | `/university` | institutions affiliated to it (read-only), degree QR tools (Week 3) |
| `VERIFIER` | public, no login | `/verify` | signed credential verification only (Week 3) |

Scope rules are enforced in FastAPI dependencies on every query. The UI hides what a role cannot use, but the api is the authority.

Unknown or mismatched role on a route group (a student opening `/aicte`) is redirected by the web layout to that role's landing route.

## 5. Wire conventions

- IDs: UUIDv4 strings. Natural keys shown alongside where useful (`aicte_permanent_id`, `seat_code`, `programme.code`).
- Dates: `YYYY-MM-DD`. Timestamps: ISO-8601 UTC with `Z` (`2026-07-14T09:30:00Z`).
- Enums: `UPPER_SNAKE` strings, never integers.
- Academic year: string `2026-27`.
- Pagination (all list endpoints): query `page` (1-based, default 1) and `page_size` (default 25, max 200). Response envelope:

```json
{ "items": [], "total": 0, "page": 1, "page_size": 25 }
```

- Errors (every non-2xx):

```json
{ "error": { "code": "SNAKE_CASE", "message": "Human readable.", "details": {} } }
```

Codes used in Week 1: `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `INVALID_CREDENTIALS`, `VALIDATION_ERROR` (422, `details.fields` = `[{field, message}]`), `RATE_LIMITED`, `SOURCE_UNAVAILABLE`, `INTERNAL`. Added in Week 2: `FILE_TOO_LARGE`, `TOO_MANY_ROWS` (413), `UNSUPPORTED_FILE_TYPE` (415), `UPLOAD_HEADER_INVALID`, `UPLOAD_EMPTY` (422), `UPLOAD_IN_PROGRESS` (409).

- JSON only. `snake_case` keys on the wire. No nulls for lists (empty list instead); nulls allowed for scalar "not yet known".
- Money: none anywhere.

## 6. PII and masking

- APAAR (12 digits) is stored as `apaar_hmac` (HMAC-SHA256 with `PII_HMAC_KEY`), `apaar_encrypted` (Fernet, `PII_FERNET_KEY`) and `apaar_last4`. The full APAAR **never leaves the api**. The only shape the web sees is `apaar_masked = "XXXX XXXX 4417"`, or `null` when the student has no APAAR (consent `REFUSED` / `PENDING` / `INTERNATIONAL`), in which case `provisional_id` (`PRV-XXXXXXXX`) is shown.
- Mobile: stored as `mobile_hmac` plus `mobile_last4`; wire shape `mobile_masked = "XXXXXX1234"`.
- Address: `address_hmac` only, never returned.
- Passport (international students): `passport_hmac` plus `passport_masked = "X1234567"` is never returned in Week 1.
- Email is returned only to the student themselves (`/students/me`).
- Every endpoint that returns a student row records a `READ` entry in `audit_log` (actor, entity, timestamp). No PII in the audit `before`/`after` payloads; only ids and masked values.

## 7. Seeded demo users (fixed, datagen must emit exactly these in `users.json`)

Password for all: `Countersign!2026`

| Email | Role | Scope |
|---|---|---|
| `admin@aicte.demo` | `AICTE_ADMIN` | national |
| `ro.west@aicte.demo` | `RO_OFFICER` | region `WEST` |
| `ro.south@aicte.demo` | `RO_OFFICER` | region `SOUTH` |
| `registrar@abc.edu.demo` | `INSTITUTION` | "ABC College of Engineering", `aicte_permanent_id` `1-ABC-0001`, state `MH`, region `WEST` |
| `registrar@xyz.edu.demo` | `INSTITUTION` | "XYZ Institute of Technology", `aicte_permanent_id` `1-XYZ-0002`, state `TN`, region `SOUTH` |
| `student@demo` | `STUDENT` | the "Ravi Kumar Sharma" student (enrolled at ABC College, B.Tech CSE, 2026-27) |
| `coe@univ.demo` | `UNIVERSITY` | the university ABC College is affiliated to (datagen names it "Maharashtra State Technical University", code `MSTU`) |

The login page shows these as role cards with the credentials prefilled. Named demo scenarios from the spec live at ABC College (132 admitted vs 120 approved in CSE; "Ravi Kumar Sharma" vs "R. K. Sharma").

## 8. Regions (AICTE regional offices)

Fixed codes. State membership drives `RO_OFFICER` scoping and the dashboard state grid. Items marked *verify* follow the AICTE RO map as best known and must be checked against the AICTE site before the panel demo.

| Code | Regional office (HQ) | States / UTs (ISO-style 2-letter codes used on the wire) |
|---|---|---|
| `NORTH` | Northern, Kanpur | UP Uttar Pradesh, UK Uttarakhand |
| `NORTH_WEST` | North-Western, Chandigarh | PB Punjab, HR Haryana, HP Himachal Pradesh, JK Jammu & Kashmir, LA Ladakh, CH Chandigarh, DL Delhi (*verify DL*) |
| `CENTRAL` | Central, Bhopal | MP Madhya Pradesh, CG Chhattisgarh |
| `WEST` | Western, Mumbai | MH Maharashtra, GA Goa, DH Dadra & Nagar Haveli and Daman & Diu |
| `WEST_CENTRAL` | Vadodara | GJ Gujarat, RJ Rajasthan (*verify RJ*) |
| `SOUTH_WEST` | South-Western, Bengaluru | KA Karnataka, KL Kerala, LD Lakshadweep |
| `SOUTH` | Southern, Chennai | TN Tamil Nadu, PY Puducherry, AN Andaman & Nicobar |
| `SOUTH_CENTRAL` | South-Central, Hyderabad | TS Telangana, AP Andhra Pradesh |
| `EAST` | Eastern, Kolkata | WB West Bengal, OD Odisha, BR Bihar, JH Jharkhand |
| `NORTH_EAST` | North-Eastern, Guwahati | AS Assam, AR Arunachal Pradesh, MN Manipur, ML Meghalaya, MZ Mizoram, NL Nagaland, SK Sikkim, TR Tripura |

Judgement call: the brief listed `CENTRAL_SOUTH` as a tenth code; AICTE's tenth office is Vadodara, so the code is `WEST_CENTRAL`. The `regions` table carries `code`, `name`, `hq_city`.

The dashboard uses a **state grid / table, never a map** (decision 8).

## 9. Countersign vocabulary (used identically by api, web, datagen, eval)

Check types, in display order: `IDENTITY`, `ADMISSION`, `SEAT`, `STUDYING`, `STUDENT`.

Check status: `PASS`, `FAIL`, `PENDING` (source unavailable or awaiting reply), `NA` (not applicable, e.g. `STUDYING` for a first-year before results, `ADMISSION` for routes with no counselling list).

Countersign score: `passes / applicable` where `applicable = checks with status != NA`. `PENDING` counts in the denominator but not the numerator. Wire shape:

```json
{ "score": { "passes": 4, "applicable": 5 }, "checks": [ { "type": "IDENTITY", "status": "PASS", "source": "APAAR", "checked_at": "2026-07-14T09:30:00Z", "detail": {} } ] }
```

Displayed as **"4 of 5"**. In Week 1 `score` is `null` and `checks` is `[]`. From Week 2 the lists (enrolment rows, `/students/me`) carry each check as `{type, status}` only, all five in display order; the full rows above (source, time, detail) come from `GET /enrolments/{id}` (API_CONTRACT §A2.10, §A2.11).

Flag types: `EXCESS_ADMISSION`, `QUOTA_BREACH`, `LATE_REFILL`, `INVALID_APAAR`, `NAME_MISMATCH`, `DUPLICATE_CROSS_INSTITUTION`, `DUPLICATE_WITHIN_UPLOAD`, `DUAL_ENROLMENT_ALLOWED`, `NO_ACADEMIC_ACTIVITY`, `STUDENT_DENIED`, `GHOST_RING`, `ANOMALY`.

Severity: `LOW`, `MEDIUM`, `HIGH`. Flag status: `OPEN`, `DOCS_REQUESTED`, `CLEARED`, `ESCALATED`, `CONFIRMED`.

Every flag carries `evidence` (JSON) that renders as human-readable lines, e.g. `{"summary": "132 admitted against 120 approved seats in CSE (2026-27)", "facts": [{"label": "Approved intake", "value": "120"}, ...]}`. Nothing is ever auto-rejected.

Consent status (student): `LINKED`, `REFUSED`, `PENDING`, `INTERNATIONAL`.

Admission route: `COUNSELLING`, `MANAGEMENT`, `NRI`, `SPOT`, `LATERAL`, `INTERNATIONAL`, `TFW`.

Seat type: `REGULAR`, `NRI`, `TFW`, `LATERAL`, `INTERNATIONAL`. Seat status: `FREE`, `ASSIGNED`, `RELEASED`. Seat code format `<PROGRAMME_CODE>-<R|N|T|L|I>-<NNN>`, e.g. `CSE-R-087`.

Enrolment status: `ACTIVE`, `WITHDRAWN`, `TRANSFERRED`, `GRADUATED`. Uploads set only the first three (D14).

Added in Week 2 (API_CONTRACT Addendum 2):

- Programme mode: `PHYSICAL`, `ODL`, `ONLINE` (drives DUAL_ENROLMENT_ALLOWED, D19).
- Upload status: `QUEUED`, `VALIDATING`, `PROCESSING`, `DONE`, `FAILED` (`PROCESSING` replaces `CHECKING`). Upload stage: `PARSE`, `VALIDATE`, `FILE_DUPLICATES`, `UPSERT`, `LEDGER`, `CHECKS`, `DUPLICATES`, `FLAGS`, `DONE`. Upload source: `FILE`, `API`, `SEED`. Row error level: `ERROR` (row rejected), `WARNING` (row accepted with a note).
- Check source: `APAAR`, `COUNSELLING`, `SEAT_LEDGER`, `ABC`, `SII`, `STUDENT_NOTICE`.
- Cohort year: the approval year a row belongs to, `academic_year` minus (`year_of_study` - 1), from `app/core/cohort.py`; stored on `enrolments.cohort_year`.
- Admitted versus enrolments: `admitted` is ACTIVE enrolments whose cohort year is the academic year shown (the intake set against that year's approved seats); `enrolments` is every student on roll in that year. Fill and over-admission are always `admitted / approved_seats`.
- CIWG student: an INTERNATIONAL-route row with nationality `IN`; only CIWG students take the CIWG-reserved international seats (D16).
- Unresolved flag: status `OPEN`, `DOCS_REQUESTED` or `ESCALATED`; `flags_open` counts these.

## 10. Endpoint availability by week

| Endpoint group | Week 1 | Week 2 | Week 3 | Week 4 |
|---|---|---|---|---|
| `/healthz`, `/auth/*`, `/me` | real | | | |
| `/dashboard/summary` | real (`flags_open` = 0, `integrity_index` null) | `flags_open`, `countersigned_pct`, `clear_pct`, `flags_by_type`, `admitted` real | | integrity real |
| `/institutions`, `/institutions/{id}`, `/seats`, `/enrolments` | real, `countersign` null/[] | countersign, flags, seats (`seated`, `unseated`), `admitted`, `last_upload` real; enrolment filters `check_status`, `check_type`, `flagged`, `seated`; sort `flags_open_desc` real and default | | |
| `/students/me` | real (no notices/credentials) | countersign real | notices, consents, wallet | |
| `/admin/adapters/ping`, `/admin/audit/verify` | real | | audit UI | |
| `/admin/demo/reset` | 501, use `make demo-reset` | 501 | | |
| `/uploads`, `/uploads/rows`, `/uploads/{id}`, `/uploads/{id}/errors`, `/uploads/{id}/errors.csv`, `/uploads/template.csv`, `/uploads/template.xlsx` | absent (404) | real | | |
| `/enrolments/{id}`, `POST /enrolments/{id}/recheck`, `POST /institutions/{id}/recheck` | absent | real | | |
| `/flags`, `/flags/{id}` | absent | real, read-only | actions, documents, history | |
| `/notices/*`, `/credentials/*`, `/verify/*`, `/university/*` | absent | | real | |
| `/reports/*`, `/scores/*`, `/psi/*` | absent | | | real |

The frontend may build Week 2+ pages against the contract once it is written, but must not ship navigation to routes whose endpoints are absent; show a "coming in Week N" placeholder behind the nav item instead.

There is no `/cases/*` api path: the officers' case queue pages (`/aicte/cases`, `/ro/cases`) read `GET /flags`.

## 11. Environment

All environment variables live in `.env.example` with a comment. Compose loads `.env`. The web uses `NEXT_PUBLIC_API_BASE=/api` in the browser and `API_INTERNAL_URL=http://api:8000` on the server.

## 12. Testing contract

- api: pytest against `countersign_test` (migrations applied fresh per session), `GOV_ADAPTER=inmemory`.
- mockgov: pytest with an in-memory SQLite fallback or `mockgov_test`; chaos tests assert 503.
- datagen: pytest on determinism and ground-truth integrity.
- web: `pnpm lint` and `pnpm typecheck` in CI; Playwright arrives in Week 3.
- `make test` runs the three Python suites inside compose.
