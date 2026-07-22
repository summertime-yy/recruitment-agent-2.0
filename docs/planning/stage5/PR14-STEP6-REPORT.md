# PR-14 · Agent REST 端点 + SSE HTTP 流 · STEP6 报告

> 关联：`docs/planning/stage5/PR14-KICKOFF-DECISION.md`（裁定即合同）· `docs/planning/stage5/PR14-KICKOFF-QUESTIONS.md`
> 分支：`feat/pr-14-s5-09-agent-endpoints`
> 完成时间：2026-07-22
> 状态：**三道门全绿**，待指挥官 FF-merge 评审

---

## 一、概要

PR-14 = **S5-09（Agent REST 端点 + SSE HTTP 流）**，落地 DECISION 的全部裁定：

- **主 A（Q5）**：`chat` 端点**异步化**（(b1) 异步 + 非流式 thinking）—— 立即返 `{task_id, PLANNING}`，后台 `_background_reason_plan` 通过 EventBuffer 发 THINKING（一次性）+ PLAN（实时）事件。
- **主 B（executions）**：`executions` 表全生命周期落库**延后 Stage 5.1**（见 §五 19.1）。
- **Q1**：Engine `db_updater` 回调（方案 B）+ 简化"中途不写 current_step"。
- **Q2/Q3/Q4/Q8**：SSE stream 端点 —— 100ms 轮询 EventBuffer + wall-clock 心跳 + 终态关流 + 404/3b 合成。
- **Q6**：cancel / execute-plan 走 SELECT FOR UPDATE + 显式状态检查。
- **Q7**：`run_skip_to_score` 加真 `task_id` 参数，移除假前缀。

---

## 二、完成清单

### REST 端点（`app/api/v1/agent.py`）

| 端点 | 行为 |
|---|---|
| `POST /agent/chat` | INSERT `tasks(PLANNING)` + `engine.start_chat(task_id, ...)` fire-and-forget → 返 `{task_id, PLANNING}`；429 → HTTP 429 `TASK_LIMIT_EXCEEDED` |
| `POST /agent/execute-plan` | SELECT FOR UPDATE 校验 `WAITING_CONFIRMATION` → 事务内捕获 `plan` → `engine.run_execute(...)`；404/409 |
| `POST /agent/skip-to-score` | `generate_task_id()` + INSERT `tasks(EXECUTING, MATCH_SCORE)` + 生成 plan → `engine.run_skip_to_score(..., task_id=...)` |
| `GET /agent/tasks/{task_id}` | SELECT → 序列化 `TaskStatus`；404 |
| `POST /agent/tasks/{task_id}/cancel` | SELECT FOR UPDATE 校验 `PLANNING/WAITING_CONFIRMATION` → UPDATE `CANCELLED` + `finished_at` → `commit` → 补发 `SYSTEM("cancelled")` + `set_terminal_ttl`；404/409 |
| `GET /agent/tasks/{task_id}/stream` | **路由声明先于 `/{task_id}`**；场景1 不存在→404，场景3 终态+缓冲空→3b 合成，场景2 正常 100ms 轮询流 |

### Engine 改造（`app/agent/orchestrator/engine.py`）

- `__init__` 增 `db_updater: DbUpdater | None = None`（`DbUpdater = Callable[[str, dict], Awaitable[None]]`）。
- `run_chat` → **重构为 `start_chat(task_id, user_message, context, db_updater)`**（task_id 由端点生成）+ 后台 `_background_reason_plan`（THINKING 一次性 + PLAN 实时 + reflect_plan 调整补发 + 终态写回）。
- `_background_execute` 补 db_updater 起始（EXECUTING/started_at）+ 结尾（COMPLETED/result 或 FAILED/TASK_TIMEOUT/INTERNAL_ERROR）。
- `run_skip_to_score` 加 `task_id` 参数，移除 `task_id = f"task_skip_{jd_id}"` 假前缀 + 移除 `check_transition(PENDING, EXECUTING)`。

### SSE 辅助 + 配置

