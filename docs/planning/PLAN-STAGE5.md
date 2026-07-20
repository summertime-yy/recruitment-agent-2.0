# PLAN-STAGE5 · 合并版（最终冻结，PR-9 交付物）

> 阶段：Stage 5 — Agent 对话核心（Orchestrator + SSE）
> 来源：双盲评审执行体版（骨架）经 `docs/planning/stage5/REVIEW.md` 裁定合并
> 配套：`TASKS-STAGE5.md`（任务拆解与 PR 归属）、`TEST-PLAN-STAGE5.md`（用例矩阵）
> 强制边界：本文件与另两份为**规划文档**，PR-9 仅交付文档与契约写回，**不写业务代码**（编码落在 PR-10..PR-18）。

---

## 0. 范围与评审结论摘要

- 双盲评审见 `docs/planning/stage5/REVIEW.md`：12 问指挥官均已回答，10 处实质差异裁定为「采用指挥官 3 / 采用执行体 4 / 混合 3」。
- **阻塞纠正 D1**：执行体版误将全部任务归属 PR-9；合并版按指挥官方案映射到 PR-10..PR-18（见 `TASKS-STAGE5.md` 表头「归属 PR」列）。
- **关键修订 D4 v2**：Orchestrator 5 阶段改为「5 个 `internal: true` Skill + Act 纯模块 + `engine.py` 状态机」，收回执行体版「纯 Python 模块」决策，保持 Skill 框架解耦哲学。
- 本 PLAN 对 `api-contract.md §3–§5` 的引用为唯一事实源；§3 发现的遗漏（事件 `id` / `retry` / 重放 / 心跳 / `optional` / `CANCELLED` / 取消端点）已在 PR-9 一并写回 `api-contract.md`（见本文 §3 与对应文件）。

---

## 1. 总体架构与决策冻结

Stage 5 是在 Stage 1–4「直接调用路径」之上的**体验增强层**：用自然语言驱动已有的 JD / 简历 / 匹配能力，不改变既有 CRUD 语义。

```
Frontend (ChatCenter / CandidateChat)
   │  POST /agent/chat  ──►  Orchestrator（R-P-R-A-R 主循环）
   │  GET  /agent/tasks/{id}/stream (SSE)
   ▼
Orchestrator Engine (backend/app/agent/orchestrator/engine.py)
   ├─ Reason/Reflect/Plan/Reflect-Plan/Act/Reflect-Act
   │      ↑ 前 5 段 = 5 个 internal Skill（走 BaseSkill 管道）
   │      Act 段 = 纯 Python 模块（for-loop 调 ToolRouter.dispatch）
   ├─ Tool Router（仅从 list_dispatchable() 结果集路由，internal 抛 SkillNotDispatchableError）
   └─ Event Bus（SSE 事件 → Redis List 缓冲 → SSE 端点）
            │
            ▼
   SkillRegistry → 已注册 dispatchable Skill（jd-candidate-matching / candidate-merge / candidate-profile）
                   + 内置工具（search_resumes / read_jd）
            │
            ▼
   LLMAdapter.call_llm_json（max_retries=0，不传 reasoning_effort）
```

**关键决策冻结**：
- Orchestrator **Engine（`engine.py`）与 Act 主循环（`act.py`）是纯 Python 运行时模块**；但 Reason/Reflect/Plan/Reflect-Plan/Reflect-Act **五个控制流阶段是 `internal: true` Skill**，走统一 BaseSkill 管道（见 §2 Q10）。
- 实际被调用的“工具” = 已注册 dispatchable Skill + 少量内置工具；Tool Router 只从 `list_dispatchable()` 结果集校验分发。
- 所有 Skill（含 internal）元数据 `max_retries: 0`，与 `LLMAdapter` 层一致（§3.1）。

---

## 2. 回答 INSTRUCTION §四 的 12 个问题（合并裁定版）

### Q1 · R-P-R-A-R 各段 I/O 契约来源与 Task 生命周期编排

- **契约来源**：`api-contract.md §5`（Reason §5.1 / Reflect §5.2 / Plan §5.3 / Reflect-Plan §5.4 / Act §5.5 / Reflect-Act §5.6）是唯一事实源，逐字段对齐。
- **Task 生命周期编排**：

