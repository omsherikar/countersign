"""CSV, XLSX and one-page PDF files for the reports (API_CONTRACT §A4.21, copy deck §28).

Pure: rows in, bytes out (openpyxl, reportlab). Every file opens with the synthetic-data
line: the first line of a CSV, the first row of the first XLSX sheet, the top of a PDF page
(and its footer). CSV and XLSX keep the wire column names and unformatted numbers; a PDF
prints the deck's words.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepInFrame,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.engine.upload.types import INDIA

if TYPE_CHECKING:
    from app.reports.registry import ReportScope, ReportSpec

# copy deck report.synthetic, and the About sheet line of API_CONTRACT §A4.21
SYNTHETIC = "Synthetic data. Every college, student and number here is generated for the demo."
ABOUT_LINE = "Synthetic demo data. Every number comes from the Countersign demo dataset."
PDF_ROWS = 25
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# column headers a PDF prints (the deck's words for the same columns on screen)
LABELS = {
    "academic_year": "Academic year",
    "state_code": "State code",
    "state_name": "State",
    "region": "Region",
    "institutions": "Colleges",
    "approved_seats": "Approved seats",
    "admitted": "Admitted",
    "records": "Records",
    "countersigned": "Countersigned",
    "awaiting_evidence": "Awaiting evidence",
    "under_review": "Under review",
    "disputed": "Disputed",
    "countersigned_pct": "Countersigned %",
    "cases_open": "Open cases",
    "joined": "Joined (authority)",
    "missing_from_upload": "Missing",
    "completeness_pct": "Completeness %",
    "institution_type": "Type",
    "case_type": "Case type",
    "case_name": "Case",
    "open": "Open",
    "docs_requested": "Documents requested",
    "escalated": "Escalated",
    "upheld": "Claim upheld",
    "corrected": "Claim corrected",
    "withdrawn": "Claim withdrawn",
    "total": "Total",
    "median_days_to_decision": "Median days to decide",
    "aicte_permanent_id": "AICTE id",
    "institution_name": "College",
    "independent_joining_record": "Joining record (independent)",
    "independent_credits": "Credits (independent)",
    "independent_student": "Student (independent)",
    "uploaded_and_joined": "Uploaded and joined",
    "missing": "Missing",
    "uploaded_not_joined": "Uploaded, never joined",
    "deadline": "Reporting deadline",
    "first_upload_on": "First upload",
    "deadline_state": "Deadline",
    "case_status": "Case",
}
WORDS = {
    "deadline_state": {
        "ON_TIME": "On time",
        "LATE": "Late",
        "OVERDUE": "Overdue",
        "NOT_DUE": "Due",
    },
    "case_status": {
        "OPEN": "Open",
        "DOCS_REQUESTED": "Documents requested",
        "ESCALATED": "Escalated",
        "UPHELD": "Claim upheld",
        "CORRECTED": "Claim corrected",
        "WITHDRAWN": "Claim withdrawn",
    },
    "institution_type": {
        "GOVERNMENT": "Government",
        "GOVERNMENT_AIDED": "Government aided",
        "PRIVATE_SELF_FINANCED": "Private self-financed",
        "UNIVERSITY_DEPARTMENT": "University department",
        "DEEMED": "Deemed",
    },
}
STATUS_WORDS = {
    "COUNTERSIGNED": "Countersigned",
    "AWAITING_EVIDENCE": "Awaiting evidence",
    "UNDER_REVIEW": "Under review",
    "DISPUTED": "Disputed",
}
STATUS_COLOURS = {
    "COUNTERSIGNED": colors.HexColor("#2F6F4E"),
    "AWAITING_EVIDENCE": colors.HexColor("#8A8F98"),
    "UNDER_REVIEW": colors.HexColor("#B7791F"),
    "DISPUTED": colors.HexColor("#9B2C2C"),
}
WIDE = {"institution_name": 3.2, "state_name": 2.0, "case_name": 2.6, "aicte_permanent_id": 1.7}


def generated_line(at: datetime) -> str:
    """`29 Oct 2026, 11:20 IST`."""
    local = at.astimezone(INDIA)
    return f"{local.day} {MONTHS[local.month - 1]} {local.year}, {local:%H:%M} IST"


def _now() -> datetime:
    return datetime.now(INDIA)


def _cell(column: str, value: Any) -> Any:
    """The value as the CSV and XLSX carry it: numbers unformatted, percentages to one
    decimal, dates `YYYY-MM-DD`, nothing as empty."""
    if value is None:
        return ""
    if column.endswith("_pct") or column == "median_days_to_decision":
        return round(float(value), 1)
    if isinstance(value, datetime):
        return value.astimezone(INDIA).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


# --------------------------------------------------------------------------- CSV


def to_csv(spec: ReportSpec, rows: Sequence[Mapping[str, Any]]) -> bytes:
    """UTF-8 with a BOM; the synthetic line, the header, then the rows."""
    columns = spec.columns
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow([SYNTHETIC])
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(c, row.get(c)) for c in columns])
    return ("﻿" + out.getvalue()).encode("utf-8")


# -------------------------------------------------------------------------- XLSX


def to_xlsx(
    spec: ReportSpec,
    rows: Sequence[Mapping[str, Any]],
    scope: ReportScope,
    academic_year: str,
    *,
    generated_at: datetime | None = None,
) -> bytes:
    """Sheet one named after the report: the synthetic line, the header, the rows. Sheet two
    `About`: title, scope, academic year, time generated and the synthetic-data line."""
    at = generated_at or _now()
    title, columns, scope_label = spec.title, spec.columns, scope.label
    book = Workbook()
    sheet = book.active
    sheet.title = title[:31]
    sheet.append([SYNTHETIC])
    sheet["A1"].font = Font(italic=True)
    sheet.append(list(columns))
    for cell in sheet[2]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([_cell(c, row.get(c)) for c in columns])
    sheet.freeze_panes = "A3"
    for i, column in enumerate(columns, start=1):
        letter = sheet.cell(row=2, column=i).column_letter
        sheet.column_dimensions[letter].width = max(10, min(40, len(column) + 2))

    about = book.create_sheet("About")
    for label, value in (
        ("Title", title),
        ("Scope", scope_label),
        ("Academic year", academic_year),
        ("Generated", generated_line(at)),
        ("Data", ABOUT_LINE),
    ):
        about.append([label, value])
        about.cell(row=about.max_row, column=1).font = Font(bold=True)
    about.column_dimensions["A"].width = 16
    about.column_dimensions["B"].width = 80
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


# --------------------------------------------------------------------------- PDF

_BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=7, leading=8.5)
_BOLD = ParagraphStyle("bold", parent=_BASE, fontName="Helvetica-Bold")
_TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=14, leading=17)
_LINE = ParagraphStyle("line", fontName="Helvetica", fontSize=8.5, leading=11)
_NOTE = ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=7.5, leading=9.5)
_HEAD = ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=9, leading=11)
_GRID = colors.HexColor("#C9CDD3")
_HEADER_FILL = colors.HexColor("#EEF0F3")


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _word(column: str, value: Any, deadline: str | None = None) -> str:
    if value is None or value == "":
        return ""
    if column in WORDS:
        word = WORDS[column].get(str(value), str(value))
        if column == "deadline_state" and value == "NOT_DUE" and deadline:
            word = f"Due {deadline}"
        return word
    if isinstance(value, float) or column.endswith("_pct"):
        return f"{float(value):.1f}"
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"
    return str(_cell(column, value))


def _totals(columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Sums of the counts, shares recomputed from the sums, text left blank."""
    out: dict[str, Any] = {}
    for column in columns:
        values = [r.get(column) for r in rows]
        if column.endswith("_pct") or column == "median_days_to_decision":
            continue
        if values and all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            out[column] = sum(values)
    if out.get("records"):
        out["countersigned_pct"] = round(100 * out.get("countersigned", 0) / out["records"], 1)
    if out.get("joined"):
        matched = out.get("uploaded_and_joined")
        if matched is None and "missing_from_upload" in out:
            matched = out["joined"] - out["missing_from_upload"]
        if matched is not None:
            out["completeness_pct"] = round(100 * matched / out["joined"], 1)
    return out


