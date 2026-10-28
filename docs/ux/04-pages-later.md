# Later pages (Weeks 2 to 4)

Lower fidelity than `03-pages-week1.md`: purpose, sketch, elements with their expected data, states and the key copy. Shared rules from `03-pages-week1.md` §0 apply. Week 2 pages read the endpoints and fields of `API_CONTRACT.md` Addendum 2 (§A2.x below); where an earlier proposal here differed, the contract replaced it. Week 3 pages read the endpoints of DECISIONS D23 to D33, written out in API_CONTRACT Addendum 3. Week 4 pages read DECISIONS D34 to D49 and the frozen scope (the SIH deck); endpoints and fields marked (pending) are not in the contract yet.

## Week 2

Nav from Week 2: the registrar's Upload and Flags items and the officers' Cases item become live. Every Week 2 page is read only for flags (officer actions are W3-8). Copy ids refer to `05-copy-deck.md`; its §3 rule "Seats against admissions" applies to every page below.

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
- Before any reply the Student check is pending, so the demo student reads "3 of 4" (Identity, Admission and Seat countersigned, Studying n/a, Student pending); after Ravi answers Yes the strip reads "4 of 4" (W3-1).

### W2-4. Enrolment tables (Enrolments tab, `/college/enrolments`)

Week 1 columns with these changes (§A2.10):
- Student is an `<a href>` to enrolment detail (W2-5).
- Seat: `seat_code` in monospace, or "Unseated" in muted text when null.
- Countersign: the live strip (W2-3).
- Flags: one chip per unresolved flag in `flags[]`, most severe first, with the type name and severity word (accessible name [flag.chip]); at most two chips, then [flags.more]. The 12 unseated ABC CSE first-years each show Excess admission.
- New filters, in the URL with the `e_` prefix (`enrolments.filter.*`): Check (`check_type`), Result (`check_status`), Flags (`flagged`), Seat (`seated`). Result alone means "any check with this result"; Check and Result together mean "this check with this result"; Check alone is not sent. Empty with filters: [empty.enrolments_filtered].

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
- Flags tab, label [tab.flags_count] with `flags_open`: `GET /flags?institution_id={id}&academic_year={year}&status=OPEN&sort=severity_desc`, the shared flags table without the Institution and State columns, count line [table.count.flags_one], empty [empty.flags_institution]. Hidden for the university.
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

Evidence
132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat.
Fact               Value  Source
Approved intake    120    AICTE approval 2026-27
Admitted (active)  132    College uploads, Regular and NRI routes
Seated             120    Seat ledger
Unseated           12     Seat ledger
Rule: AICTE approved intake; minus NRI carve-out (APH 2024-27 cl. 2.8(b))

Related enrolments (12)
Student  APAAR / Provisional  Institution  Programme  Year  Route  Seat  Countersign  Flags
...
Viewing student records is logged.

History
28 Oct 2026, 15:32 IST   Flag opened
```

Data, `GET /flags/{id}` (§A2.16):
- Header: type name, [flag.meta], [flag.where] (or [flag.where_no_programme]), then, for the registrar, [flag.readonly_college]. Officers get the action bar and history of W3-8; the registrar gets Respond (W3-7).
- Evidence: `evidence.summary` verbatim; facts table (Fact, Value, Source) in the order sent, a null source left blank; [flag.rule] when `rule_source` is set. The registrar receives the redacted summary and facts; the page prints what it gets.
- [flag.enrolment_heading]: `enrolment` as one enrolments-table row with an Institution column; left out when null (Excess admission, Quota breach).
- [flag.related_heading]: `related_enrolments` as enrolments-table rows with an Institution column; officers see both institutions of a cross-institution flag. [flag.related_hidden] when `related_hidden` is above 0. Empty [empty.related]. Student cells link to enrolment detail.
- History: [case.history.opened] with `created_at`, then the `history` rows of W3-8.
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

Week 3 pages read the endpoints of DECISIONS D23 to D33 by the names below; request and response shapes, scoping and errors are written out in API_CONTRACT Addendum 3, and where this file and the contract differ, the contract wins. Copy ids refer to `05-copy-deck.md`.

Nav from Week 3: the student's Notices, My proofs and Privacy, the university's Degree print, and the AICTE officer's Audit and Data requests are live links. Only Week 4 items (Reports, Why this score, Private matching) stay disabled.

Phone first. The notice page (W3-1) and the verify pages (W3-4) are public and mostly opened on a phone; the student pages (W3-2, W3-3) are too. Each is specified at 390 px wide: one column, 16 px side gutters, body text 16 px, primary buttons full width and at least 48 px tall, other targets at least 44 px, nothing hover-only, no horizontal scroll, and the loading, empty and error states fit the same column.

### Changes to Week 2 pages

- Countersign strip (W2-3): the Student check is live. A Yes countersigns it, a No does not, and otherwise it is pending and reads [check.pending.student] "No reply yet" in lists. A pending Student check stays out of ", n pending". The demo student reads "3 of 4" until Ravi answers, then "4 of 4".
- Enrolment detail (W2-5): the Student row prints the api sentence verbatim (deck §15) with the Result word from `detail.notice_state` (deck §3); the page gains the Student notice block and Resend notice (W3-10).

```
Countersign checks
Check      Result         Source         Checked                 Detail
Identity   Countersigned  APAAR registry 28 Oct 2026, 15:32 IST  Name and date of birth match the APAAR registry (similarity 100 of 100).
...
Student    No reply yet   Student reply  28 Oct 2026, 15:40 IST  Notice sent on 28 Oct 2026; no reply yet.
```

- Flag lists (W2-7): the officers' case queue gains the Assignee column and the Assignee and Response filters (W3-8).
- Flag detail (W2-8): officers get history and actions (W3-8); the registrar gets Respond while documents are requested (W3-7) and [flag.readonly_college] otherwise.
- Dashboards (W2-9): the Countersigned tile rises above 0 as students confirm; its tooltip is [kpi.countersigned_tip].
- `/student`: under the strip, one of [student.check_student_pending], [student.check_student_sent], [student.check_student_expired] or [student.check_student_denied] (deck §8); the Notices and My proofs sections show the newest notice and proof and link to W3-2; [privacy.how_link] links to `/student/privacy`; the consent badge tooltip ends with [student.consent_change].
- `/university`: the Degree print teaser goes; the nav item is live.
- `/verify`: the Week 1 shell is replaced by W3-4.

### W3-1. `/student/notices/[token]` (public notice page)

Purpose: the person whose details a college uploaded says yes or no, from one link, without signing in.

```
390 px
+--------------------------------------+
| [mark] Countersign        [ हिन्दी ] |
|                                      |
| ABC College of Engineering says      |
| you joined B.Tech Computer Science   |
| and Engineering                      |
| Academic year 2026-27 · Year 1       |
| They uploaded this on 14 Jul 2026    |
| for APAAR XXXX XXXX 4417.            |
|                                      |
| Is that right?                       |
| By replying, you let AICTE record    |
| your answer ...     [consent.notice] |
| [       Yes, that is right       ]   |
| [       No, that is not me       ]   |
| If you say no, an AICTE officer will |
| look into it. Nothing changes for    |
| you until then.                      |
| > What is this?                      |
+--------------------------------------+
```

Data: `GET /notices/{token}` and `POST /notices/{token}/respond {response: "YES" | "NO", comment?}`, both public and limited to 30 per minute per IP (D32). The page reads the institution name, programme name and short name, academic year, year of study, `apaar_masked` or the provisional id, the upload date, `expires_at`, `response`, `responded_at`, and whether the one change of answer is used and until when it is allowed. Opening the page writes a READ audit entry with no actor (D29). A Yes records a NOTICE consent with the text of [consent.notice] (D24). A second respond within 7 days of the first reply is the one allowed change; after that the api answers 409 `NOTICE_ALREADY_CHANGED`.

What the page never shows: the student's name, date of birth, email or mobile. The claim and the masked id are enough for the right person to recognise it, and nothing more reaches whoever holds the link.

States:
- Loading: a skeleton of the claim and two button shapes; [shell.loading_slow] after 3 s.
- Fresh: as sketched. Page title [notice.page_title].
- No pressed: a sheet with [notice.no_confirm], an optional textarea labelled [notice.no_comment_label] (500 characters) with [notice.no_comment_hint] under it, then [notice.no_submit] and [notice.no_cancel]. Focus goes to the textarea; Esc or Go back closes the sheet and returns focus to the No button.
- Sending: the pressed button reads [notice.sending]; both buttons are disabled.
- Answered Yes: [notice.yes_done], [notice.yes_next] with the link [notice.see_proofs] (`/student/wallet`, sign-in needed), then [notice.change_window] and [notice.change].
- Answered No: [notice.no_done], then [notice.change_window] and [notice.change]. The comment is not shown back.
- Opened again within 7 days, answer not changed: [notice.answered], [notice.change_window], [notice.change].
- Change: [notice.change_heading], [notice.change_once], the claim, both buttons with the current answer marked [notice.current_answer] (word and icon) and disabled; the other button confirms as in Fresh (No opens the same sheet); then [notice.changed_done].
- Change used, or a 409 `NOTICE_ALREADY_CHANGED`: [notice.change_used]; no buttons.
- Change window over: [notice.answered] and [notice.change_closed]; no buttons.
- Expired (410 `NOTICE_EXPIRED`): [notice.expired]; no claim, no form.
- Not valid (404 `NOTICE_NOT_FOUND`, the same body for a malformed and an unknown token): [notice.invalid]; no claim, no form.
- Rate limited (429): [notice.rate_limited] with a countdown; the buttons stay disabled until it ends.
- Network or server error: [err.NETWORK] or [err.INTERNAL] with [err.retry]; the choice and the comment are kept, and a retry never sends twice.

Hindi: the toggle [notice.lang_hi] / [notice.lang_en] is a `<button aria-pressed>` whose label carries its own `lang`. With Hindi on, every string above uses its `.hi` row (deck §8), states and errors included, the content carries `lang="hi"`, and institution and programme names print as sent. The choice lasts for the visit.

Phone (390 px): the claim at 22 px, body 16 px; Yes above No, both full width, 48 px tall, 12 px apart and of equal weight (No is neither red nor a text link); the consent line in small text, at least 13 px; What is this? is a native disclosure.

### W3-2. `/student/notices` and `/student/wallet`

#### Notices

```
390 px
Notices
Messages asking you to confirm what a college told AICTE about you.

