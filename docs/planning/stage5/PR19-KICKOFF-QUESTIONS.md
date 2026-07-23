# PR-19 KICKOFF QUESTIONS · S5-13 前端 ChatCenter + CandidateChat + 8 类事件卡片

> **对象**:主指挥官(用户)裁定
> **文档角色**:指挥官(Claude Code, ark-code-latest)向用户提问,收集口径后出 `PR19-KICKOFF-DECISION.md`
> **权威依据**:
> - `docs/planning/TASKS-STAGE5.md §S5-13`(线号 270-283)+ §五 清扫项(线号 293)
> - `docs/planning/TEST-PLAN-STAGE5.md §二`(线号 99-110 · TC-S5-13-1..10)
> - `docs/api-contract.md §3.1–§3.5 / §4.1–§4.5`(SSE 8 事件类型 / 重放心跳 / REST 六端点)
> - `HANDOFF.md §9.4 陷阱 4/5/6/8/10/11`(PR-14/17/18 已落定的前端消费约束 + 新增 system:cancelled 边界 + fetch 选型延续)
> - `HANDOFF.md §9.3 追债项 3`(`_ARTIFACT_TYPE_MAP` ↔ 前端 union · PR-19 卡片 switch 激活 exhaustiveness 护栏)
> - `PR18-STEP6-REPORT.md §五 obs 3`(`system:cancelled` 目前不在 hook 终态判定内,PR-19 评估)
> - PR-18 前端基建(commit `dd73c4d` HEAD):`frontend/src/types/agent.ts` + `services/agent.ts` + `hooks/useTaskStream.ts` + tests 20 passed
> **起手 master HEAD**:`9a6554e`(§9 refresh 后)
> **测试基线**:后端 **120 passed** / 前端 **20 passed(9 test files)** / 前端 lint **0 errors / 8 warnings**(基线含 `react-hooks/exhaustive-deps` 8 处,TASKS §五 列 PR-19 顺手补)

---

## 〇 · PR 范围与拆分口径(阻断级前置)

### 事实

- **TASKS §S5-13** 权威事实源(线号 270-283)交付清单 3 类:
  1. `frontend/src/pages/ChatCenter.tsx`(替换 PlaceholderPage · 消息输入框 → chat() → useTaskStream → 渲染 8 类卡片 · PlanCard 含「确认执行」「取消」按钮)
  2. `frontend/src/pages/CandidateChat.tsx`(替换 PlaceholderPage · 预填 `context.candidate_ids` 的同构对话页)
  3. `frontend/src/components/agent/*Card.tsx` × 8(`ThinkingCard / PlanCard / ToolCallCard / ProgressCard / ResultCard / ErrorCard / WarningCard / SystemCard`)
- **验收判据 4 条**:发送→PlanCard→确认/取消流 · skip-to-score 快捷入口 EXECUTING · 断线重连无重复卡片 · CANCELLED 态 UI(TC-S5-13-9)
- **测试用例 10 个**(TEST-PLAN §二 · 4 hook 已 PR-18 消化 + 10 UI = TC-S5-13-1..10):
  - `TC-S5-13-1` 发送→PlanCard→确认调 executePlan
  - `TC-S5-13-2` skip-to-score 快捷
  - `TC-S5-13-3` 8 类事件卡片均渲染
  - `TC-S5-13-4` 断线重连无重复卡片
  - `TC-S5-13-5` PlanCard 取消按钮调 cancelTask
  - `TC-S5-13-6` CandidateChat 预填 context
  - `TC-S5-13-7` WarningCard 渲染
  - `TC-S5-13-8` SystemCard 心跳不渲染为业务卡片
  - `TC-S5-13-9` CANCELLED 态显示取消提示 UI(非 ErrorCard)
  - `TC-S5-13-10` ErrorCard 渲染 + message
- **PR-18 交付基建**:`useTaskStream` 已就位、`agentApi` 5 函数已就位、`types/agent.ts` 6 键 `ArtifactType` union 就位。PR-19 **直接消费**,不改基建
- **未消化的 PR-18 观察**:
  - obs 3 · `system:cancelled` 边界(hook 非终态处理,重连 3 次后 status='error')
  - 追债项 3 · exhaustiveness 护栏激活时机(卡片 `switch` 分派 artifact.type)

### Q1 · PR-19 边界口径

**建议方案 A(推荐)**:PR-19 严格对齐 TASKS §S5-13 = **2 pages + 8 Cards + 10 用例**(TC-S5-13-1..10);**不含**基建改动、不含新引入的状态库(zustand)、不含 `services/agent.ts` 扩展。
  - **优点**:PR 粒度受 TASKS §S5-13 直接约束;测试用例数 10 严格对齐 TEST-PLAN §二;直接消费 PR-18 基建;交付面 ~10 文件(2 页 + 8 Card + tests)
  - **代价**:PR-19 是本 Stage 前端最大 PR(用例数与 PR-14 6 用例 / PR-17 4-5 用例 比翻倍),交付面达 ~10 文件 + ~10 test files;评审复杂度上一档
  - **验收边界**:每类卡片 ≥1 测试渲染断言,PlanCard 交互双向断言(确认 → executePlan · 取消 → cancelTask),skip-to-score 快捷路径断言 EXECUTING,断线重连不重复渲染

**方案 B**:拆 PR-19a + PR-19b。19a = ChatCenter + 8 Card + 5 用例(TC-S5-13-1/2/3/8/9);19b = CandidateChat + WarningCard/ErrorCard 完善 + 5 用例(TC-S5-13-4/5/6/7/10)。
  - **优点**:每 PR 粒度可控 ~5 用例、~5 文件;19a 落地后可先跑 UI 演示;19b 快速补齐
  - **代价**:测试用例 TC-S5-13-3(8 类卡片均渲染)与 19a 不天然对齐 —— WarningCard/ErrorCard 定义在 19a 还是 19b?若在 19b 则 TC-S5-13-3 只能测 6/8;若在 19a 则测试 TC-S5-13-7/10 提前落。整体拆分成本 > 收益
  - **典型 anti-pattern**:UI PR 拆分容易造成 "PR-19a 组件不完整" 或 "PR-19b 无独立价值" 两难

