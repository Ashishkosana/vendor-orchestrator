from fastapi import APIRouter

from vendor_orchestrator.db import ping_db
from vendor_orchestrator.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    await ping_db()
    return ReadyResponse(status="ok", database="up")
