# MVP-VERIFY v2 · 浏览器端到端验收清单（§4.1 / §4.2 / §4.3）

> **用途**：Bug A / B / C 全部关闭后，验证 §4 三节 chat 链路在**真实浏览器 + 真实 LLM + 真实 DB** 下端到端可跑。这是 MVP demo-ready 的**唯一判据**。
> **前置 master HEAD**：`0640d60`（PR-27 合入 + HANDOFF §9.3.21 同步后）
> **关联**：`MVP-VERIFY-CHECKLIST.md`（v1 · §1–§10 全景）· `MVP-VERIFY-RUN-REPORT.md`（v1 结果 · §4/§5/§6 挂账）
> **v2 与 v1 的关系**：v2 **只覆盖 v1 挂账的 §4.1/§4.2/§4.3**（外加它们必然带出的 §5 PlanCard / §6 SSE 事件覆盖）。v1 的 §7/§8/§9 已通过，不重跑。
>
> **⚠️ 读这份清单前先读 §0** —— 我已查过 dev DB，**当前是空库**，不做 §0 数据准备直接跑 §4 会全挂，而且挂的原因会误导你。

---

## §0 · 前置数据准备（**必做** · 不做则 §4 全挂）

### §0.1 · 我已核实的环境实况（2026-08-03 查）

| 项 | 实况 | 影响 |
|---|------|------|
| `recruitment-postgres` | Up 7 days (healthy) | ✅ 可用 |
| `recruitment-redis` | Up 7 days (healthy) | ✅ 可用 |
| `recruitment-minio` | **Up 7 days (unhealthy)** | ⚠️ **UI 上传简历路径可能挂** → 见 §0.3 |
| `resumes` 表 | **0 行** | ❌ §4.1/§4.2/§4.3 全部无数据可用 |
| `jds` 表 | **0 行** | ❌ §4.3 无 JD 可匹配 |
| `skills` 表 | **0 行** | ⚠️ 但后端启动会自动同步 → 见 §0.2 |
| `tasks` 表 | 1 行 | 无影响（历史残留） |

> **空库根因**：PR-25 / PR-26 验收期按 HANDOFF §9.4 陷阱 14 做过 TRUNCATE 清 MVP-VERIFY 残留。**这是预期的，不是 bug。**

### §0.2 · 起服（skills 表会自动填充）

```bash
# 1. 基础设施已在跑，无需重启（除 MinIO，见 §0.3）

# 2. 后端（在 backend/ 目录）
uv run alembic upgrade head          # 期望：已是 head b6c7d8e9f0a1，无新迁移
uv run uvicorn app.main:app --reload --port 8000

# 3. 前端（另开终端，在 frontend/ 目录）
npm run dev                           # Vite :5173
```

**关键**：`app/main.py::_sync_skills_to_db()` 在 lifespan 启动时自动把 registry 里的 skill 写入 `skills` 表。**起完后端务必确认**：

```bash
docker exec recruitment-postgres psql -U recruitment -d recruitment_agent \
  -c "SELECT skill_id, current_version, status FROM skills ORDER BY skill_id;"
```

**期望**：**10 行**（5 个 orchestrator internal + `candidate-merge` / `candidate-profile` / `jd-candidate-matching` / `jd-generation` / `resume-parsing`）。
**若为 0 行** → 后端启动日志里找 `Skill sync to DB skipped:` 警告（该异常被 `try/except` 吞掉，不会导致启动失败但会静默跳过）。**这是 stop-and-report 条件**，不要硬着头皮往下跑。

### §0.2b · ⚠️ 确认只有一个后端在监听 `:8000`（**必做** · 2026-07-27 事故追加）

Windows 下**两个 uvicorn 可以同时 bind `:8000` 而不报错**，内核把请求**随机**分给其中之一。命中旧进程时，它跑的是**该进程启动那一刻的代码 + 当时的 `.env`**（`--reload` 只监视自己那一个进程），于是你会看到与当前代码毫无关系的错误。2026-07-27 就因此把一个 7 天前的僵尸进程（PID 3208，起于 7/29）误诊成 `LLM_BASE_URL` 配错，白查 40 分钟。详见 HANDOFF §9.4 陷阱 17。

```bash
# 1. 列出所有监听 :8000 的 PID
netstat -ano | grep LISTENING | grep :8000

# 2. 逐个确认存活状态（已死进程的 LISTEN socket 不会被 Windows 回收，会留在 netstat 里）
powershell.exe -NoProfile -Command "Get-Process -Id <PID> -ErrorAction SilentlyContinue | Select-Object Id,StartTime,Path | Format-List"

# 3. 存活且是旧的 → 杀掉；杀完重启保留的那个，确保加载当前 HEAD
powershell.exe -NoProfile -Command "Stop-Process -Id <旧PID> -Force"
```

