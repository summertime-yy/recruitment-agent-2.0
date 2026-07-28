# PR-21 KICKOFF · REVISIONS（指挥官回复）

> 来源：docs/planning/stage5/PR21-KICKOFF-QUESTIONS.md（executor 草稿）
> base：master `c3bdc09`
> 状态：**已批复 · 选 A1（破例动 BUILTIN_TOOLS）· 双主目标（追债 12 + F1）**
> 下一步：executor 据此起 PR21-KICKOFF-DECISION.md（contract）

---

## 〇 总评 · Grep 复核质量非常好

执行体没有照 HANDOFF §9.3.12 抄，而是对着源码逐条验证并翻了两个错误假设，本次 KICKOFF 值回票价：

- **F1 · skip-to-score 已 live-bug**：`act.py:107-111` `except Exception: sr=None` 吞异常 + `router.dispatch("create_match_score")` 抛 `UnknownToolError` → 任务状态成功但零 `match_score` 落库。HANDOFF §9.3.12 措辞"未来潜在 bug"错，现改为 **"live bug"**。测试屏蔽证据链已复核（`test_stage5_s5_09_engine.py:58` `monkeypatch.setattr(act_mod, "run_act", _fake_run_act)`）。
- **F2 · 方案二不等价**：`jd-candidate-matching` `input_schema` 要 `{jd, resume}` 结构化对象 + `execute` 走 `call_llm_json`；skip-to-score 现状 plan 传 `{jd_id, resume_id}` + 生产 `POST /api/v1/match` 走 `MatchService.match_one` 确定性打分。HANDOFF "jd-candidate-matching 已能覆盖同语义" 前提错。
- **F3 排除 `match.py:23`**：REST handler 函数名，非 tool_name，不改。

这两条发现将 PR-21 从"改字符串"升级为"补一条静默失效的生产链路 + tool_name 合法化"，值 3-4 天而非 1 天。KICKOFF 停下报告是正确履行 §八求助边界，Q8.2 已触发。

---

## §一 逐条 REVISIONS

### Q1 · 硬编码点复核完整性 → 通过
§一 表格的 3 处需改（engine.py:124 map key、engine.py:511 engine 端 plan、agent.py:153 端点 plan）+ 1 处排除（match.py:23 handler 函数名）是完整的，不需要再 grep。

测试侧引用（`test_stage5_s5_09_engine.py:56/61/78`、`test_stage5_pr13_execute.py:56/71`）统一改为新 tool_name，见 Q4 决定。

**动作：Q1 定稿。**

### Q2 · 目标后端二选一（核心决策点）→ 选 A · 确定性后端 MatchService.match_one
选 A 依据：
1. `POST /api/v1/match`（Stage 4 匹配核心）线上一直用 `match_one` 打分，skip-to-score 是同一评分链路的另一入口（UI 快捷路径）。评分实现必须一致，否则同一 `(jd_id, resume_id)` 两个入口给不同分——这是产品事实 bug，不是选型自由度。
2. `match_scores` 表是 Stage 4 数据资产，`MatchService.match_one` 已封装完整（幂等 + `force` 参数 + `WHERE jd_id AND resume_id` 查询），成熟稳定。
3. B 方案把 skip-to-score 切到 LLM 打分会让同产品两条打分链路语义分叉，未来 debug 一场噩梦。
4. Stage 6/7 若真要引入 LLM 打分，那是新特性（如"LLM 复评/理由生成"），走独立 skill 独立入口，不通过硬拐现有 skip-to-score 达成。

**A 子方案选：A1（BUILTIN_TOOLS 增 match_score）**，理由见 Q7。

### Q3 · _ARTIFACT_TYPE_MAP 联动 → 通过
- key：`create_match_score` → `match_score`（与 A1 新 tool_name 对齐）
- value：`match_score` 保持不变
- 前端 `ArtifactType` union 已含 `match_score`（agent.ts:71-77），`ResultCard` 按 type 分派（ResultCard.tsx:21-22），零前端改动

**动作：定稿。**

### Q4 · plan 双份构造 → 收敛到 engine 单点（Q4.1 采纳）+ 测试 fixture 同步改名（Q4.2 采纳）
**Q4.1 采纳**：`agent.py:149-157` 的 plan 构造删除，`skip_to_score` 端点直接调 `engine.run_skip_to_score(task_id, jd_id, resume_ids)`（如现签名不合就在本 PR 里扩），engine 内一处构造 plan。消除双份硬编码，避免未来又漂移。若 `engine.run_skip_to_score` 已经内部重建 plan 但端点侧目前也在建，属重复代码，本 PR 一并清理。