def _page(canvas, doc, footer: str) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#4A5058"))
    canvas.drawString(doc.leftMargin, 7 * mm, footer)
    canvas.restoreState()


def _document(story: list, footer: str) -> bytes:
    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=9 * mm,
        bottomMargin=12 * mm,
    )
    width, height = doc.width, doc.height
    # one page: the story is shrunk to fit rather than spilling onto a second page
    frame = KeepInFrame(width, height, story, mode="shrink")
    doc.build([frame], onFirstPage=lambda c, d: _page(c, d, footer))
    return out.getvalue()


def _header(title: str, scope_label: str, academic_year: str, at: datetime) -> list:
    return [
        Paragraph(_esc(SYNTHETIC), _NOTE),
        Spacer(1, 2 * mm),
        Paragraph(_esc(title), _TITLE),
        Paragraph(
            _esc(f"{scope_label} · Academic year {academic_year} · Generated {generated_line(at)}"),
            _LINE,
        ),
        Spacer(1, 3 * mm),
    ]


def _footer(at: datetime, by: str) -> str:
    return f"Synthetic data. Generated {generated_line(at)} by {by}. Page 1 of 1."


def _table(
    columns: Sequence[str],
    body: Sequence[Sequence[Any]],
    width: float,
    *,
    total_row: bool = False,
    numeric: Sequence[bool] | None = None,
) -> Table:
    # a word is never split: a column is at least as wide as the longest word it prints
    weights = []
    for i, column in enumerate(columns):
        words = LABELS.get(column, column).split()
        words += [w for row in body for w in str(row[i]).split()]
        longest = max((len(w) for w in words), default=1)
        weights.append(WIDE.get(column, max(1.0, longest / 9)))
    unit = width / sum(weights)
    head = [Paragraph(_esc(LABELS.get(c, c)), _BOLD) for c in columns]
    cells = [[Paragraph(_esc(str(v)), _BASE) for v in row] for row in body]
    table = Table([head, *cells], colWidths=[w * unit for w in weights], repeatRows=1)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.25, _GRID),
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_FILL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
    ]
    if total_row:
        style.append(("BACKGROUND", (0, -1), (-1, -1), _HEADER_FILL))
    table.setStyle(TableStyle(style))
    return table


