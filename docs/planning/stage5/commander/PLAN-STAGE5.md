# Stage 5 规划书 · 指挥官版（PLAN-STAGE5）

> 版本：`commander-v1`（双盲评审隔离产物，未合并）
> 日期：2026-07-18
> 作者：Claude Code 总指挥官
> 约束来源：`docs/planning/COMMANDER-BRIEF.md` / `docs/api-contract.md` §3–§5 / `docs/data-model.md`
> 阶段范围：Stage 5「Agent 对话核心」—— Task Orchestrator + R-P-R-A-R + Tool Router + SSE + `candidate-merge` + `candidate-profile`

---

## 0. 目标与非目标

**目标**（Definition of Done）：
1. 用户在 `ChatCenter` 输入自然语言（如"给 JD-x 找前 10 名候选人并生成评分报告"），系统能自动 R-P-R-A-R 全流程完成。
2. Task 全过程以 SSE 事件实时推送，前端 8 类事件卡片正确渲染。
3. Tool Router 能调度已注册 Skill：`jd-candidate-matching`（Stage 4）+ 新增 `candidate-merge`、`candidate-profile`。
4. 断线重连不丢事件（`Last-Event-ID` 语义正确）。
5. 三道门（backend `pytest` / frontend `test`+`lint`+`build`）全绿，测试用例数不低于 TEST-PLAN 规定。

**非目标**（本 Stage 明确不做）：
- 认证/授权（`api-contract.md §1.1` 已声明开发阶段不接入 JWT）
- 多用户会话隔离（单用户假设）
- 消息持久化历史检索（Stage 6/7 再议）
- WebSocket 双向通道（本轮仅 SSE 单向）
- 移动端适配

---

## 1. 十二项架构决策（冻结）

### 决策 1 · R-P-R-A-R 状态机

沿用 `api-contract.md §5` 定义的 6 段：`Reason → Reflect → Plan → Reflect-Plan → Act → Reflect-Act`。**每段一个独立 Skill 或函数**，输入输出严格用 Pydantic Schema 校验。

**Task 生命周期状态**（写入 `tasks.status`）：
```
PENDING
  → PLANNING              (进入 Reason)
  → WAITING_CONFIRMATION  (Reflect-Plan 输出 Plan 后，等用户 execute-plan)
  → EXECUTING             (Act 逐步执行)
  → COMPLETED / FAILED / CANCELLED
```
> 与 `api-contract.md §4.4` 定义完全对齐。

**转移矩阵**（唯一合法转移，其他视为异常）：
- `PENDING → PLANNING`（Orchestrator 启动）
- `PLANNING → WAITING_CONFIRMATION`（Plan 生成成功且非 skip-to-score）
- `PLANNING → EXECUTING`（skip-to-score 直通）
- `WAITING_CONFIRMATION → EXECUTING`（用户 execute-plan）
- `WAITING_CONFIRMATION → CANCELLED`（用户显式取消）
- `EXECUTING → COMPLETED`（Reflect-Act 通过）
- 任意状态 `→ FAILED`（Skill 不可恢复错误 或 Task 总超时）

### 决策 2 · Execution 记录粒度

每个 R-P-R-A-R 阶段 + 每次 Skill 调用各产生 1 条 `executions` 记录。字段含 `phase`（`REASON|REFLECT|PLAN|REFLECT_PLAN|ACT|REFLECT_ACT`）、`skill_id`、`skill_version`、`input_json`、`output_json`、`status`、`duration_ms`、`error_message`。用于回放与审计。

### 决策 3 · Tool Router 路由策略

**双层路由**：
1. **意图层**（Reason 阶段输出）：LLM 分类到预定义 `task_type` 集合（初版 4 类：`MATCH_RANK` / `MATCH_ONE` / `MERGE_CANDIDATES` / `PROFILE_CANDIDATE`）；无法归类 → `needs_clarification=true`。
2. **工具层**（Plan 阶段落地）：每个 `PlanStep.tool_name` 直接映射到已注册 `skill_id`。Router 不做 LLM 二次决策，只做校验（skill 存在 + 版本存在 + 参数 schema 匹配）。

**注册表来源**：`SkillRegistry`（Stage 0 已实现），Stage 5 扩展 `list_by_task_type()` 查询接口。

### 决策 4 · SSE 事件信封

