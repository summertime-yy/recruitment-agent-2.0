# PR-14 · Agent REST 端点 + SSE HTTP 流 · 启动裁定

> 关联：`docs/planning/stage5/PR14-KICKOFF-QUESTIONS.md` · 建议分支 `feat/pr-14-s5-09-agent-endpoints`
> 权威依据：`docs/planning/PLAN-STAGE5.md §Q5/Q6/Q7/Q11` · `docs/planning/TASKS-STAGE5.md §S5-09` · `docs/planning/TEST-PLAN-STAGE5.md §S5-09（TC-S5-09-1..6）` · `docs/api-contract.md §3.1/§3.2/§3.5/§4.1-4.5` · PR-13 STEP6 §五 决策记录
> 生成时间：2026-07-21
> 状态：**9 问 + 追加 2 项主裁定 + 5 处修正裁定，全部落定**，执行体可立即按 §十四 开工

---

## 一、前置状态确认（与 QUESTIONS §前置事实同步，2026-07-21 · master `aa57270`）

| 项 | 状态 |
|---|---|
| master HEAD（本地 + 远端） | `aa57270`（PR-13 已 FF 合入 + docs 追加） |
| 本地 pytest 基线 | **101 passed** |
| 依赖状态 | `fastapi` / `redis>=5.0.0` / `fakeredis>=2.20.0` 已在；**不新增** `sse-starlette` |
| Engine 关键缺口 | `_background_execute` 不写 `tasks` 表；`run_chat` `emit=None` 未使用；`run_skip_to_score` 假前缀 `task_id`；`api/v1/__init__` 未注册 agent 路由 |
| `executions` 表 | `models/execution.py` 已存在；**本 PR 不写**（见 §十一） |

---

## 二、主裁定 A（讨论轮追加）· Q5 隐藏前提：`chat` 端点异步化

### 裁定：**(b1) 异步 + 非流式 thinking**

**理由**：同步 `run_chat` 与 §3.3 "thinking/plan 实时 SSE 事件"、§4.1 `AgentChatResponse.status='PLANNING'` 契约不可兼容。同步模型下客户端在 chat 返回前拿不到 task_id → 无法预开 /stream → "实时渲染"名不副实。(b1) 一次性还清 §3.3/§4.1 契约债，避免 PR-17 前端"哑巴 chat"。真·token 流延到后续 PR（不在 Stage 5 范围）。

### 落地契约（覆盖 QUESTIONS §Q5 方案 A）

**HTTP 契约**（覆盖 §Q5-A 中 "chat 阻塞返 plan" 的描述）：

- `POST /agent/chat` **立即（<200ms）**返回：
  ```json
  {"task_id": "task_<uuid12>", "status": "PLANNING"}
  ```
  `initial_plan` 字段不再返（api-contract §4.1 已定义为可选，PR-17 前端通过 SSE `plan` 事件消费）。

- 服务端行为：
  1. 端点入口 `INSERT tasks(task_id=<generate>, status='PLANNING', user_message=..., context=...)`
  2. `asyncio.create_task(_background_reason_plan(task_id, message, context))` fire-and-forget
  3. 立即返 `{task_id, status:"PLANNING"}` HTTP 200

- `_background_reason_plan(task_id, ...)` 内做：
  1. `emit = engine._make_emit(task_id)`
  2. `await engine.run_reason(...)` → `emit(THINKING, {"content": "<reason summary>"})` **一次性**发一条
  3. `await engine.run_reflect(...)` → 不 emit（Reflect 是内部环节；(b2) 才发独立 thinking）
  4. `await engine.run_plan(...)` → `emit(PLAN, plan_out)` 实时
  5. `await engine.run_reflect_plan(...)` → 若调整了 plan，`emit(PLAN, adjusted_plan)` 再发一条；否则不发
  6. 结尾 `db_updater(task_id, {"status":"WAITING_CONFIRMATION", "plan": <final_plan>})`（若 reflect 不可行，则 `{"status":"WAITING_CONFIRMATION", "error":{"blocking_reason":...}}` —— 契约上 `WAITING_CONFIRMATION` 也接受 error 字段承载 blocking）
  7. 异常时 `db_updater(task_id, {"status":"FAILED", "error":{"code":"REASON_PLAN_FAILED","message":str(e)}, "finished_at":utcnow_naive()})` + `emit(ERROR, ...)` + `set_terminal_ttl`

- **前端行为**（PR-17 契约）：`chat` 返 `{task_id, PLANNING}` 后立即 `GET /agent/tasks/{task_id}/stream`，从 SSE 接 THINKING → PLAN 事件；见到 PLAN 后渲染 PlanCard + 确认按钮。此时 `tasks.status` 已经异步转为 `WAITING_CONFIRMATION`。

**Engine 改造**：

- `run_chat` **保留但重命名/重构**：拆成两个方法
  - 端点层调用的：`start_chat(user_message, context, db_updater) -> {"task_id":..., "status":"PLANNING"}`
  - 内部后台：`_background_reason_plan(task_id, user_message, context)` —— 与 `_background_execute` 对称结构

- **兼容策略**：PR-12 的既有测试 `test_orchestrator_engine.py` 里对 `run_chat` 的用法要跟着改。如果测试预期"chat 返 plan"，改为"chat 返 task_id + 从 EventBuffer 读 PLAN 事件"。**基线测试数 101 不能倒退**；改测试算基线维持不算下滑。

