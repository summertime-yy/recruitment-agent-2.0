# Stage 5 测试计划 · 指挥官版（TEST-PLAN-STAGE5）

> 版本：`commander-v1`（双盲评审隔离产物）
> 依据：`docs/planning/stage5/commander/TASKS-STAGE5.md`
> 策略：TDD 强制 —— 每 PR 先写测试再写实现，红→绿→重构。
> 覆盖目标：后端 ≥40 例（S5-01..10）+ 前端 ≥12 例（S5-11..12）

---

## 编号规则

`TC-S5-<任务编号>-<两位序号>` — 一一对应到 TASKS 的 S5-01..12。

---

## S5-01 · tasks/executions 数据模型（TC-S5-01-01..08）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_tasks_table_ddl_matches_plan` | 迁移后 `information_schema` 查 tasks 表字段列表、类型、NOT NULL、DEFAULT 与 PLAN 决策 12 逐条一致 |
| 02 | `test_executions_table_ddl_matches_plan` | 同上，executions 表 |
| 03 | `test_migration_upgrade_downgrade_roundtrip` | `alembic upgrade head` → `downgrade -1` → 表消失 → `upgrade head` 再建 |
| 04 | `test_task_model_crud_basic` | 创建、查询、更新 status、软删除路径 |
| 05 | `test_execution_cascade_delete_on_task_delete` | 删除 task → 关联 executions 自动删除 |
| 06 | `test_task_status_transitions_pydantic` | Schema 枚举 `TaskStatus` 覆盖 `api-contract §4.4` 定义全集 |
| 07 | `test_plan_schema_matches_api_contract` | `Plan/PlanStep` 序列化字段名与 §3.4 严格一致 |
| 08 | `test_agent_request_response_schemas` | `AgentChatRequest/Response`、`ExecutePlanRequest`、`SkipToScoreRequest` 与 §4.1–4.3 一致 |

---

## S5-02 · SkillRegistry 扩展（TC-S5-02-01..04）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_list_by_task_type_returns_matching_skills` | 注册两个 Skill 各带 task_types，查询命中 |
| 02 | `test_list_by_task_type_returns_empty_for_unknown_type` | 未知 task_type → `[]`，不抛异常 |
| 03 | `test_skill_without_task_types_backward_compatible` | 老 Skill 缺字段仍能被 registry 加载 |
| 04 | `test_jd_candidate_matching_registers_task_types` | S5-02 补的 `[MATCH_ONE, MATCH_RANK]` 生效 |

---

## S5-03 · Tool Router（TC-S5-03-01..06）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_router_resolves_valid_plan_step` | 合法 skill_id + version → 返回 Skill 实例 |
| 02 | `test_router_raises_skill_not_found` | 未注册 skill_id → `SkillNotFoundError` |
| 03 | `test_router_raises_version_missing` | 版本不存在 → `SkillVersionMissingError` |
| 04 | `test_router_raises_param_mismatch_missing_field` | 参数缺必需字段 → `SkillParamMismatchError` |
| 05 | `test_router_accepts_param_superset` | 参数超集（有额外字段）→ 通过（Pydantic v2 默认忽略额外字段） |
| 06 | `test_router_validates_via_pydantic_v2` | 类型错误（int 给 str）→ 抛 `SkillParamMismatchError` |

---

## S5-04 · Orchestrator 阶段 Skill（TC-S5-04-01..10）

每 Skill 2 例（成功路径 + 边界/mock 异常路径），共 10。

| 编号 | 用例 | 断言 |
|---|---|---|
| 01-02 | `orchestrator_reason` mock LLM 输出合法/异常 | 输出 Schema 校验、task_type 分类命中 |
| 03-04 | `orchestrator_reflect` | is_feasible 分支、needs_clarification 分支 |
| 05-06 | `orchestrator_plan` | 生成 ≥1 step 的 Plan；空输入 fallback |
| 07-08 | `orchestrator_reflect_plan` | is_plan_sound=true 直通；false 输出 adjusted_plan |
| 09-10 | `orchestrator_reflect_act` | 全成功 result；部分失败 partial 汇总 |

---

