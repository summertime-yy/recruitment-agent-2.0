# PR-23 KICKOFF · 问题清单（QUESTIONS）

> 任务：Stage 5.1 P2 —— TIMESTAMPTZ 迁移（追债 6）+ Artifact codegen 护栏（追债 3）
> 状态：**草稿 · 待指挥官 revisions**（docs-only，本文件 commit 到 master）
> base：master @ `7198737`
> 分支（DECISION 后拉）：`feat/pr-23-s51-p2-timestamptz-codegen`
> 路径：KICKOFF（本文件）→ REVISIONS（指挥官回）→ DECISION（执行体 contract）

---

## 〇 摘要（先给结论）

grep 复核后，两个主目标均可行，但**影响面比指令列表大一圈**，需指挥官定 scope：

1. **TIMESTAMPTZ 影响列比指令清单多 13 列**：指令列了 7 列，实证 grep 出 **20 列**——
   `TimestampMixin.created_at/updated_at` 被 **9 张表**继承（2×9=18 列，但 skills 表被 Skill 类
   直接继承计 1 次），另有 `skill_versions.created_at/published_at`、`candidate_status_history.occurred_at`
   未在指令内。**全迁还是只迁指令 7 列**是本 PR 最大 scope 决策（Q1）。
2. **codegen 现状 1:1 已同步**：`_ARTIFACT_TYPE_MAP` 5 value + fallback `"generic"`（engine.py:158）
   恰好 = 前端 union 6 值（agent.ts:71-77）。本 PR 是"护栏"不是"修复"，无行为变化。
3. **测试连着开发库**：`conftest.py:41` 直接用 `settings.database_url`（复用运行中 PostgreSQL），
   迁移后**必须先 `alembic upgrade head` 再跑 pytest**，三门顺序有依赖（Q13）。

---

## Part A · TIMESTAMPTZ 迁移（追债 6）

### §一 影响列实证全清单（Q1）

`grep Mapped[datetime] backend/app/models/`（全部 `DateTime` 无 `timezone=True`，零例外）：

**指令已列（7 列）**：

| 表.列 | 位置 |
|-------|------|
| `skill_execution_logs.executed_at` | skill.py:62 |
| `tasks.started_at` / `finished_at` | task.py:42/45 |
| `executions.started_at` / `finished_at` | execution.py:46/47 |
| `match_scores.resume_updated_at_snapshot` / `jd_updated_at_snapshot` | match_score.py:44/47 |

**指令未列、grep 新增（13 列）**：

| 表.列 | 位置 |
|-------|------|
| `TimestampMixin.created_at` / `updated_at` | base.py:8/9 —— 继承表 ×9：`tasks`、`skills`、`resumes`、`match_scores`、`jd_templates`、`jds`、`executions`、`candidate_status_history`、`candidate_notes` |
| `skill_versions.created_at` / `published_at` | skill.py:42/43（SkillVersion 未继承 mixin，自带两列） |
| `candidate_status_history.occurred_at` | candidate.py:115 |

即 DB 侧共 **9×2（mixin）+ 2（skill_versions）+ 1（occurred_at）+ 7（指令列）= 28 列**（`skills` 表仅 mixin 两列）。

**问 Q1（最大 scope 决策）**：
- **(A) 全量迁 28 列**（倾向）：半迁会造成"同一 ORM 会话里 aware 与 naive datetime 并存"，
  `_to_naive_utc()` 删不掉、`utcnow_naive()` 收敛不彻底，追债 6 等于只还一半；且 mixin 只改一处
  `base.py`，migration 多写几列 ALTER 是机械工作，风险不叠加。
- (B) 只迁指令 7 列：diff 小，但 `time.py` 无法收敛单一函数（mixin 列仍需 naive default），
  与主目标 2 的"收敛为 `utcnow_aware()`"直接冲突。**若选 B，主目标 1 的第 2 条（删 utcnow_naive）必须放弃。**

### §二 USING AT TIME ZONE 'UTC' 语义核对（Q2）

- 写路径复核：所有落库 datetime 均出自 `utcnow_naive()`（`datetime.now(UTC).replace(tzinfo=None)`，
  time.py:34）或 `func.now()` 默认值（base.py / skill.py / candidate.py）。
