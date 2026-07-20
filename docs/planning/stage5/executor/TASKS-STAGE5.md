# TASKS-STAGE5 · 执行体版（独立撰写，未参考指挥官版本）

> 配套：`PLAN-STAGE5.md`（架构与 12 问）、`TEST-PLAN-STAGE5.md`（用例矩阵）
> 全部任务归属 **PR-9**（Stage 5）。严格 TDD：先写测试，再实现。
> 强制约束（INSTRUCTION §一）：不写 `backend/app/**`、`frontend/src/**`、迁移脚本以外的代码；本文件中交付清单为**规划**，落地在 PR-9 实现阶段。

---

## 任务总览（13 个）

| ID | 标题 | owner | 依赖 |
|---|---|---|---|
| S5-01 | tasks / executions 数据层（迁移+Model+Schema 基础） | backend | — |
| S5-02 | SSE 事件 / Agent 交互 Pydantic Schema | backend | S5-01 |
| S5-03 | Redis 事件缓冲层 EventBuffer | backend | S5-01 |
| S5-04 | Tool Router（意图→工具分发与校验） | backend | S5-01 |
| S5-05 | Orchestrator：Reason + Reflect（§5.1/§5.2） | backend | S5-02, S5-04 |
| S5-06 | Orchestrator：Plan + Reflect-Plan（§5.3/§5.4） | backend | S5-02, S5-04 |
| S5-07 | Orchestrator：Act + Reflect-Act（§5.5/§5.6）+ SSE 发射 | backend | S5-03, S5-05, S5-06 |
| S5-08 | Task 生命周期/状态机 + 并发/超时/失败降级 | backend | S5-05..S5-07 |
| S5-09 | REST 四端点 + SSE 流端点（路由顺序） | backend | S5-03, S5-08 |
| S5-10 | candidate-merge Skill（C1） | backend | S5-01 |
| S5-11 | candidate-profile Skill（C2） | backend | S5-01 |
| S5-12 | 前端类型 + SSE 客户端 Hook | frontend | S5-02 |
| S5-13 | 前端 ChatCenter + CandidateChat 页面 | frontend | S5-09, S5-12 |

> 顺手清扫项见文末 §五（落在 S5-01 / S5-09 / S5-12 等 PR 内）。

---

## S5-01 · tasks / executions 数据层

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: 无
- **目标**: 落地 `tasks`、`executions` 两表，提供 ORM Model 与 `TimestampMixin` 复用。
- **交付清单**:
  - `backend/alembic/versions/<rev>_add_tasks_and_executions.py`（`down_revision="e4c1a2b3d4f5"`，`upgrade()` 建两表，`downgrade()` 删）
  - `backend/app/models/task.py`：`Task(Base, TimestampMixin)`，`__tablename__="tasks"`，字段见 PLAN §2 Q12（task_id 默认 `task_{uuid4().hex[:12]}`）
  - `backend/app/models/execution.py`：`Execution(Base, TimestampMixin)`，`__tablename__="executions"`，字段见 PLAN §2 Q12（execution_id 默认 `exec_{uuid4().hex[:12]}`）
  - `backend/app/models/__init__.py`：导出 `Task`、`Execution`
- **接口/签名**: `Task` / `Execution` 为 ORM；无对外函数签名。
- **验收判据**:
  1. `alembic upgrade head` 后 `tasks`/`executions` 表存在且字段/索引与 PLAN §2 Q12 一致（`idx_tasks_status`、`idx_executions_task_id/step_id/phase`）。
  2. `Task.task_id` / `Execution.execution_id` 默认生成前缀正确（`task_`/`exec_`）。
  3. `Task.status` 默认 `PENDING`；删除 `Task` 级联删除其 `executions`（FK `ON DELETE CASCADE` 生效）。
- **测试用例**: `TC-S5-01-1`（迁移建表）、`TC-S5-01-2`（ID 前缀默认）、`TC-S5-01-3`（Cascade 删除）。

---

