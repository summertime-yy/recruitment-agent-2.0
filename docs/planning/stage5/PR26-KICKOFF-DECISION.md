# PR-26 · KICKOFF-DECISION

> 关联：`PR26-KICKOFF-QUESTIONS.md`（commit `bb20a01`）· MVP-VERIFY §4.1 Bug B · HANDOFF §9.3.20（本 PR 完成后登记）
> 起始 master HEAD：`bb20a01`（PR-26 QUESTIONS 落 master 后）
> 上一轮验收 baseline：pytest **140 passed / 2 skipped** · ruff 0 全仓 · frontend build ✓ · migration head `b6c7d8e9f0a1`
> 类型：**代码 PR**（feat 分支 · red-test · commit split · FF-merge）
> 分支：`feat/pr-26-hydrate-candidate-profile-inputs`
> QUESTIONS 应答（指挥官 · 2026-07-30）：**Q1–Q7 全部采纳我的建议 A**（Q5 认可 5 TC · Q7 认可 4 边界）

---

## §一 · 背景（不复述 QUESTIONS · 只给三点确认事实）

1. **`candidate-profile.input_schema.required = ["parsed_content", "existing_tags"]`**（`backend/app/agent/skills/candidate_profile/v1_0_0/skill.yaml:23-25`）；数据在 `resumes.parsed_content`（JSON）和 `resumes.tags`（JSONB）列。
2. **LLM plan 手上没有 parsed_content**（context 只给 candidate_id）· 若强让 LLM 拷贝会 payload 爆炸 + 数据冗余。
3. **`ToolRouter.dispatch()` 目前只做 jsonschema + 路由**（`tool_router.py:147-166`）· 没有从 DB 补齐字段的机制。**这就是 §4.1 ACT 阶段必挂的根因**。
4. **兄弟坑**：`candidate-merge` schema 允许 `resumes: [{resume_id}]` 通过（其他字段全 optional，`candidate_merge/v1_0_0/skill.yaml:38`）· skill 会拿到近乎空数据幻觉输出 —— **§4.2 会重演一次**。PR-26 顺路补。

---

## §二 · 方案裁定（QUESTIONS §Q1..§Q4 一次性锁定）

| 议题 | 裁定 | 一句话理由 |
|------|------|------------|
| Q1 修法 | **A · engine 中间件 hydration** | Skill 保持纯函数 · 单一注入点可测 · 前端 / plan LLM 都不用改 |
| Q2 触发规则 | **A · 静态注册表 `HYDRATION_RULES`** | 显式 · 可 grep · 与 `_ARTIFACT_TYPE_MAP` 同风格 |
| Q3 缺失语义 | **A · 硬失败抛 `ToolParamError`** | 用户直接看到"简历未解析" · 沿 dispatch 现有 except 链路 |
| Q4 candidate-merge | **A · 顺路补** | 一次修完两个数据型 skill · §4.2 不再重演 |

---

## §三 · 落地细节

### §三.1 · 新增 hydration 模块

**位置**：新建 `backend/app/agent/orchestrator/hydration.py`（与 `act.py` / `tool_router.py` 同级 · 单一职责）

**签名与骨架**：

