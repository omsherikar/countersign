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
11. **An officer's revocation holds (A3.18, D26).** `issue_if_eligible` never issues a new Enrolment proof for an enrolment whose earlier proof an officer revoked: reason code ADMIN, or FLAG_CONFIRMED from a confirmed flag. Only ENROLMENT_WITHDRAWN and ENROLMENT_TRANSFERRED, which a later upload can undo by making the enrolment ACTIVE again, let a proof be issued again on its own. Without this, a recheck after a confirmed flag (which is no longer unresolved) would quietly issue a fresh proof.
12. **Enrolment detail shows the proofs (A3.7).** The page lists every proof of the enrolment with its status and, when revoked, the date and reason in the wallet's words (the officer's own text for ADMIN); an AICTE officer revokes an ACTIVE one there with a reason of 5 to 300 characters.
13. **Verify chain (A3.23).** `GET /admin/audit/verify` reads the chain as plain column tuples in chunks of 5,000 (about 4 s for 124,000 entries on the small seed when idle), and the web's `/api` proxy waits up to 120 s, so a busy machine slows the answer instead of failing it.


## Addendum 4 (2026-10-29): Week 4 endpoints and shapes

Implements DECISIONS D34 to D49. Everything below is normative in the same way as sections A to E and Addenda 2 and 3: field names, casing and enum values are exact. The sentences the api writes (row findings, source lines and details, status reasons, next steps, case summaries, signal summaries, error messages) are the copy deck's (`docs/ux/05-copy-deck.md`), named here by id; the api mirrors their English text and the web prints it verbatim. Where this addendum names a copy id the deck does not have yet, it is marked "proposed". The Python interfaces behind these endpoints are in `ENGINES.md` §17; the schema is `DATA_MODEL.md` "Migration 0004". Where this addendum and an earlier section disagree, this addendum wins.

### A4.1 Conventions added

