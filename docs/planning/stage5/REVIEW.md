# Stage 5 双盲评审 · 差异报告与裁定（REVIEW）

> 版本：`review-v1`
> 日期：2026-07-18
> 评审方：Claude Code 总指挥官
> 输入：
> - `docs/planning/stage5/commander/{PLAN,TASKS,TEST-PLAN}-STAGE5.md`
> - `docs/planning/stage5/executor/{PLAN,TASKS,TEST-PLAN}-STAGE5.md`
> 输出：本文件 + 合并后的顶层三文档（后续 PR-9 归档时落地）

---

## 0. 评审摘要（TL;DR）

- ✅ **12 问指挥官均已回答，覆盖度充分**：两版对 R-P-R-A-R I/O、状态机、SSE 信封、Redis 缓冲、路由顺序、DDL 等核心决策**方向一致**，分歧集中在实现取舍。
- ⚠️ **1 项必须纠正的阻塞错误**：执行体版 TASKS 把 S5-01..S5-13 全部归属 `PR-9`，误解了 PR-9 只交付**规划文档**的边界。需重新映射到 PR-10..PR-18（见下文 §2·D1）。
- 🔀 **10 处实质差异需裁定**：**采用指挥官版 3 处、采用执行体版 4 处、混合 3 处**。其中 D4 经指挥官二次质询后**从"采用执行体版"修订为"Skill 化 + `internal: true` 隔离"混合方案**，保持 Skill 框架解耦哲学。
- 📎 **1 项新契约扩展**：执行体引入 `PlanStep.optional` 字段。同意扩，需在 PR-9 一并写回 `api-contract.md §3.4`。
- 📎 **1 项 Skill 契约扩展**：`skill.yaml` 增 `internal: bool` 字段（默认 false，向后兼容）；需在 `docs/dev-standards-and-lessons.md` 或 `HANDOFF.md §Skill 契约` 注明。
- 📊 **测试用例总数**：指挥官 62+/11，执行体 46/12+。两版均达标；合并版按执行体的分组结构 + 补充指挥官的转移矩阵参数化用例 + 补 internal Skill 隔离测试。

---

## 1. 12 问逐条对照

| # | 问题 | 指挥官版 | 执行体版 | 是否分歧 |
|---|---|---|---|---|
| Q1 | R-P-R-A-R 生命周期编排 | 六段 + 状态机分层 | 六段 + 生命周期图示 | 无（表述不同，语义一致） |
| Q2 | Task 状态集合 | 7 个（含 CANCELLED） | 6 个（**缺 CANCELLED**） | ⚠️ 见 D2 |
| Q3 | Execution 粒度 | 双粒度（阶段+Skill 各一条） | 单粒度（每 Skill 一条，phase 作字段聚合） | 🔀 见 D3 |
| Q4 | Tool Router | 双层（意图 LLM+工具校验），不二次 LLM | 主 LLM 结构化输出，Router 仅校验分发 | 无（实质一致） |
| Q5 | SSE 信封 & 心跳 | 补 `id`/`retry`/心跳 15s | 补 `id`/`retry:3000`/心跳 15s + 列 PR-9 写回条目 | 无（执行体更细） |
| Q6 | 事件缓冲（Redis） | 200 / 30min TTL / **启用** Pub-Sub | 200 / 60min TTL / **MVP 不启用** Pub-Sub | 🔀 见 D5 |
| Q7 | 并发上限 | 单 Task Act 并发 = 2；全局 10 | 单 Task Act **= 1 顺序**；全局 10 | 🔀 见 D6 |
| Q8 | 超时策略 | Skill 60s / 阶段 120s / Task 600s | Skill 120s / 阶段 180s / Task 600s | 🔀 见 D7 |
| Q9 | 失败降级 | 依 `dependencies` 决定 | 引入 `PlanStep.optional` 字段区分 | 🔀 见 D8 |
| Q10 | 主键 & Orchestrator 阶段是否做成 Skill | Skill 化（5 个新 Skill） | **纯 Python 模块**（不注册为 Skill） | 🔀 见 D4 **关键分叉** |
| Q11 | FastAPI 路由顺序 | `/stream` 先 `/{id}` | `/stream` 先 `/{id}` + 额外解释 FastAPI 段匹配语义 | 无（执行体更准确） |
| Q12 | DDL | 精简字段 + 复合索引 | 完善字段 + 单列索引 | 🔀 见 D9/D10 |