```python
"""Hydration middleware · PR-26.

在 ToolRouter.dispatch 之前，为数据型 skill 从 DB 补齐 tool_input 缺失字段。
Skill 保持纯函数 · 单点注入 · 显式静态注册表。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select

from app.agent.orchestrator.tool_router import ToolParamError
from app.models.resume import Resume

HydrationFn = Callable[[dict[str, Any], Any], Awaitable[dict[str, Any]]]


async def _hydrate_candidate_profile(tool_input: dict[str, Any], db: Any) -> dict[str, Any]:
    """从 resumes 表补 parsed_content + existing_tags 到 candidate-profile 的 tool_input。

    - 键：``candidate_id``（来自 plan LLM 的 tool_input）
    - 未提供 candidate_id → ToolParamError
    - resume 不存在 → ToolParamError
    - parsed_content 为 None（parse_status != PARSED）→ ToolParamError
    """
    cid = tool_input.get("candidate_id") or tool_input.get("resume_id")
    if not cid:
        raise ToolParamError("candidate-profile requires 'candidate_id' in tool_input")
    r = await db.execute(select(Resume).where(Resume.resume_id == cid))
    row = r.scalars().first()
    if row is None:
        raise ToolParamError(f"candidate resume not found: {cid}")
    if row.parsed_content is None:
        raise ToolParamError(f"candidate resume not parsed: {cid}")
    return {
        **tool_input,
        "parsed_content": row.parsed_content,
        "existing_tags": list(row.tags or []),
    }


async def _hydrate_candidate_merge(tool_input: dict[str, Any], db: Any) -> dict[str, Any]:
    """为 candidate-merge 的 resumes 列表每个 item 从 resumes 表补齐字段。

    - 只补 item 上没有的字段（不覆盖 LLM 显式给出的）
    - 每个 item 必须有 resume_id；任一 resume 不存在 → ToolParamError
    - parsed_content 为 None 允许（candidate-merge 对空 parsed_content 有兜底）
    """
    items = tool_input.get("resumes") or []
    if not items:
        raise ToolParamError("candidate-merge requires non-empty 'resumes' in tool_input")
    hydrated: list[dict[str, Any]] = []
    for item in items:
        rid = item.get("resume_id")
        if not rid:
            raise ToolParamError("candidate-merge resume item missing 'resume_id'")
        r = await db.execute(select(Resume).where(Resume.resume_id == rid))
        row = r.scalars().first()
        if row is None:
            raise ToolParamError(f"candidate resume not found: {rid}")
        hydrated.append({
            "resume_id": rid,
            "candidate_name": item.get("candidate_name") or row.candidate_name,
            "parsed_content": item.get("parsed_content") or row.parsed_content or {},
            "tags": item.get("tags") or list(row.tags or []),
            "duplicate_of_resume_id": item.get("duplicate_of_resume_id") or row.duplicate_of_resume_id,
        })
    return {**tool_input, "resumes": hydrated}


HYDRATION_RULES: dict[str, HydrationFn] = {
    "candidate-profile": _hydrate_candidate_profile,
    "candidate-merge": _hydrate_candidate_merge,
}


async def hydrate_tool_input(tool_name: str, tool_input: dict[str, Any], db: Any) -> dict[str, Any]:
    """按 HYDRATION_RULES 查找 hydrate fn 并调用；未登记的 tool_name 原样返回。"""
    fn = HYDRATION_RULES.get(tool_name)
    if fn is None:
        return tool_input
    if db is None:
        raise ToolParamError(f"hydration for '{tool_name}' requires a db session")
    return await fn(tool_input, db)
```

### §三.2 · 接入 `ToolRouter.dispatch`

**位置**：`backend/app/agent/orchestrator/tool_router.py:147`（`dispatch` 方法体首行）

**改动**（伪 diff）：
```python
async def dispatch(self, tool_name, tool_input=None, db=None):
    tool_input = tool_input or {}
    # PR-26: hydration middleware — 数据型 skill 从 DB 补齐 tool_input
    from app.agent.orchestrator.hydration import hydrate_tool_input
    tool_input = await hydrate_tool_input(tool_name, tool_input, db)
    # 1. 内置工具
    if tool_name in BUILTIN_TOOLS:
        return await self._execute_builtin(tool_name, tool_input, db)
    ...
```

**⚠️ 关键**：
- import 就地写在函数体内（避免顶层循环 import 风险）；
- hydration 抛的 `ToolParamError` 沿现有 `dispatch → run_act try/except` 链路走 required-step-fail 分支 → 发 SSE `ERROR` 事件（`act.py:146-153`）· 无需额外错误处理层。
- **不改** `run_act` 的签名与行为；**不改** REST schema；**不改** skill.yaml 的 `input_schema.required`。

### §三.3 · 测试面（TDD strict · 5 TC · QUESTIONS §Q5 逐字采纳）

