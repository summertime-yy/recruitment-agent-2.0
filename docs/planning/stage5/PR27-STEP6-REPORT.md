# PR-27 STEP6 验收报告（CandidateChat 激活 + 批量 entry）

## 一、PR 元信息
- 分支：`feat/pr-27-fix-candidatechat-and-entry`（from master `ce66300`，即 PR-27 QUESTIONS 已合）
- 类型：**纯前端 code PR**（无后端 / schema / migration 变更；`backend/` 零改动）
- 关联：`PR27-KICKOFF-DECISION.md`、`PR27-KICKOFF-QUESTIONS.md`
- 关闭：**MVP-VERIFY §4.1 Bug C**（CandidateChat 空壳页丢弃 `task_id` 渲染空白）

## 二、改动面（纯前端）
| 文件 | 性质 | 说明 |
|------|------|------|
| `frontend/src/components/agent/TaskStream.tsx` | 新增 | 从 `ChatCenter.tsx` 抽取的可复用 SSE 聊天流组件（`useTaskStream` + `StreamStatusBar` + `MessageTimeline` + 可选 `SkipToScorePanel` + 可选输入区） |
| `frontend/src/components/agent/SkipToScorePanel.tsx` | 新增 | JD `Select` + 简历多选 `Select` + "立即评分"按钮，调 `agentApi.skipToScore` |
| `frontend/src/pages/ChatCenter.tsx` | 改写 | 持 `taskId`/`input` state，渲染 `<TaskStream .../>`，`handleSend` 调 `agentApi.chat({message, context:{jd_id, resume_id}})` |
| `frontend/src/pages/CandidateChat.tsx` | 改写 | 激活空壳页：解析 `?candidates=a,b`，`Empty` 分支（去候选人列表选择 → `/resumes`）+ `<TaskStream/>` + 内联输入区 |
| `frontend/src/pages/Resumes.tsx` | 修改 | Table 加 `rowSelection` 多选 + 批量区"AI 对话 / 画像（N）"按钮 → `/candidate-chat?candidates=<ids>` |
| `frontend/src/types/agent.ts` | 修改 | `AgentChatRequest.context` 补 `resume_id?: string`（后端为 `dict[str, Any]`，匹配 ChatCenter 路由 `/chat/:jdId/:resumeId`） |
| `frontend/tests/pages/CandidateChat.test.tsx` | 修改 | 追加 TC-PR27-1（挂载 + SSE 请求 + 无 skip 面板）、TC-PR27-2（空 candidates → Empty + 跳转），保留原 TC-S5-13-6 |
| `frontend/tests/pages/Resumes.entry.test.tsx` | 新增 | TC-PR27-3：渲染 2 行 → 点"AI 对话/画像" → location 含 `candidates=r1,r2` |

## 三、验证结果（本地门禁 · 全绿）
- frontend `npm test`：**34 passed**（详见 §四）
- frontend `npm run lint`：**0 errors**
- frontend `npm run build`：**通过**（`tsc -b && vite build`，TS strict）
- backend `pytest`：**145 passed / 2 skipped**（无后端改动，回归基线不变）
- backend `ruff check app/`：**0 errors**（全量 `ruff check .` 仅在 untracked 临时脚本 `_diag_uat.py` 报错，非 PR 范围、不入仓）

## 四、测试门禁说明（重要：34 而非 35）
决策 §三.4 期望终值 `npm test → 35 passed（31 baseline + 4 PR-27）`。实测 **34 passed**。原因：

**TC-PR27-4 在决策中明确为"既有回归（不新增文件）：跑 ChatCenter.test.tsx 原有 case（TC-S5-13-1/2/4/5/9）· 跑 CandidateChat.test.tsx 原 TC-S5-13-6 · 全绿"** —— 它是回归运行项，**不新增测试函数**。因此 PR-27 实际新增 3 个测试函数（TC-PR27-1/2/3），总数 = 31 baseline + 3 = **34**。

