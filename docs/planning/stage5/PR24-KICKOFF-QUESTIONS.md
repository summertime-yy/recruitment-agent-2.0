# PR-24 · KICKOFF-QUESTIONS

> 关联：`docs/planning/stage5/MVP-VERIFY-RUN-REPORT.md`（B5 权威文本 · commit `98a6290`）
> 起始 master HEAD：`98a6290`（含 MVP-VERIFY report + HANDOFF §9.3.16/§9.4.13）
> 上一轮验收 baseline：pytest 131/1 skipped · ruff 0 全仓 · frontend build ✓ · migration head `b6c7d8e9f0a1`
> 类型：**代码 PR**（feat 分支 · red-test · commit split · FF-merge）
> 分支建议：`feat/pr-24-fix-orchestrator-prompt-templates`（沿用 report §附4 建议）
> 求助边界：继承 MVP-VERIFY-KICKOFF-DECISION §五 + 本 PR 增补

---

## §背景补充（QUESTIONS 之前）

**MVP-VERIFY 的三条冷酷事实**（不复述 B5，直接给三点上下文）：

1. **PR-12 老测试全用 stub 屏蔽 base_skill.execute()**（见 `tests/test_stage5_s5_05_reason_reflect.py:23-77`），5 个 orchestrator internal skill 从未走过真实的 prompt 渲染路径 · 回归防护空白 · B5 才能隐藏 15 天。
2. **5 skill 的 input_schema 各不相同**：reason 需要 `user_input`+`context`；reflect 需要 `reason_output`（dict）；plan 需要 `reason_output`+`dispatchable_tools`（str）；reflect_plan 需要 `plan`（dict）；reflect_act 需要 `step_results`（array）。**不能一个模板套完**。
3. **B5 症状里 examples.yaml 的示例值是"意外遮羞布"**：reason skill 的 examples.yaml 里恰好有 `jd_1 / c_1` 示例 → LLM 幻觉输出这些值命中，让整条链看起来"跑通了"但落 WAITING_CONFIRMATION → 用户从 UI 看不出是幻觉。这告诉我们：**修复后如果不做端到端真实 LLM 校验，我们无法确认真的修好了**。

---

## §Q1 · B5 修复的三选一：数据修 / 数据+代码 / 数据+代码+架构

**建议**：**B · 数据 + 代码 fail-fast**（推荐）

三选一对比：

| 方案 | 内容 | 优点 | 缺点 |
|------|------|------|------|
| A · 仅数据 | 5 个 prompt.md 补 USER_TEMPLATE 段 | 最小改动 · 单一 PR | 未来新 skill 若再漏写就静默重犯 |
| **B · 数据 + 代码 fail-fast** | A + `base_skill.py:_load_from_directory()` 空模板护栏 | 治本 · 未来新 skill 无法静默漏配 | +1 处代码 · +单测 |
| C · A + B + 架构 | B + `input_schema.required` 每字段必须出现在模板中的强校验 | 最严 | 强耦合 · 冷启动时如未来引入 `additionalProperties` 优先的 skill 会误伤 |

**议题**：A / **B（我建议）** / C？

---

## §Q2 · 5 个 orchestrator skill 的 USER_TEMPLATE 具体渲染

**建议**：每个 skill 按其 `input_schema` 覆盖 required + optional。以下为**我起草的 5 个模板**（QUESTIONS 阶段征求同意/修改；DECISION 阶段固定）：

### Q2.1 · orchestrator-reason
```
---USER_TEMPLATE---
## 用户消息
{{ user_input }}

## 上下文
{{ context | tojson if context else '{}' }}
```
- required: `user_input` · optional: `context`
- ⚠️ `context | tojson` 是关键：让 LLM 看到结构化 JSON 而非 python repr

### Q2.2 · orchestrator-reflect
```
---USER_TEMPLATE---
## Reason 输出
{{ reason_output | tojson }}
```
- required: `reason_output`

### Q2.3 · orchestrator-plan
```
---USER_TEMPLATE---
## Reason 输出
{{ reason_output | tojson }}

## 可派单工具清单
{{ dispatchable_tools }}
```
- required: `reason_output` · optional: `dispatchable_tools`（engine 运行时注入 · Markdown 字符串）

### Q2.4 · orchestrator-reflect-plan
```
---USER_TEMPLATE---
## Plan 输出
{{ plan | tojson }}
```
- required: `plan`

### Q2.5 · orchestrator-reflect-act
```
---USER_TEMPLATE---
## 各步骤执行结果
{{ step_results | tojson }}
```
- required: `step_results`（list of StepResult）

**议题**：认可这 5 个模板？（若需增补 few-shot 引用 / prompt 风格调整 / 变量命名，告诉我编号）

---

## §Q3 · fail-fast 触发条件（B 方案下）

**建议**：**A · 触发条件 = `_user_prompt_template == "" and input_schema.get("required")`**

三选一对比：