**判据**：`netstat` 里每个 PID 都 `Get-Process` 查一遍，**存活进程恰好 1 个**，且其 `StartTime` **晚于最后一次 `git merge`**。

> **`netstat` 出现 2 行不一定是问题。** 已退出进程残留的 LISTEN socket 在 Windows 上不会被内核回收，但它**不 accept 任何连接**，内核只把 SYN 交给能服务的活 socket。2026-07-27 实测：幽灵 PID 3208（进程已 GONE）与活进程共存时，连打 12 个 `POST /agent/chat` **12/12 全部落库**、无一丢失。所以**不要**为了让 netstat 归一到 1 行去跑 `netsh int ipv4 reset` —— 那会重置所有 TCP 连接（Postgres / Redis / MinIO / 前端代理），代价远大于收益。判据看**活进程数**，不看 netstat 行数。详见 `PR28-UAT-PORT-CLEANUP-REPORT.md` §八。

**最硬的事后指纹**（验收中途怀疑时用）：查 `tasks` 表最新行的 `created_at`。

```bash
# 期望：最新行时间 ≈ 你刚才操作的时间（分钟级）
docker exec recruitment-postgres psql -U recruitment -d recruitment_agent \
  -c "SELECT task_id, status, created_at FROM tasks ORDER BY created_at DESC LIMIT 3;"
```

**凡"UI 有反应但 `tasks` 表没有新行"** → 先怀疑请求打到了另一个进程，**不要先怀疑代码或配置**。

> 附：`思考（reasoning completed）` 这行 SSE **不能**用来判断 reason 成功 —— 它是 `engine.py:416` 的 fallback 字面量（`reason_out.get("reasoning") or "reasoning completed"`），旧代码里也有，LLM 失败时照样出现。

### §0.3 · 播种简历（**MinIO unhealthy，建议绕过 UI 上传**）

**为什么不走 UI 上传**：MinIO 容器当前 unhealthy，`ensure_buckets()` 失败也是被 `try/except` 吞的（`main.py:56-59`）。走 UI 上传大概率在文件落对象存储那步挂，而那**不是 §4 要验的东西** —— 会浪费你一轮归因。

**推荐做法 · 直接播种已解析简历**（绕开 MinIO + 简历解析 LLM 调用）：

执行体在 PR-26/27 期留了个 untracked 脚本 `backend/_seed_resume_uat.py`，播种 1 份 `parse_status='PARSED'` 且 `parsed_content` 齐备的简历（张伟 · 清华硕士 · 字节后端 · tags `["技术","高潜"]`）。

**但 §4.2 candidate-merge 需要 ≥2 份**（`candidate_merge/v1_0_0/skill.yaml:18` 有 `minItems: 2`）。所以：

```bash
# 在 backend/ 目录
uv run python _seed_resume_uat.py
# 输出形如：SEEDED_RESUME_ID=res_xxxxxxxxxxxx  ← 记下这个 ID
```

**然后你需要第二份简历**。两个选择：

| 做法 | 命令 | 适合 |
|------|------|------|
| **A · 改脚本播第二份**（推荐） | 复制 `_seed_resume_uat.py` 为 `_seed_resume_uat2.py`，改 `candidate_name="张伟"`（**同名** · 让 merge 有判定素材）、`file_name`/`file_path` 改 `seed_zhangwei2.pdf`、`parsed_content` 里公司改 `"阿里巴巴"`、`skills` 改 `["Python","Java","MySQL"]`、`tags=["技术"]` · 再跑一次 | §4.2 merge 语义最真（同名不同经历 → 正好考验 MERGE/SUGGEST/KEEP_SEPARATE 判定） |
| B · 直接 SQL 插第二份 | `INSERT INTO resumes (...) SELECT ... FROM resumes` 手改字段 | 快，但字段多容易漏 `parse_status='PARSED'` |

**播种后核实**：
```bash
docker exec recruitment-postgres psql -U recruitment -d recruitment_agent \
  -c "SELECT resume_id, candidate_name, parse_status, (parsed_content IS NOT NULL) AS has_parsed, tags FROM resumes;"
```
**期望**：2 行 · 均 `parse_status = PARSED` · 均 `has_parsed = t`。

