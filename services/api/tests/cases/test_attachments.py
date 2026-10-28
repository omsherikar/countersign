"""Attachment names and types, without a database or a request."""

from __future__ import annotations

from app.cases import attachments

PDF = b"%PDF-1.4\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
EXE = b"MZ\x90\x00\x03" + b"\x00" * 64


def test_names_are_cleaned_and_types_sniffed() -> None:
    assert attachments.clean_filename("C:\\Users\\reg\\..\\scan.pdf") == "scan.pdf"
    assert attachments.clean_filename("../../etc/passwd") == "passwd"
    assert attachments.clean_filename("bad\x00name\n.pdf") == "badname.pdf"
    assert attachments.clean_filename("..") == "attachment"
    assert attachments.clean_filename(None) == "attachment"
    assert len(attachments.clean_filename("a" * 300 + ".pdf")) == 120
    assert attachments.sniff(PDF) == "application/pdf"
    assert attachments.sniff(PNG) == "image/png"
    assert attachments.sniff(JPEG) == "image/jpeg"
    assert attachments.sniff(EXE) is None
    assert attachments.sniff(b"%PD") is None
