// PR-19 S5-13 · Card 共享容器(commit 2 实现)。
import { Card } from 'antd';
import type { ReactNode } from 'react';

export interface CardContainerProps {
  title?: ReactNode;
  extra?: ReactNode;
  children?: ReactNode;
  testId?: string;
}

export function CardContainer({ title, extra, children, testId }: CardContainerProps) {
  return (
    <Card size="small" title={title} extra={extra} data-testid={testId} style={{ marginBottom: 8 }}>
      {children}
    </Card>
  );
}
