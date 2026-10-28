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

## D14. An upload is a delta keyed by student identity (2026-10-28)
An upload carries one institution and one academic year and touches only the rows it contains. Each row upserts the enrolment keyed by (student identity, programme, academic year). Identity is the APAAR HMAC when a valid APAAR is given with consent, else the passport HMAC for an international student, else the institution's provisional match on normalised name, date of birth and mobile HMAC. Three optional columns, `status` (ACTIVE by default, WITHDRAWN or TRANSFERRED), `status_date` and `admission_date` (both ISO dates, defaulting to the upload date), let a college report withdrawals, transfers and late admissions without re-sending its roll. Re-uploading the same file changes nothing, and a bad row never aborts a file: it becomes an upload row error and the good rows proceed. Reason: colleges change their rolls all year; a delta with stable identity keys makes re-uploads safe and lets the Seat Ledger see releases and refills as events.

## D15. One pipeline function with a fixed stage order (2026-10-28)
`run_batch(batch_id)` runs parse and header check, row validation, within-file duplicates, upsert of students and enrolments, Seat Ledger, the five checks (adapter calls concurrent), cross-institution duplicates, flags, then marks the batch DONE with counts. The Celery task, the REST upload path and `make seed` all call it. Progress (`stage`, `total_rows`, `processed_rows`) is saved on `upload_batches` every 500 rows. Reason: one code path means the seeded demo and a live upload behave the same, and the order guarantees each engine finds what it depends on (checks need seats; duplicates need upserted students).

## D16. The Seat Ledger assigns seats in the database (2026-10-28)
The admission route picks the pool through `rules.yaml` `admission_routes`; the approval is the one for (programme, cohort year) from `app/core/cohort.py`. A seat is taken in one transaction with `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1` on FREE seats of that pool; CIWG-reserved seats go only to CIWG students and the INTERNATIONAL pool only to the INTERNATIONAL route. With no free seat the enrolment stays unseated and a flag is raised once per (institution, programme, cohort year, pool): EXCESS_ADMISSION (HIGH) for the REGULAR pool, QUOTA_BREACH for any other pool (MEDIUM, HIGH when INTERNATIONAL or NRI is exceeded by more than 2). Its evidence is refreshed as rows arrive ("132 admitted against 120 approved; 12 without a seat"). WITHDRAWN and TRANSFERRED release the seat back to FREE. A released seat assigned again after the approval's cutoff date (judged by `admission_date`) raises LATE_REFILL (MEDIUM). Seat events are append-only and every assignment and release is written to the audit chain. Reason: when every approved seat is a row, excess and quota breaches are counted by the database the moment a file lands; SKIP LOCKED keeps concurrent workers safe; the event log plus the hash chain give officers a tamper-evident seat history.

## D17. Name matching is a pure, heavily tested module (2026-10-28)
`app/engine/matching.py` normalises names (lower case; honorifics mr, ms, mrs, dr, shri, smt, kumari, km and sri removed; punctuation stripped; spaces collapsed; Mohd, Md, Mohammad and Muhammad folded to mohammed; common spelling folds), transliterates Devanagari to Latin with indic-transliteration (ITRANS or IAST, then ASCII-folded) and matches tokens with awareness of initials on top of RapidFuzz, so "R. K. Sharma" and "Ravi Kumar Sharma" score at least 90 when the initials line up and the surname matches. Thresholds come from `rules.yaml`: 90 and above is a match, 75 to 90 needs review, below 75 is no match. Date of birth must agree for any identity or duplicate decision. Reason: Indian names arrive with honorifics, initials, spelling variants and in Devanagari, and plain fuzzy ratios score them too low; pure functions are cheap to test exhaustively, and thresholds in `rules.yaml` keep the cut-offs visible to the panel.

