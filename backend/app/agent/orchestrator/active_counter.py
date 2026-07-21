"""S5-08 · 全局活跃任务计数（抽象接口 + 内存实现；Redis 实现 PR-13 落地）。

RedisActiveCounter 用 ``INCR + EXPIRE`` 单 pipeline 原子计数，超限 ``DECR`` 回滚并抛
``TaskLimitExceededError``；1h TTL 兜底防进程 crash 未 decr 导致的泄漏。
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from redis import asyncio as aioredis

from app.agent.orchestrator.errors import TaskLimitExceededError

ACTIVE_KEY = "task:active"
ACTIVE_TTL_SEC = 3600  # 1h 无活动兜底防泄漏（PLAN §Q7）


class ActiveCounter(Protocol):
    """活跃任务计数抽象（PR-13 由 RedisActiveCounter 实现）。"""

    async def incr(self) -> int: ...
    async def decr(self) -> int: ...
    async def current(self) -> int: ...


class InMemoryActiveCounter:
    """PR-12 默认实现；线程/协程安全（asyncio.Lock）。

    ``start`` 允许测试预填计数以模拟已达上限（TC-S5-08-3）。
    """

    def __init__(self, limit: int = 10, start: int = 0):
        self._count = start
        self._limit = limit
        self._lock = asyncio.Lock()

    async def incr(self) -> int:
        async with self._lock:
            if self._count >= self._limit:
                raise TaskLimitExceededError(current=self._count, limit=self._limit)
            self._count += 1
            return self._count

    async def decr(self) -> int:
        async with self._lock:
            self._count = max(0, self._count - 1)
            return self._count

    async def current(self) -> int:
        return self._count


class RedisActiveCounter:
    """PR-13 · 基于 Redis 的全局活跃任务计数（跨进程）。"""

    def __init__(self, redis: aioredis.Redis, limit: int = 10):
        self.redis = redis
        self.limit = limit

    async def incr(self) -> int:
        pipe = self.redis.pipeline()
        pipe.incr(ACTIVE_KEY)
        pipe.expire(ACTIVE_KEY, ACTIVE_TTL_SEC)
        results = await pipe.execute()
        current = results[0]
        if current > self.limit:
            await self.redis.decr(ACTIVE_KEY)  # 回滚
            raise TaskLimitExceededError(current=current, limit=self.limit)
        return current

    async def decr(self) -> int:
        new_val = await self.redis.decr(ACTIVE_KEY)
        if new_val < 0:
            await self.redis.set(ACTIVE_KEY, 0)
            new_val = 0
        return new_val

    async def current(self) -> int:
        val = await self.redis.get(ACTIVE_KEY)
        return int(val) if val is not None else 0
