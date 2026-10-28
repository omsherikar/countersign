# Review checklist

One line per check, pass or fail. Run against the built pages with the seeded data (`make up && make datagen && make seed`), signed in as each demo user. Record the result per page in a table under each section when reviewing. Copy ids refer to `05-copy-deck.md`.

Sections A to K are the Week 1 pages. Sections L to U are the Week 2 pages (`04-pages-later.md` W2-1 to W2-9, API_CONTRACT Addendum 2); from Week 2 the seed also loads the update files, and where a Week 1 line and a Week 2 line disagree (labels, the Countersigned tile, the default sort, nav items) the Week 2 line wins. Sections V to AH are the Week 3 pages (`04-pages-later.md` W3-1 to W3-10, DECISIONS D23 to D33); from Week 3 the seed also sends notices and applies the simulated replies, leaving Ravi Kumar Sharma's notice unanswered, and where a Week 3 line and an earlier one disagree (nav items, the Student check words, the Countersigned tile, read-only lines, the Assignee column, action buttons) the Week 3 line wins. In particular, the lines naming [university.degree_teaser] (H), [verify.coming] (I) and [flag.readonly_officer] (S) give way to sections AB, AA and AC.

## A. Global (check on every page)

- [ ] No outline of India anywhere: pages, icons, favicon, loading placeholders, empty states.
- [ ] No full APAAR, mobile, email or address appears anywhere outside `/student`; masks are exactly `XXXX XXXX 4417` and `XXXXXX4521` as sent by the api.
- [ ] A student with `apaar_masked: null` shows "Provisional id PRV-XXXXXXXX", never a blank cell.
- [ ] No status word other than Open, Documents requested, Cleared, Escalated, Confirmed is used for flags; no "rejected", "blocked", "fraud", "fake", "illegal" anywhere.
- [ ] No percentage is shown for a per-enrolment score; "Countersigned" tile reads "Not yet computed" in Week 1.
- [ ] Every Week 1 null (`integrity_index`, `countersigned_pct`, `score`) renders "Not yet computed", not "0", "N/A", "null" or blank.
- [ ] Numbers use en-IN grouping (18,960; 1,20,000) and are right-aligned with tabular numerals.
- [ ] Dates render as `14 Jul 2026`; timestamps add `, 09:30 IST`.
- [ ] Indian-English spelling: enrolment, programme, counselling; no "enrollment" or "program" in any visible string.
- [ ] No em dashes and no exclamation marks in any visible string.
- [ ] Top bar shows the scope label from `dashboard.scope.label` (or `/me` scope name) on every signed-in page.
- [ ] User menu shows the role in words from `shell.role.*` and a "Sign out" item that calls `POST /auth/logout` and lands on `/login`.
- [ ] Nav items for absent endpoints are disabled with "Coming in Week N", not dead links; none navigates.
- [ ] Opening a route of another role redirects to the user's landing route with the [err.FORBIDDEN_redirect] toast.
- [ ] A 401 during use shows [err.UNAUTHENTICATED] with a "Sign in" link carrying `next`.
- [ ] A failed request shows the message plus "Ref: CODE" in small text; never a code alone, never a raw JSON body.
- [ ] Loading states are content-shaped skeletons; the nav stays usable while loading.
- [ ] Every table is a real `<table>` with `<th scope="col">`; sortable headers expose `aria-sort`.
- [ ] Every drill-down is an `<a href>`, reachable with Tab and Enter; no click-only `div` rows.
- [ ] Focus is visible on every interactive element (2 px ring, 3:1 contrast).
- [ ] Text contrast meets 4.5:1; status is never conveyed by colour alone (word or icon present).
- [ ] Page `<title>` is "<page> | Countersign".
- [ ] Layout works at 1280, 1024 and 375 px wide with no horizontal scroll (tables may scroll inside their own container).
- [ ] Any table containing a student column carries the footer line [privacy.read_logged].

## B. `/login`

- [ ] Six role cards in the order AICTE officer, Regional officer (Western), Registrar ABC, Registrar XYZ, Student, University; each with email visible and "Demo credentials" tag.
- [ ] Clicking a card prefills email and password and moves focus to "Sign in"; cards are buttons with `aria-pressed`.
- [ ] Submitting calls `POST /auth/login` with a JSON body; button reads "Signing in" and inputs are disabled while in flight.
- [ ] 200 redirects by role: `/aicte`, `/ro`, `/college`, `/student`, `/university`; no flash of the login form after redirect.
- [ ] 401 shows [err.INVALID_CREDENTIALS] inline with `role="alert"`, clears the password and focuses it.
- [ ] 429 shows [err.RATE_LIMITED] and disables the button with a countdown.
- [ ] 422 shows field errors from `details.fields` under the matching field.
- [ ] Network failure shows [err.NETWORK].
- [ ] A signed-in user opening `/login` is redirected to their landing route.
- [ ] Labels are real `<label for>`; autocomplete attributes `username` and `current-password` are set; "Show"/"Hide" toggle works by keyboard.
- [ ] Footer line [login.demo_footer] present.

## C. `/aicte`

