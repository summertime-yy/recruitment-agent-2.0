# MVP-VERIFY 终验报告（部分执行 · 方案2 合理子集）

> 接手：MVP-VERIFY-EXECUTOR-HANDOFF Step 4b。日期：2026-07-29。
> 决策：指挥官决策**不修 P0**，走方案2 合理子集（§7 skip-to-score 绕开 reason + §8 + §9），§4–§6 不触发，登记 B5 挂账。
> 结构依据：HANDOFF Step 9「Report 骨架」（即指挥官反馈 §2）。

## §一 执行总览

- **环境**：backend `:8000`（uvicorn reload）/ frontend `:5173`（vite）均 HTTP 200；docker `postgres`（healthy）、`redis`（healthy）正常；`minio` 容器 unhealthy 但 9000/9001 端口可达。
- **起止任务**：MVP-VERIFY；本次只执行 §7/§8/§9，§4–§6 不触发（P0 挂账）。
- **通过节**：§1 环境 / §2 JD 生成 / §3 简历上传解析 / §7 skip-to-score / §8 match_scores / §9 CancelTask。
- **挂账节**：§4 candidate-profile·candidate-merge·jd-candidate-matching / §5 PlanCard / §6 SSE 全事件（均阻塞于 **B5 P0**）。
- **新增 Bug**：B5（P0，建议 PR-24 修复）。B3 现确认是 B5 同源症状。

## §二 逐节结论

- **§1 环境**：通过。三服务起服正常，PG/Redis 健康，MinIO 端口可达。
- **§2 JD 生成**：通过（前置 Step 4b 已完成，本次仅复核）。`jd_id=jd_c656a7865269`，status=DRAFT，timestamptz 字段生效。走 `/jds/generate` 表单（因 B3/B5 不走 `/chat`）。
- **§3 简历上传解析**：通过（前置）。3 份全部 PARSED：`res_90bbdc5bd678`（张三 v1）、`res_c765f4b16a0b`（张三 v2）、`res_ad1327ab12fb`（李四）；候选人识别正确。
- **§4 candidate-profile / candidate-merge / jd-candidate-matching**：**未触发**（P0 挂账）。原计划经 `/chat`、`/candidate-chat` 触发，因 B5 全部卡 `WAITING_CONFIRMATION`；按决策不触发，原 §4 卡住任务作为 §9 活体样本取消。
- **§5 PlanCard 确认**：未触发（依赖 §4 产出 plan）。
- **§6 SSE 全事件类型覆盖**：未完整覆盖（依赖 §4/§5 正常终态）。
- **§7 skip-to-score**：通过。`POST /api/v1/agent/skip-to-score`，body `{"jd_id":"jd_c656a7865269","candidate_ids":["res_ad1327ab12fb"]}` → `task_c7e0373da5e6` → **COMPLETED**，绕开 B5。⚠️ 注意事项：指挥官指令写 `resume_ids`，实际 schema 字段为 `candidate_ids`（`_build_skip_plan` 内部当作 `resume_id` 传入 `match_score`），已按真实字段执行。
- **§8 match_scores 校验**：通过。产物 `ms_f31429598e24`，`res_ad1327ab12fb`（李四）整体 **42** 分 —— `skill_match` 30 / `experience_match` 30 / `education_match` 90，`overall_reasoning="技能与经验均未达到 JD 要求，核心技能缺失且经验不足，暂不建议进入面试。"`，status=COMPLETED，真实 LLM 评分落库。
- **§9 CancelTask**：通过。4 个卡在 `WAITING_CONFIRMATION` 的 §4 活体样本全部 **CANCELLED** → `task_60f7fb5d44fc` / `task_0fdb87699b13` / `task_58b3d5626220` / `task_0802f5809a99`。

## §三 SSE 事件类型覆盖表

8 类：`thinking` / `plan` / `tool_call` / `tool_result` / `progress` / `result` / `system` / `error`

| 事件类型 | 本次命中 | 说明 |
|----------|----------|------|
| thinking | ✗ | R-P-R 链路受阻未产生 |
| plan | ✗ | §4 未触发，无 plan 事件 |
| tool_call | ✓ | §7 skip-to-score 产出 `match_score` tool_call |
| tool_result | ✗ | skip 路径用 `result` 携带（无独立 tool_result） |
| progress | ✓ | `step_score_0` percent=100 |
| result | ✓ | match_score 结果（含 42 分明细） |
| system | ✗ | 取消仅 DB 终态可见，未走 SSE system:cancelled（叠加 B4） |
| error | ✗ | 未触发 |

