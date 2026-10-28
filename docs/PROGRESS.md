# Progress

| | |
|---|---|
| Project | Countersign (SIH 2026, AICTE PS 26263) |
| Week | 1 of 4 complete apart from CI green, which GitHub has not started over account billing. Week 1 scope: repo, compose, schema, auth, datagen, mockgov, adapters, first dashboards. Week 2 is next. |
| Last updated | 2026-10-28T15:39:00+05:30 (Asia/Kolkata) |

## How to read this file

- The task board lists every Week 1 task in build order. Status moves TODO, IN PROGRESS, IN REVIEW, MERGED, DONE. MERGED means the code is on `main`; DONE means it is on `main` and its end-to-end check (browser acceptance for T12, the full demo for T13) also passed.
- Evidence is a commit on `main` (short sha) or a branch name, plus test counts when a suite exists. No evidence, no status upgrade.
- The verification checklist is the Week 1 exit bar. A box is ticked only after the command was run and the output matched.
- "What the demo can show today" is what a visitor could see right now from a clean checkout, not what is planned.
- Results marked *(reported)* come from the lead's runs on 2026-10-28 and were not re-run for this update: the integration run around 13:50 IST, and the close-out runs just before this update (`make test` in compose, web lint, typecheck and build, and the browser acceptance through the web container). Everything else was re-checked at 15:39 IST against `git log`, `git log --merges`, `docker compose ps`, both `/healthz` endpoints, `GET :3000/login`, sign-ins through the web proxy and `gh run view` on the latest CI run.
- Decisions and their reasons live in `docs/DECISIONS.md`; the shared contract is `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md` and `docs/DATA_MODEL.md`.

## Week 1 task board

