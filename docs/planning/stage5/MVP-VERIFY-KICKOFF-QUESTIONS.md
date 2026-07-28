# MVP 手工验收 · KICKOFF-QUESTIONS

> 目标：真实跑一遍 `docs/planning/stage5/MVP-VERIFY-CHECKLIST.md` §1-§9，产出验收 run report + 发现的 bug → HANDOFF §9.3 追债项。
>
> 类型：**docs-only 验收活动**（非代码 PR，无 red-test/commit split/feat 分支）；产出物为 `MVP-VERIFY-RUN-REPORT.md`，直接 commit 到 master（AGENTS.md §4.1）。
>
> 已定角色（用户已答）：**你跑 UI，我做后端伴跑**（读日志/查 PG/查 Redis buffer/curl API）；LLM 已配置（`backend/.env` 六项齐全）；严重 bug 当场修 · 其他登记。
>
> 起始 master HEAD：`46caeca`（PR-23 已合 + HANDOFF 已更）；migration head：`b6c7d8e9f0a1`；pytest 131/1 skipped；ruff 0 全仓；build ✓。
>
> 剩下 13 个议题需要确认口径与执行边界。

---

## §Q1 起服环境：docker compose 全套 vs 本机已有服务

**背景**：CHECKLIST §1 说 `docker compose up -d postgres redis`。但 `backend/.env` 里 MinIO 四项也填了，说明本机可能已有 MinIO 服务在跑（简历上传依赖 MinIO）。

**建议**：先跑一次 `docker compose ps` 确认已启动的容器，若 postgres/redis/minio 三个都在则直接进 §2 起后端；若缺则按 `docker compose up -d <缺的服务>` 补齐。**MinIO 是 §3 简历上传的硬依赖，若缺会直接 500**。

**议题**：确认 dev 环境本机的服务态是「已全套跑着」还是「需要 docker compose 起」？（决定第一步命令，我会按你答的走）

---

## §Q2 数据准备策略：全走 UI vs 部分 SQL 直插

**背景**：CHECKLIST 关键前置数据：
- §2 → 1 个 JD（走 `/chat` 或 `/jds/generate`）
- §3 → 至少 3 份简历（§4.1 需 1 份；§4.2 需 2 份同名；§4.3 复用 §3 简历）
- §5-§9 → §2/§3 产物的 task 链

**执行成本**：
- 全走 UI：真实体验最好，但 UI 每份简历上传 + LLM 生成 JD ≈ 1-2 分钟，全套 ≥15 分钟
- 部分 SQL 直插：§3 简历用 SQL 直插固件（含预解析字段），只留 §2 JD 生成走真实 LLM 验证 orchestrator 端到端；§4 三个 skill 仍走真实 chat

**建议**：**混合方案 · A**：JD 与 3 份简历全走 UI（这是 MVP demo 的必经流程，跳过就不叫端到端验收），预估 15-20 分钟。不走 SQL 直插 —— 那会绕过 `/api/v1/resumes/upload` 的 MinIO 落盘和解析路径，验收失去意义。

**议题**：确认走**全 UI 数据准备**（我建议）还是**混合直插**？

---

## §Q3 SSE 验证的两种方式：curl 抓流 vs 浏览器观察

**背景**：CHECKLIST §6 说「事件类型覆盖 8 种 + terminal 事件结束」。

**建议**：**双方式并行**：
1. **前端 UI 侧**（你）：在浏览器 devtools Network 面板看 `/api/v1/agent/tasks/{task_id}/stream` 请求，看事件流是否推进、看 PlanCard/看板是否随事件刷新
2. **后端 curl 侧**（我）：并行开一个 `curl -N .../stream` 抓原始 SSE，把 8 种事件类型出现顺序 log 下来存到 report

这样能同时验证「事件流本身完整」+「前端消费正确」。

**议题**：确认双方式并行还是仅前端观察？

---

## §Q4 §6 "terminal 事件" 的口径澄清

**背景**：CHECKLIST §6 说「流以 terminal 事件结束」，但 `SSEEventType` 8 种里没有 `terminal`。可能的口径：
- **A**：流关闭 = terminal（无显式 event，靠 HTTP stream close）
- **B**：某个 `system` 或 `result` 事件 = terminal 语义
- **C**：文档歧义，需 grep engine.py 确认

**建议**：进入验收前**我 grep 一次** `engine.py` / `act.py` 的 stream 关闭点，把「terminal 具体是什么信号」写入 §Q11 附录，如果发现文档歧义则**顺清 CHECKLIST §6** 表述（一并 commit）。

