# PR-23 KICKOFF · REVISIONS（指挥官回复）

> 来源：`docs/planning/stage5/PR23-KICKOFF-QUESTIONS.md`（executor `d836cd4`）
> base：master `7198737`
> 状态：**已批复 · Q1 选 A（全量迁 28 列）· 全部 Q 采纳 · executor 起 DECISION**

---

## 〇 总评 · Grep 复核翻出 3 个 scope 关键点

1. **28 列 vs 指令 7 列** —— TimestampMixin 继承 9 张表带出 18 列，若不全迁，`utcnow_naive()` 收敛目标直接废掉。这是本 PR 最关键的 scope 决策，executor 早翻出免二次返工。
2. **测试连开发 DB**（conftest.py:41）—— pytest 门必须在 migration 门之后，否则 asyncpg 静默漂移（naive 值写 timestamptz 按会话时区解释）。
3. **agent.ts 200+ 行手写契约** —— 全量 codegen 会把手写契约（SSE 事件、PlanStep、TaskDetail 等）挪进 python 字符串，方案否决，选局部 marker 才对。

三点若未 grep 就动手，PR-23 会连收 3 个中期 blocker。KICKOFF 值回票价。

---

## §一 逐条 REVISIONS · Part A（TIMESTAMPTZ）

### Q1 · 全量 28 列 vs 指令 7 列 → **选 A · 全量迁 28 列**

**决定理由**（3 条，从技术必要性到工程一致性）：

1. **主目标 2 依赖主目标 1 全迁**：`utcnow_naive()` 收敛为单一 `utcnow_aware()` 需所有 datetime 列都 tz-aware，否则 mixin 列还得留 naive default → `time.py` 就必须留 `utcnow_naive`（或至少 `utcnow_naive_for_mixin`）→ 追债 6 只还半份。
2. **半迁的隐藏成本比全迁高**：TIMESTAMPTZ / TIMESTAMP WITHOUT TIME ZONE 在 SQLAlchemy 比较（`WHERE started_at > created_at`）时会因类型不一致触发 asyncpg 的隐式转换，长期是巨大的 debug 面。
3. **机械工作，风险不叠加**：mixin 只改 `base.py:8-9` 一处，additional migration lines 是纯字符串复制。executor 已实证 28 列在 8 个 model 文件内。

**动作：Q1 选 A · 全量 28 列迁移。** DECISION 里必须显式列 28 列清单，不许 executor 自主删减。

### Q2 · USING AT TIME ZONE 'UTC' 语义 → 通过

MVP 阶段数据全在 docker-compose UTC 容器产生，安全前提成立。**追加**：README 或 MVP-VERIFY-CHECKLIST 里加一行"生产化前若接管非 UTC 库需运维手册"作为已知边界。此追加**不在本 PR scope**——落地建议由 PR-22（MVP release 准备）附带做（我会通知 PR-22 executor 顺手加，或本 PR STEP6 尾部记建议）。

**动作：Q2 定稿。**

### Q3 · 直接删 utcnow_naive / _to_naive_utc → 通过

executor 补的技术论据（asyncpg 对 naive→timestamptz 静默按会话时区解释，产生静默时区漂移）**采纳作为直接删除的第二理由**——保留 deprecated 别名恰好制造静默通道，删除反而安全。

**动作：Q3 直接删。**

### Q4 · 11 文件替换清单 → 通过 + match.py 重点复核

清单确认。**match.py 的 4 处 `_to_naive_utc()` 快照比较**（`resume.updated_at > snapshot_naive` → `resume.updated_at > snapshot_aware`）是**本 PR 最需人眼复核的位置**——两侧同 aware 后语义不变，但执行体在 PR-23 STEP6 报告里必须**单列一节**核对 4 处替换前后的 `assert` / `if` 语义等价（贴改动前后代码 snippet + 断言"aware>aware = 语义与 naive>naive 一致"）。

**动作：Q4 定稿 · match.py 快照比较单列一节复核。**

### Q5 · 测试断言等价微调 → 通过

