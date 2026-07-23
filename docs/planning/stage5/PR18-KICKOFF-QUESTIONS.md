# PR-18 KICKOFF QUESTIONS · S5-12 前端类型 + SSE 客户端 Hook

> **对象**:主指挥官(用户)裁定
> **文档角色**:指挥官(Claude Code, ark-code-latest)向用户提问,收集口径后出 `PR18-KICKOFF-DECISION.md`
> **权威依据**:
> - `docs/planning/TASKS-STAGE5.md §S5-12`(线号 254-266)
> - `docs/api-contract.md §3.1–§3.5 / §4.1–§4.5`(SSE 信封 / 事件类型 / 重放心跳 / REST 六端点)
> - `HANDOFF.md §9.4 陷阱 4/5/6/8/9`(PR-14/17 已落定的前端消费约束)
> - `docs/planning/PLAN-STAGE5.md §Q5–§Q7`(SSE 事件对齐、心跳、Redis 缓冲)
> **起手 master HEAD**:`f75e2a9`(§9 refresh · 内容合并了 `7810a8e` STEP6 状态)
> **测试基线**:后端 **120 passed** / 前端 lint 0 / 前端 test 现有基线待跑一次核算

---

## 〇 · PR 范围与 PR-19 拆分口径(阻断级前置)

### 事实

- **TASKS §S5-12** 只交付"类型 + services + useTaskStream Hook"(3 类文件),**测试用例 TC-S5-12-1..4**(4 个 · hook 端到端解析 8 类事件 / Last-Event-ID 重连 / chat 429 / 类型对齐 schema)
- **TASKS §S5-13** 交付 `ChatCenter.tsx` + `CandidateChat.tsx` + `components/agent/*Card.tsx` × 8,**测试用例 TC-S5-13-1..9**(9 个 · 含 CANCELLED / 断线重连无重复 / skip-to-score 快捷 等 UI 集成)
- **HANDOFF §9.1 当前表述**:PR-18 = "前端类型 + SSE Hook + **ChatCenter**",PR-19 = "**若拆分**,前端 CandidateChat"—— 这是 PR-16/17 kickoff 阶段的历史口径漂移(把 S5-12 + S5-13 部分合并给 PR-18)。
- **陷阱**:如果 PR-18 尝试打包 ChatCenter,单 PR 交付量 = 3 (Hook) + ~8 (Cards) + ChatCenter + 4 + 9 = 13 用例 · > 12 用例先例(PR-14 = 6 用例)。风险:大 PR 难以评审、rebase 成本高、卡壳时无最小可用增量。

### Q1 · PR-18 边界口径

**建议方案 A(推荐)**:PR-18 严格对齐 TASKS §S5-12 = **types + services + useTaskStream Hook + 4 用例**,**不含 ChatCenter / 任何 Card 组件**;PR-19 = TASKS §S5-13 全量 = ChatCenter + CandidateChat + 8 Card + 9 用例。
  - **优点**:PR 粒度可控(≤5 文件 + 4 tests),对应 TASKS 唯一事实源,交付节奏干净
  - **代价**:PR-18 后端 chat/stream 与前端 hook 无端到端 UI 联调,只能靠单元 + msw mock;真联调延迟到 PR-19
  - **验收边界**:hook 返回值签名、8 类事件解析、chat 429 抛错、Last-Event-ID 重连语义 —— 全在测试内验证,不铺 UI

**方案 B**:PR-18 = types + services + Hook + **最小骨架 ChatCenter**(仅消息框 + PlanCard 一个),PR-19 补齐剩余 7 Card + CandidateChat + skip-to-score 快捷入口。
  - **优点**:PR-18 有可跑 UI 演示;PR-19 仍是纯 UI 补齐
  - **代价**:PR-18 用例增至 ~7(4 hook + 2-3 ChatCenter 骨架 + PlanCard 单测),TASKS S5-12 边界破;测试路径需混 hook 单测 + msw 集成 UI,复杂度上一档

**方案 C**:合并 S5-12 + S5-13 为单大 PR-18(即照 HANDOFF §9.1 现表述),PR-19 = 空(取消)。
  - **优点**:一次交付完整前端对话链路
  - **代价**:13 用例、~20 文件、Card 8 个 + ChatCenter + CandidateChat + 3 Hook 文件,单 PR 太大;若中途 kickoff 有一 Q 卡壳,整块延后

