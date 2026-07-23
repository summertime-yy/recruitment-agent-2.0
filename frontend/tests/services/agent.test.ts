import { describe, test } from 'vitest';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import request from '@/utils/request';
import { agentApi } from '@/services/agent';

const base = request.defaults.baseURL || '';
const chatUrl = `${base}/agent/chat`;

describe('agentApi (S5-12)', () => {
  // 注:本测试在 commit 3(agentApi 落地)即转绿,故此处不标 .fails。
  // vitest .fails 为严格语义(通过即判失败),与 PR-17 pytest xfail 不同;
  // 为保持每 commit 门 2 全绿,实现落地时同步移除 .fails(最终态与 DECISION 一致)。
  test('TC-S5-12-3 chat() rejects with 429 and surfaces status on rate limit', async () => {
    server.use(http.post(chatUrl, () => new HttpResponse(null, { status: 429 })));
    let caught: unknown = null;
    try {
      await agentApi.chat({ message: 'hi' });
    } catch (e) {
      caught = e;
    }
    expect(caught).not.toBeNull();
    expect((caught as { response?: { status: number } }).response?.status).toBe(429);
  });
});
