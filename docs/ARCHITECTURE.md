# Countersign architecture (shared contract)

This document, `API_CONTRACT.md` and `DATA_MODEL.md` are the whole interface between the backend and the frontend. Both sides build against these files in parallel. If something is not written here, do not assume it: add it here first.

Tagline: **Every enrolment is a claim. We show the evidence behind it.** A college upload is a claim. From Week 4 (DECISIONS D34 to D49) each record has five evidence rows (Identity, Seat, Joining record, Credits, Student), each with one evidence state and its source and date, and one evidence rule gives each record one status: Awaiting evidence, Countersigned, Under review or Disputed. A student answers only after signing in through DigiLocker. Officers decide every case with a reason, and a decision changes the record, the seat and the attestation together. Nothing is auto-rejected.

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
                      (APAAR, Counselling, ABC, DigiLocker inbox, Study in India, chaos toggles;
                       Week 4: admission authority joining record, Demo DigiLocker sign-in)

            services/api worker (celery, same image, `celery -A app.worker worker`)  <── redis
            tools/datagen  (one-off compose service, writes /data/generated)
            tools/eval     (Week 4: make eval, runs in the api image)
            services/psi   (Week 4 stretch, D48; one linux/amd64 image, two containers, no host port)
                      psi         the partner regulator (a mock UGC); holds its own set
                      psi-client  Countersign's PSI client; the api hands it Countersign's set
                      api ──> psi-client:8002 ──> psi:8002   (only encrypted messages reach psi)
```

Ports (host): web 3000, api 8000, mockgov 8001, mailpit 8025 (web UI) and 1025 (SMTP), postgres 5432, redis 6379.

Volumes shared by the api and the worker: `upload-spool` (encrypted upload files, Week 2) and `case-files` (encrypted case attachments at `CASE_FILES_DIR`, Week 3). From Week 3 the api and the worker send mail to Mailpit (student notices, document requests); Mailpit keeps 20,000 messages (`MP_MAX_MESSAGES`), and its HTTP API on :8025 is what the end-to-end test reads. The api is also the credential issuer at `ISSUER_URL` (its JWKS and status list are public).

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
  services/psi/                 backend (Week 4 stretch: private set intersection, D48)
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
                              Week 2: uploads, enrolments, flags;
                              Week 3: notices, cases, users, credentials, issuer, verify, university, privacy;
                              Week 4: approvals, column_mapping, completeness, signals, reports
  app/adapters/               base.py protocols; inmemory/, mockgov/, real/; factory.py
  app/engine/                 seatpools.py (Week 1); Week 2: contracts.py, pipeline.py, upload/ (parse,
                              validate, upsert), matching.py, ledger.py, checks/, duplicates.py, flags.py,
                              evidence.py, score.py (interfaces in ENGINES.md)
  app/notices/                Week 3: mailer, dispatch, service, student_check (ENGINES §16.3)
  app/cases/                  Week 3: transitions, service, attachments (ENGINES §16.5)
  app/credentials/            Week 3: keys, issuer, holder, verifier, status_list, degree (ENGINES §16.6)
  app/privacy/                Week 3: notice (versioned texts), service (ENGINES §16.7)
  app/core/audit_tamper.py    Week 3: demo-only chain tamper command (DEMO_MODE)
  app/engine/status.py        Week 4: the evidence rule (decide, mark, settle, refresh) and status_text.py (ENGINES §17.2)
  app/engine/eligibility.py   Week 4: seat category eligibility (ENGINES §17.5)
  app/engine/versions.py      Week 4: enrolment versions (ENGINES §17.8)
  app/engine/completeness.py  Week 4: reconciliation with the admission authority (ENGINES §17.10)
  app/engine/upload/mapping.py  Week 4: saved column mappings (ENGINES §17.9)
  app/approvals/              Week 4: approval versions (ENGINES §17.5)
  app/auth/                   Week 4: DigiLocker sign-in and the claim (ENGINES §17.6)
  app/cases/decisions.py      Week 4: uphold, correct, withdraw (ENGINES §17.7)
  app/signals/                Week 4: rings (NetworkX), anomaly (scikit-learn), service (ENGINES §17.11)
  app/reports/                Week 4: report registry, queries, CSV, XLSX and PDF rendering (ENGINES §17.12)
  app/seed/                   importer for datagen output; cli.py; Week 3: graduates.py, replies.py; Week 4: derived.py
  app/worker.py               celery app; tasks countersign.run_batch (Week 2), countersign.send_notices and
                              countersign.deliver_notices (Week 3), countersign.refresh_completeness (Week 4);
                              worker concurrency 1
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
  app/verify/...                      public: /verify, /verify/[code], /verify/d/[jws], /verify/degree/[shortId]
  app/(public)/student/notices/[token]  public notice page (Week 3): outside the signed-in student layout
  app/(student)/student/{notices,wallet,privacy}           Week 3
  app/(university)/university/degrees/[enrolmentId]/print  Week 3
  app/(aicte)/admin/{audit,data-requests}                  Week 3 (AICTE_ADMIN)
  app/(public)/auth/digilocker/return                       Week 4: where DigiLocker sign-in lands (public)
  app/(student)/student/claim                               Week 4: claim a record by provisional id (pending DigiLocker claim)
  app/(aicte|ro)/.../{signals,completeness,reports}          Week 4 (officers)
  app/(university)/university/certificates[/[enrolmentId]/print]  Week 4: certificate integration (replaces degrees)
  e2e/                                Playwright tests of the demo path (Week 3, §12)
  next.config.ts                      rewrites /api/* to API_INTERNAL_URL (cookies, status and bodies pass through)
  lib/api.ts                          typed fetch client (throws ApiError with the envelope)
  lib/types.ts                        pasted from API_CONTRACT.md
  lib/auth.ts                         server-side getMe() for layouts and redirects
  components/ui/**                    UI agent
  components/brand/**                 UI agent
  components/**                       frontend (tables, KPI tiles, shells)
```

