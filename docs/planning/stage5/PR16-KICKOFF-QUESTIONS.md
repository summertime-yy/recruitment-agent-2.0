# PR-16 · candidate-profile Skill · 启动前求助

> 关联：PR-16 = **S5-11（candidate-profile Skill 三件套 + 测试）** · 建议分支 `feat/pr-16-s5-11-candidate-profile`
> 权威依据：`docs/planning/TASKS-STAGE5.md §S5-11` · `docs/planning/TEST-PLAN-STAGE5.md §S5-11（TC-S5-11-1..4）` · `docs/planning/PLAN-STAGE5.md §187/§269` · `docs/api-contract.md §5.1`（reason 输出 task_type 契约）· PR-15 交付物（candidate_merge/v1_0_0）作模板
> 状态：等待指挥官裁定，尚未开工

---

## 前置事实（已核验，2026-07-22 · master `dac4337`）

| 事实 | 出处 | 说明 |
|---|---|---|
| **master HEAD** | 本地 + 远端 = `dac4337` | PR-14 已合入 + HANDOFF §9 已刷新 |
| **测试基线** | `uv run pytest -q` = **110 passed** | 无预置 red 骨架，PR-16 从零建 |
| **PR-15 模板结构** | `backend/app/agent/skills/candidate_merge/v1_0_0/` | 三件套 `skill.yaml + prompt.md + examples.yaml`，无 Python 代码文件（走 BaseSkill 通用管道） |
| **PR-15 test 结构** | `tests/test_stage5_s5_10_candidate_merge.py` | monkeypatch `app.agent.llm_adapter.call_llm_json` → 直接 `BaseSkill(SKILL_DIR).execute(input)` |
| **`_ARTIFACT_TYPE_MAP` 已包含 profile** | engine.py:55 | `"candidate-profile": "candidate_profile"` PR-14 已预登记；无对应 ref_id 提取逻辑（走 `generic`+`data` 兜底还是新加？见 Q5） |
| **`resumes.tags` 字段存在** | `models/resume.py:45` | `Mapped[list[str] \| None] = mapped_column(JSON)` —— **PR-16 输入 `existing_tags` 的来源** |
| **PR-15 `task_type` 命名 = lowercase** | `candidate_merge/skill.yaml:5` | `task_type: merge_candidates`（单数字符串） |
| **TASKS §S5-11 命名 = SCREAMING 复数** | `TASKS-STAGE5.md:242` | `task_types: [PROFILE_CANDIDATE]` —— **与 PR-15 既成事实漂移**（见 Q1） |
| **tasks.status comment 用 SCREAMING** | `models/task.py:24` | comment 里写 `MATCH_SCORE/MERGE_CANDIDATES/PROFILE_CANDIDATE/GENERATE_JD/GENERAL_QA/UNKNOWN` | 
| **orchestrator-reason output_schema** | `orchestrator_reason/skill.yaml:26-28` | `task_type` 描述："与下游 dispatchable Skill 的 task_type 对齐（如 match / merge_candidates / unknown）" —— lowercase 单数 |
| **`route_task_type`** | `tool_router.py:189-194` | 从 reason_output 读 `task_type`，与 skill.yaml `task_type` 字段 1:1 对齐；缺失返 `"unknown"` |
| **PR-15 输入 schema `resumes[].tags`** | `candidate_merge/skill.yaml:28` | 字段名叫 `tags`（不是 `existing_tags`） |
| **TASKS §S5-11 输入契约** | `TASKS-STAGE5.md:243` | `input: { parsed_content, existing_tags: string[] }` —— **字段名与 PR-15 不同**（见 Q3） |
| **TASKS §S5-11 输出契约** | `TASKS-STAGE5.md:244` | `output: { profile_tags: string[], summary, strengths: string[], risks: string[] }` |
| **TASKS §S5-11 max_retries** | `TASKS-STAGE5.md:245` | `max_retries: 0`（与 PR-15 一致） |
| **验收判据 §2 归一去重** | `TASKS-STAGE5.md:248` | 大小写归一（"Python" ≡ "python"），合并后唯一 —— **归一化在 Skill 内还是外部消费者？**（见 Q2） |
| **BaseSkill 是否有 tag 归一 hook** | `app/agent/base_skill.py`（未逐字读，PR-11/12 交付） | 通用管道走 jsonschema，**无自定义后处理钩子**；归一逻辑必须写在 Skill 外部（PR-16 提供 helper？前端处理？） |
| **前端消费点** | grep frontend/src/ 无 `profile_tags` / `candidate-profile` 匹配 | PR-17/18 才落地，本 PR 无 UI 依赖，纯后端 Skill |
| **REST 端点** | api-contract 无 profile 专属端点 | PR-16 **不新增 REST**，Skill 通过 Tool Router 分发（与 PR-15 同） |
| **⚠️ 端到端路由缺口**（跨 PR-15/16） | engine.py:153 + orchestrator_plan/prompt.md:6 + reason/prompt.md:6 | reason 只列 `match / merge_candidates / unknown`；plan 只示范 `search_resumes / read_jd`；`run_plan` 不注入 dispatchable 清单 → **candidate-merge / candidate-profile 均未打通"自然语言 → LLM plan → dispatch"路径**；PR-15 已存在此债务未登记，PR-16 需明确不修（登记为追债项 11，见 Q1） |
| **三命名空间共存** | skill.yaml.skill_id / skill.yaml.task_type / tasks.task_type | `candidate-profile`（连字符）≠ `profile_candidate`（下划线）≠ `PROFILE_CANDIDATE`（SCREAMING）三层命名并存，Q1 追债项 10 明列 |