- [ ] Heading "Overview"; academic year selector shows `academic_year` from the summary.
- [ ] Five KPI tiles with the exact labels Institutions, Programmes, Approved seats, Enrolments, Open flags, values from `kpis.*`; Open flags shows "0", not blank.
- [ ] Sixth tile "Countersigned" reads "Not yet computed" when `countersigned_pct` is null.
- [ ] Sources panel lists APAAR registry, Counselling list, ABC credits, DigiLocker, Study in India with status words OK, Unavailable or Disabled, latency in ms, the adapter chip ("mockgov") and "Checked <relative>" with the absolute time on hover.
- [ ] With chaos `apaar down`, the panel shows APAAR registry Unavailable with the `detail` text on hover and nothing else on the page turns red.
- [ ] Sources panel failure shows "Sources: could not check" with retry and the rest of the page still renders.
- [ ] Institutions table columns in order: Name, Permanent id, State, Region, Type, Programmes, Approved seats, Enrolments, Open flags, Integrity Index.
- [ ] Default sort is Enrolments descending (`sort=enrolments&order=desc`), ties by name; header tooltip reads [table.sort_tip].
- [ ] Name is a link to `/aicte/institutions/{id}`; Permanent id is monospace; Type uses the words from `type.*`.
- [ ] State and Type filters and the search box set URL query params; reload keeps them; "Clear filters" appears with [empty.institutions_filtered] when nothing matches.
- [ ] Search box has placeholder [search.placeholder], is focused by `/` and `Ctrl+K`, cleared by `Esc`, and queries `GET /institutions?q=` debounced.
- [ ] Pager shows "1 to 25 of 50" and the count line "50 institutions".
- [ ] By state table: State, Region, Institutions, Programmes, Approved seats, Enrolments, Open flags; sorted by state name; row click applies the state filter to the institutions table.
- [ ] By region table: Region, Institutions, Approved seats, Enrolments, Open flags; sorted by region name; ten rows for the national seed.
- [ ] Region codes are rendered as names ("Western (Mumbai)" or "Western"), never raw `WEST`.
- [ ] Under 1024 px the By state and By region tables stack and the Sources panel drops below the tiles.
- [ ] Nav: Overview active; Cases, Reports, Audit disabled with their week; System enabled.

## D. `/aicte/institutions/[id]`

- [ ] Breadcrumb "Overview / <name>", last crumb plain text.
- [ ] Header shows name (h1), permanent id (mono), type word, "<city>, <state_code>" (city omitted when null), region name, university name, "est. <year>" (omitted when null).
- [ ] Integrity Index block reads "Not yet computed".
- [ ] Tabs Programmes, Enrolments, Seats, Flags follow the ARIA tabs pattern (arrow keys) and persist in the URL hash.
- [ ] Programmes table columns: Code, Programme, Level, Shift, Approved, Admitted, Seated, Unseated; default sort by code; header tooltips [col.approved_tip] and [col.admitted_tip] present.
- [ ] Seated equals `enrolments - unseated`; with the Week 1 seed (all unseated) the page renders without special-casing.
- [ ] Unseated > 0 renders an amber chip containing the number and the word "unseated", with tooltip [ledger.unseated_tip]; the chip is not red.
- [ ] Pools expander is a `<button aria-expanded>`; expanded text reads "Regular 114 of 114 · NRI 6 of 6 · TFW 4 of 6 (supernumerary) · Lateral 0 of 12 (supernumerary) · International 1 of 18 (6 reserved for CIWG)" for the ABC CSE seed.
- [ ] Flags section shows [empty.flags_institution] in Week 1.
- [ ] Enrolments tab columns: Student, APAAR / Provisional, Consent, Programme, Year, Route, Category, Seat, Countersign, Flags, Uploaded; defaults `status=ACTIVE`, `academic_year=2026-27`; search by name or last 4 digits.
- [ ] Route and Category cells use the words from `route.*` and `category.*`; Seat null renders "Unseated" in muted text.
- [ ] Countersign cell shows five hollow segments and "Not yet checked" when `score` is null; the strip has the aria-label from `strip.aria` or "Not yet checked".
- [ ] Enrolments footer shows "<total> enrolments" and [privacy.read_logged].
- [ ] Seats tab columns: Seat code, Programme, Type, Reserved for, Status, Holder, Assigned; filters Programme, Type, Status; Week 1 shows every seat Free with blank holder.
- [ ] An id outside scope (as `ro.west@aicte.demo` opening a Southern institution) shows [err.NOT_FOUND_institution] with "Back to overview" and no hint that it exists.
- [ ] 404 page does not render the shell of another role or leak the id in a heading.

## E. `/ro`

- [ ] Heading reads "Western region overview" from `scope.label`; top bar scope matches.
- [ ] No Sources panel; the line "Regional office: Mumbai" appears instead.
- [ ] Institutions table hides the Region column and region filter; every row's state belongs to the region (MH, GA, DH for WEST).
- [ ] By state contains only the region's states; the single By region row is rendered as a summary line, not a one-row table.
- [ ] Row links go to `/ro/institutions/{id}` and that page carries "/ro" crumbs.
- [ ] Nav: Overview, Cases (disabled, Week 2), Reports (disabled, Week 4); no System or Audit items.
- [ ] `ro.south@aicte.demo` sees Southern data only (TN, PY, AN) and a different count line.

## F. `/college`

- [ ] Top bar scope is the institution name from `/me`.
- [ ] Heading "Seat ledger"; tiles Programmes, Approved seats, Admitted, Unseated with values from the scoped summary and the detail.
- [ ] Programmes table as D with the pools row expanded by default for any programme with unseated > 0.
- [ ] Pools line ends with [ledger.pools_source] and a "What are pools?" popover showing [ledger.pools_help], reachable by keyboard.
- [ ] Flags section shows [empty.flags_college] including the sentence "Nothing is rejected automatically; an officer reviews every flag."
- [ ] "Last upload" line reads [college.no_upload_yet].
- [ ] Nav: Seat ledger active, Upload disabled (Week 2), Enrolments enabled, Flags disabled (Week 2).
- [ ] `/college/enrolments` renders the same enrolments table as D scoped to the college with the privacy footer.
- [ ] No other institution, region or national number appears anywhere on the page.
- [ ] Calling `/api/institutions/<other id>` from this session returns 404 and the UI never lists other ids.

## G. `/student`

