# PR-12 + PR-15 并行执行指令书

> 生成时间：2026-07-20
> 依据：PR-11 合并核验放行 + 指挥官并行放行决策
> 状态：**指挥官已授权并行**（PR-12 主任务 + PR-15 空窗填充）
> 当前 master HEAD：`6beb25e`（PR-11 已合入）

---

## 一、并行方案总览

**Track A · PR-12（S5-05/06/07/08 Orchestrator 主循环）**
- 复杂度：Stage 5 最重的单一 PR，需要一次性引入 R-P-R-A-R 五阶段 + 状态机 + 超时降级
- **启动即受阻**：有 5 个未固化的架构接触面必须先请示指挥官（见 §四 Q1–Q5）
- 因此执行体启动策略：**先写红态测试骨架 + 求助文档，再等裁定**

**Track B · PR-15（S5-10 candidate-merge Skill）**
- 复杂度：低，仅 1 个 dispatchable Skill + 4 个测试用例
- 依赖 S5-01/02 已就绪（均在 master），与 PR-12 文件级零重叠
- **用于填满 PR-12 等裁定的空窗时间**

**并行安全性证明**：
- 文件级零重叠（PR-12 只碰 `orchestrator_*` skill + `orchestrator/` 目录；PR-15 只碰 `candidate_merge/` skill）
- Registry 存在型断言（PR-11 已合入的 TC-S5-02-5 采用 `in` 而非 `==`），加 skill 不打破既有测试
- 合并顺序无关：任一先合，另一个 rebase 即可（FF-only，无 merge commit）

---

## 二、执行顺序（严格按此推进）

```
Step 1 · 开 Track A 分支 + 写红骨架 + 写求助文档 → 提交并立即切走
Step 2 · 开 Track B 分支 + 完整实现 PR-15 → push → 汇报（PR-15 先合入 master）
Step 3 · 等指挥官裁定 PR-12 求助 → rebase master → 继续 PR-12 转绿
Step 4 · PR-12 全绿 → push → 汇报（PR-12 后合入 master）
```

**关键纪律**：
- 禁止在同一分支上混改 PR-12 与 PR-15 的文件
- 禁止 merge commit，全程 FF-only，rebase 保持历史线性
- PR-12 裁定未回前**不要开始实现 orchestrator 生产代码**（只写测试骨架）

---

## 三、Track A · PR-12 启动步骤（Step 1）

### 3.1 建分支

```bash
git checkout master && git pull origin master --ff-only
git log --oneline -3   # 应看到 6beb25e feat(stage5): implement dispatch()... 在顶
git checkout -b feat/pr-12-s5-05-08-orchestrator
```

### 3.2 阅读参考文档（必读）

| 文档 | 章节 | 关注点 |
|---|---|---|
| `docs/planning/PLAN-STAGE5.md` | §5 R-P-R-A-R 流程 | 五阶段职责边界 |
| `docs/planning/PLAN-STAGE5.md` | §2 Q2 状态机矩阵 | 合法/非法转移含 CANCELLED |
| `docs/planning/TASKS-STAGE5.md` | §S5-05..S5-08 (L124–194) | 交付清单与验收判据 |
| `docs/planning/TEST-PLAN-STAGE5.md` | §S5-05..S5-08 | 19 用例的期望行为 |
| `docs/api-contract.md` | §3 事件契约 / §4 REST 端点 / §4.5 cancel | 输入输出结构 |

### 3.3 只做 3 件事（不做第 4 件）

**（1）新建 4 个测试文件红骨架**

按 PR-10/PR-11 的红态测试文件风格，为每个用例写 `import + 函数签名 + `pytest.raises(NotImplementedError)` / 断言未创建的模块导入即红`。**不实现生产代码**，只让 `uv run pytest -q` 显示"这些用例失败/collect error"。

