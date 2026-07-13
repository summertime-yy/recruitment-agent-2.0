# 智能招聘 Agent 项目部署与运维指南

**版本:** v1.0  
**更新日期:** 2026-07-07  
**文档性质:** 项目运行与部署技术指南

---

## 一、开发环境搭建指南

### 1.1 前端开发环境配置

#### Node.js 安装

**推荐版本:** Node.js 18.x LTS

**Windows 安装方式:**
1. 访问 https://nodejs.org/en/download/
2. 下载 Windows Installer (64-bit)
3. 运行安装程序,选择默认安装路径
4. 安装完成后验证:
   ```bash
   node --version  # 应显示 v18.x.x
   npm --version   # 应显示 9.x.x
   ```

**Linux/Mac 安装方式 (使用 nvm):**
```bash
# 安装 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc

# 安装 Node.js 18
nvm install 18
nvm use 18

# 验证安装
node --version
npm --version
```

#### React 项目初始化

```bash
# 进入前端目录
cd frontend

# 安装项目依赖
npm install

# 验证依赖安装
npm list react react-dom antd zustand

# 配置环境变量 (创建 .env 文件)
cat > .env << EOF
VITE_API_BASE_URL=http://localhost:8000/api
VITE_SSE_URL=http://localhost:8000/api/agent/stream
VITE_APP_TITLE=智能招聘Agent
EOF

# 启动开发服务器
npm run dev
```

**关键依赖说明:**

| 依赖包 | 版本 | 安装命令 | 用途 |
|-------|-----|---------|-----|
| react | ^18.2.0 | npm install react | React 核心库 |
| react-dom | ^18.2.0 | npm install react-dom | React DOM渲染 |
| antd | ^5.4.0 | npm install antd | UI组件库 |
| zustand | ^4.4.0 | npm install zustand | 状态管理 |
| react-router-dom | ^6.14.0 | npm install react-router-dom | 路由管理 |
| axios | ^1.4.0 | npm install axios | HTTP客户端 |
| typescript | ^5.0.0 | npm install -D typescript | TypeScript编译 |
| vite | ^5.0.0 | npm install -D vite | 构建工具 |

#### TypeScript 配置

创建 `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### 1.2 后端开发环境配置

#### Python 安装

**推荐版本:** Python 3.11.x

**Windows 安装方式:**
1. 访问 https://python.org/downloads/
2. 下载 Python 3.11 Windows Installer
3. 运行安装程序,勾选 "Add Python to PATH"
4. 验证安装:
   ```bash
   python --version  # 应显示 Python 3.11.x
   pip --version     # 应显示 pip 23.x.x
   ```

**Linux/Mac 安装方式:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Mac (使用 Homebrew)
brew install python@3.11

# 验证安装
python3.11 --version
```

#### 虚拟环境创建

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 验证虚拟环境
which python  # 应显示 venv/bin/python
python --version
```

#### FastAPI 项目初始化

```bash
# 安装项目依赖
pip install -r requirements.txt

# 关键依赖列表 (requirements.txt)
cat > requirements.txt << EOF
fastapi==0.103.0
uvicorn[standard]==0.23.0
pydantic==2.4.0
langgraph==0.0.50
langchain==0.0.330
openai==0.28.0
sqlalchemy==2.0.20
asyncpg==0.28.0
redis==5.0.0
minio==7.1.0
alembic==1.12.0
python-dotenv==1.0.0
prometheus-client==0.17.0
EOF

# 配置环境变量 (创建 .env 文件)
cat > .env << EOF
# 数据库配置
DATABASE_URL=postgresql://recruitment_agent:your_password@localhost:5432/recruitment_agent

# Redis配置
REDIS_URL=redis://localhost:6379/0

# MinIO配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=False

# LLM API配置
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o

# 应用配置
APP_ENV=development
APP_DEBUG=true
APP_PORT=8000
EOF

# 初始化数据库迁移
alembic upgrade head

# 启动后端服务
uvicorn main:app --reload --port 8000
```

**关键依赖说明:**

| 依赖包 | 版本 | 安装命令 | 用途 |
|-------|-----|---------|-----|
| fastapi | ^0.103.0 | pip install fastapi | Web框架 |
| uvicorn | ^0.23.0 | pip install uvicorn[standard] | ASGI服务器 |
| pydantic | ^2.4.0 | pip install pydantic | 数据校验 |
| langgraph | ^0.0.50 | pip install langgraph | Agent框架 |
| sqlalchemy | ^2.0.20 | pip install sqlalchemy | ORM |
| asyncpg | ^0.28.0 | pip install asyncpg | PostgreSQL异步驱动 |
| redis | ^5.0.0 | pip install redis | Redis客户端 |
| minio | ^7.1.0 | pip install minio | MinIO客户端 |
| alembic | ^1.12.0 | pip install alembic | 数据库迁移 |

### 1.3 PostgreSQL 安装与初始化

#### PostgreSQL 15 安装

**Windows 安装方式:**
1. 访问 https://postgresql.org/download/windows/
2. 下载 PostgreSQL 15 Windows Installer
3. 运行安装程序,设置密码和端口(默认5432)
4. 安装完成后验证:
   ```bash
   psql --version  # 应显示 psql (PostgreSQL) 15.x
   ```

**Linux 安装方式 (Ubuntu/Debian):**
```bash
# 安装 PostgreSQL 15
sudo apt update
sudo apt install postgresql-15 postgresql-contrib-15

