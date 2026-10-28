# Later pages (Weeks 2 to 4)

Lower fidelity than `03-pages-week1.md`: purpose, sketch, elements with their expected data, states and the key copy. Endpoints marked (proposed) are not in `API_CONTRACT.md` yet; the shapes below are what the pages need and are listed as contract gaps in the final report. Shared rules from `03-pages-week1.md` §0 apply.

## Week 2

### W2-1. `/college/upload`

Purpose: the registrar uploads the admission file and takes responsibility for it.

```
Upload admissions file                       Academic year [2026-27 ▾]
+----------------------------------------------------------------+
|  Drop a CSV or XLSX here, or [Choose file]                      |
|  Template: [CSV] [XLSX]   Max 20 MB                             |
+----------------------------------------------------------------+
Columns expected: apaar_id, name, dob, gender, mobile, email, address,
nationality, passport_no, programme_code, academic_year, year_of_study,
admission_route, counselling_ref, category, consent_status
Kind  (•) Initial upload for this year  ( ) Update to an earlier upload
[ ] I declare that every student in this file has consented to their
    APAAR being used to verify this enrolment, and that the file is true
    to the college's admission register.                 [upload.declaration]
[ Upload ]
Previous uploads
File                 Uploaded          Kind    Status  Rows  OK   Errors
abc_2026-27.csv      14 Jul 2026 09:30 Initial Done    571   569  2
```

Elements: drop zone; kind radio (`INITIAL`, `UPDATE`); declaration checkbox (records a `consents` row with channel `UPLOAD_DECLARATION`); `POST /uploads` (proposed, multipart `file`, `academic_year`, `kind`, `declaration: true`) -> `{id, status}`; previous uploads `GET /uploads` (proposed, list of `upload_batches` fields).
States: idle; file chosen (name, size, row count estimate); uploading (progress); rejected client-side (type, size); server 413/415/422 inline.
Copy: heading "Upload admissions file"; [upload.drop]; [upload.err_type]; [upload.err_size]; [upload.declaration]; button "Upload"; previous uploads empty [empty.uploads].

### W2-2. `/college/uploads/[batchId]` (status and row errors)

```
Seat ledger / Upload / abc_2026-27.csv
abc_2026-27.csv                     Initial · 14 Jul 2026 09:30 · by Registrar
[Queued] -> [Validating] -> [Checking] -> [Done]        ████████░░ 80%
Rows 571 · Accepted 569 · Errors 2
Checking against sources:  APAAR ✓   Counselling ✓   Seat ledger ✓   ABC awaiting source, will retry

Row errors (2)                                   [Download errors as CSV]
Row  Field        Problem                                  Value
17   apaar_id     APAAR must be 12 digits                  12345678441
41   apaar_id     Same APAAR appears on row 12             XXXX XXXX 4417

What happens next: fix the rows in your file and upload it again as an
update. Accepted rows are already in the seat ledger.   [upload.errors_next]
```

Elements: `GET /uploads/{id}` (proposed) polled every 2 s until `DONE`/`FAILED`: `status`, `progress_pct`, `rows_total`, `rows_ok`, `rows_error`, `started_at`, `finished_at`, per-source progress (proposed `sources: [{source, done, total, status}]`); `GET /uploads/{id}/errors?page` (proposed): `row_no`, `field`, `code`, `message`, `raw` (masked).
Error codes to render with the copy deck: `APAAR_FORMAT`, `DUPLICATE_IN_FILE`, `UNKNOWN_PROGRAMME`, `DOB_FORMAT`, `MISSING_REQUIRED`, `ROUTE_INVALID`, `YEAR_INVALID`, `CONSENT_INVALID`, `PASSPORT_REQUIRED`.
States: each status in the rail; `FAILED` shows [upload.failed] with the reason; errors table empty when `rows_error == 0` ("No row errors"); download produces a CSV with the same columns.
Done summary card: "569 rows accepted · 557 seats assigned · 12 unseated · 3 flags opened" and [upload.done_note].

### W2-3. `/aicte/cases` and `/ro/cases` (case queue)

```
Cases                               37 open flags in 9 institutions
Status [Open ▾] Severity [All ▾] Type [All ▾] Institution [All ▾] State [▾]  [Search]
Sev   Type                 Institution              Evidence                                  Opened      Status
High  Excess admission     ABC College of Engg      132 admitted against 120 approved in CSE   2 d ago     Open
High  Student denied       ABC College of Engg      Student replied "not me" on 16 Jul         1 d ago     Open
Med   Name mismatch        ABC College of Engg      Upload name differs from registry (71/100) 2 d ago     Docs requested
```