def to_pdf(
    spec: ReportSpec,
    rows: Sequence[Mapping[str, Any]],
    scope: ReportScope,
    academic_year: str,
    *,
    generated_at: datetime | None = None,
    by: str = "Countersign",
) -> bytes:
    """One A4 landscape page: the first 25 rows in the report's order, a totals row, and a
    line saying how many more rows the CSV or XLSX holds."""
    at = generated_at or _now()
    title, columns, scope_label = spec.title, spec.columns, scope.label
    shown = [c for c in columns if c != "academic_year"]
    deadline = next((str(r.get("deadline")) for r in rows if r.get("deadline")), None)
    body = [[_word(c, r.get(c), deadline) for c in shown] for r in rows[:PDF_ROWS]]
    totals = _totals(shown, rows)
    total_row = []
    for i, column in enumerate(shown):
        if column in totals:
            total_row.append(_word(column, totals[column]))
        else:
            total_row.append("Total" if i == 0 else "")
    story = _header(title, scope_label, academic_year, at)
    if rows:
        story.append(_table(shown, [*body, total_row], _content_width(), total_row=True))
    else:
        story.append(Paragraph(_esc(f"No data for {academic_year} in this scope."), _LINE))
    if len(rows) > PDF_ROWS:
        story += [
            Spacer(1, 2 * mm),
            Paragraph(_esc(f"and {len(rows) - PDF_ROWS} more rows in the CSV or XLSX"), _LINE),
        ]
    return _document(story, _footer(at, by))


def _content_width() -> float:
    return landscape(A4)[0] - 20 * mm


# ------------------------------------------------------------------- summary PDF


def _status_chart(by_status: Sequence[Mapping[str, Any]], width: float) -> Drawing:
    """Records by status as horizontal bars (bar charts only, D46)."""
    height = 30 * mm
    drawing = Drawing(width, height)
    chart = HorizontalBarChart()
    chart.x, chart.y = 62, 14  # room below for the value labels
    chart.width, chart.height = width - 80, height - 18
    counts = [int(s["count"]) for s in by_status]
    chart.data = [counts]
    chart.categoryAxis.categoryNames = [STATUS_WORDS[s["status"]] for s in by_status]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.reverseDirection = True
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(1, max(counts, default=0))
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 6
    chart.bars.strokeColor = None
    for i, s in enumerate(by_status):
        chart.bars[(0, i)].fillColor = STATUS_COLOURS[s["status"]]
    drawing.add(chart)
    return drawing


def _small(rows: Sequence[Sequence[Any]], widths: Sequence[float], head: Sequence[str]) -> Table:
    table = Table(
        [
            [Paragraph(_esc(h), _BOLD) for h in head],
            *[[Paragraph(_esc(str(v)), _BASE) for v in r] for r in rows],
        ],
        colWidths=list(widths),
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, _GRID),
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_FILL),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
            ]
        )
    )
    return table