- [ ] Heading "My enrolment"; name, masked APAAR (or Provisional id), consent badge with tooltip, date of birth, masked mobile, email (line omitted when null).
- [ ] One card per enrolment with lead "<institution> says you joined <programme>", meta "Academic year 2026-27 · Year 1 · Active".
- [ ] Countersign strip shows five hollow segments and "Not yet checked"; the five check names are listed under it in order.
- [ ] Notices and My proofs sections show [empty.notices_student] and [empty.credentials_student].
- [ ] Privacy line [privacy.student_line] present; "How my data is used" is disabled with "Coming in Week 3".
- [ ] Single column, max width 640 px, 44 px tap targets, body text at least 16 px; readable at 375 px.
- [ ] Tooltips open on focus and on tap, not hover only.
- [ ] Opening `/aicte` as the student redirects to `/student` with the toast.

## H. `/university`

- [ ] Top bar scope shows the university name from `/me` `scope.university_name`.
- [ ] Heading "Affiliated institutions"; tiles from the UNIVERSITY-scoped summary.
- [ ] Table columns: Name, Permanent id, State, Type, Programmes, Approved seats, Enrolments; no Region, Open flags or Integrity Index.
- [ ] Row links to `/university/institutions/{id}`, which shows the detail with the Flags tab hidden.
- [ ] Degree print nav item disabled with "Coming in Week 3"; teaser text [university.degree_teaser] present.
- [ ] Only affiliated institutions are listed (`university_id` matches on every row).

## I. `/verify`

- [ ] Public: loads with no cookie and shows no nav, no search, no sign-in requirement.
- [ ] Heading [verify.heading], lead [verify.lead], code input with placeholder [verify.placeholder], "Scan with camera" and "Check" rendered disabled with `aria-disabled` and the hint [verify.coming].
- [ ] Paragraph [verify.what] visible; "What is Countersign?" expands a static paragraph on the same page.
- [ ] Works at 320 px wide; targets 44 px.

## J. `/admin/system`

- [ ] Only `admin@aicte.demo` can open it; RO, registrar, student and university users are redirected with the toast.
- [ ] Breadcrumb "Overview / System"; heading "System".
- [ ] Government sources table: Source, Status, Latency, Detail with the five source names, "adapter: mockgov", "Checked <time>", and a "Ping" button that reads "Pinging" while in flight.
- [ ] With chaos `sii down`, the Study in India row reads Unavailable with the detail text; other rows stay OK.
- [ ] Audit chain section shows [admin.verify_idle] until "Verify chain" is pressed, then [admin.chain_ok] or [admin.chain_broken] with the entry count from `length`.
- [ ] Service health line from `/healthz` shows api, db, redis status and version.
- [ ] Demo controls section is labelled "Demo"; Chaos block either works through a proxy or shows [admin.chaos_cli]; Reset block either works or shows [admin.reset_cli]. No broken form is shown.
- [ ] Reset (when present) opens the confirmation [admin.reset_confirm] and disables other controls while running.
- [ ] Status changes are announced through an `aria-live="polite"` region.
- [ ] Nothing on this page is reachable from the RO, college, student or university nav.

## K. Demo rehearsal (Week 1 subset of Flow 0)

- [ ] Login -> `/aicte` -> ABC College detail -> `/ro` -> `/college` -> `/student` -> `/admin/system` can be walked in under 3 minutes without any error toast.
- [ ] Setting chaos `apaar down` and pressing Ping shows Unavailable; resetting chaos and pinging again shows OK.
- [ ] `make demo-reset` followed by a page refresh shows the same numbers as the first run.

## L. Week 2 global (check on every Week 2 page)

- [ ] Numbers rule: no screen compares all-year enrolments with one year's seats; no ratio, bar, percentage, difference or "against" sentence pairs Students on roll (`enrolments`) with Approved seats.
- [ ] Every Approved seats figure (tile, column, cell) is followed directly by Admitted for the same academic year.
- [ ] Every Students on roll or On roll figure carries "All years of study" (hint or tooltip) and never sits between Approved seats and Admitted.
- [ ] No fill percentage appears anywhere: no "%" beside seats, admitted or on-roll figures, including state cards.
- [ ] ABC College CSE 2026-27 reads Approved 120, Admitted 132, Seated 120, Unseated 12 on the /aicte, /ro and /college programme rows, and its flag reads "132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat."
- [ ] An institution's Admitted figure equals the sum of its programmes' Admitted column.
- [ ] Flag summaries, evidence facts, check details, row problem messages and batch `error` sentences match the api response character for character; no component builds them from `flag.*.summary` or `check.detail.*`.
- [ ] Flag types use the `flag.<TYPE>.name` words; "Invalid APAAR", "Ghost ring", "Duplicate in upload", "fraud" and "fake" appear nowhere.
- [ ] A PENDING check is hollow and never red or crossed on every strip, badge and cell.
- [ ] Open-flag counts (tiles, cells, tab labels) are ink, never red; severity colour appears only on severity chips.
- [ ] Upload status words are only Queued, Validating, Processing, Done and Failed; "Checking" never appears as a status.
- [ ] The word "rejected" appears on no upload screen.
- [ ] Masked values print exactly as sent (`XXXX XXXX 4417`, `XXXXXX4521`, `<11 characters>`); no page shows a 12-digit APAAR or a 10-digit mobile.
- [ ] A masked mobile appears only on /student and on enrolment detail for officers and the registrar; never in a table and never for the university.
- [ ] Enrolment detail, flag detail and the row problems table each carry [privacy.read_logged].
- [ ] Dates read like `5 Oct 2026` in api sentences and in web-rendered dates; "Sept" appears nowhere.
- [ ] Nav: the registrar's Upload and Flags and the officers' Cases are live links; Reports, Audit, Notices, My proofs, Degree print and Why this score stay disabled with their week.
- [ ] No Week 2 page scrolls sideways at 1280, 1024 or 375 px (tables scroll inside their own wrapper).
- [ ] No Clear, Request documents, Escalate, Confirm or Respond button appears anywhere.

