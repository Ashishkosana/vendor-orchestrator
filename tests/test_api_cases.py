import uuid

import httpx


async def test_create_and_get_case(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/v1/cases",
        json={"subject": "Hello case", "payload": {"scenario": "happy"}},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["subject"] == "Hello case"
    assert body["payload"]["scenario"] == "happy"
    assert body["status"] == "vendor_checked"
    assert body["decision"] is None
    case_id = body["id"]

    fetched = await client.get(f"/v1/cases/{case_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == case_id
    assert fetched.json()["subject"] == "Hello case"


async def test_create_case_rejects_empty_subject(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/cases", json={"subject": "", "payload": {}})
    assert response.status_code == 422


async def test_get_unknown_case_404(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/v1/cases/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_run_agent_is_not_implemented(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/v1/cases",
        json={"subject": "Needs a human-owned agent", "payload": {}},
    )
    case_id = created.json()["id"]
    response = await client.post(f"/v1/cases/{case_id}/run-agent")
    assert response.status_code == 501
    assert "YOU IMPLEMENT" in response.json()["detail"]
