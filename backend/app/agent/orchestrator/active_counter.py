"""S5-08 · 全局活跃任务计数（抽象接口 + 内存实现；Redis 实现推迟 PR-13）。"""

from __future__ import annotations

import asyncio
from typing import Protocol

from app.agent.orchestrator.errors import TaskLimitExceededError


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