## S5-02 · SSE 事件 / Agent 交互 Schema

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-01
- **目标**: 定义 SSE 事件、Agent 四端点请求/响应 Pydantic 模型，对齐 `api-contract §3/§4`。
- **交付清单**:
  - `backend/app/schemas/agent.py`：
    - `SSEEvent`（含 `id: str`、`type`、`task_id`、`step_id?`、`timestamp`、`data` —— 补 `id`，见 PLAN §3）
    - `AgentChatRequest`（`message: str`、`context?: {jd_id?, candidate_ids?}`）
    - `AgentChatResponse`（`task_id`、`status`、`initial_plan?: Plan`）
    - `ExecutePlanRequest`（`task_id`、`accepted_steps?`、`modifications?: [{step_id, modified_params?}]`）
    - `SkipToScoreRequest`（`jd_id`、`candidate_ids: list[str]`）
    - `TaskStatusResponse`（`task_id`、`status`、`current_step?`、`plan?`、`result?`、`error?`、`created_at`、`updated_at`）
    - `PlanStep` / `Plan`（对齐 `api-contract §3.4`，`step_id: str`）
- **验收判据**:
  1. `SSEEvent` 序列化含 `id` 且 `type` 仅允许 8 种枚举（校验失败抛 422）。
  2. `AgentChatRequest` 缺 `message` → 422。
  3. `PlanStep.tool_name` 为自由字符串（由 Tool Router 运行期校验，Schema 不约束）。
- **测试用例**: `TC-S5-02-1`（SSEEvent id+type 枚举）、`TC-S5-02-2`（chat 缺 message 422）、`TC-S5-02-3`（Plan/PlanStep 往返序列化）。

---

## S5-03 · Redis 事件缓冲层 EventBuffer

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-01
- **目标**: 实现 SSE 事件的 Redis 缓冲（add/trim/replay/ttl），供 SSE 端点重放与跨重连。
- **交付清单**:
  - `backend/app/agent/orchestrator/event_buffer.py`：`EventBuffer`
    - `async def append(task_id, event: SSEEvent) -> int`（写 `sse:buf:{task_id}`，MAXLEN=200 裁剪，返回 `id` 序号，TTL 3600）
    - `async def replay(task_id, after_id: int) -> list[SSEEvent]`（取 `id > after_id`）
    - `async def subscribe(task_id)` 生成器（实时 yield + 初连 replay）
  - `backend/app/core/redis.py`：`get_redis()` 异步单例（`redis.asyncio`）
  - `backend/pyproject.toml`：加 `redis[hiredis]`、`fakeredis`（dev）
- **验收判据**:
  1. 连续 append 250 条，`replay(0)` 仅返回最近 200 条（裁剪生效）。
  2. `replay(task_id, after_id=10)` 只返回 `id>10` 的事件（Last-Event-ID 语义）。
  3. 终态任务 3600s 后缓冲 TTL 过期，`replay` 返回空。
- **测试用例**: `TC-S5-03-1`（裁剪到 200）、`TC-S5-03-2`（after_id 重放）、`TC-S5-03-3`（TTL 过期）、`TC-S5-03-4`（fakeredis 单测隔离）。

---

## S5-04 · Tool Router

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-01
- **目标**: 将 `task_type` / `tool_name` 映射到已注册 Skill 或内置工具，并校验分发。
- **交付清单**:
  - `backend/app/agent/orchestrator/tool_router.py`：`ToolRouter`
    - `def route_task_type(reason_output) -> str`（映射 `api-contract §5.1` 的 `task_type` 到意图枚举）
    - `async def dispatch(step: PlanStep, ctx) -> SkillResult`：命中 Skill→`registry.get_skill(tool_name).execute(params)`；命中内置→调 service；未命中→抛 `UnknownToolError`
    - 内置工具白名单：`search_resumes`（→`Resume` 查询）、`read_jd`（→`JD` 查询）
- **验收判据**:
  1. `tool_name="jd-candidate-matching"` → 成功 dispatch 到该 Skill。
  2. `tool_name="__not_registered__"` → 抛 `UnknownToolError`（映射为 `error` 事件 `UNKNOWN_TOOL`）。
  3. `tool_name="search_resumes"` 且参数不匹配 schema → 抛 `ToolParamError`（映射 `error` 事件）。
