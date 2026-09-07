from vendor_orchestrator.config import get_settings
from vendor_orchestrator.vendors.alpha import AlphaVendorClient
from vendor_orchestrator.vendors.base import VendorClient

# Milestone 1: only Alpha is a real HTTP client.
# Later milestones register additional mock vendors here.
_IMPLEMENTED: dict[str, type[AlphaVendorClient]] = {
    "alpha": AlphaVendorClient,
}


def implemented_vendor_names() -> list[str]:
    return sorted(_IMPLEMENTED)


def get_vendor(name: str) -> VendorClient:
    if name not in _IMPLEMENTED:
        raise KeyError(
            f"Vendor {name!r} is not implemented. "
            f"Available: {implemented_vendor_names()}"
        )
    settings = get_settings()
    if name == "alpha":
        return AlphaVendorClient(base_url=settings.mock_vendor_alpha_url)
    raise KeyError(name)
