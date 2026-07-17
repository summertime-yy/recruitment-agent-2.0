# Stage 4 总体计划（PLAN）

> 版本：v1.0（Stage 4 试点计划）
> 更新时间：2026-07-16
> 作者：Lead Architect（Claude Code）
> 面向读者：执行智能体（Codex / Claude Code）+ 项目维护者
> 关联文档：`HANDOFF.md`、`AGENTS.md`、`docs/data-model.md`、`docs/api-contract.md`、`docs/development-roadmap.md`
> 配套：`docs/planning/TASKS.md`（任务清单）、`docs/planning/TEST-PLAN.md`（TDD 验证）

---

## 一、里程碑与 Stage 顺序

按路线图严格串行：**Stage 4 → 5 → 6 → 7**。本文件仅细化 **Stage 4（人岗匹配评分）**，Stage 5-7 保留高层规划锚点，后续单独产出各 Stage 的 PLAN 分册。

| 里程碑 | 交付物 | 状态 |
|-------|-------|------|
| **M4.0** 数据契约冻结 | `data-model.md §3.3 match_scores` + `api-contract.md` Stage 4 一节 完成对齐 | 待启动 |
| **M4.1** 后端骨架 | `match_scores` 表 + 模型 + 迁移 + Schema + Skill 定义（skill.yaml/prompt.md/examples.yaml） | 待启动 |
| **M4.2** 后端业务闭环 | `MatchService` + `/api/v1/match-scores` API 全绿 + pytest 覆盖 | 待启动 |
| **M4.3** 前端测试框架落地 | Vitest + @testing-library/react + jsdom 引入，首批测试可运行 | 待启动 |
| **M4.4** 前端评分报告页 | `ScoringReport.tsx` 完成；`Resumes.tsx` 置信度接入真实分；`ResumeDetail.tsx` 匹配面板 | 待启动 |
| **M4.5** Stage 4 收尾 | 端到端联调、`HANDOFF.md` 同步、覆盖率 ≥ 目标线 | 待启动 |

**Stage 5-7 展望（不在本次实施范围内）**：
- Stage 5：Task Orchestrator（R-P-R-A-R）+ SSE，将 `jd-candidate-matching` Skill 编排为「筛选 → 评分 → 报告」子任务。
- Stage 6：`communications` + `feedback` 表，将 Stage 4 输出的 top-N 候选人推入沟通流。
- Stage 7：analytics 看板消费 `match_scores` 与 `skill_execution_logs` 中的运行时指标。

---

## 二、关键架构决策（Stage 4）

### 决策 1：`match_scores` 直接引用 `resumes.resume_id`，不引入独立 `candidates` 表

**背景**：`docs/data-model.md §3.2` 原规划了独立 `candidates` 表；但 Stage 3 实际交付将候选人相关字段（`candidate_status`、`tags`、`source`、`dedup_status`、`duplicate_of_resume_id`）合并到 `resumes` 表，并新增 `candidate_status_history`、`candidate_notes` 两张扩展表。

**决策**：Stage 4 顺应现状，**`match_scores.resume_id VARCHAR(50) FK → resumes.resume_id`**，不新建 `candidates` 表。原 `data-model.md §3.2/§3.3` 需在 Task **S4-01** 中同步修订。

**理由**：
1. 保持数据模型与代码的唯一事实源一致，避免引入未使用的表。
2. 简历级别的匹配天然由 `resume_id` 定位；未来若引入「同一候选人多简历」的合并逻辑，可通过 `duplicate_of_resume_id`/合并 Skill 在数据层做投影，无需破坏 `match_scores` 契约。
3. 避免多余 FK 引发的迁移风险。

**代价**：与 `docs/development-roadmap.md §六.6.1` 原表述略有偏差，需以本决策修订文档。

### 决策 2：Skill 契约唯一，Prompt 与 Schema 全部落 YAML

**决策**：新增 Skill `jd-candidate-matching` v1.0.0，目录固定 `backend/app/agent/skills/jd_candidate_matching/v1_0_0/`，包含：
- `skill.yaml`：input_schema / output_schema / 元数据 / `max_retries: 0`（对齐 `AGENTS.md` LLM 契约）
- `prompt.md`：System Prompt + `---USER_TEMPLATE---` 分隔的 Jinja2 用户模板
- `examples.yaml`：至少 2 组 few-shot（1 组"高匹配"，1 组"低匹配"，用于稳定输出结构）

