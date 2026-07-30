# PR-26 · KICKOFF-QUESTIONS

> 关联：`docs/planning/stage5/MVP-VERIFY-RUN-REPORT.md` §4.1 复跑 · HANDOFF §9.3（本 PR 后新登记 §9.3.20）
> 起始 master HEAD：`747adc6`（PR-25 §9.3.17 CLOSED · §9.4 陷阱 14 已补）
> 上一轮验收 baseline：pytest **140 passed / 2 skipped** · ruff 0 全仓 · frontend build ✓ · migration head `b6c7d8e9f0a1`
> 类型：**代码 PR**（feat 分支 · red-test · commit split · FF-merge）
> 分支建议：`feat/pr-26-hydrate-candidate-profile-inputs`
> 求助边界：继承 AGENTS.md / CLAUDE.md 通用 + 本 PR 增补（§Q7）

---

## §背景（QUESTIONS 之前 · 三条确认事实）

1. **`candidate-profile` skill 的 `input_schema.required = ["parsed_content", "existing_tags"]`**
   （`backend/app/agent/skills/candidate_profile/v1_0_0/skill.yaml:23-25`）
   —— `parsed_content` 是 object（简历结构化解析内容 · 存在 `resumes.parsed_content` JSON 列上），`existing_tags` 是 string array（存在 `resumes.tags` JSONB 列上）。

2. **LLM plan skill 产出的 `tool_input` 天然给不出这两个字段**：orchestrator-plan skill 从 `dispatchable_tools` 清单里学到 `task_type: profile_candidate → tool_name: candidate-profile`，但 LLM 手上只有 `context.candidate_ids` / 用户消息里的候选人 ID · **没有 `parsed_content` 内容**。若强让 LLM 拷贝 parsed_content 到 tool_input，等于把整份简历塞进 plan JSON —— payload 爆炸 + 数据完全冗余（DB 是 source of truth）。

3. **`ToolRouter.dispatch()` 目前只做 jsonschema 校验 + 路由**：不做任何"从 DB 补齐字段"的动作。`act.py` 里 `run_act` 也只把 `step.tool_input` 原样传下去。**所以 candidate-profile 一旦被 plan 出来 · dispatch 到 skill.execute 时必然 jsonschema `required` 失败或幻觉出空对象** —— 这是 MVP-VERIFY §4.1 观察到的 "ACT 阶段必挂" 的确定性根因。

4. **同一坑的兄弟：`candidate-merge` skill 的 `input_schema.required = ["resumes"]`，每个 resume item 只 required `resume_id`（`parsed_content`/`tags` 是 optional）**（`candidate_merge/v1_0_0/skill.yaml:38`）。即 candidate-merge 允许 `resumes: [{resume_id: "res_x"}]` 通过 schema —— 但 skill 实际推理需要 parsed_content · 只是不会因 schema 校验失败而 dispatch 层挂 · 会在 LLM 拿到近乎空的 resume 数据后"幻觉推理"。**PR-26 是否要在同一层顺路补 candidate-merge？议题见 §Q4**。

---

## §Q1 · Bug B 修复的三选一：**engine 中间件补齐 · skill 自读 DB · plan 拆两步**

**建议**：**A · engine 中间件补齐（hydration middleware）**

三选一对比：

| 方案 | 内容 | 优点 | 缺点 |
|------|------|------|------|
| **A · engine 中间件 hydration** | 在 `run_act` 或 `ToolRouter.dispatch` 前插一层 `hydrate_tool_input(tool_name, tool_input, db) -> tool_input'`，命中约定的 tool_name（candidate-profile 必须补 parsed_content+existing_tags；candidate-merge 可选，见 §Q4）时用 SQLAlchemy 从 `resumes` 表拉数据注入 | Skill 保持纯函数 · 单一注入点可测 · 未来新增数据型 skill 只需登记 hydration rule · 前端 / plan LLM 都不用改 | 隐式约定 · 需文档化「哪些 tool_name 需要什么字段自动扩展」的注册表（避免"魔法" · Stage 5.1 追债 3 一样的问题） |
| B · candidate-profile skill 自读 DB | skill.yaml 声明依赖 db_session · BaseSkill 拿到 session 后 skill 内 SQL 补 parsed_content | 显式 · skill 自持完整逻辑 · 不需注册表 | **破坏 skill 无状态原则**（BaseSkill 目前 zero-DB · 加 DB 依赖会让 skill 层不再是"纯 LLM 调用" · 单测都得配 fixture） · 每个数据型 skill 各写一遍 SQL |
| C · plan 拆两步 · 加 `read_resume` skill | orchestrator-plan 学到"profile_candidate 任务 → step1: read_resume(resume_id) → step2: candidate-profile(parsed_content from step1.output)" · 引入 step 输出引用 / DAG chain 引擎 | 架构最正 · RAG 标准形态 · 未来任何跨步骤数据流复用 | **超 MVP scope 太多**（需引入 `${step1.output.parsed_content}` 引用语法 + engine DAG 解释器）· 属于 Stage 6+ 工作 |

