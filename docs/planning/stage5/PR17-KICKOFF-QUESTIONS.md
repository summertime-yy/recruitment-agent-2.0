# PR-17 · Orchestrator 端到端路由修复（追债项 10+11 收敛）· 启动前求助

> 关联：PR-17 = **追债项 10（task_type 三命名空间）+ 追债项 11（reason/plan 未登记 dispatchable Skill）同 PR 收敛** · 建议分支 `feat/pr-17-orchestrator-routing-fix`
> 权威依据：`docs/planning/stage5/PR16-KICKOFF-DECISION.md §十九`（追债项 10/11 canonical 表述）· `HANDOFF §9.3 追债项 10/11`（PR-16 STEP6 合入后追加）· `docs/api-contract.md §3.3/§5.1` · PR-15/16 交付物（`candidate_merge` / `candidate_profile` 作为路由目标 Skill）
> 状态：等待指挥官裁定，尚未开工
> 编号说明：**本 PR = PR-17**（追债项 10+11 收敛紧接 PR-16 之后），**原前端 PR 顺延**（原 PR-17 前端 SSE Hook → PR-18；原 PR-18 前端 CandidateChat → PR-19）

---

## 前置事实（已核验，2026-07-22 · master `bc6c2f2`，PR-16 kickoff 已合入）

### 核心代码事实（决定技术路径）

| 事实 | 出处 | 说明 |
|---|---|---|
| **master HEAD** | 本地 + 远端 = `bc6c2f2`（PR-16 kickoff docs 已合入） | PR-16 执行体分支 `feat/pr-16-*` 正在跑，**PR-17 分支必须等 PR-16 FF-merge 后从新 master 拉起** |
| **registry.list_dispatchable() 已存在** | `skill_registry.py:58-66` | 返回 `list[BaseSkill]`（排除 `internal=True`），支持 `task_type` 二次过滤 —— **数据源现成，不用新建** |
| **engine.dispatchable_tool_names() 已实现** | `engine.py:124-127` | 合并 `BUILTIN_TOOLS.keys()` + `registry.list_dispatchable().skill_id`，返 flat list —— **plan 侧 tool_name 白名单现成** |
| **⭐ reflect_plan 已用 dispatchable_tool_names 校验** | `engine.py:169` | `bad = [s.tool_name for s in steps if s.tool_name not in self.dispatchable_tool_names()]` —— **plan LLM 输出非法 tool_name 时会被 reflect_plan 挡下，保护网已在位** |
| **BaseSkill 已用 Jinja2 render USER_TEMPLATE** | `base_skill.py:161-165` | `Template(self._user_prompt_template).render(**input_params)` —— **可透明注入任意变量，不改 BaseSkill 契约** |
| **BaseSkill.execute 契约** | `base_skill.py:226-281` | `input_valid = validate_input(input_params)` → 先按 input_schema 校验；**若 dispatchable_tools 未声明在 orchestrator-plan input_schema 里，直接注入会被 schema 校验拒** |
| **orchestrator-plan input_schema 现状** | `orchestrator_plan/skill.yaml:12-19` | 仅含 `reason_output`，`additionalProperties` 未指定（jsonschema 默认允许额外字段，但 `required` 只列 reason_output） |
| **tool_router.dispatch 用 tool_name 直查** | `tool_router.py:131-150` | `skill = registry.get_skill(tool_name)` → 不消费任何 task_type→tool_name 映射；**映射表只服务 reason→plan 桥接**，不影响 dispatch |
| **create_match_score REST 硬编码 plan** | `agent.py:145-153` | skip-to-score 端点在 Python 层直构造 `plan.steps[{tool_name: create_match_score}]`，绕开 LLM plan；本 PR **不动**（决定 1 = A） |

### 现状缺口（追债项 10/11 实测细节）

| 缺口 | 现状 | 期望 |
|---|---|---|
| reason 意图值域 | `orchestrator_reason/prompt.md:6` 列 `match / merge_candidates / unknown`（3 个） | 补全为 `match / merge_candidates / profile_candidate / unknown`（4 个，可选延伸 `general_qa` / `generate_jd` 但需与 skill 存在性对齐） |
| plan dispatchable 清单注入 | `orchestrator_plan/prompt.md` 只字面说"命中 dispatchable Skill ID 或内置工具（search_resumes / read_jd）"，无动态清单 | plan LLM 每次调用收到当前 registry 全量 dispatchable 三元组（tool_name / task_type / description） |
| task_type→tool_name 映射 | 无（LLM 需自行做"下划线 profile_candidate → 连字符 candidate-profile"翻译） | 显式映射（自动从 skill.yaml 派生 or 硬编码）+ 冲突检测 |
| 端到端集成测试 | 现有测试全是"分层 mock skill 单测"，无 chat → reason → plan → dispatch → skill 端到端断言 | 至少 4 用例（正向 3 skill + 反向 1 reflect_plan 挡下犯错） |

