# Countersign

**Every enrolment, countersigned.**

SIH 2026, PS 26263 (AICTE). An APAAR-ID-based student data management and verification platform for AICTE-approved institutions.

A college's student upload is a *claim*. Five independent sources then countersign each record: Identity, Admission, Seat, Studying, Student. Officers see which check failed and decide. Nothing is auto-rejected.

## Status

Week 1 of 4, in progress (2026-10-28). On `main`: the repo skeleton, the compose file with Postgres (three databases), Redis, Mailpit and service stubs, `rules.yaml` with handbook sources, and the shared contract (`docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`). Nothing runs end to end yet: the api, mockgov, datagen and web directories are empty until their tasks merge. The task board, the end-of-week verification checklist and a dated changelog are in [docs/PROGRESS.md](docs/PROGRESS.md); the reasons behind each choice are in `docs/DECISIONS.md`.

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
