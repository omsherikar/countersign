# Countersign

**Every enrolment, countersigned.**

SIH 2026, PS 26263 (AICTE). An APAAR-ID-based student data management and verification platform for AICTE-approved institutions.

A college's student upload is a *claim*. Five independent sources then countersign each record: Identity, Admission, Seat, Studying, Student. Officers see which check failed and decide. Nothing is auto-rejected.

## Status

Week 3 of 4 is merged (2026-10-29). On top of the Week 2 engine, every finished upload now sends each student a notice by email and, with an APAAR, by DigiLocker; the student answers Yes or No on a public page reached by a one-time link (English or Hindi). A Yes countersigns the record, a No fails the Student check and opens a High "Student denied" flag, no reply stays pending. Officers act on flags (request documents, escalate, clear, confirm, assign, reopen, note) and colleges answer document requests with files; history hides internal notes from colleges. AICTE signs an SD-JWT enrolment proof once every check agrees; the student shares chosen fields as a QR that anyone verifies against the published keys and revocation list, and universities print a degree insert with masked APAAR and a signed QR. Students see their consents, who viewed their record and their data requests; the admin verifies the hash-chained audit log. Verified in Docker compose from a clean seed: 84 of 84 planted cases caught with the expected severity, 100 flags with none unexplained, none of the 20 refused-consent controls flagged, 67.9% of records fully countersigned after the simulated replies; Playwright walks the demo path (22 tests). Tests: api 516, mockgov 103, datagen 92. Week 4 adopts the team's final scope: evidence states and record statuses instead of a score, student replies only after DigiLocker sign-in, officer decisions that update the record, seat and attestation together, completeness per college, signals, reports and the evaluation. Boards and checklists are in [docs/PROGRESS.md](docs/PROGRESS.md); reasons are in `docs/DECISIONS.md` (D23 to D33 for Week 3).

## Run it

