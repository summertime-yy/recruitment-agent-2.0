"""S5-08 · Task 生命周期/状态机（含 CANCELLED）+ 并发/超时/失败降级（PR-12 红态骨架）。

归属 PR：PR-12（TASKS-STAGE5.md S5-08）
覆盖用例（TC-S5-08-1..8）：
- TC-S5-08-1  legal_transition_chain：PENDING→PLANNING→WAITING_CONFIRMATION→EXECUTING→COMPLETED 全合法。
- TC-S5-08-2  illegal_transition_rejected：COMPLETED→EXECUTING 抛 `IllegalTransitionError` 且状态不变。
- TC-S5-08-3  global_concurrency_429：活跃任务 mock 达 10 → 新 `chat` 返 429 `TASK_LIMIT_EXCEEDED`。
- TC-S5-08-4  skill_timeout_degrade：单 Skill 超时阈值设极小 → 该步 `error` 且 Task FAILED（部分 artifacts 留 result）。
- TC-S5-08-5  task_overall_timeout：整体 600s 超时 → Task FAILED + `error(TASK_TIMEOUT)`。
- TC-S5-08-6  transition_each_legal：遍历 PLAN §2 Q2 矩阵每行合法转移各 ≥1 例（参数化，含 CANCELLED 两条）。
- TC-S5-08-7  transition_each_illegal：矩阵外每类非法转移各 ≥1 例抛错。
- TC-S5-08-8  cancelled_transition_from_waiting_confirmation：WAITING_CONFIRMATION→CANCELLED 合法；EXECUTING→CANCELLED 非法（抛错）。

注意：本文件为红态骨架。模块 `app.agent.orchestrator.engine` 尚未实现，
顶部导入即触发 collection error（红）。待 PR-12 kickoff 裁定（Q4/Q5）后实现
`OrchestratorEngine` / `TransitionGuard` 并填充断言。
"""

from __future__ import annotations

import pytest

from app.agent.orchestrator.engine import (  # noqa: F401
    IllegalTransitionError,
    OrchestratorEngine,
    TransitionGuard,
)


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
    """COMPLETED→EXECUTING 抛 IllegalTransitionError 且状态不变。"""
    guard = TransitionGuard()
    with pytest.raises(IllegalTransitionError):
        guard.transition("COMPLETED", "EXECUTING")
    # 状态不变（TODO: 待裁定 guard 是否就地修改或返回新值）


@pytest.mark.asyncio
async def test_tc_s5_08_3_global_concurrency_429():
    """活跃任务 mock 达 10 → 新 chat 返 429 TASK_LIMIT_EXCEEDED。"""
    counter = _MemoryActiveCounter(start=10)  # TODO: 待 Q4 ActiveCounter 抽象
    engine = OrchestratorEngine(active_counter=counter)
    resp = await engine.run_chat({"user_input": "..."})  # TODO: 待 Q3
    assert resp["status_code"] == 429
    assert resp["error"] == "TASK_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_tc_s5_08_4_skill_timeout_degrade():
    """单 Skill 超时阈值设极小 → 该步 error 且 Task FAILED（部分 artifacts 留 result）。"""
    engine = OrchestratorEngine(skill_timeout_sec=0.01)  # TODO: 待 Q5
    result = await engine.run_step_with_timeout(  # TODO: 待裁定方法名
        {"tool_name": "search_resumes", "args": {}}
    )
    assert result["status"] == "FAILED"
    assert any(e.get("type") == "error" for e in result.get("events", []))


@pytest.mark.asyncio
async def test_tc_s5_08_5_task_overall_timeout():
    """整体 600s 超时 → Task FAILED + error(TASK_TIMEOUT)。"""
    engine = OrchestratorEngine(task_timeout_sec=0.01)  # TODO: 待 Q5
    result = await engine.run_task_with_overall_timeout({})  # TODO: 待裁定方法名
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
    """遍历 PLAN §2 Q2 矩阵每行合法转移各 ≥1 例（含 CANCELLED）。"""
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
    """矩阵外每类非法转移各 ≥1 例抛 IllegalTransitionError。"""
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


class _MemoryActiveCounter:
    """TODO: 待 Q4 裁定 ActiveCounter 抽象接口后替换为正式实现（测试用内存 mock）。"""

    def __init__(self, start: int = 0):
        self._n = start

    def incr(self) -> int:
        self._n += 1
        return self._n

    def decr(self) -> int:
        self._n = max(0, self._n - 1)
        return self._n

    def current(self) -> int:
        return self._n
