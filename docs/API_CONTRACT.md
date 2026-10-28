# API contract (Week 1)

Base URL from the browser: `/api` (proxied by the web app to `http://api:8000`). Base URL for mockgov: `http://mockgov:8001` (host `http://localhost:8001`). All bodies are JSON. Conventions (envelopes, ids, dates, enums, masking) are in `ARCHITECTURE.md` §5 and §6 and are not repeated here.

Every example below is normative: field names, casing and enum values are exact. Optional fields are marked `?`. `null` means "not known yet", never "absent".

---

## A. Countersign API (`services/api`, :8000)

### A.1 `GET /healthz` (public)

```json
200 { "status": "ok", "db": "ok", "redis": "ok", "version": "0.1.0" }
503 { "status": "degraded", "db": "ok", "redis": "down", "version": "0.1.0" }
```

### A.2 `POST /auth/login` (public, rate-limited 10/min per IP)

Request:

```json
{ "email": "registrar@abc.edu.demo", "password": "Countersign!2026" }
```

Response `200` sets cookie `cs_access` (see ARCHITECTURE §3) and returns:

```json
{
  "user": {
    "id": "6f1c0a8e-2b1d-4c9a-9e51-1c2f1a0b7d33",
    "email": "registrar@abc.edu.demo",
    "name": "Registrar, ABC College of Engineering",
    "role": "INSTITUTION",
    "scope": {
      "institution_id": "a0b1c2d3-1111-4222-8333-444455556666",
      "institution_name": "ABC College of Engineering",
      "region": "WEST",
      "student_id": null,
      "university_id": null
    }
  }
}
```

Errors: `401 INVALID_CREDENTIALS` ("Email or password is incorrect."), `422 VALIDATION_ERROR`, `429 RATE_LIMITED`.

### A.3 `POST /auth/logout` (any authenticated role)

`204`, clears the cookie. Unauthenticated callers also get `204`.

### A.4 `GET /me`

```json
200 { "user": { ...same User object as login... } }
401 { "error": { "code": "UNAUTHENTICATED", "message": "Sign in to continue.", "details": {} } }
```

`scope` always has all five keys; unused ones are `null`. For `AICTE_ADMIN` all five are `null`. For `RO_OFFICER` only `region` is set. For `UNIVERSITY` `university_id` and `university_name` (extra key, present only for that role) are set.

### A.5 `GET /dashboard/summary`

Roles: `AICTE_ADMIN`, `RO_OFFICER`, `INSTITUTION`, `UNIVERSITY`. Scoped automatically (admin: national; RO: its region; institution: its own college; university: its affiliates). `STUDENT` gets `403`.

Query: `academic_year?` (default: current, `2026-27`).

```json
200 {
  "academic_year": "2026-27",
  "scope": { "kind": "NATIONAL", "label": "All India" },
  "kpis": {
    "institutions": 50,
    "programmes": 212,
    "approved_seats": 18960,
    "enrolments": 10342,
    "flags_open": 0,
    "countersigned_pct": null
  },
  "by_state": [
    { "state_code": "MH", "state_name": "Maharashtra", "region": "WEST", "institutions": 9, "programmes": 41, "approved_seats": 3600, "enrolments": 2011, "flags_open": 0 }
  ],
  "by_region": [
    { "region": "WEST", "region_name": "Western (Mumbai)", "institutions": 12, "approved_seats": 4500, "enrolments": 2600, "flags_open": 0 }
  ]
}
```

`scope.kind` is one of `NATIONAL`, `REGION`, `INSTITUTION`, `UNIVERSITY`; `label` is display text ("Western Region", "ABC College of Engineering"). `by_state` is sorted by `state_name`; for an `INSTITUTION` it contains one row. `countersigned_pct` and `flags_open` are `null` / `0` in Week 1.

### A.6 `GET /institutions`

Roles: `AICTE_ADMIN`, `RO_OFFICER` (own region only, `region` query ignored), `UNIVERSITY` (own affiliates only), `INSTITUTION` (returns exactly one item, its own).

Query: `page`, `page_size`, `state?` (state code), `region?`, `type?`, `q?` (case-insensitive substring on name or `aicte_permanent_id`), `sort?` in `name|enrolments|approved_seats` (default `name`), `order?` in `asc|desc`.

```json
200 {
  "items": [
    {
      "id": "a0b1c2d3-1111-4222-8333-444455556666",
      "aicte_permanent_id": "1-ABC-0001",
      "name": "ABC College of Engineering",
      "type": "PRIVATE_SELF_FINANCED",
      "state_code": "MH",
      "state_name": "Maharashtra",
      "region": "WEST",
      "university_id": "c3d4e5f6-2222-4333-8444-555566667777",
      "university_name": "Maharashtra State Technical University",
      "programmes": 6,
      "approved_seats": 540,
      "enrolments": 571,
      "flags_open": 0,
      "integrity_index": null
    }
  ],
  "total": 50, "page": 1, "page_size": 25
}
```

`type` enum: `GOVERNMENT`, `GOVERNMENT_AIDED`, `PRIVATE_SELF_FINANCED`, `UNIVERSITY_DEPARTMENT`, `DEEMED`.

### A.7 `GET /institutions/{id}`

Roles: as A.6; out-of-scope id returns `404 NOT_FOUND`.

```json
200 {
  "id": "a0b1c2d3-1111-4222-8333-444455556666",
  "aicte_permanent_id": "1-ABC-0001",
  "name": "ABC College of Engineering",
  "type": "PRIVATE_SELF_FINANCED",
  "state_code": "MH",
  "state_name": "Maharashtra",
  "region": "WEST",
  "university_id": "c3d4e5f6-2222-4333-8444-555566667777",
  "university_name": "Maharashtra State Technical University",
  "address_city": "Pune",
  "established_year": 2004,
  "integrity_index": null,
  "integrity_components": null,
  "flags_open": 0,
  "programmes": [
    {
      "id": "p1p1p1p1-3333-4444-8555-666677778888",
      "code": "CSE",
      "name": "B.Tech Computer Science and Engineering",
      "level": "UG",
      "discipline": "ENGINEERING",
      "shift": "FIRST",
      "approval": { "academic_year": "2026-27", "approved_intake": 120 },
      "enrolments": 132,
      "pools": [
        { "seat_type": "REGULAR",       "capacity": 114, "is_supernumerary": false, "assigned": 114, "free": 0,  "reserved_for": null },
        { "seat_type": "NRI",           "capacity": 6,   "is_supernumerary": false, "assigned": 6,   "free": 0,  "reserved_for": null },
        { "seat_type": "TFW",           "capacity": 6,   "is_supernumerary": true,  "assigned": 4,   "free": 2,  "reserved_for": null },
        { "seat_type": "LATERAL",       "capacity": 12,  "is_supernumerary": true,  "assigned": 0,   "free": 12, "reserved_for": null },
        { "seat_type": "INTERNATIONAL", "capacity": 18,  "is_supernumerary": true,  "assigned": 1,   "free": 17, "reserved_for": "FN_OCI_PIO_CIWG" }
      ],
      "unseated": 12
    }
  ]
}
```

`level`: `DIPLOMA`, `UG`, `PG`, `POST_DIPLOMA`. `discipline`: `ENGINEERING`, `MANAGEMENT`, `COMPUTER_APPLICATIONS`, `PHARMACY`, `ARCHITECTURE`, `PLANNING`, `DESIGN`, `HOTEL_MANAGEMENT`, `APPLIED_ARTS`. `shift`: `FIRST`, `SECOND`. `unseated` = active enrolments with `seat_id = null` (0 in Week 1 for all but is computed, so the datagen "132 vs 120" scenario shows `unseated: 12` once Week 2 ledger runs; in Week 1 the seed importer leaves every enrolment unseated and `assigned` is `0` everywhere, `unseated` equals `enrolments`).

### A.8 `GET /institutions/{id}/seats`

Query: `page`, `page_size`, `programme_id?`, `seat_type?`, `status?`.

```json
200 {
  "items": [
    { "id": "s1...", "seat_code": "CSE-R-087", "programme_code": "CSE", "seat_type": "REGULAR", "status": "ASSIGNED", "reserved_for": null, "enrolment_id": "e1...", "student_name": "Ravi Kumar Sharma", "assigned_at": "2026-07-14T09:30:00Z" }
  ],
  "total": 156, "page": 1, "page_size": 25
}
```

`enrolment_id`, `student_name`, `assigned_at` are `null` for `FREE` seats. `reserved_for` is `null` or `CIWG` (one third of INTERNATIONAL seats) per rules.yaml.

### A.9 `GET /institutions/{id}/enrolments`

Query: `page`, `page_size`, `programme_id?`, `status?`, `academic_year?`, `q?` (name substring or `apaar_last4`).

```json
200 {
  "items": [
    {
      "id": "e1e1e1e1-5555-4666-8777-888899990000",
      "student": {
        "id": "st1...",
        "name": "Ravi Kumar Sharma",
        "apaar_masked": "XXXX XXXX 4417",
        "consent_status": "LINKED",
        "provisional_id": null,
        "nationality": "IN"
      },
      "programme_id": "p1...",
      "programme_code": "CSE",
      "academic_year": "2026-27",
      "year_of_study": 1,
      "admission_route": "COUNSELLING",
      "counselling_ref": "MHCET-2026-R1-004512",
      "category": "GENERAL",
      "seat_code": null,
      "status": "ACTIVE",
      "uploaded_at": "2026-07-14T09:30:00Z",
      "countersign": { "score": null, "checks": [] },
      "flags": []
    }
  ],
  "total": 571, "page": 1, "page_size": 25
}
```

`category`: `GENERAL`, `EWS`, `OBC`, `SC`, `ST`, `OTHER`. `flags` is a list of `{id, type, severity, status}` (empty in Week 1).

### A.10 `GET /students/me` (`STUDENT` only)

```json
200 {
  "id": "st1...",
  "name": "Ravi Kumar Sharma",
  "apaar_masked": "XXXX XXXX 4417",
  "consent_status": "LINKED",
  "provisional_id": null,
  "dob": "2007-03-21",
  "email": "ravi.sharma@example.demo",
  "mobile_masked": "XXXXXX4521",
  "enrolments": [
    {
      "id": "e1...",
      "institution_id": "a0b1...",
      "institution_name": "ABC College of Engineering",
      "programme_code": "CSE",
      "programme_name": "B.Tech Computer Science and Engineering",
      "academic_year": "2026-27",
      "year_of_study": 1,
      "status": "ACTIVE",
      "countersign": { "score": null, "checks": [] }
    }
  ],
  "notices": [],
  "credentials": []
}
```

### A.11 `GET /admin/adapters/ping` (`AICTE_ADMIN` only)

Calls each adapter with a harmless probe (`apaar_id` `000000000000`) and reports:

```json
200 {
  "adapter": "mockgov",
  "sources": {
    "apaar":       { "status": "OK",          "latency_ms": 12,   "detail": null },
    "counselling": { "status": "OK",          "latency_ms": 9,    "detail": null },
    "abc":         { "status": "OK",          "latency_ms": 14,   "detail": null },
    "digilocker":  { "status": "OK",          "latency_ms": 8,    "detail": null },
    "sii":         { "status": "UNAVAILABLE", "latency_ms": 3004, "detail": "timeout after 3000 ms" }
  },
  "checked_at": "2026-07-14T09:30:00Z"
}
```

`status` enum: `OK`, `UNAVAILABLE`, `DISABLED` (real adapter without `ALLOW_REAL_GOV_APIS`).

### A.12 `GET /admin/audit/verify` (`AICTE_ADMIN` only)

```json
200 { "ok": true,  "length": 1842, "first_broken_seq": null, "checked_at": "2026-07-14T09:30:00Z" }
200 { "ok": false, "length": 1842, "first_broken_seq": 917,  "checked_at": "2026-07-14T09:30:00Z" }
```

### A.13 `GET /admin/audit?page&page_size&actor_id?&entity_type?` (`AICTE_ADMIN`)

```json
200 { "items": [ { "seq": 917, "at": "2026-07-14T09:30:00Z", "actor_id": "6f1c...", "actor_email": "admin@aicte.demo", "action": "READ", "entity_type": "student", "entity_id": "st1...", "hash": "9f8e...", "prev_hash": "1a2b..." } ], "total": 1842, "page": 1, "page_size": 25 }
```

`action`: `CREATE`, `UPDATE`, `DELETE`, `READ`, `LOGIN`, `LOGOUT`, `SEED`.

