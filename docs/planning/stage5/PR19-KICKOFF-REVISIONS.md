# PR-19 KICKOFF QUESTIONS · 修订建议清单（供指挥官裁定）

> 关联：`docs/planning/stage5/PR19-KICKOFF-QUESTIONS.md`（初稿，687 行，2026-07-23）
> 目的：在出 `PR19-KICKOFF-DECISION.md` 前，先把评估中发现的 **事实矛盾 / 契约缺口 / 文档一致性冲突** 列项，交由指挥官逐项裁定。裁定后并入 DECISION。
> 说明：本文件只列修订建议，**不进 commit**（随 DECISION 一并走 docs-only 直推或本分支）。
> 核验依据（实测事实源，对照 PR-18 REVISIONS 同样以代码为准）：
> - 后端 `backend/app/schemas/agent.py:80-85`（`ExecutePlanRequest` · `accepted_steps`/`modifications` 默认 `None`）
> - 后端 `backend/app/agent/orchestrator/engine.py:374-409`（`run_execute` 仅 `accepted_steps is not None` 才过滤步骤）+ `:50-56`（`_ARTIFACT_TYPE_MAP` 5 键 + generic）
> - 后端 `backend/app/api/v1/agent.py:101-176`（`execute_plan`/`skip_to_score`）+ `:191-197`（`_is_terminal` 判定 `data.message == "cancelled"`）+ `:246`（`SYSTEM {"message":"cancelled"}`）+ `:333`（cancel 补发 SYSTEM cancelled）
> - 后端 `backend/app/api/v1/endpoints/resume.py:143-144`（`GET /resumes` 列表）+ `candidate.py`（无 collection list 路由）
> - 前端 `frontend/src/types/agent.ts:63-65`（`SystemData` 仅 `message: string`）+ `:71-85`（`ArtifactType` 6 键 union）
> - 前端 `frontend/src/hooks/useTaskStream.ts:110`（终态判定为**内联** `if (result||error) hasReachedTerminalRef=true`，**无 `isTerminal()` 函数**）+ `:115-121`（`system` 不入 `events[]`）
> - 前端 `frontend/src/services/{jd,resume,candidate}.ts`（`jdApi.list` ✓ / `resumeApi.list` ✓ / `candidateApi.list` ✗）
> - 前端 `frontend/src/pages/{CompareAnalysis,CandidateChat}.tsx`（均为 `<PlaceholderPage>`，Phase 2 占位，无 `selectedIds`）
> - `git`：`origin/master` = `b62d1df`，已含 PR-18 三件套（`useTaskStream.ts`/`types/agent.ts`/`services/agent.ts`）→ **PR-18 已 FF-merge**

---

## A 类 · 阻断级事实修正（出 DECISION 前必须改）

### A1 · Q6 终态判定字段错位（`status` → `message`），且引用了不存在的函数名（致命）

- **现状（初稿）**：`PR19-KICKOFF-QUESTIONS.md:219` Q6 选项 A 写：
  > `useTaskStream.ts` `isTerminal(event)` 从 `type === 'result' || type === 'error'` 扩展为 `type === 'result' || type === 'error' || (type === 'system' && data?.status === 'cancelled')`
- **实测事实**：
  - 后端取消事件真实形态 = `event: system` + `data: {"message": "cancelled"}`（见 `agent.py:246` 与 `:333` 补发 `SSEEventType.SYSTEM, {"message": "cancelled"}`）；
  - 后端 `_is_terminal`（`agent.py:195`）判定的是 `ev.data.get("message") == "cancelled"`（字符串 `"message"` 字段，非 `"status"`）；
  - 前端 `SystemData`（`types/agent.ts:63-65`）**只有 `message: string`，没有 `status` 字段**；
  - PR-18 hook 实际无 `isTerminal()` 函数，终态判定是 `useTaskStream.ts:110` 的内联语句 `if (typed === 'result' || typed === 'error') hasReachedTerminalRef.current = true;`。
