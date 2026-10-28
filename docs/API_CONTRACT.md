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

## Addendum 3 (2026-10-28): Week 3 endpoints and shapes

Implements DECISIONS D23 to D33. Everything below is normative in the same way as sections A to E and Addendum 2: field names, casing, enum values and the quoted sentences are exact. The Python interfaces behind these endpoints are in `ENGINES.md` §16; the schema is `DATA_MODEL.md` "Migration 0003". Where this addendum and an earlier section disagree, this addendum wins.

### A3.1 Conventions added

- **Public routes.** These need no cookie (a cookie, if sent, is ignored) and are limited per client address with the usual `429 RATE_LIMITED` envelope and `details.retry_after`:

  | route | limit (D32) |
  |---|---|
  | `GET /notices/{token}`, `POST /notices/{token}/respond` | 30 per minute |
  | `GET /verify/{code}`, `POST /verify`, `GET /verify/d/{jws}`, `GET /verify/degree/{short_id}` | 60 per minute |
  | `GET /.well-known/jwks.json`, `GET /.well-known/jwt-vc-issuer`, `GET /status-lists/1` | 120 per minute |
  | `GET /privacy/notice` | 60 per minute |

- **Signed-in write limits.** `POST /credentials/{id}/present` 10 per minute per user; `POST /students/me/data-requests` 10 per minute per user; `POST /enrolments/{id}/notices/resend` 30 per minute per user.
- **A second multipart route.** `POST /flags/{id}/response` takes `multipart/form-data` and joins `POST /uploads` as the only mutating routes exempt from the JSON-only 415 rule. The web's `/api` rewrite already streams both.
- **Non-JSON responses.** `GET /flags/{id}/attachments/{attachment_id}` (the stored file), `GET /university/degrees/{enrolment_id}/insert.pdf` (`application/pdf`), `GET /students/me/export.json` (`application/json` with `Content-Disposition: attachment`), `GET /status-lists/1` (`application/statuslist+jwt`). `Content-Type` and `Content-Disposition` pass through the web unchanged (as A2.1).
- **Errors.** The new codes are in §A3.25. Where no specific code fits, the existing generic `409 CONFLICT` is used, always with `details.reason`.
- **Dates and times.** Dates inside sentences read `5 Oct 2026` (A2.1). The api never writes a clock time into a sentence; the web formats timestamps in IST ("Shared with a verifier at 10:42").
- **Masked ids on public surfaces.** The notice page, the verifier and the degree QR and insert show an APAAR as `XXXX XXXX 4417` and a provisional id as `PRV-XXXX` plus its last four characters (`PRV-7Q2MK4PX` shows as `PRV-XXXXK4PX`). Signed-in officer pages keep the provisional id in full, as before.
- **Notice words** (DATA_MODEL `notifications`): a notice is *answered* when it has a response; *live* when it is not answered, its delivery has not FAILED and it has not expired. An enrolment *needs a notice* when it has no live and no answered notice.
- **`{programme_short}`** in notice texts: the programme name's first word followed by the programme code when that first word contains a full stop (`B.Tech Computer Science and Engineering`, `CSE` gives `B.Tech CSE`); otherwise the programme name.
- **Origins.** `WEB_ORIGIN` (default `http://localhost:3000`) builds every link a person opens; `ISSUER_URL` (default `http://localhost:8000`) is the credential issuer and the base of the JWKS and status list URLs.
- **New enums** (also in §A3.27): `NoticeChannel` `EMAIL`, `DIGILOCKER`; `NoticeResponse` `YES`, `NO`; `NoticeDelivery` `QUEUED`, `SENT`, `FAILED`; `NoticeState` `QUEUED`, `AWAITING`, `ANSWERED`, `EXPIRED`, `FAILED`; `CaseAction` `CLEAR`, `REQUEST_DOCS`, `ESCALATE`, `CONFIRM`, `NOTE`, `ASSIGN`, `REOPEN`, `COLLEGE_RESPONSE`, `SYSTEM_NOTE`; `CredentialKind` `ENROLMENT`, `DEGREE`; `CredentialStatus` `ACTIVE`, `REVOKED`, `EXPIRED`; `VerifyResultCode` `VALID`, `REVOKED`, `EXPIRED`, `INVALID`; `VerifyMethod` `signature`, `register_lookup`; `RevokedReasonCode` `ENROLMENT_WITHDRAWN`, `ENROLMENT_TRANSFERRED`, `FLAG_CONFIRMED`, `ADMIN`; `StudentNoticeState` `NOT_SENT`, `UNREACHABLE`, `SENT`, `EXPIRED`, `CONFIRMED`, `DENIED`; `ConsentPurpose` `APAAR_LINK`, `NOTICE`, `CREDENTIAL_SHARE`; `ConsentState` `GIVEN`, `WITHDRAWN`, `REFUSED`; `ConsentChannel` `COLLEGE_UPLOAD`, `NOTICE_EMAIL`, `NOTICE_DIGILOCKER`, `PORTAL`; `DataRequestKind` `ACCESS`, `CORRECTION`, `ERASURE`; `DataRequestStatus` `OPEN`, `DONE`, `REJECTED`.

### A3.2 Student notices: who gets one and what is sent (D23)

- **When.** When a batch reaches DONE, the worker runs `countersign.send_notices(batch_id)` (ENGINES §16.3). `make seed` calls the same function for every batch after the uploads (D31).
- **Who.** Every ACTIVE enrolment whose `upload_batch_id` is the batch and that needs a notice, whatever its IDENTITY result. Skipped: a student whose latest NOTICE consent is WITHDRAWN, and a student with neither an email address nor a linked APAAR (the STUDENT check then stays PENDING as `UNREACHABLE`, §A3.8, so a college cannot avoid the check by leaving out contact details).
- **Channels.** `EMAIL` when `students.email` is set; `DIGILOCKER` when the student has a linked APAAR (consent LINKED). Each channel is its own `notifications` row with its own token.
- **Token and link.** `secrets.token_urlsafe(32)` (43 characters). Only `sha256(token)` in hex is stored (`token_hash`). The link is `{WEB_ORIGIN}/student/notices/{token}`. `expires_at` is the row's creation time plus `rules.yaml` `notices.expiry_days` (30).
- **Email.** From `NOTICE_FROM`, to the student's address, plain text. Subject [notice.email_subject]; body [notice.email_body] with `{link}` the link and `{expires_date}` the expiry date in IST. Header `X-Countersign-Notice: <notification id>`. Placeholders: `{institution_name}`, `{programme_name}`, `{programme_short}`, `{academic_year}`.
- **DigiLocker.** `adapters.digilocker.notify(apaar_id, message, callback_url)` with `message` = [notice.digilocker] and `callback_url` = the link (mockgov C.5).
- **Stored text.** `notifications.message` holds the filled text without the link, so the token is never stored.
- **Delivery.** Each row is tried at most three times; email rows go first, so a DigiLocker outage never delays email.

  | outcome | `delivery_status` | `last_error` |
  |---|---|---|
  | SMTP accepted the message | SENT (`sent_at` set) | null |
  | SMTP host not in `SMTP_ALLOWED_HOSTS` and `ALLOW_REAL_SMTP` not true | FAILED after 1 try | `Mail server not allowed.` |
  | SMTP refused the address | FAILED after 1 try | `Email address was refused.` |
  | SMTP did not answer or failed temporarily, 3 times | FAILED | `Mail server did not respond.` |
  | DigiLocker 202 `delivered: true` | SENT | null |
  | DigiLocker 404 `APAAR_NOT_LINKED` (the APAAR has no DigiLocker account) | FAILED after 1 try | `No DigiLocker account.` |
  | DigiLocker unavailable (timeout, 5xx), 3 times | FAILED | `DigiLocker did not respond.` |
  | DigiLocker any other 4xx | FAILED after 1 try | `DigiLocker refused the notice.` |

  mockgov answers an APAAR with no account with `404 {"error": {"code": "APAAR_NOT_LINKED", ...}}` and stores nothing (§A3.28 updates C.5). The api's MockGov DigiLocker adapter raises `AdapterRequestError` with status 404 for it, and the notices code turns exactly that into FAILED with `last_error` "No DigiLocker account."; `InMemoryDigiLocker` raises the same for an unknown APAAR. Any other `AdapterRequestError` is FAILED at once with "DigiLocker refused the notice."; `SourceUnavailable` is the transient row above.
- After delivery the STUDENT check of each enrolment touched is refreshed (§A3.8).

### A3.3 `GET /notices/{token}` (public)

Opens the notice page `/student/notices/[token]`. The token is the only authority: no sign-in, and the page never shows a name, a date of birth, contact details or a full id.

```json
200 {
  "channel": "EMAIL",
  "institution_name": "ABC College of Engineering",
  "programme_code": "CSE",
  "programme_name": "B.Tech Computer Science and Engineering",
  "academic_year": "2026-27",
  "year_of_study": 1,
  "id_kind": "APAAR",
  "id_masked": "XXXX XXXX 4417",
  "uploaded_at": "2026-10-28T10:02:14Z",
  "sent_at": "2026-10-28T10:05:40Z",
  "expires_at": "2026-11-27T10:05:31Z",
  "response": null,
  "responded_at": null,
  "previous_response": null,
  "changed_at": null,
  "can_change_until": null,
  "consent_text": "By replying, you let AICTE record your answer with today's date against this enrolment. Your answer is shown to AICTE officers and to ABC College of Engineering as \"Confirmed\" or \"Denied\", with no other personal detail.",
  "notice_version": "v1"
}
```

- `id_kind` is `APAAR` or `PROVISIONAL`; `id_masked` follows §A3.1. `uploaded_at` is the enrolment's `uploaded_at`.
- `can_change_until` is `responded_at` plus 7 days while the answer has not been changed and that moment is still ahead; otherwise null.
- `consent_text` is [consent.notice] with `{institution_name}` filled, the text a Yes records (D30).
- The first successful view sets `opened_at`. Every successful view writes a READ audit entry: `entity_type` `notification`, `entity_id` the notice, no actor, `after: {"via": "notice-link"}`.
- An answered notice stays readable after `expires_at` (200), so the student can see what they said.

Errors: `404 NOTICE_NOT_FOUND` "This link is not valid." for a malformed or unknown token (identical bodies); `410 NOTICE_EXPIRED` "This link has expired. Ask your college to resend the notice." for an unanswered notice past `expires_at`; `429 RATE_LIMITED`. Page states: `response` null is the question; YES or NO is the answered view (with "Change my answer" while `can_change_until` is set); 410 is [notice.expired]; 404 is [notice.invalid].

### A3.4 `POST /notices/{token}/respond` (public)

```json
{ "response": "NO", "comment": "I did not join this college." }
```

`response` is `YES` or `NO`. `comment` is optional, at most 500 characters, and is kept only with `NO` (ignored with `YES`).

Rules, in order:

1. Unknown or malformed token: `404 NOTICE_NOT_FOUND`.
2. Not answered and past `expires_at`: `410 NOTICE_EXPIRED`.
3. Not answered: the first reply. `response`, `responded_at` and `comment` are stored.
4. Answered with the same response: nothing changes (the comment is not replaced); 200.
5. Answered with the other response: allowed once, within 7 days of `responded_at` (`rules.yaml` `notices.change_window_days`), even if the notice has since expired. `previous_response` keeps the first answer, `response` takes the new one and `changed_at` is set; a change to `NO` stores its comment, a change to `YES` keeps the earlier comment. Otherwise `409 NOTICE_ALREADY_CHANGED` with `details.reason` `CHANGED_ONCE` ("You have already changed your answer once.") or `WINDOW_CLOSED` ("Answers can be changed only within 7 days of the first reply.").

Effects of a first reply or a change, in one transaction (ENGINES §16.3):

- The notice row is updated; audit UPDATE on `notification` with no actor and `after: {"response", "previous_response", "via": "notice-link"}` (the comment never goes into the audit log).
- A `YES` records a `consents` row: purpose NOTICE, status GIVEN, `notice_text` = `consent_text` above, `notice_version`, channel `NOTICE_EMAIL` or `NOTICE_DIGILOCKER`, the enrolment.
- The STUDENT check is refreshed and STUDENT_DENIED raised or refreshed (§A3.8); a change from No to Yes adds a system note to that flag's history.
- When the enrolment is now eligible, its Enrolment proof is issued (§A3.15).

Response `200`: the §A3.3 body after the change. Errors: as above plus `422 VALIDATION_ERROR` and `429 RATE_LIMITED`.

### A3.5 `POST /enrolments/{id}/notices/resend`

Roles: `AICTE_ADMIN` (any), `RO_OFFICER` (institutions in its region), `INSTITUTION` (its own). `UNIVERSITY`, `STUDENT`: 403. Outside scope: 404 "Enrolment not found.". Body `{}`.

Checked in this order:

| condition | answer |
|---|---|
| the enrolment is not ACTIVE | `409 CONFLICT`, `details.reason` `NOT_ACTIVE`, "Notices go only to active enrolments." |
| a notice is answered | `409 NOTICE_LIVE`, `details.reason` `ANSWERED`, "The student has already replied." |
| a notice is live | `409 NOTICE_LIVE`, `details.reason` `LIVE`, `details.expires_at`, "A notice sent on 28 Oct 2026 is open until 27 Nov 2026." |
| the student's latest NOTICE consent is WITHDRAWN | `409 CONFLICT`, `details.reason` `CONSENT_WITHDRAWN`, "The student has asked not to receive notices." |
| no email address and no linked APAAR | `409 CONFLICT`, `details.reason` `NO_CHANNEL`, "The student has no email address or linked APAAR to send a notice to." |
| three resends already used for this enrolment | `429 RESEND_LIMIT`, `details.limit` 3, "This notice has been resent 3 times this academic year." |

