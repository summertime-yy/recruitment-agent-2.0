# PR-19 STEP6 执行报告

S5-13 前端 ChatCenter / CandidateChat / 8 事件卡片 · 5 commit TDD

---

## §一 概述

- **分支**：`feat/pr-19-s5-13-frontend-chat-cards`
- **base**：`origin/master` @ `76e73bb`（PR-18 S5-12 已合入）
- **提交数**：5（4 feat + 1 fix），strict TDD
- **变更文件**：18 frontend 文件（15 src + 3 test），0 backend 文件

---

## §二 三道门验证

| 门 | 指标 | 状态 |
|----|------|------|
| 测试 | 12 files / 31 passed / 0 expected fail | ✓ |
| Lint | 0 errors / 8 warnings（均预先存在，本项目无新增） | ✓ |
| Build | `tsc -b && vite build` ✓ | ✓ |

---

## §三 实现细节

### Commit 1 — 红测骨架
11 个 `test.fails`（ChatCenter x5、EventCards x4、CandidateChat x1、useTaskStream x1）；25 个 stub 文件（11 组件 + 6 artifact stub + fixtures/helpers + 2 page stub + 1 hook stub）。基线：20 passed + 11 expected fail = 31。

### Commit 2 — 卡片基座 + artifact 渲染器
实现 7 事件 Card（Thinking/ToolCall/Progress/Error/Warning/System/Plan）+ CardContainer；MessageTimeline 8→7 映射（system 不进列表）；6 artifact 子渲染器含 `never` 穷尽 switch；StreamStatusBar。剥离 4 个 EventCards `.fails` → 24 passed + 7 expected fail。

### Commit 3 — PlanCard 交互 + ChatCenter 装配
PlanCard 加「确认执行/取消」按钮（受 `onConfirm`/`onCancel` 回调控制）；StreamStatusBar 从 `systemMessage==='cancelled'` 推导 isCancelled；ChatCenter 完整实现（MessageInput + useTaskStream + SkipToScorePanel + plan confirm/cancel wiring）。剥离 5 个 ChatCenter `.fails`。

测试查询适配 antd v5 行为：
- 中文 Button 空格（`发送`→`发 送`），用 `cnBtn()` 辅助
- Select 占位符为 `<span>`（pointer-events:none），用 `closest('.ant-select-selector')` 点击
- TC-S5-13-4 重连 waitFor 用 8s 超时匹配 hook 退避 3000ms

### Commit 4 — CandidateChat 页面
解析 URL `?candidates=a,b` → candidate_ids；发送消息携带 `context.candidate_ids`。剥离 TC-S5-13-6 `.fails` → 30 passed / 1 expected fail。

### Commit 5 — system:cancelled 终态
useTaskStream 处理 `system` 事件时，若 `data.message === 'cancelled'` 设 `hasReachedTerminalRef + closedRef`，流结束不再重连。剥离 TC-S5-13-11 `.fails` → 31 passed / 0 expected fail。

---

## §四 文件影响

| 文件 | 变更 |
|------|------|
| `src/components/agent/PlanCard.tsx` | 新增按钮 + Button/Space import |
| `src/components/agent/StreamStatusBar.tsx` | cancelled 推导 |
| `src/components/agent/MessageTimeline.tsx` | onPlanConfirm/onPlanCancel 透传 |
| `src/components/agent/CardContainer.tsx` | 实现（shared wrapper） |
| `src/components/agent/*Card.tsx` (7) | 7 卡片实现 |
| `src/components/agent/artifacts/*.tsx` (6) | artifact 渲染器 + never switch |
| `src/components/agent/artifacts/index.ts` | barrel |
| `src/components/agent/index.ts` | barrel |
| `src/pages/ChatCenter.tsx` | 完整实现 |
| `src/pages/CandidateChat.tsx` | 完整实现 |
| `src/hooks/useTaskStream.ts` | system:cancelled 终态 |
| `tests/components/agent/EventCards.test.tsx` | 剥离 .fails + search_resumes scoped |
| `tests/pages/ChatCenter.test.tsx` | 剥离 .fails + antd v5 query fixes + fireEvent 清理 |
| `tests/pages/CandidateChat.test.tsx` | 剥离 .fails + 发送→regex |
| `tests/hooks/useTaskStream.test.ts` | 剥离 .fails |
| `tests/fixtures/sseEvents.ts` | 新建 |
| `tests/helpers/sseMock.ts` | 新建 |

---

## §五 声明 & 观察

1. **TDD 严格性**：5 commit 均按红→绿→提交顺序，`test.fails` 在实现完成后剥离。
2. **antd v5 适配**：3 处测试查询因 antd 行为（Button 空格、Select 占位符格式、selector trigger）而调整，属正确的测试层适配，非组件 bug。
3. **hook 终态扩展**：Commit 5 的 `system:cancelled` 终态是对 S5-12 已合代码的增量扩展，遵循 `hasReachedTerminalRef` + `closedRef` 双 ref 标记模式。
4. **baseline hash**：base 实为 `76e73bb`（DECISION 误写 `9a6554e`→已因 PR-18 合入而漂移）。
5. **Revisions 文档所有 A/B/C 类建议均已落地**（Q6 cancalled 终态、Q7 artifact 穷尽 switch、Q9 数据源等）。

---

## §六 求助边界
DECISION §十八 11 条求助全部未触发（执行期间无阻塞）。

---

## §七 用例表

| 编号 | 描述 | Commit | 状态 |
|------|------|--------|------|
| TC-S5-13-1 | send → plan → confirm executePlan | 3 | ✓ |
| TC-S5-13-2 | skip-to-score panel → skipToScore called | 3 | ✓ |
| TC-S5-13-3 | 8 类事件 → 7 Card timeline | 2 | ✓ |
| TC-S5-13-4 | SSE disconnect/reconnect → dedup | 3 | ✓ |
| TC-S5-13-5 | PlanCard cancel → cancelTask | 3 | ✓ |
| TC-S5-13-6 | CandidateChat URL ?candidates → chat.context | 4 | ✓ |
| TC-S5-13-7 | WarningCard 渲染 → message | 2 | ✓ |
| TC-S5-13-8 | system 事件 → 顶部条 message, 不进 timeline | 2 | ✓ |
| TC-S5-13-9 | system:cancelled stream → 「已取消」 | 3 | ✓ |
| TC-S5-13-10 | ErrorCard 渲染 → message | 2 | ✓ |
| TC-S5-13-11 | system:cancelled → status closed, no reconnect | 5 | ✓ |

---

## §八 提交链与 FF-merge 指引

```
e250c9f fix(stage5): system:cancelled terminal
7218a02 feat(stage5): CandidateChat page
32342fa feat(stage5): PlanCard + ChatCenter assembly
222032d feat(stage5): Card base + artifact renderers + StreamStatusBar
416b73a test(stage5): red-test skeleton + scaffolds
76e73bb docs(stage5): PR-19 kickoff decision (BASE)
```

**FF-merge**：`git fetch origin && git merge --ff-only origin/feat/pr-19-s5-13-frontend-chat-cards`

**合并后必做**（指挥官职责，执行体不做）：
- HANDOFF.md §9.1 / §9.3 / §9.4 / §9.5 / §9.6 更新
- TASKS §S5-12 / §S5-13 owner 更新
