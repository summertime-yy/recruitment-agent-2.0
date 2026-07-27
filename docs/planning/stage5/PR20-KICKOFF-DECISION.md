# PR-20 KICKOFF DECISION · Stage 5.1 追债项 7+8 收敛（executions 全生命周期 + current_step 中途写 DB）

> **对象**：执行体（下一 session）· 作为**唯一实施契约**
> **文档角色**：主指挥官（用户）× ark-code-latest 联合裁定书 · Stage 5.1 首个技术债 PR
> **权威依据**：
> - `HANDOFF.md §9.3 追债项 7 + 追债项 8`（本 PR 收敛目标）
> - `docs/planning/stage5/PR14-KICKOFF-DECISION.md §十九 19.1 / 19.2`（追债起源）
> - `docs/planning/stage5/PR14-STEP6-REPORT.md §五 19.1 / 19.2`（PR-14 暂行方案）
> - `docs/api-contract.md §4.5`（cancel 契约要求写 `executions.status='CANCELLED'`）
> - `docs/planning/PLAN-STAGE5.md §5.5 / Q3`（executions 逐步记录粒度）
> - 后端权威事实源：
>   - `backend/app/agent/orchestrator/engine.py` — `_background_execute` L455-540 / `_write_task` L349 / `DbUpdater` type L46
>   - `backend/app/agent/orchestrator/act.py` — `run_act` L61 / `StepResult` L28 / `_safe_emit` L42
>   - `backend/app/api/v1/agent.py` — `_make_db_updater` L57-65 / `cancel_task` L306-335 / `chat/execute` 三处 db_updater 挂载 L93/124/167
>   - `backend/app/models/execution.py`（当前闲置，本 PR 首次落库）
> - `AGENTS.md §Stage 5 Conventions`（后端约定 · fakeredis 测试 / DI 模式）
> **起手 master HEAD (base ref)**：**执行体开工时的 `origin/master` HEAD**（当前为 `2888bbb` HANDOFF 更新，PR-19 build gate 返修 `6b9372a` 已合入 · 不冻结 · 与 PR-14/19 惯例一致）
> **测试基线**（本 PR 目标基线）：
> - **后端**：`120 passed`（PR-14 起未变；本 PR 新增用例后要求 `N_before + N_after`）
> - **前端**：`31 passed / 12 files`（不触碰，免跑但基线不倒退）
> - **Lint**：`ruff check` 0 errors / `npm run lint` 0 errors 8 warnings（预存）
> **目标 N_after**：后端 `120 + 6 = 126 passed`（估计值，可上下浮动 ±2）· 前端保持 31 · Lint 保持 · Build 保持

---

## 〇 · 顶层裁定汇总（执行体必读）

主指挥官三项前置决策（QUESTIONS 轮已确认，本 DECISION 承接）：

| # | 决策 | 落地位置 |
|---|------|---------|
| **D1** | 追债 7 + 追债 8 合并**一个 PR** 完成（共用 db_updater 改造，拆开重复劳动） | 本 DECISION §一 边界 |
| **D2** | cancel 端点写 `executions.status='CANCELLED'` 的语义策略 = **"只写进行中的最后一个 step"**（`tasks.current_step` 对应的那条 execution） | 本 DECISION §五 cancel 语义 |
| **D3** | 追债 12（`create_match_score` dangling tool_name）**独立 PR-21**，不并入 PR-20 | 本 DECISION §七（不做清单） |

---

## 一 · PR 边界

### 1.1 · 交付面（严格清单）

**代码变更**：
- `backend/app/agent/orchestrator/act.py` — `run_act` 加 per-step 生命周期 callback（`on_step_start` / `on_step_end`）
- `backend/app/agent/orchestrator/engine.py` — `_background_execute` 传入 executions callback；`_write_task` 双出口（tasks + executions）
- `backend/app/api/v1/agent.py` — 新增 `_make_db_execution_writer()` 闭包；三处（chat / execute / skip-to-score）挂载；cancel 端点补 executions UPDATE
- `backend/app/models/execution.py` — 若字段/索引不足按 `PR-14 STEP6 §五 19.1` 补齐（**当前已够用，本 PR 不改结构**）
- `backend/tests/agent/orchestrator/test_run_act_callbacks.py`（新增）
- `backend/tests/api/v1/test_agent_executions_lifecycle.py`（新增）

