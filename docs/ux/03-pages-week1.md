# Week 1 pages

Each page: purpose, wireframe, elements with their data source (endpoint and field), states, microcopy, tables, density, keyboard and accessibility. Copy ids in brackets live in `05-copy-deck.md`. Shared rules first, then nine pages.

## 0. Shared rules for every page

Data loading
- Server components fetch with the `cs_access` cookie; client tables use TanStack Query with the `/api` proxy. First paint shows skeletons sized like the real content, never a spinner alone.
- Loading longer than 3 s shows the line "Still loading" under the skeleton. Never block the shell; the nav is always usable.
- Every list shows `total` from the envelope, e.g. "50 institutions".

Error rendering
- 401 anywhere: full-page [err.UNAUTHENTICATED] with "Sign in" linking to `/login?next=`.
- 403: full-page [err.FORBIDDEN] with the role sentence and "Go to my overview".
- 404 on a detail page: [err.NOT_FOUND_institution] and "Back to overview".
- 5xx or `INTERNAL`: inline card [err.INTERNAL] with "Try again" (refetch) and "Ref: INTERNAL".
- Network failure: [err.NETWORK].
- Partial failure (one tile fails, others load): the tile shows "Could not load" with a retry icon; the page stays.

Number and date formatting
- `Intl.NumberFormat("en-IN")` for counts (1,20,000). Right-aligned, `font-variant-numeric: tabular-nums`.
- Dates `14 Jul 2026`, timestamps `14 Jul 2026, 09:30 IST`. Relative time ("2 min ago") only in the Sources panel, with the absolute time on hover.
- Week 1 nulls render "Not yet computed" in muted text; zero renders "0".

Masked identifiers
- `apaar_masked` printed in monospace exactly as received (`XXXX XXXX 4417`). When null, print `provisional_id` with the prefix label "Provisional id". Never compose the mask client-side.
- `mobile_masked` and email appear only on `/student`.
- Any table that contains a student column carries the footer line [privacy.read_logged].

Badges (exact words)
- Institution type: Government, Government aided, Private self-financed, University department, Deemed.
- Consent: Linked, Refused, Pending, International.
- Enrolment status: Active, Withdrawn, Transferred, Graduated.
- Seat status: Free, Assigned, Released.
- Source status: OK, Unavailable, Disabled.
- Flag status: Open, Documents requested, Cleared, Escalated, Confirmed. Severity: Low, Medium, High.

Countersign strip (shared component, used from Week 2; Week 1 renders the empty variant)
- Five fixed segments in order Identity, Admission, Seat, Studying, Student, each 12 x 12 px with a 2 px gap, with text "n of m" to the right.
- PASS = filled, FAIL = filled with a cross, PENDING = hollow, NA = hatched grey.
- Week 1 (`score: null`, `checks: []`): five hollow grey segments and the text "Not yet checked".
- Tooltip per segment: "<Check> : <Status word> (<source>, <checked_at>)".
- `aria-label="Countersigned 4 of 5. Identity pass, Admission pass, Seat fail, Studying pending, Student pass."`

## 1. `/login`

Purpose: sign in, and for the demo pick a role in one click without anyone typing a password on stage.

```
+----------------------------------------------------------------------+
| [mark] Countersign              Every enrolment, countersigned.       |
+----------------------------------------------------------------------+
|                                                                      |
|   Sign in                                                            |
|   Pick a demo role or use your email.            [Demo] credentials  |
|                                                                      |
|   +------------------+ +------------------+ +------------------+     |
|   | AICTE officer    | | Regional officer | | Registrar        |     |
|   | National         | | Western (Mumbai) | | ABC College of   |     |
|   | admin@aicte.demo | | ro.west@aicte... | | Engineering      |     |
|   +------------------+ +------------------+ +------------------+     |
|   +------------------+ +------------------+ +------------------+     |
|   | Registrar        | | Student          | | University       |     |
|   | XYZ Institute    | | Ravi Kumar Sharma| | MSTU controller  |     |
|   +------------------+ +------------------+ +------------------+     |
|                                                                      |
|   Email     [registrar@abc.edu.demo              ]                   |
|   Password  [••••••••••••••••          ] (Show)                      |
|   [ Sign in ]                                                        |
|   ( inline error line here )                                         |
|                                                                      |
|   Demo passwords are shared and reset nightly. Not for real data.    |
+----------------------------------------------------------------------+
```

