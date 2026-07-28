# PR-23 KICKOFF · DECISION（执行体 Contract）

> 来源：`PR23-KICKOFF-QUESTIONS.md`（executor `d836cd4`）+ `PR23-KICKOFF-REVISIONS.md`（commander）
> base：master `7198737`
> 状态：**contract · 批准后起 `feat/pr-23-s51-p2-timestamptz-codegen`**
> 决策核心：**Q1 选 A · 全量迁 28 列 · time.py 收敛为单一 `utcnow_aware()`**
> 交付面：Stage 5.1 P2 双主目标（追债 6 + 追债 3）

---

## §一 交付面 · 双主目标

| 目标 | 类型 | 内容 | 追债编号 |
|------|------|------|---------|
| 主目标 1 | DB 类型工程质量 | 全量迁 28 列到 `TIMESTAMP WITH TIME ZONE` + `time.py` 收敛为单一 `utcnow_aware()` + 全仓 naive→aware 替换 | 追债 6 |
| 主目标 2 | 前后端契约护栏 | `_ARTIFACT_TYPE_MAP` value ↔ `ArtifactType` union 的 codegen 脚本 + `agent.ts` 局部 marker + 幂等校验门 | 追债 3 |

**验收判据**：
- 主目标 1：`grep -rn "utcnow_naive\|_to_naive_utc" backend/app backend/tests` → **0 命中**；migration upgrade + downgrade + upgrade 三连通过；pytest 131 passed / 1 skipped 不变。
- 主目标 2：`uv run python backend/scripts/gen_artifact_types.py && git diff --exit-code frontend/src/types/agent.ts` → **无 diff**（幂等）；`cd frontend && npm run build` 通过。

---

## §二 契约 · Part A（TIMESTAMPTZ 全量迁移）

### §2.1 影响列全清单（28 列 · 8 model 文件）

**必迁清单**（executor 不许自主删减，若遇某列迁移失败触发求助边界 #2）：

| # | 文件 | 列 |
|---|------|------|
| 1-2 | `backend/app/models/base.py:8-9` | `TimestampMixin.created_at` / `updated_at`（继承 9 张表 = 18 列） |
| 3 | `backend/app/models/skill.py:42` | `skill_versions.created_at` |
| 4 | `backend/app/models/skill.py:43` | `skill_versions.published_at` |
| 5 | `backend/app/models/skill.py:62` | `skill_execution_logs.executed_at` |
| 6-7 | `backend/app/models/task.py:42/45` | `tasks.started_at` / `finished_at` |
| 8-9 | `backend/app/models/execution.py:46/47` | `executions.started_at` / `finished_at` |
| 10-11 | `backend/app/models/match_score.py:44/47` | `match_scores.resume_updated_at_snapshot` / `jd_updated_at_snapshot` |
| 12 | `backend/app/models/candidate.py:115` | `candidate_status_history.occurred_at` |

TimestampMixin 继承 9 张表：`tasks / skills / resumes / match_scores / jd_templates / jds / executions / candidate_status_history / candidate_notes` → 18 列。
7 列 + 18 列 + 3 列 = **28 列**（skill_versions 不继承 mixin，独立带两列 + `executed_at`；`occurred_at` 独立）。

### §2.2 Migration 文件规范

- 文件名：`backend/alembic/versions/{revision_hex}_stage5_pr23_migrate_to_timestamptz.py`
- 单一 `upgrade()` / `downgrade()`，28 列在一个 revision 里 ALTER（事务原子）
- upgrade SQL 模板：`op.execute("ALTER TABLE {t} ALTER COLUMN {c} TYPE TIMESTAMP WITH TIME ZONE USING {c} AT TIME ZONE 'UTC'")`
- downgrade SQL 模板：对称 `TIMESTAMP WITHOUT TIME ZONE USING {c} AT TIME ZONE 'UTC'`
- **不动 default**（`func.now()` 保留），只改列类型

### §2.3 ORM Model 改动规范

所有 `DateTime()` → `DateTime(timezone=True)`（含 `func.now()` 默认值参数保持原状）。示例：

```python
# 改前
Mapped[datetime] = mapped_column(DateTime, default=func.now())
# 改后
Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
```

### §2.4 time.py 收敛

`backend/app/core/time.py` 迁移后：