def summary_pdf(
    data: Mapping[str, Any],
    scope: ReportScope,
    academic_year: str,
    *,
    generated_at: datetime | None = None,
    by: str = "Countersign",
) -> bytes:
    """One page: the KPIs, records by status (a bar chart with its table), open cases by type,
    the ten colleges with most unresolved cases, and the late and overdue colleges."""
    at = generated_at or _now()
    scope_label = scope.label
    width = _content_width()
    half = (width - 6 * mm) / 2
    k = data["kpis"]

    def num(value: Any) -> str:
        return "Not computed" if value is None else _word("x", value)

    kpi_cells = [
        ("Colleges", num(k["institutions"])),
        ("Approved seats", num(k["approved_seats"])),
        ("Admitted", num(k["admitted"])),
        ("Records", num(k["records"])),
        (
            "Countersigned",
            "Not computed" if k["countersigned_pct"] is None else f"{k['countersigned_pct']:.1f}%",
        ),
        ("Open cases", num(k["cases_open"])),
        (
            "Completeness",
            "Not computed" if k["completeness_pct"] is None else f"{k['completeness_pct']:.1f}%",
        ),
        ("Missing from uploads", num(k["missing_from_upload"])),
        ("Late / overdue", f"{k['colleges_late']} / {k['colleges_overdue']}"),
        ("New signals", num(k["signals_new"])),
    ]
    kpis = Table(
        [
            [Paragraph(_esc(label), _BASE) for label, _ in kpi_cells],
            [Paragraph(_esc(value), _HEAD) for _, value in kpi_cells],
        ],
        colWidths=[width / len(kpi_cells)] * len(kpi_cells),
    )
    kpis.setStyle(
        TableStyle(
            [("BOX", (0, 0), (-1, -1), 0.25, _GRID), ("BACKGROUND", (0, 0), (-1, -1), _HEADER_FILL)]
        )
    )

    by_status = data["records_by_status"]
    status_table = _small(
        [
            [
                STATUS_WORDS[s["status"]],
                f"{s['count']:,}",
                "" if s["pct"] is None else f"{s['pct']:.1f}%",
            ]
            for s in by_status
        ],
        [half * 0.5, half * 0.25, half * 0.25],
        ["Status", "Records", "Share"],
    )
    cases = _small(
        [[c["case_name"], f"{c['open']:,}"] for c in data["cases_by_type"]]
        or [["No open cases", ""]],
        [half * 0.75, half * 0.25],
        ["Open cases by type", "Open"],
    )
    top = _small(
        [
            [
                t["institution_name"],
                t["aicte_permanent_id"],
                t["cases_open"],
                t["under_review"],
                t["disputed"],
            ]
            for t in data["top_institutions"]
        ]
        or [["No unresolved cases", "", "", "", ""]],
        [half * 0.42, half * 0.19, half * 0.13, half * 0.13, half * 0.13],
        ["College", "AICTE id", "Open cases", "Under review", "Disputed"],
    )
    late = list(data["late_and_overdue"])
    late_rows = [
        [
            r["institution_name"],
            r["aicte_permanent_id"],
            WORDS["deadline_state"][r["deadline_state"]],
        ]
        for r in late[:10]
    ]
    if len(late) > 10:
        late_rows.append([f"and {len(late) - 10} more in the completeness report", "", ""])
    late_table = _small(
        late_rows or [["No late or overdue colleges", "", ""]],
        [half * 0.55, half * 0.25, half * 0.2],
        ["Late and overdue colleges", "AICTE id", f"Deadline {data['deadline']}"],
    )
    grid = Table(
        [
            [
                [
                    Paragraph("Records by status", _HEAD),
                    _status_chart(by_status, half),
                    status_table,
                ],
                [cases],
            ],
            [
                [Paragraph("Colleges with most unresolved cases", _HEAD), top],
                [Spacer(1, 4.5 * mm), late_table],
            ],
        ],
        colWidths=[half + 3 * mm, half + 3 * mm],
    )
    grid.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)])
    )
    story = _header(
        f"Countersign summary, {scope_label}, {academic_year}", scope_label, academic_year, at
    )
    story += [kpis, Spacer(1, 3 * mm), grid]
    return _document(story, _footer(at, by))