**指挥官倾向**:方案 A · 严格 S5-12,把 UI 留 PR-19。理由:TASKS 是权威事实源,HANDOFF 表述是历史漂移不应反过来牵制;S5-12 有独立的 4 个 hook 测试用例,足以证明基建正确;后端 PR-14/17 已提供完整 SSE 事件流,PR-19 加 UI 时不会踩后端阻塞。

**待裁定**:方案 A / B / C(A 推荐)

---

## 一 · 技术选型硬性问题

### Q2 · SSE 客户端实现方式(**阻断级**)

**事实**:api-contract §3.5 规定:

> 客户端断线后以 HTTP 请求头 `Last-Event-ID: <last_id>` 重新连接 `/stream` 端点。

**W3C EventSource spec**:`new EventSource(url)` **不允许**为请求带自定义 HTTP header(`Last-Event-ID` 是浏览器**自动**处理的头,浏览器会在断线自动重连时基于最后一次收到的 `id:` 字段自动填 `Last-Event-ID`,**开发者无法手动控制**该头的值,也无法在初次连接时带自定义 `Authorization` / `X-*` 等头)。

**这里出现契约与技术选型的实际张力**:

- **选项 A** · **原生 `EventSource`** —— 完全依赖浏览器自动重连 + 自动 `Last-Event-ID`。
  - **优点**:MDN 推荐、浏览器原生支持自动重连、`retry:3000` 字段自动生效、代码最少
  - **代价**:
    - 无法设置 `Authorization` 头(现阶段无鉴权,可暂时接受;但未来接入登录后**要么改传 cookie / query param,要么全换 fetch stream**)
    - 无法在初次连接主动带 `Last-Event-ID`(比如页面刷新后 hook 想从 localStorage 恢复上次断点)—— 这是 §3.5 "无该头则全量重放缓冲"路径,可接受
    - MSW 对 EventSource 的模拟:msw v2 支持 SSE mock,但需要用 `HttpResponse` 返回 ReadableStream + `text/event-stream` MIME
- **选项 B** · **`fetch` + `ReadableStream` 手写 SSE 解析器** —— 自行按 `\n\n` 分帧、维护 `lastEventId` 变量、断线时用 `fetch(url, {headers:{'Last-Event-ID': lastEventId}})` 重连
  - **优点**:完全控制头、可主动 resume(初次连接带 `Last-Event-ID`)、方便加 `Authorization`
  - **代价**:自行实现分帧、自行实现重连退避、自行处理 `retry:` 指令、代码量约 100-150 行 hook 内部 `parseSseFrame` 工具
  - **测试成本**:msw mock ReadableStream 更常见(大部分示例都是 fetch-based),但 hook 单测复杂度高
- **选项 C** · 第三方库 `@microsoft/fetch-event-source`(约 15KB gzip)
  - **优点**:兼原生易用性 + 自定义头能力
  - **代价**:引入外部依赖;项目内目前无该库

**测试维度追加事实**:TC-S5-12-2 明确写"模拟断线后重连请求头带 `Last-Event-ID`(msw mock)"—— **选项 A EventSource 下,该断言极难做**:浏览器自动重连的 `Last-Event-ID` 是浏览器行为,msw 是否能拦到取决于 msw 的 SSE 支持深度;jsdom 环境下 EventSource 通常需要 polyfill(`eventsource` npm package)。选项 B fetch-based 则天然可拦。

**指挥官倾向**:**选项 B · fetch + ReadableStream 手写解析器**。理由:
1. TC-S5-12-2 断言"重连请求头带 `Last-Event-ID`"是白纸黑字的验收标准,选项 A 下测不了
2. 未来登录鉴权几乎必然需要自定义头,晚换不如早换
3. 后端 PR-14 已按标准 SSE 分帧输出(`event:\ndata:\nid:\n\n`),前端手写解析器 100 行足够
4. `frontend/tests/services/match.test.ts` 已确立 msw + fetch adapter 的测试模式,fetch-based hook 天然对齐

**待裁定**:选项 A / B / C(B 推荐)

