# TASKS-STAGE5 · 合并版（最终冻结，PR-9 交付物）

> 配套：`PLAN-STAGE5.md`（架构与 12 问裁定）、`TEST-PLAN-STAGE5.md`（用例矩阵）
> 来源：执行体版 13 任务为骨架，经 `REVIEW.md` 裁定合并（D1 映射 PR-10..PR-18、D4 v2 改 internal Skill）
> 边界：本文件与另两份为**规划文档**，PR-9 仅交付文档与契约写回；编码落地在 **PR-10..PR-18**。
> 严格 TDD：每个任务先写测试（红）再实现（绿）。

---

## 任务总览（13 个 → PR-10..PR-18）

| ID | 标题 | owner | 依赖 | **归属 PR** |
|---|---|---|---|---|
| S5-01 | tasks / executions 数据层（迁移+Model+Schema 基础） | backend | — | **PR-10** |
| S5-02 | SkillRegistry 扩展（internal / list_dispatchable / get）+ SSE 事件 Schema | backend | S5-01 | **PR-10** |
| S5-03 | Redis 事件缓冲层 EventBuffer + 应用启动挂 Redis | backend | S5-01 | **PR-13** |
| S5-04 | Tool Router（意图→工具分发与校验，拒 internal） | backend | S5-01, S5-02 | **PR-11** |
| S5-05 | Orchestrator：Reason + Reflect（2 个 internal Skill） | backend | S5-02, S5-04 | **PR-12** |
| S5-06 | Orchestrator：Plan + Reflect-Plan（2 个 internal Skill） | backend | S5-02, S5-04 | **PR-12** |
| S5-07 | Orchestrator：Act（纯模块）+ Reflect-Act（internal Skill）+ SSE 发射 | backend | S5-03, S5-05, S5-06 | **PR-12 / PR-13** |
| S5-08 | Task 生命周期/状态机（含 CANCELLED）+ 并发/超时/失败降级 | backend | S5-05..S5-07 | **PR-12** |
| S5-09 | REST 四端点 + SSE 流端点 + 取消端点（路由顺序） | backend | S5-03, S5-08 | **PR-14** |
| S5-10 | candidate-merge Skill（C1） | backend | S5-01, S5-02 | **PR-15** |
| S5-11 | candidate-profile Skill（C2） | backend | S5-01, S5-02 | **PR-16** |
| S5-12 | 前端类型 + SSE 客户端 Hook | frontend | S5-02 | **PR-18** |
| S5-13 | 前端 ChatCenter + CandidateChat 页面 | frontend | S5-09, S5-12 | **PR-19** |

> 关键路径：`S5-01 → S5-02 → S5-04 → S5-05 → S5-06 → S5-07 → S5-08 → S5-09 → S5-12 → S5-13`；
> `S5-03` 并入 PR-13（与 S5-07 发射对齐）；`S5-10`/`S5-11` 可在 S5-05 后并行。
> 顺手清扫项见文末 §五（分配至对应 PR）。

---

## S5-01 · tasks / executions 数据层

- **owner**: backend ｜ **归属 PR**: PR-10 ｜ **依赖**: 无（承接 Stage 4 head `e4c1a2b3d4f5`）
- **目标**: 落地 `tasks`、`executions` 两表，提供 ORM Model 与 `TimestampMixin` 复用。
- **交付清单**:
  - `backend/alembic/versions/<rev>_add_agent_tasks_and_executions.py`（`down_revision="e4c1a2b3d4f5"`，`upgrade()` 建两表，`downgrade()` 删）
  - `backend/app/models/task.py`：`Task(Base, TimestampMixin)`，`__tablename__="tasks"`，字段见 PLAN §2 Q12（含 `started_at`/`finished_at`/`current_step`，**无** `request_id`/`created_by`；task_id 默认 `task_{uuid4().hex[:12]}`）
  - `backend/app/models/execution.py`：`Execution(Base, TimestampMixin)`，`__tablename__="executions"`，`execution_status` 值域 `COMPLETED/FAILED/SKIPPED`，**无** `validation_score`；execution_id 默认 `exec_{uuid4().hex[:12]}`
  - 复合索引：`idx_tasks_status_created (status, created_at DESC)`、`idx_executions_task_created (task_id, created_at ASC)`、`idx_executions_step_id (step_id)`（可选）
  - `backend/app/models/__init__.py`：导出 `Task`、`Execution`
  - `docs/data-model.md` 追加 §3.7 tasks / §3.8 executions（对齐 DDL）
