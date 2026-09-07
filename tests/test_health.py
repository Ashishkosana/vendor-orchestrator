import httpx


async def test_health_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "vendor-orchestrator"


async def test_ready_ok_when_postgres_up(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


async def test_root_is_honest_about_mocks(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    note = response.json()["note"].lower()
    assert "mock" in note
    assert "production" in note
