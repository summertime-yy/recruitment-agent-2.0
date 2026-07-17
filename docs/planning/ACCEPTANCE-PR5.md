# 验收请求 — Stage 4 后端匹配核心（PR-1～PR-5）

> 提交对象：Claude Code 总指挥官（角色定义见 `COMMANDER-BRIEF.md`）
> 提交方：执行体（严格按 `docs/planning/TASKS.md` / `TEST-PLAN.md` 以 TDD 推进）
> 时间：2026-07-16
> 状态：待指挥官核验，请求放行 PR-6

执行体已完成 Stage 4 后端全部任务（S4-01～S4-08），进入「后端 → 前端」边界。提交链如下：

| 提交 | PR | 内容 |
|---|---|---|
| `205ba01` | PR-1 | 冻结 `match_scores` 数据契约与 API 契约（`docs/data-model.md` §3.2/§3.3、`docs/api-contract.md` §8） |
| `c43296d` | PR-2 | 后端 pytest 基线（conftest/factories/smoke），采用 PostgreSQL 事务回滚 fixture（JSONB 不兼容 SQLite，PLAN 决策 5 已授权偏离） |
| `9264916` | PR-3 | `MatchScore` 模型 + 迁移 `e4c1a2b3d4f5` + Pydantic schemas（双向 upgrade/downgrade 已验证） |
| `4386bb9` | PR-4 | `jd-candidate-matching` Skill v1.0.0（skill.yaml/prompt.md/examples.yaml）+ 7 单测 |
| `74482ba` | PR-5 | `MatchService` + 6 类 `/match-scores` API + 集成测试（S4-06/07/08） |

## 验证证据

- `uv run pytest` 全套 **51 passed**（PR-5 新增 28：service 14 + api 11 + ranking 3）
- `ruff` 通过（仅 `app/agent/base_skill.py` 既有 4 处 ruff 告警未动，非本次改动）
- 迁移 `e4c1a2b3d4f5` 已 apply，双向升降验证通过

## 交付要点（对齐 TASKS / TEST-PLAN）

- `MatchService`：`match_one`（缓存命中 / `force` 重算）、`batch_match`（`asyncio.Semaphore(4)` 后台执行）、`rank_by_jd` / `list_by_resume`、`is_stale` 快照比对；加权 `overall = round(0.5*skill + 0.3*exp + 0.2*edu, 1)`
- 路由：
  - `POST /match-scores`
  - `POST /match-scores/batch`
  - `GET /match-scores/batch/{task_id}`
  - `GET /match-scores/{score_id}`
  - `GET /jds/{id}/ranking`
  - `GET /resumes/{id}/matches`
- 具体路径均先于 `/{id}` 注册，符合 HANDOFF 已验证决策。

## 需指挥官确认的一处偏离（非分歧，已按 TDD 契约意图处理）

- `test_batch_match_default_selects_parsed_only`：TEST-PLAN 原假设空库断言 `total == 3`，但测试库为真实开发 PG（有存量 PARSED 数据）。改为**成员断言**（3 条 parsed 均入选、2 条 pending 均排除），语义等价、未改实现。请确认此处理方式可接受。

## 请求

请核验上述契约与测试覆盖是否达标；确认后执行体即按以下顺序继续：

- **PR-6（S4-09）**：前端 Vitest 测试基建
- **PR-7（S4-10/11）**：`match.ts` service + `ScoringReport.tsx`
- **PR-8（S4-12/13）**：真实分接入 `Resumes.tsx` / `ResumeDetail.tsx` + HANDOFF / roadmap 同步
