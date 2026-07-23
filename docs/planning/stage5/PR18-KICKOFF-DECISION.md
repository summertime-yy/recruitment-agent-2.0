# PR-18 KICKOFF DECISION · S5-12 前端类型 + SSE 客户端 Hook

> **主指挥官裁定**(Claude Code, ark-code-latest · 主指挥官身份)
> **对象**:执行体(下一 session)
> **合并依据**:`PR18-KICKOFF-QUESTIONS.md`(初稿) + `PR18-KICKOFF-REVISIONS.md`(REVISIONS · 已裁定)
> **权威事实源**:
> - `docs/planning/TASKS-STAGE5.md §S5-12`
> - `docs/api-contract.md §3.1–§3.5 / §4.1–§4.5`
> - `HANDOFF.md §9.4 陷阱 4/5/6/8/9`
> - `backend/app/schemas/agent.py`(SSEEvent / SSEEventType 定义)
> - `backend/app/agent/orchestrator/state_machine.py`(TaskStatus 全大写)
> - `backend/app/agent/orchestrator/engine.py::_ARTIFACT_TYPE_MAP`(6 键:jd / resume / match_score / candidate_merge / candidate_profile / generic)
> - `backend/app/api/v1/agent.py:87,97`(chat 端点返裸 dict,实测 status 仅 `PLANNING`)
> - `frontend/vite.config.ts:22-27`(vitest test 段未开 typecheck)
> - `frontend/src/utils/request.ts`(axios 拦截器已 reject error)
>
> **起手 master HEAD**:`f75e2a9`
> **起手基线**:后端 **120 passed** / 前端 test `N_before`(执行体阶段 0 首次跑得数字)
> **本 PR 编号**:PR-18 · 任务 S5-12 · 分支 `feat/pr-18-s5-12-sse-hook`

---

## 〇 · PR 编号与前置事实

- **PR-18 = S5-12 严格版**(types + services + useTaskStream Hook + TC-S5-12-1..4)。TASKS §S5-12 是权威事实源,HANDOFF §9.1「PR-18 = SSE Hook + ChatCenter」是 PR-16/17 kickoff 期漂移表述,以本 DECISION 为准闭合。
- **PR-19 = S5-13**(ChatCenter / CandidateChat / 8 类 Card / TC-S5-13-1..9)· 依赖 PR-18 合入。
- **起手 master HEAD** = `f75e2a9`(§9 refresh + PR-17 STEP6 报告状态已合并)。若开工时 HEAD 不是 `f75e2a9`(可能有别的 docs-only commit 先合入)或工作区含 `frontend/src/**` 未提交改动,**§十八 clause 1 触发,停下汇报**。

---

## 一 · 交付范围硬边界

### 允许改动(必改)

| 类别 | 文件 | 说明 |
|---|---|---|
| 前端类型 | `frontend/src/types/agent.ts`(新建) | SSEEvent / SSEEventType / Plan / PlanStep / TaskStatus / AgentChatRequest 等类型联合,详见 §三 |
| 前端服务 | `frontend/src/services/agent.ts`(新建) | `agentApi` 对象 5 函数(chat/executePlan/skipToScore/cancelTask/getTask),详见 §四 |
| 前端 Hook | `frontend/src/hooks/useTaskStream.ts`(新建) | fetch + ReadableStream SSE 解析器 + 重连状态机,详见 §五 |
| 前端 Hook 目录 | `frontend/src/hooks/`(新建目录 · index.ts 可选) | 目录首次建立 |
| 前端测试目录 | `frontend/tests/hooks/`(新建)、`frontend/tests/services/`(既有)、`frontend/tests/types/`(新建) | 4 用例落点,详见 §六 |
| 前端测试文件 | `tests/hooks/useTaskStream.test.ts`、`tests/services/agent.test.ts`、`tests/types/agent.types.test.ts` | TC-S5-12-1..4 |
| 类型 re-export(可选) | `frontend/src/types/index.ts` 追加 `export * from './agent'` | 便于既有页面 import,不改既有类型 |

### 禁止改动(违则 §十八 clause 触发)

