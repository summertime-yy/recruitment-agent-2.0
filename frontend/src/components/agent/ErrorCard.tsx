// PR-19 S5-13 · 错误卡片(commit 2 实现)。
import { Typography } from 'antd';
import type { SSEEvent, ErrorData } from '@/types/agent';
import { CardContainer } from './CardContainer';

export function ErrorCard({ event }: { event: SSEEvent<ErrorData> }) {
  return (
    <CardContainer title="错误" testId="error-card">
      <Typography.Text type="danger">{event.data.message}</Typography.Text>
      {event.data.code && (
        <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
          [{event.data.code}]
        </Typography.Text>
      )}
    </CardContainer>
  );
}
