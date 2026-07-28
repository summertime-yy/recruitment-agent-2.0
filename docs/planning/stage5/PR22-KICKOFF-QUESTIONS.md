# PR-22 KICKOFF · 问题清单（QUESTIONS）

> 任务：MVP release preparation —— 隐藏空壳页 sidebar、端到端手工验收清单、MVP 快速上手 README
> 状态：**草稿 · 待指挥官 revisions**（docs-only，本文件 commit 到 master）
> base：master @ `7198737`
> 分支（DECISION 后拉）：`feat/pr-22-s51-mvp-release-prep`
> 路径：KICKOFF（本文件）→ REVISIONS（指挥官回）→ DECISION（执行体 contract）

---

## 〇 摘要（先给结论）

grep 复核后，**指令中的两处前提需要修正**：

1. **`frontend/src/router/` 目录不存在**。路由集中在 `frontend/src/App.tsx:69-83`（`<Route>` 平铺），
   sidebar 在 `frontend/src/layouts/MainLayout.tsx`。PR-22 前端改动集实为 **`App.tsx` + `MainLayout.tsx`** 两个文件。
2. **`docker-compose.yml` 已存在**（根目录，pgvector/pg15 + redis:7-alpine + minio 三服务）→ 交付面 5 **跳过**。
   `.env.example` 也在**根目录**已存在；但 **`backend/.env.example` 不存在**（AGENTS.md 却写着
   "Copy `.env.example` and set `LLM_API_KEY`"——指根目录那份）。交付面 4 需指挥官定位置口径（见 Q4b）。

其余交付面（隐藏 6 空壳页、验收清单、README）与指令一致，无阻塞。

---

## §一 6 个空壳页清单实证（Q1）

`grep PlaceholderPage frontend/src/` 全命中（组件本体 `components/PlaceholderPage.tsx` 除外）：

| # | 页面文件 | 路由（App.tsx） | sidebar 项（MainLayout.tsx） | 所在分组 |
|---|---------|----------------|------------------------------|----------|
| 1 | `pages/PushFeedback.tsx` | `/push`（L77） | `push · 推送反馈`（L37） | **核心流程**（core-group） |
| 2 | `pages/Analytics.tsx` | `/analytics`（L78） | `analytics · 数据看板`（L41） | 分析与设置（analytics-group） |
| 3 | `pages/Settings.tsx` | `/settings`（L79） | `settings · 系统设置`（L42） | 分析与设置（analytics-group） |
| 4 | `pages/InterviewSchedule.tsx` | `/interview`（L80） | `interview · 面试安排`（L46） | 更多功能（phase2-group） |
| 5 | `pages/WorkflowTrack.tsx` | `/workflow`（L82） | `workflow · 流程跟踪`（L48） | 更多功能（phase2-group） |
| 6 | `pages/CompareAnalysis.tsx` | `/compare`（L83） | `compare · 对比分析`（L49） | 更多功能（phase2-group） |

**注意两点**：
- `candidate-chat`（L47，phase2-group）**不是空壳页**——`pages/CandidateChat.tsx` 是 PR-19 的真实页面，**保留不隐藏**。
- 隐藏 6 项后各分组余量：core-group 剩 5 项（kanban/chat/jds/resumes/scores）、analytics-group 剩 **0 项**、
  phase2-group 剩 1 项（candidate-chat）。**analytics-group 会变成空分组**——分组标题
  （`nav-group-label`，L116-118）是否连带注释？phase2-group 只剩 1 项时分组标题"更多功能"是否保留？

**问 Q1**：上表 6 页清单确认？空分组（analytics-group）连带注释掉分组标题，phase2-group 保留标题 + 仅剩 candidate-chat，是否接受？

---

## §二 隐藏策略（Q2）

**Q2a · sidebar 隐藏方式**——同意指挥官倾向：**注释**（方案对比）：

- **(A) 注释 sidebar 项**（倾向）：diff 一目了然、零运维配置、Stage 6/7 实施时取消注释即回。注释上方加一行
  `// Stage 6/7 未实施 · MVP 隐藏（PR-22）——实施后取消注释`。
