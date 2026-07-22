# PR-17 · Orchestrator 端到端路由修复 · 启动裁定

> 关联：`docs/planning/stage5/PR17-KICKOFF-QUESTIONS.md`（初稿）· `docs/planning/stage5/PR17-QUESTIONS-REVISIONS.md`（修订建议）· 建议分支 `feat/pr-17-orchestrator-routing-fix`
> 权威依据：`HANDOFF §9.3 追债项 10 / 11`（PR-16 FF-merge 后 canonical 落地）· `docs/api-contract.md §3.3 / §5.1` · PR-15/16 交付物（`candidate_merge` / `candidate_profile` 作为路由目标 Skill）
> 生成时间：2026-07-22
> 状态：**12 问全部裁定 + REVISIONS 5 项事实纠错并入 + 追债项 10/11 双闭合承诺登记，执行体可立即按 §十四 开工**

---

## 〇、PR 编号与前置状态说明

### PR 编号重规划（采纳 REVISIONS §A1 (a)）

- **本 PR = PR-17**（追债项 10 + 追债项 11 同 PR 收敛），紧接 PR-16 后。
- **原前端 PR 顺延**：原 PR-17 前端 SSE Hook + ChatCenter → **PR-18**；原 PR-18 前端 CandidateChat → **PR-19**。
- **权威归属**：以 `HANDOFF §9.1 状态表` 为准（PR-16 FF-merge 时已刷新）。
- **不改动**：`PR16-STEP6-REPORT.md §八` 的"下一 PR-17 = 前端"旧措辞属**历史时点回报**，属于 executor 视角快照，保持不动。冲突已由 HANDOFF §9 refresh 覆盖，DECISION 与 HANDOFF §9.1 口径一致。

### 前置事实核验（2026-07-22 · master `00a9c1b`，REVISIONS §A2 已过期，事实以本节为准）

| 项 | 状态 |
|---|---|
| master HEAD（本地 + 远端） | **`00a9c1b`**（PR-16 全 4 commit + HANDOFF §9 refresh 合入） |
| 本地 pytest 基线 | **115 passed**（PR-16 STEP6 已验，FF-merge 后复验 115/0/0） |
| `origin/feat/pr-16-*` 远端分支 | 已删 |
| 工作区状态 | clean（仅 pre-existing 未跟踪文件：`backend/backend.err`、`backend/scripts/`、旧 PR STEP6 报告等） |
| **PR-17 base ref** | **`00a9c1b`** — 从此 hash 拉起 `feat/pr-17-orchestrator-routing-fix` |

### 核心代码事实（决定技术路径 · 已复核）

| 事实 | 出处 | 说明 |
|---|---|---|
| `registry.list_dispatchable()` 已存在 | `skill_registry.py:58-66` | 返 `list[BaseSkill]`（排除 `internal=True`）—— 数据源现成 |
| `engine.dispatchable_tool_names()` 已实现 | `engine.py:124-127` | 合并 `BUILTIN_TOOLS.keys()` + `registry.list_dispatchable().skill_id` |
| `reflect_plan` 已用 `dispatchable_tool_names()` 校验 | `engine.py:169` | plan LLM 输出非法 tool_name 时被挡下，**保护网已在位** |
| BaseSkill 已用 Jinja2 render USER_TEMPLATE | `base_skill.py:161-165` | 可透明注入任意变量 |
| `orchestrator_plan/skill.yaml` `input_schema` | line 12-19 | 仅含 `reason_output` 且 `required: [reason_output]`；**无 `additionalProperties: false`** —— 注入 `dispatchable_tools` 不会被 jsonschema 拒（REVISIONS §A3 纠错） |
| `tool_router.dispatch` 用 tool_name 直查 | `tool_router.py:131-150` | 映射表只服务 reason→plan 桥接，dispatch 无需改 |
| **`jd-candidate-matching` skill 存在且 dispatchable** | `skills/jd_candidate_matching/v1_0_0/skill.yaml:1,5` | `skill_id: jd-candidate-matching`，`task_type: match`，无 `internal: true` —— TC-PR17-3 前置成立 |
| **`create_match_score` 是 dangling tool_name**（REVISIONS §A5 实答） | `engine.py:51/418`、`agent.py:149` | 既非 BUILTIN_TOOLS 键，亦非任何 skill.yaml `skill_id`；skip-to-score 若走 `tool_router.dispatch` 会 `UnknownToolError` —— **PR-13/14 潜在遗留 bug，本 PR 不修，§五 归档** |

---

## 一、主裁定 · PR-17 交付范围硬边界

### 裁定：**PR-17 = 追债项 10（Y 方向）+ 追债项 11 同 PR 收敛**

**范围内**（本 PR 必交付）：

