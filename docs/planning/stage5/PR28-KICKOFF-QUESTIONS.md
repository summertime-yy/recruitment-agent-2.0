# PR-28 · KICKOFF-QUESTIONS

> 关联：`docs/planning/stage5/MVP-VERIFY-v2-CHECKLIST.md` §4.1 实跑失败 · HANDOFF §9.3.20（PR-26 hydration）· §9.3（追债项 11 未尽部分）
> 起始 master HEAD：`ee3276c`（MVP-VERIFY v2 清单已合）
> 上一轮验收 baseline：pytest **145 passed / 2 skipped** · ruff 0 · frontend 34 passed · build ✓ · migration head `b6c7d8e9f0a1`
> **当前实测 baseline 已破：pytest 144 passed / 1 failed / 2 skipped** —— 见 §Q6（非本 PR 代码引入）
> 类型：**代码 PR**（feat 分支 · red-test · commit split · FF-merge）
> 分支建议：`feat/pr-28-fix-execute-db-passthrough-and-schema-injection`
> 求助边界：继承 AGENTS.md / CLAUDE.md 通用 + 本 PR 增补（§Q7）

---

## §背景 · MVP-VERIFY v2 §4.1 实跑失败的**五条冷事实**

执行体上报的归因是「`_format_dispatchable_tools()` 不含 input_schema → plan LLM 不知道要 `candidate_id` → `tool_input` 为空 → hydration 抛 ToolParamError」。
**该归因方向部分正确，但三处与 DB / 代码实证矛盾。** 以下是我逐条核实后的实况。

### 事实 1 · plan 的 `tool_input` **不为空，且 ID 抽对了**

```
$ docker exec recruitment-postgres psql -U recruitment -d recruitment_agent \
    -t -c "select task_id, status, plan from tasks order by created_at desc limit 1;"

task_807a603401f2 | COMPLETED | {"steps": [{"step_id": "step_1",
  "tool_name": "candidate-profile",
  "tool_input": {"candidate_ids": ["res_dbec095e3b24"]},   ← 非空！ID 正确！
  "description": "为候选人 res_dbec095e3b24 生成人才画像"}], "reasoning": null}
```

LLM **成功**从 user_message 抽到了 `res_dbec095e3b24`，只是键名写成**复数 + 数组** `candidate_ids: [...]`，而 `hydration.py:27` 只认**单数 + 字符串** `candidate_id` / `resume_id`。

执行体所称的「`executions` 表 `input_params=null`」是真的，但**不能证明 plan 无参数** —— 因为 `_make_db_execution_writer`（`engine.py:77-118`）**从来不写这一列**：

```
$ grep -n "input_params" app/agent/orchestrator/engine.py
（零命中）
```

`error_message` 同样恒为 NULL。执行体把「writer 未实现的列」误读为「plan 无参数」。

### 事实 2 · **真因是 `/execute` 端点漏传 `session_factory`（PR-21 §3.5 db 透传的漏网点）**

`app/api/v1/agent.py:177` 调 `run_execute` 时**没有** `session_factory=async_session_factory`；对比 `:221` 的 `skip_to_score` 是传了的：

| 端点 | 行号 | 传 `session_factory`？ |
|------|------|----------------------|
| `POST /agent/execute` | `agent.py:177-184` | ❌ **无** |
| `POST /agent/skip-to-score` | `agent.py:215-222` | ✅ `session_factory=async_session_factory` |

而 `run_execute`（`engine.py:484-494`）**签名里根本没有 `session_factory` 形参**，`:522-524` 用**位置传参**调 `_background_execute`，止于 `execution_writer`：

```python
asyncio.create_task(
    self._background_execute(task_id, plan, buffer, db_updater or self.db_updater, execution_writer),
    #                                                                              ↑ 到此为止，session_factory 默认 None
)
```

于是 `_background_execute` 走 `engine.py:615` 的 `else` 分支 —— `run_act(...)` **不带 `db=`** → `act.py:109` `router.dispatch(tool_name, tool_input, db=None)` → `hydrate_tool_input(..., db=None)` → 命中 `hydration.py:83-84`：

```python
if db is None:
    raise ToolParamError(f"hydration for '{tool_name}' requires a db session")
```

**这个分支在读 `candidate_id` 之前就抛** —— 所以执行体贴的 `Input validation failed: 'parsed_content' is a required property` **不可能**来自当前 master 的这条链路（hydration 会先挡下）。该错误信息形态是 `base_skill.validate_input` 的 jsonschema 输出，说明它来自 **PR-26 hydration 合入前的旧一轮日志**，或来自绕过 `dispatch` 直调 `skill.execute` 的临时诊断脚本。**归因需在修复后复跑确认**（见 §Q7 边界 1）。

