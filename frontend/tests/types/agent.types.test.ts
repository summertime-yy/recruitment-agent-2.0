import { describe, test, expectTypeOf } from 'vitest';
import type {
  SSEEvent,
  SSEEventType,
  PlanStep,
  AgentChatResponse,
  TaskStatus,
  ResultArtifact,
  ArtifactType,
} from '@/types/agent';

describe('agent types (S5-12)', () => {
  // TC-S5-12-4 · 类型契约对齐后端 schema (api-contract §3.2/§3.4/§4.1)。
  // 注:vitest `expectTypeOf` 在运行期是 no-op(真实类型校验需 typecheck.enabled);
  // 本 PR 按 DECISION A4(b) Z-lite 取舍,运行期校验 + 计入 N_before+4 基线。
  test('TC-S5-12-4 type contracts align with backend schema', () => {
    expectTypeOf<SSEEventType>().toEqualTypeOf<
      'thinking' | 'plan' | 'tool_call' | 'progress' | 'result' | 'error' | 'warning' | 'system'
    >();
    expectTypeOf<TaskStatus>().toEqualTypeOf<
      'PENDING' | 'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
    >();
    expectTypeOf<ArtifactType>().toEqualTypeOf<
      'jd' | 'resume' | 'match_score' | 'candidate_merge' | 'candidate_profile' | 'generic'
    >();
    expectTypeOf<PlanStep>().toHaveProperty('optional').toEqualTypeOf<boolean | undefined>();
    expectTypeOf<PlanStep>().toHaveProperty('dependencies').toEqualTypeOf<string[] | undefined>();
    expectTypeOf<AgentChatResponse['status']>().toEqualTypeOf<
      'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING'
    >();
    expectTypeOf<ResultArtifact['type']>().toEqualTypeOf<ArtifactType>();
    expectTypeOf<SSEEvent>().toHaveProperty('type').toEqualTypeOf<SSEEventType>();
    expectTypeOf<SSEEvent>().toHaveProperty('task_id').toEqualTypeOf<string>();
  });
});
