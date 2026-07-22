# PR-14 · Agent REST 端点 + SSE HTTP 流 · 启动前求助

> 关联：PR-14 = **S5-09（REST 四端点 + SSE 流端点 + 取消端点）** · 建议分支 `feat/pr-14-s5-09-agent-endpoints`
> 权威依据：`docs/planning/PLAN-STAGE5.md §Q5/Q6/Q7/Q11` · `docs/planning/TASKS-STAGE5.md §S5-09` · `docs/planning/TEST-PLAN-STAGE5.md §S5-09（TC-S5-09-1..6）` · `docs/api-contract.md §3.1/§3.2/§3.5/§4.1-4.5` · PR-13 STEP6 §五 决策记录
> 状态：等待指挥官裁定，尚未开工

---

## 前置事实（已核验，2026-07-21 · master `aa57270`）

| 事实 | 出处 | 说明 |
|---|---|---|
| **master HEAD** | 本地 + 远端 = `aa57270` | PR-13 已 FF 合入 + docs 追加 |
| **测试基线** | `uv run pytest -q` = **101 passed** | 含 PR-13 两个测试骨架 |
| **Engine 已就绪的方法** | `engine.py` | `run_chat`（同步跑 R-P-R 返 plan）/ `run_execute`（fire-and-forget 起 `_background_execute`）/ `run_skip_to_score` / `run_cancel` / `run_reflect_act` |
| **`run_execute` 返回结构** | engine.py:296 | `{status_code:200, status:"EXECUTING", task_id}`，超限时 `{status_code:429, error:"TASK_LIMIT_EXCEEDED"}` |
| **`run_chat` 返回结构** | engine.py:212-231 | `{status_code, status:"WAITING_CONFIRMATION"｜..., plan?, reflect_plan?, blocking_reason?}`；R-P-R 全同步跑（4 次 LLM 调用 20-60s） |
| **`run_chat` 不接 emit** | engine.py:208 | 参数签名有 `emit=None` 但内部**未使用**（R-P-R 阶段无 SSE 事件产出） |
| **`run_skip_to_score` task_id 假前缀** | engine.py:312 | `task_id = f"task_skip_{jd_id}"` —— **不是** `task_{uuid4_hex_12}` 契约（PR-14 REST 层需覆盖） |
| **`_background_execute` 无 DB 回写** | engine.py:330-399 | 只 `EventBuffer.append(RESULT/ERROR)` + `set_terminal_ttl`；`tasks` 表的 status/finished_at/result/error **完全没写** |
| **`tasks` 表字段** | models/task.py | task_id / user_message / task_type / status / plan / context / result / error / current_step / started_at / finished_at + TimestampMixin |
| **Redis DI** | app/core/redis.py | `def get_redis(request: Request) -> aioredis.Redis` — 从 `app.state.redis` 读 |
| **EventBuffer.append** | event_buffer.py:38-60 | 自动分配 seq_id（`INCR sse:seq:{task_id}`）+ 时间戳（`datetime.now(UTC).isoformat()`）+ MAXLEN=200 环形裁剪 |
| **EventBuffer.read_after** | event_buffer.py:62-68 | `last_event_id=None` → 全量重放；否则 `id > last_event_id` 过滤 |
| **API v1 router 注册** | api/v1/__init__.py | 已注册 jd/resume/candidate/match；**未注册 agent** |
| **依赖检查** | pyproject.toml | `sse-starlette` **未依赖**；`fastapi` / `redis>=5.0.0` / `fakeredis>=2.20.0` 已在 |
| **api-contract §3.5 关键约束** | api-contract.md:245-266 | Last-Event-ID 头重放 / `retry: 3000` / 15s `system` heartbeat / 缓冲 MAXLEN 200 / 终态后 TTL 3600s |
| **PLAN §Q11 路由顺序** | PLAN-STAGE5.md:190-194 | `/stream` **必须**先于 `/{task_id}` 声明（Stage 4 教训） |

---

## Q1 · Task 生命周期的 DB 持久化边界（**核心，本 PR 最大分歧点**）

### 背景

PR-13 的 `run_execute` 用 `asyncio.create_task` fire-and-forget 起 `_background_execute`，但**`tasks` 表状态完全没写**：`status` 卡在 `PENDING`（或 `WAITING_CONFIRMATION` 若 REST 层先写），`finished_at` 永远 NULL，`result` / `error` 也没落库。

