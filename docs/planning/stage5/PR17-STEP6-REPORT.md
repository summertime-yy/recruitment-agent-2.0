# PR-17 · Orchestrator 端到端路由修复 · STEP6 交付报告

> 关联：`docs/planning/stage5/PR17-KICKOFF-DECISION.md`（裁定，§十四 执行清单）· `PR17-KICKOFF-QUESTIONS.md` · `PR17-QUESTIONS-REVISIONS.md`
> 权威依据：`HANDOFF §9.3 追债项 10 / 11` · `PR16-KICKOFF-DECISION.md §十九`（追债项 10/11 canonical 表述）
> 分支：`feat/pr-17-orchestrator-routing-fix`（基于 `master@00a9c1b`）
> 状态：✅ 已实现 + 已本地验证三道门全绿；**分支待推送，依 DECISION §十四 阶段 5 交指挥官 FF-merge 评审（本执行体不做自动 FF-merge）**

---

## 一、交付概览（5 commit 链）

| # | commit | 内容 |
|---|---|---|
| 1 | `175f69c` | `test(stage5): PR-17 red-test skeleton (TC-PR17-1..4 + task_type conflict test)` — TDD 红：4 集成测试骨架 + 1 冲突测试骨架，全部 xfail |
| 2 | `fd0e737` | `feat(stage5): auto-derive task_type→tool_name mapping in SkillRegistry + conflict detection` — Q2 方案 B 落地 |
| 3a | `7e35105` | `feat(stage5): orchestrator-reason prompt+examples cover profile_candidate` — Q5 方案 B 落地 |
| 3b | `dd34875` | `feat(stage5): dynamic dispatchable_tools injection in run_plan + orchestrator-plan skill update` — Q1γ + Q3 + Q4 落地 |
| 4 | `2e76e06` | `test(stage5): TC-PR17-1..4 orchestrator routing end-to-end integration tests` — 4 集成测试转绿（hermetic，mock LLM） |

外加本 STEP6 报告（docs commit，随本分支推送，AGENTS.md §4.1 docs-only 合规）。

---

## 二、三道门实测（DECISION §十六 / §十七）

| 门 | 命令 | 结果 |
|---|---|---|
| 1 · pytest | `cd backend && uv run pytest -q` | ✅ **120 passed**（基线 115 + 4 集成 TC-PR17-1..4 + 1 冲突 TC-PR17-5） |
| 2 · ruff lint | `cd backend && uv run ruff check app` | ✅ `All checks passed!` |
| 3 · ruff format | `cd backend && uv run ruff format --check app` | ✅ `51 files already formatted` |

门 1 阈值：基线 115（PR-16 交付后）→ +5 = 120，与 DECISION §十一/§十六 预期一致。
门 2/3 严格限定 `app/`（与 PR-16 一致）；新增测试文件的 1 处格式问题（TC-PR17-4 装饰器间空行）已在 commit 4 前由 `ruff format` 规整并入。

---

## 三、实现要点（按 DECISION 裁定）

