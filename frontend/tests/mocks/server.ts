import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// 全局 Mock Service Worker 服务实例；后续 PR 通过 server.use(...) 注入业务拦截器。
export const server = setupServer(...handlers);
