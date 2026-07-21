"""S5-08 · Task 生命周期/状态机（含 CANCELLED）+ 并发/超时/失败降级（PR-12 绿态）。

覆盖用例（TC-S5-08-1..8）：
- TC-S5-08-1  legal_transition_chain：PENDING→PLANNING→WAITING_CONFIRMATION→EXECUTING→COMPLETED 全合法。
- TC-S5-08-2  illegal_transition_rejected：COMPLETED→EXECUTING 抛 IllegalTransitionError。
- TC-S5-08-3  global_concurrency_429：活跃任务达上限 → 新 chat 返 429 TASK_LIMIT_EXCEEDED。
- TC-S5-08-4  skill_timeout_degrade：单 Skill 超时 → 该步 FAILED（error 事件）。
- TC-S5-08-5  task_overall_timeout：整体超时 → FAILED + error=TASK_TIMEOUT。
- TC-S5-08-6  transition_each_legal：矩阵每行合法转移各 ≥1 例。
- TC-S5-08-7  transition_each_illegal：矩阵外非法转移各 ≥1 例抛错。
- TC-S5-08-8  cancelled_transition：WAITING_CONFIRMATION→CANCELLED 合法；EXECUTING→CANCELLED 非法。
"""

from __future__ import annotations

import asyncio

import pytest

from app.agent.orchestrator.active_counter import InMemoryActiveCounter
from app.agent.orchestrator.engine import IllegalTransitionError, OrchestratorEngine, TransitionGuard


class _SlowRouter:
    """mock router：dispatch 故意睡 1s，用于触发超时。"""

    async def dispatch(self, tool_name, tool_input, db=None):
        await asyncio.sleep(1)
        return None


@pytest.mark.asyncio
async def test_tc_s5_08_1_legal_transition_chain():
    """PENDING→PLANNING→WAITING_CONFIRMATION→EXECUTING→COMPLETED 全合法。"""
    guard = TransitionGuard()
    states = ["PENDING", "PLANNING", "WAITING_CONFIRMATION", "EXECUTING", "COMPLETED"]
    cur = states[0]
    for nxt in states[1:]:
        cur = guard.transition(cur, nxt)
    assert cur == "COMPLETED"


@pytest.mark.asyncio
async def test_tc_s5_08_2_illegal_transition_rejected():
    """COMPLETED→EXECUTING 抛 IllegalTransitionError。"""
    guard = TransitionGuard()
    with pytest.raises(IllegalTransitionError):
        guard.transition("COMPLETED", "EXECUTING")


@pytest.mark.asyncio
async def test_tc_s5_08_3_global_concurrency_429():
    """活跃任务达上限 → 新 chat 返 429 TASK_LIMIT_EXCEEDED。"""
    counter = InMemoryActiveCounter(start=10)
    engine = OrchestratorEngine(active_counter=counter)
    resp = await engine.run_chat({"user_input": "..."})
    assert resp["status_code"] == 429
    assert resp["error"] == "TASK_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_tc_s5_08_4_skill_timeout_degrade():
    """单 Skill 超时阈值极小 → 该步 FAILED（error 事件）。"""
    engine = OrchestratorEngine(skill_timeout_sec=0.01)
    result = await engine.run_step_with_timeout({"tool_name": "search_resumes", "args": {}}, tool_router=_SlowRouter())
    assert result["status"] == "FAILED"
    assert any(e.get("type") == "error" for e in result.get("events", []))


@pytest.mark.asyncio
async def test_tc_s5_08_5_task_overall_timeout():
    """整体超时 → FAILED + error=TASK_TIMEOUT。"""
    engine = OrchestratorEngine(task_timeout_sec=0.01)
    result = await engine.run_task_with_overall_timeout(
        {"plan": {"steps": [{"tool_name": "search_resumes", "tool_input": {}}]}}, tool_router=_SlowRouter()
    )
    assert result["status"] == "FAILED"
    assert result["error"] == "TASK_TIMEOUT"


@pytest.mark.parametrize(
    "src,dst",
    [
        ("PENDING", "PLANNING"),
        ("WAITING_CONFIRMATION", "CANCELLED"),
        ("EXECUTING", "COMPLETED"),
    ],
)
@pytest.mark.asyncio
async def test_tc_s5_08_6_transition_each_legal(src, dst):
    """矩阵每行合法转移各 ≥1 例。"""
    guard = TransitionGuard()
    assert guard.transition(src, dst) == dst


@pytest.mark.parametrize(
    "src,dst",
    [
        ("COMPLETED", "EXECUTING"),
        ("EXECUTING", "CANCELLED"),
    ],
)
@pytest.mark.asyncio
async def test_tc_s5_08_7_transition_each_illegal(src, dst):
    """矩阵外非法转移各 ≥1 例抛 IllegalTransitionError。"""
    guard = TransitionGuard()
    with pytest.raises(IllegalTransitionError):
        guard.transition(src, dst)


@pytest.mark.asyncio
async def test_tc_s5_08_8_cancelled_transition_from_waiting_confirmation():
    """WAITING_CONFIRMATION→CANCELLED 合法；EXECUTING→CANCELLED 非法（抛错）。"""
    guard = TransitionGuard()
    assert guard.transition("WAITING_CONFIRMATION", "CANCELLED") == "CANCELLED"
    with pytest.raises(IllegalTransitionError):
        guard.transition("EXECUTING", "CANCELLED")
