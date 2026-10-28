# Later pages (Weeks 2 to 4)

Lower fidelity than `03-pages-week1.md`: purpose, sketch, elements with their expected data, states and the key copy. Shared rules from `03-pages-week1.md` §0 apply. Week 2 pages read the endpoints and fields of `API_CONTRACT.md` Addendum 2 (§A2.x below); where an earlier proposal here differed, the contract replaced it. Endpoints marked (proposed) in Weeks 3 and 4 are not in the contract yet.

## Week 2

Nav from Week 2: the registrar's Upload and Flags items and the officers' Cases item become live. Every Week 2 page is read only for flags (officer actions arrive in Week 3). Copy ids refer to `05-copy-deck.md`; its §3 rule "Seats against admissions" applies to every page below.

### W2-1. `/college/upload` (the form)

Purpose: the registrar uploads one academic year's admissions file and signs the declaration.

```
Upload admissions file                               Academic year [2026-27 ▾]
One file covers one academic year of your college. It changes only the
students in it; students you leave out stay as they are.       [upload.lead]
+--------------------------------------------------------------------+
|  Drop a CSV or XLSX here, or [Choose file]                         |
|  [Download CSV template]  [Download XLSX template]                 |
|  Up to 20 MB and 50,000 rows                                       |
+--------------------------------------------------------------------+
Columns expected
  Required  name, dob, programme_code, year_of_study, admission_route, category
  Optional  apaar_id, gender, mobile, email, address, nationality, passport_no,
            academic_year, counselling_ref, consent_status, status,
            status_date, admission_date
To report a withdrawal or a transfer, upload that student's row again with
status Withdrawn or Transferred and the status date.     [upload.changes_note]
[ ] I declare that this file is true to the college's admission register,
    and that each APAAR in it is shared with that student's consent as
    recorded in the consent column.                      [upload.declaration]
[ Upload ]

Previous uploads
File                            Uploaded                By         Kind     Source       Status  Rows  Accepted  With errors  With warnings
1-ABC-0001_2026-27_update1.csv  28 Oct 2026, 11:40 IST  Registrar  Update   File upload  Done      14        12            2              1
1-ABC-0001_2026-27.csv          28 Oct 2026, 09:30 IST  Registrar  Initial  Demo seed    Done     605       605            0              0
```

