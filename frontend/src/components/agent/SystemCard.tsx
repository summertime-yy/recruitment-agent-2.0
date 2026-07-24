// PR-19 S5-13 · 系统卡片(commit 2 实现 · 顶部条消费,不进 events 列表)。
import { Typography } from 'antd';
import type { SSEEvent, SystemData } from '@/types/agent';
import { CardContainer } from './CardContainer';

export function SystemCard({ event }: { event: SSEEvent<SystemData> }) {
  return (
    <CardContainer title="系统" testId="system-card">
      <Typography.Text>{event.data.message}</Typography.Text>
    </CardContainer>
  );
}