# 启动 PostgreSQL 服务
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 验证服务状态
sudo systemctl status postgresql
```

**Mac 安装方式 (Homebrew):**
```bash
# 安装 PostgreSQL 15
brew install postgresql@15

# 启动 PostgreSQL 服务
brew services start postgresql@15

# 验证安装
psql --version
```

#### 数据库初始化

```bash
# 创建数据库用户和数据库
psql -U postgres -c "CREATE USER recruitment_agent WITH PASSWORD 'your_password';"
psql -U postgres -c "CREATE DATABASE recruitment_agent OWNER recruitment_agent;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE recruitment_agent TO recruitment_agent;"

# 安装 PGVector 扩展 (向量索引)
psql -U recruitment_agent -d recruitment_agent -c "CREATE EXTENSION vector;"

# 验证扩展安装
psql -U recruitment_agent -d recruitment_agent -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

#### 数据库连接测试

```python
# 测试数据库连接 (backend/test_db_connection.py)
import asyncio
import asyncpg

async def test_connection():
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='recruitment_agent',
        password='your_password',
        database='recruitment_agent'
    )
    
    # 测试查询
    result = await conn.fetchval("SELECT version();")
    print(f"PostgreSQL版本: {result}")
    
    # 测试向量扩展
    vector_ext = await conn.fetchval("SELECT extversion FROM pg_extension WHERE extname='vector';")
    print(f"PGVector版本: {vector_ext}")
    
    await conn.close()

asyncio.run(test_connection())
```

### 1.4 Redis 安装与配置

#### Redis 7 安装

**Windows 安装方式 (使用 Docker):**
```bash
# 拉取 Redis 镜像
docker pull redis:7-alpine

# 启动 Redis 容器
docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine redis-server --appendonly yes

# 验证 Redis 运行
docker ps | grep redis
```

**Linux 安装方式 (Ubuntu/Debian):**
```bash
# 安装 Redis 7
sudo apt update
sudo apt install redis-server

# 启动 Redis 服务
sudo systemctl start redis-server
sudo systemctl enable redis-server

# 验证服务状态
sudo systemctl status redis-server
```

**Mac 安装方式 (Homebrew):**
```bash
# 安装 Redis
brew install redis

# 启动 Redis 服务
brew services start redis

# 验证安装
redis-cli --version
```

#### Redis 持久化配置

编辑 `/etc/redis/redis.conf` (Linux) 或 `redis.conf` (Windows/Docker):

```conf
# RDB 持久化配置
save 900 1      # 15分钟内至少1个key变化则保存
save 300 10     # 5分钟内至少10个key变化则保存
save 60 10000   # 1分钟内至少10000个key变化则保存

# AOF 持久化配置
appendonly yes          # 启用AOF持久化
appendfilename "appendonly.aof"
appendfsync everysec    # 每秒同步一次

# 混合持久化 (RDB+AOF)
aof-use-rdb-preamble yes
```

#### Redis 连接测试

```bash
# 测试 Redis 连接
redis-cli ping
# 应返回: PONG

# 测试基本操作
redis-cli set test_key "test_value"
redis-cli get test_key
redis-cli del test_key
```

### 1.5 MinIO 文件存储配置

#### MinIO 安装 (Docker 方式)

```bash
# 拉取 MinIO 镜像
docker pull minio/minio:RELEASE.2023-12-23T07-45-05Z

# 启动 MinIO 服务
docker run -d --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  -v /data/minio:/data \
  minio/minio server /data --console-address ":9001"

# 验证 MinIO 运行
docker ps | grep minio
```

#### MinIO 存储桶创建

```bash
# 安装 MinIO 客户端 mc
# Windows: 下载 https://dl.min.io/client/mc/release/windows-amd64/mc.exe
# Linux/Mac:
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# 配置 MinIO 连接
mc alias set myminio http://localhost:9000 minioadmin minioadmin

# 创建存储桶
mc mb myminio/resumes
mc mb myminio/jd-attachments
mc mb myminio/agent-logs

# 设置存储桶访问策略 (公开读取)
mc anonymous set download myminio/resumes

# 验证存储桶列表
mc ls myminio
```

#### MinIO 连接测试