这是 HANDOFF §9.3 明列的 Stage 5.1 妥协第 1 条（fire-and-forget），但 PR-14 必须至少把**Task 状态**写入 DB —— 否则 `GET /agent/tasks/{task_id}` 无从查询状态。

### 三个方案

- **A. REST 端点做头尾持久化 + Engine 层不动 DB**
  - `chat` 端点：`INSERT tasks(status='WAITING_CONFIRMATION', plan=..., user_message=...)`
  - `execute` 端点：`UPDATE tasks SET status='EXECUTING', started_at=NOW() WHERE task_id=? AND status='WAITING_CONFIRMATION'`（乐观锁，UPDATE 影响行数=0 → 409）
  - `_background_execute` 结尾**无 DB 写** → `finished_at` / `result` / `error` 依赖前端从 SSE `result` 事件消费；`GET /tasks/{id}` 靠 Redis 缓冲 + 状态字段回退
  - **缺点**：`GET /tasks/{id}` 拿不到 `result`（只能返 `status`+SSE 请自查）；`current_step` 无法更新；SSE 缓冲过 TTL 后终态信息永久丢失。**不合规**（api-contract §4.4 `TaskStatus.result: Any`）

- **B. Engine 层持有 `db_updater` 回调，由 Engine 内部写全部生命周期字段**
  - `OrchestratorEngine.__init__` 加 `db_updater: Callable[[str, dict], Awaitable[None]] | None = None`
  - `_background_execute` 结尾调 `db_updater(task_id, {"status":"COMPLETED","finished_at":...,"result":...})`
  - REST 端点提供 `db_updater` 实现（用独立 async session）
  - `chat` 端点：`INSERT tasks(status='WAITING_CONFIRMATION', ...)` 后再传 engine
  - **优点**：Engine 关注编排，DB 细节封装在回调；测试可注入 fake updater 断言调用参数
  - **缺点**：多一层抽象；回调闭包持有 db session 生命周期需要小心

- **C. `_background_execute` 内直接 `async with async_session_factory() as session` 自建 session 写 DB**
  - 不改 engine 接口，`_background_execute` 直接 `import` factory
  - **优点**：改动最小，无新参数
  - **缺点**：Engine 层耦合 `app.core.database`（模块边界破坏 Q3 分层设计）；测试需要 mock 全局 factory；不方便注入 in-memory 测试 DB

### 我的建议：**方案 B**

Engine 已经用 DI 拿 `registry` / `tool_router` / `active_counter` / `event_buffer`，加一个 `db_updater` 回调是**同样的模式**，不破坏边界。REST 端点在建 Engine 时把绑定 db session 的 updater 传进去；测试 fixture 传 mock。

**具体 updater 签名**（建议）：
```python
DbUpdater = Callable[[str, dict[str, Any]], Awaitable[None]]

# REST 端点里：
async def _make_updater(session_factory) -> DbUpdater:
    async def _update(task_id: str, patch: dict) -> None:
        async with session_factory() as s:
            await s.execute(update(Task).where(Task.task_id == task_id).values(**patch))
            await s.commit()
    return _update
```

**Engine 内调用点**（`_background_execute` 补齐）：
- 起始：`await db_updater(task_id, {"status":"EXECUTING","started_at":utcnow_naive()})`
- Act 单步完成后：`await db_updater(task_id, {"current_step":step_id})`
- 成功结尾：`await db_updater(task_id, {"status":"COMPLETED","finished_at":utcnow_naive(),"result":{...}})`
- 失败/超时结尾：`await db_updater(task_id, {"status":"FAILED","finished_at":utcnow_naive(),"error":{"code":...,"message":...}})`

**待裁定**：采纳方案 B？updater 签名同意？还是希望简化为只在**终态**写一次（放弃 `current_step` in-DB 追踪，Q3 由 SSE 缓冲兜底）？

---

## Q2 · SSE 端点如何"实时推送"（`asyncio.sleep` 轮询 vs `asyncio.Queue`）

### 背景

PLAN §Q6：**MVP 不启 Redis Pub/Sub**，但 SSE 端点必须实时推送——`_background_execute` 每 `EventBuffer.append` 一条，SSE 端点应几乎立刻 flush 给客户端。

PR-13 STEP6 §五 提到的实现路径是"`read_after(last_event_id)` + `asyncio.sleep(0.1)` 轮询"。这是最简单的方案，但要问清楚。

