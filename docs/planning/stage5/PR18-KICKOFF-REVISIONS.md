# PR-18 KICKOFF-QUESTIONS · 修订建议清单（供指挥官裁定）

> 关联：`docs/planning/stage5/PR18-KICKOFF-QUESTIONS.md`（初稿，2026-07-23）
> 目的：在出 `PR18-KICKOFF-DECISION.md` 前，先把评估中发现的 **事实矛盾 / 契约缺口 / 文档一致性冲突** 列项，交由指挥官逐项裁定。裁定后并入 DECISION。
> 说明：本文件只列修订建议，**不进 commit**（随 DECISION 一并走 docs-only 直推或本分支）。
> 核验依据（实测事实源）：
> - 后端 `backend/app/schemas/agent.py`（SSEEvent / SSEEventType / TaskStatus 定义）
> - 后端 `backend/app/agent/orchestrator/state_machine.py`（TaskStatus 全大写）
> - 后端 `backend/app/agent/orchestrator/engine.py::_ARTIFACT_TYPE_MAP`（`engine.py:50-56`，5 键 + generic）
> - 后端 `backend/app/api/v1/agent.py:87,97`（`POST /agent/chat` 返裸 dict `{task_id, status:"PLANNING"}`，未用 `AgentChatResponse` pydantic 模型）
> - 前端 `frontend/vite.config.ts:22-27`（vitest `test` 配置未开 `typecheck.enabled`）
> - 前端 `frontend/src/utils/request.ts`（拦截器已打印 `[API Error]` 并 reject）
> - 前端 `frontend/src/store/`（目录已存在，确认 Q15 事实）

---

## A 类 · 阻断级事实修正（出 DECISION 前必须改）

### A1 · Q11 与 Q12 直接矛盾（关流处置二义）

- **现状（初稿）**：
  - `PR18-KICKOFF-QUESTIONS.md:333`（Q11 建议）：「hook 内部把**流正常结束（server 主动关闭）与断线都当断线处理触发重连**」；
  - `:344-350`（Q12）则说「流被服务端主动关闭（RESULT / ERROR 终态事件后端会 close 连接）**不应重连**」，靠 `hasReachedTerminal` 判定。
- **矛盾点**：二者对「server 主动关闭连接」的处置**完全相反**——Q11 主张「关流即重连」，Q12 主张「收到终态后关流不重连」。
- **后果**：若执行体按 Q11 字面「关流即重连」实现，会与 Q12 的 `hasReachedTerminal` 终态判定打架；正常终态流（result/error 后 server close）会被反复重连，直到退避超 3 次才 `status='error'`，UI 出现「已完成还疯狂重连」的假错。
- **修订建议**：DECISION 必须一句话闭合——**仅当连接关闭时尚未收到 `result`/`error` 终态事件，才走重连；收到任一终态事件后连接关闭一律 `status='closed'` 不重连。** Q11 的「把关流当断线」建议作废，Q12 原则为唯一权威。
- **裁定选项**：(a) 采纳闭合措辞（推荐）/ (b) 维持 Q11「关流即重连」（不推荐，与 Q12 冲突）。

### A2 · Q12 `data.recoverable === false` 后端无契约支撑（致命错误无限重连）

- **现状（初稿）**：`:349` 终态判定 `type === 'result' || type === 'error' && data.recoverable === false`；`:351` 重连退避「超 3 次给 `status='error'`」。
- **实测事实**：
  - 后端 `schemas/agent.py:40` 中 `SSEEvent.data` 类型 = `Any`（**未结构化**）；
  - 全仓 grep ERROR 事件**无 `recoverable` 字段**（后端 ERROR 事件 `data` 不固化 `recoverable`）；
  - → 任何 `error` 事件其 `data.recoverable` 恒为 `undefined`，`undefined === false` 为 **false**。
- **后果**：照 Q12 实现时，`error` 事件**永远走「非终态 → 重连」分支** → 致命错误（如 400/500 业务错）被无限重连重试，直到退避超 3 次才止；这与「error 即终态」的工程常识相悖，且浪费后端资源。
- **修订建议**：DECISION 改为——**任何 `result` 或 `error` 事件即视为终态、停止重连**；把 `data.recoverable` 语义标记为「后端契约未定义，本 PR 不实现该分支」，不写死 `recoverable === false` 判定。
- **裁定选项**：(a) 采纳「error/result 即终态、弃 recoverable」（推荐，默认采纳）/ (b) 坚持 recoverable 分支（需后端先补契约，超出了本 PR 范围）。

