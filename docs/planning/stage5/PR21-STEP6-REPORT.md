# PR-21 STEP6 报告 · create_match_score → match_score 收敛 + F1 修复

> 依据 `docs/planning/stage5/PR21-KICKOFF-DECISION.md`（executor contract，base `c3bdc09`）执行。
> 严格 TDD · 5 commit。参考 PR-20 STEP6 结构。

## §一 概述

| 项 | 值 |
|----|----|
| 分支 | `feat/pr-21-s51-match-score-tool-name-fix` |
| base（DECISION §八） | `c3bdc09`（实际从 master `96f6a3c` 拉起，含 KICKOFF 三件套 docs commit） |
| HEAD（短 hash） | `b73ba47` |
| commit 数 | 5（≤ 5，DECISION §七 触发条件 #6 未触发） |
| 文档状态 | 起点 `96f6a3c`（QUESTIONS `34727fe` / REVISIONS `b91ca28` / DECISION `96f6a3c`）已落 master；实现 commit 落本分支 |

commit 链：
```
b73ba47 refactor/test(stage5): PR-21 #5 artifact map key + fixtures rename to match_score
3370182 feat(stage5):     PR-21 #4 simplify skip_to_score endpoint (reuse _build_skip_plan + session_factory)
39d9895 feat(stage5):     PR-21 #3 engine plan rename + db passthrough via run_act
a6f8446 feat(stage5):     PR-21 #2 register match_score builtin (tool_router)
d3a5780 test(stage5):     PR-21 #1 red - TC-S5.2-1/2 xfail skeleton (match_score builtin)
```

## §二 三门实况（未自报"通过"，贴命令 tail）

### 门 1 · pytest（全量，无 `-k`）

```bash
cd backend
uv run pytest -q
```

tail 5 行（实际输出）：

```
.....................................................................s.. [ 54%]
............................................................             [100%]
131 passed, 1 skipped in 6.24s
```

→ 目标 `131 passed / 1 skipped` 达成（129 既有 + TC-S5.2-1/2 两条新 TC）。

### 门 2 · ruff

```bash
cd backend
uv run ruff check app/agent/orchestrator app/api/v1 app/models
```

tail：

```
All checks passed!
```

### 门 3 · build

N/A（纯后端改动，无 frontend 变更；`npm run build` 不相关）。

## §三 实现细节（5 commit 逐条）

### #1 · `d3a5780` test（红）
- 新建 `backend/tests/test_stage5_pr21_match_score_tool.py`。
- TC-S5.2-1：`match_score` 必须注册进 `BUILTIN_TOOLS` 且 `dispatch` 能解析（缺 db 抛 `ToolParamError` 而非 `UnknownToolError`）。
- TC-S5.2-2：真实 `run_act` + `dispatch("match_score", db=...)` → `MatchService.match_one` 落库 `match_scores` 行（不 mock `run_act`；仅 stub `match_one` 保留"真实落库"副作用，规避 LLM 链路 hang）。
- 两条均以 `@pytest.mark.xfail(strict=True, reason="PR-21 未实现")` 标记。
- 验证：`uv run pytest tests/test_stage5_pr21_match_score_tool.py -q` → `2 xfailed`。

### #2 · `a6f8446` feat（工具路由注册）
- `tool_router.py`：`BUILTIN_TOOLS` 新增 `"match_score"` 条目（jsonschema `input_schema`：`jd_id`/`resume_id` required）。
- `_execute_builtin` 新增 `match_score` 分支：`MatchService(db).match_one(jd_id, resume_id, force=False)`，输出含 `match_score_id`/`jd_id`/`resume_id`/`score`/`dimension_scores`/`status`（供 `_build_artifacts` 取 `ref_id`）。
- 导入 `from app.services.match import MatchService`。
- 剥离 TC-S5.2-1 xfail → 该 TC 通过。验证：`1 passed, 1 xfailed`。