### Q3 · Hook 签名与状态形状

**建议签名**(基于选项 B):

```typescript
interface UseTaskStreamOptions {
  taskId: string;
  autoStart?: boolean;              // 默认 true,mount 时立即连
  lastEventId?: string;             // 首次连接的断点(可选,支持页面刷新后从 localStorage 恢复)
  onEvent?: (event: SSEEvent) => void;  // 事件监听副作用钩子(比如打点)
  onError?: (err: SSEError) => void;
}

interface UseTaskStreamResult {
  events: SSEEvent[];               // 全量事件列表(按 id 升序)
  lastEventId: string | null;
  status: 'idle' | 'connecting' | 'streaming' | 'closed' | 'error';
  latestByType: Record<SSEEventType, SSEEvent | null>;  // 便捷访问:latestByType.plan / latestByType.result
  reconnect: () => void;            // 手动重连
  close: () => void;                // 主动关闭
}

function useTaskStream(opts: UseTaskStreamOptions): UseTaskStreamResult
```

**关键问题**:

- **Q3.1** · 是否需要 `latestByType` 便捷字段?或者只暴露 `events[]` 让页面自己遍历?
  - 建议**保留** —— PlanCard / ResultCard / ErrorCard 都是"只关心该类型的最新一条",页面每次遍历筛选是重复计算(useMemo 也繁琐)。
- **Q3.2** · `events` 数组是否要**基于 `id` 去重**?
  - 建议**是** —— Last-Event-ID 重连时后端从 `id > lastEventId` 重放,理论上不会重发已收到的;但双端时钟或并发窗口极端场景可能重发,前端幂等按 `id` 去重更稳。
- **Q3.3** · 是否要把 `lastEventId` 持久化到 `localStorage`?
  - 建议**否**(本 PR)—— TASKS §S5-12 只要求"断线自动带 `Last-Event-ID` 重连",不含跨页面刷新恢复;后者是 §S5-13 的 UX 决策。若采纳,可作为 Q3 子问题裁定单独增强。

**指挥官倾向**:全部 Q3.1/3.2 采纳,Q3.3 留 PR-19。

**待裁定**:Q3.1 保留 / 不保留;Q3.2 是 / 否;Q3.3 是 / 否

---

## 二 · 前端类型契约对齐

### Q4 · types 文件组织

**事实**:现有 `frontend/src/types/index.ts` 是单文件,已有 JD / Resume / Candidate / Match / Pagination 类型混住。TASKS §S5-12 明确指向 `frontend/src/types/agent.ts`(新文件)。

**建议方案 A(推荐)**:新建 `frontend/src/types/agent.ts`,从 `types/index.ts` **仅** re-export(不迁移已有类型)。
- 优点:符合 TASKS 事实源;不动既有代码 import;新代码 `import { SSEEvent } from '@/types/agent'` 语义清晰
- 代价:多一个文件

**方案 B**:全部塞 `types/index.ts`。
- 优点:import 无变化
- 代价:与 TASKS 事实源不符;`index.ts` 越来越臃肿

**待裁定**:A / B(A 推荐)

### Q5 · 后端 enum 大小写对齐

**事实**:

- `backend/app/schemas/agent.py::SSEEventType`(StrEnum):
  - `THINKING="thinking"` / `PLAN="plan"` / `TOOL_CALL="tool_call"` / `PROGRESS="progress"` / `RESULT="result"` / `ERROR="error"` / `WARNING="warning"` / `SYSTEM="system"`
  - **wire 值全小写**
- `backend/app/agent/orchestrator/state_machine.py::TaskStatus`:
  - `PENDING / PLANNING / WAITING_CONFIRMATION / EXECUTING / COMPLETED / FAILED / CANCELLED`(全大写,值也是全大写字符串)

**建议**:
- 前端 `SSEEventType` 类型 = `'thinking' | 'plan' | 'tool_call' | 'progress' | 'result' | 'error' | 'warning' | 'system'`(小写字符串联合)
- 前端 `TaskStatus` 类型 = `'PENDING' | 'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'`(全大写字符串联合)
- **不引入 TypeScript enum**(TS 官方推荐 union type over enum,与项目内既有 `JDStatus` / `CandidateStatus` 保持一致)

