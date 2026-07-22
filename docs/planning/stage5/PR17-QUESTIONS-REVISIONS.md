# PR-17 KICKOFF-QUESTIONS · 修订建议清单（供指挥官裁定）

> 关联：`docs/planning/stage5/PR17-KICKOFF-QUESTIONS.md`（初稿，2026-07-22）
> 目的：在出 `PR17-KICKOFF-DECISION.md` 前，先把评估中发现的 **事实错误 / 前提失真 / 文档一致性冲突** 列项，交由指挥官逐项裁定。裁定后并入 DECISION。
> 说明：本文件只列修订建议，**不进 commit**（随 DECISION 一并走 docs-only 直推或本分支）。

---

## A 类 · 阻断级事实修正（出 DECISION 前必须改）

### A1 · PR 编号重置与 PR-16 既有文档冲突

- **现状（初稿）**：`PR17-KICKOFF-QUESTIONS.md:6` 已声明"本 PR = PR-17（路由修复），原前端 PR 顺延为 PR-18/19"。
- **冲突事实**：PR-16 DECISION §十七 与 PR-16 STEP6 报告 §八 都写明"**下一个 PR-17 = 前端 SSE Hook + ChatCenter**"。两份既存文档把"PR-17"绑定给了前端范围。
- **后果**：指挥官在 PR-16 FF-merge 时要落地的 `HANDOFF §9.6`（"PR-17 前端起手路径"）与此 PR-17 真实范围（路由修复）直接打架。
- **修订建议**：DECISION 显式加一条"PR 编号重规划说明"，且 **PR-16 FF-merge 时同步修正** PR-16 STEP6 报告 §八 与 HANDOFF §9.6 的"PR-17 = 前端"措辞（改为"PR-17 = 路由修复，前端顺延 PR-18/19"）。
- **裁定选项**：
  - (a) 采纳重规划，FF-merge 时同步改 PR-16 两份文档的边角措辞；
  - (b) 维持 PR-16 旧编号（即本路由修复用 PR-18，前端再顺延）—— 但需同时改初稿第 6 行与全文"PR-17"指代。

### A2 · master HEAD 前提失真 + 仓库状态缠结

- **现状（初稿）**：`:10` 写"master `bc6c2f2`，PR-16 kickoff 已合入"；`:16` 写"PR-17 必须等 PR-16 FF-merge 后从新 master 拉起"。
- **实测事实**（2026-07-22 现场核验）：
  - 本地 `master` HEAD = **`66d242c`**（= PR-16 全部 4 commit：`d762e79` / `295b8e9` / `ab99b43` / `66d242c`）；
  - `master` 相对 `origin/master` **ahead 4**；
  - `origin/master` = `bc6c2f2`；`origin/feat/pr-16-s5-11-candidate-profile` = `66d242c`（已 `-u` 推送）；
  - 当前工作分支即 `master`。
- **后果**：初稿"PR-16 未合入、必须等 FF-merge"的前提在**当前本地状态已不成立**；且仓库处于 master / 分支指针缠结态（`master` 与 feature 分支指向同一 hash），若据此拉 PR-17 base ref 会混乱。
- **修订建议**：DECISION §前置事实改写——**先裁定仓库状态**，再写 base ref：
  - (a) 维持"干净 FF-merge"叙事：把本地 `master` reset 回 `bc6c2f2`，仅留 `origin/feat/pr-16-*` 作为待合分支；PR-17 从 `bc6c2f2` 起（与你此前说的"FF-merge commit message 锚一句 branch was pushed before merge review"一致）；
  - (b) 承认 `master` 已含 PR-16：直接推 `origin/master` 到 `66d242c`，PR-17 从 `66d242c` 起（无FF-merge动作）。
- **裁定选项**：(a) reset 回 `bc6c2f2` 走干净 FF-merge / (b) 接受 master 已含 PR-16 直推。

### A3 · additionalProperties 矛盾（会误导 DECISION 的事实错误）

- **现状（初稿）**：`:21`「若 `dispatchable_tools` 未声明在 `orchestrator-plan input_schema` 里，**直接注入会被 schema 校验拒**」；`:22`「`additionalProperties` 未指定（jsonschema 默认允许额外字段）」。
- **实测事实**：
  - `orchestrator_plan/skill.yaml` 的 `input_schema` **没有 `additionalProperties: false`**（已读 `orchestrator_plan/v1_0_0/skill.yaml`）；
  - `base_skill.validate_input`（`base_skill.py:167-174`）用标准 `jsonschema.validate`——**未设 `additionalProperties: false` 时默认允许额外字段**，`run_plan` 注入 `dispatchable_tools` 不会被拒。
  - 两行自相矛盾，且 `:21` 的"会被拒"结论错误。
