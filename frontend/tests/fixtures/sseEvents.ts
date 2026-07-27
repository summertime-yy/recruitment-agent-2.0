// PR-19 S5-13 · SSE 事件工厂(测试 fixture)。
// 8 类事件工厂 + system:cancelled 特化,供 EventCards / ChatCenter / useTaskStream 测试复用。
import type {
  SSEEvent,
  ThinkingData,
  Plan,
  ToolCallData,
  ProgressData,
  ResultData,
  ErrorData,
  WarningData,
  SystemData,
  ResultArtifact,
} from '@/types/agent';

export function makeThinkingEvent(id: string, content = 'thinking-content'): SSEEvent<ThinkingData> {
  return { id, type: 'thinking', task_id: 't', timestamp: new Date().toISOString(), data: { content } };
}

export function makePlanEvent(id: string, plan?: Partial<Plan>): SSEEvent<Plan> {
  const full: Plan = {
    task_id: 't',
    steps: plan?.steps ?? [
      { step_id: 's1', description: '步骤一', tool_name: 'search_resumes', params: {}, expected_output: '' },
      { step_id: 's2', description: '步骤二', tool_name: 'score', params: {}, expected_output: '' },
    ],
    ...plan,
  };
  return { id, type: 'plan', task_id: 't', timestamp: new Date().toISOString(), data: full };
}

export function makeToolCallEvent(
  id: string,
  tool_name = 'search_resumes',
  params: Record<string, unknown> = { keyword: 'java' },
  step_id = 's1',
): SSEEvent<ToolCallData> {
  return { id, type: 'tool_call', task_id: 't', step_id, timestamp: new Date().toISOString(), data: { step_id, tool_name, params } };
}

export function makeProgressEvent(
  id: string,
  progress = 0.5,
  message = 'progress-content',
  step_id = 's1',
): SSEEvent<ProgressData> {
  return { id, type: 'progress', task_id: 't', step_id, timestamp: new Date().toISOString(), data: { step_id, progress, message } };
}

export function makeResultEvent(id: string, content = 'result-content', artifacts?: ResultArtifact[]): SSEEvent<ResultData> {
  return { id, type: 'result', task_id: 't', timestamp: new Date().toISOString(), data: { content, artifacts } };
}

export function makeErrorEvent(id: string, code = 'E001', message = 'error-content'): SSEEvent<ErrorData> {
  return { id, type: 'error', task_id: 't', timestamp: new Date().toISOString(), data: { code, message } };
}

export function makeWarningEvent(id: string, message = 'warning-content', suggestion?: string): SSEEvent<WarningData> {
  return { id, type: 'warning', task_id: 't', timestamp: new Date().toISOString(), data: { message, suggestion } };
}

export function makeSystemEvent(id: string, message = 'system-content'): SSEEvent<SystemData> {
  return { id, type: 'system', task_id: 't', timestamp: new Date().toISOString(), data: { message } };
}

export function makeSystemCancelledEvent(id: string): SSEEvent<SystemData> {
  return makeSystemEvent(id, 'cancelled');
}