1. `backend/app/agent/skills/orchestrator_reason/v1_0_0/prompt.md` 补全 `task_type` 值域（含 `profile_candidate`）
2. `backend/app/agent/skills/orchestrator_reason/v1_0_0/examples.yaml` 追加 1 个 few-shot 覆盖 `profile_candidate`
3. `backend/app/agent/skills/orchestrator_plan/v1_0_0/skill.yaml` 扩 `input_schema.properties` 加 `dispatchable_tools`（**绝不入 `required`** —— REVISIONS §A3 强制约束）
4. `backend/app/agent/skills/orchestrator_plan/v1_0_0/prompt.md` USER_TEMPLATE 加 `{{ dispatchable_tools }}` 占位 + 使用说明
5. `backend/app/agent/skill_registry.py` 加 `_task_type_to_tool_name` 自动派生 + 冲突时 `raise ValueError`
6. `backend/app/agent/orchestrator/engine.py::run_plan` 注入 `dispatchable_tools` 到 plan_input（Markdown 字符串）
7. `backend/app/agent/orchestrator/engine.py` 新增 `_format_dispatchable_tools()` 辅助方法（含 `BUILTIN_TOOLS` + `registry.list_dispatchable()`）
8. `backend/tests/test_stage5_pr17_orchestrator_routing.py`（新文件，4 集成测试 · Q10 hermetic 路径）
9. `backend/tests/test_stage5_s5_04_tool_router.py` 追加 1 个负向冲突测试

**范围外**（触碰即触发 §十三 边界）：

- `create_match_score` REST 硬编码 plan 解耦（Q9 决定 A，`agent.py:149` 保持原样）
- BaseSkill.execute 契约变更（Q1 α/β/δ 全部排除）
- `tool_router.dispatch` 签名变更（Q6 决定 A）
- `orchestrator_reflect_plan` skill 逻辑变更（Q8 决定 A）
- `plan skill.yaml output_schema.tool_name.enum` 硬约束（Q7 决定 A、C 排除）
- `task_type` 三命名空间的字段名 refactor（追债 10 X 方向留 Stage 5.2）
- DB schema 迁移（追债 10 Z 方向留 Stage 5.2）
- 前端相关改动（PR-18/19）
- 真调 LLM 端到端测试（Q10 只 mock LLM，hermetic）
- `reason` skill 动态注入 task_type_domain（Q5 决定 B，reason 侧保持静态列举）

**执行体必读**：本 PR 是追债项 10（Y 方向）+ 追债项 11 的**唯一收敛 PR**。STEP6 §五 必须显式声明"追债项 10 Y 方向已收敛（X/Z 留 Stage 5.2），追债项 11 已收敛。HANDOFF §9.3 措辞改为 ✅ 已收敛（PR-17 `<hash>`）"。

---

## 二、Q1 裁定 · 动态注入技术路径（方案 γ）

**采纳方案 γ**（Jinja `input_schema` + USER_TEMPLATE 变量）。

**理由重写**（REVISIONS §A3 纠错）：
- **不是** "避免被 schema 校验拒"（jsonschema 默认允许额外字段，不会拒）
- **是** "结构清晰 + 契约文档化 + 与既有 skill 加载/执行流程完全对称"

**强制约束（REVISIONS §A3）**：
- `dispatchable_tools` **只进 `input_schema.properties`，绝不进 `required`**
- 保护既有 `run_plan` 调用方（仅传 `reason_output`）和 PR-12 plan 测试
- 触碰即触发 §十三#2 边界

**具体落地**：
- `orchestrator_plan/skill.yaml` `input_schema.properties` 增：
  ```yaml
  dispatchable_tools:
    type: string
    description: 当前 registry 可派单的工具清单（Markdown 列表，运行时由 engine 注入）
  ```
- `prompt.md` USER_TEMPLATE 末尾加占位 + 使用说明（"以下清单为当前系统可派单的所有工具，请严格从中选择 tool_name"）

---

## 三、Q2 裁定 · task_type → tool_name 映射表定义方式（方案 B）

**采纳方案 B**：`SkillRegistry` 加载时自动派生 + 冲突 raise。

**已复核当前无冲突**（REVISIONS §D 附注）：
- `match` → `jd-candidate-matching`
- `merge_candidates` → `candidate-merge`
- `profile_candidate` → `candidate-profile`
- 三者互不冲突，fail-fast 安全

**具体落地**（in `skill_registry.py::_load_all_skills` 末尾）：
```python
self._task_type_to_tool_name: dict[str, str] = {}
for skill in self._skills.values():
    if skill.internal or not skill.task_type:
        continue
    if skill.task_type in self._task_type_to_tool_name:
        existing = self._task_type_to_tool_name[skill.task_type]
        raise ValueError(
            f"task_type conflict: '{skill.task_type}' claimed by "
            f"'{existing}' and '{skill.skill_id}'"
        )
    self._task_type_to_tool_name[skill.task_type] = skill.skill_id
```