```
POST /agent/chat
  → 建 Task(status=PENDING) → Reason(§5.1) → Reflect(§5.2)
      ├─ needs_clarification=true  → status=WAITING_CONFIRMATION（发 clarification_questions，等用户补充消息后重跑 Reason）
      └─ is_feasible=false         → 发 error/warning，status=FAILED（或降级为 COMPLETED+warning）
  → Plan(§5.3) → Reflect-Plan(§5.4)
      ├─ is_plan_sound=false 且无可救 → 发 warning，回到 Plan 或 WAITING_CONFIRMATION
      └─ 计划就绪 → status=WAITING_CONFIRMATION（前端 PlanCard 带确认按钮）
POST /agent/execute-plan（accepted_steps / modifications）
  → status=EXECUTING → Act(§5.5) 逐 step 执行（发 tool_call/progress）→ Reflect-Act(§5.6)
  → 全部完成 → 发 result，status=COMPLETED
POST /agent/skip-to-score（jd_id + candidate_ids）
  → 跳过 Reason/Plan，直接建 Plan（单步 jd-candidate-matching），status=EXECUTING → Act → COMPLETED
```

> 所有阶段 LLM 调用均经 `LLMAdapter.call_llm_json`，其输出经 Skill 的 `validate_output` + `compliance_check`（§3.1 合规约束对所有阶段生效）。

### Q2 · Task 生命周期状态与转移矩阵（含 CANCELLED · D2 裁定）

- **状态集合**（对齐 `api-contract §4.4`，已补 `CANCELLED`）：`PENDING / PLANNING / WAITING_CONFIRMATION / EXECUTING / COMPLETED / FAILED / CANCELLED`。
- **合法转移矩阵**：

| 当前 \ 事件 | chat创建 | Reason完成 | 需澄清 | 计划就绪 | 用户确认 | 取消 | 执行完成 | 步骤失败/不可行 | 超时 |
|---|---|---|---|---|---|---|---|---|---|
| PENDING | — | PLANNING | — | — | — | — | — | FAILED | FAILED |
| PLANNING | — | — | WAITING_CONFIRMATION | WAITING_CONFIRMATION | — | **CANCELLED** | — | FAILED | FAILED |
| WAITING_CONFIRMATION | — | — | — | — | EXECUTING | **CANCELLED** | — | FAILED | FAILED |
| EXECUTING | — | — | — | — | — | — | COMPLETED | FAILED* | FAILED |
| COMPLETED | — | — | — | — | — | — | — | — | — |
| FAILED | — | — | — | — | — | — | — | — | — |
| CANCELLED | — | — | — | — | — | — | — | — | — |

> `*` 步骤失败但存在部分结果时，仍可转移至 `COMPLETED` 并携带 `result.artifacts`（见 Q9）。
- **CANCELLED 触发语义（D2）**：用户在 `WAITING_CONFIRMATION` 或 `PLANNING` 显式取消，前端 PlanCard「取消」按钮 → 经 `POST /api/v1/agent/tasks/{task_id}/cancel`（见 §4 §4.5）。取消**不**走 FAILED，避免 `error_code='USER_CANCELLED'` 污染失败语义。
- **非法转移处理**：任意非矩阵内转移 → 拒绝并保留原状态，同时通过 SSE 发 `error`（code=`ILLEGAL_TRANSITION`，recoverable=false）；REST `GET /agent/tasks/{id}` 仍返回当前状态，不抛 5xx。

### Q3 · Execution 记录粒度（采用执行体版 · D3 裁定）

- **采用「每次 Skill 调用记一条」**为唯一权威粒度：`executions` 每行 = 某次对某 Skill/工具的调用（含重试内的单次尝试不单列，只记最终那次，但 `execution_time_ms` 含重试耗时）。
- 同时记录 `phase`（REASON/REFLECT/PLAN/REFLECT_PLAN/ACT/REFLECT_ACT）与 `step_id`，使「每阶段一条」可通过 `phase` 维度聚合得到（无需双写）。
- 理由：最细且最有审计/复盘价值；阶段视图由 `phase` 过滤获得，避免冗余。

### Q4 · Tool Router 路由策略（D4 v2 强化）