```python
"""UTC-aware datetime helper. 单一入口，禁用 naive。"""
from datetime import UTC, datetime

def utcnow_aware() -> datetime:
    """Return current UTC time with tzinfo."""
    return datetime.now(UTC)
```

**删除**：`utcnow_naive()`、`_to_naive_utc()`、任何 `TZ_UTC` 变量、任何 deprecated alias。docstring 重写。

### §2.5 全仓替换清单（executor QUESTIONS §四 复现于此）

| 文件 | 命中 | 动作 |
|------|------|------|
| `app/core/time.py` | 5 | 只留 `utcnow_aware`；docstring 重写 |
| `app/agent/orchestrator/engine.py` | 9 | 全部 → `utcnow_aware()` |
| `app/services/match.py` | 7 | naive→aware；**4 处 `_to_naive_utc()` 快照比较改为直接 aware 比较**（Q4 重点复核 · STEP6 单章）；快照写入路径同步删除 `_to_naive_utc` 包裹 |
| `app/services/jd.py` | 5 | → `utcnow_aware()` |
| `app/services/resume.py` | 5 | → `utcnow_aware()` |
| `app/services/candidate.py` | 4 | → `utcnow_aware()` |
| `app/main.py` | 4 | → `utcnow_aware()` |
| `app/api/v1/agent.py` | 4 | → `utcnow_aware()` |
| `tests/factories.py` | 2 | → `utcnow_aware()` |
| `tests/api/test_agent_endpoints.py` | 6 | → `utcnow_aware()`；断言 isoformat 精确值若挂需微调 |
| `tests/test_stage5_pr20_executions.py` | 2 | → `utcnow_aware()` |

**验证**（收尾）：`grep -rn "utcnow_naive\|_to_naive_utc" backend/` → 0 命中（`backend/scripts/_cleanup_dev_db.py` 未跟踪，不算）。

---

## §三 契约 · Part B（codegen 护栏）

### §3.1 codegen 脚本骨架（backend/scripts/gen_artifact_types.py）

```python
"""生成 frontend/src/types/agent.ts 里的 ArtifactType union。

规则：union = sorted(_ARTIFACT_TYPE_MAP.values()) + 'generic'
（generic 是 engine.py:158 fallback，不在 map 里，硬编码追加。）
"""
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # backend/scripts → repo root
ENGINE = REPO_ROOT / "backend" / "app" / "agent" / "orchestrator" / "engine.py"
AGENT_TS = REPO_ROOT / "frontend" / "src" / "types" / "agent.ts"
MARK_START = "// <auto-gen-artifacttype-start>"
MARK_END = "// <auto-gen-artifacttype-end>"

def extract_map_values() -> list[str]:
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_ARTIFACT_TYPE_MAP":
                    if not isinstance(node.value, ast.Dict):
                        sys.exit("_ARTIFACT_TYPE_MAP 不是字典字面量")
                    values = []
                    for v in node.value.values:
                        if not isinstance(v, ast.Constant) or not isinstance(v.value, str):
                            sys.exit(f"_ARTIFACT_TYPE_MAP value 非字符串字面量: {ast.dump(v)}")
                        values.append(v.value)
                    return values
    sys.exit("未找到 _ARTIFACT_TYPE_MAP")

def build_union(values: list[str]) -> str:
    all_types = sorted(set(values) | {"generic"})
    return " | ".join(f"'{t}'" for t in all_types)

def main() -> None:
    values = extract_map_values()
    union = build_union(values)
    content = AGENT_TS.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(MARK_START) + r".*?" + re.escape(MARK_END),
        re.DOTALL,
    )
    if not pattern.search(content):
        sys.exit(f"marker 缺失于 {AGENT_TS}: {MARK_START} / {MARK_END}")
    replacement = (
        f"{MARK_START} — DO NOT EDIT. Run: uv run python backend/scripts/gen_artifact_types.py\n"
        f"export type ArtifactType = {union};\n"
        f"{MARK_END}"
    )
    new_content = pattern.sub(replacement, content)
    AGENT_TS.write_text(new_content, encoding="utf-8", newline="\n")
    print(f"OK · {AGENT_TS} · union = {union}")

if __name__ == "__main__":
    main()
```

