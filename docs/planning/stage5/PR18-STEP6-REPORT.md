# PR-18 STEP6 交付报告 · S5-12 前端类型 + SSE 客户端 Hook

> 对象:主指挥官(用户)· 用于 FF-merge 评审
> 执行体:下一 session(本 PR 实现)
> 关联:`PR18-KICKOFF-DECISION.md`(唯一实施契约)、`PR18-KICKOFF-QUESTIONS.md`、`PR18-KICKOFF-REVISIONS.md`
> 分支:`feat/pr-18-s5-12-sse-hook`(从 `master@646efad` 起)
> 合并依据:DECISION §十 行动清单(阶段 0–5)

---

## 一 · 交付概览

- **PR 编号**:PR-18 · 任务 **S5-12**(严格版)= 前端类型 + `agentApi` services + `useTaskStream` Hook + TC-S5-12-1..4。
- **范围边界**:严格对齐 TASKS §S5-12,**不含** ChatCenter / CandidateChat / 8 类 Card / zustand store(PR-19 全量)。HANDOFF §9.1「PR-18 = SSE Hook + ChatCenter」的漂移表述由 DECISION §一就地闭合。
- **base ref**:`master@646efad`(= PR-18 kickoff docs commit,是 `f75e2a9` 的下游;DECISION §〇 写的 `f75e2a9` 因中间合入 kickoff docs 而推进为 `646efad`,属 DECISION clause 1 括号已预期的「docs-only 先合入」情形;开工时用户指令明确 base = `646efad`,未触发 §十八 clause 1 停下)。
- **commit 结构**:4 个代码 commit(红色骨架 → types → services → hook)。DECISION 原定的第 5 个 commit(移除 `.fails` 转绿)因 **vitest `.fails` 严格语义**(通过即判失败,与 PR-17 pytest `xfail` 宽容语义不同)已**增量并入 commit 3/4**,详见 §五 observation。
- **改动文件**:7 个,全部 `frontend/`,无 `backend/app`(见 §四)。

---

## 二 · 验收三道门实测

| 门 | 要求 | 实测 | 结果 |
|---|---|---|---|
| **门 1 · pytest** | 未触 `backend/app` 则免跑,维持 120 passed | 本 PR 仅改 `frontend/**`;未执行 `uv run pytest`(依据 DECISION Q19 免跑 + §十八 clause 10 未触发) | ✅ 未跑,基线 120 passed 维持(依据:未改动 pytest 覆盖范围) |
| **门 2 · 前端 test** | `N_before + 4` passed,0 failed | `N_before = 16`(阶段 0 实测,6 test files)→ `N_after = 20 passed`(9 test files,0 failed) | ✅ 20 = 16 + 4 |
| **门 3 · lint + build** | `lint` 0 errors;`build` 编译过 | `eslint .` → **0 errors / 8 warnings**(基线 8 处 `react-hooks/exhaustive-deps`,无新增);`tsc -b && vite build` → **✓ built in 6.71s**(3110 modules transformed) | ✅ 双绿 |

**数字溯源**:
- 阶段 0:`cd frontend && npm run test` → `Test Files 6 passed · Tests 16 passed`。
- 阶段 4(commit 4 后):`Tests 20 passed (20)`,`0 expected fail`(4 个 TC 全部转绿)。
- lint:仅 8 个既有 `react-hooks/exhaustive-deps` warning,无 error 级、无新增 warning(2 个由本 PR 引入的可修复 warning——未用 `Plan` 导入、多余 `eslint-disable` 指令——已在 commit 4 一并修掉,使 warning 数回到基线 8)。

---

## 三 · 实现要点

### 3.1 `frontend/src/types/agent.ts`(commit 2 · 完整落地)
- 严格对齐后端 `backend/app/schemas/agent.py` + api-contract §3.2/§3.4/§4.1:
  - `SSEEventType`(8 值小写 union)、`SSEEvent<T>`(id/type/task_id/step_id?/timestamp/data)、`TaskStatus`(7 值全大写 union)、`Plan`/`PlanStep`、`AgentChatResponse`(status 3 值子集 + `initial_plan?`)、`ExecutePlan*`/`SkipToScore*`/`CancelTask*`/`TaskStatusResponse`、`ResultArtifact`/`ArtifactType`(6 值 union)。