- `frontend/src/pages/ChatCenter.tsx` / `frontend/src/pages/CandidateChat.tsx` —— 留 PR-19 全量替换
- `frontend/src/components/agent/*Card.tsx` —— 留 PR-19 建立
- `frontend/src/store/` —— 本 PR 不引入 zustand/Redux state
- `backend/app/**` —— 前端 PR · 后端零改动
- `docs/api-contract.md` —— 契约已固化,前端严格对齐,不倒改
- `frontend/vite.config.ts` —— **本 PR 不开 typecheck**(TC-S5-12-4 走 Z-lite 运行期 · 见 A4)

### Q1 边界:方案 A · 严格 S5-12

严格对齐 TASKS §S5-12,不含 ChatCenter/任何 Card 组件。理由:TASKS 是权威事实源;HANDOFF §9.1 漂移由本 DECISION 就地闭合;S5-12 4 用例独立可验证;后端 PR-14/17 已完整交付 SSE 事件流,PR-19 加 UI 时不会踩阻塞。

---

## 二 · 关键技术选型

### Q2 决:SSE 客户端 = **fetch + ReadableStream 手写解析器**(选项 B)

**理由**:

1. **TC-S5-12-2 契约要求** —— "模拟断线后重连请求头带 `Last-Event-ID`(msw mock)"是白纸黑字的验收断言。原生 `EventSource` 由 W3C spec 规定 `Last-Event-ID` 由浏览器**自动**填充,开发者无法控制,该断言极难在 jsdom + msw 环境下测出。fetch-based 天然可拦。
2. **未来鉴权兼容** —— 项目远期接入登录必然需要 `Authorization` 头,`EventSource` 不允许自定义头,晚换不如早换。
3. **与既有测试模式对齐** —— `frontend/tests/setup.ts:8` 已强制 `request.defaults.adapter = 'fetch'`,`tests/services/match.test.ts` 已确立 msw + fetch adapter 模式,fetch-based hook 天然对齐。
4. **手写 SSE 解析器复杂度可控** —— 约 100-150 行,后端 PR-14 已按标准 `event:\ndata:\nid:\n\n` 分帧输出,解析器实现清晰。

**明确排除**:
- 选项 A(原生 EventSource · 加 jsdom polyfill):测试成本失控
- 选项 C(`@microsoft/fetch-event-source` 依赖):无必要引入外部依赖

### Q2 附:忽略 server `retry:` 指令(B3 采纳)

**规则**:hook 使用**自身指数退避**(3s → 6s → 12s,超 3 次 `status='error'`),**忽略后端 SSE 流中的 `retry:` 字段**。api-contract §3.5 的 `retry:3000` 是给原生 EventSource 用的,选项 B 手写解析器不自动消费,避免"既读 retry 又用固定退避"的二义。

---

## 三 · 类型契约(`frontend/src/types/agent.ts`)

### Q4/5/6/7/8 决:union type + 严格对齐 + Artifact 严格 union

