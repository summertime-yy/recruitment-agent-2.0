# PR-22 KICKOFF · DECISION（执行体 Contract）

> 来源：`PR22-KICKOFF-QUESTIONS.md`（executor `5fc7238`）+ `PR22-KICKOFF-REVISIONS.md`（commander）
> base：master `7198737`
> 状态：**contract · 批准后起 `feat/pr-22-s51-mvp-release-prep`**
> 交付面：MVP release 准备（sidebar 隐藏 + 端到端验收清单 + 根 README）

---

## §一 交付面

| # | 交付项 | 具体动作 | 归属 |
|---|--------|---------|------|
| 1 | 前端 sidebar 隐藏 6 空壳页 | 注释 `MainLayout.tsx` 6 项 + 整组注释 analytics-group 标题；路由 `App.tsx` 保留不动 | frontend |
| 2 | 端到端验收清单 | 新建 `docs/planning/stage5/MVP-VERIFY-CHECKLIST.md`（10 节结构） | docs |
| 3 | 项目根 README | 新建 `README.md`（项目定位 + 3 步起服 + 4 文档链接） | docs |
| 4 | ~~docker-compose~~ | 已存在，**跳过** | — |
| 5 | ~~backend/.env.example~~ | AGENTS.md 对齐根份，**不新增**（README 写清 copy 路径） | — |

---

## §二 契约明细

### §2.1 前端 sidebar 注释规则（MainLayout.tsx）

按 QUESTIONS §一 表格 6 项：

- **注释 sidebar item** L37（push）、L41（analytics）、L42（settings）、L46（interview）、L48（workflow）、L49（compare）。
- **整组注释 analytics-group**（含 L40-42 分组结构 + `nav-group-label` 标题行）。
- **保留 phase2-group 标题** + 仅剩 candidate-chat 一项。
- 每处（sidebar item + 分组标题）上方加一行统一注释：
  ```tsx
  // Stage 6/7 未实施 · MVP 隐藏（PR-22）——功能落地后取消注释即可恢复
  ```

`App.tsx` 的 6 条 `<Route>` **不动**（PlaceholderPage 组件仍作友好占位兜底，直接 URL 访问不 404）。

### §2.2 验收清单文档结构（MVP-VERIFY-CHECKLIST.md）

10 节，每节固定 4 段：**入口 · 操作步骤 · 预期结果 · 失败排查**。

| 节 | 主题 | 关键要素 |
|----|------|---------|
| 1 | 起服自检 | backend :8000 `/docs`、frontend :5173、`docker compose ps`、`alembic current` = head、Redis `PING` |
| 2 | JD 创建 | `/jds/generate` → LLM 生成 → 落库 `jds` |
| 3 | 简历上传 | `/resumes` → 上传 2 份同名（为 merge 备料）→ 解析 → 落库 `resumes` |
| 4 | chat 触发 **candidate-profile** | 自然语言 → PlanCard → SSE 事件 → ResultCard |
| 5 | chat 触发 **candidate-merge** | 同上，前置：≥2 同名简历 |
| 6 | chat 触发 **jd-candidate-matching** | 同上，前置：JD+简历 |
| 7 | executions 落库核对 | SQL：`SELECT tool_name, status, started_at, finished_at FROM executions ORDER BY created_at DESC LIMIT 10;` |
| 8 | SSE 事件全序列 | `task_started → plan_created → plan_step_started → tool_call_* → plan_step_completed → result → task_finished`；断流排查提示（Redis 连接 + HANDOFF §9.4 陷阱 11 + `_background_execute` 回调） |
| 9 | skip-to-score | curl `POST /api/v1/agent/skip-to-score` + SQL 核对 `match_scores` 落库（PR-21 F1 回归证据） |
| 10 | CancelTask | 执行中取消 → 任务态 `CANCELLED` → SSE `task_finished(cancelled)` |

**尾部一节**："验收发现问题登记表"（模板：现象 · 复现步骤 · 疑似位置 · 建议追债编号），本 PR 只登记不修。

### §2.3 根 README.md 结构