**文档变更**：
- `HANDOFF.md §9.3 追债项 7 / 追债项 8` — 标 ✅ 已收敛（PR-20 `<sha>`），保留历史行文
- `HANDOFF.md §9.4 陷阱表` — 若引入新陷阱（如 "executions 与 tasks 二阶段写入的并发风险"）追加
- `HANDOFF.md §9.5` — 新增 `_make_db_execution_writer` 到关键新增文件表
- `docs/planning/stage5/PR20-STEP6-REPORT.md`（新增，末尾提交）

### 1.2 · 禁止边界

- ❌ **不改** `backend/app/models/execution.py` 表结构（当前 PR-10 `a5b6c7d8e9f0` 迁移已建，字段够用）
- ❌ **不改** SSE 事件格式或 `EventBuffer`
- ❌ **不引入** 真实任务队列（Celery/arq）或 Redis Pub/Sub（追债 1、2 独立处理）
- ❌ **不改** `cancel_task` 允许的入口状态集合（保持 `{PLANNING, WAITING_CONFIRMATION}` · 见 §五）
- ❌ **不改** 前端（前端只从 SSE 消费步骤进度，本 PR 后 DB 侧补齐仅为断连兜底，不影响前端渲染逻辑）
- ❌ **不动** `docs/api-contract.md`（本 PR 是**契约兑现**而非契约变更）
- ❌ **不合并 PR-21 追债 12**（D3 强制）

---

## 二 · 关键契约点

### 2.1 · executions 表字段用法（对齐 `models/execution.py` L16-52 实际字段）

**实际字段名与预期差异**（DECISION 起草时已实测校对，执行体请直接照此表用）：

| 字段（实际名） | 类型 | 本 PR 写入时机 |
|--------------|------|---------------|
| `execution_id` | `String(50)` PK | 由 `default=generate_execution_id` 自动生成 `exec_{uuid.uuid4().hex[:12]}`（无需显式传） |
| `task_id` | FK → `tasks.task_id` | `on_step_start` |
| `step_id` | `String(50) \| None` | `on_step_start`，来自 `PlanStep.step_id` |
| `phase` | `String(20)` **NOT NULL** | `on_step_start`，本 PR 恒填 **`"ACT"`**（PR-20 只 instrument Act 阶段；REASON/PLAN/REFLECT_* 追债入 Stage 5.2） |
| `tool_name` | `String(100) \| None` | `on_step_start`，来自 `PlanStep.tool_name` |
| `skill_id` / `skill_version` | `String \| None` | **本 PR 不填**（保留 null，Stage 5.2 补） |
| `input_params` | `JSON \| None` | `on_step_start`，`PlanStep.params`（**注意**：字段名是 `input_params` 不是 `input`） |
| `output_result` | `JSON \| None` | `on_step_end`，`StepResult.output`（**注意**：字段名是 `output_result` 不是 `output`） |
| `execution_status` | `String(20)` `default="PENDING"` | INSERT 默认 `PENDING` → `on_step_end` UPDATE 为 `COMPLETED/FAILED`；cancel 走 D2 UPDATE `CANCELLED`。**值域详见 §二.2** |
| `execution_time_ms` | `Integer \| None` | `on_step_end`，计算 `(finished_at - started_at).total_seconds() * 1000`；简单 int cast |
| `error_message` | `Text \| None` | `on_step_end`，`StepResult.error_message` |
| `started_at` / `finished_at` | `DateTime` naive | `on_step_start` / `on_step_end`，用 `app.core.time.utcnow_naive()` |
| `created_at` / `updated_at` | 由 `TimestampMixin` 自动 | 无需显式处理 |

### 2.2 · `execution_status` 值域扩展

**当前 `models/execution.py:37-43` 定义**：
```python
execution_status: Mapped[str] = mapped_column(
    String(20),
    default="PENDING",
    server_default="PENDING",
    nullable=False,
)
```
- **列类型是 `String(20)` 非 PG enum type** — 值域仅由 Python 侧约束
- 现有 doc 注释列出 `COMPLETED/FAILED/SKIPPED` + 默认 `PENDING`
- **本 PR 新增值域**：`CANCELLED`（对应 D2 cancel 语义 · Act 中 step 被 cancel 时用）

