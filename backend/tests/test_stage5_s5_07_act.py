"""S5-07 · Orchestrator Act + Reflect-Act + SSE emit（PR-12 红态骨架）。

归属 PR：PR-12（TASKS-STAGE5.md S5-07；SSE 发射到 Redis 属 PR-13）
覆盖用例（TC-S5-07-1..5）：
- TC-S5-07-1  event_order：`run_act` 单步依次发 `tool_call`→`progress(100)`→`result`。
- TC-S5-07-2  required_step_fail_abort：必需步 Skill FAILED → 发 `error` 且中止，已成功步产物在 `StepResult`。
- TC-S5-07-3  partial_artifacts_on_invalid：`orchestrator_reflect_act` 返回 `is_result_valid=false` → `result` 事件仍带 artifacts。
- TC-S5-07-4  optional_step_fail_continue：optional 步失败 → 发 `warning` 且继续。
- TC-S5-07-5  act_emits_thinking_for_reason_phase：Reason 阶段经 emit 发 `thinking` 事件。

注意：本文件为红态骨架。模块 `app.agent.orchestrator.act` 尚未实现，
顶部导入即触发 collection error（红）。待 PR-12 kickoff 裁定（Q2 emit 签名）后
实现 `run_act` 并填充断言。mock 目标为 `BaseSkill.execute` / `ToolRouter.dispatch`。
"""

from __future__ import annotations

from typing import Any

import pytest

# 模块尚未实现 → 导入即红（collection error）。
from app.agent.orchestrator.act import StepResult, run_act  # noqa: F401


class _CollectingEmitter:
    """测试用同步/异步 emitter：记录 emit 的事件序列。"""

    def __init__(self):
        self.events: list[dict[str, Any]] = []

    async def emit(self, ev: dict[str, Any]) -> None:
        self.events.append(ev)


@pytest.mark.asyncio
async def test_tc_s5_07_1_event_order():
    """run_act 单步依次发 tool_call → progress(100) → result。"""
    plan = {"steps": [{"tool_name": "search_resumes", "args": {"keyword": "Python"}}]}
    emit = _CollectingEmitter()
    results: list[StepResult] = await run_act(plan, ctx={}, emit=emit)  # TODO: 待 Q2 确认 emit 签名

    kinds = [e["type"] for e in emit.events]
    assert kinds[0] == "tool_call"
    assert "progress" in kinds
    assert kinds[-1] == "result"
    assert len(results) == 1


@pytest.mark.asyncio
async def test_tc_s5_07_2_required_step_fail_abort():
    """必需步 Skill FAILED → 发 error 且中止，已成功步产物在 StepResult。"""
    plan = {
        "steps": [
            {"tool_name": "search_resumes", "args": {}, "required": True},
            {"tool_name": "read_jd", "args": {}, "required": True},
        ]
    }
    emit = _CollectingEmitter()
    results = await run_act(plan, ctx={}, emit=emit)  # TODO: 待 Q2

    assert any(e["type"] == "error" for e in emit.events)
    # 已成功步的产物仍在 results 中（TODO: 待裁定精确结构）
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_tc_s5_07_3_partial_artifacts_on_invalid():
    """orchestrator_reflect_act 返回 is_result_valid=false → result 事件仍带 artifacts。"""
    plan = {"steps": [{"tool_name": "search_resumes", "args": {}}]}
    emit = _CollectingEmitter()
    results = await run_act(plan, ctx={}, emit=emit)  # TODO: 待 Q2

    result_event = [e for e in emit.events if e["type"] == "result"][-1]
    assert "artifacts" in result_event  # TODO: 待裁定字段名


@pytest.mark.asyncio
async def test_tc_s5_07_4_optional_step_fail_continue():
    """optional 步失败 → 发 warning 且继续。"""
    plan = {
        "steps": [
            {"tool_name": "search_resumes", "args": {}, "required": True},
            {"tool_name": "read_jd", "args": {}, "required": False},
        ]
    }
    emit = _CollectingEmitter()
    results = await run_act(plan, ctx={}, emit=emit)  # TODO: 待 Q2

    assert any(e["type"] == "warning" for e in emit.events)
    assert len(results) == 2  # 仍完成了两步


@pytest.mark.asyncio
async def test_tc_s5_07_5_emits_thinking_for_reason_phase():
    """Reason 阶段经 emit 发 thinking 事件。"""
    emit = _CollectingEmitter()
    # TODO: 待 Q2/Q3 确认 Reason 阶段是否经同一 emit 发 thinking
    await run_act(  # 占位：实际应触发 reason 阶段 emit
        {"steps": [], "phase": "REASON"}, ctx={}, emit=emit
    )
    assert any(e["type"] == "thinking" for e in emit.events)