```typescript
// ============ SSE 信封 · api-contract §3.2 ============

export type SSEEventType =
  | 'thinking'
  | 'plan'
  | 'tool_call'
  | 'progress'
  | 'result'
  | 'error'
  | 'warning'
  | 'system';

export interface SSEEvent<T = unknown> {
  id: string;                    // 任务内单调递增序号
  type: SSEEventType;
  task_id: string;
  step_id?: string;
  timestamp: string;
  data: T;
}

// ============ 事件 data 结构(部分) · api-contract §3.3 ============

export interface ThinkingData { content: string }
export interface ToolCallData { step_id: string; tool_name: string; params: Record<string, unknown> }
export interface ProgressData { step_id: string; progress: number; message: string }
export interface ResultData { content: string; artifacts?: ResultArtifact[] }
export interface ErrorData { code: string; message: string; recoverable?: boolean }  // recoverable 字段类型保留但语义见 §五 Q12
export interface WarningData { message: string; suggestion?: string }
export interface SystemData { message: string }
// PlanData = Plan(§3.4)

// ============ Result Artifact · 追债项 3 前端 union 侧 ============

export type ArtifactType =
  | 'jd'
  | 'resume'
  | 'match_score'
  | 'candidate_merge'
  | 'candidate_profile'
  | 'generic';

export interface ResultArtifact {
  step_id: string;
  tool_name: string;
  type: ArtifactType;
  ref_id?: string;
  data?: unknown;                // 各 type 具体形状留 PR-19 卡片渲染时窄化
}

// ============ Plan · api-contract §3.4 ============

export interface PlanStep {
  step_id: string;
  description: string;
  tool_name: string;
  params: Record<string, unknown>;
  expected_output: string;
  optional?: boolean;
  dependencies?: string[];
  estimated_duration_seconds?: number;
}

export interface Plan {
  task_id: string;
  steps: PlanStep[];
  reasoning?: string;
}

// ============ TaskStatus · api-contract §4.4 ============

export type TaskStatus =
  | 'PENDING'
  | 'PLANNING'
  | 'WAITING_CONFIRMATION'
  | 'EXECUTING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

// ============ REST 请求/响应 · api-contract §4.1..§4.5 ============

export interface AgentChatRequest {
  message: string;
  context?: {
    jd_id?: string;
    candidate_ids?: string[];
  };
}

/**
 * B1 采纳(b):保留 3 值子集 + 注释。
 * api-contract §4.1 声明 status ∈ {PLANNING, WAITING_CONFIRMATION, EXECUTING};
 * 实测 PR-14 后 `backend/app/api/v1/agent.py:87` 端点 hardcode 返 `"PLANNING"`,
 * 但类型层坚持契约声明的 3 值子集,不假设实测唯一值。
 * `initial_plan` 字段类型保留 optional,但 PR-14 起后端不填,前端不消费(§9.4 陷阱 4)。
 */
export interface AgentChatResponse {
  task_id: string;
  status: 'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING';
  initial_plan?: Plan;
}

export interface ExecutePlanRequest {
  task_id: string;
  accepted_steps?: string[];
  modifications?: {
    step_id: string;
    modified_params?: Record<string, unknown>;
  }[];
}

export interface ExecutePlanResponse {
  task_id: string;
  status: 'EXECUTING';
}

export interface SkipToScoreRequest {
  jd_id: string;
  candidate_ids: string[];
}

export interface SkipToScoreResponse {
  task_id: string;
  status: 'EXECUTING';
}

export interface CancelTaskResponse {
  task_id: string;
  status: 'CANCELLED';
}

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  current_step?: string;
  plan?: Plan;
  result?: ResultData;
  error?: { code: string; message: string };
  created_at: string;
  updated_at: string;
}
```

### B2 备注:追债项 3 护栏时机

`ArtifactType` union 严格采纳(方案 A),但**本 PR 无消费点**(无 switch 分派),真正 exhaustiveness 护栏在 **PR-19 卡片 switch** 激活。附:PR-17 新债 12(`create_match_score` dangling)修复时会改 `_ARTIFACT_TYPE_MAP` 键,前端 union 届时需同步 —— PR-19 起手时留意。

### Q4 备注:types 组织

新建 `frontend/src/types/agent.ts` **独立文件**,`types/index.ts` 追加 `export * from './agent'`(不迁移既有类型),既有页面既有 import 不受影响。

---

## 四 · Services 层(`frontend/src/services/agent.ts`)

### Q9 决:仿 `candidateApi` 对象模式 · 5 函数

```typescript
import request from '@/utils/request';
import type {
  AgentChatRequest, AgentChatResponse,
  ExecutePlanRequest, ExecutePlanResponse,
  SkipToScoreRequest, SkipToScoreResponse,
  CancelTaskResponse, TaskStatusResponse,
} from '@/types/agent';

export const agentApi = {
  chat(data: AgentChatRequest): Promise<AgentChatResponse> {
    return request.post('/agent/chat', data);
  },
  executePlan(data: ExecutePlanRequest): Promise<ExecutePlanResponse> {
    return request.post('/agent/execute-plan', data);
  },
  skipToScore(data: SkipToScoreRequest): Promise<SkipToScoreResponse> {
    return request.post('/agent/skip-to-score', data);
  },
  cancelTask(taskId: string): Promise<CancelTaskResponse> {
    return request.post(`/agent/tasks/${taskId}/cancel`);
  },
  getTask(taskId: string): Promise<TaskStatusResponse> {
    return request.get(`/agent/tasks/${taskId}`);
  },
};
```

### Q9.1 决:429 不加中间层

`frontend/src/utils/request.ts` 拦截器已在 error 分支打印 `[API Error]` 并 `Promise.reject(error)`。TC-S5-12-3 断言"429 时抛出可捕获错误"—— 调用方自行 `try/catch` 判 `err.response?.status === 429`,`agentApi.chat` **不做中间层封装**,不抛自定义 error 类。