- **验收判据**:
  1. `alembic upgrade head` 后 `tasks`/`executions` 表存在且字段/索引与 PLAN §2 Q12 一致。
  2. `Task.task_id` / `Execution.execution_id` 默认生成前缀正确（`task_`/`exec_`）。
  3. `Task.status` 默认 `PENDING`；删除 `Task` 级联删除其 `executions`（FK `ON DELETE CASCADE` 生效）。
  4. 复合索引在库中存在（`TC-S5-01-4`）。
- **测试用例**: `TC-S5-01-1`（迁移建表）、`TC-S5-01-2`（ID 前缀默认）、`TC-S5-01-3`（Cascade 删除）、`TC-S5-01-4`（复合索引存在）。

---

## S5-02 · SkillRegistry 扩展 + SSE 事件 / Agent 交互 Schema

- **owner**: backend ｜ **归属 PR**: PR-10 ｜ **依赖**: S5-01
- **目标**: 扩展 `SkillRegistry` 支持 `internal` 隔离；定义 SSE 事件与 Agent 四端点 Pydantic 模型，对齐 `api-contract §3/§4`。
- **交付清单**:
  - `backend/app/agent/registry.py` 扩展：
    - `get(skill_id: str)` — 全量查询（含 `internal=true`），供 Orchestrator engine 内部调用；
    - `list_dispatchable(task_type: str | None = None)` — 过滤 `internal=true` 的 Skill，供 Tool Router；
    - `list_by_task_type()` 隐式调用 `list_dispatchable`。
  - `skill.yaml` 新增可选字段 `internal: bool`（默认 `false`，向后兼容）；现有 `jd-candidate-matching` 等不需改动。
  - `backend/app/schemas/agent.py`：
    - `SSEEvent`（含 `id: str`、`type` 8 枚举、`task_id`、`step_id?`、`timestamp`、`data`）
    - `TaskStatus` 枚举（含 `CANCELLED`，对齐 `api-contract §4.4`）
    - `ExecutionPhase` 枚举（REASON/REFLECT/PLAN/REFLECT_PLAN/ACT/REFLECT_ACT）
    - `AgentChatRequest`（`message: str`、`context?: {jd_id?, candidate_ids?}`）
    - `AgentChatResponse`（`task_id`、`status`、`initial_plan?: Plan`）
    - `ExecutePlanRequest`（`task_id`、`accepted_steps?`、`modifications?: [{step_id, modified_params?}]`）
    - `SkipToScoreRequest`（`jd_id`、`candidate_ids: list[str]`）
    - `TaskStatusResponse`（`task_id`、`status`、`current_step?`、`plan?`、`result?`、`error?`、`created_at`、`updated_at`）
    - `PlanStep` / `Plan`（对齐 `api-contract §3.4`，`step_id: str`、`optional?: boolean`）
- **验收判据**:
  1. `SSEEvent` 序列化含 `id` 且 `type` 仅允许 8 种枚举（校验失败抛 422）。
  2. `list_dispatchable()` 不返回任何 `internal=true` 的 Skill；`get('orchestrator-reason')` 可取到（见 `TC-S5-02-4`）。
  3. `AgentChatRequest` 缺 `message` → 422；`PlanStep.optional` 缺省为 `false`。
- **测试用例**: `TC-S5-02-1`（SSEEvent id+type 枚举）、`TC-S5-02-2`（chat 缺 message 422）、`TC-S5-02-3`（Plan/PlanStep 往返含 optional）、`TC-S5-02-4`（internal Skill 被 `list_dispatchable` 排除但 `get` 可查）。

---

## S5-03 · Redis 事件缓冲层 EventBuffer + 应用启动挂 Redis

- **owner**: backend ｜ **归属 PR**: PR-13 ｜ **依赖**: S5-01
- **目标**: 实现 SSE 事件的 Redis 缓冲（add/trim/replay/ttl），并在应用启动时挂载 `app.state.redis`。
- **交付清单**:
  - `backend/app/core/redis.py`：`get_redis()` 异步单例（`redis.asyncio`）
  - `backend/app/main.py`：lifespan 内 `app.state.redis = redis.asyncio.from_url(settings.redis_url, decode_responses=True)`；shutdown `await app.state.redis.aclose()`
  - `backend/app/agent/orchestrator/event_buffer.py`：`EventBuffer`
    - `async def append(task_id, event: SSEEvent) -> int`（写 `sse:buf:{task_id}`，MAXLEN=200 裁剪，返回 `id` 序号，TTL 3600s）
    - `async def replay(task_id, after_id: int) -> list[SSEEvent]`（取 `id > after_id`）
    - `async def subscribe(task_id)` 生成器（实时 yield + 初连 replay）
  - `backend/pyproject.toml`：加 `redis[hiredis]`、`fakeredis`（dev）；`.env.example` 加 `REDIS_URL`
  - `backend/app/core/config.py`：加 `redis_url: str`