---

## 2. 10 处实质差异与裁定

### D1 · TASKS 全部归属 PR-9 · ⛔ **阻塞错误 · 必须纠正**

| 维度 | 指挥官版 | 执行体版 |
|---|---|---|
| PR 边界 | PR-9 = 规划文档；编码分 PR-10..PR-18 共 9 PR | **全部 S5-01..S5-13 归属 PR-9** |

**评审意见**：执行体在 TASKS 第 4 行写"全部任务归属 PR-9（Stage 5）"，误解了 PR-9 的作用。INSTRUCTION §二明确 PR-9 交付物是三份规划文档；`ACCEPTANCE-PR8.md` 前例也表明每个 PR 是一个交付批次。若 13 个任务塞一个 PR，代码量将超过 3000 行，无法逐 PR 三道门验证，直接违背 COMMANDER-BRIEF 的 TDD 与验收纪律。

**裁定**：**采用指挥官 PR 拆分方案**。合并版按下表映射：

| 执行体任务 | 归属 PR | 说明 |
|---|---|---|
| S5-01 数据层 | PR-10 | Redis 依赖前置接入并入本 PR |
| S5-02 Schema | PR-10 | 与 S5-01 同 PR |
| S5-03 EventBuffer | PR-13 | 应用启动挂 `app.state.redis` 亦在此 PR |
| S5-04 Tool Router | PR-11 | |
| S5-05 Reason+Reflect | PR-12 | R-P-R-A-R 主循环合入一个 PR |
| S5-06 Plan+ReflectPlan | PR-12 | 同上 |
| S5-07 Act+ReflectAct+SSE 发射 | PR-12/PR-13 | Act 主循环在 PR-12；发射到 Redis 在 PR-13 |
| S5-08 状态机/并发/超时 | PR-12 | 归入 Engine 内 |
| S5-09 REST + SSE 端点 | PR-14 | |
| S5-10 candidate-merge | PR-15 | 可与 PR-12/13 并行 |
| S5-11 candidate-profile | PR-16 | 可与 PR-15 并行 |
| S5-12 前端类型+Hook | PR-17 | |
| S5-13 前端 ChatCenter+CandidateChat | PR-17（合入） / PR-18（拆分） | 若一起做则 PR-17，若拆则 PR-18 |

**动作**：合并版 TASKS 每任务加"归属 PR"列，覆盖执行体版的"PR-9"。

---

### D2 · Task 状态是否包含 CANCELLED · ✅ **采用指挥官版**

| 维度 | 指挥官版 | 执行体版 |
|---|---|---|
| 状态集合 | 7 个（含 `CANCELLED`） | 6 个（**无 `CANCELLED`**） |
| 触发场景 | 用户在 `WAITING_CONFIRMATION` 显式取消 | 无覆盖 |

**评审意见**：`api-contract.md §4.4` 定义的 `TaskStatus` 枚举确实**未列 CANCELLED**，从字面看执行体版本合规。但用户在 Plan 确认页点"取消"是**真实场景**（Plan 生成后用户不想执行）。若无 CANCELLED，只能强转 `FAILED` + `error_code='USER_CANCELLED'`，语义污染。

**裁定**：**加 CANCELLED，同步扩 `api-contract.md §4.4`**。合并版：
- 状态集合：`PENDING / PLANNING / WAITING_CONFIRMATION / EXECUTING / COMPLETED / FAILED / CANCELLED`
- 合法转移增：`WAITING_CONFIRMATION → CANCELLED`、`PLANNING → CANCELLED`
- api-contract §4.4 写回：`TaskStatus` 枚举补 CANCELLED
- 新增 REST：`POST /agent/tasks/{task_id}/cancel`（可选，若前端仅从 `WAITING_CONFIRMATION` 触发，也可复用现有 `execute-plan` 传空 `accepted_steps`——建议后者，更简）
- 测试：合并版 TEST-PLAN 加 `TC-S5-08-6` 覆盖取消转移（原 `TC-S5-08-6` 编号后移）

