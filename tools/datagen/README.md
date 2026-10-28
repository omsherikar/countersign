# datagen

Synthetic AICTE enrolment data with ground-truth labels for Countersign. Every name, APAAR
id, mobile number and address is generated; nothing comes from a real person.

```
uv run datagen generate --size small --seed 42 --out /data/generated   # 50 colleges, ~10k rows
uv run datagen generate --size full --seed 42 --out /data/generated    # 500 colleges, ~2 lakh rows
uv run datagen summary /data/generated
uv run pytest -q
```

`--no-scenarios` leaves out the named demo scenarios; `--no-xlsx` writes CSV uploads only;
`--perf 50000` also writes `perf/`, a one-college throughput dataset for `make eval`.
The same seed always writes the same bytes (except `generated_at` and timings in
`manifest.json` and `summary.json`). Sizes and planted-case counts live in `datagen.yaml`.

## Output

```
institutions.json        regions, states, universities, institutions with programmes, approvals
                         (with versions) and the autonomous flag
users.json               demo logins
column_mappings.json     the colleges that upload with their own headers, header -> template column
uploads/<aicte_id>_<year>.csv (+ .xlsx)          initial upload of every college but the overdue
uploads/<aicte_id>_<year>_update<n>.csv (+ .xlsx) withdrawals, transfers and late refills
ground_truth.json        every planted case, expected signal and expected record status
mockgov/apaar_registry.jsonl, counselling.jsonl, abc_credits.jsonl (with issuer), sii.jsonl
mockgov/admission_joinings.jsonl   the state admission authority's joinings
mockgov/digilocker_accounts.jsonl  synthetic accounts for the DigiLocker sign-in simulator
graduates.jsonl          2025-26 graduates for the university degree proof
notice_replies.jsonl     how each student answers the enrolment notice in the seeded demo
history.json             last year's first-year admissions per college
manifest.json            size, seed, counts, demo notices and accounts, sample card, uploads
summary.json             manifest plus columns, notes and timings
perf/                    only with --perf N (below)
```

The file contract is docs/API_CONTRACT.md section E, Addendum 2 (A2.24), A3.28 and A4.25; the
sections below describe what is new for A4.25. The steps that build it draw from random
streams of their own, so the rows a step does not touch keep every value; small mode runs in
under 10 seconds.

## notice_replies.jsonl

One line per row of each initial upload file (`uploads/<aicte_id>_<year>.csv`), files in name
order, rows in file order. Update files have no lines. A row the api would reject as an
in-file duplicate (DUPLICATE_IN_FILE) never becomes an enrolment and has no line.

```json
{"file":"uploads/1-ABC-0001_2026-27.csv","row_no":41,"reply":"NO","channel":"DIGILOCKER","comment":"I never joined this college.","reply_after_days":0}
```

| field | type | meaning |
|---|---|---|
| `file` | string | the upload file, as in `ground_truth.json` `rows[].file` |
| `row_no` | int | spreadsheet row (header is row 1), the api's `enrolments.source_row_no` |
| `reply` | `YES`, `NO`, `NONE` | the student's answer; `NONE` means no reply |
| `channel` | `DIGILOCKER`, `EMAIL` | the notice the student answers |
| `comment` | string or null | what the student wrote; only on some `NO` replies |
| `reply_after_days` | int | days between the notice and the reply, 0 to 12 |

Rules:

- The lines stand for answers given after DigiLocker sign-in (API_CONTRACT A4.13); `channel`
  is the notice the student answers.