### 待兑现 api-contract 条款

- §3.3 THINKING（首条 summary）+ PLAN（实时）事件真正下发
- §4.1 `AgentChatResponse.status='PLANNING'` 语义生效
- `AgentChatResponse.initial_plan` 字段本 PR **不再填**（可选字段，PR-17 完全依赖 SSE）

---

## 三、主裁定 B（讨论轮追加）· `executions` 表作用域

### 裁定：**(ii) 延后 Stage 5.1**

**理由**：
1. Q5 (b1) 异步化后 PR-14 已达 ~7-9 commit 规模，纳入 executions 会破坏"每 PR 一件事"粒度
2. `executions` 表主要用于审计/复盘，MVP 前端不消费；短期不阻断 §3.3/§4.1/§4.4 关键功能
3. 单独 PR 补齐更清爽

### 已知违契明列（登记 Stage 5.1）

- **api-contract §4.5**："cancel 时写 `executions.status='CANCELLED'`" —— PR-14 **不满足**
- **PLAN §5.5**（Act 逐步 executions 落库）—— PR-14 **不满足**

### 落地动作

- `HANDOFF.md §9.3` 追加**开放项第 7 条**："executions 表全生命周期落库（§4.5 cancel 子句 + §5.5 Act 逐步）延后至 Stage 5.1 专门 PR"
- PR-14 STEP6 报告 §五 必须明列此违契项 —— 不掩盖，不算 §十三 触发点

---

## 四、Q1 · Task DB 持久化边界（修正版）

### 裁定：**方案 B（Engine `db_updater` 回调）+ 简化"中途不写 current_step"**

**修正说明**（讨论轮达成）：原 QUESTIONS §Q1 建议"Act 单步完成后 `db_updater(current_step)`"侵入 `run_act` 内层循环，工作量被低估。**本 PR 放弃 in-DB current_step 逐步追踪**，前端进行中步骤从 SSE `tool_call`/`progress` 事件推导（每步 emit tool_call 时前端高亮该 step_id）。

### 具体落地

**Engine `__init__` 增参**（默认 None，允许旧测试不传）：
```python
DbUpdater = Callable[[str, dict[str, Any]], Awaitable[None]]

class OrchestratorEngine:
    def __init__(
        self,
        # ... 既有参数不变
        db_updater: DbUpdater | None = None,
    ):
        # ...
        self.db_updater = db_updater
```

**REST 端点侧提供 updater**：
```python
async def _make_db_updater(session_factory) -> DbUpdater:
    async def _update(task_id: str, patch: dict[str, Any]) -> None:
        async with session_factory() as s:
            await s.execute(update(Task).where(Task.task_id == task_id).values(**patch))
            await s.commit()
    return _update
```

**Engine 调用点**（**全 PR 只有 3 处**，比 QUESTIONS §Q1 简化）：

1. **`_background_reason_plan` 结尾**（Q5 (b1) 引入）：
   - 成功：`await db_updater(task_id, {"status": "WAITING_CONFIRMATION", "plan": plan_out})`
   - 失败：`await db_updater(task_id, {"status": "FAILED", "error": {...}, "finished_at": utcnow_naive()})`

2. **`_background_execute` 起始**：
   - `await db_updater(task_id, {"status": "EXECUTING", "started_at": utcnow_naive()})`

3. **`_background_execute` 结尾**（Q1↔Q8 强绑定所必需）：
   - 成功：`await db_updater(task_id, {"status": "COMPLETED", "finished_at": utcnow_naive(), "result": {"content": <final_result>, "artifacts": <_build_artifacts(results)>}})`
   - 超时：`await db_updater(task_id, {"status": "FAILED", "finished_at": utcnow_naive(), "error": {"code": "TASK_TIMEOUT", "message": "task overall timeout", "recoverable": False}})`
   - 异常：`await db_updater(task_id, {"status": "FAILED", "finished_at": utcnow_naive(), "error": {"code": "INTERNAL_ERROR", "message": str(e), "recoverable": False}})`

**INSERT 由 REST 端点侧做**（不进 Engine），保证 Engine 层零 ORM 耦合：
- `chat` 端点：INSERT `{task_id, status:"PLANNING", user_message, context, task_type:None}`
- `skip-to-score` 端点：INSERT `{task_id, status:"PENDING", task_type:"MATCH_SCORE", user_message:"skip-to-score jd=...", context:{jd_id, candidate_ids}, plan:<generated>}`，随后端点自身 UPDATE 为 EXECUTING（见 §八）
- `execute-plan` 端点：不 INSERT（chat 已建行），直接 UPDATE 为 EXECUTING（见 §七）
- `cancel` 端点：UPDATE `{status:"CANCELLED", finished_at:utcnow_naive()}`（见 §七 + §六）

**测试策略**：单元测试注入 `db_updater=AsyncMock()`，断言调用参数（`db_updater.assert_awaited_with(task_id, {...})`）；集成测试用真 async_session_factory。

---

## 五、Q2 · SSE 实时推送方式

### 裁定：**方案 A（100ms 轮询 EventBuffer）**

采纳 QUESTIONS §Q2 原建议，无修改。