```python
# 测试 MinIO 连接 (backend/test_minio_connection.py)
from minio import Minio

client = Minio(
    'localhost:9000',
    access_key='minioadmin',
    secret_key='minioadmin',
    secure=False
)

# 测试存储桶列表
buckets = client.list_buckets()
for bucket in buckets:
    print(f"存储桶: {bucket.name}, 创建时间: {bucket.creation_date}")

# 测试上传文件
client.fput_object('resumes', 'test.pdf', 'test_resume.pdf')
print("文件上传成功")

# 测试下载文件
client.fget_object('resumes', 'test.pdf', 'downloaded_test.pdf')
print("文件下载成功")
```

### 1.6 Agent 服务配置 (LLM API)

#### OpenAI API 配置

```bash
# 获取 OpenAI API Key
# 访问: https://platform.openai.com/api-keys
# 创建新的 API Key 并保存

# 配置环境变量
export OPENAI_API_KEY="sk-your-api-key-here"
export OPENAI_MODEL="gpt-4o"  # 推荐使用 gpt-4o

# 测试 API 连接
python -c "
import openai
openai.api_key = 'sk-your-api-key-here'
response = openai.ChatCompletion.create(
    model='gpt-4o',
    messages=[{'role': 'user', 'content': 'Hello'}]
)
print(response.choices[0].message.content)
"
```

#### Azure OpenAI 配置 (可选)

```bash
# Azure OpenAI 配置 (企业场景)
export AZURE_OPENAI_API_KEY="your-azure-key"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-deployment"

# 测试 Azure OpenAI 连接
python -c "
import openai
openai.api_type = 'azure'
openai.api_base = 'https://your-resource.openai.azure.com/'
openai.api_version = '2023-12-01-preview'
openai.api_key = 'your-azure-key'
response = openai.ChatCompletion.create(
    engine='gpt-4o-deployment',
    messages=[{'role': 'user', 'content': 'Hello'}]
)
print(response.choices[0].message.content)
"
```

---

## 二、生产环境部署指南

### 2.1 Docker Compose 配置

#### 完整 Docker Compose 文件

创建 `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # PostgreSQL 数据库
  postgres:
    image: postgres:15-alpine
    container_name: recruitment-postgres
    environment:
      POSTGRES_USER: recruitment_agent
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: recruitment_agent
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U recruitment_agent"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis 缓存
  redis:
    image: redis:7-alpine
    container_name: recruitment-redis
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # MinIO 文件存储
  minio:
    image: minio/minio:RELEASE.2023-12-23T07-45-05Z
    container_name: recruitment-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
    restart: unless-stopped

  # FastAPI 后端服务
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: recruitment-backend
    environment:
      DATABASE_URL: postgresql://recruitment_agent:${DB_PASSWORD}@postgres:5432/recruitment_agent
      REDIS_URL: redis://redis:6379/0?password=${REDIS_PASSWORD}
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_MODEL: ${OPENAI_MODEL}
      APP_ENV: production
      APP_DEBUG: false
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./backend/logs:/app/logs
    restart: unless-stopped

  # React 前端服务
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: recruitment-frontend
    environment:
      VITE_API_BASE_URL: http://localhost:8000/api
      VITE_SSE_URL: http://localhost:8000/api/agent/stream
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

  # Prometheus 监控
  prometheus:
    image: prom/prometheus:v2.45.0
    container_name: recruitment-prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: unless-stopped

  # Grafana 可视化
  grafana:
    image: grafana/grafana:10.0.0
    container_name: recruitment-grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_INSTALL_PLUGINS: redis-datasource
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    depends_on:
      - prometheus
      - redis
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  minio_data:
  prometheus_data:
  grafana_data:
```

#### 后端 Dockerfile

创建 `backend/Dockerfile`:

```dockerfile
# Python 3.11 基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 前端 Dockerfile

创建 `frontend/Dockerfile`:

```dockerfile
# Node.js 18 构建阶段
FROM node:18-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖
RUN npm install

# 复制应用代码
COPY . .

# 构建应用
RUN npm run build

