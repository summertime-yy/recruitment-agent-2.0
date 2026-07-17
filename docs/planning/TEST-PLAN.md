# Stage 4 TDD 验证方案（TEST-PLAN）

> 版本：v1.0
> 更新时间：2026-07-16
> 关联：`docs/planning/PLAN.md`、`docs/planning/TASKS.md`
> **强制约定：本文件中所有测试用例，必须在对应实现代码之前提交（红→绿→重构）。**

---

## 通用约定

- **后端**：`pytest` + `pytest-asyncio`（`asyncio_mode=auto`），全部用例通过 `AsyncClient(ASGITransport(app=app))` 的 `client` fixture。文件命名 `test_<module>.py`，用例命名 `test_<behavior>`。
- **后端 DB**：由 S4-05 引入的 `db_session` fixture 提供隔离数据库（优先 in-memory `aiosqlite`）；LLM 调用一律通过 `mock_llm` fixture 打桩。
- **前端**：`vitest run`（S4-09 引入）；文件命名 `<Name>.test.tsx` / `<name>.test.ts`，测试目录 `frontend/tests/`。
- **通过标准**：`uv run pytest` 全绿；`uv run ruff check .` 无 error；`npm run test` 全绿；`npm run lint && npm run build` 通过。
- 每个测试用例的"输入 / 期望 / 断言"必须清晰；**先写空实现让测试红，再实现让测试绿**。

---

## 1. S4-01｜文档契约冻结（无自动化测试）

不涉及代码执行，验收通过**人工评审**：
- `docs/data-model.md §3.3` 出现 `match_scores` 完整字段与索引说明；
- `docs/api-contract.md` 新增「Stage 4 人岗匹配 API」小节，包含 6 个端点契约；
- `docs/planning/PLAN.md` 的"契约锚点"节字段与文档一致。

---

## 2. S4-02 + S4-03｜模型 & Schema 单测

**测试文件**：`backend/tests/test_match_score_model.py`、`backend/tests/test_match_schemas.py`

| 用例 | 输入 | 期望 |
|-----|------|------|
| `test_match_score_id_default_prefix` | 实例化 MatchScore，未指定 PK | `score_id` 以 `ms_` 开头，长度 15 |
| `test_match_score_unique_pair_constraint` | 连续插入两条相同 `(jd_id, resume_id)` | 第二次 `db.commit()` 抛 `IntegrityError` |
| `test_match_score_cascade_on_resume_delete` | 建 MatchScore → 删除对应 resume | MatchScore 也被删除 |
| `test_match_score_response_serializes_dimension` | 给出 dict `dimension_scores`，实例化 `MatchScoreResponse.model_validate` | 三维度成功嵌套解析 |
| `test_match_score_request_validates_ids_length` | `jd_id` 长度 60 | Pydantic `ValidationError` |
| `test_batch_match_request_limit_bounds` | `limit=0` / `limit=999` | 均抛 `ValidationError` |
| `test_ranking_response_orders_items_desc` | 传入乱序 items | 按 `overall_score` 降序（如序列化时排序则此校验放 Service 用例中） |

**断言要点**：外键 CASCADE 策略、Unique 约束名 `uq_match_scores_jd_resume`、`is_stale` 缺省为 `False`。

---

## 3. S4-04｜Skill 单测

**测试文件**：`backend/tests/test_jd_candidate_matching_skill.py`

前置：使用 `mock_llm` fixture，将 `app.agent.llm_adapter.call_llm_json` 打桩为固定 JSON 返回。

