# PR-25 · KICKOFF-DECISION

> 关联：MVP-VERIFY §4.1 复跑发现 · HANDOFF §9.3.17 · commit anchor `5a3450c`
> QUESTIONS：**已省**（指挥官授权 · Bug A 面小 · 单议题「三方案选型」）
> 类型：**代码 PR** · 分支 `feat/pr-25-fix-get-task-schema-mismatch` · red-test → FF-merge
> Baseline：pytest 137 passed / 2 skipped · ruff 0 全仓 · frontend build ✓ · migration head `b6c7d8e9f0a1`
> 起始 master HEAD：`5a3450c`

---

## §一 · 背景（不复述 §4.1 报告 · 只给三点确认事实）

1. **REST 契约漂移**：`GET /api/v1/agent/tasks/{task_id}` 对**任何**已存 plan 的任务必 500。原因是 `TaskStatus(plan=task.plan)` 的 Pydantic 校验失败——`task.plan` 是 orchestrator 存的 raw dict，schema `Plan` 要求 4 个字段它都不提供：
   - `Plan.task_id`（必填）—— stored plan 缺
   - `PlanStep.description`（必填）—— skip plan 缺（R-P-R plan 有）
   - `PlanStep.params`（默认 `{}`）—— stored 用 `tool_input`
   - `PlanStep.expected_output`（必填）—— stored 缺

2. **两处生产 plan**：
   - `engine.py:132 _build_skip_plan` → `/skip-to-score` 存的 shape
   - `engine.py:410 final_steps = reflect_plan_out.get("steps", plan_out.get("steps", []))` → R-P-R 存的 shape（来自 `orchestrator_plan` skill LLM 输出）
   - **两处都不符 REST Plan schema**

3. **消费侧**：
   - 后端：`agent.py:289 get_task` · `agent.py:129 chat_start` · `agent.py:155 skip_to_score` · `agent.py:163` 均返回 `TaskStatus(plan=...)`
   - 前端：MessageTimeline / PlanCard 读 `step.description` + `step.tool_name`，**不读 params / expected_output / plan.task_id**（PR-19 交付时无 task_id 已工作）
   - **前端不阻塞 · 只是后端 API 500 掉了**

## §二 · 三方案选型 · 裁定 **方案 C**

| 方案 | 内容 | 优 | 缺 |
|------|------|-----|-----|
| A · 改 schema | 让 `PlanStep` 接受 `tool_input` alias · `task_id`/`description`/`expected_output` 变 optional | 改动最小 | REST 契约永久松绑 · 前端未来若要读 params 会踩坑 · 治标 |
| B · 改 orchestrator 存储 | `_build_skip_plan` 补 4 字段 · `run_reason_reflect` 存前给 plan 补 4 字段（orchestrator_plan LLM 输出保留 tool_input 但转 params 后再存）| 治本 · 存储与 REST 契约完全对齐 | 触及 orchestrator 3 处（skip / R-P-R / DB task.plan 字段语义）· 影响面大 · 已存的旧任务 DB 数据仍 500 |
| **C · adapter**（我推荐 · 已裁）| 新增 `_stored_plan_to_rest_plan(task_id, stored_plan)` 转换函数 · `get_task` / `chat_start` / `skip_to_score` 3 处调用点全部经过 adapter · orchestrator 存储 & REST schema 各自不动 | REST 契约保持 · orchestrator 存储保持 · 单点转换可测 · 旧任务数据也能被读 | +1 转换函数 · 需明确"存储 dict shape ↔ REST Plan shape"两态并存 |

**裁定 C · 理由**：
- MVP 阶段"契约稳定 > 存储漂亮"·  改 schema/存储都会牵一发动全身 · adapter 是最小 blast radius
- 单点函数好测（unit + integration + 已存 DB 数据回读三层）
- 未来若要治本（B）· 只需删 adapter · 不用回退存储契约

## §三 · 落地细节

### §三.1 · 新增 adapter 函数

**位置**：`backend/app/api/v1/agent.py`（同文件顶部 helper 区 · 或就地写在 `get_task` 前）

**签名与实现骨架**：
```python
def _stored_plan_to_rest_plan(task_id: str, stored: Any) -> Plan | None:
    """Adapt an orchestrator-stored raw plan dict to the REST Plan schema.

    Orchestrator stores plans as {"steps": [{"step_id", "tool_name",
    "tool_input", "description"?}, ...]} (see engine._build_skip_plan and
    orchestrator_plan skill output). The REST Plan schema requires
    task_id + PlanStep{step_id, description, tool_name, params,
    expected_output}. This function bridges the two without mutating
    either side.

    Returns None if stored is falsy (task with no plan yet).
    """
    if not stored:
        return None
    raw_steps = stored.get("steps", []) if isinstance(stored, dict) else []
    steps: list[PlanStep] = []
    for i, s in enumerate(raw_steps):
        steps.append(PlanStep(
            step_id=s.get("step_id", f"step_{i}"),
            description=s.get("description", ""),   # skip plan lacks it → ""
            tool_name=s.get("tool_name", ""),
            params=s.get("params") or s.get("tool_input") or {},
            expected_output=s.get("expected_output", ""),
            optional=bool(s.get("optional", False)),
            dependencies=list(s.get("dependencies") or []),
            estimated_duration_seconds=s.get("estimated_duration_seconds"),
        ))
    return Plan(
        task_id=stored.get("task_id", task_id),   # stored may or may not carry it
        steps=steps,
        reasoning=stored.get("reasoning"),
    )
```

