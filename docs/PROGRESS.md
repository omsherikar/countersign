# Progress

| | |
|---|---|
| Project | Countersign (SIH 2026, AICTE PS 26263) |
| Week | 1 of 4: repo, compose, schema, auth, datagen, mockgov, adapters, first dashboards |
| Last updated | 2026-10-28T14:37:00+05:30 (Asia/Kolkata) |

## How to read this file

- The task board lists every Week 1 task in build order. Status moves TODO, IN PROGRESS, IN REVIEW, MERGED. Only MERGED means it is on `main`.
- Evidence is a commit on `main` (short sha) or a branch name, plus test counts when a suite exists. No evidence, no status upgrade.
- The verification checklist is the Week 1 exit bar. A box is ticked only after the command was run and the output matched.
- "What the demo can show today" is what a visitor could see right now from a clean checkout, not what is planned.
- Results marked *(reported)* come from the integration run on 2026-10-28 around 13:50 IST and were not re-run for this update. Everything else was re-checked at 14:37 IST against `git log`, `docker compose ps`, both `/healthz` endpoints and row counts in the live `countersign` and `mockgov` databases.
- Decisions and their reasons live in `docs/DECISIONS.md`; the shared contract is `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md` and `docs/DATA_MODEL.md`.

## Week 1 task board

| Task | Owner | Status | Evidence | Notes |
|---|---|---|---|---|
| T1 Repo bootstrap (.gitignore, .editorconfig, README, DECISIONS D1 to D12, .env.example, Makefile, CI workflow) | lead | MERGED | `766cd16` on main | `rules.yaml` with handbook sources landed here too. D13 (role-split build) added in `8b3e87f`. |
| T2 docker-compose (postgres with three databases, redis, mailpit, api, worker, mockgov, datagen, web) | lead | MERGED | `c0f314d` on main | Up since 2026-10-28 13:50 IST: postgres, redis, mailpit, api and mockgov healthy; worker up (it has no healthcheck). The web service has nothing to build until T12 lands. Empty `rules.yaml` mount placeholders are now ignored and skipped (`32d9069`, `62da222`). |
| T3 API skeleton (uv, app factory, settings, async session, /healthz, logging, CORS, rate-limit stub, Dockerfile) | backend-api | MERGED | merge `f660128` (`api/week1`, 15 commits, `--no-ff`); `df584cc`, `770fff2`, `276e2ee` | Follow-up fix on main: comma-separated `CORS_ORIGINS` from the environment (`ec7a844`); the api container did not start healthy without it. |
| T4 Schema + migrations (all models, Alembic 0001, upgrade on start, up/down test) | backend-api | MERGED | merge `f660128`; `2d12219` | Every Week 1 table as SQLAlchemy models with migration 0001. |
| T5 Crypto + audit chain (hmac_id, encrypt/decrypt, mask_apaar, audit.record, verify_chain) | backend-api | MERGED | merge `f660128`; `e2e4667`, `c859661` | Masked APAAR `XXXX XXXX 4417` and audit verify ok in the acceptance run *(reported)*. |
| T6 Auth + RBAC (seeded users, /auth/login, /auth/logout, /me, require_roles, scope filters, read audit) | backend-api | MERGED | merge `f660128`; `8c8a768`, `157ac22`, `276e2ee`, `2503e20`, `8cdad7e` | Six role logins, 401 on a bad password, region and institution scoping, 403 and 404 cases passed *(reported)*. |
| T7 rules.yaml + seat-pool builder (loader, build_for_approval, CSE 120 gives 114/6/6/12/18) | backend-api | MERGED | merge `f660128`; `a9b89d6`, loader fix `62da222` | ABC College CSE 2026-27 pools 114 / 6 / 6 / 12 / 18 *(reported)*. TFW "filled at least 50% last year" is not evaluated yet. |
| T8 mockgov (own app and DB, five registries, verify endpoints, chaos toggles, seeder, tests) | mockgov | MERGED | merge `2cbb0d5` (`mockgov`, 22 commits, `--no-ff`) | 92 tests on a dedicated `mockgov_test` database. Endpoint shapes per API_CONTRACT §C. |
| T9 Adapters (Protocols, InMemory, MockGov with timeout and retry, Real stubs, factory) | backend-api | MERGED | merge `f660128`; `55895d3`, `05440dd` | Adapter ping and chaos passthrough on `/admin`. |
| T10 datagen (CLI, institutions, uploads CSV/XLSX, mockgov jsonl, users.json, ground_truth.json, planted anomalies) | datagen | MERGED | merge `d3af32a` (`datagen`, 8 commits, `--no-ff`) | 45 tests. Small mode generates in 2.4 s *(reported)*. |
| T11 Seed importer, make seed, make demo-reset | backend-api | MERGED | merge `f660128`; `9d7f2a3` | `make seed` 34 s, `make demo-reset` twice with identical counts *(reported)*. `POST /admin/demo/reset` answers 501 and points at `make demo-reset`. |
| T12 Web (Next.js 16 scaffold, Tailwind v4, shadcn, TanStack Query, API client, proxy, login, role shells, /aicte, /ro, /college, placeholders) | frontend (ui: primitives and theme; ux: flows) | IN PROGRESS | branch `frontend/week1` (worktree `.worktrees/frontend`), no commits beyond `main` yet | The only Week 1 task not done. Third build attempt running; the first two produced no commits (the first hit a worktree isolation problem, the second stopped at a usage limit). `apps/web/` does not exist on main. Inputs already on main: design system merge `9bb9490` (`design/system`, 18 commits: `design/` and `docs/DESIGN.md`), UX spec `edb16e3` (`docs/ux/`, 7 files), API contract addendum `3298998`, ownership update `7c52295`. |
| T13 Week 1 demo + docs (README run section, DATA_MODEL, CI green, manual acceptance script) | lead | IN PROGRESS | README Week 1 section `80a1b58`; `docs/DATA_MODEL.md` `8b3e87f` | API acceptance script passed *(reported)*. Browser acceptance waits on T12. CI: `.github/workflows/ci.yml` is on main but the repository has no remote, so no CI run exists yet. |