**综合观察**：本 PR 作用面小（三件套 + 测试 = ~200 行 + 4 测试），**主要风险不在实现，在契约漂移**：命名（Q1 三命名空间）、字段名（`existing_tags` vs `tags`）、归一化归属边界、**端到端路由缺口（PR-15 已埋，PR-16 显式不修，登记追债项 11）**。契约裁完即可开工。

---

## PR-16 交付范围（DECISION 前必须明确的边界）

**范围内**：
- `backend/app/agent/skills/candidate_profile/v1_0_0/` 三件套（skill.yaml + prompt.md + examples.yaml）
- `backend/tests/test_stage5_s5_11_candidate_profile.py`（TC-S5-11-1..4）
- Q5 若采纳方案 C：`engine.py::_build_artifacts` 数据型分支 + 1 engine 单测

**范围外，本 PR 不做**：
- **端到端路由打通**（登记为追债项 11，Stage 5.1 修）—— 交付后 candidate-profile 与 candidate-merge 一样是"孤立 Skill"，只能被 REST 硬编码 plan 或前端拼装 plan 分发，不能被自然语言用户消息触发
- reason / plan skill 描述及 examples 补 `profile_candidate` / `candidate-profile`（改一行描述**不足以让 plan 侧发出对应 tool_name**；真正修复需 plan 侧动态注入 dispatchable 清单，属追债项 11 主体，见 §十二）
- tasks.task_type 相关命名 refactor（Q1 方向 B）
- 落库副作用（Q6）

**执行体必读**：DECISION §合同 会显式声明"本 PR 交付孤立 Skill，路由由追债项 11 修"；不得顺手改 reason/plan prompt / engine.run_plan 尝试修路由 —— 会触发 §十三 边界。

---

## Q1 · `task_type` 命名一致性 —— **已裁定：方向 B（承认双语义共存）**

### 背景（含 kickoff 阶段 grep 追查结果）

**grep 追查结果**（`backend/app/` 全量）：

- **写入侧 SCREAMING 命名，仅 2 处**：
  - `app/models/task.py:24` comment: `MATCH_SCORE/MERGE_CANDIDATES/PROFILE_CANDIDATE/GENERATE_JD/GENERAL_QA/UNKNOWN`
  - `app/api/v1/agent.py:159` skip-to-score 端点写入: `task_type="MATCH_SCORE"`
- **skill.yaml `task_type` 全部 lowercase**（7 个 skill）：`merge_candidates / match / reason / plan / reflect / reflect_plan / reflect_act`
- **读取侧对 SCREAMING 的依赖**：**零**（无 `if task_type == "MATCH_SCORE"` 类比较；`route_task_type` 从 ReasonOutput 提 lowercase key）

**追查暴露的语义分层**：`task_type` 字段名承载了**两套不同语义**：