Data: `GET /flags?status&severity&type&institution_id&state&page&sort` (proposed; rows carry `id, type, severity, status, institution {id, name}, programme_code, evidence.summary, opened_at, assignee`).
Default sort: `severity desc, opened_at asc` (oldest high first). Default filter `status=OPEN`. The count line is always visible.
Columns: Severity (word), Type (human name from copy deck `flag.<TYPE>.name`), Institution (link), Evidence (`evidence.summary`, single line, truncated with full text on hover), Opened (relative with absolute on hover), Status, Assignee (initials, AICTE only).
Keyboard: `j`/`k`, `Enter`. Row is a link to `/aicte/cases/{id}`.
Empty: [empty.cases] "No open flags. Flags appear here after uploads are checked."

### W2-4. `/aicte/cases/[flagId]` and `/ro/cases/[flagId]` (flag detail)

```
Overview / Cases / Excess admission, ABC College of Engineering
Excess admission                                   High · Open · opened 14 Jul 2026
ABC College of Engineering · CSE · 2026-27

Evidence
132 admitted against 120 approved seats in CSE (2026-27).
Approved intake      120        Source: AICTE approval 2026-27
Admitted (active)    132        Source: college upload abc_2026-27.csv, 14 Jul
Seated               120        Source: seat ledger
Unseated              12        Source: seat ledger
Rule                 APH 2024-27 cl. 2.8(b)                      [Open rule]

Related enrolments (12)                            Viewing student records is logged.
Student            APAAR           Route        Seat      Countersign
...

History
14 Jul 09:31  System        Flag opened
15 Jul 11:02  RO West       Request documents: "Send admission register extract for CSE"
16 Jul 10:40  ABC Registrar Response + admission_register_cse.pdf (412 KB)

Actions
[ Clear ] [ Request documents ] [ Escalate ] [ Confirm ]            [ Add note ]
```

Data: `GET /flags/{id}` (proposed: flag fields, `evidence {summary, facts[{label, value, source?}], rule_source?}`, `related_enrolments[]` as EnrolmentRow, `history[]` from `case_actions` with actor name/role, `attachments`). Actions `POST /flags/{id}/actions {action, note, due_date?, assignee_id?}` (Week 3), attachments via multipart.
Action sheets (all require a note): [case.clear_confirm], [case.request_docs_prompt], [case.escalate_prompt], [case.confirm_confirm]. The Confirm sheet repeats "Nothing is deleted. The enrolment keeps its status; the case record and your note are what change."
Institution view `/college/flags/[flagId]` shows the same evidence and history, no action bar, plus "Respond" (note + files) when status is Documents requested.
Cross-institution duplicates: the officer sees both institutions; the registrar sees "another institution in Maharashtra" (no name).

### W2-5. Enrolment detail drawer (inside enrolments tables)

Opened from the Student cell from Week 2. Shows: masked identity, the five checks as rows (Check, Status word, Source, Checked at, Detail summary), the seat, and the flags on this enrolment. Status words: Countersigned, Not countersigned, Awaiting source, n/a. `Esc` closes; focus returns to the row.

## Week 3

### W3-1. `/student/notices/[token]` (public notice page)

```
[mark] Countersign
ABC College of Engineering says
you joined B.Tech Computer Science and Engineering
Academic year 2026-27 · Year 1
They uploaded this on 14 Jul 2026 for APAAR XXXX XXXX 4417.

Is that right?
[ Yes, that is right ]
[ No, that is not me ]
If you say no, an AICTE officer will look into it. Nothing changes for you until then.
▸ What is this?
```

Data: `GET /notices/{token}` (proposed: `institution_name, programme_name, academic_year, year_of_study, apaar_masked|provisional_id, uploaded_at, expires_at, response, responded_at`). `POST /notices/{token}/respond {response: "YES"|"NO", comment?}`.
States: fresh; answered Yes [notice.yes_done]; answered No [notice.no_done]; already answered (shows the answer and "Change my answer" once within 7 days); expired [notice.expired]; invalid token [notice.invalid].
Consent: the page shows [consent.notice] in small text above the buttons; the Yes response records a `consents` row (`NOTICE`, `GIVEN`).
Hindi: a language toggle "हिन्दी" switches the headline, buttons and next-step line to [notice.*.hi] (marked for review in the copy deck).

### W3-2. `/student/notices` and `/student/wallet`

