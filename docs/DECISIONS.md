# Decisions

Numbered, dated, with the reason. Newer entries at the bottom. Nothing here is deleted; a reversed decision gets a new entry pointing back.

## D1. Python 3.12 in every container (2026-10-28)
networkx 3.7 excludes 3.14.1 and openmined.psi wheels stop at CPython 3.13. 3.12 has a wheel for every library in the spec. `uv` manages each Python project; `uv.lock` is committed.

## D2. Next.js 16 App Router, Tailwind v4, shadcn/ui, TanStack Query, Recharts, pnpm (2026-10-28)
Matches the spec and the team's existing stack. No Vite.

## D3. One Postgres 17 instance, three databases (2026-10-28)
`countersign` (api), `mockgov` (mock government systems), `countersign_test` (pytest). mockgov is a separate process with no import path into the api; the api reaches it only over HTTP through adapters. This keeps the "swap mock for real" story honest.

## D4. Auth is email + password, argon2, short-lived JWT in an httpOnly cookie (2026-10-28)
One `users` table with a role and optional scope columns (institution, region, student, university). RBAC lives in FastAPI dependencies, never only in the UI.

## D5. Three adapter implementations per government source (2026-10-28)
`InMemory*` for unit tests, `MockGov*` for the demo (HTTP to services/mockgov), `Real*` with the same interface that raises unless `ALLOW_REAL_GOV_APIS=true`, which is never set. Selected by `GOV_ADAPTER`.

## D6. The whole schema lands in Week 1 (2026-10-28)
Every core table from the spec is in migration 0001 so later weeks add engines and columns, not tables.

## D7. Audit hash chain from day one (2026-10-28)
`audit.record()` runs in the same transaction as the write it describes and chains `sha256(prev_hash + canonical_json)`. The "verify chain" button is Week 3; the chain itself cannot be retrofitted.

## D8. No India map; a state grid instead (2026-10-28)
A wrong boundary in front of a government panel is a disaster. A map comes back only in Week 4 and only from a Survey of India-compliant source.

## D9. APAAR at rest: HMAC for lookup, Fernet copy, last four digits (2026-10-28)
The full ID never leaves the api. Mobile and address get the same HMAC treatment.

## D10. Seat-pool percentages come from the handbook text, not memory (2026-10-28)
Verified against the APH 2024-27 PDF and the 2026-27 addendum. `rules.yaml` carries a `source:` per value: NRI 5% within intake (cl. 2.8b), TFW 5% supernumerary (cl. 6.42d), lateral 10% supernumerary plus first-year vacancies (cl. 6.13a,f), international 15% Engg Diploma/UG, 25% Engg PG, 25% Management/MCA/Design/Planning/HMCT/Applied Arts all levels (cl. 2.9 + 2026-27 addendum), one third of international seats for CIWG, FN via supernumerary plus lateral capped at 15% (cl. 6.13b). EWS 10% is a reservation category, not a pool (cl. 4.6).

## D11. Tests run inside compose (2026-10-28)
`make test` runs pytest in the api, mockgov and datagen containers against `countersign_test`. Nobody needs a local Postgres.

## D12. Datagen is deterministic and never writes to the api database (2026-10-28)
It writes what a college would upload (CSV/XLSX), the mockgov registries, demo users and `ground_truth.json`. `make seed` loads them through the api's own importer. From Week 2 student rows go through the real upload engine.

## D13. Parallel build with role-split agents on separate branches (2026-10-28)
Backend, frontend, UI, UX, progress and monitor roles each work on their own branch from a shared contract in `docs/ARCHITECTURE.md` and `docs/API_CONTRACT.md`. The contract is the only thing both sides may assume about each other.
