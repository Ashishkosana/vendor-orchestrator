"""Working milestone-1 orchestration: one vendor, persist the call row.

This is infrastructure. It does **not** choose vendors or decide
escalate vs auto-resolve — that belongs in ``agent.loop``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.models import Case, CaseStatus, VendorCall, VendorCallStatus
from vendor_orchestrator.orchestration.idempotency import build_idempotency_key
from vendor_orchestrator.vendors import get_vendor
from vendor_orchestrator.vendors.base import VendorResult


async def call_vendor(
    session: AsyncSession,
    case: Case,
    vendor_name: str,
    *,
    extra_payload: dict[str, Any] | None = None,
    attempt: int = 1,
) -> VendorCall:
    """Invoke a registered vendor client and persist a ``VendorCall`` row."""
    payload = dict(case.payload)
    if extra_payload:
        payload.update(extra_payload)

    key = build_idempotency_key(case.id, vendor_name)
    client = get_vendor(vendor_name)
    result: VendorResult = await client.invoke(payload, idempotency_key=key)

    row = VendorCall(
        case_id=case.id,
        vendor_name=vendor_name,
        status=VendorCallStatus.SUCCESS if result.ok else VendorCallStatus.FAILED,
        request_payload=payload,
        response_payload=result.body,
        idempotency_key=key,
        attempt=attempt,
    )
    session.add(row)
    await session.flush()
    return row


async def run_milestone1(session: AsyncSession, case: Case) -> Case:
    """Create-path happy path: call Alpha, record the result, update case status.

    Leaves ``decision`` null. An agent decision is a later milestone.
    """
    try:
        row = await call_vendor(session, case, "alpha")
    except Exception as exc:  # noqa: BLE001 — persist failure, do not drop the case
        session.add(
            VendorCall(
                case_id=case.id,
                vendor_name="alpha",
                status=VendorCallStatus.FAILED,
                request_payload=dict(case.payload),
                response_payload={"error": str(exc)},
                idempotency_key=build_idempotency_key(case.id, "alpha"),
                attempt=1,
            )
        )
        case.status = CaseStatus.VENDOR_FAILED
        await session.flush()
        return case

    case.status = (
        CaseStatus.VENDOR_CHECKED
        if row.status == VendorCallStatus.SUCCESS
        else CaseStatus.VENDOR_FAILED
    )
    await session.flush()
    return case