- 允许对 `isoformat()` 精确字符串比较的断言做等价微调（如 `assert x.endswith("Z")` → `assert x.endswith("+00:00")` 或用 `datetime.fromisoformat` 后比较对象）。
- STEP6 报告"断言变更清单"单列一节，列出所有微调项 + 微调理由（"tz-aware isoformat 后缀 +00:00 vs naive 无后缀"）。
- 微调数 ≤ 10 处属预期，> 10 触发求助边界 #3。

**动作：Q5 定稿。**

### Q6 · func.now() 不动 → 通过

`func.now()` 保持不变，仅列类型改 `DateTime(timezone=True)`。DB 时钟一致性优于应用时钟（多实例部署）。

**动作：Q6 定稿。**

### Q7 · 对称 downgrade → 通过

`ALTER COLUMN ... TYPE TIMESTAMP WITHOUT TIME ZONE USING xxx AT TIME ZONE 'UTC'` 对称回落。三门"迁移可逆"门包含 upgrade→downgrade→upgrade 三连（DECISION §7 已列，无需变更）。

**动作：Q7 定稿。**

---

## §二 逐条 REVISIONS · Part B（codegen 护栏）

### Q8 · codegen 规则 → 通过

`union = sorted(map.values()) + 'generic'`。`generic` 硬编码追加 + 脚本注释说明"generic 非 map value 而是 engine.py:158 fallback"。

`sorted()` 是关键——保证多次运行输出稳定（Python 3.7+ dict 保序，但依赖插入顺序不安全）。

**动作：Q8 定稿。**

### Q9 · CI/pre-commit 不引入、记追债 → 通过

本 PR 只交付：
1. `backend/scripts/gen_artifact_types.py` 脚本本体
2. 三门额外门 `git diff --exit-code` 幂等校验（人工/PR 阶段跑）
3. `README.md` 或 `AGENTS.md` 里"新增 skill 三步走"指引段

**HANDOFF 追债项新增** —— PR-23 STEP6 报告里明确列一条建议：
> **§9.3.14（PR-23 建议追债 · 未落地）** CI/pre-commit 引入时把 codegen 幂等校验编入 workflow：`uv run python backend/scripts/gen_artifact_types.py && git diff --exit-code`。当前仓库无 CI 基建，PR-23 只交付脚本本体，护栏靠人工/PR review 保证。

由指挥官（我）合并 PR-23 后统一落 HANDOFF §9.3.14。

**动作：Q9 定稿。**

### Q10 · agent.ts 局部 marker → 通过

marker 方案定案：

```ts
// <auto-gen-artifacttype-start> — DO NOT EDIT. Run: uv run python backend/scripts/gen_artifact_types.py
export type ArtifactType = 'candidate_merge' | 'candidate_profile' | 'generic' | 'jd' | 'match_score' | 'resume';
// <auto-gen-artifacttype-end>
```

脚本行为约束：
- 定位到两 marker 之间→替换其间内容→**无 marker 则报错退出**（防手滑删标记后静默追加）
- **文件其他内容零变动**（SSE 事件、PlanStep 等手写类型不动）
- 输出强制 `\n` 换行 + UTF-8 无 BOM（Q11）

前端 `dayjs()` / `new Date()` 解析 aware isoformat（带 `+00:00`）兼容 ISO8601，无需前端改。

**动作：Q10 定稿。**

### Q11 · stdlib + ast + 换行/编码 → 通过

- `ast.parse` engine.py 定位 `_ARTIFACT_TYPE_MAP` 赋值节点，提取 dict values（字符串字面量校验，非字符串则报错退出触发求助边界 #4）。
- `re` 定位 marker。
- 输出 `open(path, "w", encoding="utf-8", newline="\n")`。
- **不 import app 包**（避免脚本执行拉起 settings/DB 依赖）。
- 只 add `gen_artifact_types.py`，`backend/scripts/_cleanup_dev_db.py` 保持未跟踪（不入本 PR）。

**动作：Q11 定稿。**

---

## §三 综合决策

### Q12 · 同 PR + 6-commit 分段 → 通过

commit 序列采纳原文，**顺序调整一处**：Part B 先做（commit #1）有独立价值（先绿一个门），若 Part A 中途翻车（例如 Q1 迁移出意外），Part B 可单独 cherry-pick 出 PR。

**动作：Q12 定稿 · 6 commits。**

### Q13 · 门顺序（先 migration 后 pytest） → 通过