- **验收判据**:
  1. 连续 append 250 条，`replay(0)` 仅返回最近 200 条（裁剪生效）。
  2. `replay(task_id, after_id=10)` 只返回 `id>10` 的事件（Last-Event-ID 语义）。
  3. 终态任务 3600s 后缓冲 TTL 过期，`replay` 返回空。
  4. 心跳频率断言：15s 间隔发 `system` 心跳（见 `TC-S5-03-5`）。
- **测试用例**: `TC-S5-03-1`（裁剪到 200）、`TC-S5-03-2`（after_id 重放）、`TC-S5-03-3`（TTL 过期）、`TC-S5-03-4`（fakeredis 单测隔离）、`TC-S5-03-5`（心跳每 15s，freezegun/fakeredis time travel）。

---

## S5-04 · Tool Router

- **owner**: backend ｜ **归属 PR**: PR-11 ｜ **依赖**: S5-01, S5-02
- **目标**: 将 `task_type` / `tool_name` 映射到 dispatchable Skill 或内置工具，并校验分发；拒绝 `internal` Skill。
- **交付清单**:
  - `backend/app/agent/orchestrator/tool_router.py`：`ToolRouter`
    - `def route_task_type(reason_output) -> str`（映射 `api-contract §5.1` 的 `task_type` 到意图枚举）
    - `async def dispatch(step: PlanStep, ctx) -> SkillResult`：仅从 `registry.list_dispatchable()` 结果集解析；命中 Skill→`registry.get(tool_name).execute(params)`；命中内置→调 service；未命中→抛 `UnknownToolError`；命中 `internal=true`→抛 `SkillNotDispatchableError`
    - 内置工具白名单：`search_resumes`（→`Resume` 查询）、`read_jd`（→`JD` 查询）
    - 错误类：`UnknownToolError` / `SkillNotDispatchableError` / `ToolParamError`
- **验收判据**:
  1. `tool_name="jd-candidate-matching"` → 成功 dispatch 到该 Skill（经 `list_dispatchable`）。
  2. `tool_name="__not_registered__"` → 抛 `UnknownToolError`（映射 `error` 事件 `UNKNOWN_TOOL`）。
  3. `tool_name="search_resumes"` 且参数不匹配 schema → 抛 `ToolParamError`。
  4. `tool_name="orchestrator-reason"`（internal）→ 抛 `SkillNotDispatchableError`（见 `TC-S5-04-6`）。
  5. 路由不触发任何额外 LLM 调用（`mock call_llm_json` 计数 = 主调用数）。
- **测试用例**: `TC-S5-04-1`（正例分发）、`TC-S5-04-2`（未注册 skill）、`TC-S5-04-3`（参数不匹配/内置工具）、`TC-S5-04-4`（task_type 映射）、`TC-S5-04-5`（无二次 LLM）、`TC-S5-04-6`（router 拒 internal Skill）。

---

## S5-05 · Orchestrator：Reason + Reflect（2 个 internal Skill）

- **owner**: backend ｜ **归属 PR**: PR-12 ｜ **依赖**: S5-02, S5-04
- **目标**: 实现 R-P-R-A-R 的 Reason（§5.1）与 Reflect（§5.2）两段，以 `internal: true` Skill 承载。
- **交付清单**:
  - `backend/app/agent/skills/orchestrator_reason/v1_0_0/{skill.yaml,prompt.md,examples.yaml}`（`internal: true`）
  - `backend/app/agent/skills/orchestrator_reflect/v1_0_0/{skill.yaml,prompt.md,examples.yaml}`（`internal: true`）
  - skill.yaml 均含 `internal: true`、`max_retries: 0`、禁 `reasoning_effort`
  - engine 调用：`skill = registry.get('orchestrator-reason'); result = await skill.execute(input_data, session=db)`
  - 每段调用写一条 `executions`（phase=REASON/REFLECT，经 BaseSkill 管道落 `skill_execution_logs`）