**待裁定**:全部采纳 / 有例外

### Q6 · Plan / PlanStep 字段对齐

**事实**:api-contract §3.4 与 `backend/app/schemas/agent.py` 一致:

```typescript
interface PlanStep {
  step_id: string;
  description: string;
  tool_name: string;
  params: Record<string, any>;
  expected_output: string;
  optional?: boolean;             // 默认 false
  dependencies?: string[];        // 默认 []
  estimated_duration_seconds?: number;
}

interface Plan {
  task_id: string;
  steps: PlanStep[];
  reasoning?: string;
}
```

**建议**:字段类型逐字段严格对齐,`optional` 前端类型标 `optional?: boolean`,`estimated_duration_seconds` 标 `?: number`。

**待裁定**:采纳/有例外

### Q7 · Result Artifact 类型定义(与追债项 3 关联)

**事实**:
- 后端 `backend/app/agent/orchestrator/engine.py::_ARTIFACT_TYPE_MAP` 现覆盖 6 类:`jd / resume / match_score / candidate_merge / candidate_profile / generic`(其他 fallback 到 `generic`)
- 追债项 3(§9.3):前后端手动同步,新增 type 忘同步则走 `generic`
- api-contract §3.3 `result` 事件 `data` 仅约束 `{ content: string; artifacts?: any[] }`,**未固化 artifact 结构**
- 后端实际 artifact schema(PR-13 固化):`{step_id: str, tool_name: str, type: str, ref_id?: str, data?: any}`(见 HANDOFF §9.4 陷阱 3)

**建议方案 A(推荐 · 保守)**:前端 `types/agent.ts` 定义:

```typescript
type ArtifactType = 'jd' | 'resume' | 'match_score' | 'candidate_merge' | 'candidate_profile' | 'generic';

interface ResultArtifact {
  step_id: string;
  tool_name: string;
  type: ArtifactType;
  ref_id?: string;
  data?: unknown;              // 各 type 具体形状留给 PR-19 渲染器 switch
}

interface ResultData {
  content: string;
  artifacts?: ResultArtifact[];
}
```

- 优点:类型对齐后端 schema · `ArtifactType` union 匹配 `_ARTIFACT_TYPE_MAP` 键
- 代价:追债项 3 仍未消除 · 新增 type 时必须**同步改前端** union + `_ARTIFACT_TYPE_MAP` + PR-19 卡片 switch(HANDOFF §9.4 陷阱 8 已警告)

**方案 B**:`type: string`(不限定 union)—— 削弱前端类型安全但不受追债项 3 影响。

**指挥官倾向**:方案 A · 前端严格 union · 让 TS 编译器帮监视追债项 3 漂移(新增后端 type 时前端 union 里缺少,会在 PR-19 卡片 switch 里触发 exhaustiveness error,反而是保底护栏)。

**待裁定**:A / B(A 推荐)

### Q8 · REST 请求 / 响应类型

**建议**:严格照 api-contract §4.1–§4.5 定义:

```typescript
interface AgentChatRequest {
  message: string;
  context?: { jd_id?: string; candidate_ids?: string[] };
}

interface AgentChatResponse {
  task_id: string;
  status: 'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING';
  initial_plan?: Plan;    // PR-14 起后端不填,前端类型保留 optional
}

interface ExecutePlanRequest {
  task_id: string;
  accepted_steps?: string[];
  modifications?: { step_id: string; modified_params?: Record<string, any> }[];
}

interface SkipToScoreRequest {
  jd_id: string;
  candidate_ids: string[];
}

interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  current_step?: string;
  plan?: Plan;
  result?: unknown;
  error?: { code: string; message: string };
  created_at: string;
  updated_at: string;
}
```

**待裁定**:全部采纳 / 有例外

---

## 三 · services 层

### Q9 · agent.ts 服务函数签名

**建议**:仿 `frontend/src/services/candidate.ts` 的 `candidateApi` 对象模式,新建 `frontend/src/services/agent.ts`:

