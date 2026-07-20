# PR-12 · Orchestrator 主循环启动前求助

> 关联：PR-12（S5-05/06/07/08）· 分支 `feat/pr-12-s5-05-08-orchestrator`
> 触发：TASKS-STAGE5.md 与 api-contract.md 未固化以下 5 个架构接触面
> 状态：等待指挥官裁定，暂停 PR-12 生产代码实现

## Q1 · Reason/Reflect 输出 JSON 结构

**已知**：api-contract §5.1 声明 `ReasonOutput.task_type: string`、`missing_entities: array`；
`ReflectOutput.is_feasible: bool`。

**歧义**：
- Reason 是否需要输出 `intent_summary`（供 Plan 阶段 prompt 引用）？
- Reason 是否需要输出 `parsed_entities`（结构化实体：jd_id/candidate_ids/keyword...）？
- Reflect 除 `is_feasible` 外，`reason` / `blocking_reason` 字段是否需要？

**建议**：Reason 输出 `{task_type, intent_summary, parsed_entities, missing_entities}`；
Reflect 输出 `{is_feasible, blocking_reason?, suggestion?}`。

**影响**：ReasonSkill / ReflectSkill 的 `output_schema`（skill.yaml）与 5 用例断言。

## Q2 · emit 回调签名（同步 / 异步）

**已知**：TASKS §S5-07 说 `run_act(plan, ctx, emit) -> list[StepResult]`；
S5-03（PR-13）将由 Redis `LPUSH` 提供实现（async）。

**歧义**：
- `emit` 是 `def emit(ev: dict) -> None`（同步）还是 `async def emit(ev: dict) -> None`（异步）？
- 若异步，Act 里如何处理"emit 失败但不影响主流程"（`asyncio.create_task` 触发-遗忘？）？

**建议**：`async def emit(ev: dict) -> None`；Act 内 `await emit(ev)`，捕获 emit 异常
仅 log warning 不中断执行。

**影响**：`act.py` 签名与 Reflect-Act Skill 是否需要传 emit。

## Q3 · chat 端点是否内含 Act

**已知**：
- api-contract §4.1 `POST /agent/chat` → 返回 `task_id + status=WAITING_CONFIRMATION`
- api-contract §4.2 `POST /agent/execute-plan` → 触发 Act
- PLAN §5 R-P-R-A-R 描述为一体化流程

**歧义**：
- `chat` 是否只跑 R-P-R（Reason→Plan→Reflect-Plan）后停在 WAITING_CONFIRMATION？
- Act（Act + Reflect-Act）是否**只**由 `execute-plan` 触发？
- 或 `chat` 内部条件性触发 Act（例如 confidence 高时直接 Act）？

**建议**：`chat` 严格停在 WAITING_CONFIRMATION；`execute-plan` 独占 Act 触发权。
`skip-to-score` 例外，直达 EXECUTING（bypass R-P-R 但仍走 Act+Reflect-Act）。

**影响**：`engine.run_chat` / `engine.run_execute` / `engine.run_skip_to_score` 分层。

## Q4 · Redis 全局活跃计数策略

**已知**：TASKS §S5-08 说全局活跃 `task:active`（Redis INCR/DECR + TTL）；
达 10 抛 429 `TASK_LIMIT_EXCEEDED`。

**歧义**：
- TTL 值？（建议 3600s / 1h 兜底防泄漏）
- Redis 客户端在本 PR 内建立，还是**推迟到 PR-13** 与 EventBuffer 一起接？

**建议**：本 PR 用可注入的 `ActiveCounter` 抽象接口（内存实现 + Redis 实现留占位）；
测试用内存 mock 打满 10 触发 429。真实 Redis 接线由 PR-13 完成。

**影响**：`engine.py` 依赖注入设计、S5-08-3 用例的 mock 方式。

## Q5 · 超时配置（硬编码 vs settings）

**已知**：TASKS §S5-08 数字：单 Skill 120s / 阶段 180s / 整体 600s。

**歧义**：
- 硬编码还是引入 `SKILL_TIMEOUT_SEC / PHASE_TIMEOUT_SEC / TASK_TIMEOUT_SEC` 3 个新配置？
- 测试如何在不真等 120s 的前提下验证超时（monkeypatch 到 0.01s）？

**建议**：引入 3 个 settings 配置（默认 120/180/600），测试通过 `monkeypatch.setattr(settings, "SKILL_TIMEOUT_SEC", 0.01)` 触发。

**影响**：`backend/app/core/config.py` 追加 3 个字段、engine.py 从 settings 读。

## Q6+ · 执行体在红骨架时发现的新歧义

（执行体写红骨架时如遇新歧义，按 Q1–Q5 格式追加）

- **Q6 · `OrchestratorEngine` 构造依赖注入面**：红骨架中 `OrchestratorEngine(registry=...)`、
  `OrchestratorEngine(active_counter=...)`、`OrchestratorEngine(skill_timeout_sec=...)` 三处
  构造签名均为占位猜测。建议统一为 `OrchestratorEngine(registry, active_counter=None,
  settings=None)`，超时与计数均经 settings / 注入对象读取，避免散落位置参数。待指挥官确认
  最终构造契约。
- **Q7 · 状态机 `TransitionGuard` 是否独立于 Engine**：TC-S5-08-2/6/7/8 直接对 `TransitionGuard`
  做单元测试，暗示其为独立可测单元。建议 `TransitionGuard` 作为纯函数/轻量类独立存在，
  `OrchestratorEngine` 组合使用。待确认是否纳入 `engine.py` 同文件或独立 `state_machine.py`。