---

### D3 · Execution 粒度 · ✅ **采用执行体版**

| 维度 | 指挥官版 | 执行体版 |
|---|---|---|
| 粒度 | 每阶段一条 + 每 Skill 一条（双写） | 每次 Skill/工具调用一条，`phase` 字段索引 |
| 阶段视图 | 直接查 phase 记录 | 通过 `SELECT ... WHERE phase='REASON'` 聚合 |

**评审意见**：执行体方案避免了同一事实的双写，`phase` 字段既能索引又能聚合出阶段视图。指挥官方案的"双粒度"实际上是冗余——`REASON` 阶段本身就是一次 LLM 调用，没有额外"阶段包装记录"的必要。

**裁定**：**采用执行体版单粒度**。合并版：
- executions 表每行 = 一次 Skill/工具/LLM 调用
- `phase` 字段（`REASON/REFLECT/PLAN/REFLECT_PLAN/ACT/REFLECT_ACT`）必填、加索引
- 移除指挥官版的"阶段级独立 execution 记录"

---

### D4 · Orchestrator 5 阶段是否做成 Skill · 🔀 **修订裁定 v2 · Skill 化 + `internal: true` 隔离**

> **裁定修订说明**：初版 REVIEW 采用执行体的"纯 Python 模块"方案，被指挥官（用户）在评审后质询："这与 Skill 框架解耦可扩展的原始设计是否相悖？以后想改 Skill 化怎么办？"。经复核，确实相悖 —— Skill 框架的核心哲学是"每一次 LLM 驱动的能力都是一个 Skill，走统一 BaseSkill 管道"。执行体"污染 Registry"的担忧是真实的，但解法应是**加隔离字段**，不是"不做 Skill"。原裁定撤回。

| 维度 | 指挥官版 v1 | 执行体版 | **修订裁定 v2** |
|---|---|---|---|
| 实现形态 | 5 个 Skill 全公开 | 5 个纯 Python 模块 | **5 个 Skill + `internal: true` 隔离** |
| 是否走 BaseSkill 管道 | 是 | 否（裸 LLMAdapter） | **是** |
| 是否被 Tool Router 分发 | 是（污染 Registry） | 否（因为不是 Skill） | **否**（`list_dispatchable` 过滤 internal） |
| Prompt 独立 semver | 支持 | 不支持 | **支持** |
| 执行日志写 skill_execution_logs | 是 | 否（双系统） | **是** |

**为什么撤回执行体版**：
1. Skill 框架 5 大收益（Prompt semver / 输入输出 Schema 校验 / 统一日志 / A/B 测试 / compliance check）对 Orchestrator 阶段**每一项都有价值**
2. 纯 Python 模块方案会在项目里养出两套并行的 LLM 调用体系，**与 Stage 0 架构决心相悖**
3. "以后再改 Skill 化"的迁移成本约 2 个工作日（Prompt 搬迁 + BaseSkill 包装 + 所有调用点改造 + 测试重写 + 过渡态回归），**远高于现在一次做对**

**为什么不采纳指挥官版 v1**：
- 执行体的"污染 SkillRegistry"担忧真实：若不加隔离，`list_by_task_type()` 会列出 5 个"不会被调用"的 orchestrator_* Skill，误导用户和 LLM
- 解法是加 `internal: true` 字段 + 分层查询方法

**修订裁定细则**：

1. **Orchestrator 5 阶段 = 5 个 internal Skill**（Act 阶段不是 LLM 调用，仍是纯 Python 模块）：
   ```
   backend/app/agent/skills/orchestrator_reason/v1_0_0/
   backend/app/agent/skills/orchestrator_reflect/v1_0_0/
   backend/app/agent/skills/orchestrator_plan/v1_0_0/
   backend/app/agent/skills/orchestrator_reflect_plan/v1_0_0/
   backend/app/agent/skills/orchestrator_reflect_act/v1_0_0/
   backend/app/agent/orchestrator/act.py     # ← 纯模块，循环调 ToolRouter.dispatch()
   backend/app/agent/orchestrator/engine.py  # ← 状态机 + 编排
   ```

