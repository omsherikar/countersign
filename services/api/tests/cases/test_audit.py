"""The audit list's new filters and columns, and the demo tamper command (D29, §A3.23).

The tamper test breaks the chain on purpose; the module's world is truncated afterwards,
so later tests start from a clean chain."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import func, select

from app.core import audit_tamper
from app.core.config import get_settings
from app.db.session import session_factory
from app.models.audit import AuditLog
from tests.cases.conftest import new_flag, read_entry

API_ROOT = Path(__file__).resolve().parents[2]


async def test_audit_filters_and_columns(cw, logins) -> None:
    admin = await logins("admin@aicte.demo")
    flag_id = await new_flag(cw)
    await (await logins("ro.west@aicte.demo")).get(f"/flags/{flag_id}")
    await read_entry("student", cw.ravi_student, after={"via": "verifier", "ip_hash": "ab"})

    by_entity = (await admin.get("/admin/audit", params={"entity_id": str(cw.ravi_student)})).json()
    assert by_entity["total"] >= 2
    assert {i["entity_id"] for i in by_entity["items"]} == {str(cw.ravi_student)}
    public = by_entity["items"][0]
    assert (public["actor_id"], public["actor_role"], public["via"]) == (None, None, "verifier")
    officer = next(i for i in by_entity["items"] if i["actor_id"])
    assert officer["actor_role"] == "RO_OFFICER" and officer["via"] is None
    assert officer["actor_email"] == "ro.west@aicte.demo"

    reads = (await admin.get("/admin/audit", params={"action": "READ"})).json()
    assert reads["total"] >= 2 and {i["action"] for i in reads["items"]} == {"READ"}
    bad = await admin.get("/admin/audit", params={"action": "PEEK"})
    assert bad.status_code == 422

    everything = (await admin.get("/admin/audit", params={"page_size": 200})).json()
    top = everything["items"][0]["seq"]
    opened = (await admin.get("/admin/audit", params={"seq_from": top - 3})).json()
    assert opened["items"][0]["seq"] == top - 3
    assert all(i["seq"] <= top - 3 for i in opened["items"])
    assert opened["total"] == everything["total"] - 3
    combined = (
        await admin.get(
            "/admin/audit",
            params={"entity_type": "flag", "action": "CREATE", "entity_id": str(flag_id)},
        )
    ).json()
    assert combined["total"] == 1 and combined["items"][0]["entity_id"] == str(flag_id)


def run_tamper(seq: int, demo_mode: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DEMO_MODE": demo_mode}
    return subprocess.run(
        [sys.executable, "-m", "app.core.audit_tamper", "--seq", str(seq)],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


async def test_tamper_refuses_without_demo_mode(cw, monkeypatch, capsys) -> None:
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert audit_tamper.main(["--seq", "1"]) == 2
    assert capsys.readouterr().err.strip() == "audit-tamper runs only when DEMO_MODE=true."

    refused = run_tamper(1, "false")
    assert refused.returncode == 2
    assert refused.stderr.strip() == "audit-tamper runs only when DEMO_MODE=true."
    async with session_factory()() as session:
        tampered = (
            await session.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.after["tampered"].astext == "true")
            )
        ).scalar_one()
    assert tampered == 0


async def test_after_tampering_verify_reports_that_entry(cw, logins) -> None:
    admin = await logins("admin@aicte.demo")
    await new_flag(cw)
    assert (await admin.get("/admin/audit/verify")).json()["ok"] is True
    async with session_factory()() as session:
        last = (await session.execute(select(func.max(AuditLog.seq)))).scalar_one()
    seq = last - 2

    unknown = run_tamper(last + 1000, "true")
    assert unknown.returncode == 2 and f"no audit entry {last + 1000}" in unknown.stderr

    done = run_tamper(seq, "true")
    assert done.returncode == 0, done.stderr
    assert f"Changed audit entry {seq}." in done.stdout
    async with session_factory()() as session:
        entry = await session.get(AuditLog, seq)
        await session.refresh(entry)
        assert entry.after["tampered"] is True
        # the command writes no entry of its own
        assert (await session.execute(select(func.max(AuditLog.seq)))).scalar_one() == last

    verify = (await admin.get("/admin/audit/verify")).json()
    assert verify["ok"] is False and verify["first_broken_seq"] == seq
    page = (await admin.get("/admin/audit", params={"seq_from": seq + 10})).json()
    assert seq in [i["seq"] for i in page["items"]]