**方案 C**:PR-19 只做 ChatCenter + 5 Card(不含 CandidateChat 与 WarningCard/ErrorCard/SystemCard 三类边界卡片);剩余留 PR-20。
  - **优点**:更小 PR
  - **代价**:偏离 TASKS §S5-13 权威事实源 · 8 类卡片是 API 契约 §3.3 完整语义,拆分后 exhaustiveness 护栏(追债 3)无法激活;TC-S5-13-3 不成立
  - **风险**:Stage 5 收官被推迟到 PR-20,方案 A 一步到位反而更省

**指挥官倾向**:方案 A · 严格 S5-13 全量交付。理由:
1. TASKS 是权威事实源,S5-13 明确列出 8 类卡片 + 2 页;TEST-PLAN 明确 10 用例;不应拆
2. PR-19 是前端收官,一次交付完整对话链路 · 后续 Stage 5.1 无 UI 拆分空间
3. PR-18 已把最重的 SSE 解析器 + 类型契约 + services 全部就位,PR-19 纯组件层(props → 渲染),复杂度可控
4. 8 类 Card 组件之间高内聚(共享 event.data 类型 + 布局风格),一次落地样式统一性最好
5. 追债 3 exhaustiveness 护栏一次激活到位,不留半开状态

**待裁定**:方案 A / B / C(A 推荐)

---

## 一 · 阻断级技术选型

### Q2 · 前端状态管理选型(**阻断级**)

**事实**:PR-19 需要管理的状态:

- **当前任务上下文**:`taskId` + `status`(PLANNING/EXECUTING/COMPLETED/...)  + `plan`(WAITING_CONFIRMATION 后的 Plan) + `events[]`(全量事件时序)
- **UI 交互态**:输入框内容、发送 loading、PlanCard 确认/取消进行中、错误 toast、心跳指示器
- **跨页共享**:是否需要在 ChatCenter 与 CandidateChat 之间共享任务队列?或每个页面独立?
- **PR-18 决策**:`useTaskStream` 已用 React `useState` + `useRef` 组织本地状态,**未引入任何全局 store**

**选项 A · 纯组件 `useState` + 参数下钻**(推荐):
  - ChatCenter 用 `useState` 管理 `messages: Message[]`(用户消息 + agent 回复) + `activeTaskId: string | null`;通过 `useTaskStream({taskId: activeTaskId})` 拿事件流;将 `events` 直接传给 Card 列表组件渲染
  - **优点**:零依赖、符合 React hooks 惯用法、`useTaskStream` 本身已封装全部 SSE 状态、8 类 Card 只需接 `event: SSEEvent` prop、TASKS §S5-13 未要求跨页状态共享(CandidateChat 有自己的 taskId,不需要 ChatCenter 的历史)
  - **代价**:如果未来要做「任务列表侧栏」(所有历史 task 一目了然),需要状态提升;但 TASKS §S5-13 不要求侧栏

**选项 B · 引入 zustand**(项目内首次引入):
  - 建 `frontend/src/store/agentStore.ts` 存 `tasks: Record<string, {events, status, plan}>` + `activeTaskId`
  - **优点**:跨页共享(ChatCenter 与 CandidateChat 可看到彼此任务)、便于后续多任务并行、DevTools 支持
  - **代价**:新依赖(`zustand` ~1KB gzip,不算重)、AGENTS.md 未提及状态库规范、TC-S5-13 全部用例都可用 `useState` 达成、无验收判据要求跨页;引入即扩范围
  - **PR-18 KICKOFF Q1 已明确排除 store**:方案 A 硬边界,PR-18 不引入。PR-19 是否引入需重新裁定

**选项 C · React Context**:
  - 建 `AgentTaskContext` 存 `activeTask` + provider 包 App
  - **优点**:标准库、无新依赖
  - **代价**:Context 频繁 re-render 触发 · SSE 事件流每 event 都触发 setState 会让 Provider 下所有消费者 re-render;性能上不如 zustand 或 useState 本地

**指挥官倾向**:**选项 A · 纯 useState**。理由:
1. TASKS §S5-13 未提任何跨页状态共享要求
2. TC-S5-13-1..10 全部 UI 集成测试均可用组件本地 state 达成 · msw mock SSE 流 + 断言 render 结果
3. `useTaskStream` 已是「单任务 SSE 客户端」抽象,组件层再套一层 store 是过度设计
4. Stage 5.1 若真需要多任务侧栏,再引入 zustand 是纯增量、无 breaking
5. 遵循 PR-18 建立的最小依赖原则

**待裁定**:选项 A / B / C(A 推荐)

---

### Q3 · 任务态跨刷新持久化(F5 后如何恢复)

**事实**:api-contract §3.5 规定 SSE 断线可用 `Last-Event-ID` 重放;但 **`taskId` 本身如何在 F5 后恢复**?

- 场景:用户在 ChatCenter 发起对话 → task_id=t1 → 走到 EXECUTING → F5 刷新 → 现在页面重新加载,前端如何知道 `activeTaskId = t1`?
- 若不做恢复:F5 后页面为空、用户任务在后端仍跑,前端无法看进度、无法取消

**选项 A · 不做任何持久化**(推荐):
  - 每次页面加载 = 全新 session、`activeTaskId = null`;用户如需继续需重新描述
  - **优点**:零复杂度、TASKS/TEST-PLAN 都未要求 F5 恢复;后端 tasks 表数据不丢,可以后接「任务列表」页(Stage 5.1)
  - **代价**:F5 = 任务上下文丢失;但 Stage 5 MVP 语义可接受(demo/单会话使用)

**选项 B · URL query 保存 taskId**:
  - `<ChatCenter />` 路由从 `/chat` 变为 `/chat?task=t1`,进入页面从 query 恢复;发起 chat 后 `navigate('/chat?task=t1', {replace: true})`
  - **优点**:F5 恢复、可分享链接、无 storage 副作用
  - **代价**:8 类 Card 事件历史仍需从后端拉(需 `GET /agent/tasks/{id}` + 补齐 events 快照);api-contract §4.4 是否提供 events 历史?**需核查** —— `GET /agent/tasks/{id}` 返 TaskStatusResponse 含 status/plan/result/error 但**不含 events 时序**;走 SSE 加 `Last-Event-ID=0` 请求全量重放才能恢复;此路径 hook 支持(§3.5 缓冲重放)。**但 PR-14 SSE 缓冲 TTL 30 分钟**,超过 TTL 后 `Last-Event-ID=0` 只能拿到快照 result