28 Oct 2026 · ABC College of Engineering
You joined B.Tech CSE (2026-27)
By email and DigiLocker
Your reply: Yes, on 28 Oct 2026
```

Data: the student's notices in `GET /students/me` `notices[]` (D23): institution, programme, academic year, channels, sent date, `expires_at`, `response`, `responded_at` and the change date. One block per claim (a notice sent by email and DigiLocker is one block), newest first; from 768 px a table with the [notices.col.*] headers.
- Your reply: [notices.reply.YES], [notices.reply.NO], [notices.reply.NONE] or [notices.reply.EXPIRED]; [notices.changed] in small text after a change; [notices.denied_line] under a No.
- An unanswered live notice shows [notices.reply_hint]. The list cannot link to the notice page: only a hash of each link is stored (D23).
- [notices.consent_off] above the list when the student withdrew notice consent.
- States: loading skeleton blocks; empty [empty.notices_student]; error [err.INTERNAL] with [err.retry].

#### Wallet

```
390 px
My proofs
Proofs you can show an employer or anyone else who needs to check
your enrolment. You choose what they see.
+------------------------------------+
| Enrolment proof           ✓ Active |
| ABC College of Engineering         |
| B.Tech Computer Science and        |
| Engineering                        |
| Issued by Countersign for ABC      |
| College of Engineering             |
| Issued 28 Oct 2026                 |
| Valid until 31 Aug 2027            |
| [         Share proof          ]   |
| Show details                       |
| Sharing history                    |
| 28 Oct 2026, 10:40: QR created,    |
| shares 3 of 8 fields               |
| Shared with a verifier at 10:42    |
+------------------------------------+
```

Share sheet, then its result:

```
Share this proof
Choose what to share
Institution and programme are always shared. Tick anything else the
verifier needs.
[x] Institution (always shared)  ABC College of Engineering
[x] Programme (always shared)    B.Tech Computer Science and Engineering
[ ] Name                         Ravi Kumar Sharma
[ ] Academic year                2026-27
[x] Year of study                1
[ ] Date of birth                21 Mar 2007
[ ] APAAR (masked)               XXXX XXXX 4417
[ ] Checks that agree (countersigned)
    Identity, Admission, Seat and Student, as of 28 Oct 2026
Shares 3 of 8 fields
I am creating a proof that shows only the fields I ticked. ...
[ ] I agree
[            Create QR            ]

            [ QR, 240 px ]
    K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF
Shares 3 of 8 fields
Shared: Institution, Programme, Year of study
Valid for 10 minutes · Expires in 9:42
The verifier can type this code at localhost:3000/verify instead of scanning.
[ Copy code ]  [ Copy link ]
[              Done               ]
```

Data: the student's own proofs from `GET /credentials` (kind, `short_id`, issuer, issued and expiry dates, revocation with its reason and date, the disclosable claims with their values, and each share with its dates and `verify_count`); `POST /credentials/{id}/present {fields, consent: true}` returns `{code, url, qr_svg, expires_at, disclosed, total}` (D26). A proof is issued by the api, never requested from this page: an enrolment proof appears once the Student check is countersigned, no check is not countersigned and no High flag is unresolved. Errors: 409 `CREDENTIAL_REVOKED` [err.CREDENTIAL_REVOKED]; 422 without consent [wallet.consent_required].

Elements:
- One card per proof: [wallet.kind.*], a status badge (icon and [wallet.status.*] word), institution and programme (a degree proof: university, programme and year of award), [wallet.issued_by] or [wallet.issued_by_degree], [wallet.issued_on], [wallet.valid_until], [wallet.share], and [wallet.details], which opens a definition list of every claim under [wallet.details_heading] with [wallet.proof_id].
- Revoked: badge Revoked, [wallet.revoked_line], the [wallet.revoked_reason.*] sentence and [wallet.revoked_help]; no Share. Expired: [wallet.expired_line]; no Share.
- No proof for an active enrolment: a card [wallet.not_issued_heading] with [wallet.not_issued.reply], [wallet.not_issued.checks] or [wallet.not_issued.denied] by the Student check. It never names a flag or a failed check.
- Share sheet: a modal dialog from 768 px, a full-height bottom sheet below (`role="dialog"`, `aria-modal="true"`, labelled by [wallet.share_heading]). The 8 fields of D26 in the deck §8 order, each a real checkbox with its label and the value it would share; institution and programme are checked, `aria-disabled="true"` and announced with [wallet.always_shared]. [wallet.shares] updates as boxes change, inside an `aria-live="polite"` region. [consent.credential_share] sits above [wallet.consent_label]; Create QR without the tick shows [wallet.consent_required] and focuses the checkbox. While sending, the button reads [wallet.creating].
- Result: `qr_svg` inline with `role="img"` and [wallet.qr_alt], at least 240 px with its quiet zone; the code under it in monospace, 18 px, selectable, exactly as sent; [wallet.shares] and [wallet.shared_fields]; [wallet.valid_for] and the countdown [wallet.expires_in] (screen readers hear [wallet.expires_in_sr] at 5 and at 1 minute only); [wallet.code_hint]; [wallet.copy_code] and [wallet.copy_link], confirming with [wallet.code_copied] or [wallet.copied] in the live region; [wallet.done]. At expiry the QR gives way to a dashed box with [wallet.expired_share] and [wallet.new_qr]; the old code stays, struck through, with the word Expired beside it.
- Sharing history: per proof, newest first: [wallet.history.created], then [wallet.history_item] rows (D27), [wallet.history_item_more] or [wallet.history.unused] as deck §8 says, and [wallet.history_note] under the list; empty [wallet.history_empty].
- Keyboard: Share proof opens the sheet with focus on the first unlocked checkbox (Name); Tab and Shift+Tab stay inside; Space toggles; Enter on Create QR sends; after Create QR focus moves to the code; Esc or Done closes and returns focus to Share proof.
- States: loading skeleton card; no enrolment and no proof [empty.credentials_student]; error [err.INTERNAL] with [err.retry].

Phone (390 px): one card per row, buttons full width; the bottom sheet scrolls inside itself with Create QR pinned to its foot.

### W3-3. `/student/privacy`

Purpose: the student sees what they agreed to and who looked at their record, and asks for a copy, a correction or an erasure (D30).

```
390 px
Privacy
What you agreed to, who has viewed your record, and requests
about your data.
> Read the privacy notice

What you agreed to
Using your APAAR to check your enrolment
Given on 28 Oct 2026
Recorded by your college when it uploaded your enrolment
> Show the exact text
Unlinking your APAAR is a correction request, because ...
[ Ask to unlink my APAAR ]

Notices asking you to confirm an enrolment
Given on 28 Oct 2026
Given when you replied Yes to a notice
> Show the exact text
[ Withdraw ]

Who viewed your record
Every time someone opens your record it is logged. You see
their role and the date, never their name.
Date          Who
28 Oct 2026   An AICTE officer
28 Oct 2026   Your college
28 Oct 2026   Someone who opened your notice link

Requests about your data
[ Make a request ]
Correction, sent 28 Oct 2026   Open
Waiting for a reply from AICTE
```

Data: `GET /privacy/notice` (public, versioned), `GET /students/me/consents`, `POST /students/me/consents/{purpose}/withdraw` for NOTICE and CREDENTIAL_SHARE, `GET /students/me/access-log` (READ entries about the student and their enrolments, role and date only), `POST /students/me/data-requests {kind, details}`, `GET /students/me/export.json`, and the student's own requests with their replies as API_CONTRACT Addendum 3 lists them.

Elements:
- Privacy notice: [privacy.notice_link] opens the notice in place (a disclosure) with [privacy.notice_version].
- Consents (deck §20): purpose words, state, the via line, and the exact stored text behind [privacy.consent_text_show] with [privacy.consent_version]. Withdraw opens a confirmation dialog with [consent.withdraw.NOTICE] or [consent.withdraw.CREDENTIAL_SHARE], [privacy.withdraw_confirm] and [privacy.withdraw_cancel], focus on Keep it; success shows [privacy.withdraw_done.*] in a live region and the row then reads [privacy.withdrawn_on]. The APAAR row has no Withdraw: it shows [consent.unlink_apaar] and [privacy.unlink_apaar], which opens the request form on Correction prefilled with [privacy.request.unlink_prefill]. Empty [privacy.consent_none].
- Access log: a two-column table (Date, Who), newest first, 25 rows then [privacy.access.more]. Who is a role phrase from deck §20, never a name, an email, an IP or another college. Empty [privacy.access_empty].
- Requests: [privacy.request.new] opens a form: a radio group [privacy.request.kind_label] with the three kinds and their hints, the details field labelled for the kind (required for Correction and Erasure, with [privacy.request.details_required] under an empty field), and [privacy.request.submit]. Access: the form gives way to [privacy.export_ready], [privacy.export_download] and [privacy.export_note] ([privacy.export_preparing] while the file is fetched). Correction and Erasure: [privacy.request.sent], and the list gains the request with [privacy.request.row], the [data_request_status.*] word with an icon, [privacy.request.waiting] while Open, and [privacy.request.reply] with the officer's text once resolved. Empty [privacy.request.none].
- States: each section loads and fails on its own (skeleton; [err.tile_failed] with retry); the page never blanks.

Phone (390 px): sections stack; the access log stays a two-column table; buttons full width.

### W3-4. `/verify`, `/verify/[code]` and `/verify/d/[jws]` (public verifier)

Purpose: anyone holding a student's QR or code checks it, sees only what the student shared, and learns nothing else (D27). No sign-in, no nav, no search, never a list.

```
390 px, entry                            390 px, result
+------------------------------------+   +------------------------------------+
| [mark] Countersign  Verify a proof |   | ✓ Valid                            |
| Verify an enrolment or degree      |   | Valid proof                        |
| proof                              |   | Enrolment proof                    |
| Scan the QR on the document, or    |   | Issued by Countersign for ABC      |
| type the code printed under it.    |   | College of Engineering on          |
| [       Scan with camera       ]   |   | 28 Oct 2026.                       |
| Code                               |   | Signature checked against          |
| [K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF ]   |   | Countersign's published keys.      |
| 24 letters and digits. Dashes and  |   | Revocation checked just now.       |
| spaces are optional.               |   | The student shared this proof for  |
| [            Check             ]   |   | this check, from their own wallet. |
| > Have the proof text instead of a |   | Shared by the student              |
|   code?                            |   | Institution                        |
| What you will see: ...             |   |   ABC College of Engineering       |
| > What is Countersign?             |   | Programme                          |
+------------------------------------+   |   B.Tech Computer Science and      |
                                         |   Engineering                      |
                                         | Year of study   1                  |
                                         | Nothing else is shown. The student |
                                         | chose what to share.               |
                                         | [     Check another proof      ]   |
                                         +------------------------------------+