- Every planted STUDENT_DENIED row (`will_deny: true` in ground truth) replies `NO`: on
  `DIGILOCKER` when the row has an APAAR the registry holds, otherwise by `EMAIL`. Three of
  them leave a comment; the sample card at ABC CSE (scenario `not_me`, "I never joined this
  college.") is always one of the three.
- About 70% of the clean rows reply `YES`, on a channel the student has (DigiLocker needs an
  APAAR the registry holds; every row has an email address). Clean means no planted case
  refers to the row, apart from CONSENT_REFUSED_NO_APAAR, and no update file withdraws or
  transfers it.
- Every other row is `NONE`: rows of other planted cases and of the record-status records
  (CLEAN_INDEPENDENT, SELF_ISSUED_ONLY, PROVISIONAL_UNCLAIMED), rows an update file withdraws
  or transfers, and the notices the live demo answers by hand. For `NONE`, `channel` is the
  channel the student would use and `reply_after_days` is 0; both carry no meaning.
- The live demo's notices are always `NONE`: Ravi Kumar Sharma (APAAR 123456784417, row 2 of
  ABC College), his duplicate row "R. K. Sharma", and one more clean, LINKED, counselled ABC
  CSE first-year. `manifest.json` lists the three under `demo_unanswered_notices` as
  `{role, file, row_no, name, apaar_id}` with roles `DEMO_STUDENT`,
  `DEMO_STUDENT_DUPLICATE` and `SECOND_DEMO_NOTICE`.
- `manifest.json` counts: `notice_replies`, `notice_replies_yes`, `notice_replies_no`,
  `notice_replies_none`.

## graduates.jsonl

Students who finished in 2025-26: one line per graduate, ordered by college (as in
`institutions.json`), programme and name. 40 graduates in small mode, 400 in full.

```json
{"institution_aicte_id":"1-ABC-0001","programme_code":"CSE","academic_year":"2025-26","year_of_study":4,"name":"...","dob":"2004-01-11","gender":"F","apaar_id":"229100823200","consent_status":"LINKED","provisional_id":null,"email":"...@example.com","mobile":"7410835961","nationality":"IN","year_of_award":2026,"admission_route":"COUNSELLING","category":"GENERAL","admission_date":"2022-07-22","status_date":"2026-07-14"}
```

| field | type | meaning |
|---|---|---|
| `institution_aicte_id` | string | the college, in `institutions.json` |
| `programme_code` | string | a PHYSICAL programme of that college with a 2025-26 approval |
| `academic_year` | string | always `2025-26` |
| `year_of_study` | int | the final year: the programme's `duration_years` (UG 4, BCA 3, B.Arch 5, PG 2, Diploma 3) |
| `name`, `dob`, `gender` | string | as on the admission register; `gender` is `M` or `F` |
| `apaar_id` | string or null | 12 digits when `consent_status` is `LINKED`, else null |
| `consent_status` | `LINKED`, `PENDING`, `REFUSED` | |
| `provisional_id` | string or null | `PRV-` and 8 base32 characters when there is no APAAR, else null |
| `email`, `mobile` | string | contact details, unused anywhere else in the data |
| `nationality` | string | always `IN` |
| `year_of_award` | int | always 2026 |
| `admission_route` | `COUNSELLING`, `MANAGEMENT` | how the graduate was admitted |
| `category` | `GENERAL`, `EWS`, `OBC`, `SC`, `ST`, `OTHER` | |
| `admission_date` | date | inside the cohort's admission window (from 1 July of its start year) |
| `status_date` | date | when the result was declared, 15 June to 31 July 2026 |

Rules:

- 60% of the graduates are at colleges affiliated to MSTU (the `coe@univ.demo` login):
  12 (small) or 60 (full) at ABC College of Engineering, the first four of them in CSE, the
  rest at other MSTU colleges. The others are spread over the three other universities with
  the most affiliated colleges.
- Three to five graduates have no APAAR (consent PENDING or REFUSED) and carry a provisional
  id instead: one at ABC outside CSE, the rest at other colleges.
- Graduates are new people. No graduate's APAAR id, mobile or email appears on the 2026-27
  roll (initial or update files). Every LINKED graduate's APAAR is appended to
  `mockgov/apaar_registry.jsonl` with the same name, date of birth and gender.
- The api seed imports them as students with enrolments of status GRADUATED in 2025-26:
  no seat, no upload batch, no checks and no flags, so they never count in 2026-27 figures.
- `manifest.json` counts: `graduates`.

## institutions.json: approval versions and autonomy

Every approval lists its versions in ascending order; `approved_intake` is the last one's, the
intake every cohort was admitted against.

```json
{"academic_year": "2026-27", "approved_intake": 120, "versions": [
  {"version": 1, "approved_intake": 90, "effective_from": "2026-03-15", "source": "AICTE EoA 2026-27"},
  {"version": 2, "approved_intake": 120, "effective_from": "2026-05-20", "source": "AICTE EoA 2026-27, revised"}]}
```