**选项 C · localStorage 保存 taskId + events 快照**:
  - `agentStore.saveActiveTask({taskId, lastEventId})`,F5 从 storage 恢复
  - **优点**:F5 完全恢复 + 无需重连即恢复(events 存在 storage)
  - **代价**:events 可能几 MB,storage 有 5MB 限制;需 GC 策略;超出本 PR 边界

**指挥官倾向**:**选项 A · 不做持久化**。理由:
1. TASKS/TEST-PLAN 都未要求 F5 恢复,不在验收边界内
2. 后端 SSE 缓冲 30 分钟 TTL 已提供有限恢复能力,但需要 UI 侧「任务列表」入口(Stage 5.1)
3. 选项 B URL query 看似便宜,但真正解决用户体验需要事件历史回填,复杂度大
4. Stage 5 定位是「Agent 对话能力 MVP 展示」,不是完整生产会话系统

**待裁定**:选项 A / B / C(A 推荐)

---

### Q4 · PlanCard 交互形态(**阻断级 · 验收判据 1 直接触发**)

**事实**:验收判据 1 = 「发送消息后出现 PlanCard 且「确认」按钮调用 executePlan(),「取消」调用 cancelTask()」。`ExecutePlanRequest` 类型允许 `accepted_steps?: string[]` + `modifications?: {step_id, modified_params?}[]`(选择性接受步骤 + 参数改写)。

**问题**:PlanCard 是否要暴露以下能力?

- (a) **展示 Plan.steps**:列出所有 step,含 `tool_name / params / optional / dependencies`
- (b) **单步勾选**:允许用户勾掉不想执行的 step(生成 `accepted_steps`)
- (c) **参数改写**:允许用户点某个 step 打开 params 编辑框(生成 `modifications`)
- (d) **确认按钮**:调 `executePlan(taskId, {accepted_steps, modifications})`
- (e) **取消按钮**:调 `cancelTask(taskId)`
- (f) **完整参数展示**:仅只读展示 params,不允许编辑

**选项 A · 最小可用**(推荐):(a) 展示 + (f) 只读展示 params + (d) 确认全接受 + (e) 取消。**不支持** (b)/(c),即 `executePlan` 只发 `{task_id}` 空 body 表全部执行。
  - **优点**:UI 简单、TC-S5-13-1(确认调 executePlan)/ TC-S5-13-5(取消调 cancelTask)都可直接断言;交付面小
  - **代价**:api-contract §4.2 定义的 `accepted_steps`/`modifications` 功能未使用;Stage 5.1 若接需求需扩

**选项 B · 完整支持**:(a)(b)(c)(d)(e) 全支持,用户能勾选步骤、编辑参数
  - **优点**:契约 §4.2 完整实现
  - **代价**:UI 复杂 · 每 step 一个 checkbox + 一个 "编辑参数" modal + 参数编辑器(需要根据 params schema 动态渲染 form?);TASKS/TEST-PLAN 都未提这些交互;测试量翻倍(需覆盖勾选/取消勾选/编辑保存等);超出 §S5-13 边界

**选项 C · 中间态**:(a) + (b) 勾选 + (d)(e),**不支持** (c) 参数编辑
  - **优点**:用户至少能拒绝个别 step
  - **代价**:仍需勾选交互 + 相应测试;TASKS 未要求

**指挥官倾向**:**选项 A · 最小可用**。理由:
1. TASKS §S5-13 只说「确认执行」+「取消」两个按钮,没说勾选/编辑
2. TEST-PLAN TC-S5-13-1/5 断言范式是「按钮 click → 断言 API 被调」不含勾选/编辑
3. Stage 5 定位 MVP,复杂交互留 Stage 6
4. `ExecutePlanRequest` 的 `accepted_steps/modifications` 是可选字段,不发即默认全接受(需核查后端行为 · **需在 DECISION 显式确认**)

**待裁定**:选项 A / B / C(A 推荐)· 且 DECISION 必须显式说明 `executePlan({task_id})` 空 body 是否是后端 default-all-accept

---

### Q5 · SystemCard 与心跳 UI 表现(TC-S5-13-8 直接触发)

**事实**:
- TC-S5-13-8 断言 "SystemCard 心跳事件不渲染为业务卡片(仅状态提示)"
- PR-18 `useTaskStream` 已将 `system` 事件从 `events[]` 剥离,进 `latestByType.system` + `lastHeartbeatAt`
- `PR18-STEP6-REPORT.md §五 obs 3` 提到 `system:cancelled` 目前不在 hook 终态判定内 → 走非终态重连 3 次后 `status='error'`

**问题**:「仅状态提示」具体形态是什么?

**选项 A · 页面顶部横条 · 心跳绿点 + 断线红点**(推荐):
  - ChatCenter 顶部固定一个状态条,显示 `● 已连接 · 最后心跳 3s 前` 或 `● 断线重连中(第 2 次)` 或 `● 已断开`
  - `latestByType.system?.data.message` 展示为轻量提示(比如 "任务已排队" 之类的 informational text)
  - **优点**:与 hook `status` + `lastHeartbeatAt` 直接对齐、UX 清晰、TC-S5-13-8 断言"不进 events 列表"天然通过
  - **代价**:样式需要设计 · 引 Antd Badge + 时间格式化;system.data.message 内容多样(不同 event 语义不同,需要枚举)

**选项 B · 完全隐藏 system 事件**:
  - 页面不显示 system 相关信息,仅通过控制台 log
  - **优点**:UI 最简
  - **代价**:用户不知道断线/重连,体验差;`system:cancelled` 事件用户看不到关闭原因

**选项 C · SystemCard 作为独立卡片但视觉极小**:
  - `<SystemCard message="心跳" />` 渲染成 12px 灰色小字,进 events 列表
  - **代价**:与 TC-S5-13-8 断言"不渲染为业务卡片"边界模糊;心跳每 15s 一条会灌爆列表

**指挥官倾向**:**选项 A · 顶部横条**。理由:
1. 与 `useTaskStream.status` + `lastHeartbeatAt` 天然对齐,UX 清晰
2. TC-S5-13-8 通过条件是"不进 events 列表" · A 严格符合
3. 顶部横条可复用 Antd `<Alert type="info">` + `<Badge status="success" />`,零新样式