- **Reason 阶段决定 `task_type`**：LLM 结构化输出 `task_type ∈ {MATCH_SCORE, MERGE_CANDIDATES, PROFILE_CANDIDATE, GENERATE_JD, GENERAL_QA, UNKNOWN}`，映射到一个「意图→候选工具集」。
- **Plan 阶段决定 `tool_name`**：每个 `PlanStep.tool_name` 由 LLM 给出，枚举自「已注册 dispatchable Skill + 内置工具白名单」。
- **是否二次 LLM**：**否**。路由决策是 Reason/Plan 主 LLM 调用的结构化输出字段，不单独再调一次 LLM（省成本/降延迟）。Tool Router 仅做**校验与分发**：
  1. **仅从 `SkillRegistry.list_dispatchable(task_type)` 结果集路由**（该集合已过滤 `internal=true` 的 Orchestrator 阶段 Skill，绝不对外暴露）；
  2. `tool_name` 命中 dispatchable Skill → `registry.get(tool_name).execute(params)`；
  3. 命中内置工具（如 `search_resumes` / `read_jd`）→ 调对应 service；
  4. 未命中 → 发 `error`（code=`UNKNOWN_TOOL`，recoverable=false），Task 转 `FAILED`；
  5. **若 `tool_name` 命中 `internal=true` 的 Skill（如 `orchestrator-reason`）→ 抛 `SkillNotDispatchableError`**（防止 LLM 生成的 Plan 意外引用 Orchestrator 内部阶段）。
- 内置工具白名单在 `ToolRouter` 内硬编码并附单测（见 TEST-PLAN `TC-S5-04-3`）。

### Q5 · SSE 事件信封对齐、断线重连、心跳

- **对齐 `api-contract §3.2`**：`{ id, type, task_id, step_id?, timestamp, data }`。`id` 为每任务内单调递增序号（如 `1,2,3…`），供 `Last-Event-ID` 重放（PR-9 已写回）。
- **断线重连（`Last-Event-ID`）**：客户端断开后以 `Last-Event-ID` 请求头重连；端点从 Redis 缓冲（`sse:buf:{task_id}`）重放 `id > Last-Event-ID` 的事件后继续实时推送。
- **心跳**：每 **15s** 发一条 `system` 类型心跳事件（`data={message:"heartbeat"}`）；SSE `retry:` 字段置 **3000ms**（浏览器默认重连间隔）。
- **事件类型**严格只用 `thinking/plan/tool_call/progress/result/error/warning/system`，禁用 `reason/reflect/reflect_act`（§3.3 约定）。

### Q6 · 事件缓冲（Redis，强制 · D5 裁定）

- **选型**：Redis（依 §3.3.1，指挥官已批准，不再权衡内存/Redis）。
- **结构**：每任务一个 Redis **List** `sse:buf:{task_id}`，元素为带 `id` 的序列化事件 JSON。
- **缓冲大小**：`MAXLEN=200`（环形裁剪，超出丢弃最旧）；若单任务事件超 200，重放仅覆盖最近 200，前端据此提示「早期事件已滚动」。
- **TTL**：任务进入终态（COMPLETED/FAILED/CANCELLED）后 **3600s（60min）**过期；进行中任务不过期（采用执行体版 60min，比指挥官 30min 更保守）。
- **Key 命名**：`sse:buf:{task_id}`（事件）、`sse:sub:{task_id}`（订阅计数，可选）。
- **Pub-Sub**：MVP **单实例**用「进程内 SSE 连接 + Redis 缓冲做重放」即可，**不启用** Redis Pub/Sub（采用执行体版，YAGNI）；多副本水平扩展时再启 Pub/Sub（记为 **Stage 5.1 开放项**）。

### Q7 · 并发上限（采用执行体版 · D6 裁定）

- **单 Task 内 Act 阶段 Skill 并发 = 1（顺序执行）**：`PlanStep.dependencies` 决定顺序；MVP 不做步骤级并行（避免依赖竞态、Ark 限流、提升事件序列清晰度）。
- **全局同时活跃 Task 上限 = 10**：用 Redis 原子计数器 `task:active`（`INCR`/`DECR`，TTL 兜底防泄漏）跨进程约束。
- **超限返回**：`POST /agent/chat` 返回 **429**，SSE `error` 事件 `code=TASK_LIMIT_EXCEEDED`，`recoverable=true`（客户端可稍后重试）。

### Q8 · 超时策略（采用执行体版 · D7 裁定）

| 层级 | 阈值 | 超时后行为 |
|---|---|---|
| 单 Skill 调用 | 120s | 该 step 标记失败；发 `error`（recoverable 视是否 optional） |
| 单阶段（Reason/Plan/…） | 180s | 阶段失败，按 Q9 决定 Task 走向 |
| 整个 Task | 600s（10min） | Task 强转 `FAILED`，发 `error`（code=`TASK_TIMEOUT`） |