| 方案 | 触发条件 | 影响 |
|------|----------|------|
| **A · 我建议** | 模板空 **且** required 非空 | 精确命中「skill 需要输入但没喂给 LLM」·  内置容忍 required 为空的边缘 skill |
| B · 更严 | 模板空（不管 required） | 未来若有 "system-only prompt" 类 skill（如格式转换、静态回复）会误报 |
| C · 更严+ | 模板空 **或** required 字段未出现在模板 | 强绑定 required·未来若引入 optional-heavy skill 也捕获（但可能过严）|

**议题**：A（我建议）/ B / C？

---

## §Q4 · 测试策略（3 层组合）

**建议**：**全采纳 · 3 层都做**

### Q4.1 · 单元测试（必做）
新增 `tests/test_stage5_pr24_prompt_templates.py`：
- **TC-PR24-1** `test_all_skills_render_non_empty_user_prompt`：遍历 `SkillRegistry()._skills.values()`，用**该 skill required 字段的 mock 数据**跑 `render_user_prompt()`，断言输出非空、包含所有 required 字段值
- **TC-PR24-2** `test_orchestrator_reason_reads_context`：单独针对 reason·断言 `render_user_prompt({"user_input": "找候选人 c_test_123", "context": {"jd_id": "jd_test_abc"}})` 输出**同时包含** `c_test_123` 和 `jd_test_abc`（针对 B5 精确回归）
- **TC-PR24-3** `test_base_skill_load_fail_fast_on_empty_template`：新建临时 skill dir · 无 USER_TEMPLATE 段 · 且 skill.yaml 有 `input_schema.required` · 断言 `BaseSkill(skill_dir=tmp_dir)` **raise ValueError**

### Q4.2 · 集成测试（必做）
新增 `tests/test_stage5_pr24_orchestrator_integration.py`：
- **TC-PR24-4** `test_reason_reads_frontend_context`：mock `call_llm_json` **返回自身接收的 user_prompt**（不真调 LLM），驱动 `engine.run_reason({"user_input": "找候选人 c_ABC", "context": {"jd_id": "jd_XYZ"}})`，断言 mock 收到的 user_prompt 里出现 `c_ABC` 和 `jd_XYZ`
- **TC-PR24-5** `test_full_rpr_flow_uses_input`：类似上一条 · 覆盖 reflect 也真实读入 reason_out（不用 stub）

### Q4.3 · 端到端真实 LLM smoke（可选 · 我强烈建议）
新增 `tests/test_stage5_pr24_llm_e2e.py`（**打标 `@pytest.mark.llm_e2e` · 默认不跑 · CI 时手动 opt-in**）：
- **TC-PR24-6** `test_reason_reads_context_real_llm`：真调 LLM · `{"user_input": "帮 jd_UNIQUE_XYZ_2607 找候选人 c_UNIQUE_ABC_2607", "context": {}}` · 断言 reason 输出的 `parsed_entities.jd_id == "jd_UNIQUE_XYZ_2607"` · 用极不可能被幻觉出的 unique token 排除幻觉命中
- 这是 B5 最直接的「症状复现前 → 现在通」验证 · 无它则 B5 修复只是"看起来对"

**议题**：Q4.1/4.2/4.3 各做/不做？（我建议全做）

---

## §Q5 · B4（SSE terminal 缺失）合并 PR-24 还是独立 PR-25？

**背景**：B4 = `engine.py:_background_reason_plan` L379-388 `is_feasible=false` 分支 return 前未 emit `SSEEventType.ERROR/SYSTEM` 收尾。修复面 1 文件 + 1 处 emit + 1 单测。

**建议**：**A · 独立 commit 合入 PR-24**（同分支 · 分 commit）

理由：
- 两个问题都在 orchestrator R-P-R 链路 · 修 B5 后你才有机会真跑一次 `is_feasible=false`（B5 修复前 reflect 判定本身不可靠）
- 用户视角一起验（"改一版 orchestrator 就好"）比拆两个 PR 清晰
- commit split 可分：`fix(orchestrator): emit terminal event on infeasible reflect (B4)` 独立可回退

三选一对比：

| 方案 | 内容 | 优 | 缺 |
|------|------|-----|-----|
| **A · 我建议** | B4 单独 commit 合 PR-24 | 一次 orchestrator 收敛 · 可复用 §4/§5/§6 补跑机会 | PR-24 稍大 |
| B · PR-25 独立 | 只做 B5 · B4 拆独立 PR | 每 PR 最小 | 增加一次 FF-merge 开销 |
| C · 都不做 | B4 挂账 | 最快 | 陷阱不修 · 用户 SSE 卡挂持续 |

**议题**：A（我建议）/ B / C？

---

## §Q6 · MVP-VERIFY 抓到的第 6 个 bug 苗头（`GET /tasks/{id}` 500）

**背景**：MVP-VERIFY §附3 记：`GET /api/v1/agent/tasks/{id}` 返回 500，疑似"plan 缺 task_id 字段致响应序列化失败"。执行体未列入 Bug 表 · 建议后续单独排查。

**建议**：**C · 登记不修 · 独立 PR-25 或延后**

