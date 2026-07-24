// PR-19 S5-13 · 计划卡片(commit 2 实现步骤渲染;commit 3 补交互按钮)。
import { List, Typography } from 'antd';
import type { SSEEvent, Plan } from '@/types/agent';
import { CardContainer } from './CardContainer';

export interface PlanCardProps {
  event: SSEEvent<Plan>;
  onConfirm?: () => void;
  onCancel?: () => void;
}

export function PlanCard({ event }: PlanCardProps) {
  const plan = event.data;
  return (
    <CardContainer title="计划" testId="plan-card">
      <List
        size="small"
        dataSource={plan.steps}
        renderItem={(step) => (
          <List.Item>
            <Typography.Text>{step.description}</Typography.Text>
            <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
              {step.tool_name}
            </Typography.Text>
          </List.Item>
        )}
      />
    </CardContainer>
  );
}
