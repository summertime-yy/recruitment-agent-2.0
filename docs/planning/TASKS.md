# Stage 4 任务拆解（TASKS）

> 版本：v1.0
> 更新时间：2026-07-16
> 关联：`docs/planning/PLAN.md`、`docs/planning/TEST-PLAN.md`
> 使用方式：执行智能体按下述任务卡逐条领取；**每卡必须先按 TEST-PLAN 编写测试再实现**（TDD）。

---

## 全局约束（每个 Task 都必须遵守）

- **Python**：Ruff `line-length=120`、`py311`、`snake_case`、async-first；LLM 调用统一走 `app/agent/llm_adapter.py`，`max_retries=0`，不传 `reasoning_effort`。
- **TypeScript**：`strict`、`noUnusedLocals`、`@/` 别名、命名导出、`PascalCase.tsx` 组件、`camelCase.ts` 工具。
- **Skill**：目录 `backend/app/agent/skills/<skill_id>/vX_Y_Z/`，`skill.yaml + prompt.md + examples.yaml`，不在 Python 里硬编码 prompt/schema。
- **测试先行**：任何"实现类"任务必须先在 `docs/planning/TEST-PLAN.md` 找到对应测试段，先写测试文件并让其红→再让它绿。
- **文档同步**：涉及 DB/API 变更必须同步 `docs/data-model.md` 或 `docs/api-contract.md`，与代码放同一 PR。
- **提交规范**：Conventional Commits，subject ≤ 72 字符。

---

## S4-01：冻结数据契约与 API 契约（M4.0）

- **目标**：把 `match_scores` 表与 Stage 4 API 契约写进"唯一事实源"文档，为后续所有编码任务提供锚点。
- **范围（修改/新建文件）**：
  - 修改：`docs/data-model.md`
    - 更新 §3.2「候选人表」：注明「Stage 3 实际未新建 candidates 表，候选人字段合并入 resumes；后续 Stage 引用候选人时使用 resume_id」。
    - 重写 §3.3「`match_scores` 表」为下方"字段清单"。
  - 修改：`docs/api-contract.md`
    - 新增第 4 节（或独立小节）「Stage 4 人岗匹配 API」，涵盖 5 个端点的路径/入参/响应/错误码。
- **接口契约**：
  - 表 `match_scores`：
    | 字段 | 类型 | 约束 | 说明 |
    |-----|------|------|------|
    | score_id | VARCHAR(50) | PK | 格式 `ms_<uuid12>` |
    | jd_id | VARCHAR(50) | FK → jds.jd_id, NOT NULL, ondelete=CASCADE | |
    | resume_id | VARCHAR(50) | FK → resumes.resume_id, NOT NULL, ondelete=CASCADE | |
    | overall_score | FLOAT | NOT NULL | 0-100 综合分（Service 层按权重重算） |
    | dimension_scores | JSON | NOT NULL | `{skill_match, experience_match, education_match, overall_reasoning}` |
    | matching_skill_id | VARCHAR(100) | NULL | 默认 `jd-candidate-matching` |
    | matching_skill_version | VARCHAR(20) | NULL | 如 `1.0.0` |
    | skill_execution_id | INTEGER | FK → skill_execution_logs.execution_id, NULL | |
    | resume_updated_at_snapshot | TIMESTAMP | NULL | 生成时的 resume.updated_at，用于陈旧判断 |
    | jd_updated_at_snapshot | TIMESTAMP | NULL | 同上 |
    | status | VARCHAR(20) | DEFAULT 'COMPLETED' | COMPLETED/FAILED/STALE |
    | error_message | TEXT | NULL | Skill 失败时的原因 |
    | created_at / updated_at | TIMESTAMP | NOT NULL | |
    - **唯一约束**：`UNIQUE(jd_id, resume_id)`。
    - **索引**：`idx_match_scores_jd_id_overall`（复合 `(jd_id, overall_score DESC)`）、`idx_match_scores_resume_id`。
  - API：
    | 方法 | 路径 | 说明 |
    |------|------|------|
    | POST | `/api/v1/match-scores` | 单点触发（body: `{jd_id, resume_id, force?}`），同步返回 `MatchScoreResponse` |
    | POST | `/api/v1/match-scores/batch` | JD 批量（body: `{jd_id, resume_ids?, limit?, force?}`），返回 `BatchTaskResponse{ task_id, total, submitted_at }` |
    | GET | `/api/v1/match-scores/batch/{task_id}` | 查批量任务状态（内存/DB 均可，PLAN v1 用轻量内存字典即可） |
    | GET | `/api/v1/match-scores/{score_id}` | 单条详情 |
    | GET | `/api/v1/jds/{jd_id}/ranking?limit=&offset=` | 按 overall_score DESC 排名 |
    | GET | `/api/v1/resumes/{resume_id}/matches?limit=` | 某简历对应的匹配列表（按 overall_score DESC） |
  - `MatchScoreResponse` Pydantic 字段：见 S4-03。