**关联 Q6**:`system:cancelled` 是否借顶部横条特殊显示 "已取消",UI 上避免走 error 分支?

**待裁定**:选项 A / B / C(A 推荐)

---

### Q6 · `system:cancelled` hook 边界处理(承接 PR-18 obs 3 · **阻断级**)

**事实**(PR-18 STEP6 §五 obs 3):
> 后端 `_is_terminal` 将 `system:cancelled` 也视作终态并关流,但本 hook 按 A2 仅认 `result`/`error` 为终态。若任务经 `system:cancelled` 终止,hook 会因「未收到 result/error」而走非终态重连,经历 3 次退避后 `status='error'`(非 clean `'closed'`)。属 DECISION A2 未涵盖的边界,未私自扩展;建议 PR-19 评估是否将 `system:cancelled` 纳入终态判定。

**问题**:PR-19 是否修改 `useTaskStream` 终态判定,把 `system:cancelled` 纳入终态?

**选项 A · 修改 hook 终态判定**(推荐):
  - `useTaskStream.ts` `isTerminal(event)` 从 `type === 'result' || type === 'error'` 扩展为 `type === 'result' || type === 'error' || (type === 'system' && data?.status === 'cancelled')`
  - **优点**:cancel 流程 clean 关闭 · `status='closed'` 不重连;UI 侧只需展示"已取消"状态,不走 error 分支
  - **代价**:改动 PR-18 交付的 hook · 需要新增 TC-S5-13-hook-cancel-terminal 测试(msw 发 `event: system {status: cancelled}` → 断言 hook 直接 closed 不重连);违反了「PR-19 不改基建」的原则
  - **缓解**:改动是纯扩容(既有分支不变,新增 OR 分支),回归风险低;TC-S5-13-9(CANCELLED UI)间接依赖该行为

**选项 B · 不改 hook,UI 层容忍 status='error'**:
  - hook 保持 PR-18 现状,`system:cancelled` 后 hook 走 error;ChatCenter 通过 `useTaskStream.status === 'error'` + `events` 里最后一条是 `system` 判断实际是 cancel,UI 展示"已取消"而非"出错"
  - **优点**:hook 零改动、PR-19 严格 UI-only
  - **代价**:UI 逻辑复杂 · 每次 error 都要回头看 events 最后一条判定真实语义;3 次重连的 6+9=15s 延迟仍存在,用户看到重连再看到 error 再判定 cancel,体验差

**选项 C · 后端不发 `system:cancelled` 而发 `error {code: 'CANCELLED'}`**:
  - 让后端在 cancel 时改发 `type=error` 事件让 hook 走 error 分支
  - **优点**:hook 零改动
  - **代价**:破 api-contract §3.2 与后端 `_is_terminal` 实现;需协调后端改 SSE 生成逻辑;error 用于报错语义 · cancel 语义混淆

**指挥官倾向**:**选项 A · 修改 hook**。理由:
1. PR-18 obs 3 已明确"建议 PR-19 评估" · 授权 PR-19 处理
2. cancel 是常规用户操作、不是错误 · UX 上必须 clean closed,不能让用户看重连
3. 改动可控:1 处 `isTerminal` 判定扩展 + 1 个新测试用例;PR-18 既有 20 用例不回归
4. 后端契约不动,前端 hook 独立收敛
5. 与 TC-S5-13-9(CANCELLED UI)对齐 · UI 拿到 `status='closed'` + `latestByType.system.data.status='cancelled'` 即可展示

**争议点**:选 A 后必须**扩展 PR-19 交付面**,包括:
- 修改 `frontend/src/hooks/useTaskStream.ts`
- 新增 hook 层测试 `TC-S5-13-hook-cancel-terminal`(建议编号 `TC-S5-13-11`,超出 TEST-PLAN 10 用例的追加)

**需求指挥官显式裁定**:是否允许 PR-19 追加 1 用例(TC-S5-13-11)以支撑 A 路径?

**待裁定**:选项 A / B / C(A 推荐)+ 允许追加 TC 与否

---

### Q7 · 追债项 3 exhaustiveness 护栏激活时机与方式

**事实**(HANDOFF §9.3 追债项 3 + §9.4 陷阱 8):
- PR-18 已把前端 `ArtifactType` 落地为 6 键 union:`jd / resume / match_score / candidate_merge / candidate_profile / generic`
- PR-19 卡片 `switch` 分派时 exhaustiveness 护栏激活 —— 即在 `ResultCard` 内 `switch(artifact.type)` 各分支后,default 分支落 `const _exhaustive: never = artifact.type;` 让 TS 编译期发现未处理分支

**问题**:激活 exhaustiveness 护栏的具体方式?

**选项 A · TS `never` 断言 + 每 type 独立子渲染器**(推荐):
  ```typescript
  function renderArtifactBody(artifact: ResultArtifact): React.ReactNode {
    switch (artifact.type) {
      case 'jd': return <JdArtifact data={artifact.data} />;
      case 'resume': return <ResumeArtifact data={artifact.data} />;
      case 'match_score': return <MatchScoreArtifact data={artifact.data} />;
      case 'candidate_merge': return <CandidateMergeArtifact data={artifact.data} />;
      case 'candidate_profile': return <CandidateProfileArtifact data={artifact.data} />;
      case 'generic': return <GenericArtifact data={artifact.data} />;
      default: {
        const _exhaustive: never = artifact.type;
        return <GenericArtifact data={artifact.data} />;  // runtime fallback
      }
    }
  }
  ```
  - **优点**:每 type 一处独立渲染器 · 未来加类型 TS 立即报错 · runtime 有 fallback(never 分支到 generic 兜底)
  - **代价**:6 个子渲染器 · 内部可以是简单 `<pre>{JSON.stringify}</pre>` 或结构化字段展示;测试面加大

**选项 B · 仅 generic + 有限特化**:
  - `switch` 只覆盖 `match_score` 结构化展示,其余 5 类都走 generic 显示 `<pre>` JSON
  - **优点**:开发量小
  - **代价**:护栏(never 断言)未激活,追债 3 未收敛;PR-19 名义上完成但事实上未消除追债

