# PR-29 执行体指令 · 修复 PROGRESS 事件前后端字段名不一致

> 指挥官裁决日期：2026-07-27
> 类型：前端 bug fix（小改动，无需完整 KICKOFF-QUESTIONS/DECISION 流程）
> 起手基线：master `0b2c1d0`

---

## 一、背景（必读，解释为什么测试全绿却有 bug）

MVP-VERIFY v2 §4.1 浏览器验收中，**后端全链路成功**（`tasks.status=COMPLETED`、
`executions.execution_status=COMPLETED`、画像内容真实：清华/字节/Python/Go/K8s），
但**前端进度条恒显示 0%**。

根因是 PROGRESS 事件的 payload 契约三层不一致：

| 层 | 位置 | 字段 |
|---|---|---|
| 后端**实际发送** | `backend/app/agent/orchestrator/act.py:136` | `{"step_id": step_id, "percent": 100}` |
| 前端**类型声明** | `frontend/src/types/agent.ts:39-43` | `{step_id, progress: number, message: string}` |
| 前端**渲染读取** | `frontend/src/components/agent/ProgressCard.tsx:7` | `event.data.progress` |

执行链：`event.data.progress` → `undefined` → `undefined * 100` = `NaN`
→ `Number.isFinite(NaN)` 为 `false` → 兜底 `percent={0}` → **恒 0%**。
`event.data.message` 同理恒 `undefined`，进度卡片的文字说明也一直是空的。

**为什么 PR-19 的 11 个前端测试全绿却没发现**：
`frontend/tests/fixtures/sseEvents.ts:43-47` 的 fixture 自己造了
`{step_id, progress: 0.5, message: 'progress-content'}` —— 一个**后端从不发送**的
payload 形状。测试与实现自洽，但双方都与后端契约不符。这是本次修复必须连带
修正 fixture 的原因，否则改完实现测试反而会红。

**裁决**：改前端适配后端（后端 `percent` 语义不动，零后端风险；backend 155
passed 基线不受影响）。

---

## 二、改动清单（严格照此，勿扩大范围）

### 2.1 `frontend/src/types/agent.ts`

```ts
export interface ProgressData {
  step_id: string;
  percent: number;      // ← 后端 act.py:136 发的是 percent（0-100 整数），不是 progress（0-1 小数）
  message?: string;     // ← 后端当前不发此字段，声明为 optional
}
```

### 2.2 `frontend/src/components/agent/ProgressCard.tsx`

```tsx
export function ProgressCard({ event }: { event: SSEEvent<ProgressData> }) {
  const percent = event.data.percent ?? 0;
  return (
    <CardContainer title="进度" testId="progress-card">
      {event.data.message ? <Typography.Text>{event.data.message}</Typography.Text> : null}
      <Progress percent={Number.isFinite(percent) ? percent : 0} />
    </CardContainer>
  );
}
```

**注意两点**：
- 去掉 `Math.round(... * 100)` —— 后端已是 0-100 整数，再乘 100 会得到 10000。
- `message` 改条件渲染。原代码无条件渲染 `undefined`，React 渲染为空但语义上是
  在展示一个不存在的字段；`message` 既然是 optional 就该条件渲染。

### 2.3 `frontend/tests/fixtures/sseEvents.ts`

把 `progress = 0.5` 参数改为 `percent = 100`，`data` 对象同步改为
`{ step_id, percent, message }`。**保留 `message` 参数与默认值 `'progress-content'`**
（EventCards 测试断言它）。

### 2.4 同步 4 个测试文件的假 payload

以下位置的 `{ progress: X }` 一律改为 `{ percent: Y }`（Y = X*100 取整，保持语义）：

- `frontend/tests/hooks/useTaskStream.test.ts:31` → `percent: 50`
- `frontend/tests/hooks/useTaskStream.test.ts:53` 断言 → `toMatchObject({ percent: 50 })`
- `frontend/tests/hooks/useTaskStream.test.ts:76` → `percent: 40`
- `frontend/tests/hooks/useTaskStream.test.ts:81` → `percent: 80`
- `frontend/tests/pages/ChatCenter.test.tsx:104` → `percent: 50`

---

## 三、必须新增的回归测试（防止契约再次漂移）

在 `frontend/tests/components/agent/EventCards.test.tsx` 增加 **TC-PR29-1**，
断言**用后端真实 payload 形状**渲染时进度条不是 0：