- **后果（致命）**：若执行体按 Q6 字面实现 `data?.status === 'cancelled'`，因前端 `SystemData` 无 `status` 字段 → 该谓词恒为 `undefined === 'cancelled'` = `false` → `system:cancelled` **永不判终态**，hook 照旧走非终态重连 3 次退避后 `status='error'`，**PR-18 obs 3 的 bug 原样保留**，TC-S5-13-9（CANCELLED UI）与 TC-S5-13-11（hook cancel terminal）全部转绿失败。
- **修订建议**：DECISION 必须把 Q6 选项 A 的判定改写为：
  - 字段：`(data as SystemData)?.message === 'cancelled'`（与后端 `_is_terminal`、前端 `SystemData` 严格对齐）；
  - 代码位置：修改 `frontend/src/hooks/useTaskStream.ts:110` 内联判定，扩展为 `if (typed === 'result' || typed === 'error' || (typed === 'system' && (data as {message?:string})?.message === 'cancelled')) hasReachedTerminalRef.current = true;`（**不要引用不存在的 `isTerminal()` 函数名**）；
  - 同时把 Q6 选项 A 描述里的「修改 `isTerminal(event)` 函数」改为「修改 `useTaskStream.ts:110` 内联终态判定」。
- **裁定选项**：(a) 按 `data.message === 'cancelled'` + `:110` 内联判定改写（推荐，必须）/ (b) 维持 Q6 原 `data.status` 写法（不推荐，必致 bug 残留）。

### A2 · Q10 problem-2「CompareAnalysis 附加按钮」前提不成立（占位页，无附着点）

- **现状（初稿）**：`PR19-KICKOFF-QUESTIONS.md:396-398` 指挥官倾向 problem-2：「PR-19 附加在 `CompareAnalysis.tsx` 页顶部加『与候选人对话』按钮……`navigate('/candidate-chat?candidates=' + selectedIds.join(','))`」。
- **实测事实**：
  - `frontend/src/pages/CompareAnalysis.tsx`（504 B）整体是 `<PlaceholderPage title="对比分析 (Phase 2)">`，**无任何候选人选择状态 / `selectedIds` / 交互逻辑**；
  - `frontend/src/pages/CandidateChat.tsx` 同样为 `<PlaceholderPage title="候选人沟通 (Phase 2)">`，即本 PR 要替换的也是占位页；
  - 即 QUESTIONS 把 CompareAnalysis 当成「已有多候选人对比、有 selectedIds」的功能页，但代码里它只是 Phase 2 占位骨架。
- **后果**：problem-2 的「附加按钮带 selectedIds」**没有可附着的选中态**——要么 PR-19 必须先实现 CompareAnalysis 的候选人选择 UI（远超 §S5-13 边界，与 Q1「严格 S5-13 全量但不扩」自相矛盾），要么按钮只能传空/硬编码 ID（功能不成立）。该建议建立在错误前提上。
- **修订建议**：DECISION 取消 problem-2 的 CompareAnalysis 附加授权（撤销「附加改动授权」那条待裁定项）。CandidateChat 入口**仅保留 problem-1 选项 A（URL query `?candidates=a,b`）**，自包含、零跨页依赖、可直接通过 `MemoryRouter initialEntries` 测试（TC-S5-13-6）。若仍要真实入口，应挂到**已有候选人选择态**的页（如 Resumes 列表行操作），但那同样超出 §S5-13 → 留 Stage 5.1，不在 PR-19。
- **裁定选项**：(a) 删除 problem-2、CandidateChat 仅走 URL query（推荐，保边界）/ (b) 改挂 Resumes 列表（超边界，留 Stage 5.1）/ (c) PR-19 顺带实现 CompareAnalysis 选择 UI（不推荐，破 Q1 边界）。

---

## B 类 · 措辞微调 / 边角建议（不阻断，但建议采纳）

### B1 · Q4 后端空 body 默认全接受已实测闭环（去掉开放裁定项）

- **现状（初稿）**：`:170`/`:172`/`:653` 把「`executePlan({task_id})` 空 body 是否后端 default-all-accept」列为**待 DECISION 显式确认**的开放项。
- **实测事实**：`schemas/agent.py:84-85` `accepted_steps`/`modifications` 默认 `None`；`engine.py:394` `if accepted_steps is not None:` 才过滤步骤，否则**全步执行**。→ 空 body = 后端默认全接受，已坐实。
- **修订建议**：DECISION 直接采纳「`executePlan({task_id})` 空 body → 全步执行」，把该「待确认」降级为「已核实采纳」，无需指挥官再单独裁定；§七 汇总表 Q4 行删去「+ 需确认后端空 body」。

### B2 · Q9 候选人下拉数据源应为 `resumeApi.list()`（`/resumes`），而非 `candidateApi.list()`

