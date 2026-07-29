# MVP 手工验收 · 执行者交接手册（EXECUTOR-HANDOFF）

> 面向：能直接操控浏览器 + 有 bash/docker 权限的执行者 agent
> 生成时间：2026-07-29
> 关联：`MVP-VERIFY-CHECKLIST.md`（验收清单）· `MVP-VERIFY-KICKOFF-DECISION.md`（执行契约 · 13 议题裁定 · 6 边界）
> master HEAD：`7316e02`（DECISION commit，本地已提交未 push；网络恢复后手动 `git push origin master`）
> 交接目的：session 分工从「UI-你/后端-我」切换为「UI+后端-你一体化」，一人贯通更快

---

## 一、进度快照（Step 0-3.5 已由前 agent 完成 · 你从 Step 4b 接手）

### 已完成

| Step | 内容 | 结果 |
|------|------|------|
| Step 0 | 起 KICKOFF-QUESTIONS + KICKOFF-DECISION 落 master | ✅ commit `916daf8` + `7316e02` |
| Step 1 | 环境自检：health / MinIO 9000-9001 / Redis / LLM smoke | ✅ 全通（MinIO unhealthy 是探针问题，服务实际 200 OK） |
| Step 2 | dev 库快照 + TRUNCATE 7 表 | ✅ 业务 7 表全清 0；保留 `skills=2` + `alembic_version=b6c7d8e9f0a1` |
| Step 3 | SSE 陷阱 11 前置 grep | ✅ 合规：`frontend/src/hooks/useTaskStream.ts:157` 用 `fetch + ReadableStream.getReader()`，无 EventSource |
| Step 3.5 | SSE terminal 语义 grep | ✅ 权威源 `app/api/v1/agent.py:196-202::_is_terminal()` → **terminal = result / error / system:cancelled 三种事件之一** |
| Step 4a | §2 /chat 生成 JD | ❌ **发现 2 个 P1 bug**（见 §五 Bug 表 B3/B4）· 已判定不修 · 换路径 |

### 剩余（你的执行范围）

| Step | 内容 | 关键 |
|------|------|------|
| **Step 4b** | 换 `/jds/generate` 表单生成 JD | orchestrator 路径不通，走表单直通 |
| Step 5 | §3 简历 × 3 上传 | 张三×2（同名）+ 李四×1，用于 §4.2 merge 和 §4.1 profile |
| Step 6 | §4.1/4.2/4.3 三个 skill 触发 | 每个 task 并行 `curl -N .../stream > /tmp/sse-*.log` |
| Step 7 | §5 PlanCard 确认 + §6 SSE 类型统计 | executions 落库 + 3 份 SSE log 类型分布 |
| Step 8 | §7 skip-to-score + §8 match_scores 详情 + §9 CancelTask ×2 | executing 取消 + WAITING_CONFIRMATION 取消 |
| Step 9 | 写 run report + 双写 HANDOFF §9.3 + commit master | 落地物：`docs/planning/stage5/MVP-VERIFY-RUN-REPORT.md` |

---

## 二、验收总原则（继承 KICKOFF-DECISION，不复述细节）

**先读**：`docs/planning/stage5/MVP-VERIFY-KICKOFF-DECISION.md`（197 行 · 议题裁定 + 10 步流水 + 6 求助边界）。

**核心 5 条**：

1. **一口气跑完 §1-§9**，中途遇 P0 才停
2. **P0 分级**：仅修「不能 workaround 的」（进程崩溃 / 核心 API 全 500 / SSE 完全断流 / 落库全失败）；能换路径就登记不修
3. **P0 hotfix 边界**：≤1 文件 · 不改 schema · 不改 migration · 不加依赖；超出即 stop-and-ask
4. **Bug 双写**：run report §Bug 表 + HANDOFF §9.3 追加条目
5. **不擅改 CHECKLIST**：发现文档漂移 → 登记 `文档漂移`，Step 9 统一回写

**求助边界 6 条**（继承 DECISION §五 · 触及必停）：
1. P0 触发且超 hotfix 边界
2. CHECKLIST 与代码实际矛盾 → 登记，不擅改
3. dev 库/Redis/MinIO 连不上 → 不改 `.env`
4. LLM 连续失败 3 次
5. 发现 HANDOFF §9.4 之外新陷阱 → 登记新条目
6. SSE terminal / 其他文档歧义 grep 无结论