**Q4.2 采纳**：`test_stage5_s5_09_engine.py:56/61/78` 与 `test_stage5_pr13_execute.py:56/71` 的 fake plan `tool_name` 全部改为 `match_score`（新值）。这些用例虽然 mock 了 run_act 不会真跑 dispatch，但测试代码是 contract 文档，不改会误导后来者以为 `create_match_score` 是合法 tool_name。

### Q5 · TC 范围 → 两条必须都加，且 TC-S5.2-2 走端到端
- **TC-S5.2-1（单元）**：`engine.run_skip_to_score` 构造的 plan step 的 `tool_name == "match_score"` + `ToolRouter().dispatch("match_score", {jd_id, resume_id})` 可解析（不抛 `UnknownToolError`）。
- **TC-S5.2-2（端到端 · 防 F1 回归）**：`POST /agent/skip-to-score` 请求后，**不 mock run_act**，让真实 dispatch 走进 `_execute_builtin("match_score", ...)`
  → 断言 `match_scores` 表出现新行（`WHERE jd_id AND resume_id`）+ `executions` 表 `tool_name == "match_score"` + `status == "COMPLETED"`。
  - 关键：不要用 `monkeypatch.setattr(act_mod, "run_act", _fake)`——F1 的 root cause 正是这类 mock 屏蔽了真实链路。TC-S5.2-2 必须让 `run_act` 真跑，dispatch 真进 builtin。
  - 若遭遇 §9.4 陷阱 12（ASGITransport + create_task hang），走单元级组合：直接构造 `ToolRouter` + 调 `_execute_builtin` + 断 `match_scores` 落库，不通过 REST endpoint 触发。参考 PR-20 的单元级 helper 覆盖思路。

**动作：新增测试文件 `backend/tests/test_stage5_pr21_match_score_tool.py`，覆盖 TC-S5.2-1/2。**

### Q6 · UI tool_name 显示 → match_score（不用 jd-candidate-matching）
A1 方案下新 tool_name 就是 `match_score`。UI 上从 `create_match_score` 变 `match_score` 更简洁，且与 result type 一致（`ToolCallCard` 和 `MatchScoreArtifact` 显示的字符串会对齐），可读性更好。无 UI 改动。

### Q7 · 是否触碰 BUILTIN_TOOLS → 允许 · 破例通过
原 HANDOFF "不动 BUILTIN_TOOLS" 前提是"方案二改名即可"，F2 证明改名不可行。A1 需要注册 `match_score` 到 `BUILTIN_TOOLS`（含 `input_schema: {jd_id, resume_id}` + `_execute_builtin` 分支调 `MatchService.match_one`）。

具体：
1. `tool_router.py:54` `BUILTIN_TOOLS` dict 增 `"match_score": {"input_schema": {...jd_id, resume_id...}, "description": "..."}` 条目
2. `_execute_builtin` 内加 `if tool_name == "match_score": service = MatchService(db); score = await service.match_one(tool_input["jd_id"], tool_input["resume_id"], force=False); return SkillResult(success=True, output={"match_score_id": score.id, "score": score.score, ...})` 分支
3. `_validate_tool_input`（tool_router.py 内辅助）需覆盖 `match_score` 的必填字段（`jd_id`, `resume_id` 均 required）
4. 返回的 output 结构必须与 `_ARTIFACT_TYPE_MAP` 消费方（`_build_artifacts`）预期一致，让 `ResultArtifact.type=="match_score"` 分派链路继续走通

### Q8 · 求助边界 → 触发正确，已停下等 REVISIONS
Q8.2（语义本质不同）触发是正确履行。感谢没有硬着头皮改名蒙混过关。

---

## §二 追加决策（Revisions 期发现）

### R1 · F1 是独立于追债 12 的生产 bug，本 PR 一并修复
原追债 12 是"tool_name 命名合法化"的清洁性问题，F1 是功能失效 bug。两者归到同一 PR 修复因为都需要改 `create_match_score → match_score` 这条链路。PR-21 的 §一.1 交付面必须写清双目标：
- 主目标 1（追债 12 收敛）：`create_match_score → match_score` 全链路重命名
- 主目标 2（F1 修复）：skip-to-score 恢复能真产出 `match_scores` 行的能力（通过 A1 注册 builtin 达成）

STEP6 报告的用例表必须显式覆盖 F1 回归防护（TC-S5.2-2）。