```
backend/tests/test_stage5_s5_05_reason_reflect.py     # TC-S5-05-1..3 (3 用例)
backend/tests/test_stage5_s5_06_plan.py               # TC-S5-06-1..3 (3 用例)
backend/tests/test_stage5_s5_07_act.py                # TC-S5-07-1..5 (5 用例)
backend/tests/test_stage5_s5_08_state_machine.py      # TC-S5-08-1..8 (8 用例)
```

> **注意**：某些用例的期望行为依赖 Q1–Q5 裁定结果（如 emit 回调是同步/异步）。这些用例可以：
> - **方案 A**：写 `pytest.skip("waiting for PR-12 kickoff ruling")` 占位
> - **方案 B**：写两种可能的断言分支，加 `# TODO: 待裁定` 注释
>
> **推荐方案 A**，保测试文件干净。裁定后一次性 unskip 并填充。

**（2）建 Skill 目录 scaffold（仅 skill.yaml 骨架，不写 prompt.md 与 examples.yaml）**

```
backend/app/agent/skills/orchestrator_reason/v1_0_0/skill.yaml
backend/app/agent/skills/orchestrator_reflect/v1_0_0/skill.yaml
backend/app/agent/skills/orchestrator_plan/v1_0_0/skill.yaml
backend/app/agent/skills/orchestrator_reflect_plan/v1_0_0/skill.yaml
backend/app/agent/skills/orchestrator_reflect_act/v1_0_0/skill.yaml
```

每个 `skill.yaml` 只写必需字段（`skill_id / skill_name / version / description / internal: true / max_retries: 0`），**input_schema / output_schema 留空 `{}`**，待裁定后按 Reason/Reflect/Plan 输出结构填充。

**（3）写求助文档 `docs/planning/stage5/PR12-KICKOFF-QUESTIONS.md`**

模板见 §四。**必须**包含 Q1–Q5，可追加你在写红骨架时遇到的新歧义（记为 Q6+）。

### 3.4 提交（红骨架 commit）

```
git add backend/tests/test_stage5_s5_{05,06,07,08}_*.py
git add backend/app/agent/skills/orchestrator_{reason,reflect,plan,reflect_plan,reflect_act}/
git add docs/planning/stage5/PR12-KICKOFF-QUESTIONS.md

git commit -m "test(stage5): PR-12 red test skeleton (TC-S5-05..08) + skill scaffolds + kickoff questions"
```

**不 push**（留在本地），立即切走到 Track B。裁定回来后再一起 push。

---

## 四、PR-12 求助文档模板（`PR12-KICKOFF-QUESTIONS.md`）

复制以下内容作为文件起点：