---

## 三、后端伴跑 recipe（可复制粘贴 · 你一体化执行时直接用）

### 3.1 PG 查询（docker exec 兜底 · 本机无 psql）

**注入变量**（每次开工设一次）：
```bash
PG="docker exec $(docker compose ps -q postgres) psql -U recruitment -d recruitment_agent -c"
```

**核心查询**：
```bash
# 全表行数快照
$PG "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE schemaname='public' ORDER BY relname;"

# 最新 5 个 task 完整字段
$PG "SELECT task_id, status, LEFT(user_message,50) as msg, plan IS NOT NULL as has_plan, result IS NOT NULL as has_result, error, created_at FROM tasks ORDER BY created_at DESC LIMIT 5;"

# 单个 task 详情（替 <TASK_ID>）
$PG "SELECT * FROM tasks WHERE task_id='<TASK_ID>';"

# executions 表查询（替 <TASK_ID>）
$PG "SELECT execution_id, task_id, step_id, status, LEFT(input_snapshot::text,80) as input, created_at FROM executions WHERE task_id='<TASK_ID>' ORDER BY created_at;"

# match_scores 查询（替 <JD_ID>）
$PG "SELECT jd_id, resume_id, score, resume_updated_at_snapshot, jd_updated_at_snapshot, created_at FROM match_scores WHERE jd_id='<JD_ID>' ORDER BY created_at DESC;"

# 简历 + 候选人（无独立 candidates 表，见 B1）
$PG "SELECT resume_id, candidate_name, parse_status, dedup_status, duplicate_of_resume_id, candidate_status FROM resumes ORDER BY created_at DESC LIMIT 10;"

# JD 列表
$PG "SELECT jd_id, position_title, status, created_at FROM jds ORDER BY created_at DESC LIMIT 10;"
```

### 3.2 Redis 查询

```bash
REDIS="docker exec $(docker compose ps -q redis) redis-cli"

# SSE 缓冲键列表
$REDIS --scan --pattern "sse:*"

# 具体 buffer 内容（替 <TASK_ID>）· 每条是一个 SSE 事件 JSON
$REDIS LRANGE "sse:buf:<TASK_ID>" 0 -1

# 并发计数（应 0；≥1 = 有活跃 task）
$REDIS GET task:active

# 全清 SSE 相关键（谨慎用 · 只在验收结束或某 task 出问题时）
$REDIS --scan --pattern "sse:*" | xargs -I{} $REDIS DEL {}
```

### 3.3 SSE 流实时抓取

```bash
# 后台抓 SSE 到文件（替 <TASK_ID> 和 <N>）
curl -N "http://localhost:8000/api/v1/agent/tasks/<TASK_ID>/stream" > /tmp/sse-<N>.log 2>&1 &

# 事件类型统计（在 stream 结束/超时后跑）
grep "^event:" /tmp/sse-<N>.log | sort | uniq -c
```

**SSE 事件行格式**（重要 · 用于解析）：
```
retry: 3000

event: thinking
id: 1
data: {"content":"reasoning completed"}

event: plan
id: 2
data: {...}

event: system
data: {"message":"heartbeat"}      ← 心跳无 id，不入 buffer

event: result                       ← terminal 触发
id: 8
data: {...}
```

### 3.4 API 直调

```bash
# health
curl -sS http://localhost:8000/api/v1/health

# task 详情
curl -sS http://localhost:8000/api/v1/agent/tasks/<TASK_ID> | jq

# skip-to-score（body 例）
curl -sS -X POST http://localhost:8000/api/v1/agent/skip-to-score \
  -H "Content-Type: application/json" \
  -d '{"jd_id":"<JD_ID>","resume_ids":["<RES_A>","<RES_B>"]}'

# cancel
curl -sS -X POST http://localhost:8000/api/v1/agent/tasks/<TASK_ID>/cancel
```

### 3.5 后端日志位置

