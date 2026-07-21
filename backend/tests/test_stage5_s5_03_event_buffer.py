"""S5-03 · EventBuffer 单元测试 + RedisActiveCounter 测试（PR-13）。

覆盖：
- TC-S5-03-1..5：EventBuffer.append / read_after / LTRIM 容量 / 终态 TTL / 并发 seq 原子性
- TC-S5-13-active-1..2：RedisActiveCounter 限流 429 与 decr 钳位

C_RED 阶段：相关符号（EventBuffer / RedisActiveCounter）在 C_BUF / C_COUNT 才落地，
此处用函数内 lazy import，使文件可收集、用例在 impl 到位前为 red。
"""

import asyncio

import pytest


async def test_s5_03_1_append_then_read_after_full(fake_redis, event_buffer):
    from app.agent.orchestrator.event_buffer import EventBuffer  # noqa: F401
    from app.schemas.agent import SSEEventType

    ev = await event_buffer.append("t1", SSEEventType.THINKING, {"x": 1})
    assert ev.id == "1"
    events = await event_buffer.read_after("t1")
    assert len(events) == 1
    assert events[0].id == ev.id
    assert events[0].type == SSEEventType.THINKING
    assert events[0].data == {"x": 1}


async def test_s5_03_2_read_after_filters_by_last_id(fake_redis, event_buffer):
    from app.schemas.agent import SSEEventType

    await event_buffer.append("t", SSEEventType.THINKING, {"n": 0})
    e2 = await event_buffer.append("t", SSEEventType.PLAN, {"n": 1})
    after = await event_buffer.read_after("t", last_event_id=1)
    assert [e.id for e in after] == [e2.id]


async def test_s5_03_3_ltrim_keeps_maxlen(fake_redis, event_buffer):
    from app.agent.orchestrator.event_buffer import BUFFER_MAXLEN
    from app.schemas.agent import SSEEventType

    for i in range(250):
        await event_buffer.append("t", SSEEventType.THINKING, {"i": i})
    raw_len = await fake_redis.llen("sse:buf:t")
    assert raw_len == BUFFER_MAXLEN


async def test_s5_03_4_terminal_ttl_set(fake_redis, event_buffer):
    from app.agent.orchestrator.event_buffer import TERMINAL_TTL_SEC
    from app.schemas.agent import SSEEventType

    await event_buffer.append("t", SSEEventType.THINKING, {})
    await event_buffer.set_terminal_ttl("t")
    ttl = await fake_redis.ttl("sse:buf:t")
    seq_ttl = await fake_redis.ttl("sse:seq:t")
    assert 0 < ttl <= TERMINAL_TTL_SEC
    assert 0 < seq_ttl <= TERMINAL_TTL_SEC


async def test_s5_03_5_concurrent_append_unique_seq(fake_redis, event_buffer):
    from app.schemas.agent import SSEEventType

    await asyncio.gather(*[event_buffer.append("t", SSEEventType.THINKING, {}) for _ in range(20)])
    events = await event_buffer.read_after("t")
    seqs = [int(e.id) for e in events]
    assert len(seqs) == len(set(seqs))  # 无重复
    assert sorted(seqs) == list(range(1, len(seqs) + 1))  # 单调递增


async def test_s5_13_active_1_limit_raises_429(fake_redis):
    from app.agent.orchestrator.active_counter import (
        RedisActiveCounter,
        TaskLimitExceededError,
    )

    counter = RedisActiveCounter(fake_redis, limit=10)
    for _ in range(10):
        await counter.incr()
    with pytest.raises(TaskLimitExceededError):
        await counter.incr()
    # 超限回滚：计数不破上限
    assert await counter.current() == 10


async def test_s5_13_active_2_decr_floors_at_zero(fake_redis):
    from app.agent.orchestrator.active_counter import RedisActiveCounter

    counter = RedisActiveCounter(fake_redis, limit=10)
    await counter.decr()  # 从 0 往下钳位
    assert await counter.current() == 0
