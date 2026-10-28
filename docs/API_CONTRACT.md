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
- **New enums** (also in §A2.22):
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
