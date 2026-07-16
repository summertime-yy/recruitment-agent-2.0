import { http, HttpResponse } from 'msw';

// 初始占位 handler；Stage 4 前端业务拦截器在 PR-7 起按需追加。
export const handlers = [
  http.get('http://localhost/api/v1/health', () => HttpResponse.json({ status: 'ok' })),
];
