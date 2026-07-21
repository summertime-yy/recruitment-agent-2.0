import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database import get_db
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL 事务回滚 session（每个测试隔离，结束后统一 rollback）。

    PLAN S4-05 决策 5 的退化方案：复用运行中的 PostgreSQL（resumes 使用 JSONB，
    SQLite 不支持）。为避免 Windows ProactorEventLoop 下 asyncpg 连接跨 event loop
    复用导致 'Event loop is closed'，此处为每个测试创建独立的 engine（NullPool），
    绑定到当前测试运行的 event loop，连接用后即刻关闭，不进连接池。
    """
    from sqlalchemy.pool import NullPool

    from app.core.config import get_settings

    settings = get_settings()
    eng = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    connection = await eng.connect()
    await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)

    async def _noop_commit(*args, **kwargs):  # type: ignore[method-assign]
        await session.flush()

    session.commit = _noop_commit  # type: ignore[method-assign]
    try:
        yield session
    finally:
        await session.close()
        await connection.rollback()
        await connection.close()
        await eng.dispose()


@pytest_asyncio.fixture
async def client_db(client: AsyncClient, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """绑定测试 DB session 的 client（override FastAPI 的 get_db 依赖）。"""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def mock_llm(monkeypatch):
    """打桩 app.agent.llm_adapter.call_llm_json，返回固定 JSON（不触发真实 LLM）。"""

    async def _fake_llm_json(system_prompt: str, user_prompt: str) -> dict:
        return {
            "mocked": True,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake_llm_json)
    yield _fake_llm_json


@pytest_asyncio.fixture
async def fake_redis():
    """function scope 独立 fakeredis 实例，避免测试间污染（PR-13）。"""
    import fakeredis.aioredis as fakeasync

    client = fakeasync.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def event_buffer(fake_redis):
    from app.agent.orchestrator.event_buffer import EventBuffer

    return EventBuffer(fake_redis)
