from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vendor_orchestrator import __version__
from vendor_orchestrator.api.cases import router as cases_router
from vendor_orchestrator.api.health import router as health_router
from vendor_orchestrator.db import init_db, wait_for_db
from vendor_orchestrator.vendors.mock_app import mock_vendor_app


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await wait_for_db()
    await init_db()
    yield


app = FastAPI(
    title="Vendor Orchestrator",
    version=__version__,
    description=(
        "Portfolio case-orchestration service. Creates cases, calls mock "
        "vendor HTTP clients, and persists state in Postgres. The agent "
        "decision loop is intentionally unfinished (YOU IMPLEMENT). "
        "Not a KYB/AML/sanctions product."
    ),
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(cases_router)
app.mount("/mock/vendors", mock_vendor_app)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "vendor-orchestrator",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
        "note": "Portfolio scaffold. Mock vendors only. No production vendor claims.",
    }
