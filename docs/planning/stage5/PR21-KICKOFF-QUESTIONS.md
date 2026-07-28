# PR-21 KICKOFF · 问题清单（QUESTIONS）

> 任务：create_match_score REST 硬编码 plan 未走 dispatch 收敛（追债 12，HANDOFF §9.3.12）
> 状态：**草稿 · 待指挥官 revisions**（AGENTS.md §4.1 docs-only，本文件 commit 到 master）
> base：origin/master @ `c3bdc09`
> 路径：KICKOFF（本文件）→ REVISIONS（指挥官回）→ DECISION（执行体 contract）

---

## 〇 摘要（先给结论，便于指挥官快速判断）

grep 复核后，**原 HANDOFF §9.3.12 的两处前提需要修正**，且暴露两个比"命名不合法"更严重的真实问题：

1. **skip-to-score 当前已是静默失效的真实 bug，不是"未来潜在 bug"**。
   `run_act` 对每个 step 调 `router.dispatch(tool_name)`（act.py:108），而 `create_match_score`
   既不在 `BUILTIN_TOOLS` 也非已注册 skill_id → `UnknownToolError`；`run_act` 又逐步骤吞异常
   （act.py:107-111，`except Exception: sr=None`），于是任务"EXECUTING→COMPLETED"但 **0 条 match_score 落库**。
   HANDOFF 说"若未来 skip-to-score 走 dispatch 会 UnknownToolError"——实际代码**一直走 dispatch**。
2. **方案二（直接改名 jd-candidate-matching）语义不等价**，改名后要么仍失败、要么换了评分后端。
   `jd-candidate-matching` 的 `input_schema` 要 `{jd, resume}`（结构化对象），而 skip-to-score plan 传
   `{jd_id, resume_id}`（ID 引用）；且其 `execute` 走 **LLM 打分**（`call_llm_json`，base_skill.py:226-246），
   并非生产确定性评分后端 `MatchService.match_one(jd_id, resume_id)`（services/match.py，`POST /api/v1/match`
   实际调用者）。两条路径评分实现不同。

因此本 PR 不能只是"把字符串改合法"，必须先由指挥官定：**skip-to-score 究竟该跑哪个后端**。

---

## §一 硬编码点确认（Q1）

HANDOFF 记录的三个位点行号已漂移，且存在一个被忽略的第四处。以 master `c3bdc09` 复核：

| # | 文件:行 | 现状 | 是否 tool_name 字面量 | 是否需改 |
|---|---------|------|----------------------|----------|
| 1 | `backend/app/agent/orchestrator/engine.py:124` | `_ARTIFACT_TYPE_MAP["create_match_score"] = "match_score"` | 否（map key） | 是（改 key） |
| 2 | `backend/app/agent/orchestrator/engine.py:511` | `run_skip_to_score` 构造 plan 的 `tool_name` | **是** | 是 |
| 3 | `backend/app/api/v1/agent.py:153` | `skip_to_score` REST 端点构造 plan 的 `tool_name` | **是** | 是 |
| 4 | `backend/app/api/v1/endpoints/match.py:23` | `async def create_match_score(request, ...)` —— **REST handler 函数名** | 否（端点函数名） | **否（排除）** |

> 语义澄清：`match.py:23` 是 `POST /api/v1/match` 的 handler 函数名，是合法 REST 入口，与 tool_name 无关，
> **不在本 PR 改名范围内**。HANDOFF §9.3.12 只记了 1/2/3 三处，漏记了"函数名"与"行号漂移"。

**测试侧引用**（不断言字面量，改名后仍 PASS，但建议同步更新以免误导）：
- `tests/test_stage5_s5_09_engine.py:56,61,78` —— fake plan 用 `create_match_score`
- `tests/test_stage5_pr13_execute.py:56,71` —— fake plan 用 `create_match_score`

**问 Q1**：以上 4 处复核是否完整？是否有我遗漏的硬编码点（如 `_ARTIFACT_TYPE_MAP` 的消费方、或前端 result 解析）？

---

## §二 替换值定案（Q2）

候选替换值 `jd-candidate-matching`（HANDOFF §9.3.12 建议）。

- `skill.yaml:5` 声明 `task_type: match`，`internal` 缺省 `false` → `ToolRouter.dispatch` 会命中它（不触发 `SkillNotDispatchableError`）。**但见 §新发现 F2：命中后 `execute` 会因 input 不符而失败，或评分语义漂移。**
- `SkillRegistry.get_skill` 是精确 dict 查找（skill_registry.py:65-66），无下划线/连字符归一化，故 `create_match_score` ≠ `jd-candidate-matching`。

**问 Q2（关键决策点）**：skip-to-score 的真实目标后端是哪个？
- **(A) 保留确定性后端 `MatchService.match_one(jd_id, resume_id)`**（与 `POST /api/v1/match` 一致）——
  则 `jd-candidate-matching` skill **不是**合适替换值，需一个"合法 tool_name 且封装 match_one"的 dispatcher 入口（见 §新发现 F2 的方案矩阵）。
