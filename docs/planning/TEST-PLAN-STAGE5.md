# TEST-PLAN-STAGE5 · 合并版（最终冻结，PR-9 交付物）

> 配套：`PLAN-STAGE5.md`、`TASKS-STAGE5.md`
> 来源：执行体版 46/12 为骨架，经 `REVIEW.md` 裁定合并（加 CANCELLED / internal Skill 隔离 / 心跳 / 复合索引 / 500 / 取消 UI 用例，mock 目标改 `BaseSkill.execute`）
> 严格 TDD：**测试先于实现编写**。后端 pytest+pytest-asyncio（ASGI AsyncClient / fakeredis），前端 Vitest+jsdom+@testing-library/react+msw。
> 目标：后端新增 **≥40**（本计划列 **50**）用例，前端新增 **≥12**（本计划列 **14**）用例。

---

## 一、后端测试（目标 ≥40，本计划列 50）

### S5-01 数据层（4）
- `TC-S5-01-1` migration_creates_tasks_executions：升级 head 后两表存在，复合索引 `idx_tasks_status_created`/`idx_executions_task_created` 存在。
- `TC-S5-01-2` model_id_prefix：`Task()` 默认 `task_` 前缀、`Execution()` 默认 `exec_` 前缀。
- `TC-S5-01-3` cascade_delete_tasks：删 Task → 关联 executions 一并删除（CASCADE）。
- `TC-S5-01-4` composite_index_exists：断言 `idx_tasks_status_created (status, created_at DESC)`、`idx_executions_task_created (task_id, created_at ASC)` 已在迁移中创建（元数据反射）。

### S5-02 Schema + SkillRegistry（4）
- `TC-S5-02-1` sse_event_id_type_enum：`SSEEvent(type="bogus")` 校验失败（422）；含 `id` 字段。
- `TC-S5-02-2` chat_request_requires_message：`AgentChatRequest(message=None)` 422。
- `TC-S5-02-3` plan_roundtrip：`Plan`/`PlanStep` 序列化 `step_id` 为字符串、`optional` 缺省 `false` 且字段完整。
- `TC-S5-02-4` internal_skill_excluded_from_dispatchable：`list_dispatchable()` 不返回 `internal=true` 的 Skill；`get('orchestrator-reason')` 可取到。

### S5-03 EventBuffer（Redis/fakeredis）（5）
- `TC-S5-03-1` buffer_trim_to_200：append 250 条，`replay(0)` 仅 200 条。
- `TC-S5-03-2` replay_after_id：`replay(task, after_id=10)` 仅返回 `id>10`。
- `TC-S5-03-3` buffer_ttl_expire：终态后 advance fakeredis 时钟 3600s，`replay` 空。
- `TC-S5-03-4` buffer_isolation：两 task_id 缓冲互不串。
- `TC-S5-03-5` heartbeat_every_15s：freezegun/fakeredis 时间旅行断言心跳事件间隔 15s（`system` 类型）。

### S5-04 Tool Router（6）
- `TC-S5-04-1` dispatch_registered_skill：`tool_name="jd-candidate-matching"` 成功返回 SkillResult（经 `list_dispatchable`）。
- `TC-S5-04-2` dispatch_unknown_skill：`tool_name="__x__"` 抛 `UnknownToolError` → 映射 `UNKNOWN_TOOL`。
- `TC-S5-04-3` dispatch_param_mismatch：`tool_name="search_resumes"` 缺参 → 抛 `ToolParamError`。
- `TC-S5-04-4` route_task_type：ReasonOutput 不同 `task_type` 映射到正确意图枚举。
- `TC-S5-04-5` router_no_second_llm：路由不触发额外 LLM 调用（mock `call_llm_json` 计数 = Reason/Plan 主调用数）。
- `TC-S5-04-6` router_refuses_internal_skill：`tool_name="orchestrator-reason"` → 抛 `SkillNotDispatchableError`。

### S5-05 Reason+Reflect（3，mock 目标 = BaseSkill.execute）
- `TC-S5-05-1` reason_mock_ok：mock `orchestrator_reason` Skill `execute` 返回合法 JSON → `ReasonOutput.task_type` 非空、`missing_entities` 列表。
- `TC-S5-05-2` reflect_infeasible：`orchestrator_reflect` 返回 `is_feasible=false` → 引擎进入 WAITING_CONFIRMATION/FAILED（不 Plan）。
- `TC-S5-05-3` reason_invalid_json：Skill `validate_output` 失败 → 写 execution FAILED 且不崩溃。

