# PR-13 · SSE EventBuffer + Redis 接线 + Act→Redis 发射 · 启动前求助

> 关联：PR-13 = **S5-03（EventBuffer + 应用挂 Redis）+ S5-07 剩余部分（Act 发射到 Redis）** · 分支 `feat/pr-13-s5-03-07-sse-eventbuffer`（建议）
> 权威依据：`docs/planning/PLAN-STAGE5.md §Q5/Q6/Q7`、`docs/planning/TASKS-STAGE5.md §S5-03/§S5-07`、`docs/api-contract.md §3.5`、PR-12 STEP6 §附偏差 #2
> 状态：等待指挥官裁定，尚未开工

---

## 前置事实（已核验）

| 事实 | 出处 | 说明 |
|---|---|---|
| `redis>=5.0.0` 已在依赖 | `backend/pyproject.toml` | 但**未加** `redis[hiredis]`（生产）/ `fakeredis`（测试） |
| `app/core/redis.py` 全局单例 + `get_redis()` | 现有代码 | **无任何调用点**，在 import 时构造（非 lifespan） |
| `app/main.py` lifespan | 仅挂 MinIO + Skill DB 同步 | **未挂** `app.state.redis` |
| `run_execute` 占位 | `engine.py:175-186` | 仅状态守卫，注释写"实际执行由 PR-14 完成" —— 与 TASKS §S5-07 记载的"PR-13 发射到 Redis"分歧，以 PR-13 为准纠正 |
| `act.py` emit 签名 | `EmitFn = Callable[[SSEEvent], Awaitable[None]]` | SSEEvent 是 Pydantic BaseModel（不是 dataclass，docstring 有 drift） |
| `_make_event(id="evt", timestamp="")` | `act.py:42-50` | 明确注释"Engine 层应注入单调递增 id 和真实时间戳" —— PR-13 应补齐 |
| `act.py` emit 未 try/except | 第 85/95/97/108/112 行 | 与 docstring "每次 emit 用 try/except 包裹" **不符**，PR-13 顺手修 |
| `InMemoryActiveCounter` | PR-12 已实现 | 合并版 PLAN §Q7 要求 **Redis 原子计数器**，需 PR-13 决策是否迁移 |
| Redis Key & TTL | 合并版 PLAN §Q6 权威 | `sse:buf:{task_id}` List、`MAXLEN=200`、终态后 `3600s` TTL、**MVP 不启 Pub/Sub** |
| 心跳 | 合并版 PLAN §Q5 | `system` 事件、data=`{"message":"heartbeat"}`、每 **15s**、SSE `retry:3000ms` |

---

## Q1 · EventBuffer 依赖注入位置：全局单例 vs `app.state`

**已知**：
- 现有 `app/core/redis.py` 提供全局单例 `redis_client` + `get_redis()`，import 时构造，**未接入 lifespan**
- 合并版 TASKS §S5-03 明确要求："`app.main.py` lifespan 内 `app.state.redis = redis.asyncio.from_url(...)`，shutdown 时 `await app.state.redis.aclose()`"

**歧义**：
- **保留现有全局单例**（改动小，但 shutdown 时不会 aclose，可能泄漏连接；测试注入 fakeredis 需 monkeypatch 全局变量）
- **迁移到 `app.state.redis` + lifespan 管理**（更规范，测试通过 FastAPI `app.state` 注入 fakeredis；但要清理 `app/core/redis.py` 的死代码或改为读 `app.state`）
- **两者并存**：`app/core/redis.py` 提供 `get_redis(request: Request)` 从 `app.state.redis` 读

**建议**：**迁移到 `app.state.redis` + lifespan**，同时把 `app/core/redis.py` 改为**依赖注入函数**：
```python
def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis
```
删除全局 `redis_client` 单例。理由：
1. `app.state` 是 FastAPI 官方约定，符合 STAGE5 权威 PLAN §5 表述
2. shutdown 保证 `aclose()`，无连接泄漏
3. 测试可用 `app.state.redis = fakeredis.aioredis.FakeRedis()` 一行覆盖

**影响**：`app/main.py` lifespan +5 行；`app/core/redis.py` 改写；无生产端点调用点（现网无风险）

---

## Q2 · EventBuffer 类接口：合并 emit / append / replay 到一个类，还是分层

