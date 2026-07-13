# 数据模型规范（Data Model）

> **本文档是数据库Schema的唯一事实来源（Single Source of Truth）**。
> 所有数据库变更必须先更新本文档，再通过Alembic迁移实现。code-wiki.md、architecture-modules.md中涉及DDL的内容如与本文冲突，以本文为准。

---

## 1. 设计约定

| 约定项 | 规范 |
|-------|------|
| 主键策略 | 业务表使用 **VARCHAR(50)** 存储字符串ID（格式：`{prefix}_{uuid4_hex_12chars}`，如 `jd_0144c8c45fbf`）；日志/关联表使用 **INTEGER AUTOINCREMENT** |
| 表命名 | 小写+下划线，**复数形式**（jds, skills, candidates），与SQLAlchemy `__tablename__` 一致 |
| 时间戳 | 所有业务表包含 `created_at`、`updated_at`（TIMESTAMP，服务端UTC时间），通过 `TimestampMixin` 统一注入 |
| JSON字段 | PostgreSQL原生JSON类型，存储数组/嵌套对象；应用层负责schema校验 |
| 外键 | 使用字符串ID引用时，FK指向VARCHAR列；删除策略默认RESTRICT |
| 软删除 | 通过 `status` 字段实现（如 DRAFT/PUBLISHED/ARCHIVED），不使用物理删除 |

---

## 2. 已实现表（Stage 0 + Stage 1）

### 2.1 Alembic版本管理
- **表名**: `alembic_version`
- **用途**: 数据库迁移版本跟踪（Alembic自动管理）

### 2.2 JD模板表 `jd_templates`

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| template_id | VARCHAR(50) | PK | 模板ID，格式 `tpl_xxxx` |
| template_name | VARCHAR(100) | NOT NULL | 模板名称 |
| template_type | VARCHAR(30) | | 模板类型 |
| template_content | JSON | | 模板内容（结构化） |
| usage_count | INTEGER | DEFAULT 0 | 使用次数 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

### 2.3 JD职位表 `jds`

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| jd_id | VARCHAR(50) | PK | JD ID，格式 `jd_xxxx` |
| title | VARCHAR(100) | NOT NULL | 职位名称 |
| department | VARCHAR(50) | NULL | 所属部门 |
| level | VARCHAR(20) | NULL | 职级 |
| location | VARCHAR(100) | NULL | 工作地点 |
| job_type | VARCHAR(30) | NULL | 工作类型（全职/实习/兼职） |
| salary_range | VARCHAR(50) | NULL | 薪资范围 |
| summary | TEXT | NULL | 职位摘要 |
| responsibilities | JSON | NULL | 岗位职责（字符串数组） |
| requirements | JSON | NULL | 任职要求（字符串数组） |
| required_skills | JSON | NULL | 必备技能（字符串数组） |
| preferred_skills | JSON | NULL | 加分技能（字符串数组） |
| compliance_check | JSON | NULL | 合规检查结果 `{passed: bool, issues: []}` |
| template_id | VARCHAR(50) | FK → jd_templates.template_id, NULL | 来源模板ID |
| created_by | VARCHAR(50) | NULL | 创建人ID |
| status | VARCHAR(20) | DEFAULT 'DRAFT' | 状态：DRAFT/PUBLISHED/ARCHIVED |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

### 2.4 Skill元数据表 `skills`

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| skill_id | VARCHAR(100) | PK | Skill唯一标识（如 `jd-generation`） |
| skill_name | VARCHAR(200) | NOT NULL | Skill名称 |
| description | TEXT | NULL | 描述 |
| current_version | VARCHAR(20) | NOT NULL | 当前激活版本号 |
| status | VARCHAR(20) | DEFAULT 'ACTIVE' | 状态：DRAFT/ACTIVE/DEPRECATED/ARCHIVED |
| author | VARCHAR(100) | NULL | 作者 |
| tags | JSON | NULL | 标签列表 |
| trigger_conditions | JSON | NULL | 触发条件配置 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

### 2.5 Skill版本表 `skill_versions`

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| version_id | INTEGER | PK, AUTOINCREMENT | 版本记录ID |
| skill_id | VARCHAR(100) | FK → skills.skill_id, NOT NULL | 所属Skill |
| version | VARCHAR(20) | NOT NULL | 版本号（语义化版本，如1.0.0） |
| content_path | VARCHAR(500) | NOT NULL | Skill文件目录路径 |
| input_schema | JSON | NULL | 输入JSON Schema |
| output_schema | JSON | NULL | 输出JSON Schema |
| tool_chain | JSON | NULL | 工具链配置 |
| error_handling | JSON | NULL | 错误处理策略 |
| changelog | TEXT | NULL | 变更日志 |
| status | VARCHAR(20) | DEFAULT 'DRAFT' | 状态：DRAFT/ACTIVE/DEPRECATED |
| traffic_weight | FLOAT | DEFAULT 0.0 | 流量权重（灰度发布用） |
| success_rate | FLOAT | NULL | 成功率（运行时统计） |
| avg_latency_ms | INTEGER | NULL | 平均延迟ms（运行时统计） |
| quality_score | FLOAT | NULL | 质量评分（运行时统计） |
| created_by | VARCHAR(100) | NULL | 创建人 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| published_at | TIMESTAMP | NULL | 发布时间 |

**唯一约束**: `(skill_id, version)`