**冲突处理**：应用启动阶段 raise（fail-fast），非运行时 silent 冲突。

**暴露 accessor**（供后续 PR 消费，本 PR 内部不用）：
```python
def get_tool_name_for_task_type(self, task_type: str) -> str | None:
    return self._task_type_to_tool_name.get(task_type)
```

**测试**：`tests/test_stage5_s5_04_tool_router.py` 追加 `test_registry_task_type_conflict_raises`（构造两个临时同 task_type 的 skill 目录 → 断言 SkillRegistry 初始化 raise `ValueError` 含 "conflict"）。

---

## 四、Q3 裁定 · dispatchable_tools 序列化格式（方案 B · Markdown 列表）

**采纳方案 B**：`engine._format_dispatchable_tools() -> str` 手撸 Markdown 字符串。

**具体落地**：
```python
def _format_dispatchable_tools(self) -> str:
    lines = ["可用工具列表："]
    for name in sorted(BUILTIN_TOOLS.keys()):
        desc = BUILTIN_TOOLS[name].get("description", "")
        lines.append(f"- `{name}`（内置工具）：{desc}")
    for skill in self.registry.list_dispatchable():
        tt_note = f"（task_type: {skill.task_type}）" if skill.task_type else ""
        lines.append(f"- `{skill.skill_id}`{tt_note}：{skill.description}")
    return "\n".join(lines)
```

`run_plan` 调用前构造：`plan_input["dispatchable_tools"] = self._format_dispatchable_tools()`。

---

## 五、Q4 裁定 · dispatchable_tools 含 BUILTIN_TOOLS（方案 B）

**采纳方案 B**：清单同时包含 `BUILTIN_TOOLS`（`search_resumes` / `read_jd`）与 `registry.list_dispatchable()`。

**理由**：与 `engine.dispatchable_tool_names()` 现有实现（line 124-127）完全对称，reflect_plan 校验（line 169）走同一 whitelist，保护网口径一致。

---

## 六、Q5 裁定 · reason 侧改动力度（方案 B + 子问题 A）

**主问题采纳方案 B**：`prompt.md` 补全值域文字 + `examples.yaml` 追加 1 个 few-shot。

**具体落地**：
- `orchestrator_reason/prompt.md` 意图值域文字改为：
  > `task_type`：意图对应的任务类型（当前值域：`match` / `merge_candidates` / `profile_candidate` / `unknown`；无法判定时返 `unknown`）
- `orchestrator_reason/examples.yaml` 追加 1 个 few-shot，覆盖 `profile_candidate`（输入示例："请帮我给候选人 c_1 生成画像标签"→ 输出 `task_type: profile_candidate` + `parsed_entities: {candidate_id: c_1}`）

**子问题采纳 A + REVISIONS §B1 observation**：不入追债项 12。

**§五 observation 登记文本**（STEP6 §五 必写）：
> reason 侧当前采用静态列举（`match / merge_candidates / profile_candidate / unknown`），与 Q2 自动派生映射表异构。**若 Stage 5.2 起 dispatchable skill 频繁新增（阈值：> 3 个），reason prompt 需改为动态注入方案 C**。当前 skill 数量小，手动维护成本 << 动态注入实现成本，本 PR 不入债务。

---

## 七、Q6 裁定 · tool_router.dispatch 不消费映射表（方案 A）

**采纳方案 A**：`dispatch(tool_name, ...)` 契约保持不变，用 `tool_name` 直查 registry。

**理由**：
- 映射表只服务 reason → plan 桥接（LLM 从 Markdown 清单学习 task_type ↔ tool_name 对应关系后自主输出 tool_name）
- reflect_plan（`engine.py:169`）已挡下 LLM 犯错
- Q10 反向测试覆盖此保护路径
- dispatch 职责单一，零改动

---

## 八、Q7 裁定 · LLM 输出错误 tool_name 兜底（方案 A）

**采纳方案 A**：依赖 reflect_plan 现有保护（`engine.py:169`），零新增代码。

**测试覆盖**：Q10 · TC-PR17-4 反向用例断言：
- mock plan LLM 返 `{steps: [{tool_name: "nonexistent-skill", ...}], ...}`
- 调 `run_reflect_plan(...)` 返 `is_plan_sound=False` + `issues` 含 `"unknown tool: nonexistent-skill"`

**排除方案 B/C**：
- B（run_plan 内二次校验 + 重试）与 BaseSkill.max_retries 语义混淆
- C（output_schema.enum 静态硬约束）与 Q2 自动派生原则冲突（新增 skill 又要改 skill.yaml）

---

## 九、Q8 裁定 · reflect_plan 零改动（方案 A）

**采纳方案 A**：`orchestrator_reflect_plan` skill 逻辑零改动。

STEP6 §五 声明："验证 reflect_plan 保护网（`engine.py:169`）在 dispatchable_tools 动态注入后仍有效（TC-PR17-4 覆盖）"。

