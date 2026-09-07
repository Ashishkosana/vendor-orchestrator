from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class VendorResult:
    vendor_name: str
    ok: bool
    body: dict[str, Any]
    http_status: int | None = None


class VendorClient(Protocol):
    name: str

    async def invoke(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> VendorResult: ...