**已知**：commander 版 §S5-06 用 `EventBus`（`emit` / `replay` / `subscribe`）；合并版 TASKS §S5-03 用 `EventBuffer`（`append` / `read_after`）。

**歧义**：
- **API 命名**：`emit(task_id, event_type, data, step_id=None) -> int` vs `append(event: SSEEvent) -> int` vs 两个都有？
- **谁负责分配 seq_id**？EventBuffer 内部 `INCR` 生成、还是 caller 传入？
- **谁负责给 timestamp**？EventBuffer 打（保证单调）、还是 caller 打（可控但不单调）？
- **subscribe 是否需要**（Pub/Sub 通道）？合并版 §Q6 明确"MVP 不启 Pub/Sub"，但 SSE 端点仍需要"实时推送 + Redis 缓冲重放"—— **不启 Pub/Sub 时进程内怎么推**？

**建议**：
- **单类 `EventBuffer`**，两个核心方法：
  ```python
  class EventBuffer:
      async def append(self, task_id: str, event_type: SSEEventType,
                       data: Any, step_id: str | None = None) -> SSEEvent:
          """分配 seq_id + timestamp，序列化写 Redis List，LTRIM 保 200 条，返回完整 SSEEvent。"""
      async def read_after(self, task_id: str, last_event_id: int | None) -> list[SSEEvent]:
          """last_event_id=None 时全量重放；否则返回 id > last_event_id 的事件。"""
      async def set_terminal_ttl(self, task_id: str) -> None:
          """任务进入 COMPLETED/FAILED/CANCELLED 时调用，设 3600s TTL。"""
  ```
- **seq_id 由 EventBuffer 分配**：Redis `INCR seq:task:{task_id}` 保证单调
- **timestamp 由 EventBuffer 打**（ISO8601 UTC，`datetime.now(timezone.utc).isoformat()`）
- **不做 subscribe**：SSE 端点（PR-14）改为"死循环 + `read_after` 增量拉取 + `asyncio.sleep(0.1)` 轮询"实现进程内实时推。轮询延迟 100ms 对 SSE 体验可接受，YAGNI。

**影响**：`backend/app/agent/orchestrator/event_buffer.py` 新增 ~80 行；`act.py` 的 emit 签名与之对齐

---

## Q3 · Act → EventBuffer 接线：signature 变更 vs 适配器

**已知**：`act.py` 现有 `EmitFn = Callable[[SSEEvent], Awaitable[None]]`（PR-12 已经过绿测试）。

**歧义**：
- **改 `run_act` 签名**：`run_act(plan, ctx, event_buffer: EventBuffer, tool_router)` —— 干净但破坏 PR-12 已绿的 5 个用例
- **保留 `emit` 回调 + 适配器**：`emit = lambda ev: event_buffer.append(ev.task_id, ev.type, ev.data, ev.step_id)` —— 兼容但绕
- **改 EmitFn 类型**为 `Callable[[str, SSEEventType, Any, str | None], Awaitable[SSEEvent]]`：直接对齐 `append`，SSEEvent 由 buffer 构造

**建议**：**保留 `emit` 回调 + Engine 层做适配器**。理由：
1. PR-12 的 5 个 `TC-S5-07-*` 用例用 mock emit 已经绿；改 signature 会让红转绿的路径重新过一遍
2. `act.py` 是"纯模块，可测试"，不应耦合 EventBuffer 类型
3. Engine 在 `run_execute` / `run_skip_to_score` 内构造真实 emit：
   ```python
   async def _emit(ev: SSEEvent) -> None:
       try:
           await event_buffer.append(ev.task_id, ev.type, ev.data, ev.step_id)
       except Exception as e:  # noqa: BLE001
           logger.warning("SSE emit failed: %s", e)
   ```
4. 顺手在 `run_act` 里给 emit **加 try/except**（修 docstring 与代码不符的 drift）

**影响**：`act.py` 无 signature 变更；`engine.py` `run_execute` / `run_skip_to_score` 内新增 `_emit` 适配器（~10 行）

---

## Q4 · `run_execute` 从占位到真跑：范围到哪里为止

**已知**：
- PR-12 `run_execute` 仅状态守卫 + 占位返回（`engine.py:175-186`）
- 合并版 TASKS §S5-07 明确 PR-13 交付"Act 发射到 Redis"
- api-contract §4.2 `POST /agent/execute-plan` 响应 `{ task_id, status: 'EXECUTING' }` —— 端点应"立即返回 EXECUTING，Act 后台执行 + SSE 推事件"