- **测试用例**: `TC-S5-04-1`（正例分发）、`TC-S5-04-2`（未注册 skill）、`TC-S5-04-3`（参数不匹配）、`TC-S5-04-4`（task_type 映射）。

---

## S5-05 · Orchestrator：Reason + Reflect

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-02, S5-04
- **目标**: 实现 R-P-R-A-R 的 Reason（§5.1）与 Reflect（§5.2）两段。
- **交付清单**:
  - `backend/app/agent/orchestrator/reason.py`：`run_reason(message, context) -> ReasonOutput`（调 `LLMAdapter.call_llm_json`，prompt 内置；输出经 `validate_output`）
  - `backend/app/agent/orchestrator/reflect.py`：`run_reflect(reason_output) -> ReflectOutput`
  - 每段调用写一条 `executions`（phase=REASON/REFLECT）
- **验收判据**:
  1. mock LLM 返回合法 JSON → `ReasonOutput.task_type` 非空、`missing_entities` 为列表。
  2. `ReflectOutput.is_feasible=false` → 引擎应进入 `WAITING_CONFIRMATION`/FAILED（不进入 Plan）。
  3. LLM 返回非法 JSON → 抛 `SkillResult` 失败态，写 `executions` 状态 FAILED。
- **测试用例**: `TC-S5-05-1`（reason mock 正常）、`TC-S5-05-2`（reflect 不可行分支）、`TC-S5-05-3`（LLM 非法 JSON 降级）。

---

## S5-06 · Orchestrator：Plan + Reflect-Plan

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-02, S5-04
- **目标**: 实现 Plan（§5.3）与 Reflect-Plan（§5.4），产出待确认 Plan。
- **交付清单**:
  - `backend/app/agent/orchestrator/plan.py`：`build_plan(reason_output, reflect_output) -> Plan`（`steps[].tool_name` 取自已注册 Skill + 内置白名单）
  - `backend/app/agent/orchestrator/reflect_plan.py`：`review_plan(plan) -> ReflectPlanOutput`（`is_plan_sound`/`adjusted_plan`）
- **验收判据**:
  1. `Plan.steps` 非空且每 `step.tool_name` 命中白名单（经 Tool Router 可达）。
  2. `ReflectPlanOutput.is_plan_sound=false` 且有 `adjusted_plan` → 采用 `adjusted_plan`。
  3. Plan 中某 `tool_name` 不在白名单 → `review_plan` 判 `is_plan_sound=false` 并列入 `issues`。
- **测试用例**: `TC-S5-06-1`（plan 生成+tool 合法）、`TC-S5-06-2`（reflect_plan 采纳 adjusted）、`TC-S5-06-3`（含非法 tool 的 plan 被判异常）。

---

## S5-07 · Orchestrator：Act + Reflect-Act + SSE 发射

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-03, S5-05, S5-06
- **目标**: 实现 Act（§5.5，逐步执行并推 tool_call/progress）与 Reflect-Act（§5.6），并写 EventBuffer。
- **交付清单**:
  - `backend/app/agent/orchestrator/act.py`：`run_act(plan, ctx, emit) -> list[StepResult]`：`emit` 回调推 `tool_call`→`progress`→（`result`/每步）；每步经 `ToolRouter.dispatch`；写 `executions`（phase=ACT）
  - `backend/app/agent/orchestrator/reflect_act.py`：`run_reflect_act(step_results) -> ReflectActOutput`（`is_result_valid`/`final_result`）
  - `emit` 由 `S5-03 EventBuffer.append` 注入
- **验收判据**:
  1. 单步执行依次发射 `tool_call`、`progress(100)`、`result` 三类事件（顺序正确）。
  2. 一步失败（Skill FAILED）且非 optional → 发 `error` 且 `run_act` 中止，但已成功步的产物进入 `StepResult`。
  3. `ReflectActOutput.is_result_valid=false` → 最终 `result` 事件仍带 `artifacts`（部分结果）。
- **测试用例**: `TC-S5-07-1`（事件时序 tool_call→progress→result）、`TC-S5-07-2`（必需步失败中止+部分产物）、`TC-S5-07-3`（reflect_act 无效仍出 artifacts）、`TC-S5-07-4`（可选步失败继续）。