## D18. Five checks with fixed outcomes; an outage is never a failure (2026-10-28)
Each check in `app/engine/checks/` returns a status, a source and a detail with a plain-English `summary`. IDENTITY verifies the APAAR (NA without one, FAIL with INVALID_APAAR or NAME_MISMATCH, PENDING for review between 75 and 90). ADMISSION checks the counselling list for counselling, TFW and lateral admissions, the seat-type rules for management, spot and NRI admissions, and Study in India for international ones. SEAT passes when the enrolment holds one assigned seat in its cohort approval. STUDYING reads ABC credits for each completed year, from year 2 for a lateral entrant (NA in the first year, for a year-2 lateral entrant or without an APAAR; FAIL with NO_ACADEMIC_ACTIVITY when two or more expected semesters have no credits; PENDING when one does). STUDENT stays PENDING until the Week 3 student loop. A source that cannot be reached gives PENDING with `detail.source_unavailable`, never FAIL, and the recheck endpoints re-run PENDING checks. Score is passes over applicable checks (not NA); PENDING counts as applicable but not as a pass, shown as "n of m". Reason: one independent source per check lets an officer see exactly which source disagreed, and treating an outage as pending means a government system going down never flags a genuine student.

## D19. Duplicates: exact within a file, blocked and fuzzy elsewhere (2026-10-28)
`app/engine/duplicates.py`. An APAAR repeated within one file is a row error, DUPLICATE_IN_FILE, and the later row is rejected. Within an institution, records without an APAAR are blocked on (date of birth, first initial, metaphone of the surname) and a pair whose names score 90 or more with initials awareness, or that share a mobile HMAC, raises DUPLICATE_WITHIN_UPLOAD (MEDIUM) linking both enrolments (the "R. K. Sharma" demo). The same APAAR ACTIVE at two institutions in one academic year raises DUPLICATE_CROSS_INSTITUTION (HIGH), unless one programme is PHYSICAL and the other ODL or ONLINE, which raises DUAL_ENROLMENT_ALLOWED (LOW) and cites the UGC 2022 rule. Without an APAAR across institutions, the same block plus a name score of 90 or more plus the same mobile HMAC raises DUPLICATE_CROSS_INSTITUTION (MEDIUM). This needs `programmes.mode` (migration 0002); the seed imports datagen's `mode`. Reason: a repeated id inside one file is a clerical error the college fixes itself, while everything across records needs evidence and an officer; blocking keeps comparisons near linear; and the UGC rule makes one physical plus one distance programme lawful, so it must not read as a duplicate.

## D20. Flags are made by engines, deduplicated and never deleted (2026-10-28)
Only engines create flags. Each carries a `dedupe_key`, so a re-run updates the existing flag instead of adding one; flags are never deleted and start OPEN. Evidence has one schema: `{summary, facts: [{label, value, source}], related_enrolment_ids, rule_source?}`, where `summary` is one plain-English sentence from the copy deck templates. Week 2 exposes read endpoints only; officer actions arrive in Week 3. Reason: an officer must be able to trust that a flag reflects the data and was not added or removed by hand; dedupe keys make every engine safe to re-run; one evidence shape lets the web render any flag without special cases.

## D21. Dashboard KPIs from real flags and checks (2026-10-28)
`kpis.flags_open` counts real flags. `kpis.countersigned_pct` is the share of ACTIVE enrolments whose applicable checks are all PASS; `kpis.clear_pct` is the share with no FAIL. The institutions list sort `flags_open_desc` becomes real. Reason: the share fully countersigned is the headline number; with the student check pending until Week 3 it stays below 100 percent, which is the true state, and the clear share shows how much of the roll no source contradicts.

## D22. The seed goes through the engine, against a time budget (2026-10-28)
`make seed` seeds mockgov first, then runs every datagen upload through `run_batch` in-process (no Celery), so the Makefile order changes. Target: the small seed (about 10.5k rows) in under 3 minutes. 50k rows in under 2 minutes is the Week 4 evaluation target; it is measured and recorded now. Reason: the demo data must come from the same engine the panel is shown, and measuring early tells us whether Week 4 needs bulk paths.