### A.14 `GET /meta/regions` and `GET /meta/states` (any authenticated role)

```json
200 { "items": [ { "code": "WEST", "name": "Western", "hq_city": "Mumbai" } ] }
200 { "items": [ { "code": "MH", "name": "Maharashtra", "region": "WEST" } ] }
```

---

## B. Scoping table

| Endpoint | AICTE_ADMIN | RO_OFFICER | INSTITUTION | STUDENT | UNIVERSITY |
|---|---|---|---|---|---|
| `/dashboard/summary` | national | region rows | own college | 403 | affiliates |
| `/institutions` | all | region | own only (total 1) | 403 | affiliates |
| `/institutions/{id}` | any | region, else 404 | own, else 404 | 403 | affiliate, else 404 |
| `/institutions/{id}/seats`, `/enrolments` | any | region, else 404 | own, else 404 | 403 | affiliate, else 404 |
| `/students/me` | 403 | 403 | 403 | own | 403 |
| `/admin/*` | ok | 403 | 403 | 403 | 403 |
| `/meta/*` | ok | ok | ok | ok | ok |

403 body: `{"error":{"code":"FORBIDDEN","message":"Your role cannot access this resource.","details":{"required_roles":[...]}}}`.
404 body: `{"error":{"code":"NOT_FOUND","message":"Institution not found.","details":{}}}`.

---

## C. mockgov API (`services/mockgov`, :8001)

Separate service and database. Behaves like a real government API: verify-only, never returns stored names, no auth in the demo. Every endpoint honours chaos settings (latency, failure rate, down).

### C.1 `GET /healthz`

```json
200 { "status": "ok", "db": "ok", "chaos": { "apaar": {"latency_ms": 0, "fail_rate": 0, "down": false}, "...": {} } }
```

### C.2 `POST /apaar/verify`

```json
req  { "apaar_id": "123456784417", "name": "Ravi Kumar Sharma", "dob": "2007-03-21" }
200  { "exists": true,  "name_score": 100, "dob_match": true }
200  { "exists": true,  "name_score": 71,  "dob_match": false }
200  { "exists": false, "name_score": 0,   "dob_match": false }
422  { "error": { "code": "VALIDATION_ERROR", "message": "apaar_id must be 12 digits.", "details": {} } }
503  { "error": { "code": "SOURCE_DOWN", "message": "APAAR registry unavailable.", "details": {} } }
```

`name_score` = RapidFuzz `token_set_ratio` on normalised names (0-100). The registry's stored name is never returned.

### C.3 `POST /counselling/verify`

```json
req  { "state": "MH", "year": 2026, "name": "Ravi Kumar Sharma", "dob": "2007-03-21", "roll_no": "MHCET-2026-004512", "programme": "CSE", "institution_aicte_id": "1-ABC-0001" }
200  { "found": true,  "round": 1, "category": "GENERAL", "allotment_ref": "MHCET-2026-R1-004512" }
200  { "found": false, "round": null, "category": null, "allotment_ref": null }
```

`roll_no` and `institution_aicte_id` are optional; when `roll_no` is given it is matched exactly, otherwise `name` (fuzzy ≥ 90) + `dob` + `state` + `year` + `programme`.

### C.4 `POST /abc/credits`

```json
req  { "apaar_id": "123456784417", "academic_year": "2025-26" }
200  { "apaar_id_known": true, "semesters": [ { "sem": 1, "credits": 22, "uploaded_at": "2026-01-20T00:00:00Z", "result": "PASS" }, { "sem": 2, "credits": 24, "uploaded_at": "2026-06-30T00:00:00Z", "result": "PASS" } ] }
200  { "apaar_id_known": true, "semesters": [] }
200  { "apaar_id_known": false, "semesters": [] }
```

`result`: `PASS`, `FAIL`, `PENDING`.

### C.5 `POST /digilocker/notify`

```json
req  { "apaar_id": "123456784417", "message": "ABC College of Engineering says you joined B.Tech CSE (2026-27). Is that right?", "callback_url": "http://localhost:3000/student/notices/tok_abc123" }
202  { "delivered": true, "inbox_id": "ib_01HZ..." }
200  { "delivered": false, "inbox_id": null, "reason": "APAAR_NOT_LINKED" }
```

### C.6 `GET /digilocker/inbox/{apaar_id}`

```json
200 { "items": [ { "inbox_id": "ib_01HZ...", "message": "...", "callback_url": "...", "received_at": "2026-07-14T09:30:00Z", "read": false } ] }
```

### C.7 `POST /sii/verify`

```json
req  { "passport_no": "N1234567", "name": "Aisha Rahman", "nationality": "BD" }
200  { "admitted": true,  "institution_aicte_id": "1-ABC-0001", "programme": "CSE", "academic_year": "2026-27" }
200  { "admitted": false, "institution_aicte_id": null, "programme": null, "academic_year": null }
```

### C.8 Chaos

```json
GET  /admin/chaos
200  { "apaar": { "latency_ms": 0, "fail_rate": 0.0, "down": false }, "counselling": {...}, "abc": {...}, "digilocker": {...}, "sii": {...} }

POST /admin/chaos
req  { "source": "apaar", "latency_ms": 2500, "fail_rate": 0.0, "down": true }
200  { "apaar": { "latency_ms": 2500, "fail_rate": 0.0, "down": true } }

POST /admin/chaos/reset
200  { ...all zero/false... }
```

`source` enum: `apaar`, `counselling`, `abc`, `digilocker`, `sii`, `all`. `down: true` returns `503 SOURCE_DOWN` on every call to that source. `fail_rate` (0-1) returns `503` randomly. `latency_ms` sleeps before answering. Defaults from `MOCKGOV_LATENCY_MS` and `MOCKGOV_FAIL_RATE`.

---

## D. TypeScript types (paste as `apps/web/lib/types.ts`)

```ts
export type Role = "AICTE_ADMIN" | "RO_OFFICER" | "INSTITUTION" | "STUDENT" | "UNIVERSITY" | "VERIFIER";
export type Region =
  | "NORTH" | "NORTH_WEST" | "CENTRAL" | "WEST" | "WEST_CENTRAL"
  | "SOUTH_WEST" | "SOUTH" | "SOUTH_CENTRAL" | "EAST" | "NORTH_EAST";

export type CheckType = "IDENTITY" | "ADMISSION" | "SEAT" | "STUDYING" | "STUDENT";
export type CheckStatus = "PASS" | "FAIL" | "PENDING" | "NA";
export type FlagType =
  | "EXCESS_ADMISSION" | "QUOTA_BREACH" | "LATE_REFILL" | "INVALID_APAAR" | "NAME_MISMATCH"
  | "DUPLICATE_CROSS_INSTITUTION" | "DUPLICATE_WITHIN_UPLOAD" | "DUAL_ENROLMENT_ALLOWED"
  | "NO_ACADEMIC_ACTIVITY" | "STUDENT_DENIED" | "GHOST_RING" | "ANOMALY";
export type Severity = "LOW" | "MEDIUM" | "HIGH";
export type FlagStatus = "OPEN" | "DOCS_REQUESTED" | "CLEARED" | "ESCALATED" | "CONFIRMED";
export type ConsentStatus = "LINKED" | "REFUSED" | "PENDING" | "INTERNATIONAL";
export type AdmissionRoute = "COUNSELLING" | "MANAGEMENT" | "NRI" | "SPOT" | "LATERAL" | "INTERNATIONAL" | "TFW";
export type SeatType = "REGULAR" | "NRI" | "TFW" | "LATERAL" | "INTERNATIONAL";
export type SeatStatus = "FREE" | "ASSIGNED" | "RELEASED";
export type EnrolmentStatus = "ACTIVE" | "WITHDRAWN" | "TRANSFERRED" | "GRADUATED";
export type Category = "GENERAL" | "EWS" | "OBC" | "SC" | "ST" | "OTHER";
export type InstitutionType = "GOVERNMENT" | "GOVERNMENT_AIDED" | "PRIVATE_SELF_FINANCED" | "UNIVERSITY_DEPARTMENT" | "DEEMED";
export type Level = "DIPLOMA" | "UG" | "PG" | "POST_DIPLOMA";
export type Discipline =
  | "ENGINEERING" | "MANAGEMENT" | "COMPUTER_APPLICATIONS" | "PHARMACY" | "ARCHITECTURE"
  | "PLANNING" | "DESIGN" | "HOTEL_MANAGEMENT" | "APPLIED_ARTS";
export type Shift = "FIRST" | "SECOND";
export type SourceStatus = "OK" | "UNAVAILABLE" | "DISABLED";
export type AuditAction = "CREATE" | "UPDATE" | "DELETE" | "READ" | "LOGIN" | "LOGOUT" | "SEED";

export interface ApiErrorBody { error: { code: string; message: string; details: Record<string, unknown> } }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface UserScope {
  institution_id: string | null; institution_name: string | null; region: Region | null;
  student_id: string | null; university_id: string | null; university_name?: string | null;
}
export interface User { id: string; email: string; name: string; role: Role; scope: UserScope }

export interface Check { type: CheckType; status: CheckStatus; source: string; checked_at: string | null; detail: Record<string, unknown> }
export interface Countersign { score: { passes: number; applicable: number } | null; checks: Check[] }
export interface FlagRef { id: string; type: FlagType; severity: Severity; status: FlagStatus }

export interface DashboardSummary {
  academic_year: string;
  scope: { kind: "NATIONAL" | "REGION" | "INSTITUTION" | "UNIVERSITY"; label: string };
  kpis: { institutions: number; programmes: number; approved_seats: number; enrolments: number; flags_open: number; countersigned_pct: number | null };
  by_state: { state_code: string; state_name: string; region: Region; institutions: number; programmes: number; approved_seats: number; enrolments: number; flags_open: number }[];
  by_region: { region: Region; region_name: string; institutions: number; approved_seats: number; enrolments: number; flags_open: number }[];
}

export interface InstitutionRow {
  id: string; aicte_permanent_id: string; name: string; type: InstitutionType;
  state_code: string; state_name: string; region: Region;
  university_id: string | null; university_name: string | null;
  programmes: number; approved_seats: number; enrolments: number; flags_open: number; integrity_index: number | null;
}
export interface SeatPool { seat_type: SeatType; capacity: number; is_supernumerary: boolean; assigned: number; free: number; reserved_for: string | null }
export interface ProgrammeDetail {
  id: string; code: string; name: string; level: Level; discipline: Discipline; shift: Shift;
  approval: { academic_year: string; approved_intake: number }; enrolments: number; pools: SeatPool[]; unseated: number;
}
export interface InstitutionDetail extends Omit<InstitutionRow, "programmes"> {
  address_city: string | null; established_year: number | null; integrity_components: Record<string, number> | null; programmes: ProgrammeDetail[];
}
export interface SeatRow {
  id: string; seat_code: string; programme_code: string; seat_type: SeatType; status: SeatStatus; reserved_for: string | null;
  enrolment_id: string | null; student_name: string | null; assigned_at: string | null;
}
export interface StudentRef { id: string; name: string; apaar_masked: string | null; consent_status: ConsentStatus; provisional_id: string | null; nationality: string }
export interface EnrolmentRow {
  id: string; student: StudentRef; programme_id: string; programme_code: string; academic_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category; seat_code: string | null;
  status: EnrolmentStatus; uploaded_at: string; countersign: Countersign; flags: FlagRef[];
}
export interface StudentMe {
  id: string; name: string; apaar_masked: string | null; consent_status: ConsentStatus; provisional_id: string | null;
  dob: string; email: string | null; mobile_masked: string | null;
  enrolments: { id: string; institution_id: string; institution_name: string; programme_code: string; programme_name: string; academic_year: string; year_of_study: number; status: EnrolmentStatus; countersign: Countersign }[];
  notices: unknown[]; credentials: unknown[];
}
export interface AdapterPing {
  adapter: "inmemory" | "mockgov" | "real";
  sources: Record<"apaar" | "counselling" | "abc" | "digilocker" | "sii", { status: SourceStatus; latency_ms: number; detail: string | null }>;
  checked_at: string;
}
export interface AuditVerify { ok: boolean; length: number; first_broken_seq: number | null; checked_at: string }
export interface AuditRow { seq: number; at: string; actor_id: string | null; actor_email: string | null; action: AuditAction; entity_type: string; entity_id: string | null; hash: string; prev_hash: string | null }
export interface RegionMeta { code: Region; name: string; hq_city: string }
export interface StateMeta { code: string; name: string; region: Region }
```

