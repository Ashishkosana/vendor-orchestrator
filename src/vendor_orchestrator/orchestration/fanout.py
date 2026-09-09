"""Multi-vendor fan-out: concurrent calls, transient retries, idempotency reuse.

Vendor *selection* stays in ``agent.loop``. This module only executes the
chosen names against mock HTTP vendors and persists every attempt.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.models import VendorCall, VendorCallStatus
from vendor_orchestrator.orchestration.idempotency import build_idempotency_key
from vendor_orchestrator.vendors import get_vendor
from vendor_orchestrator.vendors.base import VendorResult

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = (0.2, 0.8, 2.0)

_RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.TransportError,
    TimeoutError,
    OSError,
    ConnectionError,
)


def is_retryable(http_status: int | None, error: BaseException | None) -> bool:
    """Retry timeouts, 429, and 5xx. Do not retry ordinary 4xx validation errors."""
    if http_status in {408, 429} or (http_status is not None and http_status >= 500):
        return True
    return error is not None and isinstance(error, _RETRYABLE_EXCEPTIONS)


def _dedupe_names(vendor_names: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for name in vendor_names:
        if name in seen:
            continue
        seen.add(name)
        unique.append(name)
    return unique


def _result_from_row(row: VendorCall) -> VendorResult:
    return VendorResult(
        vendor_name=row.vendor_name,
        ok=row.status == VendorCallStatus.SUCCESS,
        body=dict(row.response_payload or {}),
        http_status=200 if row.status == VendorCallStatus.SUCCESS else None,
    )


async def _find_successful_call(
    session: AsyncSession, idempotency_key: str
) -> VendorCall | None:
    result = await session.execute(
        select(VendorCall)
        .where(
            VendorCall.idempotency_key == idempotency_key,
            VendorCall.status == VendorCallStatus.SUCCESS,
        )
        .order_by(VendorCall.created_at.desc())
    )
    return result.scalars().first()


def _backoff_delay(attempt: int, backoff_seconds: Sequence[float]) -> float:
    if not backoff_seconds:
        return 0.0
    index = min(attempt - 1, len(backoff_seconds) - 1)
    return float(backoff_seconds[index])


async def fan_out_vendors(
    session: AsyncSession,
    case_id: uuid.UUID,
    vendor_names: Sequence[str],
    payload: dict[str, Any],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: Sequence[float] | None = None,
) -> list[VendorResult]:
    """Call several vendors concurrently, persist each attempt, honor idempotency keys.

    1. Deduplicate ``vendor_names`` while preserving order.
    2. For each vendor, compute ``build_idempotency_key(case_id, name)``.
       If a successful ``VendorCall`` with that key already exists, reuse it
       (do not re-hit the mock).
    3. Fan out concurrently (``asyncio.gather``). Session writes are locked.
    4. Retry transient failures only (timeouts, 429, 5xx). Cap at
       ``max_attempts`` with exponential backoff.
    5. Persist every attempt on ``vendor_calls`` (attempt = 1, 2, ...).
    6. Return one ``VendorResult`` per requested vendor (last attempt, or reuse).
    """
    names = _dedupe_names(vendor_names)
    if not names:
        return []

    delays = (
        tuple(backoff_seconds)
        if backoff_seconds is not None
        else DEFAULT_BACKOFF_SECONDS
    )
    write_lock = asyncio.Lock()

    async def _invoke_one(name: str) -> VendorResult:
        key = build_idempotency_key(case_id, name)
        async with write_lock:
            existing = await _find_successful_call(session, key)
        if existing is not None:
            return _result_from_row(existing)

        last: VendorResult | None = None
        for attempt in range(1, max_attempts + 1):
            invoke_error: BaseException | None = None
            try:
                client = get_vendor(name)
                last = await client.invoke(payload, idempotency_key=key)
            except KeyError as exc:
                last = VendorResult(
                    vendor_name=name,
                    ok=False,
                    body={"error": str(exc), "error_type": "KeyError"},
                    http_status=None,
                )
                invoke_error = exc
            except Exception as exc:  # noqa: BLE001 — persist, then classify
                invoke_error = exc
                last = VendorResult(
                    vendor_name=name,
                    ok=False,
                    body={"error": str(exc), "error_type": type(exc).__name__},
                    http_status=None,
                )

            async with write_lock:
                session.add(
                    VendorCall(
                        case_id=case_id,
                        vendor_name=name,
                        status=(
                            VendorCallStatus.SUCCESS
                            if last.ok
                            else VendorCallStatus.FAILED
                        ),
                        request_payload=dict(payload),
                        response_payload=last.body,
                        idempotency_key=key,
                        attempt=attempt,
                    )
                )
                await session.flush()

            if last.ok:
                return last
            if attempt >= max_attempts or not is_retryable(
                last.http_status, invoke_error
            ):
                return last

            delay = _backoff_delay(attempt, delays)
            if delay > 0:
                await asyncio.sleep(delay)

        assert last is not None
        return last

    return list(await asyncio.gather(*(_invoke_one(name) for name in names)))