**理由**：与 Stage 1/2 现有 Skill 保持一致的加载路径（`SkillRegistry` 自动发现最高 `v*` 版本），复用 `BaseSkill` 的输入/输出校验、合规检查、执行日志。

### 决策 3：评分维度固化为 4 项

**决策**：`overall_score`（0-100 综合分）+ `dimension_scores` JSON：
```json
{
  "skill_match":       {"score": 0-100, "matched": [...], "missing": [...], "rationale": "..."},
  "experience_match":  {"score": 0-100, "years_required": "...", "years_actual": "...", "rationale": "..."},
  "education_match":   {"score": 0-100, "required": "...", "actual": "...", "rationale": "..."},
  "overall_reasoning": "..."
}
```
**综合分**：`overall_score = round(0.5*skill + 0.3*experience + 0.2*education, 1)`（在 Service 层再计算一次，兼容 Skill 输出偏差）。

**理由**：4 维覆盖 HR 主流决策要素，且与 `docs/development-roadmap.md §六.6.2` 原文一致；权重明确写入 Service，不进 Prompt，方便未来调参。

### 决策 4：触发模式支持"单点触发"与"JD 批量"

**决策**：
- `POST /api/v1/match-scores`：**单点触发**（body: `{jd_id, resume_id, force?}`），同步返回评分详情。
- `POST /api/v1/match-scores/batch`：**JD 视角批量**（body: `{jd_id, resume_ids?, limit?, force?}`），后台任务并发调用 Skill，返回 `task_id` 供轮询；不做 SSE，Stage 5 再引入。
- `GET /api/v1/match-scores/{score_id}`、`GET /api/v1/jds/{jd_id}/ranking`、`GET /api/v1/resumes/{resume_id}/matches`。

**幂等策略**：`(jd_id, resume_id)` 唯一约束；同一对再次触发默认返回缓存，`force=true` 才重新计算。

### 决策 5：先补 pytest 骨架，再实施新代码

**决策**：Stage 4 是补测试的最佳时机。Task **S4-05** 单独交付：
- `backend/tests/` 补 `test_health.py`、`test_jds_smoke.py`、`test_resumes_smoke.py` 三个「兜底 smoke」测试，保证 `uv run pytest` 至少收集非零用例；
- 引入 `backend/tests/factories.py`（工厂函数，构造 JD/Resume 测试夹具），供后续任务复用；
- 配置内存 SQLite 或替换 async session（如复杂度高，允许保留 PostgreSQL 但用 `pytest.mark.integration` 分组）——建议**优先内存 SQLite**，将 async engine URL 通过 fixture 覆写。

### 决策 6：前端引入 Vitest 作为测试框架

**决策**：Task **S4-09** 一次性引入前端测试基础设施：
- 依赖：`vitest`、`@vitest/ui`（可选）、`jsdom`、`@testing-library/react`、`@testing-library/jest-dom`、`@testing-library/user-event`、`@types/node`。
- 配置：`vite.config.ts` 增加 `test` 段（`environment: 'jsdom'`、`globals: true`、`setupFiles: 'tests/setup.ts'`）；`package.json` 加 `"test": "vitest run"`、`"test:watch": "vitest"`。
- 位置：测试放 `frontend/tests/`（与 AGENTS.md 一致）；命名 `<Component>.test.tsx` / `<module>.test.ts`。
- Mock：使用 `msw`（Mock Service Worker）拦截 `/api/*`——先加最小 mock，不上完整场景，避免任务膨胀。

**理由**：Vitest 与 Vite 生态天然集成，无需额外 babel/transform；team 已用 `@/` alias，Vitest 支持自动读取 `vite.config.ts` 的 alias。

### 决策 7：LLM 调用层严守既有踩坑约定

- `max_retries=0` 在 `skill.yaml` 与 `llm_adapter` 两处都必须显式为 0。
- 不传 `reasoning_effort`。
- Skill 内 Prompt 显式要求"只输出 JSON 对象"，与既有 `jd-generation` 保持一致。
- `LLM_MAX_TOKENS=4096` 已够（Skill 输出为结构化维度分，量级远小于 JD 生成）。

