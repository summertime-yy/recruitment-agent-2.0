# 招聘 Agent 2.0 项目启动实施计划

**版本**: v1.0  
**日期**: 2026-07-08  
**阶段**: Stage 0 环境搭建 + Stage 1 JD管理模块（启动部分）

---

## 一、Repo Research Conclusion（项目现状分析）

### 当前状态
- **文档完成度**: 100%（PRD、UI原型、Code Wiki、架构文档、开发路线图均已完成）
- **代码完成度**: 0%（项目目录仅有文档和HTML原型，无后端/前端代码）
- **基础设施**: 未初始化（无Docker配置、无依赖配置、无数据库）
- **现有目录结构**:
  ```
  recruitment-agent-2.0/
  ├── .trae/specs/          # 规范文档
  ├── docs/                 # 架构、部署、路线图文档
  ├── recruitment-agent-prd/ # PRD HTML
  └── ui/                   # 8个页面HTML原型
  ```

### 已确认的技术栈

| 层级 | 技术选型 | 版本 |
|-----|---------|-----|
| **后端语言** | Python | 3.11+ |
| **Python包管理** | uv | latest |
| **Web框架** | FastAPI | 0.103+ |
| **数据校验** | Pydantic v2 | 2.4+ |
| **ORM** | SQLAlchemy | 2.0+ |
| **数据库迁移** | Alembic | latest |
| **Agent框架** | LangGraph | 0.0.50+ |
| **LLM适配** | 适配器模式（OpenAI兼容格式） | - |
| **代码规范** | Ruff | latest |
| **测试框架** | pytest | latest |
| **配置管理** | pydantic-settings | latest |
| **模板引擎** | Jinja2 | 3.1+ |
| **JSON Schema校验** | jsonschema | 4.19+ |
| **文件监听** | watchdog | 3.0+ |
| **数据库** | PostgreSQL | 15 |
| **向量扩展** | pgvector | 0.5+ |
| **缓存** | Redis | 7.0+ |
| **对象存储** | MinIO | RELEASE.2023-12+ |
| **前端框架** | React + TypeScript | 18.2 / 5.0 |
| **UI组件库** | Ant Design | 5.4+ |
| **前端构建** | Vite | latest |
| **状态管理** | Zustand | 4.4+ |
| **前端路由** | React Router | 6.14+ |
| **前端测试** | Vitest + RTL | latest |
| **Word解析** | python-docx | latest |
| **PDF解析** | pdfplumber | latest |
| **认证方案** | JWT (OAuth2 PasswordBearer) | - |

### LLM策略说明
采用适配器模式，所有LLM调用通过统一接口（OpenAI兼容格式），开发阶段具体API Key和base_url在需要调用时再配置，不绑定特定供应商。

---

## 二、实施步骤（本次启动范围）

本次计划覆盖 **Stage 0 项目初始化 + Stage 1 数据层与Skill基础设施**，不包含完整JD前端页面。

### Phase 1: 基础设施搭建（Day 1）

#### Task 1.1: 创建Docker Compose开发环境
- **目标**: 一键拉起 PostgreSQL（含pgvector）、Redis、MinIO
- **文件**:
  - 新建 `docker-compose.yml`（根目录）
  - 新建 `.env.example`（环境变量模板）
- **验收**:
  - `docker compose up -d` 成功启动三个服务
  - PostgreSQL可连接，pgvector扩展可用
  - Redis可连接
  - MinIO控制台可访问（http://localhost:9001）

