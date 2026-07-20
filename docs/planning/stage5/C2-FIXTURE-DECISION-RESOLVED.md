# 【已裁定】C2 红测试 fixture 缺陷修复方案 · 处置纪要

> 关联：PR-10 · 分支 `feat/pr-10-s5-01-02-data-layer`
> 起因：`docs/planning/stage5/C2-FIXTURE-DECISION.md` 待裁定
> 裁定人：Claude Code 总指挥官
> 裁定时间：2026-07-20
> 状态：✅ 已裁定并直接落地（commit `36fb248`），执行体按 §四继续推进

---

## 一、裁定结论

| 问 | 答 |
|---|---|
| **Q1 授权微调 `test_stage5_s5_01_data_layer.py` 的 fixture？** | ✅ **是**，且已由指挥官直接改并 push（commit `36fb248`） |
| **Q2 备选方案？** | 不适用（Q1 已批） |
| **§六 契约微调 2 处（`execution_status=PENDING` 默认、`__init__` 生成前缀）** | ✅ 认可，属让契约测试成立的必要对齐，不需回改契约文档 |

**结论概述**：C1 交付的 fixture 设计有 2 处缺陷（async fixture + `asyncio.run` 冲突；`migrated_conn` teardown 与 `db_session` 假设自相矛盾），但根因认定完全正确。方案 §四方向正确，指挥官在此基础上加固 3 处否则会在后续 PR 咬人的隐患，直接改并 push。

---

## 二、已 push 的修复（commit `36fb248`）

**范围**：仅 `backend/tests/test_stage5_s5_01_data_layer.py` fixture 部分（+72 / -38 行），未动生产代码、未动断言。

**核心 3 处加固**（超越原方案 §四）：

| 隐患 | 原方案 §四 | 已落地加固 |
|---|---|---|
| **① 硬编码 `downgrade(cfg, "e4c1a2b3d4f5")` 是定时炸弹** | 沿用硬编码 Stage4 head | 改用**动态记录进入前 head**（`_current_head()` 用同步 psycopg2 引擎），teardown 回退到该 head |
| **② 若共享 dev 库已在 Stage5 head（PR-10 merge 后）** | 未考虑；会误删后续迁移 | pre_head 机制自动处理 no-op 场景（回到同一 head 是 no-op） |
| **③ `TC-S5-01-3` 复用 `conftest.db_session` 语义错位** | 表已建即可复用 | 新建 `migrated_session` fixture，独立 engine + rollback，schema 由 `_migrated_schema` 统一管 |

**新 fixture 骨架**：

```python
@pytest.fixture(scope="module")
def _migrated_schema():          # ← 同步 def, 绕开 asyncio.run 冲突
    cfg = _make_alembic_cfg()
    sync_url = get_settings().database_url.replace("+asyncpg", "+psycopg2")
    pre_head = _current_head(sync_url)   # ← 动态记录进入前 head
    command.upgrade(cfg, "head")
    try:
        yield
    finally:
        command.downgrade(cfg, pre_head or "base")   # ← 相对回退

@pytest_asyncio.fixture
async def migrated_session(_migrated_schema):
    # 独立 engine + NullPool + 事务 rollback
    ...
```

---

## 三、经验沉淀（HANDOFF.md §5.3 已写入）

新增踩坑条目（+1 行到 §5.3）：

> **⚠️ alembic 迁移不要在 `async` fixture 里跑**：`alembic.command.upgrade` 内部走 `asyncio.run(run_async_migrations())`，若外层已在 pytest-asyncio 事件循环里会抛 `asyncio.run() cannot be called from a running event loop`。必须用**同步** `@pytest.fixture(scope="module") def`，且 teardown 用**相对回退**（记录进入前 head → `command.downgrade(cfg, pre_head or "base")`），不要硬编码 revision，否则后续新迁移落地后会误删。范式见 `backend/tests/test_stage5_s5_01_data_layer.py::_migrated_schema`

**为什么写入 HANDOFF**：Stage 5 后续 PR（如 PR-13 EventBuffer 迁移、PR-15/16 candidate-merge/profile）都可能重复遇到；未来 Stage 6/7 亦然。

