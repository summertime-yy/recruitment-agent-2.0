// PR-18 S5-12 · 前端 agent 类型契约。
// 权威事实源:api-contract §3.1–§3.5 / §4.1–§4.5;backend/app/schemas/agent.py;
// HANDOFF §9.4 陷阱 4/5/6/8/9。后端 PR-14/17 已固化 SSE 事件流与 REST 端点。
// 本文件严格对齐后端 schema,不引入 TS enum(用 union type,与 JDStatus/CandidateStatus 一致)。

// ============ SSE 信封 · api-contract §3.2 ============

export type SSEEventType =
  | 'thinking'
  | 'plan'
  | 'tool_call'
  | 'progress'
  | 'result'
  | 'error'
  | 'warning'
  | 'system';

export interface SSEEvent<T = unknown> {
  id: string; // 任务内单调递增序号
  type: SSEEventType;
  task_id: string;
  step_id?: string;
  timestamp: string;
  data: T;
}

// ============ 事件 data 结构(部分) · api-contract §3.3 ============

export interface ThinkingData {
  content: string;
}

export interface ToolCallData {
  step_id: string;
  tool_name: string;
  params: Record<string, unknown>;
}

export interface ProgressData {
  step_id: string;
  progress: number;
  message: string;
}

export interface ResultData {
  content: string;
  artifacts?: ResultArtifact[];
}

// recoverable 字段类型保留,但语义见 §五 Q12/A2:后端 SSEEvent.data 为 Any,
// 该字段未固化在 pydantic schema;前端重连判定不依赖它(error/result 即终态)。
export interface ErrorData {
  code: string;
  message: string;
  recoverable?: boolean;
}

export interface WarningData {
  message: string;
  suggestion?: string;
}

export interface SystemData {
  message: string;
}

// PlanData = Plan(§3.4)

// ============ Result Artifact · 追债项 3 前端 union 侧 ============

export type ArtifactType =
  | 'jd'
  | 'resume'
  | 'match_score'
  | 'candidate_merge'
  | 'candidate_profile'
  | 'generic';

export interface ResultArtifact {
  step_id: string;
  tool_name: string;
  type: ArtifactType;
  ref_id?: string;
  data?: unknown; // 各 type 具体形状留 PR-19 卡片渲染时窄化
}

// ============ Plan · api-contract §3.4 ============

export interface PlanStep {
  step_id: string;
  description: string;
  tool_name: string;
  params: Record<string, unknown>;
  expected_output: string;
  optional?: boolean;
  dependencies?: string[];
  estimated_duration_seconds?: number;
}

export interface Plan {
  task_id: string;
  steps: PlanStep[];
  reasoning?: string;
}

// ============ TaskStatus · api-contract §4.4 ============

export type TaskStatus =
  | 'PENDING'
  | 'PLANNING'
  | 'WAITING_CONFIRMATION'
  | 'EXECUTING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

// ============ REST 请求/响应 · api-contract §4.1..§4.5 ============

export interface AgentChatRequest {
  message: string;
  context?: {
    jd_id?: string;
    candidate_ids?: string[];
  };
}

/**
 * B1 采纳(b):保留 3 值子集 + 注释。
 * api-contract §4.1 声明 status ∈ {PLANNING, WAITING_CONFIRMATION, EXECUTING};
 * 实测 PR-14 后 backend/app/api/v1/agent.py:87 端点 hardcode 返 "PLANNING",
 * 但类型层坚持契约声明的 3 值子集,不假设实测唯一值。
 * initial_plan 字段类型保留 optional,但 PR-14 起后端不填,前端不消费(§9.4 陷阱 4)。
 */
export interface AgentChatResponse {
  task_id: string;
  status: 'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING';
  initial_plan?: Plan;
}

export interface ExecutePlanRequest {
  task_id: string;
  accepted_steps?: string[];
  modifications?: {
    step_id: string;
    modified_params?: Record<string, unknown>;
  }[];
}

export interface ExecutePlanResponse {
  task_id: string;
  status: 'EXECUTING';
}

export interface SkipToScoreRequest {
  jd_id: string;
  candidate_ids: string[];
}

export interface SkipToScoreResponse {
  task_id: string;
  status: 'EXECUTING';
}

export interface CancelTaskResponse {
  task_id: string;
  status: 'CANCELLED';
}

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  current_step?: string;
  plan?: Plan;
  result?: ResultData;
  error?: { code: string; message: string };
  created_at: string;
  updated_at: string;
}