**议题**：确认允许我在验收 report 里附一节「§附 SSE 终止信号确认」并回写 CHECKLIST §6？

---

## §Q5 §9 CancelTask 三个状态的覆盖度

**背景**：CHECKLIST §9 说 "对一个 `executing`/`scoring` 中（或 `WAITING_CONFIRMATION`）的 task 发起取消"。三个状态：
- executing（skill 正在跑）
- scoring（skip-to-score 落分中）
- WAITING_CONFIRMATION（PlanCard 未确认，用户后悔）

**执行成本**：三个都要跑 = 3 个 task。executing 最容易触发（skill 跑起来后 5 秒内就点取消）；scoring 需要在 skip-to-score 后极短窗口内取消（可能来不及）；WAITING_CONFIRMATION 是 PlanCard 生成后不点确认直接取消。

**建议**：**A · 只测 executing + WAITING_CONFIRMATION**（scoring 窗口太短不稳定，且并非 demo 关键路径）；scoring 取消登记为「非阻塞未覆盖」到 report 附录。

**议题**：A · 只测 2 个 / B · 三个都测 / C · 只测 executing？

---

## §Q6 dev 库现状 · §7 unique 冲突预防

**背景**：CHECKLIST §7 排查段已提示 `uq_match_scores_jd_resume` 约束可能报重复。dev 库经过 PR-20/21/22/23 的验证跑，`match_scores` 表大概率已有历史数据。

**建议**：**验收前先 SQL 快照**当前 tasks/executions/match_scores/jds/resumes/candidates 六表行数，如果 `match_scores` 有旧数据且用同一 (jd, resume) 会撞 unique，方案二选一：
- **A · 清表**：TRUNCATE 六表（保留 skills / skill_versions / skill_execution_logs），得到纯净起点
- **B · 用新 jd_id**：这次验收生成新 JD，避免和历史撞

**我推荐 A · 清表**：验收结束后你也能直接看到「本次验收产生的所有落库数据」，report 更清晰。前提是**确认 dev 库无别人在共用**。

**议题**：A · 清六表 / B · 用新数据不清 / C · 你先看快照再决定？

---

## §Q7 P0/P1/P2 分级 & 当场修边界

**背景**：用户已答"严重 bug 当场修，其他登记"。需要明确"严重"的口径。

**建议分级**（我提议）：
- **P0（当场修，最多 1 hotfix PR）**：后端进程崩溃 / SSE 完全断流 / 核心 API 500 全挂 / 落库全失败（任一 skill 100% 无产物）
- **P1（登记不修）**：单一 skill 触发错 / 快照字段空 / UI 小 bug / duplicate key 类边界错误
- **P2（登记不修）**：文案错、样式抖动、日志刷屏、性能慢但可用

**当场修风险**：若 P0 出现，我要开新 feat 分支跑三门再 FF-merge，session 内工作量陡增；建议 P0 也**只修不能 workaround 的**（能通过换数据/重跑绕过的不算 P0）。

**议题**：认同这个分级和"仅修不能 workaround 的 P0"边界吗？

---

## §Q8 UI 侧与后端伴跑的通信 pattern

**背景**：你在浏览器点，我在 session 里做后端观察。需要一个高效的握手协议。

**建议 pattern**：
- **你每完成一节**告诉我：`§N 完成 · <一句话结果>` 或 `§N 卡住 · <现象>`
- **卡住时贴**：URL / 后端返回 body / devtools Console 报错文本 / Network 面板状态码
- **我这边**：随时在你 UI 操作前后查 PG 表行数、Redis buffer 键、`backend.err` 日志尾，快照式记录

**议题**：这个 pattern 你接受吗？还是有更顺手的（例如你直接把浏览器 Console/Network 复制粘贴给我）？

---

## §Q9 session 时间预算：一口气 vs 分批

**背景**：预估全套 §1-§9 = 环境起服 5min + UI 操作 20-30min + 中间等 LLM/SSE 完成 + bug 排查缓冲。乐观 60-90min，悲观 2-3h。

**建议**：**A · 一口气跑完 §1-§9**（session 上下文完整，我边跑边写 report），中间遇 P0 才停；如果发现 §1 就卡（起服失败）则退回 B。

**议题**：A · 一口气 / B · 先跑 §1-§4 报一次 / C · 分 3 批（§1-§3、§4-§6、§7-§9）？