```markdown
# PR-12 · Orchestrator 主循环启动前求助

> 关联：PR-12（S5-05/06/07/08）· 分支 `feat/pr-12-s5-05-08-orchestrator`
> 触发：TASKS-STAGE5.md 与 api-contract.md 未固化以下 5 个架构接触面
> 状态：等待指挥官裁定，暂停 PR-12 生产代码实现

## Q1 · Reason/Reflect 输出 JSON 结构

**已知**：api-contract §5.1 声明 `ReasonOutput.task_type: string`、`missing_entities: array`；
`ReflectOutput.is_feasible: bool`。

**歧义**：
- Reason 是否需要输出 `intent_summary`（供 Plan 阶段 prompt 引用）？
- Reason 是否需要输出 `parsed_entities`（结构化实体：jd_id/candidate_ids/keyword...）？
- Reflect 除 `is_feasible` 外，`reason` / `blocking_reason` 字段是否需要？

**建议**：Reason 输出 `{task_type, intent_summary, parsed_entities, missing_entities}`；
Reflect 输出 `{is_feasible, blocking_reason?, suggestion?}`。

**影响**：ReasonSkill / ReflectSkill 的 `output_schema`（skill.yaml）与 5 用例断言。

## Q2 · emit 回调签名（同步 / 异步）

**已知**：TASKS §S5-07 说 `run_act(plan, ctx, emit) -> list[StepResult]`；
S5-03（PR-13）将由 Redis `LPUSH` 提供实现（async）。

**歧义**：
- `emit` 是 `def emit(ev: dict) -> None`（同步）还是 `async def emit(ev: dict) -> None`（异步）？
- 若异步，Act 里如何处理"emit 失败但不影响主流程"（`asyncio.create_task` 触发-遗忘？）？

**建议**：`async def emit(ev: dict) -> None`；Act 内 `await emit(ev)`，捕获 emit 异常
仅 log warning 不中断执行。

**影响**：`act.py` 签名与 Reflect-Act Skill 是否需要传 emit。

## Q3 · chat 端点是否内含 Act

**已知**：
- api-contract §4.1 `POST /agent/chat` → 返回 `task_id + status=WAITING_CONFIRMATION`
- api-contract §4.2 `POST /agent/execute-plan` → 触发 Act
- PLAN §5 R-P-R-A-R 描述为一体化流程

**歧义**：
- `chat` 是否只跑 R-P-R（Reason→Plan→Reflect-Plan）后停在 WAITING_CONFIRMATION？
- Act（Act + Reflect-Act）是否**只**由 `execute-plan` 触发？
- 或 `chat` 内部条件性触发 Act（例如 confidence 高时直接 Act）？

**建议**：`chat` 严格停在 WAITING_CONFIRMATION；`execute-plan` 独占 Act 触发权。
`skip-to-score` 例外，直达 EXECUTING（bypass R-P-R 但仍走 Act+Reflect-Act）。

**影响**：`engine.run_chat` / `engine.run_execute` / `engine.run_skip_to_score` 分层。

## Q4 · Redis 全局活跃计数策略

**已知**：TASKS §S5-08 说全局活跃 `task:active`（Redis INCR/DECR + TTL）；
达 10 抛 429 `TASK_LIMIT_EXCEEDED`。

**歧义**：
- TTL 值？（建议 3600s / 1h 兜底防泄漏）
- Redis 客户端在本 PR 内建立，还是**推迟到 PR-13** 与 EventBuffer 一起接？

**建议**：本 PR 用可注入的 `ActiveCounter` 抽象接口（内存实现 + Redis 实现留占位）；
测试用内存 mock 打满 10 触发 429。真实 Redis 接线由 PR-13 完成。

**影响**：`engine.py` 依赖注入设计、S5-08-3 用例的 mock 方式。

## Q5 · 超时配置（硬编码 vs settings）

**已知**：TASKS §S5-08 数字：单 Skill 120s / 阶段 180s / 整体 600s。

**歧义**：
- 硬编码还是引入 `SKILL_TIMEOUT_SEC / PHASE_TIMEOUT_SEC / TASK_TIMEOUT_SEC` 3 个新配置？
- 测试如何在不真等 120s 的前提下验证超时（monkeypatch 到 0.01s）？

**建议**：引入 3 个 settings 配置（默认 120/180/600），测试通过 `monkeypatch.setattr(settings, "SKILL_TIMEOUT_SEC", 0.01)` 触发。

**影响**：`backend/app/core/config.py` 追加 3 个字段、engine.py 从 settings 读。

## Q6+ · 执行体在红骨架时发现的新歧义

（执行体写红骨架时如遇新歧义，按 Q1–Q5 格式追加）
```

---

## 五、Track B · PR-15 执行步骤（Step 2，与 Q1–Q5 裁定并行）

### 5.1 建分支

**先切回 master**，从最新 master 拉 PR-15 分支（不能在 PR-12 分支上写）：

```bash
git checkout master   # 或 git switch master
git pull origin master --ff-only
git checkout -b feat/pr-15-s5-10-candidate-merge
```

### 5.2 交付清单（TASKS §S5-10 L220–233）

**新增文件（4 个）**：

