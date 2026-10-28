# Information architecture

Routes match `docs/ARCHITECTURE.md` §2 (route groups) and §4 (landing per role). Week numbers follow §10. A route whose endpoints are absent this week is listed in the nav as a disabled item with the hint "Coming in Week N" (ARCHITECTURE §10); it is never a dead link. From Week 3 every route marked 3 below is live. Week 4 follows the frozen scope (the SIH deck, DECISIONS D34 to D49): records carry evidence states and one status, flags are called cases, proofs are attestations, students sign in only through DigiLocker, and the university page is certificate integration. Why this score is removed with the Integrity Index; only Private matching (and Evaluation, if it is not built) may stay disabled.

## 1. Global rules

- One app shell per role group. Shell = top bar (wordmark, scope label, user menu) + left nav (desktop) or bottom sheet nav (mobile) + content.
- Scope label in the top bar is `dashboard.scope.label` ("All India", "Western Region", "ABC College of Engineering") so the officer always knows what the numbers cover.
- User menu: name, role in words ("AICTE officer", "Regional officer, Western", "Registrar", "Student", "University controller"), "Sign out".
- Role mismatch on a route group redirects to that role's landing route (ARCHITECTURE §4). Show a one-line toast after redirect: "That page is for AICTE officers. You are signed in as a registrar."
- Public routes: `/login`, `/verify`, `/verify/[code]`, `/verify/d/[jws]`, `/auth/digilocker/return` (where DigiLocker sign-in lands) and `/student/notices/[token]` (the notice link shows its claim to anyone holding it, but answering needs DigiLocker sign-in, D37). `/healthz` is api only. Public routes have no nav and no breadcrumbs.
- The Demo DigiLocker is a mockgov page (`/digilocker/oauth/authorize`), not part of the web app; every screen of it is labelled "Demo DigiLocker, synthetic data".
- Renamed routes redirect (308) so links already sent keep working: `/college/flags*` to `/college/cases*`, `/university/degrees*` to `/university/certificates*`, `/aicte/institutions/[id]/score` and `/college/score` to the institution page and `/college`.
- Status is never shown by colour alone, on any route: a record status or evidence state is a word with an icon.
- Breadcrumbs appear on every page below the landing page, built from the route: `Overview / ABC College of Engineering / CSE`. The last crumb is plain text. The first crumb is the role's landing label.
- Page titles (`<title>`): `<page> | Countersign`. Landing: `Overview | Countersign`.

## 2. Sitemap per role

### AICTE_ADMIN (national)
Landing: `/aicte`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/aicte` | Overview | 1 | KPIs, state grid, ranked institutions, sources health |
| `/aicte/institutions/[id]` | (breadcrumb only) | 1 | Institution detail: programmes, seat pools, enrolments, cases |
| `/aicte/institutions/[id]/enrolments` | (tab inside detail) | 1 | Enrolment table with masked ids |
| `/aicte/institutions/[id]/seats` | (tab inside detail) | 1 | Seat ledger rows |
| `/aicte/cases` | Cases | 2 | National case queue (all open cases, ranked) |
| `/aicte/cases/[caseId]` | (breadcrumb only) | 2 | Case detail and evidence; from Week 4 the decisions Uphold claim, Correct record, Withdraw claim, with every consequence named |
| `/aicte/enrolments/[id]` | (breadcrumb only) | 2 | From Week 4 the record card: five rows with evidence state, source and date, the status and next step; history, attestations, cases |
| `/aicte/institutions/[id]/completeness` | (tab inside detail) | 4 | Completeness against the admission authority, deadline state, missing students (masked) |
| `/aicte/institutions/[id]/approvals` | (tab inside detail) | 4 | Approval versions per programme |
| `/aicte/signals` | Signals | 4 | Officer-only signals (shared contact rings, unusual patterns); never set a status |
| `/aicte/signals/[id]` | (breadcrumb only) | 4 | Signal facts, rule line, members; open a case or dismiss with a note |
| `/aicte/reports` | Reports | 4 | Reports by state, institution type, cases, coverage, completeness; CSV, XLSX, PDF; synthetic data label |
| `/admin/evaluation` | Evaluation | 4 | The synthetic evaluation report, if built |
| `/admin/system` | System | 1 | Adapter ping, audit verify, demo controls |
| `/admin/audit` | Audit | 3 | Audit log with filters, Verify chain and the broken entry marked |
| `/admin/data-requests` | Data requests | 3 | Students' correction and erasure requests, resolved with a written reply |
| `/admin/psi` | Private matching | 4 | PSI demo |

Must NOT see: `/students/me` data, any unmasked identifier, student email or mobile, upload row raw PII (upload errors show `value_masked`), a student's wallet or attestations (only what a student shares, through `/verify`), the student's DigiLocker id.

### RO_OFFICER (region scoped)
Landing: `/ro`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/ro` | Overview | 1 | Same as `/aicte` scoped to the region; state grid shows only the region's states |
| `/ro/institutions/[id]` | (breadcrumb only) | 1 | Institution detail (404 if outside region) |
| `/ro/institutions/[id]/enrolments`, `/seats` | (tabs) | 1 | As above |
| `/ro/cases` | Cases | 2 | Region case queue |
| `/ro/cases/[caseId]` | (breadcrumb only) | 2 | Case detail and evidence; decisions from Week 4 (on an escalated case, notes only) |
| `/ro/enrolments/[id]` | (breadcrumb only) | 2 | The record card (404 if outside region) |
| `/ro/institutions/[id]/completeness`, `/approvals` | (tabs) | 4 | As for AICTE, within the region |
| `/ro/signals`, `/ro/signals/[id]` | Signals | 4 | Signals touching the region's colleges; members in other regions collapsed to a count |
| `/ro/reports` | Reports | 4 | Region reports, labelled with the region |

