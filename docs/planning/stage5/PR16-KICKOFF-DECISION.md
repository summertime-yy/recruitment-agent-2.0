# PR-16 · candidate-profile Skill · 启动裁定

> 关联：`docs/planning/stage5/PR16-KICKOFF-QUESTIONS.md` · 建议分支 `feat/pr-16-s5-11-candidate-profile`
> 权威依据：`docs/planning/TASKS-STAGE5.md §S5-11` · `docs/planning/TEST-PLAN-STAGE5.md §S5-11（TC-S5-11-1..4）` · `docs/planning/PLAN-STAGE5.md §187/§269` · `docs/api-contract.md §5.1` · PR-15 交付物（`candidate_merge/v1_0_0`）作模板
> 生成时间：2026-07-22
> 状态：**9 问全部裁定 + 2 条追债项预登记 + 交付范围显式绑定，执行体可立即按 §十四 开工**

---

## 一、前置状态确认（与 QUESTIONS §前置事实同步，2026-07-22 · master `dac4337`）

| 项 | 状态 |
|---|---|
| master HEAD（本地 + 远端） | `dac4337`（PR-14 已 FF 合入 + HANDOFF §9 刷新） |
| 本地 pytest 基线 | **110 passed** |
| 依赖状态 | 无新增（100% 复用 PR-15 管道：BaseSkill + jsonschema + `llm_adapter.call_llm_json`） |
| Engine 关键预登记 | `_ARTIFACT_TYPE_MAP` 已含 `candidate-profile` → `candidate_profile`（PR-14），但 `_build_artifacts` 出口无对应分支（Q5 主线补） |
| Skill 三件套模板 | PR-15 `backend/app/agent/skills/candidate_merge/v1_0_0/`：`skill.yaml + prompt.md + examples.yaml`（无 Python 类文件） |
| 测试模板 | PR-15 `tests/test_stage5_s5_10_candidate_merge.py`（monkeypatch `app.agent.llm_adapter.call_llm_json` + `BaseSkill(SKILL_DIR).execute(...)`） |

---

## 二、主裁定 · PR-16 交付范围硬边界

### 裁定：**PR-16 = 孤立 Skill 三件套 + 单元测试 + 数据型 Artifact 出口补齐**（不含端到端路由）

**范围内**（本 PR 必交付）：

1. `backend/app/agent/skills/candidate_profile/v1_0_0/` 三件套：
   - `skill.yaml`（含三命名空间：`skill_id: candidate-profile` 连字符 / `task_type: profile_candidate` 下划线 / input/output schema）
   - `prompt.md`（SYSTEM_PROMPT + USER_TEMPLATE，四字段强约束 + 合规约束 + 归一去重指令）
   - `examples.yaml`（3 个 few-shot：正常、合并去重、空 parsed_content）
2. `backend/tests/test_stage5_s5_11_candidate_profile.py`（TC-S5-11-1..4）
3. `engine.py::_build_artifacts` 数据型 artifact 出口分支（Q5 方案 C，含 `candidate_merge` + `candidate_profile` 一并归零）
4. `backend/tests/test_stage5_s5_09_engine.py` 或独立文件追加 1 个 engine 单测（断言 `type` 不降级 + `data` 完整）

**范围外**（本 PR 显式声明不做，触碰即触发 §十三 边界）：

- **端到端路由打通**（reason → plan → dispatch 让"自然语言 → candidate-profile"跑通）—— 登记为追债项 11，Stage 5.1 修
- **修改 `orchestrator-reason` 或 `orchestrator-plan` 的 `prompt.md` / `skill.yaml` / `examples.yaml`**（无论"顺手补 profile_candidate 描述"看起来多小 —— 见 §十二 撤回说明）
- **修改 `run_plan` 逻辑**尝试注入 dispatchable 清单
- **修改 `models/task.py:24` comment 或 `api/v1/agent.py:159`** SCREAMING 字面量（Q1 方向 B 明确保留）
- **修改 TASKS-STAGE5.md § S5-11 或 S5-10** 命名漂移（Q9 明确 STEP6 归档，不改文档）
- Skill 落库副作用（Q6 明确无写库）