```typescript
import request from '@/utils/request';
import type {
  AgentChatRequest, AgentChatResponse,
  ExecutePlanRequest, SkipToScoreRequest,
  TaskStatusResponse,
} from '@/types/agent';

export const agentApi = {
  chat(data: AgentChatRequest): Promise<AgentChatResponse> {
    return request.post('/agent/chat', data);
  },
  executePlan(data: ExecutePlanRequest): Promise<{ task_id: string; status: 'EXECUTING' }> {
    return request.post('/agent/execute-plan', data);
  },
  skipToScore(data: SkipToScoreRequest): Promise<{ task_id: string; status: 'EXECUTING' }> {
    return request.post('/agent/skip-to-score', data);
  },
  cancelTask(taskId: string): Promise<{ task_id: string; status: 'CANCELLED' }> {
    return request.post(`/agent/tasks/${taskId}/cancel`);
  },
  getTask(taskId: string): Promise<TaskStatusResponse> {
    return request.get(`/agent/tasks/${taskId}`);
  },
};
```

**Q9.1** · 是否需要 `chat()` 主动检测 429 并抛可捕获错误?
- **建议**:不需要额外处理 —— `request.ts` 已在 `interceptors.response.use` error 分支打印 `[API Error]`;`request.post` 在 429 时会 reject Promise,调用方 `try/catch` 或 `.catch(err => err.response?.status === 429)`。TC-S5-12-3 断言"429 时抛出可捕获错误"—— 让调用方自己判断即可,无须在 `agent.ts` 加中间层。

**待裁定**:签名采纳 / Q9.1 不加中间层是 / 加(如加,写明是抛自定义 class `AgentChatError` 还是仅保原生 axios error)

---

## 四 · 测试策略

### Q10 · vitest 测试文件位置与 msw 拦截器

**事实**:项目内已有 `frontend/tests/services/match.test.ts` 用 `server.use(http.post(...))` 模式;`tests/setup.ts` 已启 msw + 强制 `request.defaults.adapter = 'fetch'`。

**建议 TC 落点**:

| TC | 类型 | 位置 |
|---|---|---|
| TC-S5-12-1 (8 类事件解析) | Hook 单测 | `frontend/tests/hooks/useTaskStream.test.ts`(新建 `tests/hooks/` 目录) |
| TC-S5-12-2 (Last-Event-ID 重连) | Hook 集成 | 同上 |
| TC-S5-12-3 (chat 429 处理) | Service 单测 | `frontend/tests/services/agent.test.ts`(新建) |
| TC-S5-12-4 (类型对齐 schema) | 编译期 + 单测 | `frontend/tests/types/agent.types.test.ts`(编译期通过 + runtime schema JSON snapshot) |

**Q10.1** · SSE mock 具体做法(依赖 Q2 决定):
- 若 Q2 = B(fetch-based):msw `http.get('...stream', ({request}) => { const stream = new ReadableStream({start(ctrl){ ctrl.enqueue(new TextEncoder().encode('id:1\nevent:thinking\ndata:{"content":"..."}\n\n')); ...}}); return new HttpResponse(stream, {headers:{'content-type':'text/event-stream'}}); })`
  - TC-S5-12-2 断线重连:第一次 mock 返半流(2 帧),然后 hook `reconnect()`;第二次 mock 在 handler 内断言 `request.headers.get('last-event-id') === '2'`,返 `id:3`+`id:4`
- 若 Q2 = A(EventSource):需装 `eventsource` polyfill(jsdom 没有);msw 是否能拦是未知项,若不能须换 mock 策略(比如 stub 全局 `globalThis.EventSource = class MockES { ... }`)

**Q10.2** · TC-S5-12-4 "类型对齐 schema" 怎么写?
- **方案 X**:仅编译期(types-only tests · `expectTypeOf` 或 tsd)——`SSEEvent<T>` 与 `SSEEventType` 联合值全覆盖
- **方案 Y**:runtime schema · JSON.parse 一个真实 mock event 后 asserts 结构
- **方案 Z**:X + Y 都做

**指挥官倾向**:Q10.1 = B 分支(依 Q2 = B);Q10.2 = X(仅编译期,零运行时开销;runtime 由 TC-S5-12-1 覆盖了)

**待裁定**:Q10.1(依 Q2);Q10.2 X/Y/Z

### Q11 · 副作用担保 · TC-S5-12-2 msw 断线机制

