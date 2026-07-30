"""PR-25 · TC-PR25-1..3 · 修复 GET /agent/tasks/{id} 对存 plan 的任务必 500（方案 C adapter）。

背景（HANDOFF §9.3.17 / PR25-KICKOFF-DECISION §一）：
orchestrator / ``_build_skip_plan`` 产出的存储 plan 字典形状为
``{steps:[{step_id, tool_name, tool_input, description?}], reasoning}``，
而 REST 响应 schema ``Plan`` / ``PlanStep`` 要求 ``task_id``（必填）、
``params``（非 ``tool_input``）、``expected_output``（必填）、``description``（必填）。
旧代码 ``get_task`` 直接 ``TaskStatus(plan=task.plan)``，pydantic 校验失败 → 500。

方案 C（最小 blast radius）：**不改 orchestrator 存储、不改 REST schema**，
仅在 REST 层加转换函数 ``_stored_plan_to_rest_plan``，把存储 plan 适配为 ``Plan``，
3 处消费点（chat_start / skip_to_score / get_task）全部经它（PR25-KICKOFF-DECISION §三.2）。

测试约定（对齐 tests/api/test_agent_endpoints.py）：
- ASGITransport 不触发 lifespan → get_redis 需自行 override（fake_redis，仅 chat/skip 端点需要）。
- client_db + db_session：real Postgres 事务回滚，隔离且无污染。

TC-PR25-1：单测 adapter —— tool_input 被映射为 params，并补全 task_id / expected_output / description；None → None。
TC-PR25-2：集成 —— 直接插入 stored-plan（tool_input）形状的 Task，GET /agent/tasks/{id}
            → 200，JSON.plan.task_id 非空，JSON.plan.steps[0].params 有值（取自 tool_input）。
TC-PR25-3：集成 —— 插入 plan=None 的 Task，GET /agent/tasks/{id} → 200，JSON.plan 为 null
            （adapter 对 None 返回 None，无 plan 任务也不 500）。

（TC 设计严格对齐 PR25-KICKOFF-DECISION §三.3。）
"""

from __future__ import annotations

from app.api.v1.agent import _stored_plan_to_rest_plan
from app.core.config import get_settings
from app.models.task import Task

PREFIX = get_settings().API_V1_PREFIX


# ---- TC-PR25-1 · adapter 单测（工具输入→params + 缺省补全 + None 路径）----
async def test_pr25_1_adapter_tool_input_to_params():
    """TC-PR25-1（对齐 §三.3）：skip-shape 存储 plan 用 tool_input（缺 params/expected_output/description/task_id），
    经 adapter 转 REST Plan：task_id 补全、tool_input 映射为 params、缺省字段补齐；stored=None → None。"""
    stored = {
        "steps": [
            {
                "step_id": "s1",
                "tool_name": "match_score",
                "tool_input": {"jd_id": "j1", "resume_id": "r1"},
            }
        ],
        "reasoning": "r",
    }
    plan = _stored_plan_to_rest_plan("task_abc", stored)
    assert plan is not None
    assert plan.task_id == "task_abc"
    assert plan.steps[0].step_id == "s1"
    assert plan.steps[0].tool_name == "match_score"
    # 关键：tool_input 被映射为 params（REST schema 字段名）
    assert plan.steps[0].params == {"jd_id": "j1", "resume_id": "r1"}
    # skip plan 缺 expected_output / description → 缺省 ""（不抛 ValidationError）
    assert plan.steps[0].expected_output == ""
    assert plan.steps[0].description == ""
    # stored=None → None（无 plan 的任务不崩）
    assert _stored_plan_to_rest_plan("task_none", None) is None


# ---- TC-PR25-2 · get_task 集成（stored plan 含 tool_input 形状）----
async def test_pr25_2_get_task_returns_200_with_stored_plan(client_db, db_session):
    """TC-PR25-2（对齐 §三.3）：GET /agent/tasks/{id} 对 stored-plan（tool_input）返回 200 且 plan 适配。"""
    task_id = "task_pr25_stored"
    db_session.add(
        Task(
            task_id=task_id,
            status="WAITING_CONFIRMATION",
            user_message="x",
            plan={
                "steps": [
                    {
                        "step_id": "s1",
                        "tool_name": "match_score",
                        "tool_input": {"jd_id": "j1", "resume_id": "r1"},
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
    assert body["plan"]["steps"][0]["params"] == {"jd_id": "j1", "resume_id": "r1"}


# ---- TC-PR25-3 · get_task 无 plan 任务（plan=None）也不 500（adapter None 路径）----
async def test_pr25_3_get_task_with_no_plan_returns_200(client_db, db_session):
    """TC-PR25-3（对齐 §三.3）：plan=None 的任务 GET 仍 200 且 JSON.plan 为 null。

    这是 Bug A 的互补边界——无 plan 任务（如刚 chat 新建、尚未 reason 完成）也
    不能因 ``TaskStatus(plan=...)`` 校验崩 500。adapter 对 None 返回 None，
    ``TaskStatus.plan`` 为 Optional，故 200。
    """
    task_id = "task_pr25_no_plan"
    db_session.add(
        Task(
            task_id=task_id,
            status="PLANNING",
            user_message="x",
            plan=None,
        )
    )
    await db_session.commit()
    r = await client_db.get(f"{PREFIX}/agent/tasks/{task_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"] is None
