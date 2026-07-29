# PR-24 · KICKOFF-DECISION

> 关联：`docs/planning/stage5/PR24-KICKOFF-QUESTIONS.md`（commit `b9b4668`）
> 用户裁定：**全采纳建议**（§Q1–§Q9 + §附执行流水）
> 起始 master HEAD：`b9b4668`（含本 DECISION 之前 = `b9b4668`）
> 类型：**代码 PR** · 分支 `feat/pr-24-fix-orchestrator-prompt-templates` · red-test → commit split → FF-merge
> Baseline：pytest 131 passed / 1 skipped · ruff 0 全仓 · frontend build ✓ · migration head `b6c7d8e9f0a1`

---

## 一、执行契约（§Q 逐项裁定）

| # | 议题 | 裁定 | 落地动作 |
|---|------|------|----------|
| Q1 | B5 修复策略 | **B · 数据 + 代码 fail-fast** | 5 个 prompt.md 补 USER_TEMPLATE + `base_skill.py:_load_from_directory()` 加护栏 |
| Q2 | 5 个 prompt 的 USER_TEMPLATE 措辞 | **认可 QUESTIONS §Q2.1–2.5 五段草稿** | 按下方 §三.1 逐字落地 |
| Q3 | fail-fast 触发条件 | **A · `_user_prompt_template == "" and input_schema.get("required")`** | `base_skill.py` 护栏严格采用此条件 |
| Q4 | 测试策略 | **Q4.1/4.2/4.3 全做** | TC-PR24-1..3 单元 · TC-PR24-4..5 集成 · TC-PR24-6 真 LLM e2e |
| Q5 | B4 SSE terminal | **A · 独立 commit 合入 PR-24** | commit 5 单独修 `engine.py:379-388` |
| Q6 | `GET /tasks/{id}` 500 | **C · HANDOFF §9.3.17 登记 · 挂账** | 不塞 PR-24 · Step 7 收尾时补 §9.3.17 |
| Q7 | 补跑 MVP-VERIFY §4/§5/§6 | **B · PR-24 STEP6 报告加节承担** | 不起 v2 report · Step 6 内跑通即写 |
| Q8 | commit split | **A · TDD strict · 6 commit** | 按下方 §四 6 段落地 |
| Q9 | 求助边界 | **3 条增补**（继承 6 + 新 3） | 见下方 §六 |

---

## 二、执行流水（可执行 · 顺序 · 每步产出物明确）

### Step 0 · KICKOFF-DECISION（本文档）· ~10 min
- **动作**：写完 + push master
- **完成态**：本 file commit hash 落 master

### Step 1 · 起分支 · Red-test 骨架（~30 min）
- **动作**：
  1. `git checkout master && git pull`
  2. `git checkout -b feat/pr-24-fix-orchestrator-prompt-templates`
  3. 新增 `backend/tests/test_stage5_pr24_prompt_templates.py`（TC-PR24-1/2/3 骨架 · 全 red）
  4. 新增 `backend/tests/test_stage5_pr24_orchestrator_integration.py`（TC-PR24-4/5 骨架 · 全 red）
  5. 新增 `backend/tests/test_stage5_pr24_llm_e2e.py`（TC-PR24-6 骨架 · `@pytest.mark.llm_e2e` · red）
  6. commit 1：`test(pr-24): red-test skeleton for TC-PR24-1..6 (all failing)`
- **完成态**：`pytest -q` 应 5 个 red（TC-PR24-6 用 `-m llm_e2e` 单跑）· 其余 131 依旧绿

### Step 2 · 5 个 prompt.md 补 USER_TEMPLATE（~10 min）
- **动作**：按 §三.1 逐字改 5 个文件
  - `backend/app/agent/skills/orchestrator_reason/v1_0_0/prompt.md`
  - `backend/app/agent/skills/orchestrator_reflect/v1_0_0/prompt.md`
  - `backend/app/agent/skills/orchestrator_plan/v1_0_0/prompt.md`
  - `backend/app/agent/skills/orchestrator_reflect_plan/v1_0_0/prompt.md`
  - `backend/app/agent/skills/orchestrator_reflect_act/v1_0_0/prompt.md`
- **commit 2**：`feat(orchestrator): add USER_TEMPLATE section to 5 orchestrator internal skills (B5 fix)`

