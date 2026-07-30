"""PR-26 Task-3 hydration 测试。

严格对齐 docs/planning/stage5/PR26-KICKOFF-DECISION.md §三.3（5 个 TC 逐字）：

TC-PR26-1  test_hydrate_candidate_profile_maps_parsed_content_and_tags（unit）
            -> hydrate_tool_input("candidate-profile", {"candidate_id":"res_x"}, db)
            -> parsed_content == {"skills":["Python"]} 且 existing_tags == ["高潜"]
TC-PR26-2  test_hydrate_candidate_profile_missing_resume_raises（unit）
            -> DB 空 · hydrate_tool_input("candidate-profile", {"candidate_id":"no_such"}, db)
            -> 抛 ToolParamError
TC-PR26-3  test_run_act_candidate_profile_end_to_end（integration）
            -> run_act 跑 candidate-profile 单步（resume 预置）· StepResult.success=True
            -> skill 收到的入参 parsed_content 非空 · existing_tags == ["高潜"]
TC-PR26-4  test_hydrate_candidate_merge_fills_resume_fields（integration）
            -> hydrate_tool_input("candidate-merge", {"resumes":[{"resume_id":"a"},{"resume_id":"b"}]}, db)
            -> resumes[0].parsed_content 非空 · resumes[1].parsed_content 非空 · resumes[0].candidate_name == DB 值
TC-PR26-5  test_run_act_candidate_profile_missing_resume_emits_error_event（integration）
            -> DB 无该 candidate_id · run_act 跑 candidate-profile 单步
            -> emit 列表含 SSEEventType.ERROR 事件 · StepResult.success=False 且 error_message 含 "not found"
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator.act import run_act

# 被测符号（commit 2 才落地 -> 本 commit 1 为 red）
from app.agent.orchestrator.hydration import hydrate_tool_input
from app.agent.orchestrator.tool_router import ToolParamError, ToolRouter
from app.api.v1.agent import SSEEvent, SSEEventType
from app.models.resume import Resume


# ---------------------------------------------------------------------------
# 辅助：fake SkillRegistry + 捕获 tool_input 的 fake skill
# ---------------------------------------------------------------------------
class _FakeSkill:
    internal = False

    def __init__(self):
        self.last_input = None

    async def execute(self, tool_input):
        self.last_input = tool_input
        return type("SkillResult", (), {"success": True, "output": {
            "profile_tags": [], "summary": "", "strengths": [], "risks": [],
        }})()


class _FakeRegistry:
    def __init__(self):
        self.skill = _FakeSkill()

    def get_skill(self, tool_name: str):
        if tool_name == "candidate-profile":
            return self.skill
        raise KeyError(tool_name)


def _make_router() -> tuple[ToolRouter, _FakeSkill]:
    reg = _FakeRegistry()
    return ToolRouter(registry=reg), reg.skill


def _collector_factory():
    events: list = []

    async def collector(event: SSEEvent) -> None:
        events.append(event)

    return collector, events


def _make_resume(resume_id: str, parsed_content, tags=None, candidate_name: str = "") -> Resume:
    return Resume(
        resume_id=resume_id,
        candidate_name=candidate_name,
        file_name=f"{resume_id}.pdf",
        file_path=f"raw/{resume_id}.pdf",
        file_type="pdf",
        parsed_content=parsed_content,
        tags=tags,
    )


def _plan_with(tool_input: dict) -> dict:
    return {
        "task_id": "task_pr26_int",
        "steps": [
            {"step_id": "s1", "tool_name": "candidate-profile", "tool_input": tool_input},
        ],
    }


# ---------------------------------------------------------------------------
# TC-PR26-1  _hydrate_candidate_profile 映射 parsed_content + existing_tags（unit）
# ---------------------------------------------------------------------------
async def test_tc_pr26_1_hydrate_candidate_profile_maps_parsed_content_and_tags(db_session: AsyncSession):
    db_session.add(_make_resume("res_x", {"skills": ["Python"]}, ["高潜"], "王伟"))
    await db_session.commit()

    out = await hydrate_tool_input("candidate-profile", {"candidate_id": "res_x"}, db_session)
    assert out["parsed_content"] == {"skills": ["Python"]}
    assert out["existing_tags"] == ["高潜"]


# ---------------------------------------------------------------------------
# TC-PR26-2  candidate_id 缺失 resume -> 抛 ToolParamError（unit）
# ---------------------------------------------------------------------------
async def test_tc_pr26_2_hydrate_candidate_profile_missing_resume_raises(db_session: AsyncSession):
    with pytest.raises(ToolParamError):
        await hydrate_tool_input("candidate-profile", {"candidate_id": "no_such"}, db_session)


# ---------------------------------------------------------------------------
# TC-PR26-3  run_act 端到端（candidate-profile 单步 + resume 预置）
# ---------------------------------------------------------------------------
async def test_tc_pr26_3_run_act_candidate_profile_end_to_end(db_session: AsyncSession):
    db_session.add(_make_resume("res_x", {"skills": ["Python"]}, ["高潜"], "王伟"))
    await db_session.commit()

    collector, _events = _collector_factory()
    router, skill = _make_router()
    steps_results = await run_act(
        _plan_with({"candidate_id": "res_x"}), emit=collector, tool_router=router, db=db_session
    )
    assert steps_results[0].success is True
    assert skill.last_input is not None
    assert skill.last_input["parsed_content"], "skill 收到的 parsed_content 必须非空"
    assert skill.last_input["existing_tags"] == ["高潜"]


# ---------------------------------------------------------------------------
# TC-PR26-4  candidate-merge resumes 列表字段补齐（integration）
# ---------------------------------------------------------------------------
async def test_tc_pr26_4_hydrate_candidate_merge_fills_resume_fields(db_session: AsyncSession):
    db_session.add(_make_resume("a", {"skills": ["Go"]}, ["高潜"], "李娜"))
    db_session.add(_make_resume("b", {"skills": ["Rust"]}, ["技术主管"], "张强"))
    await db_session.commit()

    out = await hydrate_tool_input(
        "candidate-merge", {"resumes": [{"resume_id": "a"}, {"resume_id": "b"}]}, db_session
    )
    assert out["resumes"][0]["parsed_content"], "resumes[0].parsed_content 必须非空"
    assert out["resumes"][1]["parsed_content"], "resumes[1].parsed_content 必须非空"
    assert out["resumes"][0]["candidate_name"] == "李娜"


# ---------------------------------------------------------------------------
# TC-PR26-5  run_act 缺失 resume -> ERROR 事件 + StepResult 失败（integration）
# ---------------------------------------------------------------------------
async def test_tc_pr26_5_run_act_candidate_profile_missing_resume_emits_error_event(db_session: AsyncSession):
    collector, events = _collector_factory()
    router, skill = _make_router()
    steps_results = await run_act(
        _plan_with({"candidate_id": "no_such"}), emit=collector, tool_router=router, db=db_session
    )
    error_events = [e for e in events if e.type == SSEEventType.ERROR]
    assert error_events, "缺失 resume 必须产出 ERROR 事件"
    assert steps_results[0].success is False
    assert "not found" in (steps_results[0].error_message or ""), "error_message 必须含 'not found'"
    assert skill.last_input is None, "ERROR 路径不应调用 skill.execute"
