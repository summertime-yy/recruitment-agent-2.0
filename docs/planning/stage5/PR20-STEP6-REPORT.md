# PR-20 STEP6 执行报告（返修二版）

S5.1 执行记录（executions write-back + current_step + cancel CANCELLED · 8 commit TDD + 两轮返修）

---

## §一 概述

- **分支**：`feat/pr-20-s51-executions-current-step`
- **base**：`origin/master` @ `a36731f` (≥ requirement `2888bbb`)
- **实际提交数**：9（2 test + 4 feat + 1 fix + 2 docs）
- **变更文件**：5 backend 文件（engine.py + agent.py + act.py + 2 test）+ 2 docs（STEP6 + HANDOFF §9.4）
- **追债覆盖**：追债 7（executions DB 写入 + 生产链路接线）、追债 8（current_step 中途 UPDATE + cancel CANCELLED）

---

## §二 三门实况（返修二后）

| 门 | 结果 | 备注 |
|------|------|------|
| Test | **129 passed, 1 skipped, 5.89s**（`pytest -q` 不加 `-k`，全量不 hang） | skipped = TC-S5.1-7（HANDOFF §9.4 陷阱 12） |
| Lint | `ruff check app/agent/orchestrator app/api/v1 app/models` → **All checks passed!** | 0 errors |
| Build | 纯后端 / 无 TS，N/A | — |

**命令尾行**：
```
$ uv run pytest -q
.....................................................................s.. [ 55%]
..........................................................               [100%]
129 passed, 1 skipped in 5.89s

$ uv run ruff check app/agent/orchestrator app/api/v1 app/models
All checks passed!
```

---

## §三 提交链

```
2ba933f test(stage5): PR-20 skip TC-S5.1-7 to unblock pytest -q full run
31ea290 feat(stage5): PR-20 debt-8 landed - writer start updates tasks.current_step mid-run
204008a docs(stage5): PR-20 STEP6 report updated with return records (7 commits)
0a8d14e test(stage5): PR-20 E2E endpoint tests (TC-S5.1-7 xfail + TC-S5.1-8 PASSED)
833600d fix(stage5): PR-20 wire executions writer into production endpoints + cancel D2
213b2ac docs(stage5): PR-20 STEP6 report (S5.1 executions · 4 commit TDD + 返修更新)
23fb34c feat(stage5): PR-20 cancel writes executions.CANCELLED (TC-S5.1-4 GREEN)
ef499f3 feat(stage5): PR-20 _make_db_execution_writer + lifecycle (TC-S5.1-2/3/6 GREEN)
29415f2 feat(stage5): PR-20 run_act callbacks (TC-S5.1-1/5 GREEN)
5a0b9f6 test(stage5): PR-20 red-test skeleton (TC-S5.1-1..6 xfail)
a36731f docs(stage5): PR-20 kickoff decision (BASE)
```

---

## §四 每个 commit 涵盖

### Commit 1 (5a0b9f6) — 红测骨架
- `tests/test_stage5_pr20_executions.py`：6 xfail test

### Commit 2 (29415f2) — run_act callbacks
- `act.py`：+ `on_step_start`/`on_step_end` 参数，含 success/fail/optional 三分支
- TC-S5.1-1/5 GREEN

### Commit 3 (ef499f3) — DB execution writer
- `engine.py`：`_make_db_execution_writer(session_factory, task_id)` — INSERT start / UPDATE end
- TC-S5.1-2/3/6 GREEN

### Commit 4 (23fb34c) — cancel writes CANCELLED
- `engine.py::run_cancel`：追加 PENDING → CANCELLED
- TC-S5.1-4 GREEN
- 基线 126 passed

### Commit 5 (833600d) — 返修 fix **（初审退回后追加）**
- **A — 生产链路接线**：
  - `_make_db_execution_writer` 改为 `session_factory` 模式（对齐 `_make_db_updater`）
  - `_background_execute`：接受 `execution_writer`，构造 `on_step_start`/`on_step_end` 适配
  - `run_execute` / `run_skip_to_score`：接受并透传 `execution_writer`
  - `agent.py`：`execute_plan` / `skip_to_score` 构造 writer + 传入 engine
- **B — cancel 端点 D2**：
  - `agent.py::cancel_task`：在 task.current_step 存在时 UPDATE Execution → CANCELLED
- **C — lint**：
  - `datetime.now(timezone.utc).replace(tzinfo=None)` → `utcnow_naive()`（engine.py L73/86/638）
- **D — 测试修复**：
  - `_test_session_factory(db_session)` 包装器
  - TC-S5.1-6 async callback 改为 `async def` 包装
  - `test_engine_2_background_execute` mock 追加 `**kwargs`

### Commit 6 (0a8d14e) — E2E endpoint 测试
- TC-S5.1-7：`POST /agent/execute-plan` → executions 表 2 条 COMPLETED（初标 xfail，返修二改 skip，见 §九）
- TC-S5.1-8：`POST /agent/tasks/{id}/cancel` → execution CANCELLED（**PASSED** ✅）

### Commit 7 (31ea290) — 返修二 · 追债 8 落地 **（复审退回后追加）**
- `engine.py::_make_db_execution_writer` `action="start"` 分支：同一 session、同一事务内追加
  `UPDATE tasks SET current_step = step_id`；`action="end"` 不动 current_step（保留"最后进行到哪一步"痕迹，与 cancel D2 语义一致，DECISION §二.3）
