"""PR-13 · run_execute 后台任务 + EventBuffer 集成测试（execute-1..2）。

- TC-S5-13-execute-1：run_execute 立即返回 EXECUTING，后台 orch-execute-* 任务已注册
- TC-S5-13-execute-2：后台任务完成后 RESULT 事件入 buffer，content 非空，artifacts 结构合规
"""

import asyncio

from app.agent.base_skill import SkillResult


class _FakeReflectActSkill:
    """stub orchestrator-reflect-act：返回固定 final_result。"""

    internal = True
    skill_id = "orchestrator-reflect-act"

    async def execute(self, inp):
        return type(
            "R", (), {"success": True, "output": {"final_result": "合并完成", "issues": []}, "error_message": None}
        )()


class _FakeRegistry:
    def get(self, skill_id):
        if skill_id == "orchestrator-reflect-act":
            return _FakeReflectActSkill()
        return None

    def list_dispatchable(self):
        return []


class _MockRouter:
    async def dispatch(self, name, inp, db=None):
        return SkillResult(success=True, output={"match_score_id": "ms_1", "id": "ms_1"})


async def _make_engine(fake_redis):
    from app.agent.orchestrator.engine import OrchestratorEngine
    from app.agent.orchestrator.event_buffer import EventBuffer

    buffer = EventBuffer(fake_redis)
    eng = OrchestratorEngine(
        registry=_FakeRegistry(),
        tool_router=_MockRouter(),
        event_buffer=buffer,
    )
    return eng, buffer


async def test_s5_13_execute_1_returns_executing_immediately(fake_redis):
    eng, _ = await _make_engine(fake_redis)
    plan = {
        "steps": [
            {"step_id": "s1", "tool_name": "create_match_score", "tool_input": {"jd_id": "jd_1", "resume_id": "r_1"}}
        ]
    }
    result = await eng.run_execute("task_x", plan=plan)
    assert result["status"] == "EXECUTING"
    bg = [t for t in asyncio.all_tasks() if t.get_name().startswith("orch-execute-")]
    assert len(bg) >= 1
    # 收尾：await 后台任务避免 event loop 上残留 pending task
    await asyncio.gather(*bg, return_exceptions=True)


async def test_s5_13_execute_2_result_in_buffer(fake_redis):
    eng, buffer = await _make_engine(fake_redis)
    plan = {
        "steps": [
            {"step_id": "s1", "tool_name": "create_match_score", "tool_input": {"jd_id": "jd_1", "resume_id": "r_1"}}
        ]
    }
    await eng.run_execute("task_x", plan=plan)
    # 等待后台任务完成
    await asyncio.gather(*[t for t in asyncio.all_tasks() if t.get_name().startswith("orch-execute-")])
    events = await buffer.read_after("task_x")
    result_events = [e for e in events if e.type.value == "result"]
    assert result_events, "应有 task 级 RESULT 事件"
    data = result_events[-1].data  # 任务级终态 result 是最后一条
    assert data.get("content")  # 非空
    artifacts = data.get("artifacts", [])
    assert len(artifacts) == 1
    assert artifacts[0]["type"] == "match_score"
    assert artifacts[0]["ref_id"] == "ms_1"