**新增文件**：`backend/tests/test_stage5_pr26_hydration.py`

- **TC-PR26-1 · `test_hydrate_candidate_profile_maps_parsed_content_and_tags`**（unit）：
  预置一条 Resume（`parsed_content={"skills":["Python"]}, tags=["高潜"]`），调 `hydrate_tool_input("candidate-profile", {"candidate_id": "res_x"}, db)`，断言返回 dict 含 `parsed_content == {"skills":["Python"]}` 且 `existing_tags == ["高潜"]`。

- **TC-PR26-2 · `test_hydrate_candidate_profile_missing_resume_raises`**（unit）：
  DB 空，调 `hydrate_tool_input("candidate-profile", {"candidate_id": "no_such"}, db)`，断言抛 `ToolParamError`。

- **TC-PR26-3 · `test_run_act_candidate_profile_end_to_end`**（integration）：
  预置一条 Resume + mock `SkillRegistry` 使 `candidate-profile` skill 返回 `{profile_tags, summary, strengths, risks}` 静态输出（不真调 LLM）；构造 plan `[{tool_name: "candidate-profile", tool_input: {candidate_id: "res_x"}}]`；跑 `run_act` · 断言 `StepResult.success=True` 且 skill 收到的入参 `parsed_content` 非空、`existing_tags == ["高潜"]`。

- **TC-PR26-4 · `test_hydrate_candidate_merge_fills_resume_fields`**（integration）：
  预置 2 条 Resume（都有 parsed_content）；调 `hydrate_tool_input("candidate-merge", {"resumes":[{"resume_id":"a"},{"resume_id":"b"}]}, db)`；断言返回 `resumes[0].parsed_content` 非空、`resumes[1].parsed_content` 非空、`resumes[0].candidate_name` 等于 DB 值。

- **TC-PR26-5 · `test_run_act_candidate_profile_missing_resume_emits_error_event`**（integration）：
  DB 无该 candidate_id · 构造 plan 后跑 `run_act` · 捕获 emit 出的 SSEEvent 列表 · 断言含 `type == SSEEventType.ERROR` 事件 · 断言最终 `StepResult.success = False` 且 error_message 含 `"not found"`。

**期望终值**：`pytest -q` → **145 passed / 2 skipped**（140 baseline + 5 PR-26）· ruff 全仓 0。

### §三.4 · Commit split（TDD strict · QUESTIONS §Q6 采纳）

1. `test(pr-26): red-test skeleton for TC-PR26-1..5 (all failing)` —— 测试文件骨架，5 TC 全 red
2. `feat(orchestrator): add hydration middleware for candidate-profile and candidate-merge` —— hydration.py + tool_router.py 接入点
3. `test(pr-26): green tests TC-PR26-1..5 pass` —— 测试转绿（若 red 骨架已能 pass，此 commit 只做小微调整）
4. `docs(stage5): PR-26 STEP6 report + HANDOFF §9.3.20 CLOSED` —— 报告 + HANDOFF 更新（如需拆开）

---

## §四 · 验收（三门 + PR-26 专项）

- **pytest 全量**：期望 **145 passed / 2 skipped**（140 baseline + PR-26 5 TC）
- **ruff 全仓**：0 error（改动文件：`hydration.py` / `tool_router.py` / 新测试文件）
- **frontend build**：不触前端 · 不跑
- **专项 curl（可选，若 dev DB 有 seed）**：起后端 · 构造一条 parsed_content 齐备的 Resume · 通过 `POST /agent/chat`（自然语言 "给候选人 res_xxx 出画像"）触发 · 观察 SSE 流事件序列含 `tool_call(candidate-profile) → result` 且 result data 里 `profile_tags/summary` 非空

---

## §五 · 求助边界（继承 AGENTS.md/CLAUDE.md 通用 + PR-26 增补 · QUESTIONS §Q7 采纳 4 条）

**继承（不复述）**：AGENTS.md + CLAUDE.md 通用 stop-and-ask + PR-25 §五。

