# MVP 端到端手工验收清单（Stage 5.1 · PR-22）

> 用途：本地起服后，按 §1→§9 顺序走完**真实数据链路**，确认 MVP 可 demo。
> 适用分支：`feat/pr-22-s51-mvp-release-prep`（仅隐藏空壳页 + 文档，不改后端逻辑）。
> 后端契约以 `backend/app/api/v1/agent.py` 与 `app/schemas/agent.py` 为准；前端路由以 `frontend/src/App.tsx` 为准。
> 每个 step 给出：**入口** · **操作** · **预期结果** · **失败排查**。
> 发现非本 PR scope 的新 bug → 回填 §10 登记表，并追加到 `HANDOFF.md §9.3`（PR 不修）。

---

## §1 环境前置（3 步起服 + 健康检查）

**入口**：终端（非 UI）

**操作**
1. 基础设施：`docker compose up -d postgres redis`（无 compose 时：`pg_ctl`/`psql` 起 PG + `redis-server` 起 Redis；PG 需 `pgvector` 扩展就绪）。
2. 后端：`cd backend && cp .env.example .env`（填入 `LLM_API_KEY`/`LLM_BASE_URL`）`&& uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8000`。
3. 前端：`cd frontend && npm i && npm run dev`（Vite :5173，代理 `/api` → :8000）。

**预期结果**
- `GET http://localhost:8000/api/v1/health` → `{"status":"ok"}`。
- 浏览器打开 `http://localhost:5173`，左侧 sidebar **仅显示 5 个 MVP 页**（看板 / 对话 / JD / 简历 / 评分）+ 候选沟通（phase2）；6 个空壳页（推送反馈、数据看板、系统设置、面试安排、流程跟踪、对比分析）不可见。

**失败排查**
- health 非 ok → 查 `backend/backend.err`；多为 PG 连接串 `DATABASE_URL` 或 `pgvector` 未装。
- sidebar 仍见空壳页 → 确认当前在 `feat/pr-22-*` 分支构建；`npm run dev` 热更新若未生效，重启 Vite。
- LLM 调用 500 → `.env` 缺 `LLM_API_KEY`/`LLM_BASE_URL`；见 `app/agent/llm_adapter.py` 报错 "LLM is not configured"。

---

## §2 JD 创建（自然语言生成 → 落库 jds）

**入口**：`http://localhost:5173/chat`（ChatCenterPage）→ 自然语言描述岗位需求；或 `http://localhost:5173/jds/generate` 表单。

**操作**
1. 在 `/chat` 输入如「帮我生成一个 Python 后端工程师的 JD，要求 3 年经验、熟悉 FastAPI」。
2. 若走 generate 页：填 `position_title`/`department` 等字段提交。

**预期结果**
- 后端 `POST /api/v1/jds/generate` 返回 `jd_id`（如 `jd-xxxxxxxx`）。
- 数据库 `jds` 表新增一行，`status` 为已生成；`/jds` 列表可见该 JD。

**失败排查**
- 生成超时/无响应 → LLM 连通性（§1）；`LLM_MAX_TOKENS` 默认 4096。
- 返回 422 → 请求体字段缺失；对照 `app/schemas/jd.py` 的 `JDGenerateRequest`。

---

## §3 简历上传 + 解析（落库 resumes + candidates）

**入口**：`http://localhost:5173/resumes`（ResumesPage）→ 上传文件。

**操作**
1. 上传一份简历文件（PDF/Word）。`POST /api/v1/resumes/upload`（multipart `file`）。

**预期结果**
- 返回 `resume_id` 与 `candidate_id`。
- `resumes` 表新增解析记录；`candidates` 表新增/复用候选人；`/resumes` 列表可见，点进 `/resumes/:id` 见解析字段。

**失败排查**
- 上传 500 → 查 MinIO 配置（`MINIO_*`）或文件解析异常 `parse_error`；见 `app/schemas/resume.py`。
- 候选人未去重 → 同名不同人属正常；去重/合并见 §4.2 candidate-merge。

---

## §4 Chat 自然语言触发（3 个 skill 分开走）

> 三个 skill 依赖前置数据不同，**分别触发、分别验收**，不要混在一次对话里。

### §4.1 candidate-profile（需先有**单**简历）
**入口**：`/chat`，已上传 1 份简历后输入「为这份简历生成候选人画像」。
**预期**：orchestrator 经 reason→plan 产出 PlanCard，task_type 含 `candidate-profile`；最终在候选人或产物区呈现画像文本。
**排查**：无 PlanCard → 意图未路由到该 skill；检查 `app/agent/skill_registry.py` 的 dispatchable skill 列表与 `task_type` 映射。

### §4.2 candidate-merge（需先有**多份同名**简历）
**入口**：`/chat`，先上传 2 份**同一候选人姓名**的简历，再输入「把这两份简历合并到同一个候选人」。
**预期**：触发 `candidate-merge`；`candidates` 表由多条合并为 1 条，`resumes` 仍保留多条但指向同一 `candidate_id`。
**排查**：未合并 → 校验简历解析出的 `name` 字段是否一致；见 `app/services/resume.py` 去重逻辑。

### §4.3 jd-candidate-matching（需 JD + 简历**都在**）
**入口**：`/chat`，在 §2 生成 JD、§3 上传简历后输入「分析这份简历与这个 JD 的匹配度」。
**预期**：触发 `jd-candidate-matching`；产出匹配分析文本（技能匹配、差距等）。
**排查**：提示缺 JD/简历 → 确认 §2/§3 已落库；matching skill 依赖 `jd_id` 与 `resume_id` 同时存在。

