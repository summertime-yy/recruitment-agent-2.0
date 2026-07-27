"""S5.1 · PR-20 执行记录（TC-S5.1-1..6）。

红测骨架（Commit 1）：6 个 xfail，覆盖 run_act callbacks / DB execution writer / cancel CANCELLED。

"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.orchestrator.act import StepResult, run_act
from app.agent.orchestrator.engine import OrchestratorEngine
from app.models.execution import Execution

# ---------------------------------------------------------------------------

pytestmark = pytest.mark.asyncio


class _FakeRouter:
    """简易 mock ToolRouter：正常返回成功 SkillResult。"""

    def __init__(self, fail_tools: frozenset[str] | None = None):
        self._fail = fail_tools or frozenset()

    async def dispatch(self, tool_name: str, tool_input: dict[str, Any], db: Any = None):
        from app.agent.base_skill import SkillResult

        if tool_name in self._fail:
            return SkillResult(success=False, error_message=f"mock-fail:{tool_name}", output={})
        return SkillResult(success=True, output={"tool": tool_name, "echo": tool_input})


class _Collector:
    """记录 callback 调用序列。"""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def on_start(self, step_id: str, tool_name: str) -> None:
        self.calls.append({"type": "start", "step_id": step_id, "tool_name": tool_name})

    async def on_end(self, step_id: str, result: StepResult) -> None:
        self.calls.append({"type": "end", "step_id": step_id, "success": result.success})


# ====== TC-S5.1-1 ======


@pytest.mark.xfail(reason="PR-20 commit 1 red: on_step_start/on_step_end not wired to run_act")
async def test_tc_s5_1_1_callbacks_called_in_order():
    """on_step_start / on_step_end 在每步执行前后依次调用。"""
    plan = {
        "steps": [
            {"step_id": "s1", "tool_name": "search_resumes", "tool_input": {}},
            {"step_id": "s2", "tool_name": "score", "tool_input": {}},
        ],
    }
    c = _Collector()
    results = await run_act(plan, on_step_start=c.on_start, on_step_end=c.on_end, tool_router=_FakeRouter())
    assert len(results) == 2
    assert c.calls == [
        {"type": "start", "step_id": "s1", "tool_name": "search_resumes"},
        {"type": "end", "step_id": "s1", "success": True},
        {"type": "start", "step_id": "s2", "tool_name": "score"},
        {"type": "end", "step_id": "s2", "success": True},
    ]


# ====== TC-S5.1-2 ======


@pytest.mark.xfail(reason="PR-20 commit 2 red: db execution writer not created")
@pytest.mark.usefixtures("db_session")
async def test_tc_s5_1_2_execution_writer_creates_record_on_start(db_session: AsyncSession):
    """DB execution writer 在每步 START 时 INSERT execution 行。"""
    from app.agent.orchestrator.engine import _make_db_execution_writer  # noqa: F811

    plan = {"steps": [{"step_id": "s1", "tool_name": "search_resumes", "tool_input": {}}]}
    writer = _make_db_execution_writer(db_session, task_id="task-w2")

    # 模拟 run_act 调用 writer
    await writer("s1", "search_resumes", action="start")

    # 验证 DB 已写入
    row = await db_session.get(Execution, "mock-exec-id")
    # 在 writer 未实现时这里无法拿到真实 execution_id
    # 我们直接查询 task 关联的 executions
    from sqlalchemy import select

    stmt = select(Execution).where(Execution.task_id == "task-w2", Execution.step_id == "s1")
    result = await db_session.execute(stmt)
    rows = result.scalars().all()
    assert len(rows) == 1
    exec_row = rows[0]
    assert exec_row.execution_id.startswith("exec_")
    assert exec_row.task_id == "task-w2"
    assert exec_row.step_id == "s1"
    assert exec_row.phase == "ACT"
    assert exec_row.tool_name == "search_resumes"
    assert exec_row.execution_status == "PENDING"
    assert exec_row.started_at is not None
    assert exec_row.finished_at is None


# ====== TC-S5.1-3 ======


@pytest.mark.xfail(reason="PR-20 commit 2 red: db execution writer update not implemented")
@pytest.mark.usefixtures("db_session")
async def test_tc_s5_1_3_execution_writer_updates_on_end(db_session: AsyncSession):
    """DB execution writer 在每步 END 时 UPDATE execution 行（status + finished_at + execution_time_ms）。"""
    plan = {"steps": [{"step_id": "s1", "tool_name": "search_resumes", "tool_input": {}}]}
    writer = _make_db_execution_writer(db_session, task_id="task-w3")

    await writer("s1", "search_resumes", action="start")
    # 模拟执行耗时
    await asyncio.sleep(0.01)
    sr = StepResult(step_id="s1", tool_name="search_resumes", success=True, output={"ok": True})
    await writer("s1", "search_resumes", action="end", result=sr)

    # 验证 UPDATE
    from sqlalchemy import select

    stmt = select(Execution).where(Execution.task_id == "task-w3", Execution.step_id == "s1")
    result = await db_session.execute(stmt)
    row = result.scalars().one()
    assert row.execution_status == "COMPLETED"
    assert row.output_result == {"ok": True}
    assert row.finished_at is not None
    assert row.execution_time_ms is not None and row.execution_time_ms > 0


# ====== TC-S5.1-4 ======


@pytest.mark.xfail(reason="PR-20 commit 3 red: cancel not writing CANCELLED to DB")
@pytest.mark.usefixtures("db_session")
async def test_tc_s5_1_4_cancel_writes_cancelled(db_session: AsyncSession):
    """Engine cancel 将 executions 表的执行状态标为 CANCELLED。"""
    engine = OrchestratorEngine()

    # 通过 run_execute 写入一条 ACT execution
    from sqlalchemy import select

    # 先直接写一条 execution 行模拟已启动但未完成的步骤
    exec_row = Execution(
        execution_id="exec-cancel-1",
        task_id="task-c4",
        step_id="s1",
        phase="ACT",
        tool_name="search_resumes",
        execution_status="PENDING",
        started_at=None,
    )
    db_session.add(exec_row)
    await db_session.commit()

    # 执行 cancel
    await engine.run_cancel("task-c4", db=db_session, event_buffer=None)

    # 验证 CANCELLED
    await db_session.refresh(exec_row)
    assert exec_row.execution_status == "CANCELLED"
    assert exec_row.finished_at is not None


# ====== TC-S5.1-5 ======


@pytest.mark.xfail(reason="PR-20 commit 1 red: failed step on_step_end not emitting FAILED")
async def test_tc_s5_1_5_failed_step_calls_on_end_with_failed():
    """必需步失败时 on_step_end 仍被调用，且 result.success == False。"""
    plan = {"steps": [{"step_id": "s1", "tool_name": "fail_tool", "tool_input": {}}]}
    c = _Collector()
    results = await run_act(
        plan, on_step_start=c.on_start, on_step_end=c.on_end, tool_router=_FakeRouter(fail_tools=frozenset({"fail_tool"}))
    )
    assert len(results) == 1
    assert c.calls == [
        {"type": "start", "step_id": "s1", "tool_name": "fail_tool"},
        {"type": "end", "step_id": "s1", "success": False},
    ]


# ====== TC-S5.1-6 ======


@pytest.mark.xfail(reason="PR-20 commit 2 red: run_act with writer creates one execution per step")
@pytest.mark.usefixtures("db_session")
async def test_tc_s5_1_6_run_act_creates_multiple_execution_records(db_session: AsyncSession):
    """完整的 run_act → 每个成功 step 产生一条 execution 记录。"""
    plan = {
        "steps": [
            {"step_id": "s1", "tool_name": "search_resumes", "tool_input": {}},
            {"step_id": "s2", "tool_name": "score", "tool_input": {}},
        ],
    }
    writer = _make_db_execution_writer(db_session, task_id="task-w6")

    await run_act(
        plan,
        on_step_start=lambda sid, tn: writer(sid, tn, action="start"),
        on_step_end=lambda sid, sr: asyncio.ensure_future(writer(sid, sr.tool_name, action="end", result=sr)),
        tool_router=_FakeRouter(),
    )
    # 刷新 DB 并查行
    await db_session.commit()
    from sqlalchemy import select

    stmt = select(Execution).where(Execution.task_id == "task-w6").order_by(Execution.created_at)
    result = await db_session.execute(stmt)
    rows = result.scalars().all()
    assert len(rows) == 2
    assert rows[0].step_id == "s1"
    assert rows[0].execution_status == "COMPLETED"
    assert rows[1].step_id == "s2"
    assert rows[1].execution_status == "COMPLETED"
