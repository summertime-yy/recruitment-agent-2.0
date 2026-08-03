# PR-28 · KICKOFF-DECISION

> 关联：`PR28-KICKOFF-QUESTIONS.md`（commit `b28a7a6`）· `MVP-VERIFY-v2-CHECKLIST.md` §4.1 实跑失败 · HANDOFF §9.3.20（PR-26 hydration）· §9.3 追债项 11 未尽部分
> 起始 master HEAD：**`b28a7a6`**（PR-28 QUESTIONS 已合）
> 上一轮验收 baseline：pytest **145 passed / 2 skipped**（历史）· 当前实测 **144 passed / 1 failed / 2 skipped**（见 §四.6）· ruff 0 · frontend 34 passed · build ✓ · migration head `b6c7d8e9f0a1`
> 类型：**代码 PR**（feat 分支 · red-test · commit split · FF-merge）
> 分支：`feat/pr-28-fix-execute-db-passthrough-and-schema-injection`
> **零 schema / migration 变更 · 纯后端 · 不触 frontend**

---

## §一 · 裁决汇总

| Q | 议题 | 裁决 | 备注 |
|---|------|------|------|
| Q1 | `session_factory` 透传收敛方式 | **A** · 补形参 + 全改关键字传参 | 指挥官"其余全采纳" |
| Q2 | `input_schema` 注入内容裁剪 | **A** · 全量 schema + `HYDRATION_HINTS` 说明行 | **指挥官显式锁定** |
| Q2.1 | `HINTS`/`RULES` key 一致性单测 | **加** | |
| Q3 | hydration 兼容 `candidate_ids` | **A** · 单元素兼容 + 多元素报错 | |
| Q4.1 | 终态 status 判定 | **A** · 全失败 FAILED · 部分成功 COMPLETED | |
| Q4.2 | `executions` 补列落点 | **A** · start 写入参 · end 写错误 | |
| Q5 | 测试用例设计 | **A** · 5 新增 + 1 既有回归 | |
| Q6 | `test_factories` 失败处置 | **A** · 本 PR 顺手修测试隔离 | **指挥官显式锁定** |
| Q6.1 | HANDOFF §9.4 补陷阱 | **补** | |
| Q7 | commit split | **A** · 6 commit | |

---

## §二 · 背景压缩（执行体必读的**四条冷事实**）

> 完整推导见 `PR28-KICKOFF-QUESTIONS.md` §背景。此处只留执行必需的结论。

1. **plan 的 `tool_input` 不为空** —— DB 实测 `{"candidate_ids": ["res_dbec095e3b24"]}`，LLM 抽对了 ID，只是键名是**复数数组**而 `hydration.py:27` 只认**单数字符串**。
   `executions.input_params = NULL` **不能**证明 plan 无参数 —— `_make_db_execution_writer` 从不写该列（`grep input_params engine.py` 零命中）。

2. **真因：`/execute` 端点漏传 `session_factory`** —— `agent.py:177` 无该参数（对比 `:221` skip-to-score 有）；`run_execute`（`engine.py:484`）签名里**根本没有**该形参；`:522` 用**位置传参**调 `_background_execute`，止于 `execution_writer` → `session_factory=None` → 走 `engine.py:615` else 分支 → `run_act` 不带 `db=` → `dispatch(db=None)` → 命中 `hydration.py:83-84` 抛 `ToolParamError("hydration for 'candidate-profile' requires a db session")`。
   **这是 PR-21 §3.5 db 透传的漏网点**（当时补了 `act.py:108` 与 skip-to-score，`/execute` 漏了；因为 PR-21 时期 `/execute` 链路上无任何组件需要 db）。

3. **`_format_dispatchable_tools()`（`engine.py:222-235`）只输出名+描述，不含 `input_schema`** —— plan LLM 靠猜键名。这是 §9.3 追债项 11（PR-17）的未尽部分：PR-17 解决了"有哪些 tool"，没解决"每个 tool 要什么参数"。