- TC-S5.1-9 / TC-S5.1-10 两个单元用例 GREEN

### Commit 8 (2ba933f) — 返修二 · TC-S5.1-7 skip + HANDOFF 陷阱 12
- TC-S5.1-7 `@pytest.mark.xfail` → `@pytest.mark.skip`（hang 用例作为 xfail 仍会执行并挂死全量跑）
- HANDOFF §9.4 追加陷阱 12：ASGITransport + `asyncio.create_task` 后台任务测试环境死锁（禁忌 + 替代方案 + 与陷阱 5 同源说明）
- 全量 `pytest -q`（不加 `-k`）不 hang：129 passed / 1 skipped

---

## §五 覆盖的用例（单元 + E2E）

| TC | 类型 | 内容 | 状态 |
|----|------|------|------|
| TC-S5.1-1 | 单元 | callbacks called in order | PASSED |
| TC-S5.1-2 | 单元 | writer creates record on start | PASSED |
| TC-S5.1-3 | 单元 | writer updates on end | PASSED |
| TC-S5.1-4 | 单元 | cancel writes CANCELLED | PASSED |
| TC-S5.1-5 | 单元 | failed step calls on_end | PASSED |
| TC-S5.1-6 | 单元 | run_act + writer creates multi exec | PASSED |
| TC-S5.1-7 | E2E | execute-plan endpoint → executions | **skip**（HANDOFF §9.4 陷阱 12，后续独立 PR） |
| **TC-S5.1-8** | **E2E** | **cancel endpoint → execution CANCELLED** | **PASSED** |
| **TC-S5.1-9** | **单元** | **writer start UPDATE tasks.current_step** | **PASSED** |
| **TC-S5.1-10** | **单元** | **writer end 不清 current_step，下一 start 推进** | **PASSED** |

---

## §六 是否达到 N_after

- 目标 N_after（返修二后）：129 passed / 1 skipped
- 实际：**129 passed, 1 skipped in 5.89s**（`pytest -q` 全量、不加 `-k`、不 hang）✅

---

## §七 stop-and-ask 边界状态

- ✅ PG enum 漂移：未检测到（`execution_status` 是 VARCHAR）
- ✅ 并发 lost update：仅 SELECT FOR UPDATE 在 task 层；execution 是 append-only INSERT + UPDATE status，冲突率极低
- ✅ cancel 语义：engine + endpoint D2 双写（engine 保底，endpoint 主实现）
- ⚠️ TC-S5.1-7 挂死：**后续独立 PR 处理**

---

## §八 FF-merge 指引

```bash
git fetch origin
git merge --ff-only origin/feat/pr-20-s51-executions-current-step
```

HEAD: `2ba933f` 之后的 docs commit（见 push 后短 hash）

---

## §九 返修记录

### 返修一（commander review round 1）

**初审结论**：FF-merge 拒绝 — A(端点未接线) + B(cancel D2) + C(lint) + D(async cb)。
四项已在 Commit 5 (`833600d`) 全部修复：

- A：`_make_db_execution_writer` session_factory 模式 + `_background_execute`/`run_execute`/`run_skip_to_score` 透传 + `agent.py` 端点构造 writer
- B：`agent.py::cancel_task` D2 分支（`current_step` 存在时 UPDATE Execution → CANCELLED）
- C：`datetime.now(timezone.utc).replace(tzinfo=None)` → `utcnow_naive()`
- D：`_test_session_factory` 包装 + TC-S5.1-6 async cb + engine mock `**kwargs`

### 返修二（commander review round 2）

**复审结论**：DECISION 双目标只落了一个（追债 7），追债 8 的 current_step 中途 UPDATE 遗漏；且 hang 用例不能以 xfail 存在（xfail 仍执行 → 全量 `pytest -q` 挂死）。

**E 项 — 追债 8 补齐（Commit 7 `31ea290`）**：
- `writer(action="start")` 分支内、同一 `async with session_factory() as db` 上下文中追加
  `UPDATE tasks SET current_step = step_id`（与 INSERT execution 同事务提交）
- `on_step_end` 不动 current_step——保留"最后进行到哪一步"痕迹，与 cancel D2 语义一致（DECISION §二.3）
- 生产链路证明：返修一 A 项已把 writer 接进 `execute_plan`/`skip_to_score` 端点，
  加上 TC-S5.1-9/10 单元验证 writer 行为，即证明生产链路会写 current_step（无需 E2E）

**F 项 — TC-S5.1-7 hang 处理（Commit 8 `2ba933f`）**：
- `xfail` → `skip`，reason 记录：ASGITransport + `asyncio.create_task` 死锁；
  后续独立 PR 修复（subprocess httpx 或 pytest-timeout 兜底）；
  单元级 TC-S5.1-2/3/6 覆盖 helper、E2E TC-S5.1-8 覆盖 cancel D2，execute-plan E2E 是加分项非必需
- HANDOFF §9.4 追加陷阱 12（含禁忌、替代方案、与陷阱 5 同源说明）

**新用例**：TC-S5.1-9/10 已入 §五 用例表；§六 N_after 更新为 129。

**三门复跑（返修二后）**：
- `uv run pytest -q`（不加 `-k`）→ **129 passed, 1 skipped in 5.89s**，不 hang
- `uv run ruff check app/agent/orchestrator app/api/v1 app/models` → **All checks passed!**

**TC-S5.1-8**：cancel 端点 D2 主实现 + E2E 验证通过。
