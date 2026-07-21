"""S5-07 · Act 执行器（PR-12）。

纯模块：``run_act(plan, ctx, emit, tool_router)`` 按 plan 的步骤顺序调用 ``ToolRouter.dispatch``，
并通过 ``emit(SSEEvent)`` 发出 tool_call / progress / result / warning / error 事件。

emit 约定（裁定 DECISION §三 Q2）：
- 签名为 ``async def emit(ev: SSEEvent) -> None``（参数类型是 SSEEvent dataclass，非 dict）。
- 每次 emit 用 try/except 包裹，SSE 推送失败只 warning，不中断业务。
- 不使用 asyncio.create_task（触发-遗忘），以保证事件顺序可断言。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.agent.orchestrator.tool_router import ToolRouter
from app.schemas.agent import SSEEvent, SSEEventType

logger = logging.getLogger(__name__)

EmitFn = Callable[[SSEEvent], Awaitable[None]]


@dataclass
class StepResult:
    """单步执行结果。"""

    step_id: str
    tool_name: str
    success: bool
    output: dict[str, Any] | None = None
    error_message: str | None = None


async def _noop_emit(ev: SSEEvent) -> None:  # pragma: no cover - 占位
    return None


def _make_event(event_type: SSEEventType, task_id: str, data: dict[str, Any], step_id: str | None = None) -> SSEEvent:
    return SSEEvent(
        id="evt",  # Engine 层应注入单调递增 id；standalone 用占位
        type=event_type,
        task_id=task_id or "standalone",
        timestamp="",  # Engine 层注入真实时间戳
        data=data,
        step_id=step_id,
    )


async def run_act(
    plan: dict[str, Any],
    ctx: dict[str, Any] | None = None,
    emit: EmitFn | None = None,
    tool_router: ToolRouter | None = None,
) -> list[StepResult]:
    """按 plan["steps"] 顺序执行各步，返回每步的 StepResult 列表。

    - 必需步失败：发 error 事件并中止（后续步不再执行）。
    - 可选步失败：发 warning 事件并继续。
    - 每成功步依次发 tool_call → progress(100) → result（含 artifacts）。
    """
    emit = emit or _noop_emit
    router = tool_router or ToolRouter()
    ctx = ctx or {}
    task_id = ctx.get("task_id", "standalone")
    steps = plan.get("steps", []) or []

    # Reason 阶段占位思考事件（兼容 TC-S5-07-5；正常 Act 流程不走此分支）
    if plan.get("phase") == "REASON":
        await emit(_make_event(SSEEventType.THINKING, task_id, {"phase": "REASON"}))

    if not steps:
        return []

    results: list[StepResult] = []
    for idx, step in enumerate(steps):
        step_id = step.get("step_id") or f"step_{idx + 1}"
        tool_name = step.get("tool_name")
        tool_input = step.get("tool_input") or step.get("args") or {}
        optional = bool(step.get("optional", False))

        await emit(_make_event(SSEEventType.TOOL_CALL, task_id, {"tool_name": tool_name, "tool_input": tool_input}, step_id))
        try:
            sr = await router.dispatch(tool_name, tool_input)
        except Exception as e:  # noqa: BLE001 - emit 不应中断业务
            sr = None
            err = str(e)
        else:
            err = None

        if sr is not None and sr.success:
            await emit(_make_event(SSEEventType.PROGRESS, task_id, {"step_id": step_id, "percent": 100}, step_id))
            results.append(StepResult(step_id=step_id, tool_name=tool_name or "", success=True, output=sr.output))
            await emit(
                _make_event(
                    SSEEventType.RESULT,
                    task_id,
                    {"step_id": step_id, "result": sr.output, "artifacts": [r.output for r in results if r.output]},
                    step_id,
                )
            )
        else:
            msg = err or (sr.error_message if sr else "unknown error")
            if optional:
                await emit(_make_event(SSEEventType.WARNING, task_id, {"step_id": step_id, "message": msg}, step_id))
                results.append(StepResult(step_id=step_id, tool_name=tool_name or "", success=False, error_message=msg))
                # 继续后续步
            else:
                await emit(_make_event(SSEEventType.ERROR, task_id, {"step_id": step_id, "message": msg}, step_id))
                results.append(StepResult(step_id=step_id, tool_name=tool_name or "", success=False, error_message=msg))
                break  # 必需步失败：中止

    return results