### #3 · `39d9895` feat（引擎 + db 透传）— F1 修复核心
- `act.py`：`run_act` 增 `db: Any = None` 形参；`router.dispatch(tool_name, tool_input, db=db)` 透传 db（DECISION §3.5）。
- `engine.py`：
  - 新增模块级 `_build_skip_plan(jd_id, candidate_ids)` 单点构造器（`tool_name="match_score"`），消除端点与引擎双份硬编码（DECISION Q4.1）。
  - `run_skip_to_score` 改用 `_build_skip_plan` 并增 `session_factory` 形参，透传至 `_background_execute`。
  - `_background_execute` 增 `session_factory` 形参；提供 `session_factory` 时 `async with session_factory() as db:` 开会话并 `run_act(..., db=db)`（db 透传落点）。
- 剥离 TC-S5.2-2 xfail → 该 TC 通过（真实落库）。验证：`2 passed`。
- **求助边界 #8（db 透传超出 act.py:108 + engine.py 两处）**：仅改 `act.py:dispatch` 与 `engine.py:_background_execute` 两处，未波及 `_run_task_body`（engine.py:307 run_execute 路径），符合边界，未触发。

### #4 · `3370182` feat（端点收敛）
- `agent.py::skip_to_score`：删除端点侧内联 plan 构造，改 `plan = _build_skip_plan(req.jd_id, req.candidate_ids)`（单点复用）；`run_skip_to_score(..., session_factory=async_session_factory)` 透传 db 工厂。
- 导入 `_build_skip_plan`。ruff 通过。

### #5 · `b73ba47` refactor/test（收尾一致）
- `engine.py`：`_ARTIFACT_TYPE_MAP` key `create_match_score` → `match_score`（value 保持 `match_score`，前端 `ArtifactType` union 已含，零前端改动）。
- 测试 fixture 同步改名：`test_stage5_s5_09_engine.py:56/61/78`、`test_stage5_pr13_execute.py:56/71` 的 `create_match_score` → `match_score`（contract 文档一致性，Q4.2）。

## §四 契约核对表（DECISION §一双主目标）

| DECISION 契约项 | 达成 | 证据 |
|---|---|---|
| 主目标 1（追债 12 收敛）`create_match_score` → `match_score` 全链路重命名 | ✅ | 代码 grep 无残留 `create_match_score` 作为 tool_name（仅 PR-21 文档字符串描述历史，非代码）；`_ARTIFACT_TYPE_MAP` key、`_build_skip_plan`、`BUILTIN_TOOLS` 均为 `match_score` |
| 主目标 2（F1 修复）skip-to-score 恢复真实产出 match_scores | ✅ | TC-S5.2-2（单元级组合）真实 `run_act`+`dispatch("match_score")` 经 builtin → `MatchService.match_one`，断言 `match_scores` 表 `WHERE jd_id AND resume_id` 出现新行 |
| Q3：`_ARTIFACT_TYPE_MAP` key 改 `match_score`，value 不变；零前端改动 | ✅ | engine.py map；前端 `ArtifactType`/`ResultCard` 分派按 `type:match_score` 不变 |
| Q4.1：plan 收敛到 engine 单点 | ✅ | `_build_skip_plan` 模块级；端点复用 |
| Q6：UI 工具名显示 `match_score` | ✅ | `ToolCallCard`/`MatchScoreArtifact` 原样显示 tool_name，无 UI 改动 |
| Q7：破例动 `BUILTIN_TOOLS` | ✅ | `BUILTIN_TOOLS["match_score"]` 已注册 |
| R2：builtin 审计埋点 | ✅ | `_execute_builtin` 无埋点；`match_score` 委托 `MatchService.match_one`（match.py:224-237 已写 `SkillExecutionLog`），沿袭一致 |
| R3：输出字段可序列化 | ✅ | `_execute_builtin` 输出 dict 仅含标量/JSON 字段（`score_id`/`jd_id`/`resume_id`/`overall_score`/`dimension_scores`/`status`），SSE 安全 |