**议题**：A（我建议）/ B / C？

---

## §Q2 · Hydration 触发条件与注册表设计（若 §Q1 选 A）

**建议**：**A · 静态注册表 · 按 tool_name 键匹配**

Bug B hydration 需要一个明确的"哪些 tool_name 触发哪些字段注入"的映射。三种做法：

| 方案 | 内容 | 优 | 缺 |
|------|------|-----|-----|
| **A · 静态注册表（我建议）** | 在 `engine.py` 或新文件 `hydration.py` 里写常量 `HYDRATION_RULES: dict[str, HydrationFn]` · `candidate-profile → _hydrate_candidate_profile` · 每个 fn 手写 SQL + 注入逻辑 | 显式 · 可 grep · 与 `_ARTIFACT_TYPE_MAP` 同风格 | 加新 skill 时要改这里（同追债项 3） |
| B · skill.yaml 声明式 `hydration:` 段 | skill.yaml 加 `hydration: {parsed_content: {from_table: resumes, key: candidate_id, column: parsed_content}}` · engine 通读 registry 自动 hydrate | 数据驱动 · 加 skill 无需改代码 | 引入新的 skill.yaml 关键字 · 需 schema 校验器扩展 · Stage 6 再做更好 |
| C · 隐式规则（tool_input 里如有 `candidate_id` 就自动补 parsed_content） | run_act 里嗅探 tool_input 字段名做匹配 | 零登记 | **危险** · 任何 skill 只要用 `candidate_id` 变量名就被静默注入 · 违最少惊讶原则 |

**议题**：**A（我建议）**/ B / C？

---

## §Q3 · Hydration 缺失数据时的失败语义

**建议**：**A · 硬失败 · 抛 `ToolParamError` · run_act 走 required-step-fail 分支**

`candidate-profile` 被 dispatch 时若 `candidate_id` 在 tool_input 里但 DB 里 `resumes` 表查不到该行（或该行 `parse_status != "PARSED"` / `parsed_content is None`）· 三种处理：

| 方案 | 内容 | 优 | 缺 |
|------|------|-----|-----|
| **A · 硬失败**（我建议） | hydration 抛 `ToolParamError("candidate resume not found or not parsed: <id>")` · 沿 dispatch 现有 except 链路 · run_act 视为必需步失败 → 发 `ERROR` SSE + 中止 | 契约明确 · 用户马上看到"简历未解析"的错误 · 与 B4 一样有 error 事件 | 用户体验略硬（但比幻觉输出好） |
| B · 软失败 · 空对象注入 | 注入 `parsed_content={}, existing_tags=[]` · skill 走 prompt.md 里的"空 parsed_content → 返回空结果"分支 | skill 已有兜底路径 | 用户拿到"空画像" · 不知道为啥 · 无 error 信号 |
| C · 抛专属错误类 · 前端可显示"该候选人简历未解析" | 新增 `CandidateResumeNotParsedError` · agent.py 把它翻译为 SSE data.error_type 字段 | 前端可差异化展示 | 引入新错误类 · 前端也要跟改 · MVP 阶段过度设计 |

**议题**：**A（我建议）**/ B / C？

---

## §Q4 · 是否顺路补 `candidate-merge`

**建议**：**A · 顺路补 · 同一 PR**

背景：candidate-merge schema 允许 `resumes: [{resume_id}]` 通过，但 skill 推理需要 parsed_content · 现状是 LLM plan 出 `resumes: [{resume_id: "res_a"}, {resume_id: "res_b"}]` → 送给 candidate-merge skill → skill 见到近乎空的 resume 数据 → 幻觉输出 MERGE/SUGGEST/KEEP_SEPARATE。**这是隐性 bug · 只不过 §4.1 没触发 merge 路径所以没抓到。**

三选一：

| 方案 | 内容 | 优 | 缺 |
|------|------|-----|-----|
| **A · 顺路补**（我建议） | 在同一 hydration 注册表加 `candidate-merge`：若 `resumes[i]` 只含 `resume_id` · 从 DB 拉 `candidate_name / parsed_content / tags / duplicate_of_resume_id` 塞回 | 一次修完两个数据型 skill · candidate-merge 也走真数据 · 未来 §4.2 merge 路径不再有隐性 bug | +1 hydration rule · 测试面 +1 |
| B · 只修 candidate-profile · candidate-merge 挂账 | 最小 scope | candidate-merge live-bug 残留 · MVP-VERIFY §4.2 会再发现一遍 · 又一轮 PR 循环 | |
| C · 都不修 · 挂账 §9.3.X | 最快 | Bug B / merge 都残留 · 不修 = MVP 不 demo-ready | |

