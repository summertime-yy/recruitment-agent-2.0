# MVP 手工验收 · KICKOFF-DECISION

> 关联：`docs/planning/stage5/MVP-VERIFY-KICKOFF-QUESTIONS.md`（commit `916daf8`）
> 用户裁定：**全采纳建议**（§Q1-§Q13 + §求助边界 6 条 + §附执行流水）
> 类型：docs-only 验收活动，直接 commit 到 master（AGENTS.md §4.1）
> 起始 master HEAD：`916daf8`（含本 DECISION 之前 = `46caeca`）
> 分工：**你跑 UI · 我做后端伴跑**（LLM 已配置 `backend/.env`）
> Baseline：pytest 131/1 skipped · ruff 0 全仓 · frontend build ✓ · migration head `b6c7d8e9f0a1`

---

## 一、执行契约（§Q 逐项裁定）

| # | 议题 | 裁定 | 落地动作 |
|---|------|------|----------|
| Q1 | 起服环境 | `docker compose ps` 先看，缺服务再补齐 | Step 1 后端伴跑 |
| Q2 | 数据准备 | **全走 UI** | Step 4-5 你操作 |
| Q3 | SSE 验证 | 双方式并行（前端 devtools + 后端 curl 抓原始流） | Step 6-7 你我并行 |
| Q4 | Terminal 语义 | 进 §6 前**我 grep** `engine.py` 确认 terminal 信号；如有文档歧义**顺清 CHECKLIST §6** | Step 3.5 后端伴跑 |
| Q5 | CancelTask 覆盖 | **只测 executing + WAITING_CONFIRMATION**；scoring 登记为"非阻塞未覆盖" | Step 8 你操作 |
| Q6 | dev 库冲突 | **先快照 6 表行数，再 TRUNCATE 六表**（tasks/executions/match_scores/jds/resumes/candidates），保留 skills/skill_versions/skill_execution_logs | Step 2 我操作 |
| Q7 | Bug 分级 | 认同 P0/P1/P2；**仅修不能 workaround 的 P0**；P0 hotfix 最多 1 文件、不改 schema、不改 migration | Step 9 |
| Q8 | 通信 pattern | 你每节完告诉我 `§N 完成/卡住 · <一句话>`；卡住贴 Console 报错 + Network 状态码 | 全程 |
| Q9 | 时间预算 | **一口气跑完 §1-§9**（顺利 90-110min，含 P0 hotfix 150-180min） | 全程 |
| Q10 | Report 命名 | `docs/planning/stage5/MVP-VERIFY-RUN-REPORT.md`；commit 信息 `docs(stage5): MVP end-to-end verify run report (2026-07-28)` | Step 9 |
| Q11 | Bug 双写 | **当场双写**：run report §Bug 表 + HANDOFF §9.3 追加条目 | 全程 |
| Q12 | SSE 陷阱 11 前置 grep | **顺便 grep**（fetch + ReadableStream vs EventSource），违规写入 report | Step 3 我操作 |
| Q13 | 验收后数据清理 | **保留**（可作后续开发固件参考）；不清库 | Step 10 |

---

## 二、执行流水（可执行 · 顺序 · 每步产出物明确）

### Step 0 · KICKOFF-DECISION（本文档）
- **动作**：写完 + commit master
- **完成态**：本 file commit hash

### Step 1 · 环境自检（我做 · ~5 min）
- **动作**：
  1. `docker compose ps`（列已启动服务）
  2. `redis-cli ping` → 期望 `PONG`
  3. `curl -s http://localhost:8000/api/v1/health` → 期望 `{"status":"ok"}`（若后端未起，等你起 `uvicorn`）
  4. LLM smoke：从 `.env` 读 base_url + api_key，`curl` 试一次 `/chat/completions`
- **产出**：4 行 log 附到 run report §附1
- **停一下**：`curl health` 失败 → 等你起后端，不擅自 `uvicorn`

### Step 2 · dev 库快照 + 清六表（我做 · ~5 min）
- **动作**：
  1. `SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname IN ('tasks','executions','match_scores','jds','resumes','candidates','candidate_status_history','candidate_notes','skills','skill_versions','skill_execution_logs') ORDER BY relname;`（快照）
  2. **保留** skills / skill_versions / skill_execution_logs
  3. `TRUNCATE TABLE match_scores, executions, tasks, candidate_status_history, candidate_notes, resumes, candidates, jds RESTART IDENTITY CASCADE;`（顺序含依赖，CASCADE 兜底）
  4. Redis：`redis-cli --scan --pattern "sse:buf:*"` + `task:active` 查值 → 若非 0 则 `DEL task:active`
- **产出**：快照表 + TRUNCATE 结果附到 run report §附2
- **停一下**：dev 库 psql 连不上 → 停，报现象

