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

### W2-3. Countersign strip, live

One shared component. Input: the compact `countersign {score, checks: [{type, status}]}` from enrolment rows and `/students/me` (§A2.10, §A2.21), or the full `checks[]` from enrolment detail (§A2.11).

```
■ ■ ■ ▨ □  3 of 4
```

- Five segments in the order Identity, Admission, Seat, Studying, Student. PASS filled; FAIL filled with a cross; PENDING hollow; NA hatched grey. PENDING is never red.
- Text: [strip.score]; [strip.score_pending] only when a check other than Student is pending (`{pending}` leaves Student out). `score: null` prints [strip.not_checked] beside five hollow grey segments.
- The strip is one focusable control (one Tab stop per row). Hover, focus or tap opens a small popover listing the five checks: [strip.segment_tip] lines in lists, [strip.segment_tip_full] lines on enrolment detail. `aria-label` is [strip.aria]. All three use the pending words of copy deck §3: in lists a pending check other than Student reads "Pending" (lists carry no detail); Student reads "Notice not sent yet".
- Week 2 truth: the Student check is pending for every active enrolment, so nobody reads "4 of 4". The demo student reads "3 of 4" (Identity, Admission and Seat countersigned, Studying n/a, Student pending).

### W2-4. Enrolment tables (Enrolments tab, `/college/enrolments`)

Week 1 columns with these changes (§A2.10):
- Student is an `<a href>` to enrolment detail (W2-5).
- Seat: `seat_code` in monospace, or "Unseated" in muted text when null.
- Countersign: the live strip (W2-3).
- Flags: one chip per unresolved flag in `flags[]`, most severe first, with the type name and severity word (accessible name [flag.chip]); at most two chips, then "+n". The 12 unseated ABC CSE first-years each show Excess admission.
- New filters, in the URL with the `e_` prefix: Check (`check_type`), Result (`check_status`), Flags (`flagged`), Seat (`seated`). Result alone means "any check with this result"; Check and Result together mean "this check with this result"; Check alone is not sent. Empty with filters: [empty.enrolments_filtered].

### W2-5. Enrolment detail `/aicte/enrolments/[id]`, `/ro/enrolments/[id]`, `/college/enrolments/[id]`, `/university/enrolments/[id]`

Purpose: everything Countersign holds about one enrolment and which source agreed, in one place an officer can link to.

```
Overview / ABC College of Engineering / Enrolments / Ravi Kumar Sharma
Ravi Kumar Sharma                                      XXXX XXXX 4417  [APAAR linked]
B.Tech Computer Science and Engineering (CSE) · ABC College of Engineering
■ ■ ■ ▨ □  Countersigned 3 of 4                                [Recheck pending checks]

Student                            Enrolment
Date of birth  21 Mar 2007         Intake           2026-27 approval
Gender         Male                Year of study    1
Mobile         XXXXXX4521          Admission route  Counselling, MHCET-2026-R1-004512
Nationality    IN                  Category         General
                                   Status           Active since 28 Oct 2026
                                   Admitted on      2 Aug 2026
                                   Mode             Physical
                                   Source row       Row 2 of 1-ABC-0001_2026-27.csv

Seat
CSE-R-001 · Regular · 2026-27 approval · assigned 28 Oct 2026

Countersign checks
Check      Result               Source            Checked                 Detail
Identity   Countersigned        APAAR registry    28 Oct 2026, 15:32 IST  Name and date of birth match the APAAR registry (similarity 100 of 100).
Admission  Countersigned        Counselling list  28 Oct 2026, 15:32 IST  Found in the Maharashtra counselling allotments for CSE (2026), round 1.
Seat       Countersigned        Seat ledger       28 Oct 2026, 15:32 IST  Holds seat CSE-R-001 (Regular, 2026-27 approval).
Studying   n/a                  ABC credits       28 Oct 2026, 15:32 IST  First year, no result yet.
Student    Notice not sent yet  Student reply     28 Oct 2026, 15:32 IST  Notice not sent yet.

Flags on this enrolment
Medium  Duplicate within institution  Open  Rows 2 and 133 of 1-ABC-0001_2026-27.csv describe the same student.  28 Oct 2026
Viewing student records is logged.
```