**执行体必读**：**PR-16 交付后 `candidate-profile` 与 PR-15 的 `candidate-merge` 一样是"孤立 Skill"**，只能通过 REST 硬编码 plan 或前端手工拼装 plan 触发，无法被用户自然语言消息触发。这是 PR-15/16 共同债务，追债项 11 在 Stage 5.1 统一收敛。

---

## 三、Q1 裁定 · task_type 三命名空间共存（方向 B）

### 裁定：**方向 B —— 承认三命名空间共存，PR-16 不做任何命名 refactor**

**三命名空间共存**（追债项 10 canonical 表述）：

| 命名空间 | 惯例 | 示例 | 谁写入 |
|---|---|---|---|
| `skill_id` / `tool_name`（分发键） | **连字符 lowercase** | `candidate-merge` / `candidate-profile` | skill.yaml `skill_id` 字段；plan 输出 `tool_name` |
| `skill.yaml.task_type`（意图键） | **下划线 lowercase** | `merge_candidates` / `profile_candidate` | skill.yaml `task_type` 字段；reason 输出 `task_type` |
| `tasks.task_type` DB 列（业务分类） | **SCREAMING** | `MATCH_SCORE` / `PROFILE_CANDIDATE` | REST 端点 INSERT |

### 本 PR 落地

- **PR-16 skill.yaml** → `skill_id: candidate-profile` + `task_type: profile_candidate`
- **不动** `models/task.py:24` comment
- **不动** `api/v1/agent.py:159` SCREAMING 字面量
- **不动** 其他任何 task_type 相关文件

### 追债项登记（STEP6 §五 强制）

**追债项第 10 条** · task_type 三命名空间共存（本 PR 首次 canonical 登记）
**追债项第 11 条** · orchestrator reason/plan 未登记 dispatchable Skill，自然语言路由不通（跨 PR-15/16 共同债务）

两条追债项完整表述见 §十九。**Stage 5.1 收敛方向**：两条追债项**必须在同一 PR 收敛**（拆命名空间时路由测试无基础，反之亦然）。

---

## 四、Q2 裁定 · tag 归一去重 → prompt 负责（方案 B）

### 裁定：**方案 B**

- `prompt.md` USER_TEMPLATE 明确指令："在生成 `profile_tags` 时，请与 `existing_tags` 合并并按大小写归一去重（'Python' 与 'python' 视为同一标签，保留首次出现形式）"
- 不改 BaseSkill、不引入 Python 后处理
- TC-S5-11-2 mock LLM 返**已归一好**的 payload（`profile_tags: ["Python", "SQL"]`），断言无重复 + 长度符合
- **测的是 Skill 契约**（output schema 通过、返值可读），**不测 LLM 归一能力**

---

## 五、Q3 裁定 · 输入字段名 `existing_tags`

### 裁定：**采纳 `existing_tags`**（沿用 TASKS §S5-11:243 字面）

- 输入 schema：`{parsed_content: object, existing_tags: string[]}`
- 与 PR-15 `resumes[].tags`（简历子字段）语义分离，命名分工清晰

---

## 六、Q4 裁定 · 空 parsed_content 处理（方案 B）

### 裁定：**方案 B**

- `input_schema.parsed_content: type: object`（无 `minProperties`，允许 `{}`）
- prompt 明确处理规则：`parsed_content` 为空时 → 返 `{"profile_tags": [], "summary": "简历内容为空", "strengths": [], "risks": []}`
- Skill 视为 SUCCESS（output schema 校验通过）
- TC-S5-11-4 mock LLM 返上述空结果，断言 success + `profile_tags=[]`

---

## 七、Q5 裁定 · Artifact ref_id 提取（方案 C）

### 裁定：**方案 C —— `_build_artifacts` 数据型分支含 `candidate_merge` + `candidate_profile` 一并归零**

