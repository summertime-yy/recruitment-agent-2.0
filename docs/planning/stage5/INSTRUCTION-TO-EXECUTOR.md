# 给执行 Agent 的指令 · Stage 5 规划文档独立撰写（PR-9 双盲评审 · 执行体侧）

> 发出日期：2026-07-18
> 发出方：Claude Code 总指挥官
> 承接方：执行 Agent
> 流程：**双盲评审第 2 步** —— 指挥官已独立完成三份规划文档（存于 `docs/planning/stage5/commander/`，你不要打开），现请你在**不参考指挥官版本**的前提下独立产出你的三份规划文档，位置 `docs/planning/stage5/executor/`。

---

## 一、强制约束：本任务只写文档，不写代码

- 允许操作：读代码/文档、写 `docs/planning/stage5/executor/*.md`
- 禁止操作：修改 `backend/app/**` / `frontend/src/**` / 任何迁移脚本；禁止运行 `alembic upgrade`；禁止 `git commit`
- **禁止打开** `docs/planning/stage5/commander/` 目录下任何文件（评审对比时才可读）

违反上述任一项，本 PR-9 双盲流程失效，需从头再来。

---

## 二、任务范围

产出三份规划文档：

1. `docs/planning/stage5/executor/PLAN-STAGE5.md` — Stage 5 架构设计与决策冻结
2. `docs/planning/stage5/executor/TASKS-STAGE5.md` — 逐任务分解（编号 `S5-01`..`S5-NN`）
3. `docs/planning/stage5/executor/TEST-PLAN-STAGE5.md` — 每任务对应的测试用例矩阵

---

## 三、既有约束（不容更改）

以下决策**已在 Stage 0–4 冻结**，你的规划文档必须体现，不得偏离：

### 3.1 LLM 契约
- 所有 Skill 元数据 `max_retries: 0`；`LLMAdapter` 层 `max_retries=0`
- **禁传** `reasoning_effort`（Ark DeepSeek-V4-flash 不支持）
- 温度参数遵循"求稳段低 / 求多样段高"的分段策略，由你决定分层

### 3.2 API 契约来源
- `docs/api-contract.md` §3（SSE 契约）§4（Agent 交互接口）§5（R-P-R-A-R I/O Schema）**是唯一事实源**
- 你必须逐条阅读这三节，并在 PLAN 中标注每个端点/事件对应契约小节
- 若你发现 api-contract 有遗漏（如 SSE `id`/`retry`/心跳未明确），需在 PLAN 中**主动提出补齐条目**并在 PR-9 一并写回 api-contract

### 3.3 数据模型来源
- `docs/data-model.md` §1 通用约定（PK 命名、FK 默认 RESTRICT、时间戳字段等）严格遵循
- Stage 4 迁移 head 为 `e4c1a2b3d4f5`（`add match_scores table`），Stage 5 新迁移必须以此为 `down_revision`
- 新增表：`tasks`、`executions`（`api-contract.md` 已提及，具体 DDL 由你设计）

### 3.3.1 Redis 引入已获指挥官批准（新增约束）
- 指挥官已确认 Stage 5 引入 Redis 作为 SSE 事件缓冲的持久层
- Docker Redis 服务已就绪；后端依赖（`redis[hiredis]`、`fakeredis`）尚未接入，需在 Stage 5 内加
- 你在 PLAN 中回答 §四·问题 6「事件缓冲放哪儿」时，**必须选 Redis 方案**（不用再权衡内存/Redis）
- 但你仍需自主决定：缓冲大小、TTL、Key 命名、Pub-Sub 是否启用、单测用 fakeredis 还是 mock —— 这些让指挥官评审时能看到你的独立取舍

### 3.4 路由顺序教训
- FastAPI 路由声明：**具体路径必须早于参数化路径**（Stage 4 已在多个端点验证）
- Stage 5 有 `GET /agent/tasks/{task_id}/stream` 与 `GET /agent/tasks/{task_id}` 两条同前缀路径，必须谨慎排序

### 3.5 Skill 三件套
- 每个 Skill 目录结构：`backend/app/agent/skills/<snake_case_id>/v<major>_<minor>_<patch>/`
- 每个版本目录内必须含 `skill.yaml + prompt.md + examples.yaml`
- 已注册 Skill 通过 `SkillRegistry` 自动加载（Stage 0 已建）