```markdown
# Recruitment Agent 2.0
（一段项目定位：招聘领域垂直 agent · Stage 5 已交付 chat/JD/简历/匹配主流程）

## 快速上手（3 步）
### 1. 起服（PostgreSQL + Redis）
`docker compose up -d postgres redis`

### 2. 后端
```bash
cd backend
cp ../.env.example .env       # Windows: copy ..\.env.example .env
# 编辑 backend/.env 填写 LLM_API_KEY
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### 3. 前端
```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## MVP 验收
参考 [docs/planning/stage5/MVP-VERIFY-CHECKLIST.md](docs/planning/stage5/MVP-VERIFY-CHECKLIST.md)

## 开发者指南
- [AGENTS.md](AGENTS.md) — 仓库规范
- [HANDOFF.md](HANDOFF.md) — 进度与已知陷阱
- [docs/planning/PLAN-STAGE5.md](docs/planning/PLAN-STAGE5.md) — Stage 5 交付计划

## 注意
- minio 是 Stage 6 附件上传预留 · MVP 阶段可不起
- Stage 6/7 页面已在 sidebar 隐藏 · 恢复见 `frontend/src/layouts/MainLayout.tsx` 注释
```

---

## §三 commit 拆分（建议 3 commits）

| # | 类型 | 内容 |
|---|------|------|
| 1 | feat | sidebar 隐藏 6 空壳页（含 analytics-group 整组注释） |
| 2 | docs | 新建 `MVP-VERIFY-CHECKLIST.md`（10 节结构） |
| 3 | docs | 新建根 `README.md`（3 步起服 + 4 文档链接） |

commit 数 = 3，未超求助边界 #5（≤3）。

---

## §四 三门期望

| 门 | 期望 |
|----|------|
| pytest（后端） | `uv run pytest -q` → **131 passed / 1 skipped**（不动后端，不许波动） |
| ruff | `uv run ruff check .` → **0**（不动后端） |
| frontend build | `cd frontend && npm run build` → **通过**（sidebar 注释是 tsx 改动，必过） |
| （附加·非门）frontend lint | `cd frontend && npm run lint` → 0 warning（建议 executor 顺手跑，unused import 处理干净） |
| （附加·非门）frontend test | `cd frontend && npm run test` → 31 passed 不变（防回归） |

---

## §五 求助边界（stop-and-ask · 6 条）

触发以下任一即**停下报告、不擅自实现**：

1. 注释 sidebar 后 `npm run build` 出现 6 页之外的 TS 错误（暗示有隐藏依赖链）。
2. 手工验收清单撰写时发现第 9 节 skip-to-score 或第 8 节 SSE 在 master 上**实际跑不通**——记录现象即停，不顺手修。
3. `README.md` 或验收清单与已有文档（AGENTS.md、HANDOFF.md）出现指令冲突表述，需指挥官定口径。
4. 隐藏 sidebar 涉及 `MainLayout.tsx` 中 6 项之外的结构性改动（如 Menu items 生成逻辑需重构才能注释）。
5. commit 数超 3。
6. 验收清单撰写过程中需要引用 `HANDOFF.md §9.3` 未覆盖的历史 bug（超出 §9.4 陷阱清单）以撰写"失败排查"提示——停，避免把非既定 bug 塞进验收文档。

---

## §六 base hash

`7198737`（PR-21 合入后的 master HEAD）

---

## §七 交付摘要模板（实现完填写）

```
分支：feat/pr-22-s51-mvp-release-prep
base：7198737
HEAD：<short hash>
三门：
  uv run pytest -q
  ... 131 passed, 1 skipped in X.XXs
  uv run ruff check .
  All checks passed!
  cd frontend && npm run build
  ✓ built in X.XXs
交付面：sidebar 隐藏 · 验收清单 · 根 README
手工验收（真跑）：10 节通过 X · 失败 Y · 登记 Z（若 Y>0 或 Z>0，尾节详列）
```

---

## §八 备注

- 本 PR 不碰 HANDOFF.md（新 bug 登记由指挥官合并后统一处理）。
- 本 PR 不引入 CI / pre-commit / short scripts（保持 MVP 阶段简单）。
- 本 PR 与 PR-23（Track B · Stage 5.1 P2）并行推进，零文件重叠，先合谁不阻塞后合谁。

---

*commander DECISION · 待批准后起分支实施*
