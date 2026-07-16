from httpx import AsyncClient


async def test_health_endpoint_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