严格遵循 `api-contract.md §3.2`：
```typescript
interface SSEEvent<T> {
  type: 'thinking'|'plan'|'tool_call'|'progress'|'result'|'error'|'warning'|'system';
  task_id: string;
  step_id?: string;
  timestamp: string;  // ISO 8601 UTC
  data: T;
}
```

**新增（本 PLAN 补齐 api-contract 未明确点）**：
- SSE 帧头必须含 `id: <event_seq>`（服务端单调递增整数，用于断线重连）
- `retry: 3000`（客户端断线后 3 秒重连）
- 心跳：服务端每 15s 发一条 `event: system` `data: {"message":"heartbeat"}`

### 决策 5 · 断线重连策略 & Redis 缓冲层（指挥官已确认）

服务端维护每个 Task 的**事件环形缓冲区**（大小 200，Redis List `sse:task:<task_id>:events`，TTL 30min）。客户端断线重连时携带 `Last-Event-ID` 头，服务端从该 seq+1 开始回放，若已滚出缓冲区则发送 `event: warning data: {"message":"部分事件丢失，请刷新"}`。

**为什么用 Redis 而非内存**：单进程重启不丢事件；多 worker 部署（未来）可共享；且 Docker 已起 Redis，接入成本低。

**接入的 3 处影响**（执行时按下表落到指定 PR，不得延后）：

| 影响 | 落在 PR | 动作 |
|---|---|---|
| 后端依赖 | PR-10 | `uv add redis[hiredis]>=5.0` + `uv add --dev fakeredis>=2.20` |
| 应用启动 | PR-13 | `main.py` 生命周期挂 `app.state.redis`（`redis.asyncio.from_url`），`shutdown` 时 `aclose()` |
| 配置项 | PR-10 | `.env.example` 加 `REDIS_URL=redis://localhost:6379/0`；`core/config.py` 增字段 |

**测试策略**：
- 单测：依赖注入 `fakeredis.aioredis.FakeRedis`，业务代码无感知
- 集成测试：跑真 Redis（Docker 已就绪），验证 TTL / LTRIM / Pub-Sub 端到端行为

**未来收益（本 Stage 不做，登记备忘）**：Stage 4 `batch_match` 内存任务状态可后续迁到 Redis，进程重启不丢；Stage 6 推送队列亦可复用。

### 决策 6 · 并发上限

- Orchestrator 单 Task 内 Act 阶段并发度：`asyncio.Semaphore(2)`（保守，避免 LLM 高并发触发 Ark 限流；Stage 4 用 4，因单 Skill 简单，Stage 5 R-P-R-A-R 单步耗 token 更多）。
- 全局同时活跃 Task 数：软上限 10（超出返回 429，后续可用队列，Stage 5 不实现队列）。

### 决策 7 · 超时策略

- 单 Skill 超时：60s（`BaseSkill` 已支持，Stage 5 沿用）。
- 单阶段（Reason/Reflect/Plan/…）总超时：120s（含内部 Skill + 校验）。
- 整个 Task 超时：600s（10min）。超时 → `FAILED`，发 `error` 事件 `code=TASK_TIMEOUT`。

### 决策 8 · LLM 契约

严格延续 `docs/dev-standards-and-lessons.md` 与 Stage 4 冻结项：
- Skill 元数据 `max_retries: 0`；`LLMAdapter` 层 `max_retries=0`。
- **禁传** `reasoning_effort`（Ark DeepSeek-V4-flash 不支持）。
- 温度：Reason/Reflect/Reflect-Plan/Reflect-Act 用 `0.3`（求稳）；Plan 用 `0.5`（求多样）。

### 决策 9 · 失败降级

- 单 Skill 失败 → 记录 execution `FAILED` → 发 `warning` 事件 → **Task 不终止**，尝试下一步。
- 若某步是关键依赖（`PlanStep.dependencies` 上游），则依赖它的下游步全部跳过，最终 `Reflect-Act` 汇总部分失败结果。
- 只有以下场景 Task 直接 `FAILED`：Reason 无法产出合法输出、Plan 为空、Task 总超时、Orchestrator 未捕获异常。

### 决策 10 · 主键与命名