决策"35"行将 TC-PR27-4 误计为第 4 个新增测试，属算术口径误差；**baseline 31 经复核成立**，满足决策"若 baseline 非 31 先报回而不是硬改期望值"规则，无违规。

测试明细：
- **TC-PR27-1**（`CandidateChat.test.tsx`）：`TaskStream` 挂载 + SSE `GET /agent/tasks/t1/stream` 被请求 + 无 skip 面板 → pass
- **TC-PR27-2**（`CandidateChat.test.tsx`）：空 candidates → `Empty` + 跳转 `/resumes` → pass
- **TC-PR27-3**（`Resumes.entry.test.tsx` NEW）：渲染 2 行 → 点"AI 对话/画像" → location 含 `candidates=r1,r2` → pass
- **TC-PR27-4**（回归）：`ChatCenter.test.tsx` 原有 TC-S5-13-1/2/4/5/9 全绿 + `CandidateChat.test.tsx` 原 TC-S5-13-6 全绿 → 全绿
- 全量 13 个测试文件 = 34 tests，全部通过。

## 五、实现要点 / 踩坑
1. antd v5 `<Header>` / `<Content>` **非顶层导出**，须用 `<Layout.Header>` / `<Layout.Content>`，否则报 "Element type is invalid"（曾卡全部渲染）。
2. `request` 直接返回 `response.data`（即 `PaginatedResponse` 本体），故 `SkipToScorePanel` 取 `jdRes.items` / `resumeRes.items`，而非 `.data.items`（原误写导致 TC-S5-13-2 选项不渲染 —— 本轮唯一修复点）。
3. `AgentChatRequest.context` 后端 schema 为 `dict[str, Any]`，前端类型此前仅含 `jd_id` / `candidate_ids`；补 `resume_id?: string` 以匹配 ChatCenter 路由的 resume 上下文（`npm run build` 原因此报错）。
4. `Resume.candidate_name` 为 `string | undefined`，map label 兜底 `?? r.resume_id`（避免 TS strict 报错）。
5. antd v5 对 ≤2 字中文按钮自动插空格（"发送" → "发 送"），测试用 `/发\s*送/` 匹配。

## 六、Commit 计划（本地 5 个，遵循 §三.5）
1. `refactor(agent): extract reusable TaskStream component from ChatCenter` — `TaskStream.tsx` + `SkipToScorePanel.tsx` + `ChatCenter.tsx` + `types/agent.ts`(resume_id)
2. `feat(candidate-chat): activate CandidateChat empty-shell with TaskStream + empty state` — `CandidateChat.tsx`
3. `feat(resumes): add bulk multi-select AI entry button → /candidate-chat` — `Resumes.tsx`
4. `test(pr-27): add TC-PR27-1..3 + ensure regression green` — `CandidateChat.test.tsx` + `Resumes.entry.test.tsx`
5. `docs(stage5): PR-27 STEP6 report + HANDOFF §9.3.21 Bug C CLOSED` — `PR27-STEP6-REPORT.md` + `HANDOFF.md`

> 注：因多 session 实现，commit 为**逻辑拆分**（非严格 red→green TDD 提交序），但每个 commit 的测试套件均绿。

## 七、待指挥官复审（本 agent 不自动执行）
- [ ] fast-forward merge `feat/pr-27-fix-candidatechat-and-entry` → master
- [ ] 删除远程分支 `feat/pr-27-fix-candidatechat-and-entry`
- [ ] 清理前端工作树临时文件 `_pr27_*.txt`（本次验收产物）

## 八、遗留 / 不修
- 决策 §三.5 的"red-test 先提交"理想流程因跨 session 已不可还原，采用逻辑拆分（见 §六 注）。
- 全量 `ruff check .` 在 untracked `_diag_uat.py` / `_seed_resume_uat.py` 报错，系开发期临时脚本，非 PR-27 范围，不修复、不入仓；提交范围严格限定 §二 八文件。
