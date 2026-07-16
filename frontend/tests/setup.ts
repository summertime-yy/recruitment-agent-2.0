import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from './mocks/server';
import request from '@/utils/request';

// jsdom 下 axios 默认走 XHR，MSW 不拦截；切到 fetch adapter（MSW 可拦截 undici fetch）。
// 同时把 baseURL 改为绝对地址：Node 的 fetch 不会像浏览器那样用 location 解析相对 URL。
request.defaults.adapter = 'fetch';
request.defaults.baseURL = 'http://localhost/api/v1';

// jsdom 缺少 antd 依赖的浏览器 API，补齐 polyfill。
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof window.ResizeObserver;
}

// MSW 全局启停钩子：套件开始时监听拦截器，每个用例后重置 handler，套件结束后关闭。
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
