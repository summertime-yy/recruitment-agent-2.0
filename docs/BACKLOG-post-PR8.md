# PR-8 之后剩余需求 Backlog

> 生成日期：2026-07-18
> 用途：供指挥官（产品/技术负责人）决策下一阶段优先级
> 当前进度：**Stage 0–4 全部完成**（PR-1~PR-8 全链路闭环，前端 `tsc`/`lint` 通过、后端 51 + 前端 16 测试通过）
> 严格串行依赖链：**Stage 4 → 5 → 6 → 7**；技术债项可随时插入、不阻塞主线

---

## A 层 · 下一阶段（Stage 5，已明确为下一个目标）

### Stage 5 — Agent 对话核心（Orchestrator + SSE）
- 体验增强层，用自然语言驱动 JD/简历/匹配全流程（前 4 阶段已可独立运行）
- **数据表**：`tasks`、`executions`（需 Alembic 迁移）
- **核心组件**：Task Orchestrator（R-P-R-A-R 推理循环）、SSE 事件推送、Tool Router
- **API 契约**（严格遵循 `docs/api-contract.md`，禁止前后端各自定义）：
  - `POST /api/agent/chat`
  - `GET /api/agent/tasks/{id}/stream`（SSE）
  - `POST /api/agent/execute-plan`
  - `POST /api/agent/skip-to-score`
- **SSE 事件信封**：`type: thinking|plan|tool_call|progress|result|error|warning|system`
- **前端**：`ChatCenter.tsx`、`CandidateChat.tsx`（当前均为占位空壳，需实现对话任务中心）

> ⚠️ 这是最大的未知块：Orchestrator 架构、Tool Router 路由规则、SSE 重连/断点续传策略均需设计决策——建议先出设计文档再编码。

---

## B 层 · 依赖 Stage 5（顺延）

### Stage 6 — 推送与反馈
- **数据表**：`communications`、`feedback`
- **组件**：推送服务、推送/反馈 Skill
- **前端**：`PushFeedback.tsx`（占位空壳，需实现）

### Stage 7 — 看板与设置
- **数据表**：`analytics`
- **组件**：数据看板、Skill 管理页面、系统设置
- **前端**：`Analytics.tsx`、`Settings.tsx`（占位空壳，需实现）

---

## C 层 · 技术债 / 增强（可随时做，不阻塞主线）

| # | 项 | 现状 | 建议 |
|---|----|------|------|
| C1 | 去重升级 | 当前为 phone/email 硬匹配；路线图规划 `candidate-merge` Skill（智能合并）未实现 | 评估是否纳入 Stage 5 或独立小 PR |
| C2 | 候选人画像 | 路线图 `candidate-profile` Skill（画像标签自动生成）未实现 | 独立小 PR |
| C3 | 简历解析成功率 | 需批量上传不同长度/格式（PDF/DOCX）验证 ~100% 成功 | 测试任务；若截断把 `LLM_MAX_TOKENS` 提至 8192 |
| C4 | raw_text 截断长度 | 确认 `services/resume.py` 中实际截断值是否合理 | 快速核对 |
| C5 | 测试补强 | 后端 51 + 前端 16 已通过，建议补充边界/异常路径用例 | 持续进行 |
| C6 | .gitignore 清理 | `.uploads/`、`frontend/tsconfig.tsbuildinfo` 未忽略 | 顺手修 |
| C7 | 路线图文档不一致 | `development-roadmap.md` 仍把 Stage 1 前端标"待开发"、Stage 2/3 仅列 slice 未标完成；实际 Stage 1–4 已全完成 | 以 HANDOFF 为准修订路线图 |

---

## D 层 · Phase 2 未排期（待指挥官定优先级）

| 页面 | 路由 | 说明 |
|------|------|------|
| `InterviewSchedule.tsx` | `/interview` | 面试排期，未排期 |
| `CompareAnalysis.tsx` | `/compare` | 对比分析，未排期 |
| `WorkflowTrack.tsx` | `/workflow` | 流程跟踪，未排期 |
| `ResumeWorkspace.tsx` | `/resumes`（旧版残留） | 可清理 |

---

## 建议决策点（抛给指挥官）

1. **Stage 5 是否立即启动？** 它是下一个硬依赖块，但架构设计工作量最大，建议先产出 Orchestrator 设计文档（R-P-R-A-R 细节、Tool Router、SSE 契约落地）。
2. **C1/C2（去重升级、候选人画像）是否提前到 Stage 5 之前做？** 它们是独立小 PR，可先交付价值、不阻塞主线。
3. **Phase 2 三页是否纳入本轮规划？** 涉及产品范围确认。
4. **文档一致性**：确认以 HANDOFF 为事实源，修订 `development-roadmap.md` 的 Stage 状态标注。

---

## 附：已交付（PR-8 收尾后全清单）

- Stage 0 基础层 ✅
- Stage 1 JD 管理（CRUD + AI 生成 + 前端页）✅
- Stage 2 简历解析（上传/解析/预览/编辑/删除 + 工作台）✅
- Stage 3 候选人管理（状态流转 + 标签 + 来源 + 去重 + 备注 + 多 JD 关联）✅
- Stage 4 人岗匹配评分（match_scores + matching Skill + 6 类 API + 评分报告/列表/详情/双向联动 + 多 JD 管理 + 生成评分加载反馈）✅
