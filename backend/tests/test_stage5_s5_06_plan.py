"""S5-06 · Orchestrator Plan + Reflect-Plan（PR-12 红态骨架）。

归属 PR：PR-12（TASKS-STAGE5.md S5-06）
覆盖用例（TC-S5-06-1..3）：
- TC-S5-06-1  plan_tools_valid：`orchestrator_plan` 产出 `steps[].tool_name` 全在白名单。
- TC-S5-06-2  reflect_plan_adopt_adjusted：`is_plan_sound=false` 且有 `adjusted_plan` → 采用之。
- TC-S5-06-3  reflect_plan_detect_bad_tool：plan 含未注册 `tool_name` → `is_plan_sound=false` 并记 `issues`。

注意：本文件为红态骨架。模块 `app.agent.orchestrator.engine` 尚未实现，
顶部导入即触发 collection error（红）。待 PR-12 kickoff 裁定（Q1-Q5）后实现
engine 并填充断言细节。mock 目标为 `BaseSkill.execute`（与 TEST-PLAN 一致）。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent.base_skill import BaseSkill, SkillResult
from app.agent.skill_registry import SkillRegistry

from app.agent.orchestrator.engine import OrchestratorEngine  # noqa: F401


class _PlanStub(BaseSkill):
    def __init__(self):
        self.skill_id = "orchestrator-plan"
        self.skill_name = "orchestrator-plan"
        self.version = "1.0.0"
        self.internal = True
        self.task_type = None

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:  # type: ignore[override]
        return SkillResult(
            success=True,
            output={"steps": [{"tool_name": "search_resumes", "args": {"keyword": "Python"}}]},
        )


class _PlanBadToolStub(BaseSkill):
    def __init__(self):
        self.skill_id = "orchestrator-plan"
        self.skill_name = "orchestrator-plan"
        self.version = "1.0.0"
        self.internal = True
        self.task_type = None

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:  # type: ignore[override]
        return SkillResult(
            success=True,
            output={"steps": [{"tool_name": "not_a_real_tool", "args": {}}]},
        )


class _ReflectPlanAdoptStub(BaseSkill):
    def __init__(self):
        self.skill_id = "orchestrator-reflect-plan"
        self.skill_name = "orchestrator-reflect-plan"
        self.version = "1.0.0"
        self.internal = True
        self.task_type = None

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:  # type: ignore[override]
        return SkillResult(
            success=True,
            output={
                "is_plan_sound": False,
                "issues": ["tool 不可用"],
                "adjusted_plan": {"steps": [{"tool_name": "search_resumes", "args": {}}]},
            },
        )


@pytest.mark.asyncio
async def test_tc_s5_06_1_plan_tools_valid():
    """orchestrator_plan 产出 steps[].tool_name 全在白名单。"""
    reg = SkillRegistry()
    reg.register_skill(_PlanStub())
    engine = OrchestratorEngine(registry=reg)

    plan = await engine.run_plan({"reason_output": {}})  # TODO: 待 Q3 确认签名
    tool_names = [s["tool_name"] for s in plan["steps"]]
    for name in tool_names:
        assert name in engine.dispatchable_tool_names()  # TODO: 待裁定白名单来源


@pytest.mark.asyncio
async def test_tc_s5_06_2_reflect_plan_adopt_adjusted():
    """is_plan_sound=false 且有 adjusted_plan → 采用之。"""
    reg = SkillRegistry()
    reg.register_skill(_ReflectPlanAdoptStub())
    engine = OrchestratorEngine(registry=reg)

    adopted = await engine.run_reflect_plan({"plan": {"steps": []}})  # TODO: 待 Q3 确认
    assert adopted["is_plan_sound"] is True
    assert adopted["steps"][0]["tool_name"] == "search_resumes"


@pytest.mark.asyncio
async def test_tc_s5_06_3_reflect_plan_detect_bad_tool():
    """plan 含未注册 tool_name → is_plan_sound=false 并记 issues。"""
    reg = SkillRegistry()
    reg.register_skill(_PlanBadToolStub())
    reg.register_skill(_ReflectPlanAdoptStub())
    engine = OrchestratorEngine(registry=reg)

    reflect = await engine.run_reflect_plan(  # TODO: 待 Q3 确认
        {"plan": {"steps": [{"tool_name": "not_a_real_tool", "args": {}}]}}
    )
    assert reflect["is_plan_sound"] is False
    assert reflect["issues"]
