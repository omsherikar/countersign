# Review checklist

One line per check, pass or fail. Run against the built pages with the seeded data (`make up && make datagen && make seed`), signed in as each demo user. Record the result per page in a table under each section when reviewing. Copy ids refer to `05-copy-deck.md`.

Sections A to K are the Week 1 pages. Sections L to U are the Week 2 pages (`04-pages-later.md` W2-1 to W2-9, API_CONTRACT Addendum 2); from Week 2 the seed also loads the update files, and where a Week 1 line and a Week 2 line disagree (labels, the Countersigned tile, the default sort, nav items) the Week 2 line wins.

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