### S5-06 Plan+ReflectPlan（3，mock 目标 = BaseSkill.execute）
- `TC-S5-06-1` plan_tools_valid：`orchestrator_plan` 产出 `steps[].tool_name` 全在白名单。
- `TC-S5-06-2` reflect_plan_adopt_adjusted：`is_plan_sound=false` 且有 `adjusted_plan` → 采用之。
- `TC-S5-06-3` reflect_plan_detect_bad_tool：plan 含未注册 `tool_name` → `is_plan_sound=false` 并记 `issues`。

### S5-07 Act+ReflectAct+SSE emit（5，mock 目标 = BaseSkill.execute / ToolRouter.dispatch）
- `TC-S5-07-1` event_order：`run_act` 单步依次发 `tool_call`→`progress(100)`→`result`。
- `TC-S5-07-2` required_step_fail_abort：必需步 Skill FAILED → 发 `error` 且中止，已成功步产物在 `StepResult`。
- `TC-S5-07-3` partial_artifacts_on_invalid：`orchestrator_reflect_act` 返回 `is_result_valid=false` → `result` 事件仍带 artifacts。
- `TC-S5-07-4` optional_step_fail_continue：optional 步失败 → 发 `warning` 且继续。
- `TC-S5-07-5` act_emits_thinking_for_reason_phase：Reason 阶段经 emit 发 `thinking` 事件。

### S5-08 状态机/并发/超时/降级（8）
- `TC-S5-08-1` legal_transition_chain：PENDING→PLANNING→WAITING_CONFIRMATION→EXECUTING→COMPLETED 全合法。
- `TC-S5-08-2` illegal_transition_rejected：COMPLETED→EXECUTING 抛 `IllegalTransitionError` 且状态不变。
- `TC-S5-08-3` global_concurrency_429：活跃任务 mock 达 10 → 新 `chat` 返 429 `TASK_LIMIT_EXCEEDED`。
- `TC-S5-08-4` skill_timeout_degrade：单 Skill 超时阈值设极小 → 该步 `error` 且 Task FAILED（部分 artifacts 留 `result`）。
- `TC-S5-08-5` task_overall_timeout：整体 600s 超时 → Task FAILED + `error(TASK_TIMEOUT)`。
- `TC-S5-08-6` transition_each_legal：遍历 PLAN §2 Q2 矩阵每行合法转移各 ≥1 例（参数化，含 CANCELLED 两条）。
- `TC-S5-08-7` transition_each_illegal：矩阵外每类非法转移各 ≥1 例抛错。
- `TC-S5-08-8` cancelled_transition_from_waiting_confirmation：`WAITING_CONFIRMATION → CANCELLED` 合法；`EXECUTING → CANCELLED` 非法（抛错）。

### S5-09 REST + SSE 端点（6）
- `TC-S5-09-1` route_order_stream_before_task：`/stream` 先于 `/{id}` 声明，两路由独立可解析。
- `TC-S5-09-2` status_codes：chat 缺 message→422；`tasks/{bad}`→404；非确认态 `cancel`→409。
- `TC-S5-09-3` sse_last_event_id_replay：带 `Last-Event-ID:5` 重连只收 `id>5`。
- `TC-S5-09-4` sse_heartbeat：连接 15s 内收到 `system` 心跳事件。
- `TC-S5-09-5` sse_content_type：`/stream` 响应头 `text/event-stream` + `retry:3000`。
- `TC-S5-09-6` orchestrator_unhandled_exception_returns_500：mock engine raise → `chat` 返 500（REST 状态码矩阵覆盖）。

### S5-10 candidate-merge（4）
- `TC-S5-10-1` high_confidence_merge：confidence≥0.9 → `action=MERGE` + `master_resume_id`。
- `TC-S5-10-2` low_confidence_suggest：confidence<0.5 → `action=SUGGEST` + `recommendation`。
- `TC-S5-10-3` conflict_keep_separate：不同姓名/手机号 → `action=KEEP_SEPARATE`。
- `TC-S5-10-4` output_schema_valid：output 缺必填字段 → Skill 返回 FAILED（`validate_output` 拦截）。

### S5-11 candidate-profile（4）
- `TC-S5-11-1` normal_generate：`profile_tags` 非空。
- `TC-S5-11-2` merge_dedup_with_manual：`existing_tags=["Python"]` + 模型给 `"python"` → 合并后唯一。
- `TC-S5-11-3` schema_fail_degrade：output 缺必填 → Skill FAILED 不写库。
- `TC-S5-11-4` empty_parsed_content：空 `parsed_content` 边界不崩、返回合理标签或空。

> 后端合计：4+4+5+6+3+3+5+8+6+4+4 = **50** 用例（≥40 ✓）。

---

## 二、前端测试（目标 ≥12，本计划列 14）