| 路径 | 内容 |
|---|---|
| `backend/app/agent/skills/candidate_merge/v1_0_0/skill.yaml` | Skill 定义，`internal: false`, `task_type: merge_candidates`, `max_retries: 0` |
| `backend/app/agent/skills/candidate_merge/v1_0_0/prompt.md` | System prompt + `---USER_TEMPLATE---` + user prompt |
| `backend/app/agent/skills/candidate_merge/v1_0_0/examples.yaml` | Few-shot examples（至少 3 例：高置信/低置信/冲突） |
| `backend/tests/test_stage5_s5_10_candidate_merge.py` | TC-S5-10-1..4 (4 用例) |

**契约（skill.yaml）**：

```yaml
skill_id: candidate-merge
skill_name: 候选人智能合并
version: "1.0.0"
description: 输入多份候选人简历结构化数据，判定合并/建议/保持分离
task_type: merge_candidates
author: recruitment-agent
tags:
  - candidate
  - merge
  - dedup
max_retries: 0

input_schema:
  type: object
  properties:
    resumes:
      type: array
      minItems: 2
      items:
        type: object
        properties:
          resume_id: { type: string }
          candidate_name: { type: string }
          parsed_content: { type: object }
          tags: { type: array, items: { type: string } }
          duplicate_of_resume_id: { type: [string, "null"] }
        required: [resume_id]
  required: [resumes]

output_schema:
  type: object
  properties:
    action:
      type: string
      enum: [MERGE, SUGGEST, KEEP_SEPARATE]
    master_resume_id:
      type: [string, "null"]
      description: MERGE 时指向合并后的主 resume_id；KEEP_SEPARATE 时为 null
    merged_fields:
      type: object
      description: MERGE 时合并后的关键字段（name/phone/email/skills 等）
    confidence:
      type: number
      minimum: 0
      maximum: 1
    conflicts:
      type: array
      items: { type: object, properties: { field: { type: string }, values: { type: array } } }
    recommendation:
      type: string
      description: 人类可读的合并建议描述
  required: [action, confidence, recommendation]
```

**参考模板**：直接照抄 `backend/app/agent/skills/jd_candidate_matching/v1_0_0/` 的目录结构与 prompt.md 分节风格（system_prompt + `---USER_TEMPLATE---` + user_prompt），是最贴合的 dispatchable Skill 模板。

### 5.3 测试用例（TC-S5-10-1..4）

| # | 场景 | Mock LLM 返回 | 断言 |
|---|---|---|---|
| TC-S5-10-1 | 高置信度合并 | `{action:'MERGE', confidence:0.95, master_resume_id:'res_a', ...}` | `result.output["action"] == "MERGE"` |
| TC-S5-10-2 | 低置信度建议 | `{action:'SUGGEST', confidence:0.4, recommendation:'...', ...}` | `action == "SUGGEST"` |
| TC-S5-10-3 | 冲突保持分离 | `{action:'KEEP_SEPARATE', confidence:0.1, conflicts:[...], ...}` | `action == "KEEP_SEPARATE"` |
| TC-S5-10-4 | schema 校验失败降级 | `{action:'INVALID_ENUM', ...}` | `result.success is False` |

**Mock 目标**：`app.agent.llm_adapter.call_llm_json`（`monkeypatch.setattr`）。参考现有测试
`backend/tests/test_match_service.py` 的 mock 用法。

### 5.4 Commit 拆分（红→绿）

```
C1  test(stage5): add S5-10 candidate-merge red tests (TC-S5-10-1..4)
    files: backend/tests/test_stage5_s5_10_candidate_merge.py

C2  feat(stage5): scaffold candidate-merge skill.yaml + input/output schema
    files: backend/app/agent/skills/candidate_merge/v1_0_0/skill.yaml

C3  feat(stage5): implement candidate-merge prompt + examples
    files: backend/app/agent/skills/candidate_merge/v1_0_0/prompt.md
           backend/app/agent/skills/candidate_merge/v1_0_0/examples.yaml
```

