"""PR-25 · TC-PR25-1..3 · 修复 GET /agent/tasks/{id} 对存 plan 的任务必 500（方案 C adapter）。

背景（HANDOFF §9.3.17 / PR25-KICKOFF-DECISION）：
orchestrator / _build_skip_plan 产出的存储 plan 字典形状为
``{steps:[{step_id, tool_name, tool_input, description?}], reasoning}``，
而 REST 响应 schema ``Plan`` / ``PlanStep`` 要求 ``task_id``（必填）、
``params``（非 ``tool_input``）、``expected_output``（必填）、``description``（必填）。
旧代码 ``get_task`` 直接 ``TaskStatus(plan=task.plan)``，pydantic 校验失败 → 500。

方案 C（最小 blast radius）：**不改 orchestrator 存储、不改 REST schema**，
仅在 REST 层加转换函数 ``_stored_plan_to_rest_plan``，把存储 plan 适配为 ``Plan``，
3 处消费点（chat_start / skip_to_score / get_task）全部经它。

测试约定（对齐 tests/api/test_agent_endpoints.py）：
- ASGITransport 不触发 lifespan → get_redis 需自行 override（fake_redis）。
- client_db + db_session：real Postgres 事务回滚，隔离且无污染。

TC-PR25-1：单测 adapter —— tool_input 被映射为 params，并补全 task_id / expected_output / description。
TC-PR25-2：集成 —— 直接插入 chat-plan 形状（tool_input）的 Task，GET /agent/tasks/{id}
            → 200，JSON.plan.task_id 非空，JSON.plan.steps[0].params 有值。
TC-PR25-3：集成 —— POST /agent/skip-to-score（engine 打桩避免后台真评分），
            响应经 adapter 包含适配后的 plan，steps[0].params 来自 tool_input。
"""

from __future__ import annotations

from app.api.v1.agent import _stored_plan_to_rest_plan, get_engine
from app.core.config import get_settings
from app.models.task import Task

PREFIX = get_settings().API_V1_PREFIX


# ---- TC-PR25-1 · adapter 单测（工具输入→params + 缺省补全）----
async def test_pr25_1_adapter_tool_input_to_params():
    """TC-PR25-1：存储 plan 用 tool_input（缺 params/expected_output/task_id），
    经 adapter 转 REST Plan：task_id 补全、tool_input 映射为 params、缺省字段补齐。"""
    stored = {
        "steps": [
            {
                "step_id": "step_1",
                "tool_name": "candidate-profile",
                "tool_input": {"candidate_ids": ["res_x"]},
                "description": "生成候选人画像",
            }
        ],
        "reasoning": "r",
    }
    plan = _stored_plan_to_rest_plan("task_abc", stored)
    assert plan is not None
    assert plan.task_id == "task_abc"
    assert plan.steps[0].step_id == "step_1"
    assert plan.steps[0].tool_name == "candidate-profile"
    # 关键：tool_input 被映射为 params（REST schema 字段名）
    assert plan.steps[0].params == {"candidate_ids": ["res_x"]}
    # 缺省字段被补全（不抛 ValidationError）
    assert plan.steps[0].expected_output == ""
    assert plan.steps[0].description == "生成候选人画像"
    # stored=None → None（无 plan 的任务不崩）
    assert _stored_plan_to_rest_plan("task_none", None) is None


# ---- TC-PR25-2 · get_task 集成（chat-plan 形状）----
async def test_pr25_2_get_task_with_chat_plan(client_db, db_session):
    """TC-PR25-2：GET /agent/tasks/{id} 对 chat-plan（tool_input）返回 200 且 plan 适配。"""
    task_id = "task_pr25_chat"
    db_session.add(
        Task(
            task_id=task_id,
            status="WAITING_CONFIRMATION",
            user_message="x",
            plan={
                "steps": [
                    {
                        "step_id": "step_1",
                        "tool_name": "candidate-profile",
                        "tool_input": {"candidate_ids": ["res_x"]},
                        "description": "生成候选人画像",
                    }
                ],
                "reasoning": "r",
            },
        )
    )
    await db_session.commit()
    r = await client_db.get(f"{PREFIX}/agent/tasks/{task_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"]["task_id"] == task_id
    assert body["plan"]["steps"][0]["params"] == {"candidate_ids": ["res_x"]}


# ---- TC-PR25-3 · skip_to_score 集成（响应经 adapter 含适配 plan）----
async def test_pr25_3_skip_to_score_returns_adapted_plan(client_db, db_session, fake_redis):
    """TC-PR25-3：skip_to_score 响应经 adapter 包含适配后的 plan（steps[0].params 来自 tool_input）。

    engine 打桩为 no-op，避免后台真评分（real LLM / match service）在单测里跑。
    """
    from app.core.redis import get_redis

    class _FakeEngine:
        async def run_skip_to_score(self, *args, **kwargs):
            return {"status": "EXECUTING"}

    app_overrides = {
        get_engine: lambda: _FakeEngine(),
        get_redis: lambda: fake_redis,
    }
    # 局部覆盖（不污染全局 conftest fixture 的清理）
    import app.api.v1.agent as agent_mod
    import app.main as main_mod

    saved = dict(main_mod.app.dependency_overrides)
    main_mod.app.dependency_overrides.update(app_overrides)
    try:
        r = await client_db.post(
            f"{PREFIX}/agent/skip-to-score",
            json={"jd_id": "jd_1", "candidate_ids": ["res_a", "res_b"]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # skip plan 无 task_id / expected_output / description，经 adapter 补全
        assert body["plan"]["task_id"]  # 非空（取自 task_id）
        assert body["plan"]["steps"][0]["params"] == {"jd_id": "jd_1", "resume_id": "res_a"}
    finally:
        main_mod.app.dependency_overrides.clear()
        main_mod.app.dependency_overrides.update(saved)
