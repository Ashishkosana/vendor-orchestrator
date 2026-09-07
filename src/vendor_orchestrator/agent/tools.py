"""Tool surface the agent loop is allowed to use.

Working pieces (safe to call today):
- ``available_vendors()`` — names with a real client (currently ``alpha``)
- ``call_vendor(name)`` — HTTP invoke + persist via the milestone-1 runner

YOU IMPLEMENT later: route multi-vendor calls through ``fan_out_vendors``
so retries and idempotency live in orchestration, not in the agent prompt.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.models import Case, VendorCall
from vendor_orchestrator.orchestration.runner import call_vendor as persist_vendor_call
from vendor_orchestrator.vendors.registry import implemented_vendor_names


class Toolbelt:
    def __init__(self, session: AsyncSession, case: Case) -> None:
        self._session = session
        self._case = case

    def available_vendors(self) -> list[str]:
        return implemented_vendor_names()

    async def call_vendor(
        self,
        vendor_name: str,
        extra_payload: dict[str, Any] | None = None,
    ) -> VendorCall:
        if vendor_name not in self.available_vendors():
            raise KeyError(
                f"Vendor {vendor_name!r} is not registered. "
                f"Available: {self.available_vendors()}"
            )
        return await persist_vendor_call(
            self._session, self._case, vendor_name, extra_payload=extra_payload
        )
