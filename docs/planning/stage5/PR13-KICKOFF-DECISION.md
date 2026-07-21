# PR-13 · SSE EventBuffer + Redis 接线 + Act→Redis 发射 · 启动裁定

> 关联：`docs/planning/stage5/PR13-KICKOFF-QUESTIONS.md` · 建议分支 `feat/pr-13-s5-03-07-sse-eventbuffer`
> 权威依据：`docs/planning/PLAN-STAGE5.md §Q5/Q6/Q7` · `docs/planning/TASKS-STAGE5.md §S5-03/§S5-07` · `docs/api-contract.md §3.5` · PR-12 STEP6 §附偏差 #2
> 生成时间：2026-07-21
> 状态：**9 问全部裁定（指挥官"全部采纳"）**，执行体可立即按 §十四 开工

---

## 一、前置状态确认

在给出裁定前先确认当前仓库状态（我已核验）：

| 项 | 状态 |
|---|---|
| master HEAD（本地 + 远端） | `039171e`（PR-12 STEP6 report 已合入 + push） |
| PR-12 分支（本地保留） | `feat/pr-12-s5-05-08-orchestrator` = `039171e`（与 master 同点） |
| PR-12 远端分支 | **已删除**（FF merge 后清理） |
| 本地 pytest | **92 passed**（73 既有 + 19 PR-12） |
| ruff（PR-12 相关目录） | 0 error |
| Redis 依赖 | `redis>=5.0.0` 已在 `pyproject.toml`；**未加** `redis[hiredis]` 生产 + `fakeredis` 测试 |
| `app/main.py` lifespan | 仅挂 MinIO buckets + Skill DB 同步，**未挂** `app.state.redis` |
| `app/core/redis.py` | 全局单例 `redis_client` + `get_redis()`（import 时构造，**无任何调用点**） |
| `engine.run_execute` | 占位实现（仅状态守卫，注释误写"PR-14"完成，本 PR 纠正） |
| `engine.run_reflect_act` | **未实现**（本 PR 补齐） |
| `act.py` emit 签名 | `Callable[[SSEEvent], Awaitable[None]]`（**docstring 与代码 drift**：说有 try/except、说 dataclass；实际都不是） |
| PR-12 §十二求助边界 | 5 种未触发，PR-12 遗留待 PR-13 处理项已列入本 §一 |

**结论**：分支基线干净（master = `039171e`，无需 rebase）；PR-12 遗留的 3 处 drift（run_execute 占位、run_reflect_act 缺失、emit try/except 缺失）由本 PR 一并修正。

---

## 二、Q1 · Redis 依赖注入位置

### 裁定：**采纳 —— `app.state.redis` + lifespan aclose；`app/core/redis.py` 改为 `get_redis(request)` DI 函数**

具体动作：

**`backend/app/main.py`** lifespan 内新增：
```python
from redis import asyncio as aioredis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 既有 MinIO / Skill 同步 ...
    app.state.redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield
    finally:
        await app.state.redis.aclose()
```

**`backend/app/core/redis.py`** 重写为：
```python
from fastapi import Request
from redis import asyncio as aioredis

def get_redis(request: Request) -> aioredis.Redis:
    """FastAPI 依赖注入函数，从 app.state 取 Redis 客户端。"""
    return request.app.state.redis
```

删除全局 `redis_client` 单例。**理由**：合并版 TASKS §S5-03 明写；shutdown 保证 aclose；测试可用 `app.state.redis = fakeredis.aioredis.FakeRedis()` 覆盖；PR-10/11/12 已跑绿的 92 用例**当前无任何 import 依赖此单例**（已 grep 核验），迁移零回归风险。

**兼容护栏**：若执行体在动手过程中发现有隐式 import 触发 `from app.core.redis import redis_client` 且不便清理，允许临时保留 `redis_client` 单例作 deprecated shim（打 FutureWarning），不阻塞交付；但**新代码禁止用**，PR-14 前必须清理。

---

## 三、Q2 · EventBuffer 接口设计

### 裁定：**采纳 —— 单类 EventBuffer，三方法，seq/timestamp 由 buffer 内部分配，不启 Pub/Sub**

**`backend/app/agent/orchestrator/event_buffer.py`** 新增：

