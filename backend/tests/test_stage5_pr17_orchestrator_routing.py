"""PR-17 · Orchestrator 端到端路由修复集成测试（hermetic，mock LLM）。

归属 PR：PR-17（追债项 10 Y 方向 + 追债项 11 同 PR 收敛）
覆盖用例（TC-PR17-1..4）：
- TC-PR17-1  candidate-profile 端到端（正向）
- TC-PR17-2  candidate-merge 端到端（正向）
- TC-PR17-3  jd-candidate-matching 端到端（正向）
- TC-PR17-4  plan 输出非法 tool_name → reflect_plan 挡下（反向 · Q7 校验）

路径：run_reason → run_plan → run_reflect_plan 单元级组合 + mock LLM，**不走 start_chat**
（避免 redis/db/SSE fixture，保 hermetic，不与 PR-14 端点测试互扰）。

dispatchable_tools 注入验证：捕获 plan 的 user_prompt，断言含全部 dispatchable 工具名
（candidate-profile / candidate-merge / jd-candidate-matching / search_resumes / read_jd）。
该断言是 PR-17 核心增量：commit 3b（engine.run_plan 注入）落地前会失败 → 本阶段 xfail 命中。

约定：本文件全部用例不依赖真实 DB / LLM（call_llm_json 通过 monkeypatch 隔离）。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent.orchestrator.engine import OrchestratorEngine


def _make_fake_llm(captured: dict[str, str], plan_tool: str, reason_task_type: str):
    """构造 mock call_llm_json：按 system_prompt 关键字分派 reason / plan / reflect_plan。

    - captured["plan_user_prompt"] 仅在 plan 调用时记录（plan 的 USER_TEMPLATE 含 dispatchable_tools）；
      不覆盖 reason/reflect_plan 的 user_prompt，避免断言串味。
    """

    async def _fake_llm_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if "计划生成" in system_prompt:
            captured["plan_user_prompt"] = user_prompt
            return {
                "steps": [
                    {
                        "step_id": "step_1",
                        "tool_name": plan_tool,
                        "tool_input": {"candidate_id": "c_1"},
                        "description": f"执行 {plan_tool}",
                    }
                ],
                "summary": "single step plan",
            }
        if "意图推理" in system_prompt:
            return {
                "task_type": reason_task_type,
                "intent_summary": f"处理 {reason_task_type}",
                "parsed_entities": {"candidate_id": "c_1"},
                "missing_entities": [],
                "confidence": 0.9,
            }
        if "计划反思" in system_prompt:
            return {"is_plan_sound": True, "issues": []}
        return {}

    return _fake_llm_json


def _assert_dispatchable_injected(plan_user_prompt: str) -> None:
    """PR-17 核心增量：plan 的 user_prompt 必须含全部 dispatchable 工具清单。"""
    for tool in ("candidate-profile", "candidate-merge", "jd-candidate-matching", "search_resumes", "read_jd"):
        assert tool in plan_user_prompt, f"dispatchable_tools 未注入 plan prompt: 缺 {tool}"


# ---------------------------------------------------------------------------
# TC-PR17-1 · candidate-profile 端到端（正向）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="PR-17 not yet implemented: dispatchable_tools not injected into run_plan", strict=False)
async def test_tc_pr17_1_candidate_profile_e2e(monkeypatch):
    """自然语言 → reason(profile_candidate) → plan(candidate-profile) → reflect_plan 通过。"""
    captured: dict[str, str] = {}
    fake = _make_fake_llm(captured, plan_tool="candidate-profile", reason_task_type="profile_candidate")
    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", fake)

    engine = OrchestratorEngine()
    reason_out = await engine.run_reason({"user_input": "请给候选人 c_1 生成画像", "context": {}})
    assert reason_out.get("task_type") == "profile_candidate"

    plan_out = await engine.run_plan({"reason_output": reason_out})
    assert plan_out["steps"][0]["tool_name"] == "candidate-profile"

    reflect_out = await engine.run_reflect_plan({"plan": plan_out})
    assert reflect_out["is_plan_sound"] is True

    # PR-17 核心增量：dispatchable_tools 已注入 plan 的 user_prompt
    _assert_dispatchable_injected(captured["plan_user_prompt"])


# ---------------------------------------------------------------------------
# TC-PR17-2 · candidate-merge 端到端（正向）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="PR-17 not yet implemented: dispatchable_tools not injected into run_plan", strict=False)
async def test_tc_pr17_2_candidate_merge_e2e(monkeypatch):
    """PR-15 交付的孤立 skill candidate-merge 现可通过自然语言路由。"""
    captured: dict[str, str] = {}
    fake = _make_fake_llm(captured, plan_tool="candidate-merge", reason_task_type="merge_candidates")
    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", fake)

    engine = OrchestratorEngine()
    reason_out = await engine.run_reason({"user_input": "把这几份简历合并评估", "context": {}})
    assert reason_out.get("task_type") == "merge_candidates"

    plan_out = await engine.run_plan({"reason_output": reason_out})
    assert plan_out["steps"][0]["tool_name"] == "candidate-merge"

    reflect_out = await engine.run_reflect_plan({"plan": plan_out})
    assert reflect_out["is_plan_sound"] is True

    _assert_dispatchable_injected(captured["plan_user_prompt"])


# ---------------------------------------------------------------------------
# TC-PR17-3 · jd-candidate-matching 端到端（正向）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="PR-17 not yet implemented: dispatchable_tools not injected into run_plan", strict=False)
async def test_tc_pr17_3_jd_candidate_matching_e2e(monkeypatch):
    """Stage 4 遗留 skill jd-candidate-matching 也接入自然语言路由。"""
    captured: dict[str, str] = {}
    fake = _make_fake_llm(captured, plan_tool="jd-candidate-matching", reason_task_type="match")
    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", fake)

    engine = OrchestratorEngine()
    reason_out = await engine.run_reason({"user_input": "帮 jd_1 找候选人", "context": {}})
    assert reason_out.get("task_type") == "match"

    plan_out = await engine.run_plan({"reason_output": reason_out})
    assert plan_out["steps"][0]["tool_name"] == "jd-candidate-matching"

    reflect_out = await engine.run_reflect_plan({"plan": plan_out})
    assert reflect_out["is_plan_sound"] is True

    _assert_dispatchable_injected(captured["plan_user_prompt"])


# ---------------------------------------------------------------------------
# TC-PR17-4 · plan 输出非法 tool_name → reflect_plan 挡下（反向 · Q7 校验）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="PR-17 verifying reflect_plan existing guard; will pass (XPASS) pre-impl, green on commit 4", strict=False)
async def test_tc_pr17_4_invalid_tool_blocked_by_reflect_plan(monkeypatch):
    """plan LLM 输出未注册 tool_name → run_reflect_plan 返 is_plan_sound=False + issues。"""
    async def _fake_llm_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if "意图推理" in system_prompt:
            return {
                "task_type": "match",
                "intent_summary": "匹配",
                "parsed_entities": {},
                "missing_entities": [],
                "confidence": 0.9,
            }
        if "计划生成" in system_prompt:
            return {
                "steps": [{"step_id": "step_1", "tool_name": "nonexistent-skill", "tool_input": {}, "description": "x"}],
                "summary": "x",
            }
        if "计划反思" in system_prompt:
            return {"is_plan_sound": True, "issues": []}
        return {}

    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake_llm_json)

    engine = OrchestratorEngine()
    reason_out = await engine.run_reason({"user_input": "帮我匹配", "context": {}})
    plan_out = await engine.run_plan({"reason_output": reason_out})
    reflect_out = await engine.run_reflect_plan({"plan": plan_out})

    assert reflect_out["is_plan_sound"] is False
    assert any("unknown tool: nonexistent-skill" in str(i) for i in reflect_out["issues"])