| Task | Owner | Status | Evidence | Notes |
|---|---|---|---|---|
| T1 Repo bootstrap (.gitignore, .editorconfig, README, DECISIONS D1 to D12, .env.example, Makefile, CI workflow) | lead | MERGED | `766cd16` on main | `rules.yaml` with handbook sources landed here too. D13 (role-split build) added in `8b3e87f`. |
| T2 docker-compose (postgres with three databases, redis, mailpit, api, worker, mockgov, datagen, web) | lead | MERGED | `c0f314d` on main; `3c0bff8` | Re-checked 15:39 IST: postgres, redis, mailpit, api and mockgov healthy; worker and web up (neither has a healthcheck); web answers `GET :3000/login` with 200. The api keeps idle connections open for 75 s so the web proxy does not reuse closed sockets (`3c0bff8` in compose, `ff74985` in the api). Empty `rules.yaml` mount placeholders are ignored and skipped (`32d9069`, `62da222`). |
| T3 API skeleton (uv, app factory, settings, async session, /healthz, logging, CORS, rate-limit stub, Dockerfile) | backend-api | MERGED | merge `f660128` (`api/week1`, 15 commits, `--no-ff`); `df584cc`, `770fff2`, `276e2ee`; merge `8062b89` (`api/week1-fixes`, 5 commits, `--no-ff`) | Comma-separated `CORS_ORIGINS` from the environment (`ec7a844`). From `api/week1-fixes`: a 422 carries its first field error as the message (`defc9cc`) and idle connections stay open for 75 s (`ff74985`); its other three commits are noted under T6 and T7. |
| T4 Schema + migrations (all models, Alembic 0001, upgrade on start, up/down test) | backend-api | MERGED | merge `f660128`; `2d12219` | Every Week 1 table as SQLAlchemy models with migration 0001. |
| T5 Crypto + audit chain (hmac_id, encrypt/decrypt, mask_apaar, audit.record, verify_chain) | backend-api | MERGED | merge `f660128`; `e2e4667`, `c859661` | Masked APAAR `XXXX XXXX 4417` and audit verify ok in the acceptance run *(reported)*. No enrolment response carries a 12-digit APAAR *(reported, browser acceptance)*. |
| T6 Auth + RBAC (seeded users, /auth/login, /auth/logout, /me, require_roles, scope filters, read audit) | backend-api | MERGED | merge `f660128`; `8c8a768`, `157ac22`, `276e2ee`, `2503e20`, `8cdad7e`; `2855d3d` in merge `8062b89` | Six role logins, 401 on a bad password, region and institution scoping, 403 and 404 cases passed *(reported)*. The login rate limit is read from `LOGIN_RATE_LIMIT` (`2855d3d`). |
| T7 rules.yaml + seat-pool builder (loader, build_for_approval, CSE 120 gives 114/6/6/12/18) | backend-api | MERGED | merge `f660128`; `a9b89d6`, loader fix `62da222`; `276cb7d`, `f8d314c` in merge `8062b89` | ABC College CSE 2026-27 pools 114 / 6 / 6 / 12 / 18 *(reported)*. Programme admitted counts use the approval's cohort (`276cb7d`) and the seats list is scoped to one approval year (`f8d314c`). TFW "filled at least 50% last year" is not evaluated yet. |
| T8 mockgov (own app and DB, five registries, verify endpoints, chaos toggles, seeder, tests) | mockgov | MERGED | merge `2cbb0d5` (`mockgov`, 22 commits, `--no-ff`) | 92 tests on a dedicated `mockgov_test` database. Endpoint shapes per API_CONTRACT §C. |
| T9 Adapters (Protocols, InMemory, MockGov with timeout and retry, Real stubs, factory) | backend-api | MERGED | merge `f660128`; `55895d3`, `05440dd` | Adapter ping and chaos passthrough on `/admin`. |
| T10 datagen (CLI, institutions, uploads CSV/XLSX, mockgov jsonl, users.json, ground_truth.json, planted anomalies) | datagen | MERGED | merge `d3af32a` (`datagen`, 8 commits, `--no-ff`) | 45 tests. Small mode generates in 2.4 s *(reported)*. |
| T11 Seed importer, make seed, make demo-reset | backend-api | MERGED | merge `f660128`; `9d7f2a3` | `make seed` 34 s, `make demo-reset` twice with identical counts *(reported)*. `POST /admin/demo/reset` answers 501 and points at `make demo-reset`. |
| T12 Web (Next.js 16 scaffold, Tailwind v4, shadcn, TanStack Query, API client, proxy, login, role shells, /aicte, /ro, /college, placeholders) | frontend (ui: primitives and theme; ux: flows) | DONE | merge `b1dd4e8` (`frontend/week1`, 46 commits, `--no-ff`); on main `4a133f6`, `4ff4cc2`, `a19b4fd`, `6ff8a54` with api `ee842c6` | `apps/web/` with a Dockerfile (dev and standalone prod targets), typed API client, `/api` proxy to the api, session lookup and role guard, login and a shell per role. Pages: national and regional overviews (KPI strip, government sources panel, state grid by regional office, region table), ranked institutions table, institution detail with programmes, enrolments and seats tabs, registrar seat ledger and enrolments, upload placeholder, student page, university affiliates, system page (source ping, audit verify, chaos controls), public `/verify` placeholder. On main: the login footer says what the demo data is (`4a133f6`), the Next.js dev indicator is hidden (`4ff4cc2`), seat rows carry their approval year (`a19b4fd`), and institution detail carries the same approved seats and enrolment totals as its list row (`ee842c6`) with the Enrolments tab badge counting every active enrolment (`6ff8a54`). Lint, typecheck and build clean; the docker dev image builds *(reported)*. Browser acceptance passed, see item 4. |
| T13 Week 1 demo + docs (README run section, DATA_MODEL, CI green, manual acceptance script) | lead | DONE | README Week 1 section `80a1b58`; `docs/DATA_MODEL.md` `8b3e87f`; private remote `https://github.com/omsherikar/countersign` with `main` pushed | CI green is still open, blocked on GitHub billing. API and browser acceptance both passed *(reported)*. `.github/workflows/ci.yml` triggers on push, but GitHub refused to start every job: "recent account payments have failed or your spending limit needs to be increased" (latest run 40669694546 on `6ff8a54`, re-checked 15:39 IST). No job ran, so this is an account problem, not a code failure. |