### 具体改动（engine.py 现有 `_build_artifacts` 逻辑附近）

```python
# 在 ref_id 提取分支之后 / generic fallback 之前 插入：
elif artifact_type in {"candidate_merge", "candidate_profile"}:
    item["data"] = output  # 数据型 artifact，无 ref_id，保留完整 output
    # type 保持原 artifact_type，不降级
elif ref_id is not None:
    item["ref_id"] = str(ref_id)
else:
    # 引用型但未提取到 ref_id → 降级为 generic
    item["type"] = "generic"
    item["data"] = output
```

### 追加测试

**必加 1 个 engine 单测**（放在 `tests/test_stage5_s5_11_candidate_profile.py` 尾部或 `tests/test_stage5_s5_09_engine.py`）：

```python
def test_build_artifacts_data_types_preserve_type():
    # 构造 tool_output(tool_name="candidate-profile", output={profile_tags:[...]})
    # 断言 result[0]["type"] == "candidate_profile"（未降级）
    # 断言 result[0]["data"] == output（完整嵌入）
    # 断言 "ref_id" not in result[0]
    ...
```

**同时补 1 个 candidate_merge 断言**（同函数内或独立测试）：确保 PR-15 交付物出口一并归零。

### 追债项 3（`_ARTIFACT_TYPE_MAP` 与前端渲染器手动同步）依然保留

Q5 只闭合"出口路径"，前端 `type` 消费点仍需 PR-17/18 建立。追债项 3 未消除。

---

## 八、Q6 裁定 · Skill 无落库副作用

### 裁定：**Skill 只出数据 · 无 DB 写入**

- Skill 契约：input `{parsed_content, existing_tags}` → output `{profile_tags, summary, strengths, risks}`
- 落库（若需要）由 REST 端点或 Stage 5.1 专门端点做，PR-16 交付面外
- 与 PR-15 candidate-merge 对称

---

## 九、Q7 裁定 · prompt.md 设计

### 裁定：对齐 PR-15 结构

**SYSTEM_PROMPT**：
- 角色：资深人才画像分析师
- 原则：客观、合规、**不基于性别 / 年龄 / 婚育 / 地域 / 民族 / 学历歧视性字段**做评价；只输出 JSON

**USER_TEMPLATE**（Jinja2）：
- `{{ parsed_content }}` + `{{ existing_tags }}` 占位
- 明列四字段输出要求（`profile_tags` / `summary` / `strengths` / `risks`）
- 归一去重规则（Q2）
- 空 parsed_content 处理规则（Q4）

**examples.yaml**：3 个 few-shot
1. 正常简历生成 4 字段
2. 与 existing_tags 合并去重（`existing_tags=["Python"]` + LLM 提取 `["Python", "SQL"]` → 输出无重复的 `["Python", "SQL"]`）
3. 空 parsed_content → 空 profile_tags + "简历内容为空" summary

---

## 十、Q8 裁定 · 测试策略

### 裁定：100% 沿用 PR-15 结构

**测试文件**：`backend/tests/test_stage5_s5_11_candidate_profile.py`

**模式**：
```python
from pathlib import Path
import pytest
from app.agent.base_skill import BaseSkill

SKILL_DIR = Path(__file__).resolve().parents[1] / "app" / "agent" / "skills" / "candidate_profile" / "v1_0_0"

def _patch_llm(monkeypatch, payload):
    async def _fake(system_prompt, user_prompt):
        return payload
    monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", _fake)

@pytest.mark.asyncio
async def test_tc_s5_11_1_profile_tags_non_empty(monkeypatch):
    _patch_llm(monkeypatch, {"profile_tags": ["Python", "Backend"], "summary": "...", "strengths": [...], "risks": [...]})
    skill = BaseSkill(SKILL_DIR)
    result = await skill.execute({"parsed_content": {...}, "existing_tags": []})
    assert result.success is True
    assert result.output["profile_tags"]
```

