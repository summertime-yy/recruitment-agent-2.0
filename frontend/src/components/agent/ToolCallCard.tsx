// PR-19 S5-13 · 工具调用卡片(commit 2 实现)。
import { Typography } from 'antd';
import type { SSEEvent, ToolCallData } from '@/types/agent';
import { CardContainer } from './CardContainer';

export function ToolCallCard({ event }: { event: SSEEvent<ToolCallData> }) {
  return (
    <CardContainer title="工具调用" testId="toolcall-card">
      <Typography.Text code>{event.data.tool_name}</Typography.Text>
      <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
        {JSON.stringify(event.data.params)}
      </Typography.Paragraph>
    </CardContainer>
  );
}