- `backend/backend.log`（SQLAlchemy + uvicorn access log · 老日志混在里面 · 用 `tail -f` + `grep -E "task_id|reason|reflect|blocking"` 过滤）
- `backend/backend.err`（stderr · 历史存量 · 新错误也追加在此）
- **uvicorn stdout**：在你启动它的终端里可见；如果需要在这个 session 抓，起服时改用 `uv run uvicorn app.main:app --reload --port 8000 2>&1 | tee -a backend/uvicorn-verify.log`

### 3.6 LLM smoke（不写库）

```bash
cd backend && uv run python -c "
from app.core.config import Settings
from openai import OpenAI
s = Settings()
c = OpenAI(base_url=s.LLM_BASE_URL, api_key=s.LLM_API_KEY, timeout=30)
r = c.chat.completions.create(model=s.LLM_MODEL, messages=[{'role':'user','content':'ping'}], max_tokens=8)
print('OK model=', r.model, 'usage=', r.usage.total_tokens)
"
```

---

## 四、异常抓取标准流程（每次 UI 卡/异常都跑一遍）

**触发条件**：
- UI 报错（Console / Toast / 空白页）
- Network 面板 4xx/5xx / (canceled) / 长时间 pending
- 后端没有预期的落库
- SSE 无预期事件

**5 步抓取流**（顺序执行 · 每步不到 10 秒）：

```bash
# 1. 后端进程活着吗？
curl -sS -w "HTTP=%{http_code}\n" http://localhost:8000/api/v1/health

# 2. task 状态（换 <TASK_ID>）
$PG "SELECT task_id, status, error, LEFT(result::text,200) as result FROM tasks WHERE task_id='<TASK_ID>';"

# 3. SSE buffer 里有什么
$REDIS LRANGE "sse:buf:<TASK_ID>" 0 -1

# 4. 后端最近 log（过滤关键字）
tail -200 backend/backend.log | grep -iE "ERROR|WARN|<TASK_ID>|reason|reflect|blocking"

# 5. 并发计数（异常时可能没回退）
$REDIS GET task:active
```

**决策树**：

- **task.status = FAILED** 且 `error` 有值 → 记录 `error.code + error.message` 到 Bug 表；判定 P0/P1
- **task.status = WAITING_CONFIRMATION** 且 `error.blocking_reason` 有值 → orchestrator reflect 判 not feasible；正常业务分支，看 blocking_reason 是否合理
- **task.status 长时间 = PLANNING** → 后台任务卡死或崩溃；查 uvicorn stdout（`asyncio.create_task` fire-and-forget 崩溃不进 log）
- **SSE buffer 空 + task 状态已终态** → SSE 缓冲被清或 buffer TTL 3600s 已过；`_synthesize_from_task` 分支会兜底
- **SSE buffer 有事件但无 terminal (result/error/system:cancelled)** → 新陷阱，触及 §求助边界 5，登记 §9.4

---

## 五、当前已发现 Bug 表（前 agent 已抓 · 你继承 · 不重复记录）

| # | 级别 | 节 | 现象 | 根因 | 处置 | Step |
|---|------|-----|------|------|------|------|
| **B1** | P1 | §3/§9 | CHECKLIST 提到 `candidates` 表，实际不存在 | 候选人概念嵌入 `resumes.candidate_name` + `duplicate_of_resume_id` 做合并；独立表未建 | 登记 · Step 9 回写 CHECKLIST | Step 2 |
| **B2** | P2 | §6 | CHECKLIST "terminal 事件"表述含糊 | 实际 = `_is_terminal()` 三种：result/error/system:cancelled | 登记 · Step 9 回写 CHECKLIST | Step 3.5 |
| **B3** | **P1** | §2 | `/chat` 输入生成 JD → WAITING_CONFIRMATION + blocking_reason="未提供reason_output"，前端 SSE (canceled) | (a) `jd-generation` skill.yaml 无 `task_type` 字段，不在 orchestrator 路由表；(b) `orchestrator-reason` prompt 值域不含 JD 生成意图 (`match/merge_candidates/profile_candidate/unknown`) | 登记 · 换 `/jds/generate` 表单继续验收 | Step 4a |
| **B4** | **P1** | §6 SSE | reflect 判 `is_feasible=false` 后，`_background_reason_plan` 直接 return，SSE 无 terminal 事件，前端 stream 挂到超时被浏览器 canceled | `engine.py:379-388` 分支缺 `await emit(SSEEventType.ERROR)` 或 `SYSTEM` 收尾 | 登记 · 新陷阱 · Step 9 追加 HANDOFF §9.4 | Step 4a |

