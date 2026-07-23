# PR-19 KICKOFF DECISION · S5-13 前端 ChatCenter + CandidateChat + 8 类事件卡片

> **对象**:执行体(下一 session)· 作为**唯一实施契约**
> **文档角色**:主指挥官(用户)综合评估 QUESTIONS + REVISIONS 后的最终裁定书 · 出自 Claude Code (ark-code-latest)
> **权威依据**:
> - `docs/planning/stage5/PR19-KICKOFF-QUESTIONS.md`(687 行 · 主指挥官初稿)
> - `docs/planning/stage5/PR19-KICKOFF-REVISIONS.md`(副指挥官核验 · A1/A2 阻断级 + B1-B7 边角 + C1-C3 §求助 + D 采纳表)
> - `docs/planning/TASKS-STAGE5.md §S5-13`(线号 270-283)
> - `docs/planning/TEST-PLAN-STAGE5.md §二`(线号 99-110 · TC-S5-13-1..10)
> - `docs/api-contract.md §3.1–§3.5 / §4.1–§4.5`
> - `HANDOFF.md §9.3` 追债项 3 + `§9.4` 陷阱 4/5/6/8/10/11
> - `PR18-STEP6-REPORT.md §五 obs 3`(system:cancelled 边界)
> - 后端权威事实源:`backend/app/schemas/agent.py:80-85` / `backend/app/agent/orchestrator/engine.py:50-92` / `backend/app/api/v1/agent.py:100-176/195/246/333` / `backend/app/api/v1/endpoints/resume.py:143`
> - 前端权威事实源:`frontend/src/types/agent.ts:63-85` / `frontend/src/hooks/useTaskStream.ts:110-121` / `frontend/src/services/{resume,jd}.ts`
> **起手 master HEAD(base ref)**:**执行体开工时的 `origin/master` HEAD**(kickoff docs commit `b62d1df` 或 DECISION 合入后的下游 · **不冻结** · 与 PR-18 惯例一致)· 若开工时 master ≠ QUESTIONS/REVISIONS 中的 `b62d1df`,属预期 docs 推进,不触发 §十八 clause 1
> **测试基线**:后端 **120 passed** / 前端 **20 passed(9 test files)** / 前端 lint **0 errors / 8 warnings**
> **目标 N_after**:前端 **31 passed(12 test files)** / 前端 lint **0 errors / 0 warnings** / 后端 120 passed 维持(未触 backend/app,免跑但基线不倒退)/ build ✓

---

## 〇 · 顶层裁定汇总(执行体必读)

副指挥官 REVISIONS 全部采纳:

| 类 | 项 | 裁定 |
|---|---|---|
| **A 阻断级** | A1 · Q6 终态判定字段 | ✅ **强制**:改 `data.message === 'cancelled'` + `useTaskStream.ts:110` 内联判定;**禁止** `data.status`;**禁止** 引用不存在的 `isTerminal()` 函数名 |
| | A2 · Q10 CompareAnalysis 附加 | ✅ **撤销**:仅保留 problem-1 URL query;**禁止** 附加改动 `CompareAnalysis.tsx`(Phase 2 占位 · 无 selectedIds) |
| **B 边角** | B1 · Q4 空 body 已闭环 | ✅ 采纳:降级为已核实(engine.py:394 已证) |
| | B2 · Q9 数据源 | ✅ 改:`resumeApi.list()`;**禁止**引用不存在的 `candidateApi.list()` |
| | B3 · Q14 test files 算术 | ✅ 修正:9 既有 + 3 新 = **12 total** |
| | B4 · Q6 措辞 | ✅ 采纳:统一改为 `useTaskStream.ts:110` 内联判定(与 A1 同源) |
| | B5 · base ref | ✅ 采纳:`b62d1df` 起 + 明注 PR-18 已合 |
| | B6 · Q7 artifact.data 字段表 | ✅ 采纳:DECISION 补 6 类实际字段(见 §三.7) |
| | B7 · Q2/Q3 一致性 | ✅ 采纳:与 PR-18 最小依赖一致 |
| **C §求助** | C1 CompareAnalysis 边界 | ✅ 采纳(改写 · 见 §七 clause 7) |
| | C2 Q6 字段以实测为准 | ✅ 采纳(新增 · 见 §七 clause 12) |
| | C3 保留 artifact.data 边界 | ✅ 采纳(见 §七 clause 11) |
| **D 全采纳** | Q1-Q14 / B1-B7 主体 | ✅ 一次性采纳(见 §一-§六) |

---

## 一 · PR 边界(Q1 决定)

**方案 A · 严格 §S5-13 全量交付**(采纳):