- **现状（初稿）**：`:341-342`/`:358-361` Q9 选项 A 称「候选人多选下拉（从 `GET /candidates` 或 `GET /resumes` 拉列表）」并断言「`jdApi.list()` / `candidateApi.list()` 已在项目内成熟」。
- **实测事实**：
  - 前端 `candidateApi`（`services/candidate.ts`）**无 `list()` 方法**（仅 `getStatusMeta`/`updateStatus`，且按 `resumeId` 寻址）；
  - 前端 `resumeApi.list()`（`services/resume.ts:41-43`）存在 → `GET /resumes`（`resume.py:143` 返回 `ResumeListResponse`，含 `resume_id`）；
  - 后端 `skip_to_score`（`agent.py:148-151`）把 `req.candidate_ids[i]` 当作 `resume_id` 塞进 `tool_input`（`"resume_id": cid`）。
- **后果**：若 UI 用 `candidateApi.list()` 拉「候选人」再传给 `skipToScore`，要么编译期就缺方法，要么即便能从别处拿到 ID，后端也按 `resume_id` 解释 → 语义错位。
- **修订建议**：DECISION 把 Q9 选项 A 文案改为「候选人多选下拉使用 `resumeApi.list()`（`GET /resumes`），标签可显示『候选人』但 `value` 为 `resume_id`」；去掉「`candidateApi.list()` 已成熟」的误述。TC-S5-13-2 仍建议用 `<Select options={mockOptions}>` 注入避免真实列表拉取。

### B3 · Q14 测试文件数算术自相矛盾（6 既有 ≠ 基线 9）

- **现状（初稿）**：`:518`「新 test files 数：预估 +4 files … → 若追加 hook TC 则新增 3 files；若不追加则新增 3 files」；`:666` 汇总「`N_after = 31 passed` · `8 test files(6 既有 + 3 新) → 12 total test files`」。
- **实测事实**：PR-19 基线（PR-18 合入后）= **20 passed / 9 test files**（QUESTIONS 自身 `:14` 头部已写「前端 20 passed (9 test files)」）。
- **矛盾点**：`6 既有 + 3 新 = 9`，与「8 test files」不符；且基线实为 **9 既有**（非 6）。正确应为「**9 既有 + 3 新（ChatCenter / CandidateChat / EventCards）= 12 total test files**」；`hooks/useTaskStream.test.ts` 是 PR-18 既有文件、追加 TC-S5-13-11 不算新文件。
- **修订建议**：DECISION 修正 Q14：`N_after = 31 passed`（Q6=A，20+10+1）；test files = `12 total`（9 既有 + 3 新）。`8 test files / 6 既有` 两处均改。

### B4 · Q6 措辞对准真实代码位置（无 `isTerminal` 函数，呼应 A1）

- **现状（初稿）**：`:219`/`:241` 多次写「修改 `useTaskStream.ts` `isTerminal(event)`」。
- **实测事实**：PR-18 hook 无 `isTerminal()` 函数，终态标记是 `useTaskStream.ts:110` 内联 `hasReachedTerminalRef.current = true`。
- **修订建议**：DECISION 全篇将「`isTerminal(event)` 函数」统一改为「`useTaskStream.ts:110` 内联终态判定」，避免执行体搜索不存在的函数名（与 A1 同源，单列提醒）。

### B5 · base hash 漂移（QUESTIONS 写 `9a6554e`，实际 `b62d1df`，且 PR-18 已合）

- **现状（初稿）**：`:13`「起手 master HEAD：`9a6554e`」；`:582` B5「base = `origin/master` = `9a6554e`」。
- **实测事实**：`origin/master` 当前 = **`b62d1df`**（`docs(stage5): PR-19 kickoff questions` 自身提交），且该提交已包含 PR-18 三件套（`useTaskStream.ts`/`types/agent.ts`/`services/agent.ts`）→ **PR-18 已 FF-merge 进 master**。
- **修订建议**：DECISION 改写 base 为「执行体开工时的 `origin/master` HEAD（当前 `b62d1df`），沿用 B5『不冻结』惯例」；并显式注明「PR-18 已合入 master，PR-19 可直接消费 `useTaskStream`/`agentApi`/`types`，Q6 对 hook 的修改是对已合代码的增量扩展（受 §求助 clause 9 守护）」，消除 PR-19↔PR-18 的顺序顾虑。