---

## S5-08 · Task 生命周期/状态机 + 并发/超时/失败降级

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-05..S5-07
- **目标**: 统一 Task 状态机（Q2）、全局并发/单 Skill/阶段/整体超时（Q7/Q8）、失败降级（Q9）。
- **交付清单**:
  - `backend/app/agent/orchestrator/engine.py`：`OrchestratorEngine`
    - `async def run_chat(req) -> Task`（PENDING→PLANNING→WAITING_CONFIRMATION）
    - `async def run_execute(task_id, accepted_steps?, modifications?) -> Task`（WAITING_CONFIRMATION→EXECUTING→COMPLETED/FAILED）
    - `async def run_skip_to_score(jd_id, candidate_ids) -> Task`（直达 EXECUTING）
    - 状态转移经 `TransitionGuard`（矩阵见 PLAN §2 Q2，非法转移抛 `IllegalTransitionError`）
    - 单 Skill `wait_for(120s)`、阶段 180s、整体 600s 超时；全局活跃计数 `task:active`（Redis `INCR`/`DECR`+TTL）
- **验收判据**:
  1. 合法转移 PENDING→PLANNING→WAITING_CONFIRMATION→EXECUTING→COMPLETED 全通过。
  2. 非法转移（如 COMPLETED→EXECUTING）→ 抛 `IllegalTransitionError` 且状态不变。
  3. 全局活跃任务达 10 后再 `run_chat` → 429 `TASK_LIMIT_EXCEEDED`（mock Redis 计数）。
  4. 单 Skill 超时（设 0.01s 阈值）→ 该步 `error` 且 Task FAILED（部分 artifacts 仍在 `result`）。
- **测试用例**: `TC-S5-08-1`（合法转移链）、`TC-S5-08-2`（非法转移拒绝）、`TC-S5-08-3`（并发上限 429）、`TC-S5-08-4`（Skill 超时降级）、`TC-S5-08-5`（整体超时 FAILED）。

---

## S5-09 · REST 四端点 + SSE 流端点

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-03, S5-08
- **目标**: 暴露 4 个 REST 端点 + SSE 流端点，正确路由顺序。
- **交付清单**:
  - `backend/app/api/v1/endpoints/agent.py`：
    - `POST /api/v1/agent/chat`
    - `POST /api/v1/agent/execute-plan`
    - `POST /api/v1/agent/skip-to-score`
    - `GET /api/v1/agent/tasks/{task_id}`（**声明在 `/stream` 之后**）
    - `GET /api/v1/agent/tasks/{task_id}/stream`（SSE；支持 `Last-Event-ID` 头；`retry: 3000`；15s 心跳）
  - `backend/app/api/v1/router.py`：注册 `agent.py`
- **验收判据**:
  1. `GET /agent/tasks/{task_id}/stream` 返回 `text/event-stream`；`GET /agent/tasks/{task_id}` 返回 JSON（两路由不冲突，stream 先声明）。
  2. `chat` 缺 `message` → 422；`tasks/{bad_id}` → 404；并发超限 `chat` → 429。
  3. SSE 连接带 `Last-Event-ID: 5` 重连 → 仅收到 `id>5` 的事件；无头则全量 replay。
- **测试用例**: `TC-S5-09-1`（stream 先于 tasks 路由 order）、`TC-S5-09-2`（chat 422 / tasks 404）、`TC-S5-09-3`（429 超限）、`TC-S5-09-4`（SSE Last-Event-ID 重放）、`TC-S5-09-5`（心跳事件 15s 间隔）。

---

## S5-10 · candidate-merge Skill（C1）

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-01
- **目标**: 多简历智能合并，复用 `resumes.duplicate_of_resume_id` / `tags`。
- **交付清单**:
  - `backend/app/agent/skills/candidate_merge/v1_0_0/skill.yaml` + `prompt.md` + `examples.yaml`
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