- **交付面**:2 pages + 8 Cards + 6 artifact 子渲染器 + 3 test files + 1 fixture · 共约 **~20 前端文件**
- **禁止**:
  - 引入 zustand / redux / Context Store(Q2 A · 纯 useState)
  - 引入任何 `services/agent.ts` 之外的新 service · agentApi 不扩展 list 端点(B3)
  - 附加改动 `frontend/src/pages/CompareAnalysis.tsx`(A2 撤销)
  - 附加改动 `frontend/src/pages/Resumes.tsx` 或其他既有页(留 Stage 5.1)
  - 触碰 `backend/app/**`(纯前端 PR · pytest 免跑但基线不倒退)
  - 触碰 `docs/api-contract.md`(严格对齐既有契约)
- **允许**(**明确扩容**):
  - **修改 PR-18 交付的 `frontend/src/hooks/useTaskStream.ts:110`**(Q6 = A · 唯一破 "PR-19 不改基建" 原则的授权点 · 受 §七 clause 9 守护)
  - 补齐 8 处 `react-hooks/exhaustive-deps` warning(B1 授权)
  - MSW stderr 顺手排查(B2 授权 · 若不可静音则回滚 + 报告)

---

## 二 · 状态管理与持久化

### Q2 (选项 A · 采纳)· 纯 `useState` + 参数下钻

- `ChatCenter.tsx` 用组件本地 state:`messages: Message[]`(用户消息 + agent 卡片时序) + `activeTaskId: string | null` + `plan: Plan | null`(WAITING_CONFIRMATION 后)
- 通过 `useTaskStream({taskId: activeTaskId})` 获取 SSE events
- 8 类 Card 接 `event: SSEEvent` prop · 无状态传递

### Q3 (选项 A · 采纳)· 不做 F5 持久化

- 每次页面加载 = 全新 session,`activeTaskId = null`
- 后端 SSE 缓冲 30 分钟 TTL 已提供有限恢复能力,但 UI 侧不消费(Stage 5.1 补任务列表页时再接)

---

## 三 · 组件与页面口径

### 3.1 · Q4 (选项 A · 采纳)· PlanCard 最小可用交互

**行为**:
- 展示 Plan.steps(只读列表 · 每 step 显示 `description / tool_name / params(JSON pretty)`)
- 「确认执行」按钮 → `agentApi.executePlan({task_id: activeTaskId})`(**空 body,不传 accepted_steps/modifications**)
- 「取消」按钮 → `agentApi.cancelTask(activeTaskId)`

**后端行为已实测坐实**(B1 闭环):
- `backend/app/schemas/agent.py:84-85`:`accepted_steps` / `modifications` 默认 `None`
- `backend/app/agent/orchestrator/engine.py:394`:`if accepted_steps is not None:` 才过滤
- ∴ 空 body → **默认全步执行**,不需前端传字段

**禁止**:实现 step 勾选 / 参数编辑 UI(超边界)

### 3.2 · Q5 (选项 A · 采纳)· 顶部状态条 · 心跳 + 断线指示

**布局**:ChatCenter 顶部固定状态条,组件 `<StreamStatusBar />` 消费 `useTaskStream` 返回的 `{status, lastHeartbeatAt, latestByType.system}`

**显示规则**:

| `status` | 表现 |
|---|---|
| `idle` | 隐藏或灰点 · "未连接" |
| `connecting` | 蓝点 · "连接中..." |
| `streaming` | 绿点 · `最后心跳 Ns 前`(每秒 tick 更新 · 使用 `lastHeartbeatAt`) |
| `closed` | 灰点 · "已完成"(或 Q6 补:"已取消") |
| `error` | 红点 · "已断开(重连失败)" |

**system 事件 message 内容**:`latestByType.system?.data.message` 展示为辅助文字(如 "任务已排队" · "任务已取消"),**不进 events 时序列表**

### 3.3 · Q6 (选项 A · 采纳 · **按 A1 修正**)· `system:cancelled` 纳入终态判定

**修改点**:`frontend/src/hooks/useTaskStream.ts:110` 内联终态判定

**改前**(PR-18 现状):
```typescript
if (typed === 'result' || typed === 'error') {
  hasReachedTerminalRef.current = true;
}
```

**改后**(A1 修正版 · 权威):
```typescript
// A1 修正:与后端 agent.py:195 _is_terminal(data.message === 'cancelled') 对齐;
// SystemData(types/agent.ts:63-65)仅 message 字段,无 status。
if (
  typed === 'result' ||
  typed === 'error' ||
  (typed === 'system' && (data as { message?: string })?.message === 'cancelled')
) {
  hasReachedTerminalRef.current = true;
}
```

**关键约束**(执行体必读):
1. **禁止** `data.status === 'cancelled'`(字段不存在,恒为 false,退化为 PR-18 bug)
2. **禁止** 引用 `isTerminal(event)` 函数名(PR-18 hook 无此函数,是内联判定)
3. **禁止** 扩展到其他 system 事件(如 `system:queued` · `system:started`)—— 只有 `message === 'cancelled'` 是终态
4. 追加 TC-S5-13-11 落 `frontend/tests/hooks/useTaskStream.test.ts`(既有文件追加,不算新 file)