**判定依据**：
- B3 修复需改 skill.yaml + reason prompt + 潜在 red-test（≥2 文件），超出 hotfix 边界
- B4 修复需改 orchestrator engine 分支（可能 1 文件，但需 red-test 覆盖新事件 · 属架构修）

---

## 六、剩余步骤精确清单（你从这里开始）

### Step 4b · §2 表单生成 JD

**UI 动作**：
1. 浏览器 → `http://localhost:5173/jds/generate`
2. 填表单：
   - 职位名称：`Python 后端工程师`
   - 职位需求描述：`3 年经验、熟悉 FastAPI、有微服务经验优先`
   - 其他字段留空
3. 提交

**后端验证**：
```bash
$PG "SELECT jd_id, position_title, status, created_at FROM jds ORDER BY created_at DESC LIMIT 3;"
```

**记录**：`§2 结果 · jd_id=<xxx>` 到 run report

**降级**：如果表单页也 500，登记 P0 → stop-and-ask（超出可 workaround 范围）

---

### Step 5 · §3 简历上传 × 3

**UI 动作**：
1. 浏览器 → `http://localhost:5173/resumes`
2. 上传 3 份 PDF/DOCX 简历：
   - **A**：候选人「张三」v1（PDF 或 DOCX，任意）
   - **B**：候选人「张三」v2（**同名**，用于 §4.2 merge · 内容可小改动）
   - **C**：候选人「李四」（另一人，用于 §4.1 profile）

**降级**：若没现成简历，用**同一份 PDF 改名两次上传**（触发 dedup_status；`candidate_name` 是解析后填的，可能 A/B/C 都被识别为同一名字 → §4.2 merge 无从对比。如出现请登记 P2）

**后端验证**：
```bash
$PG "SELECT resume_id, candidate_name, parse_status, parse_error, dedup_status, duplicate_of_resume_id, created_at FROM resumes ORDER BY created_at DESC;"

# MinIO 桶
docker exec $(docker compose ps -q minio) mc ls local/resumes/ 2>/dev/null || true
```

**记录**：
- `§3 结果 · resume_ids=[A=<xxx>, B=<xxx>, C=<xxx>] · 候选人识别=[张三×N, 李四×M]`
- parse_status 应为 `SUCCESS`；若 `FAILED` → 记 P1 Bug（parse_error 字段贴出）

---

### Step 6 · §4 三个 skill 分别触发

**每个 skill 的流程模板**（并行开 SSE 抓取）：

```bash
# 1. 你在 UI 触发 chat（见下方三个 skill 的具体 prompt）
# 2. 从 Network 面板拿到 task_id
# 3. 立即（≤3 秒内）在 bash 起 SSE curl
curl -N "http://localhost:8000/api/v1/agent/tasks/<TASK_ID>/stream" > /tmp/sse-<N>.log 2>&1 &

# 4. 等 UI PlanCard 出现（或异常提示）
# 5. 后端查 task 详情
$PG "SELECT status, plan IS NOT NULL as has_plan, error FROM tasks WHERE task_id='<TASK_ID>';"

# 6. 记录到 run report
```

**§4.1 candidate-profile**（用简历 C · 李四）：
- Prompt：`为李四生成候选人画像`
- 期望：orchestrator-reason 识别 `task_type=profile_candidate` → dispatch `candidate-profile` skill → PlanCard 显示 profile step

**§4.2 candidate-merge**（用简历 A + B · 张三 ×2）：
- Prompt：`把张三的两份简历合并到同一个候选人`
- 期望：`task_type=merge_candidates` → dispatch `candidate-merge` → PlanCard 显示 merge step
- 关键校验：合并后 resumes 表的 `duplicate_of_resume_id` 应有值

**§4.3 jd-candidate-matching**（用 §2 JD × 简历 C 李四）：
- Prompt：`分析李四这份简历与刚生成的 Python 后端工程师 JD 的匹配度`
- 期望：`task_type=match` → dispatch `jd-candidate-matching` → PlanCard 显示 match step