---

## 四、当前分支状态

```
feat/pr-10-s5-01-02-data-layer

36fb248 test(stage5): fix S5-01 fixtures — sync module scope + relative downgrade   ← ✅ 已 push
0ed9299 docs: add PR branch policy for stage 5 (feat branch required)
5067be0 test(stage5): add S5-01/02 red tests for tasks/executions & registry
```

**未 commit 的执行体工作区**（预期）：
- `backend/app/models/task.py`（就绪）
- `backend/app/models/execution.py`（就绪）
- `backend/app/models/__init__.py`（就绪）
- `backend/alembic/versions/a5b6c7d8e9f0_add_agent_tasks_and_executions.py`（就绪）

---

## 五、执行体下一步执行清单（严格按顺序）

### Step 1 · 验证红→绿转换（不新增 commit）

```bash
uv run pytest backend/tests/test_stage5_s5_01_data_layer.py -v
```

**期望结果**：
- ✅ `TC-S5-01-1 PASSED`（迁移后 tasks/executions + 复合索引存在）
- ✅ `TC-S5-01-2 PASSED`（模型前缀，已在 §六 报备）
- ✅ `TC-S5-01-3 PASSED`（CASCADE 删除生效）
- ✅ `TC-S5-01-4 PASSED`（元数据索引断言）

**若 `TC-S5-01-3` 仍 FAILED**：检查 `Execution.task_id` FK 声明是否含 `ondelete="CASCADE"`。若未加，请补齐后重试（属生产代码，无需再来问）。

**若 `TC-S5-01-1` 仍 ERROR**：粘贴堆栈来问，可能是 alembic 版本差异导致 pre_head 读取路径不同。

### Step 2 · 提交 C2（生产代码入库）· 独立 commit

```bash
git add backend/app/models/task.py \
        backend/app/models/execution.py \
        backend/app/models/__init__.py \
        backend/alembic/versions/a5b6c7d8e9f0_add_agent_tasks_and_executions.py
git commit -m "feat(stage5): add tasks/executions models & migration (S5-01)

- Task model: task_ 前缀主键, status/user_message/current_step/started_at/finished_at
- Execution model: exec_ 前缀主键, phase, execution_status(默认 PENDING), FK CASCADE
- Composite indexes: idx_tasks_status_created, idx_executions_task_created
- Migration a5b6c7d8e9f0 down_revision=e4c1a2b3d4f5

对齐 docs/planning/PLAN-STAGE5.md §2 Q12 DDL 与 TASKS-STAGE5.md §S5-01。
```

**注意**：
- 迁移文件**必须独立 commit**（按 `HANDOFF.md §4.1` 新规），但因本次 model + migration 语义紧密绑定且都是新建，允许合并为一个 C2 commit；若您希望更严格，可拆成 C2a（model）+ C2b（migration）
- **不要**把 `backend/backend.err` / `call1.txt` / `call2.txt` 加进 commit

### Step 3 · 提交 C3（SkillRegistry 扩展）

先跑一次 `uv run pytest backend/tests/test_stage5_s5_02_registry_schemas.py -v -k internal` 确认 `TC-S5-02-4` 仍红（生产代码未落地）。然后实现：

```
backend/app/agent/skill_registry.py:
  - 新增 internal: bool 字段（默认 False）从 skill.yaml 读入
  - 新增 get(skill_id: str) -> BaseSkill | None（含 internal Skill）
  - 新增 list_dispatchable(task_type: str | None = None) -> list[BaseSkill]（过滤 internal=True）
```

```bash
git add backend/app/agent/skill_registry.py
# 若 skill.yaml Loader 也改了：加 backend/app/agent/skill_loader.py 等
git commit -m "feat(stage5): extend SkillRegistry with internal/list_dispatchable/get (S5-02)

- skill.yaml 新增可选 internal: bool 字段(默认 false, 向后兼容)
- get(): 全量查询, 供 Orchestrator engine 内部调用
- list_dispatchable(): 过滤 internal=true, 供 Tool Router
- 对齐 docs/planning/PLAN-STAGE5.md §2 Q10 D4 v2 + HANDOFF §Skill 契约"
```