- **(B) 接受切换到 LLM 后端 `jd-candidate-matching` skill** —— 则需把 plan 的 `tool_input` 从
  `{jd_id, resume_id}` 改为 `{jd, resume}`（端点/engine 先按 id 加载 jd+resume 对象），评分语义变为 LLM 打分。

请指挥官在 REVISIONS 中明确选 A 还是 B（及 A 的子方案）。

---

## §三 _ARTIFACT_TYPE_MAP 联动（Q3）

`engine.py:123-129` 的 `_ARTIFACT_TYPE_MAP` 被 `_build_artifacts` 用于将 step 结果映射到任务级
`ResultArtifact.type`。当前条目 `"create_match_score": "match_score"`。

- 改名后（无论 A/B）需把 key 从 `create_match_score` 改为新 tool_name（如 A 方案的 `match_score` 或 B 方案的 `jd-candidate-matching`），**value 保持 `match_score` 不变**。
- 前端侧：`ArtifactType` union（`frontend/src/types/agent.ts:71-77`）**已含 `match_score`**，
  `ResultCard` 按 `type==='match_score'` 分派 `MatchScoreArtifact`（`ResultCard.tsx:21-22`），**不依赖 tool_name**。
  因此 HANDOFF §9.4 陷阱 8 提到的"前端 ArtifactType union 同步"**当前已满足，无需前端改动**。

**问 Q3**：新 tool_name 定案后，`_ARTIFACT_TYPE_MAP` 的 key 是否统一改为该值？value `match_score` 保持不变，确认无前端联动。

---

## §四 skip-to-score 端点硬编码 plan（Q4）

`agent.py:149-157` 与 `engine.py:507-516` 各构造一份 plan：
```python
{"step_id": f"step_score_{i}", "tool_name": "create_match_score",
 "tool_input": {"jd_id": ..., "resume_id": cid}}
```
两处需同步改 `tool_name`（及若选 B 方案则改 `tool_input` 结构）。

**问 Q4**：
1. 两处 plan 是同源复制，`engine.run_skip_to_score` 内部重建 plan，端点侧也会先建 plan 存 `Task.plan`。
   是否考虑**只在一处（engine）构造**，端点侧直接调 `engine.run_skip_to_score`（消除双份硬编码）？
2. 测试 fixture（`test_stage5_s5_09_engine.py` / `test_stage5_pr13_execute.py` 的 fake plan 用 `create_match_score`）
   是否要同步改为新 tool_name？这些用例 mock 了 `run_act`，不断言字面量，故改名后仍能 PASS；
   但为"避免回归 + 反映真实 contract"，建议本 PR 追加 TC 覆盖新 tool_name（见 Q5）。

---

## §五 测试策略（Q5）

建议追加 1-2 个 TC（接在 skip-to-score/executions 相关测试文件，参考 PR-20 单元级写法）：

- **TC-S5.2-1（单元）**：`engine.run_skip_to_score` 构造的 plan，其每个 step 的 `tool_name` == 新合法值
  （不再是 `create_match_score`），且 `ToolRouter().get_skill_or_builtin(新值)` 可被解析（不抛 UnknownToolError）。
- **TC-S5.2-2（集成，可选）**：skip-to-score 端点触发后，executions 表里落库的 `tool_name` 为新值；
  若选 A 方案，进一步断言 `MatchService.match_one` 被调用且产出 `match_scores` 行（验证不再静默失效，闭环 F1）。

**问 Q5**：TC 范围是否够？是否需要端到端断言 `match_scores` 落库（防 F1 回归）？

---

## §六 前端影响（Q6）

- `ToolCallCard`（`ToolCallCard.tsx:9`）原样展示 `event.data.tool_name`；改名后 UI 显示从 `create_match_score`
  变为 `jd-candidate-matching`（或 A 方案的新名）——**更可读，无损坏**。
- `ResultCard` / `MatchScoreArtifact` 按 `type: 'match_score'` 分派，与 tool_name 无关 → **无需前端改动**。
- `PlanCard`（`PlanCard.tsx:24`）原样显示 `step.tool_name`；同上，仅标签变化。

**问 Q6**：是否接受 UI 上工具名显示为 skill_id 风格（`jd-candidate-matching`）？若产品要求保留 `create_match_score`
可读性，则 A 方案应取一个兼顾可读与合法的 tool_name（如 `match_score`）。

---

## §七 BUILTIN_TOOLS 是否清理（Q7）

`tool_router.py:54` 的 `BUILTIN_TOOLS` 仅有 `search_resumes` / `read_jd`，`create_match_score` 从未进入。

- 若选 **A 方案且用"注册 builtin"子方案**，则需向 `BUILTIN_TOOLS` 增 `match_score` 条目（含 `input_schema`
  `{jd_id, resume_id}` + `_execute_builtin` 分支调 `MatchService.match_one`）。
- 若选 **B 方案**，不动 `BUILTIN_TOOLS`。