---

## 五 · Hook 契约(`frontend/src/hooks/useTaskStream.ts`)

### Q3 决(A3 补 `lastHeartbeatAt` 后)

```typescript
export interface UseTaskStreamOptions {
  taskId: string;
  autoStart?: boolean;              // 默认 true
  lastEventId?: string;             // 首次连接的断点(本 PR 不持久化 · Q3.3 留 PR-19)
  onEvent?: (event: SSEEvent) => void;
  onError?: (err: Error) => void;
}

export type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'closed' | 'error';

export interface UseTaskStreamResult {
  events: SSEEvent[];                                    // 按 id 去重升序(Q3.2)
  lastEventId: string | null;
  status: StreamStatus;
  latestByType: Partial<Record<SSEEventType, SSEEvent>>; // 便捷访问(Q3.1)· system 也进
  lastHeartbeatAt: number | null;                        // ms 时间戳(A3 新补)
  reconnect: () => void;
  close: () => void;
}

export function useTaskStream(opts: UseTaskStreamOptions): UseTaskStreamResult;
```

### Q3.1 决:保留 `latestByType`(便于 PR-19 页面按类型消费)
### Q3.2 决:`events` 按 `id` 升序 + 去重(幂等更稳)
### Q3.3 决:`lastEventId` 持久化到 storage · **本 PR 不做**,留 PR-19 UX 决策

### Q11 + Q12 + A1 + A2 决:重连状态机(闭合版)

**唯一权威规则**(A1 采纳 · 闭合 Q11 关流二义):

- Hook 维护布尔 `hasReachedTerminal`,当收到任一 SSE 事件其 `type === 'result' || type === 'error'` 时置 true(**A2 采纳 · 弃 `data.recoverable === false` 判定**,原因:后端 `SSEEvent.data` 是 `Any`,`recoverable` 字段未固化在 pydantic schema,前端不依赖;后端 `engine.py:507/518/531/544` 目前发的 ERROR 全带 `recoverable:false`,即所有 ERROR 都是终态,无"可恢复错误"分支)
- 流关闭(fetch stream `done: true` 或 abort/error)时:
  - 若 `hasReachedTerminal === true` → `status='closed'`,**不重连**
  - 若 `hasReachedTerminal === false` → 走重连流程(A1 闭合:仅**非终态关流才重连**)
- 重连退避:第 1 次 3000ms → 第 2 次 6000ms → 第 3 次 12000ms,超 3 次 `status='error'`(不再重试)
- 重连时构造 fetch header `Last-Event-ID: <lastEventId>`(TC-S5-12-2 断言点)

### Q13 决 + A3 补充:15s 心跳处理

- `system` 类型事件收到时更新 `latestByType.system` **和** `lastHeartbeatAt = Date.now()`
- `system` 事件**不入** `events[]` 数组(避免 UI 层历史列表污染)
- `lastHeartbeatAt` 暴露给 UI 层,PR-19 决策"心跳丢失 UX"(如 30s 内未收到心跳提示疑似断线)

### Q14 决:事件解析容错

- 未识别 `type`(不在 SSEEventType union) → `console.warn('useTaskStream: unknown SSE event type: ...')` + 跳过入 `events[]`,**不 throw**
- `JSON.parse(data)` 失败 → 同上 warn + 跳过
- 保证 hook 不因后端未来新增事件类型或异常帧崩溃

### Q16 决:`AbortController` 生命周期

- Hook 内每次连接创建新 `AbortController`,`fetch(url, {signal: controller.signal, headers: {...}})`
- `close()` 触发 `controller.abort()` + 清定时器
- React `useEffect` cleanup 保证 unmount 时必 abort,无 memory leak

---

## 六 · 测试落点与策略

### Q10 决:测试文件位置

| TC | 落点 | 类型 |
|---|---|---|
| TC-S5-12-1(8 类事件解析) | `frontend/tests/hooks/useTaskStream.test.ts` | Hook 单测 · msw ReadableStream mock |
| TC-S5-12-2(Last-Event-ID 重连) | 同上 | Hook 集成 · 2 次 msw handler(第 2 次断言 `request.headers.get('last-event-id')`) |
| TC-S5-12-3(chat 429 处理) | `frontend/tests/services/agent.test.ts` | Service 单测 · `server.use(http.post(...chat, () => new HttpResponse(null, {status: 429})))` |
| TC-S5-12-4(类型对齐 schema) | `frontend/tests/types/agent.types.test.ts` | 运行期 `expectTypeOf` 校验(A4 Z-lite) |

