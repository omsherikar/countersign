"""Approval versions (D41): AICTE revises an approval, and the Seat Ledger follows it."""

from app.approvals.service import add_version, covers, versions

__all__ = ["add_version", "covers", "versions"]