2. **`skill.yaml` 新增字段** `internal: bool`（默认 `false`，向后兼容）：
   ```yaml
   skill_id: orchestrator-reason
   version: "1.0.0"
   internal: true
   task_types: []
   description: R-P-R-A-R 循环内部 Reason 阶段，不对外暴露
   ```

3. **`SkillRegistry` 扩展方法**：
   - `get(skill_id)` — 全量查询，供 Orchestrator engine 内部调用
   - `list_dispatchable(task_type: str | None = None)` — 过滤 `internal=true`，供 Tool Router 使用
   - `list_by_task_type()` 隐式使用 `list_dispatchable`

4. **代码路径**：Orchestrator engine 内直接
   ```python
   skill = registry.get('orchestrator-reason')
   result = await skill.execute(input_data, session=db)
   ```
   走完整 BaseSkill 管道（含 compliance check、日志落 `skill_execution_logs`）。

5. **Tool Router 强化校验**：`dispatch(step)` 若命中 `internal=true` 的 Skill，抛 `SkillNotDispatchableError`（防止 LLM 生成的 Plan 意外引用 internal Skill）。

**连带修订**（合并版三文档需同步）：

| 文档 | 位置 | 修订 |
|---|---|---|
| PLAN §2 Q10 | Orchestrator 阶段实现形态 | 改为"5 internal Skill + Act 纯模块" |
| PLAN §2 Q4 | Tool Router 路由策略 | 明确"仅从 `list_dispatchable` 结果集里路由" |
| TASKS S5-02 | SkillRegistry 扩展 | 加"`internal` 字段 + `list_dispatchable` 方法 + `get` 全量查询" |
| TASKS S5-05/06 | 交付清单 | 从"reason.py/plan.py 模块"改为"5 个 orchestrator_* Skill 三件套 + engine.py 状态机" |
| TASKS S5-07 | 交付清单 | Act 部分保持纯模块，`orchestrator_reflect_act` 是 Skill |
| TEST-PLAN | S5-02 | 加 `TC-S5-02-4` `test_internal_skill_excluded_from_dispatchable` |
| TEST-PLAN | S5-04 | 加 `TC-S5-04-6` `test_router_refuses_internal_skill` |
| TEST-PLAN | S5-05/06/07 | Mock 目标从模块函数改为 `BaseSkill.execute` |

**为未来铺路**：若后续需要 A/B 测试 Reason prompt，只需新建 `orchestrator_reason/v1_1_0/`，在 config 里切换版本号，无代码改动。这正是 Skill 框架的核心价值。

---

### D5 · Redis Pub/Sub 是否启用 · ✅ **采用执行体版**

| 维度 | 指挥官版 | 执行体版 |
|---|---|---|
| Pub/Sub | 启用，通道 `sse:task:<task_id>:pub` | **MVP 不启用**（单实例够用），多副本时再启 |
| TTL | 30min | 60min（终态后） |

**评审意见**：
- Pub/Sub：MVP 单实例部署下确实不需要。SSE 端点直接从 Redis List `sse:buf:<task_id>` 轮询/长轮询即可。指挥官版是"多副本部署前瞻"，但 Stage 5 明确单实例，YAGNI。
- TTL：60min 更保守，用户可能刷新页面回看任务结果。30min 太紧。

**裁定**：**采用执行体版**。合并版：
- 仅用 Redis List 做缓冲，不启 Pub/Sub
- TTL：任务进入终态后 60min 过期，进行中不过期
- 多副本 Pub/Sub 记为 Stage 5.1 开放项

---

### D6 · Act 步骤并发度 · ✅ **采用执行体版**