## M. `/college/upload`

- [ ] Heading "Upload admissions file", academic year select at 2026-27, [upload.lead] and [upload.changes_note] present.
- [ ] "Download CSV template" and "Download XLSX template" save `countersign_upload_template.csv` and `.xlsx` with the 19 headers in §A2.2 order.
- [ ] The columns panel lists six required and thirteen optional columns in §A2.2 order, in monospace.
- [ ] No Kind control is shown and no `kind` field is sent.
- [ ] The declaration text equals [upload.declaration]; pressing Upload without the tick shows "Tick the declaration to upload." under the checkbox, focuses it and sends no request.
- [ ] A .pdf shows [upload.err_type] and a 21 MB file shows [upload.err_size], both with no network request.
- [ ] The request through the proxy is `multipart/form-data` with a boundary and carries only `file`, `academic_year` and `declaration=true`.
- [ ] While sending, the button reads "Sending file, n%" and the inputs are disabled.
- [ ] A file without `name` and `dob` columns shows "The file is missing required columns: name, dob." and [upload.header_help], stays on the page and keeps the file chosen.
- [ ] A header-only file shows "The file has a header but no rows."
- [ ] A second upload while one is running shows [err.UPLOAD_IN_PROGRESS] with a link to the running batch.
- [ ] A 202 lands on `/college/uploads/{id}` reading Queued or a later status.
- [ ] Previous uploads has columns File, Uploaded, By, Kind, Source, Status, Rows, Accepted, With errors, With warnings, newest first; seeded batches read "Demo seed"; each row links to its batch page.

## N. `/college/uploads/[batchId]`

- [ ] The header shows the filename and "<Kind> · <Source> · uploaded <date>, <time> IST by <name>".
- [ ] The rail shows Queued, Validating, Processing, Done in order, the current one marked by icon and word, not colour alone.
- [ ] While processing, the line reads "Step n of 8: <stage word>" with the `upload_stage.*` words; while queued it reads [upload.queued_note].
- [ ] The progress bar has `role="progressbar"` with `aria-valuenow` and never goes backwards between polls.
- [ ] Polling runs every 2 s and stops at Done or Failed (no further `GET /uploads/{id}` in the Network tab).
- [ ] The done card's numbers equal `counts.accepted`, `.seated`, `.unseated`, `.flags_raised`, and its change line equals `counts.created`, `.updated`, `.unchanged`, `.withdrawn`, `.transferred`, `.released`.
- [ ] The done card shows [upload.done_note] and links to the seat ledger, enrolments and flags.
- [ ] Uploading the same file again shows [upload.same_file] and "0 new".
- [ ] With chaos `apaar down`, the APAAR registry line reads [upload.source_waiting] with `sources[].unavailable` and the batch still reaches Done.
- [ ] A failed batch shows [upload.failed], the api `error` sentence verbatim, [upload.failed_earlier] and a link to upload again.
- [ ] Row problems has columns Row, Level, Column, Problem, Value as uploaded; Level is a word with an icon; Column is the template name in monospace.
- [ ] Each row problem's Problem equals the api `message` and its Value equals `value_masked` (null reads "blank").
- [ ] The heading count equals the errors endpoint `total`; All, Errors and Warnings send `level` and update the count.
- [ ] "Download errors as CSV" is a link that saves `<file stem>_errors.csv` with the header `row_no,level,field,code,message,value_masked`.
- [ ] A batch with no problems shows [upload.errors_none].
- [ ] The registrar opening another college's batch id sees [err.NOT_FOUND_upload].

## O. Countersign strip and enrolment tables

- [ ] Every strip has five segments in the order Identity, Admission, Seat, Studying, Student: filled for PASS, filled with a cross for FAIL, hollow for PENDING, hatched for NA.
- [ ] The demo student's row reads "3 of 4" with Studying hatched and Student hollow.
- [ ] ", n pending" appears only on rows with a pending check other than Student.
- [ ] The strip is one Tab stop; Enter, hover or tap opens a popover with five "<Check>: <word>" lines; Student reads "Notice not sent yet" and any other pending check reads "Pending".
- [ ] The strip's `aria-label` follows [strip.aria] with the same words.
- [ ] A row with `score: null` shows five hollow grey segments and "Not yet checked".
- [ ] The Student cell links to the role's enrolment detail route.
- [ ] The Seat cell shows the seat code in monospace or "Unseated" in muted text, never an amber chip.
- [ ] The Flags cell shows at most two chips (type name and severity word) then "+n"; each of the 12 unseated ABC CSE first-years shows Excess admission.
- [ ] Check, Result, Flags and Seat filters send `check_type`, `check_status`, `flagged` and `seated`; Check alone sends nothing; the filters survive reload; no match shows [empty.enrolments_filtered].

## P. Enrolment detail