## Verification at end of Week 1

- [x] 1. `make up` brings every container to healthy; `curl :8000/healthz` and `curl :8001/healthz` return ok. Backend only: postgres, redis, mailpit, api, mockgov healthy, worker up, both `/healthz` return `status: ok` (re-checked 14:37 IST). The web container joins when T12 lands.
- [x] 2. `make datagen && make seed` prints a summary with 50 colleges and about 10k students (small); the ABC College CSE approval is 120 with pools 114 / 6 / 6 / 12 / 18. Re-checked in the live database: 50 institutions, 187 programmes, 507 approvals, 2535 seat pools, 63759 seats, 55 users, 10561 students, 10574 enrolments, 7 rows held back with `APAAR_FORMAT`; mockgov registries 9672 APAAR, 7213 counselling, 11844 ABC, 172 Study in India. Pools *(reported)*.
- [x] 3. `make test` passes the api, mockgov and datagen suites; test counts recorded below *(reported)*.
- [ ] 4. Browser: AICTE_ADMIN sees national KPIs and the state grid; RO_OFFICER sees only its region's institutions; INSTITUTION sees only its own college; the API answers an institution asking for another institution id with 404 (ARCHITECTURE §3).
  - [x] API half *(reported)*: `ro.west` sees 7 institutions; the ABC registrar sees 1 and gets 404 on XYZ; the student gets 403 on `/institutions`.
  - [ ] Browser half: waits on T12.
- [x] 5. `POST :8001/admin/chaos {source:"apaar", down:true}` then `GET :8000/admin/adapters/ping` reports `apaar: UNAVAILABLE` and the others ok; chaos reset afterwards *(reported; chaos state is all clear at 14:37 IST)*.
- [x] 6. `make demo-reset` runs clean twice in a row *(reported, identical counts)*.
- [x] 7. `GET :8000/admin/audit/verify` returns `{ok: true, length: N}` after seeding *(reported)*.

Test counts (`make test`, 2026-10-28 around 13:50 IST, *reported*): api 64 passed, mockgov 92 passed, datagen 45 passed. The suites on main hold 64, 76 (two parametrised) and 45 test functions, consistent with those totals.

## What the demo can show today

The backend demo works end to end at the API level. From a clean checkout, the README "Week 1: run it" steps bring up postgres, redis, mailpit, api, worker and mockgov, generate small-mode data with planted anomalies and seed both databases. Through `curl` or `localhost:8000/docs` a visitor can sign in as each of the six demo roles, see region and institution scoping enforced (404 across colleges, 403 for students), read ABC College's CSE seat pools, see a masked APAAR, take APAAR down in mockgov and watch the adapter ping report it UNAVAILABLE, verify the audit chain and reset the demo. `design/preview.html` renders every design element in light and dark as a static page.

There is no web UI yet: `apps/web/` is not on main and nothing answers on `localhost:3000`.

## Blockers / risks

- The frontend is the critical path. T12 is the only Week 1 task not done, verification item 4 (browser half) and the web container in item 1 depend on it, and two earlier build attempts produced nothing. The current attempt has no commits on `frontend/week1` yet.
- CI has never run: there is no git remote, so the "CI green" part of T13 cannot be met until the repository is pushed.
- Known gaps carried into Week 2 (README): no seats are assigned, so every enrolment shows as unseated until the Seat Ledger lands; the TFW 50% condition is not evaluated and the pool is always built; seed-import audit entries are per batch, not per row. Also `POST /admin/demo/reset` is a 501 stub; `make demo-reset` is the working path.
- Region table entries marked *verify* in ARCHITECTURE §8 (DL under NORTH_WEST, RJ under WEST_CENTRAL) must be checked against the AICTE site before the panel demo.

## Changelog

- 2026-10-28 14:37 IST: Backend complete. `mockgov` (`2cbb0d5`, 22 commits, 92 tests), `design/system` (`9bb9490`, 18 commits), `datagen` (`d3af32a`, 8 commits, 45 tests) and `api/week1` (`f660128`, 15 commits, 64 tests) merged with `--no-ff`; UX spec (`edb16e3`), API contract addendum (`3298998`), ownership update (`7c52295`), README Week 1 section (`80a1b58`) and fixes `ec7a844` and `62da222` on main. T1 to T11 MERGED; T12 in progress on `frontend/week1`; T13 partly done. Integration run ticked verification items 1 to 3 and 5 to 7 and the API half of item 4; seed and registry counts re-checked in the live databases. The earlier blocker about builder branches not being visible is resolved.
- 2026-10-28: First board. T1 (`766cd16`) and T2 (`c0f314d`) merged; shared contract (`8b3e87f`) merged. T3 to T13 in progress, no branches visible yet. Verification list copied from the Week 1 plan, nothing ticked. README status paragraph points here.