4. **全步失败仍写 `COMPLETED`** —— `run_act`（`act.py:133-153`）把必需步失败**吞成** `StepResult(success=False)` + emit ERROR 后 `break`，**正常 return**；`_background_execute`（`engine.py:640-645`）只在抛异常/超时时写 FAILED，故无条件写 COMPLETED。DB 实测 `task_807a603401f2`：`status=COMPLETED` · `result.content={"error":"step_1 执行失败"}` · `artifacts=[]` · `error=NULL`。

---

## §三 · 修复面与实现骨架

### §三.1 · 修复面 1（P0 阻塞）· `session_factory` 透传

**改 3 处。**

**① `engine.py::run_execute` 签名加形参**（`:484-494`）：

```python
    async def run_execute(
        self,
        task_id: str,
        plan: dict[str, Any] | None = None,
        accepted_steps: list[str] | None = None,
        modifications: list[dict[str, Any]] | None = None,
        db: Any = None,
        event_buffer: EventBuffer | None = None,
        db_updater: DbUpdater | None = None,
        execution_writer: Any | None = None,
        session_factory: Any = None,          # ← PR-28 新增（与 run_skip_to_score 对称）
    ) -> dict[str, Any]:
```

**② `engine.py:522-525` 的 `_background_execute` 调用全改关键字传参**（Q1-A 的核心 —— 根治"加参数就静默错位"）：

```python
        asyncio.create_task(
            self._background_execute(
                task_id,
                plan,
                buffer,
                db_updater=db_updater or self.db_updater,
                execution_writer=execution_writer,
                session_factory=session_factory,      # ← PR-28：漏传点
            ),
            name=f"orch-execute-{task_id}",
        )
```

> 前 3 个（`task_id` / `plan` / `buffer`）保持位置传参即可——它们是 `_background_execute` 的必填前缀，不会错位。**从 `db_updater` 起全部关键字**。
> `run_skip_to_score`（`:547-556`）已是这个形态，保持不动。

**③ `agent.py:177-184` 端点传参**：

```python
    resp = await engine.run_execute(
        req.task_id,
        plan=task_plan,
        accepted_steps=req.accepted_steps,
        modifications=req.modifications,
        db_updater=db_updater,
        execution_writer=exec_writer,
        session_factory=async_session_factory,     # ← PR-28：与 skip_to_score(:221) 对齐
    )
```

### §三.2 · 修复面 2（P0 阻塞）· 全量 `input_schema` 注入 + `HYDRATION_HINTS`

**① `hydration.py` 新增 `HYDRATION_HINTS` 常量**（紧邻 `HYDRATION_RULES`，同 key）：

```python
# PR-28 Q2-A：面向 plan LLM 的提示语 —— 说明哪些字段由 hydration 从 DB 自动补齐、
# LLM 实际应该提供什么键。key 必须与 HYDRATION_RULES 完全一致（TC-PR28-3 断言）。
HYDRATION_HINTS: dict[str, str] = {
    "candidate-profile": (
        "注意：`parsed_content` / `existing_tags` 由系统从数据库自动补齐，**你不要填写**。"
        "你只需提供 `candidate_id`（字符串，单个候选人的 resume_id，如 `res_xxxx`）。"
    ),
    "candidate-merge": (
        "注意：每个 resume item 的 `candidate_name` / `parsed_content` / `tags` / "
        "`duplicate_of_resume_id` 由系统从数据库自动补齐，**你不要填写**。"
        "你只需提供 `resumes: [{resume_id: \"res_xxx\"}, {resume_id: \"res_yyy\"}]`"
        "（**至少 2 个**，用于判定是否为同一候选人的重复简历）。"
    ),
}
```

> `candidate-merge` 的 hint 显式写出 `minItems: 2` 的语义，这是 §4.2 的已知边界（PR-26 §五 #4）—— 让 LLM 知道单份简历不该走 candidate-merge。

**② `engine.py::_format_dispatchable_tools` 重写**（`:222-235`）：

```python
    def _format_dispatchable_tools(self) -> str:
        """把当前 registry 全量 dispatchable 工具格式化为 Markdown 列表（含内置工具）。

        与 ``dispatchable_tool_names`` 口径一致（BUILTIN_TOOLS + list_dispatchable），
        供 plan skill 的 USER_TEMPLATE ``{{ dispatchable_tools }}`` 占位注入。

        PR-28 Q2-A：每个工具追加全量 ``input_schema`` JSON；对 HYDRATION_RULES 登记的
        工具追加 HYDRATION_HINTS 说明行（避免 LLM 去填 hydration 该补的字段）。
        """
        import json

        from app.agent.orchestrator.hydration import HYDRATION_HINTS

        lines = ["可用工具列表："]
        for name in sorted(BUILTIN_TOOLS.keys()):
            desc = BUILTIN_TOOLS[name].get("description", "")
            lines.append(f"- `{name}`（内置工具）：{desc}")
            schema = BUILTIN_TOOLS[name].get("input_schema") or {}
            if schema:
                lines.append(f"  - 入参 schema：`{json.dumps(schema, ensure_ascii=False)}`")
        for skill in self.registry.list_dispatchable():
            tt_note = f"（task_type: {skill.task_type}）" if skill.task_type else ""
            lines.append(f"- `{skill.skill_id}`{tt_note}：{skill.description}")
            schema = getattr(skill, "input_schema", None) or {}
            if schema:
                lines.append(f"  - 入参 schema：`{json.dumps(schema, ensure_ascii=False)}`")
            hint = HYDRATION_HINTS.get(skill.skill_id)
            if hint:
                lines.append(f"  - {hint}")
        return "\n".join(lines)