**选项 C · 全部 generic**:
  - 完全不做特化、所有 artifact 都以 JSON 展示
  - **代价**:护栏未激活,追债 3 完全未收敛;UX 差(match_score 这种结构化数据用户想看得清)

**指挥官倾向**:**选项 A · 全 6 类特化 + never 断言**。理由:
1. HANDOFF §9.3 追债项 3 明确「PR-19 卡片 switch 时 exhaustiveness 护栏激活」是追债收敛点
2. 6 种 artifact 里 `match_score` 结构化展示体验最优 · 其他 5 种至少要有语义化字段展示(不能全是 JSON 堆)
3. never 断言是标准 TS 模式 · 每次后端新增 artifact type 前端 TS 立即报错 · 追债 3 从此消除

**代价评估**:6 个子渲染器 = 6 个小组件,每个 20-30 行,总量 ~150 行。测试用 TC-S5-13-3(8 类事件卡片)间接覆盖 result 卡内 artifact 渲染,不需要为每子渲染器单独测。

**待裁定**:选项 A / B / C(A 推荐)

---

## 二 · 页面结构与用户流程

### Q8 · ChatCenter 页面整体布局

**建议布局**:
```
┌─────────────────────────────────────────────────┐
│ 顶部状态条 · 已连接/断线重连中/已断开 · 最后心跳 3s 前  │  ← Q5 选项 A
├─────────────────────────────────────────────────┤
│ Skip-to-Score 快捷入口(可折叠)                     │
│ [JD 选择器] [候选人多选] [立即评分] 按钮              │  ← Q9
├─────────────────────────────────────────────────┤
│ 消息时序区(滚动)                                    │
│   [用户消息] "帮我评分张三、李四对某 JD"              │
│   [ThinkingCard] "分析中..."                       │
│   [PlanCard] "计划 3 步" [确认] [取消]              │
│   [ToolCallCard] "调用 jd-candidate-matching..."   │
│   [ProgressCard] "60%"                            │
│   [ResultCard] "已生成匹配分,详情..."                │
├─────────────────────────────────────────────────┤
│ 消息输入框 [发送]                                  │
└─────────────────────────────────────────────────┘
```

**Q8**:是否采纳该布局?折叠 skip-to-score(默认收起)vs 常驻(默认展开)?

**建议**:采纳 · **默认收起** · 用户点展开条才显示 JD/候选人选择器。理由:
1. skip-to-score 是快捷路径 · 大多数会话不用它 · 默认收起减少视觉噪音
2. TC-S5-13-2 断言 "选 JD+候选人 → skipToScore → 显示进度卡片" · 展开后交互不变
3. Antd `<Collapse>` 直接用

**待裁定**:采纳布局 / 修改布局细节(需求具体)

---

### Q9 · skip-to-score 快捷入口具体形态

**事实**:验收判据 2 = 「选 JD + 候选人 → 直接 EXECUTING 并显示进度」。`agentApi.skipToScore(data: {jd_id, candidate_ids})` PR-18 已实现,直接 POST `/agent/skip-to-score`(不走 chat)。

**问题**:UI 上如何呈现 "已选 JD" + "已选候选人"?

**选项 A · Antd `<Select>` + `<Select mode="multiple">`**(推荐):
  - JD 单选下拉(从 `GET /jds` 拉列表)
  - 候选人多选下拉(从 `GET /candidates` 或 `GET /resumes` 拉列表)
  - 上限 20 候选人(与 §S5-13 未明说的合理默认)
  - **优点**:标准 Antd 组件、有搜索、有 tag 展示
  - **代价**:需要提前拉 JD/候选人列表 · 引入两个 API 调用;若不希望依赖这些 API 可以用 UUID 手输
  - **测试影响**:TC-S5-13-2 需 msw mock `GET /jds` + `GET /candidates`

**选项 B · 手输 UUID**:
  - 两个 input 手动填 UUID
  - **优点**:零 API 依赖、测试面小
  - **代价**:非人类友好 · UX 差

**选项 C · 从 URL query 预填**:
  - `/chat?jd=xxx&candidates=a,b,c` 进入自动填充 · 由外部导航过来触发
  - **优点**:与 CompareAnalysis/Resumes 页联动最佳
  - **代价**:需要改其他页 · 超出 PR-19 边界

**指挥官倾向**:**选项 A · Antd Select**。理由:
1. UX 最佳、TC-S5-13-2 断言路径清晰
2. `jdApi.list()` / `candidateApi.list()` 已在项目内成熟(Stage 3/4 已就位)
3. `<Select showSearch>` 可搜、`mode="multiple"` 可多选、可加 `maxTagCount`

**测试细节**:TC-S5-13-2 是否需要 mock 列表 API?建议只 mock `skipToScore` 端点,列表 API 可用 `<Select options={mockOptions}>` 直接注入 default value 避开列表拉取。

**待裁定**:选项 A / B / C(A 推荐)

---

### Q10 · CandidateChat 入口与预填机制

**事实**:
- TC-S5-13-6:进入页时 `context.candidate_ids` 已预填并随 `chat` 发送
- 目前**无任何页面 navigate 到 `/candidate-chat`**(仅路由存在)
- `AgentChatRequest.context = {jd_id?, candidate_ids?}` 已在 types

**问题 1**:`context.candidate_ids` 从哪里来?

**选项 A · URL query**(推荐):
  - `/candidate-chat?candidates=uuid1,uuid2` → 组件 `useLocation()` 解析 query → 预填 `context.candidate_ids`
  - 无 query 时兜底空数组,组件仍可运行(用户手动输入)
  - **优点**:与 Resumes/CompareAnalysis 页联动清晰(那些页加"打开对话"按钮 → `navigate('/candidate-chat?candidates=...')`);URL 可分享;F5 保持
  - **代价**:CompareAnalysis/Resumes 页需要加入口按钮 —— 超出 PR-19 边界?或作为 PR-19 附加改动?**需 DECISION 显式界定**

**选项 B · React Router `state`**:
  - `navigate('/candidate-chat', {state: {candidate_ids: [...]}})`
  - **优点**:类型友好、无 URL 污染
  - **代价**:F5 丢失、无法分享