### 两个方案

- **A. 100ms 轮询 EventBuffer**（PR-13 STEP6 §五 提到）
  ```python
  last_seq = int(last_event_id or 0)
  while task_not_terminal:
      events = await buffer.read_after(task_id, last_seq)
      for ev in events:
          yield format_sse(ev)
          last_seq = int(ev.id)
      await asyncio.sleep(0.1)
  ```
  - **优点**：无跨进程通信，单进程即可工作，测试用 fakeredis 直接跑
  - **缺点**：轮询有 100ms 延迟；每次 `LRANGE` 全表拉再过滤（不是最优，但 200 条上限可接受）；空闲时也在轮询（CPU 极小）

- **B. `asyncio.Queue` 进程内广播**
  - Engine 内维护 `task_id → asyncio.Queue` 映射
  - `_background_execute` 每 append 一条到 EventBuffer 后同时 `queue.put_nowait(ev)`
  - SSE 端点建连时先从 EventBuffer 拉历史（重放 `> last_event_id`），然后阻塞在 `queue.get()` 等新事件
  - **优点**：真正实时，零延迟；无 sleep 循环
  - **缺点**：**只在同一进程内工作**（Uvicorn 单 worker OK；未来上多 worker 会失效，此时才该启 Pub/Sub —— 但这是 Stage 5.1 妥协项）；引入全局 queue 字典的清理时机问题（任务终态后要清）

### 我的建议：**方案 A（100ms 轮询）**

**理由**：
1. PLAN §Q6 明确 MVP 不启 Pub/Sub，方案 A 与之一致（跨进程也能工作，只是延迟高）
2. PR-13 STEP6 已经提前写死这条路径
3. 100ms 延迟在人眼可接受范围（<200ms 感知不到）
4. 方案 B 的 in-process Queue 是"提前引入不必要复杂度"，若未来 Stage 5.1 上 Pub/Sub 会推翻这层，反而多做一次迁移

**待裁定**：方案 A 采纳？还是希望方案 B？或者做**混合**（in-process queue 优先，fallback 到轮询）？

---

## Q3 · SSE 流何时优雅关闭（终态检测）

### 背景

SSE 端点是 `StreamingResponse`，`yield` 的循环得有退出条件。终态可能来自：
1. `_background_execute` 成功 → `RESULT` 事件后 `set_terminal_ttl`
2. `_background_execute` 失败/超时 → `ERROR` 事件后 `set_terminal_ttl`
3. `cancel` 端点被调用 → Task.status 转 `CANCELLED`（**cancel 现在不发 SSE 事件**）
4. 客户端断线（`StreamingResponse` 自然处理，但轮询循环要能感知 disconnect）

### 三种方案

- **A. 检测事件 type ∈ {RESULT, ERROR}** —— 从事件流本身判断
  - 优点：单一信息源，与 EventBuffer 一致
  - 缺点：**cancel 现在不发 SSE 事件** → cancel 后 stream 永不退出；需要给 cancel 加一条 `system("cancelled")` 事件

- **B. 每轮循环 `SELECT status FROM tasks WHERE task_id=?`** —— 查 DB
  - 优点：DB 是权威事实
  - 缺点：轮询里加 DB 查询，QPS 放大（100ms 一次 * 每客户端）；DB 依赖增强

- **C. 混合** —— 事件流优先，DB 兜底
  - 见到 RESULT/ERROR 后关闭
  - 5 秒无新事件时查一次 DB 确认是否终态（低频 DB 查询）

### 我的建议：**方案 A + 补 cancel SSE 事件**

**具体**：
- `run_cancel` / cancel 端点在成功转 CANCELLED 后**主动 `event_buffer.append(SSEEventType.SYSTEM, {"message":"cancelled"})` + `set_terminal_ttl`**
- SSE 端点循环退出条件：`ev.type in {RESULT, ERROR}` 或（cancel 情况下）见到 `type=SYSTEM` 且 `data.message == "cancelled"`
- **备用退出**：见到 `Task.status ∈ terminal` 的 SSE 事件后再多轮询 200ms 拉取剩余事件，然后关闭（防止有 in-flight 事件被截断）

**待裁定**：方案 A 采纳？cancel 端点补发 `SYSTEM("cancelled")` 事件？还是希望方案 C 更保守（DB 兜底）？

---

## Q4 · 15s 心跳的实现位置

