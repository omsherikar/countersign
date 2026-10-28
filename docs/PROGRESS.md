# Progress

| | |
|---|---|
| Project | Countersign (SIH 2026, AICTE PS 26263) |
| Week | 1 of 4: repo, compose, schema, auth, datagen, mockgov, adapters, first dashboards |
| Last updated | 2026-10-28T13:06:00+05:30 (Asia/Kolkata) |

## How to read this file

- The task board lists every Week 1 task in build order. Status moves TODO, IN PROGRESS, IN REVIEW, MERGED. Only MERGED means it is on `main`.
- Evidence is a commit on `main` (short sha) or a branch name, plus test counts when a suite exists. No evidence, no status upgrade.
- The verification checklist is the Week 1 exit bar. A box is ticked only after the command was run and the output matched.
- "What the demo can show today" is what a visitor could see right now from a clean checkout, not what is planned.
- Decisions and their reasons live in `docs/DECISIONS.md`; the shared contract is `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md` and `docs/DATA_MODEL.md`.

## Week 1 task board

| Task | Owner | Status | Evidence | Notes |
|---|---|---|---|---|
| T1 Repo bootstrap (.gitignore, .editorconfig, README, DECISIONS D1 to D12, .env.example, Makefile, CI workflow) | lead | MERGED | `766cd16` on main | `rules.yaml` with handbook sources landed here too. D13 (role-split build) added in `8b3e87f`. |
| T2 docker-compose (postgres with three databases, redis, mailpit, api, worker, mockgov, datagen, web) | lead | MERGED | `c0f314d` on main | Healthchecks on postgres, redis, api, mockgov; `infra/postgres/init.sh` creates the three databases. Not yet brought up: the api, mockgov and web images cannot build until T3, T8 and T12 land. |
| T3 API skeleton (uv, app factory, settings, async session, /healthz, logging, CORS, rate-limit stub, Dockerfile) | backend-api | IN PROGRESS | no branch visible in this repository yet | `services/api/` is empty on main. |
| T4 Schema + migrations (all models, Alembic 0001, upgrade on start, up/down test) | backend-api | IN PROGRESS | no branch visible in this repository yet | Table reference already fixed in `docs/DATA_MODEL.md` (`8b3e87f`). |
| T5 Crypto + audit chain (hmac_id, encrypt/decrypt, mask_apaar, audit.record, verify_chain) | backend-api | IN PROGRESS | no branch visible in this repository yet | |
| T6 Auth + RBAC (seeded users, /auth/login, /auth/logout, /me, require_roles, scope filters, read audit) | backend-api | IN PROGRESS | no branch visible in this repository yet | Demo accounts fixed in ARCHITECTURE §7. |
| T7 rules.yaml + seat-pool builder (loader, build_for_approval, CSE 120 gives 114/6/6/12/18) | backend-api | IN PROGRESS | `rules.yaml` on main (`766cd16`); builder not visible yet | |
| T8 mockgov (own app and DB, five registries, verify endpoints, chaos toggles, seeder, tests) | mockgov | IN PROGRESS | no branch visible in this repository yet | `services/mockgov/` is empty on main. Endpoint shapes fixed in API_CONTRACT §C. |
| T9 Adapters (Protocols, InMemory, MockGov with timeout and retry, Real stubs, factory) | backend-api | IN PROGRESS | no branch visible in this repository yet | Depends on T3 and the T8 contract, not the T8 code. |
| T10 datagen (CLI, institutions, uploads CSV/XLSX, mockgov jsonl, users.json, ground_truth.json, planted anomalies) | datagen | IN PROGRESS | no branch visible in this repository yet | `tools/datagen/` is empty on main. Must emit the users in ARCHITECTURE §7 exactly. |
| T11 Seed importer, make seed, make demo-reset | backend-api | IN PROGRESS | Makefile targets exist (`766cd16`); importer not visible yet | Needs T4, T7 and T10 output. |
| T12 Web (Next.js 16 scaffold, Tailwind v4, shadcn, TanStack Query, API client, proxy, login, role shells, /aicte, /ro, /college, placeholders) | frontend (ui: primitives and theme; ux: flows) | IN PROGRESS | no branch visible in this repository yet | `apps/web/` is empty on main. Ownership split in ARCHITECTURE §2. |
| T13 Week 1 demo + docs (README run section, DATA_MODEL, CI green, manual acceptance script) | lead | IN PROGRESS | README run section and `docs/DATA_MODEL.md` on main (`c0f314d`, `8b3e87f`) | Acceptance script and a green CI run wait on everything above. |

## Verification at end of Week 1

- [ ] 1. `make up` brings every container to healthy; `curl :8000/healthz` and `curl :8001/healthz` return ok.
- [ ] 2. `make datagen && make seed` prints a summary with 50 colleges and about 10k students (small); the ABC College CSE approval is 120 with pools 114 / 6 / 6 / 12 / 18.
- [ ] 3. `make test` passes the api, mockgov and datagen suites; test counts recorded below.
- [ ] 4. Browser: AICTE_ADMIN sees national KPIs and the state grid; RO_OFFICER sees only its region's institutions; INSTITUTION sees only its own college; the API answers an institution asking for another institution id with 404 (ARCHITECTURE §3).
- [ ] 5. `POST :8001/admin/chaos {source:"apaar", down:true}` then `GET :8000/admin/adapters/ping` reports `apaar: UNAVAILABLE` and the others ok; chaos reset afterwards.
- [ ] 6. `make demo-reset` runs clean twice in a row.
- [ ] 7. `GET :8000/admin/audit/verify` returns `{ok: true, length: N}` after seeding.

Test counts: api 0, mockgov 0, datagen 0 (no suites on main yet).

## What the demo can show today

Nothing runs end to end. `main` holds the repo skeleton, the compose file, `rules.yaml`, the shared contract and the decisions log. `make up` cannot complete because the api, mockgov and web directories have no code or Dockerfile yet. There is no database schema, no login and no page to open.

## Blockers / risks

- Builder branches are not yet visible in this repository: `~/countersign` has only `main` and no linked worktrees. The isolated checkouts handed to the builders were created from the parent home-folder repository, so their commits will not appear here until they branch from `~/countersign` itself. Until then the board cannot cite commits or test counts.
- Region table entries marked *verify* in ARCHITECTURE §8 (DL under NORTH_WEST, RJ under WEST_CENTRAL) must be checked against the AICTE site before the panel demo.

## Changelog

- 2026-10-28: First board. T1 (`766cd16`) and T2 (`c0f314d`) merged; shared contract (`8b3e87f`) merged. T3 to T13 in progress, no branches visible yet. Verification list copied from the Week 1 plan, nothing ticked. README status paragraph points here.
