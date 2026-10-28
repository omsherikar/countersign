import asyncio
import uuid

from sqlalchemy import select, text

from app.core import audit
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import AuditAction


async def _write(n: int) -> list[int]:
    seqs = []
    async with session_factory()() as session:
        for i in range(n):
            row = await audit.record(
                session,
                None,
                AuditAction.CREATE,
                "thing",
                uuid.uuid4(),
                before=None,
                after={"i": i, "nested": {"b": 2, "a": [1, 2]}},
            )
            seqs.append(row.seq)
        await session.commit()
    return seqs


async def test_chain_links_and_verifies(clean_db):
    seqs = await _write(3)
    assert seqs == [1, 2, 3]
    async with session_factory()() as session:
        rows = (await session.execute(select(AuditLog).order_by(AuditLog.seq))).scalars().all()
        assert rows[0].prev_hash is None
        assert rows[1].prev_hash == rows[0].hash
        assert rows[2].prev_hash == rows[1].hash
        assert all(len(r.hash) == 64 for r in rows)
        assert await audit.verify_chain(session) == (True, 3, None)


async def test_tampered_payload_is_detected(clean_db):
    await _write(4)
    async with session_factory()() as session:
        await session.execute(
            text("""UPDATE audit_log SET "after" = '{"i": 99}'::jsonb WHERE seq = 2""")
        )
        await session.commit()
    async with session_factory()() as session:
        assert await audit.verify_chain(session) == (False, 4, 2)


async def test_deleted_row_breaks_the_chain(clean_db):
    await _write(4)
    async with session_factory()() as session:
        await session.execute(text("DELETE FROM audit_log WHERE seq = 3"))
        await session.commit()
    async with session_factory()() as session:
        ok, length, broken = await audit.verify_chain(session)
        assert (ok, length, broken) == (False, 3, 4)


async def test_record_read_dedupes_and_batches(clean_db):
    ids = [uuid.uuid4(), uuid.uuid4()]
    async with session_factory()() as session:
        rows = await audit.record_read(session, None, "student", ids + [ids[0]])
        await session.commit()
    assert [r.entity_id for r in rows] == ids
    assert all(r.action is AuditAction.READ for r in rows)
    async with session_factory()() as session:
        assert await audit.verify_chain(session) == (True, 2, None)


async def test_concurrent_writers_keep_the_chain_serial(clean_db):
    async def writer(k: int) -> None:
        async with session_factory()() as session:
            for _ in range(5):
                await audit.record(session, None, AuditAction.UPDATE, f"w{k}", after={"k": k})
            await session.commit()

    await asyncio.gather(*(writer(k) for k in range(4)))
    async with session_factory()() as session:
        assert await audit.verify_chain(session) == (True, 20, None)


def test_canonical_json_is_order_independent():
    a = audit.canonical_json({"b": 1, "a": {"y": 2, "x": 1}})
    b = audit.canonical_json({"a": {"x": 1, "y": 2}, "b": 1})
    assert a == b == '{"a":{"x":1,"y":2},"b":1}'