- (B) feature flag env：需 `import.meta.env` + `.env` 运维配置，MVP 阶段过度设计。
- (C) 永久删除：Stage 6/7 要恢复时还得考古，否决。

**Q2b · 路由是否连带处理**（指令未提，需定）：sidebar 注释后 `App.tsx` 的 6 条 `<Route>` 仍在——直接敲 URL
`/analytics` 依然能进空壳页。三个子选项：
- **(B1) 路由保留**（倾向）：空壳页本身有 `PlaceholderPage` 组件兜底（有"返回"按钮、文案友好），直接 URL 访问
  不算坏体验；且 6 个 page import 保留可避免 `noUnusedLocals` 报错连锁（不用动 import 行）。
- (B2) 路由也注释：则 6 个 `import` 语句必须同步注释（TS `noUnusedLocals` 会 fail build），diff 面扩大到 12+ 行。
- (B3) 路由改重定向到 `/`：额外逻辑，无必要。

**问 Q2**：确认 (A) 注释 sidebar + (B1) 路由保留？若指挥官要求"生产完全不可达"，则选 (B2)，我会连带注释 import。

---

## §三 验收清单粒度（Q3）

同意指挥官倾向：**3 个 skill 分开写**，理由（数据前置条件不同）：

| skill | 数据前置 | chat 触发语示例 |
|-------|---------|----------------|
| candidate-profile | ≥1 份已解析简历 | "帮我看下张三的候选人画像" |
| candidate-merge | ≥2 份**同名**简历（需先上传两份） | "合并张三的重复简历" |
| jd-candidate-matching | ≥1 JD + ≥1 简历 | "用 Python 后端 JD 匹配一下张三" |

清单章节结构（拟 10 节，每节 = 入口 URL + 操作步骤 + 预期结果 + 失败排查）：

1. 起服自检（backend :8000 `/docs`、frontend :5173、Redis PING、`alembic current` == head）
2. JD 创建（`/jds/generate` → LLM 生成 → 落库 `jds`）
3. 简历上传（`/resumes` → 上传 → 解析 → 落库 `resumes`；此处上传 2 份同名，为 merge 备料）
4. chat 触发 candidate-profile（PlanCard 确认 → SSE 事件序列 → ResultCard）
5. chat 触发 candidate-merge
6. chat 触发 jd-candidate-matching
7. executions 落库核对（SQL：`SELECT tool_name,status FROM executions ORDER BY created_at DESC`）
8. SSE 事件全序列核对（`task_started → plan_* → tool_call_* → result → task_finished`，含断流排查 → Redis 连接 & HANDOFF §9.4 陷阱 11）
9. skip-to-score 直接评分（REST 或 UI 入口 → `match_scores` 落库核对，PR-21 F1 修复的回归验证点）
10. CancelTask（执行中取消 → 任务态 `CANCELLED` → SSE `task_finished(cancelled)`）

**问 Q3**：10 节结构确认？第 9 节 skip-to-score 的入口——当前前端是否有 UI 触发点还是只能 curl
`POST /api/v1/agent/skip-to-score`？（grep 前端未见调用点，拟写 curl 命令作为入口，请确认可接受。）

---

## §四 README 位置（Q4）

**Q4a · 实证**：**根 `README.md` 不存在，`docs/README.md` 也不存在**。指令的"若顶层有就加章节，否则新建"
两个前提都落空，需定新建位置：
- **(A) 新建根 `README.md`**（倾向）：GitHub/克隆后第一眼可见，MVP 快速上手放根部最自然；内容 = 一段项目简介 +
  "MVP 快速上手"3 步 + 链接（`docs/planning/stage5/MVP-VERIFY-CHECKLIST.md`、`HANDOFF.md` §一、`AGENTS.md`）。
- (B) 新建 `docs/README.md`：藏在 docs 里，发现成本高。

**Q4b · `.env.example` 口径**：根 `.env.example` 已存在；`backend/.env.example` **不存在**。AGENTS.md 的表述
（"Copy `.env.example`"）指根目录那份 copy 到 `backend/.env`。两个选项：
- **(A) 不新增文件**（倾向）：README 起服步骤里写明 `cp .env.example backend/.env`（或 Windows `copy`），交付面 4 归零。
- (B) 补一份 `backend/.env.example`：与根份内容重复，双份维护漂移风险。

