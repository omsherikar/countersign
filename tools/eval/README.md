# tools/eval

The evaluation of DECISIONS D47 and ENGINES §17.14: how the engine does on the synthetic test
bed, against datagen's `ground_truth.json`. Every number it writes is synthetic and says so.

```
make eval
```

1. regenerates `/data/generated` (`datagen --size small --seed 2026 --perf 50000`), removing
   the old upload files first so a different seed leaves none behind;
2. `make demo-reset`: a fresh database, the seed's uploads, notices and replies;
3. loads the throughput college's registry lines into mockgov (`perf/mockgov`);
4. starts `mockgov-eval` (the mockgov image with four worker processes, profile `eval`) and
   runs `python -m eval run --generated /data/generated --out /eval/out` in the api image;
5. writes `tools/eval/out/eval_report.md` and `tools/eval/out/eval.json` (git-ignored) and exits
   1 when a target is missed.

It leaves the eval data loaded (the demo data from seed 2026 plus the 50,000 records of
"Countersign Throughput Test College", `9-PERF-0001`, and one deactivated evaluation user per
college). Run `make demo-reset` before a demo.

## What it measures

| measure | how | target |
|---|---|---|
| seeded inconsistencies caught | per planted `expected_flag`: a case of that type naming the record's rows, its programme and pool, or its institution and year | 95% or more |
| severity as planted | found cases with the planted severity | reported |
| record statuses and rows | planted `expected_record_status` and `expected_rows` against the stored ones | reported |
| reporting deadlines | planted LATE and OVERDUE colleges against `GET /institutions/{id}/completeness` | reported |
| cases raised on legitimate records | ACTIVE uploaded records no ground truth names (throughput college excluded) that a case names or that read UNDER_REVIEW or DISPUTED | under 5% |
| planted controls | refused consent, CIWG seats, unreported TFW certificates, self-issued credits, unclaimed provisional ids, clean independent records: named by a case | reported |
| processing time per upload | `finished_at - started_at` of the seed's batches | reported |
| 50,000 rows | wall time of `run_batch` on `perf/9-PERF-0001_2026-27.csv`, with stage timings | under 120 s |
| officer review effort | unresolved cases per 1,000 active records, evidence facts and records per case | reported |
| signals | rings found when a GHOST_RING signal holds 80% of the planted members; anomalies by institution; precision and recall | reported |
| cross-college access | each college's user asks for every other college's institution, enrolments, completeness, one enrolment, its history, one case and one upload; refused means 403 or 404 | all refused |

Routes the api does not serve yet are skipped and listed in the report.

## Running it by hand

Inside the api image (what `make eval` does):

```
docker compose --profile eval run --rm eval run --generated /data/generated --out /eval/out
docker compose --profile eval run --rm eval run --generated /data/generated --out /eval/out --skip-perf
```

`--skip-perf` and `--skip-access` leave those measures out (reported as not run, not failed).
A second run without `make demo-reset` re-reads the throughput file over records already
loaded; the report says so and that run does not count for the throughput target.

Natively, from `services/api` with its environment (database, `GOV_ADAPTER=mockgov`,
`MOCKGOV_BASE_URL`):

```
PYTHONPATH=.:../../tools/eval .venv/bin/python -m eval run --generated DIR --out DIR
```

## Tests

The scoring is pure functions over plain views, tested on hand-made ground truth:

```
cd tools/eval && uv run pytest
docker compose --profile eval run --rm eval pytest -q
```