**实施要点**：
- ✅ **不需要 Alembic 迁移**（VARCHAR 已确认，非 PG enum）
- Python 层：若代码里有集合校验（如 `assert status in {"COMPLETED", "FAILED", "SKIPPED"}`）→ 补 `CANCELLED`
- 更新 `execution_status` 的 doc comment（在 model 或 `docs/data-model.md`）追加 `CANCELLED`

**注意**：`server_default="PENDING"` 表示新行**默认就是 PENDING**（无需显式在 `on_step_start` 中传 `execution_status`，除非要显式覆盖）。

### 2.3 · `tasks.current_step` 中途写 DB

**语义**：`current_step` 存的是**当前正在执行的 step_id**（字符串），而非索引。
- `on_step_start` 时 UPDATE `tasks.current_step = step_id`
- `on_step_end` 时**不清空**（保持"最后完成到哪一步"的痕迹，与 D2 cancel 语义一致）
- 终态（COMPLETED / FAILED / CANCELLED）时**不动** current_step（终态由 `_background_execute` 的 finally 分支写 tasks 表，与 current_step 正交）

---

## 三 · 架构与代码改造

### 3.1 · `run_act` 加 per-step callback

**当前签名**（`act.py:61`）：
```python
async def run_act(
    plan: dict,
    ctx: dict,
    emit: EmitFn | None = None,
    tool_router: ToolRouter | None = None,
) -> list[StepResult]:
```

**改造后签名**：
```python
StepStartFn = Callable[[str, dict], Awaitable[None]]  # (step_id, step_dict) -> None
StepEndFn   = Callable[[str, StepResult], Awaitable[None]]  # (step_id, result) -> None

async def run_act(
    plan: dict,
    ctx: dict,
    emit: EmitFn | None = None,
    tool_router: ToolRouter | None = None,
    on_step_start: StepStartFn | None = None,  # 新
    on_step_end: StepEndFn | None = None,      # 新
) -> list[StepResult]:
```

**调用点**：`run_act` step 循环内，在 `router.dispatch(...)` **前**调 `on_step_start(step_id, step)`，在 append 到 `results` **后**调 `on_step_end(step_id, sr)`。
- 与 `_safe_emit` 同型 try/except 包裹，callback 失败**只 log warning 不中断业务**（对齐现有 SSE emit 语义）
- callback 为 `None` 时零开销（`if on_step_start is not None: await ...`）

### 3.2 · `_make_db_execution_writer` 闭包（新增 in `agent.py`）

**风格对齐** `_make_db_updater`（L57-65）：
```python
async def _make_db_execution_writer(
    session_factory=async_session_factory,
) -> tuple[StepStartFn, StepEndFn]:
    """返回 (on_step_start, on_step_end) 一对回调，各自现建 session。"""

    async def _on_step_start(task_id: str, step_id: str, step: dict) -> None:
        async with session_factory() as s:
            s.add(Execution(
                task_id=task_id,
                step_id=step_id,
                phase="ACT",                          # 必填字段，本 PR 恒 "ACT"
                tool_name=step.get("tool_name"),
                input_params=step.get("params"),      # 注意：字段名 input_params
                # execution_status 由 server_default="PENDING" 自动填
                started_at=utcnow_naive(),
            ))
            await s.execute(
                update(Task).where(Task.task_id == task_id).values(current_step=step_id)
            )
            await s.commit()

    async def _on_step_end(task_id: str, step_id: str, sr: StepResult, started_at: datetime) -> None:
        status = "COMPLETED" if sr.success else "FAILED"
        finished = utcnow_naive()
        elapsed_ms = int((finished - started_at).total_seconds() * 1000)
        async with session_factory() as s:
            await s.execute(
                update(Execution)
                    .where(Execution.task_id == task_id, Execution.step_id == step_id)
                    .values(
                        execution_status=status,
                        output_result=sr.output,      # 注意：字段名 output_result
                        error_message=sr.error_message,
                        execution_time_ms=elapsed_ms,
                        finished_at=finished,
                    )
            )
            await s.commit()

    return _on_step_start, _on_step_end
```

**注意 task_id 与 started_at 传参**：
- `run_act` 内部当前用 `ctx.get("task_id")`（`act.py:79`）；callback 签名从 `run_act` 拿 `task_id` 后再传给 writer 闭包（partial 或再包一层 lambda，见 §3.3）
- `on_step_end` 计算 `execution_time_ms` 需要 `started_at`，由 `run_act` 在 step 循环内 `start_ts = utcnow_naive()` 记录后透传，或由 writer 从表里 SELECT 回来（**首选前者，性能开销小、逻辑局部**）

