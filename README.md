# recruitment-agent-2.0

AI 招聘助手：Python/FastAPI 后端 + React/TypeScript 前端，端到端覆盖 JD 生成、简历解析、自然语言编排（candidate-profile / candidate-merge / jd-candidate-matching）、PlanCard 确认执行、SSE 实时进度、skip-to-score 直接评分与 CancelTask。

> 详细架构、模块组织、构建/测试命令、编码规范见 [`AGENTS.md`](./AGENTS.md) 与 [`CLAUDE.md`](./CLAUDE.md)。
> 交接坑位、已知追债项、SSE 陷阱见 [`HANDOFF.md`](./HANDOFF.md)。

---

## MVP 快速上手（3 步起服）

### 1. 基础设施（Postgres + Redis）
```bash
docker compose up -d postgres redis
# 无 compose 时：pg_ctl / psql 起 PG（需 pgvector 扩展）+ redis-server 起 Redis
```

### 2. 后端（uv 管理，FastAPI :8000）
```bash
cd backend
cp .env.example .env          # 填入 LLM_API_KEY / LLM_BASE_URL
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
# 健康检查：GET http://localhost:8000/api/v1/health → {"status":"ok"}
```

### 3. 前端（Vite :5173，代理 /api → :8000）
```bash
cd frontend
npm install
npm run dev
# 打开 http://localhost:5173
```

---

## MVP 注意（Stage 5.1）

- **6 个空壳页已在 PR-22 隐藏**：推送反馈、数据看板、系统设置、面试安排、流程跟踪、对比分析（Stage 6/7 未实施）。sidebar 项为注释状态，功能落地后取消注释 `frontend/src/layouts/MainLayout.tsx` 中对应项即可恢复。
- 当前 MVP 可用的 5 个核心页 + 候选沟通：`看板 / 对话 / JD / 简历 / 评分` + `候选人沟通`。

---

## 文档导航

- **端到端手工验收清单**：[`docs/planning/stage5/MVP-VERIFY-CHECKLIST.md`](./docs/planning/stage5/MVP-VERIFY-CHECKLIST.md)（JD→简历→chat 触发 3 skill→PlanCard→executions→SSE→skip-to-score→match_scores→CancelTask）
- **项目概览 / 交接坑位**：[`HANDOFF.md`](./HANDOFF.md) §一 项目概览
- **贡献指南 / 命令 / 规范**：[`AGENTS.md`](./AGENTS.md)
- **架构与脚手架说明**：[`CLAUDE.md`](./CLAUDE.md)
- **规划文档目录**：[`docs/planning/`](./docs/planning/)

### 新增 skill 的三步走

1. **后端**：在 `backend/app/agent/orchestrator/engine.py` 的 `_ARTIFACT_TYPE_MAP` 新增一个 value（如 `'new_skill'`），对应 skill 名。
2. **codegen**：跑 `uv run python backend/scripts/gen_artifact_types.py`，自动更新前端 `frontend/src/types/agent.ts` 的 `ArtifactType` union（标记段 `// <auto-gen-artifacttype-start>` / `-end>` 之间，幂等，勿手改）。
3. **前端**：在 PlanCard / 产物卡片 `switch` 里加一个 `case` 渲染该 skill 的产物类型即可。
4. **内部 skill**：纯内部编排 skill（`orchestrator-{reason,reflect,plan,reflect-plan,reflect-act}`）标 `internal: true`，不进 `SkillRegistry.list_dispatchable()`，不要为其加前端 case。

---

## 常用命令速查

| 场景 | 命令 |
|------|------|
| 后端测试 | `cd backend && uv run pytest` |
| 后端 lint | `cd backend && uv run ruff check .` |
| 前端构建 | `cd frontend && npm run build` |
| 前端 lint | `cd frontend && npm run lint` |
| DB 迁移 | `cd backend && uv run alembic upgrade head` |