- 单 Skill 阈值包住 `LLMAdapter` 的 `LLM_TIMEOUT`（settings 配置，通常 60–120s）；Orchestrator 在 `asyncio.wait_for` 外层再套一层。
- 超时 Task 若已有部分 `artifacts`，仍在 `result` 中带上（见 Q9）。

### Q9 · 失败降级（含 PlanStep.optional · D8 裁定）

- **可选步骤失败**（`PlanStep.optional=true` 或 Tool Router 标记）：发 `warning`，Task 继续，结果中标注该步跳过。
- **必需步骤失败**（默认）：该步发 `error`（recoverable=false），Task 转 `FAILED`；**但已产出的 `artifacts` 仍随 `result` 事件发出**（部分失败 ≠ 零产出）。
- **直接 FAILED（不可恢复）场景**：
  - Reflect `is_feasible=false` 且无澄清余地；
  - Tool Router 命中 `UNKNOWN_TOOL`；
  - 单 Skill 返回 `ExecutionStatus.FAILED` 且为必需步；
  - 整个 Task 超时（Q8）。
- **部分失败产出 result**：Act 阶段每完成一个 step 即把中间产物写入 `tasks.result.draft`，最终 `result` 事件取 draft（即便最后一步失败也发 `result` + `error`）。
- **`optional` 字段**：`PlanStep.optional?: boolean`，默认 `false`；Reflect-Plan 阶段可修正（LLM 输出建议）。已扩 `api-contract §3.4`（PR-9 写回）。

### Q10 · 主键命名与 Orchestrator 阶段实现形态（D4 v2 关键修订）

- **主键前缀**：`task_id = task_{uuid4().hex[:12]}`；`execution_id = exec_{uuid4().hex[:12]}`（对齐 §12 问约定的 `{prefix}_{uuid4_hex_12}`）。
- **Orchestrator 阶段实现形态（修订裁定）**：
  - **Reason / Reflect / Plan / Reflect-Plan / Reflect-Act 五段 = 5 个 `internal: true` Skill**，走完整 BaseSkill 管道（Prompt semver / 输入出 Schema 校验 / 统一日志 / compliance check / 未来 A/B 测试）。
  - **Act 段 = 纯 Python 模块** `backend/app/agent/orchestrator/act.py`：循环调用 `ToolRouter.dispatch()`，不注册为 Skill（Act 不是 LLM 调用）。
  - **`engine.py`**：状态机 + 编排，直接 `registry.get('orchestrator-reason').execute(input_data, session=db)` 调用各阶段 Skill。
  - 目录：
    ```
    backend/app/agent/skills/orchestrator_reason/v1_0_0/      # internal: true
    backend/app/agent/skills/orchestrator_reflect/v1_0_0/    # internal: true
    backend/app/agent/skills/orchestrator_plan/v1_0_0/       # internal: true
    backend/app/agent/skills/orchestrator_reflect_plan/v1_0_0/  # internal: true
    backend/app/agent/skills/orchestrator_reflect_act/v1_0_0/  # internal: true
    backend/app/agent/orchestrator/act.py                    # 纯模块
    backend/app/agent/orchestrator/engine.py                 # 状态机 + 编排
    ```
- **`skill.yaml` 新增字段** `internal: bool`（默认 `false`，向后兼容）：
  ```yaml
  skill_id: orchestrator-reason
  version: "1.0.0"
  internal: true
  task_types: []
  description: R-P-R-A-R 循环内部 Reason 阶段，不对外暴露
  ```
- **`SkillRegistry` 扩展方法**（见 `TASKS-STAGE5.md` S5-02）：
  - `get(skill_id)` — 全量查询，供 Orchestrator engine 内部调用；
  - `list_dispatchable(task_type: str | None = None)` — 过滤 `internal=true`，供 Tool Router；
  - `list_by_task_type()` 隐式使用 `list_dispatchable`。
- **新增 dispatchable Skill 目录**（可被 Tool Router 调用的“工具”）：
  - `backend/app/agent/skills/candidate_merge/v1_0_0/`（C1）
  - `backend/app/agent/skills/candidate_profile/v1_0_0/`（C2）
  - 每目录含 `skill.yaml + prompt.md (+ examples.yaml)`，`internal` 默认 `false`，由 `SkillRegistry` 自动加载（§3.5）。

### Q11 · FastAPI 路由声明顺序