- **观察**：`GET /api/v1/agent/tasks/{id}` 返回 **500**（疑似 `TaskStatus.plan` 校验时存储的 plan 缺 `task_id` 字段导致响应序列化失败）；§8 详情经 DB 直查已取得，不影响结论。该 500 未列入新 Bug（保持 Bug 表 B1–B5 范围），建议后续单独排查。

## §四 Bug 表

| # | 级别 | 节 | 现象 | 根因 | 处置 | Step |
|---|------|-----|------|------|------|------|
| **B1** | P1 | §3/§9 | CHECKLIST 提到 `candidates` 表，实际不存在 | 候选人概念嵌入 `resumes.candidate_name` + `duplicate_of_resume_id` 合并；独立表未建 | 登记 · 回写 CHECKLIST | Step 2 |
| **B2** | P2 | §6 | CHECKLIST "terminal 事件"表述含糊 | 实际 = `_is_terminal()` 三种：result/error/system:cancelled | 登记 · 回写 CHECKLIST | Step 3.5 |
| **B3** | P1 | §2 | `/chat` 输入生成 JD → `WAITING_CONFIRMATION` + blocking_reason="未提供reason_output"，前端 SSE (canceled) | **（更新）症状实际由 B5 引起**：reason 不读用户输入，非值域问题；`jd-generation` skill.yaml 无 `task_type` 字段亦为表象 | 登记 · 换 `/jds/generate` 表单继续验收；根因归 B5 | Step 4a |
| **B4** | P1 | §6 SSE | reflect 判 `is_feasible=false` 后，`_background_reason_plan` 直接 return，SSE 无 terminal 事件，前端 stream 挂到超时被浏览器 canceled | `engine.py:379-388` 分支缺 `await emit(SSEEventType.ERROR)` / `SYSTEM` 收尾 | 登记 · 新陷阱 · 追加 HANDOFF §9.4 | Step 4a |
| **B5** | **P0** | §4/§5/§6 | 见下「B5 详述」 | orchestrator 5 个 internal skill 的 user prompt 未渲染（无 `---USER_TEMPLATE---` 段、无 `{{ }}` 变量） | 登记 · 挂账 · 建议 PR-24 修复 | 本次 |

### B5 详述（照抄指挥官反馈 §3 · 权威文本）

### B5 · Orchestrator 5 个 internal skill user prompt 未渲染

**严重级**：P0（阻塞 MVP orchestrator 自然语言主链路）

**归属节**：§4 candidate-profile/candidate-merge/jd-candidate-matching 全部；§5 PlanCard
确认（依赖 §4 产出 plan）；§6 SSE 全事件类型覆盖（依赖 §4/§5 有正常终态）

**现象**：
1. 所有走 `/chat`（ChatCenter · CandidateChat）触发的 chat 任务均卡在
`WAITING_CONFIRMATION`，`error.blocking_reason` 恒为「未提供 reason_output / 缺少输入」类文案。
2. `orchestrator-reason` 步骤幻觉输出实体（如从空输入臆造
`jd_id="jd_1"`、`task_type="match"`），命中 `examples.yaml` few-shot 示例值。
3. `orchestrator-reason` 不消费前端 `context.candidate_ids` /
`context.jd_id`（即使前端明确传入非空数组，reason 输出 `parsed_entities.candidate_ids=[]`）。
4. 前端 SSE stream 表现为 `(canceled)`，浏览器等 terminal 事件超时被 cancel（叠加
B4：`is_feasible=false` 分支未 emit terminal 事件）。

**根因链**（三段确认）：

- `backend/app/agent/base_skill.py:107-114`：从 `prompt.md` 用 `---USER_TEMPLATE---` 分隔符切成
`[system_prompt, user_prompt_template]`。
  - 若 prompt.md 无该分隔符，`_user_prompt_template` 默认 `""`（空字符串）。