## S5-05 · Orchestrator Engine（TC-S5-05-01..15）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_start_transitions_pending_to_planning` | 状态从 PENDING → PLANNING |
| 02 | `test_plan_generated_transitions_to_waiting_confirmation` | Plan 成功 → WAITING_CONFIRMATION |
| 03 | `test_resume_from_plan_transitions_to_executing` | WAITING → EXECUTING |
| 04 | `test_skip_to_score_directly_executes` | 跳过 Reason/Plan，直接 EXECUTING，Plan 由代码构造 |
| 05 | `test_completed_transition_from_executing` | 全成功 → COMPLETED |
| 06 | `test_failed_transition_when_reason_fails` | Reason 失败 → FAILED，`error_code='REASON_FAILED'` |
| 07 | `test_cancelled_transition_from_waiting` | 用户取消 → CANCELLED |
| 08 | `test_illegal_transition_raises` | PENDING → EXECUTING 直接跳（非法）→ 抛 `InvalidStateTransition` |
| 09 | `test_illegal_transition_from_completed` | COMPLETED → 任意 → 抛 |
| 10 | `test_illegal_transition_from_failed` | FAILED → 任意 → 抛 |
| 11 | `test_task_timeout_marks_failed` | Task 总时长 > 600s → FAILED，`error_code='TASK_TIMEOUT'` |
| 12 | `test_stage_timeout_recovers_with_warning` | 单阶段超时 → 发 warning，尝试下一步 |
| 13 | `test_act_concurrency_limited_by_semaphore` | 4 个并行 step，Semaphore(2) → 观察到至多 2 个同时 running（时间断言） |
| 14 | `test_partial_failure_still_completes` | 3 step 中 1 步失败 → COMPLETED，result 含 partial 标记 |
| 15 | `test_each_stage_writes_execution_record` | R-P-R-A-R 5 阶段 + N Skill 调用 → executions 表条数正确 |

---

## S5-06 · EventBus（TC-S5-06-01..08）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_emit_returns_monotonic_seq` | 连续 emit 3 次，seq 递增 1,2,3 |
| 02 | `test_replay_from_none_returns_all` | replay(None) 返回全部缓冲事件 |
| 03 | `test_replay_from_seq_returns_after` | replay(N) 只返回 seq>N 的事件 |
| 04 | `test_replay_beyond_buffer_emits_warning` | 请求 seq 已被 LTRIM 滚出 → 收到 warning 事件 |
| 05 | `test_buffer_size_limit_200` | emit 250 条后，缓冲只保留 200 条 |
| 06 | `test_buffer_ttl_30min` | fake time 前进 31min → 缓冲过期（TTL 断言） |
| 07 | `test_subscribe_yields_new_events` | 订阅期间 emit → subscriber 收到 |
| 08 | `test_heartbeat_every_15s` | fake time 前进 30s → 收到 2 条 system heartbeat |

---

## S5-07 · SSE 端点（TC-S5-07-01..05）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_sse_returns_text_event_stream_header` | Content-Type == `text/event-stream` |
| 02 | `test_sse_streams_events_from_bus` | emit 3 事件后 client 收 3 帧 |
| 03 | `test_sse_last_event_id_replays_from_seq` | 请求头 `Last-Event-ID: 5` → 只收 seq>5 |
| 04 | `test_sse_unknown_task_returns_404` | 未知 task_id → 404 |
| 05 | `test_sse_heartbeat_frame_received` | 长连接 20s → 至少 1 条心跳帧 |

---

## S5-08 · REST API 四端点（TC-S5-08-01..12）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_route_order_stream_not_shadowed_by_tasks_id` | GET `/agent/tasks/abc/stream` 命中 SSE handler，非 `/tasks/{id}` |
| 02 | `test_chat_creates_task_returns_planning` | POST /agent/chat → 200，返回 task_id 与 status='PLANNING' |
| 03 | `test_chat_starts_orchestrator_async` | 调用后异步任务已启动（mock engine） |
| 04 | `test_execute_plan_on_waiting_confirmation` | 状态正确 → 200，status='EXECUTING' |
| 05 | `test_execute_plan_conflict_on_wrong_status` | task 处于 EXECUTING → 409 |
| 06 | `test_execute_plan_task_not_found` | 未知 task_id → 404 |
| 07 | `test_skip_to_score_creates_task_executing` | 200, status='EXECUTING'，Plan 自动构造 |
| 08 | `test_skip_to_score_bad_jd_returns_404` | jd_id 不存在 → 404 |
| 09 | `test_task_status_returns_full_shape` | GET /agent/tasks/{id} 返回字段 == api-contract §4.4 |
| 10 | `test_task_status_not_found` | 未知 → 404 |
| 11 | `test_global_concurrency_limit_returns_429` | 已有 10 个活跃 task → 第 11 个 chat 请求 → 429 |
| 12 | `test_invalid_request_body_returns_400` | POST /agent/chat 无 message → 400 |