- [ ] `/aicte/enrolments/{id}`, `/ro/enrolments/{id}`, `/college/enrolments/{id}` and `/university/enrolments/{id}` open for their roles; an out-of-scope id shows [err.NOT_FOUND_enrolment].
- [ ] The header shows name, masked APAAR or provisional id, consent badge, programme, institution link and the strip with "Countersigned 3 of 4" for the demo student.
- [ ] The enrolment block shows "2026-27 approval", year, route with counselling reference, category, "Active since <date>", admitted on, mode and "Row <n> of <file>".
- [ ] The seat block shows "<seat code> · Regular · 2026-27 approval · assigned <date>", or "No seat held." with a link to the named flag for an unseated student.
- [ ] The checks table has five rows in order; Detail equals `detail.summary` verbatim; Result uses the copy deck words.
- [ ] With chaos `apaar down` and a new upload, an affected Identity row reads "Awaiting source", hollow, Detail "APAAR registry did not respond. This check stays pending until a recheck or the next upload.", plus [check.attempts].
- [ ] A name-review case (similarity 75 to 89) reads "Needs review", not "Awaiting source".
- [ ] "Recheck pending checks" shows only for the AICTE officer, the regional officer and the registrar, and only when a check other than Student is pending.
- [ ] After chaos reset, Recheck turns that Identity row to Countersigned and announces "Identity: Pending to Countersigned" in an `aria-live` region.
- [ ] A 429 on recheck shows [err.RATE_LIMITED] and the button counts down.
- [ ] Flags on this enrolment shows severity, type name, status, summary verbatim and date; rows link for officers and the registrar and are plain text for the university.
- [ ] The masked mobile shows for officers and the registrar and not for the university.

## Q. Institution detail and `/college`

- [ ] Header figures in the order Approved seats, Admitted, Students on roll, Open flags; the first two hinted "2026-27 intake", the third "All years of study".
- [ ] Programmes columns are Code, Programme, Level, Shift, Mode, Approved, Admitted, Seated, Unseated; the Admitted tooltip equals [col.admitted_tip] with the year filled.
- [ ] Seated equals the sum of the assigned figures in that programme's pools line.
- [ ] The last upload line reads [last_upload.line] from `last_upload`, with the status word.
- [ ] The Flags tab label shows `flags_open`; its request is `/flags` with `institution_id`, `academic_year` and `status=OPEN`, and its `total` equals `flags_open`.
- [ ] University users see no Flags tab and no Open flags figure.
- [ ] Officers see "Recheck pending checks" in the header; the registrar and the university do not.
- [ ] After chaos reset, the institution recheck announces [recheck.institution_result] with "0 still pending".
- [ ] `/college` tiles are Approved seats, Admitted, Seated, Unseated, then the line "<n> students on roll across all years of study"; no tile shows the all-years figure.
- [ ] The `/college` Flags section lists at most five open flags with summaries verbatim and "See all flags".
- [ ] No institution other than the registrar's own is named anywhere on `/college` pages; a cross-institution duplicate reads "another institution in <state>".

## R. Flag lists (`/aicte/cases`, `/ro/cases`, `/college/flags`, Flags tab)

- [ ] `/aicte/cases` opens on status Open, sorted most severe first; the count line equals "<total> open flags in <institutions> institutions" from the response.
- [ ] Columns are Severity, Type, Institution, Programme, Evidence, Related, Opened; there is no Assignee column.
- [ ] Evidence shows the summary on one line with the full sentence on focus and on hover.
- [ ] Status, Severity, Type, Institution, State, search and Sort set `f_` URL params that survive reload; every request carries `academic_year`.
- [ ] Setting Status to anything but Open switches the count line to [table.count.flags_any].
- [ ] Filters with no match show [empty.cases_filtered] with "Clear filters".
- [ ] `j` and `k` move through rows and Enter opens flag detail; every row is an `<a href>`.
- [ ] `/ro/cases` lists only the region's institutions and its State filter lists only the region's states.
- [ ] `/college/flags` has the heading [flags.heading_college], no Institution or State filter, and never names another institution.
- [ ] University and student users have no Cases or Flags nav item, and `/aicte/cases` redirects them with the toast.

## S. Flag detail

- [ ] The header shows the type name, "<Severity> · <Status> · opened <date>" and "<institution> · <programme> · <year>".
- [ ] [flag.readonly_officer] (officers) or [flag.readonly_college] (registrar) sits under the header, and no action button exists.
- [ ] Evidence shows `evidence.summary` verbatim, the facts as Fact, Value, Source in the order sent, and "Rule: <rule_source>".
- [ ] The ABC CSE Excess admission facts read Approved intake 120, Admitted (active) 132, Seated 120, Unseated 12.
- [ ] Excess admission and Quota breach show no "Enrolment this flag is about" block; enrolment-level flags show exactly one row there.
- [ ] Related enrolments shows the count and rows with an Institution column; officers see both institutions of a cross-institution duplicate.
- [ ] The registrar's view of a cross-institution duplicate shows [flag.related_hidden] and never the other institution's name.
- [ ] Student cells link to enrolment detail.
- [ ] History shows exactly one line, "Flag opened" with the created time.
- [ ] An out-of-scope flag id shows [err.NOT_FOUND_flag].

## T. Dashboards

- [ ] `/aicte` tiles in the order Institutions, Programmes, Approved seats, Admitted, Students on roll, Open flags, Countersigned, No source disagrees.
- [ ] Countersigned reads "0% of enrolments fully countersigned" with [kpi.countersigned_tip]; No source disagrees reads "<clear_pct>% of enrolments" with [kpi.clear_tip]; a null reads "Not yet computed".
- [ ] Percentages print as sent without a trailing ".0".
- [ ] Open flags by type lists only non-zero types, in the order sent, with copy deck names; each row links to the case queue filtered by that type and Open.
- [ ] The institutions table requests `sort=flags_open_desc` by default; the Open flags header has `aria-sort="descending"` and [table.sort_tip]; Admitted follows Approved seats and On roll follows Admitted.
- [ ] By state and By region show Approved seats, Admitted, On roll and Open flags, with no fill percentage.
- [ ] `/ro` shows the same, scoped to the region.
- [ ] `/university` shows Admitted after Approved seats and On roll in place of Enrolments, and no flag figure.
- [ ] `/student` shows "3 of 4 sources agree" under the strip and [student.check_student_pending].

## U. Demo rehearsal (Week 2)

