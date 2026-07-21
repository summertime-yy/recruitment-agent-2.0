# PR-12 · Orchestrator 主循环启动裁定

> 关联：`docs/planning/stage5/PR12-KICKOFF-QUESTIONS.md` · 分支 `feat/pr-12-s5-05-08-orchestrator`
> 生成时间：2026-07-20
> 状态：**PR-15 已合入 master（`92a322e`）**、**PR-12 分支基于 `92a322e`**、**7 问全部裁定**
> 执行体现在可以按 §六 恢复 PR-12 转绿工作

---

## 一、前置状态确认

在给出裁定前先确认当前仓库状态（我已核验）：

| 项 | 状态 |
|---|---|
| master HEAD | `92a322e`（PR-15 candidate-merge 已合入并 push） |
| feat/pr-12 分支 HEAD | `b8cf1f3`（红骨架 + 求助文档，本地未 push） |
| feat/pr-12 分支基线 | 父提交 = `92a322e`，**无需 rebase**（执行体在 PR-15 合入后建的分支） |
| PR-15 分支 | 本地 + 远端已删除，STEP6 报告已提交 |
| 本地 pytest（master） | **70 passed**（66 + PR-15 的 4） |
| PR-12 红骨架 collect | 4 errors during collection（意料之内——期望的红态） |

**结论**：并行护栏全部守住，无 rebase 冲突风险；PR-12 转绿后测试基线将是 70 → 89（+19）。

---

## 二、Q1 · Reason / Reflect / Plan / Reflect-Plan / Reflect-Act 输出 JSON 结构（🚨 加码）

### 裁定：**采纳执行体建议，并追加 Plan / Reflect-Plan / Reflect-Act 结构固化**

执行体只问了 Reason/Reflect，但 R-P-R-A-R 里另外 3 段（Plan / Reflect-Plan / Reflect-Act）也没在契约里固化。**一次性全部裁定**，避免后续再回来问。

### ReasonOutput（`orchestrator_reason/v1_0_0/skill.yaml` 的 output_schema）

```yaml
output_schema:
  type: object
  properties:
    task_type:
      type: string
      description: 与 skill.yaml 声明的 task_type 1:1 对齐（如 match / merge_candidates / unknown）
    intent_summary:
      type: string
      description: 一句话概括用户意图，用于 Plan 阶段 prompt 引用
    parsed_entities:
      type: object
      description: 从用户消息解析的结构化实体
      properties:
        jd_id: { type: [string, "null"] }
        candidate_ids: { type: array, items: { type: string } }
        keyword: { type: [string, "null"] }
      additionalProperties: true
    missing_entities:
      type: array
      items: { type: string }
      description: Reason 判定"要完成用户意图但当前上下文缺失"的实体名（如 ["jd_id"]）
    confidence:
      type: number
      minimum: 0
      maximum: 1
  required: [task_type, intent_summary, parsed_entities, missing_entities, confidence]
```

**理由**：
- `task_type` 必填，与 `list_dispatchable(task_type=X)` 直接对齐
- `intent_summary` 让 Plan prompt 简单——不必再解析原始用户消息
- `parsed_entities.additionalProperties: true` 允许未来 task_type 扩展新实体（如 `resume_ids`）
- `confidence` 供 Reflect 判 `is_feasible` 参考（低置信度 → Reflect 更倾向 `is_feasible=false`）

### ReflectOutput（`orchestrator_reflect/v1_0_0/skill.yaml` 的 output_schema）

```yaml
output_schema:
  type: object
  properties:
    is_feasible:
      type: boolean
      description: Reason 结果是否足以进入 Plan 阶段
    blocking_reason:
      type: [string, "null"]
      description: is_feasible=false 时的阻塞原因（用户可见）
    suggestion:
      type: [string, "null"]
      description: is_feasible=false 时给用户的下一步建议（如"请提供 jd_id"）
  required: [is_feasible]
```

**理由**：`is_feasible=true` 时 `blocking_reason` / `suggestion` 可为 null；`is_feasible=false` 时**必须**至少提供 `blocking_reason`，但 schema 层不强约束（避免 LLM 因缺字段整体失败），交由 prompt 引导。

### PlanOutput（`orchestrator_plan/v1_0_0/skill.yaml` 的 output_schema）