- Version 1 is effective from 15 March of the year's start ("AICTE EoA <year>"). A revised
  approval adds version 2 from 20 May ("AICTE EoA <year>, revised"), before admissions open,
  and its version 1 holds the earlier intake.
- ABC College of Engineering CSE 2026-27 goes from 90 to 120, so its 132 first-years still
  exceed it. About one approval in ten elsewhere (ABC and XYZ aside) is revised up one step of
  the intake ladder.
- The api seed imports the versions into `approval_versions` once migration 0004 declares that
  table (`services/api/app/seed/importer.py`).

Every institution has `autonomous` (bool, datagen only): about 30% of colleges
(`autonomous_share` in datagen.yaml), XYZ Institute of Technology and every deemed university
always, ABC College never. An autonomous college issues its own ABC credits.

## Upload columns: category eligibility

Every upload file (initial and update, CSV and XLSX) has three optional columns after
`admission_date` (A4.16), `yes` or `no`, blank when not reported. An update row repeats its
initial row's values. A read-only XLSX reader leaves out trailing empty cells; the api's reader
treats them as blank.

| column | `yes` on |
|---|---|
| `tfw_income_certified` | every legitimate TFW row: the family income certificate was reported |
| `nri_sponsored` | every legitimate NRI-route row: the student is an NRI or sponsored by one |
| `ciwg` | every INTERNATIONAL row of nationality `IN`: a child of an Indian worker in the Gulf, on a CIWG-reserved seat, with a Study in India record |

Planted against them (small mode): one ELIGIBILITY_BREACH per rule of A4.4, NRI_STATUS
(`nri_sponsored` no, MEDIUM), TFW_INCOME (`tfw_income_certified` no, MEDIUM) and
INTERNATIONAL_CIWG (an Indian national on an ordinary international seat with `ciwg` blank,
HIGH); two TFW_INCOME_NOT_REPORTED rows with the certificate blank (Seat pending, no case); two
CIWG_ADMISSION rows (not flagged).

## column_mappings.json

```json
{"1-XYZ-0002": {"Student Name": "name", "D.O.B.": "dob", "Course Code": "programme_code"}}
```

The colleges that upload with their own headers (three in small mode, XYZ Institute of
Technology among them), each mapping its headers to template columns. Their files, initial and
update, are written with those headers in the template's order. No such header normalises
(trimmed, lower case, spaces and hyphens as underscores) to a template column, two never
normalise alike, and with the mapping every required column is reached. The seed saves each
mapping before the college's first upload.

## mockgov/abc_credits.jsonl: issuer

Every credit record carries `issuer` and `issuer_name`: the affiliating university's code and
name, or, for an autonomous college (or a deemed university), the college's AICTE permanent id
and name. Credits a college issued for itself are not independent evidence (D38).

## mockgov/admission_joinings.jsonl

The state admission authority's joinings, one state's format simulated for every state
(mockgov `/admission-authority/*`), sorted by college, academic year, programme and date.

```json
{"state":"MH","academic_year":"2026-27","name":"Ravi Kumar Sharma","dob":"2007-03-21","roll_no":"MHCET-2026-004512","institution_code":"1-ABC-0001","programme":"CSE","joined_on":"2026-08-04","round":1,"route":"COUNSELLING","category":"GENERAL","apaar_id":"123456784417"}
```

| field | meaning |
|---|---|
| `academic_year` | the year the student joined this programme: the cohort's year, and for a lateral entrant the year it entered year 2 |
| `roll_no` | counselled, TFW and lateral admissions: the entrance-exam roll number of `counselling.jsonl`; management, NRI and spot admissions: the authority's number `<STATE>AA-<year>-<nnnnnn>` |
| `name`, `dob`, `programme`, `route`, `category` | as uploaded |
| `institution_code` | the college's AICTE permanent id |
| `joined_on` | 0 to 6 days after the admission, never after the year's reporting deadline, except 3 clean first-years (25 full) who joined after it and refills admitted after it |
| `round` | the counselling round, null for other routes |
| `apaar_id` | the APAAR when the registry holds it under this student, else null |

