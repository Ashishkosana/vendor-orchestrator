"""HTTP client for mock vendor Alpha.

Uses ASGI transport against the in-process mock app by default so Docker
Compose only needs ``app + Postgres``. Set ``MOCK_VENDOR_ALPHA_URL`` to point
at a sidecar later without changing call sites.
"""

from vendor_orchestrator.vendors.http import MockHttpVendorClient


class AlphaVendorClient(MockHttpVendorClient):
    name = "alpha"

    def __init__(self, *, base_url: str | None = None) -> None:
        super().__init__("alpha", "/alpha", base_url=base_url)
