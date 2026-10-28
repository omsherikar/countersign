# datagen

Synthetic AICTE enrolment data with ground-truth labels for Countersign. Every name, APAAR
id, mobile number and address is generated; nothing comes from a real person.

```
uv run datagen generate --size small --seed 42 --out /data/generated   # 50 colleges, ~10k rows
uv run datagen generate --size full --seed 42 --out /data/generated    # 500 colleges, ~2 lakh rows
uv run datagen summary /data/generated
uv run pytest -q
```

`--no-scenarios` leaves out the named demo scenarios; `--no-xlsx` writes CSV uploads only.
The same seed always writes the same bytes (except `generated_at` and timings in
`manifest.json` and `summary.json`). Sizes and planted-case counts live in `datagen.yaml`.

## Output

```
institutions.json        regions, states, universities, institutions with programmes, approvals
                         (with versions) and the autonomous flag
users.json               demo logins
uploads/<aicte_id>_<year>.csv (+ .xlsx)          initial upload of every college
uploads/<aicte_id>_<year>_update<n>.csv (+ .xlsx) withdrawals, transfers and late refills
ground_truth.json        every planted case and expected signal, with the upload rows it refers to
mockgov/apaar_registry.jsonl, counselling.jsonl, abc_credits.jsonl (with issuer), sii.jsonl
mockgov/joining_records.jsonl      the state admission authority's joining records
mockgov/digilocker_accounts.jsonl  synthetic accounts for the DigiLocker sign-in simulator
graduates.jsonl          2025-26 graduates for the university degree proof
notice_replies.jsonl     how each student answers the enrolment notice in the seeded demo
history.json             last year's first-year admissions per college, for the anomaly model
manifest.json            size, seed, counts, demo_unanswered_notices, deck_sample
summary.json             manifest plus columns, notes and timings
```

The file contract for everything above `graduates.jsonl` is docs/API_CONTRACT.md section E
and Addendum 2 (A2.24). The files and fields described below are new since then. Every step
added after the Week 3 generation draws from a random stream of its own, so the rows it does
not touch keep every value; small mode still runs in under 10 seconds.

## notice_replies.jsonl

One line per row of each initial upload file (`uploads/<aicte_id>_<year>.csv`), files in name
order, rows in file order. Update files have no lines. A row the api would reject as an
in-file duplicate (DUPLICATE_IN_FILE) never becomes an enrolment and has no line.

```json
{"file":"uploads/1-ABC-0001_2026-27.csv","row_no":41,"reply":"NO","channel":"DIGILOCKER_SIGNIN","comment":"I never joined this college.","reply_after_days":3,"claim_provisional_id":false,"digilocker_id":"DL-7K2M-9QRT"}
```

| field | type | meaning |
|---|---|---|
| `file` | string | the upload file, as in `ground_truth.json` `rows[].file` |
| `row_no` | int | spreadsheet row (header is row 1), the api's `enrolments.source_row_no` |
| `reply` | `YES`, `NO`, `NONE` | the student's answer; `NONE` means no reply |
| `channel` | `DIGILOCKER_SIGNIN` | always: an answer counts only after DigiLocker sign-in (D37) |
| `comment` | string or null | what the student wrote; only on some `NO` replies |
| `reply_after_days` | int | days between the notice and the reply, 0 to 12 |
| `claim_provisional_id` | bool | the student has no APAAR and claims the record with the provisional id the college gave them before answering |
| `digilocker_id` | string or null | the account in `mockgov/digilocker_accounts.jsonl` that signs in; null for an international student, who has none |

Rules:

- Every planted STUDENT_DENIED row (`will_deny: true` in ground truth) replies `NO`, signed
  in with the APAAR the notice is about. Three of them leave a comment; the deck sample at
  ABC CSE (scenario `not_me`, "I never joined this college.") is always one of the three.
