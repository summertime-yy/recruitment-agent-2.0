import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from './mocks/server';

// MSW 全局启停钩子：套件开始时监听拦截器，每个用例后重置 handler，套件结束后关闭。
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