**PR-26 增补**（触及必停）：

1. **hydration 接入 `dispatch` 后 PR-12 老 stub 类测试集体挂**：说明 stub-pattern 屏蔽了真实 dispatch 流程 · 停 · 报现象 · **不擅自**在 hydration 加 `if TESTING: skip` 类分岔。
2. **hydration 命中 candidate-profile 但 seed / factory 都会填 `parsed_content`（永不 None）**：即 TC-PR26-2 用真实 factory 造不出该分支 · 停 · 报回是否软失败兜底 · 不擅自把 factory 改成允许 None。
3. **candidate-merge 的 resume 字段与 hydration 注入字段有名字冲突**（例如 `tags` 语义分歧）：停 · **不擅自** rename · 报回。
4. **修完 PR-26 后 §4.2 merge 路径新暴露 `minItems: 2` 校验挂**（例如只 seed 了 1 条 resume）：属新 bug · 停 · 登记 §9.3 不擅自扩 scope。

---

## §六 · 通过判据 checklist

- [ ] pytest 全量 **145 passed / 2 skipped**
- [ ] ruff 全仓 0 errors（改动文件：`hydration.py` + `tool_router.py` + 新测试文件）
- [ ] TC-PR26-1..5 全绿（unit×2 + integration×3）
- [ ] `_stored_plan_to_rest_plan`、`_ARTIFACT_TYPE_MAP`、REST schema 均**未改**（scope 严限 orchestrator 层）
- [ ] STEP6 报告 `PR26-STEP6-REPORT.md` 写完 · 附三门 output
- [ ] HANDOFF 新增 §9.3.20（Bug B CLOSED · anchor 填最终测试 commit）
- [ ] 分支 push · FF-merge master · 远程分支删除

**一票否决项**：无。1–5 全部满足即通过。

---

## §七 · 执行流水（时间预估）

```
Step 0 · KICKOFF-DECISION（本 · docs-only 直落 master）· ~5 min
Step 1 · 起分支 + red-test 骨架（5 failing）· ~20 min
Step 2 · hydration.py 实现 + tool_router.dispatch 接入 · ~15 min
Step 3 · 测试转绿（TC-PR26-1..5）· ~15 min
Step 4 · 三门验收 + curl 专项（可选）· ~10 min
Step 5 · STEP6 报告 + HANDOFF §9.3.20 + push + FF-merge · ~15 min
──────────────────────────────
乐观：80 min · 悲观（边界 1 触发 · PR-12 stub 冲突）：120–150 min
```

---

## §八 · 给执行体的一句话指令（复制粘贴级）

> **PR-26 执行体接活**：拉 `feat/pr-26-hydrate-candidate-profile-inputs` 分支（起自 master HEAD `bb20a01`）· 严格按 `docs/planning/stage5/PR26-KICKOFF-DECISION.md` §三 落地 —— 新建 `backend/app/agent/orchestrator/hydration.py`（含 `HYDRATION_RULES` 静态注册表 + `_hydrate_candidate_profile` / `_hydrate_candidate_merge` 两个 async fn + `hydrate_tool_input` 单点入口 · Q3 硬失败抛 `ToolParamError`）· 在 `tool_router.py::ToolRouter.dispatch` 首行接入 `tool_input = await hydrate_tool_input(...)` · 新增 `backend/tests/test_stage5_pr26_hydration.py` 承载 TC-PR26-1..5（§三.3 5 个 TC 逐字对齐）· 按 §三.4 3 code + 1 docs commit split 提交 · 三门验收目标 **pytest 145/2 · ruff 0 · frontend 不触** · §五 4 条求助边界触及必停不擅走 · 完工后写 `PR26-STEP6-REPORT.md` + HANDOFF §9.3.20 CLOSED + FF-merge master + 删远程分支 · **禁止改** REST schema / `_ARTIFACT_TYPE_MAP` / `_stored_plan_to_rest_plan` / skill.yaml `input_schema.required`。
