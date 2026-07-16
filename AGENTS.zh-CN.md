# 仓库指南

**recruitment-agent-2.0** 贡献指南 —— AI 智能招聘助手，采用 Monorepo 架构：
后端 Python 3.11 / FastAPI + 前端 React 18 / TypeScript / Ant Design 5。

## 项目结构与模块组织

```
backend/                    # Python FastAPI 后端服务（uv 管理）
  app/
    agent/                  # AI Agent 核心（技能注册、LLM适配器）
      skills/<id>/vX_Y_Z/   # 版本化 YAML 技能配置
    api/v1/endpoints/       # REST API 路由
    core/                   # 配置、安全、依赖注入
    models/                 # SQLAlchemy ORM 模型
    schemas/                # Pydantic 请求/响应模型
    services/               # 业务逻辑层
  alembic/versions/         # 数据库迁移脚本
  tests/                    # pytest 测试用例

frontend/                   # React 前端应用（Vite 构建）
  src/
    api/                    # Axios 封装与拦截器
    components/             # 可复用组件（含候选人状态相关）
    layouts/                # 页面布局
    pages/                  # 页面组件（简历列表、详情等）
    services/               # API 服务封装
    store/                  # Zustand 状态管理
    types/                  # TypeScript 类型定义
    utils/                  # 工具函数

docs/                       # 项目文档
ui/                         # HTML 原型
docker-compose.yml          # 基础设施编排（Postgres、Redis、MinIO）
.env.example                # 环境变量模板（勿提交 .env）
```

## 构建、测试与开发命令

### 基础设施
```bash
docker compose up -d        # 启动 PostgreSQL、Redis、MinIO
```

### 后端（在 `backend/` 目录下执行）
```bash
uv sync                     # 安装依赖
uv run uvicorn app.main:app --reload --port 8000   # 开发服务器
uv run alembic upgrade head                        # 执行数据库迁移
uv run alembic revision --autogenerate -m "<说明>"  # 创建新迁移
uv run pytest                                       # 运行测试
uv run ruff check .                                 # Lint 检查
uv run ruff format .                                # 代码格式化
```

### 前端（在 `frontend/` 目录下执行）
```bash
npm install                 # 安装依赖
npm run dev                 # Vite 开发服务器 :5173（代理 /api → :8000）
npm run build               # TypeScript 编译 + Vite 生产构建
npm run lint                # ESLint 检查
```

## 编码风格与命名规范

### Python 后端
- **Linter**: Ruff，配置 `line-length=120`，目标 Python 3.11+
- **启用规则**: `E, F, I, W, N, UP`（忽略 `E501` 行长度限制）
- **缩进**: 4 空格；**命名**: 模块/函数/变量用 `snake_case`，类用 `PascalCase`
- **异步优先**: 端点使用 `async def`，SQLAlchemy 使用异步会话
- **类型注解**: 使用 `X | None` 替代 `Optional[X]`（UP045 规则）

### TypeScript 前端
- **严格模式**: `strict: true`，启用 `noUnusedLocals` / `noUnusedParameters`
- **路径别名**: 使用 `@/` 别名指向 `src/` 目录
- **命名**: 组件文件 `PascalCase.tsx`，工具/Hook `camelCase.ts`
- **导出**: 优先使用命名导出（named exports）

### AI 技能（Skills）
- 每个技能一个目录：`app/agent/skills/<skill_id>/vX_Y_Z/`
- 包含 `skill.yaml`（元数据）、`prompt.md`（提示词）、可选 `examples.yaml`
- 修改时递增版本号目录，注册表自动加载最高版本

### 数据库迁移
- 命名格式：`<rev>_<snake_case描述>.py`
- 使用 Alembic autogenerate 生成，人工审核后提交

## 测试指南

### 后端
- **框架**: pytest + pytest-asyncio（`asyncio_mode=auto`，`testpaths=["tests"]`）
- **Fixture**: 使用 `conftest.py` 中的 `client` fixture（httpx `ASGITransport`）
- **命名规范**: 文件 `test_<模块>.py`，函数 `test_<行为>`
- **Mock**: 异步 DB 和 LLM 调用需要 mock
- **覆盖要求**: 新增端点和 Service 必须有对应测试

### 前端
- 测试位于 `frontend/tests/` 目录
- 引入 Vitest 等框架后再补充具体测试用例

### 提交前必查
```bash
cd backend && uv run pytest                # 后端测试通过
cd frontend && npm run lint && npm run build  # 前端 lint + 构建
```

## 提交与 Pull Request 规范

### Commit Message 格式
采用 **Conventional Commits** 规范：
- `init:` 初始化
- `feat:` 新功能（如 `feat: add candidate status transition endpoint`）
- `fix:` Bug 修复
- `docs:` 文档更新
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 杂项/依赖更新
- 标题 ≤ 72 字符，关联 issue 放在正文

### Pull Request 要求
- 描述变更内容及其原因
- 列出验证步骤和测试方法
- 注明是否涉及数据库迁移或 `.env` 变更
- API 或数据模型变更需同步更新 `docs/` 文档
- UI 变更必须附带截图
- 确保 `uv run pytest` 和 `npm run build` 本地通过

## Agent 与 LLM 注意事项

- 所有 LLM 调用统一走 `app/agent/llm_adapter.py`（`ChatOpenAI`，OpenAI 兼容接口）
- **设置 `max_retries=0`**：在 Skill 层和 Adapter 层都设为 0，避免重试叠加超时
- 不要传 `reasoning_effort` 参数（模型不支持）
- 保持 `LLM_MAX_TOKENS=4096`
- **FastAPI 路由顺序很重要**：具体路径（如 `/{resume_id}/preview`）必须定义在通用路径（如 `/{resume_id}`）之前
- **禁止提交** `backend/.env`（已在 .gitignore 中），复制 `.env.example` 并填写 `LLM_API_KEY` / `LLM_BASE_URL`
