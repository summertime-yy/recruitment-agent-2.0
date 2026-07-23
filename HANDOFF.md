# 招聘 Agent 2.0 阶段性总结与交接文档

> 更新时间：2026-07-23
> 当前进度：**Stage 5 进行中**（PR-10/11/12/13/14/15/16/17/18 已合入 master，PR-19 待动工 —— 见 §九）
> 上一阶段：Stage 4（人岗匹配评分）已完成
> 下一阶段：Stage 5（Agent 对话核心）继续 PR-19（前端 ChatCenter + CandidateChat + 8 类 Card，S5-13）
> 对应提交：后端 `74482ba`（PR-5 匹配核心）；前端 `9002305`（PR-7 匹配服务/页面）、PR-8 `fb75251`/`6dd41b7`/`bc9545c`（接入真实分 + 匹配面板）；**本追加提交（PR-8 收尾）**：候选人管理页 UI/筛选/关联JD 重构 + ResumeDetail 匹配体验优化（详见 §3.2 / §6.1）
> 面向读者：下一位系统架构师 / 开发者

---

## 一、项目概览

**项目名称**：recruitment-agent-2.0（智能招聘助手）
**GitHub**：https://github.com/summertime-yy/recruitment-agent-2.0
**项目根目录**：`e:\AI-WORK\Project-Work\recruitment-agent-2.0`

**技术栈**：
- 后端：Python 3.11+ / FastAPI / SQLAlchemy 2.0 (async) / Alembic / PostgreSQL 15 (+pgvector) / Redis 7 / MinIO
- 前端：React 18 + TypeScript 5 + Vite 6 + Ant Design 5 + React Router v6 + Axios
- AI：火山引擎 Ark API（DeepSeek-V4-flash 模型）+ LangChain
- 包管理：后端 `uv`，前端 `npm`
- 代码规范：后端 Ruff（line-length=120, py311），前端 ESLint + tsc strict

**核心架构（双路径调用）**：
- **直接调用路径**（Stage 1-4）：`REST API → Service 层 → Skill → LLM`，用于 CRUD/表单驱动
- **Orchestrator 路径**（Stage 5 规划）：`SSE 对话 → Task Orchestrator（R-P-R-A-R）→ Skill → LLM`，用于对话驱动
- **Skill 契约唯一**：`skill.yaml` 是 Skill 的唯一契约定义，Python `BaseSkill` 仅为运行时加载/校验/执行引擎
- **Skill 契约扩展 · `internal` 字段（PR-9 写回，REVIEW D4 v2）**：`skill.yaml` 新增可选字段 `internal: bool`（默认 `false`，向后兼容）。`internal: true` 的 Skill（如 Stage 5 的 5 个 `orchestrator_*` 阶段 Skill）**走完整 BaseSkill 管道**（Prompt semver / Schema 校验 / 日志落 `skill_execution_logs` / compliance check），但**不对 Tool Router 暴露**。配套 `SkillRegistry` 语义：`get(skill_id)` 全量查询（供 Orchestrator engine 内部调用）；`list_dispatchable(task_type=None)` 过滤 `internal=true`（供 Tool Router）；`list_by_task_type()` 隐式走 `list_dispatchable`。Tool Router `dispatch(step)` 若命中 `internal=true` 的 Skill 抛 `SkillNotDispatchableError`

**权威文档（唯一事实来源，改动须先更新文档再改代码）**：
- `docs/data-model.md` — 数据库 Schema 唯一事实来源
- `docs/api-contract.md` — API / SSE 契约
- `docs/development-roadmap.md` — 分阶段开发路线图
- `AGENTS.md` — 仓库贡献规范（构建/测试/风格/提交约定）

---

## 二、进度总览

| Stage | 名称 | 状态 | 说明 |
|-------|------|------|------|
| Stage 0 | 基础层 | ✅ 完成 | Docker、PG+Redis+MinIO、SQLAlchemy/Alembic、LLM 适配器、Skill 框架、FastAPI 骨架 |
| Stage 1 | JD 管理模块 | ✅ 完成 | JD CRUD + AI 生成 + 前端页面（列表/生成/详情） |
| Stage 2 | 简历解析模块 | ✅ 完成 | 上传/解析/预览/编辑/删除 + 前端工作台 |
| Stage 3 | 候选人管理模块 | ✅ 完成 | 状态流转 + 标签 + 来源 + 去重 + 备注评价（后端全链路 + 前端组件） |
| **Stage 4** | **人岗匹配评分** | ✅ **完成** | match_scores 表 + `jd-candidate-matching` Skill v1.0.0 + 6 类匹配 API + 前端评分报告/列表/详情/简历联动 |
| **Stage 5** | **Agent 对话核心** | 🚧 **进行中** | **PR-10/11/12/13/15 已合**（tasks/executions 表 + Registry + Tool Router + Orchestrator R-P-R-A-R + SSE EventBuffer + Redis DI + Act 真跑 + candidate-merge Skill）；**PR-14 待动工**（REST 四端点 + SSE HTTP 端点）；后续 PR-16/17/18 见 §九 |
| Stage 6 | 推送与反馈 | ⏳ 未开始 | communications/feedback 表 + 推送服务 + 推送管理页 |
| Stage 7 | 看板与设置 | ⏳ 未开始 | analytics 表 + 数据看板 + Skill 管理 + 系统设置页 |

**当前数据库迁移 head**：`e4c1a2b3d4f5`（add match_scores table，Stage 4）；前置迁移 `113702a6d427`（tags/source/dedup）、`f8a2c4e91b03`（candidate status flow）

---

## 三、已完成模块详情

### 3.1 Stage 0-2（基础层 / JD / 简历解析）

**已交付能力**：
- Skill 框架：`BaseSkill`（YAML 加载 + 输入/输出校验 + 合规检查 + 重试）、`SkillRegistry`（自动发现加载）、启动时 Skill 自注册到 DB
- 已实现 Skill：`jd-generation`、`resume-parsing`（目录：`backend/app/agent/skills/<id>/vX_Y_Z/`）
- JD 模块：`POST /api/v1/jds/generate`、JD CRUD、前端 `/jds`、`/jds/generate`、`/jds/:id`
- 简历模块：上传/解析/预览/编辑/删除，前端 `/resumes`、`/resumes/:id`

**简历解析核心接口**：
| 功能 | 接口 |
|------|------|
| 上传（含 MD5 文件级去重） | `POST /api/v1/resumes/upload` |
| 触发解析（后台任务） | `POST /api/v1/resumes/{id}/parse` |
| 列表（分页/筛选/搜索） | `GET /api/v1/resumes` |
| 详情 | `GET /api/v1/resumes/{id}` |
| 原始文件预览（流式代理 MinIO） | `GET /api/v1/resumes/{id}/preview` |
| 编辑解析结果 | `PUT /api/v1/resumes/{id}` |
| 删除（同步删 MinIO 文件） | `DELETE /api/v1/resumes/{id}` |

### 3.2 Stage 3 — 候选人管理模块（完整交付）

> ⚠️ 旧版 HANDOFF 仅记录了"状态流转"，实际本阶段共交付 **5 大功能**，此处补全。

