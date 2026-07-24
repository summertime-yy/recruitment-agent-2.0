// PR-19 S5-13 · 顶部状态条(commit 2 实现 · commit 5 补已取消分支)。
import { Typography } from 'antd';

export interface StreamStatusBarProps {
  systemMessage?: string;
  status?: string;
  cancelled?: boolean;
}

export function StreamStatusBar({ systemMessage, cancelled }: StreamStatusBarProps) {
  const text = cancelled ? '已取消' : systemMessage ?? '';
  return (
    <div data-testid="stream-status-bar" style={{ marginBottom: 8 }}>
      <Typography.Text type={cancelled ? 'secondary' : undefined}>{text}</Typography.Text>
    </div>
  );
}