- **union type 非 TS enum**(与 `JDStatus`/`CandidateStatus` 一致,Q5 采纳)。
- `ArtifactType` 严格 union(Q7 采纳,追债项 3 护栏延 PR-19 激活,B2)。
- `index.ts` 追加 `export * from './agent'`(不迁移既有类型,不影响既有 import,Q4 采纳)。

### 3.2 `frontend/src/services/agent.ts`(commit 3 · 完整落地)
- 仿 `candidateApi` 对象模式,`agentApi` 5 函数:`chat` / `executePlan` / `skipToScore` / `cancelTask` / `getTask`(Q9 采纳)。
- **429 不加中间层**(Q9.1):`request.ts` 拦截器已 `Promise.reject(error)`,调用方自行 `try/catch` 判 `err.response?.status === 429`。

### 3.3 `frontend/src/hooks/useTaskStream.ts`(commit 4 · 完整落地)
- **选型**:`fetch` + `ReadableStream` 手写 SSE 解析器(Q2 选项 B);URL 由 `request.defaults.baseURL` 构造(测试环境绝对地址 `http://localhost/api/v1`,生产相对 `/api/v1`),对齐 msw + fetch 测试模式。
- **重连状态机(A1 + A2 闭合)**:维护 `hasReachedTerminal`,收到 `result`/`error` 即置 true(**弃 `data.recoverable`,因后端 `SSEEvent.data` 为 Any 无该字段**);流关闭时若已终态 → `status='closed'` 不重连,否则按 **3s→6s→12s** 指数退避重连(超 3 次 `status='error'`),重连请求带 `Last-Event-ID` 头。
- **忽略 server `retry:`**(B3):后端 `_format_sse` 首帧发 `retry: 3000`,hook 解析时跳过该控制块,用自身退避。
- **心跳(Q13 + A3)**:`system` 事件更新 `latestByType.system` + `lastHeartbeatAt = Date.now()`,**不入 `events[]`**;`lastHeartbeatAt` 已补进 `UseTaskStreamResult` 返回接口(A3 采纳)。
- **容错(Q14)**:未知 `type` / `JSON.parse` 失败 → `console.warn` + 跳过,不 throw。
- **幂等(Q3.2)**:`events` 按 `id` 升序 + 去重;`latestByType` 便捷字段(Q3.1)。
- **生命周期(Q16)**:`AbortController` 管理 fetch 流,`close()` abort + 清定时器,`useEffect` cleanup 保证 unmount 时 abort。

### 3.4 后端 SSE 线格式事实发现(影响解析器构造)
- `backend/app/api/v1/agent.py:180-188` `_format_sse` **仅序列化 `id`/`event`/`data`** 三个 SSE 字段;pydantic `SSEEvent` 的 `task_id`/`step_id`/`timestamp` **不在 SSE 线格式里**(`task_id` 仅在部分事件的 `data` 内部,`timestamp` 根本不入线)。
- 因此 hook 解析时:`task_id` 用已知 `opts.taskId` 补;`timestamp` 用本地 `new Date().toISOString()`;`step_id` 从 `data.step_id` 取。类型层(TC-S5-12-4)与后端 pydantic 模型字段一致,不受影响(该事实不触发 §十八 clause 5,因类型契约本身对齐)。

---

## 四 · 影响面清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `frontend/src/types/agent.ts` | 新建 | S5-12 类型契约(§三) |
| `frontend/src/types/index.ts` | 修改 | 追加 `export * from './agent'` |
| `frontend/src/services/agent.ts` | 新建 | `agentApi` 5 函数 |
| `frontend/src/hooks/useTaskStream.ts` | 新建 | SSE Hook |
| `frontend/tests/hooks/useTaskStream.test.ts` | 新建 | TC-S5-12-1 / TC-S5-12-2 |
| `frontend/tests/services/agent.test.ts` | 新建 | TC-S5-12-3 |
| `frontend/tests/types/agent.types.test.ts` | 新建 | TC-S5-12-4 |

**未触碰**(§一 禁止项,逐一核验未违反):
- `frontend/src/pages/ChatCenter.tsx` / `CandidateChat.tsx` — 留 PR-19
- `frontend/src/components/agent/*Card.tsx` — 留 PR-19
- `frontend/src/store/` — 本 PR 不引入状态库
- `backend/app/**` — 前端 PR 零改动(门 1 免跑依据)
- `docs/api-contract.md` — 契约已固化,严格对齐未倒改
- `frontend/vite.config.ts` — 未开 `typecheck`(TC-S5-12-4 走 Z-lite)

---

## 五 · §声明(必列 4 条 + observation)