```

**约束**：
- `import json` / `HYDRATION_HINTS` 用**函数体内 import**（`hydration.py` 已 import `tool_router`，模块级反向 import 会成环 —— 与 `tool_router.dispatch` 内 import hydration 同一手法）。
- **必须保留原有的 `- \`{name}\`` 行格式** —— `tests/test_stage5_pr17_orchestrator_routing.py:67` 的 `_assert_dispatchable_injected` 断言 `tool in plan_user_prompt`，改格式会破 PR-17 回归（TC-PR28-6）。
- `ensure_ascii=False` —— schema 里的中文 description 不要转义成 `\uXXXX`，否则 prompt 里全是乱码、白烧 token。

### §三.3 · 修复面 3（P1）· hydration 兼容 `candidate_ids`

**改 `hydration.py::_hydrate_candidate_profile`**（`:19-40`），只动取 `cid` 那一段：

```python
async def _hydrate_candidate_profile(tool_input: dict[str, Any], db: Any) -> dict[str, Any]:
    """从 resumes 表补 parsed_content + existing_tags 到 candidate-profile 的 tool_input。

    - 键：``candidate_id`` / ``resume_id``（单数字符串，来自 plan LLM 的 tool_input）
    - PR-28 Q3-A：兼容 ``candidate_ids`` / ``resume_ids`` 单元素数组（LLM 非确定性防御层）；
      多元素直接抛 ToolParamError 并指向 candidate-merge（**不静默取首个**）
    - 未提供任何候选人 ID → ToolParamError
    - resume 不存在 → ToolParamError
    - parsed_content 为 None（parse_status != PARSED）→ ToolParamError
    """
    cid = tool_input.get("candidate_id") or tool_input.get("resume_id")
    if not cid:
        # PR-28 Q3-A：LLM 常输出复数键 + 数组（MVP-VERIFY v2 §4.1 实测）
        for plural_key in ("candidate_ids", "resume_ids"):
            vals = tool_input.get(plural_key)
            if not vals:
                continue
            if len(vals) > 1:
                raise ToolParamError(
                    f"candidate-profile handles exactly one candidate; got {len(vals)} "
                    f"in '{plural_key}' — use candidate-merge for multiple resumes"
                )
            cid = vals[0]
            logger.warning(
                "candidate-profile tool_input used plural key '%s'; "
                "expected singular 'candidate_id' (PR-28 compat path)",
                plural_key,
            )
            break
    if not cid:
        raise ToolParamError("candidate-profile requires 'candidate_id' in tool_input")
    # ... 以下不变（select Resume / row is None / parsed_content is None / return）
```