- `backend/app/agent/skills/orchestrator_{reason,reflect,plan,reflect_plan,reflect_act}/v1_0_0/prompt.md`：
  - 5 个 orchestrator internal skill 均 **无 `---USER_TEMPLATE---` 段、无 `{{ }}` Jinja
  变量**（grep 实测 `USER_TEMPLATE=0 · Jinja=0`）。
  - 对比：5 个业务 skill（candidate_merge/candidate_profile/jd_candidate_matching/jd_generation/resume_parsing）prompt.md 均含 USER_TEMPLATE 段和 Jinja 变量。
- `base_skill.py:243-246 execute()`：
  - `user_prompt = self.render_user_prompt(input_params)` → `Jinja Template("").render(**dict)` → `""`。
  - `call_llm_json(system_prompt, "")` → LLM 只见 system prompt · 无 user message · 无 context ·
  无 user_input。
  - LLM 靠 system prompt + few-shot examples 幻觉输出 JSON，命中 examples.yaml
  中的示例实体值（`jd_1` / `c_1`）。

**结论**：orchestrator R-P-R 中枢链路（PR-14 引以为傲的核心设计）**全线跑空**，reason
从未真正读到用户输入。此前 B3 观察到的"reason 值域不含 JD 生成意图"是**果不是因**——真因是 reason
根本没看到用户消息，输出全靠幻觉，恰好落在 examples 值域内。

**证据 grep**（可复现）：
```bash
cd backend
for f in app/agent/skills/*/v1_0_0/prompt.md; do
  echo "$f · USER_TEMPLATE=$(grep -c USER_TEMPLATE "$f") · Jinja={{=$(grep -c '{{' "$f")"
done
# 期望输出中 5 个 orchestrator_* 全部 USER_TEMPLATE=0 · Jinja=0
# 5 个业务 skill 全部 USER_TEMPLATE=1 · Jinja≥2
```

修复建议（供 PR-24 起草人参考 · 不作本 PR 承诺）：

1. 数据修（必须 · 5 个 prompt.md）：给 5 个 orchestrator internal skill 的 prompt.md 追加
`---USER_TEMPLATE---` 段。以 orchestrator-reason 为例，模板应包含全部 input_schema 声明变量：
```
---USER_TEMPLATE---
## 用户消息
{{ user_input }}

## 上下文
{{ context | tojson }}
```
2. 代码修（强烈建议 · 1 处）：base_skill.py `_load_from_yaml()` 中，若 `_user_prompt_template` 为空且
skill 的 `input_schema.required` 非空 → 启动即 fail-fast raise ValueError（"Skill {skill_id} has
non-empty input_schema.required but no USER_TEMPLATE in prompt.md"）。防止未来新 skill 重犯。
3. 测试（必须 · 1 文件）：
   - 单元测试 `test_prompt_template_covers_input_schema`：对每个 skill 校验 `_user_prompt_template != ""`
   且 `input_schema.required` 中每个字段都以 `{{ field }}` 或 `{{ field ... }}` 形式出现在模板中。
   - 集成测试：mock LLM，断言 `render_user_prompt({"user_input": "帮我找候选人 c_123", "context":
   {"jd_id": "jd_abc"}})` 输出包含 `c_123` 和 `jd_abc`。

优先级判定：
- 阻塞面：orchestrator 自然语言主链（/chat + /candidate-chat 全部业务 skill）
- MVP 依赖：demo 无此链不可用
- 修复面：纯 prompt + 1 处代码 fail-fast + 单元测试；零 schema 变更、零 migration、无新依赖
- 建议：独立 PR-24 · 名字建议 `feat/pr-24-fix-orchestrator-prompt-templates`（虽以 fix
语义为主，但结构上是 5 文件新增段落 + 1 代码 + 测试，走完整 PR 流程 · 非 hotfix）

关联登记项：
- 本 report §Bug 表 B3（reason 值域）· 归为同源根因，B3 描述可更新为「B3 症状实际由 B5 引起」。
- 本 report §Bug 表 B4（SSE terminal 缺失）· 独立根因（engine.py:379-388 分支缺 emit），与 B5
无关联。
- HANDOFF §9.4 · 建议新增陷阱条目「orchestrator internal skill 若 prompt.md 无 USER_TEMPLATE
段，LLM 只见 system prompt，输出完全依赖 few-shot 幻觉，静默产出示例值而非真实推理结果」。