- **依赖任务**：无（起点任务）。
- **验收标准**：
  - 两份文档已包含 `match_scores` 完整 DDL 与 5 个 API 契约。
  - PR 单独提交，subject `docs(match): freeze stage4 match_scores data & api contract`。
- **DoD**：
  - 文档评审通过；`docs/planning/PLAN.md` 中"契约锚点"节的字段与本任务定义一致；Markdown lint 无警告。

---

## S4-02：`match_scores` 模型 + Alembic 迁移（M4.1）

- **目标**：按 S4-01 契约落地 SQLAlchemy 模型与迁移。
- **范围**：
  - 新建：`backend/app/models/match_score.py`（`MatchScore` 类，遵循 `TimestampMixin`）。
  - 修改：`backend/app/models/__init__.py` 导出 `MatchScore`。
  - 新建迁移：`backend/alembic/versions/<rev>_add_match_scores_table.py`，`down_revision='113702a6d427'`。
- **接口契约**：
  - `class MatchScore(Base, TimestampMixin)`；主键生成器 `generate_match_score_id() -> "ms_<uuid12>"`。
  - `__table_args__` 包含 `UniqueConstraint("jd_id", "resume_id", name="uq_match_scores_jd_resume")`、两个 Index。
- **依赖任务**：S4-01。
- **验收标准**：
  - `uv run alembic upgrade head` 成功，`\d match_scores` 显示与文档一致。
  - `uv run alembic downgrade -1 && uv run alembic upgrade head` 双向可行。
  - Ruff 通过。
- **DoD**：
  - TEST-PLAN 中「模型层」用例（test_match_score_model_pk_prefix、test_unique_constraint 等）先失败后通过；Ruff/pytest 全绿。

---

## S4-03：Pydantic Schema（M4.1）

- **目标**：定义请求/响应 DTO。
- **范围**：
  - 新建：`backend/app/schemas/match.py`。
  - 修改：`backend/app/schemas/__init__.py` 导出。
- **接口契约（关键字段）**：
  ```python
  class DimensionScore(BaseModel):
      score: float = Field(..., ge=0, le=100)
      rationale: str
      # 各维度可选扩展字段
      matched: list[str] | None = None
      missing: list[str] | None = None
      required: str | None = None
      actual: str | None = None
      years_required: str | None = None
      years_actual: str | None = None

  class DimensionScoresPayload(BaseModel):
      skill_match: DimensionScore
      experience_match: DimensionScore
      education_match: DimensionScore
      overall_reasoning: str

  class MatchScoreRequest(BaseModel):
      jd_id: str = Field(..., max_length=50)
      resume_id: str = Field(..., max_length=50)
      force: bool = False

  class BatchMatchRequest(BaseModel):
      jd_id: str
      resume_ids: list[str] | None = None
      limit: int | None = Field(None, ge=1, le=200)
      force: bool = False

  class MatchScoreResponse(BaseModel):
      score_id: str
      jd_id: str
      resume_id: str
      overall_score: float
      dimension_scores: DimensionScoresPayload
      matching_skill_id: str | None
      matching_skill_version: str | None
      skill_execution_id: int | None
      resume_updated_at_snapshot: datetime | None
      jd_updated_at_snapshot: datetime | None
      status: str
      error_message: str | None
      is_stale: bool = False   # 由 Service 层比对 snapshot 与当前 updated_at 计算
      created_at: datetime
      updated_at: datetime
      model_config = {"from_attributes": True}

  class MatchRankingItem(BaseModel):
      score_id: str
      resume_id: str
      candidate_name: str | None
      overall_score: float
      dimension_scores: DimensionScoresPayload
      is_stale: bool
      created_at: datetime

  class MatchRankingResponse(BaseModel):
      jd_id: str
      total: int
      items: list[MatchRankingItem]

  class BatchTaskResponse(BaseModel):
      task_id: str
      jd_id: str
      total_submitted: int
      submitted_at: datetime

  class BatchTaskStatusResponse(BaseModel):
      task_id: str
      jd_id: str
      total: int
      completed: int
      failed: int
      status: str  # PENDING/RUNNING/COMPLETED/FAILED
      started_at: datetime
      finished_at: datetime | None
  ```
