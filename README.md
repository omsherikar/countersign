# Countersign

**Every enrolment, countersigned.**

SIH 2026, PS 26263 (AICTE). An APAAR-ID-based student data management and verification platform for AICTE-approved institutions.

A college's student upload is a *claim*. Five independent sources then countersign each record: Identity, Admission, Seat, Studying, Student. Officers see which check failed and decide. Nothing is auto-rejected.

## Status

Week 1 of 4, in progress (2026-10-28). The backend runs end to end: the API (schema, auth, RBAC, seat pools, adapters, seed importer), mockgov with chaos toggles, datagen with planted anomalies and ground truth, and the design system are on `main`, and the Week 1 acceptance checks pass against the API (api 64, mockgov 92, datagen 45 tests passing). The web app (`apps/web`) is still being built, so there is no browser UI yet. The task board, the end-of-week verification checklist and a dated changelog are in [docs/PROGRESS.md](docs/PROGRESS.md); the reasons behind each choice are in `docs/DECISIONS.md`.

## Run it

```
cp .env.example .env
make up          # postgres, redis, mailpit, api, worker, mockgov, web
make datagen     # synthetic data, small mode (SIZE=full for 500 colleges)
make seed        # load it into api and mockgov
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
make seed                # api importer + mockgov registries, ~40 s
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

- No seats are assigned yet; every enrolment shows as unseated until the Seat Ledger lands. Programme detail counts every active row tagged 2026-27 (all years of study), so the "132 first-years vs 120 approved" scenario becomes visible as a ledger fact in Week 2.
- The TFW "filled at least 50% last year" condition is not evaluated; the pool is always built.
- Audit entries for a seed import are per batch, not per row.

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