Elements
- Role cards: static list from ARCHITECTURE §7 (email, role label, scope label). Not fetched. `ro.south@aicte.demo` is intentionally absent from the cards (keeps six cards; it stays usable by typing).
- Email, Password inputs: `POST /auth/login {email, password}`.
- Error line: from `error.message` (401) or `error.details.fields[]` (422).

States
- Idle; Card selected (form prefilled, "Sign in" focused); Submitting (button "Signing in", inputs disabled); Error (inline); Rate limited (banner, button disabled with countdown "Try again in 28 s"); Signed in (redirect, no flash of the login form on refresh).

Microcopy
- Heading [login.heading] "Sign in". Subheading [login.sub] "Pick a demo role or use your email."
- Button [login.submit] "Sign in". Loading "Signing in".
- Show password toggle: "Show" / "Hide".
- Footer [login.demo_footer].
- Errors: [err.INVALID_CREDENTIALS], [err.RATE_LIMITED], [err.NETWORK].

Density: single column, max width 720 px; cards 3 per row on desktop, 1 per row under 640 px.

Keyboard and accessibility
- Cards are `<button type="button">` with `aria-pressed`; `Enter` or `Space` selects and moves focus to "Sign in".
- Form submits on `Enter` from either field. Error line has `role="alert"`.
- Labels are real `<label for>`; no placeholder-only labels. Autocomplete `username` / `current-password`.

## 2. `/aicte` (national overview)

Purpose: the officer's ranked, defensible view of the whole country in one screen, without a map.

```
+------------------------------------------------------------------------------+
| [mark] Countersign   All India           [ / Search institutions ]  Admin ▾  |
+----------+-------------------------------------------------------------------+
| Overview |  Overview                         Academic year [2026-27 ▾]        |
| Cases    |                                                                   |
| Reports  |  +----------+ +----------+ +-------------+ +----------+ +-------+ |
| System   |  |Institut- | |Programmes| |Approved     | |Enrolments| |Open   | |
| Audit    |  |ions   50 | |     212  | |seats 18,960 | |  10,342  | |flags 0| |
|          |  +----------+ +----------+ +-------------+ +----------+ +-------+ |
|          |  +---------------------------+                                    |
|          |  | Countersigned             |   Sources   APAAR OK  Couns OK     |
|          |  | Not yet computed          |             ABC OK    SII Unavail  |
|          |  +---------------------------+             DigiLocker OK  2m ago  |
|          |                                                                   |
|          |  Institutions ranked                       [state ▾] [type ▾]     |
|          |  Name            Permanent id  State  Region  Progs Seats Enrol Flags|
|          |  ABC College ...  1-ABC-0001   MH     West     6    540   571    0 |
|          |  ...                                                              |
|          |  50 institutions                              ‹ 1 2 ›             |
|          |                                                                   |
|          |  By state                                                         |
|          |  State          Region   Institutions Programmes Seats Enrol Flags|
|          |  Andhra Pradesh South Central   4         17      1,500  812    0 |
|          |  ...                                                              |
|          |                                                                   |
|          |  By region (10 rows, same columns minus Programmes)               |
+----------+-------------------------------------------------------------------+
```