### A3 · Q13 `lastHeartbeatAt` 未进 Q3 返回类型（实现后无法暴露）

- **现状（初稿）**：
  - `:94-101`（Q3 `UseTaskStreamResult`）只含 `events / lastEventId / status / latestByType / reconnect / close`，**不含 `lastHeartbeatAt`**；
  - 但 `:361`（Q13 建议）说「提供便捷字段 `lastHeartbeatAt: number | null` 供 UI 层判定心跳丢失」。
- **矛盾点**：Q13 要求 hook 暴露 `lastHeartbeatAt`，但 Q3 的返回接口没这个字段 → 执行体在阶段 4 实现 Q13 后**无法把 `lastHeartbeatAt` 暴露给 UI**（接口缺字段，要么私自加破坏契约，要么不实现）。
- **修订建议**：DECISION 把 `lastHeartbeatAt: number | null` 显式补进 `UseTaskStreamResult` 接口（与 `events/status/...` 并列）。Q13 采纳的同时须同步修订 Q3 接口。
- **裁定选项**：(a) 补进返回接口（推荐，默认采纳）/ (b) Q13 改「心跳不入 events[] 但也不暴露 lastHeartbeatAt」。

### A4 · Q10.2「X 仅编译期」在现有 vitest 配置下跑不起来

- **现状（初稿）**：`:320-327` Q10.2 方案 X = 「仅编译期（types-only tests · `expectTypeOf` 或 tsd）」；`:325` 指挥官倾向 X「零运行时开销」。
- **实测事实**：
  - `frontend/vite.config.ts:22-27` 的 vitest `test` 配置**未开 `typecheck.enabled`**（`test.typecheck` 段缺失）；
  - 纯编译期 `types-only` 测试（tsd / `vitest --typecheck` + `.test-d.ts`）**无配置支撑**，当前 `npm run test` 不会执行类型检查分支；
  - `expectTypeOf(...)` 在普通 `*.test.ts` 里虽可用，但它是**运行期执行的**（计入 `N_before + 4` 基线），并非「零运行时开销」。
- **后果**：若 DECISION 写「TC-S5-12-4 仅编译期、零运行时」，执行体要么发现根本没类型检查入口（CI 无红信号）、要么用 `expectTypeOf` 跑成运行期测试（与「零运行时」表述不符）。
- **修订建议**：DECISION 二选一写死：
  - (a) 启用 `test.typecheck.enabled = true` + 写 `frontend/tests/types/agent.types.test-d.ts`（小幅扩 vite.config 范围，真正零运行时）；
  - (b) **务实取 Z-lite**：`frontend/tests/types/agent.types.test.ts` 用 `expectTypeOf`（随 vitest 运行期校验，计入 `N_before + 4` 基线），把「零运行时」修正为「随测试运行期校验类型」。推荐 (b)，与现有 vitest 配置零改动、风险最低。
- **裁定选项**：(a) 启用 typecheck + `.test-d.ts` / (b) Z-lite `expectTypeOf` 运行期校验（推荐）。

### A5 · Q17 红阶段用 `.skip` 而非 `.fails`（丢失红信号，与 PR-17 不对称）

- **现状（初稿）**：`:405`（commit 1）「PR-18 red-test skeleton · TC-S5-12-1..4 骨架（**全 xfail / skip**）」；`:476`（阶段 1）「4 用例骨架（**全 skip**）」。
- **事实**：
  - PR-17 用的是 **pytest `xfail`**（运行并预期失败，实现后转绿，CI 始终有红信号，体现「红→绿」TDD 对称性）；
  - vitest `test.skip` **不运行**（无红信号，CI 永不红），其等价物是 **`test.fails`**（运行并预期失败，阶段 5 实现后须移除 `.fails` 才转绿）。
- **后果**：若 DECISION 写「全 skip」，阶段 1 的 red-test skeleton **失去红信号**，名为 TDD 实为「先写空壳再回填」，与 PR-17 对称结构名不副实；且 reviewer 无法从 CI 看出「红」阶段存在。
- **修订建议**：DECISION 明确——阶段 1（commit 1）用 **`test.fails`** 标记 4 个 TC 骨架；阶段 4（commit 5）转绿时**移除 `.fails`**（而非 `.skip`）。
- **裁定选项**：(a) `.fails` 非 `.skip`（推荐，默认采纳）/ (b) 维持 `.skip`（不推荐）。