- **验收判据**:
  1. mock LLM 返回合法 JSON → `ReasonOutput.task_type` 非空、`missing_entities` 为列表。
  2. `ReflectOutput.is_feasible=false` → 引擎进入 `WAITING_CONFIRMATION`/FAILED（不进入 Plan）。
  3. LLM 返回非法 JSON → Skill 经 `validate_output` 返回失败态，写 `executions` 状态 FAILED。
- **测试用例**: `TC-S5-05-1`（reason mock 正常）、`TC-S5-05-2`（reflect 不可行分支）、`TC-S5-05-3`（LLM 非法 JSON 降级）；mock 目标为 `BaseSkill.execute`。

---

## S5-06 · Orchestrator：Plan + Reflect-Plan（2 个 internal Skill）

- **owner**: backend ｜ **归属 PR**: PR-12 ｜ **依赖**: S5-02, S5-04
- **目标**: 实现 Plan（§5.3）与 Reflect-Plan（§5.4），产出待确认 Plan。
- **交付清单**:
  - `backend/app/agent/skills/orchestrator_plan/v1_0_0/{skill.yaml,prompt.md,examples.yaml}`（`internal: true`）：输出 `Plan`，`steps[].tool_name` 取自已注册 dispatchable Skill + 内置白名单，`optional` 默认 `false`
  - `backend/app/agent/skills/orchestrator_reflect_plan/v1_0_0/{skill.yaml,prompt.md,examples.yaml}`（`internal: true`）：输出 `is_plan_sound`/`adjusted_plan`/`issues`
- **验收判据**:
  1. `Plan.steps` 非空且每 `step.tool_name` 命中白名单（经 Tool Router 可达）。
  2. `ReflectPlanOutput.is_plan_sound=false` 且有 `adjusted_plan` → 采用 `adjusted_plan`。
  3. Plan 中某 `tool_name` 不在白名单 → `review_plan` 判 `is_plan_sound=false` 并列入 `issues`。
- **测试用例**: `TC-S5-06-1`（plan 生成+tool 合法）、`TC-S5-06-2`（reflect_plan 采纳 adjusted）、`TC-S5-06-3`（含非法 tool 的 plan 被判异常）；mock 目标为 `BaseSkill.execute`。

---

## S5-07 · Orchestrator：Act（纯模块）+ Reflect-Act（internal Skill）+ SSE 发射

- **owner**: backend ｜ **归属 PR**: PR-12（Act 主循环）/ PR-13（发射到 Redis）｜ **依赖**: S5-03, S5-05, S5-06
- **目标**: 实现 Act（§5.5，顺序逐 step 执行并推 tool_call/progress）与 Reflect-Act（§5.6），写 EventBuffer。
- **交付清单**:
  - `backend/app/agent/orchestrator/act.py`（**纯模块**）：`run_act(plan, ctx, emit) -> list[StepResult]`：for step in plan.steps 顺序 `await ToolRouter.dispatch(step)`；`emit` 回调推 `tool_call`→`progress`→（每步 `result`）；写 `executions`（phase=ACT）
  - `backend/app/agent/skills/orchestrator_reflect_act/v1_0_0/{skill.yaml,prompt.md,examples.yaml}`（`internal: true`）：`run_reflect_act(step_results) -> ReflectActOutput`（`is_result_valid`/`final_result`）
  - `emit` 由 `S5-03 EventBuffer.append` 注入
- **验收判据**:
  1. 单步执行依次发射 `tool_call`、`progress(100)`、`result` 三类事件（顺序正确）。
  2. 一步失败（Skill FAILED）且非 optional → 发 `error` 且 `run_act` 中止，但已成功步的产物进入 `StepResult`。
  3. `ReflectActOutput.is_result_valid=false` → 最终 `result` 事件仍带 `artifacts`（部分结果）。
  4. optional 步失败 → 发 `warning` 且继续。
- **测试用例**: `TC-S5-07-1`（事件时序）、`TC-S5-07-2`（必需步失败中止+部分产物）、`TC-S5-07-3`（reflect_act 无效仍出 artifacts）、`TC-S5-07-4`（可选步失败继续）、`TC-S5-07-5`（Reason 阶段经 emit 发 thinking）；`BaseSkill.execute` mock。

---