Data:
- Academic year: default `2026-27`. A year with no approvals comes back as 422 `VALIDATION_ERROR` on `academic_year` ("Your college has no approvals for 2027-28.") shown under the select.
- Templates: plain links to `/api/uploads/template.csv` and `/api/uploads/template.xlsx`; the proxy keeps `Content-Disposition`, so the files save as `countersign_upload_template.*` (§A2.9).
- Columns panel: the 19 `UPLOAD_COLUMNS` in §A2.2 order, split into required and optional, names in monospace, [upload.columns_note] under them.
- Submit: `POST /uploads` as `multipart/form-data` with `file`, `academic_year` and `declaration=true` (§A2.4). No `kind` (the server sets it) and no `institution_id` (a registrar's own college). Sent with XMLHttpRequest so the button can read [upload.sending] while bytes go out. `202 {batch}` navigates to `/college/uploads/{batch.id}`.
- Previous uploads: `GET /uploads?academic_year=&page=` (§A2.6), newest first. Columns File (`filename`), Uploaded (`uploaded_at`), By (`uploaded_by.name`), Kind (`upload.kind.*`, tooltip [upload.kind_tip]), Source (`upload_source.*`), Status (`upload_status.*`), Rows, Accepted, With errors, With warnings (`counts.rows`, `.accepted`, `.errors`, `.warnings`). Each row links to its batch page. Empty: [empty.uploads].

States:
- Idle; file chosen ([upload.chosen] with "Remove file").
- Rejected in the browser before any request: wrong extension [upload.err_type]; over 20 MB [upload.err_size].
- Declaration not ticked: Upload stays enabled; pressing it shows [upload.err_declaration] under the checkbox and moves focus there.
- Sending: [upload.sending], inputs disabled.
- Server errors inline above the button, the chosen file kept: 413 [err.FILE_TOO_LARGE] or [err.TOO_MANY_ROWS]; 415 [err.UNSUPPORTED_FILE_TYPE]; 422 [err.UPLOAD_HEADER_INVALID] and [err.UPLOAD_HEADER_DUPLICATE] from `details.missing_columns` and `details.duplicate_columns`, then [upload.header_help]; 422 [err.UPLOAD_EMPTY]; 409 [err.UPLOAD_IN_PROGRESS] with [upload.in_progress_link] to `details.batch_id`.

Replaced by the contract: the Kind radio, the `{id, status}` response, the row count estimate.

### W2-2. `/college/uploads/[batchId]` (status, progress and row problems)

```
Seat ledger / Upload / 1-ABC-0001_2026-27_update1.csv
1-ABC-0001_2026-27_update1.csv    Update · File upload · uploaded 28 Oct 2026, 11:40 IST by Registrar
(✓) Queued ── (✓) Validating ── (●) Processing ── ( ) Done                 ███████░░░ 74%
Step 6 of 8: Checking with sources
Rows 14 · Accepted 12 · With errors 2 · With warnings 1

Checking against sources
APAAR registry: 9 checked
Counselling list: 6 checked
ABC credits did not respond for 3 checks. Those checks stay pending, not failed,
and run again at the next recheck or the next upload of those rows.

Upload processed                                      (when status is DONE)
12 rows accepted · 3 seats assigned · 1 unseated · 2 flags opened
2 new · 6 updated · 1 unchanged · 2 withdrawn · 1 transferred · 3 seats released
Flags are for review by an officer. A flag does not remove or change any enrolment.
[View seat ledger]  [View enrolments]  [View flags]

Row errors and warnings (3)            [All | Errors | Warnings]   [Download errors as CSV]
Row  Level    Column    Problem                          Value as uploaded
17   Warning  apaar_id  APAAR must be 12 digits          <11 characters>
41   Error    apaar_id  Same APAAR appears on row 12     XXXX XXXX 4417
58   Error    dob       Date of birth must be YYYY-MM-DD 21/03/2007
Fix the rows marked Error and upload them again, on their own or in the whole
file. Rows already accepted do not change when you upload them again.
Viewing student records is logged.
```

Data, `GET /uploads/{id}` (§A2.7), polled every 2 s while `status` is QUEUED, VALIDATING or PROCESSING; polling stops at DONE or FAILED:
- Header: `filename`; [upload.batch_meta] from `kind`, `source`, `uploaded_at`, `uploaded_by.name`.
- Rail: the five `upload_status.*` words. The current one is marked by an icon and the word, not by colour alone. FAILED takes the place of Done.
- Step line: [upload.step] with the stage's position (PARSE 1 to FLAGS 8) and `upload_stage.*`; QUEUED shows [upload.queued_note] instead.
- Progress bar: `progress_pct`, `role="progressbar"` with `aria-valuenow`; the api never lowers it and the web keeps the highest value seen.
- Counts: [upload.rows] from `counts`, shown from PROCESSING on (every key is 0 until its stage finishes).
- [upload.same_file] when `same_file_as` is set; [upload.ignored_columns] when `ignored_columns` is not empty.
- Sources, from CHECKS on: one [upload.source_line] per `sources[]` entry with `source.*` names, plus [upload.source_waiting] when `unavailable` is above 0.
- DONE: card with [upload.done_heading], [upload.done_summary], [upload.done_changes], [upload.done_note] and links to `/college`, `/college/enrolments`, `/college/flags`.
- FAILED: [upload.failed], then `error` verbatim, then [upload.failed_earlier], and a link [upload.upload_again] to `/college/upload`. The rail keeps the stage that failed.

Row problems, `GET /uploads/{id}/errors?page&page_size&level` (§A2.8), sorted by row then column, shown once VALIDATING is over:
- Columns: Row (`row_no`; the header is row 1), Level (`upload.level.*` word plus icon, tooltip `upload.level_tip.*`), Column (`field` in monospace, tooltip `field.*`), Problem (`message` verbatim), Value as uploaded (`value_masked` verbatim; null prints [upload.value_blank]).
- Level filter All, Errors, Warnings sets `level`. Heading count is `total` (entries; a row can have several).
- [upload.errors_download] is an `<a href="/api/uploads/{id}/errors.csv">`; the server names the file `<file stem>_errors.csv`.
- Empty: [upload.errors_none]. Footer [privacy.read_logged] (a Value cell can hold a name as uploaded).

Officers read the same component, without the upload links, at `/aicte/uploads/[batchId]` and `/ro/uploads/[batchId]`, linked from an institution's last upload line (optional in Week 2).

Replaced by the contract: `rows_total`, `rows_ok`, `rows_error` (now `counts.rows`, `.accepted`, `.errors`), per-source `{done, total, status}` (now `sources[].calls` and `.unavailable`), the `raw` column (now `value_masked`), the Checking status (now Processing with eight stages), and the error codes ROUTE_INVALID, YEAR_INVALID, CONSENT_INVALID (now BAD_ENUM per column and YEAR_OF_STUDY_INVALID). APAAR_FORMAT is a warning: the row is kept without its APAAR and the Identity check fails with an APAAR not verified flag.

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