```yaml
output_schema:
  type: object
  properties:
    steps:
      type: array
      minItems: 1
      items:
        type: object
        properties:
          step_id:
            type: string
            description: 步骤唯一标识（如 "step_1"）
          tool_name:
            type: string
            description: 必须命中 dispatchable Skill ID 或内置工具白名单
          tool_input:
            type: object
            description: 该 step 的入参，需与 tool 的 input_schema 匹配
          optional:
            type: boolean
            default: false
            description: 是否可选步（optional=true 时失败仅 warning 不中断）
          description:
            type: string
            description: 步骤自然语言描述（供前端 PlanCard 展示）
        required: [step_id, tool_name, tool_input, description]
    summary:
      type: string
      description: Plan 整体概述（供前端 PlanCard 顶部展示）
  required: [steps, summary]
```

**理由**：结构与 `app/schemas/agent.py::PlanStep`（PR-10 已交付）保持一致；`optional: false` 默认与 PLAN §5 一致。

### ReflectPlanOutput（`orchestrator_reflect_plan/v1_0_0/skill.yaml` 的 output_schema）

```yaml
output_schema:
  type: object
  properties:
    is_plan_sound:
      type: boolean
    adjusted_plan:
      type: [object, "null"]
      description: is_plan_sound=false 时提供替代 Plan（结构同 PlanOutput）；is_plan_sound=true 时为 null
    issues:
      type: array
      items:
        type: object
        properties:
          step_id: { type: string }
          issue: { type: string }
        required: [issue]
  required: [is_plan_sound, issues]
```

**理由**：`issues` 即使 `is_plan_sound=true` 也可为空数组；`adjusted_plan` 结构复用 PlanOutput（Engine 层可直接替换 plan 引用）。

### ReflectActOutput（`orchestrator_reflect_act/v1_0_0/skill.yaml` 的 output_schema）

```yaml
output_schema:
  type: object
  properties:
    is_result_valid:
      type: boolean
    final_result:
      type: object
      description: 综合各 step 产物的最终结果，供前端 ResultCard 渲染
    issues:
      type: array
      items: { type: string }
  required: [is_result_valid, final_result, issues]
```

**理由**：即使 `is_result_valid=false`，`final_result` 仍必填（用于呈现"部分结果"），与 TC-S5-07-3 "reflect_act 无效仍出 artifacts" 一致。

---

## 三、Q2 · emit 回调签名

### 裁定：**采纳执行体建议 — async emit + 异常兜底**

```python
# backend/app/agent/orchestrator/act.py
from typing import Awaitable, Callable
from app.schemas.agent import SSEEvent

EmitFn = Callable[[SSEEvent], Awaitable[None]]

async def run_act(
    plan: Plan,
    ctx: dict,
    emit: EmitFn,
    tool_router: ToolRouter,
    db: AsyncSession,
) -> list[StepResult]:
    ...
    try:
        await emit(SSEEvent(...))
    except Exception as e:
        logger.warning("emit failed: %s (event dropped, act continues)", e)
```

**决策要点**：
1. `emit` 签名为 `async def emit(ev: SSEEvent) -> None`（**注意参数类型是 `SSEEvent` dataclass 而非 `dict`**，配合 PR-10 已交付的 `app/schemas/agent.py`）
2. Act 内 `await emit(ev)` **同步等待**——避免"emit 失败"与"业务成功"时序颠倒
3. **`try/except Exception` 包裹每次 emit**——SSE 推送不应中断业务
4. **不用 `asyncio.create_task` 触发遗忘**——否则测试断言"事件顺序"会非确定性

**Reflect-Act 是否传 emit**：
- **传**。Reflect-Act 完成后 Engine 需要发 `result` 事件；由 Engine 层调用 emit 更清晰（Reflect-Act Skill 本身不 emit），但 `run_act` 的返回 `list[StepResult]` 后由调用者 emit `result`
- **具体分工**：
  - `run_act` 内部 emit：`tool_call` / `progress` / `warning`（optional 步失败）/ `error`（必需步失败）
  - Engine 层在 Reflect-Act 后 emit：`result`（含 `final_result` + `is_result_valid`）
  - Engine 层在 Reason/Plan 完成时 emit：`thinking` / `plan`
  - Engine 层维护 SSE `id` 单调递增计数器（每 emit 一次 `id += 1`）