| 位置 | 语义 | 命名惯例 | 谁写入 |
|---|---|---|---|
| `tasks.task_type` 表列 | **业务任务分类**（含 GENERATE_JD/GENERAL_QA 等非 dispatch key） | SCREAMING（`MATCH_SCORE` / `PROFILE_CANDIDATE`） | REST 端点 INSERT |
| `skill.yaml.task_type` | **Skill 分派键**（tool_router 目标） | lowercase（`match` / `merge_candidates`） | Reason skill 产出 |

**关键证据**：PR-14 的 `agent.py:159` 写入 `task_type="MATCH_SCORE"`，但**没有任何 skill 的 `task_type` 等于 `MATCH_SCORE`**（jd_candidate_matching skill 的 `task_type` 是 `match`）—— 说明 PR-14 落地时已经**默认这两个是不同概念**。

### 裁定：方向 B —— 承认双语义共存，PR-16 不做命名 refactor

- **PR-16 skill.yaml** → `task_type: profile_candidate`（lowercase 单数字符串，与 PR-15 对称）
- **不动** `models/task.py:24` comment（保留 SCREAMING 业务分类语义）
- **不动** `app/api/v1/agent.py:159`（保留 `task_type="MATCH_SCORE"`）
- **不动** 其他任何 task_type 相关文件

### 追债登记（STEP6 §五 强制项）

PR-16 STEP6 §五 新增两条声明，登记为 HANDOFF §9.3 追债项第 10、11 条：

**追债项第 10 条 · `task_type` 三命名空间共存**（Q1 直接引出）

> **三命名空间共存，语义各不同**：
> | 命名空间 | 惯例 | 示例 | 谁写入 |
> |---|---|---|---|
> | `skill_id` / `tool_name`（分发键） | **连字符 lowercase** | `candidate-merge` / `candidate-profile` | skill.yaml `skill_id` 字段；plan 输出 `tool_name` |
> | `skill.yaml.task_type`（意图键） | **下划线 lowercase** | `merge_candidates` / `profile_candidate` | skill.yaml `task_type` 字段；reason 输出 `task_type` |
> | `tasks.task_type` DB 列（业务分类） | **SCREAMING** | `MATCH_SCORE` / `PROFILE_CANDIDATE` | REST 端点 INSERT |
>
> **本 PR 暂行**：PR-16 skill.yaml `skill_id: candidate-profile` + `task_type: profile_candidate`，与 PR-15 三命名空间格式完全对称；不动任何既有代码。
> **Stage 5.1 收敛方向**：合并语义 or 拆字段名（skill 侧改 `dispatch_key`；引入 `task_type → tool_name` 映射表让 LLM 不再自己翻译"下划线↔连字符"）；触发条件：多进程部署前 / 前端消费两套 task_type 迷惑时 / **追债项 11 修复时必须一并处理**。

**追债项第 11 条 · orchestrator reason/plan 未登记 dispatchable Skill，自然语言路由不通**（跨 PR-15/16 共同债务）

> **现状实测**：
> - `orchestrator_reason/prompt.md:6` 仅列 `match / merge_candidates / unknown`，**不含 `profile_candidate`**
> - `orchestrator_plan/prompt.md:6` 只字面说"tool_name 必须命中 dispatchable Skill ID 或内置工具（search_resumes / read_jd）"，**未注入具体 dispatchable 清单**
> - `orchestrator_plan/examples.yaml` 仅示范 `search_resumes / read_jd`
> - `engine.py:153 run_plan` 直接 `skill.execute(plan_input)`，**不动态注入 registry 里的 dispatchable skill 列表**
> - 结论：**当前经"自然语言 → reason → plan"能 dispatch 的 tool_name 只有 `search_resumes / read_jd`**；`create_match_score` 靠 `agent.py:149` REST 端点硬编码 plan 绕开 LLM；`candidate-merge` / `candidate-profile` 既不在 plan 示例、也不在 REST 硬编码里 —— **PR-15 candidate-merge 也未端到端打通**
>
> **本 PR 暂行**：PR-16 = Skill 三件套 + 单测（与 PR-15 对称，孤立 Skill 交付），**显式声明本 PR 不打通端到端路由**
>
> **Stage 5.1 收敛方向**：
> - `orchestrator_reason/prompt.md` 补 `profile_candidate` 意图（reason 侧）
> - `orchestrator_plan/prompt.md` 或 `run_plan` 动态注入 registry.list_dispatchable() 的 tool_name 清单 + 描述（plan 侧知道有哪些 skill）
> - 引入 `task_type → tool_name` 映射表（消除 LLM 自行做"下划线→连字符"翻译的可靠性风险）
> - 与追债项 10 同 PR 收敛（否则拆命名空间时路由测试无基础）
>
> **风险等级**：此债务不修，`candidate-merge / candidate-profile / jd-candidate-matching` 永远无法通过用户自然语言触发；当前仅靠 REST 硬编码 plan 或前端手动拼装 plan 兜底。