A resend writes one QUEUED row per channel with `resent_by_id` = the caller, commits, and hands delivery to the worker (task `countersign.deliver_notices`). Resends used = the number of rows with `resent_by_id` set on the channel that has most of them. An enrolment belongs to one academic year, so "per academic year" needs no extra key.

```json
202 {
  "enrolment_id": "e1e1e1e1-5555-4666-8777-888899990000",
  "notices": [ { ...EnrolmentNotice (§A3.7), "delivery_status": "QUEUED", "state": "QUEUED", "resent": true } ],
  "resend": { "allowed": false, "blocked_by": "LIVE", "resends_left": 2 }
}
```

Audit: CREATE on `notification` per row, actor the caller, `after: {"enrolment_id", "channel", "resent": true}` (never the token).

### A3.6 `GET /students/me` changes (A.10, A2.21)

`notices` and `credentials` are filled. Nothing else changes; the STUDENT check in `enrolments[].countersign` is now real.

```json
"notices": [
  {
    "id": "n1n1n1n1-2222-4333-8444-555566667777",
    "enrolment_id": "e1e1e1e1-5555-4666-8777-888899990000",
    "channel": "EMAIL",
    "institution_name": "ABC College of Engineering",
    "programme_name": "B.Tech Computer Science and Engineering",
    "academic_year": "2026-27",
    "state": "AWAITING",
    "delivery_status": "SENT",
    "sent_at": "2026-10-28T10:05:40Z",
    "expires_at": "2026-11-27T10:05:31Z",
    "response": null, "responded_at": null, "changed_at": null, "can_change_until": null
  }
],
"credentials": [
  { "id": "c1c1c1c1-3333-4444-8555-666677778888", "kind": "ENROLMENT", "status": "ACTIVE",
    "enrolment_id": "e1e1e1e1-5555-4666-8777-888899990000", "institution_name": "ABC College of Engineering",
    "issued_at": "2026-10-29T06:10:00Z" }
]
```

- `notices`, newest first. `state`: `QUEUED` (not delivered yet), `FAILED` (delivery failed), `AWAITING` (delivered and live), `EXPIRED` (delivered, unanswered and expired), `ANSWERED`.
- There is no link: the token is not stored, so a signed-in page cannot open a notice. An unanswered notice shows [notices.reply_hint] instead (use the link in the email or the DigiLocker inbox).
- `credentials` is a short list for the overview; the wallet reads `GET /credentials` (§A3.16).

### A3.7 `GET /enrolments/{id}` changes (A2.11)

New fields, for every role that may open the enrolment:

```json
"notices": [
  { "id": "n1n1n1n1-2222-4333-8444-555566667777", "channel": "EMAIL", "state": "ANSWERED",
    "delivery_status": "SENT", "attempts": 1, "last_error": null,
    "sent_at": "2026-10-28T10:05:40Z", "expires_at": "2026-11-27T10:05:31Z",
    "response": "YES", "responded_at": "2026-10-29T06:09:12Z", "previous_response": null, "changed_at": null,
    "resent": false },
  { "id": "n2n2n2n2-2222-4333-8444-555566667777", "channel": "DIGILOCKER", "state": "AWAITING",
    "delivery_status": "SENT", "attempts": 1, "last_error": null,
    "sent_at": "2026-10-28T10:05:41Z", "expires_at": "2026-11-27T10:05:31Z",
    "response": null, "responded_at": null, "previous_response": null, "changed_at": null,
    "resent": false }
],
"resend": { "allowed": false, "blocked_by": "ANSWERED", "resends_left": 3 },
"credentials": [
  { "id": "c1c1c1c1-3333-4444-8555-666677778888", "kind": "ENROLMENT", "status": "ACTIVE", "short_id": "7Q2MK4PX",
    "issued_at": "2026-10-29T06:10:00Z", "revoked_at": null, "revoked_reason_code": null, "revoked_reason": null }
]
```

- `notices`: every notice of the enrolment, newest first, as `EnrolmentNotice`. Never the token, the message or the student's comment (officers read the comment in the STUDENT_DENIED evidence).
- `resend`: whether the caller may resend now (`blocked_by` is null when `allowed`). `blocked_by`: `LIVE`, `ANSWERED`, `LIMIT`, `CONSENT_WITHDRAWN`, `NO_CHANNEL`, `NOT_ACTIVE`, or `ROLE` for a university. The "Resend notice" button shows when `allowed`.
- `credentials`: every credential of the enrolment as `CredentialRef`; an AICTE officer sees "Revoke" on an ACTIVE one (§A3.18).
- The STUDENT row of `checks` carries the §A3.8 detail. The READ audit entry for the student (Week 2) is unchanged; that entry is the "enrolment detail view" of D29.

### A3.8 The STUDENT check and STUDENT_DENIED (D24)

The STUDENT check is derived from all the notices of the enrolment and the student's contact details; the first matching row wins. Source `STUDENT_NOTICE`.

| # | condition | status | `detail.summary` (copy deck §15) | `detail.notice_state` |
|---|---|---|---|---|
| 1 | some notice's current response is NO | FAIL | `Denied by the student on {reply_date} ({channel_word}).` | `DENIED` |
| 2 | some notice's current response is YES | PASS | `Confirmed by the student on {reply_date} ({channel_word}).` | `CONFIRMED` |
| 3 | no notice was ever delivered and the student has no email address and no linked APAAR | PENDING | `No email or APAAR on record, so no notice can be sent.` | `UNREACHABLE` |
| 4 | no notice has been delivered (SENT) yet | PENDING | `Notice not sent yet.` | `NOT_SENT` |
| 5 | a delivered notice is live | PENDING | `Notice sent on {sent_date}; no reply yet.` | `SENT` |
| 6 | every delivered notice expired unanswered | PENDING | `No reply (expired).` | `EXPIRED` |

