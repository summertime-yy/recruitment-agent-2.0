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

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator.engine import (
    DbUpdater,
    OrchestratorEngine,
    _build_skip_plan,
    _make_db_execution_writer,
)
from app.agent.orchestrator.event_buffer import EventBuffer
from app.core.config import get_settings
from app.core.database import async_session_factory, get_db
from app.core.redis import get_redis
from app.core.time import utcnow_aware
from app.models.execution import Execution
from app.models.task import Task, generate_task_id
from app.schemas.agent import (
    AgentChatRequest,
    CancelTaskResponse,
    ExecutePlanRequest,
    Plan,
    PlanStep,
    SkipToScoreRequest,
    SSEEvent,
    SSEEventType,
    TaskStatus,
)

router = APIRouter(prefix="/agent", tags=["Agent / Orchestrator"])


# ---- Bug A 适配：存储 plan dict -> REST Plan（方案 C，REST 层最小 blast radius）----
def _stored_plan_to_rest_plan(task_id: str, stored: dict | None):
    """把 orchestrator / ``_build_skip_plan`` 产出的存储 plan dict 适配为 REST ``Plan``。

    存储 plan 形状（orchestrator reason_plan / ``_build_skip_plan``）：
        ``{steps:[{step_id, tool_name, tool_input, description?}], reasoning?}``

    REST ``Plan`` / ``PlanStep`` 形状（见 ``app.schemas.agent``）：
        ``Plan(task_id 必填, steps[PlanStep])``
        ``PlanStep(step_id, tool_name, description 必填, expected_output 必填, params=dict)``

    方案 C 约束：**不改 orchestrator 存储、不改 REST schema**，仅在 REST 层适配：
    - ``task_id``：取自入参（存储 plan 不携带该字段）
    - 每步 ``tool_input`` → ``params``；``expected_output`` / ``description`` 缺省 ``""``
    - ``stored`` 为 ``None``（任务尚无 plan）→ 返回 ``None``（``TaskStatus.plan`` 可选）

    这是 PR-25 修复 ``GET /agent/tasks/{id}`` 对存 plan 任务必 500 的根因。
    """
    if stored is None:
        return None
    steps = [
        PlanStep(
            step_id=s.get("step_id", ""),
            tool_name=s.get("tool_name", ""),
            params=s.get("tool_input") or {},
            expected_output=s.get("expected_output", ""),
            description=s.get("description", ""),
        )
        for s in stored.get("steps", [])
    ]
    return Plan(
        task_id=task_id,
        steps=steps,
        reasoning=stored.get("reasoning"),
    )


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
    # 新建任务尚无 plan（reason 后台异步生成）→ adapter 对 None 返回 None
    return {
        "task_id": resp["task_id"],
        "status": resp["status"],
        "plan": _stored_plan_to_rest_plan(task_id, None),
    }


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
    # PR-20 S5.1: 构造 execution writer（后台任务用 async_session_factory 管理 session 生命周期）
    exec_writer = _make_db_execution_writer(async_session_factory, task_id=req.task_id)
    # PR-28 commit 2: PR-21 S3.5 透传 session_factory -> _background_execute(run_act)
    # -> dispatch(db=...) -> hydrate_tool_input 拿真 db，resume_parsing 才能拉
    # candidate_tags / parsed_jd 等真值。
    resp = await engine.run_execute(
        req.task_id,
        plan=task_plan,
        accepted_steps=req.accepted_steps,
        modifications=req.modifications,
        db_updater=db_updater,
        execution_writer=exec_writer,
        session_factory=async_session_factory,
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
    # PR-21：plan 单点构造（engine._build_skip_plan），tool_name 收敛为合法 builtin "match_score"
    plan = _build_skip_plan(req.jd_id, req.candidate_ids)
    db.add(
        Task(
            task_id=task_id,
            status="EXECUTING",
            task_type="MATCH_SCORE",
            user_message=f"skip-to-score jd={req.jd_id}",
            context={"jd_id": req.jd_id, "candidate_ids": req.candidate_ids},
            plan=plan,
            started_at=utcnow_aware(),
        )
    )
    await db.commit()
    db_updater = await _make_db_updater()
    # PR-20 S5.1: 构造 execution writer（后台任务用 async_session_factory 管理 session 生命周期）
    exec_writer = _make_db_execution_writer(async_session_factory, task_id=task_id)
    resp = await engine.run_skip_to_score(
        req.jd_id,
        req.candidate_ids,
        task_id=task_id,
        db_updater=db_updater,
        execution_writer=exec_writer,
        session_factory=async_session_factory,
    )
    if resp.get("status_code") == 429:
        _raise_429()
    return {
        "task_id": task_id,
        "status": "EXECUTING",
        "plan": _stored_plan_to_rest_plan(task_id, plan),
    }


# ---- SSE 流（Q2/Q3/Q4/Q8）----
def _format_sse(ev_type: SSEEventType, data: Any, ev_id: str | None = None) -> str:
    """把单个事件格式化为 SSE 帧：id / event / data + 尾部空行（§3.2）。"""
    lines = []
    if ev_id is not None:
        lines.append(f"id: {ev_id}")
    lines.append(f"event: {ev_type.value}")
    data_str = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    lines.append(f"data: {data_str}")
    return "\n".join(lines) + "\n\n"


def _is_terminal(ev: SSEEvent) -> bool:
    """终态关流条件（Q3）：result / error 事件，或 system:cancelled。"""
    if ev.type in (SSEEventType.RESULT, SSEEventType.ERROR):
        return True
    if ev.type == SSEEventType.SYSTEM and isinstance(ev.data, dict) and ev.data.get("message") == "cancelled":
        return True
    return False


async def _event_stream(
    task_id: str,
    last_event_id: int,
    buffer: EventBuffer,
    heartbeat_sec: float,
    request: Request,
):
    """SSE 主循环：先回放已有事件，再 100ms 轮询新事件 + wall-clock 心跳，终态关流（Q2/Q4）。

    每轮检查客户端断线（§十三#4）：断连立即退出，避免生成器僵尸。
    """
    yield "retry: 3000\n\n"
    last_seq = last_event_id
    last_heartbeat = time.monotonic()
    # 首帧回放（含 Last-Event-ID 重放）
    events = await buffer.read_after(task_id, last_seq)
    for ev in events:
        yield _format_sse(ev.type, ev.data, ev.id)
        last_seq = int(ev.id)
        if _is_terminal(ev):
            return
    while True:
        if await request.is_disconnected():
            return
        events = await buffer.read_after(task_id, last_seq)
        for ev in events:
            yield _format_sse(ev.type, ev.data, ev.id)
            last_seq = int(ev.id)
            if _is_terminal(ev):
                return
        now = time.monotonic()
        if now - last_heartbeat >= heartbeat_sec:
            # 心跳不入 EventBuffer（PLAN §Q5）：瞬时下发，无 id 行
            yield _format_sse(SSEEventType.SYSTEM, {"message": "heartbeat"})
            last_heartbeat = now
        await asyncio.sleep(0.1)


async def _synthesize_from_task(task: Task):
    """Q8-3b：终态且缓冲已过期（空）→ 从 tasks.result/error 合成事件帧。"""
    yield "retry: 3000\n\n"
    if task.status == "COMPLETED" and task.result:
        yield _format_sse(SSEEventType.RESULT, task.result, "1")
    elif task.status == "FAILED" and task.error:
        yield _format_sse(SSEEventType.ERROR, task.error, "1")
    elif task.status == "CANCELLED":
        yield _format_sse(SSEEventType.SYSTEM, {"message": "cancelled"}, "1")


@router.get("/tasks/{task_id}/stream")
async def stream_task(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    engine: OrchestratorEngine = Depends(get_engine),
    settings: Any = Depends(get_settings),
):
    """SSE 事件流（Q2 100ms 轮询 / Q3 关流 / Q4 心跳 / Q8 合成）。

    路由声明先于 ``/tasks/{task_id}``（PLAN §Q11），确保 /stream 子路径不被 {task_id} 吞掉。
    """
    # 场景 1：不存在 → 404
    result = await db.execute(select(Task).where(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "TASK_NOT_FOUND", "message": f"task_id={task_id} not found"},
        )
    buffer = engine.event_buffer
    last_event_id = int(request.headers.get("Last-Event-ID", 0) or 0)
    # 场景 3：终态 + 缓冲空 → 从 DB 合成事件
    buffered = await buffer.read_after(task_id, last_event_id) if buffer is not None else []
    if not buffered and task.status in {"COMPLETED", "FAILED", "CANCELLED"}:
        return StreamingResponse(_synthesize_from_task(task), media_type="text/event-stream")
    # 场景 2：正常 stream（buffer 必存在；否则退化为心跳循环）
    if buffer is None:
        buffer = EventBuffer(get_redis(request))
    return StreamingResponse(
        _event_stream(task_id, last_event_id, buffer, settings.sse_heartbeat_interval_sec, request),
        media_type="text/event-stream",
    )


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
        plan=_stored_plan_to_rest_plan(task.task_id, task.plan),
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
    task.finished_at = utcnow_aware()
    # PR-20 S5.1 D2: cancel 时将当前步骤的 PENDING execution 标为 CANCELLED
    if task.current_step is not None:
        await db.execute(
            update(Execution)
            .where(
                Execution.task_id == task_id,
                Execution.step_id == task.current_step,
                Execution.execution_status == "PENDING",
            )
            .values(execution_status="CANCELLED", finished_at=utcnow_aware()),
        )
    await db.commit()
    # 事务提交后补发 SSE（Q3）
    if engine.event_buffer is not None:
        await engine.event_buffer.append(task_id, SSEEventType.SYSTEM, {"message": "cancelled"})
        await engine.event_buffer.set_terminal_ttl(task_id)
    return CancelTaskResponse(task_id=task_id, status="CANCELLED")
