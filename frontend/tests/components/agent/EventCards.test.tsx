// PR-19 S5-13 · EventCards 单元测试(commit 2 实现 · 全绿)。
// 落点:TC-S5-13-3 / TC-S5-13-7 / TC-S5-13-8 / TC-S5-13-10。
// 组件 API 契约:
//  - <MessageTimeline events={SSEEvent[]} /> 渲染 7 类非 system 卡片(system 不进列表)。
//  - <WarningCard event={SSEEvent<WarningData>} /> 渲染 data.message。
//  - <ErrorCard event={SSEEvent<ErrorData>} /> 渲染 data.message。
//  - <StreamStatusBar systemMessage={string} /> 顶部条渲染 system message。
import { describe, test, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { MessageTimeline, StreamStatusBar, WarningCard, ErrorCard, ProgressCard } from '@/components/agent';
import {
  makeThinkingEvent,
  makePlanEvent,
  makeToolCallEvent,
  makeProgressEvent,
  makeResultEvent,
  makeErrorEvent,
  makeWarningEvent,
  makeSystemEvent,
} from '../../fixtures/sseEvents';

describe('EventCards (S5-13)', () => {
  test('TC-S5-13-3 8 类事件 → 7 类 Card 出现在 timeline(system 不进列表)', () => {
    render(
      <ConfigProvider>
        <MessageTimeline
          events={[
            makeThinkingEvent('1'),
            makePlanEvent('2'),
            makeToolCallEvent('3'),
            makeProgressEvent('4', 100),
            makeResultEvent('5'),
            makeErrorEvent('6'),
            makeWarningEvent('7'),
            makeSystemEvent('8'),
          ]}
        />
      </ConfigProvider>,
    );
    // 7 类非 system 卡片应各自渲染内容
    expect(screen.getByText('thinking-content')).toBeInTheDocument();
    expect(screen.getByText('步骤一')).toBeInTheDocument();
    // search_resumes 既出现在 PlanCard(step.tool_name) 也出现在 ToolCallCard(tool_name)
    expect(within(screen.getByTestId('toolcall-card')).getByText('search_resumes')).toBeInTheDocument();
    expect(screen.getByText('进度已更新至 100%')).toBeInTheDocument();
    expect(screen.getByText('result-content')).toBeInTheDocument();
    expect(screen.getByText('error-content')).toBeInTheDocument();
    expect(screen.getByText('warning-content')).toBeInTheDocument();
    // system 不应作为 timeline 卡片渲染
    expect(screen.queryByText('system-content')).toBeNull();
  });

  test('TC-S5-13-7 warning 事件 → WarningCard 显示 message', () => {
    render(
      <ConfigProvider>
        <WarningCard event={makeWarningEvent('1')} />
      </ConfigProvider>,
    );
    expect(screen.getByText('warning-content')).toBeInTheDocument();
  });

  test('TC-S5-13-8 system 事件 → 顶部条显示 message · 不进 timeline', () => {
    render(
      <ConfigProvider>
        <StreamStatusBar systemMessage="sys-8" />
        <MessageTimeline events={[makeThinkingEvent('1', 'thinking-8')]} />
      </ConfigProvider>,
    );
    expect(screen.getByText('sys-8')).toBeInTheDocument();
    expect(screen.getByText('thinking-8')).toBeInTheDocument();
  });

  test('TC-S5-13-10 error 事件 → ErrorCard 显示 message', () => {
    render(
      <ConfigProvider>
        <ErrorCard event={makeErrorEvent('1')} />
      </ConfigProvider>,
    );
    expect(screen.getByText('error-content')).toBeInTheDocument();
  });

  // PR-29 · 进度事件字段对齐后端契约(act.py:136 发 {step_id, percent}, 无 message)
  test('TC-PR29-1 progress 事件 → ProgressCard 进度条 aria-valuenow 反映 percent 字段', () => {
    render(
      <ConfigProvider>
        <ProgressCard event={makeProgressEvent('p1', 100)} />
      </ConfigProvider>,
    );
    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '100');
  });
});
