# PR-29 复审补丁指令（commit 3）· 红测试断错对象 + 两处偏离指令

> 复审日期：2026-07-27
> 复审基线：`origin/fix/pr-29-progress-event-field-mismatch` @ `76c5c78`
> 结论：**不通过**。修复方向正确、三道门全过，但红测试**无法检出用户实际报告的 bug**。
> 分支不要重建，在现有分支上追加 **commit 3**。

---

## 一、先说清楚：这不是粗心，是一个值得记住的陷阱

你写的 `TC-PR29-1` 和你的实现**完全自洽** —— 实现渲染 `"Updated to 100%"`，测试断言
`getByText('Updated to 100%')`，逻辑上无懈可击，35 passed 也是真的。

问题在于**两者一起偏离了"要验证进度条能动"这个真实目标**。

我用变异测试证明了这一点（两次变异，第二次是致命的）：

| 变异 | 改动 | 期望 | 实际 |
|---|---|---|---|
| 1 | `event.data.percent` → `(event.data as any).progress`（还原原 bug） | TC-PR29-1 红 | ✅ 红 |
| 2 | **`<Progress percent={0} />` 硬编码**，文案代码不动 | TC-PR29-1 红 | ❌ **5 passed 全绿** |

**变异 2 就是用户报告的原始症状**（进度条恒 0%、不动），而 TC-PR29-1 照样通过。
因为它断言的是**文案字符串**，不是**进度条的值**。

请注意这与 PR-19 的失败是**同一个模式**：PR-19 的 11 个前端测试全绿，却漏掉了
`progress`/`percent` 字段名错，因为 fixture 自造了一个后端从不发送的 payload ——
测试与实现自洽，双方一起偏离真实契约。这次是同样的病换了一层：测试与实现自洽，
双方一起偏离"进度条要真的动"这个用户可见的目标。

**教训**：断言要咬住**用户能看到的那个东西**（进度条的值），而不是咬住**你自己
刚写下的那行代码**（文案字符串）。后者永远会绿。

---

## 二、必须改的三项

### 2.1 【阻塞】TC-PR29-1 改为断言进度条的值，且必须通过变异 2

`frontend/tests/components/agent/EventCards.test.tsx`

```tsx
// PR-29 · 进度事件字段对齐后端契约（act.py:136 发 {step_id, percent}，无 message）
test('TC-PR29-1 progress 事件 → ProgressCard 进度条 aria-valuenow=100', () => {
  render(
    <ConfigProvider>
      <ProgressCard event={makeProgressEvent('p1', 100)} />
    </ConfigProvider>,
  );
  // 断言进度条本身的值 —— 这是用户能看到的东西。
  // 不要断言文案字符串：那样把 <Progress percent={0} /> 硬编码也能绿（复审已实测）。
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
});
```

**验收此项的硬要求（两次都要贴输出）**：

```bash
cd frontend

# 变异 A：还原原始字段名 bug
#   src/components/agent/ProgressCard.tsx:
#   const percent = event.data.percent;  →  const percent = (event.data as any).progress;
npx vitest run tests/components/agent/EventCards.test.tsx
# 期望：TC-PR29-1 红。贴红色输出。然后改回。

# 变异 B：文案不动，只把进度条硬编码为 0（模拟"进度条仍坏但文案对"）
#   <Progress percent={Number.isFinite(percent) ? percent : 0} />  →  <Progress percent={0} />
npx vitest run tests/components/agent/EventCards.test.tsx
# 期望：TC-PR29-1 红。贴红色输出。然后改回。
```

**变异 B 必须变红 —— 这是本次 commit 3 存在的全部意义。**
若变异 B 仍然全绿，说明断言还是没咬住进度条，**停下报告，不要交付**。

> 若该 antd 版本的 `Progress` 不输出 `role="progressbar"` 或 `aria-valuenow`：
> 先用 `console.log(container.innerHTML)` 打印实际 DOM，从中找一个**由 percent 值
> 驱动**的属性或文本来断言（例如 `.ant-progress-bg` 的 `style.width`，或 antd 自带
> 渲染的 `100%` 文本节点）。**关键判据不变：变异 B 必须能让它红。**
> 若两种都做不到，停下报告实际 DOM，不要退回断言自造文案。

### 2.2 【阻塞】恢复 `message` 的条件渲染，不要自造英文文案

`frontend/src/components/agent/ProgressCard.tsx`

```tsx
export function ProgressCard({ event }: { event: SSEEvent<ProgressData> }) {
  const percent = event.data.percent;
  return (
    <CardContainer title="进度" testId="progress-card">
      {event.data.message ? <Typography.Text>{event.data.message}</Typography.Text> : null}
      <Progress percent={Number.isFinite(percent) ? percent : 0} />
    </CardContainer>
  );
}
```

当前实现改成了 `<Typography.Text>Updated to {percent}%</Typography.Text>`，两个问题：

1. **全中文界面里会显示英文 "Updated to 100%"** —— 这是用户可见的 UI 退化。
2. **`message` 字段被永久丢弃** —— 后端将来补发 `message` 也不会显示。
   本 PR 的目标是"前端适配后端契约"，不是"前端替后端编造文案"。

### 2.3 【阻塞】`ProgressData.message` 保留为 optional，不要删除

`frontend/src/types/agent.ts`

