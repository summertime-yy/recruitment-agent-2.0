# Stage 5 任务拆解 · 指挥官版（TASKS-STAGE5）

> 版本：`commander-v1`（双盲评审隔离产物）
> 依据：`docs/planning/stage5/commander/PLAN-STAGE5.md`
> 命名规范：`S5-<两位序号>`

---

## 任务清单

### S5-01 · tasks / executions 数据模型与 Schema + Redis 依赖接入

**归属 PR**：PR-10
**依赖**：无（承接 Stage 4 head `e4c1a2b3d4f5`）
**owner**：backend
**交付**：
- `backend/alembic/versions/<rev>_add_agent_tasks_and_executions.py`
  - `down_revision = 'e4c1a2b3d4f5'`
  - 建 `tasks` 表（PLAN 决策 12）
  - 建 `executions` 表（PLAN 决策 12）
  - 索引 `idx_tasks_status_created`、`idx_executions_task_created`
- `backend/app/models/task.py`：`Task`、`Execution` ORM
- `backend/app/schemas/agent.py`：
  - `TaskStatus` 枚举（对齐 `api-contract §4.4`）
  - `ExecutionPhase` 枚举
  - `AgentChatRequest/Response`、`ExecutePlanRequest`、`SkipToScoreRequest`、`TaskStatusResponse`（对齐 `api-contract §4`）
  - `PlanStep`、`Plan`（对齐 `api-contract §3.4`）
- **Redis 依赖前置接入**（PLAN 决策 5）：
  - `uv add redis[hiredis]>=5.0`
  - `uv add --dev fakeredis>=2.20`
  - `.env.example` 追加 `REDIS_URL=redis://localhost:6379/0`
  - `backend/app/core/config.py` 增 `redis_url: str` 字段
- `docs/data-model.md` 追加 §3.7 tasks / §3.8 executions
- `docs/api-contract.md` §3.4 补 SSE `id`/`retry`/心跳字段（PLAN 决策 4）

**验收判据**：
1. `alembic upgrade head` 成功，head 推进到新 rev
2. `alembic downgrade -1` 可回滚
3. Model 字段类型、约束、索引、CASCADE 与 DDL 完全一致
4. Schema 通过 Pydantic v2 校验，字段名与 `api-contract` 一致
5. 单测：Model CRUD、Schema 序列化/反序列化各 ≥3 例

**测试用例编号**：TC-S5-01-01 ~ TC-S5-01-08（见 TEST-PLAN）

---

### S5-02 · SkillRegistry 扩展 `list_by_task_type`

**归属 PR**：PR-11
**依赖**：S5-01（Schema）
**owner**：backend
**交付**：
- 扩展 `SkillRegistry`（`backend/app/agent/registry.py`）新增：
  ```python
  def list_by_task_type(self, task_type: str) -> list[SkillMeta]: ...
  ```
- Skill 元数据 `skill.yaml` 新增可选字段 `task_types: [str]`（不填即"通用工具"）
- 现有 `jd-candidate-matching` 的 skill.yaml 补 `task_types: [MATCH_ONE, MATCH_RANK]`

**验收判据**：
1. 已注册 Skill 未标注 `task_types` 的向后兼容
2. 未知 `task_type` 返回空列表，不抛异常
3. 单测：注册后查询、多 Skill 匹配、无匹配、大小写敏感各 1 例

**测试用例**：TC-S5-02-01 ~ TC-S5-02-04

---

### S5-03 · Tool Router

**归属 PR**：PR-11
**依赖**：S5-02
**owner**：backend
**交付**：
- `backend/app/agent/orchestrator/tool_router.py`
  ```python
  class ToolRouter:
      async def resolve(self, plan_step: PlanStep) -> BaseSkill: ...
      def validate_params(self, skill: BaseSkill, params: dict) -> None: ...
  ```
- 错误分类：`SkillNotFoundError` / `SkillVersionMissingError` / `SkillParamMismatchError`

