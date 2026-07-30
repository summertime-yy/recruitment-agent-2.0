# PR-27 · KICKOFF-QUESTIONS

> 关联：`docs/planning/stage5/MVP-VERIFY-RUN-REPORT.md` §4.1 复跑发现 · HANDOFF §9.3（本 PR 后新登记 §9.3.21）
> 起始 master HEAD：`44a5a07`（PR-26 §9.3.20 CLOSED · hydration middleware 落定）
> 上一轮验收 baseline：pytest **145 passed / 2 skipped** · ruff 0 全仓 · frontend `npm test` **待复核**（预计 31 passed 沿用 PR-23 baseline） · frontend build ✓
> 类型：**代码 PR · 纯前端 scope**（无后端改动 · feat 分支 · red-test · commit split · FF-merge）
> 分支建议：`feat/pr-27-fix-candidatechat-and-entry`
> 求助边界：继承 AGENTS.md / CLAUDE.md 通用 + 本 PR 增补（§Q6）

---

## §背景（QUESTIONS 之前 · 三条冷酷事实）

1. **`CandidateChat.tsx` 是空壳（39 行）**：接 URL `?candidates=a,b`、有输入框、发 `agentApi.chat({message, context:{candidate_ids}})` —— 但 **丢弃返回的 `res.task_id`**（`frontend/src/pages/CandidateChat.tsx:17` `await agentApi.chat(...)` 无 `setTaskId`），**不渲染 StreamStatusBar / MessageTimeline / TaskStream / PlanCard**。用户点"发送"什么都看不到，感觉 UI 挂了；实际后端 task 已跑（PR-25 后能 GET · PR-26 后能过 dispatch），只是前端不接。
2. **`/candidate-chat` 路由无任何入口**：全仓 grep `<Link.*candidate-chat` / `navigate.*candidate-chat` / `href=.*candidate-chat` **均无结果**。只有 `frontend/src/App.tsx:81` 注册了路由（`<Route path="/candidate-chat" element={<CandidateChatPage />} />`）。**用户不知道怎么走到这个页面**——需要手工敲 URL 才能到。这是 MVP-VERIFY §4.1 之外的"入口 0"问题。
3. **`ChatCenter.tsx` 相对完整**：`SkipToScorePanel` + `TaskStream`（`StreamStatusBar` + `MessageTimeline` + PlanCard 确认/取消）+ 消息输入框 · `handleSend` 正确保存 `task_id` 并渲染。**本 PR 无需改 ChatCenter**（除非 §Q2 决定给它加显性 skip-to-score 提示，但那是 UX 增强不是 bug）。

> **Bug C 精确定位**：不是"ChatCenter 挂了"，而是「CandidateChat 是死链 + 空壳」双重问题。

---

## §Q1 · CandidateChat 从"stub"变"活" 的三选一：**复用 ChatCenter 组件 · 独立实现 · CandidateChat 弃用回归 ChatCenter**

**建议**：**A · 抽 `TaskStream` 为可复用组件 + `CandidateChat` 内嵌**

CandidateChat 目前有独立需求（预填 `candidate_ids` context），不能直接 `<Route path="/candidate-chat" element={<ChatCenter/>} />`。选择：

| 方案 | 内容 | 优 | 缺 |
|------|------|-----|-----|
| **A · 抽 TaskStream 组件（我建议）** | 把 `ChatCenter.tsx` 内的 `TaskStream({taskId})` 组件（当前是本地函数）提到 `frontend/src/components/agent/TaskStream.tsx` · 导出复用 · CandidateChat 拿 taskId 后 `<TaskStream taskId={taskId} />` | 单一实现 · 未来第三个 chat 页面也能复用 · DRY | 挪动一次代码 · 需微调 ChatCenter 内部引用（一行 import 变更） |
| B · CandidateChat 内联复制 StreamStatusBar+MessageTimeline+按钮回调 | 复制 15 行代码到 CandidateChat | 不动 ChatCenter | 双份维护 · 未来 PlanCard/TaskStream 改动要改两处 · 未来必然漂移 |
| C · 路由合并 · CandidateChat 弃用 · 只保 `/chat` 一个入口 | 删 CandidateChat.tsx + 路由 + Resumes 页加"从选中候选人开启对话"按钮 → navigate(`/chat?candidates=a,b`) → ChatCenter 读 URL 参数注入 context | 单页面 · 最简 · 无碎片 | 需改 App.tsx 路由 + ChatCenter 加 URL 参数解析 + 现有 CandidateChat.test.tsx 全废重写（TC-S5-13-6 契约 broken） |