### 3.6 迁移文件命名
- `<rev>_<snake_case_desc>.py`，`down_revision` 必须显式

### 3.7 三道门标准
- backend `uv run pytest` 全绿
- frontend `npm run test`（Vitest + jsdom + @testing-library/react + msw）全绿
- frontend `npm run lint` 0 error（warning 可讨论）
- frontend `npm run build` exit 0

### 3.8 提交规范
- Conventional Commits，subject ≤ 72 字
- 不 push，仅 commit
- `.uploads/`、`frontend/tsconfig.tsbuildinfo` 已在 `.gitignore` 中

### 3.9 复用要求
- Stage 4 的 `jd-candidate-matching` Skill 必须能被 Stage 5 Orchestrator 直接调用
- Stage 3 的 `resumes.duplicate_of_resume_id`、`resumes.tags` 字段必须被 Stage 5 的 `candidate-merge` / `candidate-profile` Skill 复用

---

## 四、PLAN-STAGE5.md 必须回答的 12 个问题

在你自己的 PLAN 中，用清晰小节回答以下每一个（顺序、命名你自由）：

1. **R-P-R-A-R 五段/六段各自的输入输出契约来自哪里？**（提示：`api-contract.md §5`）你怎样把它们编排成一个 Task 生命周期？
2. **Task 的生命周期状态**有哪些？合法转移矩阵是什么？非法转移如何处理？
3. **Execution 记录粒度**：每次 Skill 调用记一条？每阶段一条？两者都记？
4. **Tool Router 路由策略**：Reason 阶段如何决定 task_type？Plan 阶段如何决定 tool_name？路由是否用二次 LLM？
5. **SSE 事件信封**：如何对齐 `api-contract §3.2`？如何断线重连（`Last-Event-ID` 语义）？心跳频率与重试间隔？
6. **事件缓冲**：SSE 事件放哪儿（内存 / Redis）？多大缓冲？多久 TTL？
7. **并发上限**：单 Task 内 Act 阶段的 Skill 并发是多少？全局同时活跃 Task 上限是多少？超限返回什么码？
8. **超时策略**：单 Skill 多长？单阶段多长？整个 Task 多长？超时后 Task 状态？
9. **失败降级**：单 Skill 失败是否终止 Task？哪些场景直接 FAILED？部分失败如何产出 result？
10. **主键命名与新增 Skill 目录规划**：`tasks.task_id` / `executions.execution_id` 前缀？Orchestrator 阶段是否做成 Skill（若做，命名如何）？
11. **FastAPI 路由声明顺序**：`/agent/tasks/{id}/stream` 与 `/agent/tasks/{id}` 谁先谁后？为什么？
12. **DDL 设计**：`tasks` 和 `executions` 表的完整字段（含类型/约束/索引/CASCADE 策略）

---

## 五、TASKS-STAGE5.md 必须包含

- **任务编号**：`S5-01..S5-NN`，你决定总数（我给的参考区间是 8–14 个）
- **归属 PR**：每任务对应哪个 PR
- **依赖**：明确的前置任务
- **owner**：backend / frontend
- **交付清单**：具体文件路径与关键接口签名
- **验收判据**：至少 3 条可测断言，能被 TEST-PLAN 用例映射
- **测试用例编号**：`TC-S5-<任务号>-<序号>`
- **顺手清扫项**（若有）：Stage 4 遗留（`datetime.utcnow` / MSW stderr / `exhaustive-deps` warning）建议在哪些 PR 内顺手做，你自主决定

**必须覆盖以下能力**（不限任务粒度）：
- tasks/executions 数据层（迁移 + Model + Schema）
- Tool Router
- Orchestrator Engine（R-P-R-A-R 主循环）
- SSE 事件总线与端点
- REST API 四端点（`/agent/chat`、`/agent/execute-plan`、`/agent/skip-to-score`、`/agent/tasks/{id}`）
- `candidate-merge` Skill（C1）
- `candidate-profile` Skill（C2）
- 前端 `ChatCenter.tsx`
- 前端 `CandidateChat.tsx`

---

## 六、TEST-PLAN-STAGE5.md 必须包含