**验收判据**：
1. 三类错误各有独立异常类，能被 Orchestrator 差异化处理
2. `validate_params` 用 Skill input Schema 校验（Pydantic v2）
3. 单测：正常路由 / 3 类错误 / 参数缺失 / 参数超集 各 1 例

**测试用例**：TC-S5-03-01 ~ TC-S5-03-06

---

### S5-04 · Orchestrator 阶段 Skill（5 个）

**归属 PR**：PR-12
**依赖**：S5-03
**owner**：backend
**交付**：
- `orchestrator_reason/v1_0_0/` — Reason 阶段（输出 `task_type/intent/missing_entities`）
- `orchestrator_reflect/v1_0_0/` — Reflect（输出 `is_feasible/needs_clarification`）
- `orchestrator_plan/v1_0_0/` — Plan（输出 `Plan`）
- `orchestrator_reflect_plan/v1_0_0/` — Reflect-Plan（输出 `is_plan_sound/adjusted_plan`）
- `orchestrator_reflect_act/v1_0_0/` — Reflect-Act（输出 `is_result_valid/final_result`）

每个 Skill：`skill.yaml` + `prompt.md` + `examples.yaml`，`max_retries: 0`，禁 `reasoning_effort`。

**验收判据**：
1. 5 个 Skill 均能被 `SkillRegistry` 自动加载
2. 每 Skill 有 ≥2 个 `examples.yaml` 用例
3. 单测：每 Skill 至少 1 例 mock LLM，验证 I/O Schema

**测试用例**：TC-S5-04-01 ~ TC-S5-04-10

---

### S5-05 · Orchestrator Engine（R-P-R-A-R 主循环）

**归属 PR**：PR-12
**依赖**：S5-04
**owner**：backend
**交付**：
- `backend/app/agent/orchestrator/state_machine.py`：状态转移矩阵（PLAN 决策 1）
- `backend/app/agent/orchestrator/engine.py`：
  ```python
  class OrchestratorEngine:
      async def start(self, task_id: str) -> None: ...
      async def resume_from_plan(self, task_id: str) -> None: ...   # execute-plan 后
      async def skip_to_score(self, jd_id: str, candidate_ids: list[str]) -> str: ...
  ```
- Semaphore(2) 控制 Act 并发（PLAN 决策 6）
- 超时保护（PLAN 决策 7）：`asyncio.wait_for` 包裹每阶段
- 失败降级（PLAN 决策 9）
- 每阶段/每 Skill 调用后写 `executions` 记录

**验收判据**：
1. 单测覆盖状态机每条合法转移（≥7 条）
2. 单测覆盖每条非法转移抛异常（≥3 条）
3. Task 超时 → 状态 `FAILED`，`error_code='TASK_TIMEOUT'`
4. Semaphore 并发限制生效（时间断言）
5. Reason 失败 → Task FAILED；Act 单步失败 → Task 仍 COMPLETED 但 result 含 partial 标记

**测试用例**：TC-S5-05-01 ~ TC-S5-05-15

---

### S5-06 · SSE 事件总线（EventBus）+ 应用启动接入 Redis

**归属 PR**：PR-13
**依赖**：S5-05
**owner**：backend
**交付**：
- **应用启动挂 Redis**（PLAN 决策 5）：
  - `backend/app/main.py` lifespan 内 `app.state.redis = redis.asyncio.from_url(settings.redis_url, decode_responses=True)`
  - shutdown 时 `await app.state.redis.aclose()`
  - 依赖注入器 `get_redis()` 供 EventBus 使用
- `backend/app/agent/orchestrator/event_bus.py`：
  ```python
  class EventBus:
      async def emit(self, task_id: str, event_type: str, data: dict, step_id: str | None = None) -> int: ...  # 返回 seq
      async def replay(self, task_id: str, last_event_id: int | None) -> AsyncIterator[SSEEvent]: ...
      async def subscribe(self, task_id: str) -> AsyncIterator[SSEEvent]: ...
  ```
