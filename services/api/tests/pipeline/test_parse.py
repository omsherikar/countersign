import io
from datetime import date, datetime

import pytest
from openpyxl import Workbook

from app.engine.upload.parse import cell_text, normalise_header, parse_rows, parse_upload
from app.engine.upload.types import UPLOAD_COLUMNS, UploadFileError

HEADER = "name,dob,programme_code,year_of_study,admission_route,category"


def _csv(text: str, *, bom: bool = False) -> bytes:
    data = text.encode("utf-8")
    return b"\xef\xbb\xbf" + data if bom else data


def _xlsx(rows: list[list]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "students"
    for row in rows:
        sheet.append(row)
    workbook.create_sheet("ignored").append(["not", "read"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _error(data: bytes, filename: str = "f.csv", **kwargs) -> UploadFileError:
    with pytest.raises(UploadFileError) as caught:
        parse_upload(data, filename, **kwargs)
    return caught.value


def test_header_normalisation():
    assert normalise_header("  Programme Code ") == "programme_code"
    assert normalise_header("Year-Of-Study") == "year_of_study"
    assert normalise_header("APAAR ID") == "apaar_id"


def test_csv_with_bom_extra_columns_and_blank_lines():
    text = (
        "Name,DOB,Programme Code,year-of-study,admission_route,category,Roll No,notes\r\n"
        "Ravi Kumar Sharma,2007-03-21,CSE,1,COUNSELLING,GENERAL,R1,x\r\n"
        "\r\n"
        ",,,,,,,\r\n"
        '"Shaikh, Mohammed Irfan",2006-11-14,CSE,1,MANAGEMENT,OTHER,R2,y\r\n'
    )
    parsed = parse_upload(_csv(text, bom=True), "ABC.CSV")
    assert parsed.kind == "csv" and parsed.total_rows == 2
    assert parsed.ignored_columns == ["Roll No", "notes"]
    first, second = parsed.rows
    assert first.row_no == 2 and second.row_no == 5  # spreadsheet numbering survives blanks
    assert first.values["name"] == "Ravi Kumar Sharma" and first.values["year_of_study"] == "1"
    assert set(first.values) == set(UPLOAD_COLUMNS)
    assert first.values["apaar_id"] == "" and first.values["status"] == ""
    assert second.values["name"] == "Shaikh, Mohammed Irfan"


def test_short_rows_fill_blank_and_long_rows_are_cut():
    text = f"{HEADER}\nA,2007-01-01\nB,2007-01-01,CSE,1,SPOT,SC,extra\n"
    parsed = parse_upload(_csv(text), "f.csv")
    assert parsed.rows[0].values["programme_code"] == ""
    assert parsed.rows[1].values["category"] == "SC"


def test_missing_and_duplicate_headers():
    missing = _error(_csv("apaar_id,programme_code,year_of_study,admission_route,category\n1,2\n"))
    assert missing.code == "UPLOAD_HEADER_INVALID"
    assert missing.message == "The file is missing required columns: name, dob."
    assert missing.details == {"missing_columns": ["name", "dob"], "duplicate_columns": []}

    twice = _error(_csv(f"{HEADER},Name\nA,2007-01-01,CSE,1,SPOT,SC,B\n"))
    assert twice.code == "UPLOAD_HEADER_INVALID"
    assert twice.message == "The column name appears more than once."
    assert twice.details == {"missing_columns": [], "duplicate_columns": ["name"]}


def test_empty_and_too_many_rows():
    empty = _error(_csv(f"{HEADER}\n\n,,,,,\n"))
    assert (empty.code, empty.message) == ("UPLOAD_EMPTY", "The file has a header but no rows.")
    nothing = _error(b"")
    assert nothing.code == "UPLOAD_HEADER_INVALID"

    body = "".join(f"P{i},2007-01-01,CSE,1,SPOT,SC\n" for i in range(4))
    assert parse_upload(_csv(HEADER + "\n" + body), "f.csv", max_rows=4).total_rows == 4
    too_many = _error(_csv(HEADER + "\n" + body), max_rows=3)
    assert too_many.code == "TOO_MANY_ROWS"
    assert too_many.message == "The file has more than 3 rows. Split it and upload each part."
    assert (
        _error(_csv(HEADER + "\n" + body * 12501), max_rows=50000).message
        == "The file has more than 50,000 rows. Split it and upload each part."
    )


def test_unreadable_files():
    latin = _error("name,dob\nJosé,2007\n".encode("latin-1"))
    assert latin.code == "UNSUPPORTED_FILE_TYPE"
    assert latin.message == "The file is not UTF-8 text. Save it as CSV UTF-8 and upload it again."
    assert _error(b"PK\x03\x04garbage", "f.xlsx").message == (
        "The file could not be read as CSV or XLSX."
    )
    nul = _error(b"name\x00,dob\n", "f.csv")
    assert nul.message == "The file could not be read as CSV or XLSX."
    assert _error(b"a,b", "f.txt").code == "UNSUPPORTED_FILE_TYPE"


def test_xlsx_first_sheet_with_typed_cells(tmp_path):
    data = _xlsx(
        [
            ["APAAR ID", "Name", "DOB", "Programme Code", "Year of Study", "Admission Route",
             "Category", "Mobile", "Admission Date", "Remarks"],
            [123456784417, "Ravi Kumar Sharma", datetime(2007, 3, 21), "CSE", 1.0, "Counselling",
             "General", 9876504521, date(2026, 8, 2), "ok"],
            [None] * 10,
            [None, "Asha Patil", "2007-11-02", "IT", 2, "spot", "OBC", None, None, None],
        ]
    )  # fmt: skip
    path = tmp_path / "upload.xlsx"
    path.write_bytes(data)
    parsed = parse_upload(path, path.name)
    assert parsed.kind == "xlsx" and parsed.ignored_columns == ["Remarks"]
    ravi, asha = parsed.rows
    assert (ravi.row_no, asha.row_no) == (2, 4)
    assert ravi.values["apaar_id"] == "123456784417"
    assert ravi.values["dob"] == "2007-03-21" and ravi.values["year_of_study"] == "1"
    assert ravi.values["mobile"] == "9876504521" and ravi.values["admission_date"] == "2026-08-02"
    assert asha.values["year_of_study"] == "2" and asha.values["mobile"] == ""


def test_xlsx_bad_header_is_rejected():
    assert _error(_xlsx([["name", "dob"], ["A", "2007-01-01"]]), "f.xlsx").details[
        "missing_columns"
    ] == ["programme_code", "year_of_study", "admission_route", "category"]


def test_json_rows():
    parsed = parse_rows(
        [
            {
                "Name": "Ravi",
                "dob": "2007-03-21",
                "year_of_study": 1,
                "sis_id": 7,
                "apaar_id": None,
            },
            {"name": None, "dob": ""},
            {"name": "Asha", "year_of_study": 2.0, "SIS ID": "x"},
        ]
    )
    assert parsed.kind == "json" and parsed.total_rows == 2
    assert [r.row_no for r in parsed.rows] == [1, 3]
    assert parsed.rows[0].values["year_of_study"] == "1" and parsed.rows[0].values["apaar_id"] == ""
    assert parsed.rows[1].values["year_of_study"] == "2"
    assert parsed.ignored_columns == ["sis_id", "SIS ID"]
    with pytest.raises(UploadFileError) as caught:
        parse_rows([{"name": "A", "Name": "B"}])
    assert caught.value.message == "The column name appears more than once."
    with pytest.raises(UploadFileError) as caught:
        parse_rows([{"name": None}])
    assert caught.value.code == "UPLOAD_EMPTY"
    with pytest.raises(UploadFileError) as caught:
        parse_rows([{"name": "A"}, {"name": "B"}], max_rows=1)
    assert caught.value.code == "TOO_MANY_ROWS"


def test_cell_text():
    assert cell_text(None) == "" and cell_text(True) == "true" and cell_text(2.5) == "2.5"
    assert cell_text(" x ") == "x" and cell_text(datetime(2026, 1, 2, 10, 0)) == "2026-01-02"