之所以这个漏网点到今天才暴露：PR-21 时期 `/execute` 链路上**没有任何东西需要 db**（唯一需要 db 的 builtin `match_score` 只走 skip-to-score），`/execute` 上第一个需要 db 的组件就是 PR-26 刚加的 hydration。

### 事实 3 · `_format_dispatchable_tools()` 确实不含 `input_schema`（执行体归因正确的部分）

`engine.py:222-235` 只输出**工具名 + 描述**：

```python
lines = ["可用工具列表："]
for name in sorted(BUILTIN_TOOLS.keys()):
    desc = BUILTIN_TOOLS[name].get("description", "")
    lines.append(f"- `{name}`（内置工具）：{desc}")
for skill in self.registry.list_dispatchable():
    tt_note = f"（task_type: {skill.task_type}）" if skill.task_type else ""
    lines.append(f"- `{skill.skill_id}`{tt_note}：{skill.description}")
```

plan LLM 完全靠猜键名。这是 HANDOFF §9.3 追债项 11（PR-17 `bcc6c3b`）的**未尽部分** —— PR-17 解决了「LLM 不知道有哪些 tool_name」，没解决「LLM 不知道每个 tool 要什么参数」。

数据源是现成的：`BUILTIN_TOOLS[name]["input_schema"]`（`tool_router.py:58` 起）+ `skill.input_schema`（`base_skill.py:92` 从 skill.yaml 载入）。全量 required 字段实测：

| tool_name | internal | `input_schema.required` |
|---|---|---|
| `search_resumes` | builtin | `[keyword]` |
| `read_jd` | builtin | `[jd_id]` |
| `match_score` | builtin | `[jd_id, resume_id]` |
| `candidate-profile` | false | `[parsed_content, existing_tags]` |
| `candidate-merge` | false | `[resumes]`（item required `[resume_id]` · `minItems: 2`）|
| `jd-candidate-matching` | false | `[jd, resume]` |
| `jd-generation` | false | `[title, description]` |
| `resume-parsing` | false | `[raw_text]` |

⚠️ **注意 hydration 与 input_schema 的口径冲突**：`candidate-profile` 的 schema required 是 `[parsed_content, existing_tags]`，但**这两个字段恰恰是 hydration 要从 DB 补的、LLM 不该给的**。LLM 真正该给的是 schema 里**根本没声明**的 `candidate_id`。直接把 raw `input_schema` 注入 prompt，会指示 LLM 去填 `parsed_content` —— **正是 PR-26 明确要避免的行为**（payload 爆炸 + 数据冗余 + 幻觉）。此矛盾是 §Q2 的核心议题。

### 事实 4 · 步骤全失败仍写 `COMPLETED`（观感级 bug）

同一条 task 记录：

```
status = COMPLETED
result = {"content": {"error": "step_1 执行失败"}, "artifacts": []}
error  = NULL
```

`_background_execute`（`engine.py:593-691`）只在**抛异常 / 超时**时写 FAILED；而 `run_act`（`act.py:133-153`）把必需步失败**吞成** `StepResult(success=False)` + emit ERROR 事件后 `break`，**正常 return**。于是 `:640-645` 无条件写 `COMPLETED`：

```python
artifacts = _build_artifacts(results)     # 全失败 → []
result_payload = {"content": reflect_act_out.get("final_result", ""), "artifacts": artifacts}
await self._write_task(db_updater, task_id, {"status": "COMPLETED", ...})   # ← 无条件
```

前端收到 `COMPLETED` 会渲染成成功态。MVP demo 现场必然被看出来。

### 事实 5 · **pytest baseline 已破（非本 PR 代码引入）**

```
$ uv run pytest -q
FAILED tests/test_factories.py::test_factories_build_skill_execution_log
1 failed, 144 passed, 2 skipped in 7.92s

# 根因
asyncpg.exceptions.UniqueViolationError: duplicate key value violates
  unique constraint "skills_pkey"
DETAIL:  Key (skill_id)=(jd-candidate-matching) already exists.
```

`test_factories.py:23` 的 `db_session.add(build_skill())` 插 `jd-candidate-matching`，与 dev 库 `skills` 表已有行冲突。**dev 库 `skills` 表现有 10 行** —— 是我按 MVP-VERIFY v2 §0.2 起后端时 `main.py::_sync_skills_to_db()` 自动灌入的。