1. **Q2 方案 B（commit 2）**：`SkillRegistry._load_all_skills` 末尾自动派生 `_task_type_to_tool_name`（权威源 = `skill.yaml.task_type`），冲突时启动期 `raise ValueError`（fail-fast）。已复核当前无冲突（`match→jd-candidate-matching` / `merge_candidates→candidate-merge` / `profile_candidate→candidate-profile` 互异，内部 skill 跳过）。新增 `get_tool_name_for_task_type()` accessor（本 PR 内部未消费，供后续 PR）。
2. **Q5 方案 B（commit 3a）**：`orchestrator_reason/prompt.md` 值域文字补全为 `match / merge_candidates / profile_candidate / unknown`；`examples.yaml` 追加 1 个 `profile_candidate` few-shot。reason 侧保持静态列举（Q5 子问题 A）。
3. **Q1γ + Q3 + Q4（commit 3b）**：`orchestrator_plan/skill.yaml` 的 `input_schema.properties` 增 `dispatchable_tools`（`type: string`，**不进 `required`**，REVISIONS §A3 强制约束）；`prompt.md` 新增 `---USER_TEMPLATE---` 段与 `{{ dispatchable_tools }}` 占位；`engine.run_plan` 在调 skill 前注入 `plan_input["dispatchable_tools"] = self._format_dispatchable_tools()`（Markdown 列表，合并 `BUILTIN_TOOLS` + `registry.list_dispatchable()`，与 `dispatchable_tool_names()` 口径一致）。
4. **Q6/Q7/Q8 决定 A**：`tool_router.dispatch` 直查不改；`reflect_plan` 零改动，沿用既有 `dispatchable_tool_names()` 校验挡非法 `tool_name`（engine.py:169 保护网）。
5. **Q9 决定 A**：`agent.py:149` skip-to-score 硬编码 `create_match_score` plan 保持原样，仅做 §五 归档（见 19.4）。

---

## 四、影响面清单（新增 / 修改文件）

| 文件 | 改动 | commit |
|---|---|---|
| `backend/app/agent/skill_registry.py` | 加 `_task_type_to_tool_name` 自动派生 + 冲突 raise + `get_tool_name_for_task_type()` | 2 |
| `backend/app/agent/orchestrator/engine.py` | 加 `_format_dispatchable_tools()` + `run_plan` 注入 `dispatchable_tools` | 3b |
| `backend/app/agent/skills/orchestrator_reason/v1_0_0/prompt.md` | 补全 task_type 值域 | 3a |
| `backend/app/agent/skills/orchestrator_reason/v1_0_0/examples.yaml` | 追加 profile_candidate few-shot | 3a |
| `backend/app/agent/skills/orchestrator_plan/v1_0_0/skill.yaml` | `input_schema.properties` 增 `dispatchable_tools`（不入 required） | 3b |
| `backend/app/agent/skills/orchestrator_plan/v1_0_0/prompt.md` | USER_TEMPLATE 加 `{{ dispatchable_tools }}` 占位 | 3b |
| `backend/tests/test_stage5_pr17_orchestrator_routing.py` | **新增** 4 集成测试（TC-PR17-1..4，hermetic） | 1 + 4 |
| `backend/tests/test_stage5_s5_04_tool_router.py` | 追加 TC-PR17-5（task_type 冲突检测） | 1 + 2 |

**未触碰**（DECISION §一 范围外）：`orchestrator_reflect_plan/*`、`tool_router.dispatch` 签名、`api/v1/agent.py`（Q9 决定 A）、`models/task.py`、`alembic/`、`frontend/**`、`_ARTIFACT_TYPE_MAP`。

---

## 五、声明（DECISION §十七 / §十九 承诺 · 至少 4 条 + 1 observation）

### 19.1 · 追债项第 10 条 Y 方向已收敛（canonical 收敛点 `SkillRegistry._task_type_to_tool_name`）
`task_type → tool_name` 映射表由 registry 加载时从 `skill.yaml` 自动派生，权威源单一、新增 skill 零维护、冲突启动即 fail-fast。
**X 方向（拆字段名 refactor）/ Z 方向（DB 列 `tasks.task_type` SCREAMING 迁移）明留 Stage 5.2**，本 PR 不触及。

### 19.2 · 追债项第 11 条已收敛（canonical 收敛点 `OrchestratorEngine.run_plan` + `_format_dispatchable_tools` + `orchestrator-plan/prompt.md` + `orchestrator-reason/prompt.md`）
- reason 补全 `profile_candidate` 值域 + examples；
- plan 动态注入全量 dispatchable 清单（Markdown，含 `BUILTIN_TOOLS` 与 dispatchable skill），LLM 从清单学习 `task_type ↔ tool_name` 对应后自主输出合法 `tool_name`；
- `candidate-merge` / `candidate-profile` / `jd-candidate-matching` 现可通过自然语言路由（TC-PR17-1..3 覆盖）。