**歧义**：
- **Act 是同步跑完再返回**（阻塞 HTTP，语义错），还是**用 `asyncio.create_task` 后台跑**（对齐 SSE 语义）？
- 后台任务失败时怎么处理？异常怎么发到 SSE？
- `run_execute` 是否需要接入**数据库**读取 `tasks` 表的 `plan` 字段？还是从 `accepted_steps` 参数重构？
- **Reflect-Act 阶段是否在本 PR 接入**？（合并版 TASKS §S5-07 "Reflect-Act internal Skill" 已在 PR-12 落地，engine 里 `run_reflect_act` **未实现**）

**建议**：
- **`run_execute` 用 `asyncio.create_task` 后台跑 Act + Reflect-Act，立即返回 EXECUTING**
- **后台任务**内部：
  ```python
  async def _background_execute(task_id: str, plan: dict, ...):
      try:
          results = await run_act(plan, ctx={"task_id": task_id}, emit=_emit, tool_router=...)
          reflect_result = await self.run_reflect_act({"step_results": results})
          await event_buffer.append(task_id, RESULT, {"content": ..., "artifacts": [...]})
          await event_buffer.set_terminal_ttl(task_id)
          # UPDATE tasks SET status='COMPLETED' ...
      except Exception as e:
          await event_buffer.append(task_id, ERROR, {"code": "...", "message": str(e), "recoverable": False})
          await event_buffer.set_terminal_ttl(task_id)
          # UPDATE tasks SET status='FAILED' ...
  ```
- **数据库交互**：本 PR **只**从参数 `plan` / `accepted_steps` 读，不接 tasks 表 UPDATE（留 PR-14 REST 层处理，PR-13 只测试 in-memory task state）
- **`run_reflect_act`** 本 PR 补齐：调 `orchestrator-reflect-act` Skill，输出接到 result 事件的 `content` 字段

**影响**：`engine.py` `run_execute` 从 12 行 → ~60 行；新增 `run_reflect_act`；`run_skip_to_score` 同样接入后台任务

---

## Q5 · ActiveCounter：本 PR 迁 Redis 还是保持内存

**已知**：
- PR-12 已实现 `InMemoryActiveCounter`（`active_counter.py`），基于 `asyncio.Lock`
- 合并版 PLAN §Q7 明确要求 Redis 原子计数器 `task:active`（`INCR`/`DECR`，TTL 兜底）
- 目前无进程副本部署需求（单实例）

**歧义**：
- **本 PR 迁移**：新增 `RedisActiveCounter` 实现 `ActiveCounter` Protocol，PR-13 内切换
- **推迟到 PR-14**：REST 端点接入前保持内存版；PR-13 只做 EventBuffer
- **推迟到 Stage 5.1**：单实例部署内存版够用；跨进程扩展再做

**建议**：**本 PR 迁移到 Redis 版**。理由：
1. Redis 客户端本 PR 已接入 `app.state`，`RedisActiveCounter` 增量 ~30 行
2. TTL 兜底防泄漏是合并版明确要求，避免异常路径（进程 crash 未 decr）计数器泄漏
3. 迁移后 `InMemoryActiveCounter` 保留（测试用，通过 DI 注入内存版）
4. 单实例部署不影响正确性；跨进程扩展时**零改动**

**Redis 键设计**：
- 计数键：`task:active` （单一 INCR/DECR，全局共享）
- 超限：`INCR` 后若 > 10，`DECR` 回滚并抛 `TaskLimitExceededError`
- TTL 兜底：每次 INCR 时 `EXPIRE task:active 3600`（1h 无活动自动清零，对齐 §Q7）

**影响**：`active_counter.py` 新增 `RedisActiveCounter` class；`engine.py` 默认从 `settings.active_counter_backend` 或依赖注入选实现

---

## Q6 · Result 事件 `artifacts` payload 结构（PR-12 §十二第 4 条预警的延续）

**已知**：
- api-contract §3.3 `result` 事件 `data: { content: string; artifacts?: any[] }` —— **artifacts 具体是啥没写死**
- PR-12 `act.py:101` 现有实现：`"artifacts": [r.output for r in results if r.output]` —— 只是把所有步骤 output 堆一起
- PR-14 拼装真 result 时会撞（这次是 PR-13，仍会撞，因为 Act 后台跑要发 result 事件）

