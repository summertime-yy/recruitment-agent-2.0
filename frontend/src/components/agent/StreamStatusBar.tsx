// PR-19 S5-13 · 顶部状态条(commit 2 实现 · system:cancelled 派生已取消)。
import { Typography } from 'antd';

export interface StreamStatusBarProps {
  systemMessage?: string;
  status?: string;
  cancelled?: boolean;
}

export function StreamStatusBar({ systemMessage, cancelled }: StreamStatusBarProps) {
  const isCancelled = cancelled || systemMessage === 'cancelled';
  const text = isCancelled ? '已取消' : systemMessage ?? '';
  return (
    <div data-testid="stream-status-bar" style={{ marginBottom: 8 }}>
      <Typography.Text type={isCancelled ? 'secondary' : undefined}>{text}</Typography.Text>
    </div>
  );
}