- `func.now()` 值取决于 **PG 会话时区**：docker-compose 的 postgres 未显式设 `TZ`/`timezone` 参数，
  容器默认 `Etc/UTC` → `now()` 产 UTC。**但这是环境假设而非代码保证**——若有人在非 UTC 的自建 PG 上跑过，
  历史 `created_at` 就不是 UTC。
- MVP 阶段数据均产生于本仓 docker-compose 环境，`USING ... AT TIME ZONE 'UTC'` 语义安全。

**问 Q2**：接受"MVP 数据全 UTC"假设、统一 `USING xxx AT TIME ZONE 'UTC'`？（生产化前若有存量非 UTC 库，
需运维手册注明，不在本 PR。）

### §三 utcnow_naive() 直接删 vs deprecation（Q3）

同意指挥官倾向：**直接删**（fail-fast）。补充一个技术论据：迁移到 TIMESTAMPTZ 后，若残留代码写
naive datetime，asyncpg **不报错**——PG 会按会话时区解释 naive 值，产生**静默时区漂移**（比崩溃更难查）。
保留 deprecated 别名恰好制造这种静默通道，删除反而安全。`_to_naive_utc()` 同理删除
（迁移后所有读出值都 aware，比较不再混合）。

**问 Q3**：确认直接删 `utcnow_naive()` + `_to_naive_utc()`，不留别名？

### §四 全仓替换点清单（Q4）

`grep utcnow_naive|_to_naive_utc backend/`（计数含 import 行与 time.py 定义本体）：

| 文件 | 命中 | 替换后期望行为 |
|------|------|---------------|
| `app/core/time.py` | 5（定义+docstring） | 删两函数，仅剩 `utcnow_aware()`；docstring 重写 |
| `app/agent/orchestrator/engine.py` | 9 | 全部 → `utcnow_aware()`；SSE payload 序列化会从 `...` 变 `...+00:00`（**前端展示影响见 Q10 旁注**） |
| `app/services/match.py` | 7 | `utcnow_naive`→aware；**4 处 `_to_naive_utc()` 是快照比较**（stale 判定），删除后改为直接 aware 比较——读出值已 aware，无 TypeError 风险 |
| `app/services/jd.py` | 5 | → `utcnow_aware()` |
| `app/services/resume.py` | 5 | → `utcnow_aware()` |
| `app/services/candidate.py` | 4 | → `utcnow_aware()` |
| `app/main.py` | 4 | → `utcnow_aware()` |
| `app/api/v1/agent.py` | 4 | → `utcnow_aware()` |
| `tests/factories.py` | 2 | → `utcnow_aware()`（工厂造的 JD/Resume `updated_at`） |
| `tests/api/test_agent_endpoints.py` | 6 | → `utcnow_aware()`；断言若比较 datetime 需核对 |
| `tests/test_stage5_pr20_executions.py` | 2 | → `utcnow_aware()` |

**问 Q4**：清单确认？match.py 的 stale 快照比较（`resume.updated_at > snapshot`）在迁移后两侧均 aware，
语义不变——此为本替换最需人眼复核的位置，DECISION 请显式圈出。

### §五 测试 baseline 波动评估（Q5）

- 测试 DB = 开发 PG（conftest.py:41 `settings.database_url`）→ **迁移后才能跑测试**，naive 值将写不进
  timestamptz？不——asyncpg 对 timestamptz 列**接受** naive（按会话时区解释），风险是静默漂移不是报错，
  所以测试里残留 naive 写入不会 fail，**必须靠 §四 全量替换 + code review 兜住**。
- fakeredis：SSE 事件里 datetime 均已 `isoformat()` 字符串化后进 Redis，aware 只是多 `+00:00` 后缀，
  fakeredis 无感。**但若有测试断言 isoformat 字符串精确值/长度，会挂**——DECISION 前我会在动工分支跑
  full pytest 实测，STEP6 报告如实列出需微调的断言。
- 预期 baseline：131 passed / 1 skipped 不变（允许对断言做等价性微调并在 STEP6 说明）。

**问 Q5**：接受"动工后实测、断言等价微调、STEP6 显式列出"的口径？

### §六 TimestampMixin 默认值（Q6）

