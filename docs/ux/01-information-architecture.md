# Information architecture

Routes match `docs/ARCHITECTURE.md` §2 (route groups) and §4 (landing per role). Week numbers follow §10. A route whose endpoints are absent this week is listed in the nav as a disabled item with the hint "Coming in Week N" (ARCHITECTURE §10); it is never a dead link.

## 1. Global rules

- One app shell per role group. Shell = top bar (wordmark, scope label, user menu) + left nav (desktop) or bottom sheet nav (mobile) + content.
- Scope label in the top bar is `dashboard.scope.label` ("All India", "Western Region", "ABC College of Engineering") so the officer always knows what the numbers cover.
- User menu: name, role in words ("AICTE officer", "Regional officer, Western", "Registrar", "Student", "University controller"), "Sign out".
- Role mismatch on a route group redirects to that role's landing route (ARCHITECTURE §4). Show a one-line toast after redirect: "That page is for AICTE officers. You are signed in as a registrar."
- Public routes: `/login`, `/verify/*`, `/student/notices/[token]` (magic link, Week 3), `/healthz` is api only.
- Breadcrumbs appear on every page below the landing page, built from the route: `Overview / ABC College of Engineering / CSE`. The last crumb is plain text. The first crumb is the role's landing label.
- Page titles (`<title>`): `<page> | Countersign`. Landing: `Overview | Countersign`.

## 2. Sitemap per role

### AICTE_ADMIN (national)
Landing: `/aicte`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/aicte` | Overview | 1 | KPIs, state grid, ranked institutions, sources health |
| `/aicte/institutions/[id]` | (breadcrumb only) | 1 | Institution detail: programmes, seat pools, enrolments, flags |
| `/aicte/institutions/[id]/enrolments` | (tab inside detail) | 1 | Enrolment table with masked ids |
| `/aicte/institutions/[id]/seats` | (tab inside detail) | 1 | Seat ledger rows |
| `/aicte/cases` | Cases | 2 | National case queue (all open flags, ranked) |
| `/aicte/cases/[flagId]` | (breadcrumb only) | 2 | Flag detail and evidence, read only; actions from Week 3 |
| `/aicte/enrolments/[id]` | (breadcrumb only) | 2 | Enrolment detail: checks with sources, seat, flags, recheck |
| `/aicte/institutions/[id]/score` | (tab inside detail) | 4 | Integrity Index breakdown |
| `/aicte/reports` | Reports | 4 | Exportable summaries |
| `/admin/system` | System | 1 | Adapter ping, audit verify, demo controls |
| `/admin/audit` | Audit | 3 | Audit log table + verify chain |
| `/admin/psi` | Private matching | 4 | PSI demo |

Must NOT see: `/students/me` data, any unmasked identifier, student email or mobile, upload row raw PII (upload errors show `value_masked`).

### RO_OFFICER (region scoped)
Landing: `/ro`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/ro` | Overview | 1 | Same as `/aicte` scoped to the region; state grid shows only the region's states |
| `/ro/institutions/[id]` | (breadcrumb only) | 1 | Institution detail (404 if outside region) |
| `/ro/institutions/[id]/enrolments`, `/seats` | (tabs) | 1 | As above |
| `/ro/cases` | Cases | 2 | Region case queue |
| `/ro/cases/[flagId]` | (breadcrumb only) | 2 | Flag detail and evidence, read only; actions from Week 3 |
| `/ro/enrolments/[id]` | (breadcrumb only) | 2 | Enrolment detail (404 if outside region) |
| `/ro/reports` | Reports | 4 | Region reports |

Must NOT see: other regions' institutions (api returns 404; UI never lists them), `/admin/*`, national KPIs, chaos controls.

### INSTITUTION (registrar)
Landing: `/college`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/college` | Seat ledger | 1 | Per-programme approved vs admitted vs seated; pools |
| `/college/upload` | Upload | 2 | File upload and validation |
| `/college/uploads/[batchId]` | (breadcrumb only) | 2 | Batch status and row errors |
| `/college/enrolments` | Enrolments | 1 | Own enrolments with countersign strip (null in Week 1) |
| `/college/flags` | Flags | 2 | Flags raised against this college with evidence |
| `/college/enrolments/[id]` | (breadcrumb only) | 2 | Enrolment detail for own students |
| `/college/flags/[flagId]` | (breadcrumb only) | 2 | Flag evidence, read only; respond to a document request from Week 3 |
| `/college/score` | Why this score | 4 | Integrity Index breakdown |

Must NOT see: any other institution, region or national numbers, officer notes marked internal, student email or mobile (only masked), other colleges' duplicates (a cross-institution duplicate flag names "another institution in Maharashtra", never the name).

### STUDENT
Landing: `/student`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/student` | My enrolment | 1 | What is held on me, masked ids, countersign strip |
| `/student/notices/[token]` | (public magic link) | 3 | Yes or No to a notice |
| `/student/notices` | Notices | 3 | History of notices and replies |
| `/student/wallet` | My proofs | 3 | Credentials, share with chosen fields, QR |
| `/student/privacy` | Privacy | 3 | Consents, who viewed my record, data requests |