# Nginx 生产阶段
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
```

#### Nginx 配置文件

创建 `frontend/nginx.conf`:

```nginx
server {
    listen 80;
    server_name localhost;

    root /usr/share/nginx/html;
    index index.html;

    # 前端路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSE 流式消息代理 (关键配置)
    location /api/agent/stream {
        proxy_pass http://backend:8000/api/agent/stream;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;          # 禁用缓冲,支持流式传输
        proxy_cache off;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 2.2 环境变量配置清单

创建 `.env.production`:

```bash
# 数据库配置
DB_PASSWORD=your_secure_password_here
DATABASE_URL=postgresql://recruitment_agent:your_secure_password_here@postgres:5432/recruitment_agent

# Redis配置
REDIS_PASSWORD=your_redis_password_here
REDIS_URL=redis://redis:6379/0?password=your_redis_password_here

# MinIO配置
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_minio_secret_here
MINIO_ENDPOINT=minio:9000
MINIO_SECURE=false

# LLM API配置
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o

# Grafana配置
GRAFANA_PASSWORD=your_grafana_admin_password

# 应用配置
APP_ENV=production
APP_DEBUG=false
APP_PORT=8000
```

**关键配置项说明:**

| 配置项 | 示例值 | 说明 | 安全要求 |
|-------|-------|-----|---------|
| DB_PASSWORD | `your_secure_password` | PostgreSQL密码 | 必须16位以上,包含大小写数字特殊字符 |
| REDIS_PASSWORD | `your_redis_password` | Redis密码 | 必须12位以上 |
| MINIO_SECRET_KEY | `your_minio_secret` | MinIO密钥 | 必须20位以上 |
| OPENAI_API_KEY | `sk-...` | OpenAI API密钥 | 必须有效且有GPT-4权限 |
| GRAFANA_PASSWORD | `admin_password` | Grafana管理员密码 | 必须8位以上 |

### 2.3 数据库初始化脚本

#### SQL Migration 文件示例

创建 `migrations/001_initial_schema.sql`:

```sql
-- 启用 PGVector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- Task表: 任务元数据
CREATE TABLE tasks (
    task_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    task_type VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'CREATED',
    stage VARCHAR(30),
    jd_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);

-- JD表: 职位描述
CREATE TABLE jds (
    jd_id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    level VARCHAR(20),
    skills_required JSONB,
    requirements JSONB,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'ACTIVE'
);

-- Candidate表: 候选人
CREATE TABLE candidates (
    candidate_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20),
    education JSONB,
    experience JSONB,
    skills JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Resume表: 简历
CREATE TABLE resumes (
    resume_id SERIAL PRIMARY KEY,
    candidate_id VARCHAR(50) REFERENCES candidates(candidate_id),
    file_path TEXT NOT NULL,
    parse_status VARCHAR(20) DEFAULT 'PENDING',
    parsed_data JSONB,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    parsed_at TIMESTAMP
);

-- Score表: 评分
CREATE TABLE scores (
    score_id SERIAL PRIMARY KEY,
    candidate_id VARCHAR(50) REFERENCES candidates(candidate_id),
    jd_id VARCHAR(50) REFERENCES jds(jd_id),
    skill_match_score FLOAT,
    experience_score FLOAT,
    education_score FLOAT,
    stability_score FLOAT,
    potential_score FLOAT,
    total_score FLOAT,
    evidence JSONB,
    scored_by VARCHAR(50),
    scored_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(candidate_id, jd_id)
);

-- Push表: 推送记录
CREATE TABLE pushes (
    push_id SERIAL PRIMARY KEY,
    candidate_ids JSONB NOT NULL,
    jd_id VARCHAR(50) REFERENCES jds(jd_id),
    target_user VARCHAR(50) NOT NULL,
    push_channel VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Feedback表: 反馈
CREATE TABLE feedbacks (
    feedback_id SERIAL PRIMARY KEY,
    candidate_id VARCHAR(50) REFERENCES candidates(candidate_id),
    push_id INT REFERENCES pushes(push_id),
    feedback_type VARCHAR(20) NOT NULL,
    reasons JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Template表: JD模板
CREATE TABLE templates (
    template_id VARCHAR(50) PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    template_type VARCHAR(30),
    template_content JSONB,
    usage_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Config表: 系统配置
CREATE TABLE configs (
    config_id VARCHAR(50) PRIMARY KEY,
    config_type VARCHAR(30),
    config_key VARCHAR(100) UNIQUE,
    config_value JSONB,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Analytics表: 指标统计
CREATE TABLE analytics (
    analytic_id SERIAL PRIMARY KEY,
    metric_type VARCHAR(50),
    metric_value FLOAT,
    metric_date DATE,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 向量索引表 (PGVector)
CREATE TABLE candidate_vectors (
    candidate_id VARCHAR(50) PRIMARY KEY REFERENCES candidates(candidate_id),
    embedding VECTOR(1536),
    metadata JSONB
);

CREATE TABLE jd_vectors (
    jd_id VARCHAR(50) PRIMARY KEY REFERENCES jds(jd_id),
    embedding VECTOR(1536),
    metadata JSONB
);

-- 创建索引
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_jds_status ON jds(status);
CREATE INDEX idx_candidates_email ON candidates(email);
CREATE INDEX idx_scores_candidate_jd ON scores(candidate_id, jd_id);
CREATE INDEX idx_pushes_status ON pushes(status);
CREATE INDEX idx_feedbacks_candidate ON feedbacks(candidate_id);
CREATE INDEX idx_templates_type ON templates(template_type);
CREATE INDEX idx_configs_key ON configs(config_key);
CREATE INDEX idx_analytics_date ON analytics(metric_date);
```

### 2.4 服务启动流程

#### 启动顺序与健康检查

```bash
# 1. 启动 Docker Compose 服务
docker-compose up -d

# 2. 检查服务状态
docker-compose ps

# 3. 查看服务日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 4. 验证数据库连接
docker exec recruitment-postgres psql -U recruitment_agent -d recruitment_agent -c "SELECT version();"

# 5. 验证 Redis 连接
docker exec recruitment-redis redis-cli -a your_redis_password ping

# 6. 验证 MinIO 连接
docker exec recruitment-minio curl -f http://localhost:9000/minio/health/live

# 7. 验证后端 API
curl http://localhost:8000/api/health

# 8. 验证前端应用
curl http://localhost:80

# 9. 验证 Prometheus
curl http://localhost:9090/-/healthy

# 10. 验证 Grafana
curl http://localhost:3000/api/health
```

#### 服务启动顺序图

```mermaid
graph LR
    A[1. PostgreSQL] --> B[2. Redis]
    B --> C[3. MinIO]
    C --> D[4. Backend<br/>FastAPI]
    D --> E[5. Frontend<br/>React]
    D --> F[6. Prometheus]
    F --> G[7. Grafana]

    A -.->|健康检查| D
    B -.->|健康检查| D
    C -.->|健康检查| D
```

---

## 三、监控与运维指南

### 3.1 Prometheus 配置方案

#### Prometheus 配置文件

创建 `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s      # 默认抓取频率
  evaluation_interval: 15s  # 规则评估频率

# 告警规则文件
rule_files:
  - "alert_rules.yml"

# 抓取目标配置
scrape_configs:
  # Prometheus 自身监控
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # FastAPI 后端应用监控
  - job_name: 'recruitment-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'

  # PostgreSQL 监控 (需安装 postgres_exporter)
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Redis 监控 (需安装 redis_exporter)
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  # Node 系统监控 (需安装 node_exporter)
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

#### Prometheus 告警规则

创建 `monitoring/alert_rules.yml`:

```yaml
groups:
  - name: recruitment_agent_alerts
    rules:
      # API 错误率告警
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "高API错误率"
          description: "API 5xx错误率超过5%,当前值: {{ $value }}"

      # API 响应延迟告警
      - alert: HighResponseLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "高API响应延迟"
          description: "API P95响应延迟超过30秒,当前值: {{ $value }}s"

      # 任务失败率告警
      - alert: HighTaskFailureRate
        expr: rate(task_failures_total[1h]) > 0.1
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "高任务失败率"
          description: "任务失败率超过10%,当前值: {{ $value }}"

      # PostgreSQL 连接失败告警
      - alert: PostgresConnectionFailed
        expr: pg_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL连接失败"
          description: "PostgreSQL数据库连接失败,请检查数据库服务"

      # Redis 连接失败告警
      - alert: RedisConnectionFailed
        expr: redis_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis连接失败"
          description: "Redis缓存服务连接失败,请检查Redis服务"

      # 内存使用率告警
      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "高内存使用率"
          description: "内存使用率超过85%,当前值: {{ $value | humanizePercentage }}"
```

### 3.2 Grafana 看板配置

#### Grafana 数据源配置

创建 `monitoring/grafana/datasources/prometheus.yml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

#### Grafana 看板 JSON (示例)

创建 `monitoring/grafana/dashboards/recruitment_agent.json`:

```json
{
  "dashboard": {
    "title": "智能招聘Agent监控看板",
    "panels": [
      {
        "title": "API请求总数",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{path}}"
          }
        ],
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8}
      },
      {
        "title": "API响应延迟(P95)",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "P95延迟"
          }
        ],
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8}
      },
      {
        "title": "任务完成率",
        "type": "singlestat",
        "targets": [
          {
            "expr": "rate(task_completions_total[1h]) / (rate(task_completions_total[1h]) + rate(task_failures_total[1h]))",
            "legendFormat": "完成率"
          }
        ],
        "gridPos": {"x": 0, "y": 8, "w": 6, "h": 4}
      },
      {
        "title": "简历解析成功率",
        "type": "singlestat",
        "targets": [
          {
            "expr": "rate(resume_parse_success_total[1h]) / rate(resume_parse_total[1h])",
            "legendFormat": "解析成功率"
          }
        ],
        "gridPos": {"x": 6, "y": 8, "w": 6, "h": 4}
      },
      {
        "title": "PostgreSQL连接数",
        "type": "graph",
        "targets": [
          {
            "expr": "pg_stat_activity_count",
            "legendFormat": "活跃连接"
          }
        ],
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8}
      },
      {
        "title": "Redis内存使用",
        "type": "graph",
        "targets": [
          {
            "expr": "redis_memory_used_bytes",
            "legendFormat": "已用内存"
          }
        ],
        "gridPos": {"x": 0, "y": 12, "w": 12, "h": 8}
      }
    ]
  }
}
```

### 3.3 日志收集方案

#### 结构化日志配置

**Python 日志配置 (backend/utils/logger.py):**

```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # JSON格式化handler
        handler = logging.StreamHandler()
        handler.setFormatter(self.JsonFormatter())
        self.logger.addHandler(handler)
    
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_obj = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            
            # 添加额外字段
            if hasattr(record, 'task_id'):
                log_obj['task_id'] = record.task_id
            if hasattr(record, 'user_id'):
                log_obj['user_id'] = record.user_id
            if hasattr(record, 'error_details'):
                log_obj['error_details'] = record.error_details
            
            return json.dumps(log_obj)

# 使用示例
logger = StructuredLogger('recruitment_agent')
logger.logger.info("任务创建成功", extra={'task_id': 'task_001', 'user_id': 'user_001'})
```

**日志级别定义:**

| 级别 | 用途 | 示例场景 |
|-----|-----|---------|
| **DEBUG** | 开发调试信息 | Agent推理过程详细日志 |
| **INFO** | 关键业务事件 | 任务创建/完成、API调用 |
| **WARNING** | 潜在问题警告 | 缓存失效、性能下降 |
| **ERROR** | 错误但系统可用 | 工具调用失败、数据校验失败 |
| **CRITICAL** | 系统严重错误 | 数据库连接失败、内存溢出 |

#### 日志聚合工具 (ELK Stack)

**Elasticsearch + Logstash + Kibana 配置示例:**

```yaml
# Logstash 配置 (logstash.conf)
input {
  docker {
    container_name => "recruitment-backend"
    codec => json_lines
  }
}

filter {
  json {
    source => "message"
    target => "log_data"
  }
  
  # 添加时间戳
  date {
    match => ["log_data.timestamp", "ISO8601"]
    target => "@timestamp"
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "recruitment-agent-%{+YYYY.MM.dd}"
  }
}
```

### 3.4 告警规则配置

#### 告警通知渠道配置

**邮件告警配置 (AlertManager):**

```yaml
# alertmanager.yml
global:
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alertmanager@example.com'
  smtp_auth_username: 'alertmanager@example.com'
  smtp_auth_password: 'your_email_password'

route:
  receiver: 'team-email'
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: 'team-email'
    email_configs:
      - to: 'dev-team@example.com'
        send_resolved: true
```

**企业微信告警配置 (Webhook):**

```yaml
receivers:
  - name: 'wechat-webhook'
    webhook_configs:
      - url: 'http://wechat-webhook:8080/send'
        send_resolved: true
```

---

## 四、数据备份与恢复方案

### 4.1 PostgreSQL 备份策略

#### 全量备份脚本

```bash
#!/bin/bash
# PostgreSQL 全量备份脚本 (backup_postgres.sh)

# 配置参数
BACKUP_DIR="/data/backups/postgres"
DB_NAME="recruitment_agent"
DB_USER="recruitment_agent"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 执行全量备份 (pg_dump)
docker exec recruitment-postgres pg_dump -U $DB_USER -d $DB_NAME | gzip > $BACKUP_FILE

# 验证备份文件
if [ -f $BACKUP_FILE ]; then
    echo "备份成功: $BACKUP_FILE"
    echo "备份文件大小: $(du -h $BACKUP_FILE | cut -f1)"
else
    echo "备份失败!"
    exit 1
fi

# 删除30天前的旧备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

# 备份日志记录
echo "$(date): PostgreSQL全量备份完成 - $BACKUP_FILE" >> $BACKUP_DIR/backup.log
```

#### 增量备份 (WAL日志归档)

**PostgreSQL 配置 (postgresql.conf):**

```conf
# 启用 WAL 归档
wal_level = replica
archive_mode = on
archive_command = 'cp %p /data/archives/%f'

# WAL 保留配置
max_wal_senders = 3
wal_keep_size = 1GB
```

#### 自动备份调度 (Cron)

```bash
# 编辑 crontab
crontab -e

# 添加以下任务:
# 每日凌晨2点执行全量备份
0 2 * * * /scripts/backup_postgres.sh

# 每小时执行增量备份(WAL归档)
0 * * * * docker exec recruitment-postgres pg_switch_wal
```

### 4.2 Redis 持久化配置

#### RDB + AOF 混合持久化

**Redis 配置 (redis.conf):**

```conf
# RDB 持久化
save 900 1
save 300 10
save 60 10000
dbfilename dump.rdb
dir /data

# AOF 持久化
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec

# 混合持久化 (RDB+AOF)
aof-use-rdb-preamble yes

# AOF 重写配置
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

#### Redis 备份脚本

```bash
#!/bin/bash
# Redis 备份脚本 (backup_redis.sh)

BACKUP_DIR="/data/backups/redis"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 触发 RDB 快照
docker exec recruitment-redis redis-cli -a $REDIS_PASSWORD BGSAVE

# 等待快照完成
sleep 10

# 复制 RDB 文件
docker cp recruitment-redis:/data/dump.rdb $BACKUP_DIR/dump_${TIMESTAMP}.rdb

# 复制 AOF 文件
docker cp recruitment-redis:/data/appendonly.aof $BACKUP_DIR/appendonly_${TIMESTAMP}.aof

echo "Redis备份完成: $BACKUP_DIR"
```

### 4.3 MinIO 数据备份方案

#### MinIO 备份脚本 (使用 mc mirror)

```bash
#!/bin/bash
# MinIO 备份脚本 (backup_minio.sh)

BACKUP_DIR="/data/backups/minio"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 配置 MinIO 别名
mc alias set source http://localhost:9000 minioadmin minioadmin
mc alias set backup http://backup-server:9000 backup_user backup_password

# 同步存储桶到备份服务器
mc mirror source/resumes backup/resumes-backup
mc mirror source/jd-attachments backup/jd-attachments-backup
mc mirror source/agent-logs backup/agent-logs-backup

# 本地备份 (可选)
mkdir -p $BACKUP_DIR/$TIMESTAMP
mc cp --recursive source/resumes $BACKUP_DIR/$TIMESTAMP/resumes/
mc cp --recursive source/jd-attachments $BACKUP_DIR/$TIMESTAMP/jd-attachments/

echo "MinIO备份完成: $BACKUP_DIR/$TIMESTAMP"
```

### 4.4 灾难恢复流程

#### PostgreSQL 数据恢复

```bash
# 1. 停止 PostgreSQL 服务
docker-compose stop postgres

# 2. 删除旧数据
docker volume rm recruitment-agent-2.0_postgres_data

# 3. 创建新数据卷
docker volume create recruitment-agent-2.0_postgres_data

# 4. 启动 PostgreSQL 服务
docker-compose up -d postgres

# 5. 等待服务启动
sleep 30

# 6. 恢复全量备份
gunzip -c /data/backups/postgres/recruitment_agent_20260707.sql.gz | \
  docker exec -i recruitment-postgres psql -U recruitment_agent -d recruitment_agent

# 7. 恢复 WAL 归档 (如有增量备份)
# 需配置恢复参数 recovery.conf

# 8. 验证数据恢复
docker exec recruitment-postgres psql -U recruitment_agent -d recruitment_agent -c \
  "SELECT COUNT(*) FROM tasks; SELECT COUNT(*) FROM candidates; SELECT COUNT(*) FROM jds;"

# 9. 验证应用连接
curl http://localhost:8000/api/health
```

#### Redis 数据恢复

```bash
# 1. 停止 Redis 服务
docker-compose stop redis

# 2. 恢复 RDB 文件
docker cp /data/backups/redis/dump_20260707.rdb recruitment-redis:/data/dump.rdb

# 3. 恢复 AOF 文件
docker cp /data/backups/redis/appendonly_20260707.aof recruitment-redis:/data/appendonly.aof

# 4. 启动 Redis 服务
docker-compose up -d redis

# 5. 验证数据恢复
docker exec recruitment-redis redis-cli -a $REDIS_PASSWORD ping
docker exec recruitment-redis redis-cli -a $REDIS_PASSWORD info memory
```

#### MinIO 数据恢复

```bash
# 1. 恢复存储桶数据
mc mirror /data/backups/minio/20260707/resumes myminio/resumes
mc mirror /data/backups/minio/20260707/jd-attachments myminio/jd-attachments

# 2. 验证恢复结果
mc ls myminio/resumes
mc ls myminio/jd-attachments
```

#### 系统重建流程

```mermaid
graph TB
    A[灾难发生] --> B[停止所有服务]
    B --> C[创建新数据卷]
    C --> D[启动基础设施<br/>PostgreSQL/Redis/MinIO]
    D --> E[恢复PostgreSQL数据]
    E --> F[恢复Redis数据]
    F --> G[恢复MinIO数据]
    G --> H[验证数据完整性]
    H --> I[启动应用服务<br/>Backend/Frontend]
    I --> J[验证应用功能]
    J --> K[通知用户恢复完成]

    style A fill:#f44336
    style K fill:#4caf50
```

---

## 五、运维操作手册

### 5.1 日常运维检查清单

| 检查项 | 检查频率 | 检查命令 | 正常标准 |
|-------|---------|---------|---------|
| **服务健康状态** | 每小时 | `docker-compose ps` | 所有服务状态为 healthy |
| **API响应延迟** | 每小时 | `curl localhost:8000/api/health` | 响应时间 < 1秒 |
| **数据库连接数** | 每小时 | `docker exec postgres psql -c "SELECT COUNT(*) FROM pg_stat_activity;"` | 连接数 < 100 |
| **Redis内存使用** | 每小时 | `docker exec redis redis-cli info memory` | 内存使用 < 80% |
| **MinIO存储容量** | 每天 | `mc ls myminio --summarize` | 存储容量 < 70% |
| **日志错误统计** | 每天 | `grep "ERROR" /logs/backend.log \| wc -l` | 错误数 < 10 |
| **备份文件完整性** | 每天 | `ls -lh /data/backups/` | 备份文件存在且大小正常 |

### 5.2 常见问题排查手册

#### 问题1: API响应延迟过高

**排查步骤:**
```bash
# 1. 检查API响应延迟
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/health

# 2. 检查数据库查询性能
docker exec postgres psql -c "SELECT query, calls, total_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# 3. 检查Redis缓存命中率
docker exec redis redis-cli info stats \| grep hit_rate

# 4. 检查Agent推理时间
grep "REASONING_TIME" /logs/backend.log | tail -20

# 5. 检查系统资源使用
docker stats recruitment-backend
```

**优化措施:**
- 优化慢查询(添加索引)
- 增加Redis缓存容量
- 优化Agent推理算法(减少LLM调用次数)

#### 问题2: 简历解析失败率高

**排查步骤:**
```bash
# 1. 检查解析失败日志
grep "RESUME_PARSE_FAILED" /logs/backend.log | tail -50

# 2. 检查MinIO文件上传状态
mc ls myminio/resumes --incomplete

# 3. 检查解析队列积压
docker exec redis redis-cli llen resume_parse_queue

# 4. 检查文件格式分布
grep "FILE_TYPE" /logs/backend.log | grep -c "PDF"
grep "FILE_TYPE" /logs/backend.log | grep -c "DOCX"
```

**优化措施:**
- 增加OCR引擎(处理图片简历)
- 优化解析超时时间
- 增加人工补录入口

#### 问题3: LLM API调用失败

**排查步骤:**
```bash
# 1. 检查API调用日志
grep "OPENAI_API_ERROR" /logs/backend.log | tail -20

# 2. 检查API密钥有效性
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models

# 3. 检查API配额使用情况
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/usage

# 4. 检查网络连接
curl -I https://api.openai.com
```

**优化措施:**
- 更换API密钥或增加配额
- 切换到备用LLM模型(Azure OpenAI)
- 增加API调用重试机制

---

## 六、附录

### 6.1 环境变量完整清单

| 变量名 | 开发环境值 | 生产环境值 | 说明 |
|-------|-----------|-----------|-----|
| `DATABASE_URL` | `postgresql://...@localhost:5432` | `postgresql://...@postgres:5432` | 数据库连接字符串 |
| `REDIS_URL` | `redis://localhost:6379/0` | `redis://redis:6379/0?password=...` | Redis连接字符串 |
| `MINIO_ENDPOINT` | `localhost:9000` | `minio:9000` | MinIO服务地址 |
| `MINIO_ACCESS_KEY` | `minioadmin` | `自定义密钥` | MinIO访问密钥 |
| `MINIO_SECRET_KEY` | `minioadmin` | `自定义密钥` | MinIO安全密钥 |
| `OPENAI_API_KEY` | `sk-...` | `sk-...` | OpenAI API密钥 |
| `OPENAI_MODEL` | `gpt-4o` | `gpt-4o` | LLM模型名称 |
| `APP_ENV` | `development` | `production` | 应用环境标识 |
| `APP_DEBUG` | `true` | `false` | 调试模式开关 |
| `APP_PORT` | `8000` | `8000` | 应用端口 |

### 6.2 Docker 常用操作命令

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 重启单个服务
docker-compose restart backend

# 查看服务日志
docker-compose logs -f backend

# 进入容器内部
docker exec -it recruitment-backend bash

# 查看容器资源使用
docker stats recruitment-backend

# 清理未使用的镜像和容器
docker system prune -a
```

### 6.3 服务健康检查命令

```bash
# PostgreSQL健康检查
docker exec recruitment-postgres pg_isready -U recruitment_agent

# Redis健康检查
docker exec recruitment-redis redis-cli ping

# MinIO健康检查
curl -f http://localhost:9000/minio/health/live

# Backend API健康检查
curl http://localhost:8000/api/health

# Prometheus健康检查
curl http://localhost:9090/-/healthy

# Grafana健康检查
curl http://localhost:3000/api/health
```

---

**文档结束**

**已完成子任务清单:**
- ✅ SubTask 3.1: 编写开发环境搭建指南(前端/后端/数据库/Agent服务配置)
- ✅ SubTask 3.2: 编写生产环境部署指南(Docker Compose/环境变量/数据库初始化/服务启动)
- ✅ SubTask 3.3: 编写监控与运维指南(Prometheus/Grafana/日志收集/告警规则)
- ✅ SubTask 3.4: 编写数据备份与恢复方案(PostgreSQL/Redis/MinIO备份/灾难恢复流程)

**文件路径:** `docs/deployment-guide.md`