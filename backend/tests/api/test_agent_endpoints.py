"""S5-09 · Agent REST + SSE 端点测试（PR-14）。

覆盖 docs/planning/TEST-PLAN-STAGE5.md §S5-09 的 TC-S5-09-1..6，对齐
docs/api-contract.md §3 / §4。

- TC-S5-09-1：/stream 路由先于 /{task_id} 解析为 SSE 端点
- TC-S5-09-2：chat 缺 message→422；不存在 task→404；非确认态 cancel→409
- TC-S5-09-3：SSE 带 Last-Event-ID:5 重连只收 id>5
- TC-S5-09-4：心跳事件（短间隔 override）
- TC-S5-09-5：/stream 响应头 text/event-stream + 首帧 retry: 3000
- TC-S5-09-6：engine 抛未捕获异常 → chat 返 500

注意：
- ASGITransport 不触发 lifespan，故 app.state.redis 不会初始化；
  用到 get_redis 的测试需自行 dependency_overrides（用 fake_redis）。
- ASGITransport 下 ``request.is_disconnected()`` 在流进行中不会返回 True，
  且客户端 break 不会取消服务端协程；故所有 SSE 用例必须让流**自然终止**
  （终态 task 走合成路径 / 缓冲中含终态事件），否则连接 teardown 会挂起。

依据：DECISION §十四 阶段 3/4；api-contract §3/§4。
"""

from __future__ import annotations

import asyncio

from app.api.v1.agent import get_engine
from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.time import utcnow_naive
from app.main import app
from app.models.task import Task
from app.schemas.agent import SSEEventType
from tests.api.sse_helpers import parse_sse

PREFIX = get_settings().API_V1_PREFIX


async def test_s5_09_1_route_order_stream_before_task(client_db, db_session, fake_redis):
    """TC-S5-09-1：/stream 路由解析为 SSE 端点（200 + text/event-stream）。

    用终态 task 走合成路径，保证流自然结束（避免 ASGITransport 无限流挂起）。
    """
    app.dependency_overrides[get_redis] = lambda: fake_redis
    db_session.add(
        Task(
            task_id="task_route",
            status="COMPLETED",
            user_message="x",
            result={"ok": True},
            finished_at=utcnow_naive(),
        )
    )
    await db_session.commit()
    try:
        body = b""
        async with client_db.stream("GET", f"{PREFIX}/agent/tasks/task_route/stream") as resp:
            assert resp.status_code == 200
            assert resp.headers.get("content-type", "").startswith("text/event-stream")
            async for chunk in resp.aiter_raw():
                body += chunk
        assert b"retry: 3000" in body
    finally:
        app.dependency_overrides.clear()


async def test_s5_09_2_status_codes(client_db, db_session, fake_redis):
    """TC-S5-09-2：chat 缺 message→422；不存在 task→404；非确认态 cancel→409。"""
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        # chat 缺 message → 422（Pydantic 校验）
        r1 = await client_db.post(f"{PREFIX}/agent/chat", json={})
        assert r1.status_code == 422

        # 不存在的 task 流式 → 404（stream 路由已存在，但 task 不存在）
        r2 = await client_db.get(f"{PREFIX}/agent/tasks/does-not-exist/stream")
        assert r2.status_code == 404

        # 非确认态（EXECUTING）cancel → 409
        db_session.add(Task(task_id="task_cancel_409", status="EXECUTING", user_message="x", created_at=utcnow_naive()))
        await db_session.commit()
        r3 = await client_db.post(f"{PREFIX}/agent/tasks/task_cancel_409/cancel")
        assert r3.status_code == 409
    finally:
        app.dependency_overrides.clear()


async def test_s5_09_3_sse_last_event_id_replay(client_db, db_session, fake_redis, event_buffer):
    """TC-S5-09-3：带 Last-Event-ID:5 重连只收 id>5 的事件。

    缓冲末尾追加一条终态 RESULT 事件，使 _event_stream 回放后自然关流。
    """
    app.dependency_overrides[get_redis] = lambda: fake_redis
    db_session.add(Task(task_id="task_replay", status="EXECUTING", user_message="x", started_at=utcnow_naive()))
    await db_session.commit()
    for i in range(10):
        await event_buffer.append("task_replay", SSEEventType.TOOL_CALL, {"i": i})
    # id=11：终态事件，保证回放到此关流（Q3）
    await event_buffer.append("task_replay", SSEEventType.RESULT, {"done": True})
    try:
        body = b""
        async with client_db.stream(
            "GET", f"{PREFIX}/agent/tasks/task_replay/stream", headers={"Last-Event-ID": "5"}
        ) as resp:
            assert resp.status_code == 200
            async for chunk in resp.aiter_raw():
                body += chunk
        events = parse_sse(body.decode())
        ids = [int(e["id"]) for e in events if e.get("id")]
        assert ids, "应收到回放事件"
        assert all(i > 5 for i in ids)
    finally:
        app.dependency_overrides.clear()


async def test_s5_09_4_sse_heartbeat(client_db, db_session, fake_redis, event_buffer):
    """TC-S5-09-4：连接期间收到 system 心跳事件（短间隔 override）。

    后台延迟追加终态 RESULT 事件以结束流；期间空闲循环按 0.1s 间隔发心跳。
    """
    from app.core.config import Settings

    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_settings] = lambda: Settings(sse_heartbeat_interval_sec=0.1)
    db_session.add(Task(task_id="task_hb", status="EXECUTING", user_message="x", started_at=utcnow_naive()))
    await db_session.commit()

    async def _finish_later():
        await asyncio.sleep(0.5)
        await event_buffer.append("task_hb", SSEEventType.RESULT, {"done": True})

    finisher = asyncio.create_task(_finish_later())
    try:
        body = b""
        async with client_db.stream("GET", f"{PREFIX}/agent/tasks/task_hb/stream") as resp:
            async for chunk in resp.aiter_raw():
                body += chunk
        events = parse_sse(body.decode())
        hb = [e for e in events if e.get("event") == "system" and e.get("data", {}).get("message") == "heartbeat"]
        assert len(hb) >= 3
    finally:
        await finisher
        app.dependency_overrides.clear()


async def test_s5_09_5_sse_content_type(client_db, db_session, fake_redis):
    """TC-S5-09-5：/stream 响应头 text/event-stream + 首帧 retry: 3000。

    用终态 task 走合成路径，保证流自然结束。
    """
    app.dependency_overrides[get_redis] = lambda: fake_redis
    db_session.add(
        Task(
            task_id="task_ct",
            status="COMPLETED",
            user_message="x",
            result={"ok": True},
            finished_at=utcnow_naive(),
        )
    )
    await db_session.commit()
    try:
        body = b""
        async with client_db.stream("GET", f"{PREFIX}/agent/tasks/task_ct/stream") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            async for chunk in resp.aiter_raw():
                body += chunk
        assert b"retry: 3000" in body
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