**共同预警**：如果三个 skill 中任一 chat 也出现 B3 类似的 `blocking_reason="未提供..."` → orchestrator-reason 未识别意图，登记 P1（但从 prompt 值域看这三种意图**都在**，不应复现 B3）

---

### Step 7 · §5 PlanCard 确认 + §6 SSE 类型统计

**§5 UI 动作**：对 §4.3（jd-candidate-matching）的 PlanCard 点确认（勾选全部 step）

**后端验证**：
```bash
$PG "SELECT execution_id, task_id, step_id, status, created_at FROM executions WHERE task_id='<§4.3 TASK_ID>' ORDER BY created_at;"

# task 应从 WAITING_CONFIRMATION → EXECUTING → COMPLETED
$PG "SELECT status, plan IS NOT NULL, result IS NOT NULL FROM tasks WHERE task_id='<§4.3 TASK_ID>';"
```

**§6 SSE 类型统计**：
```bash
for f in /tmp/sse-1.log /tmp/sse-2.log /tmp/sse-3.log; do
  echo "=== $f ==="
  grep "^event:" "$f" | sort | uniq -c
done
```

**期望**：至少 5 种事件（`thinking / plan / tool_call / result / system`）出现；`progress` / `warning` / `error` 可能不出现属正常。

**记录**：SSE 类型分布表 → run report §六

---

### Step 8 · §7 skip-to-score + §8 match_scores + §9 CancelTask

**§7 skip-to-score**：

- UI：`/`（看板）选 §2 的 JD + §3 的简历 C 李四，点 skip-to-score 按钮（或用 curl 直调）
- curl 备用：
  ```bash
  curl -sS -X POST http://localhost:8000/api/v1/agent/skip-to-score \
    -H "Content-Type: application/json" \
    -d '{"jd_id":"<JD_ID>","resume_ids":["<RES_C>"]}'
  ```
- 后端验证：
  ```bash
  $PG "SELECT jd_id, resume_id, score, resume_updated_at_snapshot, jd_updated_at_snapshot, created_at FROM match_scores ORDER BY created_at DESC LIMIT 3;"
  ```

**§8 match_scores 详情**：
- UI：`/scores` → 找到 §7 记录 → 点详情
- 关键：`resume_updated_at_snapshot` 和 `jd_updated_at_snapshot` 应有值；空则记 P1

**§9 CancelTask ×2**（只测 executing + WAITING_CONFIRMATION，不测 scoring）：

- **executing 取消**：
  1. 再触发一个 §4.1 chat（李四 profile）
  2. PlanCard 一出立即点确认
  3. status → EXECUTING 后 5 秒内点看板卡片"取消"
  4. 校验：`$PG "SELECT status FROM tasks WHERE task_id='<TASK_ID>';"` → CANCELLED
  5. 校验：`$REDIS GET task:active` → 应回退为 0（或 -1，取决于是否有其他 task）

- **WAITING_CONFIRMATION 取消**：
  1. 再触发一个 §4.1 chat
  2. PlanCard 出现后**不点确认**，直接点"取消"
  3. 校验同上

---

### Step 9 · Run report + HANDOFF §9.3 + commit

**Report 骨架**（写到 `docs/planning/stage5/MVP-VERIFY-RUN-REPORT.md`）：

```markdown
# MVP 端到端手工验收 · Run Report

> 日期：2026-07-29
> 起始 master HEAD：7316e02
> 关联：MVP-VERIFY-CHECKLIST.md · MVP-VERIFY-KICKOFF-DECISION.md · MVP-VERIFY-EXECUTOR-HANDOFF.md

## §一、执行总览
- 起讫时间 / 总耗时
- 通过节数 / 卡住节数 / P0×N / P1×N / P2×N

## §二、逐节结论（§1-§9）
### §1 起服 + sidebar
- 结果：...
- SQL 快照：...
### §2 JD 生成
- 主路径（/chat）：❌ B3 阻塞 · 换 /jds/generate
- 表单路径：结果 · jd_id=<xxx>
（...每节按此格式...）

## §三、SSE 事件类型覆盖
| task_id | thinking | plan | tool_call | progress | result | error | warning | system | 总 |

## §四、Bug 表（B1-Bn）
（继承 B1/B2/B3/B4 + 新发现）

## §五、CHECKLIST 文档漂移回写
- §3/§9：删除 `candidates` 表相关表述
- §6：terminal 定义澄清
- §2：新增说明「/chat 生成 JD 当前不通，用 /jds/generate 表单」

## §附1-4：环境自检 / 清库 / SSE grep / terminal 语义 log（前 agent 已抓，直接搬运即可）
```