- **声明顺序**：先 `GET /agent/tasks/{task_id}/stream`，后 `GET /agent/tasks/{task_id}`。
- **原因**：两者共享前缀 `/agent/tasks/{task_id}`。FastAPI 按**精确路径**匹配，`{task_id}` 默认不匹配含 `/` 的段，理论上 `/stream` 不会被 `{task_id}` 吞掉；但遵循 Stage 4 已验证的「具体路径先于参数化路径」教训（`INSTRUCTION §3.4`），显式把更“具体”的 `/stream` 写在前面，避免后续有人把 `{task_id}` 改为 path 类型时回退捕获 `/stream`。
- 同理：`POST /agent/execute-plan`、`POST /agent/skip-to-score`、`POST /agent/chat` 均为字面路径，无冲突，统一集中在 `agent.py` 路由文件中。

### Q12 · DDL 设计（tasks & executions · D9/D10 混合裁定）

> 遵循 `data-model.md §1`：VARCHAR(50) 业务主键、复数表名、TimestampMixin、FK 默认 RESTRICT；
> 新增迁移 `down_revision = e4c1a2b3d4f5`（Stage 4 head）；PK 前缀 `task_` / `exec_`。

**`tasks`**（D9 混合裁定：删 `request_id`/`created_by`，加 `started_at`/`finished_at`/`current_step`）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| task_id | VARCHAR(50) | PK | `task_{uuid4_hex_12}` |
| user_message | TEXT | NOT NULL | 用户首条消息 |
| task_type | VARCHAR(50) | NULL | MATCH_SCORE/MERGE_CANDIDATES/PROFILE_CANDIDATE/GENERATE_JD/GENERAL_QA/UNKNOWN |
| status | VARCHAR(20) | DEFAULT 'PENDING', NOT NULL | 状态机（Q2，含 CANCELLED） |
| plan | JSON | NULL | Plan 对象（§3.4） |
| context | JSON | NULL | `{ jd_id?, candidate_ids? }` |
| result | JSON | NULL | 最终/部分产物 `artifacts` |
| error | JSON | NULL | `{ code, message }`（单 JSON，前端一体化消费） |
| current_step | VARCHAR(50) | NULL | 进行中 step_id（前端「进行中」展示） |
| started_at | TIMESTAMP | NULL | 进入 EXECUTING 时刻（Q8 超时判定） |
| finished_at | TIMESTAMP | NULL | 进入终态时刻（Q8 超时判定） |
| created_at / updated_at | TIMESTAMP | NOT NULL | TimestampMixin |

索引（D10 复合索引裁定）：`idx_tasks_status_created (status, created_at DESC)`。

**`executions`**（D9/D10 混合：删 `validation_score`，`execution_status` 值域改为 `COMPLETED/FAILED/SKIPPED`，复合索引）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| execution_id | VARCHAR(50) | PK | `exec_{uuid4_hex_12}` |
| task_id | VARCHAR(50) | FK→tasks.task_id ON DELETE CASCADE, NOT NULL | 归属任务 |
| step_id | VARCHAR(50) | NULL | 对应 PlanStep.step_id |
| phase | VARCHAR(20) | NOT NULL | REASON/REFLECT/PLAN/REFLECT_PLAN/ACT/REFLECT_ACT |
| tool_name | VARCHAR(100) | NULL | 调用的工具/Skill 名 |
| skill_id | VARCHAR(100) | NULL | 命中 Skill 时填 |
| skill_version | VARCHAR(20) | NULL | |
| input_params | JSON | NULL | 入参快照 |
| output_result | JSON | NULL | 出参快照 |
| execution_status | VARCHAR(20) | NOT NULL | **COMPLETED/FAILED/SKIPPED**（对齐 Stage 4 `skill_execution_logs.status`，非 SUCCESS/…） |
| execution_time_ms | INTEGER | NULL | |
| error_message | TEXT | NULL | |
| started_at | TIMESTAMP | NULL | |
| finished_at | TIMESTAMP | NULL | |
| created_at / updated_at | TIMESTAMP | NOT NULL | TimestampMixin |

索引（D10 复合索引裁定）：`idx_executions_task_created (task_id, created_at ASC)`；保留 `idx_executions_step_id (step_id)` 为可选（若 step_id 高频查询）。

> `task_id` 显式 `ON DELETE CASCADE`（与 `match_scores` 一致，对 §1 RESTRICT 的有意偏离，任务删除连带清理执行日志）。

---