即：**该测试隐式依赖 `skills` 表为空**，而 PR-25/26 期的 TRUNCATE 曾让它意外为空、掩盖了这个脆弱性。这不是 PR-27/28 代码引入的回归，是**测试隔离缺陷 + 环境状态耦合**。处置见 §Q6。

---

## §Q1 · 修复面 1（P0 阻塞）· `session_factory` 透传的收敛方式

**建议**：**A · `run_execute` 补 `session_factory` 形参 + `_background_execute` 全改关键字传参**

| 方案 | 内容 | 优点 | 缺点 |
|------|------|------|------|
| **A · 补形参 + 关键字传参** | `run_execute` 签名加 `session_factory: Any = None`；`agent.py:177` 传 `session_factory=async_session_factory`；`engine.py:522` 的 `_background_execute(...)` 调用**全部改关键字传参** | 与 `run_skip_to_score` 完全对称 · **关键字传参根治「加参数就错位」这类复发**（本次 bug 的形态就是位置传参截断） | 改动 3 处（签名 / 端点 / 调用） |
| B · 只补形参，保持位置传参 | 同 A 但 `_background_execute(task_id, plan, buffer, db_updater, execution_writer, session_factory)` | 改动最小 | **留着同一个雷** —— 下次在中间插参数会再错位一次，且同样静默 |
| C · `OrchestratorEngine.__init__` 持 `session_factory` | 构造时注入，`_background_execute` 从 `self` 取 | 所有调用点一次性受益 | 破坏现有 DI 形态（engine 目前不持 session 工厂，只持 `db_updater` 回调）· 与 `run_skip_to_score` 的显式传参风格分裂 · 测试 fixture 要全改 |

**议题**：A（我建议）/ B / C？

---

## §Q2 · 修复面 2（P0 阻塞）· `input_schema` 注入的**内容裁剪口径**

指挥官已锁定**注入全量 `input_schema` JSON**（token 贵但准）。本 Q 只议**注入哪个 schema**，因为事实 3 末尾的矛盾必须处理：**raw schema 会指示 LLM 去填 hydration 该补的字段。**

**建议**：**A · 注入全量 `input_schema` JSON + 对 hydration 登记的 tool 追加「由系统自动补齐，你不要填」的显式说明行**

| 方案 | 注入内容 | 优点 | 缺点 |
|------|---------|------|------|
| **A · 全量 schema + hydration 说明行** | 每个 tool 输出 `input_schema` 的完整 JSON；若 `tool_name in HYDRATION_RULES`，追加一行：`> 注意：parsed_content / existing_tags 由系统从数据库自动补齐，你只需提供 candidate_id（字符串，单个候选人 ID）` | 全量 schema 满足指挥官口径 · **显式消解矛盾**：LLM 既看到真实 schema 又知道该填什么 · hydration 的隐式约定被文档化进 prompt（顺手还债 §9.3 追债 3 的"魔法"问题） | 需在 hydration 侧维护「该 tool 由 LLM 提供什么键」的元数据（新增一个 `HYDRATION_HINTS: dict[str, str]` 常量，与 `HYDRATION_RULES` 同文件同 key，**不同步会漂移** —— 建议加单测断言两者 key 集合相等） |
| B · 全量 schema，不加说明行 | 只注入 raw `input_schema` | 实现最简 | **大概率使问题恶化**：LLM 会尝试编造 `parsed_content: {}` 塞进 tool_input。空 object **能过** jsonschema（`type: object` 无 required 子键）→ hydration 的 `{**tool_input, "parsed_content": ...}` 会覆盖它，侥幸无害；但 `candidate-merge` 那边 LLM 会编造 `resumes: [{resume_id, parsed_content: {}}]` —— 而 `hydration.py:65` 是 `item.get("parsed_content") or row.parsed_content or {}`，`{}` falsy 所以仍取 DB 值，**也侥幸无害**。全靠巧合成立，一旦 LLM 编出**非空**假 parsed_content 就静默用假数据推理 —— 比现在的硬失败更糟 |
| C · schema 经 hydration 感知裁剪后注入 | 对 hydration 登记的 tool，从注入的 schema 里**删掉** hydration 会补的字段、**加上** LLM 该给的字段（合成一份"面向 LLM 的 schema"） | LLM 看到的就是它该填的全集 · 无矛盾 | 违背指挥官"全量 input_schema"的口径 · 合成逻辑本身是新的可错点（要维护"删哪些加哪些"）· 排障时 prompt 里的 schema 与 skill.yaml 不一致，人会困惑 |

