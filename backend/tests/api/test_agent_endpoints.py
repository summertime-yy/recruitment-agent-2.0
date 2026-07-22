"""S5-09 · Agent REST + SSE 端点测试（PR-14）。

覆盖 docs/planning/TEST-PLAN-STAGE5.md §S5-09 的 TC-S5-09-1..6，对齐
docs/api-contract.md §3 / §4。

阶段划分：
- 阶段 3 已落地：chat / execute-plan / skip-to-score / tasks / cancel → TC-S5-09-2、TC-S5-09-6 转绿
- 阶段 4 待落地：SSE stream → TC-S5-09-1/3/4/5 仍 xfail，实现后移除标记

注意：ASGITransport 不触发 lifespan，故 app.state.redis 不会初始化；
用到 get_redis / get_engine 的测试需自行 dependency_overrides（用 fake_redis）。

依据：DECISION §十四 阶段 3/4；api-contract §3/§4。
"""

from __future__ import annotations

import asyncio

import pytest

from app.api.v1.agent import get_engine
from app.core.config import get_settings
from app.core.redis import get_redis
from app.main import app
from app.schemas.agent import SSEEventType
from tests.api.sse_helpers import parse_sse

PREFIX = get_settings().API_V1_PREFIX


async def test_s5_09_1_route_order_stream_before_task(client):
    """TC-S5-09-1：/stream 必须先于 /{task_id} 声明，子路径不被 {task_id} 吞掉。"""
    pytest.xfail("阶段 4 SSE stream 端点尚未实现")
    resp = await client.get(f"{PREFIX}/agent/tasks/abc/stream")
    assert resp.headers.get("content-type", "").startswith("text/event-stream")
    assert resp.status_code == 200


async def test_s5_09_2_status_codes(client_db, db_session, fake_redis):
    """TC-S5-09-2：chat 缺 message→422；不存在 task→404；非确认态 cancel→409。"""
    from app.core.time import utcnow_naive
    from app.models.task import Task

    # get_engine 依赖需要 redis（lifespan 未启动），用 fake_redis 覆盖
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        # chat 缺 message → 422（Pydantic 校验）
        r1 = await client_db.post(f"{PREFIX}/agent/chat", json={})
        assert r1.status_code == 422

        # 不存在的 task 流式 → 404（阶段 4 才补 stream 路由，当前仍 404）
        r2 = await client_db.get(f"{PREFIX}/agent/tasks/does-not-exist/stream")
        assert r2.status_code == 404

        # 非确认态（EXECUTING）cancel → 409
        db_session.add(Task(task_id="task_cancel_409", status="EXECUTING", user_message="x", created_at=utcnow_naive()))
        await db_session.commit()
        r3 = await client_db.post(f"{PREFIX}/agent/tasks/task_cancel_409/cancel")
        assert r3.status_code == 409
    finally:
        app.dependency_overrides.clear()


async def test_s5_09_3_sse_last_event_id_replay(client, fake_redis, event_buffer):
    """TC-S5-09-3：带 Last-Event-ID:5 重连只收 id>5 的事件。"""
    pytest.xfail("阶段 4 SSE stream 端点尚未实现")
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        task_id = "task_replay"
        for i in range(10):
            await event_buffer.append(task_id, SSEEventType.TOOL_CALL, {"i": i})

        body = b""
        async with client.stream(
            "GET", f"{PREFIX}/agent/tasks/{task_id}/stream", headers={"Last-Event-ID": "5"}
        ) as resp:
            assert resp.status_code == 200
            async for chunk in resp.aiter_raw():
                body += chunk
                if len(body) > 4000:
                    break
        events = parse_sse(body.decode())
        ids = [int(e["id"]) for e in events if e.get("id")]
        assert ids, "应收到回放事件"
        assert all(i > 5 for i in ids)
    finally:
        app.dependency_overrides.clear()


async def test_s5_09_4_sse_heartbeat(client, fake_redis):
    """TC-S5-09-4：连接期间收到 system 心跳事件（短间隔 override）。"""
    pytest.xfail("阶段 4 SSE stream 端点尚未实现")
    from app.core.config import Settings

    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_settings] = lambda: Settings(sse_heartbeat_interval_sec=0.1)
    try:
        task_id = "task_hb"
        body = b""
        start = asyncio.get_event_loop().time()
        async with client.stream("GET", f"{PREFIX}/agent/tasks/{task_id}/stream") as resp:
            async for chunk in resp.aiter_raw():
                body += chunk
                if asyncio.get_event_loop().time() - start > 0.4:
                    break
        events = parse_sse(body.decode())
        hb = [e for e in events if e.get("event") == "system" and e.get("data", {}).get("message") == "heartbeat"]
        assert len(hb) >= 3
    finally:
        app.dependency_overrides.clear()


async def test_s5_09_5_sse_content_type(client, fake_redis):
    """TC-S5-09-5：/stream 响应头 text/event-stream + 首帧 retry: 3000。"""
    pytest.xfail("阶段 4 SSE stream 端点尚未实现")
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        task_id = "task_ct"
        first = b""
        async with client.stream("GET", f"{PREFIX}/agent/tasks/{task_id}/stream") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            async for chunk in resp.aiter_raw():
                first += chunk
                if b"retry:" in first:
                    break
        assert b"retry: 3000" in first
    finally:
        app.dependency_overrides.clear()


async def test_s5_09_6_orchestrator_unhandled_exception_returns_500(client_db):
    """TC-S5-09-6：engine 抛未捕获异常 → chat 返 500。"""
    from httpx import ASGITransport, AsyncClient

    class _RaisingEngine:
        async def start_chat(self, *args, **kwargs):
            raise RuntimeError("boom")

    app.dependency_overrides[get_engine] = lambda: _RaisingEngine()
    # ASGITransport 默认 raise_app_exceptions=True 会把未捕获异常抛给调用方；
    # 此处用 False 让 ServerErrorMiddleware 返回 500 响应（符合契约）。
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"{PREFIX}/agent/chat", json={"message": "hi"})
            assert r.status_code == 500
    finally:
        app.dependency_overrides.clear()
