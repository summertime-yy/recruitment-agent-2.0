// PR-19 S5-13 · CandidateChat 集成测试(commit 1 占位骨架 · red via test.fails)。
// 落点:TC-S5-13-6。
// PR-27 · 追加 TC-PR27-1、TC-PR27-2(活化 + TaskStream 契约)。
// 组件 API 契约:
//  - <CandidateChat /> 从 useLocation().search 解析 ?candidates=a,b → candidate_ids。
//  - MessageInput: <textarea placeholder="输入消息..." /> + 按钮 "发送"。
//  - 发送 → agentApi.chat({message, context: {candidate_ids}})。
import { describe, test, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import request from '@/utils/request';
import { sseStreamUrl } from '../helpers/sseMock';
import CandidateChat from '@/pages/CandidateChat';

const base = request.defaults.baseURL || '';

function renderCandidateChat(initialEntries: string[]) {
  return render(
    <ConfigProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <CandidateChat />
      </MemoryRouter>
    </ConfigProvider>,
  );
}

function renderWithRoutes(initialEntries: string[]) {
  return render(
    <ConfigProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/candidate-chat" element={<CandidateChat />} />
          <Route path="/resumes" element={<div>RESUMES_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </ConfigProvider>,
  );
}

beforeEach(() => {
  server.resetHandlers();
});

describe('CandidateChat (S5-13 / PR-27)', () => {
  test('TC-S5-13-6 URL ?candidates=a,b → 发送 → chat.context.candidate_ids = ["a","b"]', async () => {
    const user = userEvent.setup();
    const chatCalls: unknown[] = [];
    server.use(
      http.post(`${base}/agent/chat`, async ({ request }) => {
        chatCalls.push(await request.json());
        return HttpResponse.json({ task_id: 'tc6', status: 'PLANNING' });
      }),
    );
    renderCandidateChat(['/candidate-chat?candidates=a,b']);

    const input = await screen.findByPlaceholderText('输入消息...');
    await user.type(input, '你好');
    // antd v5 中文 Button 自动插入空格，"发送" → "发 送"
    await user.click(screen.getByRole('button', { name: /发\s*送/ }));

    await waitFor(() => expect(chatCalls.length).toBe(1));
    expect((chatCalls[0] as { context?: { candidate_ids?: string[] } }).context?.candidate_ids).toEqual([
      'a',
      'b',
    ]);
  });

  test('TC-PR27-1 ?candidates=a,b → 发送 → TaskStream 挂载 + SSE /agent/tasks/t1/stream 被请求(候选流不渲染 skip-to-score)', async () => {
    const user = userEvent.setup();
    let sseCount = 0;
    server.use(
      http.post(`${base}/agent/chat`, () => HttpResponse.json({ task_id: 't1', status: 'PLANNING' })),
      http.get(sseStreamUrl('t1'), () => {
        sseCount += 1;
        return new HttpResponse('', { headers: { 'Content-Type': 'text/event-stream' }, status: 200 });
      }),
    );
    renderCandidateChat(['/candidate-chat?candidates=a,b']);

    const input = await screen.findByPlaceholderText('输入消息...');
    await user.type(input, '你好');
    await user.click(screen.getByRole('button', { name: /发\s*送/ }));

    // TaskStream 挂载 → StreamStatusBar 出现
    await screen.findByTestId('stream-status-bar');
    // SSE endpoint 被请求过
    await waitFor(() => expect(sseCount).toBeGreaterThan(0));
    // 候选聊天流不渲染 skip-to-score 面板
    expect(screen.queryByText('跳过计划直接评分')).toBeNull();
  });

  test('TC-PR27-2 无 candidates → Empty + "去候选人列表选择" → 跳转到 /resumes', async () => {
    const user = userEvent.setup();
    renderWithRoutes(['/candidate-chat?candidates=']);

    const goBtn = await screen.findByRole('button', { name: /去候选人列表选择/ });
    await user.click(goBtn);

    await screen.findByText('RESUMES_PAGE');
  });
});