- **后果**：若按错误前提写 DECISION，Q1 方案 γ 的"加进 schema 避免被拒"理由不成立；更危险的是可能误导执行体把 `dispatchable_tools` 加进 `required`——届时会破坏既有 `run_plan` 调用方（只传 `reason_output`）与 PR-12 plan 测试（触发初稿 §十三#2 的真实报错）。
- **修订建议**：
  - `:21` 改为"未声明在 schema 也能注入成功（jsonschema 默认允额外字段）"；
  - Q1 方案 γ 的理由从"避免被拒"改为"为结构清晰与文档化显式声明"；
  - **DECISION 强制约束**：`dispatchable_tools` 只能进 `input_schema.properties`，**绝不可进 `required`**（否则既有 `run_plan` / PR-12 plan 测试全红，即 §十三#2 真实触发）。
- **裁定选项**：采纳纠错 + 强制"不入 required"约束（建议默认采纳，无需选项）。

### A4 · 测试基线数字过时

- **现状（初稿）**：`:393`「110 或 114 → +5 = 119 或 120 passed」。
- **实测事实**：PR-16 交付后实跑 **115 passed**（110 基线 + 4 Skill + 1 engine，已核验）。
- **修订建议**：基线改 **115**；PR-17 后预期 **115 + 5 = 120 passed**。DECISION 与 §十三#6 阈值同步改为 115 / 120。
- **裁定选项**：采纳校正值（默认采纳）。

### A5 · Q9 追查项实答（create_match_score 是悬空引用）

- **现状（初稿）**：`:342` 把 `create_match_score` 标注为"是内置工具的名字？还是 skill 别名？需在阶段 0 追查"；`:344-348` 列追查清单。
- **实测事实**（已 grep 全仓 + 读 `tool_router.py:54-90`）：
  - `BUILTIN_TOOLS` 仅含 `search_resumes` / `read_jd`，**不含 `create_match_score`**；
  - 全仓无 `skill_id: create_match_score` 的 skill 文件；
  - 但它出现在 `agent.py:149` skip-to-score 硬编码 plan 的 `tool_name`，以及 `engine.py:51` `_ARTIFACT_TYPE_MAP["create_match_score"] = "match_score"`。
  - → 若 skip-to-score 走到 `tool_router.dispatch`，会 `not in BUILTIN_TOOLS` → `registry.get_skill` 返 None → `raise UnknownToolError`。这是 **PR-13/14 遗留潜在 bug**。
- **修订建议**：Q9 追查项直接给实答——**`create_match_score` 既非内置工具也非 skill，是 dangling tool_name**。DECISION §五 归档写明确结论 + 后续 PR 建议（要么注册进 `BUILTIN_TOOLS`，要么把 `agent.py:149` 硬编码 `tool_name` 改为 `jd-candidate-matching`）；**不要让它悄悄溜过**。保持"决定 1 = A 不动"有效，但须把真实身份写入归档而非留"待追查"。
- **裁定选项**：采纳实答 + 单列后续 PR 建议（默认采纳）。

---

## B 类 · 措辞微调（不阻断，但建议采纳）

### B1 · Q5 留痕（设计选择 vs 债 12）

- **现状（初稿）**：`:250` 把 reason 侧静态列举 vs Q2 自动派生映射表的异构，作为"设计选择"还是"新债 12"留待裁定；`:257` 倾向 A（不入债）。
- **评估**：reason 侧保持静态、plan 侧走动态——**两边异步，是真实（轻度）漂移**。建议即使不入债，STEP6 §五 也应登记一条 observation：**"若 Stage 5.2 起 dispatchable skill 频繁新增，reason 需改动态注入（方案 C）"**。
- **修订建议**：Q5 子问题裁定 = A（不入债），但 §五 明确登记该轻量 observation（是否升债 12 由指挥官在阶段 5 决定，本 PR 不自动升）。
- **裁定选项**：(a) A + 留 observation（推荐）/ (b) 直接升债 12。

### B2 · Q11 "已收敛"替代"已闭合"

- **现状（初稿）**：`:406 / :409` 用"✅ 已闭合（PR-17 `<hash>`）"。
- **评估**：债 10 只收敛了 **Y 方向**（自动派生映射）；X（拆字段名）/ Z（DB 迁移）明留 Stage 5.2。写"已闭合"易被误读为全闭环。
- **修订建议**：HANDOFF §9.3 措辞改为"**✅ 已收敛（PR-17 `<hash>`，Y 方向；X/Z 留 Stage 5.2）**"。
- **裁定选项**：采纳措辞修正（默认采纳）。