- A few refused-consent students (4 small, 30 full; `digilocker.provisional_claims` in
  datagen.yaml), the planted CONSENT_REFUSED_NO_APAAR rows first, reply `YES` with
  `claim_provisional_id: true`. Their DigiLocker account has no APAAR and the same name and
  date of birth as the row.
- About 70% of the clean rows whose student signs in with the row's own APAAR (12 digits,
  LINKED, the registry holds it under that name) reply `YES`. Clean means no planted case
  refers to the row, apart from CONSENT_REFUSED_NO_APAAR, and no update file withdraws or
  transfers it.
- Every other row is `NONE`: rows of other planted cases, rows an update file withdraws or
  transfers, students without an APAAR who do not claim, international students, and the
  notices the live demo answers by hand. `NONE` lines carry `reply_after_days` 0 and still
  name the account that would sign in.
- The live demo's notices are always `NONE`: Ravi Kumar Sharma (APAAR 123456784417, row 2 of
  ABC College, DigiLocker id `DL-RAVI-4417`), his duplicate row "R. K. Sharma", and one more
  clean, LINKED, counselled ABC CSE first-year. `manifest.json` lists the three under
  `demo_unanswered_notices` as `{role, file, row_no, name, apaar_id}` with roles
  `DEMO_STUDENT`, `DEMO_STUDENT_DUPLICATE` and `SECOND_DEMO_NOTICE`.
- `manifest.json` counts: `notice_replies`, `notice_replies_yes`, `notice_replies_no`,
  `notice_replies_none`, `notice_replies_claims`.

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

## Upload columns: category eligibility

Every upload file (initial and update, CSV and XLSX) has three optional columns after
`admission_date`, for the upload engine's eligibility rules (D41). Blank means not reported.
An update row repeats its initial row's values.

| column | values | on which rows |
|---|---|---|
| `tfw_income_certified` | `yes` or blank | `yes` on every TFW row: the family income certificate the tuition fee waiver needs was reported. One planted TFW row is blank (TFW_INCOME_NOT_REPORTED) |
| `nri_sponsored` | `NRI`, `NRI_SPONSORED`, `NO` or blank | on NRI-route rows: `NRI` (the student is a non-resident Indian, about 70%) or `NRI_SPONSORED` (a ward sponsored by an NRI). One planted NRI-route row says `NO`: neither (ELIGIBILITY_BREACH). Blank on every other route |
| `ciwg` | `yes` or blank | `yes` on the rows of children of Indian workers in the Gulf: INTERNATIONAL route, nationality `IN`, consent `INTERNATIONAL`, a passport and a Study in India record; they may take the CIWG-reserved third of the international seats |

A read-only XLSX reader leaves out trailing empty cells; the api's reader treats a short row's
missing cells as blank.

## institutions.json: approval versions and autonomy

Every approval carries its versions; `approved_intake` is the current (latest) version's.

```json
{"academic_year": "2026-27", "approved_intake": 90, "versions": [
  {"version": 1, "approved_intake": 60, "effective_from": "2026-05-15", "source": "AICTE approval 2026-27 (sample approval data)"},
  {"version": 2, "approved_intake": 90, "effective_from": "2026-10-21", "source": "AICTE revised approval 2026-27, intake 60 to 90 (sample approval data)"}]}
```

- Version 1 of every approval: the generated intake, effective from 15 May of the year's
  start, source "AICTE approval <year> (sample approval data)".
- Only ABC College of Engineering IT 2026-27 has a version 2: the intake rises from 60 to 90
  from 21 Oct 2026, after its first-years (exactly 60, the late refill programme) were
  admitted against version 1. Seat arithmetic for a cohort uses the version in force on the
  year's admission cutoff.
- The api seed imports the versions into `approval_versions` once migration 0004 declares
  that table (`services/api/app/seed/importer.py`).

Every institution has `autonomous` (bool): about 30% of colleges (`autonomous_share` in
datagen.yaml), XYZ Institute of Technology and every deemed university always, ABC College
never. An autonomous college issues its own ABC credits.