**歧义**：
- artifacts 每项的 schema？（`{step_id, tool_name, output}`？还是 `{type: "match_score" | "candidate" | "jd", ref_id, ...}`？）
- 是否要在 result 事件的 `content` 里放一段 Reflect-Act 生成的自然语言总结？
- artifacts 中的引用型对象（如 `match_score_id`）如何被前端解引用？（`GET /match-scores/{id}` 已存在）

**建议**：**本 PR 只做最小契约固化，写回 api-contract §3.3**：
```typescript
interface ResultArtifact {
  step_id: string;            // 对应 PlanStep.step_id
  tool_name: string;
  type: "match_score" | "resume" | "jd" | "candidate_merge" | "generic";
  ref_id?: string;            // type != 'generic' 时提供，前端可解引用
  data?: any;                 // type='generic' 时的原始 output
}
interface ResultData {
  content: string;            // Reflect-Act 生成的自然语言总结
  artifacts: ResultArtifact[];
}
```
- `content` = Reflect-Act 输出的 `final_result` 字段（api-contract §5.6 已定义）
- `type` 从 `tool_name` 推导（内置映射表，如 `create_match_score` → `"match_score"`）
- **不影响 PR-13 用例判定**：现有 `TC-S5-07-3` 断言 `artifacts` 非空即可，schema 细节写回 api-contract

**影响**：改 `docs/api-contract.md §3.3` 一段；`act.py` `_make_event(RESULT, ...)` 结构调整；本 PR 加一条 `TC-S5-07-6-artifacts-schema` 断言

---

## Q7 · 心跳任务寿命与失败处理

**已知**：合并版 PLAN §Q5 明确"每 15s 一条 `system` 心跳"。

**歧义**：
- 心跳 task 何时启动、何时终止？（Task 进入 EXECUTING 时启、进入终态时停？还是 SSE 连接建立时启、断开时停？）
- 心跳发到 EventBuffer（每 15s 一条 append）还是仅在 SSE 端点直接发帧、不入缓冲？
- 心跳发送本身失败（Redis 断线）时怎么办？

**建议**：**心跳只在 SSE 端点层发帧，不入 EventBuffer**。理由：
1. 心跳事件不需要重放（Last-Event-ID 补齐时若中间隔了 100 条心跳，全部重发是浪费）
2. SSE 端点是每连接独立的 `StreamingResponse`，用 `asyncio.wait_for(read_after, timeout=15)` + 超时后发心跳帧的方式即可
3. Redis 断线时心跳仍能发（心跳不依赖 Redis）

**但 PR-13 属于 EventBuffer 层，SSE 端点在 PR-14**。所以本 PR 只需**明确心跳职责边界**（"心跳不进 EventBuffer"），在 kickoff 里写死即可。

**影响**：本 PR 无代码；PR-14 kickoff 引用本裁定

---

## Q8 · 测试策略：fakeredis 还是真 Redis

**已知**：
- 合并版 PLAN §5 明确"单测用 `fakeredis` 替代真实 Redis，CI 无需起 Redis 容器"
- 现有 test suite 全部 stub / mock，未接入任何真实 Redis

**歧义**：
- fakeredis 装哪个版本？（`fakeredis[lua]` 支持更多 op，纯 `fakeredis` 已够）
- 每个测试 function 一个 fresh fakeredis instance？还是 module scope 共享？
- **既有测试如何隔离**（run_task_with_overall_timeout 等已绿的 PR-12 测试若引入 fakeredis 会破坏隔离）？

**建议**：
- 依赖：`fakeredis>=2.20.0`（纯 Python，最新版）
- fixture 设计：
  ```python
  @pytest.fixture
  async def fake_redis():
      import fakeredis.aioredis as fakeasync
      client = fakeasync.FakeRedis(decode_responses=True)
      yield client
      await client.aclose()
  @pytest.fixture
  async def event_buffer(fake_redis):
      return EventBuffer(fake_redis)
  ```
- 每个测试 function 独立 fakeredis instance（避免测试间污染）
- PR-12 已绿的用例**不动**，PR-13 新增 `test_stage5_s5_03_event_buffer.py` + 扩展 `test_stage5_s5_07_act.py` 用真 EventBuffer 断言 Redis 内容