```

Data:
- `/verify`: the camera scan uses the browser's BarcodeDetector when present (getUserMedia for the preview); a scanned Countersign link opens its own path (`/verify/{code}` or `/verify/d/{jws}`). Without BarcodeDetector the Scan button is hidden and [verify.scan_unsupported] shows. Check upper-cases the code, drops spaces and dashes, regroups it in fours and opens `/verify/{code}`; a wrong length shows [verify.code_format] and sends nothing. [verify.paste_link] discloses a textarea [verify.paste_label] with [verify.paste_hint] and [verify.paste_check], which sends `POST /verify {presentation}` and shows the result on the same page.
- `/verify/[code]`: `GET /verify/{code}`, public, 60 per minute per IP (D32), returning `{result, kind, issuer, issued_at, disclosed: [{key, label, value}], holder_bound, status_checked_at}`. Each check is audited with a hashed IP and adds a row to the student's sharing history.
- `/verify/d/[jws]`: `GET /verify/d/{jws}` for the printed degree QR (D28): the signature against the published keys and the proof's revocation status; fields name, programme, institution, university, year of award, and the APAAR's last four (or a masked provisional id).

Result states (deck §10). Each has a badge with an icon and its [verify.state.*] word, a heading and a sub line; never colour alone.
- VALID: [verify.valid], [verify.kind.*], [verify.valid_sub], [verify.signature], [verify.revocation] (or [verify.revocation_at]), [verify.holder_bound] when `holder_bound`, [verify.shared_heading] with `disclosed` as a definition list in the order sent (label and value as sent), [verify.not_shared]. A pasted proof adds [verify.pasted_note].
- REVOKED: [verify.revoked] and [verify.revoked_sub]; no fields.
- EXPIRED: [verify.expired] and [verify.expired_sub]; no fields.
- INVALID: [verify.invalid] and [verify.invalid_sub]; no fields.
- Degree QR, valid: [verify.degree_valid], [verify.degree_sub], [verify.signature], [verify.revocation], [verify.degree_heading] with its fields, [verify.degree_printed], [verify.degree_wallet]. Degree QR, revoked: [verify.revoked] with [verify.degree_revoked_sub]. Degree QR, bad signature: as INVALID.
- Unknown code (404 `PRESENTATION_NOT_FOUND`): [err.PRESENTATION_NOT_FOUND] with the code box again, prefilled and focused.
- Rate limited (429): [verify.rate_limited] with a countdown on Check.
- Loading: Check reads [verify.checking] and the result area shows a skeleton; a network or server error shows [err.NETWORK] or [err.INTERNAL] with [err.retry].
- Camera not allowed: [verify.camera_denied]; focus goes to the code box.

Every result page ends with [verify.check_another] (to `/verify`) and [verify.about_link]; page title [verify.result_title]. Never a full APAAR, never a field the student did not disclose, never a search box or a list.

Phone (390 px): the entry page is the sketch; the camera preview is a square the width of the column with [verify.scan_hint] under it and [verify.scan_stop]; in the result, a label sits above its value when the value would not fit beside it.

### W3-5. `/university/degrees` and `/university/degrees/[enrolmentId]/print`

Graduates

```
Affiliated institutions / Degree print
Degree print
Graduates of your affiliated institutions. Issue a degree proof, then print the insert with the
masked APAAR and a QR anyone can scan.
[Search by name or the last four digits of APAAR]                                     318 graduates
Graduate          APAAR / Provisional  Institution                  Programme  Year of award  Degree proof
<graduate name>   XXXX XXXX 4417       ABC College of Engineering   CSE        2026           ✓ Issued 28 Oct 2026  [Print degree insert] [Download PDF]
<graduate name>   PRV-XXXXXXXX         ABC College of Engineering   ME         2026           Not issued            [Issue degree proof]
Viewing student records is logged.
```

Data: `GET /university/graduates?q&page` (the university's own affiliates; the AICTE officer sees all), `POST /university/degrees/{enrolment_id}/issue`, `GET /university/degrees/{enrolment_id}` (print data with `qr_svg`) and `GET /university/degrees/{enrolment_id}/insert.pdf` (D28).
- Columns per deck §11; Degree proof is the [degree.status.*] word with an icon. Search sets `q`, debounced 250 ms. Count [degree.count]; the pager as on other tables. Footer [privacy.read_logged].
- Row actions: [degree.issue] opens the issue sheet: [degree.issue_heading], [degree.issue_body], [degree.issue_note], [degree.issue_revocation_note], and [degree.provisional_note] for a graduate without APAAR, then [degree.issue_confirm] and [degree.issue_cancel] ([degree.issuing] while sending); success shows [degree.issued_toast] and the row gains [degree.print_insert] and [degree.pdf]. [degree.pdf] is an `<a href>` to `/api/university/degrees/{id}/insert.pdf` with [degree.pdf_note] as its description. A revoked proof shows [degree.status.revoked] and offers [degree.issue] again.
- States: loading skeleton rows; empty [empty.graduates]; no search match [empty.graduates_search]; error card with retry; 409 `CREDENTIAL_NOT_ELIGIBLE` [err.CREDENTIAL_NOT_ELIGIBLE] in the sheet.

Print view

```
screen only:  [ Print ]   Back to graduates   Print on A4, portrait. Navigation and colours are left out.
----------------------------------------------------------------------------------------------- A4
Maharashtra State Technical University
This insert accompanies the degree awarded to
Name            <graduate name>
Programme       B.Tech Computer Science and Engineering
Institution     ABC College of Engineering
Year of award   2026
APAAR           XXXX XXXX 4417
                                                    [ QR, 30 mm ]
                                                    Proof id <short id>
                                                    Scan to verify at localhost:3000/verify
Proof issued 28 Oct 2026. Signed by Countersign for Maharashtra State Technical University.
A changed insert does not verify.
```

- Data: `GET /university/degrees/{enrolmentId}`. Labels `degree.print.*` (deck §11). The APAAR line prints `apaar_masked` exactly as sent; a graduate without APAAR prints [degree.print.provisional] with the provisional id.
- The QR is the inline `qr_svg` of `{WEB_ORIGIN}/verify/d/{jws}`, at least 30 mm square on paper, with [degree.print.proof_id] and [degree.scan_line] as text under it. The link itself (about 350 characters) is never printed.
- `@media print`: no nav, top bar, breadcrumbs, buttons or hint; no colour backgrounds or tinted panels; black text on white with hairline rules; the QR at full contrast; everything on one A4 page. Page title [degree.print_title].
- [degree.print] calls `window.print()`; [degree.print_back] returns to the list. A revoked proof does not print: [err.CREDENTIAL_REVOKED] with Back to graduates. No proof yet: the page offers [degree.issue] first.
- States: loading skeleton of the insert; error card; 404 [err.NOT_FOUND_enrolment].

### W3-6. `/admin/audit` (AICTE officer)

```
Overview / Audit
Audit
Every change, and every view of student records, in order. Each entry carries the hash of the one before ...
[ Verify chain ]   ✓ Chain intact, 1,842 entries · Checked 28 Oct 2026, 16:02 IST
Entity [All ▾]  Action [All ▾]  Actor [All ▾]  Entity id [          ]  From entry [      ]
Views of student records are logged as Viewed entries.
Entry  Time                    Actor               Action   Entity      Entity id  Hash
1842   28 Oct 2026, 16:01 IST  admin@aicte.demo    Viewed   enrolment   3f9a1c2e   9f8e7d6c
1841   28 Oct 2026, 15:58 IST  Public, verifier    Viewed   credential  a01b22c3   1a2b3c4d
1,842 entries                                                          1 to 25 of 1,842

after make audit-tamper SEQ=917
(!) Chain broken at entry 917                                       [ Show entry 917 ]
Entry 917 no longer matches its recorded hash, so it was changed after it was written.
Entries before it are intact.
 917   14 Jul 2026, 09:30 IST  admin@aicte.demo    Updated  flag        0b6fe1a4   5d4c3b2a   ✕ Chain breaks here
```

Data: `GET /admin/audit?page&page_size&entity_type&action&actor_id&entity_id&seq_from` and `GET /admin/audit/verify` (`{ok, length, first_broken_seq, checked_at}`), D29.
- Columns per deck §12: Entry (`seq`, monospace, right-aligned), Time, Actor (`actor_email`, or [audit.actor_system], or the [audit.via.*] words), Action ([audit_action.*]), Entity (`entity_type`), Entity id and Hash (first 8 characters in monospace, the full value on focus and hover with [audit.hash_tip]). Dense 32 px rows, newest first.
- Filters in the URL with the `a_` prefix: Entity, Action and Actor are selects; Entity id and From entry are text inputs applied on Enter. [audit.count] and the pager; empty [empty.audit]; no match [empty.audit_filtered] with [empty.clear_filters].
- Verify chain: [audit.verify], [audit.verifying] while it runs, then an `aria-live="polite"` banner: [audit.chain_ok] with [audit.chain_checked], or [audit.chain_broken] with [audit.chain_broken_detail] and [audit.show_entry]. Show entry n clears the other filters and opens the page with From entry set to n + 10 (`seq_from = n + 10`), so the ten newer entries sit above the broken one as context; it marks the row with an icon and [audit.break_marker] (never by colour alone), scrolls it into view and moves focus to it. When that page is already open, Show entry only scrolls to the row and focuses it.
- [audit.read_note] under the filters. No student name and no unmasked id appear; `before` and `after` are not shown on this page.
- States: loading skeleton rows; error card with retry. Other roles are redirected with the toast.
- Demo: `make audit-tamper SEQ=n` edits one entry from the command line only and refuses unless `DEMO_MODE=true`; Verify chain then reads "Chain broken at entry n", and `make demo-reset` restores the chain. The browser has no tamper control.

### W3-7. Respond on `/college/flags/[flagId]`

The registrar sees the flag as in W2-8 and its history (W3-8, read only); while the status is Documents requested a Respond panel sits above the evidence:

```
Documents requested · Reply due by 4 Nov 2026
Regional officer, Western asked on 28 Oct 2026:
"Send admission form and ID copy"

Respond to the document request
Your reply to the officer
[                                                                  ]
Required. Say what you are sending and how it answers the request.
Attach documents (PDF, PNG or JPEG, up to 3 files, 5 MB each)
[ Add file ]
admission_form.pdf, 412 KB                 [ Remove admission_form.pdf ]
1 of 3 files
[ Send to the officer ]
```

Data: `POST /flags/{id}/response` as `multipart/form-data` with `note` and up to 3 files (PDF, PNG or JPEG, 5 MB each), by a registrar of the flag's own college, only while the flag is DOCS_REQUESTED (D25). The response keeps the status and sets `response_received`.
- Request line: [college.request_line] with the officer's role (never their name) and date, the request note in quotes, and [college.due_line] when a due date is set.
- Form: [college.respond_note], required (`aria-required="true"`), with [college.respond_note_hint]; [college.respond_add_file] is a labelled file input (`accept=".pdf,.png,.jpg,.jpeg"`, multiple, keyboard reachable); each chosen file is listed as [case.attachment] with a [college.respond_remove_file] button; [college.respond_file_count]. Checked in the browser before sending: [college.respond_too_many], [college.respond_file_type], [college.respond_file_size]. An empty note shows [college.respond_note_required] under the field and moves focus there.
- Sending: [college.respond_sending], inputs disabled, upload progress for large files.
- After success: [college.respond_sent]; the history gains the Responded row; the panel shows [college.respond_waiting] and [college.respond_more] (another response is allowed while the flag stays Documents requested).
- Errors inline above the button, the chosen files kept: 413 [err.ATTACHMENT_TOO_LARGE]; 415 [err.ATTACHMENT_TYPE]; 409 [err.FLAG_TRANSITION_INVALID] (the officer decided meanwhile: the panel closes and the page refetches).
- Any other status: no panel; [flag.readonly_college].
- The registrar never sees the student's comment on a notice (D24) or another institution's name.

### W3-8. Case actions, history and the queue (officers)

Flag detail (W2-8) gains the action bar, the sheets and the history; the case queue (W2-7) gains assignment.

```
Overview / Cases / Name or date of birth mismatch, ABC College of Engineering
Name or date of birth mismatch                  Medium · Documents requested · opened 28 Oct 2026
ABC College of Engineering · CSE · 2026-27
[ Response received ]   Reply due by 4 Nov 2026   Assignee: Unassigned