**议题**：A（我建议）/ B / C？
**附带议题 Q2.1**：`HYDRATION_HINTS` 与 `HYDRATION_RULES` 的 key 一致性，是否加单测断言 `HYDRATION_HINTS.keys() == HYDRATION_RULES.keys()`？（建议**加** —— 成本一行，防的是最典型的漂移）

---

## §Q3 · 修复面 3（P1）· hydration 是否兼容 `candidate_ids: [x]`

修复面 2 治本（让 LLM 输出正确键名），但 LLM 非确定性已有先例（HANDOFF §9.3.19）。本 Q 议是否加防御层。

**建议**：**A · 兼容单元素数组，多元素时抛错并指向 candidate-merge**

| 方案 | 行为 | 优点 | 缺点 |
|------|------|------|------|
| **A · 兼容单元素 + 多元素报错** | `cid = tool_input.get("candidate_id") or tool_input.get("resume_id")`；仍为空时试 `candidate_ids` / `resume_ids`：长度 1 取首个；长度 >1 抛 `ToolParamError("candidate-profile handles one candidate; got N — use candidate-merge for multiple")` | 与修复面 2 双保险 · 多元素时错误信息**自带下一步指引**（排障友好）· 单候选人画像是 §4.1 主路径，覆盖真实场景 | 容忍了 LLM 的键名错误，可能掩盖修复面 2 的退化 → **必须配 §Q5 的日志**，命中兼容分支时 `logger.warning` 留痕 |
| B · 不兼容，只做修复面 2 | 保持 hydration 严格 | 键名错误立刻暴露，不掩盖问题 | §4.1 复跑成败**完全押在 LLM 单次输出**上 · 一旦 LLM 抽风，MVP demo 现场就挂，且现场无法诊断 |
| C · 兼容任意长度（取首个） | 长度 >1 也静默取首个 | 最宽容 | **静默丢数据** —— 用户选 3 个候选人只画像 1 个且无任何提示，是比报错更坏的失败模式 |

**议题**：A（我建议）/ B / C？

---

## §Q4 · 修复面 4（P1 · 指挥官已锁定并入本 PR）· 终态判定与 writer 补列的**具体口径**

指挥官已锁定修复面 4 并入 PR-28。本 Q 只议两个实现口径。

### Q4.1 · 终态 status 的判定规则

**建议**：**A · 「无任何成功步」→ FAILED；「部分成功」→ COMPLETED + result 内标注**

| 方案 | 规则 | 优点 | 缺点 |
|------|------|------|------|
| **A · 全失败 FAILED · 部分成功 COMPLETED** | `if results and not any(r.success for r in results): status=FAILED, error={"code":"ALL_STEPS_FAILED","message": 首个失败步的 error_message}` · 否则 COMPLETED | 与"必需步失败即 `break`"的现有语义自洽（`act.py:153`：必需步失败后不会有后续成功步，所以"部分成功"只可能来自 optional 步失败）· 前端 `COMPLETED` 语义恢复可信 | 「部分成功」仍报 COMPLETED，前端需靠 `artifacts` 判断成色（现状如此，不退化） |
| B · 任一步失败即 FAILED | `if any(not r.success ...)`: FAILED | 最严格 | **误杀 optional 步** —— `optional: true` 的设计意图就是"失败不中断"（`act.py:136-144` emit WARNING 而非 ERROR），报 FAILED 直接违背该语义 |
| C · 引入 `PARTIAL_SUCCESS` 新状态 | 三态区分 | 语义最精确 | 需改 `TaskStatus` 枚举 + 状态机 `check_transition` + REST schema + 前端 `StreamStatusBar` 映射 —— **超 MVP scope**，且新状态值未经前端 PR-19 卡片设计考虑 |

**议题**：A（我建议）/ B / C？

### Q4.2 · `executions` 表补写 `input_params` / `error_message` 的落点

**建议**：**A · `input_params` 在 `action="start"` 写、`error_message` 在 `action="end"` 写；writer 签名加 `tool_input` 参数**