| 用例 | 输入 | 期望 |
|-----|------|------|
| `test_skill_is_registered` | `get_skill_registry().get_skill("jd-candidate-matching")` | 返回非空对象，`version == "1.0.0"` |
| `test_skill_input_schema_rejects_missing_jd` | 缺 `jd` 字段调用 `execute` | `SkillResult.success=False`，`status=FAILED` |
| `test_skill_prompt_renders_jd_and_resume_fields` | Mock 一次，捕获 `user_prompt` 参数 | 渲染出 JD title、resume candidate_name、必备技能列表 |
| `test_skill_success_returns_all_dimensions` | mock 返回合格 JSON | `result.success=True`，output 含 3 维度分数，每个 0-100 |
| `test_skill_rejects_out_of_range_score` | mock 返回 `skill_match.score=150` | 校验失败，`SkillResult.success=False` |
| `test_skill_compliance_ok_when_output_clean` | mock 干净输出 | `compliance_check.passed=True` |
| `test_skill_max_retries_is_zero` | 属性断言 | `skill.max_retries == 0`（对齐 LLM 契约） |

---

## 4. S4-05｜后端 pytest 基线

**测试文件**：`backend/tests/test_health.py`、`backend/tests/test_smoke_jds.py`、`backend/tests/test_smoke_resumes.py`

| 用例 | 输入 | 期望 |
|-----|------|------|
| `test_health_endpoint_returns_ok` | `GET /health` | 200 且 body 含 `"status": "ok"`（或既有约定字段） |
| `test_list_jds_returns_empty_by_default` | `GET /api/v1/jds` | 200，`items=[]`，`total=0` |
| `test_list_resumes_returns_empty_by_default` | `GET /api/v1/resumes` | 200，`items=[]`，`total=0` |
| `test_factories_build_valid_resume` | `factories.build_resume(...)` | 返回可插入 DB 的 Resume 实例，字段全 |
| `test_mock_llm_fixture_overrides_call` | 使用 `mock_llm` 后调用 `call_llm_json` | 返回打桩值，未真调用外部 |

**通过标准**：`uv run pytest -v` 至少收集 5 条并全绿。

---

## 5. S4-06｜MatchService 单测

**测试文件**：`backend/tests/test_match_service.py`（使用 `db_session` + `mock_llm`）

| 用例 | 输入 | 期望 |
|-----|------|------|
| `test_match_one_creates_row_when_first` | 存在 JD/Resume(parsed)，调用 `match_one` | 返回 `MatchScore`，`overall_score` = round(0.5*80+0.3*70+0.2*90, 1) = 79 |
| `test_match_one_returns_cached_when_not_force` | 已存在 `(jd, res)` MatchScore | 不调用 LLM，返回已有行（`skill_execution_id` 保持不变） |
| `test_match_one_recomputes_when_force_true` | 已存在，传 `force=True` | LLM 被调用；`updated_at` 递增；`skill_execution_id` 更新 |
| `test_match_one_rejects_unparsed_resume` | Resume `parse_status='PARSING'` | 抛业务异常（Service 层 `ValueError` → API 层 409） |
| `test_match_one_missing_jd_raises` | jd_id 不存在 | `ValueError` |
| `test_match_one_missing_resume_raises` | resume_id 不存在 | `ValueError` |
| `test_match_one_writes_skill_execution_log` | 成功匹配 | `skill_execution_logs` 新增一行，`task_id` 关联到 score_id 或 resume_id |
| `test_overall_score_uses_weighted_average` | mock 分数 100/50/50 | overall = round(0.5*100+0.3*50+0.2*50, 1) = 75.0 |
| `test_is_stale_when_resume_updated_after_score` | 生成 score 后修改 resume.updated_at | `is_stale=True` |
| `test_batch_match_default_selects_parsed_only` | 存在 3 parsed + 2 pending | 只匹配 3 条 |
| `test_batch_match_respects_limit` | limit=2 | 只提交 2 条 |
| `test_batch_match_returns_task_handle` | 调用 batch | 返回含 `task_id`，可通过 `get_batch_status` 查到 PENDING/RUNNING |
| `test_rank_by_jd_orders_desc` | 插入 3 条不同分数 | 返回列表按 overall_score DESC |
| `test_list_by_resume_returns_all_jds` | 一个 resume 对 2 个 JD 生成过分 | 返回 2 条 |

---

## 6. S4-07 + S4-08｜API 集成测试

**测试文件**：`backend/tests/test_match_api.py`、`backend/tests/test_match_ranking_api.py`

