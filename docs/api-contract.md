# API & SSE 接口契约（API Contract）

> **本文档是前后端API接口的唯一事实来源（Single Source of Truth）**。
> 所有HTTP接口、SSE事件类型、请求/响应结构以本文档为准。

**版本:** v1.1
**更新日期:** 2026-07-09
**配套文档:** [data-model.md](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/docs/data-model.md)、[development-roadmap.md](file:///e:/AI-WORK/Project-Work/recruitment-agent-2.0/docs/development-roadmap.md)

---

## 1. 通用约定

### 1.1 基础信息

| 项 | 值 |
|---|---|
| API前缀 | `/api/v1` |
| 认证方式 | 暂不认证（开发阶段），后续加入JWT |
| 内容类型 | `application/json`（除文件上传外） |
| 字符编码 | UTF-8 |
| 时间格式 | ISO 8601 UTC（如 `2026-07-09T10:30:00Z`） |

### 1.2 REST端点响应格式（Stage 1-4 当前实现）

> **约定：Stage 1-4的REST API直接返回数据对象，不使用统一信封包装。**
> 错误通过HTTP状态码 + FastAPI默认错误格式（`{"detail": "错误信息"}`）返回。
> Stage 5引入Orchestrator/SSE时，再统一增加request_id等信封字段。

**错误响应格式（HTTP 4xx/5xx）：**
```json
{
  "detail": "错误描述信息"
}
```

### 1.3 分页约定

列表接口统一支持分页参数：

```typescript
interface PaginationParams {
  page?: number;      // 默认1
  page_size?: number; // 默认10，最大100
  keyword?: string;   // 关键词搜索
  status?: string;    // 状态筛选
}

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
```

---

## 2. JD管理接口（已实现）

所有JD接口前缀：`/api/v1/jds`

### 2.1 生成JD

```
POST /api/v1/jds/generate
```

**请求体：**
```typescript
interface JDGenerateRequest {
  title: string;              // 职位名称（必填，2-100字符）
  department?: string;        // 部门
  level?: string;             // 职级
  location?: string;          // 工作地点
  job_type?: string;          // 工作类型（全职/实习/兼职）
  salary_range?: string;      // 薪资范围
  description: string;        // 职位需求描述（必填，至少10字符）
  requirements?: string[];    // 硬性要求列表（可选）
  preferred_skills?: string[]; // 加分项列表（可选）
}
```

**响应：**
```typescript
interface JDGenerateResponse {
  jd: JDResponse;
  skill_execution_id: number;
  execution_time_ms: number;
  validation_score: number;   // 0-1
}
```

### 2.2 JD列表

```
GET /api/v1/jds
```

**查询参数：** `page`、`page_size`、`keyword`、`status`

**响应：** `PaginatedResponse<JDResponse>`

### 2.3 JD详情

```
GET /api/v1/jds/{jd_id}
```

**响应：**
```typescript
interface JDResponse {
  jd_id: string;
  title: string;
  department?: string;
  level?: string;
  location?: string;
  job_type?: string;
  salary_range?: string;
  summary?: string;
  responsibilities?: string[];
  requirements?: string[];
  required_skills?: string[];
  preferred_skills?: string[];
  compliance_check?: {
    passed: boolean;
    issues: string[];
  };
  template_id?: string;
  created_by?: string;
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
  created_at: string;
  updated_at: string;
}
```

### 2.4 更新JD

```
PUT /api/v1/jds/{jd_id}
```

**请求体：** `Partial<Omit<JDResponse, 'jd_id' | 'created_at' | 'updated_at'>>`

**响应：** `JDResponse`

### 2.5 删除JD

```
DELETE /api/v1/jds/{jd_id}
```

**响应：**
```json
{
  "message": "JD deleted successfully"
}
```

### 2.6 健康检查

```
GET /health
GET /api/v1/health
```

**响应：**
```json
{
  "status": "ok",
  "app": "Recruitment Agent 2.0"
}
```

---

## 3. SSE事件契约（Stage 5实现，此处固化类型）

### 3.1 SSE连接端点

```
GET /api/v1/agent/tasks/{task_id}/stream
```

**响应头：**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

### 3.2 统一SSE事件信封

**所有SSE事件严格遵循此结构，禁止前后端自定义字段：**

```typescript
interface SSEEvent<T = any> {
  id: string;               // 任务内单调递增序号（如 "1","2"...），供 Last-Event-ID 重放
  type: SSEEventType;
  task_id: string;
  step_id?: string;
  timestamp: string;
  data: T;
}
```

### 3.3 统一事件类型表

| 事件类型 | 触发时机 | data结构 | 前端卡片组件 |
|---------|---------|---------|-------------|
| `thinking` | Reason/Reflect阶段推理中 | `{ content: string }` | ThinkingCard |
| `plan` | Plan阶段生成计划后 | `Plan`（见3.4） | PlanCard（带确认按钮） |
| `tool_call` | 即将调用Skill/Tool | `{ step_id: string; tool_name: string; params: any }` | ToolCallCard |
| `progress` | 步骤执行进度更新 | `{ step_id: string; progress: number; message: string }` | ProgressCard |
| `result` | 整个任务完成 | `{ content: string; artifacts?: any[] }` | ResultCard |
| `error` | 发生错误 | `{ code: string; message: string; recoverable: boolean }` | ErrorCard |
| `warning` | 警告（不中断流程） | `{ message: string; suggestion?: string }` | WarningCard |
| `system` | 系统消息（连接、心跳等） | `{ message: string }` | 系统提示 |

> **重要约定：**
> - ❌ 禁止使用 `reason`、`reflect`、`reflect_act` 等旧类型
> - ✅ 后端统一发射 `thinking/plan/tool_call/progress/result/error/warning/system`

### 3.4 Plan结构（前后端统一）

```typescript
interface PlanStep {
  step_id: string;           // string类型（如 "step_1"）
  description: string;
  tool_name: string;
  params: Record<string, any>;
  expected_output: string;
  dependencies?: string[];
  optional?: boolean;            // ← PR-9 写回（REVIEW D8）：true 表示可选步，失败仅 warning 不中止
  estimated_duration_seconds?: number;
}

interface Plan {
  task_id: string;
  steps: PlanStep[];
  reasoning?: string;
}
```

### 3.5 SSE 连接、重放与心跳（Stage 5 固化）

> 本小节为 PR-9 评审后写回的补齐条目，解决 §3.2 信封缺 `id`、`retry`、重放与心跳语义的问题。

**事件序号与重放**：
- 每条 SSE 事件必须带 `id`（§3.2），值为**该 task 内单调递增整数序号**。
- 客户端断线后以 HTTP 请求头 `Last-Event-ID: <last_id>` 重新连接 `/stream` 端点。
- 端点收到 `Last-Event-ID` 后，先从事件缓冲重放所有 `id > last_id` 的事件，再切回实时推送；无该头则全量重放缓冲（缓冲上限见下）。

**重连间隔**：
- SSE 流首行下发 `retry: 3000`（毫秒），浏览器据此决定自动重连间隔。

**心跳**：
- 连接空闲时每 **15s** 下发一条 `system` 类型心跳事件：`data: {"message":"heartbeat"}`，保持连接存活；`system` 事件兼作系统提示（连接成功/重连/心跳）。

**事件缓冲**：
- 服务端为每个 task 维护最近 **200** 条事件的环形缓冲（超出裁剪最旧）。
- 缓冲仅在任务终态（COMPLETED/FAILED）后保留 **3600s** 即过期；进行中任务不过期。
- 缓冲实现位置由后端决定（PR-9 选用 Redis，见 `docs/planning/stage5/executor/PLAN-STAGE5.md §2 Q6`）。

**早期事件滚动提示**：
- 若任务事件数超过 200，前端在重连补齐时若发现存在更早事件无法重放，应提示「早期事件已滚动，部分历史可能缺失」。

---

## 4. Agent交互接口（Stage 5实现）

### 4.1 发起对话/创建任务

```
POST /api/v1/agent/chat
```

**请求体：**
```typescript
interface AgentChatRequest {
  message: string;
  context?: {
    jd_id?: string;
    candidate_ids?: string[];
  };
}
```

**响应：**
```typescript
interface AgentChatResponse {
  task_id: string;
  status: 'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING';
  initial_plan?: Plan;
}
```

### 4.2 确认执行计划

```
POST /api/v1/agent/execute-plan
```

**请求体：**
```typescript
interface ExecutePlanRequest {
  task_id: string;
  accepted_steps?: string[];
  modifications?: {
    step_id: string;
    modified_params?: Record<string, any>;
  }[];
}
```

**响应：** `{ task_id: string; status: 'EXECUTING' }`

### 4.3 跳过计划直接评分（快捷操作）

```
POST /api/v1/agent/skip-to-score
```

**请求体：**
```typescript
interface SkipToScoreRequest {
  jd_id: string;
  candidate_ids: string[];
}
```

**响应：** `{ task_id: string; status: 'EXECUTING' }`

### 4.4 查询任务状态

```
GET /api/v1/agent/tasks/{task_id}
```

**响应：**
```typescript
interface TaskStatus {
  task_id: string;
  status: 'PENDING' | 'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  current_step?: string;
  plan?: Plan;
  result?: any;
  error?: { code: string; message: string };
  created_at: string;
  updated_at: string;
}
```

> **`CANCELLED` 语义（PR-9 写回，REVIEW D2）**：用户在 `WAITING_CONFIRMATION`（Plan 确认页）或 `PLANNING` 阶段显式取消任务后进入的终态。合法转移仅 `PLANNING → CANCELLED`、`WAITING_CONFIRMATION → CANCELLED`；`EXECUTING` 及各终态不可转 `CANCELLED`。

### 4.5 取消任务（Stage 5 引入，REVIEW D2）

```
POST /api/v1/agent/tasks/{task_id}/cancel
```

**语义**：用户在 `PLANNING` 或 `WAITING_CONFIRMATION` 阶段显式取消任务。

**请求体**：无（或 `{}`）

**响应（200）**：`{ task_id: string; status: 'CANCELLED' }`

**错误码**：
- `404`：`task_id` 不存在
- `409`：任务当前状态非 `PLANNING/WAITING_CONFIRMATION`（EXECUTING / 各终态不可取消）

**后端动作**：收到后将该任务置为 `CANCELLED` 终态、关闭对应 SSE 流，并写 `executions.status = 'CANCELLED'`。

---

## 5. R-P-R-A-R阶段I/O Schema（Stage 5实现）

### 5.1 Reason阶段
- 输入：`{ user_message: string; context: { conversation_history: Message[]; entities?: any } }`
- 输出：`{ task_type: string; intent: string; required_entities: string[]; missing_entities: string[]; reasoning: string }`

### 5.2 Reflect阶段
- 输入：ReasonOutput
- 输出：`{ is_feasible: boolean; needs_clarification: boolean; clarification_questions?: string[]; risks: string[] }`

### 5.3 Plan阶段
- 输出：Plan（见3.4）

### 5.4 Reflect-Plan阶段
- 输入：Plan
- 输出：`{ is_plan_sound: boolean; issues: string[]; suggestions: string[]; adjusted_plan?: Plan }`

### 5.5 Act阶段
- 逐步执行，通过SSE推送tool_call/progress事件

### 5.6 Reflect-Act阶段
- 输入：执行结果
- 输出：`{ is_result_valid: boolean; quality_score: number; issues: string[]; final_result: any }`

---

## 6. 待实现API占位（后续Stage）

| Stage | 模块 | 接口前缀 | 核心接口 |
|-------|------|---------|---------|
| Stage 2 | 简历解析 | `/api/v1/resumes` | 上传、解析、查询、列表 |
| Stage 3 | 候选人 | `/api/v1/candidates` | CRUD、合并、画像、列表 |
| Stage 4 | 评分匹配 | `/api/v1/match-scores` | 触发匹配、查询结果、排行（详见 §8） |
| Stage 5 | Agent对话 | `/api/v1/agent` | chat、stream、execute-plan、skip-to-score |
| Stage 6 | 推送反馈 | `/api/v1/communications` | 发送、记录、反馈 |
| Stage 7 | 看板设置 | `/api/v1/analytics`、`/api/v1/skills`、`/api/v1/settings` | 统计、Skill管理、系统配置 |

---

## 7. 接口变更流程

1. **新增/修改接口**：必须先更新本文档
2. **后端实现**：严格按照本文档的Schema实现Pydantic模型
3. **前端对接**：严格按照本文档的TypeScript类型定义对接
4. **版本演进**：重大变更升级API版本号（v2），不破坏现有接口

---

## 8. Stage 4 人岗匹配（评分匹配）接口（S4 实现）

> 配套：任务拆解见 `docs/planning/TASKS.md`；数据模型见 `docs/data-model.md §3.3`。
> 所有端点前缀 `/api/v1`。响应直接返回数据对象（遵循 §1.2 约定，无统一信封）。

### 8.1 单点触发匹配

```
POST /api/v1/match-scores
```

**请求体：**
```typescript
interface MatchScoreRequest {
  jd_id: string;       // 必填，≤50字符
  resume_id: string;   // 必填，≤50字符
  force?: boolean;     // 默认 false；true 时忽略缓存重新计算
}
```

**响应（200）：** `MatchScoreResponse`（字段见 §8.7）
**错误码：**
- `404`：jd_id 或 resume_id 不存在
- `409`：resume 的 `parse_status` 非 `PARSED`（未解析完成，不允许评分）
- `400`：参数非法（如 jd_id 超长）

### 8.2 批量匹配（JD 视角）

```
POST /api/v1/match-scores/batch
```

**请求体：**
```typescript
interface BatchMatchRequest {
  jd_id: string;
  resume_ids?: string[];   // 缺省时取该JD下最近 limit 条已解析(PARSED)且未忽略去重的简历
  limit?: number;          // 1-200，缺省由后端决定
  force?: boolean;
}
```

**响应（202）：** `BatchTaskResponse { task_id, jd_id, total_submitted, submitted_at }`
> 批量任务后端异步执行（并发 ≤ 4），通过 `task_id` 轮询状态；Stage 4 不启用 SSE（Stage 5 引入）。

### 8.3 查询批量任务状态

```
GET /api/v1/match-scores/batch/{task_id}
```

**响应（200）：** `BatchTaskStatusResponse { task_id, jd_id, total, completed, failed, status, started_at, finished_at }`
`status` ∈ `PENDING | RUNNING | COMPLETED | FAILED`
**错误码：** `404` task_id 不存在

### 8.4 查询单条评分详情

```
GET /api/v1/match-scores/{score_id}
```

**响应（200）：** `MatchScoreResponse`
**错误码：** `404` score_id 不存在

### 8.5 JD 维度排名

```
GET /api/v1/jds/{jd_id}/ranking?limit=&offset=
```

**查询参数：** `limit`（默认 20，最大 200）、`offset`（默认 0）
**响应（200）：** `MatchRankingResponse { jd_id, total, items: MatchRankingItem[] }`
items 按 `overall_score` 降序
**错误码：** `404` jd_id 不存在

### 8.6 简历维度匹配列表

```
GET /api/v1/resumes/{resume_id}/matches?limit=
```

**响应（200）：** `MatchRankingItem[]`，按 `overall_score` 降序
**错误码：** `404` resume_id 不存在

### 8.7 数据结构

```typescript
interface DimensionScore {
  score: number;          // 0-100
  rationale: string;
  matched?: string[];     // 技能维度
  missing?: string[];     // 技能维度
  required?: string;      // 经验/学历维度
  actual?: string;
  years_required?: string;// 经验维度
  years_actual?: string;
}
interface DimensionScoresPayload {
  skill_match: DimensionScore;
  experience_match: DimensionScore;
  education_match: DimensionScore;
  overall_reasoning: string;
}
interface MatchScoreResponse {
  score_id: string;
  jd_id: string;
  resume_id: string;
  overall_score: number;          // 0-100，Service层按 0.5*skill+0.3*exp+0.2*edu 重算
  dimension_scores: DimensionScoresPayload;
  matching_skill_id: string | null;
  matching_skill_version: string | null;
  skill_execution_id: number | null;
  resume_updated_at_snapshot: string | null;
  jd_updated_at_snapshot: string | null;
  status: 'COMPLETED' | 'FAILED' | 'STALE';
  error_message: string | null;
  is_stale: boolean;              // Service层比对 snapshot 与当前 updated_at
  created_at: string;
  updated_at: string;
}
interface MatchRankingItem {
  score_id: string;
  resume_id: string;
  candidate_name: string | null;
  overall_score: number;
  dimension_scores: DimensionScoresPayload;
  is_stale: boolean;
  created_at: string;
}
interface BatchTaskResponse {
  task_id: string;
  jd_id: string;
  total_submitted: number;
  submitted_at: string;      // ISO 8601
}
interface BatchTaskStatusResponse {
  task_id: string;
  jd_id: string;
  total: number;
  completed: number;
  failed: number;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  started_at: string;
  finished_at: string | null;
}
```