**问 Q4**：确认 (A) 根 README.md 新建 + (A) 不新增 .env.example、README 写清 copy 路径？

---

## §五 docker-compose / 短命令实证（Q5）

- `docker-compose.yml` **已存在**（根目录）：`pgvector/pgvector:pg15`（recruitment-postgres）+
  `redis:7-alpine`（recruitment-redis）+ `minio`（recruitment-minio）→ **交付面 5 跳过**，README 直接写
  `docker compose up -d postgres redis`（minio 对 MVP 验收非必需，是否连带起？拟写 `up -d` 全起，省判断）。
- 短命令：`frontend/package.json` scripts 仅 `dev/build/preview/lint/test/test:watch`，**无 `mvp` 类命令**；
  `backend/pyproject.toml` **无 `[project.scripts]`**；根目录**无 Makefile**。
- **不新增短命令**（倾向）：MVP 起服 3 步已足够短，加 script 是新维护面。

**问 Q5**：确认 compose 跳过 + 不新增短命令？README 里 `docker compose up -d`（全起含 minio）还是精确 `up -d postgres redis`？

---

## §六 验收中发现新 bug 的记录方式（Q6）

同意指令建议：**追加 HANDOFF §9.3 追债项，本 PR 不修**。具体操作口径：
- 验收清单文档尾部加一节"发现问题登记表"（模板：现象 / 复现步骤 / 疑似位置 / 建议追债编号）。
- 本 PR 的 STEP6 报告列出验收中实际发现的问题（若有），由指挥官决定是否入 HANDOFF §9.3。
- **本 PR diff 不触碰 HANDOFF.md**（HANDOFF 追加由指挥官合并后统一做，与 PR-21 惯例一致）。

**问 Q6**：此口径确认？

---

## §七 求助边界建议（Q7）

触发以下任一即停下报告、不擅自实现：

1. 注释 sidebar 后 `npm run build` 出现 6 页之外的 TS 错误（暗示有隐藏依赖链）。
2. 手工验收清单撰写时发现第 9 节 skip-to-score 或第 8 节 SSE 在 master 上**实际跑不通**（说明 PR-21 修复
   之外还有 live bug）——记录现象即停，不顺手修。
3. `docs/README.md` / 根 `README.md` 与已有文档（AGENTS.md、HANDOFF.md）出现指令冲突表述，需指挥官定口径。
4. 隐藏 sidebar 涉及 `MainLayout.tsx` 中 6 项之外的结构性改动（如 Menu items 生成逻辑需重构才能注释）。
5. commit 数超预期（本 PR 拟 ≤3 commits：sidebar 注释 + 验收清单 doc + README doc，若超说明 scope 失控）。

---

## §八 三门期望核对

- **测试**：`uv run pytest -q` → 131 passed / 1 skipped（本 PR 不动后端代码，不许波动）。
- **Lint**：`uv run ruff check .` → 0（同样不应有波动）。
- **Build**：`cd frontend && npm run build` → 通过（sidebar 注释是 TS 改动，必过此门）。
- **补充问**：`frontend` 已有 vitest（`npm run test`，PR-19 引入）——是否把 `npm run test` 也纳入本 PR 门？
  （sidebar 改动理论上不碰已测组件，倾向纳入，成本低防回归。）

---

## §九 待指挥官 REVISIONS 回答速览

- Q1：6 空壳页清单 + 空分组（analytics-group）标题连带注释口径？
- Q2：(A) 注释 sidebar + (B1) 路由保留？
- Q3：验收清单 10 节结构 + skip-to-score 用 curl 作入口？
- Q4：根 `README.md` 新建（两个 README 都不存在）+ 不补 `backend/.env.example`？
- Q5：compose 已存在跳过 + 不新增短命令 + `up -d` 全起还是只起 postgres redis？
- Q6：新 bug 只登记不修、本 PR 不碰 HANDOFF.md？
- Q7：求助边界 5 条确认/增删？
- Q8（补充）：`npm run test` 是否纳入三门？

---

*起草人：agent · 复核 base `7198737` · 状态：待 commander REVISIONS*