### 类型与 Hook（4）
- `TC-S5-12-1` parse_eight_event_types：`useTaskStream` 收到 8 类事件各更新对应 state 字段。
- `TC-S5-12-2` last_event_id_reconnect：模拟断线后重连请求头带 `Last-Event-ID`（msw 校验）。
- `TC-S5-12-3` chat_429_handled：`services/agent.ts` 429 → 抛出可捕获错误且不崩溃。
- `TC-S5-12-4` types_align_schema：`SSEEvent`/`Plan`（含 `optional`）/`TaskStatus`（含 `CANCELLED`）类型字段与 `api-contract §3/§4` 一致（编译期 + 单测断言）。

### ChatCenter（5）
- `TC-S5-13-1` send_then_plan_card：输入消息 → 出现 `PlanCard` 且「确认」按钮调用 `executePlan`。
- `TC-S5-13-2` skip_to_score_quick：选 JD+候选人 → `skipToScore` → 显示进度卡片。
- `TC-S5-13-3` eight_event_cards_render：`thinking/plan/tool_call/progress/result/error/warning/system` 八类卡片均渲染（SystemCard 仅状态提示）。
- `TC-S5-13-4` reconnect_no_duplicate：断线重连后经 `Last-Event-ID` 补齐，无重复卡片。
- `TC-S5-13-5` cancel_button_calls_cancel：`PlanCard`「取消」按钮调用 `cancelTask()`（POST `/agent/tasks/{id}/cancel`）。

### CandidateChat + 边界（5）
- `TC-S5-13-6` prefilled_context：进入页时 `context.candidate_ids` 已预填并随 `chat` 发送。
- `TC-S5-13-7` warning_card_shown：`warning` 事件渲染 `WarningCard`。
- `TC-S5-13-8` system_heartbeat_ignored：`system` 心跳事件不渲染为业务卡片（仅状态提示）。
- `TC-S5-13-9` cancelled_task_shows_cancelled_ui：`CANCELLED` 态任务显示取消提示 UI（非 ErrorCard）。
- `TC-S5-13-10` error_card_shown：`error` 事件渲染 `ErrorCard` 且显示 `message`。

> 前端合计：4+5+5 = **14** 用例（≥12 ✓）。

---

## 三、覆盖维度核对（对照 INSTRUCTION §六，合并版）

| 维度 | 覆盖 |
|---|---|
| 状态机每条合法转移 ≥1 | `TC-S5-08-1`、`TC-S5-08-6`（含 CANCELLED 两条） |
| 每条非法转移 ≥1（抛异常） | `TC-S5-08-2`、`TC-S5-08-7` |
| internal Skill 隔离 | `TC-S5-02-4`（registry）、`TC-S5-04-6`（router 拒） |
| Tool Router 正例/未注册/参数不匹配/内置工具 | `TC-S5-04-1/2/3` |
| SSE 时序：Last-Event-ID 重放 / 缓冲滚出 / 心跳 | `TC-S5-09-3`、`TC-S5-03-1`、`TC-S5-03-5`、`TC-S5-09-4` |
| 每个 Orchestrator 阶段 Skill ≥1 mock（BaseSkill.execute） | `TC-S5-05-1`、`TC-S5-06-1`、`TC-S5-07-1`、`TC-S5-10-1`、`TC-S5-11-1` |
| REST 状态码矩阵 200/400/404/409/422/429/500 | `TC-S5-09-2`（422/404/409）、`TC-S5-08-3`（429）、`TC-S5-04-2`（映射 500 内部）、`TC-S5-09-6`（500）、`TC-S5-02-2`（422） |
| 前端 SSE 消费：8 类事件卡片各 1 + 断线重连 1 + 取消 1 | `TC-S5-13-3`、`TC-S5-13-4`、`TC-S5-13-5` |
| candidate-merge：高置信/低置信/冲突 各 ≥1 | `TC-S5-10-1/2/3` |
| candidate-profile：正常 / 与手工标签合并去重 各 ≥1 | `TC-S5-11-1`、`TC-S5-11-2` |

---

## 四、三道门通过标准（§3.7）

- 后端：`uv run pytest` 全绿（含本计划 50 用例 + 既有 51 用例）。
- 前端：`npm run test`（Vitest）全绿（含本计划 14 用例 + 既有 16 用例）。
- 前端：`npm run lint` 0 error；`npm run build` exit 0。

---

## 五、测试先写约定

1. 每个 S5-XX 任务**先写对应 `TC-S5-XX-*` 测试并使其失败（红）**，再实现使其转绿。
2. 后端 LLM/Skill 调用一律 mock（`BaseSkill.execute` 打桩或注入桩 Skill），不触真实 Ark。
3. Redis 相关一律 `fakeredis`，CI 不依赖外部 Redis 容器（或 stage 内起 redis 服务）。
4. 前端 SSE 用 msw 拦截 `EventSource` 或 mock `useTaskStream` 注入事件序列。