```python
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any
from redis import asyncio as aioredis
from app.schemas.agent import SSEEvent, SSEEventType

logger = logging.getLogger(__name__)

BUFFER_MAXLEN = 200         # 环形裁剪上限（PLAN §Q6）
TERMINAL_TTL_SEC = 3600     # 终态后过期（PLAN §Q6）

def _events_key(task_id: str) -> str: return f"sse:buf:{task_id}"
def _seq_key(task_id: str) -> str:    return f"sse:seq:{task_id}"

class EventBuffer:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def append(
        self,
        task_id: str,
        event_type: SSEEventType,
        data: Any,
        step_id: str | None = None,
    ) -> SSEEvent:
        """分配 seq_id + timestamp，序列化写 Redis List，LTRIM 保 MAXLEN 条。"""
        seq_id = await self.redis.incr(_seq_key(task_id))
        ev = SSEEvent(
            id=str(seq_id),
            type=event_type,
            task_id=task_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data,
            step_id=step_id,
        )
        payload = ev.model_dump_json()
        pipe = self.redis.pipeline()
        pipe.rpush(_events_key(task_id), payload)
        pipe.ltrim(_events_key(task_id), -BUFFER_MAXLEN, -1)
        await pipe.execute()
        return ev

    async def read_after(
        self, task_id: str, last_event_id: int | None = None
    ) -> list[SSEEvent]:
        """last_event_id=None → 全量重放；否则返回 id > last_event_id 的事件。"""
        raw = await self.redis.lrange(_events_key(task_id), 0, -1)
        events = [SSEEvent.model_validate_json(x) for x in raw]
        if last_event_id is None:
            return events
        return [e for e in events if int(e.id) > last_event_id]

    async def set_terminal_ttl(self, task_id: str) -> None:
        """任务进入终态时调用，为 events / seq 键各设 TTL。"""
        await self.redis.expire(_events_key(task_id), TERMINAL_TTL_SEC)
        await self.redis.expire(_seq_key(task_id), TERMINAL_TTL_SEC)
```

**要点**：
- **seq_id 单调递增**：Redis `INCR sse:seq:{task_id}`（原子操作，跨进程安全）
- **timestamp**：`datetime.now(timezone.utc).isoformat()`（顺便替换 `datetime.utcnow()` 的 DeprecationWarning，见 §顺手清扫）
- **序列化**：`ev.model_dump_json()`（Pydantic v2 API），反序列化 `SSEEvent.model_validate_json()`
- **LTRIM 保容量**：`RPUSH + LTRIM(-200, -1)` 组合，保最近 200 条
- **不启 Pub/Sub**：PR-14 的 SSE 端点用 `read_after` + `asyncio.sleep(0.1)` 轮询实现进程内实时推（本 PR 不涉及）
- **过滤实现**：`read_after` 用 Python 侧过滤（简单直白）；LRANGE 全量拉最多 200 条数据量可控。**若执行过程中发现性能瓶颈**（触发 §十三 第 6 条求助），再讨论 `ZRANGEBYSCORE` 方案。

---

## 四、Q3 · Act ↔ EventBuffer 接线

### 裁定：**采纳 —— 保留 emit(SSEEvent) 回调，Engine 层做 adapter；顺手给 emit 加 try/except，修 docstring drift**

**`backend/app/agent/orchestrator/act.py`** 改动：

1. **docstring 修 drift**：把"SSEEvent dataclass"改为"SSEEvent Pydantic BaseModel"
2. **每个 emit 调用点用 helper 包 try/except**：
   ```python
   async def _safe_emit(emit: EmitFn, ev: SSEEvent) -> None:
       """emit 失败只 log warning，不中断业务（对齐 docstring 约定）。"""
       try:
           await emit(ev)
       except Exception as e:  # noqa: BLE001
           logger.warning("SSE emit failed for task=%s type=%s: %s",
                          ev.task_id, ev.type, e)
   ```
   替换 5 处 `await emit(...)` 为 `await _safe_emit(emit, ...)`
3. **`_make_event` 保留占位签名**：`id="evt"`、`timestamp=""` 仍作占位；**实际生产路径不再走 `_make_event`**（详见下方 adapter 覆盖）

**`backend/app/agent/orchestrator/engine.py`** Engine 层新增 adapter：

```python
class OrchestratorEngine:
    def __init__(self, ..., event_buffer: EventBuffer | None = None):
        # 既有字段 ...
        self.event_buffer = event_buffer

    def _make_emit(self, task_id: str) -> EmitFn:
        """构造 emit 回调：把 SSEEvent 桥接到 EventBuffer.append。
        
        由于 EventBuffer.append 负责分配 seq_id + timestamp，
        这里传入的 SSEEvent 的 id/timestamp 会被 append 内部覆盖。
        """
        if self.event_buffer is None:
            async def _noop(ev: SSEEvent) -> None: return None
            return _noop
        buffer = self.event_buffer
        async def _emit(ev: SSEEvent) -> None:
            await buffer.append(task_id, ev.type, ev.data, ev.step_id)
        return _emit
```