**实现骨架**（放在 `agent.py` 的 stream 端点内）：
```python
async def _event_stream(task_id: str, last_event_id: int, buffer: EventBuffer, heartbeat_sec: float):
    yield "retry: 3000\n\n"
    last_seq = last_event_id
    last_heartbeat = time.monotonic()
    while True:
        events = await buffer.read_after(task_id, last_seq)
        for ev in events:
            yield _format_sse(ev)
            last_seq = int(ev["id"])
            if ev["type"] in {"result", "error"} or (ev["type"] == "system" and ev.get("data", {}).get("message") == "cancelled"):
                return  # 终态关闭
        now = time.monotonic()
        if now - last_heartbeat >= heartbeat_sec:
            yield _format_sse({"type": "system", "id": None, "timestamp": ..., "data": {"message": "heartbeat"}})
            last_heartbeat = now
        await asyncio.sleep(0.1)
```

- **心跳事件不进 EventBuffer**（PLAN §Q5 硬约束）：只在 SSE HTTP 层瞬发，`id` 字段留空（或不下发 `id:` 行）
- SSE 帧格式化按 §3.2：`id:<n>\nevent:<type>\ndata:<json>\n\n`；heartbeat 无 `id:` 行，`event:system`，`data:{"message":"heartbeat"}`

---

## 六、Q3 · SSE 优雅关闭 + cancel 发事件

### 裁定：**方案 A + cancel 端点补发 `SYSTEM("cancelled")` 事件**

采纳 QUESTIONS §Q3 建议，追加"关流匹配加固"（讨论轮追加）：

**关流条件**（stream 端点循环内判定）：
- `ev.type in {"result", "error"}` → 立即退出
- `ev.type == "system" and ev.data.get("message") == "cancelled"` → 立即退出
- **仅上述三种关流；不用 DB 兜底轮询**（避免 QPS 放大）

**cancel 端点必须**（补 QUESTIONS §Q3 未明写的调用序）：
1. SELECT FOR UPDATE 拿到 Task（见 §七 Q6 修正）
2. 状态判断 → UPDATE 为 CANCELLED
3. `await event_buffer.append(task_id, SSEEventType.SYSTEM, {"message": "cancelled"})`
4. `await event_buffer.set_terminal_ttl(task_id)`
5. 返 200 `{task_id, status:"CANCELLED"}`

`_background_reason_plan` / `_background_execute` 无需感知 cancel（前端 stream 见到 `system:cancelled` 自动关闭；后台任务超时或异常时自然结束，即使继续跑也不影响用户）。

**兜底**：若 `_background_reason_plan` / `_background_execute` 在 cancel 后仍继续 emit RESULT/ERROR，属于事件多发一条，前端 stream 已关流不消费；`set_terminal_ttl` 已设，缓冲 3600s 后自然过期。可接受。

---

## 七、Q6 · cancel / execute 并发（修正版）

### 裁定：**SELECT FOR UPDATE + 显式状态检查，rowcount 方案作废**

**修正说明**（讨论轮达成）：QUESTIONS §Q6 原建议"原子 UPDATE + rowcount==0 → 409"无法区分"task 不存在（应 404）"与"状态非法（应 409）"，违 api-contract §4.5。

### 具体落地

**cancel 端点**：
```python
async def cancel_task(task_id: str, session: AsyncSession):
    async with session.begin():
        result = await session.execute(
            select(Task).where(Task.task_id == task_id).with_for_update()
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": f"task_id={task_id} not found"})
        if task.status not in {"PLANNING", "WAITING_CONFIRMATION"}:
            raise HTTPException(409, detail={"code": "ILLEGAL_STATE_TRANSITION", "message": f"cannot cancel task in state {task.status}"})
        task.status = "CANCELLED"
        task.finished_at = utcnow_naive()
    # 事务提交后补发 SSE
    await event_buffer.append(task_id, SSEEventType.SYSTEM, {"message": "cancelled"})
    await event_buffer.set_terminal_ttl(task_id)
    return {"task_id": task_id, "status": "CANCELLED"}
```

**execute-plan 端点**（同模式）：
```python
async def execute_plan(req: ExecutePlanRequest, session: AsyncSession):
    async with session.begin():
        result = await session.execute(
            select(Task).where(Task.task_id == req.task_id).with_for_update()
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", ...})
        if task.status != "WAITING_CONFIRMATION":
            raise HTTPException(409, detail={"code": "ILLEGAL_STATE_TRANSITION", ...})
        # 此处仍在事务内，UPDATE 由 Engine 的 db_updater 起始步完成（保证 EXECUTING 状态 finished_at 一致）
        # 或端点这里也做（选一处）—— 建议端点做，Engine 里 db_updater 起始改为幂等 UPDATE
    return await engine.run_execute(req.task_id, plan=task.plan, ..., db_updater=...)
```

**注意**：`with_for_update()` 在 async SQLAlchemy + asyncpg 上是支持的（Stage 3 candidate.py 状态转移已用过，可参考）。若发现驱动不返 rowcount，此方案不依赖 rowcount，不受影响。

**测试**：TC-S5-09-2 断言 chat 422（Pydantic 校验）/ tasks 404（task_id 不存在）/ cancel 409（状态非法）。

---

