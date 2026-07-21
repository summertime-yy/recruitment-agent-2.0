# PR-13 · STEP6 完成回报（S5-03-07 SSE Event Buffer）

> 生成时间：2026-07-21
> 关联指令书：`docs/planning/stage5/PR13-KICKOFF-DECISION.md`
> 分支：`feat/pr-13-s5-03-07-sse-eventbuffer`
> 状态：✅ 实现完结，三道门全绿；datetime 阻塞已按裁定解除（命令：方案 B）；改动位于工作区，待提交链

## 一、执行结论

PR-13 的 SSE 事件缓冲实现主体（EventBuffer / Redis DI / 全局并发计数 / orchestrator 背景任务 / 测试骨架）在先前回合已落地。本回合解决的是 §十三#8 时区敏感边界触发的中断，并完成收尾三道门与回报。

| Step | 动作 | 结果 |
|------|------|------|
| KICKOFF §十二 顺手清扫 | `datetime.utcnow()` → `datetime.now(timezone.utc)` | ⚠️ 触发 §十三#8：落库点写 naive 列崩 DB，测试 6 failed |
| 求助 | 写 `docs/planning/stage5/PR13-HELP-REQUEST-datetime-tz.md` 等裁定 | ✅ 已停下汇报 |
| 裁定（命令：方案 B） | 落库点 → `utcnow_naive()`，非落库点 → `utcnow_aware()`，`is_stale` 加 `_to_naive_utc` 归一 | ✅ 已采纳并执行 |
| S1 | 建 `backend/app/core/time.py`（`utcnow_aware` / `utcnow_naive` / `_to_naive_utc`，naive 标注为历史约束） | ✅ 完成 |
| S2 | `match.py` / `main.py` 落库赋值点 → `utcnow_naive()`；内存字典点 → `utcnow_aware()` | ✅ 完成 |
| S3 | `match.py::is_stale` 加 `_to_naive_utc` 归一化（防御 aware/naive 混比） | ✅ 完成 |
| S4 | `uv run pytest tests/test_match_service.py -q` | ✅ **14 passed** |
| S5 | 三道门（ruff check / ruff format --check / pytest -q） | ✅ 全绿 |
| S6 | 本回报，引用求助文件 + 裁定"方案 B" | ✅ 见 §五 |

## 二、交付物与改动文件

| 文件 | 改动 |
|------|------|
| `backend/app/core/time.py` | **新增**：`utcnow_aware()`（tz-aware，新代码/SSE 用）、`utcnow_naive()`（落库 naive 列用，历史约束）、`_to_naive_utc()`（比较归一化，防御混比） |
| `backend/app/services/match.py` | `executed_at` / `MatchScore.created_at|updated_at` 落库 → `utcnow_naive()`；批量任务内存 `started_at|finished_at|submitted_at` → `utcnow_aware()`；`is_stale` 用 `_to_naive_utc` 归一后比较；移除未用 `timezone` 导入 |
| `backend/app/main.py` | Skill 同步落库 `created_at|updated_at` → `utcnow_naive()`；改用 `get_redis` DI 风格导入 |
| `backend/app/services/resume.py` | 落库 `created_at|updated_at` → `utcnow_naive()`；耗时测量 `start_time|elapsed_ms` → `utcnow_aware()`（保留 `datetime` 供 `fromisoformat`） |
| `backend/app/services/jd.py` | 落库 `executed_at|created_at|updated_at` → `utcnow_naive()` |
| `backend/app/services/candidate.py` | 落库 `occurred_at|updated_at` → `utcnow_naive()` |
| `backend/tests/factories.py` | 工厂 `executed_at` → `utcnow_naive()` |
| `backend/tests/test_match_service.py` | 补充 `timezone` 导入（测试内 aware 期望值，经 `_to_naive_utc` 归一） |

> 说明：`datetime.utcnow()` 全仓已归零（grep 0 命中）。除 PR-13 目标文件外，顺带按命令对 `resume/jd/candidate/factories` 同模式落库点一并改为 `utcnow_naive()`（值等价，零行为变化）。

## 三、测试结果