### R2 · _execute_builtin 分支的合规埋点
现有 `search_resumes`/`read_jd` 两个 builtin 是否有 `SkillExecutionLog` 之类的落库埋点？如没有，`match_score` builtin 也不加（保持一致）。这是发现 → 沿袭，不是新决策，执行体查一下 `_execute_builtin` 内是否有日志/审计代码，答案是"无"则不动。

> executor 复核（写于 DECISION 起稿前）：`_execute_builtin`（tool_router.py:152-186）内**无任何审计/日志埋点**，仅 `logger` 在模块顶层定义但未在 builtin 分支使用。而 `MatchService.match_one` 内部（match.py:224-237）**已写 `SkillExecutionLog`**。故 `match_score` builtin 委托 `match_one` 即自动继承审计，builtin 本身不加任何埋点，与 R2 "沿袭、不加" 一致。

### R3 · MatchService.match_one 的返回值适配
`match_one` 返回 `MatchScore` ORM 对象。`_execute_builtin` 里需转换为 dict 输出（`{"match_score_id": score.id, "jd_id": ..., "resume_id": ..., "score": score.score, "reasoning": score.reasoning, ...}`）便于 SSE JSON 序列化。字段清单以 `MatchScore` 模型现有可序列化字段为准，敏感字段（如 reasoning 全文）若过大可只返 `match_score_id` + `score` 简摘，具体字段清单执行体自主定，STEP6 记录。

> executor 复核：`MatchScore` 字段为 `score_id / jd_id / resume_id / overall_score / dimension_scores(JSON) / matching_skill_id / matching_skill_version / skill_execution_id / resume_updated_at_snapshot / jd_updated_at_snapshot / status / error_message` + TimestampMixin(`created_at`,`updated_at`)。DECISION §3.2 采用 `{match_score_id, jd_id, resume_id, score(=overall_score), dimension_scores, matching_skill_id, status}`（dimension_scores 内含 reasoning，未超量，保留）。

---

## §三 求助边界（DECISION 版本预定）

DECISION 阶段 stop-and-ask 触发条件（复用 PR-20 风格）：

1. `MatchService.match_one` 签名与本 REVISIONS 假设不符（例如需 db 而非 db + 参数、或 async 与否不匹配）。
2. `BUILTIN_TOOLS` 结构（`input_schema` / `description` 字段名）与本 REVISIONS 描述不符，需实际读 `tool_router.py:54` 现状再定 dict 结构。
3. TC-S5.2-2 走单元级组合仍 hang（重演陷阱 12），无法防 F1 回归 → 停下报告，考虑改用 subprocess httpx。
4. `_build_artifacts` 消费 `MatchService.match_one` 输出时 schema 不匹配（如 `_ARTIFACT_TYPE_MAP["match_score"]` 需 output 里有特定 key 才能构造 ResultArtifact）。
5. 三门任一未过（129→131+ passed / ruff 0 / build N/A）。
6. Commit 数超过 5（红测 + 4 绿：builtin 注册、engine plan 改名、agent.py 端点收敛、artifact map 改 key）。
7. 发现 §9.4 未记的新陷阱。

> executor 追加第 8 条（见 DECISION §3.5 新发现）：若 db 透传需改动超出 `run_act` / `_background_execute` 两处（如波及 execute-plan 主链路、或 engine 须新增 session_factory 持有），停下报告，避免 scope creep。

---

## §四 执行体下一步动作（明确指令）

1. 本 REVISIONS 内容我不 commit——直接以本对话消息为准，executor 把它落成 `PR21-KICKOFF-REVISIONS.md`（内容即上文 §一/§二/§三），提到 master。docs-only，允许直提。
2. 然后起 `PR21-KICKOFF-DECISION.md`（executor contract，10 章）：见下发的 commander 指令。
3. DECISION 提交后再等 commander 批准（不需问题清单二轮，DECISION 直接是 contract）。先提 REVISIONS，再提 DECISION，两个 commit 都到 master（docs-only）。
4. DECISION 批准后才起 feat 分支：`feat/pr-21-s51-match-score-tool-name-fix`。

---

## §五 时间预估调整

原估 1-1.5 天。因加了 F1 修复（builtin 注册 + 端到端测试防回归），上调为 2-3 天：
- KICKOFF REVISIONS + DECISION：0.5 天（本轮）
- 实现：1-1.5 天（含 F1 修复 + 双测试）
- STEP6 + FF：0.5 天

Stage 5.1 全景表不变（P2 codegen 3-5 天、MVP release 1-2 天），后续无累积影响。