## S5-08 · Task 生命周期/状态机（含 CANCELLED）+ 并发/超时/失败降级

- **owner**: backend ｜ **归属 PR**: PR-12 ｜ **依赖**: S5-05..S5-07
- **目标**: 统一 Task 状态机（Q2，含 CANCELLED）、全局并发/单 Skill/阶段/整体超时（Q7/Q8）、失败降级（Q9）。
- **交付清单**:
  - `backend/app/agent/orchestrator/engine.py`：`OrchestratorEngine`
    - `async def run_chat(req) -> Task`（PENDING→PLANNING→WAITING_CONFIRMATION）
    - `async def run_execute(task_id, accepted_steps?, modifications?) -> Task`（WAITING_CONFIRMATION→EXECUTING→COMPLETED/FAILED）
    - `async def run_skip_to_score(jd_id, candidate_ids) -> Task`（直达 EXECUTING）
    - `async def run_cancel(task_id) -> Task`（PLANNING/WAITING_CONFIRMATION→CANCELLED）
    - 状态转移经 `TransitionGuard`（矩阵见 PLAN §2 Q2，含 `→CANCELLED` 两条；非法转移抛 `IllegalTransitionError`）
    - 各阶段经 `registry.get('orchestrator-*').execute(...)` 调用 internal Skill
    - 单 Skill `wait_for(120s)`、阶段 180s、整体 600s 超时；全局活跃计数 `task:active`（Redis `INCR`/`DECR`+TTL）
- **验收判据**:
  1. 合法转移 PENDING→PLANNING→WAITING_CONFIRMATION→EXECUTING→COMPLETED 全通过。
  2. 非法转移（如 COMPLETED→EXECUTING）→ 抛 `IllegalTransitionError` 且状态不变。
  3. 全局活跃任务达 10 后再 `run_chat` → 429 `TASK_LIMIT_EXCEEDED`（mock Redis 计数）。
  4. 单 Skill 超时（设 0.01s 阈值）→ 该步 `error` 且 Task FAILED（部分 artifacts 仍在 `result`）。
  5. 整体 600s 超时 → FAILED + `error(TASK_TIMEOUT)`。
  6. `WAITING_CONFIRMATION → CANCELLED`（见 `TC-S5-08-8`）。
- **测试用例**: `TC-S5-08-1`（合法转移链）、`TC-S5-08-2`（非法转移拒绝）、`TC-S5-08-3`（并发上限 429）、`TC-S5-08-4`（Skill 超时降级）、`TC-S5-08-5`（整体超时 FAILED）、`TC-S5-08-6`（矩阵逐合法转移参数化）、`TC-S5-08-7`（矩阵逐非法转移参数化）、`TC-S5-08-8`（从 WAITING_CONFIRMATION 取消→CANCELLED）。

---

## S5-09 · REST 四端点 + SSE 流端点 + 取消端点

- **owner**: backend ｜ **归属 PR**: PR-14 ｜ **依赖**: S5-03, S5-08
- **目标**: 暴露 4 个 REST 端点 + SSE 流端点 + 取消端点，正确路由顺序。
- **交付清单**:
  - `backend/app/api/v1/endpoints/agent.py`：
    - `POST /api/v1/agent/chat`
    - `POST /api/v1/agent/execute-plan`
    - `POST /api/v1/agent/skip-to-score`
    - `POST /api/v1/agent/tasks/{task_id}/cancel`（取消：仅接受 PLANNING/WAITING_CONFIRMATION 态，否则 409）
    - `GET /api/v1/agent/tasks/{task_id}/stream`（SSE；支持 `Last-Event-ID` 头；`retry: 3000`；15s 心跳；**声明在 `/tasks/{task_id}` 之前**）
    - `GET /api/v1/agent/tasks/{task_id}`（**声明在 `/stream` 之后**）
  - `backend/app/api/v1/router.py`：注册 `agent.py`
- **验收判据**:
  1. `GET /agent/tasks/{task_id}/stream` 返回 `text/event-stream`；`GET /agent/tasks/{task_id}` 返回 JSON（两路由不冲突，stream 先声明）。
  2. `chat` 缺 `message` → 422；`tasks/{bad_id}` → 404；并发超限 `chat` → 429；`cancel` 非确认态 → 409。
  3. SSE 连接带 `Last-Event-ID: 5` 重连 → 仅收到 `id>5` 的事件；无头则全量 replay。
  4. Orchestrator 未捕获异常 → 500（`TC-S5-09-6` mock engine raise）。