### 决策 8：FastAPI 路由顺序与已验证约定对齐

- `/api/v1/match-scores/batch`、`/api/v1/match-scores/{score_id}` 的具体路径必须在 `/{score_id}` 前定义。
- `/api/v1/jds/{jd_id}/ranking` 与 `/api/v1/resumes/{resume_id}/matches` 挂在既有 `jd_router` / `resume_router` 之外，用新 `match_router`，避免污染现有路由排序。

---

## 三、双路径调用中的定位

Stage 4 仍走**直接调用路径**（REST → Service → Skill → LLM），不引入 Orchestrator。Stage 5 引入 Orchestrator 后，会将 `POST /api/agent/skip-to-score` 直接路由到本 Stage 的 Service，复用现有实现。

---

## 四、依赖矩阵

| 依赖类型 | 项目 | 状态 |
|---------|------|------|
| 前置 Stage | Stage 1（jds 表）、Stage 3（resumes+候选人字段） | ✅ 已完成 |
| 数据库 | PostgreSQL（复用 docker compose） | ✅ 已就绪 |
| Skill 框架 | `BaseSkill` / `SkillRegistry` | ✅ 已就绪 |
| LLM 适配器 | `llm_adapter.call_llm_json` | ✅ 已就绪 |
| 前端组件库 | AntD 5、React Router v6、Axios | ✅ 已就绪 |
| 新增前端依赖 | vitest、@testing-library/react、jsdom、msw | ⏳ 由 S4-09 引入 |
| 新增后端依赖 | 无（Skill 定义即够；如需 SQLite 测试可加 `aiosqlite`） | ⏳ 可选，由 S4-05 决定 |

---

## 五、风险清单与缓解

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | LLM 输出维度分抖动 | 综合分不稳 | Skill 层：详细 few-shot + JSON Schema 校验；Service 层：`overall_score` 用固定权重覆盖计算 |
| R2 | 批量匹配耗时/并发压 LLM | 超时/费用 | 批量任务限流（并发 ≤ 4），支持 `limit` 参数；短期不接 SSE，改用轮询 |
| R3 | 简历/JD 后续被编辑，`match_scores` 过期 | 用户看到脏数据 | 增加 `is_stale` 字段（对比 `updated_at`）或 `skill_execution_id` 追溯；PLAN v1 采用**在 API 响应中携带 `computed_at` + `resume_updated_at`**，由前端提示"简历已更新，可重新评分" |
| R4 | 无独立 `candidates` 表带来的语义偏差 | 影响文档理解 | S4-01 明确修订 `data-model.md`，把"候选人"字段视为 `resumes` 的一部分，`match_scores.resume_id` 直连 resumes |
| R5 | pytest 从 0 到有的迁移成本 | 拖慢 Stage 4 | 把测试基线单独拆为 S4-05；引入内存 SQLite fixture 覆盖 async engine；LLM 调用一律 mock（`patch("app.agent.llm_adapter.call_llm_json")`） |
| R6 | 前端引入 Vitest 可能与 tsc 冲突 | 构建失败 | 使用 `vitest` 3.x（兼容 vite 6），`tsconfig` 中把 `tests/**` 归入 `include`；测试类型 `@types/testing-library__jest-dom` |
| R7 | `Resumes.tsx` ScoreRing 需 JD 上下文才能取真实分 | 列表页体验 | 在筛选栏新增 JD 选择器；未选时保留占位符（无分数显示"-"），移除 `Math.random()` |
| R8 | 数据库迁移与已有 head `113702a6d427` 的 down_revision 冲突 | 迁移失败 | 新迁移 `down_revision='113702a6d427'`；`autogenerate` 前先 `alembic current` 验证 |

---

## 六、技术选型汇总

