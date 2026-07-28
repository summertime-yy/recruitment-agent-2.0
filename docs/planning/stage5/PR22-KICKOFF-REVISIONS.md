# PR-22 KICKOFF · REVISIONS（指挥官回复）

> 来源：`docs/planning/stage5/PR22-KICKOFF-QUESTIONS.md`（executor `5fc7238`）
> base：master `7198737`
> 状态：**已批复 · 全部 Q 采纳（含 4 处指令假设更正）· executor 起 DECISION**

---

## 〇 总评 · Grep 复核翻出 4 个指令假设错误，KICKOFF 值回票价

执行体没有照我的指令抄，而是先 grep 实证：

1. **无 `frontend/src/router/`**——路由在 `App.tsx:69-83` 平铺。指令的"router/ 目录"是我脑补。
2. **`docker-compose.yml` 已存在**（含 postgres+redis+minio）——指令交付面 5 归零。
3. **`backend/.env.example` 不存在**，只有根 `.env.example`——AGENTS.md 的措辞对齐是"copy 根份"，不新增 backend 份。
4. **根 `README.md` / `docs/README.md` 都不存在**——指令的"若顶层有就加章节"两个分支都落空，需要新建。

这 4 处若没 grep 到就动手，PR-22 会写出一份基于错误前提的 diff。KICKOFF 停下问是正确姿势。

---

## §一 逐条 REVISIONS

### Q1 · 6 空壳页清单 + 空分组处理 → 通过 + 补口径

6 页清单准确，`candidate-chat` 排除正确。空分组处理定案：

- **analytics-group**：整组注释掉（含分组标题 `nav-group-label`）——留一个空标题在 sidebar 会显示"分析与设置"下面没有任何项，UI 破碎。
- **phase2-group**：**保留标题 + 保留 candidate-chat 唯一项**——分组语义仍成立（"更多功能"确实只剩一个候选人聊天入口是合理的），且 candidate-chat 是 Stage 5 真交付面，展示优先。

注释块顶部统一加一行注释（executor 已提议，采纳原文）：
```tsx
// Stage 6/7 未实施 · MVP 隐藏（PR-22）——功能落地后取消注释即可恢复
```

**动作：Q1 定稿。**

### Q2 · 隐藏策略 → (A) sidebar 注释 + (B1) 路由保留

**Q2a** (A) sidebar 注释：定案。

**Q2b** (B1) 路由保留：定案。补一条决策理由——`PlaceholderPage` 是"友好占位组件"，直接 URL 访问不算 bug（且防止有人书签了 `/analytics` 后升级到 MVP 报 404 的坏体验）；sidebar 隐藏 = 主流量入口封闭 = 达成"MVP 不引诱用户点空白"目标已足够。

**动作：Q2 定稿。TS `noUnusedLocals` 无需处理（route 保留，import 保留）。**

### Q3 · 验收清单 10 节结构 → 通过 + skip-to-score 用 curl

10 节结构完全采纳。第 9 节 skip-to-score 用 curl 作入口——**接受**。补一条：curl 命令末尾附一段 SQL 核对（`SELECT score_id, overall_score, status FROM match_scores WHERE jd_id=... AND resume_id=... ORDER BY created_at DESC LIMIT 5;`），便于验收者不看 SSE 也能看到"分数真的落库了"（PR-21 F1 修复的直接回归证据）。

第 8 节 SSE 事件全序列的排查提示里追加一条：**若发现事件缺 `plan_step_started` / `plan_step_completed`，先 grep `backend/app/agent/orchestrator/engine.py::_background_execute` 是否走了 `on_step_start` / `on_step_end` 回调**（PR-14/20 修复过的老坑，防回归排查线索）。

**动作：Q3 定稿。**

### Q4 · README 位置 + .env.example → 通过（4a 选 A · 4b 选 A）

**Q4a** 新建根 `README.md`：定案。结构建议（executor 自主，非强制）：

```
# Recruitment Agent 2.0
一句话项目定位（招聘领域垂直 agent，Stage 5 已交付 chat/JD/简历/匹配主流程）
## 快速上手（3 步）
### 1. 起服 · docker-compose
### 2. 数据库迁移 & 后端
### 3. 前端
## MVP 验收
链接 `docs/planning/stage5/MVP-VERIFY-CHECKLIST.md`
## 开发者指南
链接 `AGENTS.md`、`HANDOFF.md`、`docs/planning/PLAN-STAGE5.md`
```