Must NOT see: other regions' institutions (api returns 404; UI never lists them), members of a signal outside the region (shown only as a count), `/admin/*` (audit, data requests and evaluation included), national KPIs, chaos controls.

### INSTITUTION (registrar)
Landing: `/college`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/college` | Seat Ledger | 1 | Per-programme approved vs admitted vs seated; pools; from Week 4 records by status, completeness and the deadline |
| `/college/upload` | Upload | 2 | File upload and validation |
| `/college/uploads/[batchId]` | (breadcrumb only) | 2 | Batch status and row errors |
| `/college/upload`, step 2 | (step inside Upload) | 4 | Map your columns when the file's headers do not match; saved for next time |
| `/college/column-mapping` | (linked from Upload and the batch page) | 4 | The saved column mapping: see, change, clear |
| `/college/enrolments` | Enrolments | 1 | Own enrolments; from Week 4 the Status column and filter (the strip is retired) |
| `/college/cases` | Cases | 2 | Cases about this college with evidence (was `/college/flags`) |
| `/college/completeness` | Completeness | 4 | Completeness, deadline state, the missing students to upload |
| `/college/enrolments/[id]` | (breadcrumb only) | 2 | Enrolment detail for own students |
| `/college/cases/[caseId]` | (breadcrumb only) | 2 | Case evidence, history and the decision with its reason; Respond while documents are requested |

Must NOT see: any other institution, region or national numbers, officer notes marked internal, student email or mobile (only masked), other colleges' duplicates (a cross-institution duplicate case names "another institution in Maharashtra", never the name), the student's comment on a notice (officers only), an officer's name on a request or a decision (the role only), any signal (no route, no panel, no count; a case opened from a signal shows only its own students and its rule line, never the signal, its other colleges or its model score), the student's DigiLocker sign-in details.

### STUDENT
Landing: `/student`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/student` | My enrolment | 1 | What is held on me; from Week 4 the record card per enrolment (rows, status with its student line) and the line about my notice or the officer's decision |
| `/student/notices` | Notices | 3 | Every notice sent to me and my answer |
| `/student/notices/[token]` | (public notice link) | 3 | Shows the claim; Yes or No only after DigiLocker sign-in (Week 4); "This notice is for someone else" for another identity; English or Hindi |
| `/student/claim` | (linked when needed) | 4 | Claim a record without APAAR by its provisional ID |
| `/student/wallet` | My attestations | 3 | Enrolment and completion attestations; share chosen fields as a QR and code; sharing history |
| `/student/privacy` | Privacy | 3 | What I agreed to, who viewed my record (role and date), copy, correction and erasure requests |

Must NOT see: other students, cases (a student sees "an officer is looking into this" only after a No, then the outcome in plain words), signals, institution tables, any officer note, any officer's name (the access log shows roles), the case that holds back an attestation. A student does see their own record's rows, states, source lines and status.

Sign-in: only through DigiLocker (`/auth/digilocker/start`, then the Demo DigiLocker in the demo, then `/auth/digilocker/return`); no student password exists.

### UNIVERSITY (controller of examinations)
Landing: `/university`

| Route | Nav label | Week | Purpose |
|---|---|---|---|
| `/university` | Affiliated institutions | 1 | Read-only list of affiliates and their numbers |
| `/university/institutions/[id]` | (breadcrumb only) | 1 | Read-only detail |
| `/university/enrolments/[id]` | (breadcrumb only) | 2 | Read-only record card, no recheck, no case links |
| `/university/certificates` | Certificate integration | 4 | Graduates of affiliates; issue a completion attestation for a Countersigned record; the API line for the university's own system (was Degree print) |
| `/university/certificates/[enrolmentId]/print` | (print view) | 4 | The certificate block: masked APAAR and the completion attestation QR, no nav in print |