**选项 C · 只支持 URL query · 不改其他页**:
  - PR-19 只落 CandidateChat 页支持 query,不改 Resumes/CompareAnalysis;后续 PR 补入口
  - **优点**:PR-19 边界最严
  - **代价**:PR-19 落地后 CandidateChat 无入口可测,只能靠直接输入 URL 或测试环境 mock;实际用户看不到功能

**问题 2**:PR-19 是否附加改动 Resumes/CompareAnalysis 加入口按钮?

**指挥官倾向**:
- **问题 1**:**选项 A · URL query**(TC-S5-13-6 断言路径直接)
- **问题 2**:**PR-19 附加**在 `CompareAnalysis.tsx` 页顶部加一个「与候选人对话」按钮(需要已选候选人),`navigate('/candidate-chat?candidates=' + selectedIds.join(','))`;仅一处入口,避免多点扩散。

**理由**:
1. TC-S5-13-6 断言路径 = 需要真实入口触发 · 只落 CandidateChat 页无入口不成立
2. CompareAnalysis 是"多候选人对比"页 · 自然衔接"选完对比后想直接对话"
3. Resumes 页(单简历列表)入口意义弱 · 不加

**待裁定**:问题 1 选 A/B/C + 问题 2 是否附加改动

---

## 三 · Card 组件设计口径

### Q11 · 8 类 Card 目录组织

**建议**:`frontend/src/components/agent/*Card.tsx` × 8 + 一个 `index.ts` re-export + 一个 `CardContainer.tsx`(共享布局 · Antd Card + 时间戳 header)

```
frontend/src/components/agent/
├── ThinkingCard.tsx     - Q11a
├── PlanCard.tsx         - Q11a + Q4 交互
├── ToolCallCard.tsx     - Q11a
├── ProgressCard.tsx     - Q11a(进度条)
├── ResultCard.tsx       - Q11a + Q7 exhaustiveness
├── ErrorCard.tsx        - Q11a
├── WarningCard.tsx      - Q11a
├── SystemCard.tsx       - Q11a(实际不进 events 列表 · 保留导出)
├── CardContainer.tsx    - 共享 header + 时间戳
├── artifacts/           - Q7 六个子渲染器
│   ├── JdArtifact.tsx
│   ├── ResumeArtifact.tsx
│   ├── MatchScoreArtifact.tsx
│   ├── CandidateMergeArtifact.tsx
│   ├── CandidateProfileArtifact.tsx
│   └── GenericArtifact.tsx
└── index.ts
```

**Q11a**:每 Card 用 Antd `<Card>` + 顶部 `<Space>` header?还是完全自定义样式?

**建议**:Antd `<Card size="small" title={...}>` + 内部字段展示 · 图标可用 `@ant-design/icons`(项目已引);颜色区分:
- Thinking · info(蓝色)
- Plan · primary(默认)
- ToolCall · info
- Progress · 无色 + `<Progress percent={n} />`
- Result · success(绿)
- Error · error(红)
- Warning · warning(黄)
- System · 见 Q5(不作为普通 Card 展示,仅顶部条)

**待裁定**:采纳目录 / 修改;Antd Card vs 自定义

---

### Q12 · WarningCard / ErrorCard 是否可关闭

**事实**:TC-S5-13-7/10 断言渲染 · 未提关闭交互

**选项 A · 不可关闭**(推荐):
  - 卡片持续显示在时序中 · 用户可滚动跳过
  - **优点**:与其他 Card 一致 · UI 简单
  - **代价**:错误信息一直占屏

**选项 B · 可关闭**:
  - 卡片右上角 `<CloseOutlined />` 关闭
  - **代价**:引入 dismiss 状态 · 破 events 时序一致性

**指挥官倾向**:**选项 A · 不可关闭**(TDD 语义清晰:events → 渲染,不引入 dismiss 逻辑)

**待裁定**:选项 A / B(A 推荐)

---

## 四 · 测试策略

### Q13 · TC-S5-13-1..10 测试落点组织(**阻断级**)

**建议落点**:

| TC | 落点 |
|---|---|
| TC-S5-13-1 | `frontend/tests/pages/ChatCenter.test.tsx` · 输入消息 → mock chat 返 task_id → mock SSE plan 事件 → 断言 PlanCard 出现 → click 确认 → 断言 executePlan 被调 |
| TC-S5-13-2 | `frontend/tests/pages/ChatCenter.test.tsx` · 展开 skip-to-score → 选 JD/候选人 → click 立即评分 → 断言 skipToScore 被调 + 页面显示 EXECUTING(可能通过 mock SSE progress 事件) |
| TC-S5-13-3 | `frontend/tests/components/agent/EventCards.test.tsx` · 手工构造 8 类 SSEEvent → 渲染 Card 列表 → 断言 6 类 Card 组件出现(SystemCard 不进列表 · 7 类可见 · 心跳 SystemCard 是顶部条:实际测顶部条 message) |
| TC-S5-13-4 | `frontend/tests/pages/ChatCenter.test.tsx` · msw mock SSE 断线 → 重连后同 id 事件不重复(hook 已在 PR-18 保证 · 页面消费再断一次) |
| TC-S5-13-5 | `frontend/tests/pages/ChatCenter.test.tsx` · PlanCard 出现 → click 取消 → 断言 cancelTask 被调 |
| TC-S5-13-6 | `frontend/tests/pages/CandidateChat.test.tsx` · 用 `MemoryRouter initialEntries={['/candidate-chat?candidates=a,b']}` 渲染 → 发送消息 → 断言 `chat` 请求 body 含 `context.candidate_ids: ['a', 'b']` |
| TC-S5-13-7 | 同 TC-S5-13-3 或独立 `WarningCard.test.tsx` · warning 事件 → 断言 WarningCard 显示 message |
| TC-S5-13-8 | 同 TC-S5-13-3 · 手工造 system 事件 → 断言 events 列表内不含 SystemCard · 顶部条显示 message |
| TC-S5-13-9 | `frontend/tests/pages/ChatCenter.test.tsx` · mock SSE `system:cancelled` → 断言页面显示 "已取消" 提示(非 ErrorCard) |
| TC-S5-13-10 | 同 TC-S5-13-3 或独立 `ErrorCard.test.tsx` · error 事件 → 断言 ErrorCard 显示 message |

**Q13a**:是否需要每个 Card 一个独立测试文件(8 个),还是集中 `EventCards.test.tsx` 一处?

