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


async def test_run_agent_auto_resolves_clear_complete_packet(
    client: httpx.AsyncClient,
) -> None:
    created = await client.post(
        "/v1/cases",
        json={
            "subject": "Complete intake packet",
            "payload": {"scenario": "happy", "packet_complete": True},
        },
    )
    case_id = created.json()["id"]
    response = await client.post(f"/v1/cases/{case_id}/run-agent")
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "auto_resolve"
    assert body["status"] == "auto_resolved"
    assert body["decision_reason"]
    assert "clear" in body["decision_reason"]


async def test_run_agent_escalates_review_signal(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/v1/cases",
        json={
            "subject": "Intake with review signal",
            "payload": {"scenario": "review", "packet_complete": True},
        },
    )
    case_id = created.json()["id"]
    response = await client.post(f"/v1/cases/{case_id}/run-agent")
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "escalate"
    assert body["status"] == "escalated"
    assert "review" in body["decision_reason"]


async def test_run_agent_escalates_incomplete_packet(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/v1/cases",
        json={
            "subject": "Sparse intake",
            "payload": {"scenario": "happy", "packet_complete": False},
        },
    )
    case_id = created.json()["id"]
    response = await client.post(f"/v1/cases/{case_id}/run-agent")
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "escalate"
    assert body["status"] == "escalated"
    assert "packet_complete" in body["decision_reason"]