## 3. Auth model

- `POST /auth/login` with `{email, password}` validates argon2 hash, returns the user and sets cookie `cs_access`. From Week 4 it refuses every STUDENT account (the same 401 as a wrong password): a student signs in only through DigiLocker (D37, API_CONTRACT §A4.12), which ends by setting the same `cs_access` cookie. Two short-lived signed cookies support it: `cs_dl_state` (10 minutes, the OAuth state, nonce and return path) and `cs_dl_claim` (15 minutes, a DigiLocker identity that has not claimed a record yet; never an APAAR).
- Cookie: name `cs_access`, value = JWT (HS256, `API_SECRET_KEY`), `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` only when `COOKIE_SECURE=true` (false in compose), `Max-Age` = `API_ACCESS_TOKEN_MINUTES * 60` (default 120).
- JWT claims: `sub` (user id), `role`, `exp`, `iat`, `jti`. Scope is not in the token; the api loads the user row on each request.
- `POST /auth/logout` clears the cookie (`Max-Age=0`) and returns 204.
- `GET /me` returns the current user and scope. 401 when the cookie is missing, expired or invalid.
- The web never stores the token; the browser only ever talks to `/api/*` on its own origin. The Next.js route handler `app/api/[...path]/route.ts` forwards method, path, query, JSON body, `Cookie` header and returns the upstream status, body and `Set-Cookie` unchanged.
- Server components call the api with `API_INTERNAL_URL` directly and pass the incoming `cs_access` cookie through.
- CSRF: `SameSite=Lax` cookie plus JSON-only request bodies (`Content-Type: application/json` required on every mutating route; form posts are rejected with 415). No CSRF token in Week 1. One exception from Week 2: `POST /uploads` takes `multipart/form-data` (the file); the proxy streams that body through with its own `Content-Type`, and passes CSV and XLSX downloads back with `Content-Type` and `Content-Disposition` unchanged (API_CONTRACT §A2.1).
- Public endpoints (no cookie; a cookie, if sent, is ignored), each rate-limited per client address with the `RATE_LIMITED` envelope on 429 (D32, API_CONTRACT §A3.1):

  | endpoint | limit |
  |---|---|
  | `GET /healthz` | none |
  | `POST /auth/login` | `LOGIN_RATE_LIMIT` (10/min) |
  | `GET /notices/{token}`, `POST /notices/{token}/respond` | 30/min |
  | `GET /verify/{code}`, `POST /verify`, `GET /verify/d/{jws}`, `GET /verify/degree/{short_id}` | 60/min |
  | `GET /.well-known/jwks.json`, `GET /.well-known/jwt-vc-issuer`, `GET /status-lists/1` | 120/min |
  | `GET /privacy/notice` | 60/min |
  | `GET /auth/digilocker/start`, `GET /auth/digilocker/callback` (Week 4) | 30/min |
  | `GET` and `POST /auth/digilocker/claim` (Week 4; pending-claim cookie only) | POST 5 per 15 minutes per DigiLocker subject |
  | `GET /verify/completion/{short_id}` (Week 4; shares the verifier allowance) | 60/min |