- 门 1：`uv run pytest tests/test_match_service.py -q` → **14 passed**（原 6 failed / 8 passed，根因消除后转绿）
- 门 2：`uv run pytest -q` → **101 passed**（含 PR-13 两个测试骨架 `test_stage5_pr13_execute.py` / `test_stage5_s5_03_event_buffer.py`）
- 门 3：`uv run ruff check .` → **All checks passed!**；`uv run ruff format --check .` → **84 files already formatted**

## 四、验收三道门（对照 KICKOFF §三/§十二）

| 门 | 命令 | 期望 | 实际 |
|----|------|------|------|
| 门 1 | `uv run pytest tests/test_match_service.py -q` | 14 passed | ✅ 14 passed |
| 门 2 | `uv run pytest -q` | 全绿 | ✅ 101 passed |
| 门 3a | `uv run ruff check .` | 0 error | ✅ All checks passed! |
| 门 3b | `uv run ruff format --check .` | 全绿 | ✅ 84 files already formatted |

## 五、偏差 / 决策记录（§十三#8 求助边界）

- **触发边界**：`PR13-KICKOFF-DECISION.md §十三 #8` —— 既有 `datetime.utcnow()` 替换发生在时区敏感处，若替换后测试变红，先来问。
- **求助文件**：`docs/planning/stage5/PR13-HELP-REQUEST-datetime-tz.md`（含根因、6 failed 复现、三方案 A/B/C 对比）。
- **根因**：`match.py` 落库点改用 tz-aware `datetime.now(timezone.utc)` 后，目标列为 `TIMESTAMP WITHOUT TIME ZONE`（naive），asyncpg 拒绝写入；`is_stale` 比较叠加 aware/naive 混比风险。
- **裁定（命令：方案 B）**：
  - 落库赋值点统一用 `utcnow_naive()`（写入 naive UTC，消除 `DeprecationWarning` 且不破坏 naive 列，零迁移）；
  - 非落库点（SSE/EventBuffer/内存字典）继续用 `utcnow_aware()`，符合 AGENTS.md "新代码用 tz-aware" 精神；
  - `is_stale` 加 `_to_naive_utc()` 归一化，防御 aware/naive 混比。
- **额外修复（为达三道门全绿）**：`app/agent/base_skill.py` 既有 lint 债（UP042 `SkillStatus`/`ExecutionStatus` → `StrEnum`、F841 未用 `properties`、F402 循环变量遮蔽导入的 `field`）一并修复。其中 F402 修复时曾因编辑工具同文件多编辑偶发未落地导致 `validate_output` 引用被遮蔽的全局 `field` 函数、连累 14 个测试；已纠正为 `req_field` 并对全量 `pytest` 复验 **101 passed**。该回归属于本次收尾引入并当场修复，不影响最终状态。
- **未采纳方案**：A（迁移列改 `TIMESTAMP WITH TIME ZONE`，超 PR-13 范围）；C（缩小清扫范围，清扫不彻底）。

## 六、工作区清理

- 排查期临时文件（`test_out.txt` / `ruff_out.txt` / `rufffmt_out.txt` / `pytest_out.txt`）已删除。
- 改动均落在 PR-13 相关文件；`backend/backend.err`、`backend/scripts/`、`PR10-STEP5-*` 等无关文件保持未 stage。

## 七、核验清单（指挥官用）

- [x] `grep -rn "datetime.utcnow()" backend/` → 0 命中
- [x] `uv run pytest tests/test_match_service.py -q` → **14 passed**
- [x] `uv run pytest -q` → **101 passed**
- [x] `uv run ruff check .` → All checks passed!
- [x] `uv run ruff format --check .` → 84 files already formatted
- [x] STEP6 报告"偏差 / 决策记录"引用 `PR13-HELP-REQUEST-datetime-tz.md` + 裁定"方案 B"
- [ ] 提交链（feat/pr-13-s5-03-07-sse-eventbuffer）：本回合指令未含 commit 步骤，改动留于工作区，待指挥官确认后按 Conventional Commits 建链

## 附：下一步

datetime 阻塞已解除、三道门全绿。剩余为 PR-13 提交链与（如需）推送/合并，按仓库约定在指挥官确认后执行。