#### (1) 候选人状态机
- `candidate_status` 字段，与 `parse_status`（简历解析状态）**正交**
- 6 状态：`NEW / SCREENING_PASSED / SCREENING_REJECTED / INTERVIEWING / OFFERED / ARCHIVED`
- 转移图（`ALLOWED_TRANSITIONS`）+ 服务端 `is_valid_transition()` 校验，非法转移返回 400
- 状态历史独立表 `candidate_status_history`（resume_id FK CASCADE，含 reason/operator）

#### (2) 标签 tags
- `resumes.tags`（JSONB 数组），支持编辑、列表 JSONB 包含查询筛选
- ⚠️ **前端列表筛选已于 PR-8 收尾移除「标签」下拉**（此前 `tags/meta` 聚合出的标签基本为空、无实际筛选项）

#### (3) 来源渠道 source
- `resumes.source`（BOSS/拉勾/内推/猎头/邮件等），支持编辑与筛选
- ⚠️ **前端列表筛选已于 PR-8 收尾移除「来源」下拉**：实测库内 `source` 全为空（`tags/meta` 返回 `sources=0`），属无意义筛选项。后端 `source` 字段与 `?source=` 筛选参数仍保留（供后续有数据时使用）
- ✅ **新增「核心技能标签」筛选（替代标签/来源）**：基于简历解析结果 `parsed_content.skills` 聚合，由 `tags/meta` 的 `skills` 字段提供下拉项；列表端新增 `?skill=` 参数，走 `parsed_content::jsonb->'skills'` 的 JSONB 包含查询（见 §3.2 API 表）

#### (4) 去重 dedup（硬匹配 + 人工处理）
- `resumes.dedup_status`：`NONE / SUSPECTED / CONFIRMED_DUP / IGNORED`
- `resumes.duplicate_of_resume_id`：疑似重复源简历 ID
- 解析成功后 `_detect_duplicate()` 按 phone/email 硬匹配标记 `SUSPECTED`
- 人工处理 `handle_dedup_action()`：CONFIRM_DUP / IGNORE / RECHECK
- ⚠️ 注意：目前是**数据库硬匹配**，**非** Skill 驱动的智能合并

#### (5) 备注与评价 notes
- `candidate_notes` 表：`note_type`（NOTE/EVALUATION）+ `content` + `rating`(1-5) + `author`
- 完整 CRUD

#### Stage 3 API 端点
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/candidates/{resume_id}/status/meta` | GET | 状态机元数据 + 合法转移图 |
| `/api/v1/candidates/{resume_id}/status` | PUT | 状态转移（body: `{to_status, reason?, operator?}`） |
| `/api/v1/candidates/{resume_id}/status/history` | GET | 状态流转历史（倒序） |
| `/api/v1/candidates/{resume_id}/notes` | GET/POST | 备注列表 / 新增 |
| `/api/v1/candidates/{resume_id}/notes/{note_id}` | PUT/DELETE | 更新 / 删除备注 |
| `/api/v1/resumes/tags/meta` | GET | 聚合所有标签、来源与**核心技能**（`skills`，来自 `parsed_content.skills`）（筛选下拉） |
| `/api/v1/resumes/{resume_id}/dedup` | POST | 去重处理（CONFIRM_DUP/IGNORE/RECHECK） |
| `/api/v1/resumes?tag=&source=&skill=&dedup_status=&candidate_status=` | GET | 多维筛选（新增 `skill`：核心技能 JSONB 包含查询） |

#### Stage 3 关键文件
**后端**：
- `backend/app/models/candidate.py` — 状态常量/转移图/校验、`CandidateStatusHistory`、`CandidateNote` 模型
- `backend/app/models/resume.py` — 新增 tags/source/dedup_status/duplicate_of_resume_id/candidate_status 字段
- `backend/app/schemas/candidate.py`、`backend/app/services/candidate.py`、`backend/app/api/v1/endpoints/candidate.py`
- `backend/app/services/resume.py` — `_detect_duplicate`、`handle_dedup_action`、列表多维筛选
- 迁移：`f8a2c4e91b03_add_candidate_status_flow.py`、`113702a6d427_add_candidate_tags_source_dedup_and_.py`

**前端**：
- `frontend/src/services/candidate.ts` — status/notes API
- `frontend/src/components/CandidateStatusSwitch.tsx` — 状态切换（下拉 + 原因 Modal）
- `frontend/src/components/CandidateStatusTimeline.tsx` — 状态流转时间线
- `frontend/src/components/CandidateNotesCard.tsx` — 备注/评价卡片
- `frontend/src/pages/ResumeDetail.tsx`、`Resumes.tsx` — 集成上述组件 + 去重 UI + 标签/来源筛选

#### Stage 3 验证结果（2026-07-14）
- ✅ Ruff 通过；后端 import 链完整；candidate_router 已注册
- ✅ 前端 `npm run build` 通过（0 错误）
- ✅ 状态链路 `NEW → SCREENING_PASSED → INTERVIEWING → OFFERED` 全部 200；非法转移返回 400
- ✅ 历史 API 倒序返回；列表多维筛选生效

---

## 四、环境与启动

**启动命令**：
```powershell
# 1. 基础设施（PostgreSQL + Redis + MinIO）
docker compose up -d