### 需追查项 —— 已完成

- [x] `grep MATCH_SCORE|MERGE_CANDIDATES|PROFILE_CANDIDATE backend/app/` = 写入侧 2 处（comment + agent.py:159），读取侧 0 处
- [x] 三命名空间存在性已确认（skill_id 连字符 / task_type 下划线 / tasks.task_type SCREAMING）
- [x] orchestrator reason/plan prompt 及 examples 未登记 `profile_candidate` / `candidate-profile`，自然语言路由缺口已确认（见追债项 11）

---

## Q2 · tag 归一化 & 去重逻辑归属（**验收判据 §2 直接影响**）

### 背景

TASKS §S5-11 验收判据 §2：`existing_tags=["Python"]` + 模型给 `"python"` → 合并后**唯一**（大小写归一去重）。

问题：这个"归一 + 合并"逻辑写在哪儿？

### 三个方案

- **A. Skill 内做**（BaseSkill 执行后自动后处理 `profile_tags`）
  - **优点**：Skill 输出即是最终结果，消费者拿到就是干净的
  - **缺点**：BaseSkill 通用管道**没有"后处理钩子"**（PR-15 走 jsonschema 校验就结束）；要引入必须给 BaseSkill 加 hook 或专门写一个 CandidateProfileSkill Python 子类打破当前"三件套即所有"的对称模式

- **B. LLM 提示词负责归一**（prompt.md 里明确要求"合并 existing_tags，大小写归一去重，输出 profile_tags"）
  - **优点**：零代码改动，最小摩擦；PR-15 candidate_merge 也是靠 prompt 表达业务规则（判定 MERGE/SUGGEST/KEEP_SEPARATE）
  - **缺点**：LLM 不 100% 可靠；有可能返一份未去重的 tags（虽然 schema 允许，但违反业务判据）；TC-S5-11-2 需专门 mock 一份未归一的 payload 断言"Skill 层视为通过（LLM 责任），或**测试内 assert 归一后的 profile_tags**"

- **C. 消费方（Orchestrator engine 或 REST 端点）做**（Skill 只出 profile_tags，engine 拿到后合并 existing_tags + 归一）
  - **优点**：Skill 单一职责，LLM 只管"从简历提取标签"
  - **缺点**：跨模块耦合，PR-16 交付面外溢；PR-16 STEP6 就得动 engine.py 或新加消费函数

### 我的建议：**方案 B（prompt 负责归一）+ 测试通过 mock 精确注入判据**

**理由**：
1. PR-15 已用 prompt 表达业务规则（"MERGE 时置信度偏高、KEEP_SEPARATE 应偏低"），PR-16 同模式对称
2. 方案 A 破坏"三件套即所有"对称美，一个 Skill 一个 Python 类的模式扩散风险大
3. TC-S5-11-2 明确是"验证归一效果"—— mock LLM 已归一好的 payload（`profile_tags: ["Python", "SQL"]` 无 duplicate），测试断言 output 无重复即可（不测 LLM 归一能力，测 Skill 契约）
4. 方案 C 是 PR-17 前端渲染时可以再做一遍前端去重的兜底（前后端各自防御），但 PR-16 不必外溢

**具体做法**：
- `prompt.md` USER_TEMPLATE 明确列出："在生成 `profile_tags` 时，请与 `existing_tags` 合并并按大小写归一去重（如 'Python' 与 'python' 视为同一标签，输出规范化后的第一个出现形式或全小写形式）"
- `TC-S5-11-2` 用 monkeypatch 让 LLM 返 `{"profile_tags": ["Python", "SQL"], ...}`（已归一），断言 `set(result.output["profile_tags"]) == {"Python", "SQL"}` 且长度=2
- **不改 BaseSkill**、**不引入 Python 后处理**

**待裁定**：方案 B 采纳？还是希望方案 A（BaseSkill 加后处理 hook）以提供 defense-in-depth？

---

