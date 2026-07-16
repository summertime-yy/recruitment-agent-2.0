from httpx import AsyncClient


async def test_list_jds_returns_structure(client_db: AsyncClient) -> None:
    resp = await client_db.get("/api/v1/jds")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