---

## C 类 · §十三 求助边界增补（建议新增 2 条）

### C1 · 开工前门槛（非运行时）—— 仓库状态裁定

- **对应 A2**：PR-17 分支 base ref 必须先裁定（A2 选项 a/b）。若执行体开工前发现 master 仍处缠结态（master = 66d242c 且 ahead origin/master 4），**立即停下汇报**，不擅自 reset / 不擅自起分支。
- **落入 §十三 序号 #9**（排在既有 #1–#8 后）。

### C2 · Q9 顺手修补的范围扩张风险

- **对应 A5**：若执行体在阶段 0 追查后"顺手"把 `create_match_score` 注册进 `BUILTIN_TOOLS` 或改名为 `jd-candidate-matching`（初稿 §十二 A 提及），会**扩大 PR-17 范围**（跨越"不动 REST 硬编码"的既定边界）。
- **约束**：DECISION 明确——Q9 只做"身份追查 + §五 归档"，**任何修复动作须停下汇报**，不得无声并进 commit 3。
- **落入 §十三 序号 #10**。

---

## D 类 · 待指挥官裁定的开放决策（与修订无关，纯采纳项）

以下在评估中判定"可直接采纳"，供指挥官一键确认：

| # | 建议 | 评估 |
|---|---|---|
| Q1 | 方案 γ（Jinja 注入，0 契约破坏） | ✅ 采纳（理由按 A3 纠错改写，且强制不入 `required`） |
| Q2 | 方案 B（registry 加载时自动派生 + 冲突 raise） | ✅ 采纳（已核验当前无冲突：match→jd-candidate-matching / profile_candidate→candidate-profile / merge_candidates→candidate-merge 互不重复，fail-fast 安全） |
| Q3 | 方案 B（Markdown 列表） | ✅ 采纳 |
| Q4 | 方案 B（含 BUILTIN_TOOLS） | ✅ 采纳（与 `engine.dispatchable_tool_names()` line 124-127 口径一致） |
| Q6 | 方案 A（dispatch 不消费映射表） | ✅ 采纳 |
| Q7 | 方案 A（依赖 reflect_plan 保护） | ✅ 采纳 |
| Q8 | 方案 A（reflect_plan 零改动） | ✅ 采纳 |
| Q9 | 决定 1 = A（不动 REST 硬编码） | ✅ 采纳（但 §五 归档须写 A5 实答） |
| Q10 | 4 集成 + 1 冲突 = 5 测试 | ✅ 采纳（**路径改**：走 `run_reason→run_plan→run_reflect_plan` 单元级组合 + mock LLM，**不**走 `start_chat`（需 redis/db/SSE，非 hermetic，§十三#7 已担心 PR-14 端点测试受扰）；基线改 120，见 A4；TC-PR17-3 依赖的 `jd-candidate-matching`(task_type: match) skill 存在，可行） |
| Q12 | 4 commit（或拆 5） | ✅ 采纳（建议默认拆 5：commit 3 偏大，按初稿说的 3a/3b 拆更稳） |

---

## 裁定汇总（供指挥官勾选）

- [ ] **A1** PR 编号重规划：(a) 采纳重规划+FF-merge 同步改 PR-16 边角 / (b) 维持旧编号（本路由修复用 PR-18）
- [ ] **A2** 仓库状态：(a) reset 回 `bc6c2f2` 走干净 FF-merge / (b) 接受 master 已含 PR-16 直推
- [ ] **A3** additionalProperties 纠错 + 强制 `dispatchable_tools` 不进 `required`（默认采纳）
- [ ] **A4** 测试基线 115 / 预期 120（默认采纳）
- [ ] **A5** Q9 实答：`create_match_score` 悬空；§五 写结论 + 单列后续 PR（默认采纳）
- [ ] **B1** Q5 子问题：A 不入债 + §五 留 observation（推荐）/ 升债 12
- [ ] **B2** Q11 措辞"已收敛"替代"已闭合"（默认采纳）
- [ ] **C1/C2** §十三 增补 #9/#10 求助边界（默认采纳）
- [ ] **D** 全部采纳 Q1γ/Q2B/Q3B/Q4B/Q6A/Q7A/Q8A/Q9决定A/Q10(改路径+基线)/Q12(拆5)

裁定后我出 `PR17-KICKOFF-DECISION.md`；依 AGENTS.md §4.1 docs-only 可直推 master（或随本分支），等你指令。