**约束**：
- `hydration.py` 目前**无 logger** —— 需在文件头补 `import logging` + `logger = logging.getLogger(__name__)`。
- `logger.warning` 是 Q3-A 的**明确要求**：兼容分支必须留痕，否则会掩盖修复面 2 的退化。
- **`len(vals) > 1` 必须报错，不得静默取首个**（Q3-C 已否 —— 用户选 3 个只画像 1 个且无提示，比报错更坏）。

### §三.4 · 修复面 4（P1）· 终态判定 + `executions` 补列

**① 终态 FAILED 判定** —— `engine.py::_background_execute`，在 `artifacts = _build_artifacts(results)` 之后、`_write_task` 之前插入：

```python
            artifacts = _build_artifacts(results)
            result_payload = {"content": reflect_act_out.get("final_result", ""), "artifacts": artifacts}
            # PR-28 Q4.1-A：无任何成功步 → 终态 FAILED（此前无条件写 COMPLETED，
            # 使前端把全失败任务渲染成成功态）。optional 步失败仍算部分成功 → COMPLETED。
            all_failed = bool(results) and not any(r.success for r in results)
            if buffer is not None:
                await buffer.append(task_id, SSEEventType.RESULT, result_payload)
                await buffer.set_terminal_ttl(task_id)
            if all_failed:
                first_err = next((r.error_message for r in results if r.error_message), "all steps failed")
                await self._write_task(
                    db_updater,
                    task_id,
                    {
                        "status": "FAILED",
                        "finished_at": utcnow_aware(),
                        "result": result_payload,
                        "error": {"code": "ALL_STEPS_FAILED", "message": first_err, "recoverable": False},
                    },
                )
            else:
                await self._write_task(
                    db_updater,
                    task_id,
                    {"status": "COMPLETED", "finished_at": utcnow_aware(), "result": result_payload},
                )
```

**已核实的两点（执行体不必重查）**：
- `LEGAL_TRANSITIONS[EXECUTING] = {COMPLETED, FAILED}`（`state_machine.py:31`）—— **`EXECUTING → FAILED` 合法**，Q7 边界 4 不会触发。
- `_write_task`（`engine.py:459-461`）只是 `await db_updater(task_id, patch)`，**不做 transition 校验** —— 无需额外守卫。
- `results` 为空（plan 无 steps）时 `all_failed=False` → COMPLETED，保持既有行为（`act.py:90-91` 空 steps 返 `[]`）。**不要**把空 plan 判成 FAILED。
- **保留 RESULT 事件 + TTL**（即使全失败）—— `act.py:147` 已 emit 过 ERROR 事件，前端需要 RESULT 收尾才能结束流。

**② `executions` 补写 `input_params` / `error_message`** —— 三处联动：

`act.py`：`StepCallbackFn` 类型别名扩展 + 调用点带上 `tool_input`：

```python
# (step_id, tool_name, tool_input) → None    # PR-28 Q4.2-A
StepCallbackFn = Callable[[str, str, dict[str, Any]], Awaitable[None]]
```

```python
        # PR-20 S5.1: on_step_start callback（PR-28：带 tool_input 供 executions 落库）
        if on_step_start is not None:
            await on_step_start(step_id, tool_name or "", tool_input)
```

`engine.py:587-591` 适配器：

```python
        if execution_writer is not None:
            async def _on_start(step_id: str, tool_name: str, tool_input: dict[str, Any]) -> None:
                await execution_writer(step_id, tool_name, "start", tool_input=tool_input)

            async def _on_end(step_id: str, result: Any) -> None:
                await execution_writer(step_id, result.tool_name, "end", result)
```

`engine.py::_make_db_execution_writer` 的 `writer`：

```python
    async def writer(
        step_id: str, tool_name: str, action: str, result: Any = None, tool_input: Any = None
    ) -> None:
        async with session_factory() as db:
            if action == "start":
                ...
                row = Execution(
                    task_id=task_id,
                    step_id=step_id,
                    phase="ACT",
                    tool_name=tool_name,
                    execution_status="PENDING",
                    started_at=now,
                    input_params=tool_input,          # ← PR-28 Q4.2-A
                )
                ...
            elif action == "end":
                ...
                row.execution_status = status
                row.finished_at = finished
                if sr is not None and getattr(sr, "error_message", None):
                    row.error_message = sr.error_message      # ← PR-28 Q4.2-A
                ...
```