| 用例 | 输入 | 期望 |
|-----|------|------|
| `test_post_match_score_returns_201` | POST `/api/v1/match-scores` body `{jd_id, resume_id}` | 201（或 200），响应符合 `MatchScoreResponse` |
| `test_post_match_score_404_when_jd_missing` | 不存在的 jd_id | 404 |
| `test_post_match_score_404_when_resume_missing` | 不存在的 resume_id | 404 |
| `test_post_match_score_409_when_resume_not_parsed` | resume 状态 PARSING | 409 |
| `test_post_match_score_idempotent_without_force` | 连续两次相同 body | 两次响应 `score_id` 相同 |
| `test_post_match_score_force_recomputes` | 第二次带 `force=true` | LLM 打桩再次调用；`updated_at` 变更 |
| `test_post_batch_match_returns_task_id` | POST `/api/v1/match-scores/batch` body `{jd_id, limit:2}` | 202，body 含 `task_id` |
| `test_get_batch_status_transitions` | 提交后立即 GET | 状态 ∈ {PENDING, RUNNING, COMPLETED} |
| `test_get_score_by_id_returns_row` | GET `/api/v1/match-scores/{id}` | 200，字段完整 |
| `test_get_score_by_id_404` | 不存在 | 404 |
| `test_jd_ranking_orders_desc` | 3 分数，GET `/api/v1/jds/{jd_id}/ranking` | items 按分数 desc |
| `test_jd_ranking_pagination` | `limit=1&offset=1` | 返回第 2 条 |
| `test_resume_matches_returns_multi_jds` | 一个简历 vs 2 JD | 返回 2 条，按分数 desc |
| `test_routes_order_specific_before_dynamic` | GET `/api/v1/match-scores/batch/xxx` | 走批量状态处理，而非被 `/{score_id}` 拦截 |

---

## 7. S4-09｜前端测试基线

**测试文件**：`frontend/tests/example.smoke.test.tsx`、`frontend/tests/setup.smoke.test.ts`

| 用例 | 输入 | 期望 |
|-----|------|------|
| `test_placeholder_component_renders` | 渲染 `PlaceholderPage` | 文本 "评分报告" 存在（若换测试组件，替换成对应字符串） |
| `test_msw_server_intercepts_get` | MSW 拦截 `/api/hello` → 返回 `{msg: 'hi'}` | fetch 返回一致 |
| `test_alias_import_works` | 用 `@/components/PlaceholderPage` import | 能加载 |

**通过标准**：`npm run test` ≥ 1 用例通过；`npm run lint && npm run build` 无报错。

---

## 8. S4-10｜前端 API service 测试

**测试文件**：`frontend/tests/services/match.test.ts`

| 用例 | MSW 拦截 | 期望 |
|-----|---------|------|
| `test_matchApi_matchOne_serializes_body` | POST `/match-scores` 回显 body | 断言请求 body 与传入一致；响应转 `MatchScore` 保留字段 |
| `test_matchApi_rankByJd_reads_items` | GET `/jds/:id/ranking` 返回固定 list | `items.length === 3`，`items[0].overall_score` 类型 number |
| `test_matchApi_batchMatch_returns_task_id` | POST `/match-scores/batch` → `{task_id:'t1', ...}` | 返回值 `task_id === 't1'` |
| `test_matchApi_getBatchStatus_polls_completed` | 前 2 次 RUNNING，第 3 次 COMPLETED | 组件层可退出轮询（结合 utility test） |

---

## 9. S4-11｜`ScoringReport.tsx` 组件测试

**测试文件**：`frontend/tests/pages/ScoringReport.test.tsx`（配合 MSW handlers）

| 用例 | 交互 | 期望 |
|-----|------|------|
| `test_scoring_report_shows_empty_state_without_jd` | 首次渲染 | 显示"请选择 JD"提示；无表格数据行 |
| `test_scoring_report_loads_ranking_after_jd_select` | 选择 JD → 触发 API | Table 渲染候选人列表；显示 overall_score |
| `test_scoring_report_triggers_batch_and_polls` | 点击"批量匹配" | 弹出提示 → 轮询状态 → 完成后自动刷新排名 |
| `test_scoring_report_opens_detail_drawer` | 点击某行"详情" | Drawer 打开，展示 3 维度 rationale |
| `test_scoring_report_marks_stale_row` | Mock 返回 `is_stale=true` | 行显示"简历已更新"标签 |