门顺序：
1. `uv run alembic upgrade head`（前置，非门本身）
2. `uv run pytest -q` → 131 passed / 1 skipped
3. `uv run ruff check .` → 0
4. `cd frontend && npm run build` → 通过
5. `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` → 三连通过
6. `uv run python backend/scripts/gen_artifact_types.py && git diff --exit-code frontend/src/types/agent.ts` → 幂等（无 diff）

STEP6 报告"断言变更清单"单列一节（Q5）。

**动作：Q13 定稿 · 6 门（前置 alembic upgrade + 5 门本体，第 5 是可逆门，第 6 是幂等门）。**

### Q14 · 求助边界 → 通过 + 补一条

executor 6 条全采纳。补：

7. **§9.4 未记的新陷阱** —— 迁移期间若遇到 `alembic` 或 `asyncpg` 报错涉及未记录在 HANDOFF §9.4 的行为（例如某种默认值/时区隐式转换崩溃），停下报告，不"顺手 workaround"绕过（PR-20/21 的 §9.4 陷阱都是这样漏出的）。

---

## §四 追加决策（Revisions 期发现）

### R1 · 迁移文件命名与内容规范

Alembic migration filename 建议：`{revision}_stage5_pr23_migrate_to_timestamptz.py`。migration 内单一 `upgrade()` / `downgrade()`，不拆多个 file。28 列在一个 revision 里 ALTER，事务原子。

### R2 · match.py 快照写路径同步

不只是读比较——`match_scores` 表的 `resume_updated_at_snapshot` / `jd_updated_at_snapshot` 写入路径（match.py 内某处 `snapshot = _to_naive_utc(resume.updated_at)` 之类）也要改成"直接赋 aware 值"（迁移后 `resume.updated_at` 本身已 aware，删除 `_to_naive_utc` 包裹即可）。executor 在 §四的 match.py 7 处已含此，DECISION 里显式点名一次。

### R3 · MVP 数据全 UTC 假设的运维手册补充

Q2 提及"生产化前若接管非 UTC 库需运维手册"——**由 PR-22 顺手加**（我会通知 PR-22 executor 在 README 或 MVP-VERIFY-CHECKLIST 尾部加一句"生产化时区注意"），PR-23 本身不做，避免 scope creep。

### R4 · 前端 agent.ts marker 与 ArtifactType 的历史命名对齐

executor §八列出前端 union 6 值 = `{match_score, jd, resume, candidate_merge, candidate_profile, generic}`。sorted 后为 `candidate_merge | candidate_profile | generic | jd | match_score | resume`——**与当前 agent.ts:71-77 顺序可能不一致**（当前手写顺序可能是"业务优先级"），本 PR 会因 sorted 改变顺序但**值集合零变动**，前端 TS type check 不受影响（union 无序集合）。STEP6 报告说明"顺序变更 · 集合等价"即可。

---

## §五 求助边界（DECISION 版本预定）

复用 QUESTIONS §十四 6 条 + Q14 补的 1 条 = 7 条 stop-and-ask，DECISION 阶段收纳完整清单。

---

## §六 时间预估

原估 3-5 天。因 grep 充分且 Q1 全迁决策已定，估 **3-4 天**：
- KICKOFF REVISIONS + DECISION：0.5 天（本轮）
- Part B（codegen 脚本 + agent.ts marker）：0.5 天
- Part A migration + models + time.py：1 天
- Part A 全仓替换 + tests 微调 + 三门：1-1.5 天
- STEP6 + FF：0.5 天

Track A（PR-22 · MVP release）与 B 并行推进，B 3-4 天不阻塞 A 的 1 天。

---

## §七 executor 下一步动作

1. 起 `docs/planning/stage5/PR23-KICKOFF-DECISION.md`（本次由我直接落，见下一提交）
2. DECISION 批准后拉分支 `feat/pr-23-s51-p2-timestamptz-codegen`
3. 严格 6-commit 分段（Part B → Part A → 收尾）
4. 三门 + STEP6（含"断言变更清单"+"match.py 快照比较复核"两个专章）→ 送我 FF-merge 复审

---

*commander 批复 · REVISIONS 完成 · executor 可起 DECISION*