**Q4b** 不新增 `backend/.env.example`：定案。README 起服第 2 步显式写 `cp .env.example backend/.env`（Windows：`copy .env.example backend\.env`）。

**动作：Q4 定稿。**

### Q5 · compose 已存在 + 短命令 → 通过

- compose 交付面归零。
- **`docker compose up -d postgres redis`**（精确起两个）：MVP 验收不依赖 minio（简历文件上传当前走 backend `/resumes` 端点，文件存 `resumes.parsed_content` JSON 字段，不需要 S3），减一个容器减一份 debug 面。README 里可加一行"minio 是 Stage 6 附件上传预留 · MVP 阶段可不起"。
- 不新增短命令：定案。

**动作：Q5 定稿。**

### Q6 · 新 bug 登记不修 → 通过

登记表尾部一节 + STEP6 报告实际发现 + 本 PR 不碰 HANDOFF.md：全部定案。HANDOFF 追加由指挥官（我）合并后统一做，与 PR-21 惯例一致。

**动作：Q6 定稿。**

### Q7 · 求助边界 → 通过 + 补一条

executor 5 条全采纳。补：

6. **验收清单撰写过程中，如需查阅 `HANDOFF.md §9.3` 未覆盖的历史 bug（超出 §9.4 陷阱清单）以撰写"失败排查"提示——停下问指挥官**（避免把非既定 bug 塞进验收文档）。

### Q8 · `npm run test` 是否入门 → **不入门**

理由：sidebar 注释不碰任何被 vitest 覆盖的组件（vitest 目前测的是 `MessageTimeline` / `PlanCard` / `StreamStatusBar` / `ChatCenter`，MainLayout 无测试）。三门保持 `pytest + ruff + npm run build`。**但**：STEP6 报告里额外注明"`cd frontend && npm run test` 局部跑了一次做防回归 · 结果 31 passed 不变"作为附加信息，不列入正式门。

**动作：Q8 定稿。**

---

## §二 追加决策（Revisions 期发现）

### R1 · 验收清单文档路径确认

executor 用 `docs/planning/stage5/MVP-VERIFY-CHECKLIST.md`——定案。放 `docs/planning/stage5/` 与其他 stage 5 文档同源，便于将来 archive。

### R2 · sidebar 注释后前端 lint 检查

`cd frontend && npm run lint` 不是三门里明写的必过项，但 sidebar 是 tsx 改动——**建议 executor 顺手跑一次**，若报"unused variable"要处理（可能 import 的 icon 无引用）。0 warning 是"清洁交付"的暗合规，非强制。

### R3 · STEP6 报告结构（本 PR 特殊）

因为主要是文档 + 少量前端，STEP6 报告可参考 PR-19 的"轻交付"格式（不必套用 PR-20/21 的 8 章模板）。至少覆盖：三门 tail、契约核对表（Q1-Q8 全绿）、求助边界触发情况、交付摘要（3 个 commit）、若有验收中发现的新 bug 列一节。

---

## §三 求助边界（DECISION 版本预定）

复用 QUESTIONS §七 5 条 + R1（Q7 补的）1 条 = 6 条 stop-and-ask，DECISION 阶段收纳完整清单。

---

## §四 时间预估

原估 1-2 天。实际因 grep 充分、方案清晰，估 **1 天**：
- KICKOFF REVISIONS + DECISION：0.25 天（本轮）
- 实现（sidebar 注释 + 验收清单 + README）：0.5 天
- 手工验收（真跑一遍清单）：0.25 天

Track A / B 并行推进，B 未阻塞 A。

---

## §五 executor 下一步动作

1. 起 `docs/planning/stage5/PR22-KICKOFF-DECISION.md`（本次由我直接落，见下一提交）
2. DECISION 批准（本 REVISIONS 已批 · DECISION 自动成 contract）后拉分支 `feat/pr-22-s51-mvp-release-prep`
3. 三门 + STEP6 → 送我 FF-merge 复审

---

*commander 批复 · REVISIONS 完成 · executor 可起 DECISION*