**要点**：
- `act.py` **无 signature 变更**（PR-12 的 5 个 `TC-S5-07-*` 用例不动就绿）
- `_safe_emit` helper 集中放在 `act.py` 内，5 处调用替换
- Engine 层 adapter **忽略入参 SSEEvent 的 id 和 timestamp**（buffer 内 INCR 分配），只用 `type/data/step_id`
- **`_make_event`保留但仅在 standalone 场景使用**（PR-12 测试用 mock emit 走这条路径，占位 id/timestamp 无害）

---

## 五、Q4 · `run_execute` 从占位到真跑

### 裁定：**采纳 —— asyncio.create_task 后台跑 Act + Reflect-Act；立即返回 EXECUTING；本 PR 一并实现 run_reflect_act；DB 交互留 PR-14**

**`engine.py`** `run_execute` 重写：

```python
async def run_execute(
    self,
    task_id: str,
    plan: dict[str, Any] | None = None,          # 由 PR-14 REST 层从 tasks 表读入并传入
    accepted_steps: list[str] | None = None,
    modifications: list[dict[str, Any]] | None = None,
    db: Any = None,
    event_buffer: EventBuffer | None = None,
) -> dict[str, Any]:
    """WAITING_CONFIRMATION → EXECUTING；后台跑 Act + Reflect-Act。"""
    check_transition(TaskStatus.WAITING_CONFIRMATION, TaskStatus.EXECUTING)
    buffer = event_buffer or self.event_buffer
    if plan is None:
        plan = {"steps": []}                     # PR-13 无 DB 读；PR-14 会从 tasks 表填
    # 应用 accepted_steps 过滤（若提供）
    if accepted_steps is not None:
        plan = {**plan, "steps": [
            s for s in (plan.get("steps") or [])
            if s.get("step_id") in accepted_steps
        ]}
    # 应用 modifications（若提供）
    if modifications:
        mod_map = {m["step_id"]: m.get("modified_params") for m in modifications}
        plan = {**plan, "steps": [
            {**s, "tool_input": mod_map.get(s.get("step_id"), s.get("tool_input") or s.get("args") or {})}
            if s.get("step_id") in mod_map else s
            for s in (plan.get("steps") or [])
        ]}
    # 后台跑（不阻塞 HTTP 响应）
    asyncio.create_task(
        self._background_execute(task_id, plan, buffer),
        name=f"orch-execute-{task_id}",
    )
    return {"status_code": 200, "status": "EXECUTING", "task_id": task_id}

async def _background_execute(
    self,
    task_id: str,
    plan: dict[str, Any],
    buffer: EventBuffer | None,
) -> None:
    """后台任务：跑 Act + Reflect-Act，收尾发 result 事件 + 设 TTL。"""
    from app.agent.orchestrator.act import run_act
    from app.schemas.agent import SSEEventType
    emit = self._make_emit(task_id) if buffer else None
    try:
        results = await asyncio.wait_for(
            run_act(plan, ctx={"task_id": task_id}, emit=emit, tool_router=self.tool_router),
            timeout=self.task_timeout_sec,
        )
        reflect_act_out = await self.run_reflect_act({
            "step_results": [
                {"step_id": r.step_id, "tool_name": r.tool_name,
                 "success": r.success, "output": r.output}
                for r in results
            ],
        })
        artifacts = _build_artifacts(results)     # 见 §七 Q6
        if buffer is not None:
            await buffer.append(task_id, SSEEventType.RESULT, {
                "content": reflect_act_out.get("final_result", ""),
                "artifacts": artifacts,
            })
            await buffer.set_terminal_ttl(task_id)
    except TimeoutError:
        if buffer is not None:
            await buffer.append(task_id, SSEEventType.ERROR, {
                "code": "TASK_TIMEOUT", "message": "task overall timeout",
                "recoverable": False,
            })
            await buffer.set_terminal_ttl(task_id)
    except Exception as e:  # noqa: BLE001 — 后台任务禁止抛异常
        logger.exception("background execute failed for task=%s", task_id)
        if buffer is not None:
            try:
                await buffer.append(task_id, SSEEventType.ERROR, {
                    "code": "INTERNAL_ERROR", "message": str(e),
                    "recoverable": False,
                })
                await buffer.set_terminal_ttl(task_id)
            except Exception:  # noqa: BLE001, S110
                pass

async def run_reflect_act(self, reflect_act_input: dict[str, Any]) -> dict[str, Any]:
    """调 orchestrator-reflect-act Skill，输出 final_result 供 result 事件用。"""
    skill = self.registry.get("orchestrator-reflect-act")
    if skill is None:
        return {"final_result": "", "issues": []}
    result = await skill.execute(reflect_act_input)
    if not result.success:
        return {"final_result": "", "issues": [result.error_message or "reflect-act failed"]}
    return result.output or {}
```