### 5.5 验收三道门

| 门 | 命令 | 期望 |
|----|------|------|
| 门 1 | `cd backend && uv run pytest tests/test_stage5_s5_10_candidate_merge.py -q` | 4 passed |
| 门 2 | `cd backend && uv run pytest -q` | **70 passed**（66 + 4） |
| 门 3 | `cd backend && uv run ruff check tests/test_stage5_s5_10_candidate_merge.py` | 0 error |

### 5.6 push + 汇报

```bash
sleep 15 && git push -u origin feat/pr-15-s5-10-candidate-merge   # SSH port 22 可能超时，按 PR-10/11 经验重试
```

汇报模板：**沿用 `PR11-STEP6-REPORT.md` 结构**，生成 `docs/planning/stage5/PR15-STEP6-REPORT.md`。

---

## 六、Track A 恢复（Step 3–4，PR-15 push 后进行）

### 6.1 等指挥官裁定 Q1–Q5

指挥官会针对 `PR12-KICKOFF-QUESTIONS.md` 生成 `PR12-KICKOFF-DECISION.md`。**不动工，等文件出现**。

### 6.2 rebase master（若 PR-15 已合入 master）

指挥官合并 PR-15 后：

```bash
git checkout feat/pr-12-s5-05-08-orchestrator
git fetch origin
git rebase origin/master    # 应无冲突（文件级零重叠）
```

若意外冲突（例如都改了 `skill_registry.py`），停下汇报。

### 6.3 按裁定实现 PR-12 生产代码

**建议 commit 顺序**（可根据实际情况精简为 4–6 个 commit）：

```
C_R  feat(stage5): implement Reason + Reflect internal skills (S5-05)
C_P  feat(stage5): implement Plan + Reflect-Plan internal skills (S5-06)
C_A  feat(stage5): implement act.py pure module + emit contract (S5-07)
C_RA feat(stage5): implement Reflect-Act internal skill (S5-07)
C_E  feat(stage5): implement OrchestratorEngine + TransitionGuard (S5-08)
C_T  feat(stage5): wire timeouts + active counter + cancel path (S5-08)
```

每个 commit 后跑一次 `uv run pytest -q`，确认对应用例集从红转绿。

### 6.4 验收三道门（PR-12）

| 门 | 命令 | 期望 |
|----|------|------|
| 门 1 | `cd backend && uv run pytest tests/test_stage5_s5_0{5,6,7,8}_*.py -q` | 19 passed |
| 门 2 | `cd backend && uv run pytest -q` | **85 passed**（PR-15 合入前 66+19=85；PR-15 合入后 70+19=89） |
| 门 3 | `cd backend && uv run ruff check app/agent/orchestrator/ app/agent/skills/orchestrator_*/` | 0 error |

### 6.5 push + 汇报

```bash
sleep 15 && git push -u origin feat/pr-12-s5-05-08-orchestrator
```

汇报模板：沿用 `PR11-STEP6-REPORT.md` 结构，生成 `docs/planning/stage5/PR12-STEP6-REPORT.md`。

---

## 七、并行护栏（务必遵守）

### 7.1 分支隔离

- PR-12 改动**只**进 `feat/pr-12-s5-05-08-orchestrator`
- PR-15 改动**只**进 `feat/pr-15-s5-10-candidate-merge`
- **禁止**在其中一个分支上 `git add` 另一个 PR 范围的文件

### 7.2 PR-12 测试禁用精确基数断言

| ❌ 禁止 | ✅ 允许 |
|---|---|
| `assert len(registry.list_dispatchable()) == 1` | `assert "jd-candidate-matching" in ids` |
| `assert registry.list_dispatchable() == [x]` | `assert "orchestrator-reason" not in ids` |
| `assert dispatchable_count == N` | `assert x in dispatchable and y not in dispatchable` |

