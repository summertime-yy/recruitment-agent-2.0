"""S5-09 · Agent REST 端点 + SSE HTTP 流（PR-14）。

本文件承载 DECISION §十四 阶段 3/4 的端点实现：
- POST /agent/chat                      → 异步 R-P-R，立即返 {task_id, PLANNING}（Q5 (b1)）
- POST /agent/execute-plan              → 确认执行 plan（Q6 SELECT FOR UPDATE）
- POST /agent/skip-to-score             → 跳过 R-P-R 直接评分（Q7 真 task_id）
- GET  /agent/tasks/{task_id}           → 查询任务状态
- POST /agent/tasks/{task_id}/cancel    → 取消（Q3 补发 SYSTEM("cancelled")）
- GET  /agent/tasks/{task_id}/stream    → SSE 事件流（Q2/Q3/Q4/Q8，阶段 4 实现）

阶段 3（本 commit）：chat / execute-plan / skip-to-score / tasks / cancel 五个端点 + 路由注册。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator.engine import DbUpdater, OrchestratorEngine
from app.agent.orchestrator.event_buffer import EventBuffer
from app.core.database import async_session_factory, get_db
from app.core.redis import get_redis
from app.core.time import utcnow_naive
from app.models.task import Task, generate_task_id
from app.schemas.agent import (
    AgentChatRequest,
    CancelTaskResponse,
    ExecutePlanRequest,
    SkipToScoreRequest,
    SSEEventType,
    TaskStatus,
)

router = APIRouter(prefix="/agent", tags=["Agent / Orchestrator"])


# ---- 依赖：构造 OrchestratorEngine（共享请求级 Redis / EventBuffer）----
def get_engine(redis: Any = Depends(get_redis)) -> OrchestratorEngine:
    """每个请求构造一个 Engine（构造开销极小）：用请求 Redis 建 EventBuffer。

    通过 ``Depends(get_redis)`` 注入，便于测试用 ``dependency_overrides[get_redis]`` 替换。
    """
    buffer = EventBuffer(redis)
    return OrchestratorEngine(event_buffer=buffer)


# ---- DB updater 闭包（Q1 方案 B）----
async def _make_db_updater(session_factory=async_session_factory) -> DbUpdater:
    """返回一个把 (task_id, patch) 写进 tasks 表的回调（每次现建 session，避免跨请求复用）。"""

    async def _update(task_id: str, patch: dict[str, Any]) -> None:
        async with session_factory() as s:
            await s.execute(update(Task).where(Task.task_id == task_id).values(**patch))
            await s.commit()

    return _update


def _raise_429():
    raise HTTPException(
        status_code=429,
        detail={"code": "TASK_LIMIT_EXCEEDED", "message": "too many active tasks"},
    )


# ---- 端点 ----
@router.post("/chat")
async def chat(
    req: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    engine: OrchestratorEngine = Depends(get_engine),
):
    """发起 R-P-R：端点侧 INSERT tasks(PLANNING) + fire-and-forget 后台 reason_plan。"""
    task_id = generate_task_id()
    db.add(
        Task(
            task_id=task_id,
            status="PLANNING",
            user_message=req.message,
            context=req.context or {},
        )
    )
    await db.commit()
    db_updater = await _make_db_updater()
    resp = await engine.start_chat(task_id, req.message, req.context, db_updater)
    if resp.get("status_code") == 429:
        _raise_429()
    return {"task_id": resp["task_id"], "status": resp["status"]}


@router.post("/execute-plan")
async def execute_plan(
    req: ExecutePlanRequest,
    db: AsyncSession = Depends(get_db),
    engine: OrchestratorEngine = Depends(get_engine),
):
    """确认执行 plan：SELECT FOR UPDATE 校验状态 → 后台 run_execute。"""
    result = await db.execute(select(Task).where(Task.task_id == req.task_id).with_for_update())
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "TASK_NOT_FOUND", "message": f"task_id={req.task_id} not found"},
        )
    if task.status != "WAITING_CONFIRMATION":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ILLEGAL_STATE_TRANSITION",
                "message": f"cannot execute task in state {task.status}",
            },
        )
    # 在事务内捕获 plan，避免会话关闭后惰性加载
    task_plan = task.plan
    db_updater = await _make_db_updater()
    resp = await engine.run_execute(
        req.task_id,
        plan=task_plan,
        accepted_steps=req.accepted_steps,
        modifications=req.modifications,
        db_updater=db_updater,
    )
    if resp.get("status_code") == 429:
        _raise_429()
    return {"task_id": req.task_id, "status": resp["status"]}


@router.post("/skip-to-score")
async def skip_to_score(
    req: SkipToScoreRequest,
    db: AsyncSession = Depends(get_db),
    engine: OrchestratorEngine = Depends(get_engine),
):
    """跳过 R-P-R 直接评分：INSERT tasks(EXECUTING) + 后台 run_skip_to_score（真 task_id）。"""
    task_id = generate_task_id()
    plan = {
        "steps": [
            {
                "step_id": f"step_score_{i}",
                "tool_name": "create_match_score",
                "tool_input": {"jd_id": req.jd_id, "resume_id": cid},
            }
            for i, cid in enumerate(req.candidate_ids)
        ]
    }
    db.add(
        Task(
            task_id=task_id,
            status="EXECUTING",
            task_type="MATCH_SCORE",
            user_message=f"skip-to-score jd={req.jd_id}",
            context={"jd_id": req.jd_id, "candidate_ids": req.candidate_ids},
            plan=plan,
            started_at=utcnow_naive(),
        )
    )
    await db.commit()
    db_updater = await _make_db_updater()
    resp = await engine.run_skip_to_score(
        req.jd_id,
        req.candidate_ids,
        task_id=task_id,
        db_updater=db_updater,
    )
    if resp.get("status_code") == 429:
        _raise_429()
    return {"task_id": task_id, "status": "EXECUTING"}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)) -> TaskStatus:
    """查询任务状态。"""
    result = await db.execute(select(Task).where(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "TASK_NOT_FOUND", "message": f"task_id={task_id} not found"},
        )
    return TaskStatus(
        task_id=task.task_id,
        status=task.status,
        current_step=task.current_step,
        plan=task.plan,
        result=task.result,
        error=task.error,
        created_at=task.created_at.isoformat() if task.created_at else "",
        updated_at=task.updated_at.isoformat() if task.updated_at else "",
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    engine: OrchestratorEngine = Depends(get_engine),
) -> CancelTaskResponse:
    """取消任务：SELECT FOR UPDATE 校验 → UPDATE CANCELLED → 补发 SYSTEM("cancelled") + 设 TTL。"""
    result = await db.execute(select(Task).where(Task.task_id == task_id).with_for_update())
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "TASK_NOT_FOUND", "message": f"task_id={task_id} not found"},
        )
    if task.status not in {"PLANNING", "WAITING_CONFIRMATION"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ILLEGAL_STATE_TRANSITION",
                "message": f"cannot cancel task in state {task.status}",
            },
        )
    task.status = "CANCELLED"
    task.finished_at = utcnow_naive()
    await db.commit()
    # 事务提交后补发 SSE（Q3）
    if engine.event_buffer is not None:
        await engine.event_buffer.append(task_id, SSEEventType.SYSTEM, {"message": "cancelled"})
        await engine.event_buffer.set_terminal_ttl(task_id)
    return CancelTaskResponse(task_id=task_id, status="CANCELLED")
