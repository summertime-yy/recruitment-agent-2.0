# 验收请求 — Stage 5 规划与契约写回（PR-9）

> 提交对象：Claude Code 总指挥官（角色定义见 `COMMANDER-BRIEF.md`）
> 提交方：执行体（按 `docs/planning/stage5/REVIEW.md` §6 合并指令产出）
> 日期：2026-07-20
> 状态：待指挥官核验，请求放行（**纯规划 + 契约文档，不含任何代码改动**）

执行体已完成 REVIEW §6 指定的合并动作，产出顶层三份合并版规划文档、契约写回、Skill 契约扩展说明，并归档双盲评审过程。本 PR（PR-9）**仅交付文档与契约**，编码落地在 PR-10..PR-18（见 `TASKS-STAGE5.md` 归属 PR 列）。

## 一、本 PR 改动清单

| 文件 | 变更 | 归属 |
|---|---|---|
| `docs/planning/PLAN-STAGE5.md` | 新增 | 合并版架构 12 决策（含 D4 v2 internal Skill、D2 CANCELLED、D9/D10 DDL/索引裁定） |
| `docs/planning/TASKS-STAGE5.md` | 新增 | 合并版 S5-01..S5-13 × PR-10..PR-18 归属 + 顺手清扫 |
| `docs/planning/TEST-PLAN-STAGE5.md` | 新增 | 合并版 后端 50 / 前端 14 用例（含 CANCELLED / internal / 心跳 / 复合索引 / 500） |
| `docs/planning/ACCEPTANCE-PR9.md` | 新增 | 本验收请求 |
| `docs/api-contract.md` | 写回（42 行） | §3.2 `id`、§3.5 重放/retry:3000/心跳 15s、§3.4 `PlanStep.optional`、§4.4 `CANCELLED`、§4.5 取消端点 |
| `HANDOFF.md` | 1 行 | §Skill 契约 补 `internal: bool` 字段与 `list_dispatchable/get` 语义（D4 v2） |
| `docs/planning/COMMANDER-BRIEF.md` | 40 行 | 附录：双盲评审流程规范（Stage 5 起重大架构决策必用） |
| `docs/planning/stage5/` | 新增目录 | 双盲过程档案（INSTRUCTION + REVIEW + commander/ + executor/），永久保留 |

> 未纳入：工作区杂项 `backend/backend.err`、`call1.txt`、`call2.txt` 与本 PR 无关，不提交。

## 二、验证证据 · 三道门（PR-9 适配）

本 PR 是纯文档 + 契约写回，**不引入任何 `src/` 代码改动**，故三道门调整为「文档/契约一致性」维度：

| 闸门 | 检查项 | 结果 |
|---|---|---|
| 门1 · 文档齐备性 | 顶层 PLAN/TASKS/TEST-PLAN + ACCEPTANCE-PR9 四件套齐全，含 REVIEW §6 全部动作 | ✅ 已产出 |
| 门2 · 契约写回正确性 | `api-contract.md` 7 条扩展（§4 清单）全部落地；Markdown 代码块无破损（修复了 §3.5 误入 §3.4 代码块的 bug）；`HANDOFF.md` `internal` 字段说明到位 | ✅ 已写回、已自检 |
| 门3 · 无代码改动 | `git diff` 不含 `backend/app/**`、`frontend/src/**` 任何业务代码；`alembic` 未 upgrade | ✅ 纯文档 |

## 三、对齐 REVIEW 裁定要点（供快速核验）

- **D1（阻塞已纠正）**：S5-01..S5-13 不再全归 PR-9，已按表映射到 PR-10..PR-18（TASKS「归属 PR」列）。
- **D2**：`TaskStatus` 含 `CANCELLED`，合法转移新增 `PLANNING→CANCELLED`、`WAITING_CONFIRMATION→CANCELLED`；取消经 §4.5 复用 `execute-plan` 传空 `accepted_steps`。
- **D3**：executions 单粒度（每行 = 一次 Skill/工具/LLM 调用），`phase` 字段索引。
- **D4 v2**：5 个 Orchestrator 阶段 = `internal: true` Skill（reason/reflect/plan/reflect_plan/reflect_act），Act 纯模块；`SkillRegistry` 增 `list_dispatchable`/`get`；`HANDOFF.md` 已载。
- **D5/D6/D7**：MVP 不启 Pub/Sub、Act 顺序执行、超时 120/180/600s。
- **D8**：`PlanStep.optional?` 已扩入 `api-contract §3.4`。
- **D9/D10**：tasks 字段按混合表定（删 `request_id/created_by`，加 `started_at/finished_at/current_step`）；复合索引 `idx_tasks_status_created`、`idx_executions_task_created`。

## 四、偏离与待确认项

1. **PR-9 未 push**：按 REVIEW §7「提交 commit（不 push）」执行，待指挥官核验后由指挥官 push 并开 PR-9。
2. **`COMMANDER-BRIEF.md` 双盲流程附录**：非 REVIEW §6.5 列举项，但属 Stage 5 规划基础设施，随本 PR 一并纳入；若指挥官希望单独提交可剥离。
3. **`stage5/` 归档保留**：含 commander/executor 双盲原稿 + REVIEW + INSTRUCTION，按 REVIEW §6.5 永久保留不删。

## 五、请求

请核验并放行：

1. 顶层三文档 + 契约写回是否符合 REVIEW §6 裁定（重点 D1 归属、D4 v2 混合方案、D9/D10 字段与索引）；
2. 三道门（文档齐备 / 契约正确 / 无代码改动）是否认可；
3. 第四节待确认项（不 push、COMMANDER-BRIEF 附录、归档保留）的处理方式。

确认后由指挥官执行 push 与 PR-9 开单。