## 八、Q7 · skip-to-score 走完整 DB 生命周期

### 裁定：**采纳原建议，`run_skip_to_score` 加 `task_id` 参数覆盖假前缀**

REST `skip-to-score` 端点：
```python
async def skip_to_score(req: SkipToScoreRequest, session: AsyncSession, engine: OrchestratorEngine):
    task_id = generate_task_id()  # models/task.py helper
    plan_dict = {
        "steps": [
            {"step_id": f"step_score_{i}", "tool_name": "create_match_score",
             "tool_input": {"jd_id": req.jd_id, "resume_id": cid}}
            for i, cid in enumerate(req.candidate_ids)
        ]
    }
    async with session.begin():
        session.add(Task(
            task_id=task_id,
            status="EXECUTING",  # skip 跳过 PLANNING → 直接 EXECUTING
            task_type="MATCH_SCORE",
            user_message=f"skip-to-score jd={req.jd_id}",
            context={"jd_id": req.jd_id, "candidate_ids": req.candidate_ids},
            plan=plan_dict,
            started_at=utcnow_naive(),
        ))
    # 起后台任务（Engine 内不再自作 task_id）
    await engine.run_skip_to_score(
        jd_id=req.jd_id,
        candidate_ids=req.candidate_ids,
        task_id=task_id,  # 新增参数，Engine 内不再假拼
    )
    return {"task_id": task_id, "status": "EXECUTING"}
```

**Engine 侧改造**（`engine.py:298-328`）：
- `run_skip_to_score(jd_id, candidate_ids, task_id, db_updater=None, event_buffer=None)`
- 内部**移除** `task_id = f"task_skip_{jd_id}"`，改用外部传入
- 状态守卫 `check_transition(PENDING, EXECUTING)` **移除**（端点侧已 INSERT 为 EXECUTING；skip 语义就是跳过 PENDING/PLANNING）
- 后台跑 `_background_execute(task_id, plan, buffer)` 保持不变

---

## 九、Q8 · stream 对不存在 / 已过 TTL 的 `task_id` 处理

### 裁定：**404 for 不存在；3b（从 tasks.result / tasks.error 合成事件）for 过期**

**Q1↔Q8 强绑定验证**：Q1 简化版 db_updater 写 `{status, result, error, finished_at, plan}`（不含 current_step），Q8-3b 需要的 result/error 字段齐全，绑定成立。

### 具体落地（stream 端点开头）

```python
async def stream(task_id: str, request: Request, session: AsyncSession, buffer: EventBuffer):
    # 场景 1: 不存在 → 404
    result = await session.execute(select(Task).where(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", ...})

    last_event_id = int(request.headers.get("Last-Event-ID", 0) or 0)

    # 场景 3: 终态 + 缓冲空 → 从 DB 合成
    buffered = await buffer.read_after(task_id, last_event_id)
    if not buffered and task.status in {"COMPLETED", "FAILED", "CANCELLED"}:
        # 3b: 合成事件
        return StreamingResponse(_synthesize_from_task(task), media_type="text/event-stream")

    # 场景 2: 正常 stream
    return StreamingResponse(
        _event_stream(task_id, last_event_id, buffer, heartbeat_sec),
        media_type="text/event-stream",
    )

async def _synthesize_from_task(task: Task):
    yield "retry: 3000\n\n"
    if task.status == "COMPLETED" and task.result:
        yield _format_sse({"type": "result", "id": 1, "timestamp": task.finished_at.isoformat(), "data": task.result})
    elif task.status == "FAILED" and task.error:
        yield _format_sse({"type": "error", "id": 1, "timestamp": task.finished_at.isoformat(), "data": task.error})
    elif task.status == "CANCELLED":
        yield _format_sse({"type": "system", "id": 1, "timestamp": task.finished_at.isoformat(), "data": {"message": "cancelled"}})
```

**注意**：合成事件的 `id` 用 1（表明这是 synth，非缓冲真实序号；前端不该用它做 Last-Event-ID 二次重连——业务上也没意义）。

---

## 十、Q4/Q9 · 心跳配置化 + 测试策略

### 裁定：**采纳原建议**

**Settings 新增**（`backend/app/core/config.py`）：
```python
class Settings(BaseSettings):
    # ... 既有
    sse_heartbeat_interval_sec: float = 15.0
```

**stream 端点从 `Depends(get_settings)` 读该值**，测试用 `app.dependency_overrides[get_settings]` 传短间隔。

**测试**：
- httpx.AsyncClient.stream() 消费 SSE 帧，手写 `\n\n` 边界解析（~30 行 helper 放到 `tests/agent/sse_helpers.py`）
- 不新增 `sse-starlette` 依赖
- TC-S5-09-4 心跳测试用 override `sse_heartbeat_interval_sec=0.1`，等 0.35s 断言 ≥3 条 heartbeat
- TC-S5-09-3 Last-Event-ID 重放：先 `buffer.append` 10 条，再 stream with header `Last-Event-ID: 5`，断言只收到 id > 5 的
- TC-S5-09-5 首帧头部 `retry: 3000` + `Content-Type: text/event-stream`
- TC-S5-09-6 engine raise → 500：`app.dependency_overrides[get_engine] = lambda: raising_engine`

---

## 十一、Q5 内部 · run_chat 契约破坏与既有测试适配