---

## B 类 · 措辞微调 / 边角建议（不阻断，但建议采纳）

### B1 · Q8 `AgentChatResponse.status` 联合类型含非真实返回集

- **现状（初稿）**：`:227-231` `AgentChatResponse.status: 'PLANNING' | 'WAITING_CONFIRMATION' | 'EXECUTING'`（3 值子集）；`:230` 注释「`initial_plan?: Plan; // PR-14 起后端不填」」。
- **实测事实**：`backend/app/api/v1/agent.py:87,97` 实测 `POST /agent/chat` 返回**裸 dict** `{task_id, status:"PLANNING"}`，且端点**根本不用 `AgentChatResponse` pydantic 模型**（`initial_plan` 永不返，印证 HANDOFF 陷阱 4）。
- **评估**：3 值子集含 `PLANNING` 成立，但后端 `status` 字段是 `str`、**唯一实测返回值是 `"PLANNING"`**。建议 DECISION 二选一：
  - (a) `chat()` 的返回 `status` 直接归到完整 `TaskStatus` 联合（最稳，不假设子集）；
  - (b) 保留 3 值子集但加注释「假设 chat 仅返此 3 值 active 态，实测目前仅 `PLANNING`」。
- **裁定选项**：(a) 归完整 `TaskStatus` / (b) 保留 3 值子集+注释（推荐 b，与 Q8 现状一致）。

### B2 · Q7 联合体护栏生效时机（追债项 3 护栏延至 PR-19）

- **现状（初稿）**：`:213` 指挥官倾向 Q7-A「让 TS 编译器帮监视追债项 3 漂移（新增后端 type 时前端 union 里缺少，会在 PR-19 卡片 switch 里触发 exhaustiveness error）」。
- **评估**：PR-18 **无 switch 消费 `ArtifactType`**，union 仅文档价值；真正的 exhaustiveness 护栏在 **PR-19 的卡片 `switch`**。本 PR 写严格 union 不会当场触发任何编译期护栏。
- **修订建议**：DECISION 注明「追债项 3 护栏延至 PR-19 激活」；另：PR-17 新债 12（`create_match_score` dangling）修复时会改 `_ARTIFACT_TYPE_MAP` 键（`engine.py:50-56`），前端 `ArtifactType` union 届时可能需同步——PR-19 留意。
- **裁定选项**：采纳注明（默认采纳）。

### B3 · Q2/Q12 `retry:` 指令归属（hook 用自身退避、忽略 server `retry`）

- **现状（初稿）**：`:351` 重连指数退避「第 1 次 3000ms（**遵 api-contract §3.5 `retry:3000`**）、第 2 次 6000ms、第 3 次 12000ms」。
- **评估**：api-contract §3.5 的 `retry:3000` 是 **server→client 的 SSE 指令**；但 Q2 选定**选项 B（fetch + ReadableStream 手写解析器）**，手写解析器需自行处理 `retry:` 指令。若既读 `retry:` 又用 3/6/12 指数，会二义。
- **修订建议**：DECISION 显式「hook **用自身指数退避（3/6/12s），忽略 server `retry:` 字段**」，避免二义（原生 EventSource 才会自动消费 `retry:`，选项 B 不自动）。
- **裁定选项**：采纳「忽略 server retry、用自身退避」（默认采纳）。

### B4 · §求助 clause 9 前提不可达（`initial_plan` 永不返）

- **现状（初稿）**：`:467` clause 9「若手工调 `POST /agent/chat` 发现 **`initial_plan` 又开始返值**（理论上 PR-14 后不填）→ 停下汇报」。
- **实测事实**：见 B1——端点**永不返 `initial_plan`**（返的是裸 dict，且 `AgentChatResponse` 模型根本未被使用）。
- **后果**：该 clause 前提失效：无论后端是否有 regression，`initial_plan` 都「不返值」，clause 永远不触发，等于虚设。
- **修订建议**：clause 9 改为「若 `POST /agent/chat` 返回结构异常（缺 `task_id` / `status`，或 `status` 为非预期值如小写）→ 停下汇报（可能后端 contract regression）」。
- **裁定选项**：采纳改写（默认采纳）。

### B5 · Q19 pytest 免跑的护栏补充

- **现状（初稿）**：`:428-432` Q19「PR-18 只改前端、不动 backend/app · pytest 应保持 120 passed；执行体**不必跑 pytest**」。
- **评估**：纯前端免跑合理；但 §求助 clause 5（`:463`）只覆盖「前端 test 基线倒退」，**未覆盖「误触 backend/app」**。
- **修订建议**：§求助新增一条「**若不慎改动 `backend/app`，必须跑 `uv run pytest` 维持 120 passed**」（FRONTEND-ONLY 护栏的反向兜底）。
- **裁定选项**：采纳新增（默认采纳）。

### B6 · base hash 一致性（HANDOFF §9.4 陷阱 8 须刷到 `f75e2a9`）

- **现状（初稿）**：`:10` 起手 HEAD = `f75e2a9`（已含 PR-17 STEP6 报告状态）；`:459` clause 1 正确用 `f75e2a9`。但 `HANDOFF.md:433`（§9.4 陷阱 8）仍写 `7810a8e`（PR-17 整改 deferred 的 HANDOFF 更新之一）。
- **评估**：FF-merge 时 HANDOFF §9.4 陷阱 8 须刷新到 `f75e2a9`，否则 base hash 与 QUESTIONS 自述不一致。
- **修订建议**：DECISION 在「文档同步」段显式列一条「FF-merge 时 `HANDOFF.md:433` 陷阱 8 的 hash 从 `7810a8e` 改为 `f75e2a9`」（正属 PR-17 整改 deferred 的 HANDOFF 更新）。
- **裁定选项**：采纳（默认采纳）。

### B7 · TASKS §S5-12 / §S5-13 owner 口径陈旧

- **现状（初稿）**：`:19-20` 引用 TASKS §S5-12/§S5-13 仍标 owner = **PR-17**（历史漂移，实际 PR-17 是路由修复）。
- **评估**：PR-18 落地后，§S5-12 owner 应更新为 PR-18、§S5-13 留 PR-19；否则 TASKS 权威源出现 owner 错位。
- **修订建议**：DECISION 在「文档同步」段列一条「FF-merge 时 `docs/planning/TASKS-STAGE5.md` §S5-12 owner → PR-18、§S5-13 owner → PR-19」（docs 更新随 FF-merge，参照 PR-17 模式）。
- **裁定选项**：采纳（默认采纳）。

---

## C 类 · §求助边界修订（建议改写 1 条 + 新增 2 条）

### C1 · 改写 clause 9（对应 B4）

- 原文 `:467`「`initial_plan` 又开始返值」→ 改为「`POST /agent/chat` 返回结构异常（缺 `task_id`/`status` 或非预期 status 值）」。

### C2 · 新增 clause 10 · 误触 backend/app 须跑 pytest（对应 B5）

- 若阶段 3-4 不慎改动 `backend/app` 任意文件 → 立即 `uv run pytest` 维持 120 passed，未跑不得提交；若红则停下汇报。

### C3 · 新增 clause 11 · 重连终态判定须按 A2 实现（对应 A2）

- 若执行体阶段 4 实现发现：按 Q12 原文 `data.recoverable === false` 判定终态会导致致命错误无限重连（因后端无该字段）→ 必须按 A2 闭合（error/result 即终态），**不得私自加 `recoverable` 字段或绕过**，若判定有异议停下汇报。

---

## D 类 · 待指挥官裁定的开放决策（与修订无关，纯采纳项）

以下在评估中判定「可直接采纳指挥官倾向」，供指挥官一键确认：

| # | 建议 | 评估 |
|---|---|---|
| Q1 | 方案 A（严格 S5-12，ChatCenter/Card 留 PR-19） | ✅ 采纳（与 TASKS 唯一事实源一致，避免大 PR） |
| Q2 | 选项 B（fetch + ReadableStream 手写解析器） | ✅ 采纳（TC-S5-12-2 重连头白纸黑字，B 可测；对齐 msw+fetch 测试模式） |
| Q3.1 | 保留 `latestByType` 便捷字段 | ✅ 采纳 |
| Q3.2 | `events` 按 `id` 去重 | ✅ 采纳（幂等更稳） |
| Q3.3 | `lastEventId` 持久化留 PR-19 | ✅ 采纳 |
| Q4 | 方案 A（新建 `types/agent.ts` re-export） | ✅ 采纳（符合 TASKS 事实源） |
| Q5 | union type 超 TS enum，大小写严格对齐 | ✅ 采纳（与 `JDStatus`/`CandidateStatus` 一致） |
| Q6 | Plan / PlanStep 逐字段严格对齐 | ✅ 采纳 |
| Q7 | 方案 A（严格 `ArtifactType` union） | ✅ 采纳（但护栏延 PR-19，见 B2） |
| Q8 | REST 请求/响应逐字段对齐 | ✅ 采纳（status 子集按 B1 注明） |
| Q9 | `agentApi` 5 函数签名 | ✅ 采纳 |
| Q9.1 | 429 不加中间层，调用方 try/catch | ✅ 采纳（`request.ts` 已 reject） |
| Q10 | 测试落点 `tests/hooks` + `tests/services` + `tests/types` | ✅ 采纳（TC-S5-12-4 按 A4 取 Z-lite） |
| Q10.1 | SSE mock = B 分支 ReadableStream | ✅ 采纳 |
| Q11 | msw 断线机制 | ✅ 采纳（**按 A1 闭合**后：仅非终态关流触发重连） |
| Q12 | 重连触发规则 | ✅ 采纳（**按 A2 闭合**后：error/result 即终态、弃 `recoverable`） |
| Q13 | `system` 心跳不入 `events[]` + 单独字段 | ✅ 采纳（**按 A3 补 `lastHeartbeatAt` 进返回接口**） |
| Q14 | 未知 type / JSON.parse 失败 → warn + skip 不 throw | ✅ 采纳 |
| Q15 | 方案 A（不引入 zustand） | ✅ 采纳（`store/` 已存在，本 PR 不用） |
| Q16 | `AbortController` 管理流生命周期 | ✅ 采纳 |
| Q17 | 5 commit TDD 结构 | ✅ 采纳（**阶段 1 用 `.fails` 非 `.skip`，见 A5**） |
| Q18 | 分支 `feat/pr-18-s5-12-sse-hook` | ✅ 采纳 |
| Q19 | pytest 免跑（docs-only 声明） | ✅ 采纳（但误触 backend 须跑，见 C2） |
| Q20 | 前端 test 基线 `N_before + 4` | ✅ 采纳 |
| Q21 | 前端 lint + build 全绿 | ✅ 采纳 |
| §求助 | 9 clauses（改写 clause 9、新增 10/11） | ✅ 采纳（见 C1/C2/C3） |

---

## 裁定汇总（供指挥官勾选）

- [ ] **A1** Q11/Q12 关流二义闭合：(a) 仅非终态关流触发重连，终态关流 `closed` 不重连（推荐）/ (b) 维持 Q11 关流即重连
- [ ] **A2** Q12 终态判定：(a) error/result 即终态、弃 `recoverable`（推荐）/ (b) 坚持 `recoverable === false`（需后端补契约）
- [ ] **A3** Q13 `lastHeartbeatAt` 补进 `UseTaskStreamResult`：(a) 补进（推荐）/ (b) 不暴露
- [ ] **A4** Q10.2 编译期落地：(a) 启 `typecheck` + `.test-d.ts` / (b) Z-lite `expectTypeOf` 运行期（推荐）
- [ ] **A5** Q17 红阶段：(a) `.fails` 非 `.skip`（推荐）/ (b) 维持 `.skip`
- [ ] **B1** Q8 status：(a) 归完整 `TaskStatus` / (b) 保留 3 值子集+注释（推荐）
- [ ] **B2** Q7 护栏延 PR-19 + 留意债 12（默认采纳）
- [ ] **B3** 忽略 server `retry:`、用自身 3/6/12 退避（默认采纳）
- [ ] **B4** 改写 clause 9 前提（默认采纳）
- [ ] **B5** 新增 clause 10 误触 backend 须跑 pytest（默认采纳）
- [ ] **B6** FF-merge 刷 HANDOFF §9.4 陷阱 8 → `f75e2a9`（默认采纳）
- [ ] **B7** FF-merge 刷 TASKS §S5-12/§S5-13 owner（默认采纳）
- [ ] **C1/C2/C3** §求助改写 clause 9 + 新增 10/11（默认采纳）
- [ ] **D** 全部采纳 Q1A/Q2B/Q3.1+3.2/Q4A/Q5/Q6/Q7A/Q8/Q9/Q9.1/Q10/Q10.1/Q11(A1闭合)/Q12(A2闭合)/Q13(A3补字段)/Q14/Q15A/Q16/Q17-5(A5 .fails)/Q18/Q19/Q20/Q21/§求助

裁定后我出 `PR18-KICKOFF-DECISION.md`；依 AGENTS.md §4.1 docs-only 可直推 master（或随本分支三件套），等你指令。
