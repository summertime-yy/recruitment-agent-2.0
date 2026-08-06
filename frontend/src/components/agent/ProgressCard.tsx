// PR-19 S5-13 · 进度卡片(commit 2 实现)。
import { Progress, Typography } from 'antd';
import type { SSEEvent, ProgressData } from '@/types/agent';
import { CardContainer } from './CardContainer';

export function ProgressCard({ event }: { event: SSEEvent<ProgressData> }) {
  const percent = event.data.percent;
  return (
    <CardContainer title="进度" testId="progress-card">
      {event.data.message ? <Typography.Text>{event.data.message}</Typography.Text> : null}
      <Progress percent={Number.isFinite(percent) ? percent : 0} />
    </CardContainer>
  );
}
