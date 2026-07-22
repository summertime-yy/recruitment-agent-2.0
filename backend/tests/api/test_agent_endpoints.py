"""S5-09 · Agent REST + SSE 端点测试（PR-14）。

覆盖 docs/planning/TEST-PLAN-STAGE5.md §S5-09 的 TC-S5-09-1..6，对齐
docs/api-contract.md §3 / §4。

> **阶段 1 骨架**：agent 端点与 SSE 流尚未实现，故全模块 `xfail`（strict=False）。
> 后续阶段 2~5 实现对应能力后，移除该测试上的 xfail 标记即可转绿。
> 这样可保证阶段 1 commit 不破坏 101 passed 基线（xfail 不计入 failure）。

依据：
- DECISION §十四 阶段 1（red-test skeleton）
- api-contract §3.1/§3.2/§3.3/§3.5/§4.1-4.5
"""

from __future__ import annotations

import asyncio

import pytest
from app.core.config import get_settings
from app.main import app
from app.schemas.agent import SSEEventType
from tests.api.sse_helpers import parse_sse

# 阶段 1：全模块 xfail。实现后按用例移除该标记。
pytestmark = pytest.mark.xfail(strict=False, reason="PR-14 阶段1骨架：agent 端点/SSE 尚未实现")

PREFIX = get_settings().API_V1_PREFIX


async def test_s5_09_1_route_order_stream_before_task(client):
    """TC-S5-09-1：/stream 必须先于 /{task_id} 声明，子路径不被 {task_id} 吞掉。"""
    resp = await client.get(f"{PREFIX}/agent/tasks/abc/stream")
    # 不应落到 /{task_id} 详情路由（那会返回非 SSE 的 404/200）
    assert resp.headers.get("content-type", "").startswith("text/event-stream")
    assert resp.status_code == 200


async def test_s5_09_2_status_codes(client_db, db_session):
    """TC-S5-09-2：chat 缺 message→422；不存在 task→404；非确认态 cancel→409。"""
    from app.core.time import utcnow_naive
    from app.models.task import Task

    # chat 缺 message → 422（Pydantic 校验）
    r1 = await client_db.post(f"{PREFIX}/agent/chat", json={})
    assert r1.status_code == 422

    # 不存在的 task 查询/流式 → 404
    r2 = await client_db.get(f"{PREFIX}/agent/tasks/does-not-exist/stream")
    assert r2.status_code == 404

    # 非确认态（EXECUTING）cancel → 409
    db_session.add(Task(task_id="task_cancel_409", status="EXECUTING", user_message="x", created_at=utcnow_naive()))
    await db_session.commit()
    r3 = await client_db.post(f"{PREFIX}/agent/tasks/task_cancel_409/cancel")
    assert r3.status_code == 409


async def test_s5_09_3_sse_last_event_id_replay(client, fake_redis, event_buffer):
    """TC-S5-09-3：带 Last-Event-ID:5 重连只收 id>5 的事件。"""
    from app.core.redis import get_redis

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
    from app.core.config import Settings
    from app.core.redis import get_redis

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
    from app.core.redis import get_redis

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


async def test_s5_09_6_orchestrator_unhandled_exception_returns_500(client):
    """TC-S5-09-6：engine 抛未捕获异常 → chat 返 500。"""
    # get_engine 依赖在阶段 3 提供；阶段 1 不存在 → 此处 xfail 捕获导入错误
    from app.api.v1.agent import get_engine

    class _RaisingEngine:
        async def start_chat(self, *args, **kwargs):
            raise RuntimeError("boom")

    app.dependency_overrides[get_engine] = lambda: _RaisingEngine()
    try:
        r = await client.post(f"{PREFIX}/agent/chat", json={"message": "hi"})
        assert r.status_code == 500
    finally:
        app.dependency_overrides.clear()