**允许**(§七 clause 9 守护下的改动):
- PR-18 既有 TC-S5-12-1..4 **不许回归**;若追加分支导致既有测试挂,立即停下汇报
- 追加分支不影响 `status='closed'` 判定路径(hook 现状:接到终态即 `status='closed'` 不重连)

### 3.4 · Q7 (选项 A · 采纳 · **按 B6 补 artifact.data 字段表**)· 追债 3 exhaustiveness 护栏激活

**权威事实**(`backend/app/agent/orchestrator/engine.py:59-92`):artifact **分两类**

**Class-A · 引用型**(`type ∈ {jd, resume, match_score}`):
- 结构:`{step_id, tool_name, type, ref_id: string}` · **无 `data` 字段**
- 前端渲染路径:接 `ref_id` → REST 拉详情 → 渲染
- 对应 REST:
  - `jd` · `GET /jds/{jd_id}` → `JDResponse`(既有 `jdApi.getById()`)
  - `resume` · `GET /resumes/{resume_id}` → `ResumeResponse`(既有 `resumeApi.getById()`)
  - `match_score` · `GET /match-scores/{score_id}` → `MatchScoreResponse`(既有 `matchApi.getById()` · 项目内 Stage 4 就位)

**Class-B · 数据型**(`type ∈ {candidate_merge, candidate_profile, generic}`):
- 结构:`{step_id, tool_name, type, data: <output>}` · **无 `ref_id`,有 `data`**
- 前端渲染路径:直接消费 `data`,不发 REST

**6 类 artifact.data 字段表**(权威 · 出自后端 skill.yaml `output_schema`):

**`candidate_merge`** · `backend/app/agent/skills/candidate_merge/v1_0_0/skill.yaml`:
```typescript
interface CandidateMergeData {
  action: 'MERGE' | 'SUGGEST' | 'KEEP_SEPARATE';
  master_resume_id: string | null;
  merged_fields?: Record<string, unknown>;
  confidence: number;  // 0-1
  conflicts?: { field: string; values: unknown[] }[];
  recommendation: string;
}
```

**`candidate_profile`** · `backend/app/agent/skills/candidate_profile/v1_0_0/skill.yaml`:
```typescript
interface CandidateProfileData {
  profile_tags: string[];
  summary: string;
  strengths: string[];
  risks: string[];
}
```

**`generic`** · fallback,`data: unknown`(展示为 `<pre>{JSON.stringify(data, null, 2)}</pre>`)

**引用型 3 类字段表**(前端直接消费 REST 响应,`ref_id` 只用于 GET):

- **`jd`** · `ref_id = jd_id`(参考 `frontend/src/types/jd.ts::JDResponse`)
- **`resume`** · `ref_id = resume_id`(参考 `frontend/src/types/resume.ts::ResumeResponse`)
- **`match_score`** · `ref_id = score_id`(参考 `frontend/src/types/match.ts::MatchScoreResponse` · 含 `overall_score / dimension_scores / matching_skill_id`)

**目录结构**(采纳):
```
frontend/src/components/agent/
├── CardContainer.tsx           - 共享 header + 时间戳
├── ThinkingCard.tsx
├── PlanCard.tsx                - Q4 交互
├── ToolCallCard.tsx
├── ProgressCard.tsx            - <Progress percent={n} />
├── ResultCard.tsx              - switch(artifact.type) 分派 + never 断言
├── ErrorCard.tsx
├── WarningCard.tsx
├── SystemCard.tsx              - 保留导出;实际不进 events[] 而进顶部条(见 3.2)
├── StreamStatusBar.tsx         - 顶部状态条
├── artifacts/
│   ├── JdArtifact.tsx          - 引用型 · props: {ref_id} · 内部 useEffect 拉 GET /jds/{id}
│   ├── ResumeArtifact.tsx      - 引用型 · props: {ref_id} · 内部 useEffect 拉 GET /resumes/{id}
│   ├── MatchScoreArtifact.tsx  - 引用型 · props: {ref_id} · 内部 useEffect 拉 GET /match-scores/{id}
│   ├── CandidateMergeArtifact.tsx    - 数据型 · props: {data: CandidateMergeData}
│   ├── CandidateProfileArtifact.tsx  - 数据型 · props: {data: CandidateProfileData}
│   └── GenericArtifact.tsx     - fallback · props: {data: unknown}
└── index.ts
```

