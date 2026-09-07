from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CaseCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


class VendorCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_name: str
    status: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any] | None
    idempotency_key: str
    attempt: int
    created_at: datetime


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    payload: dict[str, Any]
    status: str
    decision: str | None
    decision_reason: str | None
    vendor_calls: list[VendorCallRead]
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str = "vendor-orchestrator"


class ReadyResponse(BaseModel):
    status: str
    database: str