> **为何必须 `parsed_content` 非空**：PR-26 hydration 的 Q3-A 设计是**硬失败** —— `parsed_content IS NULL` 会抛 `ToolParamError("candidate resume not parsed")` → SSE `ERROR` 事件。那是**正确行为**，但你会误以为 §4.1 挂了。

### §0.4 · 播种 JD（§4.3 才需要）

§4.3 需要至少 1 条 JD。**推荐走 UI**（顺便验 JD 生成链路，且不依赖 MinIO）：
浏览器 → `http://localhost:5173/jds/generate` → 填岗位需求（如"招一个 5 年经验的 Python 后端工程师，要求熟悉分布式和 K8s"）→ 生成 → 保存 → 记下 `jd_id`。

若 JD 生成也挂 → 那是**独立发现**，登记但不阻塞 §4.1/§4.2（这两节不需要 JD）。

---

## §4.1 · candidate-profile（单候选人画像）

**验的是**：Bug B（hydration）+ Bug C（CandidateChat 活化 + Resumes 入口）+ Bug A（task 详情可读）三者合并后的完整链路。

### 操作步骤

| # | 操作 | 期望 | 若不符 |
|---|------|------|--------|
| 1 | 浏览器开 `http://localhost:5173/resumes` | 列表显示 2 份简历（张伟 ×2） · 每行左侧**有 checkbox** | 无 checkbox → PR-27 `rowSelection` 未生效 · 查是否跑在最新 master |
| 2 | 勾选**第 1 份**简历（只勾 1 个） | 页面上方出现按钮 **「AI 对话 / 画像（1）」** · 可点击 | 按钮不出现/灰着 → 查 `Resumes.tsx:751` 附近 |
| 3 | 点「AI 对话 / 画像（1）」 | 跳转到 `/candidate-chat?candidates=res_xxxxx` · **URL 里能看到 resume_id** | URL 无 candidates 参数 → PR-27 入口传参挂 |
| 4 | 观察 CandidateChat 页面 | 有输入框（placeholder `输入消息...`）+「发送」按钮 · **不是空白页、不是 Empty 空态** | 见 Empty「请先在候选人列表选择」→ URL 参数没传过来（回查 step 3） |
| 5 | 输入 `给这个候选人生成画像` · 点「发送」 | **页面立刻出现流式区域**（"AI 助理" 标题栏 + 状态条 + 消息时间线） | **仍然空白 → Bug C 未真正修复，立即停止并报回** |
| 6 | 观察 SSE 事件卡片依次出现 | 见下方「期望事件序列」 | 见下方「分层排查」 |

### 期望 SSE 事件序列（§6 覆盖同时完成）

```
thinking     (R 阶段 · orchestrator-reason)
  ↓
plan         (P 阶段 · PlanCard 出现 · 含「确认执行」「取消」两个按钮)
  ↓  ← 此处会停下等你点「确认执行」（WAITING_CONFIRMATION 状态）
[你点「确认执行」]                       ← §5 PlanCard 验收点
  ↓
tool_call    (data.tool_name === "candidate-profile")
  ↓
progress     (percent: 100)
  ↓
result       (data.result 含 profile_tags / summary / strengths / risks 四字段)
```

### 判据（逐条勾）

- [ ] **A1** · `thinking` 事件出现（证 orchestrator-reason 跑了 · B5 修复仍有效）
- [ ] **A2** · `plan` 事件出现且 PlanCard 渲染出「确认执行」「取消」按钮（§5 验收）
- [ ] **A3** · plan 的步骤里 `tool_name` 是 **`candidate-profile`**（不是 `profile_candidate`、不是别的 · 证 LLM 从 dispatchable 清单学对了）
- [ ] **A4** · 点「确认执行」后出现 `tool_call` 事件（证 execute-plan 端点 + dispatch 通）
- [ ] **A5** · **`result` 事件的 `profile_tags` 非空数组**（证 PR-26 hydration 真把 `parsed_content` 喂进去了 —— 空 `parsed_content` 会让 skill 走 prompt.md 的"返回空结果"分支）
- [ ] **A6** · `result` 的 `summary` 是一句关于**张伟/清华/字节/Python** 的真实描述（**不是** `jd_1` / `c_1` 之类的示例值 —— 若是示例值说明 LLM 在幻觉，B5 回归了）
- [ ] **A7** · `profile_tags` 里能看到播种时的 `tags`（`技术` / `高潜`）被合并进去（证 `existing_tags` 也 hydrate 成功了）
- [ ] **A8** · 卡片类型不是 `generic` 灰框（证 `_ARTIFACT_TYPE_MAP` → 前端 `ArtifactType` 同步没断 · HANDOFF §9.3.3）

