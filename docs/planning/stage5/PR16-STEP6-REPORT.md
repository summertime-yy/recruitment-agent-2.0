# PR-16 · STEP6 完成回报（S5-11 candidate-profile Skill）

> 生成时间：2026-07-22
> 关联裁定：`docs/planning/stage5/PR16-KICKOFF-DECISION.md`
> 分支：`feat/pr-16-s5-11-candidate-profile`（基于 master `bc6c2f2`）
> 状态：✅ 已实现 + 已本地验证三道门全绿；**分支待推送，依 DECISION §十四 阶段5 回报指挥官 FF-merge 评审（本执行体不做自动 FF-merge）**

## 一、概要

PR-16 交付 S5-11 `candidate-profile` 孤立 Skill 三件套 + 单元测试 + engine 数据型 artifact 出口补齐（Q5 方案 C，含 `candidate_merge` 一并归零）。

- 与 PR-15（`candidate-merge`）**完全对称**：纯 Skill 交付，无端到端路由，无落库副作用。
- 交付后 `candidate-profile` 与 PR-15 的 `candidate-merge` 一样是**孤立 Skill**：只能经 REST 硬编码 plan 或前端手工拼装 plan 触发，**无法被用户自然语言消息触发**（追债项 11，Stage 5.1 收敛）。
- 范围严格守在 DECISION §二 硬边界内，未触碰 reason/plan skill、未改 `tasks.task_type` 字面量、未改 TASKS 文档、未加落库副作用（§十三 9 条求助边界**零触发**）。

## 二、完成清单

| 项 | 状态 | 说明 |
|----|------|------|
| `candidate_profile/v1_0_0/skill.yaml` | ✅ | `skill_id: candidate-profile`（连字符）/ `task_type: profile_candidate`（下划线）/ `version: "1.0.0"` / `max_retries: 0` / input `{parsed_content: object, existing_tags: string[]}`（不设 `minProperties`）/ output 四字段必填 / `prompt: prompt.md` `examples: examples.yaml` |
| `candidate_profile/v1_0_0/prompt.md` | ✅ | SYSTEM_PROMPT（资深画像分析师 + 合规约束）+ USER_TEMPLATE（四字段强约束 + 归一去重指令 + 空 parsed_content 规则） |
| `candidate_profile/v1_0_0/examples.yaml` | ✅ | 3 个 few-shot：正常生成 / 与 existing_tags 合并去重 / 空 parsed_content |
| `tests/test_stage5_s5_11_candidate_profile.py` | ✅ | TC-S5-11-1..4（Skill 契约）+ `test_build_artifacts_data_types_preserve_type`（engine 数据型 artifact） |
| `engine.py::_build_artifacts` 数据型分支 | ✅ | Q5 方案 C：`elif artifact_type in {"candidate_merge", "candidate_profile"}: item["data"] = output`（保留 type 不降级、无 ref_id） |

## 三、验收三道门（对照 DECISION §十六）

| 门 | 命令 | 期望 | 实际 |
|----|------|------|------|
| 门 1 · pytest | `cd backend && uv run pytest -q` | ≥ 114 passed（0 failed / 0 error） | ✅ **115 passed** |
| 门 2 · ruff lint | `cd backend && uv run ruff check app` | 0 error | ✅ **All checks passed!** |
| 门 3 · ruff format | `cd backend && uv run ruff format --check app` | 0 diff | ✅ **51 files already formatted** |

门 1 明细（新增 5 用例 = 4 Skill + 1 engine，110 基线 → 115）：

```
uv run pytest -q
........................................................................ [ 62%]
...........................................                              [100%]
115 passed in 5.52s
```

门 2 明细：`uv run ruff check app` → `All checks passed!`
门 3 明细：`uv run ruff format --check app` → `51 files already formatted`

> 注：门 2/3 范围按 DECISION §十六 严格限定为 `app/`，不含 `tests/`（与基线一致）。`tests/` 内的既有 `test_stage5_s5_09_engine.py` 存在历史 format/F401 问题，属 PR-09 交付物、超出本 PR 范围，未触碰；本 PR 新增测试文件已自行 `ruff format` 规整（并入阶段 3 commit）。

