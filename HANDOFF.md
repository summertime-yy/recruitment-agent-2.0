# 招聘 Agent 2.0 阶段性总结与交接文档

> 更新时间：2026-07-17
> 当前进度：**Stage 4（人岗匹配评分）已完成**（后端 PR-1～PR-5 + 前端 PR-6～PR-8 全链路闭环）
> 下一阶段：Stage 5（Agent 对话核心）
> 对应提交：后端 `74482ba`（PR-5 匹配核心）；前端 `9002305`（PR-7 匹配服务/页面）、PR-8 `fb75251`/`6dd41b7`/`bc9545c`（接入真实分 + 匹配面板，三段式提交：feat/test/docs）
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
| Stage 5 | Agent 对话核心 | ⏳ 未开始 | tasks 表 + Task Orchestrator（R-P-R-A-R）+ SSE + 对话中心页 |
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

#### (3) 来源渠道 source
- `resumes.source`（BOSS/拉勾/内推/猎头/邮件等），支持编辑与筛选

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
| `/api/v1/resumes/tags/meta` | GET | 聚合所有标签与来源（筛选下拉） |
| `/api/v1/resumes/{resume_id}/dedup` | POST | 去重处理（CONFIRM_DUP/IGNORE/RECHECK） |
| `/api/v1/resumes?tag=&source=&dedup_status=&candidate_status=` | GET | 多维筛选 |

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