Who has a line: every uploaded student (refills included) except international admissions
(Study in India holds those), renamed duplicate rows (their person already has a line; such a
row may still match it by name) and the rows planted as NOT_IN_JOINING_RECORD; plus the
students colleges left out of their upload and every student of an overdue college. Ring
members have lines. One state (not ABC's or XYZ's) has published nothing for 2025-26, so its
second-years have no line and their Joining record reads pending. The reporting deadline is
`rules.yaml` `reporting.deadline` (a date, or a mapping by year), else datagen.yaml's
`joining.reporting_deadline`, else 30 September of the year's start.

Planted: six NOT_IN_JOINING_RECORD rows (MEDIUM), the sample card among them; three colleges,
XYZ among them, that left 2 to 6 joined first-years out of their upload (MISSING_FROM_UPLOAD).
`manifest.json` counts `admission_joinings`, `admission_joinings_late` and
`missing_from_upload`.

## mockgov/digilocker_accounts.jsonl

```json
{"digilocker_id":"DL-RAVI-4417","name":"Ravi Kumar Sharma","dob":"2007-03-21","gender":"M","apaar_id":"123456784417"}
```

- The demo accounts (manifest `demo_digilocker_accounts`) come first, Ravi Kumar Sharma at the
  top, so the sign-in page lists them first.
- Every APAAR in `apaar_registry.jsonl` has exactly one account with the registry's name, date
  of birth and gender.
- Every other person on the roll, left out of an upload or graduated has one account with
  `apaar_id` null under the uploaded name: consent refused or pending, an uploaded APAAR that is
  malformed or unknown, or the uploaded side of a NAME_MISMATCH. Rows describing one person (a
  renamed duplicate, one student at two colleges) share an account. International students
  have none.
- `digilocker_id` is `DL-` and two groups of four characters; Ravi Kumar Sharma's is fixed.

## history.json

Last year's first-year admissions per college and programme (colleges in `institutions.json`
order): a physical programme's second-years still on the roll (lateral entrants aside) divided
by a retention of 0.90 to 0.98, or this year's first-years times 0.9 to 1.1 for an open or
online programme. The anomaly model's own `admission_growth` (ENGINES 17.11) reads the roll's
second-years; this file is the like-for-like reference the planted growth is measured against.

## ground_truth.json

The record shape is unchanged; a row may appear in more than one record (the sample card is
both STUDENT_DENIED and NOT_IN_JOINING_RECORD). Rows named by no record are the known-clean set.
New and changed `anomaly_type` values (counts for small mode):

| anomaly_type | expected_flag | severity | small | rows | extra keys |
|---|---|---|---|---|---|
| NOT_IN_JOINING_RECORD | NOT_IN_JOINING_RECORD | MEDIUM | 6 | the uploaded row | `academic_year`, `reporting_deadline`; the sample card also `scenario: "sample_card"`, `expected_rows`, `expected_record_status: "DISPUTED"` |
| MISSING_FROM_UPLOAD | MISSING_FROM_UPLOAD | MEDIUM | 3, plus 1 per overdue college | none | `academic_year`, `missing` (a count), `missing_students`, `joined`, `uploaded_and_joined`, `completeness_pct`; XYZ's `scenario: "xyz_missing"`, an overdue college's `overdue: true` |
| ELIGIBILITY_BREACH | ELIGIBILITY_BREACH | MEDIUM, HIGH for INTERNATIONAL_CIWG | 3 | the row | `eligibility_rule`, `marker`, `source` |
| TFW_INCOME_NOT_REPORTED | null (Seat pending) | null | 2 | the TFW row | `expected_check` |
| CIWG_ADMISSION | null (not flagged) | null | 2 | the CIWG row | `seat_type`, `source` |
| GHOST_RING | null, `expected_signal: "GHOST_RING"` | null | 3 | the members | as before |
| ANOMALY | null, `expected_signal: "ANOMALY"` | null | 2 | none | `features`, `values`, `peer_medians`, `first_years`, `academic_year`; growth also `admitted_last_year`, `growth_like_for_like`, `added_rows` |
| LATE_UPLOAD | null, `expected_deadline_state: "LATE"` | null | 2 | none | `academic_year`, `deadline` |
| OVERDUE_UPLOAD | null, `expected_deadline_state: "OVERDUE"` | null | 1 | none | `academic_year`, `deadline` |
| CLEAN_INDEPENDENT | null, `expected_record_status: "COUNTERSIGNED"` | null | 5 | the row | `independent_row` |
| SELF_ISSUED_ONLY | null, `expected_record_status: "AWAITING_EVIDENCE"` | null | 3 | the second-year | `expected_rows`, `unpublished` |
| PROVISIONAL_UNCLAIMED | null, `expected_record_status: "AWAITING_EVIDENCE"` | null | 1 | the row | `expected_record_status_after_claim: "COUNTERSIGNED"` |