| 维度 | 指挥官版 | 执行体版 |
|---|---|---|
| 单 Task Act 并发 | `Semaphore(2)` | **1（顺序执行）**，依赖 `PlanStep.dependencies` |

**评审意见**：MVP 阶段步骤并行的风险大于收益：
- 依赖竞态：Skill A 与 Skill B 若共享上下文（如 `resume.tags` 写入），并行会互踩
- Ark 限流：Stage 4 已用并发 4，Stage 5 每 step 是 LLM 调用，串行更稳
- 用户体验：顺序执行的 tool_call → progress → result 事件序列更清晰

**裁定**：**采用执行体版顺序执行**。合并版：
- Act 阶段 for step in plan.steps 顺序调用（异步 `await`，非并发）
- 并行优化留到 Stage 5.1 或 Stage 6

---

### D7 · 超时阈值 · ✅ **采用执行体版**

| 维度 | 指挥官版 | 执行体版 |
|---|---|---|
| 单 Skill | 60s | 120s |
| 单阶段 | 120s | 180s |
| Task 总时长 | 600s | 600s |

**评审意见**：Stage 4 已观察到 Ark DeepSeek-V4-flash 单次调用 30–60s 抖动常见，60s 阈值容易误杀。执行体的 120/180/600 三层更贴实际。Task 总 600s 一致。

**裁定**：**采用执行体版**。合并版沿用 120/180/600。

---

### D8 · PlanStep.optional 字段 · ✅ **采用执行体版，需扩 api-contract §3.4**

| 维度 | 指挥官版 | 执行体版 |
|---|---|---|
| 可选步骤识别 | 依 `PlanStep.dependencies` 拓扑 | 显式 `PlanStep.optional: boolean` |
| 失败行为 | 依赖失败 → 下游跳过 | optional 失败 → warning + 继续；required 失败 → error + FAILED |

**评审意见**：执行体的 `optional` 字段语义更直观。但当前 `api-contract §3.4` 的 `PlanStep` 未定义此字段。需扩：
```typescript
interface PlanStep {
  step_id: string;
  description: string;
  tool_name: string;
  params: Record<string, any>;
  expected_output: string;
  dependencies?: string[];
  optional?: boolean;            // ← 新增
  estimated_duration_seconds?: number;
}
```

**裁定**：**采用 + 扩契约**。合并版：
- api-contract §3.4 补 `optional?: boolean` 字段
- Orchestrator 生成 Plan 时，`optional` 默认 `false`
- Reflect-Plan 阶段可修正 `optional`（LLM 输出建议）

---

### D9 · DDL 字段（tasks 表） · 🔀 **混合方案**

| 字段 | 指挥官版 | 执行体版 | 裁定 |
|---|---|---|---|
| `task_id` | ✓ | ✓ | 保留 |
| `user_message` | ✓ | ✓ | 保留 |
| `context_json` / `context` | ✓（`context_json`） | ✓（`context`） | 用 `context`（简短） |
| `status` | ✓ | ✓ | 保留（含 CANCELLED，D2） |
| `task_type` | ✓ | ✓ | 保留 |
| `plan_json` / `plan` | ✓ | ✓ | 用 `plan` |
| `result_json` / `result` | ✓ | ✓ | 用 `result` |
| `error_code + error_message` | 分两字段 | 单 `error` JSON | **用执行体的 `error` JSON**（前端反正一起用） |
| `current_step` | ✗ | ✓ | **保留**（前端展示"进行中步骤"） |
| `request_id` | ✗ | ✓ | **删除**（Stage 5 未实现 REST 统一信封） |
| `created_by` | ✗ | ✓ | **删除**（当前无认证，YAGNI） |
| `started_at` | ✓ | ✗ | **保留**（Q8 超时判定依赖） |
| `finished_at` | ✓ | ✗ | **保留**（Q8 超时判定依赖） |
| `created_at / updated_at` | ✓ | ✓ | 保留 |

**评审意见**：
- 执行体的 `error` JSON 打包更符合前端消费习惯（一次序列化）
- `request_id/created_by` 执行体过度设计，Stage 5 用不上，删除
- `started_at/finished_at` 是 Task 生命周期审计的关键字段，必须有
- `current_step` 是前端"进行中"UI 展示的关键