- **依赖任务**：S4-01。
- **DoD**：Pydantic 校验测试用例（TEST-PLAN §2）先红后绿；Ruff 通过。

---

## S4-04：`jd-candidate-matching` Skill（M4.1）

- **目标**：新增业务 Skill，输入 JD + 简历结构化数据，输出多维匹配分。
- **范围**：
  - 新建目录：`backend/app/agent/skills/jd_candidate_matching/v1_0_0/`
    - `skill.yaml`
    - `prompt.md`
    - `examples.yaml`
- **接口契约**：
  - `skill.yaml`：
    - `skill_id: jd-candidate-matching`，`version: "1.0.0"`，`max_retries: 0`。
    - `input_schema` 必填：`jd`（object，含 title/requirements/required_skills/preferred_skills/experience_years/education_requirement）、`resume`（object，含 candidate_name/parsed_content）。
    - `output_schema` 必填字段：`skill_match{score,rationale,matched[],missing[]}`、`experience_match{score,rationale,years_required,years_actual}`、`education_match{score,rationale,required,actual}`、`overall_reasoning`。所有 `score` 类型 number 且 0-100。
  - `prompt.md` 结构：
    - System Prompt 阐明"资深 HR 评分专家"角色、评分刻度、拒绝无根据推断的原则。
    - `---USER_TEMPLATE---` 分隔的 Jinja2 模板拼接 JD/简历文本。
  - `examples.yaml`：≥ 2 组 few-shot（一组"技能高度匹配 → 高分"，一组"经验不足 → 低分"）。
- **依赖任务**：S4-01（output schema 契约）。
- **DoD**：
  - Skill 目录被 `SkillRegistry` 自动加载（启动日志 `Loaded skill: jd-candidate-matching v1.0.0`）。
  - TEST-PLAN §3「Skill 单测」用例先红后绿（用 mock `call_llm_json` 断言输入渲染、输出校验、合规校验路径）。

---

## S4-05：后端 pytest 基线补齐（M4.0，可与 S4-01 并行）

- **目标**：让 `uv run pytest` 收集到 ≥ 3 个测试；引入通用 fixture 与工厂函数。
- **范围**：
  - 新建：`backend/tests/factories.py`（构造 JD、Resume、SkillExecutionLog 的工厂函数）。
  - 新建：`backend/tests/test_health.py`（GET /health 返回 200）。
  - 新建：`backend/tests/test_smoke_jds.py`、`backend/tests/test_smoke_resumes.py`（列表接口返回 200 且 items 是 list）。
  - 修改：`backend/tests/conftest.py`
    - 引入 `db_session` fixture（异步覆盖）。
    - 引入 async engine override：使用 `aiosqlite`（若 JSONB 兼容问题严重，允许改为使用现有 PostgreSQL 但用事务回滚）。
    - 引入 `mock_llm` fixture，`monkeypatch` 替换 `app.agent.llm_adapter.call_llm_json`。
  - 修改：`backend/pyproject.toml` dev deps 增加 `aiosqlite>=0.19.0`（若采用 SQLite 方案）。
