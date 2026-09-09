"""HTTP client for mock vendor Beta (second in-process vendor for fan-out)."""

from vendor_orchestrator.vendors.http import MockHttpVendorClient


class BetaVendorClient(MockHttpVendorClient):
    name = "beta"

    def __init__(self, *, base_url: str | None = None) -> None:
        super().__init__("beta", "/beta", base_url=base_url)