---

## §Q10 report 落点与命名

**建议**：文件 `docs/planning/stage5/MVP-VERIFY-RUN-REPORT.md`，与 `MVP-VERIFY-CHECKLIST.md` 同目录呼应。docs-only 直接 commit 到 master（AGENTS.md §4.1 允许）。commit 信息：`docs(stage5): MVP end-to-end verify run report (2026-07-28)`。

**议题**：命名与落点认可？

---

## §Q11 Bug 登记双写：run report + HANDOFF §9.3

**背景**：CHECKLIST §10 表格是本 PR 期内的临时记录，正式追债应追加到 HANDOFF §9.3。

**建议**：**当场双写**：每个 P1/P2 bug 一发现就同时写到 (a) run report 内的 §Bug 表 (b) HANDOFF §9.3 追加新条目。这样 report 独立可读，HANDOFF 是历史真源。P0 hotfix 完成后再登记 §Bug 表说明"当场修 / commit hash"。

**议题**：双写认可？还是先攒完最后批量入 HANDOFF？

---

## §Q12 SSE 陷阱 11 复核（附赠 · 5 min 成本）

**背景**：HANDOFF §9.4 陷阱 11 提示前端必须用 `fetch + ReadableStream` 消费 SSE，不能用 `EventSource`。既然要跑 §6，可顺便 grep 一下 `frontend/src/**` 确认符合规范，避免验收时 SSE 断流才发现前端代码违规。

**建议**：**A · 顺便 grep 一次**（cheap，我做，5 min），发现违规写入 report。**B · 跳过，只在 §6 出问题时才查**。

**议题**：A / B？

---

## §Q13 dev 库验收结束后清理策略

**背景**：验收会造出 1 JD + 3 简历 + 若干 tasks/executions/match_scores。这些数据未来用不用？

**建议**：**A · 保留**（可用作后续开发的固件参考数据）；**B · 报完清六表**（还原纯净 dev 环境）；**C · 你决定**（report 里给出保留/清理二选一的命令，你选执行）。

**议题**：A / B / C？

---

## §求助边界 / stop-and-ask

以下情形，我在验收过程中**必须停下报告，不自决**：

1. **P0 触发但 hotfix 超过 1 文件 / 需改 schema / 需 migration**：这不是简单 hotfix，止血报告，等你指示是否开 PR-24
2. **CHECKLIST 内容与实际 API/代码矛盾**（例：某 endpoint 不存在或行为已变）：**不擅自改 CHECKLIST**，登记为"文档漂移"回报
3. **dev 库连不上 / Redis 连不上 / MinIO 连不上**：不擅自改 `.env`，回报现象等指示
4. **LLM 调用连续失败 3 次**：不排除是 quota / endpoint 变化，回报后等你确认
5. **发现 HANDOFF §9.4 陷阱以外的新陷阱**：即使可 workaround，也要登记 §9.4 新陷阱条目而非静默绕过
6. **§Q4 SSE terminal 语义 grep 无结论**：不擅自改 CHECKLIST，回报"文档歧义待澄清"

---

## §附 · 我提议的执行流水（若你全数采纳我的建议）

```
Step 0 · 起 KICKOFF-DECISION（我写 · 待你审）· ~5 min
Step 1 · 环境自检（docker compose ps + curl health + LLM smoke）· 5 min
Step 2 · dev 库快照 + 清六表（若 §Q6 = A）· 3 min
Step 3 · SSE 陷阱 11 前置 grep（若 §Q12 = A）· 5 min
Step 4 · §1 起服 · UI 跑 §2 JD 生成 · 我查 jds 表 · ~10 min
Step 5 · §3 简历 × 3 上传 · 我查 resumes/candidates 表 · ~10 min
Step 6 · §4.1/4.2/4.3 三个 skill 分别触发 · 我并行 curl SSE 抓事件 · ~30 min
Step 7 · §5 PlanCard 确认 · 我查 executions 表 · §6 SSE 8 类型清单 · 15 min
Step 8 · §7 skip-to-score · §8 match_scores 详情 · §9 CancelTask ×2 · 20 min
Step 9 · report + §Bug 双写 HANDOFF §9.3 + commit master · 15 min
```

预估：**90-110 min**（顺利），**150-180 min**（P0 触发 + hotfix）。

---

**待你回答上述 13 议题（可复用「全采纳我建议」一句话）。回后我写 KICKOFF-DECISION。**