### 背景

PLAN §Q5 明确：**心跳不入 EventBuffer**（重放时不重发），由 SSE HTTP 端点在 `StreamingResponse` 内直接发帧。EventBuffer 的 docstring 也说了这点。

### 三个实现

- **A. 单 `asyncio.gather` 双协程**
  ```python
  async def _events_gen(): ...  # 轮询 EventBuffer
  async def _heartbeat_gen():  # 每 15s yield heartbeat
      while True:
          await asyncio.sleep(15)
          yield format_sse(system_event("heartbeat"))
  # merge two generators — 需要复杂 anext 交替
  ```
  - 缺点：Python asyncio 里 merge async generators 需要手写调度器，容易出错

- **B. 单循环里判定 wall-clock**
  ```python
  last_heartbeat = time.monotonic()
  while True:
      events = await buffer.read_after(...)
      for ev in events: yield ...
      now = time.monotonic()
      if now - last_heartbeat >= 15:
          yield format_sse(system_event("heartbeat"))
          last_heartbeat = now
      await asyncio.sleep(0.1)
  ```
  - **优点**：单循环，简单可测；100ms 轮询精度 → 心跳误差 <100ms
  - **缺点**：需要引入 `time.monotonic`

- **C. 独立 `asyncio.Task` 用 `asyncio.Queue`**
  - 一个 task 轮询 EventBuffer 并 `queue.put`；另一个 task 每 15s `queue.put` heartbeat；主循环从 queue 出
  - 缺点：状态多、清理复杂

### 我的建议：**方案 B**

单循环最少心智、最好测试。心跳测试用**可配置 `heartbeat_interval_sec`** 让 pytest 传 `0.1` 秒（默认 15s），走 15 tick 内断言收到心跳，无需 `freezegun` 时间旅行。

**待裁定**：方案 B 采纳？`heartbeat_interval_sec` 通过 `Settings` 暴露还是端点参数？

---

## Q5 · `chat` 端点是否 emit R-P-R 阶段的 `thinking` / `plan` 事件

### 背景

api-contract §3.3 定义了 `thinking`（Reason/Reflect 推理中）和 `plan`（Plan 生成后）两类事件。**当前 `run_chat` 完全不 emit**，`chat` 请求返回时 R-P-R 已经跑完，前端只能靠 HTTP 响应体的 `initial_plan` 显示，看不到过程。

api-contract 明示这两个事件应发；不发就是**违契**。

### 两个方案

- **A. PR-14 补齐**：给 `run_chat` 传 `emit` 回调（同 `run_execute` 一样），Reason 阶段前 emit `thinking("Reasoning...")`、Reflect 后 emit `thinking("Reflecting...")`、Plan 后 emit `plan(plan_out)`、Reflect-Plan 后可以再 emit 一条 `thinking("Adjusting plan...")`
  - 需要 chat 端点先 `INSERT tasks(task_id, status='PENDING')` 拿到 task_id，再传给 engine emit
  - **好处**：前端 ChatCenter（PR-17）能实时渲染 R-P-R 过程
  - **代价**：chat 端点必须先建 Task 行才能 emit（有 task_id 才能 append 到 `sse:buf:{task_id}`）；HTTP 响应仍返 `initial_plan`（同步等 20-60s）

- **B. PR-14 只发 SYSTEM("connected") 事件**，`thinking` / `plan` 事件等 PR-15/16 / 后续再补
  - **好处**：改动最小，不改 `run_chat` 签名
  - **坏处**：违契 §3.3；PR-17 前端做出来是"哑巴 chat"

### 我的建议：**方案 A**

理由：
1. api-contract §3.3 是权威契约，`thinking`/`plan` 事件是 §3.3 表格明列，PR-14 不发就是违契
2. PR-13 已经把 EventBuffer 建好、`_make_emit(task_id)` 已经实现，`run_chat` 补个 emit 参数是 10 行改动
3. PR-17 前端设计肯定基于"能看到 thinking"

**具体动作**：
- `run_chat(chat_input, db, emit)` 内 4 处 emit：`thinking("Reasoning...")` / `thinking("Reflecting...")` / `plan(plan_out)` / `thinking("Adjusting plan...")`（可选）
- REST `chat` 端点：先 `INSERT tasks(task_id, status='PLANNING', user_message=..., context=...)`，然后 `emit = engine._make_emit(task_id)`，然后 `run_chat(input, db, emit)`，最后 `UPDATE tasks SET status='WAITING_CONFIRMATION', plan=...`

