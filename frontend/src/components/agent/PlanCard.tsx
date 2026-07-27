// PR-19 S5-13 · 计划卡片(commit 2 实现步骤渲染;commit 3 补交互按钮)。
import { List, Typography, Button, Space } from 'antd';
import type { SSEEvent, Plan } from '@/types/agent';
import { CardContainer } from './CardContainer';

export interface PlanCardProps {
  event: SSEEvent<Plan>;
  onConfirm?: () => void;
  onCancel?: () => void;
}

export function PlanCard({ event, onConfirm, onCancel }: PlanCardProps) {
  const plan = event.data;
  const showActions = Boolean(onConfirm || onCancel);
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
      {showActions && (
        <Space style={{ marginTop: 8 }}>
          {onConfirm && (
            <Button type="primary" onClick={onConfirm}>
              确认执行
            </Button>
          )}
          {onCancel && (
            <Button danger onClick={onCancel}>
              取消
            </Button>
          )}
        </Space>
      )}
    </CardContainer>
  );
}
