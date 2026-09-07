"""HTTP client for mock vendor Alpha.

Uses ASGI transport against the in-process mock app by default so Docker
Compose only needs ``app + Postgres``. Set ``MOCK_VENDOR_ALPHA_URL`` to point
at a sidecar later without changing call sites.
"""

from __future__ import annotations

from typing import Any

import httpx

from vendor_orchestrator.vendors.base import VendorResult
from vendor_orchestrator.vendors.mock_app import mock_vendor_app


class AlphaVendorClient:
    name = "alpha"

    def __init__(self, *, base_url: str | None = None) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None

    async def invoke(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> VendorResult:
        headers = {"Idempotency-Key": idempotency_key}
        if self._base_url is None:
            transport = httpx.ASGITransport(app=mock_vendor_app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://mock-vendor"
            ) as client:
                response = await client.post("/alpha", json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(base_url=self._base_url) as client:
                response = await client.post("/alpha", json=payload, headers=headers)

        body: dict[str, Any]
        try:
            parsed = response.json()
            body = parsed if isinstance(parsed, dict) else {"raw": parsed}
        except ValueError:
            body = {"raw": response.text}

        return VendorResult(
            vendor_name=self.name,
            ok=response.is_success,
            body=body,
            http_status=response.status_code,
        )
