"""S5-02 · Agent / SSE 相关 Pydantic Schema（PR-10 交付物）。

对齐 docs/api-contract.md：
- §3.2 统一 SSE 事件信封（id / type / task_id / timestamp / data + 可选 step_id）
- §3.3 八类事件类型（thinking/plan/tool_call/progress/result/error/warning/system）
- §3.4 Plan / PlanStep（optional 默认 false）
- §4.1 AgentChatRequest / AgentChatResponse
- §4.2 ExecutePlanRequest / §4.3 SkipToScoreRequest / §4.4 TaskStatus / §4.5 CancelTaskResponse
- ExecutionPhase 对齐 app.models.execution.Execution.phase 列取值
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SSEEventType(StrEnum):
    """§3.3 统一事件类型（禁止 reason/reflect 等旧类型）。"""

    THINKING = "thinking"
    PLAN = "plan"
    TOOL_CALL = "tool_call"
    PROGRESS = "progress"
    RESULT = "result"
    ERROR = "error"
    WARNING = "warning"
    SYSTEM = "system"


class SSEEvent(BaseModel):
    """§3.2 统一 SSE 事件信封。"""

    id: str
    type: SSEEventType
    task_id: str
    timestamp: str
    data: Any
    step_id: str | None = None


class PlanStep(BaseModel):
    """§3.4 PlanStep。optional 缺省 false（PR-9 写回 REVIEW D8）。"""

    step_id: str
    description: str
    tool_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    expected_output: str
    optional: bool = False
    dependencies: list[str] = Field(default_factory=list)
    estimated_duration_seconds: int | None = None


class Plan(BaseModel):
    """§3.4 Plan。"""

    task_id: str
    steps: list[PlanStep]
    reasoning: str | None = None


class AgentChatRequest(BaseModel):
    """§4.1 发起对话 / 创建任务。message 必填。"""

    message: str
    context: dict[str, Any] | None = None


class AgentChatResponse(BaseModel):
    """§4.1 响应。"""

    task_id: str
    status: str
    initial_plan: Plan | None = None


class ExecutePlanRequest(BaseModel):
    """§4.2 确认执行计划。"""

    task_id: str
    accepted_steps: list[str] | None = None
    modifications: list[dict[str, Any]] | None = None


class SkipToScoreRequest(BaseModel):
    """§4.3 跳过计划直接评分。"""

    jd_id: str
    candidate_ids: list[str]


class TaskStatus(BaseModel):
    """§4.4 查询任务状态。status 含 CANCELLED（PR-9 写回 REVIEW D2）。"""

    task_id: str
    status: str
    current_step: str | None = None
    plan: Plan | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class CancelTaskResponse(BaseModel):
    """§4.5 取消任务响应。"""

    task_id: str
    status: str = "CANCELLED"


class ExecutionPhase(StrEnum):
    """Execution.phase 列取值（对齐 app.models.execution）。"""

    REASON = "REASON"
    REFLECT = "REFLECT"
    PLAN = "PLAN"
    REFLECT_PLAN = "REFLECT_PLAN"
    ACT = "ACT"
    REFLECT_ACT = "REFLECT_ACT"