**基线变化**：110 → **114 or 115**
- +4 skill 测试（TC-S5-11-1..4）
- +1 engine 测试（Q5 方案 C 追加）
- 若把 candidate_merge artifact 断言拆成独立测试，则 +2 → 115

---

## 十一、Q9 裁定 · TASKS 文档不改，STEP6 §五 归档

### 裁定：**不改 TASKS-STAGE5.md**

**归档位置**：PR-16 STEP6 §五 声明"文档字面 vs 实现差异"，明列 2 处：
1. TASKS §S5-11 `task_types: [PROFILE_CANDIDATE]`（SCREAMING 复数数组）vs 实现 `task_type: profile_candidate`（下划线单数字符串）
2. TASKS §S5-10 `task_types: [MERGE_CANDIDATES]` 同类漂移（PR-15 已交付事实）

**理由**：TASKS 是双盲评审合并版，改动需比对 commander/executor 两版原始稿谨慎；STEP6 §五 = canonical 追溯位置，未来 PR 可查"已知漂移，选实现口径"。

**若指挥官后续希望反向改 TASKS**：另开 docs-only commit（一次修 S5-10 + S5-11 两处），不入 PR-16。

---

## 十二、§十二 · 顺手清扫

### 裁定：**PR-16 无顺手清扫**

### ⚠️ 撤回 "reason skill 描述补 profile_candidate"

原 QUESTIONS 曾列此项为可选建议 —— **本 DECISION 明确撤回**。

**理由**：
- 改一行 reason skill 描述 → 让 reason LLM 可能输出 `task_type: profile_candidate`
- 但 plan 侧仍不知道 `candidate-profile` 是有效 tool_name（plan prompt/examples 未登记）
- LLM 还需自己完成"下划线 profile_candidate → 连字符 candidate-profile"翻译，无可靠性保证
- **实际路由仍不通**，只是"欺骗自己看起来修了" —— 破坏追债项 11 canonical 表述

**结论**：**本 PR 不许改 reason/plan 任何 prompt / 描述 / examples**。真正修复见追债项 11 主体（Stage 5.1）。

---

## 十三、§十三 · 求助边界（9 条，执行体强制遵守）

执行时若触碰以下任一条件，**停下汇报，不得静默处理**：

1. **BaseSkill 通用管道对 `parsed_content: type: object` 空对象 `{}` 的处理与预期不符**（比如 jsonschema 默认拒绝空对象或未定义额外字段）：停下汇报，考虑 schema 调整
2. **`llm_adapter.call_llm_json` 签名或行为在 PR-13/14 之后有 breaking change**：停下汇报核对
3. **TC-S5-11-2 mock 断言方式与判据"合并去重"字面不一致**（比如 mock 需要传"未归一"payload 才对齐判据）：停下汇报讨论
4. **Q5 方案 C 改 `_build_artifacts` 触发 PR-15 / PR-14 既有测试 regression**（pytest < 110）：停下汇报
5. **Skill test 中 `monkeypatch.setattr("app.agent.llm_adapter.call_llm_json", ...)` 路径失效**（模块结构变化）：停下汇报
6. **pytest 基线倒退**（< 110）：停下汇报（无论触发点）
7. **⚠️ 执行体误改 reason/plan skill prompt / examples / 描述尝试"修路由"**（§十二 已明确撤回；若感到"改一行就通"的诱惑）：**立即停下汇报** —— 属追债项 11 主体，PR-16 严禁触碰
8. **⚠️ 执行体触碰 `models/task.py:24` comment 或 `api/v1/agent.py:159` SCREAMING 字面量**（Q1 方向 B 明确保留）：立即停下汇报
9. **发现新的命名空间漂移**（除已登记的 skill_id 连字符 / task_type 下划线 / tasks.task_type SCREAMING 三层外）：停下汇报，追债项 10 需扩表述

**不在本清单但材料改变 PR 契约的**（例：权威文档冲突、api-contract 新条款、TASKS §S5-11 判据字面理解分歧）：**同样停下汇报**。

---

## 十四、§十四 · 执行体行动清单（Executor Action Checklist）

