# 前端测试（Vitest）

本目录为 Stage 4 前端测试基建，由 S4-09（PR-6）引入。

## 技术栈

- **vitest**（`vitest run` / `vitest` watch / `vitest --ui`）
- **jsdom** 测试环境
- **@testing-library/react** + **@testing-library/jest-dom** + **@testing-library/user-event**
- **msw**（Mock Service Worker）拦截 `/api` 请求

## 目录结构

```
tests/
  setup.ts            # 全局 setup：jest-dom 匹配器 + MSW 启停钩子
  mocks/
    server.ts         # MSW server 实例（setup.ts 引用）
    handlers.ts       # 全局 handler（占位）；业务拦截器用 server.use() 注入
  *.test.ts(x)        # 测试用例（<Name>.test.tsx / <name>.test.ts）
```

## 编写新测试

- 测试文件命名：`<Name>.test.tsx`（组件）或 `<name>.test.ts`（纯函数/service）。
- 使用 `@/` 别名引用 `src/` 下的模块（与 vite/tsconfig 一致）。
- 需要 DOM 渲染时，用 `<MemoryRouter>` 包裹（页面组件依赖 `react-router-dom`）。
- 拦截 API：在用例内 `server.use(http.get(...))`，`afterEach` 会自动 `resetHandlers()`。

## 运行

```bash
npm run test       # 单次运行（CI）
npm run test:watch # watch 模式
npm run test:ui    # 浏览器 UI
```

## 约定

- 不引入业务测试于 PR-6（仅基建 + 3 条 smoke）。
- 业务用例见 PR-7（services/match.test.ts）、PR-8（pages）。