## 四、影响面（新增 / 修改文件清单）

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/app/agent/skills/candidate_profile/v1_0_0/skill.yaml` | 新增 | Skill 元信息 + input/output schema（三命名空间） |
| `backend/app/agent/skills/candidate_profile/v1_0_0/prompt.md` | 新增 | SYSTEM_PROMPT + USER_TEMPLATE |
| `backend/app/agent/skills/candidate_profile/v1_0_0/examples.yaml` | 新增 | 3 个 few-shot |
| `backend/app/agent/orchestrator/engine.py` | 修改 | `_build_artifacts` 新增数据型 artifact 分支（`candidate_merge` + `candidate_profile`） |
| `backend/tests/test_stage5_s5_11_candidate_profile.py` | 新增 | TC-S5-11-1..4 + engine 数据型 artifact 单测 |

未触碰：`orchestrator_reason` / `orchestrator_plan` 任意文件、`models/task.py`、`api/v1/agent.py`、`TASKS-STAGE5.md`、前端 `src/**`、任何落库代码。

## 五、偏差 / 决策记录（必列 4 条 + §十三 触发登记）

### 19.1 · 追债项第 10 条登记 · task_type 三命名空间共存（本 PR 首次 canonical 表述）

`task_type` 一词在系统中承载三套语义、字面各不相同：

| 命名空间 | 惯例 | 示例 | 消费者 |
|----------|------|------|--------|
| `skill_id` / `tool_name`（分发键） | 连字符 lowercase | `candidate-profile` | tool_router dispatch by tool_name |
| `skill.yaml.task_type`（意图键） | 下划线 lowercase | `profile_candidate` | route_task_type 匹配 skill |
| `tasks.task_type` DB 列（业务分类） | SCREAMING | `PROFILE_CANDIDATE` | 前端业务分类展示 |

PR-16 `skill.yaml` 精确落地 `skill_id: candidate-profile` + `task_type: profile_candidate`，与 PR-15 格式对称；不动任何既有代码。Stage 5.1 需与追债项 11 **同 PR 收敛**（拆字段名 + 引入 `task_type → tool_name` 映射表 + 对齐 DB 列）。

### 19.2 · 追债项第 11 条登记 · orchestrator reason/plan 未登记 dispatchable Skill，自然语言路由不通

实测（kickoff 阶段核验）：`orchestrator_reason/prompt.md` 仅列 `match / merge_candidates / unknown`，不含 `profile_candidate`；`orchestrator_plan` 未注入 dispatchable 清单；`run_plan` 不动态注入 registry。`candidate-profile` / `candidate-merge` 既不在 plan examples 也不在 REST 硬编码里，自然语言无法路由。跨 PR-15/16 共同债务，Stage 5.1 紧接 PR-16 后启动收敛（风险等级：中高）。

### 19.3 · TASKS 文档字面 vs 实现差异

归档两处已知漂移（不修改 TASKS，STEP6 §五 为 canonical 追溯位）：
1. TASKS §S5-11 `task_types: [PROFILE_CANDIDATE]`（SCREAMING 复数数组）vs 实现 `task_type: profile_candidate`（下划线单数字符串）。
2. TASKS §S5-10 `task_types: [MERGE_CANDIDATES]` 同类漂移（PR-15 已交付事实）。

### 19.4 · `_ARTIFACT_TYPE_MAP` 与前端渲染器手动同步（追债项 3 未消除）

Q5 仅闭合"engine 出口路径"，使 `candidate_profile` / `candidate_merge` 的 artifact `type` 不再被降级为 `generic`、完整 `data` 嵌入。但前端 `type` 消费点（渲染器）尚未建立，仍依赖人工同步 `engine._ARTIFACT_TYPE_MAP` 与前端类型枚举，追债项 3 未消除。

### §十三 求助边界触发登记

**0 条触发**。执行全程未触碰 §十三 任一条件（空对象未被 jsonschema 拒绝、monkeypatch 路径有效、无 regression、未误改 reason/plan、未碰 `tasks.task_type` 字面量、未发现新命名空间漂移）。无静默处理事项。

## 六、工作区清理

- 临时诊断文件 `C:/temp/pr16_*.txt`、`C:/temp/g_*.txt` 均为本机临时输出，未纳入 git（§十八 约定）。
- 工作区既有未跟踪文件 `backend/backend.err`、`backend/scripts/`、`PR10/PR11/PR15-STEP6-REPORT*.md` 等**未纳入本 PR 提交**（PR-13/14 传承约定）。
- 未创建 tag、未改 `backend/.env`。

## 七、提交链（commit hash + message 列表）

PR-16 分支基于 `bc6c2f2`，含 3 个交付 commit：

```
ab99b43 feat(stage5): _ARTIFACT_TYPE_MAP data-type artifacts (candidate_merge + candidate_profile)   ← 阶段 3
295b8e9 feat(stage5): S5-11 candidate-profile skill three-parter (skill.yaml + prompt.md + examples.yaml) ← 阶段 2
d762e79 test(stage5): PR-16 red-test skeleton (TC-S5-11-1..4) + candidate_profile scaffold             ← 阶段 1
```

外加本 STEP6 报告（docs-only，可直推 master 或随本分支，见 §十五）：

```
docs(stage5): PR16 STEP6 report
```

- 阶段 1→3 严格 TDD 红→绿拆分；阶段 1 首行 `assert skill.skill_id == "candidate-profile"` 守卫在 skill.yaml 落地前为红（4 FAILED），阶段 2 三件套落地后转绿（4 passed），阶段 3 追加 engine 单测至 115 passed。
- 阶段 3 commit 已合并 `ruff format` 对测试文件的规整（分支未 push 前 amend），保持 3-commit 结构。

## 八、合入后 docs 动作（指挥官 FF-merge 时统一操作，依据 DECISION §十七）

- `HANDOFF.md` 头部：日期 → 2026-07-22；PR-16 已合入 master；下一 PR-17（前端 SSE Hook + ChatCenter）。
- `HANDOFF §9.1` 状态表：PR-16 = ✅（commit hash 填 `ab99b43`），基线 110 → 115。
- `HANDOFF §9.3` 追债项：
  - **追加第 10 条**：task_type 三命名空间共存（引用 §十九 canonical 表述）。
  - **追加第 11 条**：orchestrator reason/plan 未登记 dispatchable Skill，自然语言路由不通（跨 PR-15/16 共同债务）。
- `HANDOFF §9.4` 起手须警惕：追加 "PR-17 前端起手时须知：candidate-profile / candidate-merge 均为孤立 Skill，自然语言路由不通，前端 chat → SSE 流仅能拿到 THINKING + PLAN + RESULT 事件，不能期待 candidate-* skill 通过自然语言消息被触发"。
- `HANDOFF §9.5` 新文件表：追加 `backend/app/agent/skills/candidate_profile/v1_0_0/*`、`backend/tests/test_stage5_s5_11_candidate_profile.py`。
- `HANDOFF §9.6` PR-17 起手路径：明确必读 追债项 10/11（前端不要期待自然语言触发 candidate-* skill）。

> 注：上述 HANDOFF 改动由指挥官在 FF-merge 时统一执行（本执行体不代改 HANDOFF，避免越界扩大范围）。