### 3.3 · `engine._background_execute` 挂载 executions writer

```python
async def _background_execute(
    self,
    task_id: str,
    plan: dict,
    buffer: EventBuffer | None,
    db_updater: DbUpdater | None = None,
    on_step_start: StepStartFn | None = None,  # 新
    on_step_end: StepEndFn | None = None,      # 新
) -> None:
    ...
    results = await asyncio.wait_for(
        run_act(
            plan,
            ctx={"task_id": task_id},
            emit=emit,
            tool_router=self.tool_router,
            on_step_start=(lambda sid, step: on_step_start(task_id, sid, step)) if on_step_start else None,
            on_step_end=(lambda sid, sr: on_step_end(task_id, sid, sr)) if on_step_end else None,
        ),
        timeout=self.task_timeout_sec,
    )
    ...
```

`start_execute` / `run_execute` / `run_skip_to_score` 三处调用 `_background_execute` 时把 callback 顺带传入（chat 端点入口在异步 `_background_reason_plan` 后进入执行，同样穿透）。

### 3.4 · Cancel 端点补 executions UPDATE（D2 语义）

**约束回顾**（`agent.py:320`）：cancel 只允许 `{PLANNING, WAITING_CONFIRMATION}` → 走 cancel 时**尚未进入 EXECUTING**，通常 `tasks.current_step is None`。

**D2 落地实现**：
```python
task.status = "CANCELLED"
task.finished_at = utcnow_naive()

# 追债 7 兑现：若已进入 executing（并发/未来扩展场景），把进行中的 execution 也标 CANCELLED
if task.current_step is not None:
    await db.execute(
        update(Execution)
            .where(
                Execution.task_id == task_id,
                Execution.step_id == task.current_step,
                Execution.execution_status.in_(["PENDING"]),
            )
            .values(
                execution_status="CANCELLED",
                finished_at=utcnow_naive(),
            )
    )

await db.commit()
```

**行为说明**：
- 当前 cancel 语义（PLANNING/WAITING）下 `current_step` 恒为 `None`，UPDATE 分支不进入 → 与 D2 "只写进行中的最后一个 step" 完全一致，**executions 不产生 CANCELLED 行**
- 未来扩容 cancel 允许 EXECUTING 状态时，D2 分支自动生效，一次不需要改
- **不做**"给所有未执行 step INSERT CANCELLED"（D2 否决方案）

### 3.5 · Task 终态回写与 executions 一致性

`_background_execute` 的 `try/except/finally` 分支已写 `tasks.status = COMPLETED/FAILED`；本 PR **不改** tasks 终态写入逻辑。executions 终态由 `on_step_end` 逐步写入，两者同步性由**顺序保证**：
1. 步骤完成 → `on_step_end` 写 executions 该行 `COMPLETED/FAILED`
2. 全部步骤完成后 → `_background_execute` 的 result_payload 分支写 tasks `COMPLETED`

**并发/一致性保证**：session 独立、事务独立；executions 逐步 commit 与 tasks 终态 commit 时序上无重叠（同一后台协程内串行）。**不需要**跨表事务。

---

## 四 · TDD 用例设计（预估 6 个新用例）

### 4.1 · `test_run_act_callbacks.py`（新增 · 2 用例）

- **TC-PR20-1** · `test_run_act_invokes_on_step_start_and_on_step_end_in_order`
  - 构造 3-step plan，注入 mock callbacks，dispatch 用 fake router
  - 断言：`on_step_start` 与 `on_step_end` 各调用 3 次；顺序为 `start_1 → end_1 → start_2 → end_2 → start_3 → end_3`
  - 断言：`on_step_end` 收到的 `StepResult.success` 与 dispatch 结果一致

- **TC-PR20-2** · `test_run_act_callback_error_does_not_break_dispatch`
  - `on_step_start` 抛异常 → 断言 dispatch 仍继续，`results` 完整，log warning 命中

### 4.2 · `test_agent_executions_lifecycle.py`（新增 · 4 用例）

- **TC-PR20-3** · `test_execute_plan_writes_executions_row_per_step`
  - 端到端：POST /execute-plan → 后台跑完 → 查 executions 表
  - 断言：N step → N 条 executions 行；`execution_status` 全为 COMPLETED；`step_id` / `tool_name` / `input` / `output` 与 plan 一致