**ResultCard exhaustiveness 模板**(权威):
```typescript
function renderArtifact(artifact: ResultArtifact): React.ReactNode {
  switch (artifact.type) {
    case 'jd':
      return artifact.ref_id ? <JdArtifact ref_id={artifact.ref_id} /> : <GenericArtifact data={artifact.data} />;
    case 'resume':
      return artifact.ref_id ? <ResumeArtifact ref_id={artifact.ref_id} /> : <GenericArtifact data={artifact.data} />;
    case 'match_score':
      return artifact.ref_id ? <MatchScoreArtifact ref_id={artifact.ref_id} /> : <GenericArtifact data={artifact.data} />;
    case 'candidate_merge':
      return <CandidateMergeArtifact data={artifact.data as CandidateMergeData} />;
    case 'candidate_profile':
      return <CandidateProfileArtifact data={artifact.data as CandidateProfileData} />;
    case 'generic':
      return <GenericArtifact data={artifact.data} />;
    default: {
      const _exhaustive: never = artifact.type;
      return <GenericArtifact data={artifact.data} />;  // runtime fallback
    }
  }
}
```

**关键约束**:
- ref_id 为 undefined 时降级到 GenericArtifact(不 throw)· 与后端 `_build_artifacts:88` 「ref_id 未提取 → 降级 generic」逻辑对齐
- 引用型子渲染器内部拉 REST 时 loading/error 态由子组件自理(展示 `<Spin />` / `<Alert type="error" />`);测试面可以 mock REST 拉取

### 3.5 · Q8 (采纳)· ChatCenter 布局

```
┌─────────────────────────────────────────────┐
│ <StreamStatusBar />  (3.2)                  │
├─────────────────────────────────────────────┤
│ <SkipToScorePanel />  Antd Collapse 默认收起 │
│   [JD Select] [Resume Multi-Select] [立即评分] │
├─────────────────────────────────────────────┤
│ <MessageTimeline />  events + user msgs      │
│   滚动区 · 每 event 一 Card                   │
├─────────────────────────────────────────────┤
│ <MessageInput />  [Textarea] [发送]          │
└─────────────────────────────────────────────┘
```

### 3.6 · Q9 (选项 A · 采纳 · **按 B2 改数据源**)· skip-to-score UI

**权威事实**(REVISIONS B2):
- 前端 `candidateApi.list()` **不存在**(仅 `getStatusMeta` / `updateStatus`)
- 前端 `resumeApi.list()` 存在(`services/resume.ts:41-43` · `GET /resumes`)
- 后端 `skip_to_score:148-151` 把 `candidate_ids[i]` 当 `resume_id` 塞进 tool_input

**实现约束**:
- JD 下拉:`jdApi.list()` → 单选(Antd `<Select showSearch>`)· value 是 `jd_id`
- 候选人下拉:**`resumeApi.list()`** → 多选(Antd `<Select mode="multiple" maxTagCount={5}>`)· value 是 `resume_id` · 标签显示可用 `candidate_name`(取自 `ResumeResponse.candidate_name`)
- 「立即评分」按钮 → `agentApi.skipToScore({jd_id, candidate_ids})`(仍传字段名 `candidate_ids` · 后端按 resume_id 语义解释)
- 上限 20 候选人(前端 UI 约束,不属后端契约)
- **禁止**:引用 `candidateApi.list()`(不存在,编译期报错)

### 3.7 · Q10 (problem-1 · A2 采纳 · **problem-2 撤销**)· CandidateChat 入口

**采纳**(problem-1):
- CandidateChat 从 URL query 解析:`/candidate-chat?candidates=uuid1,uuid2`
- 组件用 `useLocation().search` → 解析 `candidates` → 得 `candidate_ids: string[]`
- 无 query 时兜底空数组(组件仍可运行,用户手输)
- 发起 `agentApi.chat({message, context: {candidate_ids}})`

**撤销**(problem-2):
- **禁止** 附加改动 `frontend/src/pages/CompareAnalysis.tsx` · Phase 2 占位页无 selectedIds 附着点(见 REVISIONS A2)
- **禁止** 附加改动 `Resumes.tsx` 或其他既有页 · 留 Stage 5.1
- TC-S5-13-6 通过 `MemoryRouter initialEntries={['/candidate-chat?candidates=a,b']}` 测试,无需真实入口

### 3.8 · Q11-Q12 (采纳)· Card 视觉

- Antd `<Card size="small" title={<Space>...icon + 时间戳 + step_id</Space>}>` 统一 header
- 颜色区分(采纳):
  - `thinking` · info(蓝)
  - `plan` · primary
  - `tool_call` · info
  - `progress` · 无色 + `<Progress percent={n} />`
  - `result` · success(绿)
  - `error` · error(红)
  - `warning` · warning(黄)
  - `system` · **不进列表**(见 3.2)
- **Q12 采纳**:Warning/Error 卡片**不可关闭**(dismiss 交互 = 破 events 时序一致性)