### §三.2 · 三处调用点

1. `agent.py:129` `chat_start` 返回 `AgentChatResponse(initial_plan=...)`：
   ```python
   initial_plan=_stored_plan_to_rest_plan(task.task_id, task.plan)
   ```
2. `agent.py:163` `skip_to_score` 返回 `TaskStatus(plan=...)`：
   ```python
   plan=_stored_plan_to_rest_plan(task.task_id, plan)  # `plan` is the just-built _build_skip_plan dict
   ```
3. `agent.py:299` `get_task` 返回 `TaskStatus(plan=...)`：
   ```python
   plan=_stored_plan_to_rest_plan(task.task_id, task.plan)
   ```

**⚠️ 不改**：orchestrator engine 的 `_build_skip_plan` / `final_steps` / DB `task.plan` 存储 shape · 均保持原样。

### §三.3 · 测试面（TDD strict · 3 测试用例）

**新增文件**：`backend/tests/test_stage5_pr25_get_task_plan_schema.py`

- **TC-PR25-1 · `test_stored_plan_to_rest_plan_maps_all_fields`**（unit）：
  构造 skip-shape stored dict（缺 description/params/expected_output/task_id）· 调 adapter · 断言返回 Plan 校验通过 · description=""· params=tool_input · task_id=传入值。

- **TC-PR25-2 · `test_get_task_returns_200_with_stored_plan`**（integration · fakeredis + in-memory DB）：
  先创建一条 Task with `plan={"steps":[{"step_id":"s1","tool_name":"match_score","tool_input":{"jd_id":"j1","resume_id":"r1"}}]}` · GET `/api/v1/agent/tasks/{id}` → 200 · response.plan.task_id == task.task_id · response.plan.steps[0].params == {"jd_id":"j1","resume_id":"r1"}。

- **TC-PR25-3 · `test_get_task_with_no_plan_returns_200`**（integration）：
  Task with `plan=None` → GET 200 · response.plan is None。

**回归覆盖**：跑 `tests/test_stage5_s5_08_agent_api*.py`（如存在）· `tests/test_agent_api.py` · 确保 chat/skip-to-score 端点仍绿。

### §三.4 · Commit split（3 commit · TDD strict）

1. `test(pr-25): red-test skeleton for TC-PR25-1..3 (all failing)` —— 3 测试文件骨架
2. `fix(agent-api): adapter stored plan dict -> REST Plan schema (Bug A)` —— adapter + 3 处调用点
3. `test(pr-25): green tests TC-PR25-1..3 pass` —— 测试转绿

## §四 · 验收（三门 + PR-25 专项）

- pytest 全量：期望 **140 passed / 2 skipped**（131 baseline + PR-24 6 + PR-25 3）
- ruff 全仓：0
- frontend build：不触前端 · 不跑
- **专项**：起后端 · `curl GET /api/v1/agent/tasks/task_c7e0373da5e6`（MVP-VERIFY §附2 落库的 skip-to-score 任务 · 若 dev DB 已 TRUNCATE 则重跑一次 skip-to-score）→ 200

## §五 · 求助边界（PR-25 增补）

**继承**：AGENTS.md · CLAUDE.md 通用 stop-and-ask + PR-24 §六 3 条。

**PR-25 增**：

1. **adapter 转换后仍 500** → 说明 stored plan 有 §三.1 未覆盖的 shape 变体（如 nested dict / null 字段）· 停 · 报现象 · 不擅自加 try/except 遮盖。
2. **回归发现 chat_start / skip_to_score 老单测断言 `initial_plan.steps[0].tool_input`（旧字段名）失败** → 说明前端或老测试预期"透传"存储 shape · 停 · 报回决定是修测试还是加 alias。
3. **`_build_skip_plan` 或 orchestrator_plan skill 输出 shape 与 §三.1 描述不一致** → 停 · 不擅改 orchestrator 侧代码（本 PR scope 仅 REST 层 adapter）· 报现象等指示。

## §六 · 通过判据 checklist

- [ ] pytest 全量 140 passed / 2 skipped
- [ ] ruff 0 errors on `app/api/v1/agent.py` + `tests/test_stage5_pr25_get_task_plan_schema.py`
- [ ] `curl GET /api/v1/agent/tasks/<existing-task-with-plan>` → 200 · JSON.plan.task_id 非空 · JSON.plan.steps[0].params 有值
- [ ] STEP6 报告 `PR25-STEP6-REPORT.md` 写完 · 附三门 output
- [ ] HANDOFF §9.3.17 状态从「登记不修」改为「CLOSED · PR-25 anchor `<commit>`」
- [ ] 分支 push · FF-merge master · 远程分支删除

## §七 · 执行流水（时间预估）

```
Step 0 · KICKOFF-DECISION（本 · docs-only 直落 master）· ~5 min
Step 1 · 起分支 + red-test 骨架（3 failing）· ~15 min
Step 2 · adapter 实现 + 3 调用点接入 · ~10 min
Step 3 · 测试转绿 · ~10 min
Step 4 · 三门验收 + curl 专项 · ~10 min
Step 5 · STEP6 报告 + HANDOFF §9.3.17 更新 + push + FF-merge · ~10 min
──────────────────────────────
乐观：60 min · 悲观（边界 1 或 2 触发）：90–120 min
```

---

**执行开跑触发条件**：本 DECISION commit 落 master 后 · 新 session 执行体拉 `feat/pr-25-fix-get-task-schema-mismatch` 分支 · 按 §七 Step 1 起。