Elements and data
- Scope label in top bar: `GET /dashboard/summary` -> `scope.label`.
- Academic year selector: `academic_year`; changes re-fetch with `?academic_year=`. Week 1 has one option.
- KPI tiles: `kpis.institutions`, `kpis.programmes`, `kpis.approved_seats`, `kpis.enrolments`, `kpis.flags_open`. Sixth tile "Countersigned": `kpis.countersigned_pct`; null -> "Not yet computed"; when present "`{pct}`% of enrolments fully countersigned" (a share, not a score).
- Sources panel: `GET /admin/adapters/ping` (AICTE_ADMIN only; on `/ro` the panel is hidden because the endpoint is 403 for RO). Shows each of `sources.apaar|counselling|abc|digilocker|sii` with `status` and `latency_ms`; `checked_at` as relative time; adapter name as a small chip ("mockgov"). Refresh every 60 s and on focus.
- Institutions table: `GET /institutions?page&page_size=25&sort&order&state&type&q`.
- By state: `by_state[]`. By region: `by_region[]`.

Institutions table columns, in order
| Column | Field | Align | Sortable | Default |
|---|---|---|---|---|
| Name (link to `/aicte/institutions/{id}`) | `name` | left | yes (`name`) | |
| Permanent id | `aicte_permanent_id` | left, mono | no | |
| State | `state_code` with `state_name` tooltip | left | no | filter |
| Region | `region` mapped to region name via `/meta/regions` | left | no | filter (hidden on `/ro`) |
| Type | `type` badge | left | no | filter |
| Programmes | `programmes` | right | no | |
| Approved seats | `approved_seats` | right | yes (`approved_seats`) | |
| Enrolments | `enrolments` | right | yes (`enrolments`) | default sort desc in Week 1 |
| Open flags | `flags_open` | right | yes (client-side in W1; `sort=flags_open` proposed) | default sort desc from Week 2 |
| Integrity Index | `integrity_index` | right | W4 | "Not yet computed" |

Default sort rule: Week 1 `sort=enrolments&order=desc` (ties broken by `name`). From Week 2, `flags_open desc, enrolments desc`. The header tooltip says "Ranked by open flags, then enrolments".
Filters: State (from `/meta/states`), Type, and the search box (`q`). Filters are URL query params so a view can be shared.
Page size 25, pager with "1 to 25 of 50".

By state table columns: State (`state_name`), Region (`region` name), Institutions, Programmes, Approved seats, Enrolments, Open flags. Sorted by `state_name` as delivered. Rows are links to `/aicte?state=MH` (applies the filter to the institutions table and scrolls to it). Flags column shows "0" in Week 1, not blank.
By region table: Region (`region_name`), Institutions, Approved seats, Enrolments, Open flags. Sorted by `region_name`.

States
- Loading: tiles show skeleton digits; tables show 8 skeleton rows.
- Empty institutions (filters too narrow): [empty.institutions_filtered] with "Clear filters".
- Empty by_state: [empty.by_state] (only possible before seed).
- Sources panel error (ping fails): panel shows "Sources: could not check" with retry; the rest of the page is unaffected.
- Any source `UNAVAILABLE`: that row amber with `detail` on hover ("timeout after 3000 ms"); `DISABLED` grey with "Real adapter disabled".

Microcopy
- Page heading [aicte.heading] "Overview". Section headings "Institutions ranked", "By state", "By region", "Sources".
- Tile labels: "Institutions", "Programmes", "Approved seats", "Enrolments", "Open flags", "Countersigned".
- Tile sublabel for Open flags in Week 1: "Checks start in Week 2" is NOT shown to a panel; show nothing.
- Search placeholder [search.placeholder] "Search institutions by name or permanent id".

Density: tiles 96 px tall; table rows 36 px; page max width 1280 px; left nav 220 px. Under 1024 px the By state and By region tables stack and the Sources panel moves below the tiles.

Keyboard and accessibility
- `/` or `Ctrl+K` focuses search. `Esc` clears it.
- Tables are real `<table>` with `<th scope="col">`; sort buttons inside headers with `aria-sort`.
- Row links are the name cell `<a>`; the whole row is clickable via CSS only, keyboard uses the link.
- Tiles are `<dl>` pairs, not headings.
- Colour never carries meaning alone: Unavailable has the word, not just amber.

## 3. `/aicte/institutions/[id]` (institution detail)

Purpose: everything an officer needs to say "this college claimed X, the sources say Y" for one institution.