Must NOT see: other students, flags (a student sees "an officer is looking into this" only when they said No), institution tables, any officer note.

### UNIVERSITY (controller of examinations)
Landing: `/university`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/university` | Affiliated institutions | 1 | Read-only list of affiliates and their numbers |
| `/university/institutions/[id]` | (breadcrumb only) | 1 | Read-only detail |
| `/university/enrolments/[id]` | (breadcrumb only) | 2 | Read-only enrolment detail, no recheck, no flag links |
| `/university/degrees` | Degree print | 3 | Pick a graduating enrolment, print masked APAAR + QR |
| `/university/degrees/[enrolmentId]/print` | (print view) | 3 | Print layout |

Must NOT see: non-affiliated institutions (404), case actions, chaos controls, student contact details.

### VERIFIER (public, no login)
Landing: `/verify`

| Route | Week | Purpose |
|---|---|---|
| `/verify` | 1 shell, 3 real | Scan a QR or paste a code |
| `/verify/[code]` | 3 | Result page (what the QR lands on) |

Must NOT see: anything not inside the presented credential; no search by name, never a list.

## 3. Nav behaviour

- Nav items for absent endpoints render disabled with `aria-disabled="true"` and a tooltip "Coming in Week N". They do not navigate.
- The active item is marked with `aria-current="page"`.
- On mobile (< 768 px) the left nav becomes a bottom bar with at most 4 items plus "More".
- The wordmark links to the role landing route, never to `/`. `/` itself redirects: signed in -> landing route; signed out -> `/login`.

## 4. Global search

- Present only for officers (`/aicte`, `/ro`) and the university, in the top bar, shortcut `/` or `Ctrl+K`.
- Searches institutions only in Week 1: `GET /institutions?q=` (name or `aicte_permanent_id`), debounced 250 ms, shows at most 8 results with name, permanent id, state, open flags.
- Week 2 adds enrolment search inside an institution page only (`?q=` name or `apaar_last4`), never global. Reason: a global person search is a privacy surface a panel will ask about.
- No search for students or verifiers.
- Empty result: "No institution matches '<q>'. Try the permanent id, e.g. 1-ABC-0001."

## 5. Breadcrumb map

| Route | Crumbs |
|---|---|
| `/aicte/institutions/[id]` | Overview / ABC College of Engineering |
| `/aicte/institutions/[id]/enrolments` | Overview / ABC College of Engineering / Enrolments |
| `/aicte/cases/[flagId]` | Overview / Cases / Excess admission, ABC College |
| `/college/uploads/[batchId]` | Seat ledger / Upload / 1-ABC-0001_2026-27.csv |
| `/aicte/enrolments/[id]` | Overview / ABC College of Engineering / Enrolments / Ravi Kumar Sharma |
| `/college/enrolments/[id]` | Seat ledger / Enrolments / Ravi Kumar Sharma |
| `/college/flags/[flagId]` | Seat ledger / Flags / Excess admission in CSE |
| `/student/wallet` | My enrolment / My proofs |
| `/university/degrees/[id]/print` | Affiliated institutions / Degree print / Ravi Kumar Sharma |
| `/admin/audit` | Overview / Audit |

## 6. Landing page per role, one sentence each

- AICTE_ADMIN: the ranked list of institutions with the most open flags, above the state grid.
- RO_OFFICER: the same list, only their region, with the region name in the heading.
- INSTITUTION: their seat ledger per programme with the "unseated" column visible without scrolling.
- STUDENT: the one card "ABC College of Engineering holds this about you" with the countersign strip.
- UNIVERSITY: the list of affiliated institutions and a disabled "Degree print" item until Week 3.
- VERIFIER: a scan box and a paste box, nothing else.