### PR-16 交付物影响面（PR-17 不重叠）

| PR-16 会改的文件 | PR-17 会改的文件 | 冲突面 |
|---|---|---|
| `engine.py::_build_artifacts`（60-92 行） | `engine.py::run_plan`（156-163 行）+ `engine.py::run_reason`（130-136 行） | 同文件不同函数，git 无冲突；**PR-17 分支必须等 PR-16 FF-merge 后从新 master 拉起**，避免 base ref 漂移 |
| `skills/candidate_profile/v1_0_0/*`（新增） | `skills/orchestrator_reason/v1_0_0/prompt.md` + `skills/orchestrator_plan/v1_0_0/prompt.md` + `skill.yaml` | 完全无重叠 |
| `tests/test_stage5_s5_11_candidate_profile.py`（新增） | `tests/test_stage5_pr17_orchestrator_routing.py`（新增） | 完全无重叠 |
| `tests/test_stage5_s5_09_engine.py`（追加 engine 单测） | 可能 `tests/test_stage5_s5_04_tool_router.py`（追加映射表冲突检测测试） | 文件不同，无重叠 |

**综合观察**：本 PR 作用面聚焦 3 个 Skill 目录（reason/plan skill）+ engine.py 2 个方法（run_reason / run_plan）+ registry 层（可能追加自动派生逻辑）+ 1 个新集成测试文件。**核心风险不在实现，在契约稳定性**：dynamic dispatchable injection 是否破坏既有 plan skill 测试？映射表冲突时 raise 还是 warn？集成测试的 mock 深度？

---

## PR-17 交付范围（DECISION 前必须明确的边界）

**范围内**：
- `backend/app/agent/skills/orchestrator_reason/v1_0_0/prompt.md` 补全 task_type 值域
- `backend/app/agent/skills/orchestrator_plan/v1_0_0/skill.yaml` 扩 input_schema（Q1 方案 γ）
- `backend/app/agent/skills/orchestrator_plan/v1_0_0/prompt.md` USER_TEMPLATE 加 `{{ dispatchable_tools }}` 占位 + 使用说明
- `backend/app/agent/orchestrator/engine.py::run_plan` 注入 `dispatchable_tools` 到 plan_input
- `backend/app/agent/orchestrator/engine.py::run_reason`（可选）注入 `task_type_domain`
- `backend/app/agent/skill_registry.py` 或 `tool_router.py` 加自动派生的 `task_type → tool_name` 映射表 + 冲突检测
- `backend/tests/test_stage5_pr17_orchestrator_routing.py`（新集成测试文件）
- 可能 `backend/tests/test_stage5_s5_04_tool_router.py`（映射表冲突检测测试）

**范围外，本 PR 不做**：
- **create_match_score REST 硬编码 plan 解耦**（决定 1 = A，skip-to-score 快捷路径保留）
- **BaseSkill.execute 契约变更**（Q1 方案 α 已排除）
- **tool_router.dispatch 逻辑变更**（tool_name 直查 registry 已工作，映射表只服务 reason→plan 桥接）
- **task_type 三命名空间的拆字段名 refactor**（追债 10 X 方向已排除，本 PR 走 Y 方向）
- **前端相关改动**（PR-18/19 起手）
- **DB schema 迁移**（追债 10 Z 方向留 Stage 5.2）
- **真调 LLM 端到端测试**（决定 3 = 中，只 mock LLM 集成）

**执行体必读**：本 PR 是追债项 10+11 的**唯一收敛 PR**（DECISION §二十 承诺），STEP6 §五 必须显式声明"追债项 10/11 已收敛，HANDOFF §9.3 改为已闭合状态"。

---

## Q1 · 动态注入技术路径

### 分歧

如何让 orchestrator-plan skill 的 LLM 每次调用知道当前 registry 的 dispatchable 清单？

- **α · 改 BaseSkill.execute 签名** 加 `system_prompt_extra` / `dispatchable_context` 参数
  - **缺点**：**破坏所有 7 个 skill 的 execute 契约**，影响面爆炸；且 orchestrator-* 内部 skill 与业务 skill（candidate-merge/profile）语义混淆 —— **明确排除**