- Public web pages: `/login`, `/verify` and its result pages, the notice page `/student/notices/[token]`, and from Week 4 `/auth/digilocker/return`. The notice page still shows its claim to whoever holds the link, but its Yes and No need DigiLocker sign-in, and `GET /notices/{token}` reads the cookie only to say who is looking. The notice page lives outside the `(student)` route group so the student layout's sign-in guard never runs for it, and `proxy.ts` lets `/student/notices/<token>` through without a cookie while `/student/notices` itself stays signed-in only.
- A second multipart route from Week 3: `POST /flags/{id}/response` (a note and up to three files) is exempt from the JSON-only 415 rule like `POST /uploads`. Binary downloads (attachments, the certificate block PDF, the data export, from Week 4 the reports and the completeness CSV) pass back with `Content-Type` and `Content-Disposition` unchanged.
- From Week 4 the `/api` proxy also passes `302` answers through with `Location` and every `Set-Cookie`, and never follows a redirect (the DigiLocker start and callback routes).

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
| `AICTE_ADMIN` | national | `/aicte` | every institution, region, case, signal, report, audit, admin tools; decides cases (D43), adds approval versions (D41) |
| `RO_OFFICER` | `scope.region` | `/ro` | institutions whose `region` equals theirs; cases and enrolments of those institutions; signals touching the region (members elsewhere counted, not listed); reports scoped to the region |
| `INSTITUTION` | `scope.institution_id` | `/college` | only its own institution, programmes, seats, records with their status, cases against it, its completeness and missing students, its column mapping; never a signal |
| `STUDENT` | `scope.student_id` | `/student` | only its own student row, its records with their status, notices, consents, attestations (wallet and shares), access log, data requests and export. From Week 4 a student signs in only through DigiLocker (D37): the account is created on first sign-in and bound to the student by APAAR, or by a provisional-id claim (D36); there is no student password |
| `UNIVERSITY` | `scope.university_id` | `/university` | institutions affiliated to it and their enrolments, read-only (case summaries on enrolment detail, no case actions, `/flags` is 403); completeness counts of its affiliates; the graduates of those institutions; certificate integration from Week 4 (completion attestations, the masked APAAR and the QR for its own certificate; D44) |
| `VERIFIER` | public, no login, not a `users` role | `/verify` | the verify pages only: a share code, a pasted presentation, a degree QR or a degree proof id. Sees the result and the fields the student disclosed (or the degree's printed fields), never a full APAAR, and has no search (Week 3) |

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

Codes used in Week 1: `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `INVALID_CREDENTIALS`, `VALIDATION_ERROR` (422, `details.fields` = `[{field, message}]`), `RATE_LIMITED`, `SOURCE_UNAVAILABLE`, `INTERNAL`. Added in Week 2: `FILE_TOO_LARGE`, `TOO_MANY_ROWS` (413), `UNSUPPORTED_FILE_TYPE` (415), `UPLOAD_HEADER_INVALID`, `UPLOAD_EMPTY` (422), `UPLOAD_IN_PROGRESS` (409). Added in Week 3 (D32, API_CONTRACT §A3.25): `NOTICE_NOT_FOUND` (404), `NOTICE_EXPIRED` (410), `NOTICE_ALREADY_CHANGED`, `NOTICE_LIVE`, `FLAG_TRANSITION_INVALID`, `CREDENTIAL_NOT_ELIGIBLE`, `CREDENTIAL_REVOKED` (409), `ATTACHMENT_TOO_LARGE` (413), `ATTACHMENT_TYPE` (415), `PRESENTATION_NOT_FOUND` (404), `RESEND_LIMIT` (429), and the generic `CONFLICT` (409, always with `details.reason`). Added in Week 4 (API_CONTRACT §A4.22, named as the copy deck's `err.*`): `SIGNIN_REQUIRED` (401), `NOTICE_IDENTITY_MISMATCH` (403), `DIGILOCKER_STATE_INVALID` (401), `CLAIM_NO_MATCH` (422), `CLAIM_ALREADY_CLAIMED`, `CLAIM_NOT_NEEDED` (409), `REASON_REQUIRED`, `CORRECTION_EMPTY`, `CORRECTION_INVALID`, `WITHDRAW_NONE_SELECTED` (422), `WITHDRAW_NOT_NAMED`, `UPHOLD_NEEDS_VERSION`, `DECISION_NOT_AVAILABLE`, `APPROVAL_BELOW_ASSIGNED` (409), `UPLOAD_HEADER_UNMAPPED`, `MAPPING_INCOMPLETE`, `MAPPING_DUPLICATE` (422), `SIGNAL_ALREADY_HANDLED` (409), `REPORT_NOT_FOUND` (404), `REPORT_FAILED` (500); `DIGILOCKER_CANCELLED` and `DIGILOCKER_FAILED` are states of the `/auth/digilocker/return` page.

- JSON only. `snake_case` keys on the wire. No nulls for lists (empty list instead); nulls allowed for scalar "not yet known".
- Money: none anywhere.

## 6. PII and masking

- APAAR (12 digits) is stored as `apaar_hmac` (HMAC-SHA256 with `PII_HMAC_KEY`), `apaar_encrypted` (Fernet, `PII_FERNET_KEY`) and `apaar_last4`. The full APAAR **never leaves the api**. The only shape the web sees is `apaar_masked = "XXXX XXXX 4417"`, or `null` when the student has no APAAR (consent `REFUSED` / `PENDING` / `INTERNATIONAL`), in which case `provisional_id` (`PRV-XXXXXXXX`) is shown.
- Mobile: stored as `mobile_hmac` plus `mobile_last4`; wire shape `mobile_masked = "XXXXXX1234"`.
- Address: `address_hmac` only, never returned.
- Passport (international students): `passport_hmac` plus `passport_masked = "X1234567"` is never returned in Week 1.
- Email is returned only to the student themselves (`/students/me`).
- Every endpoint that returns a student row records a `READ` entry in `audit_log` (actor, entity, timestamp). No PII in the audit `before`/`after` payloads; only ids and masked values.
- Week 3 adds READ entries for notice page views, credential reads and shares, verifier calls (with a keyed hash of the caller's address, never the address), attachment downloads and data exports (API_CONTRACT §A3.23); a student's access log shows the reader's role and the date, never a name.
- Student notice links: only `sha256(token)` is stored; the token is minted at delivery and exists only in the message (ENGINES §16.3). The public notice page shows no name, date of birth or contact detail.
- Public surfaces (notice page, verifier, degree QR and insert) mask a provisional id as `PRV-XXXX` plus its last four characters, as well as the APAAR.
- Case attachments are Fernet-encrypted on the `case-files` volume and read only through the scoped, audited download. A student's comment on a No is shown to officers only.
- Holder keys of the custodial demo wallet and the issuer's private key are Fernet-encrypted with `PII_FERNET_KEY`.
- Week 4: the APAAR in a DigiLocker id token is used in memory to find a student who already holds it with consent LINKED, and is never stored or logged; a student who refused consent keeps no APAAR even after signing in. Students missing from a college's upload are shown by name, roll number, programme and joining date to that college and to officers (they are its own admitted students), never with a full APAAR. Signals show shared contacts masked (`XXXXXX1234`, `r***@example.com`, "Same address") and never reach a college, a university or a student. Enrolment versions hold names and dates of birth for the record's history and only ever a masked APAAR; the audit log keeps field names, never values.

## 7. Seeded demo users (fixed, datagen must emit exactly these in `users.json`)

Password for all: `Countersign!2026`

| Email | Role | Scope |
|---|---|---|
| `admin@aicte.demo` | `AICTE_ADMIN` | national |
| `ro.west@aicte.demo` | `RO_OFFICER` | region `WEST` |
| `ro.south@aicte.demo` | `RO_OFFICER` | region `SOUTH` |
| `registrar@abc.edu.demo` | `INSTITUTION` | "ABC College of Engineering", `aicte_permanent_id` `1-ABC-0001`, state `MH`, region `WEST` |
| `registrar@xyz.edu.demo` | `INSTITUTION` | "XYZ Institute of Technology", `aicte_permanent_id` `1-XYZ-0002`, state `TN`, region `SOUTH` |
| `student@demo` | `STUDENT` | the "Ravi Kumar Sharma" student (enrolled at ABC College, B.Tech CSE, 2026-27). From Week 4 this account signs in only through DigiLocker (the Demo DigiLocker account with his APAAR binds to it on first sign-in); its password no longer works |
| `coe@univ.demo` | `UNIVERSITY` | the university ABC College is affiliated to (datagen names it "Maharashtra State Technical University", code `MSTU`) |

The login page shows these as role cards with the credentials prefilled; from Week 4 the student card is "Sign in with DigiLocker" and the Demo DigiLocker page lists Ravi Kumar Sharma first, then the other demo accounts of the datagen manifest (`demo_digilocker_accounts`). Named demo scenarios from the spec live at ABC College (132 admitted vs 120 approved in CSE; "Ravi Kumar Sharma" vs "R. K. Sharma").

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

Check status: `PASS`, `FAIL`, `PENDING` (source unavailable or awaiting reply), `NA` (not applicable, e.g. `STUDYING` for a first-year before results, `IDENTITY` when no APAAR is linked). `ADMISSION` is never `NA`: every route has a rule.

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

Added in Week 3 (API_CONTRACT Addendum 3):

- Notice channel: `EMAIL`, `DIGILOCKER`. Notice response: `YES`, `NO` (no reply is neutral). Delivery status: `QUEUED`, `SENT`, `FAILED`. A notice is live when unanswered, not FAILED and not expired.
- Student check state (`detail.notice_state`): `NOT_SENT`, `UNREACHABLE`, `SENT`, `EXPIRED` (all PENDING), `CONFIRMED` (PASS), `DENIED` (FAIL, raises STUDENT_DENIED). The Student check is never `NA`.
- Case actions: `CLEAR`, `REQUEST_DOCS`, `ESCALATE`, `CONFIRM`, `NOTE`, `ASSIGN`, `REOPEN` (officers), `COLLEGE_RESPONSE` (the college), `SYSTEM_NOTE` (the system). Transitions are the table in API_CONTRACT §A3.9.
- Credential kind: `ENROLMENT` (Enrolment proof), `DEGREE` (Degree proof). Credential status: `ACTIVE`, `REVOKED`, `EXPIRED`. Revocation reason code: `ENROLMENT_WITHDRAWN`, `ENROLMENT_TRANSFERRED`, `FLAG_CONFIRMED`, `ADMIN`.
- Verify result: `VALID`, `REVOKED`, `EXPIRED`, `INVALID`; verify method: `signature`, `register_lookup`.
- Consent purpose: `APAAR_LINK`, `NOTICE`, `CREDENTIAL_SHARE`; consent state: `GIVEN`, `WITHDRAWN`, `REFUSED`. Data request kind: `ACCESS`, `CORRECTION`, `ERASURE`; status: `OPEN`, `DONE`, `REJECTED`.

Added in Week 4 (API_CONTRACT Addendum 4; these replace the check status, the score and the flag decisions above):

- Evidence rows, in the deck's order: `IDENTITY` (Identity), `SEAT` (Seat), `ADMISSION` (Joining record), `STUDYING` (Credits), `STUDENT` (Student). Each has one evidence state: `CONFIRMED`, `CONTRADICTED`, `PENDING`, `NOT_YET_DUE`, `NOT_APPLICABLE`, `SOURCE_UNAVAILABLE` (replacing `PASS`, `FAIL`, `PENDING`, `NA`), and provenance: `supplied_by`, `observed_at`, `independent`, plus the copy deck's `finding` and `source_line`. Check source adds `ADMISSION_AUTHORITY` and `DIGILOCKER`.
- Record status, one per active record: `AWAITING_EVIDENCE`, `COUNTERSIGNED`, `UNDER_REVIEW`, `DISPUTED`; precedence DISPUTED, UNDER_REVIEW, COUNTERSIGNED, AWAITING_EVIDENCE. The evidence rule: Countersigned = identity confirmed (or the alternative route) + seat confirmed + at least one of Joining record, Credits and Student confirmed and independent of the college + nothing unresolved. There is no score and no "n of 5".
- Independent: a fact whose issuer is not the institution that made the claim (D38). Credits a college issued for itself are confirmed but not independent.
- Flag (case) types add `NOT_IN_JOINING_RECORD`, `ELIGIBILITY_BREACH`, `MISSING_FROM_UPLOAD`; `GHOST_RING` and `ANOMALY` cases are opened only from signals. Case status: `OPEN`, `DOCS_REQUESTED`, `ESCALATED`, `UPHELD`, `CORRECTED`, `WITHDRAWN` (words: Claim upheld, Claim corrected, Claim withdrawn). Case actions: `UPHOLD`, `CORRECT`, `WITHDRAW`, `REQUEST_DOCS`, `ESCALATE`, `NOTE`, `ASSIGN`, `REOPEN`, `COLLEGE_RESPONSE`, `SYSTEM_NOTE`. Every decision carries a reason code and a note.
- Credential (attestation) kind: `ENROLMENT`, `COMPLETION` (replacing `DEGREE`). Revocation reason codes add `CLAIM_WITHDRAWN` and `STUDENT_DISPUTE`.
- Deadline state: `NOT_DUE`, `ON_TIME`, `LATE`, `OVERDUE`. Signal type: `GHOST_RING`, `ANOMALY`; signal status: `NEW`, `CASE_OPENED`, `DISMISSED`. Version source: `UPLOAD`, `DECISION`, `SEED`.
- Joining year: the academic year in which the student joined the programme (the cohort year; for a lateral entrant the year it entered year 2), from `app/core/cohort.py`.

## 10. Endpoint availability by week

| Endpoint group | Week 1 | Week 2 | Week 3 | Week 4 |
|---|---|---|---|---|
| `/healthz`, `/auth/*`, `/me` | real | | | `/auth/digilocker/start`, `/callback`, `/claim` real; `POST /auth/login` refuses students |
| `/dashboard/summary` | real (`flags_open` = 0, `integrity_index` null) | `flags_open`, `countersigned_pct`, `clear_pct`, `flags_by_type`, `admitted` real | | records by status, `countersigned_pct` as the COUNTERSIGNED share, completeness, deadlines, cases by age, top institutions, `signals_new`; `clear_pct` removed |
| `/institutions`, `/institutions/{id}`, `/seats`, `/enrolments` | real, `countersign` null/[] | countersign, flags, seats (`seated`, `unseated`), `admitted`, `last_upload` real; enrolment filters `check_status`, `check_type`, `flagged`, `seated`; sort `flags_open_desc` real and default | | records by status, completeness, deadline state, approval version; enrolment rows carry the record status and brief rows; filter `record_status` replaces `check_status` and `check_type`; `integrity_index` and `countersign` removed |
| `/institutions/{id}/column-mapping` (GET, PUT), `/institutions/{id}/completeness` (+ `.csv`), `/completeness`, `POST /completeness/refresh` | absent | absent | absent | real |
| `/students/me` | real (no notices/credentials) | countersign real | `notices`, `credentials` filled; STUDENT check real | record status per enrolment, `decision`; `POST /students/me/enrolments/{id}/respond` real |
| `/admin/adapters/ping`, `/admin/audit/verify`, `/admin/audit` | real | | `/admin/audit` filters `entity_id`, `action`, `seq_from`, rows gain `actor_role` and `via`; web `/admin/audit` with Verify chain | ping adds `admission_authority` |
| `/admin/demo/reset` | 501, use `make demo-reset` | 501 | | |
| `/uploads`, `/uploads/rows`, `/uploads/{id}`, `/uploads/{id}/errors`, `/uploads/{id}/errors.csv`, `/uploads/template.csv`, `/uploads/template.xlsx` | absent (404) | real | | 22 template columns; saved column mapping and `UPLOAD_HEADER_UNMAPPED`; `column_mapping`, `counts.versions`, `counts.records` |
| `/enrolments/{id}`, `POST /enrolments/{id}/recheck`, `POST /institutions/{id}/recheck` | absent | real | enrolment detail gains `notices`, `resend`, `credentials`; `POST /enrolments/{id}/notices/resend` real | the record card: five evidence rows with provenance, record status, approval, claim, versions; `GET /enrolments/{id}/history` real; recheck answers in evidence states |
| `/approvals/{id}/versions` (GET, POST) | absent | absent | absent | real |
| `/flags`, `/flags/{id}` | absent | real, read-only | `POST /flags/{id}/actions`, `POST /flags/{id}/response` (multipart), `GET /flags/{id}/attachments/{attachment_id}`, `history`, `allowed_actions`, assignee, `assignee` and `response_received` filters; `GET /users` for the assignee picker | decisions UPHOLD, CORRECT, WITHDRAW with effects and `dry_run`; statuses UPHELD, CORRECTED, WITHDRAWN; three new case types; `covers`, `scope`, `decision`, `outstanding_enrolment_ids`, `missing_students` |
| `/notices/{token}`, `POST /notices/{token}/respond` (public) | absent | absent | real | `viewer`; answering needs DigiLocker sign-in |
| `/credentials`, `/credentials/{id}`, `/present`, `/presentations`, `/revoke` | absent | absent | real | issued when COUNTERSIGNED; kinds ENROLMENT and COMPLETION; new reason codes |
| `/.well-known/jwks.json`, `/.well-known/jwt-vc-issuer`, `/status-lists/1` (public) | absent | absent | real | |
| `/verify/{code}`, `POST /verify`, `/verify/d/{jws}`, `/verify/degree/{short_id}` (public) | absent | absent | real | `/verify/completion/{short_id}` added (the degree path stays as an alias) |
| `/university/graduates`, `/university/degrees/{id}`, `/issue`, `/insert.pdf` | absent | absent | real | replaced by `/university/certificates/{id}`, `/issue`, `/block.pdf`; graduates rows carry `attestation` |
| `/privacy/notice` (public), `/students/me/consents`, `/access-log`, `/data-requests`, `/export.json`, `/data-requests` (admin) | absent | absent | real | export carries states, the record and the history |
| `/signals`, `/signals/{id}`, `/open-case`, `/dismiss`, `POST /signals/run` | absent | absent | absent | real (officers only) |
| `/reports`, `/reports/{name}.{csv,xlsx,pdf}` | absent | absent | absent | real (AICTE and regional officers) |
| `/scores/*` | absent | | | dropped with the Integrity Index (D40) |
| `/psi/*`, web `/admin/psi` | absent | | | `POST /psi/compute` real (AICTE_ADMIN, §A4.26); services `psi` and `psi-client` (D48) |

The frontend may build pages against the contract once it is written, but must not ship navigation to routes whose endpoints are absent; show a "coming in Week N" placeholder behind the nav item instead.

There is no `/cases/*` api path: the officers' case queue pages (`/aicte/cases`, `/ro/cases`) read `GET /flags`.

## 11. Environment

All environment variables live in `.env.example` with a comment. Compose loads `.env`. The web uses `NEXT_PUBLIC_API_BASE=/api` in the browser and `API_INTERNAL_URL=http://api:8000` on the server.

Week 3 settings: `WEB_ORIGIN` (base of every link a person opens: notices, verify URLs), `ISSUER_URL` (credential `iss`, JWKS and status list base), `SMTP_ALLOWED_HOSTS` and `ALLOW_REAL_SMTP` (the mailer refuses any other host; `ALLOW_REAL_SMTP` is never set, like `ALLOW_REAL_GOV_APIS`), `NOTICE_FROM` (sender of notices and document requests), `CASE_FILES_DIR` (attachments volume), `DEMO_MODE` (true in the demo `.env`; enables `make audit-tamper`). `rules.yaml` gains `notices.expiry_days` (30) and `notices.change_window_days` (7). The older `WEB_BASE_URL` and `MAIL_FROM` keys are not read by Week 3 code.

Week 4 settings: `DIGILOCKER_CLIENT_ID`, `DIGILOCKER_CLIENT_SECRET` (shared with mockgov, which signs the demo id tokens with it), `DIGILOCKER_AUTHORIZE_URL` (the Demo DigiLocker page the browser opens) and `DIGILOCKER_ISSUER`. `rules.yaml` gains `reporting.deadline` (30 Sep 2026 for 2026-27), `eligibility` (each seat category rule with its handbook clause) and `signals.anomaly` (contamination 0.05, 200 trees, random state 0, at least 20 records); the `integrity_index` block is removed. mockgov gains `DIGILOCKER_CLIENT_ID`, `DIGILOCKER_REDIRECT_URIS` and `DIGILOCKER_ISSUER` to match.

## 12. Testing contract

- api: pytest against `countersign_test` (migrations applied fresh per session), `GOV_ADAPTER=inmemory`.
- mockgov: pytest with an in-memory SQLite fallback or `mockgov_test`; chaos tests assert 503.
- datagen: pytest on determinism and ground-truth integrity.
- web: `pnpm lint` and `pnpm typecheck` in CI.
- `make test` runs the three Python suites inside compose.
- Evaluation (D47): `make eval` rebuilds the databases, generates the small dataset with a 50,000-row throughput file, seeds everything through the engine and writes `tools/eval/out/eval_report.md` and `tools/eval/out/eval.json`, every number labelled synthetic. It exits non-zero when a target is missed: seeded inconsistencies caught at 95% or more, false alarms under 5% of known-clean records, 50,000 rows processed in under 2 minutes, and every cross-college request refused (ENGINES §17.14). It leaves the evaluation data seeded; run `make demo-reset` before a demo.
- End-to-end (D33): Playwright tests in `apps/web/e2e` drive the demo path against the running stack (`make up && make demo-reset && make seed` first). `make e2e` runs them from the host with Playwright's bundled Chromium (`pnpm exec playwright install chromium`); the config never sets `channel: "chrome"`, so no installed browser is used or copied. Base URL `WEB_ORIGIN`; Mailpit's API at `http://localhost:8025/api/v1` and mockgov's DigiLocker inbox at `http://localhost:8001/digilocker/inbox/{apaar_id}` are how the tests open notice links (the link exists only in the message). The notices left for the live demo are listed in the datagen manifest's `demo_unanswered_notices` (Ravi Kumar Sharma answers Yes, the `SECOND_DEMO_NOTICE` student answers No). The path: every role signs in; the ABC College CSE excess flag; the R. K. Sharma duplicate; Ravi's notice from Mailpit answered Yes, his Enrolment proof appears, three fields shared, the code verifies VALID; a No on the second notice raises STUDENT_DENIED; an officer requests documents, the registrar responds with a PDF, the officer clears; the university prints a degree insert and its QR (`/verify/d/...`) verifies; the AICTE officer verifies the audit chain. Tests run serially, because they share one seeded database.
- From Week 4 (D49) the end-to-end path is the deck's 60-second pitch: the ABC College sample record reads Disputed with its five rows (Joining record Contradicted, Student Contradicted "I never joined") and its next step; the evidence rule on the card; Ravi signs in through the Demo DigiLocker (`demo_digilocker_accounts` in the manifest), opens his notice and answers Yes; another account opening the same link sees "This notice is for someone else"; a refused-consent student claims a record by provisional id and it reads Countersigned; the officer requests documents, the registrar responds, and the officer withdraws the claim, after which the record reads Withdrawn, its seat is free and its attestation verifies as Revoked; completeness shows a college's missing students; a signal opens a case; a report downloads; the audit chain verifies.