1. **未触碰 `backend/app`** —— 本 PR 仅改 `frontend/src/**` + `frontend/tests/**`;pytest 维持 **120 passed**(未跑,依据 DECISION Q19 + §十八 clause 10 未触发)。
2. **严格 S5-12 边界** —— ChatCenter / CandidateChat / 8 类 Card / zustand store 均未创建或改动,全部留 PR-19(§一 硬边界未破)。
3. **未改 `frontend/vite.config.ts`** —— 未开 `typecheck`;TC-S5-12-4 按 A4(b) Z-lite 走 `expectTypeOf` 运行期校验,计入 `N_before + 4` 基线。
4. **未倒改 `docs/api-contract.md`** —— 前端类型严格对齐既有契约,无契约变更。

**observation 1(commit 结构适配)**:DECISION 原定 5 个 commit(第 5 个移除 `.fails` 转绿)。但 **vitest `test.fails` 为严格语义**(测试通过反而判失败),与 PR-17 用的 pytest `xfail`(XPASS 宽容)不同。若保留 `.fails` 到 commit 5,则 commit 3(services 落地)/ commit 4(hook 落地)时对应 TC 会「意外通过→判失败」,破坏 DECISION §十「commits 2-4 保持全绿」的硬要求。故将 `.fails` 移除**增量并入实现落地的 commit**(TC-S5-12-3 在 commit 3 转绿移除 `.fails`;TC-S5-12-1/2 在 commit 4 转绿移除 `.fails`),最终仍为 **4 个代码 commit 全绿**,终态与 DECISION 一致。这是 vitest 工具语义下的必然适配,不偏离「红→绿」TDD 精神(commit 1 仍提供真实红信号:3 个 `.fails` 预期失败)。

**observation 2(类型测试真实价值)**:TC-S5-12-4 用 `expectTypeOf`,在 vitest 运行期是 **no-op**(真实类型校验需 `typecheck.enabled`),故它提供的是「占位 + 计数」价值而非运行期类型护栏。这正属 A4(b) Z-lite 取舍的已知代价;若未来需要真正编译期护栏,再开 `test.typecheck`(需扩 vite.config,超出本 PR 边界)。

**observation 3(取消场景的已知边界)**:后端 `_is_terminal` 将 `system:cancelled` 也视作终态并关流,但本 hook 按 A2 仅认 `result`/`error` 为终态。若任务经 `system:cancelled` 终止,hook 会因「未收到 result/error」而走非终态重连,经历 3 次退避后 `status='error'`(非 clean `'closed'`)。属 DECISION A2 未涵盖的边界,未私自扩展(§十八 clause 11 未触发);建议 PR-19 评估是否将 `system:cancelled` 纳入终态判定。

---

## 六 · §求助边界触发情况(DECISION §十八 11 条)

| # | clause | 触发? | 说明 |
|---|---|---|---|
| 1 | 仓库状态偏移(master≠f75e2a9 / 前端未提交改动) | **未触发** | master 实际 = `646efad`(f75e2a9 下游,因中间合入 PR-18 kickoff docs),属 DECISION 已预期的 docs-only 推进;用户指令明确 base=`646efad`;工作树 `frontend/**` 干净 |
| 2 | 前端 test 基线丢失 | 未触发 | `N_before=16` 正常取得,0 failed |
| 3 | msw v2 SSE 支持不足 | 未触发 | `http.get` + `ReadableStream` mock 成功拦截重连 `Last-Event-ID` 头(TC-S5-12-2 通过) |
| 4 | fetch stream 在 jsdom 无法解析 | 未触发 | 全局 `fetch`/ReadableStream 可用(undici),`reader.read()` 正常分帧 |
| 5 | 类型对齐失败 | 未触发 | TC-S5-12-4 `expectTypeOf` 运行期通过;类型契约与后端 schema 一致 |
| 6 | 前端 test 基线倒退 | 未触发 | 16 → 20,单调不减 |
| 7 | 顺手扩范围 | 未触发 | 未触碰 ChatCenter/Card/store/vite.config |
| 8 | 追债项 3 命中 | 未触发 | `ArtifactType` union 与后端 `_ARTIFACT_TYPE_MAP` 6 键一致,无新增 type |
| 9 | `POST /agent/chat` 契约漂移 | 未触发 | 未手工调端点;类型层 `AgentChatResponse.status` 3 值子集与 api-contract §4.1 一致(B4 改写后前提) |
| 10 | 误触 backend/app | 未触发 | 本 PR 零 backend 改动,pytest 按 Q19 免跑(未强制跑) |
| 11 | 重连终态判定分歧 | 未触发 | 严格按 §五 A2 规则实现(`result`/`error` 即终态,未私自加 `recoverable` 分支) |

