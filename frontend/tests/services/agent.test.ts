import { describe, test } from 'vitest';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import request from '@/utils/request';
import { agentApi } from '@/services/agent';

const base = request.defaults.baseURL || '';
const chatUrl = `${base}/agent/chat`;

describe('agentApi (S5-12)', () => {
  test.fails('TC-S5-12-3 chat() rejects with 429 and surfaces status on rate limit', async () => {
    server.use(http.post(chatUrl, () => new HttpResponse(null, { status: 429 })));
    let caught: unknown = null;
    try {
      await agentApi.chat({ message: 'hi' });
    } catch (e) {
      caught = e;
    }
    expect(caught).not.toBeNull();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((caught as any).response.status).toBe(429);
  });
});
