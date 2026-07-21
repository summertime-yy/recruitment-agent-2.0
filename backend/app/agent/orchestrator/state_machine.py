"""S5-08 · Task 状态机 · 转移矩阵与守卫（纯函数式，与 Engine 解耦）。

注意：schemas/agent.py 的 ``TaskStatus`` 是 pydantic 响应模型，并非状态枚举；
本模块自包含定义编排用的 ``TaskStatus`` 枚举（裁定 DECISION §八 误引 schemas 枚举，此处修正）。
"""

from __future__ import annotations

from enum import StrEnum

from app.agent.orchestrator.errors import IllegalTransitionError


class TaskStatus(StrEnum):
    """编排层任务生命周期状态。"""

    PENDING = "PENDING"
    PLANNING = "PLANNING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# 合法转移矩阵（PLAN §2 Q2 + 裁定 DECISION §八）
LEGAL_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.PLANNING, TaskStatus.EXECUTING},  # EXECUTING 供 skip_to_score
    TaskStatus.PLANNING: {TaskStatus.WAITING_CONFIRMATION, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.WAITING_CONFIRMATION: {TaskStatus.EXECUTING, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.EXECUTING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),  # 终态
    TaskStatus.FAILED: set(),  # 终态
    TaskStatus.CANCELLED: set(),  # 终态
}


def _norm(status) -> TaskStatus:
    if isinstance(status, TaskStatus):
        return status
    return TaskStatus(status)


def check_transition(from_status, to_status) -> None:
    """合法性校验；非法转移抛 IllegalTransitionError。"""
    f = _norm(from_status)
    t = _norm(to_status)
    if t not in LEGAL_TRANSITIONS.get(f, set()):
        raise IllegalTransitionError(f, t)


class TransitionGuard:
    """轻量类版（供依赖注入测试）；内部委托 check_transition。"""

    def check(self, from_status, to_status) -> None:
        check_transition(from_status, to_status)

    def transition(self, from_status, to_status):
        """校验并返回（归一化后的）目标状态；非法则抛 IllegalTransitionError。"""
        check_transition(from_status, to_status)
        return _norm(to_status)