- [ ] The registrar uploads an update file: Queued, Validating, Processing, Done; withdrawals release seats and the `/college` Seated and Unseated tiles change within the minute.
- [ ] A late refill from the update file raises Late refill reading "after the last admission date 15 Sep 2026" with "Rule: Last admission date for 2026-27 (rules.yaml cutoff_dates)".
- [ ] Chaos `apaar down`, upload, open an affected enrolment (Identity "Awaiting source", hollow), reset chaos, recheck the institution: the row turns Countersigned and the outage raised no flag.
- [ ] `/aicte` to Cases to the ABC Excess admission flag to a related enrolment and back, by keyboard only, with no error toast.

## V. Week 3 global (check on every Week 3 page)

- [ ] Nav: Notices, My proofs and Privacy (student), Degree print (university), Audit and Data requests (AICTE officer) are live links; only Reports, Why this score and Private matching stay disabled, with "Coming in Week 4"; "Coming in Week 3" appears nowhere.
- [ ] No page, file or email shows a full APAAR: the mask is exactly `XXXX XXXX 4417` on the notice page, the share sheet, proof details, the verifier result, the degree print view, the PDF insert, the audit page, the data requests queue and the JSON export.
- [ ] The student's comment on a notice reaches the AICTE officer and the regional officer only: open the same Student denied flag and enrolment as each role and confirm it is absent from every `/college/*` and `/university/*` page, the registrar's flag evidence, the documents email and the student's own notices list.
- [ ] Every QR has its text under it as real, selectable text: the 6-group share code under a wallet QR, the proof id and the verify address under a degree QR.
- [ ] Status is never colour alone: every check result, notice reply, delivery state, proof status, verifier result, flag status, data request status and chain result shows a word with an icon, and still reads correctly in greyscale.
- [ ] A pending Student check is hollow and neutral, reads "No reply yet" in lists, and never counts in ", n pending"; only a No makes it Not countersigned; silence never does.
- [ ] No student, registrar or verifier screen shows "SD-JWT", "JWS", "nonce", "presentation", "status list", "token" or "hash".
- [ ] Every new string matches its copy deck id; no em dashes, no exclamation marks, Indian-English spelling, in English and in Hindi.
- [ ] Every sheet and dialog (No sheet, share sheet, case sheets, resend, issue degree proof, withdraw consent, resolve request) is a modal dialog labelled by its heading: focus moves inside on open, Tab and Shift+Tab stay inside, Esc closes it, and focus returns to the control that opened it.
- [ ] Every form field has a visible `<label for>`; required fields carry `aria-required`; an error sits under its field, is linked with `aria-describedby`, and the first invalid field receives focus.
- [ ] Toasts, countdown milestones, copy confirmations, live counts and chain results are announced through an `aria-live="polite"` region.
- [ ] Public pages (`/student/notices/[token]`, `/verify`, `/verify/[code]`, `/verify/d/[jws]`) and the student pages work at 390 px wide: no horizontal scroll, body text 16 px, targets at least 44 px, primary buttons full width and 48 px tall.
- [ ] Text contrast is at least 4.5:1 and focus rings at least 3:1 on every new component, in light and dark (`python3 design/tools/contrast.py` passes).
- [ ] Each read the decisions name (notice page view, proof read and share, verifier check, attachment download, enrolment detail view, data export) appears on `/admin/audit` as a Viewed entry.

## W. `/student/notices/[token]`

- [ ] The link from Mailpit and the Respond link in the mockgov DigiLocker inbox both open the page with no cookie: no nav, no sign-in.
- [ ] The claim shows institution, programme, academic year, year of study, upload date and the masked APAAR or "Provisional id PRV-XXXXXXXX"; the student's name, date of birth, email and mobile appear nowhere on the page.
- [ ] [consent.notice] sits above the buttons; at 390 px Yes and No are full width, equal weight, Yes above No, neither red.
- [ ] Tab order is language toggle, Yes, No, What is this?; every control works by keyboard.
- [ ] Yes shows [notice.yes_done] and [notice.yes_next]; Ravi's Student row then reads "Confirmed by the student on <date> (email)." and his strip "4 of 4".
- [ ] No opens the sheet with focus in the optional comment, [notice.no_comment_hint] under it; Esc returns focus to No; Send shows [notice.no_done]; a High Student denied flag appears in the officer queue and the enrolment itself is unchanged.
- [ ] Double tapping Yes sends one request.
- [ ] Reopening the link within 7 days shows [notice.answered] with Change my answer; after one change, [notice.change_used] and no buttons; a further respond returns 409 and the page shows [notice.change_used].
- [ ] Changing No to Yes turns the Student check to Countersigned while the Student denied flag keeps its status and gains a System row in its history.
- [ ] An expired link shows [notice.expired] with no claim; a malformed and an unknown link both show [notice.invalid] with no claim and look identical.
- [ ] The 31st request in a minute from one IP shows [notice.rate_limited] with a countdown.
- [ ] The Hindi toggle is a button with `aria-pressed`; with Hindi on, every visible string (states, the sheet, errors) is its `.hi` row and the content has `lang="hi"`; only names, "APAAR", "Privacy" and "My proofs" stay in Latin script.

## X. `/student/notices` and `/student`

- [ ] Every notice for the signed-in student is listed, newest first, with sent date, institution, claim, channels and the reply words of deck §8; a No carries [notices.denied_line].
- [ ] An unanswered live notice shows [notices.reply_hint] and no link to the notice page.
- [ ] No notices shows [empty.notices_student].
- [ ] At 390 px the list is stacked blocks; from 768 px it is a table with `<th scope="col">`.
- [ ] `/student`: the line under the strip follows the newest notice (not sent, sent, expired, denied; nothing after a Yes); "How my data is used" links to `/student/privacy`; no "Week 3" text remains.

## Y. `/student/wallet` and the share sheet

