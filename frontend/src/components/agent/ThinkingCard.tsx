// PR-19 S5-13 · 思考卡片(commit 2 实现)。
import { Typography } from 'antd';
import type { SSEEvent, ThinkingData } from '@/types/agent';
import { CardContainer } from './CardContainer';

export function ThinkingCard({ event }: { event: SSEEvent<ThinkingData> }) {
  return (
    <CardContainer title="思考" testId="thinking-card">
      <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
        {event.data.content}
      </Typography.Paragraph>
    </CardContainer>
  );
}