---

## 四 · 测试策略

### 4.1 · Q13 (采纳)· TC 落点组织

**3 个新 test file + 1 个既有文件追加**:

| TC | 落点 | 验证内容 |
|---|---|---|
| TC-S5-13-1 | `frontend/tests/pages/ChatCenter.test.tsx` | 输入 → mock chat → mock SSE plan → PlanCard 出现 → click 确认 → `executePlan` 被调 |
| TC-S5-13-2 | `frontend/tests/pages/ChatCenter.test.tsx` | 展开 skip-to-score → 选 JD/resume → click → `skipToScore` 被调 + mock SSE progress → 进度卡片显示 |
| TC-S5-13-3 | `frontend/tests/components/agent/EventCards.test.tsx` | 手工造 8 类 SSEEvent → 断言 7 类 Card 组件出现(system 顶部条不进列表) |
| TC-S5-13-4 | `frontend/tests/pages/ChatCenter.test.tsx` | msw mock SSE 断线 → 重连后同 id 不重复渲染(hook 已保证,页面再断一次) |
| TC-S5-13-5 | `frontend/tests/pages/ChatCenter.test.tsx` | PlanCard 出现 → click 取消 → `cancelTask` 被调 |
| TC-S5-13-6 | `frontend/tests/pages/CandidateChat.test.tsx` | `MemoryRouter initialEntries={['/candidate-chat?candidates=a,b']}` → 发送 → chat req.body.context.candidate_ids === ['a','b'] |
| TC-S5-13-7 | `frontend/tests/components/agent/EventCards.test.tsx` | warning 事件 → WarningCard 显示 message |
| TC-S5-13-8 | `frontend/tests/components/agent/EventCards.test.tsx` | system 事件 → 不进 events 列表 · 顶部条显示 message |
| TC-S5-13-9 | `frontend/tests/pages/ChatCenter.test.tsx` | mock SSE `system:cancelled` → 顶部条显示 "已取消" · 非 ErrorCard |
| TC-S5-13-10 | `frontend/tests/components/agent/EventCards.test.tsx` | error 事件 → ErrorCard 显示 message |
| **TC-S5-13-11** (追加 · 授权) | `frontend/tests/hooks/useTaskStream.test.ts`(追加,不算新 file) | msw 发 `event: system {message: 'cancelled'}` → hook `hasReachedTerminalRef=true` → `status='closed'` 不重连 |

### 4.2 · Q13b (采纳)· SSE mock helper 复用

- 复用 PR-18 建立的 msw v2 `http.get + ReadableStream` 范式
- 建议 extract 到 `frontend/tests/helpers/sseMock.ts`(若 PR-18 未 extract 则 PR-19 顺手 extract)
- `helpers/sseMock.ts` 导出:`makeSseHandler(url, frames: SSEFrame[])` / `SSEFrame = {id, event, data}`

### 4.3 · B4 (采纳)· fixture 位置

- `frontend/tests/fixtures/sseEvents.ts`:导出 8 类事件工厂函数
  - `makeThinkingEvent(id, content) → SSEEvent<ThinkingData>`
  - `makePlanEvent(id, plan) → SSEEvent<Plan>`
  - `makeToolCallEvent(id, {tool_name, params, step_id}) → SSEEvent<ToolCallData>`
  - `makeProgressEvent(id, {step_id, progress, message}) → SSEEvent<ProgressData>`
  - `makeResultEvent(id, {content, artifacts?}) → SSEEvent<ResultData>`
  - `makeErrorEvent(id, {code, message}) → SSEEvent<ErrorData>`
  - `makeWarningEvent(id, {message, suggestion?}) → SSEEvent<WarningData>`
  - `makeSystemEvent(id, {message}) → SSEEvent<SystemData>`(含特化 `makeSystemCancelledEvent(id)`)

### 4.4 · Q14 (采纳 · **按 B3 修正**)· N_after 目标

**基线**:20 passed / **9 test files** / lint 0 errors / 8 warnings

**目标**:
- **N_after = 31 passed**(20 + 10 + 1)
- **test files = 12 total**(9 既有 + 3 新)· 追加 TC-S5-13-11 不新增 file
- **lint = 0 errors / 0 warnings**(B1 补齐 8 处 exhaustive-deps)
- **build = ✓**
- **后端 = 120 passed 维持**(未触 backend/app,免跑但基线不倒退)

---

## 五 · 边角项裁定汇总

### B1 (采纳)· `react-hooks/exhaustive-deps` 补齐

- 目标:8 warnings → 0
- 策略:逐处评估
  - 数据 hook 忘 deps → 补
  - unmount cleanup / 稳定 ref → 加 `// eslint-disable-next-line react-hooks/exhaustive-deps` 单行注释,说明原因
