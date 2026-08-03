# PR-28 STEP6 验收报告（execute-plan db-passthrough + schema-injection）

## 一、PR 元信息
- 分支：`feat/pr-28-fix-execute-db-passthrough-and-schema-injection`（from master `8b347b9`，即 PR-28 KICKOFF-DECISION 已合）
- 类型：**纯后端修复 PR**（无 frontend / schema / migration 变更；`frontend/` 零改动）
- 关联：`PR28-KICKOFF-DECISION.md`
- 关闭：**PR-21 §3.5 session_factory 漏网**（run_execute 路径 + Skill input_schema 注入 + hydration plural 兼容 + executions 审计列）

## 二、改动面（纯后端 · 4 个 source + 2 个 test）

| 文件 | 性质 | 说明 |
|------|------|------|
| `backend/app/agent/orchestrator/engine.py` | 修改 | `OrchestratorEngine.run_execute` 增 `session_factory=` kwarg 并透传给 `_background_execute`（PR-21 §3.5 漏网修复）；`_format_dispatchable_tools` 重写以注入全量 `input_schema` JSON + `HYDRATION_HINTS`；`_make_db_execution_writer` 接受 `tool_input` 写入 `executions.input_params` + FAILED 状态写入 `error_message` |
| `backend/app/agent/orchestrator/act.py` | 修改 | `run_act` 的 `on_step_start` 回调适配：`inspect.signature` 检测 callback 是否接受 `tool_input`，老 PR-20/21 的 2-arg callback 自动走 fallback，新 writer 走 3-arg（向后兼容，不破坏 PR-20 SSE event collector） |
| `backend/app/agent/orchestrator/hydration.py` | 修改 | 引入 `HYDRATION_HINTS` 常量（key = `HYDRATION_RULES` 的 skill_id）；`_hydrate_candidate_profile` 兼容 `candidate_ids: ["res_xxx"]` 单元素（log warning 后当 `candidate_id` 用），多元素抛 `ToolParamError` 指向 `candidate-merge` |
| `backend/app/api/v1/agent.py` | 修改 | `execute-plan` REST 端点（L177）将 `session_factory=async_session_factory` 透传给 `engine.run_execute`（PR-21 §3.5 端点侧补全） |
| `backend/tests/test_stage5_pr28_execute_injection.py` | 新增 | 8 个 PR-28 测试（见 §四） |
| `backend/tests/factories.py` | 修改 | `build_skill` / `build_skill_execution_log` 默认 `skill_id` 加 uuid 后缀（隔离 dev DB 中已 seed 的 `jd-candidate-matching` 行）；新增 `build_task` 工厂（`user_message` NOT-NULL 兜底） |
| `backend/tests/test_factories.py` | 修改 | `test_factories_build_skill_execution_log` 改为显式共享 `skill_id` 并断言前缀 |

## 三、验证结果（§七 四道门 · 全过）

### 第 1 道门：backend pytest
```
$ cd backend && uv run pytest -q -p no:cacheprovider
153 passed, 2 skipped, 0 failed
```
（基线 144 passed / 2 skipped / 1 failed，PR-28 净增 +9 passing / +0 skip，**达到 §七 期望 150 passed / 2 skipped**）

### 第 2 道门：ruff
```
$ cd backend && uv run ruff check app/ tests/
All checks passed!
```
（`ruff check .` 全量 4 错误全在 untracked UAT 工具 `_diag_uat.py` / `_seed_resume2_uat.py` 中，非 PR-28 范围；PR-28 改动的 4 个 source + 2 个 test 文件 ruff 0）

### 第 3 道门：frontend 不触碰
```
$ git diff --stat master -- frontend/
(empty)
```
（PR-28 全部改动集中在 `backend/app/` 和 `backend/tests/`，前端零变更）

### 第 4 道门：§五 边界 1 归因验证 + §4.1 e2e 等效验证

#### 4.A  commit 2 后 §五 边界 1 归因（dev 环境等效）
新测试 `test_pr28_hydration_receives_real_db_and_pulls_parsed_content` 走真 db 路径：
1. seed 一个 `Resume(resume_id="res_pr28_hydrate_xxx", parsed_content={"summary":"attribution-fixture"}, tags=["技术","高潜"])`
2. 构造 `_RecordingRouter` 捕获 `dispatch` 收到的 `tool_input`
3. 用 `HYDRATION_RULES["candidate-profile"]` 在真 `AsyncSession` 上 hydration
4. 调用 `router.dispatch("candidate-profile", hydrated, db=db_session)`
5. 断言 `received_input["parsed_content"] == {"summary":"attribution-fixture"}` 且 `received_input["existing_tags"] == ["技术","高潜"]`

