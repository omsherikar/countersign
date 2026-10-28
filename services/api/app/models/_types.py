"""Column type helpers shared by the model modules."""

from __future__ import annotations

import enum

import sqlalchemy as sa


def pg_enum(py_enum: type[enum.Enum], name: str) -> sa.Enum:
    """Postgres ENUM named `<table>_<column>` carrying the wire values."""
    return sa.Enum(
        py_enum,
        name=name,
        native_enum=True,
        create_constraint=False,
        values_callable=lambda e: [m.value for m in e],
    )