```
cp .env.example .env
make up          # postgres, redis, mailpit, api, worker, mockgov, web
make datagen     # synthetic data, small mode (SIZE=full for 500 colleges)
make seed        # mockgov registries, every upload through the engine, notices, simulated replies (about 14 minutes, small)
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

## Week 3: run it

```
make up                  # Mailpit at :8025 holds the notices; on another machine with Redis on 6379 set REDIS_HOST_PORT
make datagen             # also writes planned student replies and the 2025-26 graduates
make demo-reset          # both databases and Mailpit wiped, then: uploads, notices, simulated replies (about 14 minutes, small)
make test                # api 516, mockgov 103, datagen 92
make e2e                 # the demo path in a browser, see below
```

After the seed, Ravi Kumar Sharma and Xavier Paul (ABC College CSE) are the two students whose notices are left unanswered for the demo.

### Walk the student loop

1. Open Mailpit (http://localhost:8025), search for Ravi Kumar Sharma, and open the link in his notice. The page shows the claim with the APAAR masked; answer Yes.
2. Sign in as `student@demo`: My proofs holds an Enrolment proof. Share it, tick Academic year, agree and create the QR. The code under it opens `/verify/{code}` in any browser: Valid, with exactly the three shared fields.
3. Open the demo DigiLocker inbox (http://localhost:8001/digilocker/ui?apaar_id=815283767032) and follow Xavier Paul's Respond link; answer No with a comment. ABC College gets a High "Student denied" flag; officers see the comment, the registrar does not.

### Work a case

1. As `ro.west@aicte.demo`, open the cases queue and an ABC College flag; Request documents with a note and a due date. The registrar gets an email in Mailpit.
2. As `registrar@abc.edu.demo`, open the flag under Flags and respond with a note and a PDF.
3. As `ro.west@aicte.demo`, download the attachment and Clear the flag with a note. The history lists each step; the college sees the clear note but never an internal note.
4. As `admin@aicte.demo`, an enrolment's page lists its proofs; Revoke takes a reason, and a verifier then sees Revoked. A revoked proof is never issued again on its own.

### Degrees, audit and privacy

- As `coe@univ.demo`, Degree print lists 2025-26 graduates; issue a degree proof, open the print view (masked APAAR and QR) or download the PDF; the QR opens `/verify/d/...` and verifies.
- As `admin@aicte.demo`, Audit verifies the chain ("Chain intact"). `make audit-tamper SEQ=n` changes one entry (demo mode only); Verify then reports the break at that entry. `make demo-reset` restores it.
- As `student@demo`, Privacy shows the consents with their exact text, who viewed the record (roles and dates only), and data requests; an Access request downloads everything held, with the APAAR masked.

### Results of the compose run (small seed, 2026-10-29)

| Measure | Result |
|---|---|
| Uploads through the engine | 53 files, 10,633 rows in 363 s |
| Notices | 20,334 sent (10,611 emails, the rest DigiLocker) in 184 s |
| Simulated replies | 7,210 Yes, 8 No, 3,398 no reply in 189 s |
| Planted cases caught | 84 of 84 with the expected severity, incl. 8 Student denied |
| Flags raised | 100, none unexplained |
| Refused-consent controls flagged | 0 of 20 |
| Fully countersigned | 67.9% of 10,611 active records |
| Playwright demo path | 22 passed, about 1.5 minutes |

### Known gaps carried into Week 4

- The small seed now takes about 14 minutes end to end, and uploads alone about 6 minutes; Week 4's evaluation sets 50,000 rows under 2 minutes.
- A reply through the notice link counts even when it came by email to an address the college supplied; Week 4 moves every reply behind DigiLocker sign-in.
- CI has never run on GitHub (Actions billing); the suites pass locally.

## End-to-end tests

Playwright tests in `apps/web/e2e` follow the 60-second pitch, one file per flow, in order:

1. Officers, registrars and the university sign in with the demo password; Ravi signs in only through the Demo DigiLocker from the login page's Student card (OTP 123456); a signed-out `/aicte` goes to `/login`.
2. The sample record (Vinayak Akshay Chavan, ABC College CSE) reads exactly as the deck's card: Identity Confirmed, Seat fits approval v2, Joining record Contradicted, Credits Not yet due, Student "I never joined" after DigiLocker sign-in, Disputed (priority) with a next step and the legend.
3. ABC College CSE shows 120 approved (v2) and 132 admitted with its Excess admission case; the R. K. Sharma duplicate leads to Ravi.
4. A record with an independent joining record is Countersigned with no answer from the student, and that student's enrolment attestation shares three fields that verify as Valid.
5. Ravi's notice from Mailpit shows the claim but asks for DigiLocker sign-in before any answer; he says Yes and his Student row is confirmed; sharing three fields of his attestation is marked fixme while the open R. K. Sharma duplicate case keeps his record Under review; another signed-in student is told the notice is for someone else.
6. Xavier Paul's notice from the DigiLocker inbox, answered No after sign-in: the record turns Disputed, a High Student dispute case opens, the attestation is revoked; officers read the comment, the registrar does not.
7. The regional officer requests admission documents on that dispute, the registrar answers with a PDF, the AICTE officer withdraws the claim (record withdrawn, seat released in the ledger, no live attestation, decision in the history), and upholds another case whose record then follows the evidence rule.
8. Priyanka Salunkhe, who has no APAAR, signs in with DigiLocker and claims her record by provisional ID; Identity reads Confirmed through her sign-in.
9. The overview counts records by status and completeness; a college with missing students lists them by name; the signals page lists the shared contact ring and the anomalies, and a case opened from the ring puts that college's members Under review; the registrar is refused signals.
10. One report downloads as CSV, XLSX and PDF.
11. The university issues a completion attestation, prints the certificate block (masked APAAR, QR) and the QR verifies.
12. The audit chain verifies as intact.

They run from the host against the running stack, one at a time, with Playwright's bundled headless Chromium (no video). The demo cast comes from the datagen manifest in the compose volume (read through the api container; `E2E_MANIFEST` names a copy instead).

```
cd apps/web && pnpm install && pnpm exec playwright install --only-shell chromium   # once
make demo-reset   # a clean run starts from a fresh seed (about 15 minutes)
make e2e          # about 6 minutes once the web has compiled its pages
```

A clean run starts from `make demo-reset`, because the tests use one-time state the seed keeps for the live demo: Ravi's and Xavier's unanswered notices, Priyanka's unclaimed record, the ring's first case, one decision of each kind and one completion attestation. A second run without a reset still passes: it answers and disputes other unanswered ABC College notices (their students sign in through the Demo DigiLocker, and their emails are found in Mailpit), checks Priyanka's claimed record instead of claiming it again, opens the ring's case for the next college or checks the cases already opened, decides the next open case and takes the next graduate, printing a `note:` line for each. Tests marked fixme name a product bug in one line. `E2E_BASE_URL`, `E2E_API_URL`, `E2E_MAILPIT_URL` and `E2E_MOCKGOV_URL` move the addresses; a failed test keeps its trace and screenshot under `apps/web/test-results`, which is safe to delete.

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