### Step 3 · SSE 陷阱 11 前置 grep（我做 · ~5 min）
- **动作**：
  1. `grep -rn "EventSource\|new EventSource\|ReadableStream\|fetch.*stream\|getReader" frontend/src/**`（首选 rg via Grep tool）
  2. 判定：所有 SSE 消费点应为 fetch + ReadableStream；不允许 EventSource
- **产出**：grep 结果附到 run report §附3；发现违规 → 立即登记 P0 candidate

### Step 3.5 · SSE terminal 信号确认（我做 · ~5 min · Q4 兜底）
- **动作**：
  1. `grep -n "terminal\|stream.*close\|StreamingResponse\|yield.*SSE\|sse_stream" backend/app/agent/**` + `backend/app/api/v1/agent.py`
  2. 拉出 stream 关闭前的最后一个 `emit` 事件类型，或"关闭本身即终止"结论
- **产出**：结论一句话附 run report §附4；若歧义 → 登记 §Bug 表"文档漂移"

### Step 4 · §1 起服 + sidebar 视觉核验（你操作 + 我伴跑 · ~10 min）
- **你**：
  1. 按 CHECKLIST §1 三步起服（若已在跑则跳过后端起服）
  2. 打开 `http://localhost:5173`，看 sidebar 是否仅有 5+1 页
  3. 报回：`§1 完成 · sidebar 正确/异常 · 起服无/有报错`
- **我**：查 `backend/backend.err` 尾 50 行

### Step 5 · §2 JD 生成（你操作 + 我伴跑 · ~10 min）
- **你**：`/chat` 输入 `帮我生成一个 Python 后端工程师的 JD，要求 3 年经验、熟悉 FastAPI`
- **报回**：`§2 完成 · jd_id=<xxx>` 或 `§2 卡住 · <现象>`
- **我**：`SELECT id, position_title, status, created_at FROM jds ORDER BY created_at DESC LIMIT 3;`

### Step 6 · §3 简历上传 × 3（你操作 + 我伴跑 · ~15 min）
- **你**：`/resumes` 上传 3 份简历
  - 简历 A：候选人「张三」v1
  - 简历 B：候选人「张三」v2（**同名**，用于 §4.2 merge）
  - 简历 C：候选人「李四」（用于 §4.1 profile 单独）
- **报回**：`§3 完成 · resume_ids={A,B,C} · candidate_ids={张三=?, 李四=?}`
- **我**：并查 resumes + candidates 表 + MinIO 桶行数
- **降级**：若真实简历难找，用同一份 PDF 改名传两次也可（MinIO key 不同 → 落两条 resume · 但可能被去重成 1 candidate，需临场判断）

### Step 7 · §4 三个 skill 分别触发（你操作 + 我并行 curl SSE · ~30 min）
- **§4.1 candidate-profile**（简历 C · 李四）
  - **你**：`/chat` 输入「为李四这份简历生成候选人画像」
  - **我**：一见 task_id 立即 `curl -N http://localhost:8000/api/v1/agent/tasks/{task_id}/stream > /tmp/sse-4-1.log &`
  - **报回**：`§4.1 完成 · task_id=<xxx> · PlanCard 显示/未显示`
- **§4.2 candidate-merge**（简历 A+B · 张三 ×2）
  - **你**：`/chat` 输入「把张三的两份简历合并到同一个候选人」
  - **我**：curl SSE 到 `/tmp/sse-4-2.log`
  - **报回**：`§4.2 完成 · task_id=<xxx> · merged candidate_id=<xxx>`
- **§4.3 jd-candidate-matching**（§2 JD × 简历 C 李四）
  - **你**：`/chat` 输入「分析李四这份简历与刚才那个 Python JD 的匹配度」
  - **我**：curl SSE 到 `/tmp/sse-4-3.log`
  - **报回**：`§4.3 完成 · task_id=<xxx> · PlanCard 显示`
- **产出**：3 份 SSE log → 事件类型清单 8 种覆盖度写入 run report

### Step 8 · §5 PlanCard 确认 + §6 SSE 类型清单（你操作 + 我伴跑 · ~15 min）
- **你**：对 §4.3 的 PlanCard 点确认（勾全部 step）
- **我**：`SELECT id, task_id, step_id, status, created_at FROM executions WHERE task_id='<§4.3 task_id>' ORDER BY created_at;`
- **报回**：`§5 完成 · executions 落库 <N> 行`
- **§6 我总结**：从 3 份 SSE log 抽事件类型分布表 → run report §6

