// PR-19 S5-13 · ChatCenter 集成测试(commit 1 占位骨架 · red via test.fails)。
// 落点:TC-S5-13-1 / TC-S5-13-2 / TC-S5-13-4 / TC-S5-13-5 / TC-S5-13-9。
// 组件 API 契约(实现见 commit 3):
//  - <ChatCenter /> 渲染 StreamStatusBar + SkipToScorePanel(Collapse) + MessageTimeline + MessageInput。
//  - MessageInput: <textarea placeholder="输入消息..." /> + 按钮 "发送"。
//  - PlanCard: "确认执行" 按钮 → agentApi.executePlan({task_id}); "取消" 按钮 → agentApi.cancelTask(task_id)。
//  - SkipToScorePanel: JD Select(placeholder "选择 JD") + Resume 多选(placeholder "选择候选人简历") + 按钮 "立即评分"。
//  - StreamStatusBar: status==='closed' 且 systemMessage==='cancelled' → 文本 "已取消"。
import { describe, test, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import request from '@/utils/request';
import ChatCenter from '@/pages/ChatCenter';
import { sseStreamUrl, makeSseHandler } from '../helpers/sseMock';

const base = request.defaults.baseURL || '';

function renderChat() {
  return render(
    <ConfigProvider>
      <MemoryRouter>
        <ChatCenter />
      </MemoryRouter>
    </ConfigProvider>,
  );
}

beforeEach(() => {
  server.resetHandlers();
});

describe('ChatCenter (S5-13)', () => {
  test.fails('TC-S5-13-1 send message → plan stream → PlanCard confirm → executePlan called', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${base}/agent/chat`, () => HttpResponse.json({ task_id: 't1', status: 'PLANNING' })),
      makeSseHandler(sseStreamUrl('t1'), [
        { id: '1', event: 'thinking', data: { content: 'thinking...' } },
        {
          id: '2',
          event: 'plan',
          data: {
            task_id: 't1',
            steps: [{ step_id: 's1', description: '步骤一', tool_name: 'search_resumes', params: {} }],
          },
        },
      ]),
    );
    renderChat();

    const input = await screen.findByPlaceholderText('输入消息...');
    await user.type(input, '帮我找简历');
    await user.click(screen.getByText('发送'));

    // PlanCard 出现并展示步骤
    await screen.findByText('步骤一');
    const confirmBtn = screen.getByText('确认执行');

    const executePlanCalls: unknown[] = [];
    server.use(
      http.post(`${base}/agent/execute-plan`, async ({ request }) => {
        executePlanCalls.push(await request.json());
        return HttpResponse.json({ task_id: 't1', status: 'EXECUTING' });
      }),
    );
    await user.click(confirmBtn);
    await waitFor(() => expect(executePlanCalls.length).toBe(1));
    expect(executePlanCalls[0]).toMatchObject({ task_id: 't1' });
  });

  test.fails('TC-S5-13-2 skip-to-score panel → select JD/resume → skipToScore called + progress card', async () => {
    const user = userEvent.setup();
    const skipCalls: unknown[] = [];
    server.use(
      http.get(`${base}/jds`, () =>
        HttpResponse.json({ items: [{ jd_id: 'jd1', title: 'JD One' }], total: 1, page: 1, page_size: 10 }),
      ),
      http.get(`${base}/resumes`, () =>
        HttpResponse.json({ items: [{ resume_id: 'r1', candidate_name: 'Alice' }], total: 1, page: 1, page_size: 10 }),
      ),
      http.post(`${base}/agent/skip-to-score`, async ({ request }) => {
        skipCalls.push(await request.json());
        return HttpResponse.json({ task_id: 't-score', status: 'EXECUTING' });
      }),
      makeSseHandler(sseStreamUrl('t-score'), [
        { id: '1', event: 'progress', data: { step_id: 's1', progress: 0.5, message: 'progress-content' } },
      ]),
    );
    renderChat();

    // 展开 skip-to-score 面板(默认收起)并选择
    await user.click(screen.getByText('跳过计划直接评分'));
    await user.click(screen.getByPlaceholderText('选择 JD'));
    await user.click(await screen.findByText('JD One'));
    await user.click(screen.getByPlaceholderText('选择候选人简历'));
    await user.click(await screen.findByText('Alice'));
    await user.click(screen.getByText('立即评分'));

    await waitFor(() => expect(skipCalls.length).toBe(1));
    expect(skipCalls[0]).toMatchObject({ jd_id: 'jd1', candidate_ids: ['r1'] });
    // 评分任务开始流式 → 进度卡片出现
    await screen.findByText('progress-content');
  });

  test.fails('TC-S5-13-4 SSE disconnect then reconnect → same event id not double-rendered', async () => {
    let call = 0;
    server.use(
      http.post(`${base}/agent/chat`, () => HttpResponse.json({ task_id: 't4', status: 'PLANNING' })),
      http.get(sseStreamUrl('t4'), () => {
        call += 1;
        if (call === 1) {
          // 首次连接异常断开(非终态)→ 触发重连
          return new HttpResponse(null, { status: 500 });
        }
        // 重连后下发 id=1(与首次相同) + id=2 → 去重后 id=1 只渲染一次
        const text =
          'id: 1\nevent: thinking\ndata: {"content":"thinking-t4"}\n\n' +
          'id: 2\nevent: thinking\ndata: {"content":"thinking-t4-b"}\n\n';
        const stream = new ReadableStream({
          start(c) {
            c.enqueue(new TextEncoder().encode(text));
            c.close();
          },
        });
        return new HttpResponse(stream, { headers: { 'content-type': 'text/event-stream' } });
      }),
    );
    renderChat();
    const input = await screen.findByPlaceholderText('输入消息...');
    await user.type(input, 'hi');
    await user.click(screen.getByText('发送'));

    const timeline = await screen.findByTestId('message-timeline');
    await waitFor(() => expect(timeline).toHaveTextContent('thinking-t4'));
    await waitFor(() => expect(timeline).toHaveTextContent('thinking-t4-b'));
    // id=1 不应重复渲染
    const matches = screen.getAllByText('thinking-t4');
    expect(matches.length).toBe(1);
  });

  test.fails('TC-S5-13-5 PlanCard cancel → cancelTask called', async () => {
    const user = userEvent.setup();
    const cancelCalls: string[] = [];
    server.use(
      http.post(`${base}/agent/chat`, () => HttpResponse.json({ task_id: 't5', status: 'PLANNING' })),
      makeSseHandler(sseStreamUrl('t5'), [
        {
          id: '2',
          event: 'plan',
          data: {
            task_id: 't5',
            steps: [{ step_id: 's1', description: '步骤五', tool_name: 'search_resumes', params: {} }],
          },
        },
      ]),
      http.post(`${base}/agent/tasks/:taskId/cancel`, ({ params }) => {
        cancelCalls.push(params.taskId as string);
        return HttpResponse.json({ task_id: params.taskId, status: 'CANCELLED' });
      }),
    );
    renderChat();
    const input = await screen.findByPlaceholderText('输入消息...');
    await user.type(input, 'plan');
    await user.click(screen.getByText('发送'));

    await screen.findByText('步骤五');
    await user.click(screen.getByText('取消'));
    await waitFor(() => expect(cancelCalls).toContain('t5'));
  });

  test.fails('TC-S5-13-9 system:cancelled stream → top bar shows "已取消" · no ErrorCard', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${base}/agent/chat`, () => HttpResponse.json({ task_id: 't9', status: 'PLANNING' })),
      makeSseHandler(sseStreamUrl('t9'), [
        { id: '1', event: 'system', data: { message: 'cancelled' } },
      ]),
    );
    renderChat();
    const input = await screen.findByPlaceholderText('输入消息...');
    await user.type(input, 'go');
    await user.click(screen.getByText('发送'));

    // 顶部状态条应显示 "已取消"(仅取消终态才出现)
    await screen.findByText('已取消');
  });
});
