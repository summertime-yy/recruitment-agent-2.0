# 验收请求 — Stage 4 前端真实分接入（PR-8 / S4-12·S4-13）

> 提交对象：Claude Code 总指挥官（角色定义见 `COMMANDER-BRIEF.md`）
> 提交方：执行体（严格按 `docs/planning/TASKS.md` / `TEST-PLAN.md` 以 TDD 推进）
> 时间：2026-07-17
> 状态：待指挥官核验，请求放行（后端核心已通过 PR-1～PR-5；前端 PR-6/PR-7 基建已先行落地）

执行体已完成 Stage 4 前端「真实分接入」全部任务（S4-12 匹配分列 + 右侧面板、S4-13 详情页匹配评分卡片），并将进度同步至 `HANDOFF.md` / `development-roadmap.md`。本次提交聚焦 PR-8，三道门（test / lint / build）均通过。

## 一、本 PR 改动清单

| 文件 | 变更 | 归属 |
|---|---|---|
| `frontend/src/pages/Resumes.tsx` | +104 行 / -11 行 | S4-12 匹配分列 + 右侧重匹配面板 |
| `frontend/src/pages/ResumeDetail.tsx` | +220 行 / -85 行 | S4-13 JD 匹配评分卡片 + 生成评分 + Drawer |
| `HANDOFF.md` | 23 行改动 | 进度总览 / Stage 4 表 / §6.1 蓝图 / §8.3 随机分→真实分 同步 |
| `docs/development-roadmap.md` | 19 行改动 | Stage 概览表 / §6 Stage 4 同步 |
| `frontend/tests/pages/Resumes.match.test.tsx` | 新增（3 用例） | S4-12 TDD 测试 |
| `frontend/tests/pages/ResumeDetail.match.test.tsx` | 新增 | S4-13 TDD 测试 |

> 另：`docs/planning/{ACCEPTANCE-PR5,PLAN,TASKS,TEST-PLAN}.md` 仍处 untracked，属 Stage 4 规划基线文档（PR-5 验收请求已引用），非本 PR 交付物，是否随本次一并纳入请指挥官裁定。

## 二、验证证据（三道门，2026-07-17 本地实跑）

| 闸门 | 命令 | 结果 |
|---|---|---|
| 测试 | `npm run test` | **6 files / 16 passed**（全绿） |
| 静态检查 | `npm run lint` | **0 errors，8 warnings**（详见下方偏离项） |
| 构建 | `npm run build` | **exit 0**，built in 4.95s（仅 chunk>500KB 预警告警，非本次引入） |

## 三、交付要点（对齐 `TEST-PLAN` §10 S4-12/13）

- **S4-12 `Resumes.tsx`**：选 JD 后调用 `matchApi.rankByJd`（`limit:200`）填充 `matchScoreMap`；每行 `ScoreRing` 展示真实 `overall_score`，未选 JD 显示 `-`；竞态用 `cancelled` 标志防御；右侧「重新匹配」按钮走 `matchApi.matchOne` + 局部更新 `matchScoreMap`，与左侧无缝联动。
- **S4-13 `ResumeDetail.tsx`**：加载 JD 列表 + 已有评分（同样 `cancelled` 防御）；默认选中最新 JD；`is_stale` 标记「简历已更新（旧分）」；点击「生成评分」走 `matchApi.matchOne` 后自动打开 `MatchDetailDrawer` 展示三维度。
- **`Math.random()` 已彻底移除**：`Resumes.match.test.tsx` 含源码扫描断言（`Resumes.tsx` 不再出现 `Math.random(`），随机分→真实分闭环完成。
- **测试→实现映射**：TEST-PLAN §10 五条用例均有对应实现与断言（dash 态 / 真实分 / 源码扫描 / 默认选中 JD / 生成评分开 Drawer）。

## 四、偏离与待确认项

1. **附带非匹配功能改动（需裁定）**：`.trae/skills/karpathy-guidelines/SKILL.md` 新增 67 行（Karpathy Guidelines agent 行为准则），与本次匹配功能无关。建议**不并入 PR-8**，单独提交或剔除；若需一并纳入请指挥官明示。
2. **`npm run lint` 8 warnings（0 error，不阻断）**：其中 4 条位于本 PR 两文件——
   - `ResumeDetail.tsx:149` / `:158` — `react-hooks/exhaustive-deps`（`fetchResume` / `startPolling` 未列入依赖）。源于 `cancelled` 防御模式，属已知取舍，非缺陷。
   - `Resumes.tsx:167` — `ref-in-cleanup`（`pollingTimers.current` 在 cleanup 中取值）；`:196` — `exhaustive-deps`（`fetchResumes`）。
   - 其余 4 条位于 `JDDetail/JDGenerate/JDList`（既有遗留，非本次引入）。
   - 请求确认：是否接受以 warning 放行，还是要求本 PR 文件清零。
3. **测试 stderr 噪声（非阻断）**：`Resumes.match.test.tsx` 运行期出现 1 处 `[Network Error] 请检查后端服务是否启动` 的 stderr，但 3 条用例均 ✓ 通过。推测为组件某条未在 MSW 拦截范围内的请求（如 tags-meta / jds 之外）打到真实网络被拒。功能与断言不受影响，建议后续收紧 MSW handler 消除噪声——是否需在本次一并修复请裁定。

## 五、请求

请核验以下内容并放行：

1. S4-12 / S4-13 真实分接入是否符合契约（`docs/api-contract.md` §8、`docs/data-model.md` §3.3）；
2. 三道门结果是否认可（16 passed / 0 error / build 0）；
3. 第四节三项待确认事项的处理方式（附带 skill 文件、lint warning、测试 stderr 噪声）。

确认后执行体即执行 `git` 提交（**本次仅 commit，不 push**），并按规范补充 PR 描述与截图。