- [ ] After Ravi answers Yes, an Enrolment proof card shows the Active badge (icon and word), the issuer line, the issued date and the valid-until date.
- [ ] A student whose Student check is pending sees [wallet.not_issued_heading] with [wallet.not_issued.reply]; no wallet text names a flag or a failed check.
- [ ] Share proof opens a modal dialog (a bottom sheet at 390 px) with focus on Name; Tab never leaves it; Esc closes it and focus returns to Share proof.
- [ ] The sheet lists 8 fields: Institution and Programme first, checked, locked and announced as always shared; then Name, Academic year, Year of study, Date of birth, APAAR (masked) and Checks that agree, unticked, each showing the value it would share.
- [ ] Each field is a real checkbox with a label; Space toggles it; "Shares n of 8 fields" updates and is announced.
- [ ] Create QR without "I agree" shows [wallet.consent_required], focuses the checkbox and sends nothing.
- [ ] Sharing Institution, Programme and Year of study shows "Shares 3 of 8 fields", the QR, the 6-group code in monospace under it, "Valid for 10 minutes" and a countdown.
- [ ] The QR image has a text alternative; the code under it is selectable text, not part of the image; focus moves to the code after Create QR.
- [ ] Copy code and Copy link copy the right values and announce [wallet.code_copied] or [wallet.copied].
- [ ] After 10 minutes the QR gives way to [wallet.expired_share]; the old code is struck through with the word Expired; the verifier then reads Expired.
- [ ] After a verifier check the history shows "Shared with a verifier at <hh:mm>".
- [ ] After an AICTE officer revokes the proof, the card shows Revoked with a reason sentence and no Share button, and the verifier reads Revoked.
- [ ] No full APAAR appears in the sheet, the details list or the history.

## Z. `/student/privacy`

- [ ] Three consent rows in the order APAAR, Notices, Sharing, each with purpose words, state word, date, the via line, and "Show the exact text" revealing the stored text with its version.
- [ ] Withdraw appears on Notices and Sharing only; its dialog opens with focus on Keep it; confirming shows [privacy.withdraw_done.*] in a live region.
- [ ] After withdrawing Notices, the enrolment's Resend notice is replaced by [enrolment.notice.consent_off]; after withdrawing Sharing, a live share code reads Expired at the verifier.
- [ ] The APAAR row has no Withdraw; Ask to unlink my APAAR opens the Correction form with [privacy.request.unlink_prefill].
- [ ] Who viewed your record shows Date and Who only; Who is a role phrase; no officer name, email, IP or other college appears; notice-link and verifier entries read as their phrases.
- [ ] An Access request downloads `export.json` at once; the file holds the APAAR masked and nothing about any other student.
- [ ] A Correction with empty details shows [privacy.request.details_required]; with details it appears as Open with "Waiting for a reply from AICTE", and later shows the officer's reply.
- [ ] At 390 px the sections stack and nothing scrolls sideways.

## AA. `/verify`, `/verify/[code]` and `/verify/d/[jws]`

- [ ] Public with no cookie; no nav, no search box and no list anywhere.
- [ ] The placeholder reads "e.g. K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF"; a code typed in lower case with spaces works; a code of the wrong length shows [verify.code_format] and sends nothing.
- [ ] Tab order is Scan, Code, Check, the proof text disclosure, What is Countersign?
- [ ] With BarcodeDetector, Scan opens the preview with [verify.scan_hint] and Stop camera, and scanning the wallet QR on a phone lands on `/verify/{code}`; without it, [verify.scan_unsupported] shows; refusing the camera shows [verify.camera_denied] and focuses the code box.
- [ ] VALID shows the badge word and icon, [verify.valid_sub], [verify.signature], "Revocation checked just now", the holder-bound line, and exactly the disclosed fields in the order sent, nothing the student did not tick.
- [ ] REVOKED, EXPIRED and INVALID each show their heading, sub line and Check another proof, and no fields.
- [ ] An unknown code shows [err.PRESENTATION_NOT_FOUND]; the 61st check in a minute shows [verify.rate_limited] with a countdown.
- [ ] Pasted proof text gives the same states, with [verify.pasted_note] on Valid.
- [ ] The degree QR from the print view verifies as Valid degree proof with its fields and [verify.degree_printed]; after revocation it reads Revoked.
- [ ] At 390 px nothing scrolls sideways, Check and Scan are full width, and a label sits above a value too long to fit beside it.

## AB. `/university/degrees` and the print view

- [ ] Degree print is a live nav item and the teaser is gone.
- [ ] Columns Graduate, APAAR / Provisional, Institution, Programme, Year of award, Degree proof; only affiliates' graduates; search by name or last four of APAAR; count, pager and [privacy.read_logged].
- [ ] Issue degree proof opens a dialog with [degree.issue_note] and [degree.issue_revocation_note]; closing returns focus to the row; success shows [degree.issued_toast] and the row gains Print degree insert and Download PDF.
- [ ] The print view shows the university, name, programme, institution, year of award, "APAAR XXXX XXXX 4417" (or the provisional id), and the QR with "Proof id" and "Scan to verify at ..." as text under it.
- [ ] Print preview has no nav, top bar, breadcrumbs, buttons, hint text or colour backgrounds; text is black on white; it fits one A4 page.
- [ ] Download PDF saves an insert with the same masked APAAR and a QR that verifies.
- [ ] A graduate without APAAR prints the provisional id, and the issue dialog shows [degree.provisional_note].

## AC. Case actions and history (`/aicte/cases/[flagId]`, `/ro/cases/[flagId]`)