`base.py:8-9` 现为 `default=func.now()`（客户端发 SQL `now()`）。迁 TIMESTAMPTZ 后 `now()` 返回
timestamptz，**默认值无需改动即正确**。可选增强：`default` 改为 python 侧 `utcnow_aware`，统一"所有
时间戳出自 time.py"。倾向**不改**（`func.now()` 用 DB 时钟，多实例部署下比应用时钟更一致，且改动零收益）。

**问 Q6**：确认 `func.now()` 保持不变，仅 `DateTime` → `DateTime(timezone=True)`？

### §七 downgrade 支持（Q7）

必需（Alembic best practice + 三门里的可逆门）。downgrade 用对称 SQL：
`ALTER COLUMN ... TYPE TIMESTAMP WITHOUT TIME ZONE USING xxx AT TIME ZONE 'UTC'`
（aware→naive 剥离回 UTC 墙钟值，与 upgrade 严格互逆，无信息损失）。

**问 Q7**：确认对称 downgrade？

---

## Part B · Artifact codegen 护栏（追债 3）

### §八 map ↔ union 映射实证（Q8）

- 后端（engine.py:123-129）：`_ARTIFACT_TYPE_MAP` 5 条 —— value 集合
  `{match_score, jd, resume, candidate_merge, candidate_profile}`；engine.py:158 fallback `"generic"`。
- 前端（agent.ts:71-77）：`ArtifactType` union 恰好 = 上述 5 值 + `'generic'`，**当前 1:1 同步**。
- codegen 规则：**union = sorted(map.values()) + `'generic'`**——`generic` 不在 map 里（是 `.get` fallback），
  脚本必须硬编码追加，此点写进脚本注释。

**问 Q8**：映射规则（map values + 恒有 generic）确认？

### §九 codegen 触发时机（Q9）

同意指挥官倾向：**手动 + CI 校验**。但实证约束：本仓**当前无 CI workflow、无 Makefile、无 pre-commit 配置、
`pyproject.toml` 无 `[project.scripts]`**。落地拆两级：
- 本 PR 交付：脚本本体 + **幂等校验门**（三门额外门已含 `git diff --exit-code`）+ README"新增 skill 三步走"。
- CI 校验：仓库尚无 CI 基建，**建 CI 属新 scope**——建议记 HANDOFF 追债（"CI 引入时把 codegen 校验编入"），
  本 PR 不建 CI。pre-commit 同理不引入（新工具链依赖）。

**问 Q9**：接受"本 PR 只交付脚本 + 手动幂等门 + README 指引，CI/pre-commit 记追债"？

### §十 agent.ts 全量生成 vs 局部段落（Q10）

同意指挥官倾向：**只生成局部段落**。实证支撑：`agent.ts` 是 200+ 行的手写契约文件
（SSE 事件、PlanStep、TaskDetail 等十余个类型），全量生成等于把手写契约挪进 python 字符串，否决。
方案：用 marker 包裹 L71-77 段落：

```ts
// <auto-gen-artifacttype-start> — DO NOT EDIT. Run: uv run python scripts/gen_artifact_types.py
export type ArtifactType = ...
// <auto-gen-artifacttype-end>
```

脚本逻辑：读 agent.ts → 定位两 marker → 替换其间内容 → 无 marker 则报错退出（防手滑删标记后静默追加）。
文件顶部不再加全文件 AUTO-GENERATED 注释（与"局部生成"口径一致，改为 marker 行内注明）。

**问 Q10**：局部 marker 方案 + 顶部注释改 marker 行内注明，确认？
（旁注：Part A 会让 SSE 时间戳多 `+00:00` 后缀，前端 `dayjs()` 解析兼容 ISO8601 带时区，无需改前端。）

### §十一 脚本实现方式（Q11）

同意指挥官倾向：**纯 stdlib**（`ast` 解析 engine.py 提取 `_ARTIFACT_TYPE_MAP` 字面量 + `re` 定位 marker），
不 import app 包（避免脚本执行需拉起 settings/DB 依赖链）。运行入口 `uv run python scripts/gen_artifact_types.py`
（cwd=backend）。两个 Windows 兼容点写进脚本：输出强制 `\n` 换行 + UTF-8 无 BOM——否则幂等门
`git diff --exit-code` 会因 CRLF 假红。