- Redis List `sse:task:<task_id>:events` 存事件，容量 200，TTL 30min（LTRIM + EXPIRE）
- Redis Pub/Sub 通道 `sse:task:<task_id>:pub` 用于活跃订阅
- 心跳 task：每 15s 发 `system` 事件

**验收判据**：
1. `emit` 返回单调递增 seq
2. `replay(None)` 从头回放；`replay(N)` 从 N+1 开始
3. 缓冲滚出后 `replay(旧seq)` 发 `warning` 事件
4. 单测用 `fakeredis` 或依赖注入的内存实现
5. 心跳频率断言

**测试用例**：TC-S5-06-01 ~ TC-S5-06-08

---

### S5-07 · SSE HTTP 端点

**归属 PR**：PR-13
**依赖**：S5-06
**owner**：backend
**交付**：
- `backend/app/api/v1/endpoints/agent.py`：
  ```
  GET /agent/tasks/{task_id}/stream
  ```
- `StreamingResponse` 返回，`text/event-stream`
- 支持请求头 `Last-Event-ID`（大小写不敏感）
- 断线时自动清理订阅

**验收判据**：
1. 集成测试：httpx AsyncClient 消费 SSE 帧
2. `Last-Event-ID` 头传入，从指定 seq+1 回放
3. 未知 `task_id` 返回 404
4. 心跳帧被客户端收到

**测试用例**：TC-S5-07-01 ~ TC-S5-07-05

---

### S5-08 · REST API 四端点

**归属 PR**：PR-14
**依赖**：S5-07
**owner**：backend
**交付**：
- `POST /agent/chat` → 创建 task，异步启动 Orchestrator，返回 `task_id + status`
- `POST /agent/execute-plan` → 校验 task 处于 `WAITING_CONFIRMATION`，触发 `resume_from_plan`
- `POST /agent/skip-to-score` → 直接构造 Plan（`jd-candidate-matching` 批量），跳过 Reason/Plan
- `GET /agent/tasks/{task_id}` → 返回 `TaskStatus`（对齐 `api-contract §4.4`）
- **路由声明顺序**（PLAN 决策 11）：chat / execute-plan / skip-to-score → tasks/{id}/stream → tasks/{id}

**验收判据**：
1. 路由顺序集成测试：`GET /agent/tasks/xxx/stream` 不被 `/agent/tasks/{task_id}` 误捕
2. 400/404/409/429/500 错误码矩阵各 ≥1 例
3. 全局并发 Task ≥10 → 429（PLAN 决策 6）
4. `execute-plan` 对非 `WAITING_CONFIRMATION` 的 task 返回 409

**测试用例**：TC-S5-08-01 ~ TC-S5-08-12

---

### S5-09 · `candidate-merge` Skill

**归属 PR**：PR-15
**依赖**：S5-02（Skill 注册）
**owner**：backend
**交付**：
- `backend/app/agent/skills/candidate_merge/v1_0_0/`
- 输入：`{ candidate_ids: [str], merge_strategy: 'auto'|'suggest' }`
- 输出：
  ```json
  {
    "merge_groups": [
      { "primary": "res_xxx", "duplicates": ["res_yyy"], "confidence": 0.95, "evidence": ["phone match", "email match", "name similarity 0.92"] }
    ],
    "conflicts": [...]
  }
  ```
- 自动合并阈值：`confidence >= 0.9`
- 与 Stage 3 `duplicate_of_resume_id` 字段联动：合并时更新此字段
- Skill task_types: `[MERGE_CANDIDATES]`

**验收判据**：
1. 高置信度自动合并 → `duplicate_of_resume_id` 正确写入
2. 低置信度返回 suggest 不落库
3. 冲突（如姓名相同电话不同）在 `conflicts` 中列出
4. mock LLM 单测：3+ 场景

**测试用例**：TC-S5-09-01 ~ TC-S5-09-06

---

### S5-10 · `candidate-profile` Skill