---

## 十、Q9 裁定 · create_match_score REST 硬编码 plan（决定 A · 不动）

**采纳决定 A**：`agent.py:145-153` skip-to-score 硬编码 plan 保持原样，本 PR 不动。

**REVISIONS §A5 追查项实答已并入**（**PR-17 阶段 0 不必再追查**，直接抄入 §五 归档）：

> `create_match_score` 是 **dangling tool_name**：
> - **既非** BUILTIN_TOOLS 键（`tool_router.py:54` 仅含 `search_resumes` / `read_jd`）
> - **亦非** 任何 skill.yaml 的 `skill_id`（`jd-candidate-matching` skill 的 skill_id 是 `jd-candidate-matching`）
> - 出现在 `engine.py:51` (`_ARTIFACT_TYPE_MAP`)、`engine.py:418`、`agent.py:149`（skip-to-score 硬编码 plan）
> - **潜在 bug**：若 skip-to-score 走 `tool_router.dispatch`，`create_match_score` `not in BUILTIN_TOOLS` → `registry.get_skill('create_match_score')` 返 None → `UnknownToolError`
> - **PR-13/14 遗留潜在 bug，本 PR 不修**（决定 A + §十三#10 边界锁定）
> - **后续 PR 建议**：单独 PR 二选一：(1) 注册 `create_match_score` 进 `BUILTIN_TOOLS`；(2) 改 `agent.py:149` 硬编码 tool_name 为 `jd-candidate-matching`。Stage 5.2 前完成。

**§十三#10 求助边界**：Q9 只做"§五 归档"，**任何 create_match_score 修复动作须停下汇报**（不得无声并进任何 commit）。

---

## 十一、Q10 裁定 · 集成测试策略（改路径 + hermetic + 5 测试）

**采纳 REVISIONS §D 路径改动**：新建 `backend/tests/test_stage5_pr17_orchestrator_routing.py`，**走 `run_reason` → `run_plan` → `run_reflect_plan` 单元级组合 + mock LLM，不走 `start_chat`**。

### 路径改动理由

- `start_chat` 需 `db_updater` / `redis` / SSE fixture，非 hermetic
- 会与 PR-14 端点测试互扰（§十三#7 已担心）
- 单元级组合覆盖同样端到端语义（reason → plan → reflect_plan），且**无需 fakeredis / no db session**
- Q10 TC-PR17-4 反向用例天然只需 reflect_plan 单点断言

### 测试列表（5 个 · 基线 115 → 预期 120 passed）

**TC-PR17-1 · candidate-profile 端到端**（正向）
- mock `orchestrator-reason` LLM 返 `{task_type: profile_candidate, intent_summary: "...", parsed_entities: {candidate_id: c_1}, ...}`
- mock `orchestrator-plan` LLM 返 `{steps: [{tool_name: candidate-profile, tool_input: {...}, ...}], summary: "..."}`
- mock `orchestrator-reflect-plan` LLM 返 `{is_plan_sound: true, issues: [], steps: [...]}`
- 依次调 `engine.run_reason(msg)` → `engine.run_plan(reason_output)` → `engine.run_reflect_plan(plan_output)`
- 断言：plan 输出的 tool_name = `candidate-profile`；reflect_plan `is_plan_sound=True`
- **额外断言**：`plan_input["dispatchable_tools"]` 是 str（Markdown 列表），含 `candidate-profile`、`candidate-merge`、`jd-candidate-matching`、`search_resumes`、`read_jd`

**TC-PR17-2 · candidate-merge 端到端**（正向）
- 同 TC-PR17-1，reason mock 返 `task_type: merge_candidates`；plan mock 返 tool_name = `candidate-merge`
- 断言 PR-15 交付的孤立 skill 现可通过自然语言路由

**TC-PR17-3 · jd-candidate-matching 端到端**（正向）
- 同上，reason 返 `task_type: match`；plan 返 tool_name = `jd-candidate-matching`
- 断言 Stage 4 遗留 skill 也接入路由
- **前置已核验**：`jd-candidate-matching` skill 存在（`skills/jd_candidate_matching/v1_0_0/skill.yaml:1`），`task_type: match`（line 5），无 `internal: true` → dispatchable 集合中存在

**TC-PR17-4 · plan LLM 输出错误 tool_name → reflect_plan 挡下**（反向 · Q7 校验）
- mock plan LLM 返 `{steps: [{tool_name: "nonexistent-skill", tool_input: {}, step_id: "step_1", description: "..."}], summary: "..."}`
- 调 `engine.run_reflect_plan(plan_output)` 返 `is_plan_sound=False` + `issues` 含 `"unknown tool: nonexistent-skill"`
- **不**断言 `engine.start_chat` 后 `tasks.status` 转 `WAITING_CONFIRMATION`（避免引入 db_updater 依赖，保 hermetic）