- **测试用例**: `TC-S5-09-1`（stream 先于 tasks 路由 order）、`TC-S5-09-2`（chat 422 / tasks 404 / cancel 409）、`TC-S5-09-3`（429 超限）、`TC-S5-09-4`（SSE Last-Event-ID 重放）、`TC-S5-09-5`（心跳事件 15s 间隔）、`TC-S5-09-6`（orchestrator 未捕获异常返回 500）。

---

## S5-10 · candidate-merge Skill（C1）

- **owner**: backend ｜ **归属 PR**: PR-15 ｜ **依赖**: S5-01, S5-02
- **目标**: 多简历智能合并，复用 `resumes.duplicate_of_resume_id` / `tags`。
- **交付清单**:
  - `backend/app/agent/skills/candidate_merge/v1_0_0/skill.yaml + prompt.md + examples.yaml`（`internal` 默认 `false`，`task_types: [MERGE_CANDIDATES]`）
  - input：`{ resumes: [{resume_id, candidate_name, parsed_content, tags, duplicate_of_resume_id}] }`
  - output：`{ action: 'MERGE'|'SUGGEST'|'KEEP_SEPARATE', master_resume_id, merged_fields, confidence, conflicts, recommendation }`
  - `max_retries: 0`
- **验收判据**:
  1. 高置信度（confidence≥0.9）→ `action=MERGE`，调用方据此写 `duplicate_of_resume_id`。
  2. 低置信度（confidence<0.5）→ `action=SUGGEST`，返回 `recommendation` 不自动合并。
  3. 明显冲突（不同姓名/手机号）→ `action=KEEP_SEPARATE`。
- **测试用例**: `TC-S5-10-1`（高置信自动合并）、`TC-S5-10-2`（低置信返建议）、`TC-S5-10-3`（冲突保持分离）、`TC-S5-10-4`（output_schema 校验）。

---

## S5-11 · candidate-profile Skill（C2）

- **owner**: backend ｜ **归属 PR**: PR-16 ｜ **依赖**: S5-01, S5-02
- **目标**: 候选人画像标签生成，与用户手工 `tags` 合并去重。
- **交付清单**:
  - `backend/app/agent/skills/candidate_profile/v1_0_0/skill.yaml + prompt.md + examples.yaml`（`internal` 默认 `false`，`task_types: [PROFILE_CANDIDATE]`）
  - input：`{ parsed_content, existing_tags: string[] }`
  - output：`{ profile_tags: string[], summary, strengths: string[], risks: string[] }`
  - `max_retries: 0`
- **验收判据**:
  1. 正常生成 → `profile_tags` 非空且与 `existing_tags` 合并后**去重无重复**。
  2. `existing_tags=["Python"]` 且模型再给 `"python"` → 合并后仅一个（大小写/归一去重）。
  3. `output_schema` 校验失败 → Skill 返回 FAILED（不写库）。
- **测试用例**: `TC-S5-11-1`（正常生成）、`TC-S5-11-2`（与手工标签合并去重）、`TC-S5-11-3`（schema 失败降级）、`TC-S5-11-4`（空 parsed_content 边界）。

---

## S5-12 · 前端类型 + SSE 客户端 Hook

- **owner**: frontend ｜ **归属 PR**: PR-18 ｜ **依赖**: S5-02
- **目标**: 前端 Task/SSE 类型与 `useTaskStream` Hook（EventSource + Last-Event-ID）。
- **交付清单**:
  - `frontend/src/types/agent.ts`：`SSEEvent`（含 `id`）、`Plan`/`PlanStep`（含 `optional`）、`TaskStatus`（含 `CANCELLED`）、`AgentChatRequest/Response` 等（对齐 `api-contract §3/§4`）
  - `frontend/src/services/agent.ts`：`chat()` / `executePlan()` / `skipToScore()` / `cancelTask()` / `getTask()`
  - `frontend/src/hooks/useTaskStream.ts`：`EventSource('/api/v1/agent/tasks/{id}/stream')`，维护 `lastEventId`，断线自动带 `Last-Event-ID` 重连，解析 8 类事件入 state
- **验收判据**:
  1. `useTaskStream` 收到 `thinking/plan/tool_call/progress/result/error/warning/system` 各事件更新对应 state。
  2. 模拟断线后重连请求头带 `Last-Event-ID`，只补收缺失事件（msw mock）。
  3. `services/agent.ts` `chat()` 调用 `POST /agent/chat` 且 429 时抛出可捕获错误；`cancelTask()` 调 `POST /agent/tasks/{id}/cancel`。