---

## E. Datagen output consumed by the seeders (file contract)

`make datagen` writes `/data/generated/` (compose volume `generated-data`):

```
institutions.json      { regions:[{code,name,hq_city}], states:[{code,name,region}], universities:[{code,name,state_code}],
                         institutions:[{aicte_permanent_id,name,type,state_code,university_code,address_city,established_year,
                                        programmes:[{code,name,level,discipline,shift,approvals:[{academic_year,approved_intake}]}]}] }
users.json             [ {email,password,role,name,institution_aicte_id?,region?,student_ref?,university_code?} ]  (exactly ARCHITECTURE §7)
uploads/<aicte_id>_<year>.csv (+ .xlsx)   columns: apaar_id,name,dob,gender,mobile,email,address,nationality,passport_no,
                                                    programme_code,academic_year,year_of_study,admission_route,counselling_ref,category,consent_status
ground_truth.json      [ {anomaly_type, institution_aicte_id, programme_code?, student_refs:[...], expected_flag, note} ]
mockgov/apaar_registry.jsonl   {apaar_id,name,dob}
mockgov/counselling.jsonl      {state,year,name,dob,roll_no,programme,institution_aicte_id,round,category,allotment_ref}
mockgov/abc_credits.jsonl      {apaar_id,academic_year,sem,credits,uploaded_at,result}
mockgov/sii.jsonl              {passport_no,name,nationality,institution_aicte_id,programme,academic_year}
manifest.json          {size,seed,generated_at,counts:{...}}
```

`student_ref` for the demo student is the row's `apaar_id` (`123456784417`, "Ravi Kumar Sharma", dob `2007-03-21`).

## Addendum 1 (2026-10-28): small Week 1 additions from the UX review

Both sides implement these in Week 1. Everything else in the contract is unchanged.

1. `GET /institutions` accepts `sort` = `enrolments_desc` (default) | `name_asc` | `flags_open_desc` (Week 2 data, allowed now, falls back to enrolments). Rows gain `region_name`.
2. `GET /institutions/{id}`: each pool gains `rule_source` (string from rules.yaml); `approval` gains `cutoff_date` (ISO date or null); detail gains `last_upload: {batch_id, uploaded_at, rows, errors} | null` (null in Week 1).
3. `GET /institutions/{id}/enrolments` accepts `sort` = `name_asc` (default) | `year_desc` | `route_asc`, and filters `admission_route`, `year_of_study`. Rows gain `upload_batch_id` (nullable) and `source_row_no` (nullable int).
4. `GET /institutions/{id}/seats` accepts `q` (matches seat_code prefix or holder name).
5. `429 RATE_LIMITED` carries `details.retry_after` (seconds, int).
6. 404 messages are entity-specific: "Institution not found.", "Enrolment not found.", "Seat not found.", "Flag not found.".
7. api passthrough for the demo (AICTE_ADMIN only, audited): `GET /admin/chaos` and `POST /admin/chaos` and `POST /admin/chaos/reset` on the api forward to mockgov with the same bodies and return mockgov's response, so the browser never talks to :8001 directly.
8. `POST /admin/demo/reset` (AICTE_ADMIN only) is reserved for Week 2; Week 1 returns 501 `NOT_IMPLEMENTED` with message "Run make demo-reset."
9. 422 `VALIDATION_ERROR` on both api and mockgov carries `details.fields = [{field, message}]` and `message` = the first field's message. (Supersedes the empty `details` shown in section C.2.)
10. `GET /institutions/{id}/seats` accepts `academic_year?` (default: current, `2026-27`) and returns only the seats in pools of that year's approvals. Each approval year has its own pools, so a seat code such as `CSE-R-087` repeats across years and is unique within one. Rows gain `academic_year`, the approval year of the seat's pool.

## Addendum 2 (2026-10-28): Week 2 endpoints and shapes

Implements DECISIONS D14 to D22. Everything below is normative in the same way as sections A to E: field names, casing, enum values and the quoted sentences are exact. The internal Python interfaces behind these endpoints are in `ENGINES.md`; the schema is `DATA_MODEL.md` "Migration 0002". Where this addendum and an earlier section disagree, this addendum wins.

### A2.1 Conventions added

- **One multipart route.** `POST /uploads` takes `multipart/form-data`; it is the only mutating route exempt from the JSON-only 415 rule (ARCHITECTURE §3). The web proxy (`app/api/[...path]/route.ts`) must forward that request body as a stream with its original `Content-Type` (boundary included), and must pass non-JSON responses (`text/csv`, XLSX) through with `Content-Type` and `Content-Disposition` unchanged.
- **New error codes**: `FILE_TOO_LARGE` (413), `TOO_MANY_ROWS` (413), `UNSUPPORTED_FILE_TYPE` (415), `UPLOAD_HEADER_INVALID` (422, `details.missing_columns`, `details.duplicate_columns`), `UPLOAD_EMPTY` (422), `UPLOAD_IN_PROGRESS` (409, `details.batch_id`). 404 messages: "Upload not found.", "Enrolment not found.", "Flag not found." (Addendum 1 item 6).
- **Dates in sentences.** Every date inside a `summary`, a check `detail.summary` or an evidence fact `value` is written `5 Oct 2026` (day without a leading zero, three-letter English month, year). Date fields stay `YYYY-MM-DD`.
- **New enums** (also in §A2.23):
  - `ProgrammeMode`: `PHYSICAL`, `ODL`, `ONLINE`.
  - `UploadStatus`: `QUEUED`, `VALIDATING`, `PROCESSING`, `DONE`, `FAILED` (`PROCESSING` replaces the Week 1 `CHECKING`).
  - `UploadStage`: `PARSE`, `VALIDATE`, `FILE_DUPLICATES`, `UPSERT`, `LEDGER`, `CHECKS`, `DUPLICATES`, `FLAGS`, `DONE`.
  - `UploadSource`: `FILE`, `API`, `SEED`. `UploadKind`: `INITIAL`, `UPDATE`.
  - `RowErrorLevel`: `ERROR` (the row was rejected), `WARNING` (the row was accepted; a note for the registrar).
  - `CheckSource`: `APAAR`, `COUNSELLING`, `SEAT_LEDGER`, `ABC`, `SII`, `STUDENT_NOTICE`.

### A2.2 Upload file format (D14)

One file (or one `POST /uploads/rows` body) is one institution and one academic year. Columns, in template order: the 16 from section E, then `status`, `status_date`, `admission_date`.

| column | header must be present | value | rule |
|---|---|---|---|
| `apaar_id` | no | optional | 12 digits after removing spaces. Anything else gives an APAAR_FORMAT warning and the row is kept without an APAAR (the Identity check then fails with INVALID_APAAR). Used only when consent is LINKED |
| `name` | yes | required | as on the admission register, up to 200 characters; Devanagari allowed |
| `dob` | yes | required | `YYYY-MM-DD`; an XLSX date cell is accepted |
| `gender` | no | optional | `M`, `F`, `O`, `U` or `Male`, `Female`, `Other`; blank is `U` |
| `mobile` | no | optional | 10 digits after removing spaces, a leading `+91` or `0`; otherwise a MOBILE_FORMAT warning and the value is not used |
| `email` | no | optional | one `@` with a dot after it; otherwise an EMAIL_FORMAT warning and the value is not used |
| `address` | no | optional | free text; stored only as an HMAC |
| `nationality` | no | optional | ISO 3166 alpha-2, default `IN` |
| `passport_no` | no | conditional | required when `admission_route` is INTERNATIONAL, `consent_status` is INTERNATIONAL or `nationality` is not `IN` |
| `programme_code` | yes | required | a programme of this institution (FIRST shift when the code exists in both) |
| `academic_year` | no | optional | must equal the upload's academic year; blank means the upload's |
| `year_of_study` | yes | required | whole number from 1 to the programme's `duration_years` |
| `admission_route` | yes | required | `COUNSELLING`, `MANAGEMENT`, `NRI`, `SPOT`, `LATERAL`, `INTERNATIONAL`, `TFW` |
| `counselling_ref` | no | optional | the counselling allotment reference, e.g. `MHCET-2026-R1-004512` |
| `category` | yes | required | `GENERAL`, `EWS`, `OBC`, `SC`, `ST`, `OTHER` |
| `consent_status` | no | optional | `LINKED`, `REFUSED`, `PENDING`, `INTERNATIONAL`. Blank: LINKED with a usable APAAR, INTERNATIONAL for an international row, else PENDING |
| `status` | no | optional | `ACTIVE`, `WITHDRAWN`, `TRANSFERRED`. Blank: ACTIVE for a new enrolment, unchanged for an existing one |
| `status_date` | no | optional | `YYYY-MM-DD`, not after the upload date. Blank: the upload date when the status changes |
| `admission_date` | no | optional | `YYYY-MM-DD`, not after the upload date. Blank: the upload date for a new enrolment, unchanged for an existing one. Drives LATE_REFILL |

Rules:

- Headers are matched after trimming, lower-casing and turning spaces and hyphens into underscores. Unknown headers are listed in the batch's `ignored_columns` and otherwise ignored. A missing required header, or a header that appears twice, rejects the whole file (`UPLOAD_HEADER_INVALID`).
- Enum values are matched case-insensitively with spaces and hyphens read as underscores (`Counselling`, `spot` and `TFW` are fine).
- Blank lines are skipped and not counted. CSV must be UTF-8 (a BOM is allowed); XLSX uses the first sheet.
- `row_no` is the spreadsheet row number: the header is row 1, the first data row is row 2. For `POST /uploads/rows` it is the 1-based position in `rows`.
- A row with any `ERROR` entry is rejected; a row with only `WARNING` entries is accepted. Every problem in a row is reported, one entry per field.
- Upsert key and identity: D14 and ENGINES.md §5. Rows not in a file are never touched (a file is a delta).
- CIWG: an INTERNATIONAL-route row with nationality `IN` is a child of an Indian worker in the Gulf and may take the CIWG-reserved international seats.

### A2.3 Row error codes

The api writes `message` exactly as below with the placeholders filled; the web shows it verbatim (copy deck `rowerr.*` follows these). `{field_word}`: `name` Name, `dob` Date of birth, `programme_code` Programme code, `year_of_study` Year of study, `admission_route` Admission route, `category` Category.

| code | level | field | message | when |
|---|---|---|---|---|
| `MISSING_REQUIRED` | ERROR | the column | `{field_word} is required` | a required value is blank |
| `APAAR_FORMAT` | WARNING | `apaar_id` | `APAAR must be 12 digits` | an APAAR is given but is not 12 digits; the row is accepted without it |
| `DUPLICATE_IN_FILE` | ERROR | `apaar_id` | `Same APAAR appears on row {other_row}` | the APAAR was already used by an earlier row of this file; the later row is rejected |
| `DUPLICATE_IN_FILE` | ERROR | `passport_no` | `Same passport number appears on row {other_row}` | the same for a passport |
| `DUPLICATE_IN_FILE` | ERROR | `name` | `Same student (name, date of birth and mobile) appears on row {other_row}` | two rows without APAAR or passport resolve to the same provisional student |
| `UNKNOWN_PROGRAMME` | ERROR | `programme_code` | `Programme code {value} is not approved for your college` | no programme with that code at this institution |
| `NO_APPROVAL_FOR_COHORT` | ERROR | `year_of_study` | `{programme_code} has no approval for {cohort_year}, the intake of a year {year_of_study} student in {academic_year}` | the programme has no approval for the row's cohort year |
| `DOB_FORMAT` | ERROR | `dob` | `Date of birth must be YYYY-MM-DD` | not a date |
| `DOB_IMPLAUSIBLE` | ERROR | `dob` | `Date of birth {value} gives an age of {age} at admission; expected 14 to 60` | age on 1 July of the cohort start year outside 14 to 60, or a date in the future |
| `BAD_ENUM` | ERROR | `admission_route` | `Admission route must be one of Counselling, Management, NRI, Spot, Lateral, International, TFW` | |
| `BAD_ENUM` | ERROR | `category` | `Category must be one of General, EWS, OBC, SC, ST, Other` | |
| `BAD_ENUM` | ERROR | `consent_status` | `Consent status must be Linked, Refused, Pending or International` | |
| `BAD_ENUM` | ERROR | `status` | `Status must be Active, Withdrawn or Transferred` | |
| `BAD_ENUM` | WARNING | `gender` | `Gender must be M, F, O or U; recorded as U` | |
| `YEAR_OF_STUDY_INVALID` | ERROR | `year_of_study` | `Year of study must be a whole number between 1 and {max}` | `{max}` is the programme's duration, 6 when the programme is unknown |
| `YEAR_MISMATCH` | ERROR | `academic_year` | `Academic year {value} does not match this upload's academic year {academic_year}` | |
| `PASSPORT_REQUIRED` | ERROR | `passport_no` | `International students need a passport number` | |
| `NATIONALITY_FORMAT` | ERROR | `nationality` | `Nationality must be a two-letter country code, e.g. IN` | |
| `DATE_FORMAT` | ERROR | `status_date` or `admission_date` | `Status date must be YYYY-MM-DD` or `Admission date must be YYYY-MM-DD` | |
| `DATE_IN_FUTURE` | ERROR | `status_date` or `admission_date` | `Status date {value} is after the upload date` or `Admission date {value} is after the upload date` | |
| `MOBILE_FORMAT` | WARNING | `mobile` | `Mobile must be 10 digits; the value was not used` | |
| `EMAIL_FORMAT` | WARNING | `email` | `Email address is not valid; the value was not used` | |
| `CONSENT_CONFLICT` | WARNING | `consent_status` | `APAAR given but consent is {consent_word}; the APAAR was not used` | APAAR present with REFUSED, PENDING or INTERNATIONAL consent |
| `CONSENT_CONFLICT` | WARNING | `consent_status` | `Consent is Linked but no APAAR was given; recorded as Pending` | |
| `NOT_PREVIOUSLY_ENROLLED` | WARNING | `status` | `No earlier enrolment matches this student; recorded as {status_word} with no seat` | a WITHDRAWN or TRANSFERRED row creates the enrolment |