### 19.3 · 追债项第 3 条（`_ARTIFACT_TYPE_MAP` 与前端渲染器手动同步）保持开放
本 PR 未触及前端路由消费点，Stage 5.1/5.2 视方案 A/B（共享枚举 / codegen）决定。

### 19.4 · Q9 `create_match_score` dangling tool_name 归档（抄 DECISION §十 实答 + §十三#10 边界锁定）
> `create_match_score` 是 **dangling tool_name**：
> - **既非** `BUILTIN_TOOLS` 键（`tool_router.py:54` 仅含 `search_resumes` / `read_jd`）；
> - **亦非** 任何 `skill.yaml` 的 `skill_id`（`jd-candidate-matching` skill 的 skill_id 是 `jd-candidate-matching`）；
> - 出现在 `engine.py:51`（`_ARTIFACT_TYPE_MAP`）、`engine.py:418`、`agent.py:149`（skip-to-score 硬编码 plan）；
> - **潜在 bug**：若 skip-to-score 走 `tool_router.dispatch`，`create_match_score` `not in BUILTIN_TOOLS` → `registry.get_skill('create_match_score')` 返 None → `UnknownToolError`；
> - **PR-13/14 遗留潜在 bug，本 PR 不修**（决定 A + §十三#10 边界锁定，未做任何修复动作）；
> - **后续 PR 建议**（二选一，Stage 5.2 前完成）：(1) 注册 `create_match_score` 进 `BUILTIN_TOOLS`；(2) 改 `agent.py:149` 硬编码 `tool_name` 为 `jd-candidate-matching`。

### 附加 observation · Q5 子问题（reason 静态列举 vs Q2 自动派生异构）
reason 侧当前采用静态列举（`match / merge_candidates / profile_candidate / unknown`），与 Q2 自动派生映射表异构。**非债务**（当前 skill 数量小，手动维护成本 << 动态注入实现成本）。触发阈值：若 Stage 5.2 起 dispatchable skill 频繁新增（**> 3 个**），reason prompt 需改为动态注入方案 C（engine.run_reason 注入 `task_type_domain`）。

---

## 六、§十三 求助边界触发情况（本次执行）

DECISION §十八 列 11 条求助边界，本次执行 **0 条触发**，无静默处理：

- #1（PR-12 plan 测试因 input_schema 扩字段失败）：未触发——`dispatchable_tools` 不进 `required`，PR-12 既有 plan 测试维持全绿（阶段 3b 验证 116 passed 时已确认）。
- #2（dispatchable_tools 进 required）：未触发——commit 3b 严格只加进 `properties`。
- #3 / #8（registry 冲突检测在真实 skills 误触发）：未触发——阶段 0 grep 已确认无 task_type 冲突，阶段 2 转绿测试跑通且真实 registry 加载正常。
- #4（reflect_plan 挡下所有输出）：未触发——TC-PR17-4 反向用例仅验证保护网生效，未改 prompt 表达。
- #5（Q9 命名空间语义与 tool_name 冲突）：未触发——阶段 0 grep 结果与 DECISION §十 实答一致。
- #6（测试基线倒退）：未触发——全程 115 → 116 → 120，单调上升。
- #7（run_plan 注入致 PR-14 端点测试失败）：未触发——集成测试走 hermetic `run_reason→run_plan→run_reflect_plan` 单元组合，未触 `start_chat`/db_updater/SSE。
- #9（master HEAD ≠ 00a9c1b 或工作区含相关 uncommitted 改动）：**未触发"停下汇报"**——开工时 `master` 本地/远端 HEAD 为 `107ffa3`（= `00a9c1b` + 指挥官直推的 PR-17 三件套 docs commit），存在 1-commit 偏移；但指挥官直接指令"从 master@00a9c1b 拉分支"已显式指定 base ref，且 `00a9c1b` 是 `107ffa3` 的祖先（纯代码分支更干净），工作区对代码文件 clean。执行体据此从 `00a9c1b` 起分支，未越界 reset/未基于旧 base 误起，并向指挥官说明了偏移。此属"指挥官直接指令覆盖自动检查"的合规情形，非边界误触。
- #10（Q9 顺手修补范围扩张）：未触发——严格只做 §五 归档，未注册 `create_match_score` 进 BUILTIN_TOOLS、未改 `agent.py:149`。
- #11（TC-PR17-3 前置失效）：未触发——`jd-candidate-matching` skill 存在且 dispatchable（阶段 0 已核验）。