Data, `GET /enrolments/{id}` (§A2.11):
- Routes are flat and thin over one shared component (pass `basePath` and the crumb root). Breadcrumbs: officers "Overview / <institution> / Enrolments / <name>"; registrar "Seat ledger / Enrolments / <name>"; university "Affiliated institutions / <institution> / <name>". Page title [enrolment.title].
- Header: `student.name`, `apaar_masked` or the provisional id, consent badge, `programme.name` and `code`, institution link, the strip from `countersign` with [enrolment.score_label].
- Student block: `dob`, `gender` (`gender.*`), `mobile_masked` as sent (not shown to the university; a null leaves the line out), `nationality`.
- Enrolment block: [enrolment.intake_value] from `cohort_year`, `year_of_study`, route word plus `counselling_ref`, category word, [enrolment.status_value], `admission_date`, `programme.mode` (`mode.*`), [enrolment.source_row] from `upload` (null: [enrolment.source_row_none]).
- Seat: [enrolment.seat_value] from `seat`; null prints [enrolment.unseated] and [enrolment.unseated_flag] linked to that flag (the SEAT check's `detail.flag_type`).
- Checks table: the five `checks` rows: Check (`check.*`), Result (deck §3 words), Source (`source.*`), Checked (`checked_at`, null prints [check.never]), Detail (`detail.summary` verbatim, plus [check.attempts] in small text when `attempts` is above 0). `checks: []` prints [empty.checks].
- Recheck: [recheck.enrolment] for AICTE officer, regional officer and registrar, shown only when a check other than Student is PENDING; `POST /enrolments/{id}/recheck` (§A2.12); the result appears in an `aria-live="polite"` region with the `recheck.*` lines, then the page refetches. 429 shows [err.RATE_LIMITED] with a countdown.
- Flags: `flags` (every status), severity chip, type name, status word, `summary` verbatim, `created_at` date. Rows link to flag detail for officers and the registrar; the university sees them as plain text (it cannot open `/flags`). Empty: [empty.flags_enrolment].
- Footer [privacy.read_logged]; the api writes a READ audit entry on every open.

States: skeleton while loading; 404 [err.NOT_FOUND_enrolment] with "Back to overview".

Replaced: the earlier drawer inside the enrolments table. A page has its own URL, so a flag can link to an enrolment and Back works.

### W2-6. Institution detail and the seat ledger, Week 2

`/aicte/institutions/[id]`, `/ro/institutions/[id]`, `/university/institutions/[id]` (§A2.20):
- Header figures, in this order: Approved seats and Admitted (both hinted [app.hint.intake]), Students on roll (hinted [app.hint.all_years]), Open flags (`flags_open`; hidden for the university).
- [last_upload.line] from `last_upload` (null: [college.no_upload_yet]); officers may link it to the batch page.
- Programmes table: Code, Programme, Level, Shift, Mode (`mode.*`), Approved, Admitted (`enrolments`, tooltip [col.admitted_tip]), Seated (`seated`), Unseated (`unseated`, amber chip when above 0). Pools line with real `assigned`.
- Enrolments tab: W2-4. Seats tab: real holders and assigned dates, same shape as Week 1.
- Flags tab, label "Flags ({flags_open})": `GET /flags?institution_id={id}&academic_year={year}&status=OPEN&sort=severity_desc`, the shared flags table without the Institution and State columns, count line [table.count.flags_one], empty [empty.flags_institution]. Hidden for the university.
- Officers (AICTE officer, regional officer) get [recheck.institution] in the header, tooltip [recheck.institution_tip]: `POST /institutions/{id}/recheck {academic_year}` (§A2.13); the result line [recheck.institution_result] (plus [recheck.flags_raised]) appears in an `aria-live` region. This is the button for the demo moment "the source is back".

`/college` (seat ledger):
- Tiles, all about one intake: Approved seats, Admitted, Seated, Unseated (sums over `programmes[]`), then the line [app.all_years_line] with `enrolments`.
- Flags: the five most severe open flags from `GET /flags?status=OPEN&page_size=5`, summaries verbatim, with [flags.see_all] to `/college/flags`; empty [empty.flags_college].
- [last_upload.line] linked to the batch page, and a link [upload.upload_again] to `/college/upload`.

### W2-7. Flag lists: `/aicte/cases`, `/ro/cases`, `/college/flags`, and the Flags tab

```
Cases                                                   37 open flags in 9 institutions
Status [Open ▾]  Severity [All ▾]  Type [All ▾]  Institution [All ▾]  State [All ▾]
[Search evidence, institution or permanent id]                Sort [Most severe first ▾]
Severity  Type                            Institution                  Programme  Evidence                                                          Related  Opened
High      Excess admission                ABC College of Engineering   CSE        132 admitted against 120 approved seats in CSE (2026-27); 12 wi…  12       28 Oct 2026
High      Duplicate across institutions   ABC College of Engineering   IT         The same student appears as active at ABC College of Engineer…    2        28 Oct 2026
Medium    Name or date of birth mismatch  XYZ Institute of Technology  ME         Name on upload differs from the APAAR registry (similarity 62 …    1        28 Oct 2026
1 to 25 of 37
```

Data, `GET /flags` (§A2.15): `status`, `severity`, `type`, `institution_id`, `state` (AICTE only), `programme_id` (once an institution is chosen), `q`, `sort`, `page`, and always `academic_year` (the selected year). Filters live in the URL with the `f_` prefix. Default `status=OPEN&sort=severity_desc` (High, Medium, Low, then oldest first; the Severity header carries [flags.sort_tip]).
- Columns: Severity (word chip), Type (`flag.<TYPE>.name`), Institution (link; dropped on the Flags tab and `/college/flags`), Programme (`programme.code`, blank when null), Evidence (`summary` verbatim on one line, full text on focus and hover), Related (`related_count`, tooltip [col.related_tip]), Opened (`created_at` date). Assignee stays hidden while every `assignee` is null.
- Count line per copy deck §18 from `total` and `institutions`; pager "1 to 25 of 37".
- Rows are `<a href>` to flag detail; `j` and `k` move, `Enter` opens.
- Empty without filters: [empty.cases] (officers), [empty.flags_college] (registrar), [empty.flags_institution] (Flags tab). Empty with filters: [empty.cases_filtered] with [empty.clear_filters].
- `/college/flags`: heading [flags.heading_college]; no Institution or State filter; the api redacts every row (a cross-institution duplicate reads "another institution in <state>").
- The regional officer only ever sees institutions of the region (the api scopes; the State filter lists the region's states).

Replaced by the contract: row fields `evidence.summary`, `opened_at`, `programme_code` (now `summary`, `created_at`, `programme.code`).

### W2-8. Flag detail: `/aicte/cases/[flagId]`, `/ro/cases/[flagId]`, `/college/flags/[flagId]` (read only)

```
Overview / Cases / Excess admission, ABC College of Engineering
Excess admission                                    High · Open · opened 28 Oct 2026
ABC College of Engineering · CSE · 2026-27
Read only for now. Clearing, requesting documents, escalating and confirming open in Week 3.

Evidence
132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat.
Fact               Value  Source
Approved intake    120    AICTE approval 2026-27
Admitted (active)  132    College uploads, Regular and NRI routes
Seated             120    Seat ledger
Unseated           12     Seat ledger
Rule: Approval record (approved_intake); minus NRI carve-out (APH 2024-27 cl. 2.8(b))

Related enrolments (12)
Student  APAAR / Provisional  Institution  Programme  Year  Route  Seat  Countersign  Flags
...
Viewing student records is logged.

History
28 Oct 2026, 15:32 IST   Flag opened
```

Data, `GET /flags/{id}` (§A2.16):
- Header: type name, [flag.meta], [flag.where] (or [flag.where_no_programme]), then [flag.readonly_officer] or, for the registrar, [flag.readonly_college]. No action bar.
- Evidence: `evidence.summary` verbatim; facts table (Fact, Value, Source) in the order sent, a null source left blank; [flag.rule] when `rule_source` is set. The registrar receives the redacted summary and facts; the page prints what it gets.
- [flag.enrolment_heading]: `enrolment` as one enrolments-table row with an Institution column; left out when null (Excess admission, Quota breach).
- [flag.related_heading]: `related_enrolments` as enrolments-table rows with an Institution column; officers see both institutions of a cross-institution flag. [flag.related_hidden] when `related_hidden` is above 0. Empty [empty.related]. Student cells link to enrolment detail.
- History: one line, [case.history.opened] with `created_at` (`history` is `[]` in Week 2).
- Footer [privacy.read_logged]; the api writes READ audit entries for every student shown.

States: 404 [err.NOT_FOUND_flag] with a link back to the list.

Replaced by the contract: `opened_at` (now `created_at`), `attachments`, and the action bar (moved to W3-8).

### W2-9. Dashboards: flags and the numbers rule

`/aicte` and `/ro` (§A2.19):
- Tiles in this order: Institutions, Programmes, Approved seats [app.hint.intake], Admitted [app.hint.intake], Students on roll [app.hint.all_years], Open flags (tooltip [kpi.flags_open_tip], links to the case queue), Countersigned ([kpi.countersigned_value], tooltip [kpi.countersigned_tip]), No source disagrees ([kpi.clear_value], tooltip [kpi.clear_tip]). A null percentage prints [kpi.not_computed].
- [section.flags_by_type]: `flags_by_type` rows with `open` above 0, in the order sent, `flag.<TYPE>.name` and the count, each linking to the case queue with `f_type=<TYPE>&f_status=OPEN`. All zero: [empty.flags_by_type].
- Institutions table: default `sort=flags_open_desc`; the Open flags header carries `aria-sort="descending"` and [table.sort_tip]. Columns Name, Permanent id, State, Region, Type, Programmes, Approved seats, Admitted, On roll ([col.enrolments_tip]), Open flags, Integrity Index.
- By state and By region: Approved seats, Admitted, On roll, Open flags. No fill percentage anywhere.
- Counts of open flags are ink with weight, never red; severity colour appears only on severity chips.

`/university`: Admitted after Approved seats; Enrolments becomes On roll with its tooltip; still no flags.

`/student`: the strip is live from `/students/me` with [student.strip_caption]; while the Student check is pending, [student.check_student_pending] sits under it.

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

### W3-7. Respond on `/college/flags/[flagId]`

The list and the read-only detail are live from Week 2 (W2-7, W2-8). Week 3 adds "Respond" when the status is Documents requested: note (required) + files; `POST /flags/{id}/response` (proposed). After submit: [college.respond_sent]. The read-only note goes.

### W3-8. Case actions on officer flag detail

The Week 2 detail (W2-8) gains history and actions:

```
History
14 Jul 09:31  System        Flag opened
15 Jul 11:02  RO West       Request documents: "Send admission register extract for CSE"
16 Jul 10:40  ABC Registrar Response + admission_register_cse.pdf (412 KB)

Actions
[ Clear ] [ Request documents ] [ Escalate ] [ Confirm ]            [ Add note ]
```

Data: `history[]` from `case_actions` with actor name and role, `attachments`; actions `POST /flags/{id}/actions {action, note, due_date?, assignee_id?}` (proposed), attachments via multipart.
Action sheets (all require a note): [case.clear_confirm], [case.request_docs_prompt], [case.escalate_prompt], [case.confirm_confirm]. The Confirm sheet repeats "Nothing is deleted. The enrolment keeps its status; the case record and your note are what change." The read-only note goes; the Assignee column appears in the queue.

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