**裁定**：合并版 tasks 表字段最终定为：
```
task_id, user_message, task_type, status, plan, context, result,
error, current_step, started_at, finished_at, created_at, updated_at
```

---

### D10 · 索引策略 · ✅ **采用指挥官版复合索引**

| 索引 | 指挥官版 | 执行体版 |
|---|---|---|
| tasks | `(status, created_at DESC)` 单复合索引 | `(status)` + `(created_at DESC)` 双单列 |
| executions | `(task_id, created_at ASC)` 单复合 | `(task_id)` + `(step_id)` + `(phase)` 三单列 |

**评审意见**：
- **tasks 查询模式**：`WHERE status='EXECUTING' ORDER BY created_at DESC LIMIT N` 是最高频（前端任务列表按状态过滤 + 时间排序）。复合索引 `(status, created_at DESC)` 直接命中；单列索引则需两阶段过滤 + 排序，性能差 3-5 倍。
- **executions 查询模式**：主要按 `task_id + created_at` 拉取某 task 的全部 execution 时间线。复合索引更优。执行体的 `(phase)` 单列索引意义不大（phase 只 6 种，选择性差，索引起不到作用）。

**裁定**：**采用指挥官版复合索引**。合并版：
- `idx_tasks_status_created (status, created_at DESC)`
- `idx_executions_task_created (task_id, created_at ASC)`
- 保留执行体的 `idx_executions_step_id (step_id)` 作为可选（若 step_id 查询高频）

---

## 3. 未列入 D1..D10 的小差异

| 项 | 说明 | 处置 |
|---|---|---|
| 执行体 TASKS 拆到 13 个（Reason+Reflect / Plan+ReflectPlan / Act+ReflectAct 三段独立） | 指挥官只列 12 个 | **采用执行体拆分**，更细粒度便于 PR 内 TDD |
| 执行体加了 executions 的 `validation_score` 字段 | 指挥官未列 | **删除**（当前 BaseSkill 无 validation_score 输出） |
| 执行体 executions 的 `execution_status` 值域 `SUCCESS/FAILED/FALLBACK/HUMAN_HANDOFF` | 指挥官用 `COMPLETED/FAILED/SKIPPED` | **采用指挥官 `COMPLETED/FAILED/SKIPPED`**，与 Stage 4 `skill_execution_logs.status` 对齐 |
| 执行体识别到 `datetime.utcnow()` 时区问题 | 指挥官已在顺手清扫单独列 | 一致，落 PR-10 |
| 执行体 SSE 内置工具白名单 `search_resumes` / `read_jd` | 指挥官未提 | **接受**，作为 Router 分发的第二类目标；测试补 `TC-S5-04-3` |
| 执行体没提"心跳频率单测"（S5-06 心跳） | 指挥官 `TC-S5-06-08` 有 | 合并版补 |
| 执行体路由声明理解更准确（FastAPI 段匹配语义） | 指挥官简化 | 合并版按执行体的解释写 |

---

## 4. 契约扩展清单（PR-9 一并写回 `docs/api-contract.md` 与 Skill 规范）

评审通过的契约扩展点，需在 PR-9 交付时同步写入：

| # | 位置 | 扩展内容 | 来源 |
|---|---|---|---|
| 1 | api-contract §3.2 SSE 信封 | 加 `id: string` 字段（任务内单调递增） | 两版共识 |
| 2 | api-contract §3.3 事件类型表 | 补 `system` 事件兼作心跳的说明 | 执行体版 |
| 3 | api-contract §3（新增小节 §3.5） | SSE 重放与心跳细则：`Last-Event-ID` 语义、`retry:3000ms`、心跳 15s、缓冲滚动提示 | 执行体版 |
| 4 | api-contract §3.4 PlanStep | 加 `optional?: boolean` 字段 | 执行体版（D8） |
| 5 | api-contract §4.4 TaskStatus | 加 `CANCELLED` 枚举 | 指挥官版（D2） |
| 6 | api-contract §4（新增小节 §4.5） | `POST /agent/tasks/{task_id}/cancel` 或说明"复用 execute-plan 传空 accepted_steps 实现取消" | 指挥官版（D2）|
| 7 | Skill 契约（dev-standards 或 HANDOFF §Skill 契约） | `skill.yaml` 加可选字段 `internal: bool`（默认 false）；SkillRegistry 新增 `list_dispatchable()` 与 `get()` 语义 | D4 v2 修订 |