## Q3 · 输入字段名 `existing_tags` vs `tags`（**契约字面漂移**）

### 背景

- **TASKS §S5-11:243**：`input: { parsed_content, existing_tags: string[] }` —— 字段名 `existing_tags`
- **PR-15 既成**（candidate_merge/skill.yaml:28）：字段名叫 `tags`（简历上直接挂）

### 分歧

PR-16 input_schema 该用哪个？

- **A. 按 TASKS 字面：`existing_tags`**
  - 语义清晰（"已有的手工标签"，与 skill 生成的 `profile_tags` 对偶）
  - 与 PR-15 命名不冲突（candidate_merge 输入是 `resumes[].tags`，语义不同：是 "简历自带的标签"）
- **B. 与 PR-15 对齐：`tags`**
  - 简短
  - 但语义混淆（"哪种 tags？"），需 description 说明

### 我的建议：**方案 A（`existing_tags`）**

理由：PR-15 的 `tags` 是简历子字段（`resumes[].tags`），PR-16 的输入是"当前候选人手工已有的 tags"，语义确实不同 —— 命名分离更好。TASKS 字面也是这么写，无漂移。

**待裁定**：采纳 `existing_tags`？

---

## Q4 · 空 `parsed_content` 边界（TC-S5-11-4）

### 背景

TC-S5-11-4：空 `parsed_content` 边界**不崩、返回合理标签或空**。

### 两个方案

- **A. Schema 层拒绝空输入**（`parsed_content: type: object, minProperties: 1`）
  - Skill 直接返 FAILED（validation error），前端 / engine 处理
  - **优点**：明确契约违约
  - **缺点**：与判据"返回合理标签或空"矛盾（判据允许空标签正常出返 SUCCESS）

- **B. Schema 允许空，prompt 处理**
  - `parsed_content: type: object`（无 minProperties）
  - prompt 明确"若 parsed_content 为空，返回 `profile_tags: []` + 简短 summary（如'简历内容为空'）"
  - Skill 视为 SUCCESS 出空结果
  - **符合判据"不崩、返合理标签或空"字面**

### 我的建议：**方案 B**

判据字面就是"合理标签或空"，方案 B 直接对齐。TC-S5-11-4 mock LLM 返 `{"profile_tags": [], "summary": "无内容", "strengths": [], "risks": []}` 断言 success + profile_tags 为空即可。

**待裁定**：采纳方案 B？

---

## Q5 · Artifact ref_id 提取（`_ARTIFACT_TYPE_MAP` 兼容）

### 背景

`engine.py:59-82 _build_artifacts` 里，`match_score` / `resume` / `jd` 类型有 ref_id 提取分支；`candidate-profile` 的输出 `{profile_tags, summary, strengths, risks}` **无 id 字段**。当前代码走 `generic` fallback？还是应新增分支？

再看代码流程：

```python
artifact_type = _ARTIFACT_TYPE_MAP.get(tool_name, "generic")  # 拿到 "candidate_profile"
# ... ref_id 提取分支只覆盖 match_score/resume/jd
# 若 ref_id is None 且 artifact_type != generic：
if artifact_type == "generic":
    item["data"] = output
elif ref_id is not None:
    item["ref_id"] = str(ref_id)
else:
    # 引用型但未提取到 ref_id → 降级为 generic
    item["type"] = "generic"
    item["data"] = output
```

**候选人-profile 会走"降级为 generic + data=output"** —— 前端能拿到完整 output，但 `type` 字段被覆盖回 `generic`，前端卡片路由靠 type 就走不到 "candidate_profile" 分支。

### 三个方案

- **A. 保持现状**（降级为 generic + data=output）
  - **优点**：零改动
  - **缺点**：`_ARTIFACT_TYPE_MAP` 里 `candidate-profile` 的登记形同虚设，前端无法用 type 路由；违反 HANDOFF §9.3 追债项 3 的初衷（type 与前端渲染器同步）

- **B. `_build_artifacts` 加规则**：`candidate_profile` 是**数据型 artifact**（无 ref_id），直接嵌 output 进 `data`，保留 `type=candidate_profile`
  ```python
  elif artifact_type == "candidate_profile":
      item["data"] = output  # 保留完整 profile_tags/summary/strengths/risks
      # type 保持 candidate_profile 不降级
  ```
  - **优点**：前端能用 `type=candidate_profile` 路由到 ProfileCard 组件；语义明确
  - **缺点**：需改 engine.py（PR-14 交付物），触及 PR-16 主线外的文件（但**属于填 PR-14 预留位**，不算范围外）

