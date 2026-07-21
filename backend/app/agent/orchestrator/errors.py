"""S5-08 · Orchestrator 错误类型（PR-12）。"""

from __future__ import annotations


class IllegalTransitionError(Exception):
    """状态机非法转移。"""

    def __init__(self, from_status, to_status):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Illegal transition: {from_status} -> {to_status}")


class TaskLimitExceededError(Exception):
    """全局活跃任务数超过上限（应转 HTTP 429 TASK_LIMIT_EXCEEDED）。"""

    def __init__(self, current: int | None = None, limit: int | None = None, message: str | None = None):
        self.current = current
        self.limit = limit
        self.message = message or f"Active task limit exceeded (current={current}, limit={limit})"
        super().__init__(self.message)


class TaskTimeoutError(Exception):
    """任务整体/单步超时（应转 HTTP 408 / 对应 error 事件）。"""

    def __init__(self, message: str = "Task timeout"):
        self.message = message
        super().__init__(message)