- **Words.** User-facing text says "case" (not flag), "attestation" (not proof or credential) and "dispute" for a student's "I never joined" (D44). The three decisions read "Claim upheld", "Claim corrected" and "Claim withdrawn" everywhere a person reads them (copy deck `flag_status.*`, `case.history.*`); the wire keeps the actions UPHOLD, CORRECT and WITHDRAW and the statuses UPHELD, CORRECTED and WITHDRAWN. Wire names do not change: paths stay `/flags` and `/credentials`, fields stay `flags_open` and `flag_type`, enums stay `FlagType` and `CredentialKind`. Every api message that a page prints verbatim and that named a flag or a proof now says case or attestation (§A4.22).
- **Rows.** The five evidence rows keep their wire names and are always listed in the deck's order: IDENTITY, SEAT, ADMISSION, STUDYING, STUDENT (labels `check.*`: Identity, Seat, Joining record, Credits, Student). This replaces the Week 2 order on every list and detail.
- **Dates inside the sentences the api writes for rows, statuses and next steps** follow the copy deck: `12 Aug` when the date is in the current calendar year (IST, at the time the sentence is written), `12 Aug 2025` otherwise. Every other sentence keeps the `5 Oct 2026` form of §A2.1. Date fields stay `YYYY-MM-DD` and timestamps ISO.
- **Removed from the wire**, everywhere they appeared: the `countersign` block (`score`, "n of m"), `kpis.clear_pct`, the enrolment filters `check_status` and `check_type`, `integrity_index` and `integrity_components` on institutions, the student password login (§A4.12), and the `/university/degrees/*` routes (§A4.15).
- **Redirects.** `GET /auth/digilocker/start` and `GET /auth/digilocker/callback` answer `302` with a `Location` header and may set cookies. The web's `/api` proxy must pass `302` responses through with `Location` and every `Set-Cookie` unchanged and must not follow them (`redirect: "manual"`).
- **A cookie on a public route.** `GET /notices/{token}` stays public, but reads the `cs_access` cookie (and the pending-claim cookie of §A4.12) when one is sent, only to say who is looking (`viewer`, §A4.13).
- **`rules.yaml` additions** (ENGINES §17.1): `reporting.deadline` (`{"2026-27": "2026-09-30"}`; a year that is not listed has its deadline on 30 September of its start year), `signals.anomaly` (`contamination: 0.05`, `n_estimators: 200`, `random_state: 0`, `min_records: 20`) beside the existing `ghost_ring` thresholds, and `eligibility` with each rule's clause (§A4.4). The `integrity_index` block is removed.
- **New enums** (also in §A4.24):
  - `EvidenceState`: `CONFIRMED`, `CONTRADICTED`, `PENDING`, `NOT_YET_DUE`, `NOT_APPLICABLE`, `SOURCE_UNAVAILABLE` (replaces `CheckStatus`; on the wire the field is `state`).
  - `RecordStatus`: `AWAITING_EVIDENCE`, `COUNTERSIGNED`, `UNDER_REVIEW`, `DISPUTED`, in that display order (the deck's legend); precedence is DISPUTED, UNDER_REVIEW, COUNTERSIGNED, AWAITING_EVIDENCE.
  - `FlagStatus`: `OPEN`, `DOCS_REQUESTED`, `ESCALATED`, `UPHELD`, `CORRECTED`, `WITHDRAWN` (replaces `CLEARED` and `CONFIRMED`). Unresolved: OPEN, DOCS_REQUESTED, ESCALATED. Decided: UPHELD, CORRECTED, WITHDRAWN.
  - `CaseAction`: `UPHOLD`, `CORRECT`, `WITHDRAW`, `REQUEST_DOCS`, `ESCALATE`, `NOTE`, `ASSIGN`, `REOPEN`, `COLLEGE_RESPONSE`, `SYSTEM_NOTE` (`CLEAR` and `CONFIRM` are gone).
  - `FlagType` gains `NOT_IN_JOINING_RECORD`, `ELIGIBILITY_BREACH`, `MISSING_FROM_UPLOAD`.
  - `CheckSource` gains `ADMISSION_AUTHORITY` and `DIGILOCKER`; `COUNSELLING` is no longer written.
  - `CredentialKind`: `ENROLMENT`, `COMPLETION` (replaces `DEGREE`). `RevokedReasonCode` gains `CLAIM_WITHDRAWN` and `STUDENT_DISPUTE` (`FLAG_CONFIRMED` is no longer written).
  - `DeadlineState`: `NOT_DUE`, `ON_TIME`, `LATE`, `OVERDUE`. `SignalType`: `GHOST_RING`, `ANOMALY`. `SignalStatus`: `NEW`, `CASE_OPENED`, `DISMISSED`. `VersionSource`: `UPLOAD`, `DECISION`, `SEED`. `NoticeMatch`: `MATCH`, `SOMEONE_ELSE`, `CLAIM_NEEDED`. `CaseScope`: `RECORD`, `MULTI_RECORD`, `INSTITUTION`. `DocsKind`: `ADMISSION`, `JOINING`, `IDENTITY`, `ELIGIBILITY`, `CREDITS`, `OTHER`.
  - Reason codes per decision: §A4.9.

### A4.2 Evidence rows (D34)

A row is one fact about one enrolment. Enrolment detail carries five full rows in row order (empty before the first evaluation):

```json
{
  "type": "ADMISSION",
  "state": "CONTRADICTED",
  "finding": "not found",
  "source_line": "State admission authority · 28 Oct",
  "summary": "Not found in the Maharashtra admission authority's joining record for CSE (2026-27) after the reporting deadline of 30 Sep.",
  "supplied_by": "State admission authority",
  "observed_at": "2026-10-28T10:02:18Z",
  "independent": true,
  "resolved": null,
  "source": "ADMISSION_AUTHORITY",
  "checked_at": "2026-10-28T10:02:18Z",
  "attempts": 0,
  "detail": { "summary": "...", "finding": "not found", "source_line": "State admission authority · 28 Oct", "basis": "NOT_IN_JOINING_RECORD", "joining_year": "2026-27", "deadline": "2026-09-30", "published": true, "case_type": "NOT_IN_JOINING_RECORD" }
}
```

- `finding`: the short phrase the card prints after the state word (`evidence.with_finding`), from `check.finding.*`, or null when the deck gives none. `source_line`: the "Source and date" cell, from `source_line.*`, with `{date}` the row's `observed_at`. `summary`: the detail sentence, from `check.detail.*`. All three are written by the api (stored in `detail.finding`, `detail.source_line` and `detail.summary`) and printed verbatim; the web never rebuilds them.
- `supplied_by`: the source in words, the provenance the rule and the reports read ("APAAR registry", "College upload", "AICTE approval v2, 2026-27 (Seat Ledger, derived)", "State admission authority", "ABC, issued by Maharashtra State Technical University", "Student via DigiLocker sign-in", "Study in India"); `""` when no source was consulted.
- `observed_at`: when that source supplied the fact (table below). It stays the same while a later evaluation gives the same state and the same `supplied_by`, and moves when either changes, so `source_line` stays stable too.
- `independent`: true when the fact does not come from the institution that made the claim (D38). The evidence rule reads it for Joining record, Credits and Student. The card shows the marker only on CONFIRMED and CONTRADICTED rows and never on the Seat row (copy deck §21).
- `resolved`: null, or `{"outcome": "UPHELD", "case_id", "case_action_seq", "reason_code", "at", "by": {"id", "name", "role"}, "line": "Claim upheld by an officer on 31 Oct"}` when an officer upheld the claim against this row (D43). `line` is `evidence.resolved.UPHELD` filled with `at`; the state stays CONTRADICTED. It is cleared when the row's state changes or the case is reopened.
- `source` (`CheckSource`), `checked_at` (the last evaluation that changed the row) and `attempts` (evaluations that met an unavailable source) keep their Week 2 meaning.
- `detail` keeps the Week 2 and 3 keys and adds `finding`, `source_line`, `basis` (always: the code naming why the row has its state, §A4.4), `approval_id`, `approval_version`, `seat_code`, `seat_type`, `eligibility_rule`, `reported`, `joining_year`, `joined_on`, `round`, `route`, `route_mismatch`, `deadline`, `published`, `issuer`, `issuer_name`, `self_issued`, `claimed_at`, `reviewed_by_officer`, `case_type` (the case the row raised, when it raised one). `flag_type` and `flag_dedupe_key` stay on the Seat row.

Lists carry the brief form, five in row order once evaluated (`resolved` is a boolean here):

```json
{ "type": "ADMISSION", "state": "CONFIRMED", "finding": "joined 2 Aug", "independent": true, "resolved": false }
```

Provenance per row (the `source_line` ids are copy deck §15):

| row | state | `supplied_by` | `observed_at` | `independent` | `source_line` |
|---|---|---|---|---|---|
| IDENTITY | CONFIRMED, CONTRADICTED or PENDING through the registry | `APAAR registry` | the registry call | true | `source_line.APAAR` |
| IDENTITY | CONTRADICTED, malformed APAAR | `College upload` | the upload | false | `source_line.COLLEGE_UPLOAD` |
| IDENTITY | CONFIRMED through a DigiLocker claim (D36) | `Student via DigiLocker sign-in` | the claim | true | `source_line.STUDENT_DIGILOCKER` |
| IDENTITY | CONFIRMED or PENDING through Study in India | `Study in India` | the call | true | `source_line.SII` |
| IDENTITY | NOT_APPLICABLE (no APAAR, not claimed) | `""` | null | false | `source_line.na.IDENTITY` |
| any of IDENTITY, ADMISSION, STUDYING | SOURCE_UNAVAILABLE | the source's words | the failed call | false | `source_line.unavailable` |
| SEAT | any | `AICTE approval v{version}, {cohort_year} (Seat Ledger, derived)` | the evaluation that derived it | false | `source_line.SEAT_LEDGER` |
| ADMISSION | CONFIRMED, CONTRADICTED, PENDING through the joining record | `State admission authority` | the call | true | `source_line.ADMISSION_AUTHORITY` |
| ADMISSION | NOT_YET_DUE, or PENDING because nothing is published | `State admission authority` | the call | false | `source_line.not_due.ADMISSION` |
| ADMISSION | through Study in India | `Study in India` | the call | true | `source_line.SII` |
| STUDYING | CONFIRMED, PENDING, CONTRADICTED | `ABC, issued by {issuer_name}` (several issuers joined with "and"); `ABC, issued by {institution_name} (the college itself)` when the claiming college issued any semester read | the latest `uploaded_at` among the semesters read | true only when no semester read was issued by the claiming institution | `source_line.ABC`, or `source_line.ABC_self` |
| STUDYING | NOT_YET_DUE | `""` | null | false | `source_line.not_due.STUDYING` or `source_line.not_due.STUDYING_lateral` |
| STUDYING | NOT_APPLICABLE | `""` | null | false | `source_line.na.STUDYING` or `source_line.na.STUDYING_abc` |
| STUDENT | CONFIRMED, CONTRADICTED | `Student via DigiLocker sign-in` | the deciding answer | true | `source_line.STUDENT_DIGILOCKER` |
| STUDENT | PENDING | `""` | null | false | `source_line.STUDENT.not_sent`, `.sent` or `.expired` |

Placeholders the source lines and details use besides the deck's: `{version}` the cohort approval's `current_version`; `{deadline_date}` the reporting deadline of the joining year (§A4.18); `{issuer_name}` the issuing body's name from ABC; `{institution_name}` the claiming institution.

### A4.3 The record status (D35)

Every enrolment carries:

```json
"record_status": "DISPUTED",
"status_reason": "The student said they never joined, after signing in with DigiLocker on 22 Aug.",
"next_step": "College asked for admission documents by 29 Aug.",
"record_status_at": "2026-10-29T06:10:00Z"
```

For an enrolment that is not ACTIVE, `record_status` and `status_reason` are null and `next_step` is `next_step.withdrawn` after a withdrawal by decision, else null; the record card shows `record.withdrawn_banner` or `record.withdrawn_upload_banner` from `status` and `status_date`.

**Words the rule uses.**

- A case **names** a record when the case's `enrolment_id` is the record, or the record is in its `related_enrolment_ids` and the case is against the record's institution (the rule enrolment rows already use, §A2.10). MISSING_FROM_UPLOAD and ANOMALY cases name no record. Signals name nothing.
- A row is **unresolved-contradicted** when its state is CONTRADICTED and `resolved` is null.
- **Identity is confirmed** when the IDENTITY row is CONFIRMED, or is PENDING with `needs_review` and `resolved` set (an officer upheld a name that scored 75 to 89 against the registry, §A4.10).
- **Independent enrolment evidence** is an ADMISSION, STUDYING or STUDENT row that is CONFIRMED and `independent`.

**The rule**, first match wins:

| # | status | when |
|---|---|---|
| 1 | DISPUTED | the STUDENT row is unresolved-contradicted and an unresolved STUDENT_DENIED case names the record |
| 2 | UNDER_REVIEW | any row is unresolved-contradicted, or any unresolved case names the record, whatever its severity |
| 3 | COUNTERSIGNED | identity is confirmed, SEAT is CONFIRMED, and there is independent enrolment evidence |
| 4 | AWAITING_EVIDENCE | otherwise (also before the first evaluation) |

An officer's decision is never evidence: an upheld row stays CONTRADICTED and only stops counting as unresolved, so an upheld record still needs independent enrolment evidence to be COUNTERSIGNED.

**`status_reason`** is written from copy deck §21 `status_reason.*`:

| status | deciding item | copy id |
|---|---|---|
| DISPUTED | the STUDENT row (`{reply_date}` its `observed_at`) | `status_reason.DISPUTED` |
| UNDER_REVIEW | the first unresolved-contradicted row in row order (`{check}` its label, `{finding}` its finding) | `status_reason.UNDER_REVIEW.row` |
| UNDER_REVIEW | else the most severe unresolved case naming it, oldest first on a tie | `status_reason.UNDER_REVIEW.case` |
| COUNTERSIGNED | the confirmed independent rows (`{independent_rows}` as the deck says) | `status_reason.COUNTERSIGNED` |
| AWAITING_EVIDENCE | identity not confirmed (`{finding}` the Identity row's finding, or its `source_line` when it has no finding) | `status_reason.AWAITING_EVIDENCE.identity` |
| AWAITING_EVIDENCE | SEAT not CONFIRMED (the same for the Seat row) | `status_reason.AWAITING_EVIDENCE.seat` |
| AWAITING_EVIDENCE | a row was upheld and nothing independent confirms the record (`{date}` the decision) | `status_reason.AWAITING_EVIDENCE.upheld` |
| AWAITING_EVIDENCE | the only CONFIRMED enrolment row comes from the college itself | `status_reason.AWAITING_EVIDENCE.only_self` |
| AWAITING_EVIDENCE | otherwise, and before the first evaluation | `status_reason.AWAITING_EVIDENCE.independent` |

**`next_step`** is written from copy deck §21 `next_step.*`. For DISPUTED and UNDER_REVIEW it follows the deciding case: the STUDENT_DENIED case, the unresolved case named by the deciding row's `detail.case_type`, else the deciding case of the table above.

| the deciding case | copy id |
|---|---|
| DOCS_REQUESTED, no response, due date today or later (`{docs_words}` from the request's `docs_kind`) | `next_step.docs_requested` |
| DOCS_REQUESTED, no response, no due date | `next_step.docs_requested_no_date` |
| DOCS_REQUESTED, no response, the due date has passed | `next_step.docs_overdue` |
| DOCS_REQUESTED, the college responded (`{date}` the latest response) | `next_step.responded` |
| ESCALATED (`{date}` the escalation) | `next_step.escalated` |
| OPEN, STUDENT_DENIED | `next_step.dispute_open` |
| OPEN, any other type | `next_step.case_open` |
| none unresolved: the case was decided, then the row was contradicted again | proposed `next_step.case_reopen`: "Waiting for an officer to reopen the {case_name} case." |

For AWAITING_EVIDENCE it comes from the first missing evidence, in the order identity, seat, ADMISSION, STUDYING, STUDENT (rows that are NOT_APPLICABLE, or CONFIRMED but not independent, are skipped):

| row and state | copy id |
|---|---|
| IDENTITY NOT_APPLICABLE | `next_step.identity_claim` |
| IDENTITY, ADMISSION or STUDYING SOURCE_UNAVAILABLE | `next_step.source_unavailable` |
| SEAT PENDING | `next_step.seat_tfw` |
| ADMISSION PENDING, not yet in a published record | `next_step.joining_record` |
| ADMISSION NOT_YET_DUE | `next_step.joining_deadline` |
| ADMISSION PENDING, nothing published and the deadline has passed | `next_step.joining_record` |
| STUDYING NOT_YET_DUE or PENDING (`{issuer_name}` the issuer of the student's latest credits, else the institution's affiliating university, else "ABC"; `{sem}` the next semester expected) | `next_step.credits` |
| STUDENT PENDING with a notice sent | `next_step.student` |
| STUDENT PENDING with no notice sent | proposed `next_step.student_not_sent`: "Waiting for evidence independent of the college; no notice has reached the student yet." |
| nothing left that could become independent evidence | proposed `next_step.no_route`: "Waiting for evidence independent of the college." |

COUNTERSIGNED: `next_step.none`.

**When it is recomputed.** In the same transaction as any change to a row (an upload, a recheck, a reply, a claim, a correction), to a case naming the record (an engine raising or refreshing it, any officer action including NOTE and ASSIGN, a college response, a case opened from a signal) or to the enrolment itself (ENGINES §17.2). `record_status_at` moves only when `record_status` changes. A change of status writes an audit UPDATE on `enrolment` with `before` and `after` `{"record_status"}`.

### A4.4 Row states, findings and their cases

Replaces the table of §A2.14 and rows 1 to 6 of §A3.8. Each `basis` names one row of copy deck §15: the api writes `finding` from `check.finding.<case>`, `source_line` from the source line that row names, and `summary` from `check.detail.<case>`. The deck's placeholders are filled as it says.

| row | state | `basis` | copy deck §15 row | case raised |
|---|---|---|---|---|
| IDENTITY, ADMISSION, STUDYING | SOURCE_UNAVAILABLE | `SOURCE_UNAVAILABLE` | `check.detail.unavailable` | |
| IDENTITY | CONFIRMED | `APAAR_MATCH` | `IDENTITY.confirmed` | |
| IDENTITY | PENDING (`needs_review`) | `NAME_REVIEW` | `IDENTITY.pending_review` | NAME_MISMATCH, LOW |
| IDENTITY | CONTRADICTED | `APAAR_UNKNOWN` | `IDENTITY.contradicted_not_found` | INVALID_APAAR, HIGH |
| IDENTITY | CONTRADICTED | `APAAR_MALFORMED` | `IDENTITY.contradicted_malformed` | INVALID_APAAR, MEDIUM |
| IDENTITY | CONTRADICTED | `NAME_MISMATCH` | `IDENTITY.contradicted_name` | NAME_MISMATCH, MEDIUM |
| IDENTITY | CONTRADICTED | `DOB_MISMATCH` | `IDENTITY.contradicted_dob` | NAME_MISMATCH, MEDIUM |
| IDENTITY | NOT_APPLICABLE | `NO_APAAR` | `IDENTITY.na_no_apaar` | |
| IDENTITY | CONFIRMED | `DIGILOCKER_CLAIM` | `IDENTITY.confirmed_digilocker` | |
| IDENTITY | CONFIRMED | `SII_MATCH` | `IDENTITY.confirmed_sii` | |
| IDENTITY | PENDING | `SII_NONE` | proposed `IDENTITY.pending_sii`: finding none; source line `source_line.SII`; "Study in India has no admission on record for this passport; see the Joining record row." | |
| SEAT | CONFIRMED | `FITS` | `SEAT.confirmed` | |
| SEAT | CONTRADICTED | `NO_SEAT` | `SEAT.contradicted_no_seat` | EXCESS_ADMISSION or QUOTA_BREACH (raised by the FLAGS stage, §A2.17) |
| SEAT | CONTRADICTED | `NO_POOL` | `SEAT.contradicted_no_pool` | QUOTA_BREACH |
| SEAT | CONTRADICTED | `NOT_ELIGIBLE` | `SEAT.contradicted_eligibility` | ELIGIBILITY_BREACH, MEDIUM; HIGH for an INTERNATIONAL seat |
| SEAT | PENDING | `TFW_NOT_REPORTED` | `SEAT.pending_tfw` | |
| ADMISSION | CONFIRMED | `JOINED` | `ADMISSION.confirmed` | |
| ADMISSION | PENDING | `NOT_YET_IN_RECORD` | `ADMISSION.pending` (not found, today on or before the deadline) | |
| ADMISSION | NOT_YET_DUE | `NOT_PUBLISHED` | `ADMISSION.not_yet_due` (`published: false`, today on or before the deadline) | |
| ADMISSION | PENDING | `NOT_PUBLISHED_LATE` | proposed `ADMISSION.pending_unpublished`: finding "not published yet"; source line `source_line.not_due.ADMISSION`; "The {state_name} admission authority has not published its joining record for {academic_year}; it was due by {deadline_date}." (`published: false` after the deadline; the authority's delay is never the student's contradiction) | |
| ADMISSION | CONTRADICTED | `NOT_IN_JOINING_RECORD` | `ADMISSION.contradicted` (not found in a published record after the deadline; source line "State admission authority · {date checked}") | NOT_IN_JOINING_RECORD, MEDIUM |
| ADMISSION | CONFIRMED | `SII_ADMITTED` | `ADMISSION.confirmed_sii` | |
| ADMISSION | CONTRADICTED | `SII_NOT_ADMITTED` | `ADMISSION.contradicted_sii` | NOT_IN_JOINING_RECORD, MEDIUM |
| STUDYING | NOT_YET_DUE | `FIRST_YEAR` | `STUDYING.not_yet_due` | |
| STUDYING | NOT_YET_DUE | `LATERAL_FIRST_YEAR` | `STUDYING.not_yet_due_lateral` | |
| STUDYING | NOT_APPLICABLE | `NO_APAAR` | `STUDYING.na_no_apaar` | |
| STUDYING | NOT_APPLICABLE | `ABC_UNKNOWN` | `STUDYING.na_abc_unknown` | |
| STUDYING | CONFIRMED | `CREDITS` | `STUDYING.confirmed` | |
| STUDYING | CONFIRMED | `CREDITS_SELF_ISSUED` | `STUDYING.confirmed_self` (`self_issued: true`, `independent: false`) | |
| STUDYING | PENDING | `ONE_SEMESTER_MISSING` | `STUDYING.pending` | |
| STUDYING | CONTRADICTED | `NO_ACADEMIC_ACTIVITY` | `STUDYING.contradicted` | NO_ACADEMIC_ACTIVITY, MEDIUM |
| STUDENT | CONTRADICTED | `DENIED` | `STUDENT.contradicted` | STUDENT_DENIED, HIGH |
| STUDENT | CONFIRMED | `CONFIRMED` | `STUDENT.confirmed` | |
| STUDENT | CONFIRMED | `CONFIRMED_CHANGED` | `STUDENT.confirmed_changed` (No changed to Yes; the case keeps its status) | |
| STUDENT | PENDING | `UNREACHABLE` | `STUDENT.pending_not_sent` (no email and no linked APAAR: no notice can be sent; the student can still sign in and answer) | |
| STUDENT | PENDING | `NOT_SENT` | `STUDENT.pending_not_sent` | |
| STUDENT | PENDING | `SENT` | `STUDENT.pending_sent` | |
| STUDENT | PENDING | `EXPIRED` | `STUDENT.pending_expired` | |

- Every route except INTERNATIONAL reads the joining record (D39); the counselling list is no longer called. `route_mismatch: true` (with `route` the authority's route) is set when the authority's route differs from the upload's; the row stays CONFIRMED.
- `{round_words}` in `ADMISSION.confirmed`: "round {round}" for a counselling joining, "{route_word} admission approved by the state" otherwise (copy deck §15).
- The STUDENT row keeps the `notice_state`, `channel`, `sent_at`, `responded_at` and `changed` keys of §A3.8 and its rules (a No beats a Yes, one change within 7 days). Every answer now comes from a student signed in through DigiLocker (§A4.13).
- Eligibility rules for the SEAT row (D41), checked when the enrolment holds a seat; `eligibility_rule` names the rule, `reported` gives the markers, `{reported_word}` is the deck's `eligibility.word.*` and `{clause}` the rule's clause from `rules.yaml` `eligibility`:

| `eligibility_rule` | breach when | `{reported_word}` | clause |
|---|---|---|---|
| `INTERNATIONAL_CIWG` | an INTERNATIONAL seat held by a student of nationality `IN` not marked `ciwg` | `eligibility.word.NOT_MARKED` | APH 2024-27 cl. 2.9 |
| `NRI_STATUS` | an NRI seat held by a row not marked `nri_sponsored` (blank or no) | `eligibility.word.NOT_MARKED` | APH 2024-27 cl. 2.8(b) |
| `TFW_INCOME` | a TFW seat with `tfw_income_certified` = no | "without a family income certificate" | APH 2024-27 cl. 6.42(d) |

  A blank `tfw_income_certified` on a TFW seat is the PENDING row above, not a breach. A CIWG student is an INTERNATIONAL-route row with nationality `IN` and `ciwg` yes; only CIWG students take the CIWG-reserved third of the international seats (replaces the rule of §A2.2 that read CIWG from route and nationality alone).
### A4.5 Enrolment list changes (`GET /institutions/{id}/enrolments`, A2.10)

Rows lose `countersign` and gain the record and the brief rows:

```json
{
  "id": "e1e1e1e1-5555-4666-8777-888899990000",
  "student": { "id": "st1...", "name": "Ravi Kumar Sharma", "apaar_masked": "XXXX XXXX 4417", "consent_status": "LINKED", "provisional_id": null, "nationality": "IN" },
  "programme_id": "p1...", "programme_code": "CSE",
  "academic_year": "2026-27", "cohort_year": "2026-27", "year_of_study": 1,
  "admission_route": "COUNSELLING", "counselling_ref": "MHCET-2026-R1-004512", "category": "GENERAL",
  "eligibility": { "tfw_income_certified": null, "nri_sponsored": null, "ciwg": null },
  "seat_code": "CSE-R-001", "status": "ACTIVE", "admission_date": "2026-08-02", "status_date": "2026-10-28",
  "uploaded_at": "2026-10-28T10:02:14Z", "upload_batch_id": "b7c1...", "source_row_no": 2,
  "record_status": "COUNTERSIGNED",
  "status_reason": "Identity, seat and the joining record confirm the record, and nothing is unresolved.",
  "next_step": "None. The evidence is complete.",
  "record_status_at": "2026-10-28T10:02:21Z",
  "checks": [
    { "type": "IDENTITY", "state": "CONFIRMED", "finding": null, "independent": true, "resolved": false },
    { "type": "SEAT", "state": "CONFIRMED", "finding": "fits approved intake", "independent": false, "resolved": false },
    { "type": "ADMISSION", "state": "CONFIRMED", "finding": "joined 2 Aug", "independent": true, "resolved": false },
    { "type": "STUDYING", "state": "NOT_YET_DUE", "finding": null, "independent": false, "resolved": false },
    { "type": "STUDENT", "state": "PENDING", "finding": "no answer yet", "independent": false, "resolved": false }
  ],
  "flags": []
}
```

- `checks` is in row order (IDENTITY, SEAT, ADMISSION, STUDYING, STUDENT); `[]` before the first evaluation.
- `eligibility` gives what the college reported (null: not reported).
- Filters: `record_status` (one value or a comma-separated list) replaces `check_status` and `check_type`, which are ignored if sent. `flagged`, `seated` and the Week 1 and 2 filters stay.
- Sorts: `status_priority` (DISPUTED, UNDER_REVIEW, AWAITING_EVIDENCE, COUNTERSIGNED, oldest `record_status_at` first within each; copy deck `record_status.sort.attention`) joins `name_asc` (default), `year_desc`, `route_asc`.
- The page envelope gains `status_counts`: `{"AWAITING_EVIDENCE": n, "COUNTERSIGNED": n, "UNDER_REVIEW": n, "DISPUTED": n}` over ACTIVE enrolments matching every filter except `record_status` and `status`, so the page's status tabs show their counts.

`GET /students/me` (A3.6): each `enrolments[]` item loses `countersign` and gains `record_status`, `status_reason`, `next_step`, `checks` (brief), `response` (the current Yes or No the student gave on this enrolment, or null), `can_respond` (true when ACTIVE) and `claimed` (true when the student's identity on this record came from a DigiLocker claim). The body gains `signed_in_with: "DIGILOCKER"`.

### A4.6 Enrolment detail changes (`GET /enrolments/{id}`, A2.11, A3.7)

The detail is the record card (D49). It loses `countersign`; `checks` becomes the five full rows of §A4.2 in row order; and it gains:

```json
"record_status": "DISPUTED",
"status_reason": "The student said they never joined, after signing in with DigiLocker on 22 Aug.",
"next_step": "College asked for admission documents by 29 Aug.",
"record_status_at": "2026-10-29T06:10:00Z",
"eligibility": { "tfw_income_certified": null, "nri_sponsored": null, "ciwg": null },
"approval": { "id": "ap1...", "academic_year": "2026-27", "version": 2, "approved_intake": 120, "effective_from": "2026-05-20", "source": "AICTE EoA 2026-27, revised" },
"claim": null,
"versions": [ { "...EnrolmentVersion (§A4.7)..." } ],
"history_count": 3
```

- `approval`: the cohort approval the Seat row was checked against, at its current version; null when the programme has none for the cohort.
- `claim`: for a record without a linked APAAR, `{"claimed": true, "claimed_at": "..."}` once the student claimed it through DigiLocker, `{"claimed": false, "claimed_at": null}` before; null for a record with a linked APAAR or an international one.
- `versions`: the 20 most recent versions, newest first, as in §A4.7 (the History section of the card); `history_count`: how many there are in all, paged by `GET /enrolments/{id}/history`.
- `flags` stays (every case naming the record, any status, `FlagSummary` with the new statuses).
- `credentials` stays (the card's attestations), with the kinds and reason codes of §A4.14.

**Recheck endpoints** (A2.12, A2.13). A recheck re-runs every IDENTITY, SEAT, ADMISSION and STUDYING row that is PENDING, NOT_YET_DUE or SOURCE_UNAVAILABLE (STUDENT is still never rechecked), then recomputes the record status, then calls attestation issuance. That is also how rows that waited for the reporting deadline move on: there is no scheduler.

```json
200 {
  "enrolment_id": "e1e1e1e1-5555-4666-8777-888899990000",
  "rechecked": 1,
  "results": [ { "type": "ADMISSION", "before": "PENDING", "after": "CONTRADICTED" } ],
  "flags_raised": 1,
  "record_status": "UNDER_REVIEW",
  "checks": [ { "type": "IDENTITY", "state": "CONFIRMED", "finding": null, "independent": true, "resolved": false }, "... five ..." ]
}
```

`POST /institutions/{id}/recheck` answers with `outcomes` in place of `now_pass`, `now_fail`, `now_na` and `still_pending`:

```json
200 {
  "institution_id": "a0b1c2d3-1111-4222-8333-444455556666", "academic_year": "2026-27",
  "enrolments": 214, "rechecked": 214,
  "outcomes": { "CONFIRMED": 200, "CONTRADICTED": 6, "PENDING": 0, "NOT_YET_DUE": 0, "NOT_APPLICABLE": 0, "SOURCE_UNAVAILABLE": 8 },
  "flags_raised": 6, "duration_ms": 1830
}
```

### A4.7 `GET /enrolments/{id}/history`

Same roles, scope and 404 as `GET /enrolments/{id}`; writes the same READ audit entry for the student. Query `page`, `page_size`. The enrolment's `enrolment_versions`, newest first:

```json
200 {
  "items": [
    {
      "version": 3, "at": "2026-10-30T09:12:00Z", "source": "DECISION",
      "actor": { "id": "u2u2...", "name": "Regional Officer, Western Region", "role": "RO_OFFICER" },
      "batch": null,
      "case": { "id": "f9f9...", "type": "NAME_MISMATCH", "action": "CORRECT", "case_action_seq": 51, "reason_code": "DATA_ENTRY_ERROR" },
      "changes": [ { "field": "name", "before": "Ravi Kumar Sharmaa", "after": "Ravi Kumar Sharma" } ]
    },
    {
      "version": 2, "at": "2026-10-20T08:00:00Z", "source": "UPLOAD",
      "actor": { "id": "6f1c...", "name": "Registrar, ABC College of Engineering", "role": "INSTITUTION" },
      "batch": { "id": "b8b8...", "filename": "1-ABC-0001_2026-27_update1.csv", "row_no": 7 },
      "case": null,
      "changes": [ { "field": "admission_route", "before": "SPOT", "after": "MANAGEMENT" } ]
    },
    {
      "version": 1, "at": "2026-10-28T10:02:14Z", "source": "SEED",
      "actor": null,
      "batch": { "id": "b7c1...", "filename": "1-ABC-0001_2026-27.csv", "row_no": 2 },
      "case": null,
      "changes": [ { "field": "year_of_study", "before": null, "after": 1 }, "... every versioned field ..." ]
    }
  ],
  "total": 3, "page": 1, "page_size": 25
}
```

- Versioned fields, in this order: `name`, `dob`, `apaar_masked`, `consent_status`, `year_of_study`, `admission_route`, `counselling_ref`, `category`, `admission_date`, `status`, `status_date`, `tfw_income_certified`, `nri_sponsored`, `ciwg`. Derived fields (seat, cohort year, record status) are never versions; the seat history is the Seat Ledger's.
- `changes` lists only what changed (version 1 lists every field with `before: null`). Values are as stored, except that an APAAR is only ever `XXXX XXXX 4417`; never a mobile number, an email address or an address.
- `actor` is null for SEED versions. `case` is set for DECISION versions; `batch` for UPLOAD and SEED versions (`row_no` the file's row).
- For an INSTITUTION caller, a DECISION version's `actor` shows the officer's role and name as the case history does (§A3.13).

### A4.8 Case transitions (D43)

Replaces the table of §A3.9. `A` = AICTE_ADMIN, `R` = RO_OFFICER (cases of institutions in its region), `I` = INSTITUTION (its own cases). "=" means the status does not change. "MR" marks the multi-record rule of §A4.10: on a multi-record case WITHDRAW and CORRECT keep the case's status while a named record is still outstanding.

| from \ action | `UPHOLD` | `CORRECT` | `WITHDRAW` | `REQUEST_DOCS` | `ESCALATE` | `NOTE` | `ASSIGN` | `REOPEN` | `COLLEGE_RESPONSE` |
|---|---|---|---|---|---|---|---|---|---|
| OPEN | UPHELD: A, R | CORRECTED (MR): A, R | WITHDRAWN (MR): A, R | DOCS_REQUESTED: A, R | ESCALATED: A, R | =: A, R | =: A, R | 409 | 409 |
| DOCS_REQUESTED | UPHELD: A, R | CORRECTED (MR): A, R | WITHDRAWN (MR): A, R | DOCS_REQUESTED: A, R | ESCALATED: A, R | =: A, R | =: A, R | 409 | =: I |
| ESCALATED | UPHELD: A | CORRECTED (MR): A | WITHDRAWN (MR): A | DOCS_REQUESTED: A | 409 | =: A, R | =: A | 409 | 409 |
| UPHELD, CORRECTED, WITHDRAWN | 409 | 409 | 409 | 409 | 409 | =: A, R | 409 | OPEN: A | 409 |

- 403 versus 409, scope 404, and the order of answers are as §A3.9 and §A3.26. A decision the table allows from the status but that does not apply to the case's type (§A4.10) is `409 DECISION_NOT_AVAILABLE`.
- **Who reads the note.** Notes on UPHOLD, CORRECT, WITHDRAW and REQUEST_DOCS are shown to the college; notes on ESCALATE, NOTE and REOPEN stay with officers; ASSIGN has none. Reason codes and `docs_kind` are shown to everyone who can open the case. A student sees only the outcome of a decision on their dispute (`student.decision.*`), never a note or an officer's name.
- `allowed_actions` (FlagDetail) lists what the table and §A4.10 allow the caller now, in the order `UPHOLD`, `CORRECT`, `WITHDRAW`, `REQUEST_DOCS`, `ESCALATE`, `NOTE`, `ASSIGN`, `REOPEN`.

### A4.9 `POST /flags/{id}/actions`

Roles: `AICTE_ADMIN`, `RO_OFFICER`. Others: 403.

```json
{ "action": "WITHDRAW", "reason_code": "STUDENT_NEVER_JOINED", "note": "The college could not produce an admission record; the student's dispute stands.", "withdrawn_enrolment_ids": ["e7e7e7e7-5555-4666-8777-888899990000"] }
{ "action": "CORRECT", "reason_code": "WRONG_SEAT_CATEGORY", "note": "Admitted through lateral entry, not counselling.", "correction": { "enrolment_id": "e8e8...", "fields": { "admission_route": "LATERAL", "year_of_study": 2 } } }
{ "action": "UPHOLD", "reason_code": "APPROVAL_VERSION_COVERS", "note": "Approval v3 raises the intake to 132.", "approval_version": 3 }
{ "action": "REQUEST_DOCS", "docs_kind": "ADMISSION", "note": "Send the admission register extract for this student.", "due_date": "2026-11-11" }
{ "action": "WITHDRAW", "reason_code": "STUDENT_NEVER_JOINED", "note": "...", "withdrawn_enrolment_ids": ["..."], "dry_run": true }
```

| field | rule |
|---|---|
| `action` | one of the officer actions of §A4.8 |
| `reason_code` | required for UPHOLD, CORRECT, WITHDRAW and ESCALATE: one of that action's codes below. Missing: `422 REASON_REQUIRED`; not one of the action's codes: `422 VALIDATION_ERROR` on `reason_code`. Ignored for the other actions |
| `note` | as §A3.10: 1 to 2,000 characters, required for every action except ASSIGN. Missing on a decision: `422 REASON_REQUIRED` |
| `docs_kind` | REQUEST_DOCS only, required: `ADMISSION`, `JOINING`, `IDENTITY`, `ELIGIBILITY`, `CREDITS` or `OTHER` (copy deck `docs_kind.*`); stored in `case_actions.reason_code` of the REQUEST_DOCS row |
| `due_date` | REQUEST_DOCS only, as §A3.10 |
| `assignee_id` | ASSIGN and ESCALATE, as §A3.10 |
| `withdrawn_enrolment_ids` | WITHDRAW only. Optional on a case that names one record (default: the case's `enrolment_id`); required on a multi-record case, and an empty list is `422 WITHDRAW_NONE_SELECTED`. Each id must be a record the case names, at the case's institution, still ACTIVE; otherwise `409 WITHDRAW_NOT_NAMED` with `details: {"n": <how many are not>, "named_enrolment_ids": [...]}` |
| `correction` | CORRECT only, required: `{"enrolment_id", "fields"}`. `enrolment_id` is optional when the case names one record at its institution, else required and checked like a withdrawal id (`409 WITHDRAW_NOT_NAMED`). `fields` with no key, or only values equal to the current ones: `422 CORRECTION_EMPTY`. A wrong value: `422 CORRECTION_INVALID`, message "{Field word}: {row error message of §A2.3}", `details.field` |
| `approval_version` | UPHOLD on an EXCESS_ADMISSION or QUOTA_BREACH case: required; the version number of the case's approval that covers the admissions (§A4.10). Ignored otherwise |
| `dry_run` | optional, default false. True runs every check and every effect of the action in a transaction that is then rolled back: nothing is stored, audited, emailed or issued, and the answer is `200 {"dry_run": true, "effects": {...}}` (below). Validation and status answers are the same as for a real action |

Reason codes (copy deck §6 `reason.<ACTION>.<CODE>` gives the words):

| action | codes |
|---|---|
| UPHOLD | `DOCUMENTS_SUPPORT_CLAIM`, `SOURCE_RECORD_WRONG`, `NAME_VARIANT`, `PERMITTED_DUAL_PROGRAMME`, `APPROVAL_VERSION_COVERS`, `STUDENT_ANSWER_MISTAKEN`, `MISSING_NOW_UPLOADED`, `OTHER` |
| CORRECT | `UPLOAD_ERROR`, `DOCUMENTS_SHOW_OTHER_VALUE`, `WRONG_SEAT_CATEGORY`, `OTHER` |
| WITHDRAW | `STUDENT_NEVER_JOINED`, `NO_JOINING_EVIDENCE`, `BEYOND_APPROVED_INTAKE`, `NOT_ELIGIBLE_FOR_SEAT`, `DUPLICATE_RECORD`, `NO_RESPONSE`, `OTHER` |
| ESCALATE | `NEEDS_AICTE_DECISION`, `POLICY_QUESTION`, `SPANS_REGIONS`, `REPEATED_PATTERN`, `OTHER` |

CORRECT `fields` (values follow the upload rules of §A2.2):

| key | changes | note |
|---|---|---|
| `name` | the student's name | applies to the student, so to every enrolment of that student; versioned on this one |
| `dob` | the student's date of birth | as `name` |
| `year_of_study` | the enrolment | 1 to the programme's duration; changes the cohort year and so the seat pool |
| `admission_route` | the enrolment | changes the target pool |
| `category` | the enrolment | |
| `counselling_ref` | the enrolment | |
| `admission_date` | the enrolment | not after today |
| `tfw_income_certified`, `nri_sponsored`, `ciwg` | `enrolments.eligibility` | `true`, `false` or `null` (not reported) |

An APAAR, a passport, contact details, the programme and the status cannot be corrected by an officer: the college uploads the row again (D14), and a withdrawal is its own decision.

Checks run in this order: the route's roles (403), body shape (422), case in scope (404 "Case not found."), role and status per §A4.8 (403, then 409 `FLAG_TRANSITION_INVALID`), the case type per §A4.10 (409 `DECISION_NOT_AVAILABLE`), then the field rules above.

Response `200` to a real action: the case as `FlagDetail` (§A4.11) after the action, plus `effects`. The same `effects` answer a dry run. They name every consequence with its real values, which the decision sheets print (copy deck `case.*_change.*`):

```json
"effects": {
  "case_status": "WITHDRAWN",
  "records": [ { "enrolment_id": "e7e7...", "status": "WITHDRAWN", "record_status": null, "status_reason": null } ],
  "version": 2,
  "changes": [],
  "rows_resolved": 0,
  "rows_rerun": 0,
  "seats_released": [ { "enrolment_id": "e7e7...", "seat_code": "CSE-R-087" } ],
  "seats_assigned": [ { "enrolment_id": "e9e9...", "seat_code": "CSE-R-087" } ],
  "attestations_revoked": [ { "enrolment_id": "e7e7...", "credential_id": "c1c1...", "short_id": "7Q2MK4PX" } ],
  "attestations_issued": [],
  "approval": null
}
```

- `case_status`: the case's status after the action (unchanged on a multi-record action that leaves records outstanding).
- `records`: every enrolment whose `status` or `record_status` changed (a backlog record seated by a released seat counts too).
- `version` and `changes`: the version number written (or to be written, on a dry run) and the changed fields `[{field, before, after}]` for a CORRECT; for a WITHDRAW, the version of the first record; else null and `[]`.
- `approval`: `{"version", "approved_intake", "cohort_year", "programme_code"}` for an UPHOLD under an approval version, else null.
- For NOTE, ASSIGN, ESCALATE, REQUEST_DOCS and REOPEN, `effects` lists the records whose status or next step changed and is otherwise empty.

### A4.10 What each decision changes (D43)

**Which row a case covers, and which decisions apply.** "Multi-record" cases name several records and are decided record by record.

| case type | covers row | scope | UPHOLD | CORRECT | WITHDRAW |
|---|---|---|---|---|---|
| EXCESS_ADMISSION | SEAT | MULTI_RECORD | only with an `approval_version` that covers the admissions | yes, one named record at a time | yes, with the record picker |
| QUOTA_BREACH | SEAT | MULTI_RECORD | the same | the same | the same |
| ELIGIBILITY_BREACH | SEAT | RECORD | yes | yes | yes |
| LATE_REFILL | none | RECORD | yes | yes | yes |
| INVALID_APAAR | IDENTITY | RECORD | yes | yes (identity details) | yes |
| NAME_MISMATCH | IDENTITY | RECORD | yes | yes | yes |
| NOT_IN_JOINING_RECORD | ADMISSION | RECORD | yes | yes | yes |
| NO_ACADEMIC_ACTIVITY | STUDYING | RECORD | yes | yes | yes |
| STUDENT_DENIED | STUDENT | RECORD | yes | yes | yes |
| DUPLICATE_WITHIN_UPLOAD | none | RECORD (either of the two) | yes | yes | yes |
| DUPLICATE_CROSS_INSTITUTION | none | RECORD (its own institution's) | yes | yes | yes |
| DUAL_ENROLMENT_ALLOWED | none | RECORD (its own institution's) | yes | yes | yes |
| GHOST_RING (opened from a signal) | none | MULTI_RECORD | yes | yes, one named record at a time | yes, with the record picker |
| MISSING_FROM_UPLOAD | none | INSTITUTION | yes | no | no |
| ANOMALY (opened from a signal) | none | INSTITUTION | yes | no | no |

A version **covers** the admissions of an EXCESS_ADMISSION or QUOTA_BREACH case when it is the approval's current version and, under it, the case's pool has no ACTIVE cohort enrolment without a seat (the backlog was seated when the version was added, §A4.17). Otherwise `409 UPHOLD_NEEDS_VERSION`.

An **outstanding** record of a multi-record case is a named record at the case's institution that is ACTIVE and, for a case that covers a row, whose covered row is unresolved-contradicted (for GHOST_RING: not withdrawn or corrected by this case). On a multi-record case, WITHDRAW and CORRECT move the case to WITHDRAWN or CORRECTED only when no named record is outstanding after the action; otherwise the status stays and the history row records what was done. UPHOLD always decides the whole case.

**Effects, all in the request's transaction** (one commit; the REQUEST_DOCS email after it, as §A3.9):

| action | case | records | seat | attestation | version |
|---|---|---|---|---|---|
| UPHOLD | UPHELD, `resolved_at` | for each named record at the case's institution that is ACTIVE: the covered row, when CONTRADICTED (or PENDING with `needs_review` for NAME_MISMATCH), gets `resolved` | none (an approval version already seated the backlog) | issued when a record becomes COUNTERSIGNED (§A4.14); one revoked by the student's dispute is issued again | none |
| CORRECT | CORRECTED (or unchanged, MR); `case_actions.correction` | the fields are applied; the record's five rows are evaluated again (adapter calls inside the request); the Seat Ledger runs for the record | released or assigned by the ledger when the target pool changed; seat cases of touched pools refreshed | as the new status says | one DECISION version with the changed fields |
| WITHDRAW | WITHDRAWN (or unchanged, MR); `withdrawn_enrolment_ids` | each listed record: `status` WITHDRAWN, `status_date` today (IST), `next_step` `next_step.withdrawn` | its seat released (seat event reason `withdrawn by decision`); the freed seat goes to the pool's backlog, whose Seat rows run again; seat cases refreshed | every live attestation of each listed record revoked with `CLAIM_WITHDRAWN` and the officer | one DECISION version per record: `status`, `status_date` |
| REQUEST_DOCS, ESCALATE, NOTE, ASSIGN, COLLEGE_RESPONSE | as §A3.9 | statuses recomputed (`next_step` follows the case) | none | none | none |
| REOPEN | OPEN, as §A3.9 | `resolved` markers this case set are cleared; statuses recomputed | none | none | none |

- Every record whose rows, case or enrolment changed has its status recomputed before the commit (§A4.3); a record that becomes DISPUTED has its attestation revoked with `STUDENT_DISPUTE` (§A4.14).
- An UPHOLD row stores `{"approval_version": n}` in `case_actions.correction` when it cites a version; the history shows it.
- Audit, in the same transaction: UPDATE on `flag` with `after: {"action", "from_status", "to_status", "case_action_seq", "reason_code"?, "docs_kind"?, "withdrawn_enrolment_ids"?, "fields"? (field names only), "approval_version"?, "assignee_id"?, "due_date"?}`; UPDATE on `enrolment` per record whose status or record status changed (`before`/`after` `{"status", "record_status"}`) and per version written (`after: {"version", "source", "changed": [field names]}`); UPDATE on `check` per row resolved or cleared (`after: {"type", "resolved": true | false}`); the ledger's seat entries and the credentials' revocation entries as before. Notes, names and dates of birth never go into the audit log. A dry run writes nothing.
- Nothing is deleted. Engines still never change a case's status; an engine refresh of a decided case adds the system note of §A3.8.

### A4.11 `GET /flags` and `GET /flags/{id}` changes (A2.15, A2.16, A3.13)

`FlagRow` gains:

```json
"covers": "STUDENT",
"scope": "RECORD",
"decision": { "action": "UPHOLD", "reason_code": "STUDENT_ANSWER_MISTAKEN", "at": "2026-10-31T04:00:00Z" },
"signal_id": null
```

- `covers`: the row type the case covers (§A4.10), or null. `scope`: `RECORD`, `MULTI_RECORD` or `INSTITUTION`. `decision`: the latest UPHOLD, CORRECT or WITHDRAW row while the case is decided, else null. `signal_id`: the signal the case was opened from, else null, and always null for an INSTITUTION caller (a college never sees a signal).
- `status` carries the new values. Filters: `status` accepts the new values, `UNRESOLVED` (as before) and `DECIDED` (UPHELD, CORRECTED, WITHDRAWN); `type` accepts the three new types; new `signal_id` (officers only).
- 404 message: "Case not found." (replaces "Flag not found." everywhere).

`FlagDetail` gains:

- `outstanding_enrolment_ids`: multi-record cases, the outstanding records; else `[]`.
- `approval`: for EXCESS_ADMISSION and QUOTA_BREACH, the case's approval `{"id", "current_version", "approved_intake", "covers": true | false}` (whether the current version covers the admissions, so the Uphold sheet can offer it); else null.
- `missing_students`: for MISSING_FROM_UPLOAD, the list of §A4.18 (name, roll number, programme, joining date); else `[]`.
- `history` items gain `reason_code`, `docs_kind`, `approval_version`, `correction` (`{"enrolment_id", "changes": [{"field", "before", "after"}]}` or null) and `withdrawn_enrolment_ids` (`[]` unless WITHDRAW).

The redaction for INSTITUTION is unchanged (§A3.13): the college sees reason codes, document kinds, its corrections and the withdrawn ids; ASSIGN rows and internal notes stay hidden. For a case opened from a signal it sees only its own students and the case's rule line: facts that name other colleges, the signal's model score and `signal_id` are officers only. Every enrolment row inside a case (`enrolment`, `related_enrolments`) is the §A4.5 row, so it shows each record's status.

**Case texts.** Names, summaries and facts of every case type are the copy deck's §5 (`flag.<TYPE>.name`, `flag.<TYPE>.summary`, the facts table); the engines mirror them. For the new types:

| type | severity | `dedupe_key` | notes |
|---|---|---|---|
| NOT_IN_JOINING_RECORD | MEDIUM | `NOT_IN_JOINING_RECORD:{enrolment_id}` | raised by the ADMISSION row after the deadline, or by a Study in India mismatch (summary then `check.detail.ADMISSION.contradicted_sii`); `rule_source` "State admission authority joining record" or "Study in India" |
| ELIGIBILITY_BREACH | MEDIUM; HIGH for an INTERNATIONAL seat | `ELIGIBILITY_BREACH:{enrolment_id}` | `{allowed_words}` from the rule; `rule_source` the clause |
| MISSING_FROM_UPLOAD | MEDIUM | `MISSING_FROM_UPLOAD:{institution_id}:{academic_year}` | `programme_id`, `enrolment_id` null, `related_enrolment_ids` `[]`; the facts are the deck's four counts; the students are in `missing_students`; when an upload brings some of them in, the refresh adds the system note `case.system_note.missing_updated`; `rule_source` "State admission authority joining record; reporting deadline {deadline_date}" |
| GHOST_RING (from a signal) | chosen by the officer (default HIGH) | `GHOST_RING:{signal_id}:{institution_id}` | summary `flag.GHOST_RING.summary`; facts: the signal's facts about this institution's members, then `Signal`: `Shared contact ring found on {date}` (officers only); `rule_source` the signal's rule |
| ANOMALY (from a signal) | chosen by the officer (default MEDIUM) | `ANOMALY:{signal_id}` | summary `flag.ANOMALY.summary`; facts: the signal's feature lines; `rule_source` the signal's rule |

STUDENT_DENIED keeps §A3.8, with the deck's summaries (`flag.STUDENT_DENIED.summary`, `.summary_changed`) and facts (Signed in with, Notice sent, Answered on, Answer changed, Comment from the student for officers only). `flags_by_type` (dashboard) lists all fifteen types in ARCHITECTURE §9 order.

### A4.12 Student sign-in through DigiLocker (D36, D37)

The api is an OpenID Connect client of DigiLocker (in the demo, mockgov's labelled simulator, §A4.25). Settings: `DIGILOCKER_CLIENT_ID` (default `countersign-demo`), `DIGILOCKER_CLIENT_SECRET`, `DIGILOCKER_AUTHORIZE_URL` (what the browser opens; default `http://localhost:8001/digilocker/oauth/authorize`), `DIGILOCKER_ISSUER` (default `http://localhost:8001/digilocker`); the token call goes through the DigiLocker adapter (`MOCKGOV_URL`). The redirect URI is `{WEB_ORIGIN}/api/auth/digilocker/callback`. Web pages: `/auth/digilocker/return` (where every sign-in lands; public) and `/student/claim`.

**`GET /auth/digilocker/start?next=/student/notices/{token}`** (public, 30 per minute). `next` must be a path starting with `/student`; anything else becomes `/student`. Creates `state` and `nonce` (each 32 random bytes, URL-safe), sets the cookie `cs_dl_state` (a JWT signed with `API_SECRET_KEY` holding `state`, `nonce` and `next`; `HttpOnly`, `SameSite=Lax`, `Path=/`, 10 minutes) and answers `302` to `{DIGILOCKER_AUTHORIZE_URL}?response_type=code&client_id={id}&redirect_uri={uri}&scope=openid&state={state}&nonce={nonce}`.

**`GET /auth/digilocker/callback?code&state`** (public, 30 per minute). Always answers `302` and clears `cs_dl_state`. Failures land on `/auth/digilocker/return?error={code}&next={next}`, where the page prints `err.{code}` and nothing has been recorded:

1. `state` missing or not the cookie's, or the cookie missing or expired: `DIGILOCKER_STATE_INVALID`.
2. DigiLocker sent `error=access_denied` (the person cancelled): `DIGILOCKER_CANCELLED`.
3. The adapter exchanges `code` for the id token and verifies it (signature, `iss`, `aud` = the client id, `exp`, `nonce` = the cookie's); any failure, or DigiLocker unavailable: `DIGILOCKER_FAILED`.
4. A user whose `digilocker_sub` is the token's `sub`: that user is signed in.
5. Else the token carries `apaar_id`, and a student holds that APAAR (`apaar_hmac`) with consent LINKED: that student's STUDENT user (the seeded `student@demo` for Ravi Kumar Sharma, or a new account) gets `digilocker_sub` and is signed in.
6. Else nobody is signed in: the cookie `cs_dl_claim` (a JWT signed with `API_SECRET_KEY` holding `sub`, `name`, `birthdate` and `next`; `HttpOnly`, `SameSite=Lax`, `Path=/`, 15 minutes; never the APAAR) is set, and the answer is `302` to `next` (a notice page then shows `CLAIM_NEEDED`), or to `/student/claim?next={next}` when `next` is not a notice page.

Signing in sets `cs_access` exactly as `POST /auth/login` does (ARCHITECTURE §3), writes a LOGIN audit entry with `after: {"via": "digilocker"}`, and answers `302` to `/auth/digilocker/return?next={next}`, which shows `signin.done` and moves on to `next`. A new account is created as DATA_MODEL `users` says (synthetic `@digilocker.invalid` email, unusable password) with the DigiLocker name, and audited (CREATE on `user`, `after: {"role": "STUDENT", "via": "digilocker"}`); binding an existing account writes UPDATE on `user` with `after: {"digilocker_bound": true}`. The APAAR in the token is used only for the lookup in step 5 and is never stored or logged. One DigiLocker account binds to one student record.

**`GET /auth/digilocker/claim`** (the pending-claim cookie only). `200 {"name": "Asha Patil", "birthdate": "2008-01-14", "next": "/student/notices/AbC..."}`: the DigiLocker identity waiting to claim a record, for the claim page to show. Without a valid cookie: `401 DIGILOCKER_STATE_INVALID`.

**`POST /auth/digilocker/claim`** (the pending-claim cookie only; 5 tries per 15 minutes per DigiLocker subject, then `429 RATE_LIMITED` with `details.retry_after`, which the page shows as `claim.locked`).

```json
{ "provisional_id": "PRV-7Q2MK4PX" }
```

The id is trimmed and upper-cased; one that is not `PRV-` and 8 characters of the provisional alphabet is `422 VALIDATION_ERROR` on `provisional_id` (`claim.format`). Then, in this order:

1. The id must be a student's `provisional_id`, that student's `dob` must equal the token's `birthdate`, and `match_names(record name, DigiLocker name).score` must be at least 75 (name matching supports the claim, the sign-in decides it). Anything else, an unknown id included: `422 CLAIM_NO_MATCH`, with no detail of which part failed.
2. The student has a linked APAAR (its record links through DigiLocker by APAAR, step 5 above): `409 CLAIM_NOT_NEEDED`.
3. The student is already bound to another DigiLocker subject: `409 CLAIM_ALREADY_CLAIMED`.

No pending claim: `401 DIGILOCKER_STATE_INVALID`. Steps 2 and 3 answer only after step 1 matched, so nobody learns which ids exist.

On success, in one transaction: the student's STUDENT user is created or bound (`digilocker_sub`), the IDENTITY row of each of the student's ACTIVE enrolments is evaluated again (CONFIRMED, basis `DIGILOCKER_CLAIM`, §A4.4), their statuses are recomputed and attestations issued where they became COUNTERSIGNED; audit UPDATE on `student` with `after: {"claimed_via": "digilocker", "enrolments": n}` and the LOGIN entry. `cs_access` is set and `cs_dl_claim` cleared. Response `200`:

```json
{ "user": { "...User (A.2)..." }, "next": "/student/notices/AbC...", "claimed": { "student_id": "st9...", "enrolments": [ { "...StudentEnrolment (§A4.5)..." } ] } }
```

**`POST /auth/login`** (A.2). A STUDENT account cannot sign in with a password any more: its email and correct password give the same `401 INVALID_CREDENTIALS` as a wrong password. Every other role is unchanged. The login page's student card links to `/api/auth/digilocker/start?next=/student` (`login.card.student`, `login.digilocker_hint`), and the demo DigiLocker page lists Ravi Kumar Sharma first. `GET /me` and `POST /auth/logout` are unchanged; signing out does not sign the student out of DigiLocker.

### A4.13 Notices behind sign-in (D37)

**`GET /notices/{token}`** (public, A3.3) gains:

```json
"viewer": { "signed_in": true, "name": "Ravi Kumar Sharma", "match": "MATCH" },
"can_answer": true,
"sign_in_url": "/api/auth/digilocker/start?next=/student/notices/AbC...",
"claim_url": null
```

| `viewer` | when | the page (copy deck §23) |
|---|---|---|
| `{"signed_in": false, "name": null, "match": null}` | no `cs_access` and no pending claim | the claim card, `notice.signin_lead` and `notice.signin_button` (`sign_in_url`) |
| `match: "MATCH"` | a STUDENT is signed in and is the notice's student (by APAAR, or by a claim) | `notice.signed_in_as`, then Yes and No as §8 (`can_answer` true while the rules of §A3.4 allow a reply or a change) |
| `match: "CLAIM_NEEDED"` | a pending claim (no student bound yet) and the notice's student has no linked APAAR and is not claimed | `notice.claim_needed_heading`, `notice.claim_needed`, `notice.claim_button` to `claim_url` (`/student/claim?next=/student/notices/{token}`) |
| `match: "SOMEONE_ELSE"` | anyone else signed in (another student, an officer, a registrar), or a pending claim for a notice whose student has a linked APAAR | `notice.someone_else_*`; no buttons; nothing recorded |

`name` is the name DigiLocker returned for the person looking (the signed-in student's account name, or the pending claim's), never the record's name; it is null for anyone who is not a student. The READ audit entry of §A3.3 gains `"match"` in `after`.

**`POST /notices/{token}/respond`** (A3.4) now needs a signed-in STUDENT. In this order: token rules (404 `NOTICE_NOT_FOUND`, 410 `NOTICE_EXPIRED`); no valid `cs_access`: `401 SIGNIN_REQUIRED`; the caller is not a STUDENT, or is not the notice's student: `403 NOTICE_IDENTITY_MISMATCH`; then rules 3 to 5 of §A3.4. Nothing is recorded on 401 or 403. Effects as §A3.4, except that the audit entry has the student as actor and `after.via` `digilocker-sign-in`, and the record status is recomputed (§A4.3). The consent row keeps the channel the notice came by (`NOTICE_EMAIL` or `NOTICE_DIGILOCKER`).

**`POST /students/me/enrolments/{enrolment_id}/respond`** (`STUDENT`, 10 per minute per user). Same body as §A3.4. The student answers a claim on their own enrolments page, with or without a notice link. The enrolment must be the student's (else 404 "Enrolment not found.") and ACTIVE (else `409 CONFLICT`, `details.reason` `NOT_ACTIVE`). The answer goes to the enrolment's latest delivered notice, else its latest notice; when it has none, one notice row is written for it (channel `DIGILOCKER`, `delivery_status` SENT, `sent_at` now, `message` "Answered after DigiLocker sign-in.", a token hash nobody holds), because the Student row is derived from notices. Rules 3 to 5 of §A3.4 then apply to that notice (409 `NOTICE_ALREADY_CHANGED` as there). Response `200`: the enrolment as in `GET /students/me`.

- Notice texts point to sign-in: copy deck `notice.email_body` and `notice.digilocker` say to sign in with DigiLocker to answer. An email to a student without a linked APAAR also carries the provisional id in full, because the student needs it to claim the record (proposed copy `notice.email_provisional_line`: "Your college recorded you without an APAAR. Your provisional ID is {provisional_id}; you need it to claim the record after signing in."); the notice page itself shows it masked.
- After a decision on the student's dispute, `GET /students/me` gives each enrolment `decision`: `{"outcome": "UPHELD" | "CORRECTED" | "WITHDRAWN" | "ESCALATED", "reason_code", "at"}` (the latest decision or escalation of a STUDENT_DENIED case on it), else null, for `student.decision.*`. Never the note or the officer.
- Seeded replies (`python -m app.seed.replies`, D31) stand for answers given after DigiLocker sign-in: they go through the same `apply_reply`, with `via` `demo-seed` and no actor, and the Student row reads them as any answer.
- `GET /students/me/export.json` (A3.22): each enrolment's `checks` items carry `state` (not `status`), `finding`, `source_line`, `supplied_by` and `observed_at`, and each enrolment gains `record_status`, `status_reason` and `history` (its versions as in §A4.7, without `actor`).

### A4.14 Attestations (D44)

- **Words.** The Enrolment proof is the "enrolment attestation"; the Degree proof is the "completion attestation". `kind` is `ENROLMENT` or `COMPLETION`. New completion attestations carry `vct` `countersign:completion:v1`; the verifier reads `countersign:degree:v1` as COMPLETION too.
- **Eligibility** replaces §A3.15 and §16.2's rule: the enrolment is ACTIVE, its `record_status` is COUNTERSIGNED, it holds no unrevoked ENROLMENT attestation, and no earlier ENROLMENT attestation of it was revoked with a code that holds (below). The Student row no longer needs to be CONFIRMED: a record countersigned by its joining record gets an attestation, which the student sees after signing in.
- **When.** Whenever a recomputation (§A4.3) finds a record COUNTERSIGNED: after a reply, a claim, a decision and a recheck at once; for uploads, in the post-batch notices task (ENGINES §17.13), so a 50,000-row batch does not sign attestations inside the upload.
- **The `countersigned` claim** keeps its key and label and now lists the rows that were CONFIRMED at issue, in row order: `{"checks": ["IDENTITY", "SEAT", "ADMISSION"], "on": "2026-10-29"}`, shown as `Identity, Seat and Joining record, as of 29 Oct 2026`.
- **Revocation reason codes** (extends §A3.18):

| `revoked_reason_code` | cause | stored `revoked_reason` | actor | issued again on its own? |
|---|---|---|---|---|
| `ENROLMENT_WITHDRAWN` | the college's upload withdrew the enrolment | the code | the uploader | yes, if the enrolment becomes ACTIVE and COUNTERSIGNED again |
| `ENROLMENT_TRANSFERRED` | the college's upload transferred it | the code | the uploader | yes, as above |
| `CLAIM_WITHDRAWN` | an officer's WITHDRAW (§A4.10) | the code | the officer | no |
| `STUDENT_DISPUTE` | the record became DISPUTED | the code | none | yes, when the dispute is upheld and the record is COUNTERSIGNED again |
| `ADMIN` | `POST /credentials/{id}/revoke` | the officer's text | the officer | no |
| `FLAG_CONFIRMED` | a CONFIRM before Week 4 (no longer written) | the code | the officer | no |

  A record that is UNDER_REVIEW or AWAITING_EVIDENCE keeps a live attestation: only the causes above revoke one, and a pending row never does.
- **Messages** (verbatim on pages) now say attestation: `CREDENTIAL_REVOKED` "This attestation was revoked on {revoked_date} and cannot be shared." and "This attestation is already revoked."; `CREDENTIAL_NOT_ELIGIBLE` "Completion attestations are issued only for graduated students.", "Issue the completion attestation first." and "This attestation expired on {expires_date} and cannot be shared."; `PRESENTATION_NOT_FOUND` "This code is not a Countersign attestation."; 404 "Attestation not found." (replaces "Credential not found.").

### A4.15 Certificate integration and the verifier (D44)

The university pages become certificate integration: the awarding body prints its own certificate and Countersign gives it the masked APAAR and a compact QR that verifies a completion attestation. A completion attestation is still issued for a GRADUATED enrolment of an affiliate (§A3.21): graduate records carry no evidence rows and no record status, so the copy deck's `cert.status.not_eligible` does not occur. Roles and scope are those of §A3.21. The `/university/degrees/*` routes are removed.

| route | replaces | answer |
|---|---|---|
| `GET /university/graduates` | itself | rows as §A3.21 with `attestation` in place of `degree`: `{credential_id, short_id, status, issued_at}` or null; query `attestation=issued \| not_issued` in place of `degree` |
| `POST /university/certificates/{enrolment_id}/issue` | `POST /university/degrees/{enrolment_id}/issue` | as before: `201` with the print data, `200` when one is already active; `409 CREDENTIAL_NOT_ELIGIBLE` `NOT_GRADUATED` |
| `GET /university/certificates/{enrolment_id}` | `GET /university/degrees/{enrolment_id}` | the print data of §A3.21 with `attestation` in place of `degree`, and `lookup_url` `{WEB_ORIGIN}/verify/completion/{short_id}` |
| `GET /university/certificates/{enrolment_id}/block.pdf` | `.../degrees/{enrolment_id}/insert.pdf` | the certificate block (copy deck §11 `cert.print.*`) as one A4 page; filename `certificate-block-{short_id}.pdf`; under the QR `cert.print.attestation_id` and `cert.scan_line`; footer "Sample certificate block generated from synthetic demo data. Countersign does not issue degrees." |

- The compact JWS and its payload `{v, cid, n, p, i, u, y, a}` are unchanged, and so is `GET /verify/d/{jws}`; its result has `kind` `COMPLETION`.
- `GET /verify/completion/{short_id}` replaces `GET /verify/degree/{short_id}` (the old path answers the same, for inserts already printed). Web routes: `/university/certificates/[enrolmentId]/print`, `/verify/completion/[shortId]`.
- Audit `via` values become `certificate-print`, `completion-qr` and `completion-lookup`; the student access log's `what` `DEGREE` becomes `COMPLETION`.

### A4.16 Column mapping (D42)

**`GET /institutions/{id}/column-mapping`**. Roles: `AICTE_ADMIN` (any), `RO_OFFICER` (region), `INSTITUTION` (own). Others 403; outside scope 404 "Institution not found.".

```json
200 {
  "institution_id": "a0b1c2d3-1111-4222-8333-444455556666",
  "mapping": { "Student Name": "name", "D.O.B.": "dob", "Course Code": "programme_code" },
  "updated_at": "2026-10-29T05:00:00Z",
  "updated_by": { "id": "6f1c...", "name": "Registrar, ABC College of Engineering" },
  "columns": [ { "column": "apaar_id", "required": false }, { "column": "name", "required": true }, "... the 22 template columns in order ..." ]
}
```

`mapping` is `{}` and `updated_at`, `updated_by` null when none was saved.

**`PUT /institutions/{id}/column-mapping`**. Roles: `INSTITUTION` (own), `AICTE_ADMIN`. Body `{"mapping": {"<their header>": "<template column>"}, "headers": ["Student Name", "D.O.B.", "..."]}`, replacing the whole mapping (`{}` clears it). `headers` is optional: the header row of the file being mapped, sent by the upload form's mapping step. Rules: at most 60 entries, each header 1 to 120 characters, each value one of the template columns (`422 VALIDATION_ERROR` on `mapping`: "Map to a template column."); two headers mapped to the same column, or two headers that normalise alike: `422 MAPPING_DUPLICATE`, `details.column`; with `headers`, a required column that the headers do not reach after the mapping: `422 MAPPING_INCOMPLETE`, `details.missing_columns`. Audit UPDATE on `institution_column_mapping` with `after: {"headers": n}`. Response `200`: the GET body.

**Uploads with a mapping** (§A2.2, A2.4, A2.5). Each header cell is normalised as §A2.2; a header whose normalised form matches a saved mapping key (also normalised) is read as the mapped column; else a header that is a template column is read as itself; else it is unknown. Then:

- every required column found: unknown headers go to `ignored_columns` as before;
- a required column missing and at least one unknown header: `422 UPLOAD_HEADER_UNMAPPED` "The file has columns Countersign does not recognise. Map them to the template once, then upload again.", `details`: `{"unknown_headers": ["Student Name", "D.O.B."], "missing_columns": ["name", "dob"], "suggestions": [{"header": "Student Name", "column": "name"}, {"header": "D.O.B.", "column": "dob"}]}` (suggestions from the synonym list and fuzzy match of ENGINES §17.9; nothing is saved);
- a required column missing and no unknown header: `422 UPLOAD_HEADER_INVALID` as before.

`POST /uploads/rows` applies the mapping to its keys the same way. `UploadBatch` gains `column_mapping`: `[{"header": "Student Name", "column": "name"}]`, the mapped headers the batch used (stored in `counts.column_mapping`), `[]` when none. `counts` gains `versions` (enrolment versions the batch wrote) and `records` (the record statuses of the batch's ACTIVE enrolments when it finished, the four keys of `RecordStatus`), so the done card can say how many records are countersigned.

**Template columns.** The template gains three optional columns after `admission_date`: `tfw_income_certified`, `nri_sponsored`, `ciwg` (22 columns). Values `yes` or `no` (also `Y`, `N`, `true`, `false`, `1`, `0`, any case); blank means not reported. Any other value is a `BAD_ENUM` WARNING ("{Field word} must be yes or no; recorded as not reported") and the row is kept. `nri_sponsored` yes means the student is an NRI or is sponsored by an NRI. The markers are stored in `enrolments.eligibility` and compared on re-upload like the other enrolment fields.

### A4.17 Approval versions (D41)

**`GET /approvals/{id}/versions`**. Roles: `AICTE_ADMIN`, `RO_OFFICER` (region), `INSTITUTION` (own), `UNIVERSITY` (affiliates). Outside scope 404 "Approval not found.".

```json
200 {
  "approval_id": "ap1...",
  "institution": { "id": "a0b1...", "name": "ABC College of Engineering", "aicte_permanent_id": "1-ABC-0001" },
  "programme": { "id": "p1...", "code": "CSE", "name": "B.Tech Computer Science and Engineering" },
  "academic_year": "2026-27",
  "current_version": 2,
  "items": [
    { "version": 2, "approved_intake": 120, "effective_from": "2026-05-20", "source": "AICTE EoA 2026-27, revised", "created_at": "2026-10-28T10:00:00Z" },
    { "version": 1, "approved_intake": 90, "effective_from": "2026-03-15", "source": "AICTE EoA 2026-27", "created_at": "2026-10-28T10:00:00Z" }
  ]
}
```

**`POST /approvals/{id}/versions`** (`AICTE_ADMIN` only; everyone else 403). Body `{"approved_intake": 132, "effective_from": "2026-11-01", "source": "AICTE EoA 2026-27, second revision"}`: intake 1 to 10,000; `effective_from` not before the current version's ("A new version must take effect after the current one."); `source` 3 to 200 characters. In one transaction (ENGINES §17.5): a new version row, `approvals.approved_intake` and `current_version` updated, every pool's capacity recomputed from `rules.yaml`; a raised pool gets new FREE seats (next seat numbers; CIWG reservation recomputed) and its backlog is seated; a lowered pool loses FREE seats, highest numbers first, a seat with history kept as `RELEASED` (retired); the Seat rows of the approval's enrolments run again (they now cite the new version); seat flags refreshed; statuses recomputed. When a lowered pool would hold fewer seats than it has ASSIGNED: `409 APPROVAL_BELOW_ASSIGNED` "The new intake is below the seats already assigned.", `details: {"intake": <the new intake>, "assigned": <seats assigned across the approval>, "pools": [{"seat_type", "assigned", "new_capacity"}]}` (copy deck `err.APPROVAL_BELOW_ASSIGNED` reads `intake` and `assigned`), and nothing changes. Audit CREATE on `approval_version` and UPDATE on `approval` (`after: {"current_version", "approved_intake"}`), plus the ledger's seat entries. Response `201`: the GET body plus `"effects": {"seats_added", "seats_removed", "seated", "flags_refreshed", "records_changed"}`.

Where the id comes from: `GET /institutions/{id}` programmes' `approval` gains `id`, `version`, `effective_from` and `source`; enrolment detail carries `approval` (§A4.6). An approval version that covers an excess lets an officer UPHOLD the EXCESS_ADMISSION case with `APPROVAL_VERSION_COVERS`; when the backlog was seated by the new version, the Seat rows are already CONFIRMED.

### A4.18 Completeness and reporting deadlines (D40)

The reconciliation of one institution and academic year (ENGINES §17.10) reads the authority's joinings list for the institution and that year, matches each joining to the institution's enrolments (any status) whose joining year is that year, by programme code, date of birth and a name score of 90 or more, and stores the result in `institution_scores` (`completeness_pct`, null when nothing joined, and the counts and missing students in `components`). It runs after every batch reaches DONE (worker), for every institution in `make seed`, and on `POST /completeness/refresh`.

- `joined`: joinings in the authority's list. `uploaded_and_joined`: joinings matched to an uploaded enrolment. `missing = joined - uploaded_and_joined`. `uploaded_not_joined`: the institution's ACTIVE records of that joining year whose ADMISSION row is CONTRADICTED with basis `NOT_IN_JOINING_RECORD`. `completeness_pct = round(100 * uploaded_and_joined / joined, 1)`, null when `joined` is 0. `published`: false when the authority has published nothing for the institution's state and that year.
- `deadline`: `rules.yaml` `reporting.deadline` for the year. `first_upload_at`: the `uploaded_at` of the institution's first DONE batch for the year. `deadline_state`, computed when read: `ON_TIME` (first upload on or before the deadline, IST), `LATE` (after it), `OVERDUE` (no DONE batch and the deadline has passed), `NOT_DUE` (no DONE batch, deadline ahead).
- When `missing` is above 0, a MISSING_FROM_UPLOAD case is raised or refreshed (§A4.11). When an upload brings some of the students in, the case's evidence is refreshed (with `case.system_note.missing_updated` on a decided case) and the case stays as it is: only officers decide. The authority being unavailable keeps the last stored result and sets `source_unavailable: true`.
- **Missing students** are the college's own admitted students, so the college and officers see who they are: each item is `{"name", "roll_no", "programme_code", "joined_on", "round", "route", "apaar_masked"}` from the authority's list (`apaar_masked` `XXXX XXXX 8812` or null; never a full APAAR). They are stored with the reconciliation and shown on the completeness page and the MISSING_FROM_UPLOAD case. A university sees the counts only.

**`GET /institutions/{id}/completeness?academic_year`**. Roles: `AICTE_ADMIN`, `RO_OFFICER` (region), `INSTITUTION` (own), `UNIVERSITY` (affiliates, `missing_students` always `[]`). Outside scope 404.

```json
200 {
  "institution": { "id": "a0b1...", "name": "ABC College of Engineering", "aicte_permanent_id": "1-ABC-0001", "state_code": "MH", "state_name": "Maharashtra", "region": "WEST" },
  "academic_year": "2026-27",
  "joined": 140, "uploaded_and_joined": 132, "missing": 8, "uploaded_not_joined": 3,
  "completeness_pct": 94.3, "published": true,
  "deadline": "2026-09-30", "first_upload_at": "2026-09-22T06:30:00Z", "deadline_state": "ON_TIME",
  "computed_at": "2026-10-29T06:00:00Z", "source_unavailable": false,
  "case": { "id": "f5f5...", "status": "OPEN" },
  "missing_students": [ { "name": "Sneha Kulkarni", "roll_no": "MHCET-2026-007731", "programme_code": "CSE", "joined_on": "2026-08-04", "round": 2, "route": "COUNSELLING", "apaar_masked": "XXXX XXXX 8812" } ]
}
```

Before the first reconciliation the counts are 0 and `completeness_pct` and `computed_at` null. A READ audit entry on `institution_score` with `after: {"via": "completeness", "missing": n}` is written when `missing_students` is returned non-empty. `GET /institutions/{id}/completeness.csv` (same roles; not the university) returns the missing list as CSV (`missing.download`): `name,roll_no,programme_code,joined_on,round,route,apaar_masked`, with the same audit entry.

**`GET /completeness?academic_year&region&state&deadline_state&sort&page&page_size`**. Roles: `AICTE_ADMIN` (all; `region`, `state` filters), `RO_OFFICER` (its region; `region` ignored). Others 403. Sort `completeness_asc` (default, nulls last), `missing_desc`, `name_asc`.

```json
200 {
  "items": [
    { "institution": { "...InstitutionRef..." }, "joined": 140, "uploaded_and_joined": 132, "missing": 8, "completeness_pct": 94.3,
      "published": true, "deadline_state": "ON_TIME", "first_upload_at": "2026-09-22T06:30:00Z", "case_status": "OPEN" }
  ],
  "total": 50, "page": 1, "page_size": 25,
  "totals": { "joined": 10410, "uploaded_and_joined": 10290, "missing": 120, "completeness_pct": 98.8,
              "deadline_states": { "NOT_DUE": 0, "ON_TIME": 44, "LATE": 4, "OVERDUE": 2 } },
  "deadline": "2026-09-30"
}
```

`totals` cover the whole filtered set. `case_status` is the MISSING_FROM_UPLOAD case's status or null.

**`POST /completeness/refresh`** (`AICTE_ADMIN`, 6 per minute). Body `{"academic_year": "2026-27", "institution_id": null}`; null refreshes every institution with an approval for that year. Synchronous: `200 {"academic_year", "institutions": 50, "missing": 120, "cases_raised": 4, "cases_updated": 1, "unavailable": 0, "duration_ms": 2100}`.

### A4.19 Signals (D45)

Officers only; `INSTITUTION`, `STUDENT`, `UNIVERSITY`: 403 on every route, and no count or panel anywhere. A regional officer sees a signal when any of its `institution_ids` is in its region; inside it, members and colleges outside the region are counted, not listed (`members_hidden`, `institutions_hidden`). Summaries, fact labels, feature words and rule lines are copy deck §27 (`signal.summary.*`, `signal.fact.*`, `signal.feature.*`, `signal.rule.*`); the api writes `summary` and `rule`.

**`GET /signals?academic_year&type&status&institution_id&state&sort&page&page_size`**. Sort `newest` (default) or `score` (ANOMALY first by score, then GHOST_RING by size).

```json
200 {
  "items": [
    {
      "id": "sg1...", "type": "GHOST_RING", "academic_year": "2026-27", "status": "NEW",
      "summary": "40 students across 3 colleges share 3 mobile numbers.",
      "member_count": 40, "members_hidden": 0, "score": null,
      "institutions": [ { "id": "a0b1...", "name": "ABC College of Engineering", "aicte_permanent_id": "1-ABC-0001", "state_code": "MH", "region": "WEST" } ],
      "institutions_hidden": 0,
      "rule": "Rule: students linked by a shared mobile number, email or address form a group; a group of 3 or more across 2 or more colleges, or of 5 or more in one college, is a signal.",
      "cases": [], "created_at": "2026-10-29T06:20:00Z", "updated_at": "2026-10-29T06:20:00Z"
    }
  ],
  "total": 6, "page": 1, "page_size": 25
}
```

**`GET /signals/{id}`**: the row plus

```json
"facts": [ { "label": "Students", "value": "40", "source": "Countersign signals" }, { "label": "Colleges", "value": "ABC College of Engineering; ...", "source": "College uploads" } ],
"shared": [ { "kind": "MOBILE", "masked": "XXXXXX1234", "students": 14 } ],
"features": [],
"members": [ { "enrolment_id": "e1...", "student": { "id": "st1...", "name": "...", "apaar_masked": "XXXX XXXX 0042", "provisional_id": null },
               "institution": { "id": "a0b1...", "name": "ABC College of Engineering" }, "programme_code": "CSE", "record_status": "UNDER_REVIEW" } ],
"dismissal": null
```

- GHOST_RING: `shared` lists each shared contact, masked (`MOBILE` as `XXXXXX1234`, `EMAIL` as `r***@example.com`, `ADDRESS` as `Same address`), with how many members share it; `members` every member the caller may see; `features` `[]`. The graph is NetworkX connected components over students linked by a shared mobile, email or address hash, with the `ghost_ring` thresholds of `rules.yaml`.
- ANOMALY: `members` `[]`, `shared` `[]`; `features` `[{"name": "nri_share", "value": 0.31, "peer_low": 0.02, "peer_high": 0.07, "peer_median": 0.04, "robust_z": 6.2, "stands_out": true}]` for every feature (ENGINES §17.11; `peer_low` and `peer_high` the 25th and 75th percentiles of the peers, for `signal.feature_line`), `score` the Isolation Forest score.
- `dismissal`: `{"note", "by": {"id", "name"}, "at"}` once dismissed, from the signal's `note`, `decided_by_id` and `decided_at`. `cases`: `[{"id", "institution_id", "status"}]` opened from it.
- READ audit entry on `student` for every member returned; the summary and facts never hold a name.

**`POST /signals/{id}/open-case`**. Body `{"institution_ids": ["a0b1..."], "note": "Shared mobiles across three colleges; ask each for admission records.", "severity": "HIGH"}`. `institution_ids`: one or more of the signal's institutions (a regional officer only those in its region); optional when the signal has one institution. `note`: 1 to 2,000 characters. `severity`: `LOW`, `MEDIUM` or `HIGH`, default HIGH for GHOST_RING and MEDIUM for ANOMALY. A DISMISSED signal, or another officer acting on it at the same moment: `409 SIGNAL_ALREADY_HANDLED`. For each institution, in one transaction: a GHOST_RING or ANOMALY case is raised through the flags engine (§A4.11: `related_enrolment_ids` the members at that institution for a ring, `[]` for an anomaly), unless a case for that signal and institution exists, in which case it is returned as it is; a NOTE row with the officer's note and the officer as actor starts its history; the signal's `status` becomes CASE_OPENED (`case_flag_id`, `note`, `decided_by_id` and `decided_at` set the first time, `facts.cases` appended). **The records each case names read Under review from that moment** (R5: the case follows §A4.3 and §A4.10 like any other), and their statuses are recomputed in the same transaction; nothing else about them changes. Audit CREATE on `flag` with the officer as actor and UPDATE on `signal`. Response `201`: `{"cases": [FlagRow...], "signal": SignalDetail}`.

**`POST /signals/{id}/dismiss`**. Body `{"note": "..."}` (1 to 2,000 characters). Only from NEW (else `409 SIGNAL_ALREADY_HANDLED`). Sets `status` DISMISSED with `note`, `decided_by_id` and `decided_at`; audit UPDATE on `signal` (`after: {"status": "DISMISSED"}`, never the note). Response `200`: the signal detail. A dismissed signal is refreshed by later runs and stays DISMISSED; no record or case changes.

**`POST /signals/run`** (`AICTE_ADMIN`, 2 per minute). Body `{"academic_year": "2026-27"}`. Runs both detectors synchronously over ACTIVE enrolments of the year and upserts by `dedupe_key`; nothing is deleted, and a signal not found again keeps its last facts and `updated_at`. `200 {"academic_year", "rings": 4, "anomalies": 3, "created": 7, "updated": 0, "duration_ms": 950, "model": {"name": "IsolationForest", "contamination": 0.05, "n_estimators": 200, "random_state": 0, "institutions": 50}}`. `make seed` runs the same after the replies.

Signals never change rows, record statuses or cases; only `open-case` makes a case, and only through that case can a record's status change (R5). A 404 for a signal out of scope reads "Signal not found." (`err.NOT_FOUND_signal`).

### A4.20 Dashboards and institutions (D46)

**`GET /dashboard/summary`** (A.5, A2.19). `kpis.clear_pct` is removed; `countersigned_pct` is the COUNTERSIGNED share of in-scope ACTIVE records of the year (0 to 100, one decimal, null when there are none). New keys:

```json
"kpis": {
  "institutions": 50, "programmes": 187, "approved_seats": 18960, "admitted": 4120, "enrolments": 10342,
  "flags_open": 214, "countersigned_pct": 61.2,
  "records": { "AWAITING_EVIDENCE": 3110, "COUNTERSIGNED": 6329, "UNDER_REVIEW": 895, "DISPUTED": 8 },
  "joined": 4210, "missing_from_upload": 120, "completeness_pct": 97.1,
  "colleges_late": 4, "colleges_overdue": 2,
  "signals_new": 6
},
"records_by_status": [
  { "status": "COUNTERSIGNED", "count": 6329, "pct": 61.2 }, { "status": "AWAITING_EVIDENCE", "count": 3110, "pct": 30.1 },
  { "status": "UNDER_REVIEW", "count": 895, "pct": 8.7 }, { "status": "DISPUTED", "count": 8, "pct": 0.1 }
],
"cases_by_age": [ { "bucket": "UNDER_7_DAYS", "open": 180 }, { "bucket": "DAYS_7_TO_30", "open": 30 }, { "bucket": "OVER_30_DAYS", "open": 4 } ],
"top_institutions": [ { "institution": { "...InstitutionRef..." }, "flags_open": 41, "disputed": 2, "under_review": 37 } ],
"completeness": null,
"by_state": [ { "...A2.19 row...", "records": { "...four counts..." }, "countersigned_pct": 60.4, "completeness_pct": 96.9, "missing_from_upload": 31 } ],
"by_region": [ { "...A2.19 row...", "records": { "...four counts..." }, "countersigned_pct": 61.0, "completeness_pct": 97.4, "missing_from_upload": 48 } ]
```

- `records` and `records_by_status` count in-scope ACTIVE enrolments of the year by `record_status`; `records_by_status` is in the order COUNTERSIGNED, AWAITING_EVIDENCE, UNDER_REVIEW, DISPUTED, and its four counts sum to `enrolments`.
- `joined`, `missing_from_upload`, `completeness_pct` sum the stored reconciliations of the in-scope institutions (`completeness_pct` from the sums). `colleges_late` and `colleges_overdue` count deadline states.
- `cases_by_age`: unresolved cases of the year by days since `opened_at` (under 7, 7 to 30, over 30).
- `top_institutions`: the ten in-scope institutions with most unresolved cases (officers only; `[]` for other roles).
- `signals_new`: NEW signals touching the scope (officers only; null for other roles).
- `completeness`: for an `INSTITUTION` caller, the §A4.18 body of its own institution without `institution` (the college dashboard's missing students and deadline); null for other roles.
- `flags_by_type` lists the fifteen types.

**`GET /institutions`** (A.6, A2.20). Rows lose `integrity_index` and gain `records` (the four counts), `countersigned_pct`, `completeness_pct`, `missing_from_upload` and `deadline_state`. New filter `deadline_state`; new sorts `completeness_asc` and `countersigned_asc` beside `flags_open_desc` (default), `enrolments_desc` and `name_asc`.

**`GET /institutions/{id}`** (A.7, A2.20). Loses `integrity_index` and `integrity_components`; gains `records`, `countersigned_pct` and `completeness` (the §A4.18 body without `institution` and without `missing_students`). Each `programmes[].approval` gains `id`, `version`, `effective_from` and `source`.

### A4.21 Reports (D46)

**`GET /reports`**. Roles: `AICTE_ADMIN`, `RO_OFFICER`. The list of reports with their columns, for the reports page:

```json
200 { "items": [ { "name": "by-state", "title": "Records by state", "formats": ["csv", "xlsx", "pdf"], "columns": ["academic_year", "state_code", "..."] } ] }
```

**`GET /reports/{name}.{format}`**. Roles: `AICTE_ADMIN` (national; optional `region`, `state`), `RO_OFFICER` (its region; `region` ignored). Others 403. Query `academic_year` (default the current year). An unknown name or a format the name does not offer: `404 REPORT_NOT_FOUND` "Report not found.". A file that cannot be built (an XLSX or PDF renderer error): `500 REPORT_FAILED` "The report could not be prepared." (the CSV of the same report is the fallback, `err.REPORT_FAILED`). Writes a READ audit entry on `report` with `after: {"name", "format", "scope"}` (aggregates only, no student data).

| name | one row per | columns, in order | formats |
|---|---|---|---|
| `by-state` | state in scope | `academic_year`, `state_code`, `state_name`, `region`, `institutions`, `approved_seats`, `admitted`, `records`, `countersigned`, `awaiting_evidence`, `under_review`, `disputed`, `countersigned_pct`, `cases_open`, `joined`, `missing_from_upload`, `completeness_pct` | csv, xlsx, pdf |
| `by-institution-type` | institution type | `academic_year`, `institution_type`, `institutions`, `approved_seats`, `admitted`, `records`, `countersigned`, `awaiting_evidence`, `under_review`, `disputed`, `countersigned_pct`, `cases_open`, `completeness_pct` | csv, xlsx, pdf |
| `cases-by-type-and-outcome` | case type | `academic_year`, `case_type`, `case_name`, `open`, `docs_requested`, `escalated`, `upheld`, `corrected`, `withdrawn`, `total`, `median_days_to_decision` | csv, xlsx, pdf |
| `countersign-coverage` | institution | `academic_year`, `aicte_permanent_id`, `institution_name`, `state_code`, `institution_type`, `records`, `countersigned`, `awaiting_evidence`, `under_review`, `disputed`, `countersigned_pct`, `independent_joining_record`, `independent_credits`, `independent_student` (records with that row CONFIRMED and independent) | csv, xlsx, pdf |
| `completeness` | institution | `academic_year`, `aicte_permanent_id`, `institution_name`, `state_code`, `joined`, `uploaded_and_joined`, `missing`, `uploaded_not_joined`, `completeness_pct`, `deadline`, `first_upload_on`, `deadline_state`, `case_status` | csv, xlsx, pdf |
| `summary` | | one page: the KPIs, records by status (a bar chart with its table), cases by type, the ten colleges with most unresolved cases, late and overdue colleges | pdf |

- CSV: `text/csv; charset=utf-8` with a BOM, the column names above as the header, numbers unformatted, percentages to one decimal, dates `YYYY-MM-DD`.
- XLSX: sheet one named after the report with the same header and rows; sheet two `About` with the title, the scope ("All India", "Western Region", "Maharashtra"), the academic year, the time generated and the line "Synthetic demo data. Every number comes from the Countersign demo dataset.".
- PDF: one A4 landscape page (reportlab): title, scope, academic year, the table's first 25 rows in the report's order and a totals row, "and {n} more rows in the CSV or XLSX" when cut, and the synthetic-data footer.
- `Content-Disposition: attachment; filename="countersign_{name}_{academic_year}_{scope_slug}.{format}"` (`scope_slug` `national`, the region code or the state code). Rows are sorted by state name, type, case type or institution name; `completeness` by `completeness_pct` ascending.

### A4.22 Error codes and messages added in Week 4

The codes are the copy deck's §13 `err.<CODE>` ids; the web prints the deck's sentence for the code, and the api's `message` below is the plain fallback.

| status | code | message | `details` |
|---|---|---|---|
| 401 | `SIGNIN_REQUIRED` | "Sign in with DigiLocker to answer this notice." | `{}` |
| 403 | `NOTICE_IDENTITY_MISMATCH` | "This notice is for someone else. Nothing was recorded." | `{}` |
| 401 | `DIGILOCKER_STATE_INVALID` | "This sign-in has expired or was started in another browser." | `{}` (also a `/auth/digilocker/return?error=` state) |
| page state | `DIGILOCKER_CANCELLED`, `DIGILOCKER_FAILED` | (only `/auth/digilocker/return?error=`; never a JSON answer) | |
| 422 | `CLAIM_NO_MATCH` | "This provisional ID does not match the name and date of birth on your DigiLocker." | `{}` |
| 409 | `CLAIM_ALREADY_CLAIMED` | "This record is already claimed through another DigiLocker sign-in." | `{}` |
| 409 | `CLAIM_NOT_NEEDED` | "This record has an APAAR, so it links to DigiLocker on its own." | `{}` |
| 422 | `REASON_REQUIRED` | "Choose a reason and write a note before you decide." | `fields` |
| 422 | `CORRECTION_EMPTY` | "Change at least one field, or choose another decision." | `{}` |
| 422 | `CORRECTION_INVALID` | "{Field word}: {message}" | `field` |
| 422 | `WITHDRAW_NONE_SELECTED` | "Select at least one record to withdraw." | `{}` |
| 409 | `WITHDRAW_NOT_NAMED` | "{n} of the selected records are not named by this case." | `n`, `named_enrolment_ids` |
| 409 | `UPHOLD_NEEDS_VERSION` | "This case can be upheld only when an approval version covers these admissions." | `current_version`, `covers` (false) |
| 409 | `DECISION_NOT_AVAILABLE` | "This decision does not apply to a {case_name} case." | `action`, `type`, `allowed_actions` (proposed copy `err.DECISION_NOT_AVAILABLE`; the action bar shows only `allowed_actions`, so a person rarely meets it) |
| 409 | `APPROVAL_BELOW_ASSIGNED` | "The new intake is below the seats already assigned." | `intake`, `assigned`, `pools` |
| 422 | `UPLOAD_HEADER_UNMAPPED` | "The file has columns Countersign does not recognise. Map them to the template once, then upload again." | `unknown_headers`, `missing_columns`, `suggestions` (proposed copy `err.UPLOAD_HEADER_UNMAPPED`, leading to the mapping step) |
| 422 | `MAPPING_INCOMPLETE` | "Map every required column before you continue: {columns}." | `missing_columns` |
| 422 | `MAPPING_DUPLICATE` | "Each Countersign column can be chosen once. {column} is chosen more than once." | `column` |
| 409 | `SIGNAL_ALREADY_HANDLED` | "This signal already has a case or was dismissed." | `status` |
| 404 | `REPORT_NOT_FOUND` | "Report not found." | `{}` (proposed copy `err.NOT_FOUND_report`) |
| 500 | `REPORT_FAILED` | "The report could not be prepared." | `{}` |

Changed messages (codes unchanged): `FLAG_TRANSITION_INVALID` "This action is not possible while the case is {status_word}." with `{status_word}` OPEN open, DOCS_REQUESTED waiting for documents, ESCALATED escalated, UPHELD claim upheld, CORRECTED claim corrected, WITHDRAWN claim withdrawn; 404 "Case not found.", "Attestation not found.", "Approval not found.", "Signal not found."; the attestation messages of §A4.14.

### A4.23 Addendum 4 scoping

| Endpoint | AICTE_ADMIN | RO_OFFICER | INSTITUTION | STUDENT | UNIVERSITY | public |
|---|---|---|---|---|---|---|
| `GET /auth/digilocker/start`, `GET /auth/digilocker/callback` | | | | | | yes, 30/min |
| `GET /auth/digilocker/claim`, `POST /auth/digilocker/claim` | | | | | | pending-claim cookie only; POST 5 per 15 min per DigiLocker subject |
| `POST /auth/login` | ok | ok | ok | 401 (DigiLocker only) | ok | yes |
| `GET /notices/{token}` | | | | | | yes, 30/min (reads a cookie for `viewer`) |
| `POST /notices/{token}/respond` | 403 | 403 | 403 | own notice, else 403 | 403 | no (401 without a session) |
| `POST /students/me/enrolments/{id}/respond` | 403 | 403 | 403 | own, else 404 | 403 | no |
| `GET /institutions/{id}/enrolments` (record filters) | any | region, else 404 | own, else 404 | 403 | affiliate, else 404 | no |
| `GET /enrolments/{id}`, `GET /enrolments/{id}/history` | any | region, else 404 | own, else 404 | 403 | affiliate, else 404 | no |
| `POST /flags/{id}/actions` (decisions, `dry_run`) | any, per §A4.8 | region, else 404; per §A4.8 | 403 | 403 | 403 | no |
| `GET`, `PUT /institutions/{id}/column-mapping` | any | GET region, PUT 403 | own | 403 | 403 | no |
| `GET /approvals/{id}/versions` | any | region, else 404 | own, else 404 | 403 | affiliate, else 404 | no |
| `POST /approvals/{id}/versions` | any | 403 | 403 | 403 | 403 | no |
| `GET /institutions/{id}/completeness` | any | region, else 404 | own, else 404 | 403 | affiliate (counts only), else 404 | no |
| `GET /institutions/{id}/completeness.csv` | any | region, else 404 | own, else 404 | 403 | 403 | no |
| `GET /completeness` | all | region | 403 | 403 | 403 | no |
| `POST /completeness/refresh` | ok | 403 | 403 | 403 | 403 | no |
| `GET /signals`, `GET /signals/{id}` | all | touching its region (members outside it counted, not listed), else 404 | 403 | 403 | 403 | no |
| `POST /signals/{id}/open-case`, `POST /signals/{id}/dismiss` | any | touching its region, else 404 (cases only for institutions in its region) | 403 | 403 | 403 | no |
| `POST /signals/run` | ok | 403 | 403 | 403 | 403 | no |
| `GET /reports`, `GET /reports/{name}.{format}` | national | region | 403 | 403 | 403 | no |
| `GET /university/graduates`, `/university/certificates/{id}`, `/issue`, `/block.pdf` | any | 403 | 403 | 403 | affiliates, else 404 | no |
| `GET /verify/completion/{short_id}` (and the old `/verify/degree/{short_id}`) | | | | | | yes, 60/min shared with the verifier routes |
| `/dashboard/summary`, `/institutions*` | as section B, with the officer-only keys of §A4.20 | | | | | |

Order of answers as §A3.26: the route's roles (403), body shape (422), scope (404), then per-status and per-type rules (403 or 409) and field rules (422).

### A4.24 TypeScript types (paste into `apps/web/lib/types.ts`)

Add the new types and replace the earlier declarations of `FlagType`, `FlagStatus`, `CaseAction`, `OfficerAction`, `CredentialKind`, `RevokedReasonCode`, `AccessedWhat` (Week 3 enums), `CheckSource`, `InstitutionSort`, `UPLOAD_COLUMNS`, `SourceKey` and `SOURCE_KEYS`, `CheckDetail`, `StudentEnrolment`, `EnrolmentRow`, `EnrolmentListQuery`, `EnrolmentDetail`, `EnrolmentRecheck`, `InstitutionRecheck`, `DashboardSummary`, `InstitutionRow`, `ProgrammeDetail`, `InstitutionDetail`, `UploadCounts`, `UploadBatch`, `FlagRow`, `FlagListQuery`, `FlagDetail`, `CaseHistoryItem`, `CaseActionRequest`, `StudentMe`, `NoticePublic`, `GraduateRow`, `GraduateListQuery` and `MyDataExport` with the ones below. Remove `CheckStatus`, `Score`, `CheckBrief`, `Countersign`, `Check` and `DegreePrint` (replaced by `EvidenceState`, `EvidenceRowBrief`, `EvidenceRow` and `CertificatePrint`). Derived names (`FlagStatusFilter`, `FlagListParams`, `InstitutionListParams`, `EnrolmentListParams`, `ScopeKind`, `StateSummaryRow`, `RegionSummaryRow`, `FlagsByType`) keep working once their bases change; `FlagStatusFilter` gains `"DECIDED"`.

```ts
// ---------- Week 4 enums ----------
export type EvidenceState =
  | "CONFIRMED" | "CONTRADICTED" | "PENDING" | "NOT_YET_DUE" | "NOT_APPLICABLE" | "SOURCE_UNAVAILABLE";
export type RecordStatus = "AWAITING_EVIDENCE" | "COUNTERSIGNED" | "UNDER_REVIEW" | "DISPUTED";
export const RECORD_STATUS_ORDER: RecordStatus[] = ["AWAITING_EVIDENCE", "COUNTERSIGNED", "UNDER_REVIEW", "DISPUTED"];
export const ROW_ORDER: CheckType[] = ["IDENTITY", "SEAT", "ADMISSION", "STUDYING", "STUDENT"];
export type RecordCounts = Record<RecordStatus, number>;
/** Replaces the Week 1 FlagType. */
export type FlagType =
  | "EXCESS_ADMISSION" | "QUOTA_BREACH" | "LATE_REFILL" | "INVALID_APAAR" | "NAME_MISMATCH"
  | "DUPLICATE_CROSS_INSTITUTION" | "DUPLICATE_WITHIN_UPLOAD" | "DUAL_ENROLMENT_ALLOWED"
  | "NO_ACADEMIC_ACTIVITY" | "STUDENT_DENIED" | "GHOST_RING" | "ANOMALY"
  | "NOT_IN_JOINING_RECORD" | "ELIGIBILITY_BREACH" | "MISSING_FROM_UPLOAD";
/** Replaces the Week 1 FlagStatus. */
export type FlagStatus = "OPEN" | "DOCS_REQUESTED" | "ESCALATED" | "UPHELD" | "CORRECTED" | "WITHDRAWN";
/** Replaces the Week 3 CaseAction. */
export type CaseAction =
  | "UPHOLD" | "CORRECT" | "WITHDRAW" | "REQUEST_DOCS" | "ESCALATE" | "NOTE" | "ASSIGN" | "REOPEN"
  | "COLLEGE_RESPONSE" | "SYSTEM_NOTE";
export type OfficerAction = Exclude<CaseAction, "COLLEGE_RESPONSE" | "SYSTEM_NOTE">;
export type DecisionAction = Extract<CaseAction, "UPHOLD" | "CORRECT" | "WITHDRAW">;
export type CaseScope = "RECORD" | "MULTI_RECORD" | "INSTITUTION";
export type UpholdReason =
  | "DOCUMENTS_SUPPORT_CLAIM" | "SOURCE_RECORD_WRONG" | "NAME_VARIANT" | "PERMITTED_DUAL_PROGRAMME"
  | "APPROVAL_VERSION_COVERS" | "STUDENT_ANSWER_MISTAKEN" | "MISSING_NOW_UPLOADED" | "OTHER";
export type CorrectReason = "UPLOAD_ERROR" | "DOCUMENTS_SHOW_OTHER_VALUE" | "WRONG_SEAT_CATEGORY" | "OTHER";
export type WithdrawReason =
  | "STUDENT_NEVER_JOINED" | "NO_JOINING_EVIDENCE" | "BEYOND_APPROVED_INTAKE" | "NOT_ELIGIBLE_FOR_SEAT"
  | "DUPLICATE_RECORD" | "NO_RESPONSE" | "OTHER";
export type EscalateReason = "NEEDS_AICTE_DECISION" | "POLICY_QUESTION" | "SPANS_REGIONS" | "REPEATED_PATTERN" | "OTHER";
export type ReasonCode = UpholdReason | CorrectReason | WithdrawReason | EscalateReason;
export type DocsKind = "ADMISSION" | "JOINING" | "IDENTITY" | "ELIGIBILITY" | "CREDITS" | "OTHER";
/** Replaces the Week 3 CredentialKind. */
export type CredentialKind = "ENROLMENT" | "COMPLETION";
/** Replaces the Week 3 RevokedReasonCode. */
export type RevokedReasonCode =
  | "ENROLMENT_WITHDRAWN" | "ENROLMENT_TRANSFERRED" | "CLAIM_WITHDRAWN" | "STUDENT_DISPUTE" | "ADMIN" | "FLAG_CONFIRMED";
/** Replaces the Week 3 AccessedWhat. */
export type AccessedWhat = "RECORD" | "EXPORT" | "COMPLETION" | "NOTICE" | "CREDENTIAL" | "PROOF";
/** Replaces the A2.23 CheckSource. */
export type CheckSource =
  | "APAAR" | "ADMISSION_AUTHORITY" | "SEAT_LEDGER" | "ABC" | "SII" | "DIGILOCKER" | "STUDENT_NOTICE" | "COUNSELLING";
/** Replaces the A2.23 InstitutionSort. */
export type InstitutionSort = "flags_open_desc" | "enrolments_desc" | "name_asc" | "completeness_asc" | "countersigned_asc";
export type DeadlineState = "NOT_DUE" | "ON_TIME" | "LATE" | "OVERDUE";
export type SignalType = "GHOST_RING" | "ANOMALY";
export type SignalStatus = "NEW" | "CASE_OPENED" | "DISMISSED";
export type VersionSource = "UPLOAD" | "DECISION" | "SEED";
export type NoticeMatch = "MATCH" | "SOMEONE_ELSE" | "CLAIM_NEEDED";
export type CaseAgeBucket = "UNDER_7_DAYS" | "DAYS_7_TO_30" | "OVER_30_DAYS";
export type ReportName =
  | "by-state" | "by-institution-type" | "cases-by-type-and-outcome" | "countersign-coverage" | "completeness" | "summary";
export type ReportFormat = "csv" | "xlsx" | "pdf";
/** Replaces the Week 1 SourceKey and SOURCE_KEYS (adapter ping and chaos). */
export type SourceKey = "apaar" | "counselling" | "admission_authority" | "abc" | "digilocker" | "sii";
export const SOURCE_KEYS: SourceKey[] = ["apaar", "counselling", "admission_authority", "abc", "digilocker", "sii"];
/** Replaces the A2.23 UPLOAD_COLUMNS. */
export const UPLOAD_COLUMNS = [
  "apaar_id", "name", "dob", "gender", "mobile", "email", "address", "nationality", "passport_no",
  "programme_code", "academic_year", "year_of_study", "admission_route", "counselling_ref", "category",
  "consent_status", "status", "status_date", "admission_date", "tfw_income_certified", "nri_sponsored", "ciwg",
] as const;

// ---------- evidence rows and the record ----------
/** Replaces the A3.27 CheckDetail. */
export interface CheckDetail {
  summary: string; finding?: string | null; source_line?: string; basis: string;
  source_unavailable?: boolean; source_error?: string; needs_review?: boolean;
  name_score?: number; dob_match?: boolean; apaar_last4?: string;
  approval_id?: string; approval_version?: number; seat_code?: string; seat_type?: SeatType;
  flag_type?: FlagType; case_type?: FlagType; eligibility_rule?: "INTERNATIONAL_CIWG" | "NRI_STATUS" | "TFW_INCOME";
  reported?: Eligibility;
  joining_year?: string; joined_on?: string; round?: number | null; route?: AdmissionRoute | null; route_mismatch?: boolean;
  deadline?: string; published?: boolean;
  expected?: number; missing?: number; semesters?: { academic_year: string; sem: number; credits: number; issuer?: string }[];
  awaiting_semester?: number; issuer?: string; issuer_name?: string; self_issued?: boolean;
  claimed_at?: string; reviewed_by_officer?: boolean;
  notice_state?: StudentNoticeState; channel?: NoticeChannel; sent_at?: string; responded_at?: string; changed?: boolean;
  delivery_failed?: boolean; consent_withdrawn?: boolean;
  [key: string]: unknown;
}
export interface RowResolution {
  outcome: "UPHELD"; case_id: string; case_action_seq: number; reason_code: UpholdReason; at: string; by: ActorRef;
  line: string;
}
export interface EvidenceRow {
  type: CheckType; state: EvidenceState; finding: string | null; source_line: string; summary: string;
  supplied_by: string; observed_at: string | null; independent: boolean; resolved: RowResolution | null;
  source: CheckSource; checked_at: string | null; attempts: number; detail: CheckDetail;
}
export interface EvidenceRowBrief { type: CheckType; state: EvidenceState; finding: string | null; independent: boolean; resolved: boolean }
export interface RecordFields {
  record_status: RecordStatus | null; status_reason: string | null; next_step: string | null; record_status_at: string | null;
}
export interface Eligibility { tfw_income_certified: boolean | null; nri_sponsored: boolean | null; ciwg: boolean | null }

// ---------- enrolments ----------
/** Replaces the A2.23 EnrolmentRow. */
export interface EnrolmentRow extends RecordFields {
  id: string; student: StudentRef; programme_id: string; programme_code: string;
  academic_year: string; cohort_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category; eligibility: Eligibility;
  seat_code: string | null; status: EnrolmentStatus; admission_date: string; status_date: string;
  uploaded_at: string; upload_batch_id: string | null; source_row_no: number | null;
  checks: EvidenceRowBrief[]; flags: FlagRef[];
}
export interface EnrolmentPage extends Page<EnrolmentRow> { status_counts: RecordCounts }
/** Replaces the A2.23 EnrolmentListQuery. */
export interface EnrolmentListQuery {
  page?: number; page_size?: number; programme_id?: string; status?: EnrolmentStatus; academic_year?: string; q?: string;
  admission_route?: AdmissionRoute; year_of_study?: number; sort?: "name_asc" | "year_desc" | "route_asc" | "status_priority";
  record_status?: RecordStatus | string; flagged?: boolean; seated?: boolean;
}
export interface ApprovalRef {
  id: string; academic_year: string; version: number; approved_intake: number; effective_from: string; source: string;
}
/** Replaces the A3.27 EnrolmentDetail: the record card. */
export interface EnrolmentDetail extends RecordFields {
  id: string;
  institution: InstitutionRef;
  student: StudentRef & { dob: string; gender: "M" | "F" | "O" | "U"; mobile_masked: string | null };
  programme: ProgrammeRef & { level: Level; mode: ProgrammeMode; duration_years: number };
  academic_year: string; cohort_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category; eligibility: Eligibility;
  status: EnrolmentStatus; status_date: string; admission_date: string; uploaded_at: string;
  upload: { batch_id: string; filename: string; row_no: number | null } | null;
  seat: { id: string; seat_code: string; seat_type: SeatType; academic_year: string; assigned_at: string | null } | null;
  approval: ApprovalRef | null;
  claim: { claimed: boolean; claimed_at: string | null } | null;
  checks: EvidenceRow[];
  flags: FlagSummary[];
  notices: EnrolmentNotice[];
  resend: ResendState;
  credentials: CredentialRef[];
  versions: EnrolmentVersion[];
  history_count: number;
}
export interface FieldChange { field: string; before: unknown; after: unknown }
export interface EnrolmentVersion {
  version: number; at: string; source: VersionSource; actor: ActorRef | null;
  batch: { id: string; filename: string; row_no: number | null } | null;
  case: { id: string; type: FlagType; action: DecisionAction; case_action_seq: number; reason_code: ReasonCode } | null;
  changes: FieldChange[];
}
/** Replaces the A2.23 EnrolmentRecheck. */
export interface EnrolmentRecheck {
  enrolment_id: string; rechecked: number;
  results: { type: CheckType; before: EvidenceState; after: EvidenceState }[];
  flags_raised: number; record_status: RecordStatus | null; checks: EvidenceRowBrief[];
}
/** Replaces the A2.23 InstitutionRecheck. */
export interface InstitutionRecheck {
  institution_id: string; academic_year: string; enrolments: number; rechecked: number;
  outcomes: Record<EvidenceState, number>; flags_raised: number; duration_ms: number;
}

// ---------- the student ----------
/** Replaces the section D StudentEnrolment. */
export interface StudentEnrolment {
  id: string; institution_id: string; institution_name: string; programme_code: string; programme_name: string;
  academic_year: string; year_of_study: number; status: EnrolmentStatus;
  record_status: RecordStatus | null; status_reason: string | null; next_step: string | null;
  checks: EvidenceRowBrief[]; response: NoticeResponse | null; can_respond: boolean; claimed: boolean;
  decision: { outcome: "UPHELD" | "CORRECTED" | "WITHDRAWN" | "ESCALATED"; reason_code: ReasonCode | null; at: string } | null;
}
/** Replaces the A3.27 StudentMe. */
export interface StudentMe {
  id: string; name: string; apaar_masked: string | null; consent_status: ConsentStatus; provisional_id: string | null;
  dob: string; email: string | null; mobile_masked: string | null; signed_in_with: "DIGILOCKER";
  enrolments: StudentEnrolment[];
  notices: StudentNotice[];
  credentials: StudentCredentialBrief[];
}
/** Replaces the A3.27 NoticePublic. */
export interface NoticePublic {
  channel: NoticeChannel; institution_name: string; programme_code: string; programme_name: string;
  academic_year: string; year_of_study: number; id_kind: IdKind; id_masked: string;
  uploaded_at: string; sent_at: string | null; expires_at: string;
  response: NoticeResponse | null; responded_at: string | null;
  previous_response: NoticeResponse | null; changed_at: string | null; can_change_until: string | null;
  consent_text: string; notice_version: string;
  viewer: { signed_in: boolean; name: string | null; match: NoticeMatch | null };
  can_answer: boolean; sign_in_url: string; claim_url: string | null;
}
export interface PendingClaim { name: string; birthdate: string; next: string }
export interface ClaimRequest { provisional_id: string }
export interface ClaimResult { user: User; next: string; claimed: { student_id: string; enrolments: StudentEnrolment[] } }

// ---------- uploads ----------
/** Replaces the A2.23 UploadCounts. */
export interface UploadCounts {
  rows: number; accepted: number; errors: number; warnings: number;
  created: number; updated: number; unchanged: number; withdrawn: number; transferred: number;
  seated: number; released: number; unseated: number; flags_raised: number; flags_updated: number;
  versions: number; records: RecordCounts;
}
/** Replaces the A2.23 UploadBatch. */
export interface UploadBatch {
  id: string; institution_id: string; institution_name: string; academic_year: string; filename: string;
  source: UploadSource; kind: UploadKind; status: UploadStatus; stage: UploadStage | null;
  total_rows: number; stage_total: number; processed_rows: number; progress_pct: number;
  counts: UploadCounts; sources: UploadSourceStat[]; timings_ms: Partial<Record<UploadStage, number>>;
  error: string | null; ignored_columns: string[]; column_mapping: { header: string; column: UploadColumn }[];
  same_file_as: { batch_id: string; uploaded_at: string } | null;
  uploaded_by: { id: string; name: string };
  uploaded_at: string; started_at: string | null; finished_at: string | null;
}
export interface ColumnMapping {
  institution_id: string; mapping: Record<string, UploadColumn>; updated_at: string | null;
  updated_by: { id: string; name: string } | null; columns: { column: UploadColumn; required: boolean }[];
}
export interface ColumnMappingPut { mapping: Record<string, UploadColumn>; headers?: string[] }
export interface HeaderUnmappedDetails {
  unknown_headers: string[]; missing_columns: UploadColumn[]; suggestions: { header: string; column: UploadColumn }[];
}

// ---------- approvals and completeness ----------
export interface ApprovalVersion { version: number; approved_intake: number; effective_from: string; source: string; created_at: string }
export interface ApprovalVersions {
  approval_id: string; institution: { id: string; name: string; aicte_permanent_id: string };
  programme: ProgrammeRef; academic_year: string; current_version: number; items: ApprovalVersion[];
}
export interface ApprovalVersionCreate { approved_intake: number; effective_from: string; source: string }
export interface ApprovalVersionCreated extends ApprovalVersions {
  effects: { seats_added: number; seats_removed: number; seated: number; flags_refreshed: number; records_changed: number };
}
export interface MissingStudent {
  name: string; roll_no: string | null; programme_code: string; joined_on: string; round: number | null;
  route: AdmissionRoute; apaar_masked: string | null;
}
export interface Completeness {
  academic_year: string; joined: number; uploaded_and_joined: number; missing: number; uploaded_not_joined: number;
  completeness_pct: number | null; published: boolean;
  deadline: string; first_upload_at: string | null; deadline_state: DeadlineState;
  computed_at: string | null; source_unavailable: boolean; case: { id: string; status: FlagStatus } | null;
  missing_students?: MissingStudent[];
}
export interface InstitutionCompleteness extends Completeness { institution: InstitutionRef }
export interface CompletenessRow {
  institution: InstitutionRef; joined: number; uploaded_and_joined: number; missing: number;
  completeness_pct: number | null; published: boolean; deadline_state: DeadlineState; first_upload_at: string | null;
  case_status: FlagStatus | null;
}
export interface CompletenessPage extends Page<CompletenessRow> {
  totals: { joined: number; uploaded_and_joined: number; missing: number; completeness_pct: number | null;
            deadline_states: Record<DeadlineState, number> };
  deadline: string;
}
export interface CompletenessQuery {
  academic_year?: string; region?: Region; state?: string; deadline_state?: DeadlineState;
  sort?: "completeness_asc" | "missing_desc" | "name_asc"; page?: number; page_size?: number;
}

// ---------- institutions and dashboard ----------
/** Replaces the A2.23 DashboardSummary. */
export interface DashboardSummary {
  academic_year: string;
  scope: { kind: "NATIONAL" | "REGION" | "INSTITUTION" | "UNIVERSITY"; label: string };
  kpis: {
    institutions: number; programmes: number; approved_seats: number; admitted: number; enrolments: number;
    flags_open: number; countersigned_pct: number | null; records: RecordCounts;
    joined: number; missing_from_upload: number; completeness_pct: number | null;
    colleges_late: number; colleges_overdue: number; signals_new: number | null;
  };
  records_by_status: { status: RecordStatus; count: number; pct: number | null }[];
  flags_by_type: { type: FlagType; open: number }[];
  cases_by_age: { bucket: CaseAgeBucket; open: number }[];
  top_institutions: { institution: InstitutionRef; flags_open: number; disputed: number; under_review: number }[];
  completeness: Completeness | null;
  by_state: {
    state_code: string; state_name: string; region: Region; institutions: number; programmes: number;
    approved_seats: number; admitted: number; enrolments: number; flags_open: number;
    records: RecordCounts; countersigned_pct: number | null; completeness_pct: number | null; missing_from_upload: number;
  }[];
  by_region: {
    region: Region; region_name: string; institutions: number; approved_seats: number; admitted: number;
    enrolments: number; flags_open: number;
    records: RecordCounts; countersigned_pct: number | null; completeness_pct: number | null; missing_from_upload: number;
  }[];
}
/** Replaces the A2.23 InstitutionRow. */
export interface InstitutionRow {
  id: string; aicte_permanent_id: string; name: string; type: InstitutionType;
  state_code: string; state_name: string; region: Region; region_name: string;
  university_id: string | null; university_name: string | null;
  programmes: number; approved_seats: number; admitted: number; enrolments: number; flags_open: number;
  records: RecordCounts; countersigned_pct: number | null; completeness_pct: number | null;
  missing_from_upload: number; deadline_state: DeadlineState;
}
/** Replaces the A2.23 ProgrammeDetail. */
export interface ProgrammeDetail {
  id: string; code: string; name: string; level: Level; discipline: Discipline; shift: Shift; mode: ProgrammeMode;
  approval: {
    id: string; academic_year: string; approved_intake: number; cutoff_date: string | null;
    version: number; effective_from: string; source: string;
  };
  enrolments: number; seated: number; unseated: number; pools: SeatPool[];
}
/** Replaces the A2.23 InstitutionDetail. */
export interface InstitutionDetail extends Omit<InstitutionRow, "programmes"> {
  address_city: string | null; established_year: number | null;
  last_upload: LastUpload | null;
  completeness: Omit<Completeness, "missing_students">;
  programmes: ProgrammeDetail[];
}

// ---------- cases ----------
/** Replaces the A3.27 CaseHistoryItem. */
export interface CaseHistoryItem {
  seq: number; at: string; action: CaseAction; from_status: FlagStatus | null; to_status: FlagStatus | null;
  actor: ActorRef | null; note: string | null; due_date: string | null;
  assignee: { id: string; name: string } | null; attachments: CaseAttachment[];
  reason_code: ReasonCode | null; docs_kind: DocsKind | null; approval_version: number | null;
  correction: { enrolment_id: string; changes: FieldChange[] } | null;
  withdrawn_enrolment_ids: string[];
}
export type CorrectableField =
  | "name" | "dob" | "year_of_study" | "admission_route" | "category" | "counselling_ref" | "admission_date"
  | "tfw_income_certified" | "nri_sponsored" | "ciwg";
/** Replaces the A3.27 CaseActionRequest. */
export interface CaseActionRequest {
  action: OfficerAction; reason_code?: ReasonCode; note?: string;
  docs_kind?: DocsKind; due_date?: string | null; assignee_id?: string | null;
  withdrawn_enrolment_ids?: string[];
  correction?: { enrolment_id?: string; fields: Partial<Record<CorrectableField, string | number | boolean | null>> };
  approval_version?: number;
  dry_run?: boolean;
}
export interface DecisionEffects {
  case_status: FlagStatus;
  records: { enrolment_id: string; status: EnrolmentStatus; record_status: RecordStatus | null; status_reason: string | null }[];
  version: number | null; changes: FieldChange[];
  rows_resolved: number; rows_rerun: number;
  seats_released: { enrolment_id: string; seat_code: string }[];
  seats_assigned: { enrolment_id: string; seat_code: string }[];
  attestations_revoked: { enrolment_id: string; credential_id: string; short_id: string }[];
  attestations_issued: { enrolment_id: string; credential_id: string; short_id: string }[];
  approval: { version: number; approved_intake: number; cohort_year: string; programme_code: string } | null;
}
export interface DryRunResult { dry_run: true; effects: DecisionEffects }
/** Replaces the A3.27 FlagRow. */
export interface FlagRow {
  id: string; type: FlagType; severity: Severity; status: FlagStatus;
  institution: InstitutionRef; programme: ProgrammeRef | null; enrolment_id: string | null; academic_year: string;
  summary: string; related_count: number; assignee: { id: string; name: string } | null;
  response_received: boolean; docs_due_on: string | null; last_action_at: string | null;
  covers: CheckType | null; scope: CaseScope;
  decision: { action: DecisionAction; reason_code: ReasonCode; at: string } | null;
  signal_id: string | null;
  created_at: string; updated_at: string;
}
/** Replaces the A3.27 FlagListQuery. */
export interface FlagListQuery {
  page?: number; page_size?: number; type?: FlagType; severity?: Severity; status?: FlagStatus;
  institution_id?: string; programme_id?: string; state?: string; academic_year?: string; q?: string; sort?: FlagSort;
  assignee?: "me" | "none" | string; response_received?: boolean; signal_id?: string;
}
/** Replaces the A3.27 FlagDetail. */
export interface FlagDetail extends FlagRow {
  evidence: Evidence;
  enrolment: RelatedEnrolmentRow | null;
  related_enrolments: RelatedEnrolmentRow[];
  related_hidden: number;
  outstanding_enrolment_ids: string[];
  approval: { id: string; current_version: number; approved_intake: number; covers: boolean } | null;
  missing_students: MissingStudent[];
  history: CaseHistoryItem[];
  allowed_actions: OfficerAction[];
  can_respond: boolean;
}
export interface CaseActionResult extends FlagDetail { effects: DecisionEffects }

// ---------- signals ----------
export interface SignalRow {
  id: string; type: SignalType; academic_year: string; status: SignalStatus; summary: string;
  member_count: number; members_hidden: number; score: number | null;
  institutions: { id: string; name: string; aicte_permanent_id: string; state_code: string; region: Region }[];
  institutions_hidden: number;
  rule: string; cases: { id: string; institution_id: string; status: FlagStatus }[];
  created_at: string; updated_at: string;
}
export interface SignalFeature {
  name: "admission_growth" | "nri_share" | "management_share" | "contradiction_rate" | "contact_sharing_rate";
  value: number; peer_low: number; peer_high: number; peer_median: number; robust_z: number; stands_out: boolean;
}
export interface SignalMember {
  enrolment_id: string; student: { id: string; name: string; apaar_masked: string | null; provisional_id: string | null };
  institution: { id: string; name: string }; programme_code: string; record_status: RecordStatus | null;
}
export interface SignalDetail extends SignalRow {
  facts: EvidenceFact[];
  shared: { kind: "MOBILE" | "EMAIL" | "ADDRESS"; masked: string; students: number }[];
  features: SignalFeature[];
  members: SignalMember[];
  dismissal: { note: string; by: { id: string; name: string }; at: string } | null;
}
export interface SignalListQuery {
  page?: number; page_size?: number; academic_year?: string; type?: SignalType; status?: SignalStatus;
  institution_id?: string; state?: string; sort?: "newest" | "score";
}
export interface SignalOpenCase { institution_ids?: string[]; note: string; severity?: Severity }
export interface SignalOpenCaseResult { cases: FlagRow[]; signal: SignalDetail }
export interface SignalDismiss { note: string }
export interface SignalRun {
  academic_year: string; rings: number; anomalies: number; created: number; updated: number; duration_ms: number;
  model: { name: "IsolationForest"; contamination: number; n_estimators: number; random_state: number; institutions: number };
}

// ---------- reports ----------
export interface ReportInfo { name: ReportName; title: string; formats: ReportFormat[]; columns: string[] }
export interface ReportQuery { academic_year?: string; region?: Region; state?: string }

// ---------- attestations and certificate integration ----------
/** Replaces the A3.27 GraduateRow. */
export interface GraduateRow {
  enrolment_id: string;
  student: { id: string; name: string; apaar_masked: string | null; provisional_id: string | null };
  institution: { id: string; name: string; aicte_permanent_id: string };
  programme: { id: string; code: string; name: string; level: Level };
  academic_year: string; year_of_award: number;
  attestation: { credential_id: string; short_id: string; status: CredentialStatus; issued_at: string } | null;
}
/** Replaces the A3.27 GraduateListQuery. */
export interface GraduateListQuery {
  page?: number; page_size?: number; q?: string; institution_id?: string; academic_year?: string;
  attestation?: "issued" | "not_issued"; university_id?: string;
}
/** Replaces the A3.27 DegreePrint. */
export interface CertificatePrint {
  enrolment_id: string;
  student: { name: string; id_kind: IdKind; id_masked: string };
  programme: { code: string; name: string; short_name: string };
  institution: { name: string; aicte_permanent_id: string; short_name: string };
  university: { code: string; name: string };
  academic_year: string; year_of_award: number;
  attestation: {
    credential_id: string; short_id: string; status: CredentialStatus; issued_at: string; revoked_at: string | null;
    jws: string; verify_url: string; lookup_url: string; qr_svg: string;
  } | null;
}

// ---------- privacy ----------
/** Replaces the A3.27 MyDataExport (enrolments carry states, the record and the history). */
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
    seat_code: string | null; record_status: RecordStatus | null; status_reason: string | null;
    checks: {
      type: CheckType; state: EvidenceState; finding: string | null; source_line: string; summary: string;
      supplied_by: string; observed_at: string | null; checked_at: string | null;
    }[];
    flags: { type: FlagType; status: FlagStatus; summary: string; created_at: string }[];
    history: Omit<EnrolmentVersion, "actor">[];
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
```

### A4.25 Sections C and E update: mockgov and datagen output for Week 4

Supersedes the matching lines of sections C and E, A2.24 and A3.28. Everything not mentioned stays as it is.

**mockgov principle.** Every new route is a labelled simulator. The joinings list (C.10) is the one route that returns stored names and dates of birth: the authority shares its joining list with AICTE for reconciliation, and the api uses those values only in memory to match.

**C.1 and C.8 Chaos.** `source` gains `admission_authority`; `GET /healthz` and `GET /admin/chaos` report it. The DigiLocker OAuth routes (C.11, C.12) stay outside the chaos gate, like `GET /digilocker/ui`, so sign-in works while "DigiLocker" notices are switched off; the `digilocker` toggle still covers `POST /digilocker/notify`.

**C.3 `POST /counselling/verify`** stays and is no longer called by the api.

**C.4 `POST /abc/credits`.** Each semester gains the issuing body:

```json
200 { "apaar_id_known": true, "semesters": [ { "sem": 1, "credits": 22, "uploaded_at": "2026-01-20T00:00:00Z", "result": "PASS", "issuer": "MSTU", "issuer_name": "Maharashtra State Technical University" } ] }
```

`issuer` is a university code, or the AICTE permanent id of a college that issues its own credits (an autonomous college, e.g. `1-PQR-0007`).

**C.9 `POST /admission-authority/joining`** (chaos source `admission_authority`).

```json
req  { "state": "MH", "academic_year": "2026-27", "name": "Ravi Kumar Sharma", "dob": "2007-03-21", "roll_no": null, "institution_code": "1-ABC-0001", "programme": "CSE" }
200  { "found": true,  "joined_on": "2026-08-02", "round": 1, "route": "COUNSELLING", "category": "GENERAL", "published": true }
200  { "found": false, "joined_on": null, "round": null, "route": null, "category": null, "published": true }
200  { "found": false, "joined_on": null, "round": null, "route": null, "category": null, "published": false }
```

- A match needs the same `state`, `academic_year`, `institution_code` and `programme`, the same `dob`, and a name score of 90 or more (`token_set_ratio` on mockgov's normalised names, as C.2); `roll_no`, when given, must match exactly instead of the name. The api sends no `roll_no` (the upload's `counselling_ref` is an allotment reference).
- `route`: `COUNSELLING`, `MANAGEMENT`, `NRI`, `SPOT`, `LATERAL` or `TFW` (management, NRI and spot admissions are in the authority's approved-admissions list too); `round` is null outside counselling. International admissions are not in this record (they are in Study in India).
- `published` is false when the authority has no joining row at all for that `state` and `academic_year`; it is true otherwise, found or not.
- `academic_year` is the year the student joined this programme (for a lateral entrant, the year it entered year 2).

**C.10 `GET /admission-authority/joinings?institution_code&academic_year`** (chaos source `admission_authority`). Both parameters required (422 otherwise).

```json
200 {
  "institution_code": "1-ABC-0001", "academic_year": "2026-27", "published": true,
  "items": [ { "roll_no": "MHCET-2026-004512", "name": "Ravi Kumar Sharma", "dob": "2007-03-21", "programme": "CSE",
               "joined_on": "2026-08-02", "round": 1, "route": "COUNSELLING", "category": "GENERAL", "apaar_last4": "4417" } ]
}
```

Every joining of the institution in that year, sorted by programme, `joined_on`, then `roll_no`; `apaar_last4` null when the authority has no APAAR for the student; `roll_no` may be null for non-counselling routes. `published` as in C.9.

**C.11 `GET /digilocker/oauth/authorize`** (HTML, outside the chaos gate). Query `response_type=code`, `client_id`, `redirect_uri`, `scope=openid`, `state`, `nonce`. The client id and redirect URI must match mockgov's `DIGILOCKER_CLIENT_ID` and `DIGILOCKER_REDIRECT_URIS` (default `countersign-demo` and `http://localhost:3000/api/auth/digilocker/callback`), else a 400 page "Unknown client or redirect address.". The page is plain and says at the top "Demo DigiLocker. A simulator for the Countersign demo, not the real DigiLocker." It lists synthetic accounts (the manifest's demo accounts first, Ravi Kumar Sharma at the top; `?q=` searches by DigiLocker id or APAAR), and has a field for the OTP and a Cancel link. It posts to `POST /digilocker/oauth/authorize` (form fields: the query parameters, `account` (a DigiLocker id or an APAAR) and `otp`). The OTP is always `123456`; a wrong OTP or an unknown account shows the page again with "Wrong OTP." or "No such account." (200). On success mockgov stores a one-time code (60 seconds) and answers `302` to `{redirect_uri}?code={code}&state={state}`; Cancel answers `302` to `{redirect_uri}?error=access_denied&state={state}`.

**C.12 `POST /digilocker/oauth/token`** (`application/x-www-form-urlencoded`: `grant_type=authorization_code`, `code`, `redirect_uri`, `client_id`, `client_secret`).

```json
200 { "access_token": "dl_at_...", "token_type": "Bearer", "expires_in": 600, "scope": "openid", "id_token": "<JWT>" }
400 { "error": "invalid_grant", "error_description": "The code is unknown, expired or used." }
401 { "error": "invalid_client", "error_description": "Unknown client or wrong secret." }
```

The id token is a JWT signed HS256 with the client secret (`DIGILOCKER_CLIENT_SECRET`, shared with the api through `.env`). Header `{"alg": "HS256", "typ": "JWT"}`; claims `iss` (mockgov's `DIGILOCKER_ISSUER`, default `http://localhost:8001/digilocker`), `sub` (the DigiLocker id), `aud` (the client id), `iat`, `exp` (`iat` + 600), `nonce` (from the authorize request), `name`, `birthdate` (`YYYY-MM-DD`), `gender` and `apaar_id` (12 digits, or null when the account has no APAAR). Errors follow OAuth (`error`, `error_description`), not the mockgov envelope. A code is used once.

**Files written by datagen** (`/data/generated/`):

- `institutions.json`: institutions gain `autonomous` (bool; datagen only, the importer ignores it). Each approval gains `versions`: `[{"version", "approved_intake", "effective_from", "source"}]` in ascending order, the approval's `approved_intake` equal to the last one's. The importer writes `approval_versions` and `current_version` and builds the pools from the current version. ABC College of Engineering CSE 2026-27 has v1 90 (`2026-03-15`, "AICTE EoA 2026-27") and v2 120 (`2026-05-20`, "AICTE EoA 2026-27, revised"), so the excess stays 132 against 120; about one approval in ten elsewhere has two versions.
- Upload files have the 22 columns of §A4.16. Every legitimate NRI-route row has `nri_sponsored` yes, every legitimate TFW row `tfw_income_certified` yes, every INTERNATIONAL row of nationality `IN` `ciwg` yes; planted ELIGIBILITY_BREACH rows break one rule each, and a few TFW rows leave the certificate blank (Seat PENDING, not a case).
- `column_mappings.json` (new): `{"<aicte_id>": {"<their header>": "<template column>"}}`. Those colleges' files (XYZ Institute of Technology among them) are written with their own headers; the seed saves the mapping (`PUT /institutions/{id}/column-mapping`, or the same service in-process) before their first upload.
- `mockgov/admission_joinings.jsonl` (new): `{state, academic_year, name, dob, roll_no, institution_code, programme, joined_on, round, route, category, apaar_id}`, one line per joining of every cohort on the roll: every uploaded, legitimate, non-international student; plus the students planted as missing from uploads (joined, never uploaded); and no line for rows planted as NOT_IN_JOINING_RECORD (uploaded, never joined). Ghost-ring members have joining lines (rings are found by signals, not by rows). The ABC College sample-card record (below) has no line.
- `mockgov/abc_credits.jsonl` gains `issuer` and `issuer_name`: the affiliating university for most colleges; the college itself for autonomous ones (their credits are self-issued).
- `mockgov/digilocker_accounts.jsonl` (new): `{digilocker_id, name, dob, gender, apaar_id}`; one account per APAAR registry entry (as notices already assume), plus accounts with `apaar_id` null, or with an APAAR the college never stored, for the refused-consent students the demo claims with.
- `manifest.json` gains:
  - `reporting_deadline`: `{"2026-27": "2026-09-30"}` (mirrors `rules.yaml`).
  - `uploads`: `[{"file", "aicte_id", "academic_year", "submitted_at"}]` for every initial and update file; the seed sets each SEED batch's `created_at` (the wire `uploaded_at`) to `submitted_at`, the only business time a SEED batch carries. Most initial files are submitted before the deadline; `late_colleges` (submitted after it) and `overdue_colleges` (no file at all for the year) list the planted ones by AICTE id.
  - `demo_digilocker_accounts`: `[{"role", "digilocker_id", "name", "dob", "apaar_id", "file", "row_no"}]` with roles `DEMO_STUDENT` (Ravi Kumar Sharma), `SECOND_DEMO_NOTICE`, `PROVISIONAL_CLAIM` (a refused-consent ABC College CSE first-year with an email address and a joining record, who becomes COUNTERSIGNED after claiming), `SOMEONE_ELSE` (an account that matches no notice the demo opens) and `SAMPLE_CARD` (the student of the sample card).
  - `sample_card`: `{"file", "row_no"}`, the deck's sample record: an ABC College B.Tech CSE 2026-27 first-year with a linked APAAR (Identity Confirmed), a seat under approval v2 (Seat Confirmed), no line in the joining record (the demo runs after the 30 Sep deadline, so Joining record reads Contradicted, "State admission authority · {date checked}"), credits Not yet due, and a planted No in `notice_replies.jsonl` (Student Contradicted, "I never joined"); the record reads Disputed, priority.
  - `perf` (only with `--perf N`): `{"institutions_file", "file", "rows"}` (below).
- `notice_replies.jsonl`: unchanged in shape; the `SAMPLE_CARD` row answers NO with the comment "I never joined this college.".
- `ground_truth.json`:
  - `expected_flag` gains `NOT_IN_JOINING_RECORD`, `ELIGIBILITY_BREACH` and `MISSING_FROM_UPLOAD`. A row may appear in more than one record (the sample card is both STUDENT_DENIED and NOT_IN_JOINING_RECORD).
  - GHOST_RING records change to `expected_flag: null` with `expected_signal: "GHOST_RING"` (signals never raise a case on their own). New ANOMALY records: `{"anomaly_type": "ANOMALY", "institution_aicte_id", "expected_flag": null, "expected_signal": "ANOMALY", "features": ["nri_share", ...]}`.
  - New institution-level records: `MISSING_FROM_UPLOAD` (`{"institution_aicte_id", "academic_year", "missing": n, "expected_flag": "MISSING_FROM_UPLOAD", "severity_expected": "MEDIUM"}`), `LATE_UPLOAD` and `OVERDUE_UPLOAD` (`{"institution_aicte_id", "expected_deadline_state": "LATE" | "OVERDUE", "expected_flag": null}`).
  - Record-level records may carry `expected_record_status`: the sample card DISPUTED; new `CLEAN_INDEPENDENT` records (COUNTERSIGNED without any reply), `SELF_ISSUED_ONLY` records (second-years at an autonomous college in a state whose authority has published no 2025-26 joining record, so their Joining record row is PENDING and not contradicted, with `reply: NONE` in `notice_replies.jsonl`: their only confirmed enrolment row is their own credits, so they stay AWAITING_EVIDENCE), `PROVISIONAL_UNCLAIMED` (AWAITING_EVIDENCE before the claim).
  - Rows not named by any record are the known-clean set the evaluation scores false alarms against.
- `perf/` (only with `--perf 50000`, used by `make eval`): `perf/institutions.json` (one synthetic college "Countersign Throughput Test College", AICTE id `9-PERF-0001`, in an existing state, with programmes and approvals large enough to seat every row), `perf/9-PERF-0001_2026-27.csv` (exactly N rows, every row legitimate) and `perf/mockgov/*.jsonl` (its registry, joining, credits and DigiLocker lines). Nothing in `perf/` is loaded by `make seed`.

**Seed order** (`make seed`, `make demo-reset`): mockgov seed (`--reset` drops and recreates its tables, then loads the new files); `python -m app.seed.cli --from /data/generated` (institutions with approval versions, users, graduates, column mappings, every upload through `run_batch` with its `submitted_at`, then `send_notices_for_batch` per batch); `python -m app.seed.replies --from /data/generated`; then `python -m app.seed.derived --from /data/generated` (completeness for every institution, then signals for the year, ENGINES §17.15).