### Step 9 · §7 skip-to-score + §8 match_scores + §9 CancelTask（你操作 + 我伴跑 · ~20 min）
- **§7**（你）：`/` 看板选 §2 JD + §3 简历 C 李四，点 skip-to-score
  - 报回：`§7 完成 · task_id=<xxx>`
  - 我：`SELECT jd_id, resume_id, candidate_id, score, resume_updated_at_snapshot, jd_updated_at_snapshot FROM match_scores ORDER BY created_at DESC LIMIT 3;`
- **§8**（你）：`/scores` 看列表 + 点详情
  - 报回：`§8 完成 · 快照字段有值/为空`
- **§9 executing 取消**（你）：再触发一个 §4.1 skill，PlanCard 一出就点确认，5 秒内点看板卡片"取消"
  - 我：查 task 最终 status + `task:active` Redis 值
- **§9 WAITING_CONFIRMATION 取消**（你）：再触发一个 §4.1 skill，PlanCard 出现后**不点确认**，直接点"取消"
  - 我：同上

### Step 10 · Run report + HANDOFF §9.3 更新 + commit（我做 · ~15 min）
- **动作**：
  1. 写 `docs/planning/stage5/MVP-VERIFY-RUN-REPORT.md`（结构见 §四）
  2. 把每个 P1/P2 bug 追加到 `HANDOFF.md §9.3`
  3. commit `docs(stage5): MVP end-to-end verify run report (2026-07-28)` + 附 HANDOFF 更新 commit
  4. push master

---

## 三、通过判定（严 · 一票否决）

**全绿判据**：
- [ ] Step 1-3 全通过（health OK · dev 库清干净 · SSE 陷阱 11 无违规 · terminal 语义明确）
- [ ] §1-§9 每节至少「完成/带 P1 登记」两种收尾之一，无「卡住无进展」
- [ ] SSE 8 种事件类型至少覆盖 5 种（thinking / plan / tool_call / result / system 是必现）；未覆盖登记
- [ ] executions 落库、match_scores 落库、CancelTask 生效三件事全部真实观测到
- [ ] P0 = 0（或最多 1 hotfix PR 已合）

**允许"部分通过"**：单一 skill 触发失败但不阻塞其他 skill → 登记 P1，继续；一票否决只针对"整链断"。

---

## 四、Run report 骨架（Step 10 我写）

```markdown
# MVP 端到端手工验收 · Run Report

> 日期：2026-07-28
> 起始 master HEAD：916daf8
> 关联：MVP-VERIFY-CHECKLIST.md · MVP-VERIFY-KICKOFF-DECISION.md

## §一、执行总览
- 起讫时间 · 总耗时
- 通过节数 / 卡住节数 / P0/P1/P2 数

## §二、逐节结论（§1-§9 各一段）
- 命令 · 期望 · 实际 · 落库校验 SQL 快照

## §三、SSE 事件类型覆盖
- 3 份 SSE log 汇总的类型分布表

## §四、Bug 表
| # | 严重级 | 节 | 现象 | 复现 | 疑似根因 | 处置 | HANDOFF §9.3 条目号 |

## §附1 环境自检 log
## §附2 dev 库快照 + 清库结果
## §附3 SSE 陷阱 11 grep
## §附4 SSE terminal 信号确认
```

---

## 五、求助边界（QUESTIONS §求助边界照搬 · 强制止血点）

进入执行后，以下情形**必停 · 报现象 · 等指示**：

1. **P0 触发且超出 hotfix 边界**（>1 文件 / 改 schema / 改 migration / 需新依赖）
2. **CHECKLIST 与代码实际不一致**（endpoint 不存在、行为漂移）→ 登记"文档漂移"，不擅改
3. **dev 库/Redis/MinIO 连不上** → 不改 `.env`，报现象
4. **LLM 连续失败 3 次** → 可能 quota/endpoint 变化，等确认
5. **HANDOFF §9.4 之外的新陷阱** → 登记新条目，不静默绕过
6. **SSE terminal grep 无结论** → 登记"文档歧义"，不擅改 CHECKLIST

---

## 六、指挥官核验清单

- [x] 本 DECISION 覆盖 QUESTIONS 13 议题 + 6 边界
- [x] 与 HANDOFF §9.4 陷阱 11 兼容（前置 grep）
- [x] Report 命名与 AGENTS.md §4.1 docs-only commit 兼容
- [x] Bug 双写 HANDOFF §9.3 明确
- [x] 起始 baseline 明确（HEAD=916daf8 · pytest 131/1 · ruff 0 · build ✓ · migration b6c7d8e9f0a1）
- [ ] **本 DECISION commit 后开跑 Step 1**（等你 GO）

---

**执行开跑触发条件**：本 DECISION commit 落 master 后，我等你一句「GO」或直接说「起后端」/「起服完毕」再进 Step 1。
