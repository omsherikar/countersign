# Countersign

**Every enrolment, countersigned.**

SIH 2026, PS 26263 (AICTE). An APAAR-ID-based student data management and verification platform for AICTE-approved institutions.

A college's student upload is a *claim*. Five independent sources then countersign each record: Identity, Admission, Seat, Studying, Student. Officers see which check failed and decide. Nothing is auto-rejected.

## Status

Week 2 of 4 is merged (2026-10-28). A college's upload now runs through the engine: parsing and validation with row warnings, name matching (initials, honorifics, spelling folds, Devanagari), the Seat Ledger, the five checks with a countersign score, duplicate detection within a file, within a college and across colleges, and flags with plain-English evidence. The web app shows all of it: upload with progress and row errors, the countersign strip, enrolment detail with recheck, flags and the officers' read-only case queue, and dashboards ranked by open flags. `make seed` sends every generated upload through the same `run_batch` the upload page uses. Week 2 was verified end to end on a native stack (local Postgres, Redis, mockgov, api, Celery worker and web) because Docker Desktop would not start on the build machine: the small seed (53 files, 10,633 rows) runs in 100 to 120 s, all 76 planted anomalies are caught with the expected severity, no flag is unexplained and none of the 20 refused-consent controls is flagged. Tests: api 306, mockgov 94, datagen 81; the web app lints, typechecks and builds clean. Still open: the compose re-run once Docker Desktop is repaired, CI (GitHub has not started a job because of an account billing problem, not a code failure) and the 50,000-rows-under-2-minutes target for Week 4. Week 3 is next: the student loop, officer actions on flags and student-held credentials. The task boards, the end-of-week verification checklists with their evidence, the Week 2 results and a dated changelog are in [docs/PROGRESS.md](docs/PROGRESS.md); the reasons behind each choice are in `docs/DECISIONS.md` (D14 to D22 for Week 2).

## Run it

```
cp .env.example .env
make up          # postgres, redis, mailpit, api, worker, mockgov, web
make datagen     # synthetic data, small mode (SIZE=full for 500 colleges)
make seed        # mockgov registries, then every upload through the engine (about 2 minutes, small)
make test
```

| Service | URL |
|---|---|
| Web | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| mockgov docs | http://localhost:8001/docs |
| Mailpit | http://localhost:8025 |

## Week 1: run it

```
cp .env.example .env     # then replace PII_FERNET_KEY with a real Fernet key (see the comment in the file)
make up                  # postgres, redis, mailpit, api, worker, mockgov, web
make datagen             # 50 colleges, ~10k students, planted anomalies with ground truth (SIZE=full for 500 / 2 lakh)
make seed                # api importer + mockgov registries, ~40 s in Week 1 (about 2 minutes from Week 2)
make test                # api, mockgov and datagen suites inside compose
make demo-reset          # wipe both databases and reseed; safe to run repeatedly
```

Demo logins (password for all: `Countersign!2026`): `admin@aicte.demo` (AICTE), `ro.west@aicte.demo` and `ro.south@aicte.demo` (regional offices), `registrar@abc.edu.demo` and `registrar@xyz.edu.demo` (colleges), `student@demo` (Ravi Kumar Sharma), `coe@univ.demo` (university).

### Week 1 acceptance, by hand

1. `curl localhost:8000/healthz` and `curl localhost:8001/healthz` both return `status: ok`.
2. Sign in as AICTE admin: national KPIs, state grid, institutions table. Open ABC College of Engineering: CSE 2026-27 shows 120 approved and pools 114 regular, 6 NRI, 6 TFW, 12 lateral, 18 international.
3. Sign in as `ro.west@aicte.demo`: only the Western region's institutions are visible. As `registrar@abc.edu.demo`: only ABC College; requesting another college's id returns 404.
4. Sign in as `student@demo`: own profile with the masked APAAR `XXXX XXXX 4417`; `/institutions` returns 403 for this role.
5. Admin system page (or `GET /admin/adapters/ping`): all five sources OK. Post `{"source":"apaar","down":true}` to `/admin/chaos`; ping now shows APAAR UNAVAILABLE and the others OK. Reset chaos.
6. `GET /admin/audit/verify` returns `ok: true` after seeding.
7. `make demo-reset` twice in a row gives identical counts.

