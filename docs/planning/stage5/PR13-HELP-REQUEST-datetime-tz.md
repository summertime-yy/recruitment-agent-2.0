# PR-13 求助回报：`datetime` tz 清扫命中 §十三#8 时区敏感边界

**分支**：`feat/pr-13-s5-03-07-sse-eventbuffer`
**日期**：2026-07-21
**发起**：agent（执行 §十二"顺手清扫"时触发）
**状态**：⛔ 已停下，等待指挥官裁定

---

## 一、背景

按 `PR13-KICKOFF-DECISION.md §十二`，PR-13 在主线任务（C_BUF/C_ACT/C_EXEC/C_COUNT + 三道门）之外顺手清扫 `datetime.utcnow()` → `datetime.now(timezone.utc)`，以符合 AGENTS.md "新代码用 tz-aware" 的要求。

清扫范围涉及 `backend/app/services/match.py` 与 `backend/app/main.py`（§十三#8 标注的 "services/match.py / main.py 批量" 点位）。

## 二、触发情形（§十三 #8）

> §十三 #8：既有 `datetime.utcnow()` 替换发生在**时区敏感**处，若替换后测试变红，先来问。

执行清扫后运行 `uv run pytest tests/test_match_service.py`，结果 **6 failed, 8 passed**，命中求助边界，立即停下。

## 三、复现与根因

### 失败用例

```
FAILED test_match_one_creates_row_when_first
FAILED test_match_one_returns_cached_when_not_force
FAILED test_match_one_recomputes_when_force_true
FAILED test_match_one_writes_skill_execution_log
FAILED test_overall_score_uses_weighted_average
FAILED test_is_stale_when_resume_updated_after_score
```

### 根因

1. `match.py` 已把落库时间点（如 `skill_execution_logs.executed_at`）改为 `datetime.now(timezone.utc)`（tz-aware）。
2. 目标 DB 列是 **`TIMESTAMP WITHOUT TIME ZONE`**（naive），asyncpg 拒绝写入 aware 值：

   ```
   DataError: invalid input for query argument $11:
     can't subtract offset-naive and offset-aware datetimes
   [SQL: INSERT INTO skill_execution_logs (... executed_at)
         VALUES (... $11::TIMESTAMP WITHOUT TIME ZONE)]
   ```

3. 前 5 个失败全部崩在 DB 写 `executed_at` 这一层。
4. 第 6 个 `is_stale` 用例额外叠加一层 Python 比较风险：`later`(aware) vs `resume_updated_at_snapshot`(naive)。

> 注：EventBuffer / SSE 侧按 §三 已用 `datetime.now(timezone.utc).isoformat()`，只生成 ISO 串、**不入库**，与 naive 列无冲突，无需改动。

## 四、待裁定的三个方案

| 方案 | 做法 | 代价 / 风险 |
|---|---|---|
| **A** | Alembic 迁移把相关列改为 `TIMESTAMP WITH TIME ZONE`，全仓统一 tz-aware | 需新增迁移，影响面大，**超出 PR-13 范围**；可能波及其他服务读写点 |
| **B（agent 倾向）** | DB 写入点统一存 **naive UTC**（封装 `_utcnow_naive()`），消除 `DeprecationWarning` 又不破坏 naive 列；`is_stale` 比较加时区归一防御 | 零迁移、零回归，改动局限在 `match.py`/`main.py` |
| **C** | 缩小 §十二 清扫范围：**凡写 DB 列的赋值点保留 naive**（保留 `utcnow()` 或等价 naive），只在 SSE/非 DB 场景用 aware | 清扫不彻底，但最保守、最小扰动 |

### agent 建议：方案 B

- 新增 `_utcnow_naive()` 小工具用于所有落库时间点。
- SSE/EventBuffer 侧继续用 aware ISO 串（不入库、无冲突，保持不变）。
- `is_stale` 内做 tz 归一防御（比较前统一 to naive UTC 或统一 aware）。

既满足 AGENTS.md "新代码用 tz-aware" 的精神（SSE/内存侧 aware），又不触碰 naive 列、不引入迁移、不扩大 PR 范围。

## 五、当前已完成、未受阻的部分

以下生产与测试文件均已就位，本次阻塞**仅卡在 datetime 清扫这一步**：

- `backend/app/agent/orchestrator/event_buffer.py`（SSE 事件缓冲，Redis List `sse:buf:{task_id}`，MAXLEN=200，终态 TTL 3600s）
- `backend/app/core/redis.py`（Redis lifespan + `Depends(get_redis)` DI，已移除全局单例）
- `backend/app/agent/orchestrator/active_counter.py`（全局并发计数 `task:active`，INCR/DECR + 1h TTL，超限 429 `TASK_LIMIT_EXCEEDED`）
- `backend/app/agent/orchestrator/engine.py`、`act.py`（`_safe_emit` / 背景任务 `run_execute` / `run_skip_to_score`）
- `backend/app/main.py`（lifespan 挂 `app.state.redis`）
- `backend/tests/conftest.py`（client 夹具 + redis mock）
- 测试骨架：`tests/test_stage5_pr13_execute.py`、`tests/test_stage5_s5_03_event_buffer.py`

## 六、裁定后待办

待指挥官选定方案（A/B/C）后，agent 继续推进：

1. 应用选定方案的 datetime 修复，使 `test_match_service.py` 全绿。
2. 完成 PR-13 主线清单：C_BUF / C_ACT / C_EXEC / C_COUNT。
3. 三道门（lint / format / pytest）全绿。
4. 提交链（按 Conventional Commits）。
5. 撰写 STEP6 报告。

---

**请指挥官在 A / B / C 中裁定，agent 收到后继续。**
