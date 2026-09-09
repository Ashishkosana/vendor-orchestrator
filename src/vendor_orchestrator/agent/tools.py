"""Tool surface the agent loop is allowed to use.

``call_vendors`` fans out through orchestration so retries and idempotency
keys stay out of the decision policy.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.models import Case, VendorCall
from vendor_orchestrator.orchestration.fanout import fan_out_vendors
from vendor_orchestrator.vendors.base import VendorResult
from vendor_orchestrator.vendors.registry import implemented_vendor_names


class Toolbelt:
    def __init__(self, session: AsyncSession, case: Case) -> None:
        self._session = session
        self._case = case

    def available_vendors(self) -> list[str]:
        return implemented_vendor_names()

    async def call_vendors(
        self,
        vendor_names: Sequence[str],
        extra_payload: dict[str, Any] | None = None,
    ) -> list[VendorResult]:
        available = set(self.available_vendors())
        unknown = [name for name in vendor_names if name not in available]
        if unknown:
            raise KeyError(
                f"Vendor(s) {unknown!r} are not registered. "
                f"Available: {self.available_vendors()}"
            )
        payload = dict(self._case.payload)
        if extra_payload:
            payload.update(extra_payload)
        return await fan_out_vendors(
            self._session, self._case.id, vendor_names, payload
        )

    async def call_vendor(
        self,
        vendor_name: str,
        extra_payload: dict[str, Any] | None = None,
    ) -> VendorCall:
        results = await self.call_vendors([vendor_name], extra_payload=extra_payload)
        if not results:
            raise RuntimeError(f"fan-out returned no result for {vendor_name}")
        stored = await self._session.execute(
            select(VendorCall)
            .where(
                VendorCall.case_id == self._case.id,
                VendorCall.vendor_name == vendor_name,
            )
            .order_by(VendorCall.created_at.desc())
        )
        row = stored.scalars().first()
        if row is None:
            raise RuntimeError(f"no persisted vendor_calls row for {vendor_name}")
        return row