**理由**：PR-15 会引入 `candidate-merge` 到 dispatchable 集合，精确基数断言会在 PR-15 合入后突然翻红。存在型 / 排除型断言鲁棒。

### 7.3 rebase 优先，禁止 merge commit

- Stage 5 全程 FF-only，历史线性
- rebase 冲突时**停下汇报**，不擅自 `git checkout --theirs / --ours`

### 7.4 PR-15 汇报后**先等指挥官合并**

- PR-15 push 完成 → 汇报 → **等指挥官 FF merge to master**
- 再切回 PR-12 rebase
- **不要**在 PR-15 未合入时先 rebase PR-12 到 PR-15 分支（保持 master 为唯一 rebase 基准）

---

## 八、状态板（并行版）

| Track | PR | 内容 | 分支 | 状态 |
|---|---|---|---|---|
| A | **PR-12** | S5-05/06/07/08 Orchestrator | `feat/pr-12-s5-05-08-orchestrator` | 🟡 Step 1 · 红骨架 + 求助文档 |
| B | **PR-15** | S5-10 candidate-merge | `feat/pr-15-s5-10-candidate-merge` | 🟢 Step 2 · 可完整实现（无阻塞） |
| — | PR-13 | S5-03 EventBuffer + SSE emit | — | ⏳ 待 PR-12 |
| — | PR-14 | S5-09 REST/SSE 端点 | — | ⏳ 待 PR-12+PR-13 |
| — | PR-16 | S5-11 candidate-profile | — | ⏳ 与 PR-15 相似，可后续并行 |
| — | PR-17/18 | 前端 | — | ⏳ 待 PR-14 |

---

## 九、启动 checklist（执行体自检）

启动前，逐条打勾确认：

- [ ] 已读 `docs/planning/PLAN-STAGE5.md` §2/§5
- [ ] 已读 `docs/planning/TASKS-STAGE5.md` §S5-05..S5-10
- [ ] 已读 `docs/planning/TEST-PLAN-STAGE5.md` §S5-05..S5-10
- [ ] 当前 master HEAD = `6beb25e`
- [ ] 理解并行护栏 §七（尤其精确基数断言禁令）
- [ ] 理解 Step 1 只做 3 件事（红骨架 + Skill scaffold + 求助文档），**不实现 orchestrator 生产代码**
- [ ] 计划 Step 2 用 PR-11 报告模板生成 PR-15 STEP6 报告

**签到方式**：完成 Step 1 后向指挥官汇报"PR-12 红骨架 + 求助文档已提交 commit `<hash>`（本地未 push），现切至 PR-15 分支执行 Step 2"。

---

## 十、附录 · 求助边界（触发即停）

除 Q1–Q5 外，遇到以下任一情况**立即停下来问**，不擅自决策：

1. **PR-12 rebase 冲突**（预期无冲突；有则说明护栏被违反或指挥官合并策略需修正）
2. **PR-15 的 candidate-merge prompt 输出与 output_schema 不匹配**（需调整 schema 还是调整 prompt）
3. **Reason/Plan 输出的 `tool_name` 需要引用 candidate-merge，但 PR-12 落地时 PR-15 未合入**（时序耦合，需裁定顺序）
4. **19 用例中某个用例的期望行为与 api-contract 现有描述冲突**（先问，不擅自改契约）
5. **PR-15 完成后指挥官指示"先做 PR-16 再回 PR-12"**（保持灵活）

**其他属实现细节，自主决策**：
- Skill prompt.md 的自然语言表达
- examples.yaml 的具体 few-shot 数据
- 测试 mock 数据的字段值
- 内部辅助函数命名

---

**开始 Step 1：切到 master 拉 PR-12 分支，写红骨架 + Skill scaffold + 求助文档，提交后立即切到 Step 2。**