### Step 3 · base_skill.py fail-fast 护栏（~15 min）
- **动作**：改 `backend/app/agent/base_skill.py:_load_from_directory()`
  - 加载 prompt.md 后判定：`if not self._user_prompt_template.strip() and self._input_schema.get("required"): raise ValueError(...)`
  - 错误文案：`f"Skill {self.skill_id} has non-empty input_schema.required={required} but no USER_TEMPLATE section in prompt.md"`
- **⚠️ 边界校验**：改完立即跑全量 `pytest -q`，若 PR-12 老 stub 集体失败 → **停 · 报回**（见 §六 边界 2）
- **commit 3**：`feat(base_skill): fail-fast on empty user prompt template with non-empty input_schema.required`

### Step 4 · 单元 + 集成 5 个测试转绿（~30 min）
- **动作**：把 TC-PR24-1..5 从 red 改成 green（填 mock 数据 / mock `call_llm_json`）
- **验证**：`cd backend && uv run pytest -q tests/test_stage5_pr24_prompt_templates.py tests/test_stage5_pr24_orchestrator_integration.py` → **5 passed**
- **commit 4**：`test(pr-24): green tests TC-PR24-1..5 pass`

### Step 5 · B4 独立 commit（~20 min）
- **动作**：改 `backend/app/agent/orchestrator/engine.py:379-388`
  - `is_feasible=false` 分支 `return` 前补 `await emit(SSEEventType.ERROR, {"error_type": "infeasible", "blocking_reason": reflect_out.blocking_reason})`（具体字段以 SSEEvent schema 为准）
  - 或用 `SYSTEM` `{"message": "cancelled"}`—在 §三.2 详述二选一
- **新增单测**：`tests/test_stage5_pr24_b4_sse_terminal.py`（红→绿 · TC-PR24-B4-1：mock reflect infeasible · 断言 stream 收到 terminal event）
- **commit 5**：`fix(orchestrator): emit SSE terminal event on infeasible reflect (B4 fix)`

### Step 6 · LLM e2e TC-PR24-6 转绿 · MVP-VERIFY §4/§5/§6 补跑（~40 min）
- **动作**：
  1. `uv run pytest -q -m llm_e2e tests/test_stage5_pr24_llm_e2e.py`（真调 LLM · unique token 断言）
  2. **前端 e2e 复核**（手工 · 起后端 + 前端 · UI 触发 §4/§5/§6 三 skill · 观察 SSE 8 类事件命中）
  3. STEP6 报告加 §MVP-VERIFY-RERUN 节记录（不起 v2）
- **commit 6**：`test(pr-24): green LLM e2e TC-PR24-6 with unique token proof`
- **完成态**：TC-PR24-6 green · UI 三 skill 均触达 COMPLETED · SSE 8 类命中 ≥6

### Step 7 · 三门验收 + STEP6 报告 + push（~15 min）
- **三门验收**：
  - `cd backend && uv run pytest -q` → 期望 **131+7 = 138 passed / 1 skipped**（TC-PR24-1..6 + TC-PR24-B4-1）
  - `cd backend && uv run ruff check app tests` → **0 errors**
  - `cd frontend && npm run lint && npm run build` → 通过（本 PR 不改前端 · 应无关）
- **文档**：
  - 写 `docs/planning/stage5/PR24-STEP6-REPORT.md`（含 §验收三道门 · §MVP-VERIFY-RERUN · §B4 结论）
  - HANDOFF.md §9.3.17 登记 `GET /tasks/{id} 500`（见 §五）
  - HANDOFF.md §9.3.18 登记 B5 修复完成（关联 §9.3.16）
- push 分支 · 报回指挥官 FF-merge

---

## 三、关键落地细节

### 三.1 · 5 个 USER_TEMPLATE 权威文本（照抄）

**orchestrator_reason**：
```
---USER_TEMPLATE---
## 用户消息
{{ user_input }}

## 上下文
{{ context | tojson if context else '{}' }}
```

**orchestrator_reflect**：
```
---USER_TEMPLATE---
## Reason 输出
{{ reason_output | tojson }}
```

**orchestrator_plan**：
```
---USER_TEMPLATE---
## Reason 输出
{{ reason_output | tojson }}

## 可派单工具清单
{{ dispatchable_tools }}
```