#### Task 1.2: 初始化后端项目
- **目标**: 使用uv创建Python项目结构，安装核心依赖
- **目录结构创建**:
  ```
  backend/
  ├── pyproject.toml          # uv项目配置+依赖声明
  ├── README.md
  ├── .env                    # 本地环境变量（不提交git）
  ├── alembic.ini             # 数据库迁移配置
  ├── app/
  │   ├── __init__.py
  │   ├── main.py             # FastAPI应用入口
  │   ├── core/
  │   │   ├── __init__.py
  │   │   ├── config.py       # pydantic-settings配置
  │   │   ├── database.py     # SQLAlchemy连接+会话
  │   │   ├── redis.py        # Redis连接
  │   │   └── minio.py        # MinIO客户端
  │   ├── models/             # SQLAlchemy模型
  │   │   └── __init__.py
  │   ├── schemas/            # Pydantic请求/响应模型
  │   │   └── __init__.py
  │   ├── api/                # API路由
  │   │   └── __init__.py
  │   ├── agent/
  │   │   └── __init__.py
  │   └── services/           # 业务逻辑
  │       └── __init__.py
  ├── alembic/
  │   └── versions/
  └── tests/
      ├── __init__.py
      └── conftest.py
  ```
- **依赖清单（pyproject.toml）**:
  - 生产依赖: fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, redis, minio, jinja2, jsonschema, watchdog, python-docx, pdfplumber, python-jose[cryptography], passlib[bcrypt], python-multipart, langgraph, langchain-core, langchain-openai, numpy
  - 开发依赖: pytest, pytest-asyncio, ruff, httpx
- **验收**:
  - `uv sync` 成功安装所有依赖
  - `uv run uvicorn app.main:app --reload` 启动成功，访问 http://localhost:8000/docs 看到Swagger文档
  - Ruff配置完成（pyproject.toml中配置line-length=120等）

#### Task 1.3: 初始化前端项目
- **目标**: 使用Vite创建React+TS项目
- **目录结构**:
  ```
  frontend/
  ├── package.json
  ├── vite.config.ts
  ├── tsconfig.json
  ├── tsconfig.node.json
  ├── index.html
  ├── src/
  │   ├── main.tsx
  │   ├── App.tsx
  │   ├── vite-env.d.ts
  │   ├── api/            # Axios封装
  │   ├── components/     # 公共组件
  │   ├── pages/          # 页面组件
  │   ├── store/          # Zustand状态
  │   └── types/          # TS类型定义
  └── tests/
  ```
- **依赖清单**:
  - 生产依赖: react, react-dom, antd, @ant-design/icons, zustand, react-router-dom, axios
  - 开发依赖: @types/react, @types/react-dom, @vitejs/plugin-react, typescript, vite, vitest, @testing-library/react
- **验收**:
  - `npm install` 成功
  - `npm run dev` 启动成功，看到Vite+React欢迎页

#### Task 1.4: 根目录配置文件
- **文件**:
  - `.gitignore`（忽略.env、__pycache__、node_modules等）
  - `README.md`（项目启动说明）
- **验收**:
  - 仓库结构清晰，敏感文件不被git跟踪

---

### Phase 2: 数据层 - 数据库表与迁移（Day 2）

#### Task 2.1: 创建SQLAlchemy模型
- **文件**:
  - 新建 `backend/app/models/base.py`（Base类、通用字段如id/created_at/updated_at）
  - 新建 `backend/app/models/jd.py`（jd_templates表、jds表模型）
  - 新建 `backend/app/models/skill.py`（skills表、skill_versions表、skill_execution_logs表模型）
  - 更新 `backend/app/models/__init__.py`（导出所有模型）
- **表结构**: 严格按照 [code-wiki.md](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/docs/code-wiki.md) 和 [architecture-modules.md](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/docs/architecture-modules.md) 中的DDL定义

#### Task 2.2: 配置Alembic迁移
- **目标**: 初始化Alembic，配置与SQLAlchemy模型的自动检测
- **文件**:
  - 更新 `backend/alembic.ini`（数据库连接字符串）
  - 新建/更新 `backend/alembic/env.py`（配置target_metadata）
- **操作**:
  - 执行 `uv run alembic init alembic`（如果需要）
  - 执行 `uv run alembic revision --autogenerate -m "init tables"` 生成初始迁移
  - 执行 `uv run alembic upgrade head` 应用迁移