---

## 四、Q3 · chat 端点是否内含 Act

### 裁定：**采纳执行体建议 — 严格分层**

| 端点 | 触发阶段 | 终态 |
|---|---|---|
| `POST /agent/chat` | R → P → R（Reason → Plan → Reflect-Plan） | `WAITING_CONFIRMATION` |
| `POST /agent/execute-plan` | A → R（Act → Reflect-Act） | `COMPLETED` / `FAILED` |
| `POST /agent/skip-to-score` | A → R（bypass R-P-R，直接用请求内的 jd/candidate 构造 Plan） | `COMPLETED` / `FAILED` |
| `POST /agent/tasks/{id}/cancel` | 无阶段执行 | `CANCELLED`（仅 `PLANNING`/`WAITING_CONFIRMATION` 可取消） |

**Engine 分层实现**：

```python
class OrchestratorEngine:
    async def run_chat(self, req: AgentChatRequest, db: AsyncSession) -> Task:
        """PENDING → PLANNING → WAITING_CONFIRMATION"""
        # 1. 建 Task（PENDING）
        # 2. 进 PLANNING：Reason → Reflect
        #    - Reflect.is_feasible=false → WAITING_CONFIRMATION with plan=null + blocking_reason
        # 3. Plan → Reflect-Plan
        #    - 若 Reflect-Plan.is_plan_sound=false 且有 adjusted_plan → 用 adjusted_plan
        # 4. 进 WAITING_CONFIRMATION（plan 已定，等 execute-plan）

    async def run_execute(self, task_id, accepted_steps=None, modifications=None, db) -> Task:
        """WAITING_CONFIRMATION → EXECUTING → COMPLETED/FAILED"""
        # 1. TransitionGuard 检查（非 WAITING_CONFIRMATION → 抛 IllegalTransitionError）
        # 2. 应用 accepted_steps + modifications 到 plan
        # 3. run_act(plan, ctx, emit)
        # 4. reflect_act(step_results) → 组装最终 result
        # 5. emit result，进 COMPLETED（或 FAILED）

    async def run_skip_to_score(self, jd_id, candidate_ids, db) -> Task:
        """PENDING → EXECUTING → COMPLETED/FAILED"""
        # 1. 建 Task（PENDING）
        # 2. 手工构造 plan = Plan(steps=[PlanStep(tool_name="jd-candidate-matching", tool_input={jd_id, candidate_id}, ...) for cid in candidate_ids])
        # 3. run_act + reflect_act（同 execute）

    async def run_cancel(self, task_id, db) -> Task:
        """PLANNING/WAITING_CONFIRMATION → CANCELLED"""
        # 1. TransitionGuard 检查（不在两态之一 → 409/IllegalTransitionError）
        # 2. Task.status = CANCELLED
        # 3. 不 emit（cancel 是通过 REST 响应即时反馈，非 SSE）
```

---

## 五、Q4 · Redis 全局活跃计数

### 裁定：**采纳执行体建议 — 抽象接口 + 内存实现**

```python
# backend/app/agent/orchestrator/active_counter.py
from typing import Protocol

class ActiveCounter(Protocol):
    async def incr(self) -> int: ...
    async def decr(self) -> int: ...
    async def current(self) -> int: ...

class InMemoryActiveCounter:
    """PR-12 默认实现；PR-13 后由 RedisActiveCounter 替换。"""
    def __init__(self, limit: int = 10):
        self._count = 0
        self._limit = limit
        self._lock = asyncio.Lock()

    async def incr(self) -> int:
        async with self._lock:
            if self._count >= self._limit:
                raise TaskLimitExceededError(current=self._count, limit=self._limit)
            self._count += 1
            return self._count

    async def decr(self) -> int:
        async with self._lock:
            self._count = max(0, self._count - 1)
            return self._count

    async def current(self) -> int:
        return self._count
```