[ Clear flag ] [ Request documents ] [ Escalate ] [ Confirm ]          [ Add note ] [ Assign ]

Evidence ...

History
When                    Who                                    What
28 Oct 2026, 15:32 IST  System                                 Flag opened
28 Oct 2026, 16:05 IST  <officer name>, Regional officer,      Requested documents
                        Western                                Open to Documents requested, Reply by 4 Nov 2026
                                                               "Send admission form and ID copy"
28 Oct 2026, 16:20 IST  <registrar name>, Registrar            Responded
                                                               "Student's full name per 10th certificate is Ravi Kumar Sharma"
                                                               admission_form.pdf, 412 KB
Each download is logged.
```

Data: `GET /flags/{id}` with `history[]` from `case_actions` (actor name and role, or no actor for System rows; `action`, `note`, `from_status`, `to_status`, `due_date`, assignee, attachments), plus `docs_due_on`, `response_received` and `assignee`; `POST /flags/{id}/actions {action, note, due_date?, assignee_id?}`; `GET /flags/{id}/attachments/{attachment_id}` (scope checked, audited); `GET /users?role=RO_OFFICER|AICTE_ADMIN` for the assignee picker (D25).

Header: [flag.meta]; the [case.response_badge] chip (tooltip [case.response_badge_tip]) when `response_received`; [case.due_line], or [case.due_passed] once the date is past, while the flag is Documents requested (plain text, never red); the assignee's name or [case.assignee_none].

Action bar (deck §6 lists the buttons per role and status): exactly the flag's `allowed_actions`, in that order. The AICTE officer on Open or Documents requested sees Clear flag, Request documents, Escalate, Confirm, Add note and Assign; on Escalated the same without Escalate; on Cleared or Confirmed, Add note and Reopen with [case.closed_admin]. The regional officer, on its region's flags, sees the same on Open and Documents requested; on Escalated only Add note, with [case.escalated_ro]; on Cleared or Confirmed only Add note, with [case.closed_line]. A closed flag cannot be assigned. A refused action is not shown at all, rather than shown disabled without a reason.

Sheets: each a modal dialog labelled by its title, focus on the note field, Tab kept inside, Esc and [case.cancel] closing it and returning focus to the button that opened it.
- Clear: [case.clear_confirm]; note [case.note_label], required.
- Request documents: [case.request_docs_prompt] as the note label; [case.due_date] with [case.due_date_hint] (a native date input, today or later); [case.request_docs_email]; [case.request_docs_send]. Sets `docs_due_on` and emails every registrar of the college ([email.docs_request.*]).
- Escalate: [case.escalate_prompt] and [case.escalate_note].
- Confirm: [case.confirm_confirm], then [case.confirm_revokes] when the flag names an enrolment; note required; the button repeats [case.confirm] and is not red.
- Reopen (AICTE officer, Cleared or Confirmed): [case.reopen_prompt]; note required.
- Add note: the note only; the status does not change.
- Assign: a combobox [case.assign_label] (`role="combobox"`, typing filters, arrow keys move, Enter chooses) listing [case.assign_option] rows from `GET /users`, with [case.assign_me] first and [case.assign_none] last, [case.assign_empty] when nothing matches; no note needed.
- An empty note shows [case.note_required] under the field, keeps focus there and sends nothing. 409 `FLAG_TRANSITION_INVALID` shows [err.FLAG_TRANSITION_INVALID] in the sheet and the flag refetches; 403 and 404 render as on every page.
- After success: the action's toast ([case.cleared_toast], [case.docs_toast], [case.escalated_toast], [case.confirmed_toast], [case.reopened_toast], [case.note_toast], [case.assigned_toast], [case.unassigned_toast]) in an `aria-live` region; the status badge flashes its soft tint once (DESIGN §7); the history gains the row.

History (deck §6): oldest first, starting with [case.history.opened]; columns When, Who, What; the status change and the due date in small text; the note in quotes on its own line; attachments as links whose accessible name is [case.attachment_download], with [case.attachments_logged] under the list. System rows read [case.history.system] and print [case.history.SYSTEM_NOTE] or the api's note ([case.system_note.reply_changed] after a student changes a No to a Yes). On a Student denied flag the evidence fact Comment from the student is shown to officers only.

Queue (`/aicte/cases`, `/ro/cases`): the Assignee column ([col.assignee]; [case.assignee_none] when null) and two filters in the URL with the `f_` prefix: [flags.filter.assignee] (All, [flags.filter.assignee_me], [flags.filter.assignee_none], or an officer) sending `assignee`, and [flags.filter.response] (All, [flags.filter.response_received]) sending `response_received=true`. A row with a response carries the [case.response_badge] chip beside its status word.

### W3-9. `/admin/data-requests` (AICTE officer)

```
Overview / Data requests
Data requests
Students' requests to correct or erase their data. Each one gets a written reply the student reads on their Privacy page.
Status [Open ▾]  Request [All ▾]                                                       1 open request
Received     Request     Student              Details                                            Status  Resolved
28 Oct 2026  Correction  Ravi Kumar Sharma    Please unlink my APAAR from my enrolment at ABC    Open            [ Resolve ]
                         XXXX XXXX 4417       College of Engineering.