## mockgov/abc_credits.jsonl: issuer

Every credit record carries `issuer: {type, code, name}`: `{"type": "INSTITUTION", "code":
<aicte_id>, "name": <college>}` when the student's college is autonomous (or a deemed
university), else `{"type": "UNIVERSITY", "code": <university_code>, "name": <university>}`
for its affiliating university. Credits a college issued for itself are not independent
evidence of the enrolment (D38).

## mockgov/joining_records.jsonl

The state admission authority's record of who reported and joined, one state's format
simulated for every state (mockgov `/admission-authority/*`). Sorted by college, academic
year, programme and roll number.

```json
{"state":"MH","academic_year":"2026-27","roll_no":"MHCET-2026-004512","name":"Ravi Kumar Sharma","dob":"2007-03-21","gender":"M","institution_code":"1-ABC-0001","programme":"CSE","joined_on":"2026-08-04","round":1,"route":"COUNSELLING","category":"GENERAL"}
```

| field | meaning |
|---|---|
| `state` | the college's state |
| `academic_year` | the academic year the row's `admission_date` falls in: `2026-27` for this year's first-years, `2025-26` for second-years and for year-2 lateral entrants (whose admission is dated in their cohort's window, as their counselling allotment is filed) |
| `roll_no` | counselled, TFW and lateral admissions: the entrance-exam roll number of `counselling.jsonl`; management, NRI and spot admissions: the authority's number `<STATE>AA-<year>-<nnnnnn>`. Unique |
| `name`, `dob`, `gender` | as uploaded |
| `institution_code` | the college's AICTE permanent id |
| `programme`, `route`, `category` | as uploaded |
| `joined_on` | 0 to 6 days after the admission, never after the year's reporting deadline; except 3 clean first-years (25 full) who joined 1 to 12 days after it and late refills admitted after it |
| `round` | the counselling round, null for routes without one |

Who has a record: every row of every upload file (refills included) except international
admissions (Study in India holds those), renamed duplicate rows (their person already has a
record; a renamed row may still match it by name, else its joining record reads not found),
and the rows planted as never joined; plus the students colleges left out of their upload.
Management, NRI and spot admissions are included. The reporting deadline is `rules.yaml`
`reporting.deadline` when present (a date, or a mapping by academic year), else
`joining.reporting_deadline` in datagen.yaml (`2026-09-30` for 2026-27), else 30 September
of the year's start.

`manifest.json` counts: `joining_records`, `joining_records_late` (joined after the
deadline), `missing_from_upload` (students left out).

## mockgov/digilocker_accounts.jsonl

Synthetic accounts for the DigiLocker sign-in simulator (mockgov `/digilocker/oauth/*`).

```json
{"digilocker_id":"DL-RAVI-4417","name":"Ravi Kumar Sharma","dob":"2007-03-21","gender":"M","apaar_id":"123456784417"}
```

- Every APAAR in `apaar_registry.jsonl` has exactly one account with that APAAR and the
  registry's name, date of birth and gender (students, refills, students left out of an
  upload, graduates, and the person behind a NAME_MISMATCH APAAR).
- Every other person has one account with `apaar_id: null` under the uploaded name: consent
  refused or pending, an uploaded APAAR that is malformed or unknown, or the uploaded side of
  a NAME_MISMATCH; graduates without an APAAR too. Rows describing one person (a renamed
  duplicate, one student at two colleges) share an account.
- International students have no account.
- `digilocker_id` is `DL-` and two groups of four characters; Ravi Kumar Sharma's is fixed.
- `manifest.json` counts: `digilocker_accounts`.

## history.json

Last year's first-year admissions per college and programme, the denominator of the anomaly
model's year-over-year feature (D45). Colleges in `institutions.json` order.

```json
{"academic_year": "2025-26", "note": "Synthetic. ...", "institutions": [
  {"institution_aicte_id": "1-ABC-0001", "admitted": 226, "programmes": {"CSE": 117, "IT": 14}}]}
```