**建议**:**集中一处** `EventCards.test.tsx` · 8 类事件 8 个 `it()` case · TC-S5-13-3/7/8/10 都落这;交互测(PlanCard 确认/取消)因涉及 API mock,落 `ChatCenter.test.tsx`

**Q13b**:msw v2 SSE mock 是否延续 PR-18 `http.get + ReadableStream` 范式?

**建议**:是 · 直接复用 `frontend/tests/hooks/useTaskStream.test.ts` 建立的 SSE mock helper(如已有,建议 extract 到 `frontend/tests/helpers/sseMock.ts` 共享)

**Q13c**:Q6 选 A 后追加的 TC-S5-13-11(hook 层 cancel terminal)落点?

**建议**:`frontend/tests/hooks/useTaskStream.test.ts` · 追加一个 `it('treats system:cancelled as terminal ...')` · 与 PR-18 TC-S5-12-1/2 同文件

**待裁定**:落点组织采纳 / 修改

---

### Q14 · 测试基线目标数(**阻断级**)

**当前基线**:20 passed(9 test files · PR-18 后)

**PR-19 计算**:
- 严格 TC-S5-13-1..10 = 10 个新用例
- 若 Q6 选 A 追加 TC-S5-13-11(hook cancel terminal)= +1 用例

**目标 N_after**:
- Q6=A 采纳:`20 + 11 = 31 passed`
- Q6=B 不改 hook:`20 + 10 = 30 passed`

**新 test files 数**:预估 +4 files(`ChatCenter.test.tsx` / `CandidateChat.test.tsx` / `EventCards.test.tsx` / `hooks/useTaskStream.test.ts` 追加不算新 file)→ 若追加 hook TC 则新增 3 files;若不追加则新增 3 files

**Q14**:确认 N_after 目标(基于 Q6 结果计算);是否允许追加 TC-S5-13-11?

**指挥官倾向**:**Q6=A 采纳 → N_after = 31 passed · 8 test files(6 既有 + 3 新) → 12 total test files**

**待裁定**:N_after 数字确认

---

## 五 · 边角问题

### B1 · `react-hooks/exhaustive-deps` 8 处 warning 顺手补齐

**事实**:TASKS-STAGE5 §五 清扫项(线号 293):
> `react-hooks/exhaustive-deps` warning | **PR-19**(S5-13) | 顺手补齐依赖数组(既有 8 处,部分与 Stage 5 新增 hook 相关)

**问题**:PR-19 是否顺手补?

**建议**:**采纳 · 顺手补齐所有 8 处**。理由:
1. TASKS §五 明确列出 · 不补是违反 TASKS
2. lint 0 warning 是干净标准
3. 逐处评估:如是数据 hook 忘 deps 就补;如是 unmount cleanup 类不能加 deps 的加 eslint-disable-next-line 注释说明

**风险**:补 deps 可能引入无限 re-render;需逐处小心评估;若某处补 dep 后测试挂,回滚该处、注释解释

**待裁定**:B1 采纳 / 保留基线 · 若采纳则加 STEP6 报告基线到 0 warnings

---

### B2 · MSW stderr 噪声(PR-18 STEP6 §未消化)

**事实**:PR-18 STEP6 基线 8 warnings 里 MSW 是否有 stderr 噪声?TASKS §五 已列 PR-18 归属 · PR-18 未做

**建议**:PR-19 顺手排查一次 · 若 MSW logger 可静音则设置(`worker.start({onUnhandledRequest: 'bypass'})` 或 `server.listen({onUnhandledRequest: 'error'})` 之类的 vitest.setup.ts 调整);若排查发现 MSW 无稳定 mute 途径则回滚记录

**待裁定**:B2 采纳评估 / 跳过

---

### B3 · `agentApi` 是否扩展(如 `getTasks()` 列表)?

**事实**:PR-18 交付 5 函数(chat/executePlan/skipToScore/cancelTask/getTask)· 无 list 端点

**问题**:PR-19 是否引入「历史任务列表」?

**建议**:**不引入**。理由:
1. TASKS §S5-13 未要求列表页
2. Stage 5.1 可能补 · PR-19 不预制

**待裁定**:B3 不扩展(推荐)

---

### B4 · 前端渲染代码 mock 后端事件序列的 fixture 位置

**建议**:`frontend/tests/fixtures/sseEvents.ts` 集中导出 6 类事件工厂函数(`makeThinkingEvent()`, `makePlanEvent()`, ...),供 `EventCards.test.tsx` 与 `ChatCenter.test.tsx` 共享

**待裁定**:采纳 fixture 位置

---

### B5 · PR-19 base ref

**建议**:base = `origin/master` = **`9a6554e`**(当前 HEAD)· 与 PR-18 base = `646efad` 类似,不冻结

**若 kickoff docs 后再合入其他:**PR-19 执行体开工时用当时 master HEAD,与 PR-18 处理一致(§求助边界 clause 1 逻辑同步)

**待裁定**:B5 采纳

---

### B6 · commit 拆分建议(执行体阶段)

**建议 5 commit 结构**(参考 PR-18 4 commit + 若 Q6=A 增加 hook 改 commit):

1. `test(stage5): PR-19 red-test skeleton (TC-S5-13-1..10 [+11]) + Card scaffold`(全部测试用 `test.skip` 或 `test.fails`)
2. `feat(stage5): S5-13 Card 组件基座 + agent/artifacts 6 子渲染器 + never assertion`(TC-S5-13-3 转绿)
3. `feat(stage5): S5-13 ChatCenter 页面 + 消息时序 + PlanCard 交互`(TC-S5-13-1/5 转绿)
4. `feat(stage5): S5-13 CandidateChat 页面 + skip-to-score 快捷 + CandidateChat 入口按钮`(TC-S5-13-2/6/9 转绿)
5. `feat(stage5): S5-13 hook cancel terminal 扩展 + WarningCard/ErrorCard + system 顶部条`(TC-S5-13-4/7/8/10 + TC-S5-13-11 转绿)

若 Q6=B 不改 hook:合并 4 commit,commit 5 内容分并入 3/4

**注意**:与 PR-18 一样 · vitest `test.fails` 严格语义,commits 转绿时需增量移除 `.fails`(执行体应能处理)

**待裁定**:5 commit 结构采纳 / 调整

---

### B7 · FF-merge 后待更新文档清单

