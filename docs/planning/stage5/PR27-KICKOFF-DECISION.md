# PR-27 · KICKOFF-DECISION

> 关联：`PR27-KICKOFF-QUESTIONS.md`（commit `ce66300`）· MVP-VERIFY §4.1 Bug C · HANDOFF §9.3.21（本 PR 完成后登记）
> 起始 master HEAD：`ce66300`（PR-27 QUESTIONS 落 master 后）
> 上一轮验收 baseline：pytest **145 passed / 2 skipped** · ruff 0 全仓 · frontend `npm test` **31 passed**（PR-23 baseline · 执行体先复核）· frontend build ✓ · migration head `b6c7d8e9f0a1`
> 类型：**代码 PR · 纯前端 scope**（feat 分支 · red-test · commit split · FF-merge）
> 分支：`feat/pr-27-fix-candidatechat-and-entry`
> QUESTIONS 应答（指挥官 · 2026-07-30）：**Q1–Q6 全部采纳我的建议 A**（Q4 认可 4 TC · Q6 认可 4 边界）

---

## §一 · 背景（不复述 QUESTIONS · 只给三点确认事实）

1. **`CandidateChat.tsx` 是空壳（39 行）**：接 URL `?candidates=a,b` · 有输入框 · 发 `agentApi.chat` —— 但丢弃 `res.task_id`（`frontend/src/pages/CandidateChat.tsx:17`）· **不渲染 TaskStream**。用户点发送看不到任何反馈。
2. **`/candidate-chat` 路由无任何入口**：`App.tsx:81` 注册路由 · 全仓 0 处链接跳转。**只能手工敲 URL 才能到**。
3. **`ChatCenter.tsx` 已完整**：`SkipToScorePanel` + `TaskStream({taskId})` + 输入框 · `handleSend` 正确保 `task_id` · 本 PR **不改 ChatCenter 主体**（只从中抽 `TaskStream` 组件外提）。

---

## §二 · 方案裁定（QUESTIONS §Q1..§Q3 一次性锁定）

| 议题 | 裁定 | 一句话理由 |
|------|------|------------|
| Q1 CandidateChat 活化 | **A · 抽 TaskStream 组件复用** | 单一实现 · DRY · 未来第三个 chat 页面也能复用 |
| Q2 入口位置 | **A · Resumes 页多选 + "AI 对话/画像" 按钮** | 最自然用户流（先选人 → 后对话） · 与 §4.1 UI 手工流一致 |
| Q3 空 candidates 行为 | **A · 渲染 `<Empty>` + 跳 /resumes 按钮** | 用户不会看到"点了没反应" · UX 完整 |

---

## §三 · 落地细节

### §三.1 · 抽 `TaskStream` 为独立组件

**位置**：新建 `frontend/src/components/agent/TaskStream.tsx`

**内容**：把 `ChatCenter.tsx:15-33` 的本地 `TaskStream({taskId})` 函数原样搬入 · 导出为默认 export。签名保持 `{ taskId: string }`。

**骨架**：
```tsx
// PR-27 · 从 ChatCenter 抽出的复用组件。
import { useCallback } from 'react';
import { useTaskStream } from '@/hooks/useTaskStream';
import { agentApi } from '@/services/agent';
import { StreamStatusBar } from './StreamStatusBar';
import { MessageTimeline } from './MessageTimeline';
import type { SystemData } from '@/types/agent';

export interface TaskStreamProps {
  taskId: string;
}

export function TaskStream({ taskId }: TaskStreamProps) {
  const { events, latestByType } = useTaskStream({ taskId });
  const systemMessage = (latestByType.system?.data as SystemData | undefined)?.message;
  const handleConfirm = useCallback(() => {
    void agentApi.executePlan({ task_id: taskId });
  }, [taskId]);
  const handleCancel = useCallback(() => {
    void agentApi.cancelTask(taskId);
  }, [taskId]);
  return (
    <>
      <StreamStatusBar systemMessage={systemMessage} />
      <MessageTimeline events={events} onPlanConfirm={handleConfirm} onPlanCancel={handleCancel} />
    </>
  );
}

export default TaskStream;
```

**ChatCenter.tsx 改动**：
- 删本地 `function TaskStream(...)` 定义（`ChatCenter.tsx:15-33`）
- 顶部 `import { TaskStream } from '@/components/agent/TaskStream'`
- `<TaskStream key={taskId} taskId={taskId} />` 用法不变

### §三.2 · CandidateChat.tsx 活化

**改造后完整结构**：