- **β · run_plan 手撸 LLM 调用** 绕开 BaseSkill
  - **缺点**：绕开 max_retries / compliance / output validation 保护，破坏 BaseSkill 抽象；且需重复实现 Jinja render + jsonschema 校验 —— **明确排除**

- **γ · 通过 `input_schema` + Jinja USER_TEMPLATE 变量传 dispatchable_tools**（**推荐**）
  - orchestrator-plan `skill.yaml.input_schema` 扩为 `{reason_output, dispatchable_tools: array}`
  - `prompt.md` USER_TEMPLATE 加 `{{ dispatchable_tools }}` 占位
  - `engine.run_plan(plan_input)` 在调用前把 `[{tool_name, task_type, description}, ...]` 塞进 plan_input
  - **优点**：**零 BaseSkill 契约破坏**、走标准 Jinja render 通道、input_schema 校验层可保 dispatchable_tools 结构一致性、与既有 skill 加载/执行流程完全对称
  - **缺点**：每次 plan 调用要序列化 dispatchable 三元组进 prompt（token 消耗小幅上升，可接受）

- **δ · 改 BaseSkill.get_system_prompt(context)** 加 context 参数
  - **缺点**：`get_system_prompt` 是 BaseSkill 公共 API，加参数影响所有 skill 且需改 7 个 skill.yaml 的调用点 —— 破坏面居中，不必要

### 建议：**方案 γ**

**待裁定**：采纳方案 γ？

---

## Q2 · task_type → tool_name 映射表定义方式

### 分歧

追债 10 Y 方向的映射表如何维护？

- **A · 静态硬编码**（in `tool_router.py`）：
  ```python
  TASK_TYPE_TO_TOOL_NAME = {
      "match": "jd-candidate-matching",
      "merge_candidates": "candidate-merge",
      "profile_candidate": "candidate-profile",
  }
  ```
  - **优点**：显式、可 grep、审查简单
  - **缺点**：**冗余**（skill.yaml 已声明 task_type + skill_id 两个字段）、新增 skill 时必须记得同步（追债项 3 的翻版）、易漏

- **B · 自动派生 at registry load time**（**推荐**）：
  ```python
  # in SkillRegistry._load_all_skills 末尾
  self._task_type_to_tool_name: dict[str, str] = {}
  for s in self._skills.values():
      if s.internal or not s.task_type:
          continue  # 只映射非 internal + 有 task_type 的 skill
      if s.task_type in self._task_type_to_tool_name:
          raise ValueError(
              f"task_type conflict: '{s.task_type}' claimed by "
              f"'{self._task_type_to_tool_name[s.task_type]}' and '{s.skill_id}'"
          )
      self._task_type_to_tool_name[s.task_type] = s.skill_id
  ```
  - **优点**：**权威源单一（skill.yaml）**、新增 skill 时零维护、冲突时启动即报错（fail-fast）
  - **缺点**：需在 registry 加载时检测冲突（增加启动时间，可忽略）

- **C · 混合方案**：自动派生 + 静态白名单（如某些 skill 显式声明"我不参与自动派生"）
  - **优点**：灵活性最高
  - **缺点**：过度设计，当前无用例

### 建议：**方案 B（自动派生 + 冲突时 raise）**

**冲突处理**：应用启动阶段 raise `ValueError` 阻止服务启动（fail-fast）；避免运行时 silent 冲突。

**测试**：`tests/test_stage5_s5_04_tool_router.py` 追加 1 个负向用例 `test_registry_task_type_conflict_raises`（构造两个同 task_type 的 skill.yaml → 断言 SkillRegistry 初始化 raise）。

**待裁定**：采纳方案 B？冲突时 raise 而非 warn？

---

## Q3 · dispatchable_tools 序列化格式

### 分歧

LLM 收到的 dispatchable 三元组以什么格式呈现？

- **A · JSON 数组**：
  ```json
  [
    {"tool_name": "candidate-profile", "task_type": "profile_candidate", "description": "..."},
    ...
  ]
  ```
  - **优点**：结构化、Jinja 直接 `{{ dispatchable_tools | tojson }}`
  - **缺点**：LLM 对 JSON schema 学习成本高（相对 Markdown），token 效率低