### B6 · Q7 六子渲染器缺后端 `artifact.data` 字段定义（执行体会频触 §求助 clause 11）

- **现状（初稿）**：`:259-293` Q7 要求 `ResultCard` 内对 6 类 `artifact.type` 各写特化子渲染器（`JdArtifact`/`ResumeArtifact`/`MatchScoreArtifact`/`CandidateMergeArtifact`/`CandidateProfileArtifact`/`GenericArtifact`）。
- **实测事实**：前端 `ResultArtifact.data` 类型为 `unknown`（`types/agent.ts:84` 注释「各 type 具体形状留 PR-19 卡片渲染时窄化」）；QUESTIONS **未列出任何一类 `artifact.data` 的具体字段**。后端 `_ARTIFACT_TYPE_MAP`（`engine.py:50-56`）只定义 type 映射，未在本 doc 给出各 `output` schema。
- **后果**：6 个子渲染器要「语义化字段展示」但不知道每类 `data` 长什么样，执行体只能猜 → 触发 §求助 clause 11「不知 data 具体字段 → 停下汇报」频繁发生，拖慢 TDD。
- **修订建议**：DECISION 在「实现约束」段**附 6 类 `artifact.data` 最小字段表**（或指向 backend skill output example / `engine.py:_build_artifacts` 的实际 `output` 形状）：`jd` / `resume` / `match_score`（含 `match_score_id`、`score` 等）/ `candidate_merge` / `candidate_profile` / `generic`。避免执行体臆测结构。

### B7 · Q2/Q3 与 PR-18 一致性收口（无矛盾，记录已核对）

- **现状（初稿）**：Q2 选项 A（纯 `useState`）、Q3 选项 A（不持久化）。
- **核对结论**：与 PR-18「最小依赖 / 不引入 store」原则一致，且 PR-18 hook 已封装全部 SSE 状态，前端 `useTaskStream` 自身即在 PR-18 范围。Q3 选项 A「F5 丢失」与后端 SSE 缓冲 30min TTL（`agent.py:333` 设 TTL）一致，属 MVP 可接受。**无矛盾，建议直接采纳**，仅在此记录已核对。

---

## C 类 · §求助边界修订（建议改写 1 条 + 新增 1 条）

### C1 · 改写 Q10 相关 clause（对应 A2）

- 若执行体在 PR-19 阶段发现 `CompareAnalysis.tsx` / `CandidateChat.tsx` 实为 Phase 2 占位页、无 `selectedIds` 可附着入口按钮 → **不得私自实现 CompareAnalysis 的候选人选择 UI**（超 §S5-13 边界），立即停下汇报，等待指挥官裁定入口归属（呼应 A2）。

### C2 · 新增 clause · Q6 字段以实测为准（对应 A1/B4）

- 若执行体实现 Q6 时发现：后端取消事件字段是 `message`（值 `"cancelled"`）而非 Q6 原文写的 `status` → **必须按 A1 修正（`data.message === 'cancelled'`）**，不得保留 `data.status` 判定或绕过；若对字段有疑义停下汇报（呼应 A1）。

### C3 · 保留 §求助 clause 11（artifact.data 字段未知，对应 B6）

- 原 `PR19-KICKOFF-QUESTIONS.md:638` clause 11「若前端不知道某类 artifact.data 具体字段 → 停下汇报，不猜结构」保留，配合 B6 的字段表补全，减少频触。

---

## D 类 · 待指挥官裁定的开放决策（与修订无关，纯采纳项）

以下在评估中判定「可直接采纳指挥官倾向（或经 A/B 修订后采纳）」，供指挥官一键确认：