- **TC-PR20-4** · `test_execute_plan_writes_current_step_progressively`
  - 端到端：POST /execute-plan → 在 step 2 完成前查 tasks 表
  - 断言：`tasks.current_step in {step_1_id, step_2_id}`（时序敏感，用 slow router fixture 保证可观察）

- **TC-PR20-5** · `test_execute_plan_marks_failed_step_in_executions`
  - fake router 在 step 2 抛异常 → 断言 executions step_2 行 `execution_status='FAILED'` 且 `error_message` 有值

- **TC-PR20-6** · `test_cancel_task_in_planning_does_not_write_executions`
  - cancel PLANNING 状态任务 → 断言 `executions` 表为空（D2 语义验证 · current_step is None）
  - **可选补充**：如果执行体愿意加一个 EXECUTING 状态 cancel 的 monkeypatch 场景验证 D2 主分支，鼓励加，但不强制

### 4.3 · 用例总量

- 新增 6，若 4.2 可选补充生效则 7
- **预期 N_after = 120 + 6 = 126 passed**（±2 浮动允许）

### 4.4 · fixtures 复用

- `conftest.py::db_session`（既有）
- `conftest.py::redis` / `event_buffer`（既有 fakeredis）
- 若需要 slow router，用 `AsyncMock` + `asyncio.sleep(0.05)` 组合，参考 `test_stage5_s5_09_*.py` 现有模式

---

## 五 · Commit 拆分（TDD 规范）

**执行体必须严格 TDD**：

| # | Commit | 内容 |
|---|--------|------|
| 1 | `test(stage5): PR-20 red-test skeleton (TC-PR20-1..6) + Execution fixture` | 6 个测试 stub（`test.fails` 或 `pytest.mark.xfail(strict=True)`）+ Execution 测试 fixture · **红** |
| 2 | `feat(stage5): PR-20 run_act per-step callbacks (TC-PR20-1/2 green)` | act.py 加 callback + engine.py 透传 · 剥离 TC-PR20-1/2 xfail · 预期 122 passed / 4 xfail |
| 3 | `feat(stage5): PR-20 _make_db_execution_writer + executions lifecycle wiring (TC-PR20-3/4/5 green)` | agent.py 加 writer 闭包 + 挂到三处入口 · 剥离 TC-PR20-3/4/5 xfail · 预期 125 passed / 1 xfail |
| 4 | `feat(stage5): PR-20 cancel writes executions.CANCELLED for active step (TC-PR20-6 green)` | cancel_task 端点补 D2 逻辑 · 剥离 TC-PR20-6 xfail · 预期 126 passed / 0 xfail |
| 5 | `docs(stage5): PR-20 STEP6 report (追债 7+8 收敛 · 4 commit TDD)` | STEP6 报告 + HANDOFF §9.3 追债 7/8 标 ✅ 已收敛 |

**若 §二.2 触发 execution_status 从 VARCHAR 改为 PG enum**（起草时已实测为 VARCHAR，仅在漂移场景需要），额外插入：
| 2.5 | `chore(stage5): PR-20 alembic add CANCELLED to execution_status enum` | Alembic 补 `ALTER TYPE` 迁移 |
— 但此路径**先触发 §八 clause 2 停下汇报**，等主指挥官确认后再执行。

---

## 六 · 三道门验收（复述硬要求）

按 `CLAUDE.md` 验收三道门：

```bash
# 门 1 · 测试
cd backend && uv run pytest -q
# 目标：126 passed（±2 浮动），未破坏既有 120，无 flaky 新增

# 门 2 · Lint
cd backend && uv run ruff check app/agent/orchestrator app/api/v1 app/models
# 目标：0 errors

# 门 3 · Build
# 后端无独立 build 门，本 PR 未触前端，前端 npm build 免跑但基线 31 passed 需保留（可选跑一次快照）
```

三条命令的输出末尾必须完整贴入 STEP6 报告 §二。

---

## 七 · 求助边界（stop-and-ask）

若命中以下条件，**停止执行**并把状态贴到本 DECISION 讨论线：