- **B · Markdown 列表**（**推荐**）：
  ```markdown
  可用工具列表：
  - `search_resumes`（内置工具）：从简历库按关键词/技能/标签检索
  - `read_jd`（内置工具）：读取单条 JD 完整字段
  - `candidate-merge`（task_type: merge_candidates）：判定多份简历合并/建议/保持分离
  - `candidate-profile`（task_type: profile_candidate）：生成候选人画像标签+summary+strengths+risks
  - `jd-candidate-matching`（task_type: match）：JD-候选人匹配打分
  ```
  - **优点**：LLM 自然语言可读性强、token 效率高、映射关系一目了然（`task_type: profile_candidate` 与 `candidate-profile` 的对应关系嵌入描述）
  - **缺点**：需在 `engine.run_plan` 里手撸格式化字符串（10 行代码）

- **C · 混合**：Jinja template 里传 raw list，模板内做 Markdown 渲染
  - **优点**：格式化逻辑在 prompt 侧，代码零字符串拼接
  - **缺点**：Jinja 模板可读性下降（for 循环 + 条件语法）

### 建议：**方案 B（Markdown 列表）**

**具体做法**：`engine.run_plan` 在调用前构造字符串：
```python
def _format_dispatchable_tools(self) -> str:
    lines = []
    for name in sorted(BUILTIN_TOOLS.keys()):
        desc = BUILTIN_TOOLS[name].get("description", "")
        lines.append(f"- `{name}`（内置工具）：{desc}")
    for s in self.registry.list_dispatchable():
        task_type_note = f"（task_type: {s.task_type}）" if s.task_type else ""
        lines.append(f"- `{s.skill_id}`{task_type_note}：{s.description}")
    return "\n".join(lines)
```
plan_input 里传 `dispatchable_tools: str`（已格式化好的 Markdown 字符串）。

**待裁定**：采纳方案 B？还是希望结构化 JSON 由 Jinja 模板渲染（方案 C）？

---

## Q4 · dispatchable_tools 是否含 BUILTIN_TOOLS

### 分歧

plan LLM 需知道 `search_resumes / read_jd` 这两个内置工具吗？

- **A · 只含 registry.list_dispatchable() skill**（不含内置工具）
  - **缺点**：plan LLM 会不知道内置工具存在，导致"用户消息 = 帮我搜候选人"时 plan 输出错误（可能命中 `candidate-profile` 或其他 skill）；违背 dispatchable 完整白名单初衷

- **B · 内置工具 + skill 全量**（**推荐**）
  - `_format_dispatchable_tools` 合并 `BUILTIN_TOOLS` + `registry.list_dispatchable()`
  - 与 `engine.dispatchable_tool_names()` 现有实现完全对称（该方法 line 124-127 就是合并两者）
  - reflect_plan 校验也走同一 whitelist（保护网口径一致）

### 建议：**方案 B**

**待裁定**：采纳方案 B（内置工具全量含入）？

---

## Q5 · reason 侧改动力度

### 分歧

追债项 11 收敛方向 §1"reason prompt 补全意图值域"具体怎么补？

- **A · 只补 `profile_candidate`**：`match / merge_candidates / profile_candidate / unknown`
  - **优点**：最小改动、精确覆盖 PR-15/16 交付的两个孤立 skill
  - **缺点**：未来新增 skill 又要手动补（Q2 映射表的意义在于自动派生，reason 侧手动列举违背该原则）

- **B · 补齐当前 dispatchable 全域**：`match / merge_candidates / profile_candidate / unknown`（同 A，但明确"当前所有 non-internal skill 的 task_type"）
  - **实操**：与 A 效果相同，但描述性文字改为"意图对应的任务类型（当前值域：match / merge_candidates / profile_candidate / unknown；未知意图返 unknown）"

- **C · 也动态注入**：reason skill.yaml.input_schema 也加 `task_type_domain: string[]` 字段，engine.run_reason 传入 registry.list_dispatchable() 的 task_type 集合
  - **优点**：与 Q1 方案 γ 对称，reason 侧也零维护
  - **缺点**：改动面翻倍（reason skill.yaml + prompt.md + engine.run_reason），且 reason 侧 task_type 值域相对稳定（新增业务 skill 频率低），过度工程

### 建议：**方案 B（补齐 + 补上"当前值域"描述文字）**

**具体做法**：`orchestrator_reason/prompt.md:6` 从
```
- task_type：意图对应的任务类型（如 match / merge_candidates / unknown）
```
改为
```
- task_type：意图对应的任务类型（当前值域：match / merge_candidates / profile_candidate / unknown；无法判定时返 unknown）
```
+ 追加一个 few-shot example 覆盖 profile_candidate（`examples.yaml` 追加 1 项）。