- **回滚门**:某处补 dep 后 test 挂或触发 re-render loop → 立即 revert 该处 + 加 disable-next-line,继续下一处
- STEP6 报告需列出 8 处逐一处理方式(补 dep vs disable-next-line + 原因)

### B2 (采纳评估)· MSW stderr 噪声

- 顺手在 `vitest.setup.ts` 或 `tests/setup.ts` 试:
  - `server.listen({ onUnhandledRequest: 'bypass' })`(降级未 mock 请求为 pass 而非 error log)
  - 或 msw v2 `http` handler 的 `verbose: false`
- 若排查发现无稳定 mute 途径 → STEP6 记为「已评估无解」,不阻塞交付

### B3 (采纳)· agentApi 不扩展 list

- **禁止** 引入 `agentApi.list()` / `agentApi.listTasks()` 等
- 未来 Stage 5.1 任务列表页再补

### B4 (采纳)· fixture 位置

- 见 4.3

### B5 (采纳)· base ref

- base = **执行体开工时的 `origin/master` HEAD**(kickoff docs 三件套合入后)· 不冻结
- 若开工时 master ≠ `b62d1df`,属预期 docs-only 推进,**不触发 §七 clause 1**
- **PR-18 已合入 master**:`useTaskStream` / `agentApi` / `types/agent.ts` 可直接消费;Q6 对 hook 的修改是对已合代码的增量扩展(受 §七 clause 9 守护)

### B6 (采纳)· artifact.data 字段表

- 见 §3.4(6 类字段表已在 DECISION 内定权威)
- 执行体不允许自己去 read backend skill.yaml 猜结构(阻塞时用 §七 clause 11 停下汇报)

### B7 (采纳)· Q2/Q3 一致性

- Q2 A `useState` + Q3 A 无持久化 · 与 PR-18 最小依赖原则一致 · 无矛盾

---

## 六 · Commit 拆分建议(执行体阶段)

**5 commit 结构**(TDD · 采纳 B6):

1. **`test(stage5): PR-19 red-test skeleton (TC-S5-13-1..11) + Card/Artifact scaffold + fixtures`**
   - 建 `frontend/tests/pages/{ChatCenter,CandidateChat}.test.tsx` + `frontend/tests/components/agent/EventCards.test.tsx`
   - 建 `frontend/tests/fixtures/sseEvents.ts` + `frontend/tests/helpers/sseMock.ts`(若 PR-18 未 extract)
   - `frontend/tests/hooks/useTaskStream.test.ts` 追加 TC-S5-13-11
   - 全部测试用 `test.fails` 或 `test.skip`(参 PR-18 obs 1 · vitest 严格语义)
   - 建 8 类 Card + 6 artifact 子渲染器空骨架(仅 export function 签名,body `return null`)
   - `useTaskStream.ts:110` 暂不改(留 commit 5 授权改动)
   - 期望:红态 · 11 个 `.fails` 提供真实红信号

2. **`feat(stage5): S5-13 Card 基座 + 6 artifact 子渲染器 + never 断言(追债 3 激活)`**
   - 落 CardContainer + 8 类 Card 组件(含 SystemCard 导出但不进列表)
   - 落 6 artifact 子渲染器(3 引用型 + 3 数据型 + GenericArtifact fallback)
   - `ResultCard.tsx` 落 switch/never 断言
   - StreamStatusBar 顶部条组件
   - 期望:TC-S5-13-3 / TC-S5-13-7 / TC-S5-13-8 / TC-S5-13-10 转绿(EventCards.test.tsx 全绿)
   - 移除对应 `.fails`

3. **`feat(stage5): S5-13 ChatCenter 页面 + 消息时序 + PlanCard 交互 + skip-to-score`**
   - `frontend/src/pages/ChatCenter.tsx` 完整实现(替换 PlaceholderPage)
   - MessageInput + MessageTimeline + SkipToScorePanel
   - PlanCard 确认/取消按钮 → agentApi 调用
   - `resumeApi.list()` + `jdApi.list()` 拉列表(B2 修正)
   - 期望:TC-S5-13-1 / TC-S5-13-2 / TC-S5-13-4 / TC-S5-13-5 转绿
   - 移除对应 `.fails`

4. **`feat(stage5): S5-13 CandidateChat 页面 + URL query 预填 context`**
   - `frontend/src/pages/CandidateChat.tsx` 完整实现(替换 PlaceholderPage)
   - `useLocation().search` 解析 `candidates` → 预填 context
   - **不改** CompareAnalysis / Resumes(A2 撤销)
   - 期望:TC-S5-13-6 转绿

