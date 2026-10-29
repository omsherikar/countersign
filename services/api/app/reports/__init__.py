"""Reports for policy, accreditation and monitoring (D46, API_CONTRACT §A4.21).

`registry` names each report, its columns and formats and resolves the caller's scope;
`queries` builds the rows with SQL aggregates over the same per-institution figures the
dashboard reads (`app.routers._stats`), so a report and the dashboard always agree; `render`
writes CSV, XLSX and one-page PDFs, each labelled as synthetic data. No report holds a
student's name or an unmasked id.
"""