**追债项闭合登记**：PR-17 STEP6 §五 声明"reason 侧当前采用静态列举，与 Q2 自动派生映射表异构。**若 Stage 5.2 起 dispatchable skill 频繁新增，reason prompt 需改为动态注入（方案 C）**"—— 作为**新追债项 12**登记？还是当作"设计选择"不入债务？

### 附加子问题 · reason 侧是否也算追债？

- **子选项 A**：不入债务（当前 skill 数量小，手动维护成本 << 动态注入实现成本）
- **子选项 B**：入债务 §12（Stage 5.2 触发条件"新增 dispatchable skill 数 > N 或 reason prompt 复杂度失控时"）

**倾向 A**：不入债务，STEP6 §五 只声明"设计选择"。

**待裁定**：Q5 主 = 方案 B？子问题 = A 不入债务？

---

## Q6 · tool_router.dispatch 是否消费映射表

### 分歧

`tool_router.dispatch(tool_name, ...)` 现在用 `tool_name` 直查 registry —— 是否需要改造为先查映射表？

- **A · 不消费映射表**（**推荐**）
  - dispatch 契约保持："输入 tool_name（已合法），路由到内置/skill"
  - 映射表只服务 reason → plan 之间的桥接：plan LLM 收到 dispatchable 清单里明列 `- candidate-profile（task_type: profile_candidate）：...`，学习"task_type profile_candidate 对应 tool_name candidate-profile"，自主翻译；LLM 输出 tool_name 后走 dispatch 直查
  - **优点**：dispatch 职责单一，零改动；映射表只在 registry 层用（Q2 冲突检测）
  - **缺点**：LLM 仍需自主翻译（依赖 prompt 学习效果）—— 但 reflect_plan 保护网已挡下犯错（engine.py:169）

- **B · dispatch 消费映射表**：`dispatch(task_type_or_tool_name, ...)` 先查映射表转 tool_name 再路由
  - **优点**：更彻底消除 LLM 翻译负担（LLM 只输出 task_type，engine 侧翻译）
  - **缺点**：破坏 plan 输出契约（当前 plan.steps[].tool_name 是权威）；需改 dispatch 签名 + tool_router 测试大改；跨 skill 语义 task_type 未定义时无处派单（`search_resumes` 是内置工具，无 task_type）

### 建议：**方案 A**

**理由**：Q3 建议里 Markdown 列表明列 `- candidate-profile（task_type: profile_candidate）：...` —— LLM 学习后自主翻译，配合 reflect_plan 已有的 dispatchable_tool_names() 校验（engine.py:169）+ Q10 集成测试覆盖"reflect_plan 挡下 LLM 犯错"用例，路径已闭合。dispatch 保持职责单一。

**待裁定**：采纳方案 A？

---

## Q7 · LLM 输出错误 tool_name 兜底

### 分歧

方案 γ + reflect_plan 保护网虽然已在位，但若 plan LLM 输出的 tool_name 都不合法，用户体验如何？

- **A · 依赖 reflect_plan 现有保护**（**推荐**）
  - `engine.py:169` 已挡下 unknown tool → 返 `{is_plan_sound: False, issues: ["unknown tool: X"], steps}`
  - reflect_plan 不通过 → engine 状态转 `WAITING_CONFIRMATION` + emit ERROR 事件 → 用户看到"plan 生成失败"
  - **优点**：零新增代码、保护网已实现；测试覆盖即可（Q10 反向用例）
  - **缺点**：用户视角看到的是通用错误，不知具体原因（reflect_plan 的 issues 已含"unknown tool: X"，前端消费即可揭示）

- **B · run_plan 内加二次校验 + 重试**
  - 若 plan LLM 输出 tool_name 非法，engine 内部提示 LLM 修正后重试
  - **优点**：用户看到成功率高
  - **缺点**：与 BaseSkill.max_retries 语义混淆（当前 orchestrator-plan skill.yaml max_retries=0）；重试逻辑放 engine 层破坏抽象

- **C · plan output 加 dispatchable 白名单硬约束**（改 orchestrator_plan/skill.yaml output_schema.tool_name.enum）
  - **优点**：schema 层挡住犯错
  - **缺点**：**静态 enum 与动态 dispatchable 冲突**（新增 skill 时又要改 skill.yaml）；违反 Q2 自动派生原则

### 建议：**方案 A（依赖 reflect_plan 现有保护）**

**测试覆盖**（Q10 反向用例）：模拟 plan LLM 输出 `tool_name: "unknown-skill-xyz"` → 断言 reflect_plan 返 `is_plan_sound=False` + `issues` 含 "unknown tool: unknown-skill-xyz" + engine 状态转 `WAITING_CONFIRMATION`。