**`run_skip_to_score`** 同样接后台任务（bypass R-P-R，直接构造一个 `create_match_score` 步骤的 Plan）：

```python
async def run_skip_to_score(
    self, jd_id: str, candidate_ids: list[str],
    db: Any = None, event_buffer: EventBuffer | None = None,
) -> dict[str, Any]:
    try:
        await self.active_counter.incr()
    except TaskLimitExceededError:
        return {"status_code": 429, "error": "TASK_LIMIT_EXCEEDED"}
    task_id = f"task_skip_{jd_id}"               # PR-14 REST 层会用真 task_id 覆盖
    check_transition(TaskStatus.PENDING, TaskStatus.EXECUTING)
    plan = {"steps": [
        {"step_id": f"step_score_{i}",
         "tool_name": "create_match_score",
         "tool_input": {"jd_id": jd_id, "resume_id": cid}}
        for i, cid in enumerate(candidate_ids)
    ]}
    buffer = event_buffer or self.event_buffer
    asyncio.create_task(
        self._background_execute(task_id, plan, buffer),
        name=f"orch-skip-{task_id}",
    )
    # 注意：decr 在后台任务完成后触发；本 PR 用 try/finally 语义可能失效，
    # 采用后台任务收尾时 decr（见下方"active_counter 与后台任务协作"）
    return {"status_code": 200, "status": "EXECUTING",
            "jd_id": jd_id, "candidate_ids": candidate_ids}
```

**active_counter 与后台任务协作**（本裁定新增，配合 Q4）：
- `run_chat` 保持既有 `try/finally` decr（同步返回前 decr）
- `run_execute` / `run_skip_to_score` 后台任务模式：**在 `_background_execute` 结束时 decr**（不管成功、失败、超时都 decr），入口只 incr
- 实现方式：`_background_execute` 用 `try/finally: await self.active_counter.decr()` 包住整个后台流程

**要点**：
- **pytest 隔离风险**（KICKOFF §十一 第 2 条）：`asyncio.create_task` 在 pytest 中若测试函数返回时未 await 会挂在 event loop 上。**测试用法**：
  - 单元测试**不测**后台任务链路（`test_run_execute_returns_executing_immediately`）
  - 集成测试**显式 `await asyncio.sleep(0)` 让出**，或用 `await asyncio.gather(*[t for t in asyncio.all_tasks() if t.get_name().startswith("orch-")])` 收集完成
  - fakeredis fixture 在 teardown 前 gather 所有后台 task，避免泄漏
- **DB 交互留 PR-14**：`run_execute` 的 `plan` 参数由 PR-14 REST 层从 `tasks` 表读入；本 PR 用参数传入，测试用 in-memory dict
- **Reflect-Act Skill 已在 PR-12 落地**（`app/agent/skills/orchestrator_reflect_act/v1_0_0/`），本 PR 只在 engine 加 `run_reflect_act` 方法调用

---

## 六、Q5 · ActiveCounter 迁 Redis

### 裁定：**采纳 —— 本 PR 迁 Redis，保留 InMemory 供测试注入**

**`backend/app/agent/orchestrator/active_counter.py`** 追加：

```python
from redis import asyncio as aioredis
from app.agent.orchestrator.errors import TaskLimitExceededError

ACTIVE_KEY = "task:active"
ACTIVE_TTL_SEC = 3600       # 1h 无活动兜底防泄漏（PLAN §Q7）

class RedisActiveCounter:
    def __init__(self, redis: aioredis.Redis, limit: int = 10):
        self.redis = redis
        self.limit = limit

    async def incr(self) -> None:
        pipe = self.redis.pipeline()
        pipe.incr(ACTIVE_KEY)
        pipe.expire(ACTIVE_KEY, ACTIVE_TTL_SEC)
        results = await pipe.execute()
        current = results[0]
        if current > self.limit:
            await self.redis.decr(ACTIVE_KEY)    # 回滚
            raise TaskLimitExceededError(
                f"active tasks {current} > limit {self.limit}"
            )

    async def decr(self) -> None:
        # 用 DECR + max(0, ...) 语义，避免负数
        new_val = await self.redis.decr(ACTIVE_KEY)
        if new_val < 0:
            await self.redis.set(ACTIVE_KEY, 0)
```