**风险**:msw v2 的 ReadableStream 支持 —— 若在流中间 `controller.close()`,axios/fetch 侧看到的是"流正常结束",不是"断线错误"。要模拟"网络断线"(真触发 `EventSource.onerror` 或 fetch stream `TypeError`),需要用 `controller.error(new Error('...'))` 或 handler 直接 `throw`。

**建议**:hook 内部把"流正常结束(server 主动关闭)"与"断线"**都当断线处理**触发重连 —— 更简单且与 EventSource 默认行为一致。TC-S5-12-2 就用"流正常结束 + reconnect() 手动触发"来验证 Last-Event-ID 逻辑。

**待裁定**:采纳(流结束 = 触发重连)/ 拒绝(必须区分正常关流和错误关流)

---

## 五 · SSE 生命周期细节

### Q12 · 何时触发重连?

**触发点**:
- 流被服务端主动关闭(RESULT / ERROR 终态事件后端会 close 连接) —— **不应重连**(任务已终态)
- 流被网络中断(fetch abort / TypeError) —— **应重连**
- 页面刷新 —— 无从判定,取决于是否 persist `lastEventId` 到 storage(Q3.3 已裁 · 本 PR 不做)

**判定规则建议**:
- Hook 内维护 `hasReachedTerminal` 标记 —— 当收到 `type === 'result' || type === 'error' && data.recoverable === false` 时置 true
- 流关闭时检查该标记,true → `status='closed'`,不重连;false → 走重连流程
- 重连指数退避:第 1 次 3000ms(遵 api-contract §3.5 `retry:3000`)、第 2 次 6000ms、第 3 次 12000ms,超 3 次给 `status='error'`

**待裁定**:采纳全部 / 有例外

### Q13 · 15s 心跳 `system` 事件的前端处理

**事实**:后端 PR-14 每 15s 发一条 `{type:'system', data:{message:'heartbeat'}}`,不入 EventBuffer。

**建议**:
- Hook 接收 `system` 事件,更新 `latestByType.system`,但**不入 `events[]` 数组**(否则 UI 层展示历史时会有一堆心跳污染)
- 提供便捷字段 `lastHeartbeatAt: number | null`(时间戳,ms)供 UI 层判定"心跳丢失"(比如 30s 内未收到心跳 = 疑似断线 · PR-19 UX 决策)

**待裁定**:采纳 / 心跳也入 events[]

### Q14 · 事件解析容错

**风险**:后端某天新增事件类型(如 `stage_start` · 未在 §3.3 表内),前端 SSEEventType union 不识别,直接 throw 会导致整个 hook 崩溃。

**建议**:
- Hook 解析器遇到未识别 `type` 时 `console.warn('unknown SSE event type: ...')` + 跳过入 `events[]`,不 throw
- 若 `data` 无法 `JSON.parse`,同样 warn + 跳过

**待裁定**:采纳容错策略 / 严格 throw

---

## 六 · Store 与页面级集成边界(为 PR-19 预留)

### Q15 · 是否引入 Redux/Zustand 存对话状态?

**事实**:项目内已有 `frontend/src/store/`(粗看结构未细读)。TASKS §S5-12 目标只到"hook",未提 store。

**建议方案 A(推荐)**:PR-18 **不引入** store · hook 内 state 就够(每个 ChatCenter 实例 mount 时新建 hook,unmount 时 close 流)。若 PR-19 需要跨路由持久化,再引入。

**方案 B**:PR-18 顺手加 zustand slice(`useChatStore`)持久化 events / task_id 到内存单例。

**待裁定**:A / B(A 推荐)

### Q16 · CancelToken / AbortController

**建议**:Hook 内用 `AbortController` 管理 fetch stream 生命周期;`close()` 触发 `controller.abort()`;React `useEffect` cleanup 保证 unmount 时必 abort,避免 memory leak。

**待裁定**:采纳(默认)

---

## 七 · commit 拆分与 PR 结构

### Q17 · TDD 红→绿分几个 commit?

**建议**(参考 PR-17 5-commit 结构):