```tsx
test('TC-PR29-1 ProgressCard 用后端真实 payload（percent:100 · 无 message）渲染出 100%', () => {
  // 这个 payload 形状抄自 backend/app/agent/orchestrator/act.py:136，
  // 改动任一侧字段名此测试即红 —— 这是本 PR 存在的意义。
  const event = {
    id: '1', type: 'progress' as const, task_id: 't', step_id: 's1',
    timestamp: new Date().toISOString(),
    data: { step_id: 's1', percent: 100 },   // ← 注意：无 message 字段
  };
  render(<ProgressCard event={event} />);
  const bar = screen.getByRole('progressbar');
  expect(bar).toHaveAttribute('aria-valuenow', '100');
});
```

**验收要求**：先只改测试不改实现，确认 TC-PR29-1 **红**（拿到失败输出），
再改实现让它转绿。**这一步的红色输出必须贴进报告** —— 它是"这个测试真的能咬住
bug"的唯一证据。若它在改实现前就是绿的，说明断言写错了，停下报告。

> `aria-valuenow` 是 antd `Progress` 渲染的属性。若该版本 antd 不输出此属性，
> 改用 `expect(screen.getByText('100%')).toBeInTheDocument()`，并在报告中注明替换原因。

---

## 四、验收三道门（全部要贴输出）

```bash
cd frontend
npm run lint          # 0 errors
npm run build         # 成功
npm test              # 期望 31 passed + 1 新增 = 32 passed（若基线数不同，以实测为准，不要调期望值凑数）
```

**backend 零改动** —— 提交前用 `git diff --stat master -- backend/` 确认为空并贴进报告。

---

## 五、提交与分支

```bash
git checkout master && git pull
git checkout -b fix/pr-29-progress-event-field-mismatch
```

commit 拆分（2 个）：

1. `test(pr29): TC-PR29-1 红测试 · ProgressCard 用后端真实 percent payload 断言 100%`
   （只含新增测试，此时应红）
2. `fix(pr29): ProgressCard/ProgressData 读 percent 适配后端 act.py 契约 + 同步 5 处测试 fixture`

推分支后**停下报告**。

---

## 六、停止并报告的边界（触发即停，不要自行绕过）

1. **`npm test` 基线不是 31 passed** —— 说明工作区有他人未提交改动或基线已漂移，
   停下报告实测数字，不要调整期望值凑数。
2. **TC-PR29-1 在改实现前就是绿的** —— 断言没咬住 bug，停下报告。
3. **发现 `percent` 之外还有其他字段名不一致**（例如 `RESULT` / `TOOL_CALL` 事件
   也对不上）—— **不要顺手一起改**。记录发现并停下报告，由指挥官决定是否扩大 PR
   范围。本 PR 只修 PROGRESS。
4. **需要改 `backend/` 任何文件** —— 本 PR 裁决是"只改前端"，若你认为必须动后端，
   停下报告理由。
5. **antd `Progress` 无法断言百分比** —— 按 §三 脚注换 `getByText`，若两种都不行
   停下报告。

---

## 七、不要做的事

- **不要自行 FF-merge，不要删远程分支** —— 留待指挥官处置。
- **不要提交** `backend/.env`、`_verify/`、`backend/_diag_uat.py`、
  `backend/_seed_resume_uat.py`、`backend/_seed_resume2_uat.py`、`backend/backend.err`、
  `backend/scripts/`、`frontend/_pr27*`、`frontend/chatcenter-out.txt`、`graphify-out/`
  等既有 untracked 产物。
- **不要创建 tag**。
- **不要动 `act.py`** —— 后端 `percent` 语义是本 PR 的适配目标，不是修改对象。

---

## 八、附：本次验收已确认为正常的行为（不要当 bug 修）

- **`POST /agent/execute-plan` 返回 409 `ILLEGAL_STATE_TRANSITION`** —— 这是**正确的**
  防重复执行保护（`agent.py:165-171` 只接受 `WAITING_CONFIRMATION` 状态）。
  用户因进度条卡 0% 误以为没反应而重复点击「确认执行」，第二次请求撞上已变为
  `EXECUTING`/`COMPLETED` 的任务 → 409。**进度条修好后这个 409 会自然消失。**
  若你想顺手在前端加"执行中禁用按钮"的防抖 —— **那属于扩大范围，停下报告，
  不要自行加**。
- **后端 `candidate-profile` 全链路已验证通过**：`task_2e858c304b80` /
  `task_12b3b59cf7fe` 均 `COMPLETED`，`executions.input_params` =
  `{"candidate_id": "res_dd43c9ab91cc"}`（PR-28 的 input_schema 注入生效 ·
  单数键 + 正确 ID），artifact `type="candidate_profile"`，summary 为真实简历
  内容（清华/字节/Python/Go/K8s）非占位符。**§4.1 的后端部分不需要再动。**