- `_format_sse` / `_is_terminal` / `_event_stream`（含 `request.is_disconnected()` 断线检测）/ `_synthesize_from_task`。
- `Settings.sse_heartbeat_interval_sec = 15.0`（`app/core/config.py`，Q4 可配）。
- `tests/api/sse_helpers.py`：`parse_sse` 帧解析（httpx.stream 消费，不引入 `sse-starlette`）。

### 路由注册

- `app/api/v1/__init__.py` 注册 `agent_router`。

---

## 三、验收三道门（§十六，不可跳过）

### 门 1 · `cd backend && uv run pytest -q`

```
110 passed in 5.46s
```
基线 101 → **110**（+3 engine 单测 `test_stage5_s5_09_engine.py`，+6 端点测试 `test_agent_endpoints.py`）；无 failed / error。✅

### 门 2 · `cd backend && uv run ruff check app`

```
All checks passed!
```
0 error。✅

### 门 3 · `cd backend && uv run ruff format --check app`

```
51 files already formatted
```
0 diff。✅

---

## 四、影响面（文件清单）

```
 backend/app/agent/orchestrator/engine.py         | 209 +++++++++++---
 backend/app/api/v1/__init__.py                   |   2 +
 backend/app/api/v1/agent.py                      | 335 +++++++++++++++++++++++
 backend/app/core/config.py                       |   3 +
 backend/tests/api/__init__.py                    |   0
 backend/tests/api/sse_helpers.py                 |  42 +++
 backend/tests/api/test_agent_endpoints.py        | 191 +++++++++++++
 backend/tests/test_stage5_s5_08_state_machine.py |   2 +-
 backend/tests/test_stage5_s5_09_engine.py        |  89 ++++++
 9 files changed, 833 insertions(+), 40 deletions(-)
```

- **新增**：`app/api/v1/agent.py`、`tests/api/__init__.py`、`tests/api/sse_helpers.py`、`tests/api/test_agent_endpoints.py`、`tests/test_stage5_s5_09_engine.py`
- **修改**：`app/agent/orchestrator/engine.py`、`app/api/v1/__init__.py`、`app/core/config.py`、`tests/test_stage5_s5_08_state_machine.py`（`run_chat`→`start_chat` 适配 1 处）

---

## 五、偏差 / 决策记录（§十九 强制 6 条声明）

### 19.1 · executions 表全生命周期未落库 —— 延后 Stage 5.1

- **违契点**：`api-contract.md §4.5`（cancel 写 `executions.status='CANCELLED'`）、`PLAN-STAGE5.md §5.5`（Act 逐步 executions 记录）。
- **本 PR 暂行**：不写 `executions` 表；`models/execution.py` 已存在但闲置。cancel 端点仅 UPDATE `tasks`。
- **登记**：`HANDOFF §9.3 追债项第 7 条`（待合入时追加）。

### 19.2 · current_step 中途不写 DB

- **本 PR 暂行**：`tasks.current_step` 列保留，db_updater 只在 INSERT/终态触碰；`_background_execute` 中途不 UPDATE。前端进行中步骤只能从 SSE `tool_call`/`progress` 推导（降级路径可接受）。
- **登记**：`HANDOFF §9.3 追债项第 8 条`（待合入时追加，与 19.1 同 PR 补齐）。

### 19.3 · THINKING 事件非 token 流

- **本 PR 暂行**：Reason 完成后**一次性**发一条 `THINKING`（summary）；Reflect / Reflect-Plan 不 emit thinking。
- **登记**：`HANDOFF §9.3 追债项第 9 条`（待合入时追加，属 Stage 6+ 体验优化，不在 Stage 5.1 范围）。

### 19.4 · SSE 端点 100ms 轮询（不启 Redis Pub/Sub）

- **沿用**：PR-13 既有决策（`HANDOFF §9.3 追债项第 2 条`已登记），本 PR **无新增**，仅闭合列表。
- **后续**：Stage 5.1 多进程部署前启 Pub/Sub 时改造。

### 19.5 · `AgentChatResponse.initial_plan` 字段本 PR 不填