**待裁定**：方案 A 采纳？还是希望简化为方案 B（只发 SYSTEM）？

---

## Q6 · `cancel` 与 `execute` 的竞态

### 背景

api-contract §4.5：cancel 仅在 `PLANNING` / `WAITING_CONFIRMATION` 有效。但用户在 UI 上可能同时点"确认执行"和"取消"——两个 POST 几乎同时到，谁先赢？

假设：
1. Client 收到 `chat` 返回 `task_id=T, status=WAITING_CONFIRMATION`
2. Client 点"确认" → POST `/execute-plan {task_id: T}`
3. Client 又点"取消" → POST `/tasks/T/cancel`

两个请求在服务端并发，都读到 `tasks.status='WAITING_CONFIRMATION'`，都通过状态守卫。竞态。

### 三个方案

- **A. 数据库层原子 UPDATE**（乐观锁）
  ```python
  # execute 端点：
  result = await s.execute(
      update(Task)
      .where(Task.task_id == req.task_id, Task.status == "WAITING_CONFIRMATION")
      .values(status="EXECUTING", started_at=utcnow_naive())
  )
  if result.rowcount == 0:
      raise HTTPException(409, "Task not in WAITING_CONFIRMATION state")
  ```
  同理 cancel 端点 `WHERE status IN ('PLANNING', 'WAITING_CONFIRMATION')`
  - **优点**：DB 层原子，简单；不需要额外锁
  - **缺点**：SQLAlchemy 需要 `synchronize_session=False` 或 emitting `RETURNING`

- **B. `SELECT FOR UPDATE`（悲观锁）**
  - 更严格，但需要事务且 SQLAlchemy async 支持稍复杂

- **C. 应用层锁（`asyncio.Lock` 按 task_id）**
  - 只在单进程内有效，多进程失效
  - PLAN §Q7 已用 Redis 计数器跨进程；应用锁不适配这个方向

### 我的建议：**方案 A**

原子 UPDATE + 检查 rowcount，是 PostgreSQL 上标准做法，也是 Stage 3 candidate.py 状态转移已经在用的模式（可以看一眼 candidate.py 状态转移代码复用套路）。

**待裁定**：方案 A 采纳？还是希望方案 B（SELECT FOR UPDATE 更严格）？

---

## Q7 · `skip-to-score` 是否走 in-DB Task 生命周期

### 背景

`run_skip_to_score`（engine.py:298-328）目前用 `task_id = f"task_skip_{jd_id}"`（**假前缀**），跳过 R-P-R 直接构造 Act plan 起后台任务。

问题：
1. 假前缀违反 `task_{uuid4_hex_12}` 契约（PLAN §Q10）
2. 无 `INSERT tasks` → `GET /tasks/{task_id}` 会 404
3. 若合规，走 `INSERT tasks(status='EXECUTING', task_type='MATCH_SCORE', context={jd_id, candidate_ids})` + `_background_execute` 前 UPDATE started_at

### 建议：**skip-to-score 走完整 DB 生命周期**

- REST `skip` 端点：
  1. 生成 `task_id = generate_task_id()`（用 models.task 的 helper）
  2. `INSERT tasks(task_id, status='PENDING', task_type='MATCH_SCORE', user_message=f"skip-to-score jd={jd_id}", context={jd_id, candidate_ids}, plan=<generated>)`
  3. `UPDATE tasks SET status='EXECUTING', started_at=NOW() WHERE task_id=?`
  4. 调 `engine.run_skip_to_score(jd_id, candidate_ids, task_id=<uuid_id>, event_buffer=...)`（**需给 run_skip_to_score 加 task_id 参数**，别再假拼）
  5. 返 `{task_id, status:'EXECUTING'}`

**待裁定**：方案采纳？还是 skip-to-score 保持"轻量、不 INSERT"（放弃状态查询能力）？

---

## Q8 · SSE `stream` 对不存在 / 已过 TTL 的 `task_id` 处理

### 三个场景