参考 PR-18 §十二 · PR-19 合入后需刷:

1. `HANDOFF.md §9.1` 状态表:PR-19 = ✅(final commit); master HEAD 更新
2. `HANDOFF.md §9.3` 追债项 3:标记「PR-19 收敛(exhaustiveness 护栏激活)」
3. `HANDOFF.md §9.4` 陷阱 10:若 Q6=A 则更新为「PR-19 已扩展 hook 终态判定」,标记收敛;若 Q6=B 则保留为已知边界
4. `HANDOFF.md §9.5` 新文件表:追加 ~10 新文件(2 pages + 8 Cards + 6 artifacts + 3 tests + fixture)
5. `HANDOFF.md §9.6` 改写为 **Stage 5 收官声明**(Stage 5.1 待启动)
6. `TASKS-STAGE5.md §S5-13` owner → PR-19;§五 清扫项 B1/B2 状态更新
7. 记忆 `stage5-progress-and-known-limits.md`:PR-19 合入 · 前端基线 30/31 passed · Stage 5 前端全量落地

**待裁定**:B7 采纳

---

## 六 · §求助边界(执行体停下并报告)

**建议 11 clauses**(参考 PR-18 结构):

1. **仓库状态偏移**:master ≠ 起手 HEAD(9a6554e)、或工作树不干净 → 停下汇报
2. **前端 test 基线丢失**:开工前跑 `npm run test` 若 ≠ 20 passed → 停下汇报
3. **msw v2 SSE mock 失败**:如 fetch stream 在 PR-19 更复杂场景下 mock 有故障 → 停下汇报
4. **PlanCard 交互与后端契约冲突**:如 `executePlan({task_id})` 空 body 后端 raise 400 而非默认全接受 → 停下汇报(Q4 需 DECISION 显式确认)
5. **追债项 3 exhaustiveness 未激活**:如 6 子渲染器未真正落到 switch/never 分支 → 停下汇报
6. **前端 test 基线倒退**:任何时刻 test 数减少 → 停下汇报
7. **顺手扩范围**:若发现 TASKS §S5-13 之外的改动诱惑(比如加多任务列表页) → 停下汇报
8. **B1 补 deps 后测试挂**:某处补 deps 引入 re-render loop → 立即回滚该处 · 加 eslint-disable-next-line 注释,报告
9. **hook 终态判定改动导致 PR-18 用例回归**:Q6=A 采纳后修改 useTaskStream,若 PR-18 TC-S5-12-1..4 挂 → 停下汇报(不许强改 PR-18 测试)
10. **误触 `backend/app`**:PR-19 应为纯前端 PR · 若诱惑改后端(如为 cancel UX 让后端改发 error 事件)→ 停下汇报
11. **artifact 子渲染器格式误判**:若前端不知道某类 artifact.data 具体字段(需读后端 skill 输出 example) → 停下汇报,不猜结构

**待裁定**:11 clauses 采纳 / 修改

---

## 七 · 汇总裁定表

| # | 问题 | 建议 | 需裁定? |
|---|---|---|---|
| **§〇 PR 范围** | | | |
| Q1 | PR-19 边界 | A · 严格 S5-13 全量 | ✅ |
| **§一 阻断级** | | | |
| Q2 | 状态管理选型 | A · 纯 useState | ✅ |
| Q3 | 任务态跨刷新 | A · 不做持久化 | ✅ |
| Q4 | PlanCard 交互 | A · 最小可用(确认全接受 + 取消) | ✅ + 需确认后端空 body |
| Q5 | SystemCard/心跳 UI | A · 顶部横条 | ✅ |
| Q6 | system:cancelled 边界 | A · 修改 hook + TC-S5-13-11 | ✅ + 追加 TC 授权 |
| Q7 | 追债 3 exhaustiveness | A · 全 6 子渲染器 + never | ✅ |
| **§二 页面** | | | |
| Q8 | ChatCenter 布局 | 采纳 · skip 默认收起 | ✅ |
| Q9 | skip-to-score UI | A · Antd Select 双下拉 | ✅ |
| Q10 | CandidateChat 入口 | A · URL query + CompareAnalysis 附加按钮 | ✅ + 附加改动授权 |
| **§三 Card 设计** | | | |
| Q11 | Card 目录组织 | 采纳建议目录 + Antd Card | ✅ |
| Q12 | Warning/Error 关闭 | A · 不可关闭 | ✅ |
| **§四 测试** | | | |
| Q13 | TC 落点组织 | 集中 EventCards.test.tsx + ChatCenter.test.tsx + CandidateChat.test.tsx | ✅ |
| Q14 | N_after 目标 | 31 passed(Q6=A) | ✅ |
| **§五 边角** | | | |
| B1 | 补 8 处 exhaustive-deps | 采纳(顺手补) | ✅ |
| B2 | MSW stderr | 顺手评估 | ✅ |
| B3 | agentApi 扩展 | 不扩展 | ✅ |
| B4 | fixture 位置 | tests/fixtures/sseEvents.ts | ✅ |
| B5 | base ref | 9a6554e | ✅ |
| B6 | commit 拆分 | 5 commit(Q6=A) | ✅ |
| B7 | FF-merge 待更新文档 | 采纳 7 项 | ✅ |
| **§六 §求助** | | | |
| C1..C11 | 11 clauses | 采纳建议 | ✅ |

---

## 八 · 结语

- PR-19 是 **Stage 5 前端收官 PR** · 交付面 ~10 pages/Cards + ~4 test files + 追债 3 收敛 + 8 warnings 清扫
- 建议裁定后由**副指挥官** produce `PR19-KICKOFF-REVISIONS.md`(参考 PR-18 REVISIONS 结构),标注硬矛盾/边角建议吸收
- 指挥官综合评估 REVISIONS 后 produce `PR19-KICKOFF-DECISION.md`(参考 PR-18 DECISION 12 章结构),作为**唯一实施契约**
- 执行体阶段 4-5 commit TDD 落地 · 目标 N_after = 31 passed / 0 warnings / build ✓

**待用户裁定 22 个问题(Q1-Q14 + B1-B7 + 边界 C 集合)+ 附加授权:Q4 后端空 body 确认 + Q6 追加 TC 授权 + Q10 CompareAnalysis 附加改动授权**。