**TC-PR17-5 · registry task_type 冲突 raise**（负向 · Q2 校验，落在 `test_stage5_s5_04_tool_router.py`）
- 构造两个临时 skill 目录（tmp_path fixture），都声明 `task_type: profile_candidate`
- 断言 `SkillRegistry(skills_dir=temp_dir)` 初始化 raise `ValueError` 含 "conflict"

**基线预期**：**115（PR-16 交付后）→ +5 = 120 passed**（REVISIONS §A4 校正）

---

## 十二、Q11 裁定 · 追债项 10/11 状态转移（决定 A + 措辞改"已收敛"）

**采纳决定 A + REVISIONS §B2 措辞修正**：保留条目 + 标记已收敛 + 关联 PR-17 hash。

**HANDOFF §9.3 具体表述**（PR-17 STEP6 §八 合入时更新，措辞改"已收敛"替代"已闭合"）：

```markdown
- 追债项第 10 条 ~~task_type 三命名空间共存~~ **✅ 已收敛（PR-17 `<hash>`，Y 方向；X/Z 留 Stage 5.2）**：
  - Y 方向（自动派生映射表）已实施；X（拆字段名 refactor）/ Z（DB 列 SCREAMING 迁移）留 Stage 5.2 视需要
  - canonical 收敛点：`SkillRegistry._task_type_to_tool_name`（`skill_registry.py`）
- 追债项第 11 条 ~~reason/plan 未登记 dispatchable Skill~~ **✅ 已收敛（PR-17 `<hash>`）**：
  - reason prompt 补全值域 + examples 追加 profile_candidate；plan 动态注入 dispatchable 清单（方案 γ + Markdown）
  - canonical 收敛点：`OrchestratorEngine.run_plan` + `_format_dispatchable_tools` + `orchestrator-plan/prompt.md` + `orchestrator-reason/prompt.md`
```

**追债项 3**（`_ARTIFACT_TYPE_MAP` 与前端渲染器手动同步）**保持开放**（PR-17 未触及前端路由消费点）。

**理由**：
- **不用"已闭合"**：债 10 只收敛 Y 方向，X/Z 明留 Stage 5.2，"已闭合"易被误读为全闭环
- **保留条目**：历史可追溯（`~~删除线~~ **已收敛**`）比彻底删条目更利于后续审计

---

## 十三、Q12 裁定 · commit 拆分（5 commit · 采纳 REVISIONS §D）

**采纳 5 commit 版**（3 拆成 3a + 3b，避免 commit 3 过大 + reason skill 3a 先跑保护 §十三#2）：

| # | commit message | 内容 | 期望 pytest 结果 |
|---|---|---|---|
| 1 | `test(stage5): PR-17 red-test skeleton (TC-PR17-1..4 + task_type conflict test)` | 建 `tests/test_stage5_pr17_orchestrator_routing.py` 骨架（TC-PR17-1..4）+ `tests/test_stage5_s5_04_tool_router.py` 追加 TC-PR17-5 骨架 · 全部 xfail 或 red | **115 passed**（新测试 xfail，不影响基线） |
| 2 | `feat(stage5): auto-derive task_type→tool_name mapping in SkillRegistry + conflict detection` | `skill_registry.py` 加 `_task_type_to_tool_name` 派生 + 冲突 raise + `get_tool_name_for_task_type()` accessor · 移除 TC-PR17-5 xfail | **116 passed**（TC-PR17-5 转绿） |
| 3a | `feat(stage5): orchestrator-reason prompt+examples cover profile_candidate` | `orchestrator_reason/prompt.md` 补全值域 + `examples.yaml` 追加 profile_candidate few-shot · **不移除任何 TC-PR17-* xfail**（这些等 3b 才能绿） | **116 passed**（新增 skill 变更不破坏既有测试） |
| 3b | `feat(stage5): dynamic dispatchable_tools injection in run_plan + orchestrator-plan skill update` | `orchestrator_plan/skill.yaml` `input_schema.properties` 加 `dispatchable_tools`（**不进 required**）· `orchestrator_plan/prompt.md` USER_TEMPLATE 加占位 · `engine.py` 加 `_format_dispatchable_tools()` + `run_plan` 注入 | **116 passed**（PR-12 既有 plan 测试仍通过；TC-PR17-1..4 仍 xfail 等 4 转绿） |
| 4 | `test(stage5): TC-PR17-1..4 orchestrator routing end-to-end integration tests` | 移除 TC-PR17-1..4 xfail · 完善 mock（reason / plan / reflect_plan LLM）· 断言含 dispatchable_tools 注入到 plan_input | **120 passed** |

**外加**（阶段 5）：`docs(stage5): PR17 STEP6 report` — AGENTS.md §4.1 docs-only 可直推 master 或走本分支均可。