---

## 5. 合并后顶层文档清单

评审对齐后，产出以下**最终冻结版本**（PR-9 交付物）：

```
docs/planning/
├── PLAN-STAGE5.md             ← 合并版：架构 12 决策
├── TASKS-STAGE5.md            ← 合并版：S5-01..S5-13 × PR-10..PR-18 归属
├── TEST-PLAN-STAGE5.md        ← 合并版：后端 ~50 / 前端 ~14 用例
├── ACCEPTANCE-PR9.md          ← PR-9 验收请求（执行体产出）
└── stage5/                    ← 双盲评审过程档案（保留归档）
    ├── INSTRUCTION-TO-EXECUTOR.md
    ├── REVIEW.md              ← 本文件
    ├── commander/{PLAN,TASKS,TEST-PLAN}-STAGE5.md
    └── executor/{PLAN,TASKS,TEST-PLAN}-STAGE5.md
```

**归档目的**：`stage5/` 目录保留双盲评审过程，供后续 Stage 6/7 借鉴此流程；顶层三份是唯一事实源。

---

## 6. 给执行 Agent 的合并指令（下一步动作）

请执行体按以下动作产出**合并版**三份顶层文档（本次仍是纯文档，不写代码）：

### 6.1 PLAN-STAGE5.md 合并版

基础：以你执行体版为骨架（回答 12 问的结构较清晰），按以下修改：

- **§2 Q2**：`Task 状态集合`加 `CANCELLED`，合法转移矩阵补两条：`PLANNING → CANCELLED`、`WAITING_CONFIRMATION → CANCELLED`
- **§2 Q4**：Tool Router 明确"仅从 `list_dispatchable()` 结果集里路由，命中 `internal=true` 的 Skill 抛 `SkillNotDispatchableError`"
- **§2 Q6**：TTL 保持 60min；确认"MVP 不启用 Pub/Sub"
- **§2 Q10 · 重要修订**：撤回"纯 Python 模块"决策，改为 **"5 个 orchestrator_* Skill（internal: true）+ Act 纯模块 + engine.py 状态机"**（详细规范见 REVIEW §2·D4 v2）
- **§2 Q12 tasks 表**：按 D9 表格调整字段（删 `request_id/created_by`，加 `started_at/finished_at/current_step`）
- **§2 Q12 索引**：改为复合索引 `idx_tasks_status_created`、`idx_executions_task_created`
- **§2 Q12 executions 表**：`execution_status` 值域改为 `COMPLETED/FAILED/SKIPPED`；删除 `validation_score`
- **§3 契约写回**：按本文 §4 七条契约扩展清单完整列出（含 Skill 契约扩展 `internal` 字段）

### 6.2 TASKS-STAGE5.md 合并版

基础：以你执行体版 13 任务分组为骨架，按以下修改：