**`engine.py`** 依赖注入选实现：

```python
# 构造时优先用注入的 active_counter，否则按 event_buffer 是否存在决定
if active_counter is None:
    if event_buffer is not None:
        active_counter = RedisActiveCounter(event_buffer.redis, limit=self.settings.task_active_limit)
    else:
        active_counter = InMemoryActiveCounter(limit=self.settings.task_active_limit)
```

**要点**：
- InMemory 保留：**测试用**，PR-12 的 `TC-S5-08-3`（并发 429）不动
- Redis 实现：`INCR + EXPIRE` 单 pipeline，减少 RTT；超限用 `DECR` 回滚
- TTL 兜底：1h 无活动自动清零，防进程 crash 未 decr
- **新增测试**：`TC-S5-13-01-redis-active-counter-429`（用 fakeredis 打满 10 触发 429）

---

## 七、Q6 · Result 事件 artifact schema 固化

### 裁定：**采纳 —— 固化 `{step_id, tool_name, type, ref_id?, data?}`，写回 api-contract §3.3；content = Reflect-Act.final_result**

**`docs/api-contract.md §3.3`** 追加（`result` 事件行详细说明段）：

```typescript
// §3.3 result 事件 data 结构（PR-13 写回）
interface ResultArtifact {
  step_id: string;                                 // 对应 PlanStep.step_id
  tool_name: string;                               // 触发该产物的工具名
  type: "match_score" | "resume" | "jd"
      | "candidate_merge" | "candidate_profile"
      | "generic";                                 // 前端据此决定卡片渲染
  ref_id?: string;                                 // 引用型产物（match_score / resume / jd）的主键 ID
  data?: any;                                      // type="generic" 时的原始 output
}

interface ResultData {
  content: string;                                 // Reflect-Act 生成的自然语言总结
  artifacts: ResultArtifact[];
}
```

**`engine.py`** 新增 `_build_artifacts` helper：

```python
# tool_name → artifact.type 的映射（内置工具白名单）
_ARTIFACT_TYPE_MAP: dict[str, str] = {
    "create_match_score": "match_score",
    "read_jd": "jd",
    "read_resume": "resume",
    "candidate-merge": "candidate_merge",
    "candidate-profile": "candidate_profile",
}

def _build_artifacts(results: list[StepResult]) -> list[dict[str, Any]]:
    """把 Act 各步 StepResult 映射为 ResultArtifact 列表。"""
    out: list[dict[str, Any]] = []
    for r in results:
        if not r.success or not r.output:
            continue
        artifact_type = _ARTIFACT_TYPE_MAP.get(r.tool_name, "generic")
        # ref_id 提取（match_score 用 output.match_score_id / resume 用 output.resume_id ...）
        ref_id = None
        if artifact_type == "match_score":
            ref_id = r.output.get("match_score_id") or r.output.get("id")
        elif artifact_type == "resume":
            ref_id = r.output.get("resume_id") or r.output.get("id")
        elif artifact_type == "jd":
            ref_id = r.output.get("jd_id") or r.output.get("id")
        item = {
            "step_id": r.step_id,
            "tool_name": r.tool_name,
            "type": artifact_type,
        }
        if artifact_type == "generic":
            item["data"] = r.output
        elif ref_id is not None:
            item["ref_id"] = str(ref_id)
        else:
            # 引用型但未提取到 ref_id → 降级为 generic
            item["type"] = "generic"
            item["data"] = r.output
        out.append(item)
    return out
```

**要点**：
- `content` 从 `run_reflect_act` 输出的 `final_result` 字段取（api-contract §5.6 已定义）
- `_ARTIFACT_TYPE_MAP` 内置在 engine.py（不动 `builtin_tools` 定义）
- 引用型 artifact 前端可解引用（如 `GET /match-scores/{ref_id}`）
- **`act.py` 内的 result 事件**（第 97-104 行）保留现有 `{step_id, result, artifacts}` 结构 —— 那是**步骤级** result 事件（每步跑完发一次），与本节讨论的**任务级**终态 result 事件是两个不同点位。任务级由 `_background_execute` 最后一次 `buffer.append(RESULT, ...)` 发出；步骤级不动。
  - ⚠️ **注意**：api-contract §3.3 表格里"`result` 触发时机=整个任务完成"—— **步骤级** result 事件与契约不完全对齐；PR-12 遗留问题。本 PR 不改 `act.py` 步骤级 result 结构（不破坏 PR-12 用例），但**写回 api-contract §3.3**时补一句"部分实现可能在步骤成功后发步骤级 result，最终仍以任务终态 result 为准"，语义兜底。