5. **`feat(stage5): S5-13 useTaskStream cancel terminal + system:cancelled UI + exhaustive-deps 补齐`**
   - **修改 `frontend/src/hooks/useTaskStream.ts:110`** 内联判定(A1 权威版本 · `data.message === 'cancelled'`)
   - StreamStatusBar 增加 "已取消" 状态分支
   - 补齐 8 处 `react-hooks/exhaustive-deps` warning
   - 期望:TC-S5-13-9 / TC-S5-13-11 转绿,前端 lint 0 warnings
   - 若 vitest `.fails` 严格语义导致中间 commit 转绿"意外通过判失败" → **`.fails` 移除增量并入实现落地的 commit**(PR-18 obs 1 已建立此适配,执行体应能处理)

**allowed commit reordering**:执行体如果发现 5 commit 拆分不适应真实开发节奏(比如 CandidateChat 内容太少不值单开一个 commit)· 允许合并为 4 commit,但需在 STEP6 §五 observation 说明;不允许拆分为 >5 commit(避免过度切分)。

---

## 七 · §求助边界(执行体停下并报告)

**12 条 clauses**(承接 PR-18 · 采纳 C1/C2 修订 · 新增 clause 12):

1. **仓库状态偏移**:master ≠ 起手 HEAD 或工作树 `frontend/src` 未提交改动 → 停下汇报
2. **前端 test 基线丢失**:开工前跑 `npm run test` 若 ≠ 20 passed / 9 test files → 停下汇报
3. **msw v2 SSE mock 失败**:如 fetch stream mock 在多次断连/重连场景下有故障(超出 PR-18 建立的 mock 范式) → 停下汇报
4. **PlanCard 交互与后端契约冲突**:如 `executePlan({task_id})` 空 body 后端 raise 400(与 B1 实测冲突)→ 停下汇报;**不许自行传 accepted_steps=[] 绕过**
5. **追债项 3 exhaustiveness 未激活**:如 6 子渲染器未真正落到 switch/never 分支 → 停下汇报
6. **前端 test 基线倒退**:任何时刻 test 数减少 → 停下汇报
7. **顺手扩范围 · CompareAnalysis / Resumes / 其他既有页**:若发现诱惑改这些页(如为 CandidateChat 加入口)→ 停下汇报;**A2 已明确禁止 CompareAnalysis 附加**;若发现 CompareAnalysis 实为占位不能挂按钮,**不得私自实现候选人选择 UI**(C1 授权)
8. **B1 补 deps 后测试挂**:某处补 deps 引入 re-render loop → 立即回滚该处 + 加 `eslint-disable-next-line` 注释,STEP6 记录 · 不停下汇报(有明确回滚门,允许自处理)
9. **hook 终态判定改动导致 PR-18 用例回归**:Q6 = A 采纳后修改 `useTaskStream.ts:110`,若 PR-18 TC-S5-12-1..4 挂 → 停下汇报,**不许强改 PR-18 测试**
10. **误触 `backend/app`**:PR-19 应为纯前端 PR · 若诱惑改后端(如为 cancel UX 让后端改 SSE 契约)→ 停下汇报
11. **artifact 子渲染器格式误判**:如 §3.4 字段表未覆盖某类新增 artifact.type(后端偷偷加了),或 API 返回不符预期 → 停下汇报,**不猜结构**
12. **Q6 字段以实测为准**(C2 新增):若执行体实现 Q6 时对 cancel 字段判定有疑义(比如后端 SSE 帧格式变了)→ 停下汇报;**不得保留 `data.status` 判定** 也 **不得绕过判定用其他信号**(如 `latestByType.system` 存在 判为 cancel);字段唯一权威是 `data.message === 'cancelled'`

---

## 八 · 验收三道门

**门 1 · pytest**:
- 未触 `backend/app` 则**免跑**(依据本 DECISION §一 边界)
- 但基线必须维持 **120 passed**(若执行体不小心触了 backend 需跑全量,失败即停下)

**门 2 · 前端 test**:
- `cd frontend && npm run test`
- 期望:`Test Files 12 passed | Tests 31 passed`
- **0 failed / 0 expected fail**(所有 `.fails` 已增量移除)

**门 3.1 · 前端 lint**:
- `cd frontend && npm run lint`
- 期望:**0 errors / 0 warnings**(B1 补齐 8 处 exhaustive-deps)

**门 3.2 · 前端 build**:
- `cd frontend && npm run build`
- 期望:`✓ built in Xs`(编译过 · Xs < 10s 参考)

**STEP6 报告须内嵌**:3 道门各自的命令输出片段(至少末尾 5 行),证明实测通过。

---

## 九 · 交付物与文件影响面

**新建**(约 20 文件):