**HANDOFF §9.3 追加**（每个 P1/P2 一条）：
```markdown
### §9.3.NN · <bug 一句话标题> · 登记（PR-XX 待修）
- **现象**：（抄 Bug 表 现象列）
- **根因**：（抄 Bug 表 根因列）
- **发现时机**：MVP 手工验收（run report §四 B<N>）
- **修复建议**：（一句话给 PR-XX 起草人参考）
- **优先级**：P1/P2
```

**Commit 命令**：
```bash
cd E:/AI-WORK/Project-Work/recruitment-agent-2.0
git add docs/planning/stage5/MVP-VERIFY-RUN-REPORT.md HANDOFF.md docs/planning/stage5/MVP-VERIFY-CHECKLIST.md
git commit -m "docs(stage5): MVP end-to-end verify run report (2026-07-29) + HANDOFF §9.3 debts + CHECKLIST fixups"
git push origin master  # 网络若失败见 §八
```

---

## 七、通过判定（严 · 一票否决）

**全绿判据**：
- [ ] §1-§9 每节至少「完成/带 Bug 登记」两种收尾之一，无「卡住无进展」
- [ ] SSE 至少 5 种事件类型覆盖
- [ ] executions 落库 / match_scores 落库 / CancelTask 生效 三件事全部真实观测到
- [ ] P0 = 0（或 ≤1 hotfix PR）

**允许"部分通过"**：单一 skill 触发失败但不阻塞其他 skill → 登记 P1 继续。一票否决只针对"整链断"。

---

## 八、待办 & 注意事项

### 网络待办

- KICKOFF-DECISION commit `7316e02` **本地已提交，push 因 GitHub 网络 reset 失败两次**
- 你开工时先跑 `git push origin master`，若失败则等网络恢复再试；不阻塞验收本身
- 本 EXECUTOR-HANDOFF 文档也是 docs-only，请一并 commit：
  ```bash
  git add docs/planning/stage5/MVP-VERIFY-EXECUTOR-HANDOFF.md
  git commit -m "docs(stage5): MVP verify · executor handoff manual (progress snapshot + recipe + remaining steps)"
  ```

### 上下文注意

- `.env` 已配好（LLM + PG + Redis + MinIO 四套）· 勿动
- LLM = `deepseek-v4-flash-260425` · 已确认可用（Step 1 smoke pass）
- MinIO 9000/9001 实测 HTTP 200 · docker unhealthy 只是探针问题
- **不要**读 `docs/planning/stage5/commander/` 或 `executor/` 子目录（superseded drafts）

### AGENTS.md § 4.1 提醒

- 本次验收是 **docs-only** · 直接 commit master，无需 feat 分支
- 若发现 P0 需当场修，只有那个 hotfix 需要 feat 分支（`feat/pr-24-<slug>`）+ FF-merge 流程
- git 身份仍是 `unknown <yangyang@sylincom.com>` · 与 PR-21/22/23 一致

### 沟通协议

- **不需要**你事无巨细回报每个 SQL 查询；只需在每个 §N 完成后总结一句 + 遇到异常时贴 5 步抓取流的输出
- Report 是唯一的最终交付物，session 内的口头汇报是过程

---

## 九、你已经从这里开始

**下一步立即动作**：

```bash
# 0. push 前 agent 未推的 commit（若网络恢复）
cd E:/AI-WORK/Project-Work/recruitment-agent-2.0
git log --oneline -3
git push origin master

# 1. 进入 §2 Step 4b：打开浏览器 http://localhost:5173/jds/generate 填表单
```

**祝顺利。有质疑当前 KICKOFF-DECISION 或 handoff 内容的空间时，止血报告，别静默绕过。**