**议题**：**A（我建议）**/ B / C？

---

## §Q5 · 测试面（TDD strict · 期望 pytest total）

**建议**：**A · 单测 + 集成 + hydration 契约测试 · 5 个 TC**

测试用例草案（若 §Q1 选 A + §Q4 选 A）：

- **TC-PR26-1**（unit · hydration 注册表）：`hydrate_tool_input("candidate-profile", {"candidate_id": "res_x"}, mock_db)` · 断言返回 dict 含 `parsed_content` + `existing_tags` · 值等于 mock_db 的 resume 行。
- **TC-PR26-2**（unit · resume 不存在硬失败）：`hydrate_tool_input("candidate-profile", {"candidate_id": "no_such"}, db)` · 断言抛 `ToolParamError`。
- **TC-PR26-3**（integration · run_act 全链）：预置 resume 行含 parsed_content · 构造 plan `[{tool_name: "candidate-profile", tool_input: {candidate_id}}]` · 断言 run_act 结果 success=True · output 含 `profile_tags/summary/strengths/risks`。
- **TC-PR26-4**（integration · candidate-merge hydration）：预置 2 个 resume · plan `[{tool_name: "candidate-merge", tool_input: {resumes: [{resume_id: "a"}, {resume_id: "b"}]}}]` · 断言 dispatch 时 skill 拿到的 `resumes[0].parsed_content` 非空。
- **TC-PR26-5**（integration · SSE ERROR on missing）：resume 不存在 · run_act 发 SSE `ERROR` 事件 · task 状态 FAILED。

**议题**：认可这 5 个 TC？还是要增/减/调整？

---

## §Q6 · Commit split（TDD strict）

**建议**：**A · 4 commit split**

commit 序列：
1. `test(pr-26): red-test skeleton for TC-PR26-1..5 (all failing)`
2. `feat(orchestrator): add hydration middleware for candidate-profile and candidate-merge`
3. `test(pr-26): green tests TC-PR26-1..5 pass`
4. （若需 docs 拆开）`docs(stage5): PR-26 STEP6 report + HANDOFF §9.3.20`

**分支**：`feat/pr-26-hydrate-candidate-profile-inputs`

**议题**：认可这个 split？（若需微调命名或拆分粒度，告诉我）

---

## §Q7 · 求助边界（继承 CLAUDE.md/AGENTS.md 通用 + PR-26 增补）

**继承（不复述）**：AGENTS.md + CLAUDE.md 通用 stop-and-ask 规则。

**PR-26 增补**（触及必停）：

1. **§Q1 若选 A · 但发现 `run_act` 里嵌入 hydration 会破 PR-12 stub 类测试**：说明 stub-pattern 屏蔽了真实 dispatch 流程 · 停 · 报现象 · 不擅自加 `if TESTING: skip_hydration` 之类的分岔。
2. **hydration 命中 candidate-profile 但 DB 里 `resumes.parsed_content` 为 None（`parse_status != PARSED`）**：按 §Q3 走硬失败 · 但如果测试证明该字段永远不为 None（即 seed / factory 都会填上）· 停 · 报回是否要软失败兜底。
3. **candidate-merge 的 resume 字段结构与 hydration 注入字段有名字冲突**（例如 `tags` 字段在 skill 里是 skill 生成的、不是 resume 原有的）· 停 · 不擅自 rename · 报回。
4. **修完 PR-26 后 MVP-VERIFY §4.1（profile）能走通 · 但 §4.2（merge）新暴露"resume 只有 1 份"的场景**：说明 candidate-merge schema 的 `minItems: 2` 校验会挂 · 属新 bug · 停 · 登记 §9.3 不擅自扩 scope。

**议题**：4 条边界够吗？还是要补？

---

## §附 · 落地位置候选（供你在 DECISION 时定）

- **hydration 实现文件**：新建 `backend/app/agent/orchestrator/hydration.py`（推荐 · 与 `act.py` / `tool_router.py` 同级 · 单一职责） OR 直接写在 `tool_router.py` 底部
- **hydration 调用点**：`ToolRouter.dispatch()` 入口（在 `_execute_builtin` / `skill.execute` 之前）· 单点接入 · 影响所有走 dispatch 的路径（run_act + 未来其他调用者）
- **db 传参**：`dispatch(tool_name, tool_input, db=None)` 已经收 db 形参（PR-21 §3.5）· 复用即可

---

## §附 · PR-26 之后（供你排后续路径）

- **PR-27**：Bug C · UI 入口缺口（ChatCenter/CandidateChat 传参 · 前端 scope · 无后端）
- **MVP-VERIFY §4.1 / §4.2 / §4.3 全流程 3 节 · 浏览器 e2e 补跑** —— PR-26+PR-27 都合完后做

---

**指挥官回议题即可**（§Q1..§Q7 每题给个字母或"其它+说明"），我把 DECISION 起草出来交给执行体。