### 分层排查（挂在哪一层）

| 症状 | 大概率原因 | 验证命令 |
|------|-----------|---------|
| 无任何事件 · 页面空白 | 前端未挂 TaskStream | 浏览器 DevTools Network 看有无 `GET /api/v1/agent/tasks/<id>/stream` |
| 有 `thinking` 无 `plan` | orchestrator-plan 挂 | 看 `backend/backend.err` 或 uvicorn 控制台 |
| `plan` 的 tool_name 不对 | LLM 选错工具 · reflect_plan 拦下了 | 查 SSE `error` 事件的 message 是否含 `unknown tool` |
| 有 `tool_call` 无 `result` · 出 `error` | **hydration 硬失败**（正常行为！） | error message 含 `not parsed` / `not found` → 回 §0.3 检查 `parsed_content` |
| `result` 的 `profile_tags` 是空数组 | hydration 没注入成功 | `SELECT parsed_content FROM resumes WHERE resume_id='res_xxx';` 确认非 null |
| 卡在 `WAITING_CONFIRMATION` 不动 | 你还没点「确认执行」 | 正常 · 点按钮 |

### 附 · 后端侧交叉验证（可选但推荐）

事件跑完后，用 §4.1 的 task_id 查 REST 详情（**这条同时验 Bug A 的 PR-25 修复**）：
```bash
curl -s http://localhost:8000/api/v1/agent/tasks/<task_id> | python -m json.tool
```
- [ ] **A9** · **返回 200 不是 500**（PR-25 adapter 生效）· `plan.steps[0].tool_name == "candidate-profile"` · `plan.steps[0].params` 里能看到 candidate_id

---

## §4.2 · candidate-merge（双候选人合并判定）

**验的是**：PR-26 §Q4 顺路补的 candidate-merge hydration（v1 从未触发过这条路径）。

### 操作步骤

| # | 操作 | 期望 |
|---|------|------|
| 1 | 回 `/resumes` | 列表 2 份简历 |
| 2 | 勾选**两份都勾** | 按钮变 **「AI 对话 / 画像（2）」** |
| 3 | 点按钮 | 跳 `/candidate-chat?candidates=res_aaa,res_bbb`（**两个 ID 逗号分隔**） |
| 4 | 输入 `判断这两份简历是否是同一个候选人，需要合并吗` · 发送 | 流式开始 |
| 5 | 走完 `thinking → plan → [确认执行] → tool_call → result` | 见判据 |

### 判据

- [ ] **B1** · plan 的 `tool_name` 是 **`candidate-merge`**
- [ ] **B2** · `tool_call` 事件的 `tool_input.resumes` 是**长度 2 的数组**
- [ ] **B3** · **`result` 的 `action` ∈ {`MERGE`, `SUGGEST`, `KEEP_SEPARATE`}**（不是 null、不是别的字符串）
- [ ] **B4** · `result.confidence` 是 0–1 的数字
- [ ] **B5** · `result.recommendation` 是一句提到**张伟 / 字节 / 阿里** 等真实播种内容的描述（证 hydration 把两份 `parsed_content` 都喂进去了 —— 否则 LLM 只见 `resume_id` 会幻觉）
- [ ] **B6** · 若 `action == MERGE` 则 `master_resume_id` 是两个 ID 之一；若 `KEEP_SEPARATE` 则为 null

### ⚠️ PR-26 §五 边界 4 预警（触发即停）

若出现 **`minItems: 2` 校验失败**（error message 含 `minItems` 或 `too short`）：
- 说明 LLM 只往 `resumes` 里塞了 1 个 resume_id（尽管 URL 传了 2 个）
- **这是新 bug，不是 PR-26 的锅** —— 属于 plan 阶段 LLM 对 `context.candidate_ids` 的提取问题（同 §9.3.19 家族）
- **停 · 记录 error message 原文 · 报回** · 不要自己改 schema

---

## §4.3 · jd-candidate-matching（JD × 候选人匹配）

**验的是**：v1 挂账的第三个 skill · 需要 §0.4 的 JD。

### 操作步骤

| # | 操作 | 期望 |
|---|------|------|
| 1 | 开 `http://localhost:5173/chat`（**ChatCenter**，不是 candidate-chat） | 见 "AI 助理" 标题 + 输入框 |
| 2 | 输入 `帮我把 jd_xxxxx 和候选人 res_xxxxx 做匹配分析`（**把真实 ID 拼进自然语言里**） | 流式开始 |
| 3 | 走完事件链 | 见判据 |

