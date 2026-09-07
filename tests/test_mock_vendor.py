import httpx

from vendor_orchestrator.vendors.alpha import AlphaVendorClient


async def test_mock_vendor_http_happy_path(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/mock/vendors/alpha",
        json={"scenario": "happy"},
        headers={"Idempotency-Key": "test-key-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vendor"] == "alpha"
    assert body["signal"] == "clear"
    assert body["echo_idempotency_key"] == "test-key-1"


async def test_alpha_client_happy_path_inprocess() -> None:
    client = AlphaVendorClient()
    result = await client.invoke({"scenario": "happy"}, idempotency_key="k-happy")
    assert result.ok
    assert result.vendor_name == "alpha"
    assert result.http_status == 200
    assert result.body["signal"] == "clear"
    assert result.body["notes"].startswith("mock fixture")


async def test_create_case_calls_mock_vendor(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/v1/cases",
        json={"subject": "Vendor happy path", "payload": {"scenario": "happy"}},
    )
    assert response.status_code == 201
    calls = response.json()["vendor_calls"]
    assert len(calls) == 1
    assert calls[0]["vendor_name"] == "alpha"
    assert calls[0]["status"] == "success"
    assert calls[0]["response_payload"]["signal"] == "clear"
    assert calls[0]["response_payload"]["notes"].startswith("mock fixture")