### 说明

Q5 (b1) 异步化会破坏 PR-12 里 `test_orchestrator_engine.py` 对 `run_chat` 的既有断言（预期同步返 plan）。**执行体必须**：

1. 找出所有依赖 `run_chat` 同步返 plan 的测试（预计 2-3 个）
2. 改为：调 `start_chat` 拿 `{task_id, PLANNING}`，然后从注入的 fake `EventBuffer` 读 THINKING/PLAN 事件断言
3. **101 baseline 不能倒退**。测试改写后 pytest 总数应 ≥ 101（新增 TC-S5-09-* 会让基线上升）

**若发现改动量 > 6 个测试**，触发 §十三#10 停下汇报（异步化影响面超预期）。

---

## 十二、§十二 · 顺手清扫

### 裁定：**无顺手清扫**

采纳 QUESTIONS §十二 建议。PR-14 集中在端点/SSE，不再叠 lint/refactor 债，避免 §十三#8 类边界连锁。以下 3 项均是 PR-14 **主线**必修（不是顺手），已在各 Q 裁定内明列：
- Q7 修 `run_skip_to_score` 假前缀
- Q5 补 `run_chat` emit
- 兑现 engine.py:273 注释"PR-14 会从 tasks 表读入真实 plan"

---

## 十三、§十三 · 求助边界（10 条，最终版）

以下条件**任何一条命中**即停下汇报，不得自作主张：

1. **httpx.AsyncClient.stream() SSE 帧解析不稳定**（buffering 边界、`\n\n` 分隔）：停下讨论是否换 `TestClient` 或加 `httpx-sse`
2. **`asyncio.create_task` + DB session 生命周期**：`_background_reason_plan` / `_background_execute` 里 `db_updater` 闭包引用了已 close 的 session，raise `IllegalStateChangeError` 或类似 → 停下汇报，讨论 session 归属（可能要在 updater 内 `async_session_factory()` 现建）
3. **`sqlalchemy.select().with_for_update()` 在 asyncpg 上出错**：停下汇报（asyncpg 支持 FOR UPDATE，但语法差异或 `NOWAIT` 支持问题可能触发）
4. **StreamingResponse 客户端断线时 `active_counter` 泄漏**：即使 `_background_execute` 有 finally 兜底，若发现 stream 端点循环里 `asyncio.sleep(0.1)` 拒绝响应 `request.is_disconnected()`，导致协程僵尸 → 停下汇报
5. **Redis List `LRANGE 0 -1` 每次读全表**：200 条上限下 OK；若某测试 append > 200 后依赖旧事件重放失败（属 §3.5 "早期事件滚动"预期），停下汇报确认
6. **FastAPI 路由匹配意外**：`/tasks/{task_id}/stream` 与 `/tasks/{task_id}` 顺序对了但 `{task_id}` 依旧吞掉 `/stream`（Stage 4 先例），停下汇报
7. **测试基线倒退**：pytest 数量 < 101 即回归，停下汇报
8. **datetime aware/naive 混比新出现**（PR-13 决策 B 遗留）：走 `utcnow_naive()` / `_to_naive_utc()` 归一，**无新决策**，可自行修
9. **fakeredis 与真 Redis 的 pipeline / expire 行为差异**：TC-S5-09-* 在 fakeredis 上跑绿即算过（HANDOFF §9.3 第 4 条已列 Stage 6 兜底），不追究
10. **Q5 (b1) 异步化影响面超预期**：改动 `run_chat` 相关测试数 > 6 个，或发现异步化破坏 PR-13 的 EventBuffer/emit 测试，停下汇报（可能要退回 (a) 老实同步 + 违契文档化）

**不在本清单但材料改变 PR 契约的**（例：权威文档冲突、api-contract 又有新条目）：**同样停下汇报**。

---

## 十四、§十四 · 执行体行动清单（Executor Action Checklist）

按顺序完成，每步做完即打勾。

### 阶段 0 · 前置准备

- [ ] `git checkout master && git pull` 确认 = `aa57270`（或更新）
- [ ] `git checkout -b feat/pr-14-s5-09-agent-endpoints`
- [ ] `cd backend && uv run pytest -q` = **101 passed**（基线）
- [ ] `cd backend && uv run ruff check app` = 0 error（基线）
- [ ] 读完本 DECISION + `PR14-KICKOFF-QUESTIONS.md`（核对 9 问 + 追加 5 修正是否理解）

### 阶段 1 · Red-test skeleton commit（TDD 起手）

- [ ] 建 `backend/app/api/v1/agent.py` 空骨架（`router = APIRouter(prefix="/agent")`），**不加任何路由**
- [ ] 建 `backend/tests/api/test_agent_endpoints.py` 写 TC-S5-09-1..6 的骨架（`pytest.mark.xfail` 或直接 red）
- [ ] 建 `backend/tests/api/sse_helpers.py` 空文件（后续填 SSE 帧解析）
- [ ] Commit: `test(stage5): PR-14 red-test skeleton (TC-S5-09-1..6) + agent.py stub`

### 阶段 2 · Engine 改造（Q1 + Q5 + Q7 + Q8 都在这一步）

