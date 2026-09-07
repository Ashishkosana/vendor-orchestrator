"""In-process mock vendor HTTP surface.

This is a stand-in for a paid third-party API. Responses are deterministic
fixtures keyed by ``payload["scenario"]`` so tests and later evals stay honest.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header
from pydantic import BaseModel, ConfigDict, Field


class AlphaResponse(BaseModel):
    vendor: str = "alpha"
    signal: str
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str
    echo_idempotency_key: str | None = None


class AlphaRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    scenario: str = "happy"


mock_vendor_app = FastAPI(title="Mock vendor (in-process)", docs_url=None)


@mock_vendor_app.post("/alpha", response_model=AlphaResponse)
async def alpha_check(
    body: AlphaRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AlphaResponse:
    extra: dict[str, Any] = body.model_dump()
    scenario = str(extra.get("scenario") or "happy")
    if scenario == "review":
        return AlphaResponse(
            signal="review",
            confidence=0.64,
            notes="mock fixture: scenario=review",
            echo_idempotency_key=idempotency_key,
        )
    return AlphaResponse(
        signal="clear",
        confidence=0.91,
        notes="mock fixture: scenario=happy",
        echo_idempotency_key=idempotency_key,
    )