**待裁定**：采纳方案 A？

---

## Q8 · reflect_plan 逻辑是否需要改动

### 分歧

reflect_plan 已用 `dispatchable_tool_names()` 校验（engine.py:169），本 PR 是否需要动它？

- **A · 零改动**（**推荐**）
  - 仅在 STEP6 §五 声明"验证 reflect_plan 保护网仍有效（Q10 反向用例覆盖）"
- **B · 顺手增强**：错误信息里追加"建议的 tool_name（模糊匹配最近的合法名）"
  - **缺点**：过度工程，reflect_plan issues 字段已有 "unknown tool: X"，前端消费即可

### 建议：**方案 A（零改动）**

**待裁定**：采纳方案 A？

---

## Q9 · create_match_score REST 硬编码 plan 是否顺手解耦

### 分歧

**已在决定 1 = A 层拍板：不动**。此处仅记录 §五 归档表述。

STEP6 §五 声明：`create_match_score / MATCH_SCORE / match` 三命名空间在本 PR 后依然共存：
- `skill.yaml.task_type = "match"` → 通过 chat 自然语言路由到 `jd-candidate-matching` skill（本 PR 打通）
- `agent.py:159 tasks.task_type = "MATCH_SCORE"` → skip-to-score REST 端点写入（未变）
- `agent.py:149 tool_name = "create_match_score"` → skip-to-score REST 端点硬编码 plan（未变）—— **注意**：这个 tool_name 与 skill_id 不一致（`jd-candidate-matching` skill 的 skill_id 是 `jd-candidate-matching`，`create_match_score` 是内置工具的名字？还是 skill 别名？需在阶段 0 追查）

### ⚠️ 需追查项（PR-17 阶段 0 必做）

- [ ] `grep -rn "create_match_score" backend/app/` 确认 `create_match_score` 是 skill_id 还是内置工具名
- [ ] 若是内置工具名 → 补进 BUILTIN_TOOLS 或明列 §五 归档
- [ ] 若是 skill 别名 → 追债项 10 表述需扩展"同一 skill 多个 tool_name 别名"这一层

### 建议：**保持决定 1 = A（不动 REST 硬编码 plan），阶段 0 追查后补充 §五 表述**

**待裁定**：确认决定 1 = A？追查项照做？

---

## Q10 · 集成测试位置 + 用例设计

### 分歧

集成测试放在哪个文件？用例数？mock 深度？

### 建议：**新建 `backend/tests/test_stage5_pr17_orchestrator_routing.py`**

**用例设计（4 个）**：

**TC-PR17-1 · candidate-profile 端到端**（正向）
- mock `orchestrator-reason` LLM 返 `{task_type: profile_candidate, intent_summary: "...", parsed_entities: {candidate_id: c_1}, ...}`
- mock `orchestrator-plan` LLM 返 `{steps: [{tool_name: candidate-profile, tool_input: {...}, ...}], summary: "..."}`
- mock `orchestrator-reflect-plan` LLM 返 `{is_plan_sound: true, issues: [], steps: [...]}`
- mock `candidate-profile` LLM 返合法 payload
- 走 `engine.start_chat(...)` 或 `run_reason_reflect + run_plan` 路径
- 断言：plan 输出的 tool_name = `candidate-profile`；reflect_plan 通过；最终产出 profile_tags

**TC-PR17-2 · candidate-merge 端到端**（正向）
- 同 TC-PR17-1，但 reason mock 返 `task_type: merge_candidates`；plan mock 返 tool_name = `candidate-merge`
- 断言 PR-15 交付的孤立 skill 现在可通过自然语言路由

**TC-PR17-3 · jd-candidate-matching 端到端**（正向）
- 同上，reason 返 `task_type: match`；plan 返 tool_name = `jd-candidate-matching`
- 断言 Stage 4 遗留 skill 也接入路由

**TC-PR17-4 · plan LLM 输出错误 tool_name → reflect_plan 挡下**（反向 · Q7 校验）
- mock plan LLM 返 `{steps: [{tool_name: "nonexistent-skill", ...}], ...}`
- 断言 `run_reflect_plan(...)` 返 `is_plan_sound=False` + `issues` 含 "unknown tool: nonexistent-skill"
- 可选：`engine.start_chat` 后 `tasks.status` 转 `WAITING_CONFIRMATION`（若 db_updater 注入）

### 附加：映射表冲突检测测试

- `tests/test_stage5_s5_04_tool_router.py` 追加 `test_registry_task_type_conflict_raises`：
  - 构造两个临时 skill 目录，都声明 `task_type: profile_candidate`
  - 断言 `SkillRegistry(skills_dir=temp_dir)` 初始化 raise `ValueError` 含 "conflict"