- `{reply_date}`: the date of the answer that decided the row (`changed_at` when that notice's answer was changed, else `responded_at`), taking the earliest such NO for row 1 and the earliest YES for row 2. `{channel_word}`: `email` or `DigiLocker`. `{sent_date}`: the latest `sent_at` among live delivered notices.
- Other `detail` keys: `channel` (`EMAIL` or `DIGILOCKER`: the deciding notice for rows 1 and 2, the latest delivered one for rows 5 and 6), `sent_at` (rows 1, 2, 5, 6), `responded_at` (rows 1, 2: the time of the deciding answer), `changed` (true when the deciding notice's answer was changed, else false), and, on row 4 only, `delivery_failed: true` when a delivery FAILED and `consent_withdrawn: true` when the student withdrew notice consent. Timestamps as on the wire.
- UNREACHABLE is PENDING, not NA: the check still counts in the score, so leaving out a student's contact details never removes the Student check.
- No reply is never FAIL and never a flag. A NO beats a YES on another channel.
- The check is refreshed after every delivery, reply and change, and whenever the checks engine evaluates the enrolment (an upload of its row). There is no scheduler, so "No reply (expired)." appears at the next of these after the expiry; the status is PENDING either way.
- Result words on enrolment detail follow `notice_state` (copy deck §3): [check.pending.student_not_sent] for NOT_SENT, [check.pending.student] for SENT, [check.pending.student_expired] for EXPIRED. UNREACHABLE has no word of its own yet and uses [check.pending.student_not_sent] until the deck adds one.

STUDENT_DENIED, raised by row 1 and refreshed by later evaluations:

| field | value |
|---|---|
| severity | HIGH |
| `dedupe_key` | `STUDENT_DENIED:{enrolment_id}` |
| `institution_id`, `programme_id`, `enrolment_id`, `academic_year` | the enrolment's |
| `summary` | `Student replied "not me" to the notice sent on {sent_date}.` (copy `flag.STUDENT_DENIED.summary`) |
| `summary` after the No was changed to Yes | `Student replied "not me" to the notice sent on {sent_date}, then changed the reply to Yes on {changed_date}.` (copy `flag.STUDENT_DENIED.summary_changed`) |
| `facts`, in order, all with source `Student reply` | Channel: `Email` or `DigiLocker`. Notice sent: `{sent_date}`. Replied on: `{reply_date}`. Reply changed: `Yes on {changed_date}` (only after a change). Comment from the student: `{comment}`, or `None`, with `audience: "OFFICER"` |
| `related_enrolment_ids` | `[enrolment_id]` |
| `rule_source` | `Student reply` |

The notice described is the one whose NO decided row 1, or, after a change to Yes, the notice whose `previous_response` is NO. The comment fact is dropped for the registrar and the university by the A2.16 redaction.

After a change from No to Yes the check is PASS, the flag keeps its status, its evidence takes the `summary_changed` sentence and the Reply changed fact, and its history gains a SYSTEM_NOTE. After a change from Yes to No the check is FAIL and the flag is raised (or refreshed, if it exists).

System notes (`case_actions.action` SYSTEM_NOTE, no actor), exact sentences:

- `Evidence updated after the decision.` (copy `case.history.SYSTEM_NOTE`): an engine changed the evidence of a CLEARED or CONFIRMED flag (D25).
- `The student changed the reply from No to Yes on {changed_date}. The flag keeps its status until an officer decides.` (copy `case.system_note.reply_changed`): D24.

### A3.9 Flag transitions (D25)

`A` = AICTE_ADMIN, `R` = RO_OFFICER (flags of institutions in its region), `I` = INSTITUTION (its own flags). "=" means the status does not change.

| from \ action | `REQUEST_DOCS` | `ESCALATE` | `CLEAR` | `CONFIRM` | `NOTE` | `ASSIGN` | `REOPEN` | `COLLEGE_RESPONSE` (§A3.11) |
|---|---|---|---|---|---|---|---|---|
| OPEN | DOCS_REQUESTED: A, R | ESCALATED: A, R | CLEARED: A, R | CONFIRMED: A, R | =: A, R | =: A, R | 409 | 409 |
| DOCS_REQUESTED | DOCS_REQUESTED: A, R | ESCALATED: A, R | CLEARED: A, R | CONFIRMED: A, R | =: A, R | =: A, R | 409 | =: I |
| ESCALATED | DOCS_REQUESTED: A | 409 | CLEARED: A | CONFIRMED: A | =: A, R | =: A | 409 | 409 |
| CLEARED | 409 | 409 | 409 | 409 | =: A, R | 409 | OPEN: A | 409 |
| CONFIRMED | 409 | 409 | 409 | 409 | =: A, R | 409 | OPEN: A | 409 |

- **403 or 409.** An action the table allows from the flag's status for some role, but not for the caller's, is `403 FORBIDDEN` (a regional officer clearing an escalated flag, a regional officer reopening). An action the table does not allow from that status for anyone is `409 FLAG_TRANSITION_INVALID` (clearing a cleared flag, escalating an escalated one). A flag outside the caller's scope is `404` before either. `UNIVERSITY` and `STUDENT` get 403 on every case route; `INSTITUTION` gets 403 on `/actions`.
- Adding a note is allowed in every status (it records, it decides nothing). `SYSTEM_NOTE` is written only by the system.
- **Who reads the note.** Notes on `CLEAR`, `REQUEST_DOCS` and `CONFIRM` are shown to the college; notes on `ESCALATE`, `NOTE` and `REOPEN` are internal to officers (AICTE and regional); `ASSIGN` has no note. The college's own `COLLEGE_RESPONSE` note and the system notes are shown to everyone who can open the flag.

Effects of each action, all in the request's transaction except the email:

| action | flag changes | also |
|---|---|---|
| `REQUEST_DOCS` | status DOCS_REQUESTED; `docs_due_on` = `due_date` (null when not given); `response_received` = false | after the commit, one email to every active INSTITUTION user of the flag's institution (§A3.10) |
| `ESCALATE` | status ESCALATED; `assignee_id` = `assignee_id` when given | |
| `CLEAR` | status CLEARED; `resolved_at` = now | `credentials.issue_if_eligible` for the flag's `enrolment_id` and every id in `related_enrolment_ids` (§A3.15) |
| `CONFIRM` | status CONFIRMED; `resolved_at` = now | every active credential of the flag's `enrolment_id` is revoked with reason code `FLAG_CONFIRMED` and the officer as `revoked_by_id` (§A3.18). The enrolment, its seat and its checks are not touched; nothing is deleted |
| `NOTE` | none | |
| `ASSIGN` | `assignee_id` = `assignee_id` (null unassigns) | |
| `REOPEN` | status OPEN; `resolved_at`, `docs_due_on` = null; `response_received` = false | |
| `COLLEGE_RESPONSE` | `response_received` = true | `case_attachments` rows |

Every action writes one `case_actions` row (`from_status`, `to_status`, `note`, `due_date`, `assignee_id`, `actor_id`) and sets `flags.last_action_at`. Audit: UPDATE on `flag` with the actor and `after: {"action", "from_status", "to_status", "case_action_seq", "assignee_id"?, "due_date"?}`; the note text never goes into the audit log.

### A3.10 `POST /flags/{id}/actions`

Roles: `AICTE_ADMIN`, `RO_OFFICER`. Others: 403.

```json
{ "action": "REQUEST_DOCS", "note": "Send the admission register extract for CSE, 2026-27.", "due_date": "2026-11-11", "assignee_id": null }
```

| field | rule |
|---|---|
| `action` | `REQUEST_DOCS`, `ESCALATE`, `CLEAR`, `CONFIRM`, `NOTE`, `ASSIGN` or `REOPEN` |
| `note` | 1 to 2,000 characters after trimming; required for every action except `ASSIGN` ("Add a note before you continue.", copy `case.note_required`). `ASSIGN` takes no note: one sent with it is ignored. Who reads it: §A3.9 |
| `due_date` | `REQUEST_DOCS` only (ignored otherwise), optional; not before today (IST) and at most 90 days ahead |
| `assignee_id` | `ASSIGN` (required key; null unassigns) and `ESCALATE` (optional); ignored otherwise. Must be an active AICTE_ADMIN, or an active RO_OFFICER of the flag's institution's region; for `ESCALATE` an AICTE_ADMIN. Otherwise 422 on `assignee_id`: "Choose an officer who can see this flag." or "Escalate to an AICTE officer." |

Checks run in this order: the route's roles (403), body shape (422), flag in scope (404 "Flag not found."), role and status per §A3.9 (403, then 409 `FLAG_TRANSITION_INVALID` with `details: {"status", "action", "allowed_actions"}`), then the field rules above (422).

Response `200`: the flag as `FlagDetail` (§A3.13) after the action.

The REQUEST_DOCS email (sent after the commit; a mail failure is logged and never undoes the action): from `NOTICE_FROM` to each active registrar of the institution; subject [email.docs_request.subject], body [email.docs_request.body] with the placeholders the copy deck lists (`{role_word}`, `{institution_name}`, `{flag_name}`, `{where}`, `{summary}` the institution's summary per A2.16, `{note}`, `{due_sentence}` from [email.docs_request.due] or empty, `{link}` = `{WEB_ORIGIN}/college/flags/{id}`). No student and no officer is named in the email.

### A3.11 `POST /flags/{id}/response` (multipart)

Roles: `INSTITUTION` on its own flags (another institution's flag: 404 "Flag not found."). Everyone else: 403. The flag must be DOCS_REQUESTED, else `409 FLAG_TRANSITION_INVALID`.

Form fields: `note` (required, 1 to 2,000 characters) and `files` (zero to three parts, each named `files`).

| check | answer |
|---|---|
| more than three files | `422 VALIDATION_ERROR` on `files`: "Attach at most 3 files." |
| a file's first bytes are not PDF (`%PDF-`), PNG (`89 50 4E 47 0D 0A 1A 0A`) or JPEG (`FF D8 FF`); the declared content type is not trusted | `415 ATTACHMENT_TYPE` "Only PDF, PNG and JPEG files can be attached.", `details.filename` |
| a file larger than 5 MB (5,242,880 bytes) | `413 ATTACHMENT_TOO_LARGE` "Each file can be at most 5 MB.", `details.filename`, `details.max_bytes` |
| request body larger than 16 MB | `413 ATTACHMENT_TOO_LARGE` |

All or nothing: one bad file rejects the whole response and nothing is stored. Effects: a COLLEGE_RESPONSE `case_actions` row (status unchanged), one `case_attachments` row per file (the file encrypted under `CASE_FILES_DIR`, ENGINES §16.5), `flags.response_received` = true, `last_action_at`; audit UPDATE on `flag` and CREATE on `case_attachment` per file (`after: {"flag_id", "sha256", "size_bytes", "content_type"}`).

Response `201`: `FlagDetail` (§A3.13). Copy deck `college.respond_files` should read 5 MB, not 10 MB.

### A3.12 `GET /flags/{id}/attachments/{attachment_id}`

Roles: `AICTE_ADMIN`, `RO_OFFICER` (region), `INSTITUTION` (its own flags). `UNIVERSITY`, `STUDENT`: 403. An attachment that is not on that flag, or a flag outside scope: 404 "Attachment not found.".

`200` with the original bytes, `Content-Type` as stored, `Content-Disposition: attachment; filename="admission_register_cse.pdf"; filename*=UTF-8''admission_register_cse.pdf`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`. Writes a READ audit entry on `case_attachment` with `after: {"flag_id"}`.

### A3.13 `GET /flags` and `GET /flags/{id}` changes (A2.15, A2.16)

`FlagRow` (list and detail) gains, and makes real:

```json
"assignee": { "id": "u2u2u2u2-1111-4222-8333-444455556666", "name": "Regional Officer, Western Region" },
"response_received": true,
"docs_due_on": "2026-11-11",
"last_action_at": "2026-10-30T09:12:00Z"
```

`assignee` is null when unassigned, and always null for an `INSTITUTION` caller.

New `GET /flags` filters: `assignee` = `me` | `none` | an officer's id (ignored for `INSTITUTION`); `response_received` = `true` | `false`. They combine with the Week 2 filters, so the "Responses to read" view is `status=DOCS_REQUESTED&response_received=true`.

`FlagDetail` gains:

- `history`: the flag's `case_actions` rows in `seq` order as `CaseHistoryItem`. The page still prints [case.history.opened] from `created_at` first.
- `allowed_actions`: the officer actions §A3.9 allows the caller now, in the order `CLEAR`, `REQUEST_DOCS`, `ESCALATE`, `CONFIRM`, `NOTE`, `ASSIGN`, `REOPEN`; `[]` for `INSTITUTION`. The action bar shows exactly these.
- `can_respond`: true for an `INSTITUTION` caller when the flag is DOCS_REQUESTED.

```json
"history": [
  { "seq": 41, "at": "2026-10-29T05:32:00Z", "action": "REQUEST_DOCS", "from_status": "OPEN", "to_status": "DOCS_REQUESTED",
    "actor": { "id": "u2u2u2u2-1111-4222-8333-444455556666", "name": "Regional Officer, Western Region", "role": "RO_OFFICER" },
    "note": "Send the admission register extract for CSE, 2026-27.", "due_date": "2026-11-11", "assignee": null, "attachments": [] },
  { "seq": 44, "at": "2026-10-30T09:12:00Z", "action": "COLLEGE_RESPONSE", "from_status": "DOCS_REQUESTED", "to_status": "DOCS_REQUESTED",
    "actor": { "id": "6f1c0a8e-2b1d-4c9a-9e51-1c2f1a0b7d33", "name": "Registrar, ABC College of Engineering", "role": "INSTITUTION" },
    "note": "Extract attached.", "due_date": null, "assignee": null,
    "attachments": [ { "id": "a1a1a1a1-1111-4222-8333-444455556666", "filename": "admission_register_cse.pdf", "content_type": "application/pdf", "size_bytes": 421888, "sha256": "9f2c4e0d1b3a5c7e9f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f70" } ] },
  { "seq": 47, "at": "2026-10-31T04:00:00Z", "action": "SYSTEM_NOTE", "from_status": "CLEARED", "to_status": "CLEARED",
    "actor": null, "note": "Evidence updated after the decision.", "due_date": null, "assignee": null, "attachments": [] }
]
```

- `actor` is null for system rows; the web prints [case.history.system].
- **Redaction for `INSTITUTION`.** Every row is listed except ASSIGN (the college never sees who a flag is assigned to). Rows whose note is internal (ESCALATE, NOTE, REOPEN, §A3.9) come with `note: null`, so the college sees "Escalated" or "Reopened the flag" without the officer's words; REQUEST_DOCS, CLEAR, CONFIRM, COLLEGE_RESPONSE and SYSTEM_NOTE rows keep their notes. `assignee` is always null. The officer's sheets for Escalate, Add note and Reopen say the note stays with officers; `case.note_label` "Note (shown to the college)" stays on Request documents, Clear and Confirm.
- `GET /flags/{id}` keeps its Week 2 READ audit entries.

### A3.14 `GET /users` (assignee picker)

Roles: `AICTE_ADMIN`, `RO_OFFICER`. Others: 403.

Query: `role` (required; `RO_OFFICER`, `AICTE_ADMIN` or both comma-separated; any other value 422), `flag_id?` (only officers who may be assigned that flag; a flag outside scope 404), `page`, `page_size`. Scope: an AICTE officer sees every officer; a regional officer sees AICTE officers and the regional officers of its own region. Active users only, sorted by role (AICTE_ADMIN first) then name. Never an email address or other contact detail.

```json
200 {
  "items": [
    { "id": "u1u1u1u1-1111-4222-8333-444455556666", "name": "AICTE Administrator", "role": "AICTE_ADMIN", "region": null },
    { "id": "u2u2u2u2-1111-4222-8333-444455556666", "name": "Regional Officer, Western Region", "role": "RO_OFFICER", "region": "WEST" }
  ],
  "total": 2, "page": 1, "page_size": 25
}
```

### A3.15 Credential format (D26)

**Issuer-signed JWT.** Header `{"alg": "ES256", "typ": "dc+sd-jwt", "kid": "<issuer kid>"}` (set through the library's `extra_header_parameters`). Payload of an Enrolment proof, with the selectively disclosable claims shown as the `_sd` digests they become:

```json
{
  "iss": "http://localhost:8000",
  "iat": 1793254200,
  "exp": 1819736999,
  "vct": "countersign:enrolment:v1",
  "status": { "status_list": { "idx": 48213, "uri": "http://localhost:8000/status-lists/1" } },
  "cnf": { "jwk": { "kty": "EC", "crv": "P-256", "x": "<base64url>", "y": "<base64url>" } },
  "_sd_alg": "sha-256",
  "_sd": [ "<one digest per disclosable claim>" ]
}
```

- Always visible: `iss` (`ISSUER_URL`), `iat`, `exp` (31 August of the year the academic year ends, 23:59:59 IST: `2026-27` gives `2027-08-31T18:29:59Z`), `vct`, `status.status_list` (`idx`, the credential's `status_list_index`; `uri`, `{ISSUER_URL}/status-lists/1`) and `cnf.jwk` (the student's holder key, public part only).
- Selectively disclosable, one top-level disclosure each, in this order (`credentials.disclosable`):

| key | label | claim value | display value (`value` on the wire) |
|---|---|---|---|
| `name` | Name | `"Ravi Kumar Sharma"` | as is |
| `dob` | Date of birth | `"2007-03-21"` | `21 Mar 2007` |
| `apaar_masked` | APAAR (masked) | `"XXXX XXXX 4417"`; left out when the student has no linked APAAR | as is |
| `institution` | Institution | `{"name": "ABC College of Engineering", "aicte_id": "1-ABC-0001"}` | `ABC College of Engineering (1-ABC-0001)` |
| `programme` | Programme | `{"name": "B.Tech Computer Science and Engineering", "level": "UG"}` | `B.Tech Computer Science and Engineering (UG)` |
| `academic_year` | Academic year | `"2026-27"` | as is |
| `year_of_study` | Year of study | `1` | `1` |
| `countersigned` | Countersigned by | `{"checks": ["IDENTITY", "ADMISSION", "SEAT", "STUDENT"], "on": "2026-10-29"}` | `Identity, Admission, Seat and Student, as of 29 Oct 2026` |

  `countersigned.checks` lists the check types that were PASS when the proof was issued, in display order (NA checks are left out); `on` is the issue date in IST. Check words are the copy deck's `check.*`.
- `institution` and `programme` are always disclosed in a presentation; the share sheet shows them ticked and locked.
- **Degree proof** (D28): the same header, `vct` `countersign:degree:v1`, no `cnf` and no `exp`. Disclosable, in order: `name`, `apaar_masked` (or left out), `institution`, `programme`, `university` (`{"name": "Maharashtra State Technical University", "code": "MSTU"}`, label University, value `Maharashtra State Technical University (MSTU)`) and `year_of_award` (`2026`, label Year of award).
- No decoy digests (`add_decoy_claims=False`).

**Presentation.** `SDJWTHolder(credential.sd_jwt).create_presentation(claims_to_disclose={key: True for each disclosed key}, nonce=<share code>, aud="{ISSUER_URL}/verify", holder_key=<holder key>, sign_alg="ES256")`. The key-binding JWT has header `typ: "kb+jwt"` and claims `iat`, `aud`, `nonce` and `sd_hash`. A presentation is the issuer JWT, the chosen disclosures and the key-binding JWT joined by `~`.

**Share code.** 120 random bits as 24 Crockford base32 characters (`0123456789ABCDEFGHJKMNPQRSTVWXYZ`), shown as six groups of four joined by hyphens: `K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF`. Input is normalised before lookup: trim, upper case, drop spaces and hyphens, read `O` as `0` and `I` and `L` as `1`, then require exactly 24 characters of the alphabet and regroup. `code_hash` is the hex SHA-256 of the six-group form. The six-group form is also the key-binding `nonce`. The copy deck placeholder `verify.placeholder` should show six groups.

**Status list token** (`GET /status-lists/1`). A JWT with header `{"alg": "ES256", "kid": "<issuer kid>", "typ": "statuslist+jwt"}` and payload:

```json
{
  "iss": "http://localhost:8000",
  "sub": "http://localhost:8000/status-lists/1",
  "iat": 1793254320,
  "exp": 1793340720,
  "ttl": 60,
  "status_list": { "bits": 1, "lst": "<base64url of the zlib-compressed bits>" }
}
```

- 131,072 entries, one bit each: 16,384 bytes, compressed with zlib (DEFLATE in the ZLIB format) and base64url-encoded without padding into `lst`.
- The status of index `i` is bit `i mod 8` (least significant bit first) of byte `floor(i / 8)`; `1` means revoked, `0` valid. Index 48213 is bit 5 of byte 6026.
- `exp` is `iat` plus one day; `ttl` 60 seconds. The api rebuilds the token at most every 60 seconds, and at once after a revocation made in the same process; the verifier reads the bit from this same token, so it sees what any third party sees.

### A3.16 `GET /credentials` and `GET /credentials/{id}`

Roles for both: `STUDENT` (own credentials only; another id is 404 "Credential not found."), `AICTE_ADMIN` (any). `RO_OFFICER`, `INSTITUTION`, `UNIVERSITY`: 403.

`GET /credentials`: query `page`, `page_size`, and for `AICTE_ADMIN` only `student_id?`, `enrolment_id?`, `kind?`, `status?` (ignored for a student). Newest first. Writes a READ audit entry on `credential` for each item returned.

```json
200 {
  "items": [
    {
      "id": "c1c1c1c1-3333-4444-8555-666677778888",
      "kind": "ENROLMENT",
      "status": "ACTIVE",
      "vct": "countersign:enrolment:v1",
      "short_id": "7Q2MK4PX",
      "issuer": { "name": "Countersign", "url": "http://localhost:8000" },
      "enrolment_id": "e1e1e1e1-5555-4666-8777-888899990000",
      "institution_name": "ABC College of Engineering",
      "programme_name": "B.Tech Computer Science and Engineering",
      "academic_year": "2026-27",
      "university_name": null,
      "issued_at": "2026-10-29T06:10:00Z",
      "expires_at": "2027-08-31T18:29:59Z",
      "revoked_at": null,
      "revoked_reason_code": null,
      "revoked_reason": null,
      "holder_bound": true,
      "disclosable": [
        { "key": "name", "label": "Name", "always": false },
        { "key": "dob", "label": "Date of birth", "always": false },
        { "key": "apaar_masked", "label": "APAAR (masked)", "always": false },
        { "key": "institution", "label": "Institution", "always": true },
        { "key": "programme", "label": "Programme", "always": true },
        { "key": "academic_year", "label": "Academic year", "always": false },
        { "key": "year_of_study", "label": "Year of study", "always": false },
        { "key": "countersigned", "label": "Countersigned by", "always": false }
      ],
      "shares": 2,
      "last_verified_at": "2026-10-29T06:12:31Z",
      "presentations": [
        { "id": "p1p1p1p1-4444-4555-8666-777788889999", "created_at": "2026-10-29T06:10:00Z", "expires_at": "2026-10-29T06:20:00Z",
          "disclosed": ["institution", "programme", "academic_year"], "verify_count": 1, "last_verified_at": "2026-10-29T06:12:31Z" }
      ]
    }
  ],
  "total": 1, "page": 1, "page_size": 25
}
```

- `status`: `REVOKED` when revoked, else `EXPIRED` when `expires_at` has passed, else `ACTIVE`.
- `holder_bound`: true for ENROLMENT (the proof carries `cnf`), false for DEGREE.
- `university_name`: the awarding university for a DEGREE, else null.
- `shares`: presentations created; `last_verified_at`: the latest verification of any of them, or null.
- `presentations`: the five most recent shares, newest first, so the wallet can draw its history without another call; `GET /credentials/{id}/presentations` (§A3.17) pages through all of them.
- `revoked_reason_code` and `revoked_reason`: §A3.18; both null unless revoked.

`GET /credentials/{id}`: the same object plus `claims`, every claim the credential holds, for the holder to read:

```json
"claims": [
  { "key": "name", "label": "Name", "value": "Ravi Kumar Sharma", "disclosable": true },
  { "key": "institution", "label": "Institution", "value": "ABC College of Engineering (1-ABC-0001)", "disclosable": true },
  { "key": "issued", "label": "Issued", "value": "29 Oct 2026", "disclosable": false },
  { "key": "expires", "label": "Valid until", "value": "31 Aug 2027", "disclosable": false }
]
```

Writes a READ audit entry on `credential`.

### A3.17 `POST /credentials/{id}/present` and `GET /credentials/{id}/presentations`

`POST /credentials/{id}/present`: `STUDENT`, own credential only (another id 404). `AICTE_ADMIN` and everyone else: 403 (only the holder shares). 10 per minute per user.

```json
{ "fields": ["academic_year"], "consent": true }
```

- `fields`: keys from the credential's `disclosable`; an unknown key is 422 on `fields` ("Unknown field: {key}."). `institution` and `programme` are added when missing.
- `consent`: must be `true`, else 422 on `consent` ("Agree to the share text to create a proof.").
- A REVOKED credential: `409 CREDENTIAL_REVOKED` "This proof was revoked on {revoked_date} and cannot be shared.". An EXPIRED one: `409 CREDENTIAL_NOT_ELIGIBLE`, `details.reason` `EXPIRED`, "This proof expired on {expires_date} and cannot be shared.".

Effects: a `credential_presentations` row (10-minute expiry); a `consents` row (CREDENTIAL_SHARE, GIVEN, channel `PORTAL`, `notice_text` = [consent.credential_share], no enrolment); audit CREATE on `credential_presentation` (`after: {"credential_id", "disclosed", "expires_at"}`) and READ on `credential` (`after: {"via": "share", "presentation_id"}`).

```json
201 {
  "id": "p1p1p1p1-4444-4555-8666-777788889999",
  "code": "K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF",
  "url": "http://localhost:3000/verify/K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF",
  "qr_svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 41 41\">...</svg>",
  "expires_at": "2026-10-29T06:20:00Z",
  "disclosed": ["institution", "programme", "academic_year"],
  "total": 8
}
```

- `code` is returned only here; only its hash is stored.
- `qr_svg`: the QR of `url` (segno, error correction M, quiet zone 4 modules, black on white, a `viewBox` and no fixed size, no XML declaration). It is generated by the api, so the web may insert it as markup.
- `disclosed` follows the credential's disclosable order; `total` is the number of disclosable claims ("Shares 3 of 8 fields").

`GET /credentials/{id}/presentations`: `STUDENT` (own), `AICTE_ADMIN`. Newest first; never the code or the presentation itself.

```json
200 {
  "items": [
    { "id": "p1p1p1p1-4444-4555-8666-777788889999", "created_at": "2026-10-29T06:10:00Z", "expires_at": "2026-10-29T06:20:00Z",
      "state": "EXPIRED", "disclosed": ["institution", "programme", "academic_year"],
      "verify_count": 1, "first_verified_at": "2026-10-29T06:12:31Z", "last_verified_at": "2026-10-29T06:12:31Z" }
  ],
  "total": 1, "page": 1, "page_size": 25
}
```

`state` is `LIVE` or `EXPIRED`. The wallet's history (copy deck `wallet.history.*`, `wallet.history_item*`) reads `created_at`, `verify_count`, `last_verified_at` and `expires_at` of each share.

### A3.18 `POST /credentials/{id}/revoke` and revocation reasons

Roles: `AICTE_ADMIN` only. Body `{ "reason": "Admission found to be fraudulent after inquiry." }` (5 to 300 characters, and not one of the reason codes below, else 422 on `reason`). Already revoked: `409 CREDENTIAL_REVOKED` "This proof is already revoked.".

Sets `revoked`, `revoked_at`, `revoked_reason` (the officer's text), `revoked_by_id`; the status-list bit flips with the next token (at once in the api process). Audit UPDATE on `credential` with `after: {"revoked": true, "reason_code": "ADMIN"}` (the reason text stays out of the audit log). Response `200`: the `CredentialCard` (§A3.16) with `status: "REVOKED"`.

Every revocation has a reason code. `credentials.revoked_reason` stores the code itself for the three system causes and the officer's text for an officer's revocation, so no new column is needed:

| `revoked_reason_code` (wire) | cause | stored `revoked_reason` | actor | wallet words |
|---|---|---|---|---|
| `ENROLMENT_WITHDRAWN` | the Seat Ledger released the seat because the enrolment was withdrawn | `ENROLMENT_WITHDRAWN` | the batch's uploader (none for a seeded batch) | `wallet.revoked_reason.ENROLMENT_WITHDRAWN` |
| `ENROLMENT_TRANSFERRED` | the same, for a transfer | `ENROLMENT_TRANSFERRED` | the batch's uploader (none for a seeded batch) | `wallet.revoked_reason.ENROLMENT_TRANSFERRED` |
| `FLAG_CONFIRMED` | an officer confirmed a flag on the enrolment (§A3.9) | `FLAG_CONFIRMED` | the officer | `wallet.revoked_reason.FLAG_CONFIRMED` |
| `ADMIN` | this endpoint | the officer's text | the officer | `wallet.revoked_reason.ADMIN` |

On the wire, `revoked_reason_code` is derived (the stored value when it is one of the first three codes, else `ADMIN`) and `revoked_reason` is the stored value as is. The words come from the copy deck, never from the stored text. A pending check never revokes. The verifier never says why a proof was revoked.

### A3.19 Public issuer endpoints

| route | response |
|---|---|
| `GET /.well-known/jwks.json` | `200 application/json`, `Cache-Control: public, max-age=300`: `{"keys": [{"kty": "EC", "crv": "P-256", "x": "...", "y": "...", "kid": "...", "use": "sig", "alg": "ES256"}]}`, every issuer key, active and retired. The first call creates the key if none exists, so the set is never empty |
| `GET /.well-known/jwt-vc-issuer` | `200`: `{"issuer": "http://localhost:8000", "jwks_uri": "http://localhost:8000/.well-known/jwks.json"}` |
| `GET /status-lists/1` | `200 application/statuslist+jwt`, `Cache-Control: public, max-age=60`, body the compact JWT of §A3.15. Any other list id: `404 NOT_FOUND` "Status list not found." |

These are served by the api at `ISSUER_URL`; the browser can also reach them through `/api/...`.

### A3.20 Verifier (D27)

All four are public, 60 per minute per address, and answer with a `VerifyResult`:

```json
200 {
  "result": "VALID",
  "kind": "ENROLMENT",
  "issuer": { "name": "Countersign", "url": "http://localhost:8000" },
  "institution_name": "ABC College of Engineering",
  "university_name": null,
  "issued_at": "2026-10-29T06:10:00Z",
  "expires_at": "2026-10-29T06:20:00Z",
  "revoked_at": null,
  "disclosed": [
    { "key": "institution", "label": "Institution", "value": "ABC College of Engineering (1-ABC-0001)" },
    { "key": "programme", "label": "Programme", "value": "B.Tech Computer Science and Engineering (UG)" },
    { "key": "academic_year", "label": "Academic year", "value": "2026-27" }
  ],
  "holder_bound": true,
  "status_checked_at": "2026-10-29T06:12:00Z",
  "method": "signature",
  "nonce": null
}
```

- `result`, decided in this order: `INVALID` (anything cryptographic fails: issuer signature, unknown `kid`, key binding, nonce, audience, or an unreadable input), then `REVOKED` (status bit 1), then `EXPIRED` (the presentation is past its 10 minutes, or the credential past its `exp`), else `VALID`.
- Only `VALID` carries `disclosed` and `institution_name`; other results have `disclosed: []` and `institution_name: null`. `REVOKED` carries `revoked_at`. `INVALID` has `kind`, `issuer`, `issued_at` and `status_checked_at` null and `holder_bound` false.
- `disclosed` lists only what the presentation disclosed, labelled as in §A3.15. Never an undisclosed claim, never a full APAAR. There is no search endpoint.
- `expires_at`: the presentation's expiry (code), the credential's `exp` (pasted), null (degree QR and register lookup). `status_checked_at`: the `iat` of the status list token used, or the time of the database read for a register lookup. `nonce`: only for `POST /verify`, else null.
- `method`: `signature` when the answer comes from checking Countersign's signature (share code, pasted presentation, degree QR); `register_lookup` when it comes from AICTE's own record (`GET /verify/degree/{short_id}`), so the page can say which check was made.

**`GET /verify/{code}`.** Normalise the code (§A3.15); malformed or unknown: `404 PRESENTATION_NOT_FOUND` "This code is not a Countersign proof." (the web shows [err.PRESENTATION_NOT_FOUND]). Otherwise verify the stored presentation with `SDJWTVerifier`, its key callback reading the JWKS document of §A3.19 and checking `iss` equals `ISSUER_URL`, `expected_nonce` = the code and `expected_aud` = `{ISSUER_URL}/verify`; then the presentation's `expires_at`, the credential's `exp` and the status bit. Every call on a found presentation increments `verify_count` and sets `first_verified_at` (once) and `last_verified_at`, whatever the result. Audit READ on `credential_presentation`, no actor, `after: {"via": "verifier", "ip_hash", "result"}`.

**`POST /verify`.** Body `{ "presentation": "<issuer JWT>~<disclosure>~...~<key-binding JWT>" }` (1 to 16,384 characters, else 422). Checks the issuer signature, the key binding (signature and `sd_hash`; the nonce and audience are read from the key-binding JWT and passed as the expected values, so they are reported, not enforced), the credential's `exp`, the key-binding `iat` (older than 10 minutes is `EXPIRED`, the same life as a shared code) and the status bit. A credential with `cnf` presented without key binding is `INVALID`. `nonce` echoes the key-binding nonce. When the nonce is a stored code and the stored presentation is identical, that presentation's counters move as above. Audit READ on `credential` (found by `status.status_list.idx`), `after: {"via": "verifier-paste", "ip_hash", "result"}`; no entity when nothing matched.

**`GET /verify/d/{jws}`** (degree QR, §A3.21). Verify the compact JWS against the JWKS by its `kid`, require `v` = 1, find the DEGREE credential whose `short_id` is `cid`, and read its status bit. Unreadable input, a bad signature or an unknown `cid` is `INVALID`. `kind` is `DEGREE`, `holder_bound` false, `expires_at` null, `institution_name` the signed `i`, `university_name` the name of university `u`. `disclosed`, from the signed payload only: `name` (Name, `n`), `programme` (Programme, `p`), `institution` (Institution, `i`), `university` (University, `{name} ({u})`), `year_of_award` (Year of award, `y`), and `apaar_masked` (APAAR (masked), `XXXX XXXX {a}`) or `provisional_id` (Provisional id, `a` as signed). Audit READ on `credential`, `after: {"via": "degree-qr", "ip_hash", "result"}`. `disclosed` also carries `proof_id` (Proof id, the `cid`), the id printed under the QR.

**`GET /verify/degree/{short_id}`** (degree proof id, register lookup). For a reader who has the printed proof id but cannot scan. Normalise the id (trim, upper case, `O` read as `0`, `I` and `L` as `1`); an id that is malformed or not a DEGREE credential's `short_id` is `404 PRESENTATION_NOT_FOUND`. The answer has the same shape as the degree QR's, built from AICTE's stored record instead of a signature: `method` `register_lookup`, `result` `REVOKED` when the credential is revoked, else `VALID`; `kind` `DEGREE`; `issued_at`; `revoked_at`; `holder_bound` false; `institution_name` and `university_name` the full names; `disclosed` (when VALID): `proof_id`, `name`, `programme` (full name), `institution` (full name), `university` (`{name} ({code})`), `year_of_award`, and `apaar_masked` or `provisional_id` (masked as in §A3.1). Audit READ on `credential`, `after: {"via": "degree-lookup", "ip_hash", "result"}`. Web route `/verify/degree/[shortId]`; the `/verify` entry page sends an 8-character id there and a six-group code to `/verify/[code]`.

`ip_hash` is the first 16 hex characters of HMAC-SHA256(`PII_HMAC_KEY`, client address). Error answers: `404 PRESENTATION_NOT_FOUND` (share code and proof id), `422 VALIDATION_ERROR` (paste only), `429 RATE_LIMITED`. Web: `/verify` scans with `BarcodeDetector` when the browser has it, else takes a typed or pasted code or a pasted presentation; `/verify/[code]` and `/verify/d/[jws]` show the result.

### A3.21 University endpoints and the degree QR (D28)

**`GET /university/graduates`.** Roles: `UNIVERSITY` (graduates of its own affiliates), `AICTE_ADMIN` (all; optional `university_id`). Others 403. Query: `page`, `page_size`, `q?` (name substring, APAAR last four or provisional id), `institution_id?` (outside scope 404), `academic_year?`, `degree?` = `issued` | `not_issued`. Graduates are enrolments with status GRADUATED. Sorted by institution name, then student name. Writes a READ audit entry on `student` for each row.

```json
200 {
  "items": [
    {
      "enrolment_id": "g1g1g1g1-6666-4777-8888-999900001111",
      "student": { "id": "s9s9s9s9-6666-4777-8888-999900001111", "name": "Asha Patil", "apaar_masked": "XXXX XXXX 0011", "provisional_id": null },
      "institution": { "id": "a0b1c2d3-1111-4222-8333-444455556666", "name": "ABC College of Engineering", "aicte_permanent_id": "1-ABC-0001" },
      "programme": { "id": "p1p1p1p1-3333-4444-8555-666677778888", "code": "CSE", "name": "B.Tech Computer Science and Engineering", "level": "UG" },
      "academic_year": "2025-26",
      "year_of_award": 2026,
      "degree": { "credential_id": "c9c9c9c9-3333-4444-8555-666677778888", "short_id": "4ZK8M2QD", "status": "ACTIVE", "issued_at": "2026-10-29T07:00:00Z" }
    }
  ],
  "total": 412, "page": 1, "page_size": 25
}
```

`year_of_award` is the year the academic year ends (`2025-26` gives 2026). `degree` is null until a Degree proof is issued.

**`POST /university/degrees/{enrolment_id}/issue`.** Roles: `UNIVERSITY` (its affiliates; else 404 "Enrolment not found."), `AICTE_ADMIN`. Body `{}`. An enrolment that is not GRADUATED: `409 CREDENTIAL_NOT_ELIGIBLE`, `details.reason` `NOT_GRADUATED`, "Degree proofs are issued only for graduated students.". An active Degree proof already: `200` with the print data, nothing new. Otherwise issue (§A3.15; a revoked earlier proof does not block a new one) and answer `201` with the print data below. Audit CREATE on `credential` with the user as actor.

**`GET /university/degrees/{enrolment_id}`.** Same roles and 404 and 409 (`NOT_GRADUATED`) rules. Writes a READ audit entry on `student` with `after: {"via": "degree-print"}`.

```json
200 {
  "enrolment_id": "g1g1g1g1-6666-4777-8888-999900001111",
  "student": { "name": "Asha Patil", "id_kind": "APAAR", "id_masked": "XXXX XXXX 0011" },
  "programme": { "code": "CSE", "name": "B.Tech Computer Science and Engineering", "short_name": "B.Tech CS & Engg." },
  "institution": { "name": "ABC College of Engineering", "aicte_permanent_id": "1-ABC-0001", "short_name": "ABC College of Engg." },
  "university": { "code": "MSTU", "name": "Maharashtra State Technical University" },
  "academic_year": "2025-26",
  "year_of_award": 2026,
  "degree": {
    "credential_id": "c9c9c9c9-3333-4444-8555-666677778888",
    "short_id": "4ZK8M2QD",
    "status": "ACTIVE",
    "issued_at": "2026-10-29T07:00:00Z",
    "revoked_at": null,
    "jws": "eyJhbGciOiJFUzI1NiIsImtpZCI6Ii4uLiJ9.eyJ2IjoxLCJjaWQiOiI0Wks4TTJRRCIsLi4ufQ.<signature>",
    "verify_url": "http://localhost:3000/verify/d/eyJhbGciOiJFUzI1NiIsImtpZCI6Ii4uLiJ9.eyJ2IjoxLCJjaWQiOiI0Wks4TTJRRCIsLi4ufQ.<signature>",
    "lookup_url": "http://localhost:3000/verify/degree/4ZK8M2QD",
    "qr_svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 57 57\">...</svg>"
  }
}
```

`degree` is null until issued; the print view then shows [degree.issue] first. `verify_url` is what the QR encodes and is never printed as text; the print shows [degree.print.proof_id] and [degree.scan_line] under the QR, and `lookup_url` is where a typed proof id leads (§A3.20).

**The compact JWS.** Header `{"alg": "ES256", "kid": "<issuer kid>"}` (no `typ`, to keep it short). Payload, keys in this order, no spaces:

```json
{"v":1,"cid":"4ZK8M2QD","n":"Asha Patil","p":"B.Tech CS & Engg.","i":"ABC College of Engg.","u":"MSTU","y":2026,"a":"0011"}
```

`cid` the credential `short_id`; `n` the student's name; `p` and `i` the short names below; `u` the university code; `y` the year of award; `a` the last four APAAR digits, or the masked provisional id (`PRV-XXXXK4PX`) when there is no linked APAAR. Short name: replace `Engineering` with `Engg.`, `Technology` with `Tech.`, `Institute` with `Inst.`, `Management` with `Mgmt.`, `Computer Science` with `CS`, `Information Technology` with `IT`, ` and ` with ` & `, `University` with `Univ.`, then cut to at most 28 characters at a space. The URL `{WEB_ORIGIN}/verify/d/{jws}` stays near 350 characters. The JWS is signed on each request (ES256 signatures differ each time; every one verifies), so it is not stored. The QR is segno, error correction M, as in §A3.17.

**`GET /university/degrees/{enrolment_id}/insert.pdf`.** Same roles. No active Degree proof: `409 CREDENTIAL_NOT_ELIGIBLE`, `details.reason` `NOT_ISSUED`, "Issue the degree proof first."; a revoked one: `409 CREDENTIAL_REVOKED`. `200 application/pdf`, `Content-Disposition: attachment; filename="degree-insert-4ZK8M2QD.pdf"`. One A4 portrait page (reportlab): university name, the student's name, programme, institution, year of award, the id line `APAAR XXXX XXXX 0011` (or `Provisional id PRV-XXXXK4PX`), the QR about 40 mm wide with `Proof id 4ZK8M2QD` and the verify page's host and path (`localhost:3000/verify`) under it, and the footer "Sample degree insert generated from synthetic demo data. Not a degree certificate.". Writes the same READ audit entry as the print data.

### A3.22 Privacy and data rights (D30)

**`GET /privacy/notice`** (public, 60 per minute).

```json
200 {
  "version": "v1",
  "effective_from": "2026-10-28",
  "title": "How Countersign uses your data",
  "sections": [ { "id": "what_we_hold", "heading": "What we hold", "body": "..." } ],
  "consent_texts": {
    "APAAR_LINK": "I allow AICTE to use my APAAR id to check that my enrolment at {institution_name} is genuine. ...",
    "NOTICE": "By replying, you let AICTE record your answer with today's date against this enrolment. ...",
    "CREDENTIAL_SHARE": "I am creating a proof that shows only the fields I ticked. ..."
  }
}
```

The text lives in `app/privacy/notice.py` (version `v1`), mirrored from the copy deck: the sections from the privacy keys the copy deck adds for the notice, the consent texts from §9 with their placeholders left in. A new wording is a new version; stored consents keep the version they were given under.

**`GET /students/me/consents`** (`STUDENT`).

```json
200 {
  "current": [
    { "purpose": "APAAR_LINK", "status": "GIVEN", "since": "2026-10-28T10:02:14Z", "can_withdraw": false },
    { "purpose": "NOTICE", "status": "NONE", "since": null, "can_withdraw": true },
    { "purpose": "CREDENTIAL_SHARE", "status": "GIVEN", "since": "2026-10-29T06:10:00Z", "can_withdraw": true }
  ],
  "items": [
    { "id": "k1k1k1k1-7777-4888-8999-000011112222", "purpose": "APAAR_LINK", "status": "GIVEN", "channel": "COLLEGE_UPLOAD",
      "notice_text": "I allow AICTE to use my APAAR id to check that my enrolment at ABC College of Engineering is genuine. ...",
      "notice_version": "v1", "recorded_at": "2026-10-28T10:02:14Z", "withdrawn_at": null,
      "enrolment": { "id": "e1e1e1e1-5555-4666-8777-888899990000", "institution_name": "ABC College of Engineering",
                     "programme_name": "B.Tech Computer Science and Engineering", "academic_year": "2026-27" } }
  ]
}
```

- `current`: one entry per purpose, in the order above, from the latest row of that purpose; `status` is `GIVEN`, `WITHDRAWN`, `REFUSED` or `NONE` (no row). `can_withdraw`: NOTICE unless already WITHDRAWN; CREDENTIAL_SHARE when GIVEN; APAAR_LINK never (it is a correction request).
- `items`: every row, newest first, with the exact text the student saw.
- APAAR_LINK rows are written by the upload pipeline when a student's consent is first recorded or changes: LINKED gives GIVEN, REFUSED gives REFUSED, PENDING and INTERNATIONAL write nothing; channel `COLLEGE_UPLOAD`, text [consent.apaar_link] with the institution's name, `actor_id` the uploader in the audit entry.

**`POST /students/me/consents/{purpose}/withdraw`** (`STUDENT`). Body `{}`. `purpose` is `NOTICE` or `CREDENTIAL_SHARE`; `APAAR_LINK` is `422` on `purpose`: "To unlink your APAAR, send a correction request. Your college must upload your record again; your admission is not affected." Any other value is 422. Withdrawing what is already withdrawn changes nothing.

- NOTICE: every GIVEN NOTICE row becomes WITHDRAWN with `withdrawn_at`; when there is none, one WITHDRAWN row is written (channel `PORTAL`, `notice_text` = [consent.withdraw]) so the choice is kept. No new notices are sent; notices already delivered can still be answered, and a later Yes records a new GIVEN row.
- CREDENTIAL_SHARE: every GIVEN row becomes WITHDRAWN, and every live presentation of the student's credentials gets `expires_at` = now (a verifier then sees EXPIRED).

Audit UPDATE on `consent` per row (`after: {"purpose", "status"}`). Response `200`: the `GET` body plus `"presentations_expired": 2` (0 for NOTICE). Copy deck `consent.withdraw` mentions APAAR checks and needs a NOTICE and a CREDENTIAL_SHARE variant.

**`GET /students/me/access-log`** (`STUDENT`). Page of READ audit entries about the student's record, notices, credentials and proofs, newest first; reads made by the student's own login are left out.

```json
200 {
  "items": [
    { "at": "2026-10-29T06:12:31Z", "role": "VERIFIER", "what": "PROOF" },
    { "at": "2026-10-29T05:40:02Z", "role": "RO_OFFICER", "what": "RECORD" },
    { "at": "2026-10-28T11:15:09Z", "role": "NOTICE_LINK", "what": "NOTICE" }
  ],
  "total": 3, "page": 1, "page_size": 25
}
```

| audit entry | `what` |
|---|---|
| `student`, the student's id (enrolment detail, flag detail, graduates list, data request lists) | `RECORD` |
| `student` with `after.via` `export` | `EXPORT` |
| `student` with `after.via` `degree-print` | `DEGREE` |
| `notification` of the student's notices | `NOTICE` |
| `credential` of the student's credentials | `CREDENTIAL` |
| `credential_presentation` of those credentials | `PROOF` |

`role` is the reader's role; for entries without an actor it is `VERIFIER` (`via` `verifier`, `verifier-paste`, `degree-qr` or `degree-lookup`), `NOTICE_LINK` (`via` `notice-link`) or `SYSTEM`. Never a name, an email or an id of the reader.

**`POST /students/me/data-requests`** (`STUDENT`, 10 per minute).

```json
{ "kind": "CORRECTION", "details": "My date of birth is recorded wrongly at ABC College of Engineering.", "enrolment_id": "e1e1e1e1-5555-4666-8777-888899990000" }
```

`details`: 10 to 2,000 characters, required for CORRECTION and ERASURE, optional for ACCESS. `enrolment_id`: optional, must be one of the student's enrolments (else 422). ACCESS is DONE at once with `response` "Your data is ready to download." and `resolved_at` now; CORRECTION and ERASURE are OPEN. Audit CREATE on `data_request` (`after: {"kind", "status"}`).

```json
201 {
  "id": "d1d1d1d1-8888-4999-8aaa-bbbbccccdddd",
  "kind": "ACCESS", "status": "DONE",
  "details": null, "response": "Your data is ready to download.",
  "enrolment": null,
  "created_at": "2026-10-29T07:30:00Z", "resolved_at": "2026-10-29T07:30:00Z",
  "export_path": "/students/me/export.json"
}
```

`export_path` (an api path; the web prefixes `/api`) is set for ACCESS only.

**`GET /students/me/data-requests`** (`STUDENT`). The student's own requests, newest first, with the officers' replies: a page of `DataRequestRow` (the shape of the `201` above; `response` and `resolved_at` filled once resolved).

**`GET /students/me/export.json`** (`STUDENT`). `200 application/json`, `Content-Disposition: attachment; filename="countersign-my-data.json"`. Everything held about the student, APAAR masked, never another person's data:

```json
{
  "generated_at": "2026-10-29T07:30:02Z",
  "privacy_notice_version": "v1",
  "student": { "id": "...", "name": "Ravi Kumar Sharma", "dob": "2007-03-21", "gender": "M", "nationality": "IN",
               "apaar_masked": "XXXX XXXX 4417", "provisional_id": null, "consent_status": "LINKED",
               "email": "ravi.sharma@example.demo", "mobile_masked": "XXXXXX4521" },
  "enrolments": [ { "id": "...", "institution_name": "...", "programme_name": "...", "academic_year": "2026-27", "year_of_study": 1,
                    "admission_route": "COUNSELLING", "category": "GENERAL", "status": "ACTIVE", "status_date": "2026-10-28",
                    "admission_date": "2026-08-02", "seat_code": "CSE-R-001",
                    "checks": [ { "type": "IDENTITY", "status": "PASS", "summary": "...", "checked_at": "..." } ],
                    "flags": [ { "type": "DUPLICATE_WITHIN_UPLOAD", "status": "OPEN", "summary": "...", "created_at": "..." } ] } ],
  "notices": [ { "channel": "EMAIL", "sent_at": "...", "expires_at": "...", "delivery_status": "SENT",
                 "response": "YES", "responded_at": "...", "changed_at": null, "comment": null } ],
  "consents": [ "...as items in GET /students/me/consents..." ],
  "credentials": [ { "id": "...", "kind": "ENROLMENT", "status": "ACTIVE", "issued_at": "...", "expires_at": "...",
                     "revoked_at": null, "revoked_reason": null, "claims": [ { "key": "name", "label": "Name", "value": "Ravi Kumar Sharma" } ] } ],
  "presentations": [ { "credential_id": "...", "created_at": "...", "expires_at": "...", "disclosed": ["institution", "programme"], "verify_count": 1 } ],
  "data_requests": [ "...DataRequestRow..." ],
  "access_log": [ "...AccessLogRow..." ]
}
```

Flag summaries use the institution wording (A2.16), which never names another student. Writes a READ audit entry on `student` with `after: {"via": "export"}`.

**`GET /data-requests`** (`AICTE_ADMIN`). Query `page`, `page_size`, `status?`, `kind?`. OPEN first, then oldest first. Writes a READ audit entry on `student` for each row.

```json
200 {
  "items": [
    { "id": "d2d2d2d2-8888-4999-8aaa-bbbbccccdddd", "kind": "CORRECTION", "status": "OPEN",
      "details": "My date of birth is recorded wrongly at ABC College of Engineering.", "response": null,
      "enrolment": { "id": "e1e1e1e1-5555-4666-8777-888899990000", "institution_name": "ABC College of Engineering",
                     "programme_name": "B.Tech Computer Science and Engineering", "academic_year": "2026-27" },
      "student": { "id": "st1...", "name": "Ravi Kumar Sharma", "apaar_masked": "XXXX XXXX 4417", "provisional_id": null },
      "created_at": "2026-10-29T07:31:00Z", "resolved_at": null, "resolved_by": null, "export_path": null }
  ],
  "total": 1, "page": 1, "page_size": 25
}
```

**`POST /data-requests/{id}/resolve`** (`AICTE_ADMIN`). Body `{ "status": "DONE" | "REJECTED", "response": "..." }` (10 to 2,000 characters). Unknown id: 404 "Data request not found.". Not OPEN: `409 CONFLICT`, `details.reason` `ALREADY_RESOLVED`, "This request is already resolved.". Sets `status`, `response`, `resolved_at`, `resolved_by_id`; audit UPDATE on `data_request` (`after: {"status"}`). Response `200`: the row. Resolving a correction changes no data: the college corrects its upload. The web prefills an erasure response with [admin.requests.erasure_reply], which explains the statutory retention.

### A3.23 Audit (D29)

**`GET /admin/audit`** (A.13) gains filters `entity_id` (uuid), `action` (`AuditAction`) and `seq_from` (integer: only entries with `seq` at most `seq_from`; the list is newest first, so `seq_from=n` opens the list at entry n). Rows gain `actor_role` (the actor's role, or null) and `via` (`after.via` when present, else null).

```json
{ "seq": 917, "at": "2026-10-29T06:12:31Z", "actor_id": null, "actor_email": null, "actor_role": null, "via": "verifier",
  "action": "READ", "entity_type": "credential_presentation", "entity_id": "p1p1p1p1-4444-4555-8666-777788889999",
  "hash": "9f8e...", "prev_hash": "1a2b..." }
```

**`GET /admin/audit/verify`** (A.12) is unchanged: `first_broken_seq` is the first entry whose stored `hash` does not match its recomputation or whose `prev_hash` is not the previous entry's `hash`, else null. The `/admin/audit` page shows "Chain broken at entry {first_broken_seq}", loads `seq_from={first_broken_seq + 10}` and highlights that row.

READ entries added in Week 3 (writes keep the ENGINES §12 table):

| read | `entity_type` | `entity_id` | actor | `after` |
|---|---|---|---|---|
| notice page view (`GET /notices/{token}`) | `notification` | notice | null | `{"via": "notice-link"}` |
| credential list and detail (`GET /credentials`, `/credentials/{id}`) | `credential` | credential | user | null |
| share (`POST /credentials/{id}/present`) | `credential` | credential | student | `{"via": "share", "presentation_id"}` |
| verifier, share code | `credential_presentation` | presentation | null | `{"via": "verifier", "ip_hash", "result"}` |
| verifier, pasted presentation | `credential` or none | credential | null | `{"via": "verifier-paste", "ip_hash", "result"}` |
| verifier, degree QR | `credential` | credential | null | `{"via": "degree-qr", "ip_hash", "result"}` |
| verifier, degree proof id | `credential` | credential | null | `{"via": "degree-lookup", "ip_hash", "result"}` |
| attachment download | `case_attachment` | attachment | user | `{"flag_id"}` |
| enrolment detail (since Week 2) | `student` | student | user | null |
| graduates list, degree print data and PDF | `student` | student | user | null; `{"via": "degree-print"}` for print data and PDF |
| student export | `student` | student | student | `{"via": "export"}` |
| admin data request list | `student` | student | user | null |

**`make audit-tamper SEQ=n`** runs `python -m app.core.audit_tamper --seq n` in the api container. It refuses (exit code 2, "audit-tamper runs only when DEMO_MODE=true.") unless `DEMO_MODE=true`, refuses an unknown `seq`, and otherwise changes the stored `after` of entry n (adds `"tampered": true`) without recomputing any hash, so `GET /admin/audit/verify` reports `first_broken_seq: n`. It writes no audit entry of its own. `make demo-reset` rebuilds the database and a clean chain.

### A3.24 Dashboard and student overview

No shape changes. With replies flowing, `kpis.countersigned_pct` rises above 0 (the STUDENT check is now PASS for students who said Yes) and `flags_by_type` counts STUDENT_DENIED. The `/student` overview drops [student.check_student_pending] once a notice exists and shows the notices and the wallet card instead.

### A3.25 Error codes added in Week 3

| status | code | message (exact) | `details` |
|---|---|---|---|
| 404 | `NOTICE_NOT_FOUND` | "This link is not valid." | `{}` (identical for malformed and unknown tokens) |
| 410 | `NOTICE_EXPIRED` | "This link has expired. Ask your college to resend the notice." | `{}` |
| 409 | `NOTICE_ALREADY_CHANGED` | "You have already changed your answer once." or "Answers can be changed only within 7 days of the first reply." | `reason`: `CHANGED_ONCE` or `WINDOW_CLOSED` |
| 409 | `NOTICE_LIVE` | "A notice sent on {sent_date} is open until {expires_date}." or "The student has already replied." | `reason`: `LIVE` (with `expires_at`) or `ANSWERED` |
| 429 | `RESEND_LIMIT` | "This notice has been resent 3 times this academic year." | `limit`: 3 |
| 409 | `FLAG_TRANSITION_INVALID` | "This action is not possible while the flag is {status_word}." | `status`, `action`, `allowed_actions` |
| 413 | `ATTACHMENT_TOO_LARGE` | "Each file can be at most 5 MB." | `filename`, `max_bytes` |
| 415 | `ATTACHMENT_TYPE` | "Only PDF, PNG and JPEG files can be attached." | `filename` |
| 409 | `CREDENTIAL_NOT_ELIGIBLE` | "Degree proofs are issued only for graduated students.", "Issue the degree proof first." or "This proof expired on {expires_date} and cannot be shared." | `reason`: `NOT_GRADUATED`, `NOT_ISSUED` or `EXPIRED` |
| 409 | `CREDENTIAL_REVOKED` | "This proof was revoked on {revoked_date} and cannot be shared." or "This proof is already revoked." | `revoked_at` |
| 404 | `PRESENTATION_NOT_FOUND` | "This code is not a Countersign proof." | `{}` |
| 409 | `CONFLICT` (existing generic) | per route: §A3.5, §A3.22 | `reason` |

`{status_word}` for `FLAG_TRANSITION_INVALID`: OPEN open, DOCS_REQUESTED waiting for documents, ESCALATED escalated, CLEARED cleared, CONFIRMED confirmed. New 404 messages: "Credential not found.", "Attachment not found.", "Data request not found.", "Status list not found.". Copy deck §13 gains an `err.<CODE>` line for each.

### A3.26 Addendum 3 scoping

"public" means no sign-in is needed (any cookie is ignored).

| Endpoint | AICTE_ADMIN | RO_OFFICER | INSTITUTION | STUDENT | UNIVERSITY | public |
|---|---|---|---|---|---|---|
| `GET /notices/{token}`, `POST /notices/{token}/respond` | | | | | | yes, 30/min |
| `POST /enrolments/{id}/notices/resend` | any | region, else 404 | own, else 404 | 403 | 403 | no |
| `GET /students/me` (notices, credentials) | 403 | 403 | 403 | own | 403 | no |
| `GET /enrolments/{id}` (notices, resend, credentials) | any | region, else 404 | own, else 404 | 403 | affiliate, else 404 (`resend.blocked_by` ROLE) | no |
| `POST /flags/{id}/actions` | any, per §A3.9 | region, else 404; per §A3.9 | 403 | 403 | 403 | no |
| `POST /flags/{id}/response` | 403 | 403 | own, else 404; DOCS_REQUESTED only | 403 | 403 | no |
| `GET /flags/{id}/attachments/{attachment_id}` | any | region, else 404 | own, else 404 | 403 | 403 | no |
| `GET /flags`, `GET /flags/{id}` (history, assignee, filters) | all | region, else 404 | own, redacted (§A3.13), else 404 | 403 | 403 | no |
| `GET /users` | every officer | AICTE officers and own region's officers | 403 | 403 | 403 | no |
| `GET /credentials`, `GET /credentials/{id}` | any | 403 | 403 | own, else 404 | 403 | no |
| `POST /credentials/{id}/present` | 403 | 403 | 403 | own, else 404 | 403 | no |
| `GET /credentials/{id}/presentations` | any | 403 | 403 | own, else 404 | 403 | no |
| `POST /credentials/{id}/revoke` | any | 403 | 403 | 403 | 403 | no |
| `GET /.well-known/jwks.json`, `/.well-known/jwt-vc-issuer`, `GET /status-lists/1` | | | | | | yes, 120/min |
| `GET /verify/{code}`, `POST /verify`, `GET /verify/d/{jws}`, `GET /verify/degree/{short_id}` | | | | | | yes, 60/min |
| `GET /university/graduates` | all | 403 | 403 | 403 | affiliates | no |
| `POST /university/degrees/{id}/issue`, `GET /university/degrees/{id}`, `.../insert.pdf` | any | 403 | 403 | 403 | affiliate, else 404 | no |
| `GET /privacy/notice` | | | | | | yes, 60/min |
| `GET /students/me/consents`, `POST .../consents/{purpose}/withdraw`, `GET /students/me/access-log`, `GET` and `POST /students/me/data-requests`, `GET /students/me/export.json` | 403 | 403 | 403 | own | 403 | no |
| `GET /data-requests`, `POST /data-requests/{id}/resolve` | all | 403 | 403 | 403 | 403 | no |
| `GET /admin/audit` (new filters), `GET /admin/audit/verify` | ok | 403 | 403 | 403 | 403 | no |

403 and 404 bodies are as in section B. Order of answers: the route's roles (403), body shape (422), scope (404), then per-status rules (403 or 409, §A3.9) and field rules (422).

### A3.27 TypeScript types (paste into `apps/web/lib/types.ts`)

Add the new types and replace the earlier declarations of `CheckDetail`, `FlagRow`, `FlagListQuery`, `FlagDetail`, `EnrolmentDetail` (all A2.23), `StudentMe` and `AuditRow` (section D) with the ones below. `FlagListParams`, `FlagStatusFilter` and the other derived names keep working.

```ts
// ---------- Week 3 enums ----------
export type NoticeChannel = "EMAIL" | "DIGILOCKER";
export type NoticeResponse = "YES" | "NO";
export type NoticeDelivery = "QUEUED" | "SENT" | "FAILED";
export type NoticeState = "QUEUED" | "AWAITING" | "ANSWERED" | "EXPIRED" | "FAILED";
export type StudentNoticeState = "NOT_SENT" | "UNREACHABLE" | "SENT" | "EXPIRED" | "CONFIRMED" | "DENIED";
export type IdKind = "APAAR" | "PROVISIONAL";
export type ResendBlock = "LIVE" | "ANSWERED" | "LIMIT" | "CONSENT_WITHDRAWN" | "NO_CHANNEL" | "NOT_ACTIVE" | "ROLE";
export type CaseAction =
  | "CLEAR" | "REQUEST_DOCS" | "ESCALATE" | "CONFIRM" | "NOTE" | "ASSIGN" | "REOPEN" | "COLLEGE_RESPONSE" | "SYSTEM_NOTE";
export type OfficerAction = Exclude<CaseAction, "COLLEGE_RESPONSE" | "SYSTEM_NOTE">;
export type OfficerRole = Extract<Role, "AICTE_ADMIN" | "RO_OFFICER">;
export type CredentialKind = "ENROLMENT" | "DEGREE";
export type CredentialStatus = "ACTIVE" | "REVOKED" | "EXPIRED";
export type PresentationState = "LIVE" | "EXPIRED";
export type VerifyResultCode = "VALID" | "REVOKED" | "EXPIRED" | "INVALID";
export type VerifyMethod = "signature" | "register_lookup";
export type RevokedReasonCode = "ENROLMENT_WITHDRAWN" | "ENROLMENT_TRANSFERRED" | "FLAG_CONFIRMED" | "ADMIN";
export type ClaimKey =
  | "name" | "dob" | "apaar_masked" | "provisional_id" | "institution" | "programme" | "academic_year"
  | "year_of_study" | "countersigned" | "university" | "year_of_award" | "proof_id";
export type ConsentPurpose = "APAAR_LINK" | "NOTICE" | "CREDENTIAL_SHARE";
export type ConsentState = "GIVEN" | "WITHDRAWN" | "REFUSED";
export type ConsentCurrentState = ConsentState | "NONE";
export type ConsentChannel = "COLLEGE_UPLOAD" | "NOTICE_EMAIL" | "NOTICE_DIGILOCKER" | "PORTAL";
export type DataRequestKind = "ACCESS" | "CORRECTION" | "ERASURE";
export type DataRequestStatus = "OPEN" | "DONE" | "REJECTED";
export type AccessorRole = Role | "NOTICE_LINK" | "SYSTEM";
export type AccessedWhat = "RECORD" | "EXPORT" | "DEGREE" | "NOTICE" | "CREDENTIAL" | "PROOF";

// ---------- checks ----------
/** Replaces the A2.23 CheckDetail: adds the STUDENT check keys of A3.8. */
export interface CheckDetail {
  summary: string;
  source_unavailable?: boolean; source_error?: string; needs_review?: boolean;
  name_score?: number; dob_match?: boolean; apaar_last4?: string;
  round?: number; allotment_ref?: string; ref_mismatch?: boolean;
  seat_code?: string; seat_type?: SeatType; flag_type?: FlagType;
  expected?: number; missing?: number; semesters?: { academic_year: string; sem: number; credits: number }[];
  awaiting_semester?: number;
  notice_state?: StudentNoticeState; channel?: NoticeChannel; sent_at?: string; responded_at?: string; changed?: boolean;
  delivery_failed?: boolean; consent_withdrawn?: boolean;
  [key: string]: unknown;
}

// ---------- notices ----------
export interface NoticePublic {
  channel: NoticeChannel; institution_name: string; programme_code: string; programme_name: string;
  academic_year: string; year_of_study: number; id_kind: IdKind; id_masked: string;
  uploaded_at: string; sent_at: string | null; expires_at: string;
  response: NoticeResponse | null; responded_at: string | null;
  previous_response: NoticeResponse | null; changed_at: string | null; can_change_until: string | null;
  consent_text: string; notice_version: string;
}
export interface NoticeRespondRequest { response: NoticeResponse; comment?: string }
export interface StudentNotice {
  id: string; enrolment_id: string; channel: NoticeChannel;
  institution_name: string; programme_name: string; academic_year: string;
  state: NoticeState; delivery_status: NoticeDelivery; sent_at: string | null; expires_at: string;
  response: NoticeResponse | null; responded_at: string | null; changed_at: string | null; can_change_until: string | null;
}
export interface EnrolmentNotice {
  id: string; channel: NoticeChannel; state: NoticeState; delivery_status: NoticeDelivery;
  attempts: number; last_error: string | null; sent_at: string | null; expires_at: string;
  response: NoticeResponse | null; responded_at: string | null;
  previous_response: NoticeResponse | null; changed_at: string | null; resent: boolean;
}
export interface ResendState { allowed: boolean; blocked_by: ResendBlock | null; resends_left: number }
export interface NoticeResendResult { enrolment_id: string; notices: EnrolmentNotice[]; resend: ResendState }

// ---------- credentials ----------
export interface IssuerRef { name: string; url: string }
export interface CredentialRef {
  id: string; kind: CredentialKind; status: CredentialStatus; short_id: string;
  issued_at: string; revoked_at: string | null; revoked_reason_code: RevokedReasonCode | null; revoked_reason: string | null;
}
export interface StudentCredentialBrief {
  id: string; kind: CredentialKind; status: CredentialStatus; enrolment_id: string; institution_name: string; issued_at: string;
}
export interface DisclosableField { key: ClaimKey; label: string; always: boolean }
export interface PresentationBrief {
  id: string; created_at: string; expires_at: string; disclosed: ClaimKey[]; verify_count: number; last_verified_at: string | null;
}
export interface CredentialCard {
  id: string; kind: CredentialKind; status: CredentialStatus; vct: string; short_id: string; issuer: IssuerRef;
  enrolment_id: string; institution_name: string; programme_name: string; academic_year: string;
  university_name: string | null;
  issued_at: string; expires_at: string | null; revoked_at: string | null;
  revoked_reason_code: RevokedReasonCode | null; revoked_reason: string | null;
  holder_bound: boolean; disclosable: DisclosableField[]; shares: number; last_verified_at: string | null;
  presentations: PresentationBrief[];
}
export interface CredentialClaim { key: string; label: string; value: string; disclosable: boolean }
export interface CredentialDetail extends CredentialCard { claims: CredentialClaim[] }
export interface CredentialListQuery {
  page?: number; page_size?: number; student_id?: string; enrolment_id?: string; kind?: CredentialKind; status?: CredentialStatus;
}
export interface PresentRequest { fields: ClaimKey[]; consent: true }
export interface PresentationCreated {
  id: string; code: string; url: string; qr_svg: string; expires_at: string; disclosed: ClaimKey[]; total: number;
}
export interface PresentationRow {
  id: string; created_at: string; expires_at: string; state: PresentationState; disclosed: ClaimKey[];
  verify_count: number; first_verified_at: string | null; last_verified_at: string | null;
}
export interface RevokeRequest { reason: string }

// ---------- verifier ----------
export interface DisclosedField { key: ClaimKey; label: string; value: string }
export interface VerifyResult {
  result: VerifyResultCode; kind: CredentialKind | null; issuer: IssuerRef | null;
  institution_name: string | null; university_name: string | null;
  issued_at: string | null; expires_at: string | null; revoked_at: string | null;
  disclosed: DisclosedField[]; holder_bound: boolean; status_checked_at: string | null;
  method: VerifyMethod; nonce: string | null;
}
export interface VerifyPasteRequest { presentation: string }

// ---------- university ----------
export interface GraduateRow {
  enrolment_id: string;
  student: { id: string; name: string; apaar_masked: string | null; provisional_id: string | null };
  institution: { id: string; name: string; aicte_permanent_id: string };
  programme: { id: string; code: string; name: string; level: Level };
  academic_year: string; year_of_award: number;
  degree: { credential_id: string; short_id: string; status: CredentialStatus; issued_at: string } | null;
}
export interface GraduateListQuery {
  page?: number; page_size?: number; q?: string; institution_id?: string; academic_year?: string;
  degree?: "issued" | "not_issued"; university_id?: string;
}
export interface DegreePrint {
  enrolment_id: string;
  student: { name: string; id_kind: IdKind; id_masked: string };
  programme: { code: string; name: string; short_name: string };
  institution: { name: string; aicte_permanent_id: string; short_name: string };
  university: { code: string; name: string };
  academic_year: string; year_of_award: number;
  degree: {
    credential_id: string; short_id: string; status: CredentialStatus; issued_at: string; revoked_at: string | null;
    jws: string; verify_url: string; lookup_url: string; qr_svg: string;
  } | null;
}

// ---------- cases ----------
export interface ActorRef { id: string; name: string; role: Role }
export interface CaseAttachment {
  id: string; filename: string; content_type: "application/pdf" | "image/png" | "image/jpeg"; size_bytes: number; sha256: string;
}
export interface CaseHistoryItem {
  seq: number; at: string; action: CaseAction; from_status: FlagStatus | null; to_status: FlagStatus | null;
  actor: ActorRef | null; note: string | null; due_date: string | null;
  assignee: { id: string; name: string } | null; attachments: CaseAttachment[];
}
export interface CaseActionRequest { action: OfficerAction; note?: string; due_date?: string | null; assignee_id?: string | null }
/** POST /flags/{id}/response is multipart: FormData with "note" and up to three "files". */
/** Replaces the A2.23 FlagRow. */
export interface FlagRow {
  id: string; type: FlagType; severity: Severity; status: FlagStatus;
  institution: InstitutionRef; programme: ProgrammeRef | null; enrolment_id: string | null; academic_year: string;
  summary: string; related_count: number; assignee: { id: string; name: string } | null;
  response_received: boolean; docs_due_on: string | null; last_action_at: string | null;
  created_at: string; updated_at: string;
}
/** Replaces the A2.23 FlagListQuery. */
export interface FlagListQuery {
  page?: number; page_size?: number; type?: FlagType; severity?: Severity; status?: FlagStatus;
  institution_id?: string; programme_id?: string; state?: string; academic_year?: string; q?: string; sort?: FlagSort;
  assignee?: "me" | "none" | string; response_received?: boolean;
}
/** Replaces the A2.23 FlagDetail. */
export interface FlagDetail extends FlagRow {
  evidence: Evidence;
  enrolment: RelatedEnrolmentRow | null;
  related_enrolments: RelatedEnrolmentRow[];
  related_hidden: number;
  history: CaseHistoryItem[];
  allowed_actions: OfficerAction[];
  can_respond: boolean;
}
export interface OfficerRow { id: string; name: string; role: OfficerRole; region: Region | null }
export interface UserListQuery {
  role: OfficerRole | `${OfficerRole},${OfficerRole}`; flag_id?: string; page?: number; page_size?: number;
}

// ---------- enrolments and the student ----------
/** Replaces the A2.23 EnrolmentDetail. */
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
  notices: EnrolmentNotice[];
  resend: ResendState;
  credentials: CredentialRef[];
}
/** Replaces the section D StudentMe. */
export interface StudentMe {
  id: string; name: string; apaar_masked: string | null; consent_status: ConsentStatus; provisional_id: string | null;
  dob: string; email: string | null; mobile_masked: string | null;
  enrolments: StudentEnrolment[];
  notices: StudentNotice[];
  credentials: StudentCredentialBrief[];
}

// ---------- privacy ----------
export interface PrivacyNotice {
  version: string; effective_from: string; title: string;
  sections: { id: string; heading: string; body: string }[];
  consent_texts: Record<ConsentPurpose, string>;
}
export interface EnrolmentBrief { id: string; institution_name: string; programme_name: string; academic_year: string }
export interface ConsentRow {
  id: string; purpose: ConsentPurpose; status: ConsentState; channel: ConsentChannel;
  notice_text: string; notice_version: string; recorded_at: string; withdrawn_at: string | null;
  enrolment: EnrolmentBrief | null;
}
export interface ConsentCurrent { purpose: ConsentPurpose; status: ConsentCurrentState; since: string | null; can_withdraw: boolean }
export interface ConsentsView { current: ConsentCurrent[]; items: ConsentRow[] }
export interface ConsentWithdrawResult extends ConsentsView { presentations_expired: number }
export interface AccessLogRow { at: string; role: AccessorRole; what: AccessedWhat }
export interface DataRequestRow {
  id: string; kind: DataRequestKind; status: DataRequestStatus; details: string | null; response: string | null;
  enrolment: EnrolmentBrief | null; created_at: string; resolved_at: string | null; export_path: string | null;
}
export interface DataRequestAdminRow extends DataRequestRow {
  student: { id: string; name: string; apaar_masked: string | null; provisional_id: string | null };
  resolved_by: { id: string; name: string } | null;
}
export interface DataRequestCreate { kind: DataRequestKind; details?: string; enrolment_id?: string }
export interface DataRequestResolve { status: Exclude<DataRequestStatus, "OPEN">; response: string }
export interface DataRequestListQuery { page?: number; page_size?: number; status?: DataRequestStatus; kind?: DataRequestKind }
export interface MyDataExport {
  generated_at: string; privacy_notice_version: string;
  student: {
    id: string; name: string; dob: string; gender: "M" | "F" | "O" | "U"; nationality: string;
    apaar_masked: string | null; provisional_id: string | null; consent_status: ConsentStatus;
    email: string | null; mobile_masked: string | null;
  };
  enrolments: {
    id: string; institution_name: string; programme_name: string; academic_year: string; year_of_study: number;
    admission_route: AdmissionRoute; category: Category; status: EnrolmentStatus; status_date: string; admission_date: string;
    seat_code: string | null;
    checks: { type: CheckType; status: CheckStatus; summary: string; checked_at: string | null }[];
    flags: { type: FlagType; status: FlagStatus; summary: string; created_at: string }[];
  }[];
  notices: {
    channel: NoticeChannel; sent_at: string | null; expires_at: string; delivery_status: NoticeDelivery;
    response: NoticeResponse | null; responded_at: string | null; changed_at: string | null; comment: string | null;
  }[];
  consents: ConsentRow[];
  credentials: {
    id: string; kind: CredentialKind; status: CredentialStatus; issued_at: string; expires_at: string | null;
    revoked_at: string | null; revoked_reason: string | null; claims: { key: string; label: string; value: string }[];
  }[];
  presentations: { credential_id: string; created_at: string; expires_at: string; disclosed: ClaimKey[]; verify_count: number }[];
  data_requests: DataRequestRow[];
  access_log: AccessLogRow[];
}

// ---------- audit ----------
/** Replaces the section D AuditRow. */
export interface AuditRow {
  seq: number; at: string; actor_id: string | null; actor_email: string | null; actor_role: Role | null; via: string | null;
  action: AuditAction; entity_type: string; entity_id: string | null; hash: string; prev_hash: string | null;
}
export interface AuditListQuery {
  page?: number; page_size?: number; actor_id?: string; entity_type?: string; entity_id?: string;
  action?: AuditAction; seq_from?: number;
}
```

### A3.28 Sections C and E update: mockgov and datagen output for Week 3

Supersedes the matching lines of sections C and E and of A2.24. Everything not mentioned stays as it is.

**mockgov C.5 `POST /digilocker/notify`.** `202 {"delivered": true, "inbox_id": "ib_01HZ..."}` when the APAAR has a DigiLocker account (a registry entry); otherwise `404 {"error": {"code": "APAAR_NOT_LINKED", "message": "No DigiLocker account is linked to this APAAR id.", "details": {}}}` and nothing is stored. The Week 1 `200 {"delivered": false, ...}` answer is gone. The route stays behind the chaos gate, so a DigiLocker outage in the demo gives 503.

**mockgov `GET /digilocker/ui`** (new). An HTML inbox page for the demo, outside the chaos gate (it shows the inbox even while DigiLocker is "down"), no sign-in like every mockgov route: every message, newest first, optional `?apaar_id=` filter, each row showing the APAAR's last four digits, the message, the time received and a "Respond" link to its `callback_url`. `GET /digilocker/inbox/{apaar_id}` is unchanged.

**`notice_replies.jsonl`** (new, `/data/generated/`). One line per accepted row of every initial upload file, in file and row order; rows the api rejects as upload errors and the rows of update files (refills included) have no line.

```json
{"file": "1-ABC-0001_2026-27.csv", "row_no": 57, "reply": "YES", "channel": "EMAIL", "comment": null, "reply_after_days": 3}
```

- `file` and `row_no` name the row exactly as the api stores it (`upload_batches.filename`, `enrolments.source_row_no`; header row 1, first data row 2).
- `reply`: `YES` for about 70 percent of clean rows (no planted anomaly, not withdrawn or transferred by a later update file); `NO` for every row planted with `will_deny`, three of them with a short `comment`; `NONE` for every other row.
- `channel`: the channel the student answers on (`DIGILOCKER` or `EMAIL`). A NO goes by DigiLocker when the row's APAAR is in the registry, else by email. A NONE line still names the channel the student would use, with `reply_after_days` 0.
- `reply_after_days`: how long after the notice the student answered (0 to 12 for YES, 0 to 5 for NO). The api applies every reply at seed time and does not use this value in Week 3.
- The seed (`python -m app.seed.replies`) applies only YES and NO lines.

**`graduates.jsonl`** (new). One line per graduate: final-year students of 2025-26 at institutions affiliated to each university, fields in this order:

```json
{"institution_aicte_id": "1-ABC-0001", "programme_code": "CSE", "academic_year": "2025-26", "year_of_study": 4, "name": "Asha Patil", "dob": "2004-05-17", "gender": "F", "apaar_id": "987654320011", "consent_status": "LINKED", "provisional_id": null, "email": null, "mobile": null, "nationality": "IN", "year_of_award": 2026, "admission_route": "COUNSELLING", "category": "OBC", "admission_date": "2022-08-01", "status_date": "2026-06-30"}
```

- Most graduates have an `apaar_id` with `consent_status` LINKED and a registry entry in `mockgov/apaar_registry.jsonl`; a few have `apaar_id: null` and a `provisional_id`. ABC College of Engineering has B.Tech CSE graduates, all LINKED, for the degree demo.
- The existing seed CLI imports them right after the institutions (`app/seed/graduates.py`): each line becomes a student stored as an upload stores one, and one GRADUATED enrolment of 2025-26 with its cohort year, no seat, no upload batch, no checks and no flags; a re-run adds nothing; one SEED audit entry per run.

**`manifest.json`.** `counts` gains `graduates`, `notice_replies`, `notice_replies_yes`, `notice_replies_no` and `notice_replies_none`. New key `demo_unanswered_notices`: `[{"role", "file", "row_no", "name", "apaar_id"}]`, the notices left for the live demo and the end-to-end test, with `role` `DEMO_STUDENT` (Ravi Kumar Sharma, row 2 of `1-ABC-0001_2026-27.csv`), `DEMO_STUDENT_DUPLICATE` (his "R. K. Sharma" row) and `SECOND_DEMO_NOTICE` (a clean ABC College CSE first-year with an email and a DigiLocker account; row 9 in the small size), who answers No live.

**`ground_truth.json`.** Unchanged: the STUDENT_DENIED records (8 in the small size) are already there, and the quick check must still find every planted case after `make seed`.

**Seed order** (`make seed` and `make demo-reset`): mockgov seed (with the graduates' registry rows); `python -m app.seed.cli --from /data/generated` (institutions and users, graduates, every upload through `run_batch`, then `send_notices_for_batch` for every batch in upload order); `python -m app.seed.replies --from /data/generated`.

## Addendum 3 errata (2026-10-29): corrections from the built api and web

These override anything in Addendum 3 that disagrees.

1. **Degree QR fit (A3.21).** Short names are made as written, with two refinements: the replacements run longest phrase first (`Information Technology` and `Computer Science` before `Technology` and `Engineering`), and the cut at a space never leaves a trailing "of", "&", "and", "in", "for", "the" or "at", or an unclosed bracket. The URL `{WEB_ORIGIN}/verify/d/{jws}` is kept under 400 characters: when it would reach 400, the longer of `p` and `i` (the programme on a tie) drops its last word, and this repeats until the URL fits or both are 8 characters or fewer. The student's name `n` is never shortened. The print data's `programme.short_name` and `institution.short_name` keep the plain 28-character form, so after a fit they can be longer than what the QR carries (`app/credentials/degree.py`, `fitted_payload`).
2. **Rate limits (A3.1, A3.20, A3.26, D32).** Limits count per path unless routes share a scope, and every token, code and JWS is its own path, so the public routes share their allowances. The four verifier routes (`GET /verify/{code}`, `POST /verify`, `GET /verify/d/{jws}`, `GET /verify/degree/{short_id}`) share one allowance of 60 a minute per client address. The three issuer documents (`GET /.well-known/jwks.json`, `GET /.well-known/jwt-vc-issuer`, `GET /status-lists/{id}`) share one of 120. `GET /notices/{token}` and `POST /notices/{token}/respond` share one of 30 over every token, so a new token never brings a new allowance. `POST /enrolments/{id}/notices/resend` shares 30 a minute per signed-in user over every enrolment. `POST /credentials/{id}/present` is counted per user and per credential (10 a minute for each of the student's credentials). `GET /privacy/notice` and `POST /students/me/data-requests` have a single path each and read as written.
3. **Credential header and the `countersigned` label (A3.15).** The issuer JWT header is `{"alg": "ES256", "typ": "dc+sd-jwt", "kid": "<issuer kid>"}` as written: `extra_header_parameters` replaces the library's default `typ`. The key-binding JWT keeps `typ` `kb+jwt` and the status list token `statuslist+jwt`. The `countersigned` claim carries the label "Countersigned by" on the wire, in `disclosable`, in `claims` and in the verifier's `disclosed`. The verifier result and the wallet's claim list print that label; the share sheet prints the copy deck's `wallet.field.countersigned` ("Checks that agree (countersigned)"). Copy deck `verify.field.countersigned` now reads "Countersigned by" to match what the verifier prints.
4. **`detail.changed` on the STUDENT check (A3.8).** `changed` is present only on rows 1 and 2 (`notice_state` DENIED and CONFIRMED), like `responded_at`. Rows 3 to 6 do not carry the key.
5. **Resends and delivery (A3.2, A3.5).**
   - The resend `202` lists only the rows the resend created (one QUEUED row per channel), never the enrolment's earlier notices. `resend` is worked out after they exist, so it reads `"allowed": false, "blocked_by": "LIVE"`.
   - A row is created with a placeholder hash. Each delivery try mints a new token and commits its hash before the link is sent. When the try fails, whether it will be retried or ends FAILED, the hash is replaced at once, so the link minted for a failed try never opens the notice; only the link of the try that succeeded works.
   - Delivery outcomes are audited. When a row ends SENT or FAILED, one UPDATE on `notification` is written with no actor and `after: {"delivery_status", "attempts", "last_error"?}`. A try that will be retried writes no entry.
   - `last_error` has three sentences besides the A3.2 table: "No email address on record." and "No linked APAAR on record." when the contact detail is gone by the time of the try, and "DigiLocker is not connected." when the real DigiLocker adapter is selected while `ALLOW_REAL_GOV_APIS` is not true.
6. **Data requests (A3.22).** `GET /data-requests` without `kind` lists CORRECTION and ERASURE requests only, and `total` counts the same set; ACCESS requests are fulfilled at once and are listed only with `kind=ACCESS`. A request's enrolment is stored in `data_requests.payload` as `{"enrolment_id": "<uuid>"}` (`{}` without one); there is no `enrolment_id` column. An `enrolment_id` that is not one of the student's is `422` on `enrolment_id`: "Choose one of your enrolments.".
7. **REQUEST_DOCS email (A3.10).** `{role_word}` in [email.docs_request.body] is "An AICTE officer" when an AICTE officer asks, and "The {region_name} regional office" when a regional officer asks, with the region's `name` ("The Western regional office").
8. **Assign on decided flags (A3.9, A3.13).** The A3.9 table stands: ASSIGN on a CLEARED or CONFIRMED flag is `409 FLAG_TRANSITION_INVALID` for every role, and on an ESCALATED flag only an AICTE officer assigns. `allowed_actions` follows the table, so a decided flag offers an AICTE officer `NOTE` and `REOPEN` and a regional officer `NOTE` only. The action bar shows exactly `allowed_actions`, in its order; copy deck §6 is corrected to match.
9. **Seed replies (A3.28).** `python -m app.seed.replies` applies a YES or NO line to the latest delivered notice of the line's `channel`, else the latest notice of that channel. When the enrolment has no notice on that channel, the reply goes to its notice on the other channel, chosen the same way. A line whose enrolment has no notice at all is reported and skipped. The audit entry carries `via` `demo-seed`.
10. **Known gaps.** The api does not cover these:
    - `StudentNotice` (A3.6) carries no programme code. `/student/notices` takes the code from the matching enrolment in `GET /students/me` to build `{programme_short}`, and prints the programme name without one.
    - A share stopped because CREDENTIAL_SHARE consent was withdrawn is not marked as such. Its `state` is EXPIRED, and the only sign is an `expires_at` earlier than 10 minutes after `created_at`.
    - `ActorRef` has no region, so a history row shows a regional officer's name and role, not the region.
    - No endpoint lists every audit actor. The `/admin/audit` Actor filter offers the officers from `GET /users` and, by email, any other actor on the page in view.
    - The student's comment is not on `EnrolmentNotice` (A3.7). It reaches officers only through the STUDENT_DENIED flag detail, as the officers-only "Comment from the student" fact; enrolment detail reads that flag to show the comment under the notice.
