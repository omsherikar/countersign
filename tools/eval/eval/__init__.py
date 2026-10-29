"""Countersign's evaluation on synthetic data (DECISIONS D47, ENGINES §17.14).

The scoring modules (truth, detection, false_alarms, effort, signals, timing's summaries,
report) are pure and tested without a database; snapshot, access and timing.run_perf read
the api's database and call its code, so they run where `app` is importable (the api
container, or services/api on PYTHONPATH).
"""