- [ ] The read-only line is gone; the action bar shows exactly the buttons deck §6 lists for the role and status.
- [ ] Each sheet is a modal with focus on its note; an empty note shows [case.note_required] and sends nothing; Esc returns focus to the button that opened it.
- [ ] Request documents with a date moves the flag to Documents requested, shows [case.due_line], and Mailpit receives [email.docs_request.subject] for every registrar account of the college, naming no student and no officer.
- [ ] Confirm on an enrolment-level flag shows [case.confirm_revokes]; afterwards the student's proof reads Revoked in the wallet and at the verifier, and the enrolment's status is unchanged.
- [ ] As `ro.west@aicte.demo` on an Escalated flag only Add note shows, with [case.escalated_ro]; as the AICTE officer, Clear flag, Request documents, Confirm, Add note and Assign show.
- [ ] Reopen shows only for the AICTE officer on Cleared or Confirmed flags, and needs a note.
- [ ] Assign is a combobox that works by keyboard alone and lists only officers in scope; Assign to me works; the queue's Assignee column updates.
- [ ] History lists Flag opened, then one row per action with When, Who (name and role, or System), What, the status change, the due date, the note in quotes and the attachment links; a System row reads "Evidence updated after the decision" where the engines refreshed a decided flag.
- [ ] Downloading an attachment works for officers in scope and adds a Viewed entry on `/admin/audit`.
- [ ] Acting on a stale page shows [err.FLAG_TRANSITION_INVALID] and refreshes the status.
- [ ] No action button is red; a past due date reads [case.due_passed] in plain text.
- [ ] The queue has the Assignee column; Assigned to me, Unassigned and Response received set URL params that survive reload and send `assignee` and `response_received`; a responded flag carries the Response received chip.
- [ ] On a Student denied flag the officer sees the Comment from the student fact.

## AD. College response (`/college/flags/[flagId]`)

- [ ] Respond shows only while the flag is Documents requested; otherwise [flag.readonly_college].
- [ ] The request line names the officer's role, not their name, with the date, the note and the due date.
- [ ] An empty reply shows [college.respond_note_required] and focuses the field.
- [ ] The file input takes PDF, PNG and JPEG only; a .docx shows [college.respond_file_type], a 6 MB PDF [college.respond_file_size] and a fourth file [college.respond_too_many], all before any request.
- [ ] Each chosen file has a Remove button reachable by keyboard; the count reads "n of 3 files".
- [ ] A server 413 or 415 shows [err.ATTACHMENT_TOO_LARGE] or [err.ATTACHMENT_TYPE] and keeps the files.
- [ ] After sending: [college.respond_sent]; the history gains Responded with the file names; the status stays Documents requested; the officer's queue shows Response received.
- [ ] The registrar never sees the student's comment or another institution's name.

## AE. `/admin/audit`

- [ ] Only the AICTE officer can open it; other roles are redirected with the toast.
- [ ] Columns Entry, Time, Actor, Action, Entity, Entity id, Hash; actions read as deck §4 words (Viewed, not READ); ids and hashes show 8 characters with the full value on focus and hover.
- [ ] Entity, Action, Actor, Entity id and From entry set URL params that survive reload and send `entity_type`, `action`, `actor_id`, `entity_id` and `seq_from`.
- [ ] Verify chain reads "Chain intact, <n> entries" with en-IN grouping, announced in a live region.
- [ ] After `make audit-tamper SEQ=n`, Verify chain reads "Chain broken at entry n" with [audit.chain_broken_detail]; Show entry loads that page, marks the row with an icon and "Chain breaks here", scrolls to it and focuses it; `make demo-reset` brings back "Chain intact".
- [ ] Entries written by notice links, verifiers and the seed read "Public, notice link", "Public, verifier" and "Demo seed"; no student name or unmasked id appears.

## AF. `/admin/data-requests`

- [ ] Only the AICTE officer can open it; Data requests is in that nav.
- [ ] Correction and Erasure requests are listed, Open first, oldest first; Access requests never appear.
- [ ] The Student cell shows the name with the masked APAAR or provisional id; details wrap.
- [ ] Resolve opens a dialog; the reply is required; Done and Decline are a radio group.
- [ ] An Erasure shows [admin.requests.erasure_retention] and a reply prefilled with [admin.requests.erasure_reply].
- [ ] After resolving, the row shows the new status and date, and the student's Privacy page shows the reply.

## AG. Enrolment detail: Student check and Resend notice

- [ ] The Student row prints the api sentence verbatim ("Notice sent on <date>; no reply yet.", "Confirmed by the student on <date> (email).") with the Result word No reply yet, Notice not sent yet, No reply (expired), Countersigned or Not countersigned.
- [ ] The Student notice block shows one line per channel with its delivery word; a student with no DigiLocker account reads "Not delivered, <date> (no DigiLocker account)".
- [ ] Officers see the comment under a No; the registrar never does; the university sees no notice block.
- [ ] Resend notice shows for officers and the registrar, disabled with [resend.live_tip] while a notice is live; once every notice has expired it opens the confirm dialog and sends; a fourth resend in the year shows [err.RESEND_LIMIT].

## AH. Demo rehearsal (Week 3)

- [ ] Each role signs in from its login card.
- [ ] The ABC CSE Excess admission flag and the R. K. Sharma duplicate open from the case queue with their evidence.
- [ ] Ravi's notice opens from Mailpit; Yes; his wallet shows the Enrolment proof; sharing 3 fields gives a QR; `/verify/{code}` reads Valid with only those 3 fields.
- [ ] Another notice answered No raises Student denied (High), with the comment visible to the officer and hidden from the registrar.
- [ ] The officer requests documents, the registrar responds with a PDF, the officer downloads it and clears the flag; the history shows each step.
- [ ] The university issues a degree proof, prints the insert, and its QR verifies Valid.
- [ ] The AICTE officer verifies the audit chain: intact.
- [ ] The whole path runs without an error toast and with no full APAAR on any screen.