1. `pytest -q` 基线 `120` 与实际不符（PR-19 后有 backend 相关合并未纳入 HANDOFF 基线）
2. **`execution_status` 若被发现是 PG enum type**（DECISION 起草时实测为 VARCHAR，若执行体发现被迁移改成 PG enum）— 停下汇报，主指挥官裁定是否走独立迁移
3. `models/execution.py` 已有字段与 §二.1 表冲突（例如某字段类型不同、或缺 index）导致 executions 行插入失败
4. `run_act` 内部 `emit` 语义与 `on_step_start/end` 语义冲突（例如 emit 已经在做类似逐步落库的兜底 · 当前 grep 判定为无，若发现相反 → 停）
5. `_make_db_execution_writer` 与既有 `_make_db_updater` 并发写同一 `tasks.current_step` 出现 lost update（并发写测试暴露 race condition）
6. `alembic upgrade head` 报 dirty state（本 PR 不预期迁移，若报错说明 §二.2 已触发）
7. 后端测试改动**超过 6 个既有测试文件**（触及非追债 7/8 范围）
8. cancel 端点 D2 分支设计发现漏洞（如未来 cancel 扩容到 EXECUTING 时会破坏 executions 时序）— 停下与主指挥官确认是否需要在**本 PR 内**扩容
9. `HANDOFF.md §9.4` 陷阱 4-8 中任一条件在本 PR 内被引发新 flaky（例如 SSE + executions 落库互相干扰）
10. 追债 8 的 `current_step` 中途写 DB 后，前端断连重连场景在 pytest 中出现回归

---

## 八 · 契约与文档回写

**必须更新的文档**：

- `HANDOFF.md §9.1` PR 状态表新增：`| PR-20 | Stage 5.1 追债 7+8 | executions 全生命周期 + current_step 中途写 DB | ✅ | <sha> |`
- `HANDOFF.md §9.3 追债项 7`：末尾追加 `✅ 已收敛（PR-20 <sha>）` + 一句话总结实施要点
- `HANDOFF.md §9.3 追债项 8`：同上
- `HANDOFF.md §9.5`：新增 `_make_db_execution_writer` 到关键新增文件表
- `HANDOFF.md §9.6`：更新为"下一步 PR-21 追债 12 独立收敛 / Stage 5.1 P2（TIMESTAMPTZ + Artifact 护栏）"
- **不改** `docs/api-contract.md`（本 PR 是契约兑现）
- **不改** `docs/planning/PLAN-STAGE5.md`（架构未变）

**PR-20-STEP6-REPORT.md 必备结构**（参考 PR-19 STEP6 §一-§九）：
- §一 概述（分支 / base / 提交数 / 变更文件）
- §二 三道门验证（三条命令末尾输出）
- §三 实现细节（4 commit 逐一）
- §四 文件影响表
- §五 声明 & 观察（新引入的陷阱、设计权衡）
- §六 求助边界（§七 10 条哪些触发过、如何处理）
- §七 用例表（6 用例逐一 ✓）
- §八 提交链 + FF-merge 指引
- §九（若有）返修记录

---

## 九 · 执行体行动清单

按顺序执行：

1. `git checkout master && git pull` → 确认 HEAD ≥ `2888bbb`
2. `git checkout -b feat/pr-20-s51-executions-current-step`
3. `cd backend && uv run pytest -q` → 确认基线 120 passed（若失败走 §七 clause 1 停）
4. **红测提交**（commit 1）：写 6 个 xfail 用例骨架 + Execution 测试 fixture
5. **绿测提交**（commit 2-4）：按 §五 拆分严格 TDD
6. 全过程若触碰 §二.2 PG enum 或 §七 任一条件 → 停下汇报
7. 三道门本地验证 → 全绿
8. push branch → 写 `PR20-STEP6-REPORT.md` → 报告给主指挥官 FF-merge 评审

---

## 十 · 补充说明

- 本 PR **不影响前端**。前端 `useTaskStream` 断连重连仍然从 SSE 缓冲拿事件，不消费 tasks/executions 表。DB 侧补齐是**为未来运维/审计/多客户端场景**准备。
- 本 PR 是 Stage 5.1 首个技术债 PR，为后续 P2（TIMESTAMPTZ 迁移 + Artifact 护栏）建立"追债 PR 模式"参照。
- 本 PR 完成后，**MVP 交付前只剩 P2（约 3-5 天）+ 侧栏隐藏 6 空壳（1 天）** 即可对外发布 v1.0。

---

**本 DECISION 落地即视为主指挥官已授权执行体开工。**
**执行过程中如需修订 DECISION 本身，需回主指挥官确认（docs-only 提交可直接改 master 上的本文件，代码相关需回本讨论线）。**