### Q10.1 决:SSE mock 方式(fetch/ReadableStream 分支)

```typescript
// 示意:mock 一个含 2 帧的 SSE 流
server.use(
  http.get('http://localhost/api/v1/agent/tasks/:taskId/stream', () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('id: 1\nevent: thinking\ndata: {"content":"..."}\n\n'));
        controller.enqueue(new TextEncoder().encode('id: 2\nevent: plan\ndata: {"task_id":"...","steps":[]}\n\n'));
        controller.close();
      },
    });
    return new HttpResponse(stream, { headers: { 'content-type': 'text/event-stream' } });
  })
);
```

TC-S5-12-2 断线重连断言:
- 第一次 handler:返 2 帧后 `controller.close()`(流结束)
- Hook 感知流关(未收 result/error 终态) → 走非终态重连(A1 闭合规则)
- 第二次 handler:断言 `request.headers.get('last-event-id') === '2'`,返 `id:3 + id:4`
- Hook `events` 最终有 4 条(id 1..4,按 id 升序去重)

### Q10.2 决:TC-S5-12-4 走 A4 (b) · Z-lite

**采纳 A4 (b)**:`frontend/tests/types/agent.types.test.ts` 用 `expectTypeOf`(vitest 内置)运行期校验,vitest 配置**零改动**。理由:vite.config.ts:22-27 未开 `typecheck.enabled`,方案 (a) 需扩配置增复杂度;方案 (b) 单文件 ~20 行 `expectTypeOf` 断言 = 运行期低开销、CI 有断言信号、计入 `N_before + 4` 基线。

示意:
```typescript
import { expectTypeOf } from 'vitest';
import type { SSEEvent, SSEEventType, Plan, PlanStep, AgentChatResponse, TaskStatus } from '@/types/agent';

test('SSEEventType covers 8 event types', () => {
  expectTypeOf<SSEEventType>().toEqualTypeOf<
    'thinking' | 'plan' | 'tool_call' | 'progress' | 'result' | 'error' | 'warning' | 'system'
  >();
});
test('TaskStatus covers 7 states including CANCELLED', () => {
  expectTypeOf<TaskStatus>().toEqualTypeOf<
    'PENDING' | 'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  >();
});
test('PlanStep has optional and dependencies as optional', () => {
  expectTypeOf<PlanStep>().toHaveProperty('optional').toEqualTypeOf<boolean | undefined>();
  expectTypeOf<PlanStep>().toHaveProperty('dependencies').toEqualTypeOf<string[] | undefined>();
});
// ...共 ~5 条断言,覆盖 SSEEvent 泛型、AgentChatResponse.status 3 值子集、ResultArtifact.type union
```

**表述更正**:REVISIONS A4 (b) 确认 —— TC-S5-12-4 是"运行期类型校验"(expectTypeOf 在 vitest 运行时执行断言),**非"零运行时"**,计入 `N_before + 4` 基线数。

### Q11 决 + A1 闭合:msw 断线机制

流的 `controller.close()` = server 主动关流,**hook 视为「未收终态则重连、已收终态则 closed」**(A1 闭合)。TC-S5-12-2 用"发 2 帧后 close · hook 未见终态 · 自动重连 · 断言 Last-Event-ID 头"路径。

---

## 七 · 求助边界 stop-and-ask(§十八 · 11 条)

**开工前门槛**:

1. **仓库状态偏移** —— 开工时 `master` HEAD 不是 `f75e2a9`,或工作区含 `frontend/src/**` / `frontend/tests/**` 未提交改动 → 停下汇报,不擅自 reset / 不擅自起分支。
2. **前端 test 基线丢失** —— 阶段 0 `cd frontend && npm run test` 若失败或存在既有红测(non-zero exit),先记 `N_before` 数字后停下汇报,不擅自修既有测试。

**实施中门槛**:

3. **msw v2 SSE 支持不足** —— 若 TC-S5-12-2 断线重连 msw handler 无法拦到重连的 `Last-Event-ID` 头(msw stream API 限制、jsdom fetch 实现差异等)→ 停下汇报,不擅自换 mock 框架/不擅自改 EventSource 分支。
4. **fetch stream 在 jsdom 下无法解析 `text/event-stream`** —— 若阶段 3 hook 实现完发现 jsdom 环境 fetch response body reader 无法读到流帧(nodejs undici 实现差异)→ 停下汇报,不擅自切原生 EventSource。
5. **类型对齐失败** —— 若 TC-S5-12-4 `expectTypeOf` 发现 `SSEEvent` / `Plan` 类型定义与 `backend/app/schemas/agent.py` 有字段不匹配 → 停下汇报(可能是本 DECISION §三 类型抄错或后端契约漏 export,非执行体私自修契约)。
6. **前端 test 基线倒退** —— 阶段 1..5 任一 commit 后 `npm run test` 数字 < `N_before + n`(n = 该 commit 阶段应加的用例数)→ 停下汇报。
7. **顺手扩范围** —— 若在阶段 3-4 想顺手加 PlanCard / 更新 ChatCenter.tsx / 引入 zustand slice / 改 vite.config.ts 开 typecheck 等 → **停下汇报**(违 §一 硬边界)。
8. **追债项 3 命中** —— 若发现 `ArtifactType` union 与 `backend/app/agent/orchestrator/engine.py::_ARTIFACT_TYPE_MAP` 键实际有差异(比如后端某 skill artifact type 已悄然新增)→ 停下汇报,不擅自扩 union(可能是 debt 12 修复副作用,该由 backend PR 领导对齐)。
9. **`POST /agent/chat` 契约漂移**(B4 改写) —— 手工验证 `POST /agent/chat` 时若返回结构异常(缺 `task_id` / 缺 `status` / `status` 为非预期值如小写、或返回其他非契约字段) → 停下汇报(可能后端 contract regression)。
10. **误触 backend/app**(B5 新增) —— 若阶段 3-4 任何 commit 不慎改动 `backend/app` 任意文件 → 立即 `cd backend && uv run pytest -q` 维持 **120 passed**,未跑不得提交;若红则停下汇报。
11. **重连终态判定分歧**(C3 新增,对应 A2) —— 若执行体阶段 4 实现时想按 `data.recoverable === false` 分支判定终态,或想跳过 A2 闭合规则 → **停下汇报**,不得私自扩 error 分支或加 `recoverable` 字段消费逻辑,按 §五 唯一权威规则(`type === 'result' || type === 'error'` 即终态)实现。

---

## 八 · Commit 拆分与分支

### Q17 决 + A5 闭合:5-commit TDD 结构 · 阶段 1 用 `.fails` 非 `.skip`

| # | 提交类型 | 内容 | 阶段 |
|---|---|---|---|
| 1 | `test(stage5)` | PR-18 red-test skeleton · TC-S5-12-1..4 骨架(**全 `test.fails`**,阶段 1 · A5 闭合)+ `types/agent.ts` / `services/agent.ts` / `hooks/useTaskStream.ts` 占位空文件(仅 export 骨架)| 1 |
| 2 | `feat(stage5)` | S5-12 types · `types/agent.ts` 完整落地(§三 全量)+ `types/index.ts` 追加 re-export | 2 |
| 3 | `feat(stage5)` | S5-12 services · `services/agent.ts`(§四 · agentApi 5 函数) | 2 |
| 4 | `feat(stage5)` | S5-12 useTaskStream hook · `hooks/useTaskStream.ts`(§五 · 完整 SSE 解析器 + 重连状态机) | 3 |
| 5 | `test(stage5)` | TC-S5-12-1..4 全部**移除 `.fails` 转绿**(阶段 4 · A5 闭合) | 4 |

**说明**:
- 阶段 1 骨架用 `test.fails` 而非 `.skip` —— vitest `.fails` 语义 = 「预期该测试失败,实测失败则 pass、实测成功则 fail」,提供**红→绿信号对称性**(与 PR-17 pytest xfail 对称)。阶段 5 转绿必须**移除 `.fails`**(而非改 `.skip`),否则测试实际未跑而 pass 是假绿。
- Commit 1 骨架文件(`types/agent.ts` / `services/agent.ts` / `hooks/useTaskStream.ts`)必须**至少 export 名称**以让红测试文件 import 时不报错(`export function useTaskStream(): never { throw new Error('not implemented'); }` 或 minimal 类型 stub)。

### Q18 决:分支命名