## 3. api-contract.md 契约写回清单（PR-9 交付物，按 REVIEW §4 七条）

评审通过的契约扩展点，已在 PR-9 同步写入 `docs/api-contract.md` 与 Skill 规范：

| # | 位置 | 扩展内容 | 来源 |
|---|---|---|---|
| 1 | `api-contract §3.2` SSE 信封 | 加 `id: string`（任务内单调递增） | 两版共识（已写回） |
| 2 | `api-contract §3.3` 事件类型表 | 补 `system` 事件兼作心跳说明 | 执行体版（已覆盖） |
| 3 | `api-contract §3.5` 新增小节 | SSE 重放与心跳细则：`Last-Event-ID` 语义、`retry:3000ms`、心跳 15s、缓冲滚动提示 | 执行体版（已写回） |
| 4 | `api-contract §3.4` PlanStep | 加 `optional?: boolean` | 执行体版 D8（**本次写回**） |
| 5 | `api-contract §4.4` TaskStatus | 加 `CANCELLED` 枚举 | 指挥官版 D2（**本次写回**） |
| 6 | `api-contract §4.5` 新增小节 | `POST /agent/tasks/{task_id}/cancel`（取消语义） | 指挥官版 D2（**本次写回**） |
| 7 | Skill 契约（HANDOFF §Skill 契约） | `skill.yaml` 加可选字段 `internal: bool`（默认 false）；`SkillRegistry` 新增 `list_dispatchable()` 与 `get()` | D4 v2 修订（**本次写回**） |

（执行体侧已在本文件 §2 各 Q 采用上述约定；最终以写回后的 `api-contract.md` 与 HANDOFF 为准。）

---

## 4. 复用的既有资产（§3.9）

- **`jd-candidate-matching` Skill（v1.0.0）**：Orchestrator 的 `MATCH_SCORE` 意图直接经 Tool Router 调用，入参构造复用 `MatchService.match_one` 的字段映射（`jd.*` + `resume.parsed_content`）。
- **`resumes` 字段复用**：
  - `candidate-merge` 复用 `duplicate_of_resume_id`（高置信度自动合并时写入指向）、`tags`；
  - `candidate-profile` 复用 `tags`（与用户手工标签合并去重）。
- **`MatchService` / `SkillRegistry.get().execute()` / `LLMAdapter.call_llm_json`**：作为 Stage 5 的底层调用原语，不重新造轮子。
- SSE 端点新增于 `backend/app/api/v1/endpoints/agent.py`（与现有 `jd.py/resume.py/match.py/candidate.py` 并列）。

---

## 5. Redis 引入决策（§3.3.1）

- Docker Redis 已就绪；Stage 5 内新增依赖 `redis[hiredis]`（生产）与 `fakeredis`（测试）到 `backend/pyproject.toml`。
- 客户端：`redis.asyncio` 单例（复用 `app/core/` 下的连接管理风格），应用启动时挂 `app.state.redis`，shutdown 释放。
- 仅用于 SSE 事件缓冲与全局活跃任务计数（§2 Q6/Q7）；**不**用于业务数据持久化（业务数据仍在 PostgreSQL）。
- 单测用 `fakeredis` 替代真实 Redis，CI 无需起 Redis 容器（或 stage 内起 redis 服务）。

---

## 6. 风险与开放问题

| 风险/开放项 | 说明 | 处置 |
|---|---|---|
| SSE 跨重启用重放 | 缓冲 200 上限可能截断长任务早期事件 | 前端提示「早期事件已滚动」；不在 PR-9 做无限缓冲 |
| 多副本 SSE | MVP 单实例，未启用 Pub/Sub | 记为 **Stage 5.1** 开放项 |
| LLM 计划质量 | Plan 可能含非法 tool_name/参数 | Tool Router 校验 + Reflect-Plan 兜底，失败转 FAILED |
| `datetime.utcnow()` 时区 | Stage 4 `services/match.py` 用朴素 UTC，建议改 `datetime.now(timezone.utc)` | 顺手清扫（落 PR-10，见 `TASKS-STAGE5.md §五`） |
| 全局并发计数泄漏 | 任务异常退出未 DECR | `task:active` 加 TTL 兜底 + finally DECR |
| Orchestrator 阶段 Skill 化 | 5 个 internal Skill 首次引入，需确认 BaseSkill 管道对 `internal` 透明 | `list_dispatchable` 过滤 + `get` 全量查（D4 v2） |
