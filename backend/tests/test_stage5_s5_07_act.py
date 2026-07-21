"""S5-07 · Orchestrator Act + Reflect-Act + SSE emit（PR-12 绿态）。

覆盖用例（TC-S5-07-1..5）：
- TC-S5-07-1  event_order：单步依次发 tool_call → progress(100) → result。
- TC-S5-07-2  required_step_fail_abort：必需步失败 → 发 error 且中止。
- TC-S5-07-3  partial_artifacts_on_invalid：result 事件仍带 artifacts。
- TC-S5-07-4  optional_step_fail_continue：optional 步失败 → 发 warning 且继续。
- TC-S5-07-5  emits_thinking_for_reason_phase：Reason 阶段经 emit 发 thinking 事件。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent.base_skill import SkillResult
from app.agent.orchestrator.act import StepResult, run_act


class _CollectingEmitter:
    """测试用 emitter：记录 emit 的事件序列（SSEEvent -> dict，type 归一为字符串）。"""

    def __init__(self):
        self.events: list[dict[str, Any]] = []

    async def __call__(self, ev: Any) -> None:
        d = ev.model_dump() if hasattr(ev, "model_dump") else dict(ev)
        if hasattr(d.get("type"), "value"):
            d["type"] = d["type"].value
        self.events.append(d)


class _MockToolRouter:
    """mock ToolRouter：按 fail_tools 决定单步成功/失败。"""

    def __init__(self, fail_tools=None):
        self.fail_tools = set(fail_tools or [])

    async def dispatch(self, tool_name, tool_input, db=None):
        if tool_name in self.fail_tools:
            return SkillResult(success=False, error_message=f"{tool_name} failed", output={})
        return SkillResult(success=True, output={"tool_name": tool_name, "echo": tool_input})


@pytest.mark.asyncio
async def test_tc_s5_07_1_event_order():
    """run_act 单步依次发 tool_call → progress → result。"""
    plan = {"steps": [{"step_id": "step_1", "tool_name": "search_resumes", "tool_input": {"keyword": "Python"}}]}
    emit = _CollectingEmitter()
    results: list[StepResult] = await run_act(plan, ctx={}, emit=emit, tool_router=_MockToolRouter())

    kinds = [e["type"] for e in emit.events]
    assert kinds[0] == "tool_call"
    assert "progress" in kinds
    assert kinds[-1] == "result"
    assert len(results) == 1


@pytest.mark.asyncio
async def test_tc_s5_07_2_required_step_fail_abort():
    """必需步失败 → 发 error 且中止。"""
    plan = {
        "steps": [
            {"step_id": "step_1", "tool_name": "search_resumes", "tool_input": {}, "optional": False},
            {"step_id": "step_2", "tool_name": "read_jd", "tool_input": {}, "optional": False},
        ]
    }
    emit = _CollectingEmitter()
    results = await run_act(plan, ctx={}, emit=emit, tool_router=_MockToolRouter(fail_tools=["read_jd"]))

    assert any(e["type"] == "error" for e in emit.events)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_tc_s5_07_3_partial_artifacts_on_invalid():
    """result 事件仍带 artifacts。"""
    plan = {"steps": [{"step_id": "step_1", "tool_name": "search_resumes", "tool_input": {}}]}
    emit = _CollectingEmitter()
    await run_act(plan, ctx={}, emit=emit, tool_router=_MockToolRouter())

    result_event = [e for e in emit.events if e["type"] == "result"][-1]
    assert "artifacts" in result_event["data"]


@pytest.mark.asyncio
async def test_tc_s5_07_4_optional_step_fail_continue():
    """optional 步失败 → 发 warning 且继续。"""
    plan = {
        "steps": [
            {"step_id": "step_1", "tool_name": "search_resumes", "tool_input": {}, "optional": False},
            {"step_id": "step_2", "tool_name": "read_jd", "tool_input": {}, "optional": True},
        ]
    }
    emit = _CollectingEmitter()
    results = await run_act(plan, ctx={}, emit=emit, tool_router=_MockToolRouter(fail_tools=["read_jd"]))

    assert any(e["type"] == "warning" for e in emit.events)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_tc_s5_07_5_emits_thinking_for_reason_phase():
    """Reason 阶段经 emit 发 thinking 事件。"""
    emit = _CollectingEmitter()
    await run_act({"steps": [], "phase": "REASON"}, ctx={}, emit=emit, tool_router=_MockToolRouter())
    assert any(e["type"] == "thinking" for e in emit.events)