- ANOMALY `features` are the model's (ENGINES 17.11): `["admission_growth"]` for the college
  that admits extra first-years into its free regular seats until it has about three times
  last year's admissions, `["management_share", "nri_share"]` for the college whose counselled
  and spot first-years move to management and whose NRI seats fill up. Both stay inside every
  seat pool. Colleges with a planted EXCESS_ADMISSION also stand out on growth and management
  share, and the ring colleges on contact sharing.
- CLEAN_INDEPENDENT, SELF_ISSUED_ONLY and PROVISIONAL_UNCLAIMED rows answer no notice (`NONE`).
  SELF_ISSUED_ONLY second-years are at an autonomous college in the state with no 2025-26
  joinings, so their only confirmed enrolment row is the college's own credits.
- An overdue college carries no other record and sends no file; its students still have
  registry entries, joining lines and accounts.

## manifest.json

New keys:

- `reporting_deadline`: `{"2026-27": "2026-09-30"}`.
- `uploads`: `[{"file", "aicte_id", "academic_year", "submitted_at"}]` for every initial file
  (name order) and update file; the seed sets each batch's upload time to `submitted_at`.
  Initial files arrive 16 to 29 September, the late colleges' in October, update files 21 to
  27 October, after every date they carry.
- `late_colleges` and `overdue_colleges`: AICTE ids (2 and 1 in small mode).
- `demo_digilocker_accounts`: `[{"role", "digilocker_id", "name", "dob", "apaar_id", "file",
  "row_no"}]` with roles `DEMO_STUDENT` (Ravi Kumar Sharma), `SECOND_DEMO_NOTICE`,
  `PROVISIONAL_CLAIM` (a refused-consent ABC College CSE first-year with an email and a joining
  line, seated, who becomes countersigned after claiming), `SOMEONE_ELSE` (a linked first-year
  at another college, whose account matches no notice the demo opens) and `SAMPLE_CARD`.
- `sample_card`: `{"file", "row_no"}`, the deck's sample record: an ABC College CSE
  2026-27 first-year with a linked APAAR, a seat under approval v2, no joining line (the demo
  runs after the 30 Sep deadline, so Joining record reads contradicted), credits not yet due and
  a planted No; the record reads Disputed. Null without the named scenarios.
- `perf` (only with `--perf N`): `{"institutions_file", "file", "rows"}`.
- `counts` gains `admission_joinings`, `admission_joinings_late`, `missing_from_upload`,
  `digilocker_accounts` and `history_institutions`; `students` counts the rows of the files
  written (an overdue college's students are not among them).

## perf/ (`--perf N`)

`perf/institutions.json` (the main file's regions, states and universities and one college,
"Countersign Throughput Test College", `9-PERF-0001`, Maharashtra, whose ten B.Tech
programmes have 2025-26 and 2026-27 approvals that seat every row),
`perf/9-PERF-0001_2026-27.csv` (exactly N rows, every one legitimate: a linked APAAR the
registry holds, a regular-pool route, a seat, a joining line, credits for the 30% who are
second-years, no shared contact) and `perf/mockgov/apaar_registry.jsonl`,
`admission_joinings.jsonl`, `abc_credits.jsonl` and `digilocker_accounts.jsonl`. Nothing in
`perf/` is loaded by `make seed`; its ids never repeat the main dataset's. 50,000 rows take
about four seconds.
