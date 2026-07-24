// PR-19 S5-13 · 消息时序(commit 2 实现 · 7 类 Card + system 不进列表)。
import type { SSEEvent } from '@/types/agent';
import { ThinkingCard } from './ThinkingCard';
import { PlanCard } from './PlanCard';
import { ToolCallCard } from './ToolCallCard';
import { ProgressCard } from './ProgressCard';
import { ResultCard } from './ResultCard';
import { ErrorCard } from './ErrorCard';
import { WarningCard } from './WarningCard';

export function MessageTimeline({ events }: { events: SSEEvent[] }) {
  return (
    <div data-testid="message-timeline">
      {events
        .filter((e) => e.type !== 'system')
        .map((e) => {
          switch (e.type) {
            case 'thinking':
              return <ThinkingCard key={e.id} event={e} />;
            case 'plan':
              return <PlanCard key={e.id} event={e} />;
            case 'tool_call':
              return <ToolCallCard key={e.id} event={e} />;
            case 'progress':
              return <ProgressCard key={e.id} event={e} />;
            case 'result':
              return <ResultCard key={e.id} event={e} />;
            case 'error':
              return <ErrorCard key={e.id} event={e} />;
            case 'warning':
              return <WarningCard key={e.id} event={e} />;
            default:
              return null;
          }
        })}
    </div>
  );
}
