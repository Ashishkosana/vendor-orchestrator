"""Shared HTTP client for in-process (ASGI) or sidecar mock vendors."""

from __future__ import annotations

from typing import Any

import httpx

from vendor_orchestrator.config import get_settings
from vendor_orchestrator.vendors.base import VendorResult
from vendor_orchestrator.vendors.mock_app import mock_vendor_app


class MockHttpVendorClient:
    def __init__(
        self,
        name: str,
        path: str,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.name = name
        self._path = path
        self._base_url = base_url.rstrip("/") if base_url else None
        settings = get_settings()
        self._timeout = httpx.Timeout(
            timeout_seconds
            if timeout_seconds is not None
            else settings.vendor_http_timeout_seconds
        )

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
                transport=transport,
                base_url="http://mock-vendor",
                timeout=self._timeout,
            ) as client:
                response = await client.post(self._path, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = await client.post(self._path, json=payload, headers=headers)

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