---

## §5 PlanCard 确认 → dispatch → executions 落库

**入口**：`/chat` 中任一 skill 产出的 PlanCard。

**操作**
1. 在 PlanCard 勾选要执行的 step，点「确认/执行」。
2. 后端 `POST /api/v1/agent/execute-plan`，body `{task_id, accepted_steps}`。

**预期结果**
- 返回 `task_id`；`tasks` 表 `status` 进入 `executing`。
- `executions` 表按 accepted step 落库对应执行记录（`task_id`/`step_id` 关联）。
- 前端看板 `/` 出现该 task 卡片，状态随执行推进。

**失败排查**
- 确认后无 executions → 查 `execute-plan` 是否真把 step 写入 `executions`；见 `app/api/v1/agent.py` 与 `app/services` 写库逻辑。
- 看板不刷新 → 见 §6 SSE 断流排查。

---

## §6 SSE 事件全序列（8 类型 + terminal）

**入口**：前端自动订阅；手动核验可用 `curl`：
```
curl -N "http://localhost:8000/api/v1/agent/tasks/{task_id}/stream"
```

**预期结果**
- 事件类型覆盖 8 种（`app/schemas/agent.py::SSEEventType`）：
  `thinking` · `plan` · `tool_call` · `progress` · `result` · `error` · `warning` · `system`。
- 流以 **terminal 事件结束**：`GET /api/v1/agent/tasks/{task_id}` 的 `status` ∈ {`completed`,`cancelled`,`failed`}。
- Redis List `sse:buf:{task_id}` 缓冲事件（MAXLEN=200），terminal 后 TTL 3600s。

**失败排查**
- **SSE 断流 / 前端无进度** → 首要查 **Redis 连接**（`redis-cli ping`）；其次查 `HANDOFF.md §9.4 陷阱 11`：前端 SSE 消费必须用 **fetch + ReadableStream** 手动读，不能用 `EventSource`（其仅支持 GET 且对多行 `data:` 解析有坑，是历史断流根因）。
- 事件类型缺失 → 对照 `engine.py`/`act.py` 的 `emit(SSEEventType.*)` 调用点，确认 skill 是否真在执行。

---

## §7 skip-to-score 直接评分（match_scores 落库）

**入口**：看板 task 卡片「跳过执行直接评分」按钮；或 `POST /api/v1/agent/skip-to-score`。

**操作**
- body `{jd_id, candidate_ids}`（用 §2 的 `jd_id` 与 §3 的 `candidate_id`）。

**预期结果**
- 返回 `task_id`；后端 `_build_skip_plan` 构造 skip plan 并触发 scoring。
- `match_scores` 表落库一行（jd_id / resume_id / candidate_id / score 等）。

**失败排查**
- 评分 500 / `duplicate key ... uq_match_scores_jd_resume` → 同一 (jd,resume) 已存在评分；属已知约束（见 `backend/backend.err`），换不同简历或清表重试，本 PR 不修。
- 无 match_scores → 查 scoring 服务写库路径；见 `app/services/match.py`。

---

## §8 match_scores 落库校验

**入口**：`http://localhost:5173/scores`（ScoringReportPage）→ 查看 §7 落库的评分。

**预期结果**
- 列表出现 §7 的评分记录，含 `score` 与快照字段 `resume_updated_at_snapshot` / `jd_updated_at_snapshot`（见 `app/models/match.py`）。
- 点进详情可见完整匹配维度。

**失败排查**
- 快照字段为空 → 确认 scoring 时 JD/简历的 `updated_at` 已落库；非阻塞，记录到 §10。

---

## §9 CancelTask

**入口**：看板 task 卡片「取消」；或 `DELETE /api/v1/agent/tasks/{task_id}/cancel`。

**操作**
1. 对一个 `executing`/`scoring` 中（或 `WAITING_CONFIRMATION`）的 task 发起取消。

**预期结果**
- `GET /api/v1/agent/tasks/{task_id}` 的 `status` → `cancelled`。
- 全局并发计数器 `task:active`（`INCR`/`DECR`）正确回退，不卡后续任务（上限 10）。

**失败排查**
- 取消无效 → 确认走的是 `cancel_task`（`app/api/v1/agent.py`），且后台 `asyncio.create_task` 的 `orch-*` 任务已被取消信号中断；见 `HANDOFF.md` 全局并发段落。

---

## §10 通关判定 + 新 bug 登记表

**通关条件（全满足 = MVP demo 就绪）**
- [ ] §1 三步入服 + health ok + sidebar 仅 5+1 页
- [ ] §2 JD 生成落库
- [ ] §3 简历上传解析落库
- [ ] §4.1/4.2/4.3 三个 skill 分别触发成功
- [ ] §5 PlanCard 确认 → executions 落库
- [ ] §6 SSE 8 类型 + terminal 事件齐全
- [ ] §7 skip-to-score → match_scores 落库
- [ ] §8 评分详情可见（含快照字段）
- [ ] §9 CancelTask 生效，并发计数回退

**新 bug 登记（非本 PR scope，回填 HANDOFF §9.3）**

| # | 现象 | 复现 step | 疑似根因 | 处置 |
|---|------|-----------|----------|------|
| （例）| skip-to-score 重复 (jd,resume) 报 unique 冲突 | §7 | `uq_match_scores_jd_resume` 约束，无 upsert | 记追债项，本 PR 不修 |
|   |   |   |   |   |

> 登记表仅作本 PR 验收期间的临时记录；正式追债项请追加到 `HANDOFF.md §9.3`，本 PR 不修改 HANDOFF。