```
+------------------------------------------------------------------------------+
| Overview / ABC College of Engineering                                        |
|                                                                              |
| ABC College of Engineering                      Integrity Index              |
| 1-ABC-0001 · Private self-financed · Pune, MH   Not yet computed             |
| Western region · Maharashtra State Technical University · est. 2004          |
|                                                                              |
| [ Programmes ] [ Enrolments 571 ] [ Seats ] [ Flags 0 ]                      |
|                                                                              |
| Programmes (6)                                   Academic year 2026-27       |
| Code Programme                 Level Shift Approved Admitted Seated Unseated |
| CSE  B.Tech Computer Science   UG    First   120      132     120     12 ▲   |
|   ▸ pools  Regular 114/114 · NRI 6/6 · TFW 4 of 6 (supernumerary) ·          |
|            Lateral 0 of 12 (supernumerary) · International 1 of 18 (CIWG 6)  |
| ECE  ...                                                                     |
|                                                                              |
| Flags (0)                                                                    |
| No flags open. Flags appear here after the first upload is checked.          |
+------------------------------------------------------------------------------+
```

Elements and data (`GET /institutions/{id}`)
- Header: `name`, `aicte_permanent_id` (mono), `type` badge, `address_city` + `state_code` ("Pune, MH"; omit city when null), region name (map `region` via `/meta/regions`), `university_name` (link to nothing in Week 1), `established_year` ("est. 2004"; omit when null).
- Integrity Index block: `integrity_index` null -> "Not yet computed"; W4 shows number with "Why this score" link to `/score`.
- Tabs: Programmes (default), Enrolments (count = sum of `programmes[].enrolments`, or the `total` from the enrolments endpoint once loaded), Seats, Flags (`flags_open`).
- Programmes table: `programmes[]`.
- Pools expander per row: `pools[]`: `seat_type`, `assigned`, `capacity`, `is_supernumerary`, `reserved_for`. Format "Regular 114 of 114", "TFW 4 of 6 (supernumerary)", "International 1 of 18 (6 reserved for CIWG)". Free = `free`.
- Enrolments tab: see page 3b. Seats tab: see page 3c.
- Flags section: Week 1 always empty state [empty.flags_institution]. Week 2: `GET /flags?institution_id=`.

Programmes table columns
| Column | Field | Align | Notes |
|---|---|---|---|
| Code | `code` | left, mono | |
| Programme | `name` | left | |
| Level | `level` | left | Diploma, UG, PG, Post diploma |
| Shift | `shift` | left | First, Second |
| Approved | `approval.approved_intake` | right | header tooltip "Approved intake for 2026-27" |
| Admitted | `enrolments` | right | header tooltip "Active enrolments uploaded by the college" |
| Seated | `enrolments - unseated` | right | |
| Unseated | `unseated` | right | > 0 renders an amber chip with the number and tooltip [ledger.unseated_tip]; 0 renders "0" |
Default sort: `code` asc. No filters. Row expander (chevron) reveals pools.

Week 1 caveat (API_CONTRACT A.7): the seed leaves every enrolment unseated, so `unseated == enrolments` and `assigned == 0` everywhere. The page must still render; the Seated column will show 0. Do not special-case it; the Week 2 ledger fixes the data, not the UI.

States
- Loading: header skeleton, 4 skeleton rows.
- 404: [err.NOT_FOUND_institution].
- No programmes: [empty.programmes].

Microcopy
- Tab labels: "Programmes", "Enrolments", "Seats", "Flags".
- Pools expander button: "Show seat pools" / "Hide seat pools".
- Index block label "Integrity Index"; value "Not yet computed".

Density: header 2 lines; table rows 36 px; expander row 28 px of small text.

Keyboard and accessibility
- Tabs follow the WAI-ARIA tabs pattern (arrow keys move, `Tab` enters the panel). Tab state in the URL hash (`#enrolments`) so refresh keeps it.
- Expander is a `<button aria-expanded>` in the first cell.
- Heading order: h1 name, h2 per section.

