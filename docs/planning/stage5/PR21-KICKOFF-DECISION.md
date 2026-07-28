# PR-21 KICKOFF · DECISION（执行体 Contract）

> 来源：PR21-KICKOFF-QUESTIONS.md（executor）+ PR21-KICKOFF-REVISIONS.md（commander）
> base：master `c3bdc09`
> 状态：**contract · 待 commander 批准 · 批准后起 `feat/pr-21-s51-match-score-tool-name-fix`**
> 决策结论：**选 A1** —— 注册 `match_score` 到 `BUILTIN_TOOLS`，委托 `MatchService.match_one`（与 `POST /api/v1/match` 同源）

---

## §一 交付面 · 双主目标

| 目标 | 类型 | 内容 | 来源 |
|------|------|------|------|
| 主目标 1 | 清洁性（追债 12） | `create_match_score → match_score` 全链路重命名，使 tool_name 合法（dispatch 可解析，不触发 `UnknownToolError`） | HANDOFF §9.3.12 |
| 主目标 2 | 功能修复（F1） | skip-to-score 恢复真产出 `match_scores` 行的能力（经 A1 builtin 真正落库，而非静默吞异常） | REVISIONS R1 / F1 |

**验收判据（双目标必须同时达成）**：
- 主目标 1：`ToolRouter().dispatch("match_score", {jd_id, resume_id})` 不再抛 `UnknownToolError`。
- 主目标 2：`POST /api/v1/agent/skip-to-score` 后，`match_scores` 表出现对应 `(jd_id, resume_id)` 新行；`executions` 表 `tool_name == "match_score"`、`status == "COMPLETED"`。

---

## §二 契约 · Q1/Q3/Q4/Q6/Q7 采纳定案

| 项 | 定案 |
|----|------|
| Q1 硬编码点 | 改 3 处：`engine.py:124`（`_ARTIFACT_TYPE_MAP` key）、`engine.py:507-516`（engine plan）、`agent.py:149-158`（端点 plan）；排除 `match.py:23`（handler 函数名） |
| Q3 Artifact map | key `create_match_score → match_score`；value `match_score` 不变；前端 `ArtifactType` union 已含 `match_score`，**零前端改动** |
| Q4.1 plan 单点 | 端点删 plan 构造，engine 单一构造 plan（抽 `_build_skip_plan(jd_id, candidate_ids)` 共用） |
| Q4.2 fixture | `test_stage5_s5_09_engine.py:56/61/78`、`test_stage5_pr13_execute.py:56/71` 的 fake plan `tool_name` 改 `match_score` |
| Q6 UI | 新 tool_name = `match_score`，UI 显示更简洁、与 result type 对齐，**零 UI 改动** |
| Q7 BUILTIN_TOOLS | **破例允许改** `tool_router.py:54`，注册 `match_score` 条目 + `_execute_builtin` 分支 |

---

## §3.1 BUILTIN_TOOLS["match_score"] 结构（tool_router.py:54）

```python
# 在 BUILTIN_TOOLS dict 内新增：
"match_score": {
    "description": "对单条 (jd_id, resume_id) 跑确定性匹配打分，复用 MatchService.match_one（与 POST /api/v1/match 同源）",
    "input_schema": {
        "type": "object",
        "properties": {
            "jd_id": {
                "type": "string",
                "pattern": "^jd_[a-zA-Z0-9]+$",
                "description": "JD 唯一标识（jd_ 前缀）",
            },
            "resume_id": {
                "type": "string",
                "pattern": "^resume_[a-zA-Z0-9]+$",
                "description": "简历唯一标识（resume_ 前缀）",
            },
            "force": {"type": "boolean", "default": False, "description": "为 True 时忽略幂等缓存强制重算"},
        },
        "required": ["jd_id", "resume_id"],
    },
},
```

> 自检（REVISIONS 求助边界 #2）：`input_schema`/`description` 字段名与现有 `search_resumes`/`read_jd` 结构一致（tool_router.py:54-90 已核实），无需改结构。
> 需 `import`：`from app.services.match import MatchService`（在 tool_router.py 顶部与 `JDService`/`ResumeService` 并列导入）。

---

## §3.2 _execute_builtin 分支代码骨架（tool_router.py:152-186）

在 `_execute_builtin` 内、`if tool_name == "read_jd":` 之后、`raise UnknownToolError(tool_name)` 之前新增：

```python
if tool_name == "match_score":
    service = MatchService(db)
    score = await service.match_one(
        tool_input["jd_id"],
        tool_input["resume_id"],
        force=bool(tool_input.get("force", False)),
    )
    return SkillResult(
        success=True,
        output={
            "match_score_id": score.score_id,      # ← _build_artifacts 取 ref_id 用（engine.py:143）
            "jd_id": score.jd_id,
            "resume_id": score.resume_id,
            "score": score.overall_score,          # MatchScore.overall_score（0-100）
            "dimension_scores": score.dimension_scores,  # JSON，含 reasoning
            "matching_skill_id": score.matching_skill_id,
            "status": score.status,
        },
    )
```