**关键约束**：
- 纯 stdlib（`ast` + `re` + `pathlib` + `sys`），不 import app 包。
- 输出 `newline="\n"` + `encoding="utf-8"`（无 BOM）—— Windows CRLF 陷阱防御。
- marker 缺失 → `sys.exit(非零)`，不静默追加。
- map value 非字符串字面量 → `sys.exit`（触发求助边界 #4）。

### §3.2 agent.ts marker 改造

将 `frontend/src/types/agent.ts:71-77` 现有段落：

```ts
export type ArtifactType =
  | 'match_score'
  | 'jd'
  | 'resume'
  | 'candidate_merge'
  | 'candidate_profile'
  | 'generic';
```

替换为：

```ts
// <auto-gen-artifacttype-start> — DO NOT EDIT. Run: uv run python backend/scripts/gen_artifact_types.py
export type ArtifactType = 'candidate_merge' | 'candidate_profile' | 'generic' | 'jd' | 'match_score' | 'resume';
// <auto-gen-artifacttype-end>
```

**顺序变更 · 集合等价**（sorted 后字母序）——STEP6 报告说明"union 无序集合，TS type check 不受影响"。

### §3.3 README 里"新增 skill 三步走"指引段

添加位置：**根 `README.md`（由 PR-22 新建）**。若 PR-22 未合并，PR-23 落 `AGENTS.md` 尾部。DECISION 拟定内容：

```markdown
## 新增 skill 的三步走

1. **注册 skill** —— 在 `backend/app/skills/{skill_id}/` 新建 skill.yaml + python 实现（参考 `candidate-profile`）。
2. **更新 `_ARTIFACT_TYPE_MAP`** —— `backend/app/agent/orchestrator/engine.py:123` 添加 `tool_name → artifact_type`。
3. **跑 codegen** —— `uv run python backend/scripts/gen_artifact_types.py`，前端 `frontend/src/types/agent.ts` 的 ArtifactType union 自动同步；然后前端 `ResultCard.tsx` 加对应 `type` 分派 case。

**幂等校验**：PR 阶段人工跑 `uv run python backend/scripts/gen_artifact_types.py && git diff --exit-code frontend/src/types/agent.ts`，无 diff 通过。CI 化见 HANDOFF §9.3.14 追债。
```

---

## §四 用例 · 无新 TC（三门 + 断言微调）

- Part A 全量迁移是**类型改动 + 全仓替换**，无新增业务逻辑 → 不加 TC，靠现有 131 passed 覆盖 + 断言等价微调。
- Part B codegen 是**脚本 + 幂等校验**，无新增业务逻辑 → 不加 TC，靠幂等门覆盖。

若 executor 认为某处需专项 TC 兜底（例如 `_ARTIFACT_TYPE_MAP` 变动的正反向），可自主加，但**不算 KICKOFF 强制项**（DECISION 灵活度）。

---

## §五 commit 拆分（6 commits · Part B 先做）

| # | 类型 | 内容 |
|---|------|------|
| 1 | feat | Part B：`backend/scripts/gen_artifact_types.py` + `agent.ts` marker 改造（独立可回退，先绿一个门） |
| 2 | feat | Part A：Alembic migration `_stage5_pr23_migrate_to_timestamptz.py`（upgrade/downgrade 对称） |
| 3 | refactor | Part A：8 model 文件 `DateTime` → `DateTime(timezone=True)` 全量 + `time.py` 收敛为单一 `utcnow_aware()` |
| 4 | refactor | Part A：`app/` 层全仓 `utcnow_naive` → `utcnow_aware` 替换（engine/services/main/api） |
| 5 | refactor/test | Part A：`tests/` 层替换 + 断言等价微调（isoformat 后缀等） |
| 6 | docs | README/AGENTS "新增 skill 三步走" 指引段 |

commit 数 = 6，未超求助边界 #6（≤8）。

---

## §六 三门 + 额外门（6 门 · 门顺序严格）

**前置**：`cd backend && uv run alembic upgrade head`（非门本身，但 pytest 依赖）