**Ordering 强约束**（我的额外补充判断 #3）：
- **必须严格 3a 先 → 3b 后**
- 理由：3a（reason skill 值域扩大）不会破坏既有测试；3b（plan skill `input_schema` 扩字段）**可能触发 §十三#2 求助边界**（PR-12 plan 测试若严格断言 `input_schema.properties` 全字段清单会 red）
- 顺序颠倒风险：3b 先跑若破坏 PR-12 plan 测试，3a 未来得及独立验证 reason 侧无副作用，回滚成本高

---

## 十四、执行体行动清单（阶段化）

### 阶段 0 · 开工前门槛验证（≤ 5 min）

- [ ] `git status` + `git log -1` 确认 master HEAD = `00a9c1b`（若不等，触发 §十三#9 停下汇报）
- [ ] 工作区 clean（仅 pre-existing 未跟踪文件，见 §前置）；若有 `orchestrator_reason` / `orchestrator_plan` / `skill_registry.py` / `tool_router.py` uncommitted 改动，触发 §十三#9 停下
- [ ] `cd backend && uv run pytest -q` 验证基线 = **115 passed**（若 < 115，触发 §十三#6 停下）
- [ ] `git checkout -b feat/pr-17-orchestrator-routing-fix`
- [ ] `grep -n "task_type" backend/app/agent/skills/*/v1_0_0/skill.yaml` 手动确认无 task_type 冲突（低概率，但 §十三#3 需预防）

### 阶段 1 · red-test skeleton（commit 1）

- [ ] 建 `tests/test_stage5_pr17_orchestrator_routing.py`：4 test 函数骨架（TC-PR17-1..4），全部 `@pytest.mark.xfail(reason="PR-17 not yet implemented")` 或 raise NotImplementedError
- [ ] `tests/test_stage5_s5_04_tool_router.py` 末尾追加 `test_registry_task_type_conflict_raises` 骨架 · xfail
- [ ] `uv run pytest -q` 验证 **115 passed**（xfail 不计入 failed）
- [ ] commit 1

### 阶段 2 · registry 自动派生 + 冲突检测（commit 2）

- [ ] `skill_registry.py::_load_all_skills` 末尾加 `_task_type_to_tool_name` 派生 + 冲突 raise（Q2 落地）
- [ ] `skill_registry.py` 加 `get_tool_name_for_task_type(task_type) -> str | None` accessor（供后续 PR 消费）
- [ ] 移除 `test_registry_task_type_conflict_raises` 的 xfail，实现测试体（构造 tmp_path fixture，两个同 task_type skill 目录）
- [ ] `uv run pytest -q` 验证 **116 passed**（TC-PR17-5 转绿）
- [ ] commit 2

### 阶段 3a · orchestrator-reason skill 更新（commit 3a）

- [ ] `orchestrator_reason/prompt.md` 修改意图值域文字（§六 具体落地）
- [ ] `orchestrator_reason/examples.yaml` 追加 1 个 profile_candidate few-shot
- [ ] `uv run pytest -q` 验证 **116 passed**（reason 侧改动不破坏既有测试）
- [ ] commit 3a

### 阶段 3b · orchestrator-plan + engine.run_plan 动态注入（commit 3b）

- [ ] `orchestrator_plan/skill.yaml` `input_schema.properties` 增 `dispatchable_tools`（`type: string`）· **不进 `required`**（REVISIONS §A3 强制）
- [ ] `orchestrator_plan/prompt.md` USER_TEMPLATE 末尾加 `{{ dispatchable_tools }}` 占位 + 使用说明
- [ ] `engine.py` 加 `_format_dispatchable_tools() -> str` 方法（§四 具体落地）
- [ ] `engine.py::run_plan` 在调用 skill 前构造 `plan_input["dispatchable_tools"] = self._format_dispatchable_tools()`
- [ ] `uv run pytest -q` 验证 **116 passed**（PR-12 plan 测试仍通过 —— 若 red，触发 §十三#2 停下汇报）
- [ ] commit 3b

### 阶段 4 · 集成测试转绿（commit 4）

- [ ] 移除 `test_stage5_pr17_orchestrator_routing.py` 4 个 test 的 xfail
- [ ] 完善 mock：`monkeypatch` `app.agent.llm_adapter.call_llm_json` 分层返值（按 skill 名分派）或用 `unittest.mock.patch` 逐 skill mock
- [ ] TC-PR17-1..3 断言 tool_name + 断言 `plan_input["dispatchable_tools"]` 含预期 5 项工具
- [ ] TC-PR17-4 反向断言 `reflect_plan` 返 `is_plan_sound=False` + `issues` 匹配
- [ ] `uv run pytest -q` 验证 **120 passed**
- [ ] `uv run ruff check app` = 0 error
- [ ] `uv run ruff format --check app` = 0 diff
- [ ] commit 4

### 阶段 5 · STEP6 报告 + 汇报