- **接口契约**：无对外接口变更。
- **依赖任务**：无。
- **验收标准**：
  - `uv run pytest -v` 全绿且 collected ≥ 3。
  - `mock_llm` fixture 可被 Skill 层测试直接引入。
- **DoD**：Ruff/pytest 全绿；`backend/tests/README.md`（新建）简述如何写新测试。

---

## S4-06：`MatchService` 实现（M4.2）

- **目标**：封装单点/批量匹配、查询、排行的核心业务逻辑。
- **范围**：
  - 新建：`backend/app/services/match.py`（`MatchService` 类）。
  - 修改：`backend/app/services/__init__.py`（如存在）。
- **接口契约（关键方法签名）**：
  ```python
  class MatchService:
      def __init__(self, db: AsyncSession): ...

      async def match_one(self, jd_id: str, resume_id: str, *, force: bool = False) -> MatchScore: ...

      async def get_score(self, score_id: str) -> MatchScore | None: ...

      async def get_score_by_pair(self, jd_id: str, resume_id: str) -> MatchScore | None: ...

      async def rank_by_jd(self, jd_id: str, *, limit: int = 20, offset: int = 0) -> tuple[list[MatchScore], int]: ...

      async def list_by_resume(self, resume_id: str, *, limit: int = 20) -> list[MatchScore]: ...

      async def batch_match(
          self, jd_id: str, *, resume_ids: list[str] | None = None,
          limit: int | None = None, force: bool = False,
      ) -> BatchTaskHandle: ...

      def is_stale(self, score: MatchScore, *, jd_updated_at: datetime, resume_updated_at: datetime) -> bool: ...
  ```
- **实现细节**：
  - `match_one` 内部：
    1. 校验 JD/Resume 存在，Resume 必须 `parse_status='PARSED'` 才允许评分（否则抛业务错）。
    2. 若已存在 `(jd_id, resume_id)` 且 `force=False`，直接返回已存条目。
    3. 组装 Skill 输入，调用 `skill.execute()`。
    4. 校验并计算 `overall_score = round(0.5*skill + 0.3*experience + 0.2*education, 1)`。
    5. 写 `SkillExecutionLog`，写/更新 `MatchScore`。
  - 批量匹配：内存中维护 `batch_tasks: dict[str, BatchTaskState]`，用 `asyncio.Semaphore(4)` 限并发；`resume_ids` 缺省时默认取 `parse_status='PARSED' AND dedup_status IN ('NONE','IGNORED')` 的最近 `limit` 条。
- **依赖任务**：S4-02、S4-03、S4-04、S4-05。
- **DoD**：TEST-PLAN §4「Service 单测」用例先红后绿；Ruff 通过。

---

## S4-07：API 路由（M4.2）

- **目标**：暴露 S4-01 定义的 6 个端点。
- **范围**：
  - 新建：`backend/app/api/v1/endpoints/match.py`（`match_router`，`prefix="/match-scores"`）。
  - 修改：`backend/app/api/v1/endpoints/jd.py`（新增 `GET /{jd_id}/ranking`）。
  - 修改：`backend/app/api/v1/endpoints/resume.py`（新增 `GET /{resume_id}/matches`）。
  - 修改：`backend/app/api/v1/__init__.py`（`api_v1_router.include_router(match_router)`）。
- **路由顺序**：新端点必须在 `/{jd_id}` / `/{resume_id}` 参数化路径 **之前** 定义（FastAPI 路由顺序踩坑）。
- **依赖任务**：S4-06。
- **DoD**：TEST-PLAN §5「API 集成测试」用例先红后绿；HTTPExeption 状态码与契约一致（404 未找到、409 简历未解析、400 参数非法）。

---

## S4-08：后端 E2E/集成测试收敛（M4.2）