- **owner**: backend ｜ **PR**: PR-9 ｜ **依赖**: S5-01
- **目标**: 候选人画像标签生成，与用户手工 `tags` 合并去重。
- **交付清单**:
  - `backend/app/agent/skills/candidate_profile/v1_0_0/skill.yaml` + `prompt.md` + `examples.yaml`
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

- **owner**: frontend ｜ **PR**: PR-9 ｜ **依赖**: S5-02
- **目标**: 前端 Task/SSE 类型与 `useTaskStream` Hook（EventSource + Last-Event-ID）。
- **交付清单**:
  - `frontend/src/types/agent.ts`：`SSEEvent`（含 `id`）、`Plan`/`PlanStep`、`TaskStatus`、`AgentChatRequest/Response` 等（对齐 `api-contract §3/§4`）
  - `frontend/src/services/agent.ts`：`chat()` / `executePlan()` / `skipToScore()` / `getTask()`
  - `frontend/src/hooks/useTaskStream.ts`：`EventSource('/api/v1/agent/tasks/{id}/stream')`，维护 `lastEventId`，断线自动带 `Last-Event-ID` 重连，解析 8 类事件入 state
- **验收判据**:
  1. `useTaskStream` 收到 `thinking/plan/tool_call/progress/result/error/warning/system` 各事件更新对应 state。
  2. 模拟断线后重连请求头带 `Last-Event-ID`，只补收缺失事件（msw mock）。
  3. `services/agent.ts` `chat()` 调用 `POST /agent/chat` 且 429 时抛出可捕获错误。
- **测试用例**: `TC-S5-12-1`（8 类事件解析）、`TC-S5-12-2`（Last-Event-ID 重连）、`TC-S5-12-3`（chat 429 处理）、`TC-S5-12-4`（类型对齐 schema）。

---

## S5-13 · 前端 ChatCenter + CandidateChat 页面

- **owner**: frontend ｜ **PR**: PR-9 ｜ **依赖**: S5-09, S5-12
- **目标**: 用对话中心替换占位页，渲染事件卡片。
- **交付清单**:
  - `frontend/src/pages/ChatCenter.tsx`：消息输入框 → `chat()` → `useTaskStream` → 渲染 `ThinkingCard/PlanCard/ToolCallCard/ProgressCard/ResultCard/ErrorCard/WarningCard/SystemCard`（6 类以上事件卡片各 1 例）
  - `frontend/src/pages/CandidateChat.tsx`：预填 `context.candidate_ids` 的同构对话页
  - `frontend/src/components/agent/*Card.tsx`：各事件卡片
- **验收判据**:
  1. 发送消息后出现 `PlanCard` 且「确认」按钮调用 `executePlan()`。
  2. `skip-to-score` 快捷入口：选 JD + 候选人 → 直接 `EXECUTING` 并显示进度。
  3. 断网/重连后历史事件经 `Last-Event-ID` 补齐，无重复卡片。
- **测试用例**: `TC-S5-13-1`（发送→PlanCard→确认流）、`TC-S5-13-2`（skip-to-score 快捷）、`TC-S5-13-3`（6 类事件卡片渲染）、`TC-S5-13-4`（断线重连无重复）、`TC-S5-13-5`（CandidateChat 预填 context）。

---

## §五 · 顺手清扫项（建议落点）

| 清扫项 | 落点 PR/任务 | 说明 |
|---|---|---|
| `services/match.py` 中 `datetime.utcnow()` → `datetime.now(timezone.utc)` | S5-09（首个较大 backend 实现 PR）或独立 `chore:` | 时区正确性，非功能阻断 |
| 前端 MSW stderr 噪声 | S5-12 | 检查 `vitest` setup 中 MSW 日志级别 |
| `react-hooks/exhaustive-deps` warning | S5-12/S5-13 | 顺手补齐依赖数组（既有 8 处，部分与 Stage 5 新增 hook 相关） |
| `ResumeWorkspace.tsx` 删除 | **PR-9.pre**（见 INSTRUCTION §八，独立提交） | 全仓仅自引用，无路由 |

> 注：`raw_text[:3000]` 截断是否放宽至 6000–8000 仅**记录**于 HANDOFF（§八），本 PR-9 **不改代码**。