- [ ] `OrchestratorEngine.__init__` 加 `db_updater: DbUpdater | None = None`
- [ ] 新增 `_background_reason_plan(task_id, user_message, context)` 方法（Q5 (b1)）
- [ ] `run_chat` 拆重构：新增 `start_chat` 端点接口方法，返 `{task_id, status:"PLANNING"}`；旧 `run_chat` 可保留但内部走 `start_chat` + await 后台完成（若测试需要），或直接删除并适配测试
- [ ] `_background_execute` 补 db_updater 起始 + 结尾 3 处调用
- [ ] `run_skip_to_score` 新增 `task_id` 参数，移除假前缀
- [ ] 修 `test_orchestrator_engine.py` 里所有 `run_chat` 同步返 plan 的断言（预计 2-3 个测试）
- [ ] `uv run pytest -q` 确认 ≥ 101 passed（改测试后不倒退）
- [ ] Commit: `feat(stage5): S5-09 engine async chat + db_updater callback (Q1/Q5/Q7)`

### 阶段 3 · REST 端点（chat + execute + skip + cancel）

- [ ] `agent.py` 实现 4 个端点：
  - `POST /chat` → INSERT tasks + `asyncio.create_task(engine._background_reason_plan(...))` + 返 `{task_id, PLANNING}`
  - `POST /execute-plan` → SELECT FOR UPDATE 校验 → UPDATE EXECUTING → `engine.run_execute(...)`
  - `POST /skip-to-score` → generate_task_id + INSERT + `engine.run_skip_to_score(...)`
  - `GET /tasks/{task_id}` → SELECT + 序列化 TaskStatus
  - `POST /tasks/{task_id}/cancel` → SELECT FOR UPDATE + 状态校验 + UPDATE + emit SYSTEM("cancelled") + set_terminal_ttl
- [ ] `api/v1/__init__.py` 注册 `agent_router`
- [ ] `_make_db_updater(session_factory)` helper 放在 `agent.py` 或独立 `deps.py`
- [ ] TC-S5-09-2 转绿
- [ ] Commit: `feat(stage5): S5-09 agent REST endpoints (chat/execute/skip/cancel) + Q6 SELECT FOR UPDATE`

### 阶段 4 · SSE stream 端点（Q2/Q3/Q4/Q8）

- [ ] `agent.py` 加 `GET /tasks/{task_id}/stream`
  - **路由顺序**：**先声明 `/stream`，再声明 `/{task_id}`**（PLAN §Q11）
  - 场景 1 (404) + 场景 3 (3b synth) + 场景 2 (正常 stream)
  - `_event_stream(task_id, last_event_id, buffer, heartbeat_sec)` 主循环（100ms 轮询 + wall-clock heartbeat + 终态关流）
  - `_format_sse(ev)` helper（`id:` / `event:` / `data:` / `\n\n`）
  - `_synthesize_from_task(task)` helper（3b 路径）
- [ ] `Settings.sse_heartbeat_interval_sec = 15.0` 加入 `core/config.py`
- [ ] `sse_helpers.py` 填 SSE 帧解析（httpx.stream 消费）
- [ ] TC-S5-09-1/3/4/5/6 转绿
- [ ] Commit: `feat(stage5): S5-09 SSE stream endpoint + Last-Event-ID replay + heartbeat + Q8 synth (Q2/Q3/Q4/Q8)`

### 阶段 5 · 测试补齐 + 验收三道门