**问 Q7**：本 PR 是否允许触碰 `BUILTIN_TOOLS`？（HANDOFF 原话"此 PR 不动 BUILTIN_TOOLS"，但该前提建立在
"方案二改名即可"之上；F2 证明改名不可行，故 A 的子方案可能需破例。请指挥官明确。）

---

## §八 求助边界（Q8）

按指令，触发以下任一即**停下报告、不擅自实现**：

1. grep 出更多未记录的硬编码点（除 §一 4 处外）。
2. `jd-candidate-matching` 与 `create_match_score` 语义有本质差别。

**现状：Q8 第 2 条已触发**——两者输入契约（结构化对象 vs ID）与评分实现（LLM vs 确定性 match_one）均不同，
见 §新发现 F2。这恰是 HANDOFF "jd-candidate-matching 已存在且能覆盖同语义" 假设的风险点。
故本 PR 必须先 DECISION 选 A/B 再动手，不能默认方案二。

---

## §新发现（grep 后才暴露，原 HANDOFF 未记）

### F1 · skip-to-score 当前已静默失效（严重度：高）
- 证据链：`act.py:108` `router.dispatch(tool_name, tool_input)` 必然执行 →
  `tool_router.py:144-146` `get_skill("create_match_score")` 返回 `None` → `raise UnknownToolError` →
  `act.py:107-111` 逐步骤 `except Exception: sr=None`，step 标记失败但任务继续 → 最终 0 条 match_score。
- 后果：HANDOFF §9.3.12 "若未来 skip-to-score 走 dispatch 会 UnknownToolError" 与代码事实不符；
  **该 bug 已 live**。原测试用 `monkeypatch.setattr(act_mod, "run_act", _fake)` 屏蔽了真实 dispatch，故未暴露。
- 影响范围：所有 `POST /api/v1/agent/skip-to-score` 请求目前不产生评分结果。

### F2 · 方案二改名语义不等价（严重度：高）
- `jd-candidate-matching` `input_schema`（skill.yaml:12-52）要求 `{jd: {title, summary, ...}, resume: {parsed_content, ...}}`；
  skip-to-score plan 传 `{jd_id, resume_id}`。
- `BaseSkill.execute`（base_skill.py:226-238）先 `validate_input` → 不通过直接返回 `SkillResult(success=False)`，
  故即便改名，step 仍失败（从 UnknownToolError 变成 Input validation failed）。
- 即便把 `tool_input` 改成 `{jd, resume}`，`jd-candidate-matching.execute` 走 `call_llm_json`（LLM 打分），
  而生产现状（match.py 端点）走 `MatchService.match_one`（确定性打分）——**评分后端不同**。

### F2 方案矩阵（供指挥官 DECISION 选 A 的子方案）
- **A1（最小正确修复）**：向 `BUILTIN_TOOLS` 增加 `match_score` 条目
  （`input_schema: {jd_id, resume_id}`，`_execute_builtin` 调 `MatchService.match_one`），
  并把 skip-to-score plan 的 `tool_name` 改为 `match_score`。保留确定性后端，tool_name 合法。
  —— 需破例触碰 `BUILTIN_TOOLS`（Q7）。
- **A2（纯 Skill 包装）**：新建 `jd-match-score` skill（skill.yaml + python 封装 `MatchService.match_one`），
  降级原 `create_match_score` 端点到该 skill。即 HANDOFF 所说"方案一"，工作量更大。
- **B（切 LLM 后端）**：skip-to-score 改调 `jd-candidate-matching`，端点/engine 先按 id 加载 jd+resume 对象，
  再把 `{jd, resume}` 作为 `tool_input`。评分语义变为 LLM 打分，与 `POST /api/v1/match` 行为分叉。

> 个人建议（非决策）：**A1** 风险最低、语义与现有 `POST /api/v1/match` 完全一致、改动最小；
> 代价仅是多注册一个 builtin（与"此 PR 不动 BUILTIN_TOOLS"的初衷冲突，需指挥官拍板）。

### F3 · 第四处字面量需排除（严重度：低）
`match.py:23` 的 `create_match_score` 是 REST handler 函数名，非 tool_name，改名须排除，避免误伤 `POST /api/v1/match`。

---

## §九 待指挥官 REVISIONS 回答的 8 问速览

- Q1：硬编码点是否仅 §一 的 4 处（含 match.py 函数名排除）？
- Q2：**skip-to-score 目标后端选 A（match_one 确定性）还是 B（jd-candidate-matching LLM）？**（核心）
- Q3：`_ARTIFACT_TYPE_MAP` key 统一为新 tool_name、value 保持 `match_score`、无前端联动，确认？
- Q4：两处 plan 是否收敛到 engine 单点构造？测试 fixture 是否同步改名？
- Q5：TC-S5.2-1/2 范围（是否含 match_scores 落库断言）？
- Q6：接受 UI 工具名显示为 skill_id 风格？
- Q7：本 PR 是否允许触碰 `BUILTIN_TOOLS`（A1 子方案需要）？
- Q8：已触发"语义本质不同"边界（F2），请确认 DECISION 前不擅自实现。

---

*起草人：agent · 复核 base `c3bdc09` · 状态：待 commander REVISIONS*