# 2. 后端（backend/，使用 uv）
cd e:\AI-WORK\Project-Work\recruitment-agent-2.0\backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 前端（frontend/）
cd e:\AI-WORK\Project-Work\recruitment-agent-2.0\frontend
npm install
npm run dev   # Vite :5173，代理 /api → :8000
```

**访问**：前端 http://localhost:5173 ｜ API 文档 http://localhost:8000/docs ｜ 健康检查 http://localhost:8000/health

**关键配置（backend/.env，不入库，从 .env.example 复制）**：
```
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/plan/v3   # ✅ 火山方舟 Agent Plan 网关（OpenAI 兼容）；原 /api/v3 已无额度
LLM_MODEL=deepseek-v4-flash-260425   # ⚠️ 必须用 DeepSeek-V4-flash，不能用推理模型
LLM_MAX_TOKENS=4096                   # ⚠️ 当前验证可用值
LLM_TIMEOUT=180
MINIO_RESUME_BUCKET=resumes
DATABASE_URL=postgresql+asyncpg://...
```

**提交前检查**：`uv run pytest` + `npm run lint && npm run build`
**提交规范**：Conventional Commits（`feat:`/`fix:`/`docs:`/`refactor:`/`chore:`），subject ≤ 72 字符

### 4.1 PR 分支策略（Stage 5 PR-10 起沿用）

> 背景：PR-9 是纯文档 + 契约 PR，允许直推 master；PR-10 起进入 Stage 5 代码实现阶段，含红测试与 DDL/迁移，必须回归标准 feat 分支模式，保 master 常绿。

- **纯文档 / 契约 PR**（不改 `backend/app/**`、`frontend/src/**`）：可直接 commit 后 `git push origin master`，无需 feat 分支
- **含生产代码或红测试的 PR**（改 `backend/app/**`、`frontend/src/**`、`backend/tests/**`、`frontend/src/**/*.test.*`、`alembic/versions/**`）：**必须**走 `feat/pr-NN-<slug>` 分支
  - 命名：`feat/pr-<PR编号>-<S<Stage>-<Task>-<Task>...>-<短描述>`，例：`feat/pr-10-s5-01-02-data-layer`
  - TDD 红态 commit 落在 feat 分支上，禁止直推 master
  - push 分支后经指挥官核验 → 平台开 PR → fast-forward merge to master
- **迁移文件（`alembic/versions/**`）** 必须独立 commit，方便回退（不与 Model/Schema 合并）
- **红态 → 绿态**：先 `test: add S5-XX red tests`（红），再依次 `feat(stage5): ...` 使其转绿；同一 feat 分支上多个 commit 完整还原 TDD 节奏

---

## 五、踩坑记录（重要，务必先读）

### 5.1 LLM 相关
- **❌ 不要用推理模型（如 doubao-seed-2-1-turbo）做结构化解析**：推理链消耗大量 completion tokens，即使 max_tokens=4096 也可能被 reasoning_tokens 占满导致 JSON 截断
- **❌ 不要设置 `reasoning_effort` 参数**：DeepSeek 模型不兼容，会 API 报错
- **❌ 不要多层重试**：Skill 层与 LangChain ChatOpenAI 层都设 max_retries 会导致超时叠加。**两处都必须 `max_retries=0`**
- **✅ 所有 LLM 调用统一走** `app/agent/llm_adapter.py`
- **❌ `deepseek-v4-flash-260425`（含 Plan 网关）不支持 `response_format=json_object`**：会返回 400 `InvalidParameter`。已加 `LLM_JSON_MODE` 开关（默认 `False`）关闭强制 JSON 模式，改由 Skill prompt 约束输出 + `call_llm_json` 的 regex 兜底解析。切勿对该模型开启 `LLM_JSON_MODE`
- **✅ 2026-07-17 起 LLM 切到火山方舟 Agent Plan 网关**：`LLM_BASE_URL=…/api/plan/v3` + Plan 专属 API Key（原 `…/api/v3` 的 `ark-…-54561` 已无额度，报 429）。换模型只需改 `LLM_MODEL`，无需动代码；`.env` 不入库，新 key 仅本地

### 5.2 前端相关
- **✅ 打开新窗口用** `window.open(url, '_blank', 'noopener,noreferrer')`，在 onClick 同步上下文调用；不要用动态创建 `<a>.click()`（可能被安全策略拦截）
- **✅ Modal + Form 抽为独立子组件** + 条件渲染 `{visible && <EditModal />}`，避免 "useForm is not connected" 警告
- **Ant Design v5**：`destroyOnClose` 已废弃，用 `destroyOnHidden`

### 5.3 后端相关
- **FastAPI 路由顺序**：具体路径（如 `/{resume_id}/preview`、`/tags/meta`）必须定义在 `/{resume_id}` 之前，否则被路径参数覆盖
- **迁移命名**：`<rev>_<snake_case_desc>.py`；改 DB 前先更新 `docs/data-model.md`
- **⚠️ 本地启动后端必须直接 `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`**（让 IDE harness 托管为常驻服务）；用 `Start-Process`/`cmd /c` 后台拉起会被进程组回收，端口随即释放。改 `.env` 后需重启进程才会重读（--reload 只监听 `.py`）
- **⚠️ alembic 迁移不要在 `async` fixture 里跑**：`alembic.command.upgrade` 内部走 `asyncio.run(run_async_migrations())`，若外层已在 pytest-asyncio 事件循环里会抛 `asyncio.run() cannot be called from a running event loop`。必须用**同步** `@pytest.fixture(scope="module") def`，且 teardown 用**相对回退**（记录进入前 head → `command.downgrade(cfg, pre_head or "base")`），不要硬编码 revision，否则后续新迁移落地后会误删。范式见 `backend/tests/test_stage5_s5_01_data_layer.py::_migrated_schema`
- **⚠️ 共享 dev 库测试数据可能跨 PR 累积泄漏**：`conftest.db_session` 是 PR-9 前后新加的 rollback 护栏，其之前的 Stage 2-4 历史测试真 `commit()` 了脏数据。跑全量 `uv run pytest` 若失败原因是 `UniqueViolationError`（如 `skills.jd-candidate-matching` 重复主键）或 `logs[0]`/`ranking[0]` 不符预期，先查 `skills` / `skill_execution_logs` / `match_scores` 表是否有陈旧行；**确认非业务数据后可精确 `DELETE`**（不要 `TRUNCATE`）。**长期方案**：Stage 7 前引入独立测试 DB（`recruitment_test` schema 或每次 pytest 运行起 fresh docker container）

---

## 六、后续未完成任务梳理（给下一位架构师）

> 以下为规划蓝图，**下一位架构师应据此产出各 Stage 的详细设计与任务拆解**。开发严格串行依赖：Stage 4 → 5 → 6 → 7。

### 6.1 Stage 4 — 人岗匹配评分模块（✅ 已完成）

**目标**：给定 JD 与候选人简历，AI 计算多维匹配分并生成匹配报告。

**依赖**：Stage 1（jds 表）+ Stage 3（简历/候选人已就绪）——依赖已满足。

**交付物（已全部完成）**：
- **数据表** `match_scores`（参见 `docs/data-model.md §3.3`）：同时引用 jds 与 resumes，存储各维度分数、综合推荐度、匹配报告内容
- **Skill** `jd-candidate-matching v1.0.0`：输入 JD + 简历结构化数据，输出多维匹配分（技能/经验/学历/综合）——已创建 skill.yaml + prompt.md + examples.yaml
- **后端 API**：`POST /match-scores`、`POST /match-scores/batch`、`GET /match-scores/batch/{task_id}`、`GET /match-scores/{score_id}`、`GET /jds/{id}/ranking`、`GET /resumes/{id}/matches`（均已实现 + pytest 集成测试，51 测试全绿）
- **前端页面**：`ScoringReport.tsx`（JD 选择器 + 批量匹配轮询 + 排名表 + 详情 Drawer）已落地
- **前端联动**：`Resumes.tsx` 已移除 `Math.random()` 随机数，改为按所选 JD 拉取真实匹配分（「匹配分」列 + 右侧面板重新匹配）；`ResumeDetail.tsx` 已替换占位为「JD 匹配评分」卡片（生成评分 + 详情 Drawer）
- **PR-8 收尾 · 候选人管理页体验重构**（本追加提交）：
  - **整页滚动**：列表卡片改为按内容自适应高度，移除内部固定高度与滚动条，由 `MainLayout` 的 `Content`（`overflow:auto`）承载整页滚动；顶部 `Header` 为 `position:sticky` 固定不动；分页器保留
  - **右侧「关联 JD」面板重构**：从"展示候选人列表"改为**展示该候选人已关联的多条 JD 及各自匹配评分**（调用 `GET /resumes/{id}/matches`），每张卡片含 JD 标题/部门、评分环、是否"简历已更新"、失败标记，支持「查看详情」（`MatchDetailDrawer`）与「重新匹配」，底部支持关联新 JD
  - **筛选区精简**：移除无数据的「标签」「来源」下拉，仅保留「核心技能标签」（`tags/meta.skills` + `?skill=`）
  - **ResumeDetail 匹配体验优化**：JD 列表加载不再依赖简历解析状态（任意简历详情均可选 JD 匹配），补齐加载/错误态、`showSearch` 搜索、按钮文案随是否已评分切换（生成/重新生成）、新增「查看匹配详情」「重新生成」入口
  - **ResumeDetail 多 JD 管理**：「JD 匹配评分」卡片由单条展示改为**多 JD 评分列表**，每个 JD 各自展示评分环 + 「查看详情」「重新匹配」，新增 JD 不再覆盖已有评分（与列表页关联 JD 侧边栏行为一致）
  - **生成评分 交互反馈（PR-8 收尾）**：修复顶部「生成评分」按钮点击无响应问题——原 `loading={matchLoading && !rematchJdId}` 因 `rematchJdId` 总被赋值而恒为 `false`；现区分顶部按钮（`matchLoading`）与卡片「重新匹配」（`rematchJdId`）各自 loading；点击后立即弹出 `正在匹配中...` 全局提示、按钮显示加载态并禁用防重复点击，成功/失败自动关闭提示、失败给出错误文案

**注意**：`match_scores` 同时引用 jds 和 resumes，必须在两表都存在后建（已满足）。

### 6.2 Stage 5 — Agent 对话核心（Orchestrator + SSE）

**目标**：引入对话式交互（体验增强层），通过自然语言驱动全流程。

**依赖**：Stage 1-4 全部业务 Skill 就绪。

**待交付物**：
- **数据表** `tasks`、`executions`
- **核心组件**：Task Orchestrator（R-P-R-A-R 推理循环）、SSE 事件推送、Tool Router
- **API 契约**（严格遵循 `docs/api-contract.md`，禁止前后端各自定义）：
  - `POST /api/agent/chat`
  - `GET /api/agent/tasks/{id}/stream`（SSE）
  - `POST /api/agent/execute-plan`
  - `POST /api/agent/skip-to-score`
- **SSE 事件信封**：`type: thinking|plan|tool_call|progress|result|error|warning|system`
- **前端页面**：对话任务中心 `ChatCenter.tsx` / `CandidateChat.tsx`（当前均为**占位空壳**）

### 6.3 Stage 6 — 推送与反馈

**依赖**：Stage 5。
**待交付物**：`communications`/`feedback` 表、推送服务、推送/反馈 Skill、推送管理前端；`PushFeedback.tsx`（当前**占位空壳**）需实现。

### 6.4 Stage 7 — 看板与设置

**依赖**：Stage 5+6。
**待交付物**：`analytics` 表、数据看板、Skill 管理页、系统设置；`Analytics.tsx` / `Settings.tsx`（当前**占位空壳**）需实现。

### 6.5 前端占位页清单（10 个空壳，随对应 Stage 补齐）

| 页面 | 路由 | 归属 Stage |
|------|------|-----------|
| `ScoringReport.tsx` | `/scores` | Stage 4 ✅ 已实现（评分报告/排名/详情） |
| `ChatCenter.tsx` | `/chat` | Stage 5 |
| `CandidateChat.tsx` | `/candidate-chat` | Stage 5 |
| `PushFeedback.tsx` | `/push` | Stage 6 |
| `Analytics.tsx` | `/analytics` | Stage 7 |
| `Settings.tsx` | `/settings` | Stage 7 |
| `InterviewSchedule.tsx` | `/interview` | 未排期（Phase 2） |
| `CompareAnalysis.tsx` | `/compare` | 未排期（Phase 2） |
| `WorkflowTrack.tsx` | `/workflow` | 未排期（Phase 2） |
| `ResumeWorkspace.tsx` | `/resumes`（旧版残留） | 可清理 |

### 6.6 技术债务与待验证项

1. **简历解析成功率**：需批量上传不同长度/格式（PDF/DOCX）简历验证 100% 成功；若截断，将 `LLM_MAX_TOKENS` 提升至 8192
2. **传给 LLM 的 raw_text 截断长度**：确认 `services/resume.py` 中实际截断值是否合理
   - **PR-9.pre 记录（不改代码）**：当前 `raw_text[:3000]` 截断，待 Stage 5 前评估是否放宽至 `6000–8000`（长简历解析可能丢失尾部经历）
3. **测试已建立（原"测试缺失"已解决）**：后端 `pytest` 收集 **51 passed**（PR-1~PR-5 引入 model/skill/service/api/ranking）；前端 Vitest 收集 **16 passed**（PR-6 基建 + PR-8 集成测试）。建议持续补充边界与异常路径用例
4. **去重升级**：当前为 phone/email 硬匹配，路线图规划有 `candidate-merge` Skill（智能合并）——尚未实现，可评估是否纳入 Stage 4/后续
5. **候选人画像**：路线图 `candidate-profile` Skill（画像标签自动生成）尚未实现
6. **工作区未纳管文件**：`.uploads/`、`frontend/tsconfig.tsbuildinfo` 建议加入 `.gitignore`；`scripts/`（一次性辅助脚本）与 `AGENTS.md` 待决定是否提交

---

## 七、关键文件速查表

### 后端
| 文件 | 用途 |
|------|------|
| `backend/app/main.py` | FastAPI 入口（CORS、路由注册、Skill 同步） |
| `backend/app/api/v1/__init__.py` | 路由聚合（jd/resume/candidate router） |
| `backend/app/agent/llm_adapter.py` | LLM 适配器（max_retries=0，无 reasoning_effort） |
| `backend/app/agent/base_skill.py` / `skill_registry.py` | Skill 运行时 / 注册表 |
| `backend/app/agent/skills/` | Skill 定义（jd_generation、resume_parsing） |
| `backend/app/models/` | 数据模型（jd/resume/candidate/skill） |
| `backend/app/services/` | 服务层（jd/resume/candidate） |
| `backend/app/api/v1/endpoints/` | API 路由（jd/resume/candidate） |
| `backend/alembic/versions/` | 数据库迁移（head: 113702a6d427） |

### 前端
| 文件 | 用途 |
|------|------|
| `frontend/src/App.tsx` | 路由配置 + AntD 主题 |
| `frontend/src/pages/Resumes.tsx` | 简历工作台（列表/上传/筛选/标签/去重） |
| `frontend/src/pages/ResumeDetail.tsx` | 简历详情（解析内容 + 状态 + 备注 + 去重） |
| `frontend/src/components/Candidate*.tsx` | 候选人状态/时间线/备注组件 |
| `frontend/src/services/` | API 服务层（resume/candidate/jd） |
| `frontend/src/types/index.ts` | TypeScript 类型定义 |
| `frontend/vite.config.ts` | Vite 配置（/api 代理） |

### 文档
| 文件 | 用途 |
|------|------|
| `docs/data-model.md` | 数据库 Schema 唯一事实来源 |
| `docs/api-contract.md` | API / SSE 契约 |
| `docs/development-roadmap.md` | 分阶段开发路线图 |
| `AGENTS.md` | 仓库贡献规范 |

---

## 八、给下一位架构师的建议

1. **从 Stage 4 起步**：先更新 `docs/data-model.md` 定义 `match_scores` 表，再按"表 → 模型 → 迁移 → Schema → Skill → Service → API → 测试 → 前端"顺序推进（见 `development-roadmap.md §9.1`）
2. **Skill 优先**：Stage 4 的核心是 `jd-candidate-matching` Skill，务必遵循 Skill 唯一契约（skill.yaml + prompt.md + examples.yaml），勿在 Python 中硬编码 prompt
3. **打通"随机分 → 真实分"**：✅ 已完成——`Resumes.tsx` 已移除 `Math.random()`，按所选 JD 拉取真实匹配分（「匹配分」列 + 右侧面板重新匹配），`ResumeDetail.tsx` 已替换占位为「JD 匹配评分」卡片
4. **保持文档同步**：任何 DB/API 变更先改 `docs/`，与提交一起入库
5. **测试已补齐**：后端 51 + 前端 16 关键路径用例已随 PR-1~PR-8 入库，提交前 `uv run pytest` + `npm run test` 可复验，降低回归风险

---

## 九、Stage 5 进行中（2026-07-21 追加，2026-07-23 PR-18 合入后更新）

> 权威规划文档三件套（顶层，双盲评审合并版）：`docs/planning/PLAN-STAGE5.md`、`docs/planning/TASKS-STAGE5.md`、`docs/planning/TEST-PLAN-STAGE5.md`
> 各 PR 启动裁定归档：`docs/planning/stage5/PR{10..19}-KICKOFF-{QUESTIONS,REVISIONS,DECISION}.md` + `PR{10..18}-STEP6-REPORT.md`
> ⚠️ **不要读** `docs/planning/stage5/commander/` 和 `docs/planning/stage5/executor/` —— 那是双盲评审前的初稿，已被合并版覆盖

### 9.1 PR 切分与状态

| PR | 任务 | 内容 | 状态 | 合入 commit |
|----|------|------|------|-------------|
| PR-10 | S5-01 + S5-02 | tasks/executions 表 + SkillRegistry.internal + SSE/Agent Schema | ✅ | 见 git log |
| PR-11 | S5-04 | Tool Router | ✅ | 6beb25e |
| PR-12 | S5-05/06/07/08 | 5 个 Orchestrator internal Skill + Engine 主循环 + 状态机 | ✅ | 039171e |
| PR-13 | S5-03 + S5-07 剩余 | SSE EventBuffer + Redis lifespan DI + Act→Redis 发射 + run_execute 真跑 + run_reflect_act + datetime helpers（决策 B） | ✅ | aa57270 |
| PR-14 | S5-09 | REST 四端点（chat/execute/skip/cancel）+ SSE 流端点 + Engine 异步 chat + db_updater 回调 | ✅ | 2124953 |
| PR-15 | S5-10 | candidate-merge Skill | ✅ | 92a322e |
| PR-16 | S5-11 | candidate-profile Skill + engine 数据型 artifact 出口补齐 | ✅ | ab99b43 |
| PR-17 | 追债项 10+11 收敛 | Orchestrator 端到端路由修复（`SkillRegistry._task_type_to_tool_name` 自动派生 + engine `run_plan` 动态注入 dispatchable Markdown 清单 + reason 值域补全） | ✅ | bcc6c3b |
| PR-18 | S5-12 | 前端类型 + `agentApi` services + `useTaskStream` SSE Hook（fetch + ReadableStream 手写解析器 + Last-Event-ID 重连 + 3/6/12s 指数退避 + 心跳 `lastHeartbeatAt` 字段） | ✅ | 34703a0 |
| **PR-19** | **S5-13** | **前端 ChatCenter + CandidateChat + 8 类事件卡片** | ⏳ **下一个** | — |

**当前 master HEAD**：`dd73c4d`（PR-18 STEP6 报告） · **后端测试基线**：**120 passed**（未变，PR-18 未触碰 backend/app）· **前端测试基线**：**20 passed**（PR-17 期 `N_before=16` → PR-18 新增 4：TC-S5-12-1..4）。

### 9.2 Stage 5 架构约束（PR-13 起生效）

- **Redis 成为对话域硬依赖**：Stage 4 前 Redis 无调用点；PR-13 起 chat/stream/execute 端点依赖 Redis 存事件缓冲 + 全局并发计数。**Redis 挂 = 对话不可用**（但既有 CRUD 不受影响）。运维需 Redis 高可用。
- **Redis 访问统一走 `Depends(get_redis)`**：`app/main.py` lifespan 挂 `app.state.redis`，`app/core/redis.py` 提供 `get_redis(request)` DI。**禁止** `from app.core.redis import redis_client`（PR-13 已删除全局单例）。
- **SSE 事件缓冲**（合并版 PLAN §Q6 权威）：Redis List `sse:buf:{task_id}`、`MAXLEN=200` 环形裁剪、终态后 TTL **3600s（60min）**、**MVP 不启 Pub/Sub**（SSE 端点用 `read_after` + 100ms 轮询做进程内实时推）。
- **全局并发上限 = 10**：Redis 原子计数器 `task:active`（`INCR/DECR` + TTL 1h 兜底）；超限 429 `TASK_LIMIT_EXCEEDED`。
- **超时分层**：单 Skill 120s / 单阶段 180s / 整个 Task 600s（10min，PLAN §Q8）。
- **心跳**：SSE 端点层每 15s 发 `system` 心跳帧，**不入 EventBuffer**（重放时不重发）—— PR-14 实施。
- **五段 R-P-R-A-R Skill 都是 `internal: true`**：走完整 BaseSkill 管道（Schema 校验 / 日志 / compliance），但**不对 Tool Router 暴露**（LLM 生成的 Plan 意外引用 `orchestrator-reason` 等会抛 `SkillNotDispatchableError`）。
- **datetime helpers 双出口（决策 B）**：`app/core/time.py` 提供 `utcnow_naive()`（落库 `TIMESTAMP WITHOUT TIME ZONE` 列用）与 `utcnow_aware()`（SSE / 内存 / 日志用）。全仓 `datetime.utcnow()` 已归零。Stage 5.1 迁 `TIMESTAMPTZ` 后收敛为单一 aware。

### 9.3 已知妥协与 Stage 5.1 开放项

以下是 MVP 明确妥协、后期需处理的技术债：

1. **后台任务 fire-and-forget，无崩溃恢复** — `run_execute` 用 `asyncio.create_task` 后台跑 Act，进程重启后 in-flight 任务全丢失，`tasks` 表卡在 EXECUTING 永不更新。Stage 5.1 需接入真实任务队列（Celery / arq）+ worker daemon 拾回。
2. **不启 Redis Pub/Sub，SSE 端点 100ms 轮询** — 多进程副本部署时无法水平扩展。Stage 5.1 开放项。
3. **Result Artifact `type` 字段无自动化护栏** — 后端 `_ARTIFACT_TYPE_MAP` 与前端卡片渲染器手动同步，新增工具（如 PR-16 的 `candidate-profile`）时**必须同步改两边**，忘记会走 `generic` fallback。Stage 5.1 前建议改共享枚举或 codegen。
4. **fakeredis 覆盖不到真 Redis 边界差异** — pipeline 语义、LTRIM 负索引等边界在 fakeredis 与真 Redis 上可能不一致。Stage 6/后期加 docker-redis 集成测试套件。
5. **`app/core/redis.py` 全局单例已删除（PR-13）** — 若后续发现历史代码有隐式引用（当前 grep 无匹配），走 `Depends(get_redis)` 补齐。
6. **DB 列仍为 `TIMESTAMP WITHOUT TIME ZONE`（naive）** — PR-13 §十二 清扫 `datetime.utcnow()` 时发现，`skill_execution_logs.executed_at` 等列是 naive，直接改 tz-aware 会导致 asyncpg 写入失败。PR-13 裁定采用方案 B：新增 `app/core/time.py` 提供 `utcnow_naive()`（落库用）和 `utcnow_aware()`（SSE / 内存 / 日志用）双 helper。**Stage 5.1 需专项 PR 用 Alembic 迁移相关列到 `TIMESTAMPTZ`，然后收敛为单一 `utcnow_aware()`**。详见 `docs/planning/stage5/PR13-HELP-REQUEST-datetime-tz.md`。
7. **`executions` 表全生命周期未落库**（PR-14 §19.1 引入）— `api-contract.md §4.5`（cancel 写 `executions.status='CANCELLED'`）与 `PLAN-STAGE5.md §5.5`（Act 逐步 executions 记录）**违契**。PR-14 的 cancel/execute 端点仅操作 `tasks` 表；`models/execution.py` 已存在但闲置。**Stage 5.1 专门 PR**：db_updater 回调扩至两张表 + `run_act` 加 per-step callback + cancel 端点同事务内 UPDATE `executions`。详见 `docs/planning/stage5/PR14-KICKOFF-DECISION.md §19.1` + `PR14-STEP6-REPORT.md §五 19.1`。
8. **`tasks.current_step` 中途不写 DB**（PR-14 §19.2 引入）— db_updater 只在 INSERT/终态触碰；`_background_execute` 中途不 UPDATE。前端进行中步骤高亮**只能从 SSE `tool_call`/`progress` 事件推导**；SSE 断连且 TTL 过期后前端拿不到"进行到哪一步"（属降级路径，可接受）。**与追债项 7 同 PR 补齐**：给 `run_act` 加 `on_step_start` / `on_step_end` callback，db_updater 逐步 UPDATE `current_step`。
9. **`THINKING` 事件非 token 流**（PR-14 §19.3 引入）— Reason 完成后**一次性**发一条 `THINKING`（summary），Reflect / Reflect-Plan 不 emit thinking。**不在 Stage 5.1 范围**，属 Stage 6+ 独立 PR：Reason skill 接入流式 LLM adapter（`langchain-openai` 的 `astream`），`run_reason` 改为 async generator 逐 token yield，`_background_reason_plan` 逐帧 `emit(THINKING, {"delta": token})`。
10. **`task_type` 三命名空间共存**（PR-16 §19.1 引入，canonical 表述见 `PR16-KICKOFF-DECISION.md §十九`）**✅ 已收敛（PR-17 `bcc6c3b`，Y 方向；X/Z 留 Stage 5.2）** — `skill_id` / `tool_name`（连字符 lowercase）≠ `skill.yaml.task_type`（下划线 lowercase）≠ `tasks.task_type` DB 列（SCREAMING）三层同名不同义。**Y 方向已实施**：`SkillRegistry._load_all_skills` 末尾自动从 `skill.yaml.task_type` 派生 `_task_type_to_tool_name` 映射表，权威源单一、新增 skill 零维护、冲突启动即 fail-fast raise（PR-17 canonical 收敛点，见 `skill_registry.py`）。**X 方向（拆字段名 refactor）/ Z 方向（DB 列 SCREAMING → 与 skill.yaml 对齐迁移）明留 Stage 5.2**，触发条件不变。
11. **orchestrator reason/plan 未登记 dispatchable Skill，自然语言路由不通**（PR-16 §19.2 引入，跨 PR-15/16 共同债务）**✅ 已收敛（PR-17 `bcc6c3b`）** — reason 补全 `profile_candidate` 值域 + examples；`OrchestratorEngine._format_dispatchable_tools` 合并 `BUILTIN_TOOLS` + `registry.list_dispatchable()` 生成 Markdown 列表；`run_plan` 每次调用注入 `plan_input["dispatchable_tools"]`（`orchestrator_plan/skill.yaml.input_schema.properties` 加 `dispatchable_tools` **不入 `required`**）；LLM 从清单学习 `task_type ↔ tool_name` 对应后自主输出合法 `tool_name`，`reflect_plan` 保护网（engine.py:169 `dispatchable_tool_names()` 校验）挡下 LLM 犯错。**canonical 收敛点**：`engine.run_plan` + `_format_dispatchable_tools` + `orchestrator-plan/prompt.md` + `orchestrator-reason/prompt.md`。集成测试 TC-PR17-1..4 覆盖 candidate-profile / candidate-merge / jd-candidate-matching 三条正向路径 + 1 条 reflect_plan 反向拦截。
12. **`create_match_score` dangling tool_name**（PR-17 §19.4 归档，Q9 决定 A 未修） — 该 tool_name 既非 `BUILTIN_TOOLS` 键（`tool_router.py:54` 仅含 `search_resumes` / `read_jd`）亦非任何 `skill.yaml` 的 `skill_id`，却出现在 `engine.py:51`（`_ARTIFACT_TYPE_MAP`）、`engine.py:418`、`agent.py:149`（skip-to-score 硬编码 plan）。**潜在 bug**：若 skip-to-score 走 `tool_router.dispatch`，`create_match_score` `not in BUILTIN_TOOLS` → `registry.get_skill('create_match_score')` 返 None → `UnknownToolError`。**PR-13/14 遗留潜在 bug，Stage 5.2 前需二选一独立 PR 收敛**：(1) 注册 `create_match_score` 进 `BUILTIN_TOOLS`；(2) 改 `agent.py:149` 硬编码 `tool_name` 为 `jd-candidate-matching`。风险等级：低（skip-to-score 是显式 REST 硬编码路径，未走 dispatch，当前无实际触发）。

### 9.4 已知陷阱（PR-19 起须警惕）

1. **`asyncio.create_task` 在 pytest 中泄漏 / hang** — 后台任务若在测试函数返回前未 await，event loop 无法退出，CI 卡住。测试 fixture 必须显式 `asyncio.gather` 所有 `orch-*` 命名 task（PR-13 conftest 已加）。
2. **`datetime.utcnow()` 已归零，新代码请用 `app.core.time` 的 helpers** — 落库赋值点 → `utcnow_naive()`；其他（SSE / 日志 / 内存） → `utcnow_aware()`；跨 aware/naive 比较 → `_to_naive_utc()` 归一化。
3. **PR-13 已完成的收尾**（记录以供后续 PR 参考）：`run_execute` 真跑（`asyncio.create_task` fire-and-forget）、`run_reflect_act` 已补齐、`act.py` 加 `_safe_emit` try/except、`RedisActiveCounter` 替代 InMemory（测试仍保留 InMemory）、Result Artifact schema `{step_id, tool_name, type, ref_id?, data?}` 已固化（6 类型）。
4. **`POST /agent/chat` 是异步端点**（PR-14 §19 引入）— 立即返 `{task_id, status:"PLANNING"}`，R-P-R 在后台 `_background_reason_plan` 内跑；前端拿到 task_id 后必须**立即 `GET /agent/tasks/{task_id}/stream`** 才能接住 THINKING/PLAN 事件。**`AgentChatResponse.initial_plan` 字段本 PR 不填**（前端完全依赖 SSE `PLAN` 事件消费）；老代码若期望"chat 同步返 plan"必须适配。PR-18 前端 `agentApi.chat` 已按此约定实现（`AgentChatResponse.initial_plan?: Plan` 声明为 optional，前端不消费该字段）。
5. **SSE stream 端点的 `request.is_disconnected()` 在 pytest ASGITransport 下不生效**（PR-14 §五 补充 3）— httpx 测试客户端在 stream 期间不上报 disconnect。所有 SSE 测试改为"让流自然终止"策略（终态 task 走 3b 合成，或在缓冲/心跳用例中后台延迟追加终态 RESULT 事件）。**生产 `_event_stream` 保留 `is_disconnected()` 检测**（真实 ASGI server 下有效），仅测试消费方式适配。
6. **REST 端点内不显式 `async with db.begin()`**（PR-14 §五 补充 2）— conftest 的 `db_session` fixture 已开事务，嵌套 begin 会 raise "transaction already begun"。cancel 端点改为设值后显式 `await db.commit()`；`with_for_update()` 直接跑在既有事务上。**生产 `get_db` 每请求独立会话，语义不变**。
7. **`test_s5_09_4_sse_heartbeat` 已知 flaky**（PR-14 §五 补充 3 · SSE 时序敏感） — 全量重跑约 1/N 概率单点失败（`hb` 长度 2 vs 3），isolated 运行必 pass。判定标准：若隔离 pass + 后续全量重跑连续 2 次通过，即非 regression。PR-16/17/18 FF-merge 评审均按此策略处理，未 flag 为回归。
8. **dispatch 端点已支持自然语言触发 candidate-* skill**（PR-17 §19.2 追债项 11 已收敛，起手 master HEAD `dd73c4d`）— `candidate-merge` / `candidate-profile` / `jd-candidate-matching` 可通过 `POST /agent/chat` 自然语言用户消息触发（LLM 从注入的 dispatchable Markdown 清单学习 `task_type ↔ tool_name` 后自主输出合法 `tool_name`，`reflect_plan` 保护网挡下 LLM 犯错）。**前端 chat → SSE 流可拿到 THINKING + PLAN + TOOL_CALL + PROGRESS + RESULT 全事件序列**，可正常渲染 PlanCard 与 candidate-* skill 的 result artifact。**渲染时须知**：追债项 3（`_ARTIFACT_TYPE_MAP` 与前端渲染器手动同步）仍未消除，新增 artifact `type` 必须**同步改后端 `engine._ARTIFACT_TYPE_MAP` 与前端 `frontend/src/types/agent.ts::ArtifactType` union + PR-19 卡片 `switch` 分派**，忘则走 `generic` fallback（PR-18 前端 union 已就位 6 键 `jd/resume/match_score/candidate_merge/candidate_profile/generic`，PR-19 卡片 switch 时 exhaustiveness 护栏激活）。
9. **`create_match_score` REST 硬编码 plan 未走 dispatch**（PR-17 §19.4 归档追债项 12） — 前端不要期待通过 `POST /agent/chat` 自然语言触发 skip-to-score；skip-to-score 仍走 `POST /agent/skip-to-score` REST 端点硬编码 plan 绕开 tool_router（Stage 5.2 前独立 PR 二选一收敛，见 §9.3 追债项 12）。PR-18 前端 `agentApi.skipToScore` 已按此约定实现（直接调 REST 端点，不走 `agentApi.chat`）。
10. **PR-19 前端起手警惕：`useTaskStream` 终态判定按 A2 闭合**（PR-18 KICKOFF-DECISION §五）— hook 仅认 `type === 'result' || type === 'error'` 为终态并 `status='closed'` 不再重连；**弃 `data.recoverable` 判定**（后端 `SSEEvent.data` 为 Any 未固化 `recoverable`）。**已知边界**（PR-18 STEP6 §五 obs 3）：若任务经后端 `system:cancelled` 终止，hook 会因未收 `result/error` 而进入非终态重连（3s→6s→12s 退避 3 次后 `status='error'`，非 clean `closed`）。PR-19 若需处理 cancel 场景的 clean 关流 UX，评估是否将 `system:cancelled` 纳入终态判定（可能需扩 `system` 事件 payload 或改 hook 内规则；若改则同步 PR-18 KICKOFF-DECISION §五 备忘）。
11. **PR-19 前端 SSE 消费选型延续**（PR-18 KICKOFF-DECISION §二 Q2 选项 B）— hook 用 **fetch + ReadableStream 手写 SSE 解析器**，非原生 `EventSource`；未来引入 `Authorization` 头亦通过 fetch 加。忽略 server `retry:` 字段，用自身 3/6/12s 退避（B3）。PR-19 若消费 hook 无须改此选型。

### 9.5 关键新增文件（PR-10~18 已合入）

| 文件 | 用途 |
|------|------|
| `backend/app/agent/orchestrator/engine.py` | OrchestratorEngine：R-P-R-A-R 主循环编排（**PR-14** 重构：`run_chat` → `start_chat` + `_background_reason_plan` 异步；`__init__` 增 `db_updater` 回调；`run_skip_to_score` 加 `task_id` 参数） |
| `backend/app/agent/orchestrator/state_machine.py` | TaskStatus 枚举 + 合法转移矩阵 + TransitionGuard |
| `backend/app/agent/orchestrator/act.py` | run_act：按 Plan 顺序 dispatch + 发 SSE 事件 |
| `backend/app/agent/orchestrator/active_counter.py` | 并发计数：InMemory（测试用）+ **RedisActiveCounter**（PR-13，生产用，`task:active` INCR/DECR + 1h TTL） |
| `backend/app/agent/orchestrator/tool_router.py` | ToolRouter：意图→工具分发，拒 internal Skill |
| `backend/app/agent/orchestrator/errors.py` | IllegalTransitionError / TaskLimitExceededError / TaskTimeoutError |
| `backend/app/agent/orchestrator/event_buffer.py` | **PR-13 新增**：SSE 事件缓冲（Redis List `sse:buf:{task_id}`、MAXLEN=200、终态 TTL 3600s、`append/read_after/set_terminal_ttl`） |
| `backend/app/agent/skills/orchestrator_{reason,reflect,plan,reflect_plan,reflect_act}/v1_0_0/` | 5 个 internal Skill（yaml + prompt + examples） |
| `backend/app/schemas/agent.py` | SSEEvent / SSEEventType / Plan / PlanStep / Agent{Chat,Execute,Skip,Cancel}Request/Response |
| `backend/app/models/{task,execution}.py` | tasks / executions 表模型（PR-10）；executions 表 PR-14 起仍闲置（§9.3 追债 7） |
| `backend/app/core/redis.py` | **PR-13 重写**：Redis lifespan + `Depends(get_redis)` DI，全局单例已删 |
| `backend/app/core/time.py` | **PR-13 新增**：`utcnow_aware()` / `utcnow_naive()` / `_to_naive_utc()`（决策 B，双出口 helpers） |
| `backend/app/api/v1/agent.py` | **PR-14 新增**：Agent REST 端点（chat/execute-plan/skip-to-score/tasks GET/cancel/stream 6 端点）+ `_make_db_updater` 工厂 + `_event_stream` / `_synthesize_from_task` SSE helpers |
| `backend/tests/api/sse_helpers.py` | **PR-14 新增**：`parse_sse` 帧解析（httpx.stream 消费，不引入 sse-starlette） |
| `backend/tests/api/test_agent_endpoints.py` | **PR-14 新增**：TC-S5-09-1..6（路由顺序 / 状态码 / Last-Event-ID 重放 / 15s 心跳 / retry:3000 / engine raise → 500） |
| `backend/app/agent/skills/candidate_profile/v1_0_0/{skill.yaml,prompt.md,examples.yaml}` | **PR-16 新增**：candidate-profile Skill 三件套（`skill_id: candidate-profile` / `task_type: profile_candidate` / 合规约束 / 4 字段强约束 / 3 few-shot） |
| `backend/tests/test_stage5_s5_11_candidate_profile.py` | **PR-16 新增**：TC-S5-11-1..4 + engine 数据型 artifact 单测（`test_build_artifacts_data_types_preserve_type`） |
| `backend/app/agent/skill_registry.py` | **PR-17 修改**：`_load_all_skills` 末尾自动派生 `_task_type_to_tool_name` + 冲突启动即 `raise ValueError`（fail-fast） + 新增 `get_tool_name_for_task_type()` accessor（追债项 10 Y 方向 canonical 收敛点） |
| `backend/app/agent/orchestrator/engine.py` | **PR-17 修改**：新增 `_format_dispatchable_tools()`（合并 `BUILTIN_TOOLS` + `registry.list_dispatchable()` 生成 Markdown 列表）+ `run_plan` 在调用 skill 前注入 `plan_input["dispatchable_tools"]`（追债项 11 canonical 收敛点之一） |
| `backend/app/agent/skills/orchestrator_reason/v1_0_0/{prompt.md,examples.yaml}` | **PR-17 修改**：`prompt.md` 补全 task_type 值域（`match / merge_candidates / profile_candidate / unknown`）+ `examples.yaml` 追加 profile_candidate few-shot |
| `backend/app/agent/skills/orchestrator_plan/v1_0_0/{skill.yaml,prompt.md}` | **PR-17 修改**：`skill.yaml.input_schema.properties` 加 `dispatchable_tools`（**不进 `required`**）+ `prompt.md` USER_TEMPLATE 加 `{{ dispatchable_tools }}` 占位与使用说明 |
| `backend/tests/test_stage5_pr17_orchestrator_routing.py` | **PR-17 新增**：TC-PR17-1..4（4 集成测试，hermetic · `engine.run_reason → run_plan → run_reflect_plan` 单元级组合 + monkeypatch `call_llm_json`） |
| `backend/tests/test_stage5_s5_04_tool_router.py` | **PR-17 追加**：TC-PR17-5（`SkillRegistry` `task_type` 冲突 fail-fast raise 负向用例） |
| `frontend/src/types/agent.ts` | **PR-18 新增**：S5-12 前端类型契约（`SSEEventType` 8 值 union / `SSEEvent<T>` / `TaskStatus` 7 值 union / `Plan`/`PlanStep` / `AgentChatRequest`/`AgentChatResponse`（`status` 3 值子集 + `initial_plan?`）/ `ExecutePlan*`/`SkipToScore*`/`CancelTaskResponse`/`TaskStatusResponse` / `ResultArtifact`+`ArtifactType` 6 值 union · 严格对齐 `backend/app/schemas/agent.py` + api-contract §3/§4） |
| `frontend/src/types/index.ts` | **PR-18 修改**：追加 `export * from './agent'` re-export |
| `frontend/src/services/agent.ts` | **PR-18 新增**：`agentApi` 对象 5 函数（`chat` / `executePlan` / `skipToScore` / `cancelTask` / `getTask`）· 429 不加中间层，调用方自行 try/catch |
| `frontend/src/hooks/useTaskStream.ts` | **PR-18 新增**：`useTaskStream` SSE Hook · fetch + ReadableStream 手写解析器 + `AbortController` 生命周期 + 按 `id` 去重升序 + `latestByType` 便捷字段 + `lastHeartbeatAt` 心跳字段 + 重连状态机（终态 `type==='result'\|\|type==='error'` 即 `closed` / 非终态 3/6/12s 指数退避 3 次后 `error`）+ `Last-Event-ID` 重连头 + 忽略 server `retry:` |
| `frontend/tests/hooks/useTaskStream.test.ts` | **PR-18 新增**：TC-S5-12-1（8 类事件解析 · system 不入 `events[]` 但进 `latestByType` + `lastHeartbeatAt`）· TC-S5-12-2（Last-Event-ID 重连头断言） |
| `frontend/tests/services/agent.test.ts` | **PR-18 新增**：TC-S5-12-3（429 抛可捕获错误） |
| `frontend/tests/types/agent.types.test.ts` | **PR-18 新增**：TC-S5-12-4（`expectTypeOf` 运行期类型校验 · 8 类型 union / 3 值子集 / union 完整性） |

### 9.6 下一位接手 Stage 5 的建议

1. **PR-19 起手**（S5-13 前端 ChatCenter + CandidateChat + 8 类事件卡片）：**必读 §9.4 陷阱 4/5/6/8/10**（陷阱 4：`chat` 异步端点，前端已在 PR-18 `agentApi.chat` 按此约定；陷阱 5：`is_disconnected()` 测试限制；陷阱 6：REST 端点内不显式 `db.begin()`；陷阱 8：dispatch 端点支持自然语言触发 candidate-* skill，卡片 `switch` 分派时**追债项 3 exhaustiveness 护栏激活**，新增 artifact `type` 必须同步改后端 `_ARTIFACT_TYPE_MAP` 与前端 `ArtifactType` union；陷阱 10：`system:cancelled` 目前不在 hook 终态判定内，若需 clean 关流 UX 需评估是否扩规则）。**基建已就位**：PR-18 交付 `types/agent.ts` + `services/agent.ts` + `hooks/useTaskStream.ts`，PR-19 直接消费。**起手 master HEAD = `dd73c4d`，后端基线 120 passed，前端基线 20 passed**。
2. **PR-19 交付清单**（TASKS §S5-13）：`pages/ChatCenter.tsx`（消息输入 → `agentApi.chat` → `useTaskStream` → 渲染 8 类事件卡片 · PlanCard 含"确认执行/取消"按钮 → `agentApi.executePlan` / `agentApi.cancelTask`）· `pages/CandidateChat.tsx`（预填 `context.candidate_ids`）· `components/agent/*Card.tsx` × 8（Thinking/Plan/ToolCall/Progress/Result/Error/Warning/System）· skip-to-score 快捷入口（选 JD + 候选人 → `agentApi.skipToScore`）· TC-S5-13-1..9（含 CANCELLED UI）。
3. **不要碰 `docs/planning/stage5/commander/` 和 `executor/` 子目录** —— 双盲评审前的初稿，已被顶层合并版覆盖。
4. **写代码前先 `git log --oneline master` 确认基线** —— Stage 5 每个 PR 都以 master HEAD 为起点建 feat 分支，走 fast-forward merge 回归。**当前 master HEAD = `dd73c4d`（PR-18 STEP6），后端基线 120 passed，前端基线 20 passed**。
5. **完成一个 PR 后**：更新本节 9.1 表格的状态与合入 commit；更新 9.4 陷阱表（如果新踩到坑）；`git push origin --delete feat/pr-NN-...` 清远端 feat 分支。