---

## 八、Q7 · 心跳寿命

### 裁定：**采纳 —— 心跳不进 EventBuffer，由 PR-14 SSE 端点层发帧；本 PR 只写死原则**

具体表现：

- 本 PR **无代码影响**
- 在 `event_buffer.py` docstring 内明确注释："心跳（`system` 事件、`{message:'heartbeat'}`）**不入 EventBuffer**；由 SSE HTTP 端点在 `StreamingResponse` 内每 15s 直接发帧（PR-14 落实）。"
- 在 `PR13-STEP6-REPORT.md` 中同步这一裁定，供 PR-14 kickoff 引用

**理由**（重申）：心跳不需要重放（重连时全部重发是浪费）；心跳不依赖 Redis（连接层职责）；`system` 事件用于"连接建立/重连/心跳"三类系统提示，业务事件缓冲不应混入。

---

## 九、Q8 · 测试策略

### 裁定：**采纳 —— fakeredis>=2.20.0；function scope 独立 instance；S5-03 独立测试文件 + S5-07 扩展**

**`backend/pyproject.toml`** dev 依赖追加：

```toml
[dependency-groups]
dev = [
    # ... 既有 ...
    "fakeredis>=2.20.0",
]
```

生产依赖优化（可选，若执行体空闲）：`redis>=5.0.0` → `redis[hiredis]>=5.0.0`（hiredis C 解析器，PLAN §5 建议）。**若追加 hiredis 编译失败**（Windows 无 C 编译器），触发 §十三 第 4 条求助边界，回退到纯 Python。

**`backend/tests/conftest.py`** 追加 fixture：

```python
import pytest
import fakeredis.aioredis as fakeasync

@pytest.fixture
async def fake_redis():
    """function scope 独立 fakeredis 实例，避免测试间污染。"""
    client = fakeasync.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()

@pytest.fixture
async def event_buffer(fake_redis):
    from app.agent.orchestrator.event_buffer import EventBuffer
    return EventBuffer(fake_redis)
```

**新增测试文件** `backend/tests/test_stage5_s5_13_event_buffer.py`（注：为避 PR-12 已入库的 `test_stage5_s5_0{3,7,8}_*.py` 命名冲突，用 S5-13 表示"PR-13 引入"，与合并版 TASKS §S5-13"前端页面"不冲突 —— 那是 frontend 测试文件、路径不同）：

⚠️ **PR-13 测试文件命名裁定**：由于 PR-12 已经把 `test_stage5_s5_03_*.py` 用掉的可能性存在（`grep test_stage5_s5_03` 需先核验），采用**功能命名**避冲突：

| 用例集 | 文件名 |
|---|---|
| EventBuffer 单元测试（TC-S5-13-01..08） | `test_stage5_s5_03_event_buffer.py`（**若与既有冲突改** `test_stage5_pr13_event_buffer.py`） |
| RedisActiveCounter 测试 | 并入 `test_stage5_pr13_event_buffer.py` 或既有 `test_stage5_s5_08_state_machine.py`（追加参数化） |
| Act ↔ EventBuffer 集成 | 扩展 `test_stage5_s5_07_act.py` 追加 1-2 用例 |
| run_execute 后台任务返回 EXECUTING | 扩展 `test_stage5_s5_08_state_machine.py` 或新建 `test_stage5_pr13_execute.py` |

**执行体先 `ls tests/ | grep s5_03`**：若无冲突用 `test_stage5_s5_03_event_buffer.py`（与合并版 S5-03 编号对齐）；若冲突用 `test_stage5_pr13_event_buffer.py`。**自主决策**。

**用例矩阵**（对齐合并版 TEST-PLAN §TC-S5-03-1..5，本 PR 落地 5 个 + 扩展 2-3 个）：

| TC | 断言 |
|---|---|
| TC-S5-03-1 | `append` 后 `read_after(None)` 返回全量、按 seq_id 升序 |
| TC-S5-03-2 | `read_after(N)` 只返回 id > N 的事件 |
| TC-S5-03-3 | 连续 append 250 条后，`llen == 200`（LTRIM 生效） |
| TC-S5-03-4 | `set_terminal_ttl` 后 `ttl(events_key) > 0` 且 `<= 3600` |
| TC-S5-03-5 | 并发两个 append（`asyncio.gather`），seq_id 无重复（INCR 原子性） |
| TC-S5-13-active-1 | `RedisActiveCounter` 打满 10 触发 429 且 counter 不涨 |
| TC-S5-13-active-2 | `RedisActiveCounter.decr` 到 -1 时钳位到 0 |
| TC-S5-13-execute-1 | `run_execute` 立即返回 EXECUTING，后台 task 已注册（`asyncio.all_tasks()` 含 `orch-execute-*`） |
| TC-S5-13-execute-2 | 后台任务完成后 `RESULT` 事件已入 buffer，`content` 非空，`artifacts` 结构符合 §七 |