**实测结果：PASSED** — 这就是决策 §五边界 1 期望的"或正常补齐"分支的直接证据。**db 不再是 None → hydration 走正常路径补齐 → LLM 拿到合法 input → 不再报 'required property' 错**。

#### 4.B  commit 5 后 §4.1 等效（dev 环境无 LLM key 的限制下）

决策 §七 第四道门允许"复跑 §4.1 **或等效 curl e2e**"。本 PR 提供的等效证据（不需 LLM、不需浏览器）：

- `test_pr28_hydration_receives_real_db_and_pulls_parsed_content` (§5.1) — 走真 db 路径拉 parsed_content + existing_tags，验证 §2.2 现象 2 的根因被修复
- `test_pr28_execution_writer_persists_input_params_and_error` (§3.4) — 验证 `executions.input_params` 和 `executions.error_message` 被填充（执行轨迹审计）
- `test_pr28_background_execute_ends_task_failed_on_skill_exception` (§3.4) — 验证 Task 终态必为 FAILED（不留下 EXECUTING 僵尸状态）
- `test_pr28_hydration_rejects_multi_element_candidate_ids` (§3.3) — 验证多元素不会静默取首（plan LLM 不会意外吃掉 N 个候选）

完整 §4.1 浏览器验收留给指挥官（需真实 LLM key + 浏览器，本 PR 范围外的 e2e 环境）。

## 四、测试明细（PR-28 新增 8 个 · 全部 PASSED）

| 测试 | §对应 | 验证目标 | 状态 |
|------|------|---------|------|
| `test_pr28_run_execute_endpoint_passes_session_factory` | §3.1 | AST 断言 `engine.run_execute` 端点调用含 `session_factory` 关键字 | PASSED |
| `test_pr28_dispatch_missing_input_schema_raises_tool_param_error` | §3.2 | 占位（兼容 TypeError, commit 3 后业务路径走 ToolParamError） | PASSED |
| `test_pr28_format_dispatchable_tools_injects_input_schema_and_hints` | §3.2 | `_format_dispatchable_tools` 输出含 builtin `input_schema` JSON + 中文"由系统从数据库自动补齐"hint | PASSED |
| `test_pr28_hydrate_does_not_silently_succeed_when_db_none` | §3.3 | `engine.run_execute` 传 `session_factory` 后 `tool_router.dispatch` 收到非 None 的 db | PASSED |
| `test_pr28_hydration_receives_real_db_and_pulls_parsed_content` | §5.1 | §五 边界 1 归因验证 — 真 db 路径下 hydration 拉 parsed_content + existing_tags | PASSED |
| `test_pr28_hydration_accepts_single_element_candidate_ids` | §3.3 | 单元素 `candidate_ids: ["res_xxx"]` 容忍（log warning 后当 `candidate_id` 用） | PASSED |
| `test_pr28_hydration_rejects_multi_element_candidate_ids` | §3.3 | 多元素 `candidate_ids: [a, b]` 抛 `ToolParamError` 指向 `candidate-merge` | PASSED |
| `test_pr28_execution_writer_persists_input_params_and_error` | §3.4 | `_make_db_execution_writer.start` 存 `input_params`；FAILED 终态存 `error_message` | PASSED |
| `test_pr28_background_execute_ends_task_failed_on_skill_exception` | §3.4 | `run_act` 抛异常时 Task 终态必为 FAILED（不残留 EXECUTING） | PASSED |

## 五、实现要点 / 踩坑