`programmes` lists every programme with an approval for that year: for a physical programme,
its second-years still on the roll (lateral entrants aside) divided by a retention of 0.90 to
0.98; for an open or online programme, this year's first-years times 0.9 to 1.1. Compare like
for like: this year's first-years in the programmes listed with admissions above zero, over
those admissions (a programme new this year is not growth).

## ground_truth.json additions

The record shape is unchanged. New `anomaly_type` values:

| anomaly_type | expected_flag | severity | small | rows | extra keys |
|---|---|---|---|---|---|
| NOT_IN_JOINING_RECORD | NOT_IN_JOINING_RECORD | MEDIUM | 6 | the uploaded row | `academic_year`, `reporting_deadline`; the deck sample also `scenario: "deck_sample"`, `expected_rows`, `expected_record_status` |
| MISSING_FROM_UPLOAD | MISSING_FROM_UPLOAD | MEDIUM | 3 (one per college) | none | `academic_year`, `missing: [{roll_no, name, dob, programme_code, academic_year, joined_on, route, apaar_id}]`, `joined`, `uploaded_and_joined`, `completeness`; XYZ's has `scenario: "xyz_missing"` |
| ELIGIBILITY_BREACH | ELIGIBILITY_BREACH | MEDIUM | 1 | the NRI-route row | `seat_type: "NRI"`, `marker`, `source` |
| TFW_INCOME_NOT_REPORTED | null (SEAT pending, no case) | null | 1 | the TFW row | `seat_type`, `expected_check: {"type": "SEAT", "status": "PENDING"}` |
| CIWG_ADMISSION | null (must not be flagged) | null | 2 | the CIWG row | `seat_type`, `source` |
| ANOMALY | null (a signal, not a case) | null | 2 | none | `expected_signal: "ANOMALY"`, `feature`, `value`, `peer_median`, `first_years`, `academic_year`; growth also `admitted_last_year`, `added_rows` |

- Every GHOST_RING record gains `expected_signal: "GHOST_RING"`; the named ring (40 students
  across 3 colleges sharing contacts) stays as it was.
- ANOMALY `feature` is `admission_growth` (like-for-like first-years over last year's
  admissions; the planted college admits extra first-years into free regular seats until it
  is at 3 times, peers near 1) or `nri_management_share` (NRI and management share of
  first-years; the planted college moves its counselled and spot first-years to management
  and fills its NRI seats, about 3 times the peer median). Both stay inside every seat pool.
  Colleges with a planted EXCESS_ADMISSION also stand out on both features; the ring colleges
  stand out on contact sharing.
- Institution-level records (MISSING_FROM_UPLOAD, ANOMALY) have `rows: []` and
  `student_refs: []`.
- A row can carry more than one record: the deck sample is both STUDENT_DENIED and
  NOT_IN_JOINING_RECORD.

## manifest.json: deck_sample

The deck's sample record (DECISIONS D49), null without the named scenarios: an ABC College
CSE first-year whose APAAR verifies and whose seat fits, with no joining record, who answers
No through DigiLocker sign-in.

```json
{"file": "uploads/1-ABC-0001_2026-27.csv", "row_no": 41, "name": "...", "apaar_id": "...",
 "institution_aicte_id": "1-ABC-0001", "programme_code": "CSE", "year_of_study": 1,
 "reply": "NO", "channel": "DIGILOCKER_SIGNIN", "comment": "I never joined this college.",
 "expected_rows": {"IDENTITY": "CONFIRMED", "SEAT": "CONFIRMED", "ADMISSION": "CONTRADICTED",
                   "STUDYING": "NOT_YET_DUE", "STUDENT": "CONTRADICTED"},
 "expected_record_status": "DISPUTED"}
```

The joining record reads Contradicted because the demo runs after the 30 Sep 2026 reporting
deadline.