> 审计（R2）：`_execute_builtin` 内**不加** `SkillExecutionLog`；`MatchService.match_one` 内部（match.py:224-237）已写 `SkillExecutionLog`，委托即继承，与现有 builtin "无埋点" 风格一致。
> 输出 schema（R3 / 求助边界 #4）：必须含 `match_score_id`（engine.py:143 `output.get("match_score_id") or output.get("id")` 取 ref_id），确保 `ResultArtifact.type=="match_score"` 分派链路走通。

---

## §3.3 engine.run_skip_to_score 内 plan 单点构造（engine.py:491-528）

抽模块级 helper，engine 与端点共用，消除双份硬编码：

```python
def _build_skip_plan(jd_id: str, candidate_ids: list[str]) -> dict[str, Any]:
    """skip-to-score 专用 plan（单一构造点）。tool_name 已合法化为 match_score（A1）。"""
    return {
        "steps": [
            {
                "step_id": f"step_score_{i}",
                "tool_name": "match_score",
                "tool_input": {"jd_id": jd_id, "resume_id": cid},
            }
            for i, cid in enumerate(candidate_ids)
        ]
    }
```

`run_skip_to_score` 内部改用 `_build_skip_plan(jd_id, candidate_ids)`（替换原 engine.py:507-516 的内联字面量）。

**§3.5 前置（executor 新发现，必做，否则 F1 仍修不了）**：`run_act`→`router.dispatch` 当前**不传 db**（act.py:108 `router.dispatch(tool_name, tool_input)`），且 engine 不持有 session factory；而 `match_score` builtin 需 `db` 才能跑 `MatchService.match_one`，否则 `_execute_builtin` 抛 `ToolParamError("requires a db session")`。

解决（最小改动）：
1. `run_act(..., db: AsyncSession | None = None)` 新增形参，act.py:108 改为 `router.dispatch(tool_name, tool_input, db=db)`。
2. `engine.run_skip_to_score` / `_background_execute` 增加 `session_factory` 形参（端点把 `async_session_factory` 传入，与 `execution_writer` 同源）。
3. `_background_execute` 内 `async with session_factory() as db:`，把 `db` 透传给 `run_act(plan, ctx=..., emit=..., tool_router=self.tool_router, db=db, ...)`（原调用点 engine.py:564-571）。
4. 另一调用点 `_run_task_body`（engine.py:307）同步补 `db=None`（该路径不跑 builtin，传 None 保持现状行为，不扩大 scope）。

> 求助边界 #8：若 db 透传需改动超出上述 2 处（act.py:108 + engine.py:564），或 engine 须新增 session_factory 持有（而非仅透传参数），停下报告，避免 scope creep。

---

## §3.4 agent.py::skip_to_score 端点简化（agent.py:141-183）

删除端点内的 plan 构造（原 149-158），复用 engine 的 `_build_skip_plan` 存 `Task.plan`：

```python
@router.post("/skip-to-score")
async def skip_to_score(
    req: SkipToScoreRequest,
    db: AsyncSession = Depends(get_db),
    engine: OrchestratorEngine = Depends(get_engine),
):
    """跳过 R-P-R 直接评分：INSERT tasks(EXECUTING) + 后台 run_skip_to_score（真 task_id）。"""
    task_id = generate_task_id()
    plan = _build_skip_plan(req.jd_id, req.candidate_ids)   # 单一构造点
    db.add(
        Task(
            task_id=task_id,
            status="EXECUTING",
            task_type="MATCH_SCORE",
            user_message=f"skip-to-score jd={req.jd_id}",
            context={"jd_id": req.jd_id, "candidate_ids": req.candidate_ids},
            plan=plan,
            started_at=utcnow_naive(),
        )
    )
    await db.commit()
    db_updater = await _make_db_updater()
    exec_writer = _make_db_execution_writer(async_session_factory, task_id=task_id)
    resp = await engine.run_skip_to_score(
        req.jd_id,
        req.candidate_ids,
        task_id=task_id,
        db_updater=db_updater,
        execution_writer=exec_writer,
        session_factory=async_session_factory,   # §3.5 新增透传
    )
    if resp.get("status_code") == 429:
        _raise_429()
    return {"task_id": task_id, "status": "EXECUTING"}
```

需要 `from app.agent.orchestrator.engine import ... _build_skip_plan`（按现有导入风格补）。

---

## §四 用例表 · TC-S5.2-1 / TC-S5.2-2

| TC | 类型 | 内容 | 防回归目标 |
|----|------|------|-----------|
| TC-S5.2-1 | 单元 | `engine.run_skip_to_score` 构造的 plan 各 step `tool_name == "match_score"`；`ToolRouter().dispatch("match_score", {jd_id, resume_id})` 可解析（不抛 `UnknownToolError`） | 主目标 1（命名合法化） |
| TC-S5.2-2 | 端到端（防 F1） | `POST /api/v1/agent/skip-to-score` 后**不 mock run_act**，真实 dispatch → `_execute_builtin("match_score")` → 断言 `match_scores` 表出现新行（`WHERE jd_id AND resume_id`）+ `executions` 表 `tool_name == "match_score"` + `status == "COMPLETED"` | 主目标 2（F1 修复） |