---

## 10. S4-12｜`Resumes.tsx` / `ResumeDetail.tsx` 测试

**测试文件**：`frontend/tests/pages/Resumes.match.test.tsx`、`frontend/tests/pages/ResumeDetail.match.test.tsx`

| 用例 | 交互 | 期望 |
|-----|------|------|
| `test_resumes_score_ring_shows_dash_without_jd` | 无 JD 选中 | 每行 `ScoreRing` 位置显示 `-`，DOM 无随机数 |
| `test_resumes_score_ring_uses_real_match_score` | Mock rankByJd 返回 `{resume_id: 'r1', overall_score: 82}` | `r1` 行显示 82 |
| `test_resumes_no_math_random_in_source` | 单测辅助：`Resumes.tsx` 源码扫描 | 不出现 `Math.random(` 字符串（通过读取文件断言，可与 vitest snapshot 结合） |
| `test_resume_detail_match_panel_default_selects_recent_jd` | 打开详情页 | 匹配面板默认选中最新 JD，展示当前简历评分或"未评分"按钮 |
| `test_resume_detail_match_panel_trigger_creates_score` | 点击"生成评分" | MSW 拦截 POST `/match-scores`，Drawer 内显示新分数 |

---

## 11. 覆盖率与最终通过标准

- **后端**：`uv run pytest` 收集 ≥ 20 用例并全绿；Ruff `check .` 无 error；关键路径覆盖 ≥ 80%（`pytest --cov=app.services.match --cov=app.api.v1.endpoints.match --cov=app.agent.skills.jd_candidate_matching --cov-report=term-missing`）。若引入覆盖率工具，测试补丁一起提交。
- **前端**：`npm run test` ≥ 15 用例并全绿；`npm run lint && npm run build` 通过。
- **联调**：`docker compose up -d` → 后端 `uvicorn` → 前端 `npm run dev` → 端到端手动验证清单：
  1. 上传 1 份简历（PARSED）；生成 1 个 JD。
  2. 打开 `/scores`，选择该 JD，触发单点匹配 / 批量匹配。
  3. 排名表格显示；打开详情 Drawer 见 3 维度。
  4. 打开 `/resumes` 选择同一 JD，`ScoreRing` 显示真实分。
  5. 打开 `/resumes/{id}` 详情页，匹配面板可再次触发/展示。

---

## 12. 测试→实现映射汇总

| Task | 测试文件（先写）| 实现文件（后写） |
|------|----------------|-----------------|
| S4-02 | `test_match_score_model.py` | `app/models/match_score.py` + 迁移 |
| S4-03 | `test_match_schemas.py` | `app/schemas/match.py` |
| S4-04 | `test_jd_candidate_matching_skill.py` | `app/agent/skills/jd_candidate_matching/v1_0_0/*` |
| S4-05 | `test_health.py`、`test_smoke_*.py` | `tests/conftest.py`、`tests/factories.py` |
| S4-06 | `test_match_service.py` | `app/services/match.py` |
| S4-07 | `test_match_api.py`、`test_match_ranking_api.py` | `app/api/v1/endpoints/match.py`（+ jd/resume endpoints 补丁） |
| S4-09 | `frontend/tests/example.smoke.test.tsx` | `frontend/tests/setup.ts` + vite.config.ts test 段 |
| S4-10 | `frontend/tests/services/match.test.ts` | `frontend/src/services/match.ts` + types |
| S4-11 | `frontend/tests/pages/ScoringReport.test.tsx` | `frontend/src/pages/ScoringReport.tsx` + 子组件 |
| S4-12 | `frontend/tests/pages/Resumes.match.test.tsx`、`ResumeDetail.match.test.tsx` | 修改对应 pages |