```tsx
// PR-27 · CandidateChat 活化：接 TaskStream + 空态引导。
import { useCallback, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button, Empty, Input, Space } from 'antd';
import { agentApi } from '@/services/agent';
import { TaskStream } from '@/components/agent/TaskStream';

const CandidateChat: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const params = new URLSearchParams(location.search);
  const candidateIds = (params.get('candidates') ?? '').split(',').filter(Boolean);

  const [message, setMessage] = useState('');
  const [taskId, setTaskId] = useState<string | null>(null);

  const handleSend = useCallback(async () => {
    const text = message.trim();
    if (!text || candidateIds.length === 0) return;
    const res = await agentApi.chat({ message: text, context: { candidate_ids: candidateIds } });
    setTaskId(res.task_id);
    setMessage('');
  }, [message, candidateIds]);

  // Q3-A · 空 candidates 空态引导
  if (candidateIds.length === 0) {
    return (
      <div style={{ padding: 16 }}>
        <Empty description="请先在候选人列表选择要对话的候选人">
          <Button type="primary" onClick={() => navigate('/resumes')}>
            去候选人列表选择
          </Button>
        </Empty>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, maxWidth: 720 }}>
      {taskId && <TaskStream key={taskId} taskId={taskId} />}
      <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
        <Input.TextArea
          placeholder="输入消息..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={3}
        />
        <Button type="primary" onClick={handleSend}>
          发送
        </Button>
      </Space>
    </div>
  );
};

export default CandidateChat;
```

**关键约束**：
- **保留** 现有 TC-S5-13-6 断言的 `agentApi.chat({message, context:{candidate_ids}})` 调用签名（不改）
- **不改** placeholder `"输入消息..."` 文本、"发送" 按钮文本（既有测试选择器依赖）
- **新增** `setTaskId(res.task_id)` + `<TaskStream />` 挂载（活化本体）
- **新增** `Empty` 空态分支（在 hooks 之后 · 遵 React hooks 规则 · 早 return 前 hooks 已全部调用）

### §三.3 · Resumes.tsx 批量入口

**位置**：`frontend/src/pages/Resumes.tsx`

**改造内容**（增量式 · 不破现有单选 `selectedResume` 状态）：
- 新增 state：`const [checkedResumeIds, setCheckedResumeIds] = useState<string[]>([]);`
- Resume 表格新增 `rowSelection` prop（antd Table 内置多选 checkbox 列）：
  ```tsx
  rowSelection={{
    selectedRowKeys: checkedResumeIds,
    onChange: (keys) => setCheckedResumeIds(keys as string[]),
  }}
  ```
- 在表格上方（或工具栏区域）新增按钮：
  ```tsx
  <Button
    type="primary"
    disabled={checkedResumeIds.length === 0}
    onClick={() => navigate(`/candidate-chat?candidates=${checkedResumeIds.join(',')}`)}
  >
    AI 对话 / 画像（{checkedResumeIds.length}）
  </Button>
  ```
- 若已有 `useNavigate` 引用则复用；无则顶部加 `const navigate = useNavigate();`

**关键约束**：
- **不改** 现有单选 `selectedResume` 语义（详情面板逻辑保持）· 多选与单选**独立共存**（§Q6 边界 2 已锁定策略：**共存 · 不改造既有单选** —— 若冲突则触边界停）
- **不改** 表格现有列定义 / 现有筛选 / 现有分页

### §三.4 · 测试面（TDD strict · 4 TC · QUESTIONS §Q4 逐字采纳）

**新增文件**：`frontend/tests/pages/Resumes.entry.test.tsx`（TC-PR27-3 独立文件 · 与既有 `Resumes.match.test.tsx` 不冲突）

**追加到既有文件**：`frontend/tests/pages/CandidateChat.test.tsx` 追加 TC-PR27-1、TC-PR27-2 两个 `test(...)` block（保留原 TC-S5-13-6 · 该测试即 TC-PR27-4 回归的一部分）

- **TC-PR27-1 · `CandidateChat activated: URL ?candidates=a,b + send → TaskStream renders with taskId`**：
  MemoryRouter `initialEntries=['/candidate-chat?candidates=a,b']` · msw mock `POST /agent/chat` 返回 `{task_id:'t1', status:'PLANNING'}` · type message + click "发送" · 断言 `<StreamStatusBar>` 挂载（可用 `screen.findByTestId('stream-status-bar')` 或角色文本，视既有组件 markup） · 断言 `useTaskStream` 被激活（等价断言：SSE endpoint `/agent/tasks/t1/stream` 被请求过 —— 可用 msw handler 计数）。