| 方案 | 落点 | 优点 | 缺点 |
|------|------|------|------|
| **A · start 写入参 · end 写错误** | `_make_db_execution_writer` 的 `writer(step_id, tool_name, action, result=None, tool_input=None)`；`act.py` 的 `on_step_start(step_id, tool_name)` 回调签名扩展为带 `tool_input` | 语义正确（入参在 start 时已知，错误在 end 时才知）· 排障时能看到"这一步实际收到什么"—— **本次事故正是因为缺这一列而误判** | 要改 `act.py` 的 `on_step_start` 回调签名（`StepCallbackFn` 类型别名）+ `engine.py:587` 的 `_on_start` 适配器，共 3 处 |
| B · 全在 `action="end"` 写 | end 时一并写 input_params + error_message，writer 签名只加 `tool_input` | 不动 `on_step_start` 签名 | 若任务在 step 执行中崩溃/超时，`end` 从不触发 → `input_params` 永远丢失，**恰恰是最需要排障的场景** |
| C · 本 PR 只补 `error_message` | 不动任何签名，`end` 分支加 `row.error_message = sr.error_message`（`result` 已带） | 改动最小（1 行） | `input_params` 仍为 NULL —— 本次事故的误判根源没修掉，下次还会重演 |

**议题**：A（我建议）/ B / C？

---

## §Q5 · 测试用例设计（TC-PR28-*）

**建议**：**A · 5 个新用例 + 1 个既有回归**

| TC | 名称 | 类型 | 覆盖修复面 | 断言要点 |
|----|------|------|-----------|---------|
| TC-PR28-1 | `/execute` 端点 db 透传 | 集成（mock dispatch 捕获 db） | 1 | `run_execute(session_factory=...)` → `run_act` 收到非 None `db` → `dispatch(db=<session>)`。**不 mock `run_act`**（防 PR-21 F1 的"mock 屏蔽 root cause"陷阱，见 HANDOFF §9.4.24） |
| TC-PR28-2 | `_format_dispatchable_tools` 含 input_schema | 单元 | 2 | 输出含 `parsed_content` / `existing_tags` / `keyword` / `jd_id` 等 required 字段名；hydration 登记的 tool 含 hint 行关键字（如 `candidate_id`） |
| TC-PR28-3 | `HYDRATION_HINTS` 与 `HYDRATION_RULES` key 一致 | 单元 | 2（Q2.1） | `set(HYDRATION_HINTS) == set(HYDRATION_RULES)` |
| TC-PR28-4 | hydration 兼容 `candidate_ids: [x]` + 多元素报错 | 单元（fake db） | 3 | 单元素 → 正常补齐；2 元素 → `ToolParamError` 且 message 含 `candidate-merge` |
| TC-PR28-5 | 全步失败 → task 写 FAILED | 集成 | 4（Q4.1） | `_background_execute` 后 `db_updater` 收到 `status=FAILED` + `error.code=ALL_STEPS_FAILED`；且 optional 步失败场景仍 COMPLETED（同一用例双断言或拆 5a/5b） |
| TC-PR28-6 | PR-17 路由回归 | **既有回归 · 不新增文件** | 2 | `tests/test_stage5_pr17_orchestrator_routing.py` 的 `_assert_dispatchable_injected` 仍绿（改 `_format_dispatchable_tools` 后不得破 PR-17 断言） |

**新增用例数 = 5**（TC-PR28-1..5；TC-PR28-6 是既有文件回归，**不计入新增**）。
预期 baseline：`145 + 5 = 150 passed`（**前提是 §Q6 的 `test_factories` 失败先解决**，否则是 `149 passed / 1 failed`）。

> ⚠️ 我在 PR-27 DECISION §三.4 犯过把回归项计入新增数的算术错（写 35 应为 34）。本次显式分离，执行体若实测与 150 不符**请报回不要自行改期望**。

**议题**：A（我建议）/ 增删某条？

---

## §Q6 · `test_factories` 失败（事实 5）的处置

**建议**：**A · 本 PR 顺手修（改测试隔离，不改 `main.py`）**

| 方案 | 内容 | 优点 | 缺点 |
|------|------|------|------|
| **A · 本 PR 修测试隔离** | `test_factories.py:22-29` 改为**幂等**：先 `delete(Skill).where(skill_id==...)` 或用 `session.merge()`，或改用一个**不与真实 skill 撞名**的 `skill_id`（如 `test-only-skill`）+ 相应改 `build_skill_execution_log` 的外键 | 门禁恢复干净 · 修的是真实的测试隔离缺陷 · 与 PR-28 主题（环境状态耦合导致的误判）气质一致 | 轻微扩大 PR 范围（+1 测试文件） |
| B · 拆独立 docs-free 小 PR | PR-28 只做 4 个修复面，另开 PR 修测试 | PR 边界最干净 | **PR-28 的门禁没法报"全绿"** —— 每次都要人工解释"这个 fail 不是我引入的"，正是这类噪声让本次事故被误判 |
| C · 不修，STEP6 报告注明已知失败 | 保持 144/1/2 | 零成本 | 门禁失去"绿/红"二值意义 · 下一个 PR 的执行体会继承这个模糊基线，**债务复利** |

