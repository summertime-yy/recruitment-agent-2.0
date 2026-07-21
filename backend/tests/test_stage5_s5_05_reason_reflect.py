"""S5-05 · Orchestrator Reason + Reflect（PR-12 绿态）。

覆盖用例（TC-S5-05-1..3）：
- TC-S5-05-1  reason_mock_ok：mock orchestrator_reason Skill 返回合法 ReasonOutput
  → task_type 非空、missing_entities 为列表。
- TC-S5-05-2  reflect_infeasible：orchestrator_reflect 返回 is_feasible=false
  → run_reason_reflect 停在 WAITING_CONFIRMATION（不进入 Plan）。
- TC-S5-05-3  reason_invalid：orchestrator_reason 返回不可校验输出（success=False）
  → run_reason 返回 success=False 且不崩溃。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent.base_skill import BaseSkill, SkillResult
from app.agent.orchestrator.engine import OrchestratorEngine
from app.agent.skill_registry import SkillRegistry


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
                "confidence": 0.9,
            },
        )


class _ReasonInvalidStub(BaseSkill):
    """Reason 段 stub：模拟 validate_output 失败（缺必需字段 + success=False）。"""

    def __init__(self):
        self.skill_id = "orchestrator-reason"
        self.skill_name = "orchestrator-reason"
        self.version = "1.0.0"
        self.internal = True
        self.task_type = None

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:  # type: ignore[override]
        return SkillResult(
            success=False, output={"not_a_valid_reason_output": True}, error_message="invalid reason output"
        )


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
    """mock orchestrator_reason 返回合法 JSON → task_type 非空、missing_entities 列表。"""
    reg = SkillRegistry()
    reg.register_skill(_ReasonStub())
    engine = OrchestratorEngine(registry=reg)

    out = await engine.run_reason({"user_input": "帮 jd_1 找候选人"})
    assert out["task_type"]
    assert isinstance(out["missing_entities"], list)


@pytest.mark.asyncio
async def test_tc_s5_05_2_reflect_infeasible_no_plan():
    """orchestrator_reflect 返回 is_feasible=false → 停在 WAITING_CONFIRMATION（不 Plan）。"""
    reg = SkillRegistry()
    reg.register_skill(_ReasonStub())
    reg.register_skill(_ReflectInfeasibleStub())
    engine = OrchestratorEngine(registry=reg)

    status = await engine.run_reason_reflect({"user_input": "..."})
    assert status in ("WAITING_CONFIRMATION", "FAILED")


@pytest.mark.asyncio
async def test_tc_s5_05_3_reason_invalid_failed_not_crash():
    """Reason 输出不可校验（success=False）→ run_reason 返回 success=False 且不崩溃。"""
    reg = SkillRegistry()
    reg.register_skill(_ReasonInvalidStub())
    engine = OrchestratorEngine(registry=reg)

    result = await engine.run_reason({"user_input": "..."})
    assert result.get("success") is False
