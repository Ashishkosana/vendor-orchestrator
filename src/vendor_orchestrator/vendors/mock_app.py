"""In-process mock vendor HTTP surface.

This is a stand-in for a paid third-party API. Responses are deterministic
fixtures keyed by ``payload["scenario"]`` so tests and evals stay honest.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

# Visible to tests: how many times each mock vendor path was invoked.
INVOKE_COUNTS: dict[str, int] = defaultdict(int)
_TRANSIENT_HITS: dict[str, int] = defaultdict(int)

TRANSIENT_FAILURES_BEFORE_SUCCESS = 2


def reset_mock_state() -> None:
    INVOKE_COUNTS.clear()
    _TRANSIENT_HITS.clear()


class VendorResponse(BaseModel):
    vendor: str
    signal: str
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str
    echo_idempotency_key: str | None = None


class VendorRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    scenario: str = "happy"


mock_vendor_app = FastAPI(title="Mock vendor (in-process)", docs_url=None)


def _resolve_mock(
    vendor: str,
    scenario: str,
    idempotency_key: str | None,
) -> VendorResponse:
    INVOKE_COUNTS[vendor] += 1

    if scenario == "client_error":
        raise HTTPException(
            status_code=400, detail=f"mock fixture: {vendor} client_error"
        )

    if scenario == "transient":
        bucket = f"{vendor}:{idempotency_key or 'none'}"
        hits = _TRANSIENT_HITS[bucket]
        _TRANSIENT_HITS[bucket] = hits + 1
        if hits < TRANSIENT_FAILURES_BEFORE_SUCCESS:
            raise HTTPException(
                status_code=503, detail=f"mock fixture: {vendor} transient"
            )

    if scenario == "review":
        return VendorResponse(
            vendor=vendor,
            signal="review",
            confidence=0.64,
            notes=f"mock fixture: vendor={vendor} scenario=review",
            echo_idempotency_key=idempotency_key,
        )

    return VendorResponse(
        vendor=vendor,
        signal="clear",
        confidence=0.91,
        notes=f"mock fixture: vendor={vendor} scenario=happy",
        echo_idempotency_key=idempotency_key,
    )


@mock_vendor_app.post("/alpha", response_model=VendorResponse)
async def alpha_check(
    body: VendorRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> VendorResponse:
    extra: dict[str, Any] = body.model_dump()
    scenario = str(extra.get("scenario") or "happy")
    return _resolve_mock("alpha", scenario, idempotency_key)


@mock_vendor_app.post("/beta", response_model=VendorResponse)
async def beta_check(
    body: VendorRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> VendorResponse:
    extra: dict[str, Any] = body.model_dump()
    scenario = str(extra.get("scenario") or "happy")
    return _resolve_mock("beta", scenario, idempotency_key)
