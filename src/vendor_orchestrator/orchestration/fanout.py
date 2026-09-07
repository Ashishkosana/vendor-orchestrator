"""Multi-vendor fan-out — scaffold only.

YOU IMPLEMENT: concurrent vendor calls, retries, and idempotency reuse.
Do not pretend this is production-hardened until you can defend the policy.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.vendors.base import VendorResult

# YOU IMPLEMENT: tune these once you own the retry policy.
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = (0.2, 0.8, 2.0)


async def fan_out_vendors(
    session: AsyncSession,
    case_id: uuid.UUID,
    vendor_names: Sequence[str],
    payload: dict[str, Any],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> list[VendorResult]:
    """Call several vendors, persist each attempt, honor idempotency keys.

    Suggested contract (YOU IMPLEMENT — do not leave this as a silent no-op):

    1. Deduplicate ``vendor_names`` while preserving order.
    2. For each vendor, compute ``build_idempotency_key(case_id, name)``.
       If a successful ``VendorCall`` with that key already exists, reuse it
       (do not bill / re-hit the mock).
    3. Fan out **concurrently** (``asyncio.gather`` or a task group).
    4. Retry **transient** failures only (timeouts, 429, 5xx). Do not retry
       4xx validation errors. Cap at ``max_attempts`` with exponential backoff
       (see ``DEFAULT_BACKOFF_SECONDS``).
    5. Persist every attempt on ``vendor_calls`` (attempt = 1, 2, ...).
    6. Return one ``VendorResult`` per requested vendor (last attempt).

    This is orchestration, not an agent. Vendor *selection* stays in
    ``agent.loop``.
    """
    raise NotImplementedError(
        "YOU IMPLEMENT: multi-vendor fan-out with retries and idempotency keys "
        f"(case_id={case_id}, vendors={list(vendor_names)}, "
        f"max_attempts={max_attempts}, payload_keys={sorted(payload)})"
    )


def is_retryable(http_status: int | None, error: BaseException | None) -> bool:
    """YOU IMPLEMENT: classify retryable vs terminal vendor failures."""
    raise NotImplementedError(
        "YOU IMPLEMENT: retry classification "
        f"(http_status={http_status}, error={type(error).__name__ if error else None})"
    )