### 2.6 Skill执行日志表 `skill_execution_logs`

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| execution_id | INTEGER | PK, AUTOINCREMENT | 执行记录ID |
| skill_id | VARCHAR(100) | FK → skills.skill_id, NOT NULL | 执行的Skill |
| version | VARCHAR(20) | NOT NULL | Skill版本号 |
| task_id | VARCHAR(50) | NULL | 关联任务ID（如jd_id） |
| user_id | VARCHAR(50) | NULL | 触发用户ID |
| input_params | JSON | NULL | 输入参数快照 |
| output_result | JSON | NULL | 输出结果快照 |
| execution_status | VARCHAR(20) | NOT NULL | 状态：SUCCESS/FAILED/FALLBACK/HUMAN_HANDOFF |
| execution_time_ms | INTEGER | NULL | 执行耗时ms |
| validation_score | FLOAT | NULL | 输出验证分数(0-1) |
| error_message | TEXT | NULL | 错误信息 |
| executed_at | TIMESTAMP | NOT NULL | 执行时间 |

---

## 3. 待实现表（后续Stage）

> 以下为规划中的表，**PK策略统一为VARCHAR(50)字符串ID**，命名遵循复数规范，此处先占位定义，到对应Stage时通过Alembic迁移落地。

### 2.7 简历表 `resumes`（Stage 2）
| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| resume_id | VARCHAR(50) | PK | 简历ID，格式 `res_xxxx` |
| candidate_name | VARCHAR(100) | NULL | 候选人姓名（解析后填充） |
| file_name | VARCHAR(255) | NOT NULL | 原始文件名 |
| file_path | VARCHAR(500) | NOT NULL | MinIO对象存储路径 |
| file_size | INTEGER | NULL | 文件大小（字节） |
| file_type | VARCHAR(20) | NOT NULL | 文件类型：pdf/docx |
| file_hash | VARCHAR(64) | NULL | 文件MD5哈希（去重用） |
| phone | VARCHAR(30) | NULL | 手机号（解析后填充） |
| email | VARCHAR(100) | NULL | 邮箱（解析后填充） |
| parsed_content | JSON | NULL | 解析后结构化内容：<br>- education: 教育经历数组<br>- work_experience: 工作经历数组<br>- project_experience: 项目经历数组<br>- skills: 技能标签数组<br>- summary: 个人简介 |
| raw_text | TEXT | NULL | 提取的原始文本 |
| parse_status | VARCHAR(20) | DEFAULT 'PENDING' | 解析状态：PENDING/PARSING/PARSED/FAILED |
| parse_error | TEXT | NULL | 解析失败错误信息 |
| parsing_skill_id | VARCHAR(100) | NULL | FK→skills.skill_id |
| parsing_skill_version | VARCHAR(20) | NULL | 使用的解析Skill版本 |
| parse_time_ms | INTEGER | NULL | 解析耗时ms |
| created_by | VARCHAR(50) | NULL | 上传人ID |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

### 3.2 候选人表 `candidates`（Stage 3）
| 字段 | 类型 | 说明 |
|-----|------|------|
| candidate_id | VARCHAR(50) PK | 候选人ID |
| name | VARCHAR(100) | 姓名 |
| phone | VARCHAR(30) | 手机号 |
| email | VARCHAR(100) | 邮箱 |
| resume_id | VARCHAR(50) FK→resumes | 关联简历 |
| profile | JSON | 结构化画像（技能、经验等） |
| source | VARCHAR(50) | 来源渠道 |
| status | VARCHAR(20) | 候选人状态 |
| created_at / updated_at | TIMESTAMP | 时间戳 |

### 3.3 人岗匹配评分表 `match_scores`（Stage 4）
| 字段 | 类型 | 说明 |
|-----|------|------|
| score_id | VARCHAR(50) PK | 评分记录ID |
| jd_id | VARCHAR(50) FK→jds | JD ID |
| candidate_id | VARCHAR(50) FK→candidates | 候选人ID |
| overall_score | FLOAT | 综合匹配度(0-100) |
| dimension_scores | JSON | 各维度分数（技能/经验/学历等） |
| matching_skill_version | VARCHAR(20) | 匹配Skill版本 |
| status | VARCHAR(20) | 状态 |
| created_at / updated_at | TIMESTAMP | 时间戳 |

> **注意依赖顺序**：`match_scores` 依赖 `candidates`（Stage 3）和 `jds`（Stage 1），因此Stage 4（评分匹配）**必须**在Stage 3（候选人）之后。

### 3.4 面试评估表 `interview_evaluations`（Stage 5+）
（待设计）

### 3.5 沟通记录表 `communications`（Stage 5+）
（待设计）

### 3.6 向量存储方案
- **方案选择**：使用pgvector扩展，**向量列直接挂在业务表上**（resumes和jds表各加`embedding vector(1536)`列），不建独立向量表
- 需要先安装pgvector扩展（已在Docker镜像中包含）
- 通过迁移添加vector列和IVFFlat/HNSW索引

---

## 4. 迁移规范

1. 所有表结构变更**必须**通过Alembic迁移：
   ```bash
   cd backend
   uv run alembic revision --autogenerate -m "描述变更内容"
   uv run alembic upgrade head
   ```
2. 迁移文件需人工review后再提交，尤其注意：
   - 自动生成的迁移是否包含意外的drop操作
   - JSON列、外键约束是否正确
   - 向量列需要显式添加`vector`类型
3. 本文档必须在迁移合并前同步更新