Viewing student records is logged.
```

Data: `GET /data-requests` (AICTE officer only) and `POST /data-requests/{id}/resolve {status: "DONE" | "REJECTED", response}` (D30). The queue holds Correction and Erasure requests; an Access request is fulfilled at once and never waits here.
- Columns and words per deck §12 ([admin.requests.*], [data_request_kind.*], [data_request_status.*] with an icon). Default Status Open, oldest first; filters in the URL with the `r_` prefix. Count [admin.requests.count]. Details wrap; the student cell shows the name with the masked APAAR or provisional id under it.
- Resolve sheet: [admin.requests.resolve_heading]; [admin.requests.request_line] and the details in quotes; the kind's hint ([admin.requests.correction_hint], plus [admin.requests.unlink_hint] when the text asks to unlink an APAAR; for an erasure, [admin.requests.erasure_retention] above a reply prefilled with [admin.requests.erasure_reply]); the radio group [admin.requests.outcome] (Done, Decline); the reply [admin.requests.response_label], required, with [admin.requests.response_hint] and [admin.requests.response_required]; [admin.requests.submit] ([admin.requests.sending] while sending). Keyboard and focus as the case sheets.
- After success: [admin.requests.resolved_toast]; the row shows its new status and resolved date; the student reads the reply on their Privacy page.
- States: loading skeleton rows; empty [admin.requests.empty]; no match [admin.requests.empty_filtered]; error card with retry. Other roles are redirected with the toast.

### W3-10. Student notice block and Resend notice on enrolment detail

Enrolment detail (W2-5) gains a block under Countersign checks for the AICTE officer, the regional officer and the registrar. The university sees the Student check row but not this block.

```
Student notice                                                     [ Resend notice ]
Email: Sent, 28 Oct 2026
DigiLocker: Not delivered, 28 Oct 2026 (no DigiLocker account)
Expired on 27 Nov 2026 without a reply.
```

Data: the enrolment's notices on `GET /enrolments/{id}` (channel, `delivery_status`, `last_error`, sent and expiry dates, `response`, `responded_at`, the change date, and the comment for officers only) and `POST /enrolments/{id}/notices/resend` (D23: when no notice is live, by the registrar of the college or an officer, at most 3 per enrolment per academic year).
- One [enrolment.notice.channel_line] per channel of the newest notice, with [enrolment.notice.failed_reason] for a failed delivery; then [enrolment.notice.expires], [enrolment.notice.expired] or [enrolment.notice.reply] with [enrolment.notice.changed]. Officers also see [enrolment.notice.comment] and the comment. No notice: [enrolment.notice.none].
- Resend notice: [resend.button] with the tooltip [resend.tip]; disabled with [resend.live_tip] while a notice is live; replaced by [enrolment.notice.consent_off] when the student withdrew notice consent. Pressing it opens a dialog with [resend.confirm_heading], [resend.confirm], [resend.send] and [resend.cancel]; success shows [resend.sent] in an `aria-live` region and the block refetches. 429 `RESEND_LIMIT`: [err.RESEND_LIMIT], the button stays disabled. 409 `NOTICE_LIVE`: [err.NOTICE_LIVE].
- States: the block loads with the page; if the notices part fails, [err.tile_failed] with retry in its place.

## Week 4

Week 4 pages follow the frozen scope (the SIH deck) and DECISIONS D34 to D49 with rules R1 to R6. API_CONTRACT Addendum 4 is being written alongside: endpoints and fields marked (pending) are named here so the pages can be built, and the contract wins wherever it differs. Copy ids refer to `05-copy-deck.md` §21 to §29 and the sections it rewrote (§6, §11, §15, §17).

Every Week 4 page, besides the shared rules of `03-pages-week1.md` §0:
- A record's status and a row's evidence state are always a word with its icon. Colour is a second cue, never the only one, and the page reads the same in greyscale.
- One contradiction visibly outranks any number of confirmations: the record's status is the largest mark on the card, above the rows, and a Contradicted row is never visually smaller than a Confirmed one.
- No score anywhere: no strip, no "n of 5", no percentage for one record. Percentages appear only as shares of a population (dashboard tiles, completeness, reports).
- APAAR is printed exactly as sent (`XXXX XXXX 4417`), never composed in the browser; a provisional ID prints with its label.
- Signals appear only on officer pages (AICTE officer, regional officer). No `/college/*`, `/university/*`, `/student/*` or public page requests a signal or names one.
- Every decision sheet names every consequence before the officer submits.
- Loading: content-shaped skeletons, [shell.loading_slow] after 3 s. Error: the page's error card with [err.retry] and the `Ref:` line; one failed panel never blanks the page. Empty: the deck's empty line and the one action that fills it.
- Phone width 390 px: one column, 16 px side gutters, body text 16 px, targets at least 44 px, primary buttons full width and 48 px tall, no horizontal page scroll (a wide table scrolls inside its own container with its first column sticky), nothing hover-only.

Proposed for DESIGN.md §3.2 and §5 (its owner decides; the words above hold whatever the hues):

| Mark | Hue | Icon |
|---|---|---|
| Confirmed | ok | `Check` |
| Contradicted | alert | `X` |
| Pending | caution | `Clock` |
| Not yet due | neutral | `CalendarClock` |
| Not applicable | neutral, dotted | `Minus` |
| Source unavailable | caution | `CloudOff` |
| Countersigned | ok | `BadgeCheck` |
| Awaiting evidence | caution | `Hourglass` |
| Under review | blue | `FileSearch` |
| Disputed | alert | `OctagonAlert` |
| Independent of the college | none (ink) | `ShieldCheck` |
| From the college itself | none (ink-muted) | `Building2` |
| Claim upheld by an officer | seal | `Gavel` |
| Case statuses Claim upheld, Claim corrected, Claim withdrawn | ok, blue, neutral | `CircleCheck`, `PencilLine`, `CircleSlash` |
| On time, Late, Overdue | neutral, caution, caution | `CalendarCheck`, `CalendarClock`, `CalendarX` |

### Changes to earlier pages

- The countersign strip (W2-3) is retired everywhere. Lists show the record's status in a Status column (W4-2); the student's home shows the record card (W4-1, student variant).
- Flags become cases in every visible word. Routes: `/college/flags` and `/college/flags/[flagId]` become `/college/cases` and `/college/cases/[caseId]`; the officers' `/aicte/cases/[flagId]` and `/ro/cases/[flagId]` keep their paths with the parameter renamed. Old paths redirect (308) so emails already sent still open.
- Clear flag and Confirm give way to the three decisions (W4-5). The flag status words Cleared and Confirmed give way to Claim upheld, Claim corrected and Claim withdrawn.
- The notice page (W3-1) shows its claim to anyone with the link, as before, but Yes and No appear only after DigiLocker sign-in (W4-8). Their words become [notice.yes] "Yes, I joined" and [notice.no] "No, I never joined".
- My proofs becomes My attestations (W3-2), Verify a proof becomes Verify an attestation (W3-4), and Degree print becomes Certificate integration (W4-12). The degree proof is now a completion attestation.
- `/login`: the Student card opens DigiLocker sign-in ([login.card.student], [login.digilocker]); no student password exists.
- Nav: officers gain Signals and live Reports; the AICTE officer gains Evaluation (if built); the registrar's Flags becomes Cases and gains Completeness; Why this score goes. Only Private matching may stay disabled.
- Integrity Index: every mention, column and page is removed (`/aicte/institutions/[id]/score`, `/college/score` redirect to the institution page and `/college`).

### W4-1. The record card: enrolment detail

`/aicte/enrolments/[id]`, `/ro/enrolments/[id]`, `/college/enrolments/[id]`, `/university/enrolments/[id]`, and the card on `/student`.

Purpose: one place that answers "is this enrolment backed by evidence, and if not, what happens next", drawn exactly as the deck's sample card, with the record's history and attestations under it.

```
Overview / ABC College of Engineering / Enrolments / <student name>
<student name>                                              (!) Disputed (priority)
B.Tech CSE 2026, ABC College of Engineering · APAAR XXXX XXXX 4417          since 22 Aug
+------------------------------------------------------------------------------------------+
| Check           Evidence state                     Source and date                         |
| Identity        (✓) Confirmed                      APAAR verification · 12 Aug             |
|                                                    [shield] Independent of the college     |
| Seat            (✓) Confirmed: fits approved       AICTE approval v2, 2026-27              |
|                     intake                         (Seat Ledger, derived)                  |
| Joining record  (✕) Contradicted: not found        State admission authority · 20 Aug      |
|                                                    [shield] Independent of the college     |
| Credits         (–) Not yet due                    First semester not complete             |
| Student         (✕) Contradicted: "I never joined" Student sign-in via DigiLocker · 22 Aug |
|                                                    [shield] Independent of the college     |
| Status: Disputed (priority). Next step: College asked for admission documents by 29 Aug.   |
| Why: The student said they never joined, after signing in with DigiLocker on 22 Aug.       |
| Awaiting evidence · Countersigned · Under review · Disputed      What the statuses mean (i) |
+------------------------------------------------------------------------------------------+
[Show details]                                                     [Recheck evidence]

Cases about this record
High  Student dispute   Documents requested   The student said they never joined, ...   22 Aug
Medium Not in joining record  Open            Not found in the Maharashtra admission ...   20 Aug

Student                     Enrolment                       Seat
Date of birth  21 Mar 2007  Intake  AICTE approval v2, 2026-27   CSE-R-014 · Regular · approval v2,
Gender         Male         Year of study 1                       2026-27 · assigned 14 Aug
Mobile         XXXXXX4521   Admission route Counselling ...
                            Reported eligibility  none

Student notice                                                   [Resend notice]
Email: Sent, 15 Aug · DigiLocker: Sent, 15 Aug
Answer: Never joined, 22 Aug (DigiLocker sign-in)

Attestations
Enrolment attestation K7PQ3M2X, issued 16 Aug
Revoked on 22 Aug: You told us you never joined, so this attestation was revoked while an officer reviews it.
Revoked when the student disputed the record. Issued again only if an officer upholds the claim and the record is Countersigned.

History
When              What changed                                                         By
14 Aug, 11:40 IST Programme changed from B.Tech ME to B.Tech CSE by upload on 14 Aug.  Registrar
                  Upload 1-ABC-0001_2026-27_update1.csv · Version 2
28 Jul, 09:30 IST Record created by upload 1-ABC-0001_2026-27.csv on 28 Jul.           Registrar
Viewing student records is logged.
```

Data: `GET /enrolments/{id}` with the Addendum 4 fields (pending): `record_status`, `status_reason`, `next_step`, `record_status_at`; `rows[]` in the order IDENTITY, SEAT, ADMISSION, STUDYING, STUDENT, each with `check`, `status`, `finding`, `source_line`, `supplied_by`, `observed_at`, `independent`, `resolved {outcome, by, at}`, `detail.summary`, `attempts`; `versions[]` (D42: `version`, `changes {field: [before, after]}`, `source`, `batch {filename}`, `case {id, type}`, `actor {name, role}`, `at`); `attestations[]`; the Week 2 and 3 fields (student, enrolment, seat with its approval `version`, flags as cases, notices).

Elements, top to bottom:
1. Heading: the student's name (officers, registrar, university), then the status badge at its largest size: icon and [record_status.DISPUTED_priority] for a Disputed record, else `record_status.*`, with [record.status_since] under it. The badge's tooltip is `record_status.meaning.*`.
2. The card, labelled [record.aria_card]: [record.header], then a real `<table>` with [record.col.check], [record.col.state], [record.col.source] as `<th scope="col">` and the row label as `<th scope="row">` with its [check.label_tip.*]. The state cell: the icon and `evidence.state.*` word, then [evidence.with_finding] when `finding` is set. The source cell: `source_line` verbatim, then on Confirmed and Contradicted rows the marker [evidence.independent] or [evidence.from_college] with its icon and tooltip (none on the Seat row). An upheld contradiction adds [evidence.resolved.UPHELD] with its icon and [evidence.resolved_tip], on its own line under the state; the state stays Contradicted. Each row is announced as one [evidence.sr_row].
3. The footer, inside the card: [record.footer_status] (Disputed prints "Disputed (priority)") and [record.footer_next] on one line as the deck draws it, then [record.reason] for officers, the registrar and the university, then the legend [record_status.legend] with the current status's word in bold and its icon, and a disclosure [record_status.legend_label] opening the four `record_status.meaning.*` lines and [record_status.rule].
4. [record.details_show] toggles one `detail.summary` sentence under each row (and [check.attempts] in small text). Recheck: [recheck.enrolment] with [recheck.enrolment_tip], for officers and the registrar, only when a row other than Student is Pending or Source unavailable; results per §17 in an `aria-live` region; the card refetches.
5. Cases about this record ([enrolment.section.flags]): severity chip, `flag.<TYPE>.name`, `flag_status.*` word with icon, `summary` verbatim, opened date; rows link to case detail for officers and the registrar, plain text for the university; empty [empty.flags_enrolment].
6. Student, Enrolment and Seat blocks as W2-5, with [enrolment.intake_value] and [enrolment.seat_value] naming the approval version, and [enrolment.field.eligibility] listing reported markers (TFW income certificate, NRI sponsored, CIWG) or "none".
7. Student notice block (W3-10) with the answer words Joined or Never joined and "(DigiLocker sign-in)".
8. Attestations ([enrolment.section.attestations], officers only): one [enrolment.attestations.line] per attestation; a revoked one adds [enrolment.attestations.revoked_line] with the `wallet.revoked_reason.*` sentence, and [enrolment.attestations.held_by_dispute] when the reason is STUDENT_DISPUTE; Revoke for the AICTE officer on an active one (the dialog of copy-cases, renamed). None: [enrolment.attestations.none].
9. History ([history.heading]): a table When, What changed, By per §22; newest first; empty [history.empty].
10. Footer [privacy.read_logged].

Withdrawn records: [record.withdrawn_banner] or [record.withdrawn_upload_banner] above the card, with an icon; the card keeps its last rows and reads the last status it held; no Recheck.

Role differences: the registrar sees the same card and footer, the history with roles only, no attestations block, and the cases list of its own college. The university sees the card, the footer and History with roles only; no Recheck, no notice block, no attestations block, no case links. No role sees a signal here.

Student variant (`/student`): the same card for each of the student's active records, without Recheck, cases, notice block or attestations block; under the footer the line `record_status.student.*` in place of [record.reason], then the §8 notice line or a `student.decision.*` line. History shows the sentences only (no By column). The student sees the row states and source lines of their own record and nothing about cases, officers, notes or signals.

States:
- Loading: the card's frame with five skeleton rows, the badge as a grey pill; the blocks below load on their own.
- Not found: [err.NOT_FOUND_enrolment] with [err.back_overview].
- A row never checked: Source and date reads [check.never]; an empty `rows` prints [empty.checks] inside the card in place of the rows.
- Error: the card shows [err.tile_failed] with retry; the page's other blocks still render.
- After a decision elsewhere: the card refetches when the page regains focus, and the badge flashes its soft tint once (DESIGN §7).

Phone (390 px): the card becomes a stack of five blocks, one per row, in the same order: the row label as a small heading, the state word and finding on the next line, the source line and the marker under it. The status badge sits above the stack, full width; the footer and legend follow the stack, the legend wrapping onto as many lines as it needs. The history table becomes a list of entries (When, then What changed). Nothing scrolls sideways.

### W4-2. Enrolment lists with status

The Enrolments tab of institution detail, `/college/enrolments`, and the related records on case detail.

```
Status [All statuses ▾]  Row [Any ▾]  Evidence state [Any ▾]  Cases [Any ▾]  Seat [Any ▾]   Sort [Needs attention first ▾]
Student            APAAR / Provisional   Programme  Year  Route        Seat        Status                 Cases
<student name>     XXXX XXXX 4417        CSE        1     Counselling  CSE-R-014   (!) Disputed           Student dispute, High
<student name>     PRV-XXXXXXXX          CSE        1     Management   CSE-R-102   (⌛) Awaiting evidence
<student name>     XXXX XXXX 9021        CSE        1     Counselling  CSE-R-001   (✓) Countersigned
1 to 25 of 605                                                    Viewing student records is logged.
```

Data: `GET /enrolments` (and `GET /institutions/{id}/enrolments`) with `record_status` on each row and new query params `record_status`, `row` (`check_type` renamed in words only), `row_state`, and `sort=attention` (pending).
- The Countersign column becomes Status ([col.record_status]): the icon and `record_status.*` word, with `status_reason` as its tooltip when the list carries it (pending; otherwise `record_status.meaning.*`).
- Filters in the URL with the `e_` prefix: Status ([enrolments.filter.status], the four words in legend order plus [enrolments.filter.status_all]), Row ([enrolments.filter.check], the five labels in deck order), Evidence state ([enrolments.filter.result], the six words), Cases, Seat. Row and Evidence state together mean "this row in this state".
- Default sort [record_status.sort.attention], explained by [record_status.sort_tip] on the Status header (`aria-sort`).
- A status count line above the table, in legend order, each a link that sets the Status filter: "312 Awaiting evidence · 254 Countersigned · 37 Under review · 2 Disputed".
- Empty with filters: [empty.status_filtered] or [empty.enrolments_filtered] with [empty.clear_filters].

States: skeleton rows; error card; empty [empty.enrolments]. Phone (390 px): the table scrolls inside its container with Student sticky; the count line wraps; filters collapse behind a "Filters" button opening a sheet.

### W4-3. Dashboards by status: national, regional and college

`/aicte`, `/ro`, `/college`.

```
Overview                                                         Academic year [2026-27 ▾]
Records by status
(⌛) Awaiting evidence   (✓) Countersigned   (◎) Under review   (!) Disputed
    9,412 · 49.6%           8,120 · 42.8%        1,388 · 7.3%      40 · 0.2%
Countersigned = identity verified (or the alternative route) + seat fits the approval + ...
[bar chart, one bar per status, with the same numbers in the table beside it]

Completeness and deadlines                     Open cases by type        Signals (officers only)
Colleges   Completeness   Missing   Deadline   Student dispute   40      3 new · See all signals
ABC ...    92%            14        Late       Not in joining ... 212     Shared contact ring, 3 colleges
XYZ ...    100%           0         On time    Excess admission    9     Unusual pattern, XYZ Institute
...                                            ...                        Signals never change a
                                                                          record's status.
Institutions ranked
Name  Permanent id  State  Approved seats  Admitted  Countersigned  Under review  Disputed  Completeness  Deadline  Open cases
```

Data: `GET /dashboard/summary` adds (pending) `by_status {AWAITING_EVIDENCE, COUNTERSIGNED, UNDER_REVIEW, DISPUTED}` with counts and shares, `countersigned_pct`, `completeness {pct, joined, missing}`, `deadlines {on_time, late, overdue, not_due}`, `cases_by_type` with ages, `signals {new, top[]}` (officers only); `GET /institutions` rows add `by_status`, `completeness_pct`, `missing`, `deadline_state`, `flags_open`.

Elements:
- Records by status ([kpi.status_heading], tooltip [kpi.status_tip]): four tiles in legend order, each the icon and word, the count and share ([kpi.status_value]), linking to the enrolment list filtered by that status (officers: the case queue for Under review and Disputed is one click further). Under them [record_status.rule]. A bar chart of the same four counts sits beside a table of the same numbers (D46: bar charts only, the table always present); bars use the status hues with the word under each bar.
- Completeness and deadlines: a table of colleges (Name, [completeness.col] with [completeness.tip], [completeness.col_missing], [deadline.col] word with icon and `deadline.tip.*`), sorted by missing, descending; the national tile [kpi.completeness] with [kpi.completeness_value].
- Open cases by type ([section.flags_by_type]) with counts and the median age per type, each linking to the case queue.
- Signals panel ([signal.panel_heading], officers only): [signal.count], the three newest signal summaries with their type word, [signal.panel_more] to W4-6, and [signal.never_status] under it.
- Institutions ranked: the default sort becomes open cases, then Disputed, then Under review ([table.sort_tip]); columns as sketched; Integrity Index is gone.
- By state and By region tables gain the four status columns and completeness; still no map, no fill percentage of seats.

`/ro`: the same, scoped to the region, heading [ro.heading].

`/college` (registrar): the Seat Ledger tiles stay first ([nav.ledger]); then the college's Records by status (four tiles, linking to `/college/enrolments?e_status=`), its completeness line ([completeness.line]) linking to W4-4, its deadline word with [deadline.tip.*], the five newest open cases about the college, and the last upload line. No signals panel, no other college, no national number.

States: each panel loads and fails on its own ([err.tile_failed] with retry); nulls read [kpi.not_computed]; completeness before the authority publishes reads [completeness.line_none]. Phone (390 px): tiles in a 2 by 2 grid, each word above its number; tables scroll in their containers; the chart sits under its table.

### W4-4. Completeness and missing students

`/aicte/institutions/[id]/completeness` and `/ro/institutions/[id]/completeness` (a tab, [tab.completeness]), and `/college/completeness` ([nav.completeness]).

```
Seat Ledger / Completeness
Completeness                                         Academic year [2026-27 ▾]
92% of joined students uploaded, 14 missing          (⏰) Late · first upload 3 Oct, deadline 30 Sep
Joined (authority) 180 · Uploaded and joined 166 · Missing 14
A Missing from upload case is open for these students.  [See the case]

Missing from the upload (14)                                     [Download the list as CSV]
The state admission authority lists these students as joined at your college in 2026-27,
but they are not in your uploads. Upload their rows to complete your record.
Student            Programme  Joined on   Admission round
XXXX XXXX 2231     CSE        4 Aug       round 1
Roll XXXX7710      ME         6 Aug       Management admission approved by the state
Viewing student records is logged.
```

Data (pending): `GET /institutions/{id}/completeness?academic_year` returning `{joined, matched, missing, completeness_pct, deadline_date, deadline_state, first_upload_at, case_id, students[] {id_masked, programme_code, joined_on, round_words}}`; the CSV at `/api/institutions/{id}/completeness.csv`.
- Heading line [completeness.line] (or [completeness.line_full]); the deadline word with its icon and `deadline.tip.*` as visible text, not only a tooltip.
- [missing.heading], [missing.lead_college] or [missing.lead_officer], the table with `missing.col.*`; [missing.case_line] with a link to the MISSING_FROM_UPLOAD case when `case_id` is set; [missing.download].
- The registrar's page links [upload.upload_again]; uploading the missing rows updates the line and the case gains [case.system_note.missing_updated].

States: skeleton; empty [missing.none]; before the authority publishes, [completeness.line_none] and no table; error card. Phone (390 px): the summary lines stack; the table becomes a list (masked id as heading, programme, joined on, round).

### W4-5. Officer decision sheets

On `/aicte/cases/[caseId]` and `/ro/cases/[caseId]` (W3-8 gains these sheets; Clear and Confirm go).

```
Student dispute                                   High · Documents requested · opened 22 Aug
ABC College of Engineering · CSE · 2026-27
Decide: [ Uphold claim ] [ Correct record ] [ Withdraw claim ]     [ Request documents ] [ Escalate ]  [ Add note ] [ Assign ]

Withdraw the claim?                                                        (modal)
The college's claim that this student joined does not stand.
Reason     [ The student never joined ▾ ]
Note (shown to the college)
[ Joining record not found after the deadline; the college sent no admission documents.  ]
What will change
• The record is withdrawn: its status becomes Withdrawn, with the reason "withdrawn by decision",
  and it leaves the college's active counts.
• Seat CSE-R-014 is released.
• Enrolment attestation K7PQ3M2X is revoked. Anyone who checks it sees Revoked.
• Nothing is deleted. Each record and its history stay, marked withdrawn.
• The case closes as Claim withdrawn.
• The student sees that the college's claim was withdrawn.
ABC College of Engineering sees your decision, its reason and your note.
The student sees the outcome in plain words, never your note or your name.
[ ] I have read what will change.
[ Withdraw claim ]  [ Cancel ]
```

Programme-level Withdraw (Excess admission) adds the picker:

```
Records to withdraw                     Only records this case names are listed.
[ ] Select all 12                                                   3 of 12 selected
[x] <student name>   XXXX XXXX 1182   CSE-unseated   Awaiting evidence
[x] <student name>   PRV-XXXXXXXX     unseated       Under review
...
What will change
• 3 records are withdrawn: ...   • No seat to release.   • No attestation to revoke.  ...
[ Withdraw 3 records ]
```

Correct record:

```
Correct the record
Choose the fields that are wrong and enter the right values. Only the fields you change are stored,
as a new version of the record.
Field [ Programme ▾ ]      Now  B.Tech ME      Correct value [ B.Tech CSE ▾ ]     [Remove Programme]
[ Add another field ]
APAAR and status are not corrected here. ...
Reason [ Documents show a different value ▾ ]   Note [ ... ]
What will change
• These fields change, saved as version 3 of the record with your name and reason:
  Programme: B.Tech ME to B.Tech CSE
• Countersign checks every row of the record again against its sources and the Seat Ledger.
• Seat ME-R-031 is released, and a Regular seat in CSE is assigned if one is free. If none is free,
  the record is unseated and a case opens.
• The case closes as Claim corrected.  • The record's status is worked out again from the new evidence.
[ Correct record ]
```

Uphold claim lists [case.uphold_change.case], `.row`, `.status`, `.not_evidence`, `.seat` (or, on a programme-level case, the approval version select and `.version`), and `.attestation` only when a dispute revoked one.

Data: `POST /flags/{id}/actions` with `action` UPHOLD, CORRECT, WITHDRAW, ESCALATE, REQUEST_DOCS, NOTE, ASSIGN or REOPEN, and `reason_code`, `note`, `correction {enrolment_id, fields {field: value}}`, `withdrawn_enrolment_ids`, `approval_version`, `docs_kind`, `due_date`; the preview with `dry_run: true` (pending) returning the consequences with seat codes, attestation ids and the next version number; `GET /approvals/{id}/versions` for the Uphold select.

Behaviour (deck §6 lists every string and rule):
- The three decisions sit together under [case.decide_heading], in the order Uphold claim, Correct record, Withdraw claim; none is red or styled as dangerous; all share one weight.
- Each sheet is a modal dialog labelled by its heading; focus goes to the reason select; Tab stays inside; Esc and Cancel return focus to the button that opened it.
- "What will change" is a list (`<ul>`), each item a full sentence with real values; it refreshes when the reason, the picked records or the corrected fields change (debounced 300 ms, from the dry run). While it loads, the list shows skeleton lines and the submit button is disabled with "Working out what will change". If the dry run fails, the sheet shows [err.tile_failed] in place of the list and the submit stays disabled: an officer never decides without seeing the consequences.
- Withdraw needs [case.withdraw_ack] ticked; the submit reads [case.withdraw_submit] or [case.withdraw_submit_many] with the count.
- Correct: field select lists the correctable fields with their `field.*` words; the correct-value input matches the field (a select for enums and programmes, a date input for dates); a value equal to Now is refused inline with [err.CORRECTION_EMPTY] on submit if nothing changed.
- Errors in the sheet: [case.reason_required], [case.note_required], [case.withdraw_ack_required] under their fields; 409 [err.FLAG_TRANSITION_INVALID], [err.WITHDRAW_NOT_NAMED], [err.UPHOLD_NEEDS_VERSION]; 422 [err.CORRECTION_INVALID] under the field it names.
- After success: the toast in an `aria-live` region, the history row with [case.history.reason], correction lines or [case.history.withdrawn_line], and the related records refetch with their new status. The registrar's case page then shows [college.decision_line].

States: sending ([case.sending], inputs disabled; a double press sends once). Phone (390 px): each sheet is a full-height bottom sheet; the consequences list scrolls with the form; the submit is pinned to the foot, full width; the record picker is a list of checkable rows 56 px tall with the masked id under the name.

### W4-6. Signals (officers only)

`/aicte/signals`, `/aicte/signals/[id]`, `/ro/signals`, `/ro/signals/[id]` ([nav.signals]); the dashboard panel of W4-3.

```
Overview / Signals
Signals                                                  Academic year [2026-27 ▾]   5 signals, 3 new
Patterns worth a look, found by a published rule or a model. Only AICTE and regional officers see signals.
Signals never change a record's status. Only a case an officer opens can lead to a decision.
Type [All ▾]  Status [New ▾]  Institution [All ▾]
Type                  What stands out                                                 Colleges  Records  Found   Status
Shared contact ring   40 students across 3 colleges share 6 mobile numbers and ...  3         40       28 Oct  New
Unusual pattern       XYZ Institute of Technology stands out from 49 similar ...     1         -        28 Oct  New
```

Signal detail:

```
Overview / Signals / Shared contact ring
Shared contact ring                                              New · found 28 Oct 2026
40 students across 3 colleges share 6 mobile numbers, 2 email addresses and 3 addresses.
+---------------------------+  Fact                     Value
| [node-link drawing]       |  Students                 40
|                           |  Colleges                 ABC College of Engineering (18), ...
+---------------------------+  Shared mobile numbers    6
The drawing shows how members link. The table beside it is the evidence.
Rule: students linked by a shared mobile number, email or address form a group; a group of 3 or
more across 2 or more colleges, or of 5 or more in one college, is a signal.
Members (40)   <student name>  XXXX XXXX 1182  ABC College of Engineering  CSE  Awaiting evidence ...
[ Open case ]  [ Dismiss ]
Signals never change a record's status. Only a case an officer opens can lead to a decision.
Viewing student records is logged.
```

Data (pending): `GET /signals?academic_year&type&status&institution_id&page`, `GET /signals/{id}` (`type`, `summary`, `facts`, `rule`, `score`, `status`, `institution_ids`, `enrolment_ids` with masked members, `case_flag_id`, dismissal note), `POST /signals/{id}/open-case {institution_ids, note}`, `POST /signals/{id}/dismiss {note}`. Officers only; any other role gets 403 and the nav never lists the item.
- List: columns per `signal.col.*`; status words with icons; default Status New, newest first; filters in the URL with the `s_` prefix; [signal.count]; empty [signal.empty], filtered [signal.empty_filtered].
- Detail: the summary verbatim, the facts table, the rule line ([signal.rule.GHOST_RING] or [signal.rule.ANOMALY] with its `{n}`) printed every time, the members table (masked ids; members in other regions collapsed for a regional officer), and the drawing for a ring (decorative support with a text alternative summarising it; the table is the evidence) or the feature lines for an anomaly ([signal.feature_line] each).
- Open case: a dialog [signal.open_case_heading] with [signal.open_case_body], a checkbox list [signal.open_case_colleges] (one case per college chosen), a note, and [signal.open_case_submit] or [signal.open_case_submit_many]. The cases cite the signal ([case.from_signal]); the signal's status becomes Case opened with [signal.case_link].
- Dismiss: a dialog with [signal.dismiss_body], the note [signal.dismiss_note_label] (required), [signal.dismiss_submit]; afterwards [signal.dismissed_line].
- 409 [err.SIGNAL_ALREADY_HANDLED] refetches; 404 [err.NOT_FOUND_signal].

States: skeleton rows; error card. Phone (390 px): the list becomes stacked blocks (type word, summary, colleges and status); the drawing is hidden below 768 px and the facts table carries the evidence; the actions sit full width at the foot.

### W4-7. Reports

`/aicte/reports` and `/ro/reports` ([nav.reports]).

```
Overview / Reports
Reports                                                   Academic year [2026-27 ▾]
Summaries for policy, accreditation and monitoring. Each downloads as CSV or XLSX; the summary also as a one-page PDF.
(i) Synthetic data. Every college, student and number here is generated for the demo.
All India · Academic year 2026-27 · Generated 29 Oct 2026, 10:12 IST

Records by state                Active records by status in each state, with approved seats and admitted.   [CSV] [XLSX]  [Preview]
Records by institution type     ...                                                                         [CSV] [XLSX]  [Preview]
Cases by type and outcome       ...                                                                         [CSV] [XLSX]  [Preview]
Countersign coverage            ...                                                                         [CSV] [XLSX]  [Preview]
Completeness and deadlines      ...                                                                         [CSV] [XLSX]  [Preview]
One-page summary                ...                                                                         [PDF]
```

Data (pending): `GET /reports/{name}.csv`, `.xlsx` and `GET /reports/summary.pdf` (AICTE and RO scoped, D46), and `GET /reports/{name}?preview=25` for the preview.
- One row per report with `report.name.*`, `report.desc.*` and one download link per format; each link is an `<a href>` with the accessible name [report.download_label] and the format word as its text. [report.synthetic] sits at the top of the page with an icon and is never dismissible. A regional officer sees [report.ro_scope] under the lead.
- Preview opens the first 25 rows in a table under the report ([report.preview_rows]) with the same column words as the file; a bar chart appears only beside its table, never alone, and never a map.
- While a file is prepared the link reads [report.preparing]; failure shows [err.REPORT_FAILED] inline under that report.

States: empty [report.empty] per report; error per report. Phone (390 px): each report is a block (name, description, then the format buttons full width in a row of two); the preview table scrolls in its container.

### W4-8. DigiLocker sign-in and the notice page

Web: `/login` (student entry), `/student/notices/[token]` (gate and states), `/auth/digilocker/return` (the page the callback lands on). mockgov: `GET /digilocker/oauth/authorize` and its steps (the Demo DigiLocker).

Notice page, signed out (390 px):

```
+--------------------------------------+
| [mark] Countersign        [ हिन्दी ] |
| ABC College of Engineering says      |
| you joined B.Tech Computer Science   |
| and Engineering                      |
| Academic year 2026-27 · Year 1       |
| They uploaded this on 14 Jul 2026    |
| for APAAR XXXX XXXX 4417.            |
|                                      |
| To answer, sign in with DigiLocker.  |
| Only the person this record is about |
| can answer.                          |
| [ Sign in with DigiLocker to answer ]|
| You go to DigiLocker to sign in,     |
| then come back here.                 |
| Demo: this opens a simulated         |
| DigiLocker with synthetic accounts.  |
| > What is this?                      |
+--------------------------------------+
```

Demo DigiLocker (mockgov), three steps, each with the banner:

```
+--------------------------------------+   +--------------------------------------+   +--------------------------------------+
| Demo DigiLocker, synthetic data      |   | Demo DigiLocker, synthetic data      |   | Demo DigiLocker, synthetic data      |
| This is a simulated DigiLocker for   |   | Enter the OTP                        |   | Share with Countersign?              |
| the Countersign demo. Every account  |   | A real DigiLocker sends an OTP to    |   | Countersign will receive your name,  |
| here is synthetic. Never type real   |   | the mobile number linked to the      |   | your date of birth, your APAAR if    |
| details.                             |   | account. In this demo the OTP is     |   | linked, and your DigiLocker id.      |
| Countersign is asking you to sign in.|   | always 123456.                       |   | [            Allow             ]     |
| Choose a demo account                |   | OTP [______]                         |   | [            Deny              ]     |
| [Search by APAAR or DigiLocker id ]  |   | [            Verify            ]     |   | Choose another account               |
| ( ) Ravi Kumar Sharma · APAAR XXXX   |   | Choose another account               |   | Run by the Countersign demo's mock   |
|     XXXX 4417                        |   |                                      |   | services, not by DigiLocker.         |
| ( ) <name> · No APAAR linked · ...   |   |                                      |   |                                      |
| [          Continue            ]     |   |                                      |   |                                      |
+--------------------------------------+   +--------------------------------------+   +--------------------------------------+
```

Back on the notice page, signed in, the four cases (deck §23):

```
Match                                    Someone else                             Claim needed
Signed in with DigiLocker as Ravi        This notice is for someone else          Claim this record first
Kumar Sharma. Not you? Sign out          You are signed in with DigiLocker as     This record has no APAAR, so ...
Is that right?                           <name>, but this notice is about a       [ Claim with provisional ID ]
[      Yes, I joined       ]             different person's record. Nothing       Not you? Sign out
[    No, I never joined    ]             was recorded.
If you say no, a priority dispute        If you did join ABC College of
opens and an AICTE officer looks into    Engineering, the college may have ...
it first. Nothing changes for you        If you have never had anything to do
until they decide.                       with ABC College ..., you do not need
                                         to do anything.      [ Sign out ]
```

Data (pending): `GET /auth/digilocker/start?next=` (redirects to mockgov), `GET /auth/digilocker/callback?code&state` (signs the STUDENT in, sets the session, redirects to `/auth/digilocker/return?next=`); `GET /notices/{token}` adds `viewer {signed_in, name, match: MATCH | SOMEONE_ELSE | CLAIM_NEEDED}`; `POST /notices/{token}/respond` requires the student session and refuses with 401 `SIGNIN_REQUIRED` or 403 `NOTICE_IDENTITY_MISMATCH` otherwise. mockgov: `GET /digilocker/oauth/authorize` (picker, OTP, consent), `POST /digilocker/oauth/token`.
- `/login`: the Student card reads [login.card.student] and is a link to `/api/auth/digilocker/start?next=/student`, with [login.digilocker_hint] under it; no password field ever appears for a student.
- Notice page signed out: the claim card (W3-1), then [notice.signin_lead], [notice.signin_button] (a link, full width, 48 px), [signin.redirect_note] and [signin.demo_note] (the demo note only when `DEMO_MODE`), then What is this?. Yes and No do not exist in the page until sign-in.
- Return page: [signin.returning] with a progress indicator while the session settles, then a redirect to `next` (a same-origin path only). Cancelled at DigiLocker: [err.DIGILOCKER_CANCELLED] with [signin.try_again]; failed: [err.DIGILOCKER_FAILED]; bad or stale state: [err.DIGILOCKER_STATE_INVALID] with a link back to the notice.
- Signed in, MATCH: [notice.signed_in_as] and [notice.signout] above the question; Yes and No as W3-1 with the new words; the No sheet's text is [notice.no_confirm]; the answered states as W3-1 with [notice.no_done] and [notice.yes_done].
- Signed in, SOMEONE_ELSE: the claim card stays visible, then [notice.someone_else_heading] (h2), [notice.someone_else_body], [notice.someone_else_college], [notice.someone_else_other] and [notice.signout]; no buttons. Nothing is recorded, and the page never shows the record's student name.
- Signed in, CLAIM_NEEDED: [notice.claim_needed_heading], [notice.claim_needed], [notice.claim_button] to `/student/claim?next=/student/notices/{token}`, and [notice.signout].
- Demo DigiLocker (mockgov page, plain HTML): [dldemo.title] as the page title and heading, [dldemo.banner] in a bordered box on every step, [dldemo.footer] at the foot; the account list is a radio group with [dldemo.account_line] or [dldemo.account_line_no_apaar]; Ravi first; the search filters as you type ([dldemo.search_empty]); OTP is a one-field form with `inputmode="numeric"` and `autocomplete="one-time-code"`, [dldemo.otp_wrong] under it; consent has Allow and Deny of equal weight. Deny returns to Countersign as cancelled. The page never uses DigiLocker's logo or colours.
- Hindi: the toggle stays on the notice page and carries into the return page and the claim page for the visit; every string above has its `.hi` row (deck §23), except the Demo DigiLocker pages, which are English only.

States: loading skeleton of the claim; the W3-1 states (expired, invalid, change window, rate limited) unchanged; a network error during respond keeps the choice and retries once. Phone (390 px): as sketched; the sign-in button full width; the someone-else text in 16 px, never in an alert colour.

### W4-9. Claim by provisional ID

`/student/claim` (signed in as a STUDENT through DigiLocker).

```
390 px
Claim your record
Your college recorded your enrolment without an APAAR and gave you a provisional ID.
Enter it to link the record to your DigiLocker sign-in.
Provisional ID
[ PRV-________ ]
It starts with PRV- and has 8 more letters and digits, for example PRV-7K2M9QXA.
Countersign checks that the name and date of birth on your DigiLocker match the record.
A small difference in spelling is allowed; your DigiLocker sign-in decides.
[          Claim record          ]
Signed in with DigiLocker as <name> · Sign out
```

Data (pending): `POST /students/me/claim {provisional_id}` returning the claimed record (Identity now Confirmed with `source_line` "Student sign-in via DigiLocker · <date>"), or 422 `CLAIM_NO_MATCH`, 409 `CLAIM_ALREADY_CLAIMED`, 409 `CLAIM_NOT_NEEDED`, 429 with `retry_after`.
- The field upper-cases as typed, accepts the ID with or without the PRV- prefix and with spaces, and checks the shape before sending ([claim.format] under the field, focus kept, nothing sent).
- Submitting reads [claim.submitting]; success replaces the form with [claim.done_heading], [claim.done], then [claim.done_answer] (when `next` is a notice) and [claim.done_home].
- Errors under the field, the value kept: [err.CLAIM_NO_MATCH], [err.CLAIM_ALREADY_CLAIMED], [err.CLAIM_NOT_NEEDED]; after five failures in 15 minutes, [claim.locked] with the minutes, the button disabled.
- Signed out: redirect to DigiLocker sign-in with `next=/student/claim`.
- Hindi with the toggle, every string from its `.hi` row.

States: as above; an unexpected error shows [err.INTERNAL] with [err.retry]. Phone (390 px): as sketched; the input 48 px tall, monospace, `autocapitalize="characters"`.

### W4-10. Column mapping in the upload flow

`/college/upload` gains a step between choosing the file and uploading it; `/college/column-mapping` shows and changes the saved mapping.

```
Seat Ledger / Upload
Upload admissions file                          Academic year [2026-27 ▾]
1 Choose file ✓   2 Map your columns   3 Declare and upload
Map your columns
Your saved mapping matched 17 of 21 columns. Check the rest.
Column in your file        Countersign column
Student Name               [ Name (name) ▾ ]                 Required
DOB                        [ Date of birth (dob) ▾ ]         Required
Branch Code                [ Programme code (programme_code) ▾ ]  Required
Quota                      [ Admission route (admission_route) ▾ ] Required
Remarks                    [ Not used ▾ ]
...
Required columns not mapped yet: Category
[x] Saved for next time
[ Save mapping and continue ]   [ Choose another file ]
```

Data (pending): `POST /uploads/headers` (multipart `file`) returning the file's header names and the saved mapping's matches; `GET /institutions/{id}/column-mapping` and `PUT` the same with `{mapping: {their_header: our_column}}`; `POST /uploads` then applies the saved mapping (the batch shows it, D42).
- The step appears only when a header does not match a template column or the saved mapping; a file with template headers goes straight to step 3.
- One row per column of the file: its name as uploaded (monospace) and a select of the template columns ([mapping.col.ours], each "Field word (column)" with [mapping.required_tag]) plus [mapping.not_used]. [mapping.required_missing] and [mapping.duplicate] update live in an `aria-live` region; [mapping.continue] stays enabled and, when pressed with problems, moves focus to the first one and sends nothing ([err.MAPPING_INCOMPLETE], [err.MAPPING_DUPLICATE] from the server too).
- [mapping.saved_for_next_time] is ticked by default; saving shows [mapping.saved].
- The batch page (W2-2) gains [mapping.batch_line] with [mapping.view] to the settings page.
- `/college/column-mapping`: [mapping.settings_heading], [mapping.settings_lead], the same two-column table read only, [mapping.edit] to make it editable with [mapping.save], and [mapping.reset] with the dialog [mapping.reset_confirm] and [mapping.reset_done]; empty [mapping.empty].

States: reading headers (a skeleton of the table); error card; no student value from the file is shown at any step. Phone (390 px): each column becomes a block (their name above the select); the step indicator reads "Step 2 of 3: Map your columns".

### W4-11. Approval versions

A tab on institution detail ([tab.approvals]) for officers and the university; read only for the registrar on `/college` under each programme.

```
Programme  Version  Approved intake  Effective from  Source                   
CSE        v2       132              1 Sep 2026      Sample approval data      Current
CSE        v1       120              1 Jul 2026      Sample approval data
v2 raised the intake from 120 to 132 on 1 Sep 2026: 12 seats added and 12 records seated from the backlog.
```

Data (pending): `GET /approvals?institution_id&academic_year` with `versions[]` (D41). Columns `approval.col.*`, [approval.current] as a tag with an icon, [approval.change_up] or [approval.change_down] under the programme's rows, [approval.rule_tip] on the Approved intake header. Recording a version is not a web action this week; [err.APPROVAL_BELOW_ASSIGNED] is listed for the api's refusal. States: skeleton; empty [empty.programmes]. Phone: table in its container.

### W4-12. Certificate integration

`/university/certificates` ([nav.certificates]) and `/university/certificates/[enrolmentId]/print`. `/university/degrees*` redirect here.

```
Affiliated institutions / Certificate integration
Certificate integration
Countersign does not issue degrees. Your university awards the degree and prints its own certificate.
Countersign gives you two things to print on it: the graduate's masked APAAR, and a QR to their
completion attestation.
> How it works        > For your certificate system
[Search by name or the last four digits of APAAR]                              318 graduates
Graduate        APAAR / Provisional  Institution                 Programme  Year of completion  Completion attestation
<graduate name> XXXX XXXX 4417       ABC College of Engineering  CSE        2026                (✓) Issued 28 Oct 2026  [Print certificate block] [Download PDF]
<graduate name> PRV-XXXXXXXX         ABC College of Engineering  ME         2026                Not issued              [Issue completion attestation]
<graduate name> XXXX XXXX 8810       XYZ Institute of Technology CSE        2026                (⌛) Record not Countersigned
Viewing student records is logged.
```

Print view (the block for the certificate):

```
screen only: [ Print ]  Back to graduates  Print on A4, portrait, or place the PDF on your certificate.
------------------------------------------------------------------------------------------- A4
For the certificate awarded by Maharashtra State Technical University to
Name                 <graduate name>
Programme            B.Tech Computer Science and Engineering
Institution          ABC College of Engineering
Year of completion   2026
APAAR                XXXX XXXX 4417
                                                     [ QR, 30 mm ]
                                                     Attestation id <short id>
                                                     Scan to verify at localhost:3000/verify
Completion attestation issued 28 Oct 2026.
Signed by Countersign for Maharashtra State Technical University. This block is not a degree, and a
changed block does not verify.
```

Data (pending paths, D28 renamed): `GET /university/graduates?q&page` with each graduate's `record_status`; `POST /university/certificates/{enrolment_id}/issue`; `GET /university/certificates/{enrolment_id}` (print data with `qr_svg`); `GET /university/certificates/{enrolment_id}/block.pdf`.
- Copy and row actions per deck §11. A graduate whose record is not Countersigned shows [cert.status.not_eligible] with [cert.not_eligible_tip] and no action.
- The how-it-works and API disclosures are native `<details>`, closed by default after the first visit (remembered per browser).
- Issue sheet, print view, `@media print` rules and the QR rules as W3-5, with the `cert.*` words; the word "degree" appears only where the page says Countersign does not issue one.

States: skeleton rows; empty [empty.graduates]; no match [empty.graduates_search]; error card; 409s per deck §11. Phone (390 px): each graduate a block with the attestation word and the actions full width; the print view is not offered below 768 px (Download PDF is).

### W4-13. Evaluation report (if built)

`/admin/evaluation` (AICTE officer, [nav.evaluation]). Optional: `make eval` writes `eval_report.md` and `eval.json`, and this page only renders `eval.json` with the deck's labels.

```
Overview / Evaluation
Evaluation                                                              (i) Synthetic data
How Countersign performs on the synthetic test bed: generated colleges, students and planted cases.
Run 29 Oct 2026, 09:10 IST · seed 42 · 50 colleges · 50,000 records
Measure                                   Result                          Target        Met
Seeded inconsistencies caught             97.2% (486 of 500)              95% or more   (✓) Met
Cases raised on legitimate records        2.1% (21 of 1,000 known-clean)  Under 5%      (✓) Met
Time to process 50,000 rows               104.6 s                         Under 2 min   (✓) Met
Cross-college access attempts refused     2,450 of 2,450                  All refused   (✓) Met
...
Detection by case type
We can only check data we receive, and a student who colludes cannot always be caught. ...
[Download eval_report.md]  [Download eval.json]
```

Data (pending): `GET /admin/evaluation` returning the latest `eval.json`. The numbers above are an illustration of the layout, not results. Columns `eval.col.*`, values per `eval.value.*`, Met and Not met words with icons ([eval.met.*]), [eval.limit] under the tables, [eval.synthetic] as a tag beside the heading. Empty: [eval.none]. Phone: the table scrolls in its container with Measure sticky.

### W4-14. `/admin/psi` (private set intersection, last and only if disk allows)

Unchanged from the earlier plan: two panels "Countersign holds" and "Partner registry holds" showing only counts; [psi.compute]; [psi.result] with [psi.explain]; "Show how" reveals the steps. If it is not built, the nav item stays disabled with its hint.