| 类 | 文件 |
|---|---|
| pages | `frontend/src/pages/ChatCenter.tsx`(替换) + `frontend/src/pages/CandidateChat.tsx`(替换) |
| components/agent | `CardContainer.tsx` + 8 类 Card + `StreamStatusBar.tsx` |
| components/agent/artifacts | `JdArtifact.tsx` + `ResumeArtifact.tsx` + `MatchScoreArtifact.tsx` + `CandidateMergeArtifact.tsx` + `CandidateProfileArtifact.tsx` + `GenericArtifact.tsx` |
| components/agent | `index.ts`(barrel re-export) |
| tests/pages | `ChatCenter.test.tsx` + `CandidateChat.test.tsx` |
| tests/components/agent | `EventCards.test.tsx` |
| tests/fixtures | `sseEvents.ts` |
| tests/helpers | `sseMock.ts`(若 PR-18 未 extract 则本 PR extract) |

**修改**:

| 文件 | 改动 |
|---|---|
| `frontend/src/hooks/useTaskStream.ts` | `:110` 内联终态判定扩展(A1 权威版) |
| `frontend/tests/hooks/useTaskStream.test.ts` | 追加 TC-S5-13-11 |
| 若干含 `react-hooks/exhaustive-deps` warning 的既有文件 | 逐处补 deps 或加 disable-next-line 注释(B1) |

**禁止改动**(§一 硬边界):

- `backend/app/**`
- `docs/api-contract.md`
- `frontend/src/pages/CompareAnalysis.tsx` / `Resumes.tsx` / 其他 Stage 4/2/3 既有页
- `frontend/src/types/agent.ts`(PR-18 已定,PR-19 消费)
- `frontend/src/services/agent.ts`(PR-18 已定 5 函数,PR-19 消费,不扩展)
- `frontend/vite.config.ts`(与 PR-18 一致,不开 typecheck)

---

## 十 · FF-merge 后待更新文档清单(执行体不做,主指挥官统一)

参考 PR-18 §十二 结构 · **共 7 项**:

1. **`HANDOFF.md §9.1`** 状态表:PR-19 = ✅(final commit);前端基线 `20 → 31 passed`;后端 120 passed 维持;master HEAD 更新到 PR-19 tip;PR-19 列 "**Stage 5 前端收官**"
2. **`HANDOFF.md §9.3`** 追债项 3:标记「PR-19 收敛 · exhaustiveness 护栏激活」
3. **`HANDOFF.md §9.4`** 陷阱表:
   - 陷阱 10 · system:cancelled:更新为「PR-19 已扩展 hook 终态判定(`data.message === 'cancelled'`)」标记收敛
   - 新增/更新 · **B1 exhaustive-deps 清扫完成**
4. **`HANDOFF.md §9.5`** 新文件表:追加约 20 新文件(2 pages + 8 Cards + StreamStatusBar + 6 artifacts + index + 3 tests + fixture + helper)
5. **`HANDOFF.md §9.6`** 改写为 **Stage 5 前端收官声明**(Stage 5.1 待启动 · 列 12 条开放项状态)
6. **`TASKS-STAGE5.md`**:
   - §S5-13 owner → **PR-19**
   - §五 清扫项:B1 状态 = ✅ PR-19 收敛
7. **记忆 `stage5-progress-and-known-limits.md`**:PR-19 合入 · 前端基线 31 passed · Stage 5 前端全量落地 · 追债 3 收敛 · 陷阱 10 收敛

---

## 十一 · 主指挥官声明

- 本 DECISION 是**唯一实施契约**,执行体不得偏离 §一-§六 主体裁定;偏离必须落 STEP6 §五 observation 说明,并**触发 §七 相关 clause**
- 副指挥官 REVISIONS 全部采纳:A1 / A2 阻断级修订 + B1-B7 边角吸收 + C1-C3 §求助修订
- Q6 对 PR-18 hook 的修改是**唯一破 "PR-19 不改基建" 原则的授权点**,受 §七 clause 9 守护 —— PR-18 既有测试**不许回归**
- STEP6 报告须**内嵌 3 道门实测输出片段**(参 PR-18 STEP6 结构),证明基线达标

---

## 十二 · 起手 checklist(执行体第一件事)

1. 核验 `git status` 干净 · `git branch --show-current` = `master`
2. 核验 `git log --oneline -3` HEAD 是本 DECISION 合入后的 tip
3. 跑 `cd frontend && npm run test` 确认基线 **20 passed / 9 files**;若 ≠ → §七 clause 2 停下
4. 跑 `cd frontend && npm run lint` 确认基线 **0 errors / 8 warnings**;若 errors > 0 → 停下汇报
5. 建 feat 分支:`git checkout -b feat/pr-19-s5-13-frontend-chat-cards`
6. 阶段 1 · commit 1 · 红骨架(参 §六)
7. 阶段 2-5 · commit 2-5 · 见 §六
8. 阶段 6 · 跑 3 道门验证(§八)· 写 STEP6 报告
9. push 分支 → 报告主指挥官进行 FF-merge 评审(**不自动 FF-merge**)

---

_END OF DECISION_