- `tasks.task_id`：`task_<uuid4_hex_12>`
- `executions.execution_id`：`exec_<uuid4_hex_12>`
- `executions.parent_task_id` FK → `tasks.task_id`，`ON DELETE CASCADE`
- 新增 Skill 目录：
  - `backend/app/agent/skills/candidate_merge/v1_0_0/`
  - `backend/app/agent/skills/candidate_profile/v1_0_0/`
- Orchestrator 阶段 Skill（若拆为 Skill，非纯函数）：
  - `backend/app/agent/skills/orchestrator_reason/v1_0_0/`
  - `backend/app/agent/skills/orchestrator_plan/v1_0_0/`
  - Reflect / Reflect-Plan / Reflect-Act 三段建议做成 Skill，便于 prompt 独立演进

### 决策 11 · FastAPI 路由顺序（关键）

Stage 4 教训延续：**具体路径必须先于参数化路径**。

`backend/app/api/v1/endpoints/agent.py` 内声明顺序强制：
```
POST /agent/chat
POST /agent/execute-plan
POST /agent/skip-to-score
GET  /agent/tasks/{task_id}/stream   ← 参数路径，但因带 /stream 后缀，与下面不冲突
GET  /agent/tasks/{task_id}
```

`ranking` / `matches` 等 Stage 4 路径不受本 Stage 影响。

### 决策 12 · 数据表 DDL（tasks / executions）

**新增迁移**：`<rev>_add_agent_tasks_and_executions.py`，`down_revision='e4c1a2b3d4f5'`（承接 Stage 4）。

**`tasks` 表**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| task_id | VARCHAR(50) | PK | `task_<uuid12>` |
| user_message | TEXT | NOT NULL | 用户原始输入 |
| context_json | JSONB | NULL | 关联 jd/candidates 快照 |
| status | VARCHAR(30) | NOT NULL, DEFAULT 'PENDING' | 见决策 1 |
| task_type | VARCHAR(50) | NULL | Reason 阶段输出 |
| plan_json | JSONB | NULL | Plan 结构（`api-contract §3.4`） |
| result_json | JSONB | NULL | 最终产物 |
| error_code | VARCHAR(50) | NULL | 失败码 |
| error_message | TEXT | NULL | 失败原因 |
| started_at | TIMESTAMP | NULL | 首次进入 EXECUTING 时间 |
| finished_at | TIMESTAMP | NULL | 到达终态时间 |
| created_at | TIMESTAMP | NOT NULL | |
| updated_at | TIMESTAMP | NOT NULL | |

索引：`idx_tasks_status_created (status, created_at DESC)`

**`executions` 表**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| execution_id | VARCHAR(50) | PK | `exec_<uuid12>` |
| task_id | VARCHAR(50) | FK→tasks.task_id, ON DELETE CASCADE, NOT NULL | |
| step_id | VARCHAR(50) | NULL | 对应 `PlanStep.step_id`（阶段类无 step_id） |
| phase | VARCHAR(30) | NOT NULL | REASON/REFLECT/PLAN/REFLECT_PLAN/ACT/REFLECT_ACT |
| skill_id | VARCHAR(100) | NULL | Skill 调用时填写 |
| skill_version | VARCHAR(20) | NULL | |
| input_json | JSONB | NULL | Skill/阶段输入 |
| output_json | JSONB | NULL | Skill/阶段输出 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'RUNNING' | RUNNING/COMPLETED/FAILED/SKIPPED |
| duration_ms | INTEGER | NULL | |
| error_message | TEXT | NULL | |
| created_at | TIMESTAMP | NOT NULL | |

索引：`idx_executions_task_created (task_id, created_at ASC)`

---

## 2. 组件切分