发现时机：MVP 手工验收 Step 4（新 agent 触发 chat 时 reflect 恒判 not feasible → 复核
base_skill.py 加载逻辑 + 5 skill prompt.md 后确认根因）。

## §五 CHECKLIST 文档漂移回写

- **B1**：建议删 CHECKLIST §3/§9 中 `candidates` 表引用，统一为 `resumes.candidate_name` + `duplicate_of_resume_id` 合并模型。
- **B2**：CHECKLIST §6 terminal 事件表述 clarify 为 `_is_terminal()` 三态：result / error / system:cancelled。
- **B3（更新）**：原「reason 值域不含 JD 生成意图」改为「B3 症状实际由 B5 引起」——`/chat` JD 生成卡 `WAITING_CONFIRMATION` 的真因是 B5（prompt 未渲染，reason 不读输入）。临时规避仍走 `/jds/generate` 表单。
- **B4**：SSE terminal 缺失为独立根因（engine.py:379-388 分支缺 emit），建议追加 HANDOFF §9.4 陷阱条目。
- **新增（B5 关联）**：HANDOFF §9.4 建议新增陷阱「orchestrator internal skill prompt.md 无 `---USER_TEMPLATE---` 段 → LLM 只见 system prompt，输出全靠 few-shot 幻觉，静默产出示例值」（见 §9.3.16）。

## §附1 复现命令

```bash
# §7 skip-to-score（字段名 candidate_ids，非 resume_ids）
curl.exe --globoff -X POST http://localhost:8000/api/v1/agent/skip-to-score \
  -H "Content-Type: application/json" \
  -d '{"jd_id":"jd_c656a7865269","candidate_ids":["res_ad1327ab12fb"]}'
# → task_c7e0373da5e6 · COMPLETED

# §8 match_scores（DB 直查，绕过 GET /tasks 500）
docker exec $(docker compose ps -q postgres) psql -U recruitment -d recruitment_agent \
  -c "SELECT score_id, jd_id, resume_id, overall_score, status FROM match_scores WHERE score_id='ms_f31429598e24';"

# §9 CancelTask（4 个 WAITING_CONFIRMATION 活体样本）
for t in task_60f7fb5d44fc task_0fdb87699b13 task_58b3d5626220 task_0802f5809a99; do
  curl.exe --globoff -X POST http://localhost:8000/api/v1/agent/tasks/$t/cancel
done
```

## §附2 数据落库证据

| 对象 | 值 |
|------|-----|
| jd_id | `jd_c656a7865269`（status=DRAFT，TIMESTAMPTZ 生效） |
| resume_id | `res_90bbdc5bd678`（张三 v1）· `res_c765f4b16a0b`（张三 v2）· `res_ad1327ab12fb`（李四），均 PARSED |
| skip 任务 | `task_c7e0373da5e6`（COMPLETED，plan step_score_0 → match_score） |
| match_score | `ms_f31429598e24`，resume=res_ad1327ab12fb，overall=42，status=COMPLETED |
| 取消任务 | `task_60f7fb5d44fc` / `task_0fdb87699b13` / `task_58b3d5626220` / `task_0802f5809a99`（均 → CANCELLED） |

## §附3 未覆盖项

- §4–§6 因 B5 P0 未触发（指挥官决策：不修 P0，走方案2）。
- SSE 事件 `thinking` / `plan` / `tool_result` / `system` / `error` 未覆盖（依赖 R-P-R 正常终态）。
- `GET /api/v1/agent/tasks/{id}` 返回 500，未列入新 Bug，建议后续单独排查（疑似 plan 缺 `task_id` 字段致响应序列化失败）。

## §附4 建议下一步

1. **PR-24 修 B5**（独立 · 建议分支 `feat/pr-24-fix-orchestrator-prompt-templates`）：5 个 orchestrator internal skill 的 prompt.md 补 `---USER_TEMPLATE---` 段 + base_skill.py fail-fast + 单元测试/集成测试，零 schema/migration 变更。
2. **B4 独立修**：engine.py:379-388 `is_feasible=false` 分支补 emit terminal 事件。
3. **B3 复盘**：B5 修复后 `/chat` JD 生成路径是否仍需走 `/jds/generate` 表单，重新评估。
4. 起 **PR-24 KICKOFF-QUESTIONS**（用户后续接手）。