- **目标**：整合 S4-05 至 S4-07 的用例，跑一次完整回归。
- **范围**：无新代码，仅补测试与整理。
  - `backend/tests/test_match_scores_api.py`（若尚未合并到 S4-07 中）。
  - `backend/tests/test_match_ranking.py`。
- **依赖任务**：S4-06、S4-07。
- **DoD**：`uv run pytest -v` 全绿；Ruff 通过；PR 描述附覆盖率简表。

---

## S4-09：前端 Vitest 基础设施（M4.3）

- **目标**：一次性引入前端测试栈，为 S4-10 起的前端任务提供基础。
- **范围**：
  - 修改：`frontend/package.json` 增加 devDependencies：
    - `vitest`、`@vitest/ui`（可选）、`jsdom`、`@testing-library/react`、`@testing-library/jest-dom`、`@testing-library/user-event`、`@types/testing-library__jest-dom`、`msw`、`@types/node`。
    - `scripts` 增加 `"test": "vitest run"`、`"test:watch": "vitest"`、`"test:ui": "vitest --ui"`。
  - 修改：`frontend/vite.config.ts` 增加 `test` 段（`environment: 'jsdom'`、`globals: true`、`setupFiles: ['./tests/setup.ts']`、`css: false`）。
  - 修改：`frontend/tsconfig.json` 把 `tests` 目录纳入 `include`；确保 `types` 含 `["vitest/globals", "@testing-library/jest-dom"]`。
  - 新建：`frontend/tests/setup.ts`（`import '@testing-library/jest-dom'`；MSW server 启停钩子）。
  - 新建：`frontend/tests/mocks/server.ts`、`frontend/tests/mocks/handlers.ts`（初始占位）。
  - 新建：`frontend/tests/example.smoke.test.tsx`（渲染任意组件，断言存在，作为流水线兜底）。
- **接口契约**：无。
- **依赖任务**：无（可与 S4-01/S4-05 并行）。
- **验收标准**：
  - `npm run test` 至少通过 1 个用例。
  - `npm run lint && npm run build` 保持通过。
- **DoD**：新增 `frontend/tests/README.md`；`AGENTS.md` 若涉及前端测试指引可小幅补充（可选）。

---

## S4-10：前端 API service + 类型（M4.4）

- **目标**：为 Stage 4 前端页面提供强类型 API 客户端。
- **范围**：
  - 新建：`frontend/src/services/match.ts`。
  - 修改：`frontend/src/types/index.ts` 增加：
    - `DimensionScore`、`DimensionScoresPayload`、`MatchScore`、`MatchRankingItem`、`MatchRankingResponse`、`BatchTaskResponse`、`BatchTaskStatus`。
- **接口契约（关键函数）**：
  ```ts
  export const matchApi = {
    matchOne: (data: { jd_id: string; resume_id: string; force?: boolean }) =>
      request.post<any, MatchScore>('/match-scores', data),
    batchMatch: (data: { jd_id: string; resume_ids?: string[]; limit?: number; force?: boolean }) =>
      request.post<any, BatchTaskResponse>('/match-scores/batch', data),
    getBatchStatus: (taskId: string) =>
      request.get<any, BatchTaskStatus>(`/match-scores/batch/${taskId}`),
    getScore: (scoreId: string) => request.get<any, MatchScore>(`/match-scores/${scoreId}`),
    rankByJd: (jdId: string, params?: { limit?: number; offset?: number }) =>
      request.get<any, MatchRankingResponse>(`/jds/${jdId}/ranking`, { params }),
    listByResume: (resumeId: string, params?: { limit?: number }) =>
      request.get<any, MatchScore[]>(`/resumes/${resumeId}/matches`, { params }),
  };
  ```
- **依赖任务**：S4-09。
- **DoD**：`frontend/tests/services/match.test.ts` 用 MSW 拦截后调用，断言反序列化字段；`npm run lint && npm run build` 通过。

---

## S4-11：`ScoringReport.tsx` 页面实现（M4.4）

- **目标**：替换现有占位页，实现"选择 JD → 查看候选人排名 → 单条匹配详情"三段体验。
- **范围**：
  - 重写：`frontend/src/pages/ScoringReport.tsx`。
  - 新建：`frontend/src/components/MatchRankingTable.tsx`、`frontend/src/components/MatchDetailDrawer.tsx`（或等价拆分）。