另：`backend/scripts/` 目前是**未跟踪目录**（内有本地工具 `_cleanup_dev_db.py`）。本 PR 只 add
`gen_artifact_types.py`，`_cleanup_dev_db.py` 保持未跟踪（是否入库另议）。

**问 Q11**：stdlib + ast 方案、`\n`+UTF-8 输出、只 add 新脚本，确认？

---

## §十二 双主目标同 PR vs 拆分（Q12）

同意同 PR：两者零文件交集（A 碰 models/alembic/time.py/services，B 碰 scripts/agent.ts），
都是 P2 工程质量项，一次 FF 省事。commit 序列上**严格分段**（拟 6 commits）：

1. Part B：codegen 脚本 + agent.ts 加 marker（幂等门先绿，独立可回退）
2. Part A：migration（upgrade/downgrade 对称）
3. Part A：models `DateTime(timezone=True)` 全量 + `time.py` 收敛
4. Part A：app 层 `utcnow_naive` → `utcnow_aware` 全替换
5. Part A：tests 替换 + 断言微调
6. README"新增 skill 三步走" + 收尾

若指挥官改判拆 PR，天然以 commit 1 为界拆开即可。

**问 Q12**：同 PR + 6-commit 分段确认？

---

## §十三 三门 + 额外门（Q13）

| 门 | 期望 | 备注 |
|----|------|------|
| pytest | `uv run pytest -q` → 131 passed / 1 skipped | **前置**：先 `alembic upgrade head`（测试连开发库，§五） |
| ruff | `uv run ruff check .` → 0 | |
| build | `cd frontend && npm run build` 通过 | agent.ts 加 marker 后 TS 必须过 |
| 迁移可逆 | `upgrade head && downgrade -1 && upgrade head` 三连通过 | |
| codegen 幂等 | `uv run python scripts/gen_artifact_types.py && git diff --exit-code frontend/src/types/agent.ts` | Windows CRLF 陷阱见 §十一 |

**问 Q13**：门顺序（migration 门 → pytest 门）与上表确认？测试断言若因 tz 微调，STEP6 报告"断言变更清单"单列一节。

---

## §十四 求助边界建议（Q14）

触发以下任一即停下报告、不擅自实现：

1. Q1 若指挥官选 (B) 部分迁移，但实施中发现 naive/aware 混存导致 `_to_naive_utc` 删不掉——停，回报矛盾。
2. `alembic downgrade -1` 失败或 upgrade↔downgrade 不对称（数据损失迹象）——停。
3. full pytest 出现 **>5 个**测试因 tz 改动失败（预估应为个位数断言微调；超阈值说明影响面判断错误）——停。
4. `ast` 解析 `_ARTIFACT_TYPE_MAP` 时发现 map 不是纯字符串字面量（如出现变量/表达式 value）——停，codegen 前提破裂。
5. agent.ts 中 marker 段落之外出现与 ArtifactType 耦合的手写类型需要连带改动（超出"局部生成"承诺）——停。
6. commit 数超 8（6 计划 + 2 缓冲）——停，报告 scope 失控。

---

## §十五 待指挥官 REVISIONS 回答速览

- Q1：**28 列全量迁 (A) 还是指令 7 列 (B)？**（核心，B 会废掉 time.py 收敛目标）
- Q2：`USING AT TIME ZONE 'UTC'` + "MVP 数据全 UTC" 假设接受？
- Q3：`utcnow_naive` / `_to_naive_utc` 直接删不留别名？
- Q4：11 文件替换清单 + match.py 快照比较为重点复核位？
- Q5：测试断言"等价微调 + STEP6 列清单"口径？
- Q6：`func.now()` 默认值不动，仅加 `timezone=True`？
- Q7：对称 downgrade？
- Q8：codegen 规则 = map values + 恒有 `generic`？
- Q9：CI/pre-commit 不引入、记追债？
- Q10：agent.ts 局部 marker 生成？
- Q11：stdlib+ast、`\n`+UTF-8、只 add 新脚本？
- Q12：同 PR + 6-commit 分段？
- Q13：门顺序（先 migration 后 pytest）？
- Q14：求助边界 6 条确认/增删？

---

*起草人：agent · 复核 base `7198737` · 状态：待 commander REVISIONS*