- [ ] 写 `docs/planning/stage5/PR17-STEP6-REPORT.md`：三门实测输出 + §四 影响面清单 + §五 至少 4 条声明（19.1 追债 10 Y 收敛 / 19.2 追债 11 收敛 / 19.3 追债 3 保持开放 / 19.4 Q9 create_match_score dangling tool_name 归档 · 抄 §十 实答 + §十三#10 边界锁定）+ §五 additional observation（Q5 子问题 reason 静态列举，Stage 5.2 触发阈值）
- [ ] `git push -u origin feat/pr-17-orchestrator-routing-fix`
- [ ] 报告本执行体不做 FF-merge，交指挥官评审

### 阶段 6 · 指挥官 FF-merge 后 docs 动作（**指挥官侧**，STEP6 §八 列明）

- [ ] `HANDOFF.md` 头部日期不变；§9.1 状态表：PR-17 = ✅（commit hash 填 commit 4）；基线 115 → 120
- [ ] `HANDOFF §9.3 追债项`：第 10 条 / 第 11 条改为 ✅ 已收敛（措辞按 §十二）；追债项 3 保持开放；追加**新债 12（可选）**：`create_match_score` dangling tool_name 待后续 PR 二选一收敛
- [ ] `HANDOFF §9.4 陷阱`：PR-17 起手警惕撤销；追加"PR-18 起手警惕：前端 SSE stream 消费时须知 dispatch 端点已支持自然语言触发 candidate-* skill"
- [ ] `HANDOFF §9.6 起手路径`：改写为 PR-18（前端 SSE Hook + ChatCenter）起手指南
- [ ] 记忆 `stage5-progress-and-known-limits.md` 更新：PR-17 已合，基线 120，追债 10/11 已收敛 Y 方向

---

## 十五、影响面预估（新增 / 修改文件清单）

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `backend/app/agent/skills/orchestrator_reason/v1_0_0/prompt.md` | 修改 | 意图值域文字补全 |
| `backend/app/agent/skills/orchestrator_reason/v1_0_0/examples.yaml` | 修改 | 追加 profile_candidate few-shot |
| `backend/app/agent/skills/orchestrator_plan/v1_0_0/skill.yaml` | 修改 | `input_schema.properties` 增 `dispatchable_tools`（不入 required） |
| `backend/app/agent/skills/orchestrator_plan/v1_0_0/prompt.md` | 修改 | USER_TEMPLATE 加 `{{ dispatchable_tools }}` 占位 |
| `backend/app/agent/skill_registry.py` | 修改 | 加 `_task_type_to_tool_name` 派生 + 冲突 raise + accessor |
| `backend/app/agent/orchestrator/engine.py` | 修改 | 加 `_format_dispatchable_tools()` + `run_plan` 注入 |
| `backend/tests/test_stage5_pr17_orchestrator_routing.py` | 新增 | TC-PR17-1..4（4 集成测试） |
| `backend/tests/test_stage5_s5_04_tool_router.py` | 修改 | 追加 TC-PR17-5（1 冲突测试） |

**不触碰**：
- `orchestrator_reflect_plan/*`（Q8 决定 A）
- `orchestrator_reflect_act/*`（无关）
- `tool_router.py::dispatch`（Q6 决定 A）
- `api/v1/agent.py`（Q9 决定 A）
- `models/task.py`（追债 10 Z 方向）
- `alembic/versions/*`（无迁移）
- 前端 `frontend/src/**`（PR-18/19）

---

## 十六、验收三道门（PR-17 STEP6 必测）

| 门 | 命令 | 期望 | 备注 |
|---|---|---|---|
| 1 · pytest | `cd backend && uv run pytest -q` | **120 passed / 0 failed / 0 error** | 基线 115 + 4 集成 + 1 冲突 = 120 |
| 2 · ruff lint | `cd backend && uv run ruff check app` | `All checks passed!` | 范围严格限定 `app/`（与 PR-16 一致） |
| 3 · ruff format | `cd backend && uv run ruff format --check app` | `X files already formatted` | 若新增测试文件有格式问题，阶段 4 前 `ruff format` 规整并入 commit 4 |

**flaky 处理**：如遇 `test_s5_09_4_sse_heartbeat` 单点 fail（PR-14 已知 timing 敏感），按 PR-16 处理策略：隔离运行验证 pass，全量重跑 2 次全绿即视为 flaky 非 regression（HANDOFF §9.4 陷阱 3 已登记）。

---

## 十七、STEP6 §五 声明清单（预登记 · 至少 4 条 + 1 observation）