**orchestrator_reflect_plan**：
```
---USER_TEMPLATE---
## Plan 输出
{{ plan | tojson }}
```

**orchestrator_reflect_act**：
```
---USER_TEMPLATE---
## 各步骤执行结果
{{ step_results | tojson }}
```

### 三.2 · B4 fix · SSE terminal 选型

**选定**：**ERROR 事件** · payload 结构：
```python
await emit(SSEEventType.ERROR, {
    "error_type": "infeasible",
    "blocking_reason": reflect_out.blocking_reason,
    "reason_output": reason_out.model_dump() if reason_out else None,
})
```

理由：`_is_terminal()` 认可 ERROR / RESULT / SYSTEM(cancelled) 三态；infeasible 语义上是"不可继续"→ ERROR 比 SYSTEM 更准；且前端 error 卡片已在 PR-19 落地（可直接 render blocking_reason）。

**⚠️ 执行体如发现 SSEEvent schema 与上文字段名不符** → 停 · 报回（不擅改 schema）。

### 三.3 · Test 结构骨架（合同）

**`tests/test_stage5_pr24_prompt_templates.py`**：
```python
import pytest
from app.agent.base_skill import BaseSkill
from app.agent.skill_registry import SkillRegistry

# TC-PR24-1
def test_all_skills_render_non_empty_user_prompt(): ...
# TC-PR24-2
def test_orchestrator_reason_reads_context(): ...
# TC-PR24-3
def test_base_skill_load_fail_fast_on_empty_template(tmp_path): ...
```

**`tests/test_stage5_pr24_orchestrator_integration.py`**：
```python
# TC-PR24-4
async def test_reason_reads_frontend_context(monkeypatch): ...
# TC-PR24-5
async def test_full_rpr_flow_uses_input(monkeypatch): ...
```

**`tests/test_stage5_pr24_llm_e2e.py`**：
```python
@pytest.mark.llm_e2e
async def test_reason_reads_context_real_llm():
    # unique tokens: jd_UNIQUE_XYZ_2607 / c_UNIQUE_ABC_2607
    ...
```

**`pyproject.toml` markers**：确认已有 `llm_e2e` marker，若无则加：
```toml
[tool.pytest.ini_options]
markers = [
    "llm_e2e: real LLM end-to-end tests (opt-in, network + API key required)",
]
```

---

## 四、Commit split（TDD strict · 6 commit）

| # | commit | 触及文件 |
|---|--------|----------|
| 1 | `test(pr-24): red-test skeleton for TC-PR24-1..6 (all failing)` | 3 新测试文件（骨架 · red） |
| 2 | `feat(orchestrator): add USER_TEMPLATE section to 5 orchestrator internal skills (B5 fix)` | 5 prompt.md |
| 3 | `feat(base_skill): fail-fast on empty user prompt template with non-empty input_schema.required` | `base_skill.py` |
| 4 | `test(pr-24): green tests TC-PR24-1..5 pass` | 3 测试文件（填充实现） |
| 5 | `fix(orchestrator): emit SSE terminal event on infeasible reflect (B4 fix)` | `engine.py` + `test_stage5_pr24_b4_sse_terminal.py` |
| 6 | `test(pr-24): green LLM e2e TC-PR24-6 with unique token proof` | `test_stage5_pr24_llm_e2e.py` 填充 |

**分支**：`feat/pr-24-fix-orchestrator-prompt-templates`

---

## 五、HANDOFF 更新契约（Step 7 落地）

**§9.3.17**（新增 · GET /tasks/{id} 500 挂账）：
```
### §9.3.17 GET /api/v1/agent/tasks/{id} 返回 500（挂账）
- **状态**：登记不修 · 等某 PR 顺清
- **现象**：MVP-VERIFY §附3 记录 · 疑似 plan 缺 task_id 字段致响应序列化失败
- **绕过**：DB 直查 executions/tasks 表（MVP-VERIFY §附1 有示范）
- **建议**：独立 PR-25 或后续任一 PR 顺路修
```