The copy deck's `ROUTE_INVALID`, `CONSENT_INVALID` and `YEAR_INVALID` keys are replaced by `BAD_ENUM` (per field) and `YEAR_OF_STUDY_INVALID`.

`value_masked`, the offending value as the registrar may see it: a 12-digit APAAR as `XXXX XXXX 4417`, any other APAAR value as `<11 characters>` (its length only); passport as `XXXXX567` (last three kept); mobile as `XXXXXX1234` (or `<n characters>` when shorter than 4); email as `r***@example.com`; `address` never (null); every other field as uploaded, cut to 64 characters; null when the value is blank.

### A2.4 `POST /uploads` (multipart)

Roles: `INSTITUTION` (its own institution), `AICTE_ADMIN` (any institution, `institution_id` required). `RO_OFFICER`, `UNIVERSITY`, `STUDENT`: 403.

Form fields: `file` (required, `.csv` or `.xlsx`, at most `UPLOAD_MAX_BYTES`, 20 MB), `academic_year` (required, `YYYY-YY`, must have at least one approval at the institution), `institution_id` (required for AICTE_ADMIN; an INSTITUTION may omit it, and any other value than its own gives 404), `declaration` (required, the string `true`; the registrar ticked [upload.declaration]). A `kind` field, if sent, is ignored: the server sets `kind` (INITIAL when the institution has no earlier DONE batch for that academic year, else UPDATE).

The api checks the header synchronously (so a wrong template fails at once), writes the file encrypted to the spool, commits the batch as QUEUED, enqueues `run_batch` and answers:

```json
202 Location: /uploads/b7c1d2e3-4444-4555-8666-777788889999
{ "batch": { ...UploadBatch (§A2.7), "status": "QUEUED", "stage": null, "progress_pct": 0... } }
```

Errors:

| status | code | message |
|---|---|---|
| 409 | `UPLOAD_IN_PROGRESS` | "An upload for this college and year is still being processed." `details.batch_id` |
| 413 | `FILE_TOO_LARGE` | "The file is larger than 20 MB. Split it by programme and upload each part." |
| 413 | `TOO_MANY_ROWS` | "The file has more than 50,000 rows. Split it and upload each part." |
| 415 | `UNSUPPORTED_FILE_TYPE` | "Only .csv and .xlsx files can be uploaded." |
| 422 | `UPLOAD_HEADER_INVALID` | "The file is missing required columns: name, dob." (`details.missing_columns: ["name","dob"]`, `details.duplicate_columns: []`) |
| 422 | `UPLOAD_EMPTY` | "The file has a header but no rows." |
| 422 | `VALIDATION_ERROR` | first field message, e.g. `declaration`: "Tick the declaration to upload.", `academic_year`: "Your college has no approvals for 2027-28." |
| 404 | `NOT_FOUND` | "Institution not found." |

### A2.5 `POST /uploads/rows` (JSON, for institution systems)

Same roles, scoping, declaration and errors as §A2.4 (`TOO_MANY_ROWS` above `UPLOAD_ROWS_API_MAX`, 5,000 rows per call). Same columns as §A2.2 as JSON keys; values are strings, `year_of_study` may be a number, `null` means blank. Unknown keys go to `ignored_columns`.

```json
POST /uploads/rows
{
  "academic_year": "2026-27",
  "institution_id": null,
  "declaration": true,
  "label": "SIS sync 28 Oct",
  "rows": [
    { "apaar_id": "123456784417", "name": "Ravi Kumar Sharma", "dob": "2007-03-21", "programme_code": "CSE",
      "year_of_study": 1, "admission_route": "COUNSELLING", "counselling_ref": "MHCET-2026-R1-004512",
      "category": "GENERAL", "consent_status": "LINKED", "admission_date": "2026-08-02" },
    { "apaar_id": "987654320011", "name": "Asha Patil", "dob": "2007-11-02", "programme_code": "IT",
      "year_of_study": 1, "admission_route": "MANAGEMENT", "category": "OBC",
      "status": "WITHDRAWN", "status_date": "2026-10-20" }
  ]
}
202 { "batch": { ...UploadBatch, "source": "API", "filename": "SIS sync 28 Oct", "status": "QUEUED"... } }
```

`label` (optional, up to 120 characters) becomes the batch `filename`; default `rows.json`.

### A2.6 `GET /uploads`

Roles: `AICTE_ADMIN` (all), `RO_OFFICER` (institutions in its region), `INSTITUTION` (its own; `institution_id` ignored). `UNIVERSITY`, `STUDENT`: 403.

Query: `page`, `page_size`, `institution_id?`, `academic_year?`, `status?`. Sorted by `uploaded_at` descending.

```json
200 { "items": [ ...UploadBatch... ], "total": 3, "page": 1, "page_size": 25 }
```

### A2.7 `GET /uploads/{id}`

Same roles; a batch outside scope is 404 "Upload not found.". The web polls it every 2 s until `DONE` or `FAILED`.

```json
200 {
  "id": "b7c1d2e3-4444-4555-8666-777788889999",
  "institution_id": "a0b1c2d3-1111-4222-8333-444455556666",
  "institution_name": "ABC College of Engineering",
  "academic_year": "2026-27",
  "filename": "1-ABC-0001_2026-27.csv",
  "source": "FILE",
  "kind": "INITIAL",
  "status": "DONE",
  "stage": "DONE",
  "total_rows": 605,
  "stage_total": 0,
  "processed_rows": 0,
  "progress_pct": 100,
  "counts": {
    "rows": 605, "accepted": 605, "errors": 0, "warnings": 0,
    "created": 605, "updated": 0, "unchanged": 0, "withdrawn": 0, "transferred": 0,
    "seated": 593, "released": 0, "unseated": 12,
    "flags_raised": 3, "flags_updated": 0
  },
  "sources": [
    { "source": "APAAR", "calls": 571, "unavailable": 0 },
    { "source": "COUNSELLING", "calls": 402, "unavailable": 0 },
    { "source": "ABC", "calls": 381, "unavailable": 0 },
    { "source": "SII", "calls": 4, "unavailable": 0 }
  ],
  "timings_ms": { "PARSE": 40, "VALIDATE": 120, "FILE_DUPLICATES": 8, "UPSERT": 900, "LEDGER": 700, "CHECKS": 6100, "DUPLICATES": 300, "FLAGS": 60 },
  "error": null,
  "ignored_columns": [],
  "same_file_as": null,
  "uploaded_by": { "id": "6f1c0a8e-2b1d-4c9a-9e51-1c2f1a0b7d33", "name": "Registrar, ABC College of Engineering" },
  "uploaded_at": "2026-10-28T10:02:11Z",
  "started_at": "2026-10-28T10:02:12Z",
  "finished_at": "2026-10-28T10:02:21Z"
}
```

(The numbers are illustrative.) Fields:

- `status` and `stage` move together: QUEUED has `stage: null`; VALIDATING covers PARSE, VALIDATE, FILE_DUPLICATES; PROCESSING covers UPSERT, LEDGER, CHECKS, DUPLICATES, FLAGS; DONE has `stage: "DONE"`; FAILED keeps the stage that failed.
- `progress_pct` (0 to 100, never decreases) is computed by the api from `stage`, `processed_rows` and `stage_total` (ENGINES.md §4.6).
- `counts` always has every key; values are 0 until their stage finishes. `rows` data rows; `accepted` rows kept (warnings allowed); `errors` rows rejected; `warnings` accepted rows with at least one warning; `created`, `updated`, `unchanged` enrolments; `withdrawn`, `transferred` enrolments moved to that status by this batch; `seated` seats assigned by this batch (including earlier unseated enrolments that got a freed seat); `released` seats released; `unseated` enrolments of this batch that are ACTIVE and without a seat; `flags_raised` new flags; `flags_updated` existing flags whose evidence changed.
- `sources`: adapter calls per check source in this batch and how many found the source unavailable (the "APAAR awaiting source, will retry" line); empty until CHECKS starts.
- `same_file_as`: `{ "batch_id", "uploaded_at" }` of an earlier batch of this institution with the same file hash, else null (a re-upload is safe and changes nothing; the page can say so).
- `error`: null unless FAILED. Exact sentences: "The file could not be read as CSV or XLSX.", "The file is not UTF-8 text. Save it as CSV UTF-8 and upload it again.", "The file is missing required columns: {columns}.", "The column {column} appears more than once.", "The file has a header but no rows.", "The file has more than {max} rows. Split it and upload each part.", "Processing stopped while {stage_words}. Upload the file again; rows already saved are kept." with `{stage_words}`: PARSE reading the file, VALIDATE checking rows, FILE_DUPLICATES looking for repeated rows, UPSERT saving students and enrolments, LEDGER assigning seats, CHECKS checking with sources, DUPLICATES looking for duplicates, FLAGS raising flags.
- `uploaded_by`: `{id, name}`; for SEED batches the institution's registrar.

Proposed copy for the progress rail (UX owns the final words): `upload_status.PROCESSING` "Processing" (replaces `CHECKING`); `upload_stage.PARSE` "Reading file", `VALIDATE` "Checking rows", `FILE_DUPLICATES` "Repeated rows", `UPSERT` "Saving", `LEDGER` "Seat ledger", `CHECKS` "Checking sources", `DUPLICATES` "Duplicates", `FLAGS` "Flags", `DONE` "Done". The done card uses `upload.done_summary` with `{ok} = accepted`, `{seated}`, `{unseated}`, `{flags} = flags_raised`.

### A2.8 `GET /uploads/{id}/errors` and `GET /uploads/{id}/errors.csv`

Same roles and scoping as §A2.7.

`GET /uploads/{id}/errors?page&page_size&level?&code?`, sorted by `row_no` then `field`:

```json
200 {
  "items": [
    { "row_no": 17, "level": "WARNING", "field": "apaar_id", "code": "APAAR_FORMAT", "message": "APAAR must be 12 digits", "value_masked": "<11 characters>" },
    { "row_no": 41, "level": "ERROR", "field": "apaar_id", "code": "DUPLICATE_IN_FILE", "message": "Same APAAR appears on row 12", "value_masked": "XXXX XXXX 4417" },
    { "row_no": 58, "level": "ERROR", "field": "dob", "code": "DOB_FORMAT", "message": "Date of birth must be YYYY-MM-DD", "value_masked": "21/03/2007" }
  ],
  "total": 3, "page": 1, "page_size": 25
}
```

`total` counts entries (a row can have several). `GET /uploads/{id}/errors.csv` returns every entry, unpaged: `200 text/csv; charset=utf-8` with a BOM, `Content-Disposition: attachment; filename="<file stem>_errors.csv"`, header `row_no,level,field,code,message,value_masked`.

### A2.9 `GET /uploads/template.csv` and `GET /uploads/template.xlsx`