- 每任务映射的测试用例编号（`TC-S5-<任务号>-<序号>`）
- 每用例：一句话意图 + 关键断言
- 覆盖以下维度（不完整视为不合格）：
  - **状态机每条合法转移** 至少 1 例
  - **每条非法转移** 至少 1 例（抛异常）
  - **Tool Router 路由决策**：正例 / 未注册 skill / 参数不匹配 各 ≥1
  - **SSE 事件时序**：包括 `Last-Event-ID` 重放、缓冲滚出、心跳
  - **每个 Orchestrator 阶段 Skill** 至少 1 mock LLM 单测
  - **REST 端点** 状态码矩阵（200/400/404/409/429/500 各 ≥1 处）
  - **前端 SSE 消费**：至少覆盖 6 类事件卡片各 1 例；断线重连 1 例
  - **candidate-merge**：高置信度自动合并 / 低置信度返建议 / 冲突场景 各 ≥1
  - **candidate-profile**：正常生成 / tags 与用户手工标签合并去重 各 ≥1
- 后端新增测试总数目标：**≥40**
- 前端新增测试总数目标：**≥12**

---

## 七、执行流程

1. 打开并逐行读：
   - `docs/api-contract.md` §3–§5
   - `docs/data-model.md` §1 与 §3（了解已建表的字段风格）
   - `docs/planning/COMMANDER-BRIEF.md`（角色与规则）
   - `HANDOFF.md`（Stage 0–4 交付状况）
   - `backend/app/agent/registry.py`、`backend/app/agent/skills/jd_candidate_matching/v1_0_0/skill.yaml`（了解 Skill 三件套怎么写）
   - `backend/app/services/match.py`（了解已有 Service 层的形态）
2. **不要打开** `docs/planning/stage5/commander/` 下任何文件
3. 逐份撰写三文档，中文正文 + 英文标识符
4. 完成后在会话中告知我"执行体版三份规划已就位"，并附一段自评：三份文档最难决策的一处、最没把握的一处、你希望我在评审时特别关注的一处
5. 我会做逐条差异评审，产出 `docs/planning/stage5/REVIEW.md`，双方对齐后合并为顶层 `docs/planning/PLAN-STAGE5.md` / `TASKS-STAGE5.md` / `TEST-PLAN-STAGE5.md`

---

## 八、可选前置：PR-9.pre 一次性清扫（若你愿一并做）

**允许操作**（如你选择先做此项）：
- 删除 `frontend/src/pages/ResumeWorkspace.tsx`（全仓仅自引用，无路由使用，已确认）
- 修订 `docs/development-roadmap.md`：Stage 1–4 状态标注对齐 `HANDOFF.md`
- 在 `HANDOFF.md` 追加一行：`services/resume.py` 中 `raw_text[:3000]` 截断值，Stage 5 前评估是否放宽至 6000–8000（仅记录，不改代码）
- 提交为 `chore: pre-stage5 cleanup — drop legacy page and sync roadmap`

**不允许**：清理 `.uploads/` 目录内容（可能是用户测试文件）；改动 `raw_text[:3000]` 代码（决策未定）；删除 `backend/backend.err` / `call1.txt` / `call2.txt` 之外的任何 untracked 文件。

**注**：C6 `.gitignore` 忽略项目已存在，无需追加。指挥官验证：`git ls-files` 未追踪 `tsconfig.tsbuildinfo` 与 `.uploads/`。

PR-9.pre 是可选顺手项，如果不做，PR-9 主体（三份规划文档）也可独立提交。

---

## 九、时间预算

三份规划文档建议 3–4 小时内完成。若超过 5 小时仍未收束，暂停并向指挥官同步阻塞点。

---

## 十、交付确认清单

完成后你的会话回复必须含：

- [ ] `docs/planning/stage5/executor/PLAN-STAGE5.md` 已产出（回答 §四 全部 12 问）
- [ ] `docs/planning/stage5/executor/TASKS-STAGE5.md` 已产出（覆盖 §五 全部能力）
- [ ] `docs/planning/stage5/executor/TEST-PLAN-STAGE5.md` 已产出（满足 §六 各维度覆盖与总数）
- [ ] 未打开 `docs/planning/stage5/commander/` 下任何文件
- [ ] 未修改任何 src 代码
- [ ] 自评三点（最难决策 / 最没把握 / 请指挥官特别关注）

请开始。