- **C. 引入 `candidate_merge` 一并处理**（`_ARTIFACT_TYPE_MAP` 里 `candidate-merge` 同为数据型无 ref_id，PR-15 也没测过 artifact 出口）
  - 同 B，但把 `candidate_merge` 一并加进"数据型"分支
  - **优点**：一次归零，两个 Skill 对称
  - **缺点**：动到 PR-15 交付物的 artifact 出口语义（虽然 PR-15 无相关测试断言，但改动纳入 PR-16 STEP6 §五 声明即可）

### 我的建议：**方案 C**（B 的扩展版）

**理由**：
1. `candidate-merge` 与 `candidate-profile` 都是**数据型**（输出即结果，无 DB 引用），出口语义相同
2. PR-14 已在 `_ARTIFACT_TYPE_MAP` 预登记两者，出口路径不闭合 = 债务
3. 一次改齐避免 PR-16 之后再来一个 PR 补 candidate_merge

**具体改动**（engine.py:73-82 附近）：
```python
elif artifact_type in {"candidate_merge", "candidate_profile"}:
    item["data"] = output  # 数据型 artifact，无 ref_id，保留完整 output
elif ref_id is not None:
    item["ref_id"] = str(ref_id)
else:
    item["type"] = "generic"
    item["data"] = output
```

需追加 1 个单测：`test_stage5_s5_11_candidate_profile.py::test_artifact_shape_no_ref_downgrade` 或 `test_stage5_s5_09_engine.py::test_build_artifacts_data_types`。

**待裁定**：方案 C 采纳（含 candidate_merge 一并归零）？还是保守方案 B（仅本 PR 的 candidate_profile）？或方案 A（降级 generic）？

---

## Q6 · Skill 是否有落库副作用（写 `resumes.tags`）

### 背景

TASKS §S5-11 判据没有明说"生成后是否要写回 `resumes.tags`"。类比 PR-15 candidate-merge：judgement 出 `action=MERGE/master_resume_id` 但**不自动执行合并**（写库/UI 层做）。

### 建议：**Skill 只出数据，不落库**

- Skill 契约：input `{parsed_content, existing_tags}` → output `{profile_tags, summary, strengths, risks}`
- 落库（若需要）由 REST 端点（PR-14 已交付 `POST /agent/skip-to-score` / `POST /agent/execute-plan` 均可承载）或未来专门端点做
- 与 PR-15 保持对称

**待裁定**：确认 Skill 无副作用，无需 PR-16 交付落库路径？

---

## Q7 · prompt.md 设计要点 & LLM 输出稳定性

### 背景

TC-S5-11-3 校验 output_schema 失败降级：prompt 需强约束 LLM 输出四字段（`profile_tags`, `summary`, `strengths`, `risks`）；缺一即 SUCCESS=False。

### 建议

prompt.md 结构对齐 PR-15：
- SYSTEM_PROMPT：角色（"资深人才画像分析师"）+ 原则（客观、合规、不基于性别/年龄/婚育/地域评价、只输出 JSON）
- USER_TEMPLATE：{{ parsed_content }} + {{ existing_tags }}
- 输出要求：明列四字段 + 归一去重规则（Q2）
- Few-shot examples in `examples.yaml`：3 个（正常生成、与手工合并去重、空 parsed_content）

需追加"合规"约束（Stage 4/PR-15 已建立此风格），避免 LLM 生成歧视性标签。

**待裁定**：以上 prompt 设计要点无异议？examples.yaml 3 个够用？

---

## Q8 · 测试策略（对齐 PR-15）

### TC-S5-11-1..4 已明列判据

- **TC-S5-11-1**：`profile_tags` 非空 → mock LLM 返合法 payload，断言 success + 非空
- **TC-S5-11-2**：existing_tags 合并去重 → mock LLM 返已归一 payload（Q2 方案 B），断言无重复 + 长度符合
- **TC-S5-11-3**：schema 失败降级 → mock LLM 返缺字段 payload，断言 success=False
- **TC-S5-11-4**：空 parsed_content 边界 → mock LLM 返空结果，断言 success=True + tags=[]

### 建议