**§9.3.18**（新增 · B5 修复完成）：
```
### §9.3.18 B5 orchestrator prompt template 修复完成（PR-24）
- **状态**：CLOSED · commit <PR-24 最终 hash>
- **关联**：§9.3.16 · MVP-VERIFY-RUN-REPORT §四 B5
- **修复面**：5 prompt.md + base_skill.py fail-fast + 6 测试
- **e2e 证明**：TC-PR24-6 用 unique token `jd_UNIQUE_XYZ_2607` 反幻觉验证通过
```

**§9.4.13** 已由 MVP-VERIFY 执行体登记（"orchestrator internal skill prompt.md 无 USER_TEMPLATE 段"陷阱），本 PR 不再重复。

---

## 六、求助边界（继承 MVP-VERIFY §五 6 条 + PR-24 增 3 条）

**继承**（不复述）：MVP-VERIFY-KICKOFF-DECISION §五 6 条边界。

**PR-24 增补**（触及必停）：

1. **修完后 TC-PR24-6（LLM e2e）依然失败** → 说明 5 skill USER_TEMPLATE 内容/变量不对 · 停 · 不擅自改模板措辞 · 报回让指挥官定。
2. **`base_skill.py` 加 fail-fast 后 PR-12 老单测集体失败** → 说明 stub-pattern 冲突 · 停 · 分析后报回（可能需修 5 stub 加 skill.yaml 副本，或 fail-fast 改 `skill_dir is None` 分岔）。
3. **修复后 §4/§5/§6 补跑仍有异常** → 不擅自登记为 B7/B8 · 先检查是否 B5/B4 未清 · 报回决定继续修还是独立 PR。

**通用**（AGENTS.md 已定 · 复述加固）：
- SSEEvent schema 与 §三.2 描述不符 → 停 · 不擅改 schema。
- 三门验收任一失败 → 停 · 不 push · 报回。

---

## 七、通过判定（严 · 一票否决）

**全绿判据**：
- [ ] pytest 全量 `138 passed / 1 skipped`（含 TC-PR24-1..6 + TC-PR24-B4-1）
- [ ] ruff 全仓 0 errors
- [ ] frontend build 通过（无关本 PR · 但要跑）
- [ ] TC-PR24-6 真调 LLM · unique token `jd_UNIQUE_XYZ_2607` 与 `c_UNIQUE_ABC_2607` 均出现在 `reason_out.parsed_entities`
- [ ] MVP-VERIFY §4/§5/§6 三 skill UI 手动补跑均触达 COMPLETED
- [ ] SSE 8 类事件命中 ≥6（B4 修完后 error 类必现）
- [ ] STEP6 报告写完 · HANDOFF §9.3.17/§9.3.18 落 · push 分支等 FF-merge

---

## 八、指挥官核验清单

- [x] 本 DECISION 覆盖 QUESTIONS 9 议题 + 3 边界
- [x] 与 HANDOFF §9.4 陷阱兼容（§9.4.13 已存在 · PR-24 是治本 PR）
- [x] TDD 6-commit split 与 AGENTS.md 兼容
- [x] Baseline 明确（HEAD=`b9b4668` · pytest 131/1 · ruff 0 · migration `b6c7d8e9f0a1`）
- [x] Q4.3 真 LLM e2e 为唯一证伪手段 · 已明确 opt-in 机制
- [ ] **本 DECISION commit 后开跑 Step 1**（等执行体接手）

---

## 九、执行流水（时间预估）

```
Step 0 · KICKOFF-DECISION（本 · docs-only 落 master）· ~10 min
Step 1 · 起分支 + red-test 骨架 6 个 failing · ~30 min
Step 2 · 5 prompt.md USER_TEMPLATE · ~10 min
Step 3 · base_skill.py fail-fast + 全量 pytest 边界校验 · ~15 min
Step 4 · TC-PR24-1..5 转绿 · ~30 min
Step 5 · B4 独立 commit + TC-PR24-B4-1 · ~20 min
Step 6 · TC-PR24-6 LLM e2e 转绿 + MVP-VERIFY §4/§5/§6 补跑 · ~40 min
Step 7 · 三门验收 + STEP6 报告 + HANDOFF 更新 + push · ~15 min
─────────────────────────────
顺利：170 min · 悲观（边界 2 触发）：3–4 h
```

---

**执行开跑触发条件**：本 DECISION commit 落 master 后 · 新 session 执行体拉 `feat/pr-24-fix-orchestrator-prompt-templates` 分支 · 按 §二 Step 1 起。
