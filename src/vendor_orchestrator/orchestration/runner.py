"""Milestone-1 create path: call Alpha, persist the call row, update status.

This is infrastructure. It does **not** choose vendors or decide
escalate vs auto-resolve — that belongs in ``agent.loop``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.models import Case, CaseStatus, VendorCall
from vendor_orchestrator.orchestration.fanout import (
    DEFAULT_MAX_ATTEMPTS,
    fan_out_vendors,
)


async def call_vendor(
    session: AsyncSession,
    case: Case,
    vendor_name: str,
    *,
    extra_payload: dict[str, Any] | None = None,
    attempt: int = 1,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> VendorCall:
    """Invoke via fan-out (retries + idempotency) and return the latest row."""
    _ = attempt  # attempt numbers are assigned inside fan-out
    payload = dict(case.payload)
    if extra_payload:
        payload.update(extra_payload)

    await fan_out_vendors(
        session,
        case.id,
        [vendor_name],
        payload,
        max_attempts=max_attempts,
        backoff_seconds=(0.0, 0.0, 0.0),
    )
    result = await session.execute(
        select(VendorCall)
        .where(VendorCall.case_id == case.id, VendorCall.vendor_name == vendor_name)
        .order_by(VendorCall.created_at.desc())
    )
    row = result.scalars().first()
    if row is None:
        raise RuntimeError(
            f"fan-out did not persist a vendor_calls row for {vendor_name}"
        )
    return row


async def run_milestone1(session: AsyncSession, case: Case) -> Case:
    """Create-path happy path: call Alpha, record the result, update case status.

    Leaves ``decision`` null. An agent decision is a later call to ``decide_case``.
    """
    results = await fan_out_vendors(
        session,
        case.id,
        ["alpha"],
        dict(case.payload),
        backoff_seconds=(0.0, 0.0, 0.0),
    )
    ok = bool(results) and results[0].ok
    case.status = CaseStatus.VENDOR_CHECKED if ok else CaseStatus.VENDOR_FAILED
    await session.flush()
    return case
