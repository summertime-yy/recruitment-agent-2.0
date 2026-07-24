// PR-19 S5-13 · 警告卡片(commit 2 实现)。
import { Typography } from 'antd';
import type { SSEEvent, WarningData } from '@/types/agent';
import { CardContainer } from './CardContainer';

export function WarningCard({ event }: { event: SSEEvent<WarningData> }) {
  return (
    <CardContainer title="警告" testId="warning-card">
      <Typography.Text>{event.data.message}</Typography.Text>
      {event.data.suggestion && (
        <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
          建议：{event.data.suggestion}
        </Typography.Paragraph>
      )}
    </CardContainer>
  );
}