Notices list: Date, From (institution), Claim, Your reply (Confirmed / Denied / No reply yet), link to the notice page.
Wallet: one card per credential: kind ("Enrolment proof", "Degree"), issuer line "Issued by Countersign for ABC College of Engineering", issued date, status Active or Revoked. Buttons "Share proof", "Show details". Share sheet per Flow 5 with [consent.credential_share]; QR with the human code under it and "Shares n of m fields", "Valid for 10 minutes". History list "Shared with a verifier at 10:42".
Data: `GET /credentials`, `POST /credentials/{id}/present {fields}` -> `{code, qr_svg|url, expires_at}` (proposed).

### W3-3. `/student/privacy`

Sections: Consents (purpose in words, status, date, the exact text shown, "Withdraw" where allowed), Who viewed my record (from audit READ rows: role and date only, never officer names), Data requests (Access, Correction, Erasure forms -> `data_requests`). Copy [privacy.*].

### W3-4. `/verify` and `/verify/[code]`

Entry page as Week 1 but live: camera scan (getUserMedia, fallback to paste), code input, "Check" -> `GET /verify/{code}` (public, 60/min).
Result page states:
- Valid: large heading [verify.valid], issuer, issued date, the disclosed fields as a definition list, "Revocation checked just now", nothing else.
- Revoked [verify.revoked]; expired presentation [verify.expired]; malformed [verify.invalid]; rate limited [err.RATE_LIMITED].
Never shows a full APAAR, never offers search.

### W3-5. `/university/degrees` and print view

List: `GET /university/graduates?q` (proposed): name, institution, programme, year, masked APAAR, degree credential status. Row action "Print degree insert" or "Issue degree proof".
Print view: A4, no nav, `@media print`; university name, student name, programme, institution, year of award, "APAAR XXXX XXXX 4417", QR (DEGREE credential), "Scan to verify" with the verify URL. Button "Print" calls `window.print()`.

### W3-6. `/admin/audit`

Table from `GET /admin/audit?page&actor_id&entity_type`: Seq, Time, Actor (email), Action, Entity type, Entity id (short), Hash (first 8, full on hover). Filters by entity type and actor. "Verify chain" button as on `/admin/system`; result banner "Chain intact, 1,842 entries" or "Chain broken at entry 917" (the row is highlighted and scrolled into view).

### W3-7. `/college/flags` and `/college/flags/[flagId]`

List: same columns as the officer queue minus Assignee; status filter default All. Detail: evidence and history read-only, plus "Respond" when Documents requested: note (required) + files; `POST /flags/{id}/response` (proposed). After submit: "Sent to the officer. You will see their decision here."

## Week 4

### W4-1. `/aicte/institutions/[id]/score` and `/college/score` ("why this score")

```
Integrity Index  72 of 100             Rank 41 of 50 nationally · computed 20 Jul 2026
Start at 100, minus:
Component                 Count   Weight   Penalty   Source
Invalid or missing APAAR    7     0.5       3.5      rules.yaml integrity.invalid_id
Excess admissions          12     1.0      12.0      APH 2024-27 cl. 2.8(b)
Name mismatches             4     0.5       2.0
Student denied              1     5.0       5.0
Duplicates across colleges  3     1.5       4.5
No academic activity        2     0.5       1.0
= 72
What would raise it: resolve the 12 unseated enrolments (up to +12).
```

Data: `GET /scores/institutions/{id}` (proposed: `integrity_index`, `rank`, `of`, `computed_at`, `components[{key, label, count, weight, penalty, rule_source}]`). Always a number with its arithmetic visible; never a colour band on its own. The registrar sees the same table with the extra "What would raise it" line.

### W4-2. `/aicte/reports` and `/ro/reports`

Pre-built summaries: by state, by institution type, flags by type, countersign coverage, each as a table with "Download CSV". No charts without the table beside them. Any chart is a bar chart; never a map.

### W4-3. `/admin/psi` (private set intersection demo)

Two panels "Countersign holds" and "Partner registry holds" showing only counts; button "Compute overlap"; result "Overlap: 1,204 records. Neither side learned the other's members." with a short explanation [psi.explain]. A toggle "Show how" reveals the step list.

### W4-4. Fraud graph and anomaly panel (inside flag detail)

For `GHOST_RING` and `ANOMALY` flags the evidence card adds a small node-link drawing (students as dots, shared mobile/email/address as links) with the facts table beside it: "40 students across 3 institutions share 6 mobile numbers". The drawing is decorative support; the facts table is the evidence.