按顺序完成，每步做完即打勾。

### 阶段 0 · 前置准备

- [ ] `git checkout master && git pull` 确认 = `dac4337`（或更新）
- [ ] `git checkout -b feat/pr-16-s5-11-candidate-profile`
- [ ] `cd backend && uv run pytest -q` = **110 passed**（基线）
- [ ] `cd backend && uv run ruff check app` = 0 error（基线）
- [ ] `cd backend && uv run ruff format --check app` = 0 diff（基线）
- [ ] 读完本 DECISION + `PR16-KICKOFF-QUESTIONS.md`（**特别精读 §二 交付范围硬边界 + §十二 撤回说明 + §十三 求助边界**）
- [ ] 读 PR-15 交付物 `backend/app/agent/skills/candidate_merge/v1_0_0/` 三件套 + `tests/test_stage5_s5_10_candidate_merge.py`（模板参考）
- [ ] 读 `engine.py::_build_artifacts` 附近代码（Q5 方案 C 落点定位）

### 阶段 1 · Red-test skeleton commit（TDD 起手）

- [ ] 建 `backend/app/agent/skills/candidate_profile/v1_0_0/` 空目录（暂不放 skill.yaml）
- [ ] 建 `backend/tests/test_stage5_s5_11_candidate_profile.py`：写 TC-S5-11-1..4 骨架（4 个 `@pytest.mark.asyncio` async def，可用 `pytest.mark.xfail(strict=True, reason="pending impl")` 或直接 red）
- [ ] `cd backend && uv run pytest -q tests/test_stage5_s5_11_candidate_profile.py` 确认 4 个红/xfail
- [ ] Commit: `test(stage5): PR-16 red-test skeleton (TC-S5-11-1..4) + candidate_profile scaffold`

### 阶段 2 · Skill 三件套落地（TC-S5-11-1..4 转绿）

- [ ] `skill.yaml`：
  - `skill_id: candidate-profile`（连字符）
  - `skill_name: 候选人画像生成`
  - `version: "1.0.0"`
  - `task_type: profile_candidate`（下划线）
  - `max_retries: 0`
  - `input_schema`：`{parsed_content: object, existing_tags: string[]}`（**不设 `minProperties: 1`**）
  - `output_schema`：`{profile_tags: string[], summary: string, strengths: string[], risks: string[]}`（四字段必填）
  - `prompt: prompt.md` / `examples: examples.yaml` 引用（对齐 PR-15 结构）
- [ ] `prompt.md`：Q7 定义的 SYSTEM_PROMPT + USER_TEMPLATE（含合规约束 + 归一去重指令 + 空 parsed_content 规则）
- [ ] `examples.yaml`：3 个 few-shot（Q7 §Q7 列表）
- [ ] `cd backend && uv run pytest -q tests/test_stage5_s5_11_candidate_profile.py` → **4 TC 转绿**
- [ ] `cd backend && uv run pytest -q` → **≥ 114 passed**（110 基线 + 4 新增）
- [ ] Commit: `feat(stage5): S5-11 candidate-profile skill three-parter (skill.yaml + prompt.md + examples.yaml)`

### 阶段 3 · Q5 方案 C · engine 数据型 artifact 出口

- [ ] 修 `backend/app/agent/orchestrator/engine.py::_build_artifacts`：在现有分支之间插入 `candidate_merge` + `candidate_profile` 数据型分支（§七 代码示范）
- [ ] 追加 1 个 engine 单测（`tests/test_stage5_s5_11_candidate_profile.py` 尾部 or `tests/test_stage5_s5_09_engine.py`）：
  - 构造 `tool_output(tool_name="candidate-profile", output={profile_tags: [...], summary: ..., ...})`
  - 断言 `result[0]["type"] == "candidate_profile"`（未降级 generic）
  - 断言 `result[0]["data"] == output`（完整嵌入）
  - 断言 `"ref_id" not in result[0]`
  - **可选**：同 test 或独立 test 覆盖 `candidate-merge`（PR-15 交付物一并断言）