> `executions.input_params` 列类型是 `json`（已核实 `\d executions`），直接塞 dict 即可，**无需 migration**。
> `error_message` 列类型 `text`，nullable。

**⚠️ 全仓 `on_step_start` 调用点排查** —— 改签名前先 `grep -rn "on_step_start" app/ tests/`，所有调用点（含测试中的 fake callback）都要同步改成 3 参。

### §三.5 · Q6-A · `test_factories` 隔离修复

**根因**：`tests/factories.py:9` 的 `build_skill()` 硬编码 `skill_id="jd-candidate-matching"`，与 `main.py::_sync_skills_to_db()` 灌入 dev 库的 10 行真实 skill 撞主键。PR-25/26 期的 TRUNCATE 曾让 `skills` 表意外为空、掩盖了这个脆弱性。

**改法**：`build_skill` / `build_skill_execution_log` 的默认 `skill_id` 改为**不与真实 skill 撞名**的值：

```python
# tests/factories.py
_TEST_SKILL_ID = "test-only-skill"   # PR-28 Q6-A：不得与 _sync_skills_to_db 灌入的
                                     # 10 个真实 skill_id 撞主键（见 HANDOFF §9.4 新增陷阱）

def build_skill(**kwargs) -> Skill:
    data: dict = {
        "skill_id": _TEST_SKILL_ID,
        "skill_name": "测试专用 Skill",
        "current_version": "1.0.0",
        "status": "ACTIVE",
    }
    data.update(kwargs)
    return Skill(**data)


def build_skill_execution_log(**kwargs) -> SkillExecutionLog:
    data: dict = {
        "skill_id": _TEST_SKILL_ID,     # ← FK → skills.skill_id，必须与 build_skill 一致
        "version": "1.0.0",
        ...
    }
```

`tests/test_factories.py:29` 的断言同步改：

```python
    assert log.skill_id == "test-only-skill"
```

**已核实**：`build_skill` 全仓仅 `test_factories.py:23` 一处使用；`SkillExecutionLog.skill_id` 有 `ForeignKey("skills.skill_id")`（`app/models/skill.py:28`），所以两个 factory 的 `skill_id` **必须一致**。

---

## §四 · 测试用例（TC-PR28-1..5 新增 · TC-PR28-6 既有回归）

| TC | 文件 | 类型 | 覆盖 | 断言要点 |
|----|------|------|------|---------|
| TC-PR28-1 | `tests/test_stage5_pr28_execute_db.py` | 集成 | 修复面 1 | `run_execute(session_factory=fake)` → 捕获 `dispatch` 收到的 `db` **非 None**。**不 mock `run_act`**（防 PR-21 F1 的 mock 屏蔽 root cause 陷阱，HANDOFF §9.4.24）—— mock `ToolRouter.dispatch` 或注入 fake router |
| TC-PR28-2 | `tests/test_stage5_pr28_schema_injection.py` | 单元 | 修复面 2 | `_format_dispatchable_tools()` 输出含 `parsed_content` / `existing_tags` / `keyword` / `jd_id` / `resume_id`；含 `candidate_id`（来自 hint）；且**仍含**全部 5 个工具名（PR-17 格式兼容） |
| TC-PR28-3 | 同上 | 单元 | Q2.1 | `set(HYDRATION_HINTS) == set(HYDRATION_RULES)` |
| TC-PR28-4 | `tests/test_stage5_pr28_hydration_compat.py` | 单元（fake db） | 修复面 3 | ① `{"candidate_ids": ["res_x"]}` → 正常补齐 `parsed_content`/`existing_tags`；② `{"candidate_ids": ["a","b"]}` → `ToolParamError` 且 message 含 `candidate-merge`；③ `{}` → `ToolParamError` 含 `candidate_id` |
| TC-PR28-5 | `tests/test_stage5_pr28_terminal_status.py` | 集成 | Q4.1 | ① 唯一必需步失败 → `db_updater` 收到 `status="FAILED"` + `error.code=="ALL_STEPS_FAILED"`；② optional 步失败但有成功步 → `status=="COMPLETED"`（可拆 5a/5b） |
| TC-PR28-6 | `tests/test_stage5_pr17_orchestrator_routing.py` | **既有回归 · 不新增文件** | 修复面 2 | `_assert_dispatchable_injected` 仍绿 —— 改 `_format_dispatchable_tools` 后不得破 PR-17 断言 |