**PR-12 用例护栏**：既有 `test_stage5_s5_0{5,6,7,8}_*.py` 22 项**保持全绿**，不允许 signature 变更导致回归。

---

## 十、Q9 · Commit 拆分

### 裁定：**采用 5-commit 精简版**（对齐 PR-12 精简版）

```
1. C_RED   test(stage5): PR-13 red test skeleton (S5-03 EventBuffer + PR-13 extensions)
2. C_INFRA infra(stage5): +fakeredis / lifespan 挂 app.state.redis / get_redis DI 重构
3. C_BUF   feat(stage5): S5-03 EventBuffer (append/read_after/set_terminal_ttl) + tests
4. C_ACT   feat(stage5): S5-07 wire EventBuffer via engine adapter + emit try/except 修正
5. C_EXEC  feat(stage5): S5-07 run_execute 后台任务 + run_reflect_act + result artifacts schema
6. C_COUNT feat(stage5): S5-08 RedisActiveCounter (INCR/DECR + TTL 兜底) + tests
7. C_DOCS  docs: api-contract §3.3 固化 result artifact schema + kickoff decision 归档
```

（写成 7 条更清晰；若历史过细也接受合并 C_INFRA + C_BUF、C_ACT + C_EXEC 为 5 条）

**执行体自主选择** 7-commit 精细版或 5-commit 精简版，历史清晰性优先。

---

## 十一、目录与文件清单

```
backend/
  pyproject.toml                                          [MOD] +fakeredis dev dep
  app/
    main.py                                               [MOD] lifespan 挂 app.state.redis
    core/
      redis.py                                            [REWRITE] get_redis(request) DI
    agent/orchestrator/
      event_buffer.py                                     [NEW] EventBuffer 类
      active_counter.py                                   [MOD] +RedisActiveCounter
      act.py                                              [MOD] emit try/except + docstring
      engine.py                                           [MOD] run_execute 真跑 + run_reflect_act
                                                                + _make_emit adapter
                                                                + _build_artifacts helper
  tests/
    conftest.py                                           [MOD] +fake_redis / event_buffer fixture
    test_stage5_s5_03_event_buffer.py                     [NEW] TC-S5-03-1..5 (若冲突改名)
    test_stage5_pr13_execute.py                           [NEW] TC-S5-13-execute-1..2
                                                                + TC-S5-13-active-1..2
    test_stage5_s5_07_act.py                              [MOD] 追加 EventBuffer 集成断言
docs/
  api-contract.md                                         [MOD] §3.3 固化 ResultArtifact
  planning/stage5/
    PR13-KICKOFF-DECISION.md                              [NEW] 本文件
    PR13-STEP6-REPORT.md                                  [NEW] PR-13 收尾报告
```

---

## 十二、顺手清扫（本 PR 内完成，不单独立项）

对齐合并版 TASKS-STAGE5 §五"顺手清扫"表：

| 项 | 出处 | 本 PR 动作 |
|---|---|---|
| `datetime.utcnow()` → `datetime.now(timezone.utc)` 全仓替换（Stage 4 遗留） | 合并版 TASKS §五 归属 PR-10 | **PR-10 未处理**，PR-13 顺手处理 `app/services/match.py` + `app/main.py:34,43,44` + `backend/tests/test_match_service.py:168` |
| `act.py` docstring drift（SSEEvent dataclass → BaseModel、try/except 缺失） | 本 PR 前置事实 | 修正 docstring + 加 `_safe_emit` helper（§四已裁定） |
| `engine.py` `run_execute` 注释误写"PR-14 完成" | 本 PR 前置事实 | 改注释为"PR-13 完成，DB 交互留 PR-14" |
| `app/core/redis.py` 全局单例死代码 | 本 PR 前置事实 | 重写为 `get_redis(request)` DI（§二已裁定） |

**⚠️ `datetime.utcnow()` 替换护栏**：全仓 grep `datetime.utcnow`，逐一改为 `datetime.now(timezone.utc)`。**排除**：`.venv/`、`.git/`、`backend/alembic/versions/`（历史迁移文件不改）。改完再跑 `uv run pytest` 确认无回归。

---

## 十三、求助边界（触发即停）