| # | 门 | 命令 | 期望 |
|---|-----|------|------|
| 1 | pytest | `cd backend && uv run pytest -q` | **131 passed / 1 skipped**（不许下降；断言微调允许） |
| 2 | ruff | `cd backend && uv run ruff check .` | **All checks passed!** |
| 3 | frontend build | `cd frontend && npm run build` | **通过**（agent.ts marker 后 TS 必过） |
| 4 | frontend test | `cd frontend && npm run test` | **31 passed 不变**（附加·非门，防回归） |
| 5 | 迁移可逆 | `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` | 三连通过 |
| 6 | codegen 幂等 | `uv run python backend/scripts/gen_artifact_types.py && git diff --exit-code frontend/src/types/agent.ts` | **无 diff** |

STEP6 报告贴 6 门 tail + "断言变更清单"专章 + "match.py 快照比较复核"专章。

---

## §七 求助边界（stop-and-ask · 7 条）

触发以下任一即**停下报告、不擅自实现**：

1. Q1 若发现全迁过程中某列 ALTER 失败（如 `func.now()` 默认值与 timezone=True 冲突未预期），停下问指挥官，不改用半迁方案绕过。
2. `alembic downgrade -1` 失败或 upgrade↔downgrade 不对称（数据损失迹象）——停。
3. full pytest 出现 **> 10 处**测试因 tz 改动失败（预估个位数微调；超阈值说明影响面判断错误）——停。
4. `ast` 解析 `_ARTIFACT_TYPE_MAP` 时发现 map value 非纯字符串字面量（例如出现变量/表达式）——停，codegen 前提破裂。
5. agent.ts 中 marker 段落之外出现与 ArtifactType 耦合的手写类型需连带改动（超"局部生成"承诺）——停。
6. commit 数超 8。
7. **§9.4 未记新陷阱** —— 迁移期间遇 alembic/asyncpg 报错涉及未记录在 HANDOFF §9.4 的行为（默认值/时区隐式转换崩溃等），停，不"顺手 workaround"绕过（PR-20/21 的 §9.4 陷阱都是这样漏出的）。

---

## §八 base hash

`7198737`（PR-21 合入后的 master HEAD）

---

## §九 交付摘要模板（实现完填写）

```
分支：feat/pr-23-s51-p2-timestamptz-codegen
base：7198737
HEAD：<short hash>
三门 + 额外门：
  cd backend && uv run alembic upgrade head          # 前置
  uv run pytest -q                                    # 131 passed, 1 skipped
  uv run ruff check .                                 # All checks passed!
  cd frontend && npm run build                        # ✓ built
  uv run alembic upgrade head && downgrade -1 && upgrade head   # 三连通过
  uv run python backend/scripts/gen_artifact_types.py && git diff --exit-code frontend/src/types/agent.ts   # 无 diff

交付面：主目标 1（追债 6 全量迁 28 列 + time.py 收敛）+ 主目标 2（追债 3 codegen 护栏）
断言变更清单：X 处（详见 STEP6 §M）
match.py 快照比较复核：4 处（详见 STEP6 §N）
建议 HANDOFF 新增 §9.3.14（PR-23 建议追债 · CI 引入时接入 codegen 幂等校验）
```

---

## §十 备注

- **HANDOFF §9.3.14 新追债项**（本 PR 建议、由指挥官合并后落）：
  > **§9.3.14（PR-23 建议追债 · 未落地）** CI/pre-commit 引入时把 codegen 幂等校验编入 workflow：`uv run python backend/scripts/gen_artifact_types.py && git diff --exit-code`。当前仓库无 CI 基建，PR-23 只交付脚本本体，护栏靠人工/PR review 保证。

- **README 里"新增 skill 三步走"**：若 PR-22 已合并（含新 README），本 PR 落根 README；若 PR-22 未合，本 PR 落 `AGENTS.md` 尾部。STEP6 报告说明落到哪。

- **本 PR 与 PR-22（Track A）并行推进** —— 零文件重叠（B 碰 models/alembic/time.py/services/scripts/agent.ts；A 碰 layouts/App.tsx/新 docs），先合谁不阻塞后合谁。若 PR-22 先合，PR-23 拉最新 master rebase 后 README 里加"新增 skill 三步走"章节（如已有 `## 开发者指南` 分节则加入其下）。

- **MVP 数据全 UTC 假设**：R3 已定，PR-22 顺手加运维时区注意到 README/CHECKLIST，PR-23 不做。

---

*commander DECISION · 待批准后起分支实施*
