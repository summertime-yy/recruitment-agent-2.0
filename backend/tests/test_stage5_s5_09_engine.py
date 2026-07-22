"""PR-14 阶段 2 · Engine Q1/Q5/Q7 单测（engine-1..3）。

- engine-1：start_chat 立即返 {task_id, PLANNING} 且 db_updater 写入 PLANNING 行（Q5 (b1) + Q1）
- engine-2：_background_execute 经 db_updater 写 EXECUTING→COMPLETED（Q1 方案 B）
- engine-3：run_skip_to_score 使用外部传入 task_id（移除假前缀 task_skip_{jd_id}）
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest


class _FakeResult:
    def __init__(self, step_id: str, tool_name: str, success: bool = True, output: dict | None = None):
        self.step_id = step_id
        self.tool_name = tool_name
        self.success = success
        self.output = output


async def _make_engine(fake_redis, db_updater=None):
    from app.agent.orchestrator.engine import OrchestratorEngine
    from app.agent.orchestrator.event_buffer import EventBuffer

    buffer = EventBuffer(fake_redis)
    eng = OrchestratorEngine(event_buffer=buffer, db_updater=db_updater)
    return eng, buffer


async def test_engine_1_start_chat_returns_task_id_and_inserts_planning(fake_redis, mock_llm):
    db_updater = AsyncMock()
    eng, _ = await _make_engine(fake_redis, db_updater=db_updater)
    resp = await eng.start_chat("task_x1", "hello", context={"jd_id": "jd_1"})
    assert resp["status_code"] == 200
    assert resp["status"] == "PLANNING"
    assert resp["task_id"] == "task_x1"
    # 立即 INSERT PLANNING（Q5 (b1) 异步化 + Q1 方案 B）
    db_updater.assert_awaited()
    first_call = db_updater.call_args_list[0]
    assert first_call.args[1]["status"] == "PLANNING"
    # 收尾后台任务避免 event loop 残留
    bg = [t for t in asyncio.all_tasks() if t.get_name().startswith("orch-reason-plan-")]
    await asyncio.gather(*bg, return_exceptions=True)


async def test_engine_2_background_execute_writes_executing_then_completed(fake_redis, monkeypatch):
    from app.agent.orchestrator import act as act_mod

    db_updater = AsyncMock()
    eng, _ = await _make_engine(fake_redis, db_updater=db_updater)

    async def _fake_run_act(plan, ctx=None, emit=None, tool_router=None):
        return [_FakeResult("s1", "create_match_score", success=True, output={"match_score_id": "ms_1"})]

    monkeypatch.setattr(act_mod, "run_act", _fake_run_act)
    eng.run_reflect_act = AsyncMock(return_value={"final_result": "ok"})

    plan = {"steps": [{"step_id": "s1", "tool_name": "create_match_score", "tool_input": {"jd_id": "j", "resume_id": "r"}}]}
    await eng._background_execute("task_e2", plan, eng.event_buffer, db_updater)

    statuses = [c.args[1]["status"] for c in db_updater.call_args_list]
    assert "EXECUTING" in statuses
    assert "COMPLETED" in statuses
    completed = [c for c in db_updater.call_args_list if c.args[1]["status"] == "COMPLETED"][0]
    assert completed.args[1]["result"]["artifacts"][0]["type"] == "match_score"


async def test_engine_3_skip_to_score_uses_provided_task_id(fake_redis, monkeypatch):
    from app.agent.orchestrator import act as act_mod

    db_updater = AsyncMock()
    eng, _ = await _make_engine(fake_redis, db_updater=db_updater)

    async def _fake_run_act(plan, ctx=None, emit=None, tool_router=None):
        return [_FakeResult("step_score_0", "create_match_score", success=True, output={"match_score_id": "ms_1"})]

    monkeypatch.setattr(act_mod, "run_act", _fake_run_act)
    eng.run_reflect_act = AsyncMock(return_value={"final_result": "ok"})

    resp = await eng.run_skip_to_score("jd_9", ["r_1", "r_2"], task_id="task_real_999", db_updater=db_updater)
    assert resp["task_id"] == "task_real_999"  # 不是 task_skip_jd_9
    # 后台任务名用真实 task_id，收尾避免 event loop 残留
    bg = [t for t in asyncio.all_tasks() if t.get_name().startswith("orch-skip-task_real_999")]
    await asyncio.gather(*bg, return_exceptions=True)
    # db_updater 起始写到 EXECUTING（Q1 方案 B 第 2 处）
    assert any(c.args[1]["status"] == "EXECUTING" for c in db_updater.call_args_list)