**基线预期**：110 或 114（视 PR-16 STEP6 交付后基线）→ **+5 测试** = **119 或 120 passed**（取决于 PR-16 具体基线）

**待裁定**：4 集成 + 1 映射冲突 = 5 测试，OK？还是需要更多正向 skill 覆盖？

---

## Q11 · 追债项 10/11 状态转移

### 决定 2 已裁定 = A（保留条目 + 标记已闭合 + 关联 PR-17 hash）

**HANDOFF §9.3 具体表述**（PR-17 STEP6 §八 合入时更新）：

```markdown
- 追债项第 10 条 ~~task_type 三命名空间共存~~ **✅ 已闭合（PR-17 `<hash>`）**：
  - Y 方向（自动派生映射表）已实施；X/Z 方向（拆字段名/DB 迁移）留 Stage 5.2 视需要
  - canonical 收敛：`SkillRegistry._task_type_to_tool_name`（skill_registry.py）
- 追债项第 11 条 ~~reason/plan 未登记 dispatchable Skill~~ **✅ 已闭合（PR-17 `<hash>`）**：
  - reason prompt 补全值域；plan 动态注入 dispatchable 清单（方案 γ）
  - canonical 收敛：`OrchestratorEngine.run_plan` + `orchestrator-plan/prompt.md`
```

**追债项 3**（_ARTIFACT_TYPE_MAP 与前端渲染器手动同步）**保持开放**（PR-17 未触及前端路由消费点）。

**待裁定**：这种"标记已闭合但保留条目"的表述 OK？

---

## Q12 · commit 拆分

### 建议：**4 commit 版**

1. `test(stage5): PR-17 red-test skeleton (TC-PR17-1..4 + task_type conflict test)` — 建 `tests/test_stage5_pr17_orchestrator_routing.py` 骨架 + 追加 tool_router 冲突测试骨架，全部 xfail 或 red
2. `feat(stage5): auto-derive task_type→tool_name mapping in SkillRegistry + conflict detection` — Q2 方案 B 实施 + 映射冲突测试转绿
3. `feat(stage5): dynamic dispatchable_tools injection in run_plan + orchestrator-plan skill update` — Q1 方案 γ + Q3 Markdown 格式 + Q4 内置工具合并 + orchestrator-plan skill.yaml/prompt.md 修改 + orchestrator-reason prompt.md/examples.yaml 补 profile_candidate（Q5 方案 B）
4. `test(stage5): TC-PR17-1..4 orchestrator routing end-to-end integration tests` — 4 集成测试转绿

**外加**：`docs(stage5): PR17 STEP6 report`（阶段 5，AGENTS.md §4.1 docs-only 可直推 master 或走本分支均可）

**若执行体判断 commit 3 过大**：可拆成 3a（Q5 reason skill 更新，含 examples 追加）+ 3b（Q1 γ plan skill 更新 + engine.run_plan 注入）= 5 commit。

**待裁定**：4 commit OK？还是拆更细（5 commit）？或合并 2+3 = 3 commit 更粗？

---

## §十二 · 顺手清扫候选

### 潜在项

**A · 补 create_match_score 到映射表？**
- 需先追查（Q9 追查项）：`create_match_score` 是内置工具还是 skill_id
- 若是 skill_id 且有对应 skill.yaml → 自动派生映射表可覆盖（Q2 方案 B 自动搞定），不需要顺手
- 若是内置工具名 → 与 BUILTIN_TOOLS 已有 `search_resumes / read_jd` 语义不同（`create_match_score` 是"创建资源型"内置工具），若发现缺失需补进 BUILTIN_TOOLS —— **不是顺手，属追查后决定**

**B · orchestrator-plan skill.yaml.output_schema.tool_name 加 pattern 校验？**
- 当前 output_schema tool_name 只有 `type: string`，无 pattern
- 顺手加 `pattern: "^[a-z_-]+$"` 约束命名规范
- **风险**：可能与既有 tool_name 命名冲突（`create_match_score` 用下划线，`candidate-profile` 用连字符）—— 需在追查 Q9 之后决定

**C · 补 `search_resumes / read_jd` 的 examples**（orchestrator_plan/examples.yaml 当前已有）
- **不必要**：现有 examples 已充分（覆盖典型 match 意图）

### 建议：**PR-17 无强制顺手清扫**