- **表头加"归属 PR"列**：按本文 §2·D1 表填 PR-10..PR-18
- **每任务加"顺手清扫"标注**：把 §五 顺手清扫的四项分配到对应 PR 的"顺手项"字段
- **S5-02 交付**：SkillRegistry 扩展加 `internal` 字段解析 + `list_dispatchable()` + `get()` 全量查询三处
- **S5-05 交付**：从"reason.py 模块"改为"`orchestrator_reason/v1_0_0/{skill.yaml,prompt.md,examples.yaml}` + `orchestrator_reflect/v1_0_0/*`"；`skill.yaml` 均含 `internal: true`
- **S5-06 交付**：同上，两个 Skill：`orchestrator_plan`、`orchestrator_reflect_plan`
- **S5-07 交付**：`orchestrator_reflect_act` 是 Skill；Act 主循环仍为 `orchestrator/act.py` 纯模块（负责 for-loop 调 `ToolRouter.dispatch()`）
- **S5-08 交付**：`TransitionGuard` 覆盖 CANCELLED 转移；`engine.py` 直接 `registry.get('orchestrator-reason').execute(...)` 调用各阶段 Skill
- **S5-09 交付**：加 `POST /agent/tasks/{task_id}/cancel`（或说明"通过 execute-plan 传空实现取消"，选后者更简）
- **PR-9 单独一节**："PR-9 交付物 = PLAN/TASKS/TEST-PLAN 三份顶层文档 + ACCEPTANCE-PR9.md + `api-contract.md` 契约写回 + Skill 契约 `internal` 字段说明"，与 S5-* 编码任务分离

### 6.3 TEST-PLAN-STAGE5.md 合并版

基础：以你执行体版 46/12 为基础，按以下修改：

- 加 CANCELLED 相关用例：`TC-S5-08-8` `test_cancelled_transition_from_waiting_confirmation`
- 加 internal Skill 隔离用例：`TC-S5-02-4` `test_internal_skill_excluded_from_dispatchable`
- 加 Tool Router 拒 internal 用例：`TC-S5-04-6` `test_router_refuses_internal_skill`
- 加心跳频率参数化用例：`TC-S5-03-5` `test_heartbeat_every_15s`（用 freezegun 或 fakeredis time travel）
- 加复合索引验证（可选）：`TC-S5-01-4` `test_composite_index_exists`
- 前端补 CANCELLED 提示卡片：`TC-S5-13-9` `test_cancelled_task_shows_cancelled_ui`
- 覆盖矩阵中的 `500` 状态码：加 `TC-S5-09-6` `test_orchestrator_unhandled_exception_returns_500`（mock engine raise）
- **S5-05/06/07 mock 目标调整**：从 mock 模块函数改为 mock `BaseSkill.execute` 或注入桩 Skill
- 保留你原有的"覆盖维度核对"表并按合并版更新

### 6.4 契约同步

**同步写回 `docs/api-contract.md`**（按本文 §4 的 6 条）—— 这是 PR-9 交付物的一部分，不是 PR-10+ 的动作。

### 6.5 交付确认清单

完成后你的会话回复必须含：

- [ ] 顶层 `docs/planning/PLAN-STAGE5.md` 已产出（合并版）
- [ ] 顶层 `docs/planning/TASKS-STAGE5.md` 已产出（合并版）
- [ ] 顶层 `docs/planning/TEST-PLAN-STAGE5.md` 已产出（合并版）
- [ ] `docs/api-contract.md` 已按 §4 六条契约扩展写回
- [ ] `docs/planning/ACCEPTANCE-PR9.md` 已产出（简短，含三道门检查项列表）
- [ ] `docs/planning/stage5/{commander,executor}/` 目录**保留不删**（作为过程档案）

---

## 7. 评审结论

- ✅ 执行体版整体质量高，10 处实质差异中我采纳执行体 4 处、指挥官 3 处、混合 3 处
- ⛔ 唯一阻塞项 D1（PR 全部塞 PR-9）必须纠正
- 🔀 D4 经指挥官二次质询后修订为"Skill 化 + `internal` 隔离"混合方案，保持 Skill 框架的核心解耦哲学；本次修订是双盲流程之后的**第三方复核**，说明"评审也需要被评审"
- ✅ 双盲流程有效：执行体独立识别到"MVP 不启用 Pub/Sub"、"Act 顺序执行更安全"、"引入 PlanStep.optional 字段"等更贴 MVP 的判断；同时指挥官在 D4 保守裁定后经用户质询回到 Skill 化路径，双方对齐
- 📎 PR-9 交付准备就绪：合并版三文档 + api-contract 写回 + Skill 契约扩展 + ACCEPTANCE-PR9 一次性完成，即可提交 commit（不 push）

**放行合并动作**。请执行体按 §6 指令产出合并版并提请下一轮验收。