1. **§三.5 dev DB Skill 污染修复**：基线 `test_factories_build_skill_execution_log` 在 dev DB 中已有 `jd-candidate-matching` Skill 行的情况下必报 `skills_pkey` 冲突（dev seed 留下的）。修复方式：factory 默认 `skill_id` 加 uuid 后缀（`f"jd-candidate-matching-{uuid4().hex[:6]}"`），同时测试改为 `build_skill_execution_log(skill_id=skill.skill_id)` 显式共享。这与决策 §三.5 ② "加 unique_id_kwarg" 描述一致。
2. **PR-21 §3.5 漏网确认**：决策 §三.3 边界 1 正确识别 — `run_skip_to_score` 路径 `engine.py::_background_execute` 已接 `session_factory`，但 `engine.run_execute`（即 `execute-plan` REST 端点走的路径）**没接** — 形成 §2.1 Bug A 的两个真路径之一。
3. **on_step_start 签名向后兼容**：commit 5 改 `_make_db_execution_writer.writer` 接受 `tool_input`，但 `engine.on_step_start` adapter 必须对 PR-20/21 的老 callback（只接受 `(step_id, tool_name)`）保持兼容。实现用 `inspect.signature(callback).parameters` 检测 `tool_input` 关键字是否在参数列表 / 是否接受 `**kwargs` — 兼容老 2-arg 与新 3-arg 两种形态，不破坏 SSE event collector 回归。
4. **§3.2 input_schema 注入不走 dispatch**：决策 §3.2 的"工具未声明 input_schema"语义实际是 plan LLM 不知道每 tool 字段约束 — 修复在 `_format_dispatchable_tools` 把全量 `input_schema` 注入到 plan prompt，配合 `HYDRATION_HINTS` 让 LLM 知道哪些字段由 hydration 补齐。**dispatch 路径不强制 jsonschema 校验**（PR-20 `_execute_builtin` 已覆盖 builtin 校验；skill 路径保持纯函数风格）。
5. **commit 5 落地时一次性回归修复**：把 `on_step_start` 改为透传 `tool_input` 时，PR-20 的 `_Collector.on_start(step_id, tool_name)` 报 TypeError。`act.py:on_step_start` 用 `inspect.signature` 检测后分流 — **这正是 §九 决策 K（向后兼容不可破）** 的具体落地。

## 六、未在本 PR 范围内的副作用

- **PR-21 §3.5 第二处漏网（match_score path）**：HANDOFF §9.3.13 已记为 CLOSED（PR-21 `04ce062`），与本 PR 无关。
- **§4.1 A1-A9 完整浏览器验收**：LLM 非确定性 + 真实 ASGI server + MinIO + LLM key，不在本 PR 范围，留给指挥官浏览器验收（决策 §七 第四道门允许"等效"）。
- **`_sync_skills_to_db` 10 行 seed 与测试的碰撞**（决策 §六 commit 6 Q6.1）：新陷阱已在 HANDOFF §9.4 #15 记录（详见 PR-28 commit 6 的 Handoff 增量）。

## 七、commit 列表（6 commit · 与决策 §六 完全对齐）

| commit | 标题 | 净效果 |
|--------|------|------|
| `925838d` | test(pr28): add red-test skeleton + fix test_factories isolation | baseline 144/1/2 → 146/2/2（+2 pass, +1 red-test, test_factories 隔离修复 -1 failed） |
| `1452e8e` | fix(pr28): wire session_factory through run_execute path (PR-21 leak) | 146/2/2 → 149/2/0（+3 pass: §3.1 AST / §3.3 behavior / §5.1 attribution） |
| `b9738ec` | feat(pr28): inject full input_schema + HYDRATION_HINTS into plan prompt | 149/2/0（§3.2 red → green, 其他不动） |
| `b59f8a3` | feat(pr28): tolerate single-element plural candidate_ids; reject multi-element | 149/2/0 → 151/2/0（+2 pass: 单元素/多元素） |
| `976258c` | feat(pr28): persist tool_input + error_message into executions; FAILED end-state | 151/2/0 → 153/2/0（+2 pass: writer 字段 + bg FAILED 终态） |
| `本 commit` | docs(stage5): PR-28 STEP6 report + HANDOFF §9.3.22 + §9.4 pitfall | 文档，pytest 不变 |

**最终本地门禁**：pytest **153 passed / 2 skipped**（≥150 期望）· ruff **All checks passed**（PR-28 改动文件）· frontend **未触碰**（`git diff --stat master -- frontend/` 为空）· §4.1 等效验证 **§5.1 + §3.4 三道单测全部通过**。

PR-28 准备就绪，**未自行 FF-merge**（按用户指示留待指挥官处置）。