**议题**：**A（我建议）** / B / C？

---

## §Q2 · CandidateChat 的入口在哪里加

**建议**：**A · Resumes 页多选后加"批量对话/画像"按钮**

`/candidate-chat` 现在无任何入口。三选一：

| 方案 | 内容 | 优 | 缺 |
|------|------|-----|-----|
| **A · Resumes 页批量选择 + "AI 对话/画像"按钮**（我建议） | Resumes.tsx 已有 selectedResume state（`Resumes.tsx:96`，目前是单选）· 扩到多选 checkbox · 加按钮 `navigate('/candidate-chat?candidates=' + selectedIds.join(','))` | 最自然的用户流（先选人 → 后对话） · 与 §4.1 UI 手工验收流一致 | 需扩 Resumes 表格多选逻辑（+~40 行） · 增 1 个测试 |
| B · 主菜单/顶部导航加"候选人对话"入口 | 需要在 layout / menu 层加固定入口 · 但候选人对话没有候选人上下文是无意义的 | 简单 | 无候选人时点开是死链（要求用户先去选人） · UX 差 |
| C · Resumes 详情页加"发起画像对话"单人入口 · 不做批量 | 只支持单人 chat · 多人对话（candidate-merge）仍无路径 | 最小改动 | 阻塞 §4.2 merge 路径 UI 验收 · Bug C 不完全修 |

**议题**：**A（我建议）** / B / C？

---

## §Q3 · URL 参数解析 · CandidateChat 空 `candidates=` 行为

**建议**：**A · 空 candidates 直接引导用户去 /resumes 选人**

现状 `CandidateChat.tsx:16` 是 `if (!text || candidateIds.length === 0) return;` —— 默默 no-op，用户看不到任何反馈。三选一：

| 方案 | 内容 | 优 | 缺 |
|------|------|-----|-----|
| **A · 空 candidates 显示空态引导**（我建议） | `if (candidateIds.length === 0)` 渲染 antd `<Empty>` 组件 · 描述"请先在候选人列表选择要对话的候选人" · 加 `Button` 跳 `/resumes` | 用户不会看到"点了没反应" · UX 完整 | +~10 行 · +1 空态测试 |
| B · 允许空 candidates · 走通用 chat（无 context） | 让用户在 CandidateChat 里发通用消息 · context 为空 | 灵活 | 与 CandidateChat 页面语义冲突（叫"候选人对话"却没候选人） · 用户误以为一样功能 |
| C · 空 candidates 直接 redirect `/resumes` | 挂载即跳 | 最少代码 | 用户不知为啥跳 · 更迷惑 |

**议题**：**A（我建议）** / B / C？

---

## §Q4 · 测试面（Vitest · TDD strict · 期望 npm test total）

**建议**：**A · 4 个 TC**

测试用例草案（若 §Q1 选 A + §Q2 选 A + §Q3 选 A）：

- **TC-PR27-1**（CandidateChat 活化）：URL `?candidates=a,b` · 输入消息 → 发送 → `agentApi.chat` 返回 `task_id: 't1'` · 断言页面渲染 `<StreamStatusBar>` + `<MessageTimeline>`（找 `data-testid` 或角色文本） · 断言 `useTaskStream({taskId: 't1'})` 被激活。
- **TC-PR27-2**（CandidateChat 空态）：URL `?candidates=` 或缺参 · 断言渲染 antd `<Empty>` + "去候选人列表选择" 按钮 · 点按钮 → navigate `/resumes`（用 MemoryRouter + navigate spy）。
- **TC-PR27-3**（Resumes 多选批量对话入口）：Resumes 页有多个 resume 行 · 勾选 2 个 · 点"AI 对话/画像"按钮 → navigate `/candidate-chat?candidates=<id1>,<id2>` · 断言 URL 携带正确 candidates。
- **TC-PR27-4**（既有回归：ChatCenter 与 TaskStream 组件抽取后不破 TC-S5-13-*）：跑既有 ChatCenter.test.tsx 全部 case · 全绿。