验证：`TC-S5-02-4` 转绿。

### Step 4 · 提交 C4（Agent Schemas）

实现：
```
backend/app/schemas/agent.py:
  - SSEEvent (含 id 字段)
  - SSEEventType (8 枚举: thinking/plan/tool_call/progress/result/error/warning/system)
  - PlanStep (含 optional: bool = False)
  - Plan
  - AgentChatRequest / AgentChatResponse
  - TaskStatus (含 CANCELLED)
  - ExecutePlanRequest / SkipToScoreRequest
  - CancelTaskResponse
  - ExecutionPhase 枚举
```

```bash
git add backend/app/schemas/agent.py
git commit -m "feat(stage5): add agent schemas — SSEEvent/Plan/AgentChatRequest/TaskStatus (S5-02)

- 对齐 docs/api-contract.md §3.2 SSEEvent 信封 + §3.3 8 类事件
- 对齐 §3.4 PlanStep (含 optional 字段) / Plan
- 对齐 §4.4 TaskStatus (含 CANCELLED) + §4.5 取消端点
- 严格 pydantic 校验, 缺 message → ValidationError"
```

验证：`TC-S5-02-{1,2,3}` 转绿。

### Step 5 · 全绿态最终校验

```bash
uv run pytest backend/tests/test_stage5_s5_01_data_layer.py backend/tests/test_stage5_s5_02_registry_schemas.py -v
```

**必须全部 PASSED**。

再跑全量：
```bash
uv run pytest
```

**必须全绿**（含 Stage 4 51 用例 + 本 PR 新增 8 用例）。

### Step 6 · push 并报回

```bash
git push origin feat/pr-10-s5-01-02-data-layer
```

回报格式：

> PR-10 · S5-01/02 全绿完成
> - Branch: feat/pr-10-s5-01-02-data-layer
> - Commits: 5067be0 → 36fb248 → C2 → C3 → C4（共 5 个）
> - `uv run pytest` 全绿：xxx passed
> - 请指挥官核验并 fast-forward merge to master

指挥官核验通过后**由指挥官在 GitHub 平台开 PR-10 并 merge**（或您 push 后由指挥官直接 `git merge --ff-only` 到 master）。

---

## 六、若 Step 1-5 中途遇阻 · 求助边界

**必须先来问**：
- `TC-S5-01-1` upgrade/downgrade 报错（可能 alembic 版本差异）
- `TC-S5-02-4` `list_dispatchable` 返回结构不确定（如是否分 task_type 维度过滤）
- 任何**动到契约字段命名/类型**的场景

**可自主决策**（无需请示）：
- 添加 `ondelete="CASCADE"` / `nullable=False` 等模型细节
- pydantic v2 的 `Field(...)` 用法
- schema 内部字段顺序、docstring
- commit 拆分粒度（C3+C4 合并也可）

---

## 七、后续 Stage 5 PR 的默认套路（PR-11..PR-18 沿用）

1. 从 `master` 拉 `feat/pr-<N>-<slug>` 分支
2. 先提交红测试 commit（`test(stage5): ...`）
3. 再依次提交绿态实现 commit（`feat(stage5): ...`）
4. 迁移文件**必须独立 commit**（不与 model/schema 合并）
5. 分支上跑 `uv run pytest` 全绿后 push
6. 指挥官核验 → 平台开 PR 或本地 `git merge --ff-only` → 删分支

**分支策略规范原文**：`HANDOFF.md §4.1`。

---

## 附：文件索引

- 待裁定源文档：`docs/planning/stage5/C2-FIXTURE-DECISION.md`（保留原样，作为过程档案）
- 本处置纪要：`docs/planning/stage5/C2-FIXTURE-DECISION-RESOLVED.md`（本文件）
- 已 push commit：`36fb248 test(stage5): fix S5-01 fixtures — sync module scope + relative downgrade`
- 经验沉淀：`HANDOFF.md §5.3`（+1 条 alembic 陷阱）
- 分支策略：`HANDOFF.md §4.1`（PR-10 起沿用）