理由：
- 不在 PR-24 scope（B5/B4 都在 chat 触发链路 · 这个 500 在 task 详情读路径）
- 复现有可能是 plan schema 契约 vs Pydantic response_model 冲突 · 排查面未知
- 现有绕过：DB 直查（MVP-VERIFY §附1 已示范）

三选一对比：

| 方案 | 内容 |
|------|------|
| A | 一并塞 PR-24 排查（+1 未知面 · 风险不确定） |
| B | 独立 PR-25 立即启动 |
| **C · 我建议** | HANDOFF §9.3.17 登记 · 挂账 · 等某 PR 顺清 |

**议题**：A / B / **C（我建议）**？

---

## §Q7 · PR-24 完工后自动补跑 MVP-VERIFY §4/§5/§6？

**背景**：MVP-VERIFY 挂账 §4/§5/§6 三节；PR-24 修完 orchestrator 后这些节应该都能跑通。

**建议**：**B · 由 PR-24 STEP6 报告承担**（不起 v2 独立 report）

三选一对比：

| 方案 | 内容 | 优 | 缺 |
|------|------|-----|-----|
| A | PR-24 完工后新起 `MVP-VERIFY-RUN-REPORT-v2.md` | report 独立 · 全景可追 | 多一份文档 · 维护碎片 |
| **B · 我建议** | PR-24 STEP6 报告加一节「MVP-VERIFY 挂账 §4/§5/§6 补跑」，跑通后就地记录，无需独立 v2 | 落地简单 · 与 PR-24 强绑定 | v1 report 状态永远"部分" |
| C | PR-24 完工暂不补跑 · 由后续独立活动做 | 最简 | MVP-VERIFY 状态永久悬空 |

**议题**：A / **B（我建议）** / C？

---

## §Q8 · 提交策略 & commit split

**建议**：**A · TDD strict · 6 commit split**（沿用 PR-19/20/23 pattern）

commit split（TDD red-test 骨架先行）：

1. `test(pr-24): red-test skeleton for TC-PR24-1..6 (all failing)` — 单元 + 集成 + LLM e2e 骨架
2. `feat(orchestrator): add USER_TEMPLATE section to 5 orchestrator internal skills (B5 fix)` — 5 个 prompt.md 修改
3. `feat(base_skill): fail-fast on empty user prompt template with non-empty input_schema.required` — 代码护栏
4. `test(pr-24): green tests TC-PR24-1..5 pass` — 5 个非 e2e 测试转绿
5. `fix(orchestrator): emit SSE terminal event on infeasible reflect (B4 fix)` — B4 单独 commit
6. `test(pr-24): green LLM e2e TC-PR24-6 with unique token proof` — LLM e2e 转绿

**分支**：`feat/pr-24-fix-orchestrator-prompt-templates`

**议题**：认可这个 split？（若需微调 commit 顺序 / 拆分粒度，告诉我编号）

---

## §Q9 · 求助边界（继承 MVP-VERIFY §五 + PR-24 增补）

**继承（不复述）**：MVP-VERIFY-KICKOFF-DECISION §五 6 条边界。

**PR-24 增补**（触及必停）：

1. **修完后 TC-PR24-6（LLM e2e）依然失败**：说明 5 skill USER_TEMPLATE 内容/变量不对 · 停 · 不擅自改模板措辞 · 报回让指挥官定
2. **`base_skill.py:_load_from_directory()` 加 fail-fast 后 PR-12 老单测集体失败**：说明现有 stub-pattern 冲突 · 停 · 分析后报回（可能需要修 5 个 stub 加 skill.yaml 副本，或 fail-fast 改按 skill_dir 是否为 None 分岔）
3. **修复后 §4/§5/§6 补跑仍有异常**：不擅自登记为 B7/B8 · 先检查是否为 B5/B4 未清 · 报回决定是继续修还是独立 PR

**议题**：3 条边界够吗？还是要补？

---

## §附 · 我提议的执行流水（若全采纳）

```
Step 0 · KICKOFF-DECISION（我写 · 待你审）· ~10 min
Step 1 · 起分支 · red-test 骨架（6 个测试全 failing）· ~30 min
Step 2 · 5 个 prompt.md 补 USER_TEMPLATE + base_skill.py fail-fast · ~20 min
Step 3 · 单元 + 集成 5 个测试转绿 · ~30 min
Step 4 · B4 独立 commit：engine.py:_background_reason_plan L379-388 补 emit · ~20 min
Step 5 · LLM e2e TC-PR24-6 转绿（真调 LLM · unique token 验证）· ~10 min
Step 6 · 三门验收（pytest 131+6 · ruff 0 · frontend build 无关）+ 补跑 MVP-VERIFY §4/§5/§6 · ~30 min
Step 7 · STEP6 报告 + push · ~15 min
```

预估：**顺利 145 min · 悲观 3-4h**（若求助边界 2 触发需修 5 个 stub 追加时间）。

---

**待你回答上述 9 议题 · 一句「全采纳」也可 · 有需要不同处告诉我编号。回后我写 PR24-KICKOFF-DECISION，然后执行体（新 session/新 agent）开跑。**