1. **19.1 · 追债项第 10 条 Y 方向已收敛**：canonical 收敛点 `SkillRegistry._task_type_to_tool_name`；X（拆字段名）/ Z（DB 迁移）留 Stage 5.2
2. **19.2 · 追债项第 11 条已收敛**：canonical 收敛点 `OrchestratorEngine.run_plan` + `_format_dispatchable_tools` + `orchestrator-plan/prompt.md` + `orchestrator-reason/prompt.md`
3. **19.3 · 追债项第 3 条（`_ARTIFACT_TYPE_MAP` 与前端手动同步）保持开放**：PR-17 未触及前端消费点，Stage 5.2 视方案 A/B 决定
4. **19.4 · Q9 `create_match_score` dangling tool_name 归档**（抄 §十 实答 + 后续 PR 二选一建议 + §十三#10 边界锁定）
5. **附加 observation · Q5 子问题**：reason 侧静态列举与 Q2 自动派生异构（非债，触发阈值 `> 3 个 dispatchable skill 新增`）

---

## 十八、求助边界 · §十三（10 条 · 采纳 REVISIONS C1/C2）

执行体触发以下条件时**立即停下汇报**，不擅自处理：

1. **PR-12 既有 plan 测试因 `input_schema` 扩字段失败**：评估是否 revise 测试或让 `dispatchable_tools` 变可选字段（已强制不进 required，若仍破坏说明测试严格模式意外）
2. **`orchestrator_plan/skill.yaml.input_schema` 加 `dispatchable_tools` 到 `required`**（本 PR 强制约束不允许，若代码 diff 里出现即触发） · REVISIONS §A3
3. **`registry.list_dispatchable()` 冲突检测 raise 时，PR-15/16 交付的 skill.yaml 已存在冲突**（阶段 0 grep 未发现，但阶段 2 转绿测试跑起来 raise）
4. **plan LLM 收到 dispatchable 清单后，reflect_plan 挡下所有输出**（Q3 Markdown 格式表达不清，LLM 无法学习 task_type ↔ tool_name 映射） · Q10 测试 mock LLM 输出不覆盖此情况，但生产真实调用可能触发 —— 若 Q10 mock 意外挂了也停下
5. **Q9 追查发现 `create_match_score` 命名空间语义与既有 tool_name 冲突**（本 DECISION §十 已归档实答，若阶段 0 grep 结果与 §十 不符即触发）
6. **测试基线倒退**（pytest < 115 或阶段 4 < 120）
7. **`engine.run_plan` 注入 dispatchable_tools 后，PR-14 已有 chat / execute-plan 端点集成测试失败**（`db_updater` 回调时序或 SSE 事件序列变化）
8. **发现 PR-16 交付的 candidate-profile skill 的 task_type 与另一现存 skill 冲突**（阶段 2 冲突检测转绿测试跑到主流程时挂）
9. **开工前 master HEAD ≠ `00a9c1b` 或工作区含 `orchestrator_reason` / `orchestrator_plan` / `skill_registry` / `tool_router` uncommitted 改动** · REVISIONS §C1 · **不擅自 reset / 不擅自基于旧 base 起分支**
10. **Q9 顺手修补范围扩张**：任何 `create_match_score` 修复动作（注册进 BUILTIN_TOOLS 或改 `agent.py:149`）· REVISIONS §C2 · **不得无声并进任何 commit**
11. **TC-PR17-3 前置失效**：若阶段 0 grep `jd-candidate-matching` skill.yaml 缺失或 `internal: true`（本 DECISION §前置已核验存在且 dispatchable，此条兜底防止 PR-17 开工前 master 又变化）

---

## 十九、工作区清理

- 不新建 tag、不改 `backend/.env`（gitignored）
- **不 commit** 既有未跟踪文件：`backend/backend.err`、`backend/scripts/`、`docs/planning/stage5/C2-FIXTURE-DECISION.md`、`PR10-STEP5-*.md`、`PR10-STEP6-REPORT.md`、`PR11-STEP6-REPORT.md`、`PR15-STEP6-REPORT.md`（AGENTS.md 传承约定）
- STEP6 报告文件 `docs/planning/stage5/PR17-STEP6-REPORT.md` 走 commit（docs-only），FF-merge 后指挥官 §9 update 单独 commit

---

## 二十、承诺陈述

**本 DECISION 承诺**：PR-17 是**追债项 10（Y 方向）+ 追债项 11 的唯一收敛 PR**。STEP6 §五 必须显式声明"两项已收敛"，HANDOFF §9.3 相应更新（措辞用"已收敛"而非"已闭合"，标注 X/Z 留 Stage 5.2）。

**本 DECISION 拒绝**：任何"顺手修 `create_match_score` dangling tool_name / 顺手拆 task_type 字段名 / 顺手改前端渲染器同步"的范围扩张。这些留 Stage 5.2 或独立 PR。

**下一步**：DECISION 与 QUESTIONS/REVISIONS 三件套 docs-only 直推 master。执行体在独立会话里读本 DECISION §十四 开工，禁读 QUESTIONS/REVISIONS（避免被裁前建议干扰）。