### 3b. Enrolments tab (`/aicte/institutions/[id]/enrolments`)

Data: `GET /institutions/{id}/enrolments?page&page_size&programme_id&status&academic_year&q`.

```
| Programme [All ▾]  Status [Active ▾]  Year [2026-27 ▾]  [ Search name or last 4 of APAAR ]  |
| Student              APAAR / Provisional  Consent  Prog  Yr Route        Category Seat     Countersign    Flags |
| Ravi Kumar Sharma    XXXX XXXX 4417       Linked   CSE   1  Counselling  General  Unseated ○○○○○ Not yet        |
| ...                                                                                                             |
| 571 enrolments · Viewing student records is logged.                                            ‹ 1 2 3 … 23 ›   |
```

Columns
| Column | Field | Align | Notes |
|---|---|---|---|
| Student | `student.name` | left | no link in Week 1 |
| APAAR / Provisional | `student.apaar_masked` or `student.provisional_id` | left, mono | label prefix "PRV" is already in the id |
| Consent | `student.consent_status` badge | left | |
| Programme | `programme_code` | left, mono | filter `programme_id` from the detail's `programmes[]` |
| Year | `year_of_study` | right | |
| Route | `admission_route` in words | left | Counselling, Management, NRI, Spot, Lateral, International, TFW |
| Category | `category` | left | General, EWS, OBC, SC, ST, Other |
| Seat | `seat_code` or "Unseated" | left, mono | null -> muted "Unseated" |
| Countersign | `countersign` strip + "n of m" | left | Week 1 "Not yet checked" |
| Flags | `flags[]` severity chips | left | empty -> "" (blank, not a dash in the data cell; a visually hidden "none") |
| Uploaded | `uploaded_at` date | right | hidden under 1280 px |
Default: `status=ACTIVE`, `academic_year=2026-27`, sort as delivered by the API (no `sort` param exists; see gaps). Search box `q` (name or `apaar_last4`), debounced 300 ms.
Footer: "`{total}` enrolments" and [privacy.read_logged].
Empty: [empty.enrolments]. Empty with search: [empty.enrolments_search].

### 3c. Seats tab (`/aicte/institutions/[id]/seats`)

Data: `GET /institutions/{id}/seats?page&page_size&programme_id&seat_type&status`.
Columns: Seat code (`seat_code`, mono), Programme (`programme_code`), Type (`seat_type` in words), Reserved for (`reserved_for`, "CIWG" or blank), Status (`status` badge), Holder (`student_name` or blank), Assigned (`assigned_at` timestamp or blank).
Default: no filters, order as delivered (seat_code). Filters: Programme, Type, Status. Week 1 shows every seat Free. Footer "`{total}` seats · Viewing student records is logged." (the holder column is a student name).

## 4. `/ro` (regional overview)

Purpose: identical to `/aicte` with the region baked in; the officer must never wonder whether a number is national.

Differences from `/aicte`, everything else identical
- Heading [ro.heading] "Western region overview" built from `scope.label`. Top bar scope label the same.
- No Sources panel (endpoint is 403 for RO). In its place a one-line "Regional office: Mumbai" from `/meta/regions` `hq_city`.
- Institutions table: `GET /institutions` already region scoped; the Region column and the region filter are hidden.
- By state: `by_state[]` contains only the region's states. By region: `by_region[]` has one row; render it as a single summary line above By state rather than a one-row table ("Western region: 12 institutions, 4,500 approved seats, 2,600 enrolments, 0 open flags").
- Row links go to `/ro/institutions/{id}`.
- Nav: Overview, Cases (Week 2, disabled), Reports (Week 4, disabled).
- `/ro/institutions/[id]` is the same component as 3 with `/ro` crumbs and links.

## 5. `/college` (seat ledger)

Purpose: the registrar sees, per programme, approved versus admitted versus seated, and the pools, without any other college's numbers.