---

## S5-09 · candidate-merge Skill（TC-S5-09-01..06）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_high_confidence_auto_merges` | confidence≥0.9 → `duplicate_of_resume_id` 写入 |
| 02 | `test_low_confidence_returns_suggest_only` | confidence<0.9 → 不落库，返回 merge_groups |
| 03 | `test_phone_same_email_diff_flagged_as_conflict` | 生成 conflicts 条目 |
| 04 | `test_empty_input_returns_empty_groups` | 输入空列表 → 空返回，无异常 |
| 05 | `test_merge_updates_primary_wins` | primary 保留，duplicates 挂 duplicate_of |
| 06 | `test_skill_registered_with_task_type_merge` | SkillRegistry.list_by_task_type('MERGE_CANDIDATES') 命中 |

---

## S5-10 · candidate-profile Skill（TC-S5-10-01..05）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_profile_generates_tags` | 输出 tags 列表非空 |
| 02 | `test_tags_merged_with_existing_no_overwrite` | 已有用户手工标签保留 |
| 03 | `test_one_line_summary_length_bounded` | ≤200 字 |
| 04 | `test_empty_resume_returns_fallback` | parsed_content 缺失 → 兜底文案，不抛 |
| 05 | `test_skill_registered_with_task_type_profile` | SkillRegistry 命中 |

---

## S5-11 · 前端 ChatCenter + useSSE（TC-S5-11-01..08）

**技术栈**：Vitest + jsdom + @testing-library/react + msw + `eventsource-mock` 或 `msw-sse`

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_chatcenter_renders_input_and_task_list` | 页面骨架渲染 |
| 02 | `test_chat_submit_calls_agent_chat_api` | 输入 + 发送 → POST /agent/chat |
| 03 | `test_sse_thinking_event_renders_thinking_card` | mock SSE 帧 → ThinkingCard 出现 |
| 04 | `test_sse_plan_event_renders_plan_card_with_confirm` | PlanCard 出现且有"执行"按钮 |
| 05 | `test_click_execute_plan_calls_api` | 点击"执行" → POST /agent/execute-plan |
| 06 | `test_progress_card_updates_on_progress_event` | 进度条更新 |
| 07 | `test_reconnect_sends_last_event_id_header` | EventSource close → 重连时携带 lastEventId（用 `eventsource-mock` 断言） |
| 08 | `test_error_card_shown_on_error_event` | error 事件 → ErrorCard |

---

## S5-12 · 前端 CandidateChat（TC-S5-12-01..03）

| 编号 | 用例 | 断言 |
|---|---|---|
| 01 | `test_candidate_chat_prefills_context` | 进入页面，context.candidate_ids 已含 resume_id |
| 02 | `test_generate_profile_triggers_agent_chat` | 点击快捷"生成画像"→ POST /agent/chat with task hint |
| 03 | `test_result_event_shows_tags_in_ui` | Result 事件 → 页面显示 tags |

---

## 三道门集成校验

| 门 | 命令 | 目标 |
|---|---|---|
| backend | `cd backend && uv run pytest -q` | 新增 ≥40 用例，全绿 |
| frontend test | `cd frontend && npm run test` | 新增 ≥12 用例（本 Stage 累计 28+），全绿 |
| frontend lint | `npm run lint` | 0 error；新增文件 0 warning |
| frontend build | `npm run build` | exit 0 |

---

## TDD 执行序

每 PR 内：
1. 先在对应测试文件写红测试（对齐本 TEST-PLAN 编号），运行确认失败
2. 写最小实现让测试变绿
3. 重构 & 再跑三道门
4. commit（Conventional Commits，subject ≤ 72 字）