- **场景 1**：`task_id` 不在 `tasks` 表 → 404（api-contract §4.4 隐含）
- **场景 2**：`task_id` 在 tasks 表且进行中 → 正常 stream
- **场景 3**：`task_id` 在 tasks 表且已终态但**过了 TTL 3600s**（EventBuffer 空） → ?
  - 3a. 立刻 200 + 发 `SYSTEM("task terminated, buffer expired")` 单帧后关闭
  - 3b. 200 + 从 tasks 表读 `result`/`error` 字段合成一条 `result`/`error` 事件后关闭
  - 3c. 404（把过期视同不存在）

### 我的建议

- 场景 1：**404**（`tasks` 表查不到）
- 场景 2：正常
- 场景 3：**3b**（从 `tasks.result` / `tasks.error` 合成事件返回）—— 这样 `GET /tasks/{id}` 与 stream 端点行为一致；前端补拉能拿到终态

**待裁定**：3 号场景选 3b？

---

## Q9 · 测试策略与 SSE 断线重连的 pytest 实现

### 已知 TC-S5-09-1..6

- `TC-S5-09-1` route order（stream 先于 tasks）—— 静态断言路由列表
- `TC-S5-09-2` status codes：chat 422 / tasks 404 / cancel 409 —— 直接调用
- `TC-S5-09-3` Last-Event-ID 重放 —— **需断线重连**
- `TC-S5-09-4` 15s 心跳 —— **时间敏感**
- `TC-S5-09-5` content-type + `retry:3000` —— 断言首帧头部
- `TC-S5-09-6` engine 未捕获异常 → 500 —— mock engine raise

### 三个技术挑战

**(1) SSE 断线重连测试**：httpx AsyncClient 支持 `client.stream()` 拿 async iterator，但要模拟"断开后带 Last-Event-ID 重连"——两个 `.stream()` 调用之间设 header。有先例吗？

- **建议**：先 append 10 条事件到 fakeredis buffer，然后 `client.stream("GET", "/stream", headers={"Last-Event-ID": "5"})`，断言只收到 id > 5 的事件。**不需要真断线**，因为 Last-Event-ID 只是首连 header，一次 stream 建连就能测。

**(2) 心跳测试**：默认 15s 太长，用 `heartbeat_interval_sec` 配置 → 测试 fixture 传 0.1s，等 0.35s 后 assert 收到至少 3 条 heartbeat。

- **建议**：Settings 加 `sse_heartbeat_interval_sec: float = 15.0`；端点从 Depends(Settings) 读或从 fixture override；测试用 `dependency_overrides` 传 0.1。

**(3) engine raise 500**：`app.dependency_overrides[get_engine] = lambda: raising_engine` 注入。

### 我的建议

三个都可解，但**建议在 QUESTIONS 阶段就把 `heartbeat_interval_sec` 定为可配置**，避免执行体反复来问。

**待裁定**：
- 心跳间隔通过 `Settings.sse_heartbeat_interval_sec` 暴露？（是/否）
- 测试用 `httpx.AsyncClient.stream()` 消费 SSE 帧？（是/否，或者用 `httpx-sse` / `sse-starlette`）
- 是否新增 `sse-starlette` 依赖？（推荐：**不加**，用 FastAPI 原生 `StreamingResponse` + 手写格式化——省一个依赖，代码总共 30 行）

---

## §十二 · 顺手清扫候选（可选，非强制）

PR-14 建议**不做**顺手清扫（PR-13 已经清扫了 datetime；PR-14 集中在端点/SSE，作用面正交）。以下列出**可能踩到**的边角，若发现就顺手：

- `run_skip_to_score` 的 `task_id = f"task_skip_{jd_id}"` 假前缀 → **本 PR 主线必修**（Q7）
- `run_chat` 的 `emit=None` 未使用参数 → **本 PR 主线补齐**（Q5）
- `run_execute` 内注释"PR-14 会从 tasks 表读入真实 plan"（engine.py:273）→ **本 PR 主线兑现**

以上都不算"顺手清扫"，都是 PR-14 本身范围内的必做项。

**建议**：不列 §十二 顺手清扫，避免像 PR-13 那样触发 §十三#8 类边界。

**待裁定**：是否同意 PR-14 无顺手清扫？

---

## §十三 · 求助边界（预估）

PR-14 执行时可能触发的求助点，先列出让指挥官心中有数：