```
+------------------------------------------------------------------------------+
| [mark] Countersign   ABC College of Engineering                  Registrar ▾ |
+------------+-----------------------------------------------------------------+
| Seat ledger| Seat ledger                                 Academic year 2026-27|
| Upload (W2)|                                                                 |
| Enrolments | +----------+ +----------+ +------------+ +----------+            |
| Flags (W2) | |Programmes| |Approved  | |Admitted    | |Unseated  |            |
|            | |     6    | |seats 540 | |   571      | |  571     |            |
|            | +----------+ +----------+ +------------+ +----------+            |
|            |                                                                 |
|            | Programmes                                                      |
|            | Code Programme            Approved Admitted Seated Unseated Pools|
|            | CSE  B.Tech Computer ...    120      132     120     12 ▲   ▸    |
|            |   Regular 114 of 114 · NRI 6 of 6 · TFW 4 of 6 · Lateral 0 of 12 |
|            |   International 1 of 18 (6 reserved for CIWG)                   |
|            |   Pool sizes follow AICTE APH 2024-27. [What are pools?]        |
|            | ...                                                             |
|            |                                                                 |
|            | Flags against your college (0)                                  |
|            | No flags. Flags appear after your upload is checked. Nothing is |
|            | rejected automatically; an officer reviews every flag.          |
|            |                                                                 |
|            | Last upload: none yet. Upload opens in Week 2.                  |
+------------+-----------------------------------------------------------------+
```

Elements and data
- Top bar scope: `/me` `scope.institution_name`.
- Tiles: `GET /dashboard/summary` (scoped) `kpis.programmes`, `kpis.approved_seats`, `kpis.enrolments`; Unseated tile = sum of `programmes[].unseated` from `GET /institutions/{scope.institution_id}`.
- Programmes table: `GET /institutions/{scope.institution_id}` `programmes[]`, same columns as page 3 plus Pools expander opened by default for any row with `unseated > 0`.
- Pools line adds [ledger.pools_source] "Pool sizes follow AICTE APH 2024-27" with a "What are pools?" popover [ledger.pools_help]. Per-pool `rule_source` is not in the API (gap); use the generic line.
- Flags section: Week 1 empty state [empty.flags_college].
- Last upload line: Week 1 fixed text [college.no_upload_yet]; Week 2 from `GET /uploads?page_size=1`.

States: loading skeletons; 404 on own institution (should not happen) -> [err.INTERNAL]; no programmes -> [empty.programmes_college].

Microcopy
- Heading [college.heading] "Seat ledger".
- Tile labels: "Programmes", "Approved seats", "Admitted", "Unseated".
- Unseated chip tooltip [ledger.unseated_tip] "Enrolments beyond the approved intake or not yet given a seat. An officer reviews these; nothing is rejected automatically."
- Enrolments nav item opens `/college/enrolments`, the same table as 3b scoped to this college, with the same privacy footer.

Density: as officer pages (36 px rows). The registrar is a power user too.

Keyboard and accessibility: as page 3. The amber chip has the text "12 unseated" inside it, not colour only.

## 6. `/student` (my enrolment)

Purpose: the student sees exactly what is held about them, masked, and that nothing is decided without them.

```
+--------------------------------------------------------------+
| [mark] Countersign                                 Ravi ▾    |
+--------------------------------------------------------------+
|  My enrolment                                                |
|                                                              |
|  Ravi Kumar Sharma                                           |
|  APAAR  XXXX XXXX 4417   ·  Linked                           |
|  Date of birth 21 Mar 2007 · Mobile XXXXXX4521               |
|  Email ravi.sharma@example.demo                              |
|                                                              |
|  +--------------------------------------------------------+  |
|  | ABC College of Engineering says                        |  |
|  | you joined B.Tech Computer Science and Engineering     |  |
|  | Academic year 2026-27 · Year 1 · Active                |  |
|  |                                                        |  |
|  | Countersign  ○○○○○  Not yet checked                    |  |
|  | Identity · Admission · Seat · Studying · Student        |  |
|  +--------------------------------------------------------+  |
|                                                              |
|  Notices        You have no notices yet.                     |
|  My proofs      Proofs you can share arrive in Week 3.       |
|                                                              |
|  Only you can see your email and mobile here. Officers see   |
|  masked ids only. [How my data is used]                      |
+--------------------------------------------------------------+
```

