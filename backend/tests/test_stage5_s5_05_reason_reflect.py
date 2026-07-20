"""S5-05 · Orchestrator Reason + Reflect（PR-12 红态骨架）。

归属 PR：PR-12（TASKS-STAGE5.md S5-05）
覆盖用例（TC-S5-05-1..3）：
- TC-S5-05-1  reason_mock_ok：mock `orchestrator_reason` Skill `execute` 返回合法 JSON
  → `ReasonOutput.task_type` 非空、`missing_entities` 列表。
- TC-S5-05-2  reflect_infeasible：`orchestrator_reflect` 返回 `is_feasible=false`
  → 引擎进入 WAITING_CONFIRMATION/FAILED（不 Plan）。
- TC-S5-05-3  reason_invalid_json：Skill `validate_output` 失败
  → 写 execution FAILED 且不崩溃。

注意：本文件为红态骨架。模块 `app.agent.orchestrator.engine` 尚未实现，
顶部导入即触发 collection error（红）。待 PR-12 kickoff 裁定（Q1-Q5）后实现
engine 并填充断言细节。mock 目标为 `BaseSkill.execute`（与 TEST-PLAN 一致）。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent.base_skill import BaseSkill, SkillResult
from app.agent.skill_registry import SkillRegistry

# 模块尚未实现 → 导入即红（collection error）。
from app.agent.orchestrator.engine import OrchestratorEngine  # noqa: F401


class _ReasonStub(BaseSkill):
    """Reason 段 stub：返回合法 ReasonOutput。"""

    def __init__(self):
        self.skill_id = "orchestrator-reason"
        self.skill_name = "orchestrator-reason"
        self.version = "1.0.0"
        self.internal = True
        self.task_type = None

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:  # type: ignore[override]
        return SkillResult(
            success=True,
            output={
                "task_type": "match",
                "intent_summary": "为 JD 匹配候选人",
                "parsed_entities": {"jd_id": "jd_1"},
                "missing_entities": [],
            },
        )


class _ReasonInvalidStub(BaseSkill):
    """Reason 段 stub：返回非法 JSON（缺必需字段）。"""

    def __init__(self):
        self.skill_id = "orchestrator-reason"
        self.skill_name = "orchestrator-reason"
        self.version = "1.0.0"
        self.internal = True
        self.task_type = None

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:  # type: ignore[override]
        return SkillResult(success=True, output={"not_a_valid_reason_output": True})


class _ReflectInfeasibleStub(BaseSkill):
    """Reflect 段 stub：返回不可行。"""

    def __init__(self):
        self.skill_id = "orchestrator-reflect"
        self.skill_name = "orchestrator-reflect"
        self.version = "1.0.0"
        self.internal = True
        self.task_type = None

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:  # type: ignore[override]
        return SkillResult(
            success=True,
            output={"is_feasible": False, "blocking_reason": "缺少 jd_id", "suggestion": None},
        )


@pytest.mark.asyncio
async def test_tc_s5_05_1_reason_mock_ok():
    """mock orchestrator_reason Skill execute 返回合法 JSON → task_type 非空、missing_entities 列表。"""
    reg = SkillRegistry()
    reg.register_skill(_ReasonStub())
    engine = OrchestratorEngine(registry=reg)  # TODO: 待 Q3 确认入口签名

    out = await engine.run_reason({"user_input": "帮 jd_1 找候选人"})  # TODO: 待 Q3 确认
    assert out["task_type"]  # 非空
    assert isinstance(out["missing_entities"], list)


@pytest.mark.asyncio
async def test_tc_s5_05_2_reflect_infeasible_no_plan():
    """orchestrator_reflect 返回 is_feasible=false → 引擎停在 WAITING_CONFIRMATION/FAILED（不 Plan）。"""
    reg = SkillRegistry()
    reg.register_skill(_ReasonStub())
    reg.register_skill(_ReflectInfeasibleStub())
    engine = OrchestratorEngine(registry=reg)

    status = await engine.run_reason_reflect({"user_input": "..."})  # TODO: 待 Q3 确认
    assert status in ("WAITING_CONFIRMATION", "FAILED")
    # 不进入 Plan 阶段（TODO: 待裁定确认如何断言"未 Plan"）


@pytest.mark.asyncio
async def test_tc_s5_05_3_reason_invalid_json_failed_not_crash():
    """Skill validate_output 失败 → 写 execution FAILED 且不崩溃。"""
    reg = SkillRegistry()
    reg.register_skill(_ReasonInvalidStub())
    engine = OrchestratorEngine(registry=reg)

    result = await engine.run_reason({"user_input": "..."})  # TODO: 待 Q3 确认
    # TODO: 待裁定输出形态（execution 记录 / SkillResult.success=False）
    assert result.get("success") is False