**归属 PR**：PR-16
**依赖**：S5-02
**owner**：backend
**交付**：
- `backend/app/agent/skills/candidate_profile/v1_0_0/`
- 输入：`{ resume_id: str }`
- 输出：
  ```json
  {
    "tags": ["高级前端", "5-8年经验", "教育背景优秀"],
    "strengths": [...],
    "concerns": [...],
    "one_line_summary": "..."
  }
  ```
- 落库：更新 `resumes.tags`（合并去重，不覆盖用户已加标签）
- Skill task_types: `[PROFILE_CANDIDATE]`

**验收判据**：
1. tags 与用户手工标签合并去重
2. 生成的 one_line_summary 长度 ≤ 200 字
3. mock LLM 单测：≥3 场景（工程师 / 产品 / 空简历兜底）

**测试用例**：TC-S5-10-01 ~ TC-S5-10-05

---

### S5-11 · 前端 ChatCenter.tsx + useSSE hook + 事件卡片

**归属 PR**：PR-17
**依赖**：S5-08
**owner**：frontend
**交付**：
- `frontend/src/hooks/useSSE.ts`：EventSource 封装
  - 自动携带 `lastEventId` 重连
  - 心跳/warning/error 事件回调
- `frontend/src/pages/ChatCenter.tsx`：
  - 左侧任务列表（列出 tasks）
  - 中央对话流（按事件类型渲染卡片）
  - 底部输入框 + 「跳过计划直接评分」快捷入口
- 6 类卡片组件：`ThinkingCard/PlanCard/ToolCallCard/ProgressCard/ResultCard/ErrorCard`
- `PlanCard` 支持"执行"/"修改参数"/"取消"三按钮
- `frontend/src/api/agent.ts`：4 个 REST + SSE 客户端封装
- 路由 `/chat` 挂载 ChatCenter

**验收判据**：
1. Vitest + msw：任务创建 → SSE 事件消费 → 卡片渲染各 ≥1 例
2. Plan 展示后点击"执行"，触发 `execute-plan` API
3. 断线模拟（EventSource close & reconnect），Last-Event-ID 传递
4. 顺手清理：`Resumes.match.test.tsx` MSW stderr 消噪；本文件内 `exhaustive-deps` 4 条 warning 局部整改

**测试用例**：TC-S5-11-01 ~ TC-S5-11-08

---

### S5-12 · 前端 CandidateChat.tsx（候选人详情内嵌）

**归属 PR**：PR-18
**依赖**：S5-11
**owner**：frontend
**交付**：
- `frontend/src/pages/CandidateChat.tsx`（嵌入 `ResumeDetail.tsx` 一个侧栏或独立路由 `/resumes/:id/chat`）
- 复用 `useSSE` + 事件卡片
- 上下文预填 `context.candidate_ids = [resume_id]`

**验收判据**：
1. 从候选人详情进入 Chat，输入"给这个候选人生成画像"能触发 `candidate-profile` Skill
2. Vitest ≥2 例

**测试用例**：TC-S5-12-01 ~ TC-S5-12-03

---

## 关键路径

```
S5-01 → S5-02 → S5-03 → S5-04 → S5-05 → S5-06 → S5-07 → S5-08 → S5-11 → S5-12
                            ↘ S5-09 (可并行 S5-05 之后)
                            ↘ S5-10 (可并行 S5-05 之后)
```

单人执行按 S5-01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 顺序。

---

## 顺手清扫（在对应 PR 内完成，不单独立项）

| PR | 顺手项 | 来源 |
|---|---|---|
| PR-10 | `datetime.utcnow()` → `datetime.now(UTC)` 全仓替换 | Stage 4 遗留 |
| PR-17 | `Resumes.match.test.tsx` MSW 边缘 handler 补齐消 stderr | Stage 4 遗留 |
| PR-17 | `Resumes.tsx` / `ResumeDetail.tsx` 4 条 `exhaustive-deps` 局部整改 | Stage 4 遗留 |