阶段 0 追查 Q9 后再决定是否需要补 create_match_score 到 BUILTIN_TOOLS。若需要，独立 commit `chore(stage5): register create_match_score builtin tool` 或合入 commit 3。

**待裁定**：确认无强制顺手清扫，追查 Q9 后视情况增补？

---

## §十三 · 求助边界（预估 8 条）

PR-17 执行时可能触发的求助点：

1. **PR-16 STEP6 尚未 FF-merge 时启动 PR-17**（base ref 不稳）：立即停下等待 PR-16 合入
2. **`orchestrator-plan/skill.yaml.input_schema` 扩字段后，既有 PR-12 plan skill 测试失败**（PR-12 有 `test_stage5_s5_06_plan.py` 类似测试 mock `plan_input` 只含 `reason_output`）：停下汇报，评估是否修测试 or 让 dispatchable_tools 变可选字段
3. **`registry.list_dispatchable()` 冲突检测 raise 时，PR-15/16 交付的 skill.yaml 已存在冲突**（低概率，但需在阶段 1 skeleton 前 grep 验证）：停下汇报
4. **plan LLM 收到 dispatchable 清单后，reflect_plan 挡下所有输出**（可能 prompt 表达不清 LLM 无法学习映射关系）：停下汇报，重构 Q3 Markdown 格式
5. **Q9 追查发现 `create_match_score` 命名空间语义与既有 tool_name 冲突**：停下汇报讨论
6. **测试基线倒退**（pytest < PR-16 交付后基线）：停下汇报
7. **`engine.run_plan` 注入 dispatchable_tools 后，PR-14 已有的 chat / execute-plan 端点集成测试失败**（可能因 `db_updater` 回调时序）：停下汇报
8. **发现 PR-16 交付的 candidate-profile skill 的 task_type 与另一现存 skill 冲突**（低概率但需 Q2 冲突检测负测覆盖）：停下汇报

**待裁定**：以上 8 条边界是否同意？还有别的须提前 flagged 的边角？

---

## §附 · 建议 commit 拆分（Q12 已明列）

**4 commit 版**（推荐）：
1. red-test skeleton
2. registry 映射表 + 冲突检测
3. run_plan 动态注入 + 3 个 skill 文件更新
4. 4 集成测试转绿

**5 commit 版**（若 commit 3 过大）：3 拆成 3a（reason skill 更新）+ 3b（plan skill + engine.run_plan 注入）

**docs commit**（直推 master）：`docs(stage5): PR17 STEP6 report + HANDOFF 追债项 10/11 已闭合`

---

## 汇总：12 问 + 附加

| # | 主题 | 建议 |
|---|---|---|
| Q1 | 动态注入技术路径 | **方案 γ（Jinja 变量注入 dispatchable_tools，0 契约破坏）** |
| Q2 | 映射表定义方式 | **方案 B（registry 加载时自动派生 + 冲突 raise）** |
| Q3 | dispatchable_tools 序列化格式 | **方案 B（Markdown 列表）** |
| Q4 | 是否含 BUILTIN_TOOLS | **方案 B（含）** |
| Q5 | reason 侧改动 | **方案 B（prompt 补全值域 + examples.yaml 追加 profile_candidate 示例）；子问题 A（不入追债项 12）** |
| Q6 | tool_router.dispatch 是否消费映射表 | **方案 A（不消费，dispatch 职责单一）** |
| Q7 | LLM 输出错误 tool_name 兜底 | **方案 A（依赖 reflect_plan 现有保护 + Q10 反向用例）** |
| Q8 | reflect_plan 逻辑改动 | **方案 A（零改动）** |
| Q9 | create_match_score REST 硬编码 plan | **保持决定 1 = A（不动，阶段 0 追查后 §五 归档表述）** |
| Q10 | 集成测试位置 + 用例数 | **新建 `test_stage5_pr17_orchestrator_routing.py`；4 集成 + 1 映射冲突 = 5 新测试** |
| Q11 | 追债项 10/11 状态转移 | **决定 2 = A（保留条目 + 标记已闭合 + 关联 PR-17 hash）** |
| Q12 | commit 拆分 | **4 commit（skeleton + registry + skill+engine + 集成测试）** |
| 附 | §十二 顺手清扫 | **无强制（Q9 追查后视情况）** |
| 附 | §十三 求助边界 | **8 条** |
| 附 | 基线预期 | **PR-16 后基线 + 5 = 119 或 120 passed** |

**请指挥官逐项裁定，或"全部采纳"**。裁定后我出 `PR17-KICKOFF-DECISION.md`，等 PR-16 FF-merge 后执行体照做。