| # | 建议 | 评估 |
|---|---|---|
| Q1 | 方案 A（严格 §S5-13 全量：2 页 + 8 Card + 10 用例） | ✅ 采纳（与 TASKS 唯一事实源一致，Stage 5 前端收官） |
| Q2 | 选项 A（纯 `useState` + 参数下钻） | ✅ 采纳（与 PR-18 最小依赖一致） |
| Q3 | 选项 A（不做 F5 持久化） | ✅ 采纳（MVP 可接受，B7 已核对） |
| Q4 | 选项 A（确认全接受 + 取消） | ✅ 采纳（**后端空 body 默认全接受已实测闭环，见 B1，无需再裁定**） |
| Q5 | 选项 A（顶部状态条 · 心跳绿点/断线红点） | ✅ 采纳（与 `useTaskStream.status`/`lastHeartbeatAt` 对齐） |
| Q6 | 选项 A（改 hook 终态判定 + TC-S5-13-11） | ✅ 采纳（**须按 A1 改 `data.message==='cancelled'` + `:110` 内联判定**，非 `data.status`/非 `isTerminal()`） |
| Q7 | 选项 A（6 子渲染器 + `never` 断言） | ✅ 采纳（**须补 artifact.data 字段表，见 B6**） |
| Q8 | 采纳布局 · skip-to-score 默认收起 | ✅ 采纳 |
| Q9 | 选项 A（Antd Select 双下拉） | ✅ 采纳（**数据源改 `resumeApi.list()`，见 B2**） |
| Q10 | problem-1 选项 A（URL query 预填） | ✅ 采纳（**problem-2 CompareAnalysis 附加删除，见 A2**） |
| Q11 | 采纳目录 + Antd Card | ✅ 采纳 |
| Q12 | 选项 A（Warning/Error 不可关闭） | ✅ 采纳 |
| Q13 | 集中 `EventCards.test.tsx` + `ChatCenter.test.tsx` + `CandidateChat.test.tsx` | ✅ 采纳（TC-S5-13-11 落 `hooks/useTaskStream.test.ts`） |
| Q14 | `N_after = 31 passed` | ✅ 采纳（**test files 改为 12 total = 9 既有 + 3 新，见 B3**） |
| B1 | 补 8 处 `exhaustive-deps` | ✅ 采纳（逐处评估，re-render 风险回滚 + `eslint-disable` 注释） |
| B2 | MSW stderr 顺手排查 | ✅ 采纳评估 |
| B3 | `agentApi` 不扩展 list | ✅ 采纳 |
| B4 | fixture `tests/fixtures/sseEvents.ts` | ✅ 采纳 |
| B5 | base ref | ✅ 采纳（**写实际 `origin/master` HEAD `b62d1df`，PR-18 已合，见 B5**） |
| B6 | 5 commit（Q6=A 含 hook 改 commit） | ✅ 采纳（`.fails` 增量移除，同 PR-18） |
| B7 | FF-merge 待更新文档 7 项 | ✅ 采纳 |
| §求助 | 11 clauses（改写 Q10 相关 / 新增 Q6 字段 clause） | ✅ 采纳（见 C1/C2/C3） |

---

## 裁定汇总（供指挥官勾选）

- [ ] **A1** Q6 终态判定：(a) 改 `data.message === 'cancelled'` + `useTaskStream.ts:110` 内联判定（推荐）/ (b) 维持 `data.status`（不推荐，必致 bug 残留）
- [ ] **A2** Q10 入口：(a) 删 problem-2、CandidateChat 仅 URL query（推荐）/ (b) 改挂 Resumes（留 Stage 5.1）/ (c) PR-19 实现 CompareAnalysis 选择 UI（不推荐）
- [ ] **B1** Q4 空 body：已实测闭环，直接采纳（默认采纳）
- [ ] **B2** Q9 数据源：`resumeApi.list()`（`/resumes`）（默认采纳）
- [ ] **B3** Q14 test files：12 total（9 既有 + 3 新）（默认采纳）
- [ ] **B4** Q6 措辞：改 `:110` 内联判定（默认采纳）
- [ ] **B5** base：`b62d1df` + 注明 PR-18 已合（默认采纳）
- [ ] **B6** Q7 artifact.data 字段表：DECISION 补 6 类字段（默认采纳）
- [ ] **B7** Q2/Q3 一致性：直接采纳（默认采纳）
- [ ] **C1/C2/C3** §求助改写/新增（默认采纳）
- [ ] **D** 全部采纳 Q1A/Q2A/Q3A/Q4(闭环)/Q5A/Q6A(按A1)/Q7A(按B6)/Q8/Q9A(按B2)/Q10(problem-1按A2)/Q11/Q12/Q13/Q14(按B3)/B1-B7/§求助

裁定后我出 `PR19-KICKOFF-DECISION.md`（参考 PR-18 DECISION 12 章结构），作为**唯一实施契约**；执行体阶段 4-5 commit TDD 落地 · 目标 `N_after = 31 passed` / 0 warnings / build ✓。
