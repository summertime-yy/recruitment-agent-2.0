import request from '@/utils/request';
import type {
  AgentChatRequest,
  AgentChatResponse,
  ExecutePlanRequest,
  ExecutePlanResponse,
  SkipToScoreRequest,
  SkipToScoreResponse,
  CancelTaskResponse,
  TaskStatusResponse,
} from '@/types/agent';

// PR-18 S5-12 · Agent REST 服务层。
// 仿 candidateApi 对象模式(见 services/candidate.ts)。
// Q9.1:429 不加中间层 —— request.ts 拦截器已 reject 原始 error,
// 调用方自行 try/catch 判 err.response?.status === 429。
export const agentApi = {
  chat(data: AgentChatRequest): Promise<AgentChatResponse> {
    return request.post('/agent/chat', data);
  },

  executePlan(data: ExecutePlanRequest): Promise<ExecutePlanResponse> {
    return request.post('/agent/execute-plan', data);
  },

  skipToScore(data: SkipToScoreRequest): Promise<SkipToScoreResponse> {
    return request.post('/agent/skip-to-score', data);
  },

  cancelTask(taskId: string): Promise<CancelTaskResponse> {
    return request.post(`/agent/tasks/${taskId}/cancel`);
  },

  getTask(taskId: string): Promise<TaskStatusResponse> {
    return request.get(`/agent/tasks/${taskId}`);
  },
};