Must NOT see: non-affiliated institutions (404), case actions, signals, chaos controls, student contact details, notice answers, comments or delivery, a student's wallet beyond issuing a completion attestation into it. Countersign does not issue degrees; no university route says it does.

### VERIFIER (public, no login)
Landing: `/verify`

| Route | Week | Purpose |
|---|---|---|
| `/verify` | 1 shell, 3 live | Scan a QR, type a code, or paste attestation text |
| `/verify/[code]` | 3 | Result for a student's shared attestation (what the wallet QR lands on) |
| `/verify/d/[jws]` | 3 | Result for the completion attestation QR printed on a university's certificate |

Must NOT see: anything not inside the presented attestation, including why it was revoked; no search by name, never a list.

## 3. Nav behaviour

- Nav items for absent endpoints render disabled with `aria-disabled="true"` and a tooltip "Coming in Week N". They do not navigate.
- The active item is marked with `aria-current="page"`.
- On mobile (< 768 px) the left nav becomes a bottom bar with at most 4 items plus "More".
- Signals is a nav item for AICTE_ADMIN and RO_OFFICER only; for every other role it is absent, not disabled.
- The wordmark links to the role landing route, never to `/`. `/` itself redirects: signed in -> landing route; signed out -> `/login`.

## 4. Global search

- Present only for officers (`/aicte`, `/ro`) and the university, in the top bar, shortcut `/` or `Ctrl+K`.
- Searches institutions only in Week 1: `GET /institutions?q=` (name or `aicte_permanent_id`), debounced 250 ms, shows at most 8 results with name, permanent id, state, open cases.
- Week 2 adds enrolment search inside an institution page only (`?q=` name or `apaar_last4`), never global. Reason: a global person search is a privacy surface a panel will ask about.
- No search for students or verifiers. Signals are never searchable.
- Empty result: "No institution matches '<q>'. Try the permanent id, e.g. 1-ABC-0001."

## 5. Breadcrumb map

| Route | Crumbs |
|---|---|
| `/aicte/institutions/[id]` | Overview / ABC College of Engineering |
| `/aicte/institutions/[id]/enrolments` | Overview / ABC College of Engineering / Enrolments |
| `/aicte/cases/[caseId]` | Overview / Cases / Excess admission, ABC College |
| `/college/uploads/[batchId]` | Seat Ledger / Upload / 1-ABC-0001_2026-27.csv |
| `/aicte/enrolments/[id]` | Overview / ABC College of Engineering / Enrolments / Ravi Kumar Sharma |
| `/college/enrolments/[id]` | Seat Ledger / Enrolments / Ravi Kumar Sharma |
| `/college/cases/[caseId]` | Seat Ledger / Cases / Excess admission in CSE |
| `/college/completeness` | Seat Ledger / Completeness |
| `/college/column-mapping` | Seat Ledger / Upload / Column mapping |
| `/ro/cases/[caseId]` | Overview / Cases / Student dispute, ABC College |
| `/student/notices` | My enrolment / Notices |
| `/student/wallet` | My enrolment / My attestations |
| `/student/claim` | My enrolment / Claim your record |
| `/student/privacy` | My enrolment / Privacy |
| `/university/certificates` | Affiliated institutions / Certificate integration |
| `/university/certificates/[id]/print` | Affiliated institutions / Certificate integration / <graduate name> (on screen only; the print has no crumbs) |
| `/aicte/signals/[id]` | Overview / Signals / Shared contact ring |
| `/aicte/institutions/[id]/completeness` | Overview / ABC College of Engineering / Completeness |
| `/aicte/reports` | Overview / Reports |
| `/admin/evaluation` | Overview / Evaluation |
| `/admin/audit` | Overview / Audit |
| `/admin/data-requests` | Overview / Data requests |

## 6. Landing page per role, one sentence each

- AICTE_ADMIN: Records by status (four tiles in the deck's legend order, with the evidence rule), then completeness and deadlines, open cases by type and the signals panel, then the institutions ranked by open cases, above the state grid.
- RO_OFFICER: the same, only their region, with the region name in the heading.
- INSTITUTION: their Seat Ledger per programme with the "unseated" column visible without scrolling, then their records by status, completeness and deadline.
- STUDENT: the record card for each enrolment a college reported in their name, with the status and its student line; reached only after DigiLocker sign-in.
- UNIVERSITY: the list of affiliated institutions, with Certificate integration in the nav.
- VERIFIER: a scan box and a paste box, nothing else.