**影响**：`pyproject.toml` 加 `fakeredis>=2.20.0` 到 dev；`conftest.py` +2 fixture；新增 1 个测试文件

---

## Q9 · Commit 拆分建议

按 PR-12 6-commit 精简版风格：

```
1. b8cf1f3 red skeleton  ← 红骨架 + 求助文档（本文件）
2. C_DEPS  chore(stage5): +fakeredis + redis[hiredis]
3. C_LIFESPAN feat(stage5): S5-03 lifespan 挂 app.state.redis + get_redis DI 重构
4. C_BUFFER feat(stage5): S5-03 EventBuffer (append / read_after / set_terminal_ttl) + tests
5. C_COUNTER feat(stage5): S5-08 RedisActiveCounter (INCR/DECR + TTL 兜底) + tests
6. C_ACT_INTEGRATE feat(stage5): S5-07 wire EventBuffer into Act via engine._emit adapter
7. C_EXECUTE feat(stage5): S5-07 run_execute 后台任务 + run_reflect_act + result artifacts schema
8. C_DOCS docs: api-contract §3.3 固化 result artifact schema
```

若过细可合到 **5 commit**：
```
1. red skeleton
2. infra: fakeredis + lifespan + EventBuffer + RedisActiveCounter
3. integrate: act↔EventBuffer via engine adapter
4. execute: run_execute + run_reflect_act 真跑 + result artifacts
5. docs: api-contract §3.3 + kickoff/step6 报告
```

**执行体自选**。

---

## 十、验收三道门（PR-13）

| 门 | 命令 | 期望 |
|---|---|---|
| 门 1 | `cd backend && uv run pytest tests/test_stage5_s5_03_event_buffer.py tests/test_stage5_s5_07_act.py -q` | 全绿（S5-03 5 用例 + S5-07 扩展） |
| 门 2 | `cd backend && uv run pytest -q` | 全绿（92 + 新增用例，无回归） |
| 门 3 | `cd backend && uv run ruff check app/agent/orchestrator/ app/core/redis.py app/main.py` | 0 error |

---

## 十一、求助边界（触发即停）

除本 KICKOFF 覆盖的 9 问，遇以下情况**立即停下汇报**：

1. **fakeredis 与真 Redis Pub/Sub 行为差异**导致测试通过但生产失败 —— 提前发现即停
2. **`asyncio.create_task` 后台任务在 pytest 中泄漏**（event loop 关闭后仍在执行）导致 CI hang
3. **PR-12 遗留的 emit 无 try/except、id="evt" 占位**在真 EventBuffer 下暴露新问题（如并发写入 seq_id 竞态）
4. **合并版 PLAN 与 api-contract 之间发现新的分歧**（如 result artifact 结构在 api-contract §3.3 与 §5.6 之间不一致）
5. **`app/core/redis.py` 全局单例被 PR-10/11/12 已有代码隐式引用**（虽当前 grep 只匹配自身，但可能被间接 import） —— 迁移前跑一次 `uv run pytest` 若报错立即停

**自主决策边界**（不必问）：
- EventBuffer 内部键命名（`seq:task:{id}` vs `sse:seq:{id}` 等）
- fakeredis fixture 具体命名
- ruff / import 排序
- log 语句措辞

---

## 十二、执行体行动清单

```
1. 阅读本 QUESTIONS + 后续 DECISION
2. 在 feat/pr-13-s5-03-07-sse-eventbuffer 分支上：
   a. 加 fakeredis / redis[hiredis] 依赖
   b. 重构 app/core/redis.py + app/main.py lifespan（Q1）
   c. 新建 backend/app/agent/orchestrator/event_buffer.py（Q2）
   d. RedisActiveCounter（Q5）
   e. engine.run_execute 真跑（Q4）+ run_reflect_act + adapter emit（Q3）
   f. api-contract §3.3 写回 artifact schema（Q6）
   g. 三道门验收（§十）
3. Push：sleep 15 && git push -u origin feat/pr-13-...
4. 生成 PR13-STEP6-REPORT.md
5. 汇报"已 push + STEP6 就位，待核验放行 FF merge"
```

**未开工前先等待 DECISION**。遇 §十一 5 种情况**立即停下**。