- [ ] `cd backend && uv run pytest -q` → **≥ 115 passed**（若含 candidate_merge 独立断言则 115；合并到同一 test 则 114）
- [ ] Commit: `feat(stage5): _ARTIFACT_TYPE_MAP data-type artifacts (candidate_merge + candidate_profile)`

### 阶段 4 · 验收三道门

- [ ] `cd backend && uv run pytest -q` → **≥ 114 passed**（无 error / failed）
- [ ] `cd backend && uv run ruff check app` → **0 error**
- [ ] `cd backend && uv run ruff format --check app` → **0 diff**
- [ ] `cd frontend && npm run lint && npm run build` **可跳过**（PR-16 不动 frontend/src/**）
- [ ] 三道门输出粘贴到 STEP6 报告 §三

### 阶段 5 · STEP6 报告

- [ ] 写 `docs/planning/stage5/PR16-STEP6-REPORT.md`：
  - §一 概要（PR-16 = S5-11，交付孤立 Skill + 数据型 artifact 出口）
  - §二 完成清单（三件套 + 4 测试 + engine 分支 + engine 测试）
  - §三 验收三道门（三段输出粘贴）
  - §四 影响面（新增/修改文件清单）
  - §五 偏差 / 决策记录（**必列 4 条**）：
    - **19.1** · 追债项第 10 条登记 · task_type 三命名空间共存（本 PR 首次 canonical 表述）
    - **19.2** · 追债项第 11 条登记 · orchestrator reason/plan 未登记 dispatchable Skill，自然语言路由不通（跨 PR-15/16）
    - **19.3** · TASKS 文档字面 vs 实现差异（S5-10 / S5-11 两处 SCREAMING 复数数组 vs 实际 lowercase 单数字符串）
    - **19.4** · `_ARTIFACT_TYPE_MAP` 与前端渲染器手动同步（追债项 3 未消除，Q5 只闭合出口路径）
    - 如触发 §十三 任一条，此处也登记
  - §六 工作区清理（临时文件 rm 清单）
  - §七 提交链（commit hash + message 列表）
  - §八 合入后 docs 动作（HANDOFF §9.1 状态表 + §9.3 追债项 10/11 追加 + §9.5 新文件表）
- [ ] Push branch: `git push -u origin feat/pr-16-s5-11-candidate-profile`
- [ ] 回报指挥官 FF-merge 评审

---

## 十五、§十五 · Commit 拆分（最终建议）

**3 commit 版**（推荐，与 PR-15 对称）：

1. `test(stage5): PR-16 red-test skeleton (TC-S5-11-1..4) + candidate_profile scaffold`（阶段 1）
2. `feat(stage5): S5-11 candidate-profile skill three-parter (skill.yaml + prompt.md + examples.yaml)`（阶段 2）
3. `feat(stage5): _ARTIFACT_TYPE_MAP data-type artifacts (candidate_merge + candidate_profile)`（阶段 3）

**外加**：`docs(stage5): PR16 STEP6 report`（阶段 5，AGENTS.md §4.1 docs-only 可直推 master 或走本分支均可）。

**若执行体判断阶段 3 独立性不足**：可合入阶段 2 一并处理，变 2 commit（skeleton + all-in-one 三件套 + engine 出口）。**不建议**：会淡化"engine 出口修复"与"新增 Skill"的关注点分离。

---

## 十六、§十六 · 验收三道门（不可跳过）

| 门 | 命令 | 通过标准 |
|---|---|---|
| 门 1 · pytest | `cd backend && uv run pytest -q` | **≥ 114 passed**（含 4 skill 测试 + ≥1 engine 测试）；0 failed / 0 error |
| 门 2 · ruff lint | `cd backend && uv run ruff check app` | 0 error |
| 门 3 · ruff format | `cd backend && uv run ruff format --check app` | 0 diff |

三门任一 fail → 不得声明 PR 完成，不得写 "全绿" STEP6。

---

## 十七、§十七 · 合入后 docs 动作（指挥官 FF-merge 时统一操作）

- `HANDOFF.md` 头部：日期 → 2026-07-XX；PR-16 已合入 master；下一个 PR-17（前端 SSE Hook + ChatCenter）
- `HANDOFF §9.1` 状态表：PR-16 = ✅（commit hash 填入），基线 110 → 114 或 115
- `HANDOFF §9.3` 追债项：
  - **追加第 10 条**：task_type 三命名空间共存（引用 §十九 canonical 表述）
  - **追加第 11 条**：orchestrator reason/plan 未登记 dispatchable Skill，自然语言路由不通（跨 PR-15/16 共同债务）
- `HANDOFF §9.4` 起手须警惕：追加 "PR-17 前端起手时须知：candidate-profile / candidate-merge 均为孤立 Skill，自然语言路由不通，前端 chat → SSE 流仅能拿到 THINKING + PLAN + RESULT 事件，不能期待 candidate-* skill 通过自然语言消息被触发"
- `HANDOFF §9.5` 新文件表：追加 `backend/app/agent/skills/candidate_profile/v1_0_0/*`、`backend/tests/test_stage5_s5_11_candidate_profile.py`
- `HANDOFF §9.6` PR-17 起手路径：明确必读 追债项 10/11（前端不要期待自然语言触发 candidate-* skill）

---

## 十八、§十八 · 工作区清理

- 执行体产生的临时输出（如 `C:/temp/pytest_pr16.txt` 之类）**不纳入 git**，仅用作 STEP6 §三 输出粘贴源
- 工作区既有未跟踪文件（`backend/backend.err`、`backend/scripts/`）**不许纳入本 PR 提交**（PR-13/14 传承约定）
- 不许创建 tag、不许改 `backend/.env`（gitignored）

---

## 十九、§十九 · 追债项 canonical 表述（STEP6 §五 强制引用，HANDOFF §9.3 追加锚点）

### 追债项第 10 条 · task_type 三命名空间共存

**现状**：`task_type` 一词在系统中承载三套语义，字面各不相同：

| 命名空间 | 惯例 | 示例 | 谁写入 | 消费者 |
|---|---|---|---|---|
| `skill_id` / `tool_name`（分发键） | **连字符 lowercase** | `candidate-merge` / `candidate-profile` | skill.yaml `skill_id` 字段；plan 输出 `tool_name` | tool_router dispatch by tool_name |
| `skill.yaml.task_type`（意图键） | **下划线 lowercase** | `merge_candidates` / `profile_candidate` | skill.yaml `task_type` 字段；reason 输出 `task_type` | route_task_type 匹配 skill |
| `tasks.task_type` DB 列（业务分类） | **SCREAMING** | `MATCH_SCORE` / `PROFILE_CANDIDATE` / `GENERATE_JD` / `GENERAL_QA` | REST 端点 INSERT（agent.py:159） | 前端业务分类展示（Stage 5.1+） |

**本 PR 暂行**：PR-16 skill.yaml `skill_id: candidate-profile` + `task_type: profile_candidate`，与 PR-15 三命名空间格式完全对称；不动任何既有代码。

**风险**：
- LLM 需自行完成"下划线 profile_candidate → 连字符 candidate-profile"翻译，可靠性无保证
- 前端消费两套 task_type 易迷惑

**Stage 5.1 收敛方向**（**必须与追债项 11 同 PR 收敛**）：
1. **拆字段名**：`skill.yaml.task_type` → 改名 `dispatch_key`（消歧）
2. **引入映射表**：显式定义 `task_type → tool_name` 映射（消除 LLM 翻译负担）
3. **对齐 DB 列**：`tasks.task_type` 保持 SCREAMING 业务分类 or 迁移到 lowercase（Alembic 迁移决策）

**触发条件**：多进程部署前 / 前端消费两套 task_type 迷惑时 / 追债项 11 修复启动时

---

### 追债项第 11 条 · orchestrator reason/plan 未登记 dispatchable Skill，自然语言路由不通

**现状实测**（PR-16 kickoff 阶段核验，2026-07-22 · master `dac4337`）：

- `orchestrator_reason/prompt.md:6` 仅列 `match / merge_candidates / unknown`，**不含 `profile_candidate`**
- `orchestrator_plan/prompt.md:6` 字面说"tool_name 必须命中 dispatchable Skill ID 或内置工具（search_resumes / read_jd）"，**未注入具体 dispatchable 清单**
- `orchestrator_plan/examples.yaml` 仅示范 `search_resumes / read_jd`
- `engine.py:153 run_plan` 直接 `skill.execute(plan_input)`，**不动态注入 registry 里的 dispatchable skill 列表**

**结论**：**当前经"自然语言 → reason → plan"能 dispatch 的 tool_name 只有 `search_resumes / read_jd`**：
- `create_match_score` 靠 `agent.py:149` REST 端点硬编码 plan 绕开 LLM
- `candidate-merge` / `candidate-profile` / `jd-candidate-matching` 既不在 plan examples 也不在 REST 硬编码里

**影响的 Skill**：
- `jd-candidate-matching`（PR-2 前 Stage 4 交付，与 REST 硬编码 `create_match_score` 有映射但未打通）
- `candidate-merge`（PR-15 交付，仅孤立 Skill）
- `candidate-profile`（PR-16 交付，同为孤立 Skill）

**本 PR 暂行**：PR-16 = Skill 三件套 + 单测（与 PR-15 对称，孤立 Skill 交付），**显式声明本 PR 不打通端到端路由**

**Stage 5.1 收敛方向**（**必须与追债项 10 同 PR 收敛**）：
1. `orchestrator_reason/prompt.md` 补全意图值域（`match / merge_candidates / profile_candidate / generate_jd / general_qa / unknown`）
2. `orchestrator_plan/prompt.md` 或 `run_plan` 动态注入 `registry.list_dispatchable()` 的 `(tool_name, description, task_type)` 三元组清单（让 plan LLM 知道有哪些 skill 可用）
3. 引入追债项 10 的 `task_type → tool_name` 映射表（消除 LLM 翻译负担）
4. 至少 1 个端到端集成测试：模拟 "帮我看下 candidate_1 的画像" 用户消息 → 端到端跑通 chat → reason (task_type=profile_candidate) → plan (tool_name=candidate-profile) → dispatch → Skill → RESULT

**风险等级**：**中高**。此债务不修，Stage 5 后半段（PR-17/18）前端交付的"自然语言对话"对绝大多数 candidate-* skill 都是**空转**；仅 search_resumes / read_jd 能被自然语言触发，其他必须靠 REST 硬编码 plan 或前端手工拼装 plan 兜底。

**Stage 5.1 优先级建议**：**紧接 PR-16 之后立即启动**（PR-17 前端起手前也可，避免前端做出无法路由的 UX）。

---

## 二十、§二十 · 契约裁定收官声明（§十九 收官原则）

**本 PR 交付面已在 §二 硬边界内穷尽表述**：三件套 + 单测 + engine 数据型出口 + 追债项 10/11 canonical 登记，**无隐藏工作**。

**执行体承诺**（起手前默读）：
- 我不动 reason / plan skill 任何文件（追债项 11 主体）
- 我不动 `tasks.task_type` 相关命名代码（Q1 方向 B）
- 我不动 TASKS-STAGE5.md（Q9）
- 我不加落库副作用（Q6）
- 遇到 §十三 任一条件立即停下汇报
- STEP6 §五 必列 4 条声明（19.1-19.4）

**指挥官承诺**：Stage 5.1 启动路由修复 PR 时，追债项 10 与 11 必须同 PR 收敛（不许"只补 prompt 不改命名"或"只改命名不动 prompt"）。

---

**指挥官 FF-merge 后本 DECISION 归档为 canonical 契约。执行体开工前必读整份文档，签字后可 checkout 新分支。**
