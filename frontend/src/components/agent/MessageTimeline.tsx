// PR-19 S5-13 · 消息时序(commit 2 实现 · 7 类 Card + system 不进列表)。
import type {
  SSEEvent,
  Plan, ThinkingData, ToolCallData, ProgressData,
  ResultData, ErrorData, WarningData,
} from '@/types/agent';
import { ThinkingCard } from './ThinkingCard';
import { PlanCard } from './PlanCard';
import { ToolCallCard } from './ToolCallCard';
import { ProgressCard } from './ProgressCard';
import { ResultCard } from './ResultCard';
import { ErrorCard } from './ErrorCard';
import { WarningCard } from './WarningCard';

export interface MessageTimelineProps {
  events: SSEEvent[];
  onPlanConfirm?: () => void;
  onPlanCancel?: () => void;
}

export function MessageTimeline({ events, onPlanConfirm, onPlanCancel }: MessageTimelineProps) {
  return (
    <div data-testid="message-timeline">
      {events
        .filter((e) => e.type !== 'system')
        .map((e) => {
          switch (e.type) {
            case 'thinking':
              return <ThinkingCard key={e.id} event={e as SSEEvent<ThinkingData>} />;
            case 'plan':
              return (
                <PlanCard
                  key={e.id}
                  event={e as SSEEvent<Plan>}
                  onConfirm={onPlanConfirm}
                  onCancel={onPlanCancel}
                />
              );
            case 'tool_call':
              return <ToolCallCard key={e.id} event={e as SSEEvent<ToolCallData>} />;
            case 'progress':
              return <ProgressCard key={e.id} event={e as SSEEvent<ProgressData>} />;
            case 'result':
              return <ResultCard key={e.id} event={e as SSEEvent<ResultData>} />;
            case 'error':
              return <ErrorCard key={e.id} event={e as SSEEvent<ErrorData>} />;
            case 'warning':
              return <WarningCard key={e.id} event={e as SSEEvent<WarningData>} />;
            default:
              return null;
          }
        })}
    </div>
  );
}