**新增用例数 = 5**（TC-PR28-1..5）。TC-PR28-6 是既有文件回归，**不计入新增**。

**预期 baseline**：`144 (当前实测) + 1 (Q6 修复的 test_factories) + 5 (新增) = 150 passed / 2 skipped`。

> ⚠️ 我在 PR-27 DECISION §三.4 犯过把回归项计入新增数的算术错（写 35 应为 34）。本次显式分离并双路验算：
> 历史 145 passed 含当前失败的 test_factories → 145 + 5 = **150**。两条路径一致。
> **实测与 150 不符请报回（§五 边界 5），不要自行调整期望值。**

---

## §五 · 求助边界 / stop-and-ask（严格遵守）

1. **归因验证边界（最重要）** —— 修复面 1（commit 2）落地后**必须立即**复跑一次 §4.1 或等效 curl e2e，确认 §二.2 的推断成立：错误应变为 `hydration for 'candidate-profile' requires a db session` 或（若 commit 4 已落）正常补齐。
   **若实际错误仍是 `Input validation failed: 'parsed_content' is a required property`** —— 说明还有**第三条未知路径**绕过了 hydration，**停 · 报指挥官**，不要继续往下改。
   （执行体上报的这条错误在当前 master 链路上不可能出现，我判断来自 PR-26 合入前的旧日志或绕过 dispatch 的诊断脚本 —— 但必须实测确认。）

2. **`input_schema` 注入后 token / 质量边界** —— 若注入全量 schema 后 plan prompt 超模型上限，或实测 LLM 输出**质量下降**（如开始编造 `parsed_content`、或不再输出正确 `tool_name`），**停 · 报**，不要自行改成裁剪方案（Q2-C 已被否决）。

3. **`minItems: 2` 边界（继承 PR-26 §五 #4）** —— 若 §4.2 candidate-merge 因 `minItems: 2` 失败，**不得改 `skill.yaml`**，停 · 报。

4. **状态机边界** —— 已核实 `LEGAL_TRANSITIONS[EXECUTING] = {COMPLETED, FAILED}` 合法、`_write_task` 不做 transition 校验，**本边界预期不触发**。若仍出现 `IllegalTransitionError`，**停 · 报**，不要自行放宽状态机。

5. **测试数量边界** —— 实测 passed 数与 §四 预期（**150**）不符时**报回**，不要自行调整期望值。

6. **不得触碰** —— `frontend/**`（纯后端 PR）· `alembic/versions/**`（零 schema 变更）· 任何 `skill.yaml` 的 `input_schema.required` · `app/main.py::_sync_skills_to_db`（Q6 修的是测试侧，不是同步逻辑）。

7. **文档读法** —— 引用本 DECISION 的任何 import 路径 / 行号前**先 grep 确认**，不要凭直觉复述（PR-26 曾因此误报 `skill_errors` 模块不存在，浪费一轮往返）。

8. **`on_step_start` 签名变更边界** —— 改签名前 `grep -rn "on_step_start" app/ tests/` 排查全部调用点。若发现 **3 处以上**调用点（预期仅 `act.py` 定义处 + `engine.py` 适配器 + 可能的测试 fake），**停 · 报**，评估是否改用 `**kwargs` 兼容形态。

---

## §六 · commit split（6 commit）