Elements and data (`GET /students/me`)
- Name `name`; `apaar_masked` (or "Provisional id `provisional_id`" when null); `consent_status` badge; `dob` formatted; `mobile_masked`; `email` (nullable, omit line when null).
- One card per `enrolments[]`: `institution_name`, `programme_name`, `academic_year`, `year_of_study`, `status`, `countersign` strip.
- Notices: `notices[]` (empty in Week 1) -> [empty.notices_student]. Credentials: `credentials[]` -> [empty.credentials_student].
- Privacy line [privacy.student_line] with a link to `/student/privacy` (Week 3, disabled with "Coming in Week 3").

States: loading skeleton card; no enrolments -> [empty.enrolments_student]; 403 (wrong role) handled by layout redirect.

Microcopy
- Heading [student.heading] "My enrolment".
- Card lead [student.card_lead] "`{institution}` says you joined `{programme}`".
- Strip caption "Not yet checked" (Week 1), later "4 of 5 sources agree".
- Consent badge words: Linked, Refused, Pending, International; tooltip [consent.tip_<status>].

Density: single column, max width 640 px, 16 px gutters, 44 px tap targets, body 16 px.

Keyboard and accessibility: the card is a `<section aria-labelledby>`; the strip has the full aria-label; nothing is hover-only (tooltips also open on focus and tap).

## 7. `/university` (affiliated institutions)

Purpose: the controller of examinations sees affiliates read-only and finds the Degree print entry (Week 3).

```
+------------------------------------------------------------------------------+
| [mark] Countersign   Maharashtra State Technical University       COE ▾      |
+--------------+---------------------------------------------------------------+
| Affiliated   | Affiliated institutions                      Academic year ... |
| Degree print | +----------+ +----------+ +-------------+ +----------+         |
|   (W3)       | |Institut- | |Programmes| |Approved     | |Enrolments|         |
|              | |ions   12 | |     41   | |seats 3,600  | |  2,011   |         |
|              | +----------+ +----------+ +-------------+ +----------+         |
|              | Name          Permanent id  State  Type   Progs Seats Enrol    |
|              | ABC College   1-ABC-0001    MH     Private  6    540   571    |
|              | 12 institutions                                               |
|              |                                                               |
|              | Degree print opens in Week 3. You will pick a graduating       |
|              | student and print a degree insert with masked APAAR and a QR.  |
+--------------+---------------------------------------------------------------+
```

Elements and data
- Scope: `/me` `scope.university_name`.
- Tiles: `GET /dashboard/summary` (`scope.kind == "UNIVERSITY"`).
- Table: `GET /institutions` (affiliates only). Columns as `/aicte` minus Region, Open flags and Integrity Index (university does not act on flags). Row link `/university/institutions/{id}` (read-only detail, same component as page 3 with the Flags tab hidden and no actions).
- Degree print teaser [university.degree_teaser].

States: loading; empty affiliates [empty.affiliates].

Microcopy: heading [university.heading] "Affiliated institutions".

Density and keyboard: as `/aicte`.

## 8. `/verify` (public verifier shell)

Purpose: in Week 1, a public page that explains what will be verifiable and accepts nothing; from Week 3, the scan or paste entry.

```
+--------------------------------------------+
| [mark] Countersign  Verify a proof         |
+--------------------------------------------+
|  Verify an enrolment or degree proof       |
|                                            |
|  Scan the QR on the document, or paste     |
|  the code printed under it.                |
|                                            |
|  [ Scan with camera ]   (Week 3)           |
|  Code  [                       ] [Check]   |
|                                            |
|  Verification opens in Week 3. Until then  |
|  no code can be checked here.              |
|                                            |
|  What you will see: whether the proof is   |
|  valid, who issued it, and only the fields |
|  the student chose to share. Never a full  |
|  APAAR number.                             |
+--------------------------------------------+
```