Roles: `AICTE_ADMIN`, `RO_OFFICER`, `INSTITUTION`. The header row only, the 19 columns in §A2.2 order; CSV as `text/csv` with `Content-Disposition: attachment; filename="countersign_upload_template.csv"`, XLSX with one sheet `students` and filename `countersign_upload_template.xlsx`. These two routes are declared before `/uploads/{id}` so they are never read as an id.

### A2.10 Enrolment list changes (`GET /institutions/{id}/enrolments`, A.9)

Rows keep the A.9 and Addendum 1 shape, with these changes:

- `countersign` is real and compact: `{ "score": {"passes", "applicable"} | null, "checks": [{"type", "status"}] }`. Once an enrolment is checked, `checks` has all five types in the order IDENTITY, ADMISSION, SEAT, STUDYING, STUDENT; before that `score` is null and `checks` is `[]`. Full check rows (source, time, detail) are only in `GET /enrolments/{id}`.
- `seat_code` is the held seat's code, or null when unseated.
- `flags` lists the unresolved flags (status OPEN, DOCS_REQUESTED or ESCALATED) that name this enrolment as `enrolment_id` or in `related_enrolment_ids`, as `{id, type, severity, status}`, most severe first. The 12 unseated ABC CSE rows each carry the EXCESS_ADMISSION flag.
- New fields: `cohort_year`, `admission_date`, `status_date`.
- New filters: `check_status` (`PASS`, `FAIL`, `PENDING`, `NA`): enrolments with at least one check in that status; with `check_type` (`IDENTITY` ... `STUDENT`) as well: that check in that status (`check_type` alone is ignored). `flagged` (`true` | `false`): has, or has no, unresolved flag as above. `seated` (`true` | `false`): holds a seat, or does not.

```json
{
  "id": "e1e1e1e1-5555-4666-8777-888899990000",
  "student": { "id": "st1...", "name": "Ravi Kumar Sharma", "apaar_masked": "XXXX XXXX 4417", "consent_status": "LINKED", "provisional_id": null, "nationality": "IN" },
  "programme_id": "p1...", "programme_code": "CSE",
  "academic_year": "2026-27", "cohort_year": "2026-27", "year_of_study": 1,
  "admission_route": "COUNSELLING", "counselling_ref": "MHCET-2026-R1-004512", "category": "GENERAL",
  "seat_code": "CSE-R-001", "status": "ACTIVE", "admission_date": "2026-08-02", "status_date": "2026-10-28",
  "uploaded_at": "2026-10-28T10:02:14Z", "upload_batch_id": "b7c1...", "source_row_no": 2,
  "countersign": {
    "score": { "passes": 3, "applicable": 4 },
    "checks": [
      { "type": "IDENTITY", "status": "PASS" }, { "type": "ADMISSION", "status": "PASS" },
      { "type": "SEAT", "status": "PASS" }, { "type": "STUDYING", "status": "NA" },
      { "type": "STUDENT", "status": "PENDING" }
    ]
  },
  "flags": [ { "id": "f2...", "type": "DUPLICATE_WITHIN_UPLOAD", "severity": "MEDIUM", "status": "OPEN" } ]
}
```

### A2.11 `GET /enrolments/{id}`

Roles: `AICTE_ADMIN` (any), `RO_OFFICER` (institutions in its region), `INSTITUTION` (its own), `UNIVERSITY` (its affiliates, read-only). `STUDENT`: 403 (students use `/students/me`). Outside scope: 404 "Enrolment not found.". Writes a READ audit entry for the student.

```json
200 {
  "id": "e1e1e1e1-5555-4666-8777-888899990000",
  "institution": { "id": "a0b1c2d3-1111-4222-8333-444455556666", "name": "ABC College of Engineering", "aicte_permanent_id": "1-ABC-0001", "state_code": "MH", "state_name": "Maharashtra", "region": "WEST" },
  "student": {
    "id": "st1...", "name": "Ravi Kumar Sharma", "apaar_masked": "XXXX XXXX 4417", "consent_status": "LINKED",
    "provisional_id": null, "nationality": "IN", "dob": "2007-03-21", "gender": "M", "mobile_masked": "XXXXXX4521"
  },
  "programme": { "id": "p1...", "code": "CSE", "name": "B.Tech Computer Science and Engineering", "level": "UG", "mode": "PHYSICAL", "duration_years": 4 },
  "academic_year": "2026-27", "cohort_year": "2026-27", "year_of_study": 1,
  "admission_route": "COUNSELLING", "counselling_ref": "MHCET-2026-R1-004512", "category": "GENERAL",
  "status": "ACTIVE", "status_date": "2026-10-28", "admission_date": "2026-08-02",
  "uploaded_at": "2026-10-28T10:02:14Z",
  "upload": { "batch_id": "b7c1...", "filename": "1-ABC-0001_2026-27.csv", "row_no": 2 },
  "seat": { "id": "s1...", "seat_code": "CSE-R-001", "seat_type": "REGULAR", "academic_year": "2026-27", "assigned_at": "2026-10-28T10:02:15Z" },
  "countersign": { "score": { "passes": 3, "applicable": 4 }, "checks": [ { "type": "IDENTITY", "status": "PASS" }, "... five, in order ..." ] },
  "checks": [
    { "type": "IDENTITY", "status": "PASS", "source": "APAAR", "checked_at": "2026-10-28T10:02:18Z", "attempts": 0,
      "detail": { "summary": "Name and date of birth match the APAAR registry (similarity 100 of 100).", "name_score": 100, "dob_match": true, "apaar_last4": "4417" } },
    { "type": "ADMISSION", "status": "PASS", "source": "COUNSELLING", "checked_at": "2026-10-28T10:02:18Z", "attempts": 0,
      "detail": { "summary": "Found in the Maharashtra counselling allotments for CSE (2026), round 1.", "round": 1, "allotment_ref": "MHCET-2026-R1-004512", "ref_mismatch": false } },
    { "type": "SEAT", "status": "PASS", "source": "SEAT_LEDGER", "checked_at": "2026-10-28T10:02:18Z", "attempts": 0,
      "detail": { "summary": "Holds seat CSE-R-001 (Regular, 2026-27 approval).", "seat_code": "CSE-R-001", "seat_type": "REGULAR" } },
    { "type": "STUDYING", "status": "NA", "source": "ABC", "checked_at": "2026-10-28T10:02:18Z", "attempts": 0,
      "detail": { "summary": "First year, no result yet." } },
    { "type": "STUDENT", "status": "PENDING", "source": "STUDENT_NOTICE", "checked_at": "2026-10-28T10:02:18Z", "attempts": 0,
      "detail": { "summary": "Notice not sent yet." } }
  ],
  "flags": [
    { "id": "f2...", "type": "DUPLICATE_WITHIN_UPLOAD", "severity": "MEDIUM", "status": "OPEN",
      "summary": "Rows 2 and 133 of 1-ABC-0001_2026-27.csv describe the same student.", "created_at": "2026-10-28T10:02:20Z" }
  ]
}
```

- `upload` is null for an enrolment with no batch; `seat` is null when unseated.
- `checks` is `[]` before the first check, else all five in order. `attempts` counts evaluations that met an unavailable source.
- `flags` lists every flag (any status) naming the enrolment as `enrolment_id` or in `related_enrolment_ids`, most severe first, as `FlagSummary` (§A2.15). For an `INSTITUTION`, `summary` follows the redaction in §A2.16.

### A2.12 `POST /enrolments/{id}/recheck`

Roles: `AICTE_ADMIN`, `RO_OFFICER` (region), `INSTITUTION` (own). `UNIVERSITY`, `STUDENT`: 403. Body `{}`. Rate limit 30 per minute per user (429 `RATE_LIMITED`). Re-runs this enrolment's PENDING checks except STUDENT (D18), synchronously, and raises any flags the new results call for.

```json
200 {
  "enrolment_id": "e1e1e1e1-5555-4666-8777-888899990000",
  "rechecked": 1,
  "results": [ { "type": "IDENTITY", "before": "PENDING", "after": "PASS" } ],
  "flags_raised": 0,
  "countersign": { "score": { "passes": 3, "applicable": 4 }, "checks": [ "... five ..." ] }
}
```

Nothing PENDING: `rechecked: 0`, `results: []`. A source still down leaves the check PENDING (`after: "PENDING"`), never FAIL.

### A2.13 `POST /institutions/{id}/recheck`

Roles: `AICTE_ADMIN`, `RO_OFFICER` (institutions in its region). `INSTITUTION`, `UNIVERSITY`, `STUDENT`: 403. Body `{ "academic_year": "2026-27" }` (optional key; default the current year). Rate limit 6 per minute per user. Re-runs, synchronously with `CHECKS_CONCURRENCY` adapter calls in flight, every PENDING check except STUDENT of the institution's ACTIVE enrolments in that year. This is the "recheck after the source is back" button on the chaos demo.

```json
200 {
  "institution_id": "a0b1c2d3-1111-4222-8333-444455556666",
  "academic_year": "2026-27",
  "enrolments": 214,
  "rechecked": 214,
  "now_pass": 214, "now_fail": 0, "now_na": 0, "still_pending": 0,
  "flags_raised": 0,
  "duration_ms": 1830
}
```

### A2.14 Check rows and their detail sentences

Wire shape of a full check (only in `GET /enrolments/{id}`):

```json
{ "type": "IDENTITY", "status": "PENDING", "source": "APAAR", "checked_at": "2026-10-28T10:02:18Z", "attempts": 2,
  "detail": { "summary": "APAAR registry did not respond. This check stays pending until a recheck or the next upload.", "source_unavailable": true, "source_error": "HTTP 503" } }
```

`detail.summary` is always present and is shown verbatim. Optional keys the web may use: `source_unavailable` (bool), `needs_review` (bool), `name_score` (int), `dob_match` (bool), `apaar_last4`, `round`, `allotment_ref`, `ref_mismatch` (bool), `seat_code`, `seat_type`, `flag_type`, `expected`, `missing`, `semesters` (`[{academic_year, sem, credits}]`), `awaiting_semester`. Never a full APAAR, passport or mobile.

Placeholder words: `{source_name}` from copy deck `source.*` (APAAR registry, Counselling list, ABC credits, Study in India); `{route_word}` from `route.*`; `{seat_type_word}` from `seat_type.*`; `{flag_name}` from `flag.<TYPE>.name`; `{cohort_start}` the start year of the cohort (`2026`).

