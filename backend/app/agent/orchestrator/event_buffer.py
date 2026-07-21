"""S5-03 · SSE 事件环形缓冲（PR-13）。

事件写入 Redis List ``sse:buf:{task_id}``，seq_id 由 Redis ``INCR sse:seq:{task_id}``
原子分配，保证跨进程单调递增。读取通过 ``read_after`` 重放（PR-14 SSE 端点轮询用）。

心跳（``system`` 事件 / ``{message:'heartbeat'}``）**不进 EventBuffer**：由 SSE HTTP
端点在 ``StreamingResponse`` 内每 15s 直接发帧（PR-14 落实），不依赖 Redis、不重放。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from redis import asyncio as aioredis

from app.schemas.agent import SSEEvent, SSEEventType

logger = logging.getLogger(__name__)

BUFFER_MAXLEN = 200  # 环形裁剪上限（PLAN §Q6）
TERMINAL_TTL_SEC = 3600  # 终态后过期（PLAN §Q6）


def _events_key(task_id: str) -> str:
    return f"sse:buf:{task_id}"


def _seq_key(task_id: str) -> str:
    return f"sse:seq:{task_id}"


class EventBuffer:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def append(
        self,
        task_id: str,
        event_type: SSEEventType,
        data: Any,
        step_id: str | None = None,
    ) -> SSEEvent:
        """分配 seq_id + timestamp，序列化写 Redis List，LTRIM 保 MAXLEN 条。"""
        seq_id = await self.redis.incr(_seq_key(task_id))
        ev = SSEEvent(
            id=str(seq_id),
            type=event_type,
            task_id=task_id,
            timestamp=datetime.now(UTC).isoformat(),
            data=data,
            step_id=step_id,
        )
        payload = ev.model_dump_json()
        pipe = self.redis.pipeline()
        pipe.rpush(_events_key(task_id), payload)
        pipe.ltrim(_events_key(task_id), -BUFFER_MAXLEN, -1)
        await pipe.execute()
        return ev

    async def read_after(self, task_id: str, last_event_id: int | None = None) -> list[SSEEvent]:
        """last_event_id=None → 全量重放；否则返回 id > last_event_id 的事件。"""
        raw = await self.redis.lrange(_events_key(task_id), 0, -1)
        events = [SSEEvent.model_validate_json(x) for x in raw]
        if last_event_id is None:
            return events
        return [e for e in events if int(e.id) > last_event_id]

    async def set_terminal_ttl(self, task_id: str) -> None:
        """任务进入终态时调用，为 events / seq 键各设 TTL。"""
        await self.redis.expire(_events_key(task_id), TERMINAL_TTL_SEC)
        await self.redis.expire(_seq_key(task_id), TERMINAL_TTL_SEC)