- **性质**：**非债务**，契约明晰化。`api-contract §4.1` 定义 `initial_plan?: Plan`（可选）；`chat` 返 `{task_id, PLANNING}`，前端完全靠 SSE `PLAN` 事件消费。
- **登记**：不入 §9.3，仅此处记录一次契约字段用法澄清。

### 19.6 · `run_chat` 契约破坏（PR-12 老测试改写）

- **改动测试数**：**1 个**（`test_stage5_s5_08_state_machine.py::test_tc_s5_08_3`，`run_chat(...)` → `start_chat("task_429", ...)`）。
- **远低于 §十三#10 阈值（6 个）**，未触发停下汇报；异步化影响面在预期内。

### 补充 · 执行过程中新增的暂行/工程决策（§十九 收官原则：不沉默留下）

1. **`start_chat` 由端点侧生成 task_id 并 INSERT `tasks` 行**（而非 Engine 内 `generate_task_id`）：避免"Engine 生成 id ↔ 端点 INSERT"竞态，保证 Engine 零 ORM 耦合。与 DECISION §四"INSERT 由 REST 端点侧做"一致。
2. **端点不显式 `async with db.begin()`**：conftest 的 `db_session` 已开事务（嵌套 begin 会 raise "transaction already begun"）。cancel 端点改为设值后显式 `await db.commit()`；execute/cancel 的 `with_for_update()` 直接跑在既有会话事务上。**生产环境 `get_db` 每请求独立会话，语义不变。**
3. **SSE 测试自然终止策略（§十三#4 相关）**：ASGITransport 下 `request.is_disconnected()` 在流进行中**不会**返回 True（httpx 的 receive 在流期间等待响应完成而非 disconnect），且客户端 break 不取消服务端协程。故所有 SSE 用例改为让流**自然终止**（终态 task 走 3b 合成；缓冲/心跳用例在缓冲尾部或后台延迟追加终态 RESULT 事件）。**生产代码 `_event_stream` 仍保留 `request.is_disconnected()` 检测**（真实 ASGI server 下有效），本项仅为测试消费方式的适配，非生产行为降级。
4. **本环境已 `alembic upgrade head`** 建 `tasks`/`executions` 表（`a5b6c7d8e9f0`），端点测试依赖。

---

## 六、工作区清理

- 临时输出文件位于 `C:/temp/`（`pytest_pr14.txt` / `ruff*.txt` / `gate*.txt` / `diffstat.txt`），**不在工作区内，无需 git 清理**。
- 工作区未产生临时脚本 / 中间文件（`backend/backend.err`、`backend/scripts/` 为本 PR 之前既存的未跟踪文件，**未纳入本 PR 提交**）。

---

## 七、提交链

```
8b08d9b test(stage5): TC-S5-09-1..6 green + engine.py format (gate3)
52f6dbc feat(stage5): S5-09 SSE stream endpoint + Last-Event-ID replay + heartbeat + Q8 synth (Q2/Q3/Q4/Q8)
2b62b39 feat(stage5): S5-09 agent REST endpoints (chat/execute/skip/cancel) + Q6 SELECT FOR UPDATE
d395983 feat(stage5): S5-09 engine async chat + db_updater callback (Q1/Q5/Q7)
a3da47d test(stage5): PR-14 red-test skeleton (TC-S5-09-1..6) + agent.py stub
```
（`730c3b7 docs(stage5): PR-14 kickoff questions + decision` 为起手前既有 docs commit，非本 PR 功能提交。）

---

## 八、合入后 docs 动作（§十七，指挥官 FF-merge 时统一操作）

- `HANDOFF.md` 头部：PR-14 已合入；§9.1 状态表 PR-14 = ✅，基线 101 → 110。
- `HANDOFF §9.3` 追加第 7/8/9 条（对应 §五 19.1/19.2/19.3）。
- `HANDOFF §9.5` 新文件表追加 `app/api/v1/agent.py`、`tests/api/test_agent_endpoints.py`、`tests/api/sse_helpers.py`。

---

**PR-14 三道门全绿，待指挥官 FF-merge 评审。**