- **验收**:
  - 数据库中成功创建所有表
  - 索引正确创建
  - pgvector扩展已安装

---

### Phase 3: Skill基础设施 + 第一个Skill（Day 3-5）

#### Task 3.1: 实现Skill Registry核心框架
- **目标**: 实现MVP简化版Skill加载与执行框架
- **文件**:
  - 新建 `backend/app/agent/base_skill.py`（BaseSkill基类，包含元数据定义、输入校验、输出校验、重试逻辑）
  - 新建 `backend/app/agent/skill_registry.py`（Skill注册表，单例模式，加载/获取/注册Skill）
  - 新建 `backend/app/agent/skill_executor.py`（Skill执行器：渲染prompt→调用工具链→调用LLM→校验输出→记录日志）
  - 新建 `backend/app/agent/llm_adapter.py`（LLM适配器，统一调用接口，支持OpenAI兼容格式）
  - 新建 `backend/app/agent/skills/`（Skill定义根目录）
- **MVP简化说明（不做）**:
  - 暂不实现SkillVersionManager（灰度/A/B测试在Stage 5实现）
  - 暂不实现watchdog热更新（Stage 5实现）
  - 暂不实现SkillMatcher意图匹配（直接通过skill_id调用，Stage 5再集成到LangGraph）
  - 暂不实现Redis/MinIO加载（先从本地文件系统加载，后续再扩展）
- **MVP必须做**:
  - Skill基类定义完整
  - 从本地YAML/JSON/MD文件加载Skill
  - Jinja2模板渲染
  - jsonschema输出校验
  - 执行日志写入数据库
  - 统一LLM调用接口

#### Task 3.2: 创建JD生成Skill v1.0.0
- **目标**: 第一个可运行的Skill，验证整条链路
- **目录结构**:
  ```
  backend/app/agent/skills/jd_generation/
  ├── v1_0_0/
  │   ├── skill.yaml          # Skill元数据（skill_id/名称/描述/输入schema/输出schema）
  │   ├── prompt.md           # Prompt模板（Jinja2格式，含系统提示词）
  │   ├── tool_chain.json     # 工具链配置（MVP先简化为仅调用LLM，后续加工具）
  │   └── examples.yaml       # 3-5个few-shot examples
  └── __init__.py
  ```
- **Skill元数据**:
  - skill_id: `job_description_generation`
  - 输入字段: position_name, department, experience_level, required_skills (list), job_type, location
  - 输出字段: title, department, summary, responsibilities (list), requirements (list), required_skills (list), preferred_skills (list), salary_range (optional), location, compliance_check (object)
- **验收标准（关键！）**:
  - 给定标准输入，连续10次调用LLM生成JD
  - 必填字段完整度 > 95%
  - 输出100%符合JSON Schema
  - 合规检查（性别歧视/年龄歧视关键词）正常工作

#### Task 3.3: 编写JD Skill验收测试
- **文件**:
  - 新建 `backend/tests/test_jd_skill.py`
- **测试用例**:
  - test_skill_load: Skill能从文件正确加载元数据
  - test_prompt_render: Prompt模板渲染正确（变量插值工作）
  - test_output_validation: 非法输出（缺字段、格式错）能被正确拒绝
  - test_jd_generation_e2e: 端到端调用（mock LLM或真实调用），验证输出结构

---

### Phase 4: JD管理后端API（Day 6-7）

#### Task 4.1: JD CRUD API
- **文件**:
  - 新建 `backend/app/schemas/jd.py`（JD Pydantic模型）
  - 新建 `backend/app/services/jd_service.py`（JD业务逻辑）
  - 新建 `backend/app/api/jd.py`（JD路由：GET/POST/PUT/DELETE）
  - 更新 `backend/app/api/__init__.py`（注册路由）