- **UI 契约**：
  - 页面顶部：JD 选择器（Select，绑定 `jdApi.list`）；「触发批量匹配」按钮（`batchMatch` + 轮询 `getBatchStatus`）。
  - 主体：`MatchRankingTable`（AntD Table，列：候选人名 / overall_score / 三维度小分 / 状态标记 `is_stale` / 详情按钮）。
  - 详情：`MatchDetailDrawer` 展示 `overall_reasoning` 与三维度 rationale + matched/missing 列表。
- **依赖任务**：S4-10。
- **DoD**：TEST-PLAN §7 前端用例先红后绿；`npm run lint && npm run build` 通过。

---

## S4-12：`Resumes.tsx` 置信度接入 + `ResumeDetail.tsx` 匹配面板（M4.4）

- **目标**：把两个业务已完成页面的"随机分/占位"替换为真实匹配数据。
- **范围**：
  - 修改：`frontend/src/pages/Resumes.tsx`：
    - 顶部筛选栏新增 JD 选择器 `matchAgainstJdId`。
    - 列表拉取增补：拿到 `resume` 后并发 `matchApi.rankByJd(matchAgainstJdId, { limit: 200 })` 或缓存查询；在渲染 `ScoreRing` 时按 `resume_id` 查表；无对应记录时显示"-"（不允许再用 `Math.random()`）。
  - 修改：`frontend/src/pages/ResumeDetail.tsx`：
    - 新增右侧「匹配报告」卡片，允许选择 JD（默认最近生成的 1 个）→ 触发/展示当前简历评分。
- **依赖任务**：S4-10、S4-11。
- **DoD**：Grep `Math.random()` 在 `frontend/src/pages/Resumes.tsx` 中不再存在；前端测试覆盖"未选 JD 时显示 -"、"选择 JD 后显示真实分"。

---

## S4-13：收尾与文档同步（M4.5）

- **目标**：Stage 4 收尾。
- **范围**：
  - 修改：`HANDOFF.md`（把 Stage 4 状态从 ⏳ 更新为 ✅，记录已交付能力与迁移 head）。
  - 修改：`docs/development-roadmap.md`（Stage 4 状态更新；如决策 1 修改了 candidates 表规划，此处同步）。
  - 可选：`docs/planning/COMMANDER-BRIEF.md` 追加"Stage 4 完成，进入 Stage 5 规划"备注。
- **验收标准**：
  - 端到端联调：从上传简历 → 生成 JD → 触发单点/批量匹配 → 前端列表/详情展示均正常。
  - 所有测试全绿；ruff、eslint、tsc 全过。
- **DoD**：提交 `docs(match): stage4 handoff & roadmap sync`。

---

## 任务依赖图（Blocking）

```
S4-01 ──▶ S4-02 ──▶ S4-06 ──▶ S4-07 ──▶ S4-08
   │           │        ▲
   │           └▶ S4-03 ┤
   │                    │
   ├──────────▶ S4-04 ──┘
S4-05 ────────────────▶ (all S4-06+ 用)
S4-09 ──▶ S4-10 ──▶ S4-11 ──▶ S4-12 ──▶ S4-13
                        ▲
S4-08 ──────────────────┘（后端全绿后前端才能真联调）
```

---

## 交付节奏建议

- **PR-1**：S4-01（纯文档）。
- **PR-2**：S4-05（后端测试基线）。
- **PR-3**：S4-02 + S4-03（模型 + Schema + 迁移）。
- **PR-4**：S4-04（Skill 定义 + 单测）。
- **PR-5**：S4-06 + S4-07 + S4-08（Service + API + 集成测试）。
- **PR-6**：S4-09（前端测试基线）。
- **PR-7**：S4-10 + S4-11（API service + ScoringReport 页面）。
- **PR-8**：S4-12 + S4-13（真实分接入 + HANDOFF 同步）。