测试文件：`backend/tests/test_stage5_pr21_match_score_tool.py`（新建）。

**TC-S5.2-2 实现注意（REVISIONS Q5 / 求助边界 #3）**：
- 严禁 `monkeypatch.setattr(act_mod, "run_act", _fake)`——F1 的 root cause 正是屏蔽真实链路。
- 必须让 `run_act` 真跑、`dispatch` 真进 builtin（需 §3.5 的 db 透传到位）。
- 若触发 §9.4 陷阱 12（ASGITransport + create_task hang），降级为单元级组合：直接构造 `ToolRouter(db)` + 调 `_execute_builtin("match_score", ...)` + 断言 `match_scores` 落库（参考 PR-20 单元级 helper 思路），并在 STEP6 注明。

---

## §五 commit 拆分（建议 4-5 commit）

| # | 类型 | 内容 | 对应改动 |
|---|------|------|----------|
| 1 | test（红） | 新增 `test_stage5_pr21_match_score_tool.py`，TC-S5.2-1/2（先红，验证未实现时失败） | §四 |
| 2 | feat | `tool_router.py`：`BUILTIN_TOOLS` 增 `match_score` + `_execute_builtin` 分支 + import `MatchService` | §3.1 / §3.2 |
| 3 | feat | `engine.py`：`_build_skip_plan` 单点 + `run_skip_to_score` 改用；§3.5 db 透传（run_act 形参 + `_background_execute` session_factory） | §3.3 / §3.5 |
| 4 | feat | `agent.py`：端点删 plan 构造、复用 `_build_skip_plan`、传 `session_factory` | §3.4 |
| 5 | refactor/test | `_ARTIFACT_TYPE_MAP` key 改 `match_score`；测试 fixture 同步改名（test_stage5_s5_09_engine.py / test_stage5_pr13_execute.py） | §二 Q1/Q3/Q4.2 |

> commit 数 = 5，未超 REVISIONS 求助边界 #6（≤5）。

---

## §六 三门期望

| 门 | 结果 |
|----|------|
| Test | **131 passed, 1 skipped**（129 基线 + TC-S5.2-1/2；skip 仍为 PR-20 的 TC-S5.1-7） |
| Lint | `ruff check app/agent/orchestrator app/api/v1 app/models` → **All checks passed!** |
| Build | 纯后端 / 无 TS，N/A |

> 注：若 TC-S5.2-2 因陷阱 12 降级为单元级组合，仍计入 passed（不新增 skip）。

---

## §七 求助边界（stop-and-ask）

复用 REVISIONS §三 7 条 + executor 追加 1 条：

1. `MatchService.match_one` 签名与本 DECISION 假设不符（需 db 之外的额外参数，或同步/异步不符）。
2. `BUILTIN_TOOLS` 结构（`input_schema`/`description` 字段名）与现状不符，需重读 `tool_router.py:54` 定结构。
3. TC-S5.2-2 走单元级组合仍 hang（重演陷阱 12）→ 停下，考虑 subprocess httpx。
4. `_build_artifacts` 消费 `match_one` 输出 schema 不匹配（缺 `match_score_id` 等 ref_id 提取失败）。
5. 三门任一未过（≠131 passed / ruff ≠0 / build 失败）。
6. commit 数 > 5。
7. 发现 §9.4 未记的新陷阱。
8. **（executor 追加）** db 透传改动超出 `act.py:108` + `engine.py:564` 两处，或 engine 须新增 session_factory 持有而非参数透传 → 停下报告，防 scope creep。

---

## §八 base hash

`c3bdc09`（origin/master，PR-21 起点；feature 分支从此切出）

---

## §九 交付摘要模板（批准后实现完填写）

```
分支：feat/pr-21-s51-match-score-tool-name-fix
base：c3bdc09
HEAD：<short hash>
三门：
  uv run pytest -q
  ... 131 passed, 1 skipped in X.XXs
  uv run ruff check app/agent/orchestrator app/api/v1 app/models
  All checks passed!
交付面：主目标1（追债12 收敛）+ 主目标2（F1 修复）
```

---

## §十 备注

- **F1 归类调整**：`create_match_score` 静默失效（原 HANDOFF §9.3.12 描述为"未来潜在 bug"）经本 PR 核实为 **live bug**，应从 §9.3.12 移出，建议 HANDOFF 新增 **§9.3.13 独立追债项**（"skip-to-score 经 dispatch 静默零产出"），并由 PR-21 一并收敛修复。DECISION 批准后实现阶段同步更新 HANDOFF。
- 不改 `jd-candidate-matching` skill（保留给未来 LLM 复评独立入口，REVISIONS Q2 依据 4）。
- 不改前端（§二 Q3/Q6 已确认零前端改动）。
- 不改 `BUILTIN_TOOLS` 现有 `search_resumes`/`read_jd` 条目（仅追加 `match_score`）。
