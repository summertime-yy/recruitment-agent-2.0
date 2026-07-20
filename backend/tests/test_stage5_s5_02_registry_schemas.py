"""S5-02 · SkillRegistry 扩展 + SSE/Agent Schema TDD 测试骨架（PR-10 交付物，当前「红」态）。

归属 PR：PR-10（TASKS-STAGE5.md S5-02，依赖 S5-01）
TDD 约定：先写测试（红）再实现（绿）。本文件导入的模块/方法在 PR-10 落地前不存在，
`uv run pytest backend/tests/test_stage5_s5_02_registry_schemas.py` 当前应整文件收集失败（红）。

覆盖用例：
- TC-S5-02-1  sse_event_id_type_enum（SSEEvent 含 id；type 仅 8 枚举，非法抛 ValidationError）
- TC-S5-02-2  chat_request_requires_message（AgentChatRequest 缺 message → ValidationError）
- TC-S5-02-3  plan_roundtrip（Plan/PlanStep 含 step_id(str)/optional 默认 false）
- TC-S5-02-4  internal_skill_excluded_from_dispatchable（list_dispatchable 排除 internal；get 可取）
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# 待 PR-10 实现的 Schema（当前导入即红）
from app.schemas.agent import (  # noqa: F401
    AgentChatRequest,
    ExecutionPhase,
    Plan,
    PlanStep,
    SSEEvent,
    SSEEventType,
    TaskStatus,
)

# 待 PR-10 扩展的 Registry（get / list_dispatchable 当前不存在）
from app.agent.skill_registry import SkillRegistry  # noqa: F401


# --- TC-S5-02-1 ---------------------------------------------------------------
def test_tc_s5_02_1_sse_event_id_type_enum():
    """SSEEvent 含 id；type 仅允许 8 种枚举，非法值抛 ValidationError。"""
    # 非法 type → 校验失败
    with pytest.raises(ValidationError):
        SSEEvent(type="bogus", task_id="task_x", timestamp="2026-07-20T00:00:00Z", data={})

    # 合法构造 + id 字段存在
    ev = SSEEvent(
        id="1",
        type="thinking",
        task_id="task_x",
        timestamp="2026-07-20T00:00:00Z",
        data={"content": "推理中"},
    )
    assert ev.id == "1"
    assert ev.type == SSEEventType.THINKING

    # 8 类事件类型均可构造
    for t in ["thinking", "plan", "tool_call", "progress", "result", "error", "warning", "system"]:
        SSEEvent(id="1", type=t, task_id="t", timestamp="x", data={})


# --- TC-S5-02-2 ---------------------------------------------------------------
def test_tc_s5_02_2_chat_request_requires_message():
    """AgentChatRequest 缺 message → 校验失败。"""
    with pytest.raises(ValidationError):
        AgentChatRequest()  # message 必填

    # 合法构造
    req = AgentChatRequest(message="帮我匹配候选人", context={"jd_id": "jd_1"})
    assert req.message == "帮我匹配候选人"


# --- TC-S5-02-3 ---------------------------------------------------------------
def test_tc_s5_02_3_plan_roundtrip():
    """Plan / PlanStep 序列化：step_id 为字符串；optional 缺省 false，可置 true。"""
    step = PlanStep(
        step_id="step_1",
        description="检索简历",
        tool_name="search_resumes",
        params={"jd_id": "jd_1"},
        expected_output="候选列表",
    )
    assert step.step_id == "step_1"
    assert step.optional is False, "PlanStep.optional 缺省应为 false"

    step_optional = PlanStep(
        step_id="step_2",
        description="可选步",
        tool_name="t",
        params={},
        expected_output="o",
        optional=True,
    )
    assert step_optional.optional is True

    plan = Plan(task_id="task_x", steps=[step, step_optional])
    assert plan.task_id == "task_x"
    assert len(plan.steps) == 2
    assert plan.steps[1].optional is True


# --- TC-S5-02-4 ---------------------------------------------------------------
def test_tc_s5_02_4_internal_skill_excluded_from_dispatchable():
    """list_dispatchable() 排除 internal=true 的 Skill；get() 仍可取到 internal Skill。"""

    class _InternalStub:
        skill_id = "orchestrator-reason"
        internal = True
        version = "1.0.0"

    reg = SkillRegistry()
    reg.register_skill(_InternalStub())

    # engine 内部调用：get() 可取 internal Skill
    assert reg.get("orchestrator-reason") is not None

    # Tool Router 调用：list_dispatchable() 过滤 internal
    dispatchable = reg.list_dispatchable()
    assert all(not getattr(s, "internal", False) for s in dispatchable)
    dispatchable_ids = [getattr(s, "skill_id", None) for s in dispatchable]
    assert "orchestrator-reason" not in dispatchable_ids