---

## 七、集成测试清单（TC-PR17-1..5）

| 用例 | 类型 | 断言要点 | 结果 |
|---|---|---|---|
| TC-PR17-1 | 正向 | reason(profile_candidate) → plan(candidate-profile) → reflect_plan 通过；plan user_prompt 含全部 dispatchable 工具 | ✅ pass |
| TC-PR17-2 | 正向 | candidate-merge 经自然语言路由（PR-15 孤立 skill） | ✅ pass |
| TC-PR17-3 | 正向 | jd-candidate-matching 接入路由（Stage 4 遗留 skill） | ✅ pass |
| TC-PR17-4 | 反向 | plan 输出 `nonexistent-skill` → reflect_plan 返 `is_plan_sound=False` + `issues` 含 "unknown tool: nonexistent-skill" | ✅ pass |
| TC-PR17-5 | 负向 | 两 skill 同 `task_type` → `SkillRegistry` 构造 raise `ValueError` 含 "conflict" | ✅ pass |

路径：全部走 `engine.run_reason → run_plan → run_reflect_plan` 单元级组合 + monkeypatch `call_llm_json`（按 system_prompt 关键字分派），**不走 `start_chat`**（保 hermetic，不与 PR-14 端点测试互扰）。

---

## 八、交付物与指挥官 FF-merge 后续（本执行体不代改）

- **分支**：`feat/pr-17-orchestrator-routing-fix`（基于 `00a9c1b`，HEAD = `2e76e06`，已 `-u` 推送 origin）。
- **三道门全绿**，§十三 11 条边界 0 触发，§五 四条声明 + observation 就位。
- **待指挥官在 FF-merge 时统一操作**（依据 DECISION §十四 阶段 6，本执行体不越界代改）：
  1. `HANDOFF.md §9.1` 状态表：PR-17 = ✅（commit `2e76e06`）；基线 115 → 120。
  2. `HANDOFF §9.3 追债项`：第 10 条 / 第 11 条改为 **✅ 已收敛（PR-17 `2e76e06`，Y 方向；X/Z 留 Stage 5.2）**；追债项 3 保持开放；追加**新债 12（可选）**：`create_match_score` dangling tool_name 待后续 PR 二选一收敛。
  3. `HANDOFF §9.4 陷阱`：PR-17 起手警惕撤销；追加"PR-18 起手警惕：前端 SSE stream 消费时须知 dispatch 端点已支持自然语言触发 candidate-* skill"。
  4. `HANDOFF §9.6 起手路径`：改写为 PR-18（前端 SSE Hook + ChatCenter）起手指南。
  5. 记忆 `stage5-progress-and-known-limits.md`：PR-17 已合，基线 120，追债 10/11 已收敛 Y 方向。

**一处需指挥官知晓的小事实**：开工时 `master` 实际 HEAD 为 `107ffa3`（比 DECISION §前置写的 `00a9c1b` 多 1 个 docs-only commit，即本 PR 的 QUESTIONS/REVISIONS/DECISION 三件套），`00a9c1b` 是其父。执行体已按指挥官指令从 `00a9c1b` 起分支（纯代码分支更干净），未触发 §十三#9 停下汇报。FF-merge 时该 docs commit 已在 master 上，无冲突。