除本 DECISION 覆盖的 9 问，遇到以下情况**立即停下汇报**：

1. **fakeredis 与真 Redis Pub/Sub 行为差异**：虽然本 PR 不用 Pub/Sub，但若发现 `INCR/EXPIRE/LTRIM/LRANGE` 在 fakeredis 与真 Redis 上行为不一致（例如 pipeline 语义差异导致 seq_id 竞态），先来问
2. **`asyncio.create_task` 在 pytest 中泄漏或 CI hang**：若 `test_run_execute_returns_executing_immediately` 后 pytest 卡住不退出，先来问再改测试模式
3. **PR-12 遗留的 emit 无 try/except 修正影响既有用例**：若加 `_safe_emit` 后 `test_stage5_s5_07_act.py` 的 5 个用例任意一条变红，先来问再改
4. **`redis[hiredis]` 在 Windows 编译失败**：回退到纯 Python `redis>=5.0.0`，把 `hiredis` 挪到 optional-dependencies（若 pyproject.toml 支持）
5. **`app/core/redis.py` 全局单例被 PR-10/11/12 已有代码隐式引用**：迁移前跑一次 `uv run pytest` 若报错 `AttributeError: 'FastAPI' object has no attribute 'state.redis'` 或类似，先来问
6. **EventBuffer `read_after` 用 LRANGE 全量 + Python 侧过滤**发现性能瓶颈（如某测试 append 上千条后 `read_after` 超过 500ms），先来问再讨论 `ZRANGEBYSCORE` 方案
7. **`_build_artifacts` 的 tool_name 映射**发现某个内置工具无法归类到 5 种 type 之一（如新加的 `internal-analyze`），先来问再决定是加映射还是保 `generic`
8. **既有 `datetime.utcnow()` 替换发生**在时区敏感的比较处（如 `is_stale_when_resume_updated_after_score`），若替换后测试变红，先来问

**自主决策边界**（不必问）：
- EventBuffer 内部键命名细节（`sse:seq:{id}` vs `seq:sse:{id}` 等）
- fakeredis fixture 具体命名与 scope
- ruff / import 排序
- log 语句措辞与级别
- 测试文件命名冲突时用 `pr13` 前缀 vs `s5_03` 前缀（自查后决定）

---

## 十四、执行体行动清单

```
1. 阅读本 DECISION（当前文件）
2. 在 feat/pr-13-s5-03-07-sse-eventbuffer 分支上（从 master=039171e 分出）：
   a. C_RED — 写红测试骨架（8 用例 skip 或 xfail）
   b. C_INFRA — 加 fakeredis 依赖 + main.py lifespan 挂 app.state.redis + core/redis.py 重写
   c. C_BUF — 实现 EventBuffer（§三 完整代码），跑绿 TC-S5-03-1..5
   d. C_ACT — engine._make_emit adapter + act.py `_safe_emit` + docstring 修正
   e. C_EXEC — engine.run_execute 后台任务 + run_reflect_act + _build_artifacts；跑绿 TC-S5-13-execute-*
   f. C_COUNT — RedisActiveCounter；跑绿 TC-S5-13-active-*
   g. C_DOCS — 写回 api-contract.md §3.3 + 本 DECISION 归档
   h. 顺手清扫 datetime.utcnow() 替换
   i. 三道门验收（下方 §十五）
3. Push：sleep 15 && git push -u origin feat/pr-13-s5-03-07-sse-eventbuffer
   （SSH port 22 超时按 PR-10/11/12/15 经验重试）
4. 生成 docs/planning/stage5/PR13-STEP6-REPORT.md（沿用 PR-12 STEP6 模板）
5. 汇报"PR-13 已 push + STEP6 报告已就位，待核验放行 FF merge"
```

---

## 十五、验收三道门（PR-13）

| 门 | 命令 | 期望 |
|---|---|---|
| 门 1 | `cd backend && uv run pytest tests/test_stage5_s5_03_event_buffer.py tests/test_stage5_pr13_execute.py tests/test_stage5_s5_07_act.py -q` | **全绿**（新增 8-10 用例 + PR-12 既有 5 用例 = 13-15 passed） |
| 门 2 | `cd backend && uv run pytest -q` | **全绿**（92 + 新增，无回归） |
| 门 3 | `cd backend && uv run ruff check app/agent/orchestrator/ app/core/redis.py app/main.py` | **0 error** |

**门 2 基线增长**：92（PR-12 后）→ 预计 **100-105 passed**（+8-13 新增）。

---

**开始动工**。裁定覆盖 9 问；遇 §十三 8 种情况**立即停下**，其他自主决策。
