"""Change one audit entry so the demo can show the chain break (D29).

    python -m app.core.audit_tamper --seq N

Runs only when DEMO_MODE=true. It adds `"tampered": true` to the stored `after` of entry
N without recomputing any hash, so GET /admin/audit/verify reports the chain broken at N.
It writes no audit entry of its own; `make demo-reset` rebuilds a clean chain.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import dispose_engine, session_factory

REFUSED = "audit-tamper runs only when DEMO_MODE=true."
# `after` may be SQL NULL or a JSON null (how the ORM stores None); both start from {}
TAMPER = text(
    """UPDATE audit_log
    SET "after" = CASE WHEN jsonb_typeof("after") = 'object' THEN "after" ELSE '{}'::jsonb END
        || '{"tampered": true}'::jsonb
    WHERE seq = :seq"""
)


async def tamper(seq: int) -> bool:
    """Change entry `seq` in its own short transaction; False when there is no such entry."""
    async with session_factory()() as session:
        result = await session.execute(TAMPER, {"seq": seq})
        if result.rowcount == 0:
            await session.rollback()
            return False
        await session.commit()
        return True


async def _run(seq: int) -> bool:
    try:
        return await tamper(seq)
    finally:
        await dispose_engine()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit-tamper", description="Change one audit entry to show the chain break."
    )
    parser.add_argument("--seq", type=int, required=True, help="the entry to change")
    args = parser.parse_args(argv)
    if not get_settings().demo_mode:
        print(REFUSED, file=sys.stderr)
        return 2
    if not asyncio.run(_run(args.seq)):
        print(f"There is no audit entry {args.seq}.", file=sys.stderr)
        return 2
    print(f"Changed audit entry {args.seq}. Verifying the chain now reports it broken there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