```ts
export interface ProgressData {
  step_id: string;
  percent: number;      // 后端 act.py:136 发 0-100 整数
  message?: string;     // 后端当前不发；保留 optional 以便后端补发时前端无需再改
}
```

当前把 `message` 整行删掉了。原指令 §2.1 写的是 `message?: string`（optional **保留**），
不是删除。

---

## 三、需要回退的未授权改动

以下三处不在原指令 §二 的改动清单内，原指令 §七 已明确"不要扩大范围"：

| 文件 | 改动 | 处置 |
|---|---|---|
| `frontend/package.json` | 新增 `"vite-node": "^3.2.4"` | **回退** |
| `frontend/package-lock.json` | 686 行变动（装包连带） | **回退** |
| `frontend/vite.config.ts` | `defineConfig` 从 `vite` 改为 `vitest/config`、删 `/// <reference types="vitest/config" />` | **回退** |

**回退 `vite-node` 的理由**：我已 `grep` 全仓（`src/`、`tests/`、`package.json`、
`vite.config.ts`），**代码里零引用**，只存在于 package.json 的 devDependencies。
一个没有任何引用的依赖会长期留在 lockfile 里，是纯负债。

```bash
git checkout master -- frontend/package.json frontend/package-lock.json frontend/vite.config.ts
npm ci          # 让 node_modules 与回退后的 lockfile 一致
npm test        # 确认回退后测试仍然可跑
```

**若 `npm test` 在回退后无法运行**（例如 vitest 4 确实需要 `vitest/config` 才能识别
`test` 段）—— **停下报告**，把失败输出贴出来。那种情况下这三处就不是"顺手改的"
而是"必需的"，我会补授权并要求在报告里说明必要性。**不要默默留着，也不要默默回退
到跑不起来的状态。**

---

## 四、commit 3 的验收（全部要贴输出）

```bash
cd frontend
npm run lint      # 期望 0 errors（8 个既有 warning 属基线，不要顺手修）
npm run build     # 期望成功
npm test          # 期望 35 passed（34 基线 + TC-PR29-1）
```

**外加变异测试两次红色输出**（§2.1 的变异 A 和变异 B），这是本次交付的核心证据。

**backend 零改动**：贴 `git diff --stat master -- backend/` 为空的输出。

commit message 建议：

```
fix(pr29): TC-PR29-1 改断言进度条 aria-valuenow（原断言自造文案 · 变异 B 可全绿）
           + 恢复 message 条件渲染 + 回退未授权的 vite-node 依赖
```

---

## 五、停止并报告的边界（触发即停）

1. **变异 B 改完断言后仍然全绿** —— 断言没咬住进度条，停下报告，不要交付。
2. **antd `Progress` 无 `role="progressbar"` / `aria-valuenow`** —— 按 §2.1 脚注打印
   实际 DOM 并报告，不要退回断言自造文案。
3. **回退 `vite.config.ts` / `vite-node` 后 `npm test` 跑不起来** —— 停下报告失败输出。
4. **`npm test` 基线不是 35 passed** —— 停下报告实测数字，不要调期望值凑数。
5. **需要改 `backend/` 任何文件** —— 停下报告。
6. **发现 PROGRESS 之外还有其他事件字段名不一致** —— 记录并停下报告，不要顺手改。
   本 PR 只修 PROGRESS。

---

## 六、不要做的事

- **不要 rebase / force-push / 重建分支** —— 在现有分支上追加 commit 3，保留
  `792e8a8` + `76c5c78` 的历史（复审痕迹要留）。
- **不要自行 FF-merge，不要删远程分支** —— 留待指挥官处置。
- **不要顺手修那 8 个既有 lint warning** —— 不在范围内。
- **不要顺手加"执行中禁用按钮"防抖** —— 原指令 §八 已说明，属扩大范围。
- **不要提交** `_verify/`、`backend/_diag_uat.py`、`backend/_seed_resume_uat.py`、
  `backend/_seed_resume2_uat.py`、`backend/backend.err`、`backend/mig1.txt`、
  `backend/scripts/`、`backend/test-full.txt`、`frontend/_pr27*`、
  `frontend/chatcenter-out.txt`、`graphify-out/` 等既有 untracked 产物。
  **特别注意**：`backend/_seed_resume_uat.py` 与 `_seed_resume2_uat.py`
  **必须保留在工作区**（§4.2/§4.3 验收还要用），既不要提交也不要删除。
- **不要创建 tag。**

---

## 七、复审已确认无问题的部分（不用动）

- **字段同步 5 处全部正确**：`sseEvents.ts` fixture、`useTaskStream.test.ts:31/53/76/81`、
  `ChatCenter.test.tsx:104` 的 `progress: 0.X` → `percent: XX` 换算与断言均正确。
- **`ProgressCard` 去掉 `Math.round(... * 100)` 正确** —— 后端已是 0-100 整数，
  再乘 100 会得到 10000。
- **三道门本身全过**（复审实测）：`35 passed (13 files)` · `lint 0 errors, 8 warnings`
  · `build ✓ built in 5.56s` · 分支可 FF（`master` 是其祖先）。
- **变异 1 通过** —— 测试确实咬住了字段名 `percent`，这部分有效，保留。
- **未跟踪噪声文件均未入 commit** ✅ 确认无误。