- [ ] 补 TC-S5-09-3 的 fakeredis 前置数据 + `httpx.AsyncClient.stream()` 消费断言
- [ ] 补 TC-S5-09-4 的 `dependency_overrides` 短心跳
- [ ] 补 TC-S5-09-6 的 engine raise → 500 断言
- [ ] `cd backend && uv run pytest -q` → 全绿（预计 ~107-110 passed）
- [ ] `cd backend && uv run ruff check app` → 0 error
- [ ] `cd backend && uv run ruff format --check app` → 0 diff
- [ ] `cd frontend && npm run lint && npm run build` **可跳过**（PR-14 不动 frontend/src/**）
- [ ] Commit: `test(stage5): TC-S5-09-1..6 + SSE fixtures + heartbeat override`

### 阶段 6 · STEP6 报告

- [ ] 写 `docs/planning/stage5/PR14-STEP6-REPORT.md`：
  - §一 概要（PR-14 = S5-09，合入 §Q5 (b1) 异步 + executions 延后）
  - §二 完成清单（4 端点 + stream + 心跳 + Q1 db_updater + Q5 异步 + Q6 SELECT FOR UPDATE + Q7 真 task_id + Q8 3b synth）
  - §三 验收三道门（pytest / ruff / ruff format 输出粘贴）
  - §四 影响面（新增/修改文件清单）
  - §五 偏差 / 决策记录（**必列**：executions 表未纳入 →Stage 5.1 开放项；`run_chat` 契约破坏 → PR-12 老测试改写；current_step 中途不写；如触发 §十三 任一条也在此登记）
  - §六 工作区清理（临时文件 rm 清单）
  - §七 提交链（commit hash + message 列表）
- [ ] Push branch: `git push -u origin feat/pr-14-s5-09-agent-endpoints`
- [ ] 回报指挥官 FF-merge 评审

---

## 十五、§十五 · Commit 拆分（最终建议）

**6 commit 版**（推荐）：

1. `test(stage5): PR-14 red-test skeleton (TC-S5-09-1..6) + agent.py stub` （阶段 1）
2. `feat(stage5): S5-09 engine async chat + db_updater callback (Q1/Q5/Q7)` （阶段 2）
3. `feat(stage5): S5-09 agent REST endpoints (chat/execute/skip/cancel) + Q6 SELECT FOR UPDATE` （阶段 3）
4. `feat(stage5): S5-09 SSE stream endpoint + Last-Event-ID replay + heartbeat + Q8 synth (Q2/Q3/Q4/Q8)` （阶段 4）
5. `test(stage5): TC-S5-09-1..6 + SSE fixtures + heartbeat override` （阶段 5）
6. `docs(stage5): PR14 STEP6 report` （阶段 6，直推 master 或走本分支均可；AGENTS.md §4.1 docs-only 可直推）

**若执行体判断 commit 2 过大**，允许拆成 2a (engine async chat + Q5) / 2b (db_updater + Q7)，共 7 commit。

**若发现 commit 4 过大**（stream 主循环 + heartbeat + synth），允许拆成 4a (stream 主循环) / 4b (heartbeat + synth)，共 7 commit。

**禁止**：把测试与实现分开成两个 PR 提交（TDD 骨架 commit 1 除外；后续每个功能 commit 内应带对应测试转绿或跟随下一 commit）。

---

## 十六、§十六 · 验收三道门（不可跳过）

`PR14-STEP6-REPORT.md` §三 必须粘贴以下三段输出：

1. **`cd backend && uv run pytest -q`** —— 必须 ≥ 101 passed（预计 107-110）；任何 failed / error 视为不通过
2. **`cd backend && uv run ruff check app`** —— 必须 0 error
3. **`cd backend && uv run ruff format --check app`** —— 必须 0 diff

三道门任一失败，不得声称 PR-14 完成，不得写 STEP6 §三"全绿"。

---

## 十七、§十七 · 与既有 HANDOFF 状态的对齐

PR-14 STEP6 报告合入后，`HANDOFF.md` 需更新：

- 头部：`PR-10/11/12/13/14/15 已合入 master，PR-16 待动工`（或调整为下一个 PR）
- §9.1 状态表：PR-14 行 = ✅，测试基线 101 → 新数（预计 107-110）
- §9.3 开放项**追加第 7 条**："executions 表全生命周期落库（§4.5 cancel 子句 + §5.5 Act 逐步）延后至 Stage 5.1 专门 PR"
- §9.4 已知陷阱：追加"异步 `chat` 端点的 `db_updater` 闭包 session 生命周期"（如触发 §十三#2 则详述）
- §9.5 新文件表：追加 `app/api/v1/agent.py`、`tests/api/test_agent_endpoints.py`、`tests/api/sse_helpers.py`
- §9.6 下个架构建议：改写为 PR-15/16（假定顺序）的入手路径

（此步是 STEP6 报告后的额外 docs 动作，指挥官走 FF-merge 时统一操作。）

---

## 十八、§十八 · 汇总裁定表

| # | 主题 | 裁定 |
|---|---|---|
| 主 A | Q5 隐藏前提 chat 同步/异步 | **(b1) 异步 + 非流式 thinking** |
| 主 B | executions 表作用域 | **(ii) 延后 Stage 5.1** |
| Q1 | Task DB 持久化边界 | **方案 B（Engine `db_updater` 回调）+ 简化"中途不写 current_step"** |
| Q2 | SSE 实时推送方式 | **方案 A（100ms 轮询 EventBuffer）** |
| Q3 | SSE 优雅关闭 | **方案 A + cancel 补发 SYSTEM("cancelled") + set_terminal_ttl** |
| Q4 | 15s 心跳实现 | **方案 B（单循环 wall-clock）+ `sse_heartbeat_interval_sec` 配置** |
| Q5 | chat emit thinking/plan | **方案 A + 异步化落地（THINKING 一次性 + PLAN 实时）** |
| Q6 | cancel/execute 竞态 | **修正为 SELECT FOR UPDATE + 显式状态检查**（rowcount 方案作废） |
| Q7 | skip-to-score DB 生命周期 | **走完整 DB + `run_skip_to_score` 加 task_id 参数** |
| Q8 | stream 不存在/过期 task | **404 / 3b（从 tasks.result/error 合成事件，与 Q1 强绑定）** |
| Q9 | 测试策略 | **httpx.stream() + Settings 心跳可配 + 不加 sse-starlette** |
| 附 | commit 拆分 | **6 commit（推荐）or 7 commit（允许 2/4 拆分）** |
| 附 | §十二 顺手清扫 | **无** |
| 附 | §十三 求助边界 | **10 条（原 9 + 追加异步化影响面）** |
| 附 | §十九 暂行方案追债 | **5 条（3 需 §9.3 登记 + 1 沿用既有 + 1 契约澄清）** |

---

**执行体可立即按 §十四 开工。裁定文件即合同，未列条款保留 QUESTIONS 建议不变；触及 §十三 停下汇报。**

---

## 十九、§十九 · 本 PR 暂行方案 & 后续 PR 追债清单

以下条目是 PR-14 为控制作用面**有意留下**的暂行方案。落地时执行体**必须**在 STEP6 报告 §五 内逐条声明，并同步登记到 `HANDOFF.md §9.3`（Stage 5.1 追债清单）。

**不允许"沉默地留下"**：任何一条未在 STEP6 §五 明列即视为 §十三#7 类隐蔽变更，PR 打回。

### 19.1 · executions 表全生命周期未落库

- **违契点**：`api-contract.md §4.5`（cancel 时写 `executions.status='CANCELLED'`）、`PLAN-STAGE5.md §5.5`（Act 逐步 executions 记录）
- **本 PR 暂行**：不写 executions 表；`models/execution.py` 已存在但闲置
- **后续补齐**：**Stage 5.1 专门 PR**
  - db_updater 回调扩至两张表（executions 表随每步 Act 结束 INSERT，随终态 UPDATE）
  - cancel 端点在 UPDATE tasks 后同事务内 UPDATE executions
  - `run_act` 加 per-step callback（配合 19.2 一并解决）
- **登记位置**：`HANDOFF §9.3 追债项第 7 条`（待 PR-14 STEP6 追加）

### 19.2 · current_step 中途不写 DB

- **本 PR 暂行**：`tasks.current_step` 列保留，但 db_updater 只在 INSERT/终态触碰；`_background_execute` 中途不 UPDATE
- **前端影响**：ChatCenter（PR-17）进行中步骤高亮**只能从 SSE `tool_call` / `progress` 事件推导**；SSE 断连且 TTL 过期后前端不知道"进行到哪一步"（属降级路径，可接受）
- **后续补齐**：**与 19.1 同 PR**
  - 给 `run_act` 加 `on_step_start` / `on_step_end` callback
  - db_updater 在每步开始时更新 `current_step`
  - 配合 executions 表逐步落库
- **登记位置**：`HANDOFF §9.3 追债项第 8 条`（待 PR-14 STEP6 追加）

### 19.3 · THINKING 事件非 token 流

- **契约位置**：`api-contract.md §3.3` 未明确要求 token 流；但 UX 上"边思考边流"是通用期待
- **本 PR 暂行**：Reason 完成后**一次性**发一条 `THINKING` 事件（`data.content` = reason 输出的 summary/内心独白）；Reflect / Reflect-Plan 阶段**不 emit thinking**
- **后续补齐**：**Stage 6+（暂无 PR 编号）**
  - Reason skill 接入流式 LLM adapter（`langchain-openai` 已支持 `astream`）
  - `run_reason` 改造成 async generator，逐 token yield
  - `_background_reason_plan` 接住 stream，逐帧 `emit(THINKING, {"delta": token})`
  - 前端 PR-17 的 ThinkingCard 支持增量渲染
- **登记位置**：`HANDOFF §9.3 追债项第 9 条`（待 PR-14 STEP6 追加）
- **备注**：此项**不在 Stage 5.1 范围**（Stage 5.1 只清 MVP 硬伤），列为 Stage 6 或独立体验优化 PR

### 19.4 · SSE 端点 100ms 轮询（不启 Redis Pub/Sub）

- **已登记**：`HANDOFF §9.3 追债项第 2 条`（PR-13 已列）
- **本 PR 无新增**：只是继续沿用；此处提及**用于闭合列表**，避免误以为 PR-14 新引入
- **后续补齐**：Stage 5.1 多进程部署前启 Pub/Sub 时改造

### 19.5 · `AgentChatResponse.initial_plan` 字段本 PR 不填

- **契约位置**：`api-contract.md §4.1` 明确 `initial_plan?: Plan`（可选）
- **本 PR 行为**：`chat` 端点返 `{task_id, status:"PLANNING"}`，`initial_plan` 字段**不返**；前端完全靠 SSE `PLAN` 事件消费
- **性质**：**非债务**，是契约明晰化（字段可选）
- **登记位置**：不入 §9.3；仅在 PR-14 STEP6 §五 记录一次"契约字段用法澄清"

### 19.6 · STEP6 报告 §五 强制条款

PR-14 STEP6 报告 `§五 偏差 / 决策记录` 必须包含以下 **6 条声明**（缺一视为报告不合格，退回补写）：

- [ ] 19.1 executions 未落库 → HANDOFF §9.3 追债项第 7 条已追加
- [ ] 19.2 current_step 中途不写 → HANDOFF §9.3 追债项第 8 条已追加
- [ ] 19.3 THINKING 非 token 流 → HANDOFF §9.3 追债项第 9 条已追加
- [ ] 19.4 SSE 100ms 轮询沿用（引用 §9.3 第 2 条既有登记，无新追加）
- [ ] 19.5 `initial_plan` 字段不填 → 契约澄清，不入 §9.3
- [ ] `run_chat` 契约破坏（PR-12 老测试改写清单） → 若改动 > 6 个测试触发 §十三#10（回滚决策 A/B/C 讨论）

**若本 PR 执行过程中新增更多暂行方案（例：SELECT FOR UPDATE 遇 asyncpg 特性只做半吊子）**，一律追加到本 §十九 与 HANDOFF §9.3，**禁止只在 commit message 里带过一句**。

---

**§十九 收官原则**：暂行方案不是耻辱，隐藏的暂行方案才是。每一条都有 canonical 家门（DECISION §十九 + HANDOFF §9.3），后续架构师不必翻 git log 考古。