| # | 提交类型 | 内容 |
|---|---|---|
| 1 | `test(stage5)` | PR-18 red-test skeleton · TC-S5-12-1..4 骨架(全 xfail / skip) + 新建 `types/agent.ts` 占位 |
| 2 | `feat(stage5)` | S5-12 types · `types/agent.ts` 完整落地(Q4/5/6/7/8 采纳的类型) |
| 3 | `feat(stage5)` | S5-12 services · `services/agent.ts`(5 个函数,Q9) |
| 4 | `feat(stage5)` | S5-12 useTaskStream hook · `hooks/useTaskStream.ts`(SSE 解析器 + 状态机 + 重连) |
| 5 | `test(stage5)` | TC-S5-12-1..4 全部转绿(hook 事件解析 + Last-Event-ID + 429 + 类型对齐) |

**Q17.1** · 5 commit 还是 4 commit(把 2/3 合并)?
- 建议 5 —— 更细粒度,便于评审;每步都可独立回滚

**待裁定**:5 / 4 / 其他

### Q18 · 分支命名

**建议**:`feat/pr-18-s5-12-sse-hook`(照 AGENTS.md §4.1 · `feat/pr-NN-<slug>`)

**待裁定**:采纳 / 其他 slug

---

## 八 · 验收三道门

### Q19 · 门 1 · pytest 基线维持

**事实**:PR-18 只改前端,不动 backend/app · pytest 应保持 **120 passed** 无变化。

**建议**:执行体不必跑 pytest(前端 PR 免除),但需在 STEP6 报告写明"未触碰 backend/app,pytest 基线维持 120 passed(未跑,依据未改动 pytest 覆盖范围)"。

**待裁定**:采纳(不跑)/ 必须跑一次留证据

### Q20 · 门 2 · 前端 test 基线

**事实**:当前 `frontend` 侧测试数目未跑过统计。TASKS 期望 PR-18 + 4 用例(TC-S5-12-1..4)。

**建议**:
- 阶段 0 · 执行体先跑 `cd frontend && npm run test` 得基线数字 `N_before`
- 交付后须 = `N_before + 4`(0 failed)

**待裁定**:采纳

### Q21 · 门 3 · 前端 lint + build

**建议**:
- `cd frontend && npm run lint` → 0 errors(warnings 允许 · 现有 `react-hooks/exhaustive-deps` warning 是既有 8 处,不属 PR-18 范围)
- `cd frontend && npm run build` → 编译通过(不断言 bundle size)
- **不检查** `tsc --noEmit`(build 已包含)

**待裁定**:采纳

---

## 九 · §求助边界 · stop-and-ask

**建议 §求助边界 clauses**(参照 PR-17 §十八):

1. **仓库状态偏移** —— 若开工时 master HEAD 不是 `f75e2a9` 或工作区含前端 `frontend/src/**` 未提交改动 → **停下汇报**
2. **msw v2 SSE 支持不足** —— 若 TC-S5-12-2 断线重连 mock 无法实现(msw stream API 限制或 jsdom 环境限制) → **停下汇报,不擅自换 mock 框架**
3. **Q2 决策后发现 EventSource + polyfill 组合在 jsdom 下无法 mock** —— 如指挥官选了 A,执行体阶段 3 实现时发现不可行 → 停下汇报,不擅自切 B
4. **类型对齐失败** —— 若 TC-S5-12-4 编译期检查发现 `SSEEvent` / `Plan` 与后端 pydantic schema 有字段不匹配 → 停下汇报(可能是后端契约漏了 export,不是前端职责)
5. **前端 test 基线倒退** —— `N_before` 到交付后中间任一 commit 出现 pytest-frontend 数字下降(既有测试因新代码破坏) → 停下汇报
6. **顺手扩范围** —— 若在阶段 3-4 想顺手加 PlanCard / ChatCenter 更新以"演示 hook 能用" → **停下汇报**(违 Q1 方案 A 硬边界,应留给 PR-19)
7. **追债项 3 命中** —— 若前端 `ArtifactType` union 与后端 `_ARTIFACT_TYPE_MAP` 键实际不一致(比如后端某 skill artifact type 已经悄悄新增) → 停下汇报,不擅自扩 union
8. **cancel/execute 端点契约漂移** —— 若发现 `POST /agent/execute-plan` 或 `/cancel` 返回的字段与 api-contract §4.2/§4.5 不符 → 停下汇报
9. **PR-14 陷阱 4 前置失效** —— 若手工调 `POST /agent/chat` 发现 `initial_plan` 又开始返值(理论上 PR-14 后不填) → 停下汇报(可能后端有 regression)