- **TC-PR27-2 · `CandidateChat empty state: URL ?candidates= → renders Empty + navigate button`**：
  MemoryRouter `initialEntries=['/candidate-chat?candidates=']` · 断言渲染 `<Empty>` 组件（可用 `screen.getByText('请先在候选人列表选择要对话的候选人')`） · 点 "去候选人列表选择" 按钮 · 断言 navigate 到 `/resumes`（用 MemoryRouter + `useLocation` spy 或 Routes 挂 `/resumes` mock 目标断言）。
- **TC-PR27-3 · `Resumes bulk entry: check 2 rows → click "AI 对话/画像" → navigate to /candidate-chat?candidates=<id1>,<id2>`**：
  Mock `resumeApi.list` 返回 2 条 resume · 渲染 Resumes 页 · 勾选表格多选 checkbox 2 项 · 点按钮 · 断言 URL query param 含 `candidates=<id1>,<id2>`（顺序按勾选顺序 or 表格显示顺序 · 断言用 Set 比较更稳）。
- **TC-PR27-4 · 既有回归（不新增文件）**：跑 `ChatCenter.test.tsx` 全部原有 case（TC-S5-13-1 / 2 / 4 / 5 / 9） · 跑 `CandidateChat.test.tsx` 原 TC-S5-13-6 · 全绿。

**期望终值**：`npm test` → **35 passed**（31 baseline + 4 PR-27） · `npm run build` 通过。

### §三.5 · Commit split（TDD strict · QUESTIONS §Q5 采纳 · 4 code + 1 docs = 5 commit）

1. `test(pr-27): red-test skeleton for TC-PR27-1..3 (all failing)` —— 3 新 TC 骨架
2. `refactor(agent): extract TaskStream component from ChatCenter for reuse` —— 抽组件 + ChatCenter 改 import（TC-PR27-4 回归保绿）
3. `feat(candidate-chat): activate CandidateChat with TaskStream + empty state · Resumes bulk entry` —— CandidateChat 活化 + Resumes 入口
4. `test(pr-27): green tests TC-PR27-1..4 pass` —— 转绿
5. `docs(stage5): PR-27 STEP6 report + HANDOFF §9.3.21 CLOSED` —— 报告 + HANDOFF 更新

**分支**：`feat/pr-27-fix-candidatechat-and-entry`

---

## §四 · 验收（三门 + PR-27 专项）

- **pytest 全量**：期望 **145 passed / 2 skipped**（无后端改动 · 与 PR-26 baseline 完全一致）
- **ruff 全仓**：0 error（无后端改动 · 与 PR-26 baseline 完全一致）
- **frontend `npm test`**：期望 **35 passed**（31 baseline + 4 PR-27） · **若执行体首跑复核 baseline 不是 31，先报回而不是硬改期望值**
- **frontend `npm run build`**：通过（TypeScript 严格模式 · 无 `any` 泄漏）
- **专项浏览器 e2e（可选，若能起前后端全栈）**：
  1. 起后端（含 PR-25 + PR-26 修复）+ 前端
  2. 进 `/resumes` · 勾选 2 条 resume · 点 "AI 对话 / 画像" · 断跳 `/candidate-chat?candidates=<id1>,<id2>`
  3. CandidateChat 挂载 · 输入 "给候选人画像" · 点发送 · 断 `<StreamStatusBar>` 显示 · SSE 流事件序列含 `thinking → plan → tool_call(candidate-profile) → progress → result` · `result.data` 里 `profile_tags/summary` 非空

---

## §五 · 求助边界（继承 AGENTS.md/CLAUDE.md 通用 + PR-27 增补 · QUESTIONS §Q6 采纳 4 条）

**继承（不复述）**：AGENTS.md + CLAUDE.md 通用 stop-and-ask + PR-25/26 已定基调。

**PR-27 增补**（触及必停）：

