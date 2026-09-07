import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.models import Case, VendorCall


async def test_create_case_persists_row(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    response = await client.post(
        "/v1/cases",
        json={"subject": "Persisted case", "payload": {"k": "v"}},
    )
    assert response.status_code == 201
    case_id = uuid.UUID(response.json()["id"])

    stored = await session.get(Case, case_id)
    assert stored is not None
    assert stored.subject == "Persisted case"
    assert stored.payload == {"k": "v"}
    assert stored.status.value == "vendor_checked"


async def test_vendor_call_row_persisted(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    response = await client.post(
        "/v1/cases",
        json={"subject": "Vendor persist", "payload": {"scenario": "happy"}},
    )
    case_id = uuid.UUID(response.json()["id"])

    result = await session.execute(
        select(func.count())
        .select_from(VendorCall)
        .where(VendorCall.case_id == case_id)
    )
    assert result.scalar_one() == 1

    call = (
        await session.execute(select(VendorCall).where(VendorCall.case_id == case_id))
    ).scalar_one()
    assert call.vendor_name == "alpha"
    assert call.status.value == "success"
    assert call.idempotency_key.startswith(f"case:{case_id}:vendor:alpha")
    assert call.response_payload is not None
    assert call.response_payload["signal"] == "clear"