- **API端点**:
  - `GET /api/v1/jd/templates` - JD模板列表
  - `POST /api/v1/jd/templates` - 创建JD模板
  - `GET /api/v1/jds` - JD列表（分页）
  - `POST /api/v1/jds` - 从输入生成JD（调用JD Skill）
  - `GET /api/v1/jds/{jd_id}` - 获取JD详情
  - `PUT /api/v1/jds/{jd_id}` - 更新JD
  - `DELETE /api/v1/jds/{jd_id}` - 删除JD

#### Task 4.2: Skill执行API
- **文件**:
  - 新建 `backend/app/api/skills.py`
- **API端点**:
  - `GET /api/v1/skills` - 已注册Skill列表
  - `POST /api/v1/skills/{skill_id}/execute` - 执行指定Skill
  - `GET /api/v1/skills/{skill_id}/executions` - Skill执行历史

#### Task 4.3: 测试验证
- 所有API端点可通过Swagger文档测试
- CRUD操作正常
- JD生成API能成功调用Skill并返回结构化JD
- 错误处理正常（非法输入返回422，内部错误返回500）

---

## 三、本次启动计划不包含的内容

| 模块 | 推迟到哪个Stage |
|-----|----------------|
| JD管理前端页面 | Stage 1 后半段（当前Phase 4完成后） |
| 完整LangGraph R-P-R-A-R流程 | Stage 5 |
| Skill热更新（watchdog+Redis广播） | Stage 5 |
| Skill版本管理（灰度/A/B测试） | Stage 5 |
| 简历解析Skill | Stage 3 |
| 评分引擎Skill | Stage 4 |
| 用户认证JWT实现 | Stage 1后半段（API做完后加） |
| MinIO文件上传 | Stage 3（简历上传时需要） |

---

## 四、依赖关系与执行顺序

```
Phase 1 (基础设施) ──┐
                     ├──> Phase 2 (数据层) ──> Phase 3 (Skill基础设施+JD Skill) ──> Phase 4 (API)
Phase 1 (前端)  ─────┘                                                    └──> (后续：前端页面)
```

- Phase 1 内 Task 1.1/1.2/1.3 可并行（Docker、后端、前端初始化互不依赖）
- Phase 2 必须等 Phase 1 后端初始化完成
- Phase 3 必须等 Phase 2 数据模型完成
- Phase 4 必须等 Phase 3 JD Skill完成

---

## 五、风险与处理

| 风险 | 影响 | 应对策略 |
|-----|------|---------|
| LLM输出不稳定，无法通过95%完整度验收 | Phase 3延期 | 先优化prompt和few-shot examples，必要时增加规则校验兜底；允许初期放宽到90%，后续迭代提升 |
| uv在Windows上有兼容性问题 | 环境搭建失败 | 备用方案：回退到pip+venv |
| pgvector安装问题 | 数据库迁移失败 | Docker镜像使用已预装pgvector的postgres镜像（如pgvector/pgvector:pg15） |
| Skill设计过复杂，MVP难以快速验证 | Phase 3延期 | 严格按MVP简化方案，先跑通"加载→渲染→调用LLM→校验"主链路，高级功能后续迭代 |

---

## 六、Phase 1-4 验收标准（Definition of Done）

1. **基础设施**: Docker三服务可一键启动，后端FastAPI Swagger可访问，前端Vite dev server可访问
2. **数据库**: 所有表成功创建，Alembic迁移可正常执行和回滚
3. **Skill框架**: Skill Registry能正确加载JD Skill，SkillExecutor能执行并通过输出校验
4. **JD生成质量**: 连续10次生成，必填字段完整度>95%，Schema合规率100%
5. **API**: JD CRUD和Skill执行API全部可通过Swagger测试，返回格式正确

---

## 七、Phase 4完成后的下一步

Phase 1-4验收通过后，立即进入：
1. JD管理前端页面开发（page-3-jd-management.html对应的React页面）
2. 用户认证（JWT登录注册）
3. Stage 1验收复盘，准备进入Stage 2（人才库）或开始简历解析Skill预研