1. **httpx.AsyncClient.stream() SSE 消费**：若发现 stream 帧解析在测试中不稳定（buffering 边界、`\n\n` 分隔），停下汇报，考虑加 `httpx-sse` 或改用 `TestClient`（同步）
2. **`asyncio.create_task` + DB session 生命周期**：`_background_execute` 里如果用 `db_updater` 引用了闭包 session，闭包外 session 已 close 会 raise。若发现，停下讨论 session 归属
3. **`sqlalchemy.update` 的 `rowcount` 在 async 下不可用**（部分驱动不返 rowcount）：若发现，停下改用 `RETURNING` 或 `SELECT ... FOR UPDATE`
4. **`StreamingResponse` 在客户端断线时的清理**：如果 `_background_execute` 因客户端断线不 decr `active_counter` 导致泄漏（已有 finally 兜底，但依旧检查一下）
5. **Redis List `LRANGE 0 -1` 每次读全表**：200 条上限下 OK，若发现某些测试 append > 200 后依赖旧事件重放失败（属于 §3.5 "早期事件滚动"预期行为），停下汇报
6. **FastAPI 路由匹配意外**：若 `/tasks/{task_id}/stream` 与 `/tasks/{task_id}` 顺序对了但依然被 `{task_id}` 吞（因为 `{task_id}` path type），停下汇报（Stage 4 已有先例）
7. **测试基线倒退**：任何 pytest 数量 < 101 即为回归，停下汇报
8. **既有 datetime 相关（PR-13 决策 B 后遗留）**：若发现 datetime aware/naive 混比新出现（比如 `TaskStatus.created_at` 字段序列化），走 `_to_naive_utc()` 归一，无新决策
9. **`fakeredis` 与真 Redis 的 pipeline / expire 行为差异**：TC-S5-09-4/5 在 fakeredis 上跑绿不代表真 Redis 也绿（HANDOFF §9.3 第 4 条已列 Stage 6 兜底），本 PR 不追究

**待裁定**：以上 9 条边界是否同意？还有别的须提前 flagged 的边角？

---

## §附 · 建议 commit 拆分（供参考，执行体可自选）

**5 commit 版**（推荐）：
1. `feat(stage5): S5-09 agent endpoints skeleton + route registration`（agent.py 骨架 + api/v1/__init__ 注册，测试 TC-S5-09-1 绿）
2. `feat(stage5): chat / execute / skip / cancel endpoints + DB persistence (Q1 采纳方案 B / Q6 采纳方案 A)`（Engine 加 db_updater 参数，端点接线，TC-S5-09-2/6 绿）
3. `feat(stage5): SSE stream endpoint with Last-Event-ID replay + heartbeat + terminal detection (Q2/Q3/Q4)`（TC-S5-09-3/4/5 绿）
4. `refactor(stage5): run_chat emit thinking/plan events + run_skip_to_score task_id contract (Q5/Q7)`
5. `test(stage5): fixtures for httpx SSE + heartbeat_interval override + TC-S5-09-*`

**7 commit 版**（更细）：把 2 拆成 chat / execute 各一，把 3 拆成 stream / heartbeat 各一。

**待裁定**：执行体自选还是指定？

---

## 汇总：9 问 + 1 备注

| # | 主题 | 建议 |
|---|---|---|
| Q1 | Task DB 持久化边界 | 方案 B（Engine `db_updater` 回调） |
| Q2 | SSE 实时推送方式 | 方案 A（100ms 轮询 EventBuffer） |
| Q3 | SSE 优雅关闭 | 方案 A + cancel 端点补 SYSTEM("cancelled") 事件 |
| Q4 | 15s 心跳实现 | 方案 B（单循环 wall-clock 判定）+ `heartbeat_interval_sec` 配置 |
| Q5 | chat emit thinking/plan | 方案 A（补齐，契约要求） |
| Q6 | cancel/execute 竞态 | 方案 A（原子 UPDATE + rowcount 检查） |
| Q7 | skip-to-score DB 生命周期 | 走完整 DB（含 INSERT + task_id 契约） |
| Q8 | stream 不存在/过期 task | 404 / 3b（从 tasks 表合成事件） |
| Q9 | 测试策略 | `heartbeat_interval_sec` 可配 + httpx.stream() 消费 + 无 sse-starlette 依赖 |
| 附 | commit 拆分 | 5 commit 或 7 commit 由执行体自选 |
| 附 | §十二 顺手清扫 | 无 |
| 附 | §十三 求助边界 | 上列 9 条 |

**请指挥官逐项裁定，或"全部采纳"**。裁定后我出 `PR14-KICKOFF-DECISION.md`，执行体照做。