Elements: no data in Week 1. Scan button and code input rendered disabled with the hint "Coming in Week 3". No login, no nav, no search. Footer link "What is Countersign?" to a static paragraph on the same page.

Week 3: `GET /verify/{code}` and the result states in `04-pages-later.md`.

Microcopy: heading [verify.heading]; lead [verify.lead]; placeholder [verify.placeholder] "e.g. K7PQ-3M2X-9ZAB"; disabled hint [verify.coming].

Density: single column 480 px, 44 px targets, works at 320 px wide. Keyboard: input and button in order; the disabled state uses `aria-disabled` and keeps the explanation visible to screen readers.

## 9. `/admin/system` (system and demo controls)

Purpose: the only page with demo machinery; proves the adapters are live, the audit chain is intact, and lets the presenter reset between runs.

```
+------------------------------------------------------------------------------+
| Overview / System                                                            |
| System                                                                       |
|                                                                              |
| Government sources            adapter: mockgov       Checked 09:30:12  [Ping]|
| Source                 Status        Latency   Detail                        |
| APAAR registry         OK            12 ms                                   |
| Counselling list       OK             9 ms                                   |
| ABC credits            OK            14 ms                                   |
| DigiLocker             OK             8 ms                                   |
| Study in India         Unavailable 3,004 ms   timeout after 3000 ms          |
|                                                                              |
| Audit chain                                              [Verify chain]      |
| 1,842 entries · Chain intact · Checked 09:30:12                              |
|                                                                              |
| Service health                                                               |
| API ok · Database ok · Redis ok · version 0.1.0                              |
|                                                                              |
| Demo controls                                                   [Demo]       |
| Chaos (mockgov)   Source [APAAR ▾]  Latency [0] ms  Fail rate [0.0]  [ ] Down|
|                   [Apply]  [Reset chaos]                                     |
| Reset demo data   [Reset demo data]   Drops and re-seeds. About 30 seconds.  |
+------------------------------------------------------------------------------+
```

Elements and data
- Sources table: `GET /admin/adapters/ping` -> `adapter`, `sources.*.status|latency_ms|detail`, `checked_at`. "Ping" re-fetches; button shows "Pinging" while in flight (the call can take 3 s per unavailable source; show that it is working).
- Audit: `GET /admin/audit/verify` on button press, not on load (it walks the chain). Result: `ok` -> "Chain intact"; `!ok` -> "Chain broken at entry `{first_broken_seq}`" in red with the word; `length` as "`{length}` entries".
- Service health: `GET /healthz` (`status`, `db`, `redis`, `version`).
- Chaos: mockgov `GET /admin/chaos` and `POST /admin/chaos` and `POST /admin/chaos/reset`. These are on `:8001`, not behind the `/api` proxy (gap). Until a proxy exists, render the Chaos block with the note "Use `curl localhost:8001/admin/chaos` for now" rather than a broken form.
- Reset demo data: proposed `POST /admin/demo/reset` (gap). Until it exists, show the CLI line "Run `make demo-reset`" instead of the button.

States
- Ping loading: rows keep their last values, status cell shows "checking".
- Ping error: [err.INTERNAL] inline in the panel.
- Verify never run: "Not checked yet. Press Verify chain."
- Chaos apply success: toast "Chaos applied to APAAR: down".

Microcopy
- Heading [admin.heading] "System". Section headings: "Government sources", "Audit chain", "Service health", "Demo controls".
- Buttons: "Ping", "Verify chain", "Apply", "Reset chaos", "Reset demo data".
- Source names: APAAR registry, Counselling list, ABC credits, DigiLocker, Study in India.
- Status words: OK, Unavailable, Disabled ("Real adapter disabled" in Detail).
- Reset sheet [admin.reset_confirm].

Density: compact, 32 px rows; this page is for the presenter.

Keyboard and accessibility: every control is a native button or input; the Demo block is wrapped in a `<section aria-label="Demo controls">`; status changes are announced through an `aria-live="polite"` region ("APAAR registry now Unavailable").