- **测试用例**: `TC-S5-12-1`（8 类事件解析）、`TC-S5-12-2`（Last-Event-ID 重连）、`TC-S5-12-3`（chat 429 处理）、`TC-S5-12-4`（类型对齐 schema）。

---

## S5-13 · 前端 ChatCenter + CandidateChat 页面

- **owner**: frontend ｜ **归属 PR**: PR-19 ｜ **依赖**: S5-09, S5-12
- **目标**: 用对话中心替换占位页，渲染事件卡片；候选人详情内嵌对话。
- **交付清单**:
  - `frontend/src/pages/ChatCenter.tsx`：消息输入框 → `chat()` → `useTaskStream` → 渲染 `ThinkingCard/PlanCard/ToolCallCard/ProgressCard/ResultCard/ErrorCard/WarningCard/SystemCard`（8 类事件卡片各 ≥1 例）；`PlanCard` 含「确认执行」「取消」按钮
  - `frontend/src/pages/CandidateChat.tsx`：预填 `context.candidate_ids` 的同构对话页
  - `frontend/src/components/agent/*Card.tsx`：各事件卡片（`SystemCard` 不渲染为业务卡片，仅状态提示）
- **验收判据**:
  1. 发送消息后出现 `PlanCard` 且「确认」按钮调用 `executePlan()`，「取消」调用 `cancelTask()`。
  2. `skip-to-score` 快捷入口：选 JD + 候选人 → 直接 `EXECUTING` 并显示进度。
  3. 断网/重连后历史事件经 `Last-Event-ID` 补齐，无重复卡片。
  4. `CANCELLED` 态任务显示取消提示 UI（见 `TC-S5-13-9`）。
- **测试用例**: `TC-S5-13-1`（发送→PlanCard→确认流）、`TC-S5-13-2`（skip-to-score 快捷）、`TC-S5-13-3`（8 类事件卡片渲染）、`TC-S5-13-4`（断线重连无重复）、`TC-S5-13-5`（CandidateChat 预填 context）、`TC-S5-13-6`（error 卡片）、`TC-S5-13-7`（warning 卡片）、`TC-S5-13-8`（system 心跳忽略）、`TC-S5-13-9`（cancelled 任务 UI）。

---

## §五 · 顺手清扫项（分配至对应 PR，不单独立项）

| 清扫项 | 归属 PR/任务 | 说明 |
|---|---|---|
| `services/match.py` 等 `datetime.utcnow()` → `datetime.now(timezone.utc)` | **PR-10**（S5-01 首个较大 backend 实现 PR） | 时区正确性，非功能阻断 |
| 前端 MSW stderr 噪声 | **PR-18**（S5-12） | 检查 `vitest` setup 中 MSW 日志级别 |
| `react-hooks/exhaustive-deps` warning | **PR-19**（S5-13） | 顺手补齐依赖数组（既有 8 处，部分与 Stage 5 新增 hook 相关） |
| `ResumeWorkspace.tsx` 删除 | **PR-9.pre**（已提交 `819227e`，非本合并版范围） | 全仓仅自引用，无路由 |

> 注：`raw_text[:3000]` 截断是否放宽至 6000–8000 仅**记录**于 HANDOFF（PR-9.pre 已记录），本 Stage 5 **不改代码**。

---

## §六 · PR-9 交付物边界（与编码任务分离）

> **PR-9 = 规划文档交付批次**，含以下文件，**不含任何 `backend/app/**`、`frontend/src/**`、迁移脚本的业务代码改动**：

- `docs/planning/PLAN-STAGE5.md`（本文件合并版）
- `docs/planning/TASKS-STAGE5.md`（本文件合并版）
- `docs/planning/TEST-PLAN-STAGE5.md`（合并版）
- `docs/planning/ACCEPTANCE-PR9.md`（验收请求）
- `docs/api-contract.md` 契约写回（§3.2 `id`、§3.5 重放/心跳、§3.4 `optional`、§4.4 `CANCELLED`、§4.5 取消端点）
- `HANDOFF.md` Skill 契约 `internal` 字段说明（§Skill 契约）

编码任务严格按上表「归属 PR」列拆分到 **PR-10..PR-18**，每 PR 独立三道门验证。