| # | 类型 · 消息 | 内容 |
|---|-----------|------|
| 1 | `test(pr-28): red-test skeleton TC-PR28-1..5 + fix test_factories skill_id collision` | 3 个新测试文件（全 fail / xfail）+ §三.5 的 `factories.py` / `test_factories.py` 隔离修复（**此项应立即转绿**，使 baseline 从 144 → 145） |
| 2 | `fix(orchestrator): pass session_factory through /execute to run_act (PR-21 gap)` | §三.1 三处改动。**落地后立即执行 §五 边界 1 的归因验证** |
| 3 | `feat(orchestrator): inject full input_schema + hydration hints into plan prompt` | §三.2 · `HYDRATION_HINTS` + `_format_dispatchable_tools` 重写 |
| 4 | `fix(hydration): accept singleton candidate_ids array, reject multi with hint` | §三.3 · 兼容层 + `logger.warning` |
| 5 | `fix(orchestrator): write FAILED on all-steps-failed + persist executions input/error` | §三.4 ① 终态判定 + ② `executions` 补列（含 `on_step_start` 签名变更） |
| 6 | `docs(stage5): PR-28 STEP6 report + HANDOFF §9.3.22 + §9.4 pitfall` | STEP6 报告 + HANDOFF §9.3.22（Bug D CLOSED）+ §9.4 新陷阱（Q6.1：测试插 `skills` 表须与 `_sync_skills_to_db` 的 10 行错开）+ 状态表更新 |

---

## §七 · 验收门禁（四道门 · 输出须粘贴进 STEP6 报告）

```bash
cd backend
uv run pytest -q                      # 期望 150 passed / 2 skipped
uv run ruff check app/ tests/         # 期望 All checks passed
```

前端**不触碰**，故 `npm test` / `npm run build` **仅需确认未改动**（`git diff --stat master -- frontend/` 应为空），不必重跑。

**第四道门 · e2e 归因验证**（本 PR 特有）：
- commit 2 后按 §五 边界 1 复跑，记录实际错误信息。
- commit 5 后完整复跑 MVP-VERIFY v2 **§4.1**，记录 A1–A9 判据结果。**§4.2 / §4.3 不在本 PR 门禁内**（LLM 非确定性，留给指挥官的浏览器验收）。
- 两次复跑的**原始输出**（SSE 事件序列 + `tasks` / `executions` 表实际行）粘进 STEP6 报告。

---

## §八 · 执行流程

```
1. git checkout master && git pull                      # 起点 b28a7a6
2. git checkout -b feat/pr-28-fix-execute-db-passthrough-and-schema-injection
3. commit 1 (red-test + factories 隔离修复)
4. commit 2 (session_factory 透传) → 【立即执行 §五 边界 1 归因验证】
5. commit 3 (input_schema + HYDRATION_HINTS)
6. commit 4 (hydration 兼容层)
7. commit 5 (终态 FAILED + executions 补列)
8. 跑 §七 四道门 → 复跑 §4.1
9. commit 6 (STEP6 报告 + HANDOFF)
10. push 分支，报回指挥官复审（**不要自行 FF-merge / 删远程分支**）
```

> 起始 HEAD `b28a7a6` 已在 §头部核实（`git log --oneline -1` 实测）。
> ⚠️ 远端 push 当前可能超时（`ssh.github.com:443` timeout）—— 若 `git pull` / `git push` 失败，**本地提交照常进行**，报回时注明未推送状态，不要因此中断。

---

## §附 · 工作区清理（不属本 PR，勿提交）

`_verify/` · `backend/_diag_uat.py` · `backend/backend.err` · `backend/mig1.txt` · `backend/scripts/` · `backend/test-full.txt` · `frontend/_pr27_dbg*.txt` · `frontend/_pr27_test.txt` · `graphify-out/` · `docs/planning/stage5/{C2-FIXTURE-DECISION,PR10-STEP5-*,PR10-STEP6-REPORT,PR11-STEP6-REPORT,PR15-STEP6-REPORT,PR23-STEP6-REPORT}.md`

**`backend/_seed_resume_uat.py` / `backend/_seed_resume2_uat.py` 保留** —— §七 第四道门复跑 §4.1 要用。

---

_裁决：sub-commander · 2026-07-27 · Q1–Q7 全部锁定（Q2-A / Q6-A 指挥官显式指定，余项"其余全采纳"）· 执行体可开工_
