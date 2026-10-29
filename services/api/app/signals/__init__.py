"""Signals (D45): patterns across records that only AICTE and regional officers see.

Two detectors write the `signals` table: `rings` (students linked by a shared mobile, email or
address, as NetworkX connected components) and `anomaly` (a scikit-learn Isolation Forest per
academic year over institution features). A signal is support for an officer, never evidence
about one record: nothing here changes a row, a case or a record's status (R5). Only an
officer opening a case from a signal (`service.open_cases`) makes a case, and that case then
follows the evidence rule like any other.
"""