```
backend/app/
├─ agent/
│  ├─ orchestrator/
│  │  ├─ __init__.py
│  │  ├─ state_machine.py       # Task 状态转移（决策 1）
│  │  ├─ engine.py               # R-P-R-A-R 主循环
│  │  ├─ event_bus.py            # SSE 事件发射器（Redis Pub/Sub）
│  │  └─ tool_router.py          # 决策 3
│  ├─ skills/
│  │  ├─ candidate_merge/v1_0_0/
│  │  ├─ candidate_profile/v1_0_0/
│  │  └─ orchestrator_{reason,plan,reflect,reflect_plan,reflect_act}/v1_0_0/
├─ models/task.py                # tasks / executions ORM
├─ schemas/agent.py              # 请求/响应 Pydantic
├─ services/agent.py             # AgentService：REST 入口 + Orchestrator 编排
├─ api/v1/endpoints/agent.py     # 5 个 REST + 1 个 SSE
└─ core/sse.py                    # 通用 SSE 响应工具（信封序列化）

frontend/src/
├─ pages/
│  ├─ ChatCenter.tsx             # 对话中心（列表 + 详情 + 输入）
│  └─ CandidateChat.tsx          # 候选人详情内嵌
├─ components/agent/
│  ├─ ThinkingCard.tsx
│  ├─ PlanCard.tsx               # 带"执行/修改/跳过"按钮
│  ├─ ToolCallCard.tsx
│  ├─ ProgressCard.tsx
│  ├─ ResultCard.tsx
│  └─ ErrorCard.tsx
├─ hooks/useSSE.ts               # EventSource 封装（Last-Event-ID 支持）
└─ api/agent.ts                  # 前端 API 客户端
```

---

## 3. PR 拆分（10 个）

| PR | 范围 | 关键交付 | 前置 |
|---|---|---|---|
| PR-9 | 规划文档 | PLAN/TASKS/TEST-PLAN 三份最终版 + ACCEPTANCE-PR9 | 无 |
| PR-10 | S5-01/02 数据层 | 迁移 + Model + Schema + 单测 | PR-9 |
| PR-11 | S5-03/04 Tool Router + Skill 注册扩展 | `list_by_task_type` + 单测 | PR-10 |
| PR-12 | S5-05 Orchestrator 状态机 & Engine（同步版，无 SSE） | R-P-R-A-R 主循环单测 | PR-11 |
| PR-13 | S5-06/07 SSE 通道 + 事件总线 | Redis 环形缓冲 + `Last-Event-ID` 单测 | PR-12 |
| PR-14 | S5-08 REST API 四端点 | chat / execute-plan / skip-to-score / tasks/{id} | PR-13 |
| PR-15 | S5-09 `candidate-merge` Skill | Skill 三件套 + 单测 | PR-11 |
| PR-16 | S5-10 `candidate-profile` Skill | 同上 | PR-11 |
| PR-17 | S5-11 `ChatCenter.tsx` 前端 | 对话中心 + `useSSE` + 6 类事件卡片 | PR-14 |
| PR-18 | S5-12 `CandidateChat.tsx` 前端 | 候选人详情内嵌 | PR-17 |

PR-15/16 与 PR-13/14 可并行；单人执行按上表顺序。

---

## 4. 与既有契约的衔接

- **api-contract v1.1 §3–§5**：Stage 5 严格实现，本 PLAN 补齐三点（SSE `id` 序号、`retry` 值、心跳频率），需在 PR-9 冻结版一并写回 `api-contract.md`。
- **data-model.md**：新增 §3.7 `tasks` + §3.8 `executions`（PR-9 一并写入）。
- **Stage 4 匹配契约**：`orchestrator_plan` 生成 `PlanStep` 时，`tool_name='jd-candidate-matching'` 直接映射到 Stage 4 已有 Skill；参数即 `{jd_id, resume_id, force}`。

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| Ark DeepSeek 速率限制触发 | Task 长时间失败 | 决策 6 并发 2；`warning` 事件透传给用户 |
| SSE 长连接被反向代理断开 | 用户体验差 | 决策 4 心跳 15s；nginx `proxy_read_timeout 3600` 建议写入部署文档 |
| Plan 生成质量差 | Task 无用 | Reflect-Plan 阶段兜底；用户可在 `WAITING_CONFIRMATION` 编辑 |
| tasks 表膨胀 | 长期性能 | 索引 `(status, created_at DESC)` 支撑；Stage 7 加归档策略 |
| candidate-merge 误合并 | 数据污染 | Skill 输出 `confidence` + `evidence`，只有 confidence≥0.9 才自动合并，否则返回给用户确认 |

---

## 6. 三道门标准（延续 Stage 4）

| 门 | 命令 | 通过标准 |
|---|---|---|
| 后端测试 | `cd backend && uv run pytest` | 新增 ≥40 用例，全绿 |
| 前端测试 | `cd frontend && npm run test` | 新增 ≥12 用例，全绿 |
| 前端 lint | `npm run lint` | 0 error（warning 参照 Stage 4 政策不追新增） |
| 前端构建 | `npm run build` | exit 0 |