- 100% 沿用 PR-15 `test_stage5_s5_10_candidate_merge.py` 结构：`monkeypatch app.agent.llm_adapter.call_llm_json` + `BaseSkill(SKILL_DIR).execute(input)`
- 不新建 fixture / conftest
- 测试文件命名：`tests/test_stage5_s5_11_candidate_profile.py`
- **若采纳 Q5 方案 C**（改 `_build_artifacts`），追加 1 个 engine 层测试断言 `data` 字段非空、`type` 保持 `candidate_profile`

**待裁定**：测试策略无异议？基线预期 110 → 114 or 115（含 Q5 追加测试）？

---

## Q9 · TASKS §S5-11 文档勘误处理

### 背景

发现 3 处 TASKS 权威文档与实际 / 提议实现漂移：

1. `task_types: [PROFILE_CANDIDATE]` vs 实际 lowercase 单数（Q1）
2. TASKS §S5-10 同样写 `task_types: [MERGE_CANDIDATES]`（第 225 行），实际 PR-15 已是 lowercase —— **PR-15 已交付事实**
3. `existing_tags` 字段名与 PR-15 的 `tags` 不重合（Q3 沿用 TASKS 命名 = 无漂移）

### 建议：**不改 TASKS，PR-16 STEP6 §五 声明"文档字面 vs 实现差异"归档**

**理由**：
- TASKS 是双盲评审合并版，改动需比对 commander/executor 两版原始稿谨慎（避免搅动权威文档基线）
- STEP6 §五 声明本身就是 canonical 追溯位置，未来其他 PR 遇到同问题可查到"已知漂移，选实现口径"
- 若指挥官希望反向改 TASKS，另开 docs-only commit（一次修 S5-10 + S5-11 两处），不入 PR-16

**待裁定**：不改 TASKS + STEP6 §五 归档 = OK？还是希望本 PR 顺手改 TASKS 两处？

---

## §十二 · 顺手清扫候选

PR-16 **无顺手清扫**。Q1 方向 B 明确不触及任何写入侧命名代码（tasks 表 comment / agent.py:159 均保留）；Q5 若采纳方案 C，engine.py 改动**已归入主线**（不算顺手）。

### ⚠️ 特别澄清：reason/plan skill 描述补 `profile_candidate` **不是有效修复**

原 QUESTIONS 曾提出"顺手在 `orchestrator-reason/skill.yaml` 描述里补 `profile_candidate`"作为可选建议 —— **现撤回**。

**理由**（追债项 11 引出）：
- 改一行 reason skill 描述字符串 → 让 reason LLM 可能输出 `task_type: profile_candidate`
- 但 plan 侧仍不知道 `candidate-profile` 是有效 tool_name（plan prompt/examples 未登记）
- LLM 也需要自己完成"下划线 profile_candidate → 连字符 candidate-profile"翻译，无可靠性保证
- **实际路由仍不通**，只是"欺骗自己看起来修了"

**结论**：**本 PR 不要改 reason/plan 任何 prompt 或描述**。真正修复需在追债项 11 里同时做：
1. reason 侧列全意图值域
2. plan 侧动态注入 dispatchable 清单（或 examples 覆盖所有 skill）
3. 引入 `task_type → tool_name` 映射消除 LLM 翻译负担

**待裁定**：确认 PR-16 无 §十二 顺手清扫（reason/plan 补描述已撤回，归入追债项 11）？

---

## §十三 · 求助边界（预估 9 条）

PR-16 执行时可能触发的求助点：

