from vendor_orchestrator.config import get_settings
from vendor_orchestrator.vendors.alpha import AlphaVendorClient
from vendor_orchestrator.vendors.base import VendorClient
from vendor_orchestrator.vendors.beta import BetaVendorClient


def implemented_vendor_names() -> list[str]:
    return ["alpha", "beta"]


def get_vendor(name: str) -> VendorClient:
    settings = get_settings()
    if name == "alpha":
        return AlphaVendorClient(base_url=settings.mock_vendor_alpha_url)
    if name == "beta":
        return BetaVendorClient(base_url=settings.mock_vendor_beta_url)
    raise KeyError(
        f"Vendor {name!r} is not implemented. Available: {implemented_vendor_names()}"
    )