A scripted version of steps 1 to 7 against the API lives in `docs/ux/06-review-checklist.md` (UI) and ran clean on 2026-10-28 (api 64, mockgov 92, datagen 45 tests passing).

### Known gaps carried into Week 2

- Closed in Week 2: no seats were assigned, so every enrolment showed as unseated until the Seat Ledger landed. Admitted counts already follow cohorts, so ABC College CSE shows 132 first-years against 120 approved; the Seat Ledger turns the 12 over intake into an EXCESS_ADMISSION flag with evidence.
- The TFW "filled at least 50% last year" condition is not evaluated; the pool is always built.
- Audit entries for a seed import are per batch, not per row.

## Week 2: run it

The commands are the same as Week 1; the seed now does the real work.

```
make up                  # postgres, redis, mailpit, api, worker (solo pool), mockgov, web
make datagen             # small mode also writes update files (withdrawals, transfers, refills after the cutoff) and Week 2 ground truth
make seed                # mockgov registries first, then every upload file through the engine: about 2 minutes for small
make test                # api 306, mockgov 94, datagen 81
```

After the seed every enrolment carries its five checks and a score, seats are assigned from the pools, and flags are open with evidence. As `admin@aicte.demo`, open ABC College of Engineering: CSE 2026-27 shows 120 approved, 132 admitted, 120 seated and 12 without a seat, with one Excess admission flag: "132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat." The "R. K. Sharma" row is flagged as a duplicate of Ravi Kumar Sharma, and two refills after the 15 Sep cutoff raise Late refill.

Week 2 was verified on a native stack because Docker Desktop would not start on the build machine; the compose path above is unchanged apart from the worker's solo pool, and needs a re-run once Docker Desktop is repaired.

### Try an upload as the registrar

1. Sign in as `registrar@abc.edu.demo` and open Upload (`/college/upload`).
2. Download the CSV template and fill in a few rows. Required columns: `name`, `dob`, `programme_code`, `year_of_study`, `admission_route`, `category`; `status`, `status_date` and `admission_date` are optional. Give one row a malformed APAAR (11 digits, say).
3. Pick the academic year, tick the declaration and send. The batch page moves through Queued, Validating, Processing and Done, then shows the rows accepted, the seats assigned and the flags raised. The malformed APAAR shows as a row warning with its value masked; `errors.csv` downloads the list.
4. Open Enrolments for the countersign strip on the new rows, and Flags for anything the upload raised.

### See an outage stay pending

1. As `admin@aicte.demo`, open System (`/admin/system`). Under Chaos, pick APAAR, tick Down and Apply (or `curl -X POST localhost:8001/admin/chaos -H 'content-type: application/json' -d '{"source":"apaar","down":true}'`).
2. As the ABC registrar, upload a file with valid APAARs. On a new enrolment, Identity shows Pending ("Awaiting source") and no flag is raised: an outage is never a fail.
3. Press Recheck pending checks on that enrolment while APAAR is still down: Identity stays Pending.
4. Back on System, press Reset chaos, then Recheck pending checks again: Identity turns Pass and the score goes up by one (2 of 4 to 3 of 4 in the verification run).

### Known gaps carried into Week 3

- The STUDENT check is pending for everyone until the Week 3 student loop sends the notice, so the countersigned share reads 0% (the share where no source disagrees reads 99% on the small seed).
- Flags are read-only; officer actions arrive in Week 3.
- About 11 ms per row with live checks against mockgov, so 50,000 rows take roughly 8 to 10 minutes; the Week 4 target is under 2 minutes.
- The TFW pool's "filled at least 50% last year" condition and the lateral-entry vacancy rule are not applied.
- Only one roll year is supported.
- CI has never run on GitHub (Actions billing); the suites pass locally.
- `POST /admin/demo/reset` still answers 501; `make demo-reset` is the working path.

## Layout

```
apps/web          Next.js front end
services/api      FastAPI, the product
services/mockgov  simulated government systems (APAAR, counselling, ABC, DigiLocker, Study in India)
tools/datagen     synthetic data with ground-truth labels
tools/eval        accuracy evaluation (Week 4)
docs/             ARCHITECTURE, API_CONTRACT, DATA_MODEL, DECISIONS, PROGRESS
rules.yaml        seat pools, thresholds, weights, each with its handbook source
```

No real student data, ever. No real government API is ever called.