**决策要点**：
1. 本 PR **不接真实 Redis**，用 `InMemoryActiveCounter`
2. 上限 `limit=10` 从 settings 读（见 Q5）
3. `TaskLimitExceededError` 由 `run_chat` / `run_execute` / `run_skip_to_score` 入口 catch → 转成 HTTP 429（在 PR-14 REST 层完成）
4. Engine 内**必须**在成功进入 EXECUTING 前 `await counter.incr()`，进入终态（COMPLETED/FAILED/CANCELLED）时 `await counter.decr()`——使用 `try/finally` 保证 decr 不漏
5. Redis TTL 决定推迟到 **PR-13**（`RedisActiveCounter` 实现时决定，建议 3600s + 后台 sweeper）

**测试策略**（TC-S5-08-3 并发上限 429）：
```python
counter = InMemoryActiveCounter(limit=2)
engine = OrchestratorEngine(..., active_counter=counter)
# 打满 2 个
await counter.incr(); await counter.incr()
with pytest.raises(TaskLimitExceededError):
    await engine.run_chat(...)
```

---

## 六、Q5 · 超时配置

### 裁定：**采纳执行体建议 — 3 个 settings 字段 + monkeypatch 测试**

**`backend/app/core/config.py` 追加**：

```python
class Settings(BaseSettings):
    # ... 既有字段 ...

    # Stage 5 · PR-12 Orchestrator 超时（秒）
    skill_timeout_sec: float = 120.0
    phase_timeout_sec: float = 180.0
    task_timeout_sec: float = 600.0

    # Stage 5 · PR-12 全局活跃任务上限
    task_active_limit: int = 10
```

**Engine 读取**：

```python
class OrchestratorEngine:
    def __init__(
        self,
        registry: SkillRegistry,
        tool_router: ToolRouter,
        active_counter: ActiveCounter | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.registry = registry
        self.tool_router = tool_router
        self.active_counter = active_counter or InMemoryActiveCounter(
            limit=self.settings.task_active_limit
        )

    async def _run_skill_with_timeout(self, skill, input_data):
        return await asyncio.wait_for(
            skill.execute(input_data),
            timeout=self.settings.skill_timeout_sec,
        )
```

**测试策略**（TC-S5-08-4 Skill 超时）：
```python
def test_tc_s5_08_4_skill_timeout(monkeypatch):
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "skill_timeout_sec", 0.01)
    # 构造一个 sleep 1s 的 mock skill → 触发 TimeoutError
```

**同时应用于 Q6**（构造签名）：`OrchestratorEngine(registry, tool_router, active_counter=None, settings=None)` 为最终构造契约。所有可选依赖走 kwarg + Optional，不散落位置参数。

---

## 七、Q6 · OrchestratorEngine 构造依赖注入

### 裁定：**采纳执行体建议 + 明确必需与可选**

**最终构造契约**：

```python
class OrchestratorEngine:
    def __init__(
        self,
        registry: SkillRegistry,           # 必需（Reason/Reflect/Plan/Reflect-Plan/Reflect-Act 都要 registry.get）
        tool_router: ToolRouter,           # 必需（Act 分派需要）
        active_counter: ActiveCounter | None = None,   # 可选，默认 InMemoryActiveCounter
        settings: Settings | None = None,  # 可选，默认 get_settings()
    ):
        ...
```

**理由**：
- `registry` + `tool_router` 是 Engine 的**核心协作对象**，必须显式注入（便于测试注入 stub）
- `active_counter` + `settings` 是**基础设施**，有合理默认值（便于生产代码 `OrchestratorEngine(registry, tool_router)` 一行构造）
- 不引入 `db` 到 __init__——`db: AsyncSession` 作为**每方法参数**传入（每次请求 session 不同）
- 不引入 `emit`——emit 由 REST 层构造后作为 `run_execute` / `run_skip_to_score` 的方法参数传入

---

## 八、Q7 · TransitionGuard 是否独立模块

### 裁定：**独立文件 `state_machine.py`，纯函数式**

**新增文件 `backend/app/agent/orchestrator/state_machine.py`**：