---

## 七 · 集成测试清单(TC-S5-12-1..4 全部 ✅)

| TC | 落点 | 验证内容 | 结果 |
|---|---|---|---|
| TC-S5-12-1 | `tests/hooks/useTaskStream.test.ts` | 8 类事件解析(thinking/plan/tool_call/progress/result/error/warning/system);`system` 不入 `events[]` 但进 `latestByType` + `lastHeartbeatAt`;按 id 去重升序;`lastEventId`/`status` 正确 | ✅ pass |
| TC-S5-12-2 | `tests/hooks/useTaskStream.test.ts` | 非终态断流后自动重连;第二次连接断言请求头 `Last-Event-ID: 2`;最终 4 条事件、`status='closed'` | ✅ pass |
| TC-S5-12-3 | `tests/services/agent.test.ts` | `agentApi.chat` 遇 429 抛可捕获错误,`err.response.status === 429` | ✅ pass |
| TC-S5-12-4 | `tests/types/agent.types.test.ts` | `SSEEventType`/`TaskStatus`/`ArtifactType` union、`PlanStep.optional/dependencies`、`AgentChatResponse.status` 3 值、`ResultArtifact.type` union、`SSEEvent` 字段对齐 | ✅ pass(运行期 no-op,见 §五 obs 2) |

---

## 八 · 交付物与后续

- **commit 链**(从 `646efad` 起):
  ```
  34703a0  feat(stage5): S5-12 useTaskStream hook (SSE parser + reconnect state machine + heartbeat) + TC-S5-12-1/2 turn green
  8faccac  feat(stage5): S5-12 services - agentApi 5 functions (chat/executePlan/skipToScore/cancelTask/getTask)
  b8abab1  feat(stage5): S5-12 types - types/agent.ts (SSE/REST contract) + index re-export
  770b4c5  test(stage5): PR-18 red-test skeleton (TC-S5-12-1..4) + agent hook/services/types scaffold
  646efad  docs(stage5): PR-18 kickoff questions + revisions + decision   ← base
  ```
- **推送**:`git push -u origin feat/pr-18-s5-12-sse-hook`(待指挥官确认后执行;执行体不做自动 FF-merge)。
- **FF-merge 时指挥官统一操作**(供参考,不属执行体范围,DECISION §十二):
  1. `HANDOFF.md §9.1` 状态表:PR-18 = ✅(commit `34703a0`);前端基线 `16 → 20 passed`;后端 120 passed 维持;master HEAD 更新到 PR-18 tip `34703a0`。
  2. `HANDOFF.md §9.3` 追债项 3:保持开放(前端 union 护栏延 PR-19 卡片 switch 激活)。
  3. `HANDOFF.md §9.4` 陷阱表:PR-18 起手警惕撤销(改 PR-19 起手);**陷阱 8 内 hash 应更新为 `646efad`**(注:B6 原写 `f75e2a9`,但 PR-18 实际起手 HEAD 已推进为 `646efad`,须同步顺延)。
  4. `HANDOFF.md §9.5` 新文件表:追加 `frontend/src/types/agent.ts` / `services/agent.ts` / `hooks/useTaskStream.ts` / `tests/hooks/*` / `tests/services/agent.test.ts` / `tests/types/agent.types.test.ts`。
  5. `HANDOFF.md §9.6` 改写为 PR-19(ChatCenter / CandidateChat / 8 类 Card)起手指南,必读陷阱 4/5/6/8 + 追债项 3(此时前端 union 消费点上线,exhaustiveness 护栏激活)。
  6. `TASKS-STAGE5.md §S5-12` owner → PR-18;§S5-13 owner → PR-19(B7)。
  7. 记忆 `stage5-progress-and-known-limits.md`:PR-18 已合;前端 SSE Hook 基建就位;PR-19 待动工。

**一处需指挥官知晓的取舍**:DECISION §〇 写 `f75e2a9` 为起手 HEAD,实际开工 master = `646efad`(kickoff docs 合入推进)。本执行体以用户指令的 `646efad` 为 base,未触发 clause 1 停下;FF-merge 时 HANDOFF 相关 hash(B6)应记为 `646efad` 而非 `f75e2a9`。