| 层级 | 选型 | 说明 |
|-----|------|------|
| Skill 定义 | YAML（skill.yaml + prompt.md + examples.yaml） | 复用 Stage 1/2 模式 |
| ORM | SQLAlchemy 2.0 async | 无变更 |
| 迁移 | Alembic autogenerate（人工 review） | 无变更 |
| API 层 | FastAPI + Pydantic v2 | 无变更 |
| 后端测试 | pytest + pytest-asyncio（`asyncio_mode=auto`）+ httpx `AsyncClient`（`ASGITransport`） | 现有 `conftest.py` 已给出 client fixture |
| 后端测试 DB | 优先 **内存 SQLite via aiosqlite**（隔离、快），如遇 JSONB/pgvector 兼容问题则退化为 PostgreSQL + 事务回滚 fixture | S4-05 决定 |
| 前端测试 | **Vitest** + `@testing-library/react` + `jsdom` + `msw` | S4-09 引入 |
| 前端 Mock | msw（Service Worker）拦截 axios 到 `/api/*` | 与真实运行时行为一致 |
| CI（可选） | 保持本地 `uv run pytest` + `npm run test` + `npm run lint && npm run build` | 暂不引入 GH Actions |

---

## 七、执行顺序清单（建议）

执行智能体按下表 **自上而下** 领取任务；同一里程碑内可并行，跨里程碑必须串行。

| 顺序 | Task ID | 里程碑 | 说明 |
|-----|---------|--------|------|
| 1 | S4-01 | M4.0 | 更新 `docs/data-model.md` 与 `docs/api-contract.md`，冻结 `match_scores` 与 API 契约 |
| 2 | S4-05 | M4.0 | 后端 pytest 基线（不阻塞 M4.1，但强烈推荐先做） |
| 3 | S4-02 | M4.1 | `match_scores` 模型 + Alembic 迁移 |
| 4 | S4-03 | M4.1 | Pydantic Schema（请求/响应 DTO） |
| 5 | S4-04 | M4.1 | `jd-candidate-matching` Skill（skill.yaml + prompt.md + examples.yaml） |
| 6 | S4-06 | M4.2 | `MatchService`（单点/批量/查询/排行） |
| 7 | S4-07 | M4.2 | API 路由（`/api/v1/match-scores` + JD/Resume 视角） |
| 8 | S4-08 | M4.2 | API 集成测试全绿 |
| 9 | S4-09 | M4.3 | 前端 Vitest 基础设施（依赖、配置、setup、示例测试） |
| 10 | S4-10 | M4.4 | 前端 API service + TS 类型 |
| 11 | S4-11 | M4.4 | `ScoringReport.tsx` 页面实现 |
| 12 | S4-12 | M4.4 | `Resumes.tsx` 置信度接入真实分 + `ResumeDetail.tsx` 匹配面板 |
| 13 | S4-13 | M4.5 | 端到端联调、`HANDOFF.md` 更新、覆盖率检查 |

**分支约定**：Stage 4 允许拆成多个 PR 合并回 `master`，每个 PR 对应 1-3 个 Task；提交格式 `feat(match): ...` / `test(match): ...` / `docs(match): ...`。

---

## 八、Done-Definition（Stage 4 出口条件）

- [ ] `uv run pytest` 全绿，覆盖 Skill 单测、Service 单测、API 集成测试。
- [ ] `uv run ruff check .` 无 error。
- [ ] `npm run test` 全绿，`npm run lint && npm run build` 通过。
- [ ] `docs/data-model.md`、`docs/api-contract.md`、`HANDOFF.md` 与代码状态一致。
- [ ] 前端 `ScoringReport.tsx` 可选择 JD → 触发/查看候选人排名，且能进入单个匹配详情。
- [ ] `Resumes.tsx` 中 `ScoreRing` 已移除 `Math.random()`，改由真实 `match_scores` 供分（未选 JD 时显示"-"）。
- [ ] `ResumeDetail.tsx` 展示当前简历相对某个（默认最近）JD 的匹配报告。
- [ ] `match_scores` 表通过 Alembic 迁移创建，head 为新迁移；`alembic history` 与 `docs/data-model.md` 版本一致。

---

## 九、附：契约锚点（详见 TASKS.md / TEST-PLAN.md）

- 表：`match_scores`（PK: score_id VARCHAR(50)，格式 `ms_<uuid12>`）
- Skill ID：`jd-candidate-matching`，版本 `1.0.0`
- API 前缀：`/api/v1/match-scores`
- 前端页面：`/scores`（`ScoringReport.tsx`）
- Skill 目录：`backend/app/agent/skills/jd_candidate_matching/v1_0_0/`