```python
"""S5-08 · Task 状态机 · 转移矩阵与守卫（纯函数式，与 Engine 解耦）。"""

from app.schemas.agent import TaskStatus

class IllegalTransitionError(Exception):
    def __init__(self, from_status: TaskStatus, to_status: TaskStatus):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Illegal transition: {from_status} → {to_status}")


# 合法转移矩阵（PLAN §2 Q2）
LEGAL_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.PLANNING, TaskStatus.EXECUTING},  # EXECUTING 用于 skip_to_score
    TaskStatus.PLANNING: {TaskStatus.WAITING_CONFIRMATION, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.WAITING_CONFIRMATION: {TaskStatus.EXECUTING, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.EXECUTING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),  # 终态
    TaskStatus.FAILED: set(),      # 终态
    TaskStatus.CANCELLED: set(),   # 终态
}


def check_transition(from_status: TaskStatus, to_status: TaskStatus) -> None:
    """合法性校验；非法转移抛 IllegalTransitionError。"""
    if to_status not in LEGAL_TRANSITIONS.get(from_status, set()):
        raise IllegalTransitionError(from_status, to_status)


class TransitionGuard:
    """轻量类版（供依赖注入测试）；内部委托 check_transition。"""
    def check(self, from_status: TaskStatus, to_status: TaskStatus) -> None:
        check_transition(from_status, to_status)
```

**理由**：
- 状态机是**纯数据 + 纯函数**，独立文件便于单元测试（TC-S5-08-6/7 矩阵参数化）
- `LEGAL_TRANSITIONS` 表格化 → 后续修改状态机只改一处
- Engine 内直接 `check_transition(current, target)`，不必实例化 Guard；Guard 类保留供未来注入不同策略（如"仅记录不阻断"模式）

**转移矩阵关键点**：
- **PENDING → EXECUTING**：允许！这是 `skip_to_score` 的合法路径（bypass R-P-R）
- **WAITING_CONFIRMATION → FAILED**：允许（用户长时间不确认，可能被清理任务标 FAILED）
- **PLANNING → CANCELLED**：允许（Reason/Plan 阶段取消，虽然 chat 端点是同步的，但预留状态机能力）
- **三个终态**（COMPLETED/FAILED/CANCELLED）出度为空——不允许"复活"

---

## 九、生产代码目录与文件清单（PR-12 全部交付物）

```
backend/app/agent/orchestrator/
├── __init__.py                    # 已在 PR-11
├── tool_router.py                 # 已在 PR-11
├── act.py                         # 【本 PR 新增】run_act 纯模块
├── engine.py                      # 【本 PR 新增】OrchestratorEngine
├── state_machine.py               # 【本 PR 新增】LEGAL_TRANSITIONS + check_transition
├── active_counter.py              # 【本 PR 新增】ActiveCounter Protocol + InMemoryActiveCounter
└── errors.py                      # 【本 PR 新增】IllegalTransitionError / TaskLimitExceededError / TaskTimeoutError

backend/app/agent/skills/
├── orchestrator_reason/v1_0_0/    # 【本 PR 新增】internal Skill
│   ├── skill.yaml                 (已 scaffold，本 PR 填 output_schema)
│   ├── prompt.md                  (本 PR 新增)
│   └── examples.yaml              (本 PR 新增)
├── orchestrator_reflect/v1_0_0/   # 【本 PR 新增】internal Skill
├── orchestrator_plan/v1_0_0/      # 【本 PR 新增】internal Skill
├── orchestrator_reflect_plan/v1_0_0/  # 【本 PR 新增】internal Skill
└── orchestrator_reflect_act/v1_0_0/   # 【本 PR 新增】internal Skill

backend/app/core/config.py         # 【本 PR 修改】追加 4 个 settings 字段

backend/tests/                     # 【本 PR 新增】19 用例（红态骨架已提交）
├── test_stage5_s5_05_reason_reflect.py
├── test_stage5_s5_06_plan.py
├── test_stage5_s5_07_act.py
└── test_stage5_s5_08_state_machine.py
```

---

## 十、Commit 拆分建议（红→绿）

红骨架 commit `b8cf1f3` 已存在，转绿链路建议（可根据实际情况精简为 5–7 个 commit）：