## Verification at end of Week 1

- [x] 1. `make up` brings every container to healthy; `curl :8000/healthz` and `curl :8001/healthz` return ok. Re-checked 15:39 IST: postgres, redis, mailpit, api and mockgov healthy; worker and web up (neither defines a healthcheck); web serves `:3000/login`; both `/healthz` return `status: ok`.
- [x] 2. `make datagen && make seed` prints a summary with 50 colleges and about 10k students (small); the ABC College CSE approval is 120 with pools 114 / 6 / 6 / 12 / 18. Re-checked in the live database at 14:37 IST: 50 institutions, 187 programmes, 507 approvals, 2535 seat pools, 63759 seats, 55 users, 10561 students, 10574 enrolments, 7 rows held back with `APAAR_FORMAT`; mockgov registries 9672 APAAR, 7213 counselling, 11844 ABC, 172 Study in India. Pools *(reported)*.
- [x] 3. `make test` passes the api, mockgov and datagen suites; test counts recorded below *(reported)*.
- [x] 4. Browser: AICTE_ADMIN sees national KPIs and the state grid; RO_OFFICER sees only its region's institutions; INSTITUTION sees only its own college; the API answers an institution asking for another institution id with 404 (ARCHITECTURE §3).
  - [x] API half *(reported)*: `ro.west` sees 7 institutions; the ABC registrar sees 1 and gets 404 on XYZ; the student gets 403 on `/institutions`.
  - [x] Browser half *(reported)*: through the web container on `:3000`, five roles sign in via the web proxy; signed out, `/aicte` redirects to `/login`; a route for another role sends the user to their own home with a denied notice; the ABC registrar sees only ABC College; `/verify` is public; no enrolment response contains a 12-digit APAAR. A headless screenshot of ABC College shows CSE at 120 approved, 132 admitted and 132 unseated, and the Enrolments tab at 605.
  - [x] Scoping through the web proxy, re-checked 15:39 IST: `GET :3000/api/institutions` returns 50 institutions for the AICTE admin, 7 for `ro.west` and 1 (ABC College) for the ABC registrar.
- [x] 5. `POST :8001/admin/chaos {source:"apaar", down:true}` then `GET :8000/admin/adapters/ping` reports `apaar: UNAVAILABLE` and the others ok; chaos reset afterwards *(reported; chaos state is all clear at 15:39 IST)*.
- [x] 6. `make demo-reset` runs clean twice in a row *(reported, identical counts)*.
- [x] 7. `GET :8000/admin/audit/verify` returns `{ok: true, length: N}` after seeding *(reported)*.

Test counts (`make test` in compose, 2026-10-28 just before this update, *reported*): api 76 passed, mockgov 92 passed, datagen 45 passed. The api total rose from 64 with the `api/week1-fixes` merge and the institution totals change. The suites on main hold 71, 76 and 45 test functions; parametrised cases account for the larger api and mockgov totals. Web: lint, typecheck and build clean, and the docker dev image builds *(reported)*.

## What the demo can show today

The demo works end to end in the browser. From a clean checkout, the README "Week 1: run it" steps bring up postgres, redis, mailpit, api, worker, mockgov and web, generate small-mode data with planted anomalies and seed both databases. At `localhost:3000` a visitor can:

