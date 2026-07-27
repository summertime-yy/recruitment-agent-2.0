// PR-19 S5-13 · CandidateChat 集成测试(commit 1 占位骨架 · red via test.fails)。
// 落点:TC-S5-13-6。
// 组件 API 契约(实现见 commit 4):
//  - <CandidateChat /> 从 useLocation().search 解析 ?candidates=a,b → candidate_ids。
//  - MessageInput: <textarea placeholder="输入消息..." /> + 按钮 "发送"。
//  - 发送 → agentApi.chat({message, context: {candidate_ids}})。
import { describe, test, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import request from '@/utils/request';
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

beforeEach(() => {
  server.resetHandlers();
});

describe('CandidateChat (S5-13)', () => {
  test(
    'TC-S5-13-6 URL ?candidates=a,b → 发送 → chat.context.candidate_ids = ["a","b"]',
    async () => {
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
    },
  );
});