1. **抽 `TaskStream` 组件后既有 `ChatCenter.test.tsx` 里 antd `useToken` / `ConfigProvider` 类的 context 依赖挂**：说明组件抽离带出了隐式 hooks 依赖 · 停 · 报现象 · **不擅自** 在新组件里 mock context。
2. **Resumes.tsx 现有单选 `selectedResume` 与新多选 `checkedResumeIds` 冲突**：例如某个已有测试断言"点行 → selectedResume 设置" 与新 rowSelection 联动冲突 · 停 · 报回是"改造成完全多选（可能破 Resumes.match.test.tsx）"还是"多选与单选完全独立"（DECISION 默认后者）。
3. **既有 `CandidateChat.test.tsx` TC-S5-13-6 契约与 §Q1 A 方案产物冲突**（比如新组件挂载后 `agentApi.chat` 调用签名意外变了）：停 · 报回是修测试还是调实现 · **不擅自** 改测试断言。
4. **PR-27 完工后 `/candidate-chat?candidates=a,b` 手工浏览器验收：`agentApi.chat` 返回 `task_id` 但 SSE 流永远不出 `tool_call` 事件**：说明后端 dispatch / hydration 侧新暴露的 bug（**不是 PR-27 scope**）· 停 · 登记 §9.3 · 不擅自扩到后端。

---

## §六 · 通过判据 checklist

- [ ] pytest 全量 **145 passed / 2 skipped**（无后端改动，回归即可）
- [ ] ruff 全仓 0 errors
- [ ] frontend `npm test` **35 passed**（31 baseline + 4 PR-27） · 若 baseline 复核不是 31 先报回
- [ ] frontend `npm run build` 通过
- [ ] TC-PR27-1..4 全绿（活化 · 空态 · 入口 · 回归）
- [ ] **不改** ChatCenter.tsx 主体行为（只挪 TaskStream 提取 · TC-S5-13-* 全绿）
- [ ] **不改** CandidateChat 现有 `agentApi.chat` 调用签名（TC-S5-13-6 保绿）
- [ ] **不改** Resumes 现有单选 `selectedResume` 语义（既有 test 保绿）
- [ ] STEP6 报告 `PR27-STEP6-REPORT.md` 写完 · 附三门 output
- [ ] HANDOFF 新增 §9.3.21（Bug C CLOSED · anchor 填最终测试 commit）
- [ ] 分支 push · FF-merge master · 远程分支删除

**一票否决项**：无。1–7 全部满足即通过。

---

## §七 · 执行流水（时间预估）

```
Step 0 · KICKOFF-DECISION（本 · docs-only 直落 master）· ~5 min
Step 1 · 起分支 + red-test 骨架（TC-PR27-1..3 全 red）· ~25 min
Step 2 · 抽 TaskStream 组件 + ChatCenter 改 import · ~15 min
Step 3 · CandidateChat 活化 + Empty 空态 + Resumes 多选按钮 · ~30 min
Step 4 · 测试转绿（TC-PR27-1..4）· ~20 min
Step 5 · 三门验收（pytest 145/2 · ruff 0 · npm test 35 · build ✓）· ~15 min
Step 6 · STEP6 报告 + HANDOFF §9.3.21 + push + FF-merge + 删远程分支 · ~15 min
──────────────────────────────
乐观：125 min · 悲观（边界 1 或 2 触发）：180–240 min
```

---

## §八 · 给执行体的一句话指令（复制粘贴级）

> **PR-27 执行体接活**：拉 `feat/pr-27-fix-candidatechat-and-entry` 分支（起自 master HEAD `ce66300`）· 严格按 `docs/planning/stage5/PR27-KICKOFF-DECISION.md` §三 落地 —— 新建 `frontend/src/components/agent/TaskStream.tsx`（把 `ChatCenter.tsx:15-33` 的本地 TaskStream 函数原样搬入并 export）· `ChatCenter.tsx` 改 import 复用（**不改主体行为**）· `CandidateChat.tsx` 加 `taskId` state + `<TaskStream />` 挂载 + `<Empty>` 空态分支（**保留** `agentApi.chat({message, context:{candidate_ids}})` 签名 + placeholder `"输入消息..."` + "发送" 按钮文本）· `Resumes.tsx` 加 antd Table `rowSelection` + "AI 对话/画像" 按钮 → `navigate('/candidate-chat?candidates=<ids>')`（**不改**现有单选 `selectedResume` 语义 · 多选独立共存）· 新增 `frontend/tests/pages/Resumes.entry.test.tsx`（TC-PR27-3）· `CandidateChat.test.tsx` 追加 TC-PR27-1/2 · 按 §三.5 4 code + 1 docs commit split 提交 · 三门验收目标 **pytest 145/2 · ruff 0 · npm test 35 · build ✓**（若 npm test baseline 复核不是 31 先报回不硬改期望）· §五 4 条求助边界触及必停不擅走 · 完工后写 `PR27-STEP6-REPORT.md` + HANDOFF §9.3.21 CLOSED + FF-merge master + 删远程分支 · **纯前端 scope · 禁止改**任何 `backend/**`。