**期望终值**：`npm test` → **35 passed**（31 baseline + 4 PR-27） · `npm run build` 通过。

**议题**：认可这 4 个 TC？还是要增/减/调整？

---

## §Q5 · Commit split（TDD strict）

**建议**：**A · 4 commit split**

commit 序列：
1. `test(pr-27): red-test skeleton for TC-PR27-1..3 (all failing)` —— 3 新测试骨架
2. `refactor(agent): extract TaskStream component from ChatCenter for reuse` —— 抽组件（TC-PR27-4 回归）
3. `feat(candidate-chat): activate CandidateChat with TaskStream + empty state · Resumes bulk entry` —— 实现 CandidateChat 活化 + Resumes 入口
4. `test(pr-27): green tests TC-PR27-1..4 pass` —— 转绿
5. （合并进 4）或单独 `docs(stage5): PR-27 STEP6 report + HANDOFF §9.3.21`

**分支**：`feat/pr-27-fix-candidatechat-and-entry`

**议题**：认可这个 split？（若需微调命名或粒度，告诉我）

---

## §Q6 · 求助边界（继承 AGENTS.md / CLAUDE.md 通用 + PR-27 增补）

**继承（不复述）**：AGENTS.md + CLAUDE.md 通用 stop-and-ask + PR-25/26 已定基调。

**PR-27 增补**（触及必停）：

1. **抽 `TaskStream` 组件后既有 ChatCenter.test.tsx 里 antd `useToken` / `ConfigProvider` 类的 context 依赖挂**：说明组件抽离带出了隐式 hooks 依赖 · 停 · 报现象 · **不擅自** 在新组件里 mock context。
2. **Resumes.tsx 现有单选状态 `selectedResume` 与新引入的多选状态冲突**：说明 UX 现有分岔 · 停 · 报回是"改造成多选（可能破 Resumes 现有测试）"还是"新增独立多选 checkbox 列共存"。
3. **既有 `CandidateChat.test.tsx` (TC-S5-13-6) 契约与 §Q1 A 方案产物冲突**（比如新组件挂载后原有 `agentApi.chat` 调用签名变了）：停 · 报回是修测试还是调实现，**不擅自** 改测试断言。
4. **PR-27 完工后 `/candidate-chat?candidates=a,b` 手工浏览器验收：`agentApi.chat` 返回 `task_id` 但 SSE 流永远不出 tool_call 事件**：说明是后端 dispatch/hydration 侧新暴露的 bug（**不是 PR-27 scope**）· 停 · 登记 §9.3 · 不擅自扩到后端。

**议题**：4 条边界够吗？还是要补？

---

## §附 · 落地文件清单（供 DECISION 阶段固化）

**新建**：
- `frontend/src/components/agent/TaskStream.tsx`（从 ChatCenter.tsx 抽出）

**改造**：
- `frontend/src/pages/CandidateChat.tsx`（+~30 行：taskId state + TaskStream 挂载 + 空态 Empty）
- `frontend/src/pages/ChatCenter.tsx`（-~20 行 TaskStream 本地函数 + 改 import）
- `frontend/src/pages/Resumes.tsx`（+~40 行多选 checkbox + 批量按钮 + navigate）

**新增测试**：
- `frontend/tests/pages/CandidateChat.test.tsx`（增 TC-PR27-1 · TC-PR27-2 两条）
- `frontend/tests/pages/Resumes.entry.test.tsx`（新文件 · TC-PR27-3 一条）
- 既有 `ChatCenter.test.tsx` / `CandidateChat.test.tsx` 原 TC-S5-13-6 保绿（TC-PR27-4）

---

## §附 · PR-27 之后（供你排 MVP demo 收尾）

- **MVP-VERIFY §4.1 / §4.2 / §4.3 全流程 3 节 · 浏览器 e2e 补跑** —— Bug A/B/C 都合完后做（这才是真正的 demo-ready 判据）
- **§9.3.19**（LLM context 提取非确定性）—— 独立 PR-28 挂账 · 非 MVP demo 阻塞项
- **§9.3.15**（Artifact codegen CI/pre-commit 校验）—— Stage 5.1 尾债 · 独立

---

**指挥官回议题即可**（§Q1..§Q6 每题给个字母或"其它+说明"），我把 DECISION 起草出来 + 给执行体的一句话指令一并交给你。