1. **BaseSkill 通用管道对 `parsed_content: type: object` 空对象 `{}` 的处理与预期不符**（比如 jsonschema 默认拒绝空对象）：停下汇报，考虑加 `type: [object, null]` 或调整 schema
2. **`llm_adapter.call_llm_json` 签名或行为在 PR-13/14 之后有 breaking change**（PR-15 后未再改动，理论稳定）：停下汇报
3. **TC-S5-11-2 mock 后 profile_tags 断言方式与判据"合并去重"字面理解不一致**（Q2 归一 mock 已归一化）：停下汇报讨论
4. **`_ARTIFACT_TYPE_MAP` 相关改动（Q5 方案 C）触发 PR-15 或 PR-14 既有测试 regression**（虽然 grep 未见断言 `candidate_merge` artifact 出口，但测试基线倒退即回归）：pytest < 110 停下汇报
5. **Skill test 中 `monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", ...)` 路径失效**（模块结构变化）：停下汇报核对 llm_adapter 位置
6. **测试基线倒退**：pytest < 110 = 回归，停下汇报（无论 Q5 方案）
7. **⚠️ 执行体误改 reason/plan skill 尝试"修路由"**（§十二 已明确撤回；若发现"改一行 prompt 就能让路由通"的诱惑）：停下汇报 —— 属追债项 11 主体，不是本 PR 顺手
8. **⚠️ 执行体触碰 tasks.task_type comment 或 agent.py:159 SCREAMING 字面量**（Q1 方向 B 明确保留）：停下汇报
9. **发现新的命名空间漂移**（除已登记的 skill_id 连字符 / task_type 下划线 / tasks.task_type SCREAMING 三层外）：停下汇报，追债项 10 需扩表述

**待裁定**：以上 9 条边界是否同意？还有别的须提前 flagged 的边角？

---

## §附 · 建议 commit 拆分（供参考，执行体可自选）

**3 commit 版**（推荐，PR-15 就是 3 commit）：

1. `test(stage5): PR-16 red-test skeleton (TC-S5-11-1..4)` — 建 `tests/test_stage5_s5_11_candidate_profile.py` 骨架 + skill 空目录
2. `feat(stage5): S5-11 candidate-profile skill three-parter (skill.yaml + prompt.md + examples.yaml)` — 三件套落地 + TC 转绿
3. `feat(stage5): _ARTIFACT_TYPE_MAP data-type artifacts (candidate_merge + candidate_profile)` — Q5 方案 C 改 engine.py + 追加 1 engine 单测（若采纳 Q5-C 才需）

**Q1 方向 B 已裁定：无 comment / agent.py 改动**，不产生额外 chore commit。

**若 Q5 采纳方案 A/B**（不改 _ARTIFACT_TYPE_MAP 或只改 candidate_profile 一处）：省 1 commit 变 2 commit（skeleton + 三件套）。

**若采纳 §十二 可选建议**（reason skill 描述补 profile_candidate）：可并入 commit 2 或独立 `docs(stage5): document profile_candidate in orchestrator-reason` 单 commit。

**待裁定**：commit 拆分建议 OK？还是希望更细/更粗？

---

## 汇总：9 问 + 附加

| # | 主题 | 建议 |
|---|---|---|
| Q1 | task_type 命名一致性 | **✅ 已裁定：方向 B（三命名空间共存 · PR-16 skill_id=candidate-profile 连字符 / task_type=profile_candidate 下划线 · 不动 tasks.task_type SCREAMING · 追债项第 10 条登记）** |
| Q2 | tag 归一化归属 | **方案 B（prompt 负责归一 + 测试 mock 精确注入）** |
| Q3 | 输入字段名 | **`existing_tags`（沿用 TASKS 字面）** |
| Q4 | 空 parsed_content | **方案 B（schema 允许空 + prompt 处理 + Skill success 出空结果）** |
| Q5 | Artifact ref_id | **方案 C（`_ARTIFACT_TYPE_MAP` 数据型分支含 candidate_merge + candidate_profile）** |
| Q6 | Skill 落库副作用 | **无副作用，与 PR-15 对称** |
| Q7 | prompt 设计 | **对齐 PR-15：合规约束 + 四字段强约束 + 3 个 few-shot** |
| Q8 | 测试策略 | **沿用 PR-15，基线 110 → 114 或 115** |
| Q9 | TASKS 文档勘误 | **不改 TASKS，STEP6 §五 归档** |
| **⚠️ 追债项 11** | **端到端路由缺口（PR-15/16 共同债务）** | **本 PR 显式不修 · reason/plan 不动 prompt · Stage 5.1 与追债项 10 同 PR 收敛** |
| 附 | §十二 顺手清扫 | **无**（reason/plan 补描述已撤回，归入追债项 11） |
| 附 | §十三 求助边界 | **9 条**（新增 §十三 #7/#8 明确不许改 reason/plan / SCREAMING 字面量） |
| 附 | commit 拆分 | **3 commit（skeleton + 三件套 + engine artifact）** |

**请指挥官逐项裁定，或"全部采纳"**。裁定后我出 `PR16-KICKOFF-DECISION.md`，执行体照做。