> **为何要把 ID 拼进自然语言**：HANDOFF §9.3.19 记录了 orchestrator-reason 对 `context` 字段提取的**非确定性** —— 只塞 context 不写进消息文本，LLM 有概率丢掉。**这是已知问题的既定绕过法**，写在 §9.3.19 的「绕过」里。

### 判据

- [ ] **C1** · plan 的 `tool_name` 是 `jd-candidate-matching`
- [ ] **C2** · `result` 含匹配得分/维度分析等实质内容
- [ ] **C3** · `result` 里提到的 JD 要求与候选人技能是**真实播种的内容**（Python/K8s/分布式），不是幻觉值

### 备选路径（若自然语言触发不稳）

ChatCenter 里应有 **skip-to-score 面板**（PR-27 新建的 `SkipToScorePanel`，`TaskStream` 的 `showSkipToScore` prop 控制）：
- 展开「跳过调研直接评分」→ 选 JD + 选候选人 → 点「立即评分」
- **这条走的是确定性 `MatchService.match_one`（不经 LLM）** · v1 §7 已验过通
- **注意**：这条**不验** `jd-candidate-matching` skill（skip-to-score 用的是 builtin `match_score`）· 只能作为"匹配功能可用"的兜底证据，**不能替代 C1–C3**

---

## §5 / §6 覆盖情况（跟着 §4 自动完成）

- **§5 PlanCard 确认**：§4.1 step 「点确认执行」即完成（判据 A2 + A4）
- **§6 SSE 事件类型覆盖**：§4.1 走完覆盖 `thinking` / `plan` / `tool_call` / `progress` / `result` 五类。剩余三类：
  - `error` —— 故意验：勾一份 `parsed_content` 为 null 的简历（或临时 `UPDATE resumes SET parsed_content=NULL WHERE ...`）触发 hydration 硬失败 · **记得跑完改回来**
  - `warning` —— 需 plan 里有 `optional: true` 的步骤，LLM 一般不产出 · **可挂账不强求**
  - `system:cancelled` —— v1 §9 已验过通（4 个任务成功 CANCELLED）· **不重跑**

---

## §附 · 新 bug 登记模板（发现问题照这个格式记）

```markdown
### Bug <编号> · <一句话现象>
- **触发路径**：§4.x step N · <具体操作>
- **观察到的**：<SSE 事件原文 / 错误消息原文 / 截图描述>
- **期望的**：<判据编号 · 期望内容>
- **task_id**：<从 URL 或 DevTools 拿>
- **后端日志**：<uvicorn 控制台或 backend.err 相关行>
- **DB 交叉验证**：<相关 SELECT 结果>
- **归属判断**：□ Bug A/B/C 回归  □ §9.3.19 家族  □ 全新问题
```

**报回时给我这些就够了**，我负责归因 + 排 PR。

---

## §附 · 通关判定

| 节 | 判据 | 全过则 |
|----|------|--------|
| §4.1 | A1–A9（9 条） | Bug A + B + C 三修复**联合验证通过** |
| §4.2 | B1–B6（6 条） | PR-26 §Q4 顺路补的 merge hydration 验证通过 |
| §4.3 | C1–C3（3 条） | v1 挂账三 skill 全部激活 |
| §5 | A2 + A4 | PlanCard 确认链路通 |
| §6 | 5/8 事件类型 + error 补验 | SSE 覆盖达标（warning 可挂账） |

**全过 = MVP demo-ready 达成**，我会写 `MVP-VERIFY-RUN-REPORT-v2.md` 定稿 + 更新 HANDOFF 状态表。

**任一节挂 = 停在那节报回**，不要跳过继续跑后面的节 —— §4.2/§4.3 依赖 §4.1 验证的同一套 hydration + dispatch 基础设施，前者挂了后者的结果没有诊断价值。

---

## §附 · 跑完后的清理（可选）

```bash
# 若想把 dev DB 恢复干净（HANDOFF §9.4 陷阱 14 的命令）
docker exec recruitment-postgres psql -U recruitment -d recruitment_agent -c \
  "TRUNCATE TABLE match_scores, executions, tasks, candidate_status_history, candidate_notes, resumes, jds, skill_execution_logs, skill_versions, skills RESTART IDENTITY CASCADE;"
```

> **注意**：清完后**下次跑本地 pytest 前不用再清**（这就是陷阱 14 要解决的问题）· 但清完 `skills` 表后**重启后端会自动重新同步**，不影响。