**议题**：A（我建议）/ B / C？
**附带议题 Q6.1**：若选 A，是否同时在 HANDOFF §9.4 补一条陷阱「测试插 `skills` 表须与 `_sync_skills_to_db()` 灌入的 10 行错开」？（建议**补** —— 这个坑会随任何 `skills` 相关测试复发）

---

## §Q7 · commit split 与求助边界

**建议**：**A · 6 commit**

| # | 类型 | 内容 |
|---|------|------|
| 1 | `test` | red-test skeleton：TC-PR28-1..5（全 fail / xfail），含 §Q6 的 `test_factories` 隔离修复 |
| 2 | `fix` | 修复面 1：`run_execute` 补 `session_factory` + 端点传参 + `_background_execute` 全改关键字传参 |
| 3 | `feat` | 修复面 2：`_format_dispatchable_tools` 注入全量 `input_schema` + `HYDRATION_HINTS` |
| 4 | `fix` | 修复面 3：hydration 兼容 `candidate_ids` 单元素 + 多元素报错 + `logger.warning` 留痕 |
| 5 | `fix` | 修复面 4：终态 FAILED 判定 + `executions.input_params` / `error_message` 补写 |
| 6 | `docs` | STEP6 报告 + HANDOFF §9.3.22 + §9.4 陷阱（Q6.1）|

**求助边界（本 PR 增补 · 严格遵守）**：

1. **归因验证边界** —— 修复面 1 落地后**必须**复跑一次 §4.1（或等效的 curl e2e），确认事实 2 的推断（`db=None` → hydration 抛 `requires a db session`）成立。若实际错误是执行体报的 `'parsed_content' is a required property`，说明**还有第三条未知路径**绕过了 hydration，**停 · 报指挥官**，不要继续往下改。
2. **`input_schema` 注入后 token 膨胀边界** —— 若注入全量 schema 后 plan prompt 超出模型上限、或实测 LLM 输出质量**下降**（如开始编造 `parsed_content`），**停 · 报**，不要自行改成 Q2-C 的裁剪方案。
3. **`minItems: 2` 边界（继承 PR-26 §五 #4）** —— 若 §4.2 candidate-merge 因 `minItems: 2` 失败，**不得改 skill.yaml**，停 · 报。
4. **状态机边界** —— 修复面 4 若发现 `check_transition` 不允许 `EXECUTING → FAILED`，**停 · 报**，不要自行放宽状态机。
5. **测试数量边界** —— 实测 passed 数与 §Q5 预期（150）不符时**报回**，不要自行调整期望值。
6. **不得触碰**：`frontend/**`（本 PR 纯后端）· `alembic/versions/**`（零 schema 变更）· 任何 skill.yaml 的 `input_schema.required`。
7. **文档读法** —— 引用本 DECISION 的任何 import 路径 / 行号前，**先 grep 确认**，不要凭直觉复述（PR-26 曾因此误报 `skill_errors` 不存在）。

**议题**：A（我建议）/ 调整 commit 划分？

---

## §附 · 工作区清理（不属本 PR，勿提交）

`_verify/` · `backend/_diag_uat.py` · `backend/_seed_resume_uat.py` · `backend/_seed_resume2_uat.py` · `backend/backend.err` · `backend/mig1.txt` · `backend/scripts/` · `backend/test-full.txt` · `frontend/_pr27_dbg*.txt` · `frontend/_pr27_test.txt` · `graphify-out/` · `docs/planning/stage5/{C2-FIXTURE-DECISION,PR10-STEP5-*,PR10-STEP6-REPORT,PR11-STEP6-REPORT,PR15-STEP6-REPORT,PR23-STEP6-REPORT}.md`

两个种子脚本（`_seed_resume_uat.py` / `_seed_resume2_uat.py`）**保留** —— 修复后复跑 §4.1/§4.2 要用。

---

_撰写：sub-commander · 2026-07-27 · 待指挥官裁决 Q1–Q7（Q2 注入粒度、Q4 并入范围已锁定）_
