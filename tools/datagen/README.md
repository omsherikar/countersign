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
institutions.json        regions, states, universities, institutions with programmes and approvals
users.json               demo logins
uploads/<aicte_id>_<year>.csv (+ .xlsx)          initial upload of every college
uploads/<aicte_id>_<year>_update<n>.csv (+ .xlsx) withdrawals, transfers and late refills
ground_truth.json        every planted case, with the upload rows it refers to
mockgov/*.jsonl          APAAR registry, counselling allotments, ABC credits, Study in India
graduates.jsonl          2025-26 graduates for the university degree proof
notice_replies.jsonl     how each student answers the enrolment notice in the seeded demo
manifest.json            size, seed, counts, demo_unanswered_notices
summary.json             manifest plus columns, notes and timings
```

The file contract for everything above `graduates.jsonl` is docs/API_CONTRACT.md section E
and Addendum 2 (A2.24). The two files below are new.

## notice_replies.jsonl

One line per row of each initial upload file (`uploads/<aicte_id>_<year>.csv`), files in name
order, rows in file order. Update files have no lines. A row the api would reject as an
in-file duplicate (DUPLICATE_IN_FILE) never becomes an enrolment and has no line.

```json
{"file":"uploads/1-ABC-0001_2026-27.csv","row_no":41,"reply":"NO","channel":"DIGILOCKER","comment":"I never applied to this college.","reply_after_days":0}
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

- Every planted STUDENT_DENIED row (`will_deny: true` in ground truth) replies `NO`: on
  `DIGILOCKER` when the row has an APAAR the registry holds, otherwise by `EMAIL`. Three of
  them leave a comment; the named "not me" scenario at ABC CSE is always one of the three.
- About 70% of the clean rows reply `YES`, on a channel the student has (DigiLocker needs an
  APAAR the registry holds; every row has an email address). Clean means no planted case
  refers to the row, apart from CONSENT_REFUSED_NO_APAAR, and no update file withdraws or
  transfers it.
- Every other row is `NONE`: rows of other planted cases, rows an update file withdraws or
  transfers, and the notices the live demo answers by hand. For `NONE`, `channel` is the
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