```
b8cf1f3  test(stage5): PR-12 red test skeleton (TC-S5-05..08) + skill scaffolds + kickoff questions  ← 已提交
         ↓
C_CFG    feat(stage5): add orchestrator settings (skill/phase/task timeout + active limit)
C_SM     feat(stage5): implement state_machine.py — LEGAL_TRANSITIONS + check_transition + IllegalTransitionError
C_AC     feat(stage5): implement active_counter.py — InMemoryActiveCounter + TaskLimitExceededError
C_ERR    feat(stage5): add errors.py — TaskTimeoutError etc. (若 SM/AC 已含则合并)
C_REA    feat(stage5): implement Reason + Reflect internal skills (S5-05)
C_PLN    feat(stage5): implement Plan + Reflect-Plan internal skills (S5-06)
C_ACT    feat(stage5): implement act.py pure module + emit contract (S5-07)
C_RAC    feat(stage5): implement Reflect-Act internal skill + result assembly (S5-07)
C_ENG    feat(stage5): implement OrchestratorEngine (run_chat/run_execute/run_skip_to_score/run_cancel) (S5-08)
C_TO     feat(stage5): wire timeouts (skill/phase/task) + active counter (S5-08)
```

**精简版建议**（若上面拆得过细）：合并为 **6 个 commit** — 红骨架 + 4 主题 commit + 1 集成 commit：
1. `b8cf1f3` 红骨架（已提交）
2. `C_INFRA` — state_machine + active_counter + errors + settings 一次到位
3. `C_S5-05` — Reason + Reflect Skill
4. `C_S5-06` — Plan + Reflect-Plan Skill
5. `C_S5-07` — act.py + Reflect-Act Skill
6. `C_S5-08` — OrchestratorEngine 集成 + 超时 + 计数

**执行体自主选择** 6-commit 精简版或 10-commit 精细版，历史清晰性优先。

---

## 十一、验收三道门（PR-12）

| 门 | 命令 | 期望 |
|---|---|---|
| 门 1 | `cd backend && uv run pytest tests/test_stage5_s5_0{5,6,7,8}_*.py -q` | **19 passed** |
| 门 2 | `cd backend && uv run pytest -q` | **89 passed**（70 + 19） |
| 门 3 | `cd backend && uv run ruff check app/agent/orchestrator/ app/agent/skills/orchestrator_*/ app/core/config.py` | 0 error |

---

## 十二、求助边界（触发即停）

除本 DECISION 覆盖的 7 问，遇到以下情况**立即停下汇报**：

1. **Reason/Plan prompt 引导 LLM 输出 output_schema 时**，若某字段 LLM 频繁给不出（如 `parsed_entities`），需要 schema 微调
2. **状态机矩阵**中发现 §八 遗漏的合法转移（如 `EXECUTING → CANCELLED` 是否允许——**当前决策不允许**，即 EXECUTING 不可取消，只可等 COMPLETED/FAILED；若测试用例要求"执行中取消"，先问）
3. **超时用 `asyncio.wait_for` 时**触发 `CancelledError` 泄漏（既有 Skill 若不响应取消可能挂住），需要更强的隔离手段
4. **积木组合**：`run_execute` 内如何将 `Reflect-Act.final_result` 组装成 SSE `result` 事件的 `payload` 字段（`api-contract §3` 未固化 result payload 结构），若歧义先问
5. **执行过程中发现某项裁定与实际实现冲突**（如 emit 用 `SSEEvent` dataclass 反而不如 dict 灵活），来问再改，别擅自反着做

**自主决策边界**（不必问）：
- Skill prompt.md 的自然语言表达细节
- examples.yaml 的具体 few-shot 数据
- 内部辅助函数命名
- log 语句的具体措辞与级别

---

## 十三、执行体行动清单

```
1. 阅读本 DECISION（当前文件）
2. 在 feat/pr-12-s5-05-08-orchestrator 分支上：
   a. 更新 5 个 orchestrator_* skill.yaml 的 output_schema（按 §二）
   b. 更新 4 个测试文件 unskip 用例（按 §二 的 output 结构 + §四 的分层设计写断言）
   c. 实现生产代码（按 §九 目录 + §十 commit 拆分）
   d. 三道门验收（按 §十一）
3. Push：sleep 15 && git push -u origin feat/pr-12-s5-05-08-orchestrator
   （SSH port 22 超时按 PR-10/11/15 经验重试）
4. 生成 docs/planning/stage5/PR12-STEP6-REPORT.md（沿用 PR-11/15 STEP6 模板）
5. 汇报"PR-12 已 push + STEP6 报告已就位，待核验放行 FF merge"
```

**开始动工**。裁定覆盖 7 问；遇 §十二 5 种情况**立即停下**，其他自主决策。