| check | status | when | `detail.summary` |
|---|---|---|---|
| any | PENDING | the source did not answer | `{source_name} did not respond. This check stays pending until a recheck or the next upload.` |
| IDENTITY | NA | no APAAR (consent Refused or Pending) | `APAAR not linked; admission is not blocked.` |
| IDENTITY | NA | international student | `International student; identity is checked through the passport, not APAAR.` |
| IDENTITY | FAIL | malformed APAAR on upload | `APAAR as uploaded {problem}; the enrolment was kept without it.` (`{problem}`: "has 11 digits, expected 12" or "contains characters other than digits") |
| IDENTITY | FAIL | registry: no such id | `APAAR ending {apaar_last4} is not in the APAAR registry.` |
| IDENTITY | FAIL | date of birth differs | `Date of birth on upload does not match the APAAR registry.` |
| IDENTITY | FAIL | similarity below 75 | `Name on upload differs from the APAAR registry (similarity {name_score} of 100).` |
| IDENTITY | PENDING | similarity 75 to 89 (`needs_review`) | `Name on upload is close to the APAAR registry but not a clear match (similarity {name_score} of 100); an officer should review.` |
| IDENTITY | PASS | similarity 90 or more | `Name and date of birth match the APAAR registry (similarity {name_score} of 100).` |
| ADMISSION | PASS | in the counselling list | `Found in the {state_name} counselling allotments for {programme_code} ({cohort_start}), round {round}.` |
| ADMISSION | PASS | found, reference differs | `Found in the {state_name} counselling allotments for {programme_code} ({cohort_start}), round {round}, as {allotment_ref}; the upload says {counselling_ref}.` |
| ADMISSION | FAIL | not in the counselling list | `Not found in the {state_name} counselling allotments for {programme_code} ({cohort_start}).` |
| ADMISSION | PASS | management, spot or NRI with a seat in the route's pool | `{route_word} admission is allowed for {programme_code} and holds a {seat_type_word} seat.` |
| ADMISSION | FAIL | the approval has no seats of the route's type | `{route_word} admission is not allowed for {programme_code}: the {cohort_year} approval has no {seat_type_word} seats.` |
| ADMISSION | FAIL | no seat of the route's type | `{route_word} admission has no {seat_type_word} seat in {programme_code} ({cohort_year}).` |
| ADMISSION | PASS | Study in India confirms | `Study in India confirms this admission to {programme_code} ({cohort_year}).` |
| ADMISSION | FAIL | Study in India does not | `Study in India has no matching admission for this passport at this institution.` |
| SEAT | PASS | holds a seat of its cohort approval | `Holds seat {seat_code} ({seat_type_word}, {cohort_year} approval).` |
| SEAT | FAIL | no seat | `No {seat_type_word} seat is free in {programme_code} ({cohort_year}); see the {flag_name} flag.` |
| STUDYING | NA | first year | `First year, no result yet.` |
| STUDYING | NA | lateral entrant in year 2 (route `LATERAL`; a lateral's completed years start at year 2) | `Joined in year 2 as a lateral entrant; no completed year to check yet.` |
| STUDYING | NA | no APAAR | `APAAR not linked; ABC credits cannot be checked.` |
| STUDYING | NA | ABC does not know the APAAR | `ABC has no record of this APAAR; see the Identity check.` |
| STUDYING | PASS | credits in every expected semester | `Credits recorded in ABC for all {expected} semesters since admission.` |
| STUDYING | PENDING | one semester missing | `No credits recorded in ABC for semester {sem} ({academic_year}); waiting for the next upload.` |
| STUDYING | FAIL | two or more missing | `No credits recorded in ABC for {missing} of {expected} semesters since admission.` |
| STUDENT | PENDING | Week 2, always | `Notice not sent yet.` |

Status words on the web: PASS, FAIL and NA as in the copy deck (`check.status.*`). PENDING depends on the detail; proposed copy keys (UX owns the words): `check.pending.unavailable` "Awaiting source" when `source_unavailable`, `check.pending.review` "Needs review" when `needs_review`, `check.pending.student` "Not sent yet" for STUDENT, `check.pending.results` "Awaiting results" for STUDYING with `awaiting_semester`.

### A2.15 `GET /flags` (read-only in Week 2)

Roles: `AICTE_ADMIN` (all), `RO_OFFICER` (flags whose institution is in its region), `INSTITUTION` (flags against its own institution, redacted as in §A2.16). `UNIVERSITY`, `STUDENT`: 403.

Query: `page`, `page_size`, `type?`, `severity?`, `status?` (no default: all statuses; the case queue sends `status=OPEN`), `institution_id?`, `programme_id?`, `state?` (state code), `academic_year?`, `q?` (case-insensitive substring of the summary, the institution name or its `aicte_permanent_id`), `sort?` = `severity_desc` (default: HIGH, MEDIUM, LOW, then oldest first) | `created_desc` (newest first).

```json
200 {
  "items": [
    {
      "id": "f1f1f1f1-7777-4888-8999-000011112222",
      "type": "EXCESS_ADMISSION",
      "severity": "HIGH",
      "status": "OPEN",
      "institution": { "id": "a0b1c2d3-1111-4222-8333-444455556666", "name": "ABC College of Engineering", "aicte_permanent_id": "1-ABC-0001", "state_code": "MH", "state_name": "Maharashtra", "region": "WEST" },
      "programme": { "id": "p1...", "code": "CSE", "name": "B.Tech Computer Science and Engineering" },
      "enrolment_id": null,
      "academic_year": "2026-27",
      "summary": "132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat.",
      "related_count": 12,
      "assignee": null,
      "created_at": "2026-10-28T10:02:20Z",
      "updated_at": "2026-10-28T10:02:20Z"
    }
  ],
  "total": 37, "page": 1, "page_size": 25,
  "institutions": 9
}
```

`institutions` is the number of distinct institutions across the whole filtered set (the "37 open flags in 9 institutions" line). `assignee` is `{id, name} | null`, always null in Week 2. `related_count` counts the related enrolments the caller may see.

`FlagSummary`, used in enrolment detail: `{id, type, severity, status, summary, created_at}`.

### A2.16 `GET /flags/{id}`

Same roles and scoping; outside scope 404 "Flag not found.". Writes READ audit entries for the students in `enrolment` and `related_enrolments`.

```json
200 {
  "id": "f1f1f1f1-7777-4888-8999-000011112222",
  "type": "EXCESS_ADMISSION", "severity": "HIGH", "status": "OPEN",
  "institution": { "id": "a0b1...", "name": "ABC College of Engineering", "aicte_permanent_id": "1-ABC-0001", "state_code": "MH", "state_name": "Maharashtra", "region": "WEST" },
  "programme": { "id": "p1...", "code": "CSE", "name": "B.Tech Computer Science and Engineering" },
  "enrolment_id": null,
  "academic_year": "2026-27",
  "summary": "132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat.",
  "evidence": {
    "summary": "132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat.",
    "facts": [
      { "label": "Approved intake", "value": "120", "source": "AICTE approval 2026-27" },
      { "label": "Admitted (active)", "value": "132", "source": "College uploads, Regular and NRI routes" },
      { "label": "Seated", "value": "120", "source": "Seat ledger" },
      { "label": "Unseated", "value": "12", "source": "Seat ledger" }
    ],
    "related_enrolment_ids": [ "e9...", "e10..." ],
    "rule_source": "AICTE approved intake; minus NRI carve-out (APH 2024-27 cl. 2.8(b))"
  },
  "enrolment": null,
  "related_enrolments": [ { ...EnrolmentRow (§A2.10)..., "institution": { "id": "a0b1...", "name": "ABC College of Engineering" } } ],
  "related_hidden": 0,
  "related_count": 12,
  "assignee": null,
  "history": [],
  "created_at": "2026-10-28T10:02:20Z",
  "updated_at": "2026-10-28T10:02:20Z"
}
```

- `enrolment`: the flag's own enrolment as an EnrolmentRow plus `institution`, or null for programme-level flags (EXCESS_ADMISSION, QUOTA_BREACH).
- `related_enrolments`: every enrolment in `evidence.related_enrolment_ids` the caller may see, as EnrolmentRow plus `institution {id, name}`, in the order of the ids. Officers (AICTE_ADMIN, RO_OFFICER) see both sides of a cross-institution flag, whatever the other side's region.
- **Redaction for `INSTITUTION`**: `summary` and `evidence.summary` are `evidence.summary_for_institution` when the engine stored one; facts with `audience: "OFFICER"` are dropped and facts with `audience: "INSTITUTION"` kept (officers get the reverse; facts without `audience` go to everyone); enrolments of other institutions are removed from `related_enrolments` and `evidence.related_enrolment_ids` and counted in `related_hidden`. The wire never carries `audience`, `summary_for_institution` or `data`.
- `history` is always `[]` in Week 2; Week 3 fills it from `case_actions`. The page shows "Flag opened" from `created_at`.

### A2.17 Evidence templates per flag type

Stored by the engines in `flags.evidence`, shown verbatim. `summary` is one sentence and never holds a student name or a full id; facts may hold the name as uploaded (only authorised, audited readers see them). Names in the first column follow copy deck `flag.<TYPE>.name`. `{cohort_year}` is the approval year (`2026-27`); for flags that are not about seats `{academic_year}` is the roll year.

| type | severity | `summary` | `facts` (label: value, source) | `rule_source` |
|---|---|---|---|---|
| EXCESS_ADMISSION | HIGH | `{admitted} admitted against {approved} approved seats in {programme_code} ({cohort_year}); {unseated} without a seat.` | Approved intake: `{approved}`, AICTE approval {cohort_year}. Admitted (active): `{admitted}`, College uploads, Regular and NRI routes. Seated: `{seated}`, Seat ledger. Unseated: `{unseated}`, Seat ledger. When `peak_unseated` is higher than `unseated`, also Most unseated at once: `{peak_unseated}`, Seat ledger | the REGULAR pool's `rule_source` |
| QUOTA_BREACH | MEDIUM; HIGH for INTERNATIONAL or NRI more than 2 over | `{admitted} {seat_type_word} admissions against {capacity} {seat_type_word} seats in {programme_code} ({cohort_year}).` | Pool: `{seat_type_word}`, Seat ledger. Capacity: `{capacity}`, AICTE approval rules. Admitted via route: `{admitted} ({route_words})`, College uploads. Unseated: `{unseated}`, Seat ledger. Rule percentage: `{share}% of approved intake {approved}`, AICTE approval rules | that pool's `rule_source` |
| LATE_REFILL | MEDIUM | `Seat {seat_code} assigned on {assigned_date}, after the last admission date {cutoff_date}.` | Seat: `{seat_code}`, Seat ledger. Released on: `{released_date}`, Seat ledger. Assigned on: `{assigned_date}`, College upload {filename}, row {row_no}. Last admission date: `{cutoff_date}`, AICTE admission schedule | `Last admission date for {cohort_year} (AICTE admission schedule)` |
| INVALID_APAAR (not in registry) | HIGH | `APAAR ending {apaar_last4} is not in the APAAR registry.` | APAAR (masked): `XXXX XXXX {apaar_last4}`, College upload. Registry reply: `Not found`, APAAR registry. Checked at: `{checked_date}`, APAAR registry | `APAAR verification` |
| INVALID_APAAR (malformed) | MEDIUM | `APAAR as uploaded {problem}, so it could not be checked.` | APAAR (masked): `<{n} characters>`, College upload. Registry reply: `Not checked`, APAAR registry. Checked at: `{checked_date}`, Countersign | `APAAR verification` |
| NAME_MISMATCH (name) | MEDIUM below 75; LOW from 75 to 89 | `Name on upload differs from the APAAR registry (similarity {name_score} of 100).` | Name on upload: `{name}`, College upload. Similarity: `{name_score} of 100`, APAAR registry. Date of birth match: `Yes`, APAAR registry. Checked at: `{checked_date}`, APAAR registry | `APAAR verification` |
| NAME_MISMATCH (date of birth) | MEDIUM | `Date of birth on upload differs from the APAAR registry.` | Name on upload: `{name}`, College upload. Similarity: `{name_score} of 100`, APAAR registry. Date of birth match: `No`, APAAR registry. Checked at: `{checked_date}`, APAAR registry | `APAAR verification` |
| DUPLICATE_WITHIN_UPLOAD (one file) | MEDIUM | `Rows {row_a} and {row_b} of {filename} describe the same student.` | Match on: `{match_words}`, Duplicate detection. Row A: `{filename_a}, row {row_a}`, College upload. Row B: `{filename_b}, row {row_b}`, College upload. Names as uploaded: `{name_a} / {name_b}`, College upload | `Upload validation` |
| DUPLICATE_WITHIN_UPLOAD (two files) | MEDIUM | `Row {row_b} of {filename_b} describes the same student as row {row_a} of {filename_a}.` | as above | `Upload validation` |
| DUPLICATE_CROSS_INSTITUTION | HIGH with a shared APAAR or passport; MEDIUM by name, date of birth and mobile | `The same student appears as active at {institution_a} and {institution_b} ({academic_year}).` For the institution: `The same student appears as active here and at another institution in {state_b} ({academic_year}).` | Match on: `{match_words}`, Duplicate detection. Institution A programme: `{institution_a}: {programme_a}`, College upload {uploaded_a}. Institution B programme: `{institution_b}: {programme_b}`, College upload {uploaded_b} (audience OFFICER), or `Another institution in {state_b}: {programme_b}` (audience INSTITUTION). Uploaded on: `{uploaded_a} and {uploaded_b}`, College uploads | `One active full-time enrolment per student` |
| DUAL_ENROLMENT_ALLOWED | LOW | `The student holds two enrolments; one is distance or online, which is permitted.` | Enrolment A mode: `{institution_a}: {programme_a}, {mode_a_word}`, College upload. Enrolment B mode: `{institution_b}: {programme_b}, {mode_b_word}`, College upload (audience OFFICER), or `Another institution in {state_b}: {programme_b}, {mode_b_word}` (audience INSTITUTION). UGC notification: `Pursuing two academic programmes simultaneously, 2022`, UGC | `UGC dual-degree guidelines 2022` |
| NO_ACADEMIC_ACTIVITY | MEDIUM | `No credits recorded in ABC for {missing} semesters while enrolled in year {year_of_study}.` | Semesters checked: `{expected} ({first_academic_year} to {last_academic_year})`, ABC. Credits found: `Sem 1: 0, Sem 2: 0`, ABC. Last ABC entry: `{last_entry_date}` or `None`, ABC | `ABC credit record` |

Words: `{match_words}` is `Same APAAR`, `Same passport`, or `Name ({name_score} of 100), date of birth and mobile` (whichever matched, joined with "and"); `{mode_word}` is `physical`, `open and distance learning` or `online`; `{route_words}` lists the routes mapped to the pool (`NRI`; `TFW`; `Lateral`; `International`); A is always the flag's own institution and B the other one.

Two changes from copy deck §5, to be mirrored there: QUOTA_BREACH counts `{admitted}` (enrolments by route), because assigned seats can never exceed capacity; LATE_REFILL cites the `rules.yaml` cutoff date instead of APH cl. 6.13(f), which is the lateral-entry vacancy clause.

### A2.18 Seats against admissions: one comparable pair everywhere

Week 1 pages set one year's approved seats against enrolments from every year of study, so ABC College read as 605 enrolled against 540 seats. From Week 2 every place that shows seats also shows `admitted`:

- `admitted` = ACTIVE enrolments whose `cohort_year` equals the academic year asked for (default the current year), counted in the current roll (`enrolments.academic_year` = the current academic year). That is the first-year intake of that year; lateral entrants count in the cohort they join, as `app/core/cohort.py` assigns it (a year-2 lateral in 2026-27 belongs to 2025-26). It is the same rule A.7 already uses for each programme's `enrolments`, so an institution's `admitted` equals the sum of its `programmes[].enrolments` for that year.
- `approved_seats` stays the approved intake of that year.
- `enrolments` stays "students on roll, all years of study": every ACTIVE enrolment in the academic year.
- Any fill or over-admission figure the web shows is `admitted / approved_seats`, never `enrolments / approved_seats`.
- `seated` (ASSIGNED seats) becomes real once the Seat Ledger runs (Week 2); in Week 1 data it is 0 everywhere and `unseated` equals the admitted count.

### A2.19 `GET /dashboard/summary` changes (A.5, D21)

```json
200 {
  "academic_year": "2026-27",
  "scope": { "kind": "NATIONAL", "label": "All India" },
  "kpis": {
    "institutions": 50,
    "programmes": 187,
    "approved_seats": 18960,
    "admitted": 4120,
    "enrolments": 10342,
    "flags_open": 214,
    "countersigned_pct": 0.0,
    "clear_pct": 91.4
  },
  "flags_by_type": [
    { "type": "EXCESS_ADMISSION", "open": 5 }, { "type": "QUOTA_BREACH", "open": 5 }, { "type": "LATE_REFILL", "open": 2 },
    { "type": "INVALID_APAAR", "open": 15 }, { "type": "NAME_MISMATCH", "open": 13 },
    { "type": "DUPLICATE_CROSS_INSTITUTION", "open": 20 }, { "type": "DUPLICATE_WITHIN_UPLOAD", "open": 12 },
    { "type": "DUAL_ENROLMENT_ALLOWED", "open": 6 }, { "type": "NO_ACADEMIC_ACTIVITY", "open": 12 },
    { "type": "STUDENT_DENIED", "open": 0 }, { "type": "GHOST_RING", "open": 0 }, { "type": "ANOMALY", "open": 0 }
  ],
  "by_state": [
    { "state_code": "MH", "state_name": "Maharashtra", "region": "WEST", "institutions": 9, "programmes": 41, "approved_seats": 3600, "admitted": 1210, "enrolments": 2011, "flags_open": 38 }
  ],
  "by_region": [
    { "region": "WEST", "region_name": "Western (Mumbai)", "institutions": 12, "approved_seats": 4500, "admitted": 1500, "enrolments": 2600, "flags_open": 51 }
  ]
}
```

(Numbers illustrative.)

- `flags_open` (KPI, per state, per region and per institution everywhere in the api) = flags with status OPEN, DOCS_REQUESTED or ESCALATED whose `academic_year` is the requested year, against institutions in scope.
- `countersigned_pct` = share of in-scope ACTIVE enrolments of the year whose applicable checks (status not NA) are all PASS; `clear_pct` = share with no FAIL. Both are percentages from 0 to 100 rounded to one decimal, over ACTIVE enrolments that have at least one check row, and null when there are none. With STUDENT PENDING for everyone in Week 2, `countersigned_pct` is 0.0; that is the true state (D21) and the tile says "0% of enrolments fully countersigned".
- `flags_by_type`: all twelve flag types in ARCHITECTURE §9 order, zeros included, counting `flags_open` by type. The UI may hide zero rows.
- `admitted`: §A2.18.

### A2.20 Institutions changes (A.6, A.7, Addendum 1)

`GET /institutions` rows:

- `admitted` added (§A2.18); `flags_open` real.
- `sort=flags_open_desc` is real: `flags_open` descending, then `enrolments` descending, then name. It becomes the default sort ("Ranked by open flags, then enrolments"); `enrolments_desc` and `name_asc` stay available.

`GET /institutions/{id}`:

- `admitted` added beside `approved_seats` and `enrolments` (§A2.18); `flags_open` real (the Flags tab count).
- each `programmes[]` item gains `mode` (`PHYSICAL`, `ODL`, `ONLINE`) and `seated` (ASSIGNED seats across the approval's pools, equal to the sum of `pools[].assigned`); `pools[].assigned`, `pools[].free` and `unseated` are real once the Seat Ledger has run.
- `last_upload` is real: `{ "batch_id", "uploaded_at", "rows", "errors", "status" }` for the institution's most recent batch of the year (`rows` = `counts.rows`, `errors` = `counts.errors`), or null.

```json
{
  "id": "p1...", "code": "CSE", "name": "B.Tech Computer Science and Engineering", "level": "UG", "discipline": "ENGINEERING",
  "shift": "FIRST", "mode": "PHYSICAL",
  "approval": { "academic_year": "2026-27", "approved_intake": 120, "cutoff_date": "2026-09-15" },
  "enrolments": 132, "seated": 120, "unseated": 12,
  "pools": [
    { "seat_type": "REGULAR", "capacity": 114, "is_supernumerary": false, "assigned": 114, "free": 0, "reserved_for": null, "rule_source": "AICTE approved intake; minus NRI carve-out (APH 2024-27 cl. 2.8(b))" },
    { "seat_type": "NRI", "capacity": 6, "is_supernumerary": false, "assigned": 6, "free": 0, "reserved_for": null, "rule_source": "APH 2024-27 cl. 2.8(b)" }
  ]
}
```

`GET /institutions/{id}/seats`: rows are real (holders, `assigned_at`). Unchanged shape.

### A2.21 `GET /students/me` change (A.10)

`enrolments[].countersign` is real, in the compact shape of §A2.10. Nothing else changes in Week 2.

### A2.22 Scoping for Week 2 endpoints

| Endpoint | AICTE_ADMIN | RO_OFFICER | INSTITUTION | STUDENT | UNIVERSITY |
|---|---|---|---|---|---|
| `POST /uploads`, `POST /uploads/rows` | any institution (`institution_id` required) | 403 | own only | 403 | 403 |
| `GET /uploads`, `GET /uploads/{id}`, `/errors`, `/errors.csv` | all | region, else 404 | own, else 404 | 403 | 403 |
| `GET /uploads/template.csv`, `.xlsx` | ok | ok | ok | 403 | 403 |
| `GET /enrolments/{id}` | any | region, else 404 | own, else 404 | 403 | affiliate, else 404 |
| `POST /enrolments/{id}/recheck` | any | region, else 404 | own, else 404 | 403 | 403 |
| `POST /institutions/{id}/recheck` | any | region, else 404 | 403 | 403 | 403 |
| `GET /flags`, `GET /flags/{id}` | all | region, else 404 | own, redacted (§A2.16), else 404 | 403 | 403 |
| `/dashboard/summary`, `/institutions*` | as section B | | | | |

### A2.23 TypeScript types (paste into `apps/web/lib/types.ts`)

Add the new types and replace the Week 1 declarations of `Countersign`, `Check`, `DashboardSummary`, `InstitutionRow`, `SeatPool`, `ProgrammeDetail`, `InstitutionDetail`, `SeatRow` and `EnrolmentRow` with the ones below (they also carry the Addendum 1 fields). `StudentMe` keeps its declaration and picks up the new `Countersign`.

```ts
// ---------- Week 2 enums ----------
export type ProgrammeMode = "PHYSICAL" | "ODL" | "ONLINE";
export type UploadStatus = "QUEUED" | "VALIDATING" | "PROCESSING" | "DONE" | "FAILED";
export type UploadStage =
  | "PARSE" | "VALIDATE" | "FILE_DUPLICATES" | "UPSERT" | "LEDGER" | "CHECKS" | "DUPLICATES" | "FLAGS" | "DONE";
export type UploadSource = "FILE" | "API" | "SEED";
export type UploadKind = "INITIAL" | "UPDATE";
export type RowErrorLevel = "ERROR" | "WARNING";
export type RowErrorCode =
  | "MISSING_REQUIRED" | "APAAR_FORMAT" | "DUPLICATE_IN_FILE" | "UNKNOWN_PROGRAMME" | "NO_APPROVAL_FOR_COHORT"
  | "DOB_FORMAT" | "DOB_IMPLAUSIBLE" | "BAD_ENUM" | "YEAR_OF_STUDY_INVALID" | "YEAR_MISMATCH" | "PASSPORT_REQUIRED"
  | "NATIONALITY_FORMAT" | "DATE_FORMAT" | "DATE_IN_FUTURE" | "MOBILE_FORMAT" | "EMAIL_FORMAT"
  | "CONSENT_CONFLICT" | "NOT_PREVIOUSLY_ENROLLED";
export type CheckSource = "APAAR" | "COUNSELLING" | "SEAT_LEDGER" | "ABC" | "SII" | "STUDENT_NOTICE";
export type FlagSort = "severity_desc" | "created_desc";
export type InstitutionSort = "flags_open_desc" | "enrolments_desc" | "name_asc";

export const UPLOAD_COLUMNS = [
  "apaar_id", "name", "dob", "gender", "mobile", "email", "address", "nationality", "passport_no",
  "programme_code", "academic_year", "year_of_study", "admission_route", "counselling_ref", "category",
  "consent_status", "status", "status_date", "admission_date",
] as const;
export type UploadColumn = (typeof UPLOAD_COLUMNS)[number];

// ---------- countersign ----------
export interface Score { passes: number; applicable: number }
export interface CheckBrief { type: CheckType; status: CheckStatus }
/** Replaces the Week 1 Countersign: list rows carry type and status only. */
export interface Countersign { score: Score | null; checks: CheckBrief[] }
export interface CheckDetail {
  summary: string;
  source_unavailable?: boolean; source_error?: string; needs_review?: boolean;
  name_score?: number; dob_match?: boolean; apaar_last4?: string;
  round?: number; allotment_ref?: string; ref_mismatch?: boolean;
  seat_code?: string; seat_type?: SeatType; flag_type?: FlagType;
  expected?: number; missing?: number; semesters?: { academic_year: string; sem: number; credits: number }[];
  awaiting_semester?: number;
  [key: string]: unknown;
}
/** Replaces the Week 1 Check. */
export interface Check { type: CheckType; status: CheckStatus; source: CheckSource; checked_at: string | null; attempts: number; detail: CheckDetail }

// ---------- uploads ----------
export interface UploadCounts {
  rows: number; accepted: number; errors: number; warnings: number;
  created: number; updated: number; unchanged: number; withdrawn: number; transferred: number;
  seated: number; released: number; unseated: number; flags_raised: number; flags_updated: number;
}
export interface UploadSourceStat { source: CheckSource; calls: number; unavailable: number }
export interface UploadBatch {
  id: string; institution_id: string; institution_name: string; academic_year: string; filename: string;
  source: UploadSource; kind: UploadKind; status: UploadStatus; stage: UploadStage | null;
  total_rows: number; stage_total: number; processed_rows: number; progress_pct: number;
  counts: UploadCounts; sources: UploadSourceStat[]; timings_ms: Partial<Record<UploadStage, number>>;
  error: string | null; ignored_columns: string[];
  same_file_as: { batch_id: string; uploaded_at: string } | null;
  uploaded_by: { id: string; name: string };
  uploaded_at: string; started_at: string | null; finished_at: string | null;
}
export interface UploadAccepted { batch: UploadBatch }
export interface UploadRowError {
  row_no: number; level: RowErrorLevel; field: UploadColumn | null; code: RowErrorCode; message: string; value_masked: string | null;
}
export type UploadRowInput = Partial<Record<UploadColumn, string | number | null>>;
export interface UploadRowsRequest {
  academic_year: string; institution_id?: string | null; declaration: true; label?: string; rows: UploadRowInput[];
}

// ---------- institutions and dashboard ----------
export interface DashboardSummary {
  academic_year: string;
  scope: { kind: "NATIONAL" | "REGION" | "INSTITUTION" | "UNIVERSITY"; label: string };
  kpis: {
    institutions: number; programmes: number; approved_seats: number; admitted: number; enrolments: number;
    flags_open: number; countersigned_pct: number | null; clear_pct: number | null;
  };
  flags_by_type: { type: FlagType; open: number }[];
  by_state: {
    state_code: string; state_name: string; region: Region; institutions: number; programmes: number;
    approved_seats: number; admitted: number; enrolments: number; flags_open: number;
  }[];
  by_region: {
    region: Region; region_name: string; institutions: number; approved_seats: number; admitted: number;
    enrolments: number; flags_open: number;
  }[];
}
export interface InstitutionRow {
  id: string; aicte_permanent_id: string; name: string; type: InstitutionType;
  state_code: string; state_name: string; region: Region; region_name: string;
  university_id: string | null; university_name: string | null;
  programmes: number; approved_seats: number; admitted: number; enrolments: number;
  flags_open: number; integrity_index: number | null;
}
export interface SeatPool {
  seat_type: SeatType; capacity: number; is_supernumerary: boolean; assigned: number; free: number;
  reserved_for: string | null; rule_source: string;
}
export interface ProgrammeDetail {
  id: string; code: string; name: string; level: Level; discipline: Discipline; shift: Shift; mode: ProgrammeMode;
  approval: { academic_year: string; approved_intake: number; cutoff_date: string | null };
  enrolments: number; seated: number; unseated: number; pools: SeatPool[];
}
export interface LastUpload { batch_id: string; uploaded_at: string; rows: number; errors: number; status: UploadStatus }
export interface InstitutionDetail extends Omit<InstitutionRow, "programmes"> {
  address_city: string | null; established_year: number | null;
  integrity_components: Record<string, number> | null;
  last_upload: LastUpload | null;
  programmes: ProgrammeDetail[];
}
export interface SeatRow {
  id: string; seat_code: string; programme_code: string; academic_year: string; seat_type: SeatType; status: SeatStatus;
  reserved_for: string | null; enrolment_id: string | null; student_name: string | null; assigned_at: string | null;
}

// ---------- enrolments ----------
export interface EnrolmentRow {
  id: string; student: StudentRef; programme_id: string; programme_code: string;
  academic_year: string; cohort_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category;
  seat_code: string | null; status: EnrolmentStatus; admission_date: string; status_date: string;
  uploaded_at: string; upload_batch_id: string | null; source_row_no: number | null;
  countersign: Countersign; flags: FlagRef[];
}
export interface EnrolmentListQuery {
  page?: number; page_size?: number; programme_id?: string; status?: EnrolmentStatus; academic_year?: string; q?: string;
  admission_route?: AdmissionRoute; year_of_study?: number; sort?: "name_asc" | "year_desc" | "route_asc";
  check_status?: CheckStatus; check_type?: CheckType; flagged?: boolean; seated?: boolean;
}
export interface InstitutionRef {
  id: string; name: string; aicte_permanent_id: string; state_code: string; state_name: string; region: Region;
}
export interface ProgrammeRef { id: string; code: string; name: string }
export interface FlagSummary extends FlagRef { summary: string; created_at: string }
export interface EnrolmentDetail {
  id: string;
  institution: InstitutionRef;
  student: StudentRef & { dob: string; gender: "M" | "F" | "O" | "U"; mobile_masked: string | null };
  programme: ProgrammeRef & { level: Level; mode: ProgrammeMode; duration_years: number };
  academic_year: string; cohort_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category;
  status: EnrolmentStatus; status_date: string; admission_date: string; uploaded_at: string;
  upload: { batch_id: string; filename: string; row_no: number | null } | null;
  seat: { id: string; seat_code: string; seat_type: SeatType; academic_year: string; assigned_at: string | null } | null;
  countersign: Countersign;
  checks: Check[];
  flags: FlagSummary[];
}
export interface EnrolmentRecheck {
  enrolment_id: string; rechecked: number;
  results: { type: CheckType; before: CheckStatus; after: CheckStatus }[];
  flags_raised: number; countersign: Countersign;
}
export interface InstitutionRecheck {
  institution_id: string; academic_year: string; enrolments: number; rechecked: number;
  now_pass: number; now_fail: number; now_na: number; still_pending: number; flags_raised: number; duration_ms: number;
}

// ---------- flags ----------
export interface EvidenceFact { label: string; value: string; source: string | null }
export interface Evidence { summary: string; facts: EvidenceFact[]; related_enrolment_ids: string[]; rule_source: string | null }
export interface FlagRow {
  id: string; type: FlagType; severity: Severity; status: FlagStatus;
  institution: InstitutionRef; programme: ProgrammeRef | null; enrolment_id: string | null; academic_year: string;
  summary: string; related_count: number; assignee: { id: string; name: string } | null;
  created_at: string; updated_at: string;
}
export interface FlagPage extends Page<FlagRow> { institutions: number }
export interface FlagListQuery {
  page?: number; page_size?: number; type?: FlagType; severity?: Severity; status?: FlagStatus;
  institution_id?: string; programme_id?: string; state?: string; academic_year?: string; q?: string; sort?: FlagSort;
}
export interface RelatedEnrolmentRow extends EnrolmentRow { institution: { id: string; name: string } }
export interface FlagDetail extends FlagRow {
  evidence: Evidence;
  enrolment: RelatedEnrolmentRow | null;
  related_enrolments: RelatedEnrolmentRow[];
  related_hidden: number;
  history: unknown[]; // always [] in Week 2
}
```

### A2.24 Section E update: datagen output for Week 2

Supersedes the matching lines of section E. Everything not mentioned stays as it is.

**Upload columns.** Every upload CSV and XLSX has the 19 columns of §A2.2, in that order: the 16 of section E, then `status`, `status_date`, `admission_date`.

- Initial files `uploads/<aicte_id>_<year>.csv` (+ `.xlsx`): `status` and `status_date` blank on every row (so re-uploading an initial file after an update never undoes a withdrawal); `admission_date` filled on every row with a date in the cohort's admission window: 1 July of the cohort start year up to that year's cutoff (`2026-09-15` for 2026-27, from `rules.yaml` `cutoff_dates`), or up to 30 September when `rules.yaml` has no cutoff for that year.
- Update files `uploads/<aicte_id>_<year>_update<n>.csv` (+ `.xlsx`), `n` from 1: small size 3 colleges (ABC College plus two others), full size 20. An update file holds only rows that change something; an existing student's row repeats every identity column of its initial row exactly so it resolves to the same student. Each update file has:
  - 2 to 4 withdrawals: `status = WITHDRAWN`, `status_date` between `2026-09-16` and `2026-10-20`;
  - 1 or 2 transfers: `status = TRANSFERRED`, same date range;
  - late refills in one programme whose first-year REGULAR pool is exactly full in the initial file (datagen tops the cohort up to the pool's capacity if needed): `k` first-years of REGULAR-pool routes are withdrawn in the same file and `k` new first-year students (MANAGEMENT or SPOT, with an APAAR and a registry entry) are added with `admission_date` between `2026-09-16` and `2026-10-20`, after the cutoff. Each refill takes a released seat and must raise LATE_REFILL.
  - Never: ABC College CSE first-years (the 132 against 120 demo stays exact), the demo student, any row tagged by another planted anomaly, or a programme with a planted EXCESS_ADMISSION or QUOTA_BREACH (its numbers must stay as planted).
- `make seed` loads every initial file first (sorted by name), then the update files (sorted by college, then `n`).

**Programmes.** `institutions.json` programmes keep `mode` (`PHYSICAL`, `ODL`, `ONLINE`); the seed imports it into `programmes.mode`.

**ground_truth.json.**

- `expected_flag` takes exactly these values: `EXCESS_ADMISSION`, `QUOTA_BREACH`, `LATE_REFILL`, `INVALID_APAAR`, `NAME_MISMATCH`, `DUPLICATE_WITHIN_UPLOAD`, `DUPLICATE_CROSS_INSTITUTION`, `DUAL_ENROLMENT_ALLOWED`, `NO_ACADEMIC_ACTIVITY` (raised in Week 2), `STUDENT_DENIED`, `GHOST_RING` (kept for Weeks 3 and 4), or `null` for a legitimate case that must not be flagged (`CONSENT_REFUSED_NO_APAAR`, and the new `WITHDRAWAL` and `TRANSFER` records).
- `severity_expected` follows ENGINES.md §10: EXCESS_ADMISSION HIGH; QUOTA_BREACH HIGH when an NRI or INTERNATIONAL pool is exceeded by more than 2, else MEDIUM; LATE_REFILL MEDIUM; INVALID_APAAR HIGH for kind `UNKNOWN` (well-formed, not in the registry) and MEDIUM for `SHORT`, `LONG`, `LETTERS` (malformed); NAME_MISMATCH MEDIUM (planted names score below 75); DUPLICATE_WITHIN_UPLOAD MEDIUM; DUPLICATE_CROSS_INSTITUTION HIGH (shared APAAR); DUAL_ENROLMENT_ALLOWED LOW; NO_ACADEMIC_ACTIVITY MEDIUM.
- New records: `LATE_REFILL` (rows = the refill rows; extra keys `seat_type`, `cutoff_date`, `released_rows`), `WITHDRAWAL` and `TRANSFER` (rows = the update rows; `expected_flag: null`).
- `rows[].row_no` becomes the spreadsheet row number (header row 1, first data row 2), the same numbering as the api's `enrolments.source_row_no` and `upload_row_errors.row_no`; `rows[].file` names the initial or the update file. `student_refs` for rows without an APAAR are `<file>#<row_no>` with that numbering.
- DUPLICATE_CROSS_INSTITUTION and DUAL_ENROLMENT_ALLOWED stay one record per pair; the api raises one flag per institution, and a ground-truth check accepts either.

**mockgov registries.** Refill students get `apaar_registry` entries; no counselling or ABC rows are needed for them (first-year MANAGEMENT or SPOT). Withdrawn and transferred students keep their registry rows.

**manifest.json** `counts` gains `update_files` and `update_rows`.

## Addendum 2 errata (2026-10-28): corrections from the UX review of the contract

These override anything above that disagrees.

1. **Pending sentence.** There is no scheduler. A PENDING check re-runs only on a recheck or the next upload of that row, so the sentence is "{source_name} did not respond. This check stays pending until a recheck or the next upload." (A2.14 updated in place.)
2. **Unresolved flags filter.** `GET /flags?status=` accepts a single status, a comma-separated list, or `UNRESOLVED`, which means OPEN, DOCS_REQUESTED and ESCALATED. `flags_open` everywhere counts exactly the UNRESOLVED set, so the Open flags tile and a list filtered by `status=UNRESOLVED` always agree.
3. **Admitted and approved intake.** `admitted` (A2.18, A2.20) counts every route into the cohort, including supernumerary TFW, international and lateral admissions, which the handbook places over and above approved intake. So `admitted` may exceed `approved_seats` without any excess. Excess is decided only by the Seat Ledger (EXCESS_ADMISSION counts Regular and NRI routes against approved intake; QUOTA_BREACH covers the supernumerary pools). The UI never shows an admitted/approved percentage; it shows the two numbers side by side and the flags. ABC CSE (132 admitted, 120 approved, all Regular or NRI) is unaffected.
4. **ADMISSION is never NA.** Every route has a rule: counselling list, seat-type rules or Study in India (A2.14, ENGINES section 8). ARCHITECTURE section 9 updated.
5. **Redaction covers universities.** Wherever a summary or fact names another institution, it is redacted for every role except AICTE_ADMIN and RO_OFFICER (so for INSTITUTION and UNIVERSITY alike), using the A2.16 wording ("another institution in {state}").
6. **No config file names in evidence.** Officer- and college-facing evidence never says "rules.yaml". Sources read "AICTE approval rules" (with the handbook clause from `rule_source`) or "AICTE admission schedule" for cut-off dates. The QUOTA_BREACH and LATE_REFILL rows in A2.16 are updated in place.