**match_scores 落库证据**：TC-S5.2-2 在 `db_session` 中先建父表 `jd_tc`/`resume_tc` 行（满足 FK），stub `match_one` 仅保留 `self.db.add(sm); await self.db.commit()` 真实落库副作用，`run_act` 走真实 `dispatch` → builtin → `match_one`，随后 `select(MatchScore).where(jd_id="jd_tc", resume_id="resume_tc")` 断言 `first() is not None` 通过。

## §五 求助边界触发情况（DECISION §七 8 条）

| # | 触发条件 | 是否触发 | 说明 |
|---|---|---|---|
| 1 | `match_one` 签名不符 | 否 | `match_one(self, jd_id, resume_id, *, force=False)` 与假设一致 |
| 2 | `BUILTIN_TOOLS` 结构不符 | 否 | 沿用现有 jsonschema `input_schema` + `description` 结构 |
| 3 | TC-S5.2-2 单元级降级后仍 hang | 否 | 单元级组合（`run_act` 直接驱动，不经 REST/任务 hang）通过 |
| 4 | `_build_artifacts` 消费 output schema 不匹配 | 否 | `output["match_score_id"]` 被 `_build_artifacts` 取 `ref_id`（`engine.py:159`），链路续通 |
| 5 | 三门任一未过 | 否 | pytest 131 passed/1 skipped；ruff 0；build N/A |
| 6 | commit > 5 | 否 | 恰好 5 commit |
| 7 | 发现 §9.4 未记新陷阱 | 否 | 仅复现已知 F1；FK 约束（测试需建父表行）属常规测试 fixtures 范畴，非新陷阱 |
| 8 | db 透传超出 act.py:108 + engine.py 两处 | 否 | 仅改 `act.py:dispatch(db=db)` 与 `engine.py:_background_execute(session_factory)`；`run_execute` 路径（`engine.py:307`）未波及，符合边界 |

## §六 用例表

| 用例 | 类型 | 落点 | 状态 |
|---|---|---|---|
| TC-S5.2-1 | 单元 | `test_stage5_pr21_match_score_tool.py::test_tc_s5_2_1_match_score_registered_and_dispatch_resolves` | ✅ PASS（commit #2 起，原 xfail） |
| TC-S5.2-2 | 单元级组合（防 F1 回归） | `test_stage5_pr21_match_score_tool.py::test_tc_s5_2_2_skip_to_score_persists_match_score` | ✅ PASS（commit #3 起，原 xfail） |

## §七 HANDOFF §9.3.13 新增建议

本 PR 将 F1 从 HANDOFF §9.3.12 移出，建议 commander 合入后于 HANDOFF 新增独立追债项：

> **§9.3.13（PR-21 一并收敛）skip-to-score 静默失效 live-bug（原 §9.3.12 误标"潜在"）**
> - 现象：`run_act` 必走 `router.dispatch(tool_name)`；`create_match_score` 既非 `BUILTIN_TOOLS` 键亦非 skill_id → `UnknownToolError`，且 `run_act` 逐步骤 `except Exception: sr=None`（`act.py:107-111`）吞异常 → 任务状态成功但 0 条 `match_score` 落库。
> - 根因：硬编码 tool_name 非法 + 编排器 `dispatch` 从不传 `db`（F1 真正修复还需 db 透传，见 PR-21 §3.5）。
> - 修复：PR-21 收敛为合法 builtin `match_score`（确定性后端 `MatchService.match_one`，与 `POST /api/v1/match` 同源），并补 db 透传。
> - 回归防护：`test_stage5_pr21_match_score_tool.py::TC-S5.2-2` 断言真实 dispatch 落库（不 mock `run_act`）。

## §八 交付摘要（HEAD / base / 三门 tail）

- HEAD：`b73ba47`
- base：`c3bdc09`（分支自 master `96f6a3c`）
- 三门：
  - pytest：`131 passed, 1 skipped in 6.24s`
  - ruff：`All checks passed!`
  - build：N/A
- 待 commander 复审后 FF-merge；合并后落地 §七 HANDOFF §9.3.13 新增建议。
