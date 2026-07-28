"""PR-21 · create_match_score -> match_score 收敛 + F1 修复单测。

追债 12（HANDOFF §9.3.12 / §9.3.13）：create_match_score 既非 BUILTIN_TOOLS 键、亦非任何
skill_id，是硬编码的非法 tool_name。本 PR 收敛为合法 builtin "match_score"，并修复由此引发的
live bug（F1）：run_act 必走 dispatch，create_match_score 解析失败被逐步骤吞异常，导致
skip-to-score 任务"成功"却 0 条 match_score 落库。

- TC-S5.2-1（单元）：BUILTIN_TOOLS 注册 "match_score"；dispatch 能解析（不抛 UnknownToolError）。
- TC-S5.2-2（单元级组合 · 防 F1 回归）：真实 dispatch -> _execute_builtin("match_score")
  -> MatchService.match_one 落库 match_scores 行。不 mock run_act（F1 root cause 即 run_act 被
  mock 屏蔽真实链路）；仅 stub match_one 保留"真实落库"副作用，规避 LLM 链路 hang。
"""

from __future__ import annotations

import pytest


async def test_tc_s5_2_1_match_score_registered_and_dispatch_resolves():
    from app.agent.orchestrator.tool_router import (
        ToolParamError,
        ToolRouter,
        _validate_tool_input,
    )

    router = ToolRouter()
    # 追债 12：tool_name "match_score" 必须作为合法 builtin 被识别
    assert "match_score" in router.list_builtin_tools()
    # input schema 合法（jd_id + resume_id 均 required）
    _validate_tool_input("match_score", {"jd_id": "jd_x", "resume_id": "resume_y"})
    # 缺 db 时抛 ToolParamError（业务必填缺失），而非 UnknownToolError
    # -> 证明已识别为合法 builtin 并走到 _execute_builtin
    with pytest.raises(ToolParamError):
        await router.dispatch("match_score", {"jd_id": "jd_x", "resume_id": "resume_y"})


@pytest.mark.xfail(strict=True, reason="PR-21 未实现：run_act db 透传 + 计划 tool_name 未收敛")
async def test_tc_s5_2_2_skip_to_score_persists_match_score(db_session, monkeypatch):
    from sqlalchemy import select

    from app.agent.orchestrator.act import run_act
    from app.agent.orchestrator.engine import _build_skip_plan
    from app.agent.orchestrator.tool_router import ToolRouter
    from app.models.match_score import MatchScore, generate_match_score_id
    from app.services.match import MatchService

    # 单元级组合：stub match_one 仅保留"真实落库"副作用，避免 LLM 链路 hang
    async def _fake_match_one(self, jd_id, resume_id, *, force=False):
        sm = MatchScore(
            score_id=generate_match_score_id(),
            jd_id=jd_id,
            resume_id=resume_id,
            overall_score=88.0,
            dimension_scores={"skill": 90, "experience": 80, "education": 85},
            status="COMPLETED",
        )
        self.db.add(sm)
        await self.db.commit()
        return sm

    monkeypatch.setattr(MatchService, "match_one", _fake_match_one)

    # 真实 run_act + dispatch（不 mock run_act，F1 root cause 即 run_act 被 mock 屏蔽）
    plan = _build_skip_plan("jd_tc", ["resume_tc"])
    results = await run_act(
        plan,
        ctx={"task_id": "tc_task"},
        tool_router=ToolRouter(),
        db=db_session,
    )
    assert results[0].success
    assert results[0].tool_name == "match_score"
    # match_scores 表出现新行（F1 回归防护：dispatch 真实落库）
    res = await db_session.execute(
        select(MatchScore).where(
            MatchScore.jd_id == "jd_tc", MatchScore.resume_id == "resume_tc"
        )
    )
    assert res.scalars().first() is not None