`feat/pr-18-s5-12-sse-hook`(照 AGENTS.md §4.1 `feat/pr-NN-<slug>`),从 `master@f75e2a9` 起分支。

---

## 九 · 验收三道门

### Q19 决 + B5 补充:门 1 · pytest(前端 PR 免跑,但误触 backend 强制跑)

- **默认免跑**:PR-18 只改前端(`frontend/src/**` + `frontend/tests/**`),不动 `backend/app` · pytest 应维持 **120 passed**。执行体在 STEP6 报告写明"未触碰 backend/app,pytest 基线维持 120 passed(未跑,依据未改动 pytest 覆盖范围)"。
- **反向兜底**(B5 · §十八 clause 10):若阶段 3-4 任何 commit 不慎改动 `backend/app` → 立即 `cd backend && uv run pytest -q` 必须维持 120 passed。

### Q20 决:门 2 · 前端 test 基线

- **阶段 0**:执行体首次 `cd frontend && npm run test`,记录 `N_before` 数字(0 failed 前提下)
- **交付后**:`N_before + 4`(TC-S5-12-1..4)· 0 failed
- **中间任一 commit**:数字必须 monotone non-decreasing(仅 commit 5 转绿会新增 4;commits 1-4 保持 `N_before` 因 red-tests 用 `.fails`,不计入 pass 数)

### Q21 决:门 3 · 前端 lint + build

- `cd frontend && npm run lint` → **0 errors**(warnings 允许:既有 `react-hooks/exhaustive-deps` 8 处等,不属 PR-18 范围)
- `cd frontend && npm run build` → 编译通过(不断言 bundle size)
- `tsc --noEmit` 不单跑(build 已含)

---

## 十 · 执行体行动清单

### 阶段 0 · 探勘(前置)

1. `git log --oneline master | head -3` 确认 HEAD = `f75e2a9`;若非,§十八 clause 1 触发。
2. `git status`:确认工作区对 `frontend/**` clean(既有 `backend/backend.err` / `backend/scripts/` 等 untracked 保持不动)。
3. `cd frontend && npm run test` 首次跑,记录 `N_before` 数字(下方 STEP6 报告要用);若失败或存在既有红测,§十八 clause 2 触发。
4. `git checkout -b feat/pr-18-s5-12-sse-hook`。
5. `grep -rn "useTaskStream\|agentApi" frontend/src` 应为空(前置事实核查)。

### 阶段 1 · 红测试 skeleton(commit 1)

- 新建 `frontend/src/types/agent.ts`(空 shell:`export type _placeholder = never;` 或 minimal)
- 新建 `frontend/src/services/agent.ts`(`export const agentApi = {} as any;` 或类似 stub)
- 新建 `frontend/src/hooks/useTaskStream.ts`(`export function useTaskStream(): never { throw new Error('not implemented'); }`)
- 新建 `frontend/tests/hooks/useTaskStream.test.ts`、`tests/services/agent.test.ts`、`tests/types/agent.types.test.ts`,每 TC 骨架用 `test.fails('TC-S5-12-N: ...', async () => { ... })`
- `npm run test` 应通过(`.fails` 预期失败 = pass)
- commit 1 = `test(stage5): PR-18 red-test skeleton (TC-S5-12-1..4) + agent hook/services/types scaffold`

### 阶段 2 · types + services(commits 2, 3)

- commit 2:`types/agent.ts` 完整实现 §三 全量类型 + `types/index.ts` 追加 `export * from './agent'`;`npm run test` 仍全绿(`.fails` 测试仍预期失败)
- commit 3:`services/agent.ts` 完整实现 §四 `agentApi` 5 函数;`npm run test` 仍全绿

### 阶段 3 · hook 实现(commit 4)

- commit 4:`hooks/useTaskStream.ts` 完整实现 §五 SSE 解析器 + 重连状态机 + AbortController + 心跳字段;`npm run test` 仍全绿(测试尚未从 `.fails` 转绿)

### 阶段 4 · 转绿 + 三道门(commit 5 + STEP6 报告)