- Sign in as any demo role and land on that role's home. Signed out, a role page goes to the login page; a page for another role sends the user back to their own home with a notice.
- As the AICTE admin, see the national KPIs, the government sources panel, the state grid grouped by regional office and the ranked institutions table with search, filters, sort and pages.
- As `ro.west`, see the regional overview and only the 7 Western-region institutions.
- Open ABC College of Engineering: the programmes table shows CSE 2026-27 at 120 approved, 132 admitted and 132 unseated, with its seat pools and their rule sources; the Enrolments tab lists 605 active enrolments with masked ids, consent and the countersign strip; the seats tab pages through seats by approval year.
- As the ABC registrar, see only ABC College, its seat ledger, its enrolments and the upload page listing the expected file columns.
- As the student, see the masked identity and enrolment cards; as the university, the affiliates page.
- On the system page, ping the five government sources, verify the audit chain and take a source down with the chaos controls.
- Open `/verify` without signing in.

The API (`localhost:8000/docs`) and mockgov (`localhost:8001`) still answer the same checks by `curl`, and `design/preview.html` renders every design element in light and dark.

Not in the demo yet: uploads, validation, name matching, seat assignment, countersigning and duplicate detection. The upload page and `/verify` are placeholders until Week 2.

## Blockers / risks

- CI green is the one open Week 1 item. The repository is on GitHub (private) and `main` is pushed, but GitHub refused to start any CI job because of an account billing or spending-limit problem (annotation on run 40669694546). No job has run, so the workflow itself is unproven on GitHub, although the same suites pass in compose. Settling billing or raising the Actions spending limit, then re-running the latest workflow, closes it.
- Known gaps carried into Week 2 (README): no seats are assigned, so every enrolment shows as unseated (ABC CSE: 132 unseated) until the Seat Ledger lands; the TFW 50% condition is not evaluated and the pool is always built; seed-import audit entries are per batch, not per row. Also `POST /admin/demo/reset` is a 501 stub; `make demo-reset` is the working path.
- Region table entries marked *verify* in ARCHITECTURE §8 (DL under NORTH_WEST, RJ under WEST_CENTRAL) must be checked against the AICTE site before the panel demo.

## Changelog

- 2026-10-28 15:39 IST: Week 1 complete apart from CI green. `frontend/week1` merged as `b1dd4e8` (46 commits, `--no-ff`): the Next.js web app with role shells and every Week 1 page. `api/week1-fixes` merged as `8062b89` (5 commits, `--no-ff`): cohort-based admitted counts, per-year seats, first-field 422 message, 75 s keep-alive, `LOGIN_RATE_LIMIT` setting. On main: login footer copy (`4a133f6`), hidden dev indicator (`4ff4cc2`), compose keep-alive (`3c0bff8`), seat year on web rows (`a19b4fd`), institution detail totals with the matching Enrolments badge (`ee842c6`, `6ff8a54`). Tests: api 76, mockgov 92, datagen 45 passing; web lint, typecheck and build clean. Browser acceptance through the web container passed, so verification items 1 to 7 are all ticked. T12 and T13 DONE. Private remote `https://github.com/omsherikar/countersign` added and `main` pushed; CI has not run because GitHub refused to start the jobs over account billing. The frontend critical-path risk is closed.
- 2026-10-28 14:37 IST: Backend complete. `mockgov` (`2cbb0d5`, 22 commits, 92 tests), `design/system` (`9bb9490`, 18 commits), `datagen` (`d3af32a`, 8 commits, 45 tests) and `api/week1` (`f660128`, 15 commits, 64 tests) merged with `--no-ff`; UX spec (`edb16e3`), API contract addendum (`3298998`), ownership update (`7c52295`), README Week 1 section (`80a1b58`) and fixes `ec7a844` and `62da222` on main. T1 to T11 MERGED; T12 in progress on `frontend/week1`; T13 partly done. Integration run ticked verification items 1 to 3 and 5 to 7 and the API half of item 4; seed and registry counts re-checked in the live databases. The earlier blocker about builder branches not being visible is resolved.
- 2026-10-28: First board. T1 (`766cd16`) and T2 (`c0f314d`) merged; shared contract (`8b3e87f`) merged. T3 to T13 in progress, no branches visible yet. Verification list copied from the Week 1 plan, nothing ticked. README status paragraph points here.