---

## 十 · 附:执行体行动清单预览(供你判定粒度是否合适)

预定 DECISION 会写成 5 阶段:

- **阶段 0 · 探勘** · 跑一次 `npm run test` 得 `N_before`;grep 确认无 `useTaskStream` / `agentApi` 既有实现
- **阶段 1 · 红测试** · commit 1 · 4 用例骨架(全 skip)+ `types/agent.ts` 空文件
- **阶段 2 · 类型 + services** · commit 2 + 3 · `types/agent.ts` 完整 + `services/agent.ts` 完整
- **阶段 3 · Hook 实现** · commit 4 · `hooks/useTaskStream.ts` 完整
- **阶段 4 · 转绿 + 三道门** · commit 5 · TC 全部转绿 · 三道门(pytest 免跑 · npm test / lint / build 全绿)· 报告

**待裁定**:粒度采纳 / 需调整

---

## 附录:待裁定项汇总(供你逐项勾选或简答)

| # | 主题 | 选项 | 指挥官倾向 | 你的裁定 |
|---|---|---|---|---|
| Q1 | PR 边界 | A(纯 S5-12)/ B(+骨架)/ C(合并) | A | |
| Q2 | SSE 实现 | A(EventSource)/ B(fetch)/ C(第三方) | B | |
| Q3.1 | latestByType 便捷字段 | 保留 / 不保留 | 保留 | |
| Q3.2 | 事件按 id 去重 | 是 / 否 | 是 | |
| Q3.3 | lastEventId 持久化 localStorage | 本 PR / 留 PR-19 | 留 PR-19 | |
| Q4 | types 组织 | A(新 agent.ts)/ B(塞 index.ts) | A | |
| Q5 | enum 大小写 | 采纳 union / 有例外 | 采纳 | |
| Q6 | PlanStep 字段 | 逐字段严格对齐 | 采纳 | |
| Q7 | Artifact 类型 | A(严格 union)/ B(string) | A | |
| Q8 | REST 请求响应类型 | 逐字段对齐 | 采纳 | |
| Q9 | agent.ts 签名 | 采纳 / 微调 | 采纳 | |
| Q9.1 | 429 处理 | 不加中间层 / 抛自定义 error | 不加 | |
| Q10 | 测试落点 | tests/hooks + tests/services + tests/types | 采纳 | |
| Q10.1 | SSE mock 方式 | 依 Q2 = B → ReadableStream | 采纳 | |
| Q10.2 | TC-S5-12-4 类型 | X(编译期)/ Y(runtime)/ Z | X | |
| Q11 | msw 断线机制 | 流关 = 触发重连 / 严格区分 | 流关触发 | |
| Q12 | 重连触发规则 | 采纳建议 / 有例外 | 采纳 | |
| Q13 | system 心跳处理 | 不入 events[] · 单独字段 / 入 events[] | 不入 | |
| Q14 | 事件解析容错 | warn + skip / 严格 throw | warn + skip | |
| Q15 | 引入 store | A(不引)/ B(zustand) | A | |
| Q16 | AbortController | 采纳 | 采纳 | |
| Q17 | commit 拆分 | 5 / 4 / 其他 | 5 | |
| Q17.1 | commit 2/3 是否合并 | 拆(5) / 合(4) | 拆 | |
| Q18 | 分支命名 | `feat/pr-18-s5-12-sse-hook` | 采纳 | |
| Q19 | pytest 免跑 | 采纳 / 必须跑 | 采纳(免跑) | |
| Q20 | 前端 test 基线 | 阶段 0 得 N_before + 4 | 采纳 | |
| Q21 | 前端 lint + build | 采纳 | 采纳 | |
| §求助 | 9 clauses | 采纳 / 调整 | 采纳 | |

---

**下一步**:请就上表逐项裁定(可用一句话回复"全部采纳指挥官倾向"或按 Q# 逐条说异见)。裁定后我出 `PR18-KICKOFF-DECISION.md`,依 AGENTS.md §4.1 docs-only 可直推 master(或与 PR18-KICKOFF-QUESTIONS 三件套一并直推)。