- commit 5:移除 4 个 TC 的 `.fails` 标记,写完整断言(mock ReadableStream / 断线重连头 / 429 handler / expectTypeOf)。所有 4 TC 转绿。
- 门 1(pytest):**默认免跑**(未触 backend/app)。若 §十八 clause 10 触发,`cd backend && uv run pytest -q` 应 120 passed。
- 门 2(前端 test):`cd frontend && npm run test`,应 `N_before + 4` passed,0 failed。
- 门 3(前端 lint + build):`npm run lint`(0 errors)、`npm run build`(编译过)。
- 输出结果贴入 STEP6 报告 §二 "验收三道门"。

### 阶段 5 · STEP6 报告 + 推分支

- 撰写 `docs/planning/stage5/PR18-STEP6-REPORT.md`,严格套用 PR-17 STEP6 模板:一 交付概览 / 二 三道门实测 / 三 实现要点 / 四 影响面清单 / 五 §声明(必列 4 条 + observation)/ 六 §求助边界触发情况 / 七 集成测试清单 / 八 交付物与后续。
- `git push -u origin feat/pr-18-s5-12-sse-hook`
- 回报指挥官进行 FF-merge 评审。**执行体不做自动 FF-merge**。

---

## 十一 · 主指挥官承诺陈述

- **本 DECISION 是 PR-18 唯一实施契约**:执行体除 §一"允许改动"外的任何文件改动、除 §八 commit 结构外的任何提交序列、除 §十行动清单外的任何流程调整,均需按 §十八 求助边界停下汇报。
- **测试基线绝对不倒退**:`npm run test` 每阶段可持平或上升,禁止下降;`pytest` 若被触碰须维持 120 passed。
- **无声妥协禁令**:执行体阶段 3-4 若发现 §五 hook 契约在 jsdom + msw 环境下有实现障碍(比如 fetch stream reader 语义 / msw handler 无法拦断线重连头),**必须停下汇报**,不得私自切 EventSource / 加 polyfill / 引入外部库 / 加特殊分支绕过。
- **诚实报告**:阶段 4 三道门的输出必须原样贴入 STEP6 §二,禁止美化;若门 3 有 lint warning 数字变化(既有 8 处上下浮动),按 PR-17 §二 门 3 修订脚注模式如实登记原因。

---

## 十二 · FF-merge 后指挥官统一操作(供参考,不属执行体范围)

指挥官在 FF-merge 时统一操作,依据本 DECISION §十:

1. `HANDOFF.md §9.1` 状态表:PR-18 = ✅(commit hash 待填),基线 `N_before + 4` passed(前端);后端基线 120 passed 维持;master HEAD 更新到 PR-18 STEP6 tip。
2. `HANDOFF.md §9.3` 追债项:第 3 条保持开放(前端护栏落地推至 PR-19);其他项状态无变化。
3. `HANDOFF.md §9.4` 陷阱表:PR-18 起手警惕撤销(改为 PR-19 起手警惕);追加陷阱(如 PR-18 踩到新的前端 SSE 消费坑,该 PR 无预设)。
4. `HANDOFF.md §9.5` 新文件表:追加 `frontend/src/types/agent.ts` / `services/agent.ts` / `hooks/useTaskStream.ts` / `tests/hooks/*` / `tests/services/agent.test.ts` / `tests/types/agent.types.test.ts`。
5. `HANDOFF.md §9.6` 下一 PR 起手路径:改写为 PR-19(前端 ChatCenter / CandidateChat / 8 类 Card)起手指南;必读陷阱 4/5/6/8 + 追债项 3(此时前端 union 消费点上线,exhaustiveness 护栏激活)。
6. **B6 采纳**:`HANDOFF.md` §9.4 陷阱 8 内的 hash 引用从 `7810a8e` 更新为 `f75e2a9`(PR-17 整改 deferred 的 HANDOFF 更新之一,PR-18 FF-merge 一并统一)。
7. **B7 采纳**:`docs/planning/TASKS-STAGE5.md` §S5-12 「归属 PR」字段从 `PR-17` 改为 `PR-18`;§S5-13 「归属 PR」字段从 `PR-17(合入)/ PR-18(拆分)` 改为 `PR-19`(与 §9.1 表格对齐)。
8. 记忆 `stage5-progress-and-known-limits.md`:PR-18 已合;基线更新;前端 SSE Hook 基建就位;PR-19 待动工。

---

_本 DECISION 作为 `PR18-KICKOFF-QUESTIONS.md` + `PR18-KICKOFF-REVISIONS.md` 的最终裁定合并版。docs-only,依 AGENTS.md §4.1 可直推 master。_
